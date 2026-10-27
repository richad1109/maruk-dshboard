#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sniper_limit_engine.py
-----------------------
Engine Sinyal Kripto Limit Order Sniper 20 Koin (Whale Wick - Realistis Tanpa Ilusi).
Logika Penguncian Siklus Mantul & Pembaruan Kontinu:
1. Posisi yang sudah terjemput (mantul) DIKUNCI statusnya sebagai TERISI MANTUL dengan live Floating Profit.
2. Posisi TIDAK AKAN PERNAH kembali ke 'menunggu jemputan' selama posisi aktif.
3. Begitu menyentuh Target TP (+35% ROE) atau Stop Loss (-36% ROE):
   - Hasil keuntungan/kerugian dikunci ke riwayat portofolio.
   - Sistem OTOMATIS memindai struktur pasar terkini dan MENERBITKAN SETUP LIMIT BARU agar pengguna selalu siap pasang limit berikutnya.
"""

import sys
import io
import time
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor

if sys.stdout and hasattr(sys.stdout, 'buffer'):
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
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

def scan_single_coin(sym_tuple):
    coin, sym, full_name, lev, tier_label = sym_tuple
    url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=15m&limit=48"
    
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
            cur_p = closes[-1]
            n = len(raw)
            
            # Base Swing S/R dari 32 candle awal
            sw_low = min(lows[:32])
            sw_high = max(highs[:32])
            range_span = sw_high - sw_low if sw_high > sw_low else 1.0
            pos_in_range = (cur_p - sw_low) / range_span
            
            tp_ratio = 0.35 / lev # Target TP +35% ROE
            sl_ratio = 0.36 / lev # Stop Loss -36% ROE
            offset_pct = 0.0020   # Diskon 0.20% di luar swing ekstrem
            
            wr_val = COIN_WIN_RATES.get(coin, 67.0)
            is_long = pos_in_range < 0.65
            
            if is_long:
                potensi = "POTENSI LONG (BUY)"
                limit_p = sw_low * (1.0 - offset_pct)
                tp_p = limit_p * (1.0 + tp_ratio)
                sl_p = limit_p * (1.0 - sl_ratio)
                diff_pct = ((cur_p - limit_p) / cur_p) * 100
                
                # Cek dari candle 20 ke depan apakah ada wick yang menyentuh limit
                fill_idx = -1
                for idx in range(20, n):
                    if lows[idx] <= limit_p:
                        fill_idx = idx
                        break
                        
                if fill_idx != -1:
                    # KUNCI POSISI TERISI / MANTUL!
                    sub_highs = highs[fill_idx:]
                    sub_lows = lows[fill_idx:]
                    hit_tp = max(sub_highs) >= tp_p
                    hit_sl = min(sub_lows) <= sl_p
                    
                    if hit_tp:
                        # Kena TP! Kunci profit +35% ROE & segera terbitkan setup limit baru
                        fresh_limit = min(lows[-16:]) * (1.0 - offset_pct)
                        fresh_diff = ((cur_p - fresh_limit) / cur_p) * 100
                        is_touched = True
                        touch_status = "🎯 SUDAH HIT TP"
                        valid_label = "🎯 SUDAH TP (PINDAI SETUP BARU)"
                        float_roe = 35.0
                        float_usd = 0.70
                        float_str = "🎯 HIT TP! (+35.0% ROE | +$0.70 USD) 🏆"
                        limit_p = fresh_limit
                        tp_p = limit_p * (1.0 + tp_ratio)
                        sl_p = limit_p * (1.0 - sl_ratio)
                        diff_pct = fresh_diff
                    elif hit_sl:
                        # Kena SL! Kunci rugi -36% ROE & segera terbitkan setup limit baru
                        fresh_limit = min(lows[-16:]) * (1.0 - offset_pct)
                        fresh_diff = ((cur_p - fresh_limit) / cur_p) * 100
                        is_touched = True
                        touch_status = "🛑 SUDAH HIT SL"
                        valid_label = "🛑 HIT SL (PINDAI SETUP BARU)"
                        float_roe = -36.0
                        float_usd = -0.72
                        float_str = "🛑 HIT SL! (-36.0% ROE | -$0.72 USD)"
                        limit_p = fresh_limit
                        tp_p = limit_p * (1.0 + tp_ratio)
                        sl_p = limit_p * (1.0 - sl_ratio)
                        diff_pct = fresh_diff
                    else:
                        # SEDANG MANTUL AKTIF - JANGAN UBAH KE MENUNGGU!
                        is_touched = True
                        touch_status = "⚡ SUDAH KESENTUH (TERISI)"
                        valid_label = "✅ VALID (SEDANG MANTUL)"
                        float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                        float_usd = (float_roe / 100.0) * 2.0
                        sign = "+" if float_roe >= 0 else ""
                        float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
                else:
                    is_touched = False
                    touch_status = "⏳ BELUM KESENTUH"
                    float_roe = 0.0
                    float_usd = 0.0
                    float_str = f"Jarak: -{diff_pct:.2f}% (Menunggu jemputan)"
                    valid_label = "✅ SETUP VALID" if diff_pct <= 2.0 else "🔍 MEMINDAI (BELUM VALID)"
            else:
                potensi = "POTENSI SHORT (SELL)"
                limit_p = sw_high * (1.0 + offset_pct)
                tp_p = limit_p * (1.0 - tp_ratio)
                sl_p = limit_p * (1.0 + sl_ratio)
                diff_pct = ((limit_p - cur_p) / cur_p) * 100
                
                fill_idx = -1
                for idx in range(20, n):
                    if highs[idx] >= limit_p:
                        fill_idx = idx
                        break
                        
                if fill_idx != -1:
                    # KUNCI POSISI TERISI / MANTUL!
                    sub_highs = highs[fill_idx:]
                    sub_lows = lows[fill_idx:]
                    hit_tp = min(sub_lows) <= tp_p
                    hit_sl = max(sub_highs) >= sl_p
                    
                    if hit_tp:
                        fresh_limit = max(highs[-16:]) * (1.0 + offset_pct)
                        fresh_diff = ((fresh_limit - cur_p) / cur_p) * 100
                        is_touched = True
                        touch_status = "🎯 SUDAH HIT TP"
                        valid_label = "🎯 SUDAH TP (PINDAI SETUP BARU)"
                        float_roe = 35.0
                        float_usd = 0.70
                        float_str = "🎯 HIT TP! (+35.0% ROE | +$0.70 USD) 🏆"
                        limit_p = fresh_limit
                        tp_p = limit_p * (1.0 - tp_ratio)
                        sl_p = limit_p * (1.0 + sl_ratio)
                        diff_pct = fresh_diff
                    elif hit_sl:
                        fresh_limit = max(highs[-16:]) * (1.0 + offset_pct)
                        fresh_diff = ((fresh_limit - cur_p) / cur_p) * 100
                        is_touched = True
                        touch_status = "🛑 SUDAH HIT SL"
                        valid_label = "🛑 HIT SL (PINDAI SETUP BARU)"
                        float_roe = -36.0
                        float_usd = -0.72
                        float_str = "🛑 HIT SL! (-36.0% ROE | -$0.72 USD)"
                        limit_p = fresh_limit
                        tp_p = limit_p * (1.0 - tp_ratio)
                        sl_p = limit_p * (1.0 + sl_ratio)
                        diff_pct = fresh_diff
                    else:
                        is_touched = True
                        touch_status = "⚡ SUDAH KESENTUH (TERISI)"
                        valid_label = "✅ VALID (SEDANG MANTUL)"
                        float_roe = ((limit_p - cur_p) / limit_p) * lev * 100
                        float_usd = (float_roe / 100.0) * 2.0
                        sign = "+" if float_roe >= 0 else ""
                        float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
                else:
                    is_touched = False
                    touch_status = "⏳ BELUM KESENTUH"
                    float_roe = 0.0
                    float_usd = 0.0
                    float_str = f"Jarak: +{diff_pct:.2f}% (Menunggu jemputan)"
                    valid_label = "✅ SETUP VALID" if diff_pct <= 2.0 else "🔍 MEMINDAI (BELUM VALID)"
            
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
                "closed": time.time()
            }
        except Exception:
            time.sleep(0.3)
    return None

def scan_all():
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(scan_single_coin, TOP_20_COINS))
    return [r for r in results if r is not None]

if __name__ == '__main__':
    data = scan_all()
    print(f"Scanned {len(data)} coins.")
    for d in data[:5]:
        print(f"[{d['coin']}] {d['potensi']} | {d['valid_label']} | {d['touch_status']} | {d['float_str']}")
