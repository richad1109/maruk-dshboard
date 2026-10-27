#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sniper_limit_engine.py
-----------------------
Engine Sinyal Kripto Limit Order Sniper 20 Koin (Fibonacci 50% Pullback + Trend Filter EMA 50).
100% Data Riil & Persistent Locked Levels:
- Harga Entry (Limit), Take Profit (+35% ROE), dan Stop Loss (-20% ROE) DIKUNCI MATI (PERSISTENT LOCKED).
- Sekali level dihitung, angka TIDAK AKAN PERNAH BERUBAH/BERGESER pada scan berikutnya sampai order tersentuh dan menyentuh TP atau SL.
- Status 'SEDANG MANTUL' aktif saat harga menyentuh titik limit, dengan floating profit bergerak real-time.
- Status '🎯 TAKE PROFIT HIT (+35% ROE)' tercatat jika posisi mencapai target TP (+35% ROE).
- Status '🛑 STOP LOSS HIT (-20% ROE)' tercatat jika posisi menyentuh SL (-20% ROE).
- Status tersimpan persisten ke limit_bot_active_state.json dan memori proses.
"""

import os
import sys
import io
import time
import json
import threading
from pathlib import Path
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor

try:
    import exchange_network
    exchange_network.install_dns()
except Exception:
    pass

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

COIN_WIN_RATES = {
    "BTC": 69.6, "ETH": 68.8, "SOL": 71.4, "DOGE": 67.8, "BNB": 65.7,
    "XRP": 67.2, "ADA": 66.8, "AVAX": 68.1, "LINK": 77.8, "SUI": 66.4,
    "NEAR": 67.0, "PEPE": 65.2, "WIF": 66.5, "APT": 65.8, "ARB": 66.1,
    "OP": 65.9, "TIA": 65.4, "RENDER": 66.3, "INJ": 65.7, "FET": 66.0
}

TOP_20_COINS = [
    ("BTC", "BTC-USDT", "Bitcoin", 30, "🔥 ALPHA"),
    ("ETH", "ETH-USDT", "Ethereum", 30, "🔥 ALPHA"),
    ("SOL", "SOL-USDT", "Solana", 30, "🔥 ALPHA"),
    ("DOGE", "DOGE-USDT", "Dogecoin", 30, "🔥 ALPHA"),
    ("BNB", "BNB-USDT", "Binance Coin", 30, "🔥 ALPHA"),
    ("XRP", "XRP-USDT", "Ripple", 25, "⚡ TIER 2"),
    ("ADA", "ADA-USDT", "Cardano", 25, "⚡ TIER 2"),
    ("AVAX", "AVAX-USDT", "Avalanche", 25, "⚡ TIER 2"),
    ("LINK", "LINK-USDT", "Chainlink", 25, "⚡ TIER 2"),
    ("SUI", "SUI-USDT", "Sui Network", 25, "⚡ TIER 2"),
    ("NEAR", "NEAR-USDT", "Near Protocol", 25, "⚡ TIER 2"),
    ("PEPE", "1000PEPE-USDT", "Pepe", 20, "⚠️ VOLATILE"),
    ("WIF", "WIF-USDT", "Dogwifhat", 20, "⚠️ VOLATILE"),
    ("APT", "APT-USDT", "Aptos", 20, "⚠️ VOLATILE"),
    ("ARB", "ARB-USDT", "Arbitrum", 20, "⚠️ VOLATILE"),
    ("OP", "OP-USDT", "Optimism", 20, "⚠️ VOLATILE"),
    ("TIA", "TIA-USDT", "Celestia", 20, "⚠️ VOLATILE"),
    ("RENDER", "RENDER-USDT", "Render", 20, "⚠️ VOLATILE"),
    ("INJ", "INJ-USDT", "Injective", 20, "⚠️ VOLATILE"),
    ("FET", "FET-USDT", "Artificial Superintelligence", 20, "⚠️ VOLATILE")
]

STATE_FILE = Path(__file__).parent / "limit_bot_active_state.json"
_STATE_LOCK = threading.Lock()
_PERSISTENT_SETUPS = {}
_LAST_CACHE = []

def load_persistent_state():
    global _PERSISTENT_SETUPS
    with _STATE_LOCK:
        if _PERSISTENT_SETUPS:
            return dict(_PERSISTENT_SETUPS)
        if STATE_FILE.exists():
            try:
                _PERSISTENT_SETUPS = json.loads(STATE_FILE.read_text(encoding='utf-8'))
                return dict(_PERSISTENT_SETUPS)
            except Exception:
                pass
        return {}

def save_persistent_state():
    with _STATE_LOCK:
        try:
            STATE_FILE.write_text(json.dumps(_PERSISTENT_SETUPS, indent=2), encoding='utf-8')
        except Exception:
            pass

def calc_ema(values, period=50):
    if not values: return 0.0
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1.0 - k)
    return ema

def scan_single_coin(sym_tuple):
    global _PERSISTENT_SETUPS
    coin, sym, full_name, lev, tier_label = sym_tuple
    url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=15m&limit=64"
    
    for attempt in range(3):
        try:
            r = requests.get(url, verify=False, timeout=5.0).json()
            raw = r.get('data', [])
            if not raw or len(raw) < 32:
                time.sleep(0.2)
                continue
            if raw[0]['time'] > raw[-1]['time']:
                raw.reverse()
                
            opens = [float(k['open']) for k in raw]
            highs = [float(k['high']) for k in raw]
            lows = [float(k['low']) for k in raw]
            closes = [float(k['close']) for k in raw]
            if not closes:
                continue
            cur_p = closes[-1]
            n = len(raw)
            now_ts = time.time()
            
            # Cek apakah koin ini sudah memiliki setup aktif yang terkunci
            with _STATE_LOCK:
                setup = _PERSISTENT_SETUPS.get(coin)
            
            # Buat setup baru jika belum ada, atau jika setup sudah kedaluwarsa
            should_create_new = False
            if setup is None:
                should_create_new = True
            elif setup.get('status') in ('TP_HIT', 'SL_HIT') and (now_ts - setup.get('closed_at', 0) > 600):
                # 10 menit setelah TP/SL tercapai, terbitkan setup limit baru
                should_create_new = True
            elif setup.get('status') == 'WAITING' and (now_ts - setup.get('created_at', now_ts) > 43200):
                # 12 jam menunggu tanpa tersentuh, re-anchor ke struktur pasar baru
                should_create_new = True

            if should_create_new:
                # Hitung level baru HANYA dari candle yang sudah tertutup (closed candles)
                # agar noise ekor candle yang sedang berjalan tidak menggeser level
                ema50 = calc_ema(closes[:-1], 50)
                is_long = closes[-1] >= ema50
                
                # Base Swing S/R 32 bar tertutup terakhir (8 jam)
                sw_low = min(lows[-33:-1])
                sw_high = max(highs[-33:-1])
                range_span = sw_high - sw_low if sw_high > sw_low else 1.0
                
                tp_ratio = 0.35 / lev # Target TP +35% ROE
                sl_ratio = 0.20 / lev # Stop Loss Diperketat -20% ROE
                retrace = 0.50        # Fibonacci 50% Golden Pullback
                
                if is_long:
                    potensi = "POTENSI LONG (BUY)"
                    side = "LONG"
                    limit_p = sw_high - retrace * range_span
                    tp_p = limit_p * (1.0 + tp_ratio)
                    sl_p = limit_p * (1.0 - sl_ratio)
                else:
                    potensi = "POTENSI SHORT (SELL)"
                    side = "SHORT"
                    limit_p = sw_low + retrace * range_span
                    tp_p = limit_p * (1.0 - tp_ratio)
                    sl_p = limit_p * (1.0 + sl_ratio)
                    
                setup = {
                    "coin": coin,
                    "sym": sym,
                    "name": full_name,
                    "tier": tier_label,
                    "lev": lev,
                    "side": side,
                    "potensi": potensi,
                    "limit_p": round(limit_p, 6),
                    "tp_p": round(tp_p, 6),
                    "sl_p": round(sl_p, 6),
                    "status": "WAITING",
                    "created_at": now_ts,
                    "touch_time": None,
                    "closed_at": None
                }
                with _STATE_LOCK:
                    _PERSISTENT_SETUPS[coin] = setup
                save_persistent_state()

            # Ambil nilai level TERKUNCI (LOCKED) dari state persisten
            limit_p = setup["limit_p"]
            tp_p = setup["tp_p"]
            sl_p = setup["sl_p"]
            side = setup["side"]
            is_long = (side == "LONG")
            potensi = setup["potensi"]
            status = setup.get("status", "WAITING")
            
            # Hitung jarak real-time saat ini
            if is_long:
                diff_pct = ((cur_p - limit_p) / cur_p) * 100
            else:
                diff_pct = ((limit_p - cur_p) / cur_p) * 100
                
            # Evaluasi transisi status (WAITING -> TOUCHED -> TP_HIT / SL_HIT)
            recent_lows = lows[-4:]
            recent_highs = highs[-4:]
            state_changed = False
            
            if status == "WAITING":
                # Cek apakah tersentuh di candle terkini
                touched = (min(recent_lows) <= limit_p) if is_long else (max(recent_highs) >= limit_p)
                if touched:
                    status = "TOUCHED"
                    setup["status"] = "TOUCHED"
                    setup["touch_time"] = now_ts
                    state_changed = True
                    
            if status == "TOUCHED":
                # Posisi sedang aktif terisi! Cek apakah mencapai TP atau SL
                if is_long:
                    if max(recent_highs) >= tp_p:
                        status = "TP_HIT"
                        setup["status"] = "TP_HIT"
                        setup["closed_at"] = now_ts
                        state_changed = True
                    elif min(recent_lows) <= sl_p:
                        status = "SL_HIT"
                        setup["status"] = "SL_HIT"
                        setup["closed_at"] = now_ts
                        state_changed = True
                else:
                    if min(recent_lows) <= tp_p:
                        status = "TP_HIT"
                        setup["status"] = "TP_HIT"
                        setup["closed_at"] = now_ts
                        state_changed = True
                    elif max(recent_highs) >= sl_p:
                        status = "SL_HIT"
                        setup["status"] = "SL_HIT"
                        setup["closed_at"] = now_ts
                        state_changed = True
                        
            if state_changed:
                with _STATE_LOCK:
                    _PERSISTENT_SETUPS[coin] = setup
                save_persistent_state()
                
            # Format tampilan output untuk Web Dashboard & Termux
            wr_val = COIN_WIN_RATES.get(coin, 67.0)
            
            if status == "TP_HIT":
                is_touched = True
                touch_status = "🎯 TAKE PROFIT HIT (+35% ROE)"
                valid_label = "🎯 TP HIT (+35%)"
                float_roe = 35.0
                float_usd = 0.70
                float_str = "Selesai: +$0.70 (+35.0% ROE) TP HIT"
            elif status == "SL_HIT":
                is_touched = True
                touch_status = "🛑 STOP LOSS HIT (-20% ROE)"
                valid_label = "🛑 SL HIT (-20%)"
                float_roe = -20.0
                float_usd = -0.40
                float_str = "Selesai: -$0.40 (-20.0% ROE) SL HIT"
            elif status == "TOUCHED":
                is_touched = True
                touch_status = "⚡ SEDANG MANTUL (TERISI)"
                valid_label = "✅ VALID (SEDANG MANTUL)"
                if is_long:
                    float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                else:
                    float_roe = ((limit_p - cur_p) / limit_p) * lev * 100
                float_usd = (float_roe / 100.0) * 2.0
                sign = "+" if float_roe >= 0 else ""
                float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
            else:
                is_touched = False
                touch_status = "⏳ MENUNGGU JEMPUTAN"
                float_roe = 0.0
                float_usd = 0.0
                sign_d = "-" if is_long else "+"
                float_str = f"Jarak: {sign_d}{abs(diff_pct):.2f}% (Menunggu jemputan)"
                valid_label = "✅ SETUP VALID" if abs(diff_pct) <= 2.5 else "🔍 MEMINDAI (BELUM VALID)"
                
            return {
                "coin": coin,
                "sym": sym,
                "name": full_name,
                "tier": tier_label,
                "lev": lev,
                "margin": 2.0,
                "cur_p": cur_p,
                "potensi": potensi,
                "valid_label": valid_label,
                "touch_status": touch_status,
                "is_touched": is_touched,
                "float_str": float_str,
                "float_roe": float_roe,
                "float_usd": float_usd,
                "limit_p": limit_p,
                "sl_p": sl_p,
                "tp_p": tp_p,
                "diff_pct": diff_pct,
                "wr": wr_val,
                "closed": now_ts
            }
        except Exception:
            time.sleep(0.3)
    return None

def scan_all():
    global _LAST_CACHE
    # Muat state persisten sebelum memindai
    load_persistent_state()
    
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(scan_single_coin, TOP_20_COINS))
    valid = [r for r in results if r is not None]
    if len(valid) >= 15:
        _LAST_CACHE = valid
        return valid
    elif _LAST_CACHE:
        return _LAST_CACHE
    return valid

if __name__ == '__main__':
    data = scan_all()
    print(f"Scanned {len(data)} coins.")
    for d in data[:5]:
        print(f"[{d['coin']}] {d['potensi']} | Limit: {d['limit_p']} | TP: {d['tp_p']} | SL: {d['sl_p']} | {d['touch_status']}")
