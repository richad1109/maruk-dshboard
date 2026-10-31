"""
sinyal_engine.py
=================
Multi-Confirmation Sniper Limit Order Signal Engine
----------------------------------------------------
Strategi: 5-Layer Confluence (HTF Trend + RSI + Order Block SMC + Volume + ATR)
Target WR: 78-85% | Hanya Limit Order | BingX Futures 50 Koin Teratas

Scoring System (0-100):
  Layer 1 - HTF EMA Trend (4H)           : 0-25 pts
  Layer 2 - RSI Pullback/Bounce (1H)     : 0-20 pts
  Layer 3 - Smart Money Order Block (4H) : 0-25 pts
  Layer 4 - Volume Surge (1H)            : 0-15 pts
  Layer 5 - ATR Volatility Quality (1H)  : 0-15 pts

Signal hanya diterbitkan jika skor >= 70.
"""

from __future__ import annotations

import time
import math
import json
import threading
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WIB = timezone(timedelta(hours=7))
BINGX = "https://open-api.bingx.com"
TIMEOUT = 12
SIGNAL_TTL_HOURS = 8
MIN_SCORE = 70
MAX_WORKERS = 12
SCAN_CACHE_FILE = Path(__file__).parent / "assets" / "sinyal_cache.json"
_SCAN_LOCK = threading.Lock()

# ─── 50 KOIN TERATAS BINGX (diperbarui dinamis, ini fallback) ───────────────
FALLBACK_50_COINS = [
    "BTC-USDT","ETH-USDT","SOL-USDT","BNB-USDT","XRP-USDT",
    "DOGE-USDT","ADA-USDT","AVAX-USDT","DOT-USDT","LINK-USDT",
    "MATIC-USDT","NEAR-USDT","OP-USDT","ARB-USDT","SUI-USDT",
    "APT-USDT","INJ-USDT","TIA-USDT","WIF-USDT","PEPE-USDT",
    "FET-USDT","RENDER-USDT","JTO-USDT","BONK-USDT","WLD-USDT",
    "MANTA-USDT","PYTH-USDT","JUP-USDT","STRK-USDT","BLUR-USDT",
    "LTC-USDT","BCH-USDT","FIL-USDT","ATOM-USDT","UNI-USDT",
    "AAVE-USDT","MKR-USDT","SAND-USDT","MANA-USDT","AXS-USDT",
    "GMT-USDT","GALA-USDT","IMX-USDT","DYDX-USDT","CFX-USDT",
    "AGIX-USDT","OCEAN-USDT","LQTY-USDT","CYBER-USDT","ID-USDT",
]


# ═══════════════════════════════════════════════════════════════════════════════
# A. DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def _get(url: str, params: dict, retries: int = 2) -> Optional[dict]:
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT, verify=False)
            data = r.json()
            if str(data.get("code")) == "0":
                return data
        except Exception:
            if i < retries - 1:
                time.sleep(0.3)
    return None


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 200) -> Optional[list[dict]]:
    """Ambil OHLCV dari BingX Swap API v3. Return list of dicts atau None."""
    data = _get(
        f"{BINGX}/openApi/swap/v3/quote/klines",
        {"symbol": symbol, "interval": interval, "limit": limit}
    )
    if data is None:
        return None
    rows = data.get("data", [])
    if not rows or len(rows) < 30:
        return None
    result = []
    for r in rows:
        try:
            result.append({
                "time":   int(r["time"]) / 1000,
                "open":   float(r["open"]),
                "high":   float(r["high"]),
                "low":    float(r["low"]),
                "close":  float(r["close"]),
                "volume": float(r.get("volume", 0)),
            })
        except (KeyError, ValueError, TypeError):
            continue
    if not result:
        return None
    # BingX bisa return desc atau asc, pastikan ascending (oldest first)
    result.sort(key=lambda x: x["time"])
    return result


