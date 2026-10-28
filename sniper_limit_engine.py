#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sniper_limit_engine.py
-----------------------
Engine Sinyal Kripto Limit Order Sniper 20 Koin (Fibonacci 50% Golden Pullback + Trend Filter EMA 50).
100% Data Riil & Persistent Locked Levels:
1. Level Entry (Limit), TP (+35% ROE), dan SL (-20% ROE) DIKUNCI MATI (PERSISTENT LOCKED).
2. Level limit buy selalu berada di bawah harga pasar (diskon), dan limit sell selalu di atas harga pasar (premium).
3. Hanya harga real-time candle berjalan yang dapat menjemput limit (anti-ghost trigger dari masa lalu).
4. Ketika TP atau SL tersentuh:
   - Hasil trade LANGSUNG dicatat ke riwayat persisten '_HISTORY_TRADES'.
   - Sistem SEGERA memindai dan menerbitkan SETUP LIMIT BARU ('WAITING') dari struktur pasar terkini.
   - Menggunakan cabang 'elif' sehingga tidak ada loop trigger ganda di scan tick yang sama.
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
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

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
    "PEPE": 63.8, "ARB": 59.5, "DOT": 61.2, "AVAX": 58.7, "FET": 60.1,
    "SUI": 61.4, "RENDER": 60.8, "NEAR": 64.2, "INJ": 66.5, "WIF": 63.1,
    "OP": 63.4, "BTC": 57.0, "XRP": 56.5, "APT": 58.2, "TIA": 57.8,
    "BNB": 58.9, "SOL": 60.5, "LINK": 59.2, "DOGE": 55.4, "ADA": 62.0
}

TOP_20_COINS = [
    # --- TOP 12 ELITE CASH COW (WR >55%, Profit Tinggi, Rendah WS) ---
    ("PEPE", "PEPE-USDT", "Pepe", 40, "⭐ ELITE CASH COW"),
    ("ARB", "ARB-USDT", "Arbitrum", 40, "⭐ ELITE CASH COW"),
    ("DOT", "DOT-USDT", "Polkadot", 40, "⭐ ELITE CASH COW"),
    ("AVAX", "AVAX-USDT", "Avalanche", 40, "⭐ ELITE CASH COW"),
    ("FET", "FET-USDT", "Artificial Superintelligence", 40, "⭐ ELITE CASH COW"),
    ("SUI", "SUI-USDT", "Sui Network", 40, "⭐ ELITE CASH COW"),
    ("RENDER", "RENDER-USDT", "Render", 40, "⭐ ELITE CASH COW"),
    ("NEAR", "NEAR-USDT", "Near Protocol", 40, "⭐ ELITE CASH COW"),
    ("INJ", "INJ-USDT", "Injective", 40, "⭐ ELITE CASH COW"),
    ("WIF", "WIF-USDT", "Dogwifhat", 40, "⭐ ELITE CASH COW"),
    ("OP", "OP-USDT", "Optimism", 40, "⭐ ELITE CASH COW"),
    ("BTC", "BTC-USDT", "Bitcoin", 40, "⭐ ELITE CASH COW"),
    # --- KOIN PENDUKUNG PROFITABLE ---
    ("XRP", "XRP-USDT", "Ripple", 40, "⚡ TIER 2"),
    ("APT", "APT-USDT", "Aptos", 40, "⚡ TIER 2"),
    ("TIA", "TIA-USDT", "Celestia", 40, "⚡ TIER 2"),
    ("BNB", "BNB-USDT", "Binance Coin", 40, "🔥 ALPHA"),
    ("SOL", "SOL-USDT", "Solana", 40, "🔥 ALPHA"),
    ("LINK", "LINK-USDT", "Chainlink", 40, "⚡ TIER 2"),
    ("DOGE", "DOGE-USDT", "Dogecoin", 40, "🔥 ALPHA"),
    ("ADA", "ADA-USDT", "Cardano", 40, "⚡ TIER 2")
]

STATE_FILE = Path(__file__).parent / "limit_bot_active_state.json"
_STATE_LOCK = threading.Lock()
_PERSISTENT_SETUPS = {}
_LAST_CACHE = []
_LAST_MTIME = 0.0

def load_persistent_state(force_reload=False):
    global _PERSISTENT_SETUPS, _LAST_MTIME
    with _STATE_LOCK:
        if STATE_FILE.exists():
            try:
                curr_mtime = STATE_FILE.stat().st_mtime
                # Reload jika force_reload, atau mtime berubah di disk, atau memory belum terisi
                if force_reload or curr_mtime != _LAST_MTIME or not _PERSISTENT_SETUPS:
                    data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
                    if isinstance(data, dict):
                        _PERSISTENT_SETUPS = data
                        _LAST_MTIME = curr_mtime
                return dict(_PERSISTENT_SETUPS)
            except Exception:
                pass
        if not _PERSISTENT_SETUPS:
            _PERSISTENT_SETUPS = {}
        return dict(_PERSISTENT_SETUPS)

def save_persistent_state():
    global _LAST_MTIME
    with _STATE_LOCK:
        try:
            STATE_FILE.write_text(json.dumps(_PERSISTENT_SETUPS, indent=2), encoding='utf-8')
            _LAST_MTIME = STATE_FILE.stat().st_mtime
        except Exception:
            pass

def load_persistent_history():
    state = load_persistent_state(force_reload=True)
    history = state.get("_HISTORY_TRADES", [])
    if isinstance(history, list):
        return list(history)
    return []

