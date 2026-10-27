#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sniper_limit_engine.py
-----------------------
Engine Sinyal Kripto Limit Order Sniper 20 Koin (Whale Wick - Realistis Tanpa Ilusi).
Menjaga status aktif setelah mantul:
- Jika sudah terjemput (mantul), status TETAP FLOATING PROFIT sampai kena TP atau SL!
- Tidak akan reset ke 'menunggu jemputan' sebelum siklus selesai.
- Menampilkan:
  * ⚡ LIMIT TERJEMPUT (MANTUL): Floating Profit (+ROE% & +USD)
  * 🎯 TARGET TP TERSENTUH (+35% ROE | +$0.70 USD)
  * 🛑 STOP LOSS TERSENTUH (-36% ROE | -$0.72 USD)
  * ⏳ LIMIT BELUM KESENTUH: Jarak % ke titik jemputan
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
            if not raw or len(raw) < 30:
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
            
            # Base Swing S/R dari 32 candle awal (candle 0 s/d 31)
            # Candle 32 s/d 47 (16 candle terakhir = 4 jam) adalah execution window
            split_idx = max(24, n - 16)
            base_lows = lows[:split_idx]
            base_highs = highs[:split_idx]
            
            sw_low = min(base_lows)
            sw_high = max(base_highs)
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
                
                # Cari candle pertama di execution window yang menyentuh limit
                fill_idx = -1
                for idx in range(split_idx, n):
                    if lows[idx] <= limit_p:
                        fill_idx = idx
                        break
                        
                if fill_idx != -1:
                    # LIMIT SUDAH TERSENTUH / MANTUL!
                    sub_highs = highs[fill_idx:]
                    sub_lows = lows[fill_idx:]
                    hit_tp = max(sub_highs) >= tp_p
                    hit_sl = min(sub_lows) <= sl_p
                    is_touched = True
                    
                    if hit_tp:
                        touch_status = "🎯 TARGET TP TERSENTUH"
                        valid_label = "🎯 SUDAH TP (MANTUL SUKSES)"
                        float_roe = 35.0
                        float_usd = 0.70
                        float_str = "🎯 HIT TP! (+35.0% ROE | +$0.70 USD) 🏆"
                    elif hit_sl:
                        touch_status = "🛑 STOP LOSS TERSENTUH"
                        valid_label = "🛑 HIT SL (STOP LOSS)"
                        float_roe = -36.0
                        float_usd = -0.72
                        float_str = "🛑 HIT SL! (-36.0% ROE | -$0.72 USD)"
                    else:
                        touch_status = "⚡ SUDAH KESENTUH (TERISI)"
                        valid_label = "✅ VALID (SEDANG MANTUL)"
                        float_roe = ((cur_p - limit_p) / limit_p) * lev * 100
                        float_usd = (float_roe / 100.0) * 2.0
                        sign = "+" if float_roe >= 0 else ""
                        float_str = f"Floating: {sign}${float_usd:.2f} ({sign}{float_roe:.1f}% ROE)"
                else:
                    # Belum tersentuh sama sekali
                    is_touched = False
                    touch_status = "⏳ BELUM KESENTUH"
                    float_roe = 0.0
                    float_usd = 0.0
                    float_str = f"Jarak: -{diff_pct:.2f}% (Menunggu jemputan)"
                    if diff_pct <= 2.0:
                        valid_label = "✅ SETUP VALID"
                    else:
                        valid_label = "🔍 MEMINDAI (BELUM VALID)"
            else:
                potensi = "POTENSI SHORT (SELL)"
                limit_p = sw_high * (1.0 + offset_pct)
                tp_p = limit_p * (1.0 - tp_ratio)
                sl_p = limit_p * (1.0 + sl_ratio)
                diff_pct = ((limit_p - cur_p) / cur_p) * 100
                
                # Cari candle pertama di execution window yang menyentuh short limit
                fill_idx = -1
                for idx in range(split_idx, n):
                    if highs[idx] >= limit_p:
                        fill_idx = idx
                        break
                        
                if fill_idx != -1:
                    # LIMIT SUDAH TERSENTUH / MANTUL!
                    sub_highs = highs[fill_idx:]
                    sub_lows = lows[fill_idx:]
                    hit_tp = min(sub_lows) <= tp_p
                    hit_sl = max(sub_highs) >= sl_p
                    is_touched = True
                    
                    if hit_tp:
                        touch_status = "🎯 TARGET TP TERSENTUH"
                        valid_label = "🎯 SUDAH TP (MANTUL SUKSES)"
                        float_roe = 35.0
                        float_usd = 0.70
                        float_str = "🎯 HIT TP! (+35.0% ROE | +$0.70 USD) 🏆"
                    elif hit_sl:
                        touch_status = "🛑 STOP LOSS TERSENTUH"
                        valid_label = "🛑 HIT SL (STOP LOSS)"
                        float_roe = -36.0
                        float_usd = -0.72
                        float_str = "🛑 HIT SL! (-36.0% ROE | -$0.72 USD)"
                    else:
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
                    if diff_pct <= 2.0:
                        valid_label = "✅ SETUP VALID"
                    else:
                        valid_label = "🔍 MEMINDAI (BELUM VALID)"
            
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