def fetch_top_50_symbols() -> list[str]:
    """Ambil 50 simbol BingX Futures teratas berdasarkan quote volume 24 jam."""
    data = _get(f"{BINGX}/openApi/swap/v2/quote/ticker", {})
    if data is None:
        return FALLBACK_50_COINS
    tickers = data.get("data", [])
    if not isinstance(tickers, list):
        tickers = [tickers] if isinstance(tickers, dict) else []
    usdt = [
        t for t in tickers
        if isinstance(t, dict) and str(t.get("symbol", "")).endswith("-USDT")
    ]
    usdt.sort(key=lambda x: float(x.get("quoteVolume") or 0), reverse=True)
    symbols = [t["symbol"] for t in usdt[:50]]
    return symbols if len(symbols) >= 10 else FALLBACK_50_COINS


def fetch_current_price(symbol: str) -> Optional[float]:
    """Harga mark price real-time dari BingX."""
    data = _get(f"{BINGX}/openApi/swap/v2/quote/ticker", {"symbol": symbol})
    if data is None:
        return None
    d = data.get("data", {})
    if isinstance(d, list):
        d = d[0] if d else {}
    try:
        return float(d.get("lastPrice") or d.get("closePrice") or 0)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# B. INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def _closes(rows: list[dict]) -> list[float]:
    return [r["close"] for r in rows]


def ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < 2:
        return values[:]
    k = 2.0 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def rsi_series(closes: list[float], period: int = 14) -> list[float]:
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    result = [50.0] * (period + 1)
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rs = avg_g / (avg_l + 1e-10)
        result.append(100 - 100 / (1 + rs))
    return result


def atr_series(rows: list[dict], period: int = 14) -> list[float]:
    tr_list = []
    for i, r in enumerate(rows):
        if i == 0:
            tr_list.append(r["high"] - r["low"])
        else:
            prev_c = rows[i - 1]["close"]
            tr_list.append(max(
                r["high"] - r["low"],
                abs(r["high"] - prev_c),
                abs(r["low"] - prev_c),
            ))
    # Wilder smoothing
    if len(tr_list) < period:
        return tr_list
    result = [0.0] * period
    result.append(sum(tr_list[:period]) / period)
    for i in range(period, len(tr_list)):
        result.append((result[-1] * (period - 1) + tr_list[i]) / period)
    return result


def detect_order_blocks(rows: list[dict], lookback: int = 40) -> list[dict]:
    """
    Smart Money Order Blocks:
    - Bullish OB: Candle bearish terakhir sebelum impuls bullish kuat
    - Bearish OB: Candle bullish terakhir sebelum impuls bearish kuat
    """
    obs = []
    rows = rows[-lookback - 3:]
    if len(rows) < 4:
        return obs

    # Rata-rata body untuk filter "impuls kuat"
    bodies = [abs(r["close"] - r["open"]) for r in rows]
    avg_body = sum(bodies) / max(len(bodies), 1)

    for i in range(1, len(rows) - 2):
        curr = rows[i]
        nxt = rows[i + 1]
        nxt2 = rows[i + 2] if i + 2 < len(rows) else nxt

        curr_body = abs(curr["close"] - curr["open"])
        nxt_body = abs(nxt["close"] - nxt["open"])

        # Bullish OB: curr = bearish → next = strong bullish breaking above curr.high
        if (curr["close"] < curr["open"] and          # bearish candle
                nxt["close"] > nxt["open"] and         # bullish candle
                nxt_body >= avg_body * 1.2 and         # cukup kuat
                nxt["close"] > curr["high"]):          # breakout atas OB
            obs.append({
                "type": "bullish_ob",
                "high": curr["high"],
                "low": curr["low"],
                "mid": (curr["high"] + curr["low"]) / 2,
                "time": curr["time"],
                "strength": nxt_body / (avg_body + 1e-10),
            })

        # Bearish OB: curr = bullish → next = strong bearish breaking below curr.low
        if (curr["close"] > curr["open"] and           # bullish candle
                nxt["close"] < nxt["open"] and          # bearish candle
                nxt_body >= avg_body * 1.2 and          # cukup kuat
                nxt["close"] < curr["low"]):            # breakout bawah OB
            obs.append({
                "type": "bearish_ob",
                "high": curr["high"],
                "low": curr["low"],
                "mid": (curr["high"] + curr["low"]) / 2,
                "time": curr["time"],
                "strength": nxt_body / (avg_body + 1e-10),
            })

    return obs