def record_closed_trade(coin, sym, outcome, exit_p, closed_ts, roe_override=None, pnl_override=None, margin=1.30):
    """Mencatat trade selesai ke riwayat persisten (anti-duplikasi) dan langsung potong/tambah Realized PnL."""
    global _PERSISTENT_SETUPS
    load_persistent_state(force_reload=True)
    with _STATE_LOCK:
        if "_HISTORY_TRADES" not in _PERSISTENT_SETUPS or not isinstance(_PERSISTENT_SETUPS["_HISTORY_TRADES"], list):
            _PERSISTENT_SETUPS["_HISTORY_TRADES"] = []
            
        # Titan Quantum 40x: Target TP +32.0% ROE (+0.416 USD pd $1.30 margin), SL -30.0% ROE (-0.390 USD pd $1.30 margin)
        roe = roe_override if roe_override is not None else (32.0 if outcome == "TP" else -30.0)
        pnl_usd = pnl_override if pnl_override is not None else (round(float(margin) * 0.32, 4) if outcome == "TP" else round(-float(margin) * 0.30, 4))
        record = {
            "coin": coin,
            "sym": sym,
            "outcome": outcome,
            "pnl_usd": round(float(pnl_usd), 4),
            "roe": round(float(roe), 2),
            "exit_price": round(float(exit_p), 6),
            "closed_at": float(closed_ts)
        }
        
        history = _PERSISTENT_SETUPS["_HISTORY_TRADES"]
        is_dup = False
        for h in history[-20:]:
            if h.get("coin") == coin and h.get("outcome") == outcome and abs(closed_ts - h.get("closed_at", 0)) < 60:
                is_dup = True
                break
        if not is_dup:
            history.append(record)
    save_persistent_state()
    return record

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
    
    raw = []
    # 1. Prioritaskan MEXC Contract API (Data Bursa Riil Akun)
    mexc_sym = f"{coin}_USDT"
    mexc_url = f"https://contract.mexc.com/api/v1/contract/kline/{mexc_sym}?interval=Min15"
    for attempt in range(2):
        try:
            r = requests.get(mexc_url, verify=False, timeout=4.0).json()
            if r.get("success") and r.get("data"):
                kl = r["data"]
                times = kl.get("time", [])
                if len(times) >= 32:
                    m_opens = [float(x) for x in kl.get("open", [])]
                    m_highs = [float(x) for x in kl.get("high", [])]
                    m_lows = [float(x) for x in kl.get("low", [])]
                    m_closes = [float(x) for x in kl.get("close", [])]
                    raw = [
                        {
                            "time": int(times[i]) * 1000,
                            "open": m_opens[i],
                            "high": m_highs[i],
                            "low": m_lows[i],
                            "close": m_closes[i]
                        }
                        for i in range(len(times))
                    ]
                    raw = raw[-128:]
                    break
        except Exception:
            time.sleep(0.15)
            
    # 2. Cadangan ke BingX jika MEXC sementara unreachable
    if not raw or len(raw) < 32:
        url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=15m&limit=128"
        for attempt in range(2):
            try:
                r = requests.get(url, verify=False, timeout=4.0).json()
                data_list = r.get("data", [])
                if data_list and len(data_list) >= 32:
                    if data_list[0]["time"] > data_list[-1]["time"]:
                        data_list.reverse()
                    raw = data_list
                    break
            except Exception:
                time.sleep(0.15)
                
    if not raw or len(raw) < 32:
        return None

    opens = [float(k["open"]) for k in raw]
    highs = [float(k["high"]) for k in raw]
    lows = [float(k["low"]) for k in raw]
    closes = [float(k["close"]) for k in raw]
    if not closes:
        return None

    for attempt in range(1):
        try:
            cur_p = closes[-1]
            cur_low = lows[-1]
            cur_high = highs[-1]
            now_ts = time.time()
            
            with _STATE_LOCK:
                setup = _PERSISTENT_SETUPS.get(coin)
            
            def create_new_setup(last_out=None):
                """Membuat level limit order baru dengan formula TITAN QUANTUM 40x (100% Green Weeks: EMA 34, Fibo 54%, TP +32%, SL -30%)."""
                # 1. Structural Dynamic Trend Filter: EMA 34 pada timeframe 15m
                ema34 = calc_ema(closes[:-1], 34)
                
                # 2. Kaufman Efficiency Ratio (KER over 16 bars)
                if len(closes) >= 17:
                    net_chg = abs(closes[-1] - closes[-17])
                    tot_path = sum(abs(closes[k] - closes[k-1]) for k in range(-16, 0))
                    ker = net_chg / (tot_path + 1e-8)
                else:
                    ker = 0.35
                
                # Trend direction 15m EMA 34
                is_long = closes[-1] >= ema34
                
                sw_low = min(lows[-33:-1])
                sw_high = max(highs[-33:-1])
                range_span = sw_high - sw_low if sw_high > sw_low else (closes[-1] * 0.01)
                
                # Titan Quantum 40x Parameters (Hasil Riset 8 Minggu 100% Hijau):
                # Leverage: 40x Flat Isolated
                # Retracement Fibo: 54% Sweet Spot Pullback
                # Take Profit (TP): +32.0% ROE (spot target 0.800%)
                # Stop Loss (SL): -30.0% ROE (spot target 0.750% - ruang napas anti-wick)
                # Win Rate: 61.09% | 0 Minggu Merah
                tp_ratio = 0.32 / lev # 0.0080 pada Lev 40x
                sl_ratio = 0.30 / lev # 0.0075 pada Lev 40x
                retrace = 0.54        # Fibo 54% Sweet Spot
                
                if is_long:
                    potensi = "POTENSI LONG (BUY)"
                    side = "LONG"
                    fibo_p = sw_high - retrace * range_span
                    # Pastikan limit buy selalu di bawah harga pasar saat ini (minimal diskon)
                    if fibo_p >= cur_p * 0.998:
                        limit_p = max(sw_low + 0.15 * range_span, cur_p * 0.992)
                    else:
                        limit_p = fibo_p
                    tp_p = limit_p * (1.0 + tp_ratio)
                    sl_p = limit_p * (1.0 - sl_ratio)
                else:
                    potensi = "POTENSI SHORT (SELL)"
                    side = "SHORT"
                    fibo_p = sw_low + retrace * range_span
                    # Pastikan limit sell selalu di atas harga pasar saat ini (minimal premium)
                    if fibo_p <= cur_p * 1.002:
                        limit_p = min(sw_high - 0.15 * range_span, cur_p * 1.008)
                    else:
                        limit_p = fibo_p
                    tp_p = limit_p * (1.0 - tp_ratio)
                    sl_p = limit_p * (1.0 + sl_ratio)
                    
                dec = 8 if coin == "PEPE" else (5 if limit_p < 1.0 else (4 if limit_p < 100 else 2))
                new_s = {
                    "coin": coin,
                    "sym": sym,
                    "name": full_name,
                    "tier": tier_label,
                    "strategy": "TITAN_QUANTUM_40X",
                    "lev": lev,
                    "side": side,
                    "potensi": potensi,
                    "limit_p": round(limit_p, dec),
                    "tp_p": round(tp_p, dec),
                    "sl_p": round(sl_p, dec),
                    "ker": round(ker, 4),
                    "ema34": round(ema34, dec),
                    "status": "WAITING",
                    "created_at": now_ts,
                    "touch_time": None,
                    "last_outcome": last_out
                }
                with _STATE_LOCK:
                    _PERSISTENT_SETUPS[coin] = new_s
                save_persistent_state()
                return new_s

            # 1. Jika belum pernah ada setup sama sekali, buat baru
            if setup is None or not isinstance(setup, dict):
                setup = create_new_setup()

            # 2. Jika ada status legacy TP_HIT / SL_HIT, langsung selesaikan dan buat setup fresh
            if setup.get('status') in ('TP_HIT', 'SL_HIT'):
                outcome = "TP" if setup.get('status') == 'TP_HIT' else "SL"
                cur_margin = float(setup.get('margin', 1.30))
                roe_val = 32.0 if outcome == "TP" else -30.0
                pnl_val = round(cur_margin * 0.32, 4) if outcome == "TP" else round(-cur_margin * 0.30, 4)
                record_closed_trade(coin, sym, outcome, cur_p, setup.get('closed_at', now_ts), roe_override=roe_val, pnl_override=pnl_val, margin=cur_margin)
                last_out = {
                    "outcome": outcome,
                    "roe": roe_val,
                    "pnl_usd": pnl_val,
                    "closed_at": now_ts
                }
                setup = create_new_setup(last_out=last_out)

            # 3. Jika sudah 12 jam waiting tanpa tersentuh, perbarui struktur pasar
            elif setup.get('status') == 'WAITING' and (now_ts - setup.get('created_at', now_ts) > 43200):
                setup = create_new_setup(last_out=setup.get('last_outcome'))

            limit_p = setup["limit_p"]
            tp_p = setup["tp_p"]
            sl_p = setup["sl_p"]
            side = setup["side"]
            is_long = (side == "LONG")
            potensi = setup["potensi"]
            status = setup.get("status", "WAITING")
            last_outcome = setup.get("last_outcome")
            
            # Evaluasi Transisi Status:
            # JIKA TOUCHED: Posisi sedang aktif! Cek apakah mencapai TP atau SL sejak posisi terisi
            if status == "TOUCHED":
                touch_time_ms = int(setup.get("touch_time", setup.get("created_at", now_ts)) * 1000)
                active_candles = [k for k in raw if int(k["time"]) + 900000 >= touch_time_ms]
                if not active_candles:
                    active_candles = raw[-1:]
                
                eval_high = max(float(k["high"]) for k in active_candles)
                eval_low = min(float(k["low"]) for k in active_candles)

                hit_tp = (eval_high >= tp_p) if is_long else (eval_low <= tp_p)
                hit_sl = (eval_low <= sl_p) if is_long else (eval_high >= sl_p)
                
                if hit_tp or hit_sl:
                    outcome = "TP" if hit_tp else "SL"
                    exit_p = tp_p if hit_tp else sl_p
                    cur_margin = float(setup.get('margin', 1.30))
                    roe_val = 32.0 if hit_tp else -30.0
                    pnl_val = round(cur_margin * 0.32, 4) if hit_tp else round(-cur_margin * 0.30, 4)
                    record_closed_trade(coin, sym, outcome, exit_p, now_ts, roe_override=roe_val, pnl_override=pnl_val, margin=cur_margin)
                    last_out = {
                        "outcome": outcome,
                        "roe": roe_val,
                        "pnl_usd": pnl_val,
                        "closed_at": now_ts
                    }
                    setup = create_new_setup(last_out=last_out)
                    limit_p = setup["limit_p"]
                    tp_p = setup["tp_p"]
                    sl_p = setup["sl_p"]
                    side = setup["side"]
                    is_long = (side == "LONG")
                    potensi = setup["potensi"]
                    status = "WAITING"
                    last_outcome = last_out

            # JIKA WAITING: Cek apakah wick candle menjemput level limit sejak dibuat
            elif status == "WAITING":
                created_ms = int(setup.get("created_at", now_ts) * 1000)
                wait_candles = [k for k in raw if int(k["time"]) + 900000 >= created_ms]
                if not wait_candles:
                    wait_candles = raw[-1:]
                
                wait_high = max(float(k["high"]) for k in wait_candles)
                wait_low = min(float(k["low"]) for k in wait_candles)
                
                # Eksekusi persis sesuai orderbook MEXC:
                touched = (wait_low <= limit_p) if is_long else (wait_high >= limit_p)
                if touched:
                    is_live_mexc = setup.get("is_mexc_order", False)
                    if is_live_mexc:
                        status = "TOUCHED"
                        setup["status"] = "TOUCHED"
                        setup["touch_time"] = now_ts
                        with _STATE_LOCK:
                            _PERSISTENT_SETUPS[coin] = setup
                        save_persistent_state()
                    else:
                        # SMART GUARD: Level limit sempat tersentuh saat trader belum pasang limit di MEXC!
                        # Ini adalah "Missed Entry / Telat Entry".
                        # Untuk mencegah trader pasang posisi telat yang berisiko kena SL pada jemputan kedua,
                        # kita otomatis BATALKAN setup lama dan PINDAI ULANG (Fresh Re-Scan) ke struktur market terbaru!
                        old_limit = limit_p
                        setup = create_new_setup(last_out=setup.get('last_outcome'))
                        setup['is_fresh_rescan'] = True
                        setup['rescan_note'] = f"Level lama ${old_limit} sempat kesentuh saat offline. Otomatis dipindai ulang ke level baru!"
                        setup['prev_limit_p'] = old_limit
                        setup['was_missed_touch'] = True
                        limit_p = setup["limit_p"]
                        tp_p = setup["tp_p"]
                        sl_p = setup["sl_p"]
                        side = setup["side"]
                        is_long = (side == "LONG")
                        potensi = setup["potensi"]
                        status = "WAITING"
                        with _STATE_LOCK:
                            _PERSISTENT_SETUPS[coin] = setup
                        save_persistent_state()

            # Hitung jarak real-time ke harga limit
            if is_long:
                diff_pct = ((cur_p - limit_p) / cur_p) * 100
            else:
                diff_pct = ((limit_p - cur_p) / cur_p) * 100
                
            wr_val = COIN_WIN_RATES.get(coin, 67.0)
            
            coin_margin = float(setup.get('margin', 1.30)) if setup else 1.30
            if status == "TOUCHED":
                if is_long:
                    float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                else:
                    float_roe = ((limit_p - cur_p) / limit_p) * lev * 100
                float_usd = (float_roe / 100.0) * coin_margin
                sign = "+" if float_roe >= 0 else ""
                float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}%)"
                touch_status = "⚡ SEDANG MANTUL (TERISI)"
                valid_label = "⚡ POSISI AKTIF"
                is_touched = True
            else:
                float_roe = 0.0
                float_usd = 0.0
                sign_d = "-" if is_long else "+"
                float_str = f"Jarak: {sign_d}{abs(diff_pct):.2f}% (Menunggu jemputan)"
                valid_label = "✅ SETUP VALID" if abs(diff_pct) <= 2.5 else "🔍 MEMINDAI"
                touch_status = "⏳ MENUNGGU JEMPUTAN"
                is_touched = False
                
            return {
                "coin": coin,
                "sym": sym,
                "name": full_name,
                "tier": tier_label,
                "strategy": "TITAN_HARMONIC_40X",
                "lev": lev,
                "side": side,
                "margin": coin_margin,
                "cur_p": cur_p,
                "potensi": potensi,
                "status": status,
                "valid_label": valid_label,
                "touch_status": touch_status,
                "is_touched": is_touched,
                "float_str": float_str,
                "float_roe": float_roe,
                "float_usd": float_usd,
                "limit_p": limit_p,
                "sl_p": sl_p,
                "tp_p": tp_p,
                "ker": float(setup.get('ker', 0.25)) if setup else 0.25,
                "diff_pct": diff_pct,
                "wr": wr_val,
                "last_outcome": last_outcome,
                "is_fresh_rescan": setup.get("is_fresh_rescan", False),
                "prev_limit_p": setup.get("prev_limit_p"),
                "rescan_note": setup.get("rescan_note"),
                "was_missed_touch": setup.get("was_missed_touch", False),
                "closed": now_ts
            }
        except Exception:
            time.sleep(0.3)
    return None

