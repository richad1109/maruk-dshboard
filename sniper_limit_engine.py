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
    "PEPE": 69.8, "ARB": 59.4, "DOT": 61.1, "AVAX": 63.0, "FET": 63.0,
    "SUI": 57.6, "RENDER": 60.4, "NEAR": 60.9, "INJ": 57.7, "WIF": 58.7,
    "OP": 55.2, "BTC": 64.0, "XRP": 58.3, "APT": 54.7, "TIA": 54.7,
    "BNB": 60.0, "SOL": 51.0, "LINK": 50.0, "DOGE": 50.0, "ADA": 49.0
}

TOP_20_COINS = [
    # --- TOP 12 ELITE CASH COW (WR >55%, Profit Tinggi, Rendah WS) ---
    ("PEPE", "PEPE-USDT", "Pepe", 30, "⭐ ELITE CASH COW"),
    ("ARB", "ARB-USDT", "Arbitrum", 30, "⭐ ELITE CASH COW"),
    ("DOT", "DOT-USDT", "Polkadot", 30, "⭐ ELITE CASH COW"),
    ("AVAX", "AVAX-USDT", "Avalanche", 30, "⭐ ELITE CASH COW"),
    ("FET", "FET-USDT", "Artificial Superintelligence", 30, "⭐ ELITE CASH COW"),
    ("SUI", "SUI-USDT", "Sui Network", 30, "⭐ ELITE CASH COW"),
    ("RENDER", "RENDER-USDT", "Render", 30, "⭐ ELITE CASH COW"),
    ("NEAR", "NEAR-USDT", "Near Protocol", 30, "⭐ ELITE CASH COW"),
    ("INJ", "INJ-USDT", "Injective", 30, "⭐ ELITE CASH COW"),
    ("WIF", "WIF-USDT", "Dogwifhat", 30, "⭐ ELITE CASH COW"),
    ("OP", "OP-USDT", "Optimism", 30, "⭐ ELITE CASH COW"),
    ("BTC", "BTC-USDT", "Bitcoin", 30, "⭐ ELITE CASH COW"),
    # --- KOIN PENDUKUNG PROFITABLE ---
    ("XRP", "XRP-USDT", "Ripple", 30, "⚡ TIER 2"),
    ("APT", "APT-USDT", "Aptos", 30, "⚡ TIER 2"),
    ("TIA", "TIA-USDT", "Celestia", 30, "⚡ TIER 2"),
    ("BNB", "BNB-USDT", "Binance Coin", 30, "🔥 ALPHA"),
    ("SOL", "SOL-USDT", "Solana", 30, "🔥 ALPHA"),
    ("LINK", "LINK-USDT", "Chainlink", 30, "⚡ TIER 2"),
    ("DOGE", "DOGE-USDT", "Dogecoin", 30, "🔥 ALPHA"),
    ("ADA", "ADA-USDT", "Cardano", 30, "⚡ TIER 2")
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

def record_closed_trade(coin, sym, outcome, exit_p, closed_ts, roe_override=None, pnl_override=None):
    """Mencatat trade selesai ke riwayat persisten (anti-duplikasi) dan langsung potong/tambah Realized PnL."""
    global _PERSISTENT_SETUPS
    load_persistent_state(force_reload=True)
    with _STATE_LOCK:
        if "_HISTORY_TRADES" not in _PERSISTENT_SETUPS or not isinstance(_PERSISTENT_SETUPS["_HISTORY_TRADES"], list):
            _PERSISTENT_SETUPS["_HISTORY_TRADES"] = []
            
        # Target TP +35.0% ROE (+0.70 USD pada margin 2.00 USD), SL -30.0% ROE (-0.60 USD)
        roe = roe_override if roe_override is not None else (35.0 if outcome == "TP" else -30.0)
        pnl_usd = pnl_override if pnl_override is not None else (0.70 if outcome == "TP" else -0.60)
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
                    raw = raw[-64:]
                    break
        except Exception:
            time.sleep(0.15)
            
    # 2. Cadangan ke BingX jika MEXC sementara unreachable
    if not raw or len(raw) < 32:
        url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=15m&limit=64"
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
                """Membuat level limit order baru yang segar (fresh) dan selalu diskon/premium sejati."""
                ema34 = calc_ema(closes[:-1], 34)
                is_long = closes[-1] >= ema34
                sw_low = min(lows[-33:-1])
                sw_high = max(highs[-33:-1])
                range_span = sw_high - sw_low if sw_high > sw_low else 1.0
                
                tp_ratio = 0.35 / lev # Target TP +35.0% ROE (+1.167% jarak harga pada Lev 30x)
                sl_ratio = 0.30 / lev # Stop Loss -30.0% ROE (-1.000% jarak harga pada Lev 30x)
                retrace = 0.55        # Fibonacci 55% Sweet Spot Pullback
                
                if is_long:
                    potensi = "POTENSI LONG (BUY)"
                    side = "LONG"
                    fibo_p = sw_high - retrace * range_span
                    # Pastikan limit buy selalu di bawah harga pasar saat ini (minimal diskon 0.5%)
                    if fibo_p >= cur_p * 0.998:
                        limit_p = max(sw_low + 0.15 * range_span, cur_p * 0.990)
                    else:
                        limit_p = fibo_p
                    tp_p = limit_p * (1.0 + tp_ratio)
                    sl_p = limit_p * (1.0 - sl_ratio)
                else:
                    potensi = "POTENSI SHORT (SELL)"
                    side = "SHORT"
                    fibo_p = sw_low + retrace * range_span
                    # Pastikan limit sell selalu di atas harga pasar saat ini (minimal premium 0.5%)
                    if fibo_p <= cur_p * 1.002:
                        limit_p = min(sw_high - 0.15 * range_span, cur_p * 1.010)
                    else:
                        limit_p = fibo_p
                    tp_p = limit_p * (1.0 - tp_ratio)
                    sl_p = limit_p * (1.0 + sl_ratio)
                    
                dec = 8 if coin == "PEPE" else 6
                new_s = {
                    "coin": coin,
                    "sym": sym,
                    "name": full_name,
                    "tier": tier_label,
                    "lev": lev,
                    "side": side,
                    "potensi": potensi,
                    "limit_p": round(limit_p, dec),
                    "tp_p": round(tp_p, dec),
                    "sl_p": round(sl_p, dec),
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
                roe_val = 35.0 if outcome == "TP" else -30.0
                pnl_val = 0.70 if outcome == "TP" else -0.60
                record_closed_trade(coin, sym, outcome, cur_p, setup.get('closed_at', now_ts), roe_override=roe_val, pnl_override=pnl_val)
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
                    roe_val = 35.0 if hit_tp else -30.0
                    pnl_val = 0.70 if hit_tp else -0.60
                    record_closed_trade(coin, sym, outcome, exit_p, now_ts, roe_override=roe_val, pnl_override=pnl_val)
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
                    status = "TOUCHED"
                    setup["status"] = "TOUCHED"
                    setup["touch_time"] = now_ts
                    with _STATE_LOCK:
                        _PERSISTENT_SETUPS[coin] = setup
                    save_persistent_state()
                    # Menunggu scan berikutnya untuk evaluasi TP/SL (anti-loop)

            # Hitung jarak real-time ke harga limit
            if is_long:
                diff_pct = ((cur_p - limit_p) / cur_p) * 100
            else:
                diff_pct = ((limit_p - cur_p) / cur_p) * 100
                
            wr_val = COIN_WIN_RATES.get(coin, 67.0)
            
            if status == "TOUCHED":
                if is_long:
                    float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                else:
                    float_roe = ((limit_p - cur_p) / limit_p) * lev * 100
                float_usd = (float_roe / 100.0) * 2.0
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
                "lev": lev,
                "side": side,
                "margin": 2.0,
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
                "diff_pct": diff_pct,
                "wr": wr_val,
                "last_outcome": last_outcome,
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
                r['mexc_badge'] = f"🟢 SUDAH LIMIT DI MEXC (ID: {o['id']})"
                r['float_usd'] = 0.0
                r['float_roe'] = 0.0
                is_long = (o['side'] == 'LONG')
                cur_p = r.get('cur_p', o['price'])
                diff_pct = ((cur_p - o['price']) / cur_p) * 100 if is_long else ((o['price'] - cur_p) / cur_p) * 100
                r['diff_pct'] = diff_pct
                sign_d = "-" if is_long else "+"
                r['float_str'] = f"Jarak: {sign_d}{abs(diff_pct):.2f}% (Antre di MEXC)"
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
                r['mexc_badge'] = "🟡 BELUM LIMIT / SIAP PASANG"
                r['float_usd'] = 0.0
                r['float_roe'] = 0.0
                cur_p = r.get('cur_p', 0.0)
                is_long = "LONG" in r.get('potensi', 'LONG')
                diff_pct = ((cur_p - r['limit_p']) / cur_p) * 100 if is_long and cur_p > 0 else 0.0
                r['diff_pct'] = diff_pct
                r['float_str'] = f"Jarak: {diff_pct:.2f}% (Siap Pasang)"
                r['touch_status'] = "⏳ SIAP PASANG"
                r['valid_label'] = "🟡 BELUM LIMIT"

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

if __name__ == '__main__':
    data = scan_all()
    summ = get_portfolio_summary(data)
    print(f"Scanned {len(data)} coins.")
    print(f"Floating: ${summ['floating_usd']:.2f} ({summ['active_count']} mantul) | Realized: ${summ['realized_usd']:.2f} ({summ['tp_count']} TP / {summ['sl_count']} SL)")
    for d in data[:5]:
        print(f"[{d['coin']}] {d['status']} | {d['potensi']} | Limit: {d['limit_p']} | TP: {d['tp_p']} | SL: {d['sl_p']}")