def detect_fvg(rows: list[dict]) -> list[dict]:
    """Fair Value Gap (Imbalance) — area yang sering diisi ulang."""
    fvgs = []
    for i in range(2, len(rows)):
        prev = rows[i - 2]
        curr = rows[i]
        # Bullish FVG: gap antara high[i-2] dan low[i]
        if curr["low"] > prev["high"]:
            fvgs.append({
                "type": "bullish_fvg",
                "high": curr["low"],
                "low": prev["high"],
                "mid": (curr["low"] + prev["high"]) / 2,
                "time": curr["time"],
            })
        # Bearish FVG: gap antara low[i-2] dan high[i]
        if curr["high"] < prev["low"]:
            fvgs.append({
                "type": "bearish_fvg",
                "high": prev["low"],
                "low": curr["high"],
                "mid": (prev["low"] + curr["high"]) / 2,
                "time": curr["time"],
            })
    return fvgs[-20:]  # Hanya 20 FVG terbaru


def kaufman_er(closes: list[float], period: int = 10) -> float:
    """Kaufman Efficiency Ratio — mengukur seberapa 'trending' pasar."""
    if len(closes) < period + 1:
        return 0.3
    net = abs(closes[-1] - closes[-(period + 1)])
    path = sum(abs(closes[-i] - closes[-i - 1]) for i in range(1, period + 1))
    return net / (path + 1e-10)


# ═══════════════════════════════════════════════════════════════════════════════
# C. SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _price_decimals(price: float) -> int:
    if price >= 10000:
        return 1
    if price >= 100:
        return 2
    if price >= 1:
        return 4
    if price >= 0.01:
        return 5
    return 8


def _fmt(v: float) -> float:
    d = _price_decimals(abs(v))
    return round(v, d)