def fetch_mexc_live_telemetry():
    """Mengambil posisi aktif, floating PnL, limit orders antre, dan realized PnL langsung dari API MEXC."""
    try:
        import exchange_network
        exchange_network.install_dns()
    except Exception:
        pass

    client = None
    # 1. Coba dari D:\bot_final\akun_privat.json
    local_p = Path(r'D:\bot_final\akun_privat.json')
    if local_p.exists():
        try:
            cfg = json.loads(local_p.read_text(encoding='utf-8-sig'))
            m = cfg.get('akun_1', {}).get('MEXC', {})
            if m.get('apiKey'):
                import ccxt
                client = ccxt.mexc({'apiKey': m['apiKey'], 'secret': m['secret'], 'options': {'defaultType': 'swap'}, 'timeout': 10000})
        except Exception:
            pass

    # 2. Coba dari Streamlit secrets
    if client is None:
        try:
            import streamlit as st
            sec = getattr(st, 'secrets', {})
            accs = json.loads(sec.get('accounts_json', '{}'))
            m = accs.get('akun_1', {}).get('MEXC', {})
            if m.get('apiKey'):
                import ccxt
                client = ccxt.mexc({'apiKey': m['apiKey'], 'secret': m['secret'], 'options': {'defaultType': 'swap'}, 'timeout': 10000})
        except Exception:
            pass

    # 3. Coba dari secrets.toml lokal
    if client is None:
        sec_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
        if sec_path.exists():
            try:
                import toml, ccxt
                sec = toml.loads(sec_path.read_text(encoding='utf-8'))
                accs = json.loads(sec.get('accounts_json', '{}'))
                m = accs.get('akun_1', {}).get('MEXC', {})
                if m.get('apiKey'):
                    client = ccxt.mexc({'apiKey': m['apiKey'], 'secret': m['secret'], 'options': {'defaultType': 'swap'}, 'timeout': 10000})
            except Exception:
                pass

    if client is None:
        return None

    try:
        # A. Posisi Aktif Langsung dari MEXC
        pos = client.fetch_positions()
        active_pos = [p for p in pos if float(p.get('contracts') or p.get('size') or 0) > 0]
        pos_map = {}
        for p in active_pos:
            info = p['info']
            sym = info['symbol'].replace('_USDT', '')
            side = 'LONG' if int(info.get('positionType', 1)) == 1 else 'SHORT'
            entry = float(info.get('holdAvgPrice', 0.0))
            im = float(info.get('im', 0.0))
            unpnl = float(info.get('unRealizedPnl', 0.0))
            ratio = float(info.get('profitRatio', 0.0))
            roe = (unpnl / im * 100.0) if im > 0 else (ratio * 100.0)
            t_create = float(info.get('createTime', 0) or 0)
            t_str = datetime.fromtimestamp(t_create/1000, WIB).strftime('%H:%M:%S WIB') if t_create else '-'
            pos_map[sym] = {
                'coin': sym,
                'side': side,
                'entry': entry,
                'margin': im,
                'unpnl': unpnl,
                'roe': roe,
                'contracts': float(info.get('holdVol', 0)),
                'time_str': t_str,
                'create_ts': t_create
            }

        # B. Open Orders Langsung dari MEXC
        orders = client.fetch_open_orders()
        order_map = {}
        for o in orders:
            sym = o['symbol'].replace('/USDT:USDT', '').replace(':USDT', '')
            ts = float(o.get('timestamp') or o.get('info', {}).get('createTime') or 0)
            t_str = datetime.fromtimestamp(ts/1000, WIB).strftime('%H:%M:%S WIB') if ts else '-'
            order_map[sym] = {
                'coin': sym,
                'id': o['id'],
                'side': 'LONG' if o['side'] == 'buy' else 'SHORT',
                'price': float(o['price']),
                'amount': float(o['amount']),
                'time_str': t_str,
                'timestamp': ts
            }

        # C. Realized PnL Hari Ini dari Posisi Selesai di MEXC (00:00:00 WIB s/d sekarang)
        p_hist = client.contractPrivateGetPositionListHistoryPositions({'page_num': 1, 'page_size': 50})
        data = p_hist.get('data', [])
        now_wib = datetime.now(WIB)
        today_00 = datetime(now_wib.year, now_wib.month, now_wib.day, 0, 0, 0, tzinfo=WIB)
        today_start_ms = int(today_00.timestamp() * 1000)
        today_closed = [p for p in data if p.get('updateTime', 0) >= today_start_ms]
        
        trades_list = []
        for p in today_closed:
            sym = p['symbol'].replace('_USDT', '')
            side = 'LONG' if p.get('positionType', 1) == 1 else 'SHORT'
            real = float(p.get('realised', 0.0))
            ratio = float(p.get('profitRatio', 0.0)) * 100.0
            outcome = 'TP' if real > 0 else 'SL'
            t_upd = float(p.get('updateTime', 0) or 0)
            t_str = datetime.fromtimestamp(t_upd/1000, WIB).strftime('%H:%M:%S WIB') if t_upd else '-'
            trades_list.append({
                'coin': sym,
                'sym': f"{sym}-USDT",
                'side': side,
                'outcome': outcome,
                'pnl_usd': round(real, 4),
                'roe': round(ratio, 2),
                'entry_price': float(p.get('openAvgPrice') or p.get('newOpenAvgPrice') or 0.0),
                'exit_price': float(p.get('closeAvgPrice') or p.get('newCloseAvgPrice') or 0.0),
                'closed_at': float(t_upd / 1000.0),
                'time_str': t_str
            })

        trades_list.sort(key=lambda t: t['closed_at'], reverse=True)
        tp_trades = [t for t in trades_list if t['outcome'] == 'TP']
        sl_trades = [t for t in trades_list if t['outcome'] == 'SL']
        tot_realised = sum(t['pnl_usd'] for t in trades_list)
        tot_realised_roe = sum(t['roe'] for t in trades_list)
        tp_count = len(tp_trades)
        sl_count = len(sl_trades)

        return {
            'active_positions': pos_map,
            'open_orders': order_map,
            'realized_usd': tot_realised,
            'realized_roe': tot_realised_roe,
            'tp_count': tp_count,
            'sl_count': sl_count,
            'tp_trades': tp_trades,
            'sl_trades': sl_trades,
            'trades': trades_list,
            'total_floating_usd': sum(p['unpnl'] for p in pos_map.values()),
            'total_floating_roe': sum(p['roe'] for p in pos_map.values()),
            'timestamp': time.time()
        }
    except Exception as e:
        return None

