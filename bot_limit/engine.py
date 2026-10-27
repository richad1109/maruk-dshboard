#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py
---------
Mesin Kuantitatif Limit Order Sniper 20 Koin (Whale Wick & Pullback).
Logika Penguncian Siklus Mantul & Pembaruan Kontinu:
1. Posisi yang sudah terjemput (mantul) DIKUNCI statusnya sebagai TERISI MANTUL dengan live Floating Profit.
2. Posisi TIDAK AKAN PERNAH kembali ke 'menunggu jemputan' selama posisi aktif.
3. Begitu menyentuh Target TP (+35% ROE) atau Stop Loss (-36% ROE):
   - Hasil keuntungan/kerugian dikunci ke ringkasan portofolio.
   - Sistem OTOMATIS memindai struktur pasar terkini dan MENERBITKAN SETUP LIMIT BARU agar pengguna selalu siap pasang limit berikutnya.
"""

import time
import requests
import urllib3
from config import (
    MARGIN_PER_TRADE, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER,
    AUTO_BEP_TRIGGER_ROE, COIN_WIN_RATES
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_15m_candles(sym, limit=48):
    """Mengambil candle 15M dari API publik BingX."""
    url = f"https://open-api.bingx.com/openApi/swap/v3/quote/klines?symbol={sym}&interval=15m&limit={limit}"
    for _ in range(3):
        try:
            r = requests.get(url, verify=False, timeout=5.0).json()
            d = r.get('data', [])
            if len(d) >= 32:
                if d[0]['time'] > d[-1]['time']:
                    d.reverse()
                return d
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    return []

def analyze_coin(coin_cfg):
    coin = coin_cfg['coin']
    sym = coin_cfg['sym']
    lev = coin_cfg['lev']
    tier = coin_cfg['tier']
    
    raw = fetch_15m_candles(sym, limit=48)
    if len(raw) < 32:
        return None
        
    opens = [float(k['open']) for k in raw]
    highs = [float(k['high']) for k in raw]
    lows = [float(k['low']) for k in raw]
    closes = [float(k['close']) for k in raw]
    cur_p = closes[-1]
    n = len(raw)
    
    sw_low = min(lows[:32])
    sw_high = max(highs[:32])
    range_span = sw_high - sw_low if sw_high > sw_low else 1.0
    pos_in_range = (cur_p - sw_low) / range_span
    
    tp_ratio = 0.35 / lev
    sl_ratio = 0.36 / lev
    offset_pct = 0.0020
    
    wr_val = COIN_WIN_RATES.get(coin, 67.0)
    is_long = pos_in_range < 0.65
    
    if is_long:
        potensi = "POTENSI LONG (BUY)"
        limit_p = sw_low * (1.0 - offset_pct)
        tp_p = limit_p * (1.0 + tp_ratio)
        sl_p = limit_p * (1.0 - sl_ratio)
        diff_pct = ((cur_p - limit_p) / cur_p) * 100
        
        fill_idx = -1
        for idx in range(20, n):
            if lows[idx] <= limit_p:
                fill_idx = idx
                break
                
        if fill_idx != -1:
            sub_highs = highs[fill_idx:]
            sub_lows = lows[fill_idx:]
            hit_tp = max(sub_highs) >= tp_p
            hit_sl = min(sub_lows) <= sl_p
            
            if hit_tp:
                fresh_limit = min(lows[-16:]) * (1.0 - offset_pct)
                fresh_diff = ((cur_p - fresh_limit) / cur_p) * 100
                is_touched = True
                touch_status = "🎯 SUDAH HIT TP"
                valid_status = "🎯 SUDAH TP (PINDAI SETUP BARU)"
                float_roe = 35.0
                float_usd = 0.70
                float_str = "🎯 HIT TP! (+35.0% ROE | +$0.70 USD) 🏆"
                limit_p = fresh_limit
                tp_p = limit_p * (1.0 + tp_ratio)
                sl_p = limit_p * (1.0 - sl_ratio)
                diff_pct = fresh_diff
            elif hit_sl:
                fresh_limit = min(lows[-16:]) * (1.0 - offset_pct)
                fresh_diff = ((cur_p - fresh_limit) / cur_p) * 100
                is_touched = True
                touch_status = "🛑 SUDAH HIT SL"
                valid_status = "🛑 HIT SL (PINDAI SETUP BARU)"
                float_roe = -36.0
                float_usd = -0.72
                float_str = "🛑 HIT SL! (-36.0% ROE | -$0.72 USD)"
                limit_p = fresh_limit
                tp_p = limit_p * (1.0 + tp_ratio)
                sl_p = limit_p * (1.0 - sl_ratio)
                diff_pct = fresh_diff
            else:
                is_touched = True
                touch_status = "⚡ SUDAH KESENTUH (TERISI)"
                valid_status = "✅ VALID (SEDANG MANTUL)"
                float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                float_usd = (float_roe / 100.0) * MARGIN_PER_TRADE
                sign = "+" if float_roe >= 0 else ""
                float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
        else:
            is_touched = False
            touch_status = "⏳ BELUM KESENTUH"
            float_roe = 0.0
            float_usd = 0.0
            float_str = f"Jarak: -{diff_pct:.2f}% (Menunggu jemputan)"
            valid_status = "✅ SETUP VALID" if diff_pct <= 2.0 else "🔍 MEMINDAI (BELUM VALID)"
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
            sub_highs = highs[fill_idx:]
            sub_lows = lows[fill_idx:]
            hit_tp = min(sub_lows) <= tp_p
            hit_sl = max(sub_highs) >= sl_p
            
            if hit_tp:
                fresh_limit = max(highs[-16:]) * (1.0 + offset_pct)
                fresh_diff = ((fresh_limit - cur_p) / cur_p) * 100
                is_touched = True
                touch_status = "🎯 SUDAH HIT TP"
                valid_status = "🎯 SUDAH TP (PINDAI SETUP BARU)"
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
                valid_status = "🛑 HIT SL (PINDAI SETUP BARU)"
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
                valid_status = "✅ VALID (SEDANG MANTUL)"
                float_roe = ((limit_p - cur_p) / limit_p) * lev * 100
                float_usd = (float_roe / 100.0) * MARGIN_PER_TRADE
                sign = "+" if float_roe >= 0 else ""
                float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
        else:
            is_touched = False
            touch_status = "⏳ BELUM KESENTUH"
            float_roe = 0.0
            float_usd = 0.0
            float_str = f"Jarak: +{diff_pct:.2f}% (Menunggu jemputan)"
            valid_status = "✅ SETUP VALID" if diff_pct <= 2.0 else "🔍 MEMINDAI (BELUM VALID)"
            
    return {
        "coin": coin,
        "sym": sym,
        "name": coin_cfg.get('name', coin),
        "tier": tier,
        "lev": lev,
        "margin": MARGIN_PER_TRADE,
        "cur_p": cur_p,
        "potensi": potensi,
        "valid_status": valid_status,
        "touch_status": touch_status,
        "is_touched": is_touched,
        "float_str": float_str,
        "float_roe": float_roe,
        "float_usd": float_usd,
        "limit_p": limit_p,
        "sl_p": sl_p,
        "tp_p": tp_p,
        "diff_pct": diff_pct,
        "wr": wr_val
    }