def score_and_generate(rows_4h: list[dict], rows_1h: list[dict]) -> Optional[dict]:
    """
    Core engine: hitung 5-layer score dan generate sinyal jika lolos MIN_SCORE.
    Return dict sinyal atau None.
    """
    if len(rows_4h) < 60 or len(rows_1h) < 60:
        return None

    # Semua indikator
    closes_4h = _closes(rows_4h)
    closes_1h = _closes(rows_1h)

    ema20_4h = ema_series(closes_4h, 20)[-1]
    ema50_4h = ema_series(closes_4h, 50)[-1]
    ema200_4h = ema_series(closes_4h, 200)[-1] if len(closes_4h) >= 200 else ema_series(closes_4h, len(closes_4h) // 2)[-1]
    rsi_4h_all = rsi_series(closes_4h, 14)
    rsi_4h = rsi_4h_all[-1]

    ema20_1h = ema_series(closes_1h, 20)[-1]
    ema50_1h = ema_series(closes_1h, 50)[-1]
    rsi_1h_all = rsi_series(closes_1h, 14)
    rsi_1h = rsi_1h_all[-1]

    atr_4h_all = atr_series(rows_4h, 14)
    atr_4h = atr_4h_all[-1] if atr_4h_all else rows_4h[-1]["close"] * 0.02

    atr_1h_all = atr_series(rows_1h, 14)
    atr_1h = atr_1h_all[-1] if atr_1h_all else rows_1h[-1]["close"] * 0.005

    vol_1h_last = rows_1h[-1]["volume"]
    vol_1h_ma20 = sum(r["volume"] for r in rows_1h[-21:-1]) / 20 if len(rows_1h) >= 21 else vol_1h_last

    ker = kaufman_er(closes_1h, 10)
    obs_4h = detect_order_blocks(rows_4h, 40)
    fvgs_1h = detect_fvg(rows_1h[-30:])

    price = rows_1h[-1]["close"]
    atr_pct = (atr_1h / price) * 100

    # ── Scoring per arah ──────────────────────────────────────────────────────
    score_l = 0
    score_s = 0
    reasons_l: list[str] = []
    reasons_s: list[str] = []

    # ── Layer 1: HTF EMA Trend (4H) — 25 pts ─────────────────────────────────
    if ema20_4h > ema50_4h > ema200_4h:
        score_l += 25; reasons_l.append("✅ EMA20>50>200 Bull Aligned")
    elif ema20_4h > ema50_4h:
        score_l += 15; reasons_l.append("🟡 EMA20>50 Mild Bull")
    elif ema20_4h > ema200_4h:
        score_l += 8; reasons_l.append("EMA20>200 Weak Bull")

    if ema20_4h < ema50_4h < ema200_4h:
        score_s += 25; reasons_s.append("✅ EMA20<50<200 Bear Aligned")
    elif ema20_4h < ema50_4h:
        score_s += 15; reasons_s.append("🟡 EMA20<50 Mild Bear")
    elif ema20_4h < ema200_4h:
        score_s += 8; reasons_s.append("EMA20<200 Weak Bear")

    # ── Layer 2: RSI Pullback/Bounce (1H) — 20 pts ───────────────────────────
    # Long: 4H bullish (RSI>50), 1H pullback (RSI 35-55) → dip buying
    if rsi_4h > 52 and 35 <= rsi_1h <= 55:
        score_l += 20; reasons_l.append(f"✅ RSI Dip: 4H={rsi_4h:.0f} 1H={rsi_1h:.0f}")
    elif rsi_4h > 50 and rsi_1h < 52:
        score_l += 10; reasons_l.append(f"🟡 RSI Mild Dip: 4H={rsi_4h:.0f}")
    elif rsi_4h > 50 and rsi_1h < 65:
        score_l += 5

    # Short: 4H bearish (RSI<50), 1H bounce (RSI 45-65) → rally selling
    if rsi_4h < 48 and 45 <= rsi_1h <= 65:
        score_s += 20; reasons_s.append(f"✅ RSI Bounce: 4H={rsi_4h:.0f} 1H={rsi_1h:.0f}")
    elif rsi_4h < 50 and rsi_1h > 48:
        score_s += 10; reasons_s.append(f"🟡 RSI Mild Bounce: 4H={rsi_4h:.0f}")
    elif rsi_4h < 50 and rsi_1h > 35:
        score_s += 5

    # ── Layer 3: Smart Money Order Block (4H) — 25 pts ───────────────────────
    proximity_mul = 1.0  # ATR multiplier untuk proximity check
    best_bullish_ob = None
    best_bearish_ob = None

    for ob in reversed(obs_4h[-15:]):
        dist = abs(price - ob["mid"])
        if ob["type"] == "bullish_ob" and dist < atr_4h * proximity_mul:
            if best_bullish_ob is None or dist < abs(price - best_bullish_ob["mid"]):
                best_bullish_ob = ob
        if ob["type"] == "bearish_ob" and dist < atr_4h * proximity_mul:
            if best_bearish_ob is None or dist < abs(price - best_bearish_ob["mid"]):
                best_bearish_ob = ob

    if best_bullish_ob:
        strength = min(best_bullish_ob.get("strength", 1.5), 3.0)
        pts = int(15 + (strength - 1) * 5)
        score_l += min(pts, 25)
        reasons_l.append(f"✅ Bullish OB @ {_fmt(best_bullish_ob['low'])}-{_fmt(best_bullish_ob['high'])}")
    else:
        # Cek FVG sebagai alternatif
        for fvg in reversed(fvgs_1h):
            if fvg["type"] == "bullish_fvg" and abs(price - fvg["mid"]) < atr_1h * 1.5:
                score_l += 12; reasons_l.append(f"🟡 Bullish FVG @ {_fmt(fvg['low'])}-{_fmt(fvg['high'])}"); break

    if best_bearish_ob:
        strength = min(best_bearish_ob.get("strength", 1.5), 3.0)
        pts = int(15 + (strength - 1) * 5)
        score_s += min(pts, 25)
        reasons_s.append(f"✅ Bearish OB @ {_fmt(best_bearish_ob['low'])}-{_fmt(best_bearish_ob['high'])}")
    else:
        for fvg in reversed(fvgs_1h):
            if fvg["type"] == "bearish_fvg" and abs(price - fvg["mid"]) < atr_1h * 1.5:
                score_s += 12; reasons_s.append(f"🟡 Bearish FVG @ {_fmt(fvg['low'])}-{_fmt(fvg['high'])}"); break

    # ── Layer 4: Volume Surge (1H) — 15 pts ──────────────────────────────────
    vol_ratio = vol_1h_last / (vol_1h_ma20 + 1e-10)
    if vol_ratio >= 2.0:
        v_pts = 15; v_note = f"✅ Volume {vol_ratio:.1f}x avg"
    elif vol_ratio >= 1.5:
        v_pts = 10; v_note = f"🟡 Volume {vol_ratio:.1f}x avg"
    elif vol_ratio >= 1.1:
        v_pts = 5; v_note = f"Volume {vol_ratio:.1f}x avg"
    else:
        v_pts = 0; v_note = f"Volume rendah {vol_ratio:.1f}x"
    score_l += v_pts; score_s += v_pts
    reasons_l.append(v_note); reasons_s.append(v_note)

    # ── Layer 5: ATR & KER Quality (1H) — 15 pts ─────────────────────────────
    if 0.2 <= atr_pct <= 3.0 and ker >= 0.3:
        q_pts = 15; q_note = f"✅ ATR {atr_pct:.2f}% | KER {ker:.2f}"
    elif 0.15 <= atr_pct <= 5.0 and ker >= 0.2:
        q_pts = 8; q_note = f"🟡 ATR {atr_pct:.2f}% | KER {ker:.2f}"
    elif atr_pct > 0.1:
        q_pts = 3; q_note = f"ATR {atr_pct:.2f}% | KER {ker:.2f}"
    else:
        q_pts = 0; q_note = f"Volatilitas terlalu kecil"
    score_l += q_pts; score_s += q_pts
    reasons_l.append(q_note); reasons_s.append(q_note)

    # ── Pilih arah terbaik ────────────────────────────────────────────────────
    if score_l >= score_s and score_l >= MIN_SCORE:
        direction = "LONG"
        final_score = min(score_l, 100)
        reasons = reasons_l
    elif score_s > score_l and score_s >= MIN_SCORE:
        direction = "SHORT"
        final_score = min(score_s, 100)
        reasons = reasons_s
    else:
        return None  # Skor tidak mencukupi

    # ── Hitung Entry, TP1/2/3, SL berbasis ATR ───────────────────────────────
    if direction == "LONG":
        # Limit BUY: pasang di bawah harga saat ini (tunggu retrace)
        # Entry terbaik: di EMA20 1H atau 0.4xATR di bawah harga, pilih yang lebih dekat ke harga
        entry_opt_a = ema20_1h
        entry_opt_b = price - atr_1h * 0.4
        entry = max(entry_opt_a, entry_opt_b)           # ambil yang lebih tinggi (lebih dekat ke harga)
        entry = min(entry, price * 0.998)               # pastikan di bawah harga current
        entry = max(entry, price * 0.93)                # jangan terlalu jauh (maks 7% di bawah)

        sl = entry - atr_1h * 1.2                       # 1.2 ATR di bawah entry
        tp1 = entry + atr_1h * 1.5                      # 1.5R
        tp2 = entry + atr_1h * 2.5                      # 2.5R
        tp3 = entry + atr_1h * 4.0                      # 4R

    else:  # SHORT
        # Limit SELL: pasang di atas harga saat ini (tunggu bounce)
        entry_opt_a = ema20_1h
        entry_opt_b = price + atr_1h * 0.4
        entry = min(entry_opt_a, entry_opt_b)
        entry = max(entry, price * 1.002)               # pastikan di atas harga
        entry = min(entry, price * 1.07)                # jangan terlalu jauh

        sl = entry + atr_1h * 1.2
        tp1 = entry - atr_1h * 1.5
        tp2 = entry - atr_1h * 2.5
        tp3 = entry - atr_1h * 4.0

    # Risk-Reward ratio
    risk = abs(entry - sl)
    rr = round(abs(tp1 - entry) / (risk + 1e-10), 2)

    now_ts = time.time()
    valid_until_ts = now_ts + SIGNAL_TTL_HOURS * 3600
    valid_until_wib = datetime.fromtimestamp(valid_until_ts, WIB).strftime("%H:%M WIB")

    return {
        "direction": direction,
        "score": final_score,
        "entry": _fmt(entry),
        "sl": _fmt(sl),
        "tp1": _fmt(tp1),
        "tp2": _fmt(tp2),
        "tp3": _fmt(tp3),
        "current_price": _fmt(price),
        "atr_1h": _fmt(atr_1h),
        "rsi_4h": round(rsi_4h, 1),
        "rsi_1h": round(rsi_1h, 1),
        "ker": round(ker, 3),
        "vol_ratio": round(vol_ratio, 2),
        "rr": rr,
        "reasons": reasons,
        "generated_at": now_ts,
        "valid_until": valid_until_ts,
        "valid_until_wib": valid_until_wib,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# D. STATUS TRACKER
# ═══════════════════════════════════════════════════════════════════════════════

def get_signal_status(sig: dict, current_price: float) -> str:
    """
    Status real-time sinyal berdasarkan harga saat ini:
      SCANNING    → Menunggu retrace ke entry (harga belum sampai)
      MENDEKATI   → Harga dalam 0.5% dari entry (hampir terisi)
      AKTIF       → Harga sudah menyentuh/melewati entry (posisi terisi)
      TP1_HIT     → TP1 tercapai
      TP2_HIT     → TP2 tercapai
      TP3_HIT     → TP3 tercapai (jackpot)
      KENA_SL     → Stop loss tercapai
      TELAT       → Harga lari terlalu jauh dari entry (sinyal basi)
      EXPIRED     → Waktu validitas habis
    """
    now_ts = time.time()
    valid_until = sig.get("valid_until", now_ts)

    if now_ts > valid_until:
        return "EXPIRED"

    d = sig["direction"]
    entry = float(sig["entry"])
    sl = float(sig["sl"])
    tp1 = float(sig["tp1"])
    tp2 = float(sig["tp2"])
    tp3 = float(sig["tp3"])

    if d == "LONG":
        # Sudah kena exit?
        if current_price <= sl:
            return "KENA_SL"
        if current_price >= tp3:
            return "TP3_HIT"
        if current_price >= tp2:
            return "TP2_HIT"
        if current_price >= tp1:
            return "TP1_HIT"

        dist_pct = (current_price - entry) / entry * 100

        # Harga lari naik > 3% tanpa terisi entry → sinyal telat
        if dist_pct > 3.0:
            return "TELAT"
        # Harga sudah di bawah atau dalam 0.5% entry → terisi
        if current_price <= entry * 1.005:
            # Sudah terisi, cek apakah harga masih di antara entry dan SL
            return "AKTIF"
        # Harga dalam 0.5% di atas entry → mendekati
        if current_price <= entry * 1.005:
            return "MENDEKATI"
        # Masih menunggu retrace
        return "SCANNING"

    else:  # SHORT
        if current_price >= sl:
            return "KENA_SL"
        if current_price <= tp3:
            return "TP3_HIT"
        if current_price <= tp2:
            return "TP2_HIT"
        if current_price <= tp1:
            return "TP1_HIT"

        dist_pct = (entry - current_price) / entry * 100

        # Harga drop > 3% tanpa terisi → telat
        if dist_pct > 3.0:
            return "TELAT"
        if current_price >= entry * 0.995:
            return "AKTIF"
        return "SCANNING"


def status_label(status: str) -> tuple[str, str]:
    """Return (emoji_label, css_color) untuk tampilan UI."""
    MAP = {
        "SCANNING":  ("🔍 SCANNING",  "#7ec8e3"),
        "MENDEKATI": ("⚡ MENDEKATI", "#f0c040"),
        "AKTIF":     ("✅ AKTIF",      "#4caf50"),
        "TP1_HIT":   ("🎯 TP1 KENA",  "#00e676"),
        "TP2_HIT":   ("🎯🎯 TP2 KENA","#00bcd4"),
        "TP3_HIT":   ("💰 TP3 KENA",  "#ffd700"),
        "KENA_SL":   ("❌ KENA SL",   "#f44336"),
        "TELAT":     ("⏰ TELAT",      "#9e9e9e"),
        "EXPIRED":   ("💀 EXPIRED",   "#616161"),
    }
    return MAP.get(status, ("❓ UNKNOWN", "#ffffff"))


# ═══════════════════════════════════════════════════════════════════════════════
# E. MAIN SCAN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_symbol(symbol: str) -> Optional[dict]:
    """Pipeline lengkap untuk 1 simbol. Thread-safe."""
    try:
        rows_4h = fetch_klines(symbol, "4h", 220)
        rows_1h = fetch_klines(symbol, "1h", 220)
        if rows_4h is None or rows_1h is None:
            return None
        result = score_and_generate(rows_4h, rows_1h)
        if result is None:
            return None
        return {"symbol": symbol, **result}
    except Exception:
        return None


def scan_50_coins(progress_callback=None) -> list[dict]:
    """
    Scan 50 koin teratas BingX secara paralel.
    Hanya return sinyal dengan score >= MIN_SCORE, diurutkan tertinggi.
    progress_callback(done, total) dipanggil tiap koin selesai.
    """
    symbols = fetch_top_50_symbols()
    total = len(symbols)
    signals = []
    done_count = 0
    lock = threading.Lock()

    def worker(sym):
        nonlocal done_count
        result = analyze_symbol(sym)
        with lock:
            done_count += 1
            if progress_callback:
                try:
                    progress_callback(done_count, total)
                except Exception:
                    pass
        return result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(worker, s): s for s in symbols}
        for fut in as_completed(futures):
            try:
                r = fut.result(timeout=30)
                if r is not None:
                    signals.append(r)
            except Exception:
                pass

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals


# ═══════════════════════════════════════════════════════════════════════════════
# F. CACHE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_cache() -> Optional[dict]:
    """Load sinyal cache dari file JSON."""
    try:
        if SCAN_CACHE_FILE.exists():
            raw = json.loads(SCAN_CACHE_FILE.read_text(encoding="utf-8"))
            return raw
    except Exception:
        pass
    return None


def save_cache(signals: list[dict]) -> None:
    """Simpan sinyal ke file cache."""
    try:
        SCAN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCAN_CACHE_FILE.write_text(
            json.dumps({"signals": signals, "scanned_at": time.time()}, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


def get_cached_signals(max_age_minutes: int = 15) -> Optional[list[dict]]:
    """Return sinyal dari cache jika belum expired, else None."""
    data = load_cache()
    if data is None:
        return None
    scanned_at = data.get("scanned_at", 0)
    age_min = (time.time() - scanned_at) / 60
    if age_min > max_age_minutes:
        return None
    return data.get("signals", [])


def refresh_scan(progress_callback=None) -> list[dict]:
    """Scan ulang 50 koin dan update cache."""
    signals = scan_50_coins(progress_callback=progress_callback)
    save_cache(signals)
    return signals