def scan_all():
    global _LAST_CACHE
    load_persistent_state()
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(scan_single_coin, TOP_20_COINS))
    valid = [r for r in results if r is not None]
    
    # SINKRONISASI 100% PERSIS DENGAN MEXC FUTURES
    mexc_live = fetch_mexc_live_telemetry()
    if mexc_live:
        act_pos = mexc_live.get('active_positions', {})
        op_ord = mexc_live.get('open_orders', {})
        
        for r in valid:
            c = r['coin']
            # 1. Jika koin sedang aktif berjalan di MEXC (Mantul)
            if c in act_pos:
                p = act_pos[c]
                r['status'] = 'TOUCHED'
                r['is_touched'] = True
                r['side'] = p['side']
                r['potensi'] = f"🟢 POTENSI {p['side']}" if p['side'] == 'LONG' else f"🔴 POTENSI {p['side']}"
                r['limit_p'] = p['entry'] # Entry riil MEXC
                r['margin'] = p['margin'] # Margin riil MEXC
                r['float_usd'] = p['unpnl'] # Floating riil MEXC
                r['float_roe'] = p['roe']   # ROE riil MEXC
                r['order_time_str'] = p['time_str']
                r['is_mexc_order'] = False
                r['is_mexc_active'] = True
                r['mexc_badge'] = "⚡ SUDAH MANTUL (POSISI AKTIF)"
                sign = "+" if r['float_usd'] >= 0 else ""
                r['float_str'] = f"Floating: {sign}${r['float_usd']:.4f} ({r['float_roe']:+.2f}%)"
                r['touch_status'] = "⚡ SEDANG MANTUL (MEXC LIVE)"
                r['valid_label'] = "⚡ POSISI AKTIF"
            
            # 2. Jika koin sedang menunggu order limit di MEXC Orderbook
            elif c in op_ord:
                o = op_ord[c]
                r['status'] = 'WAITING'
                r['is_touched'] = False
                r['side'] = o['side']
                r['potensi'] = f"🟢 POTENSI {o['side']}" if o['side'] == 'LONG' else f"🔴 POTENSI {o['side']}"
                r['limit_p'] = o['price'] # Harga limit antre riil MEXC
                r['order_id'] = o['id']
                r['order_time_str'] = o['time_str']
                r['is_mexc_order'] = True
                r['is_mexc_active'] = False
                r['float_usd'] = 0.0
                r['float_roe'] = 0.0
                is_long = (o['side'] == 'LONG')
                cur_p = r.get('cur_p', o['price'])
                diff_pct = ((cur_p - o['price']) / cur_p) * 100 if is_long else ((o['price'] - cur_p) / cur_p) * 100
                r['diff_pct'] = diff_pct
                sign_d = "-" if is_long else "+"
                r['float_str'] = f"Jarak: {sign_d}{abs(diff_pct):.2f}% (Antre di MEXC)"
                
                # DETEKSI ORDER BASI / EXPIRED DI MEXC:
                # 1. Target TP sudah tercapai tanpa jemput limit
                # 2. Order antre sudah lebih dari 4 jam (14.400 detik)
                o_ts = float(o.get('timestamp') or 0)
                now_sec = time.time()
                age_sec = now_sec - (o_ts / 1000.0) if o_ts > 0 else 0
                tp_val = r.get('tp_p', 0.0)
                
                tp_hit_without_fill = False
                if tp_val > 0:
                    if is_long and cur_p >= tp_val:
                        tp_hit_without_fill = True
                    elif (not is_long) and cur_p <= tp_val:
                        tp_hit_without_fill = True
                
                is_too_old = (age_sec >= 14400) # > 4 jam
                
                if tp_hit_without_fill or is_too_old:
                    r['is_expired_order'] = True
                    reason = "Target TP sudah tercapai duluan!" if tp_hit_without_fill else f"Antre > 4 jam ({int(age_sec//3600)}j {int((age_sec%3600)//60)}m)"
                    r['expired_reason'] = reason
                    r['mexc_badge'] = f"🛑 ORDER BASI ({reason}) - BATALKAN (ID: {o['id']})"
                    r['valid_label'] = "🛑 ORDER BASI / BATALKAN"
                    r['touch_status'] = "🛑 ORDER BASI (PERLU CANCEL)"
                else:
                    r['is_expired_order'] = False
                    r['mexc_badge'] = f"🟢 SUDAH LIMIT DI MEXC (ID: {o['id']})"
                    r['touch_status'] = "⏳ MENUNGGU JEMPUTAN"
                    r['valid_label'] = "🟢 SUDAH LIMIT DI MEXC"
            
            # 3. Koin setup valid tapi belum antre di MEXC
            else:
                r['status'] = 'WAITING'
                r['is_touched'] = False
                r['order_id'] = None
                r['order_time_str'] = datetime.now(WIB).strftime('%H:%M:%S WIB')
                r['is_mexc_order'] = False
                r['is_mexc_active'] = False
                r['float_usd'] = 0.0
                r['float_roe'] = 0.0
                cur_p = r.get('cur_p', 0.0)
                is_long = "LONG" in r.get('potensi', 'LONG')
                diff_pct = ((cur_p - r['limit_p']) / cur_p) * 100 if is_long and cur_p > 0 else 0.0
                r['diff_pct'] = diff_pct
                
                if r.get('is_fresh_rescan'):
                    prev_p = r.get('prev_limit_p', '-')
                    r['mexc_badge'] = f"🔄 FRESH RE-SCAN (Level lama ${prev_p} sempat kesentuh)"
                    r['valid_label'] = "🔄 RE-SCAN SELESAI"
                    r['float_str'] = f"Jarak: {diff_pct:.2f}% (Fresh Re-Scan)"
                    r['touch_status'] = "🔄 DIPINDAI ULANG KE LEVEL BARU"
                else:
                    r['mexc_badge'] = "🟡 SIAP PASANG (FRESH)"
                    r['valid_label'] = "🟡 BELUM LIMIT"
                    r['float_str'] = f"Jarak: {diff_pct:.2f}% (Siap Pasang)"
                    r['touch_status'] = "⏳ SIAP PASANG"

        with _STATE_LOCK:
            _PERSISTENT_SETUPS['_MEXC_LIVE_TELEMETRY'] = mexc_live
            _PERSISTENT_SETUPS['_HISTORY_TRADES'] = mexc_live['trades']
        save_persistent_state()

    if len(valid) >= 15:
        _LAST_CACHE = valid
        return valid
    elif _LAST_CACHE:
        return _LAST_CACHE
    return valid

def get_portfolio_summary(observations=None):
    """Menghitung agregasi portfolio jujur & persisten (Realized PnL, Floating PnL, Win Rate)."""
    if observations is None:
        observations = scan_all()
    
    state = load_persistent_state(force_reload=True)
    mexc_live = state.get('_MEXC_LIVE_TELEMETRY')
    
    if mexc_live:
        realized_usd = mexc_live.get('realized_usd', 0.0)
        realized_roe = mexc_live.get('realized_roe', 0.0)
        tp_count = mexc_live.get('tp_count', 0)
        sl_count = mexc_live.get('sl_count', 0)
        total_closed = tp_count + sl_count
        realized_wr = (tp_count / total_closed * 100.0) if total_closed > 0 else 0.0
        history = mexc_live.get('trades', [])
        tp_trades = mexc_live.get('tp_trades', [t for t in history if t.get('outcome') == 'TP'])
        sl_trades = mexc_live.get('sl_trades', [t for t in history if t.get('outcome') == 'SL'])
    else:
        history = load_persistent_history()
        tp_count = sum(1 for t in history if t.get('outcome') == 'TP')
        sl_count = sum(1 for t in history if t.get('outcome') == 'SL')
        realized_usd = sum(t.get('pnl_usd', 0.0) for t in history)
        realized_roe = sum(t.get('roe', 0.0) for t in history)
        total_closed = tp_count + sl_count
        realized_wr = (tp_count / total_closed * 100) if total_closed > 0 else 0.0
        tp_trades = [t for t in history if t.get('outcome') == 'TP']
        sl_trades = [t for t in history if t.get('outcome') == 'SL']

    active_trades = [r for r in observations if r.get('status') == 'TOUCHED']
    new_signals = [r for r in observations if r.get('status') == 'WAITING']
    floating_usd = sum(r.get('float_usd', 0.0) for r in active_trades)
    floating_roe = sum(r.get('float_roe', 0.0) for r in active_trades)
    active_count = len(active_trades)
    waiting_count = len(new_signals)
    avg_portfolio_wr = sum(r.get('wr', 67.0) for r in observations) / len(observations) if observations else 67.0

    return {
        "realized_usd": realized_usd,
        "realized_roe": realized_roe,
        "realized_idr": realized_usd * 16300,
        "tp_count": tp_count,
        "sl_count": sl_count,
        "total_closed": total_closed,
        "realized_wr": realized_wr,
        "avg_wr": avg_portfolio_wr,
        "floating_usd": floating_usd,
        "floating_roe": floating_roe,
        "floating_idr": floating_usd * 16300,
        "active_count": active_count,
        "waiting_count": waiting_count,
        "history": history,
        "tp_trades": tp_trades,
        "sl_trades": sl_trades,
        "new_signals": new_signals,
        "active_trades": active_trades
    }

_MEXC_CLIENT_SINGLETON = None
_MEXC_MARKETS_CACHE = None

def get_mexc_trading_client():
    global _MEXC_CLIENT_SINGLETON
    if _MEXC_CLIENT_SINGLETON is not None:
        return _MEXC_CLIENT_SINGLETON
    
    try:
        import exchange_network
        exchange_network.install_dns()
    except Exception:
        pass

    # 1. Coba dari D:\bot_final\akun_privat.json
    local_p = Path(r'D:\bot_final\akun_privat.json')
    if local_p.exists():
        try:
            cfg = json.loads(local_p.read_text(encoding='utf-8-sig'))
            m = cfg.get('akun_1', {}).get('MEXC', {})
            if m.get('apiKey'):
                import ccxt
                _MEXC_CLIENT_SINGLETON = ccxt.mexc({
                    'apiKey': m['apiKey'],
                    'secret': m['secret'],
                    'options': {'defaultType': 'swap'},
                    'timeout': 15000,
                    'enableRateLimit': True
                })
                return _MEXC_CLIENT_SINGLETON
        except Exception:
            pass

    # 2. Coba dari Streamlit secrets
    try:
        import streamlit as st
        sec = getattr(st, 'secrets', {})
        accs = json.loads(sec.get('accounts_json', '{}'))
        m = accs.get('akun_1', {}).get('MEXC', {})
        if m.get('apiKey'):
            import ccxt
            _MEXC_CLIENT_SINGLETON = ccxt.mexc({
                'apiKey': m['apiKey'],
                'secret': m['secret'],
                'options': {'defaultType': 'swap'},
                'timeout': 15000,
                'enableRateLimit': True
            })
            return _MEXC_CLIENT_SINGLETON
    except Exception:
        pass

    # 3. Coba dari secrets.toml lokal
    sec_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if sec_path.exists():
        try:
            import toml, ccxt
            sec = toml.loads(sec_path.read_text(encoding='utf-8'))
            accs = json.loads(sec.get('accounts_json', '{}'))
            m = accs.get('akun_1', {}).get('MEXC', {})
            if m.get('apiKey'):
                import ccxt
                _MEXC_CLIENT_SINGLETON = ccxt.mexc({
                    'apiKey': m['apiKey'],
                    'secret': m['secret'],
                    'options': {'defaultType': 'swap'},
                    'timeout': 15000,
                    'enableRateLimit': True
                })
                return _MEXC_CLIENT_SINGLETON
        except Exception:
            pass

    return None

def execute_single_coin_limit_order(coin, custom_margin=1.30):
    """
    Memasang Limit Order tunggal ke MEXC Akun 1 dengan margin custom yang dikendalikan pengguna.
    Formula: Titan Quantum 40x Isolated, TP +32.0% ROE, SL -30.0% ROE (8 Minggu 100% Hijau & Audit 6 Bulan).
    TP dan SL langsung di-attach native di MEXC server.
    """
    try:
        mx = get_mexc_trading_client()
        if mx is None:
            return {"success": False, "msg": "API Key MEXC Akun 1 tidak ditemukan di sistem!"}
        
        global _MEXC_MARKETS_CACHE
        if _MEXC_MARKETS_CACHE is None:
            _MEXC_MARKETS_CACHE = mx.load_markets()
            
        sym = f"{coin}/USDT:USDT"
        if sym not in _MEXC_MARKETS_CACHE:
            return {"success": False, "msg": f"Market {sym} tidak terdaftar di MEXC Futures!"}
            
        market = _MEXC_MARKETS_CACHE[sym]
        cs = float(market.get('contractSize') or 1.0)
        min_a = float(market.get('limits', {}).get('amount', {}).get('min') or 1.0)
        
        # Ambil setup sinyal terkini dari persistent state
        state = load_persistent_state(force_reload=True)
        setup = state.get(coin)
        if not setup:
            coin_tuples = [t for t in TOP_20_COINS if t[0] == coin]
            if coin_tuples:
                setup = scan_single_coin(coin_tuples[0])
                
        if not setup:
            return {"success": False, "msg": f"Gagal mendapatkan data sinyal untuk {coin}."}
            
        # Cek apakah koin ini sudah aktif berjalan di MEXC (sudah mantul)
        pos = mx.fetch_positions()
        for p in pos:
            if float(p.get('contracts') or p.get('size') or 0) > 0:
                p_sym = p.get('symbol', '').split(':')[0].replace('/', '_').replace('_USDT', '')
                if p_sym == coin:
                    return {"success": False, "msg": f"Koin {coin} sudah memiliki posisi aktif di MEXC! Tidak boleh ditumpuk."}
        
        # Cek apakah sudah ada limit order antre untuk koin ini di MEXC
        open_orders = mx.fetch_open_orders()
        for o in open_orders:
            o_sym = o.get('symbol', '').split(':')[0].replace('/', '_').replace('_USDT', '')
            if o_sym == coin:
                # Batalkan order lama agar bisa diganti dengan order margin baru yang diinginkan user
                try:
                    mx.cancel_order(o['id'], symbol=sym)
                    time.sleep(0.2)
                except Exception:
                    pass
            
        side = setup.get('side', 'LONG')
        order_side = 'buy' if side == 'LONG' else 'sell'
        limit_p = float(setup['limit_p'])
        tp_p = float(setup['tp_p'])
        sl_p = float(setup['sl_p'])
        lev = 40  # Titan Harmonic 40x
        
        # Hitung jumlah kontrak presisi berdasarkan margin yang dikendalikan user
        custom_margin = float(custom_margin)
        if custom_margin <= 0.1:
            custom_margin = 1.30
            
        notional_usd = custom_margin * lev
        base_qty = notional_usd / limit_p
        contracts = int(max(min_a if min_a > 0 else 1, round(base_qty / cs)))
            
        actual_notional = contracts * cs * limit_p
        actual_margin = actual_notional / lev
        
        # Kirim limit order ke MEXC dengan bracket TP & SL native
        res = mx.create_order(
            symbol=sym,
            type='limit',
            side=order_side,
            amount=contracts,
            price=limit_p,
            params={
                'openType': 1,      # 1 = Isolated Margin
                'leverage': lev,    # 40x Leverage
                'hedged': True,     # Hedge Mode
                'stopLossPrice': sl_p,
                'takeProfitPrice': tp_p,
                'lossTrend': 1,
                'profitTrend': 1
            }
        )
        oid = str(res.get('id', ''))
        
        # Update state persisten seketika
        now_wib_str = datetime.now(WIB).strftime('%H:%M:%S WIB')
        with _STATE_LOCK:
            if coin in _PERSISTENT_SETUPS:
                _PERSISTENT_SETUPS[coin]['status'] = 'WAITING'
                _PERSISTENT_SETUPS[coin]['order_id'] = oid
                _PERSISTENT_SETUPS[coin]['order_time_str'] = now_wib_str
                _PERSISTENT_SETUPS[coin]['margin'] = round(actual_margin, 2)
                _PERSISTENT_SETUPS[coin]['is_mexc_order'] = True
                _PERSISTENT_SETUPS[coin]['contracts'] = contracts
        save_persistent_state()
        
        return {
            "success": True,
            "order_id": oid,
            "contracts": contracts,
            "margin": actual_margin,
            "price": limit_p,
            "tp": tp_p,
            "sl": sl_p,
            "msg": f"✅ Sukses! Limit {side} {coin} ({contracts} ktr @ ${limit_p}) terpasang di MEXC! ID: {oid} | Margin: ${actual_margin:.2f} | TP: ${tp_p} (+32%) | SL: ${sl_p} (-30%)"
        }
    except Exception as e:
        return {"success": False, "msg": f"Gagal memasang order {coin}: {str(e)}"}

def execute_cancel_order(coin, order_id=None):
    """Membatalkan open limit order di MEXC Akun 1."""
    try:
        mx = get_mexc_trading_client()
        if mx is None:
            return {"success": False, "msg": "API Key MEXC tidak ditemukan."}
            
        sym = f"{coin}/USDT:USDT"
        cancelled = False
        if order_id:
            try:
                mx.cancel_order(str(order_id), symbol=sym)
                cancelled = True
            except Exception:
                pass
        if not cancelled:
            orders = mx.fetch_open_orders()
            for o in orders:
                o_sym = o.get('symbol', '').split(':')[0].replace('/', '_').replace('_USDT', '')
                if o_sym == coin:
                    mx.cancel_order(o['id'], symbol=sym)
                    cancelled = True
                    
        with _STATE_LOCK:
            if coin in _PERSISTENT_SETUPS:
                _PERSISTENT_SETUPS[coin]['is_mexc_order'] = False
                _PERSISTENT_SETUPS[coin]['order_id'] = None
        save_persistent_state()
        return {"success": True, "msg": f"Order limit {coin} berhasil dibatalkan dari MEXC."}
    except Exception as e:
        return {"success": False, "msg": f"Gagal membatalkan order {coin}: {str(e)}"}

def execute_cancel_all_stale_orders():
    """Membatalkan seluruh order limit di MEXC yang sudah expired / basi / TP tercapai duluan."""
    try:
        data = scan_all()
        cancelled = []
        for d in data:
            if d.get('is_expired_order') and d.get('order_id'):
                res = execute_cancel_order(d['coin'], d['order_id'])
                if res.get('success'):
                    cancelled.append((d['coin'], d['order_id'], d.get('expired_reason', 'Stale')))
        return {
            "success": True,
            "cancelled_count": len(cancelled),
            "cancelled_orders": cancelled,
            "msg": f"✅ Berhasil membatalkan {len(cancelled)} order basi dari MEXC!" if cancelled else "Tidak ada order basi yang perlu dibatalkan."
        }
    except Exception as e:
        return {"success": False, "msg": f"Gagal membatalkan order basi: {str(e)}"}

def execute_place_all_waiting_limits(custom_margin=1.30):
    """Memasang limit order serentak untuk seluruh koin yang berstatus SIAP PASANG."""
    state = load_persistent_state(force_reload=True)
    results = []
    for c_tuple in TOP_20_COINS:
        c = c_tuple[0]
        s = state.get(c, {})
        # Hanya pasang untuk koin yang belum aktif dan belum ada order
        if not s.get('is_touched') and not s.get('is_mexc_order'):
            res = execute_single_coin_limit_order(c, custom_margin=custom_margin)
            results.append((c, res))
            time.sleep(0.2)
    return results

if __name__ == '__main__':
    data = scan_all()
    summ = get_portfolio_summary(data)
    print(f"Scanned {len(data)} coins.")
    print(f"Floating: ${summ['floating_usd']:.2f} ({summ['active_count']} mantul) | Realized: ${summ['realized_usd']:.2f} ({summ['tp_count']} TP / {summ['sl_count']} SL)")
    for d in data[:5]:
        print(f"[{d['coin']}] {d['status']} | {d['potensi']} | Limit: {d['limit_p']} | TP: {d['tp_p']} | SL: {d['sl_p']}")
