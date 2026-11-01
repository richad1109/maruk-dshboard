#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vps_bot2_auto_sniper.py
-------------------------
BOT 2: AUTO-PILOT LIMIT SNIPER 50 KOIN (MARGIN $0.20 | LEVERAGE 40X ISOLATED)
Fitur Utama:
1. 100% Otomatis: Scan 50 koin -> Pasang Limit Order -> Attach TP/SL -> Auto-BEP Lock.
2. DUA ARAH: LONG dan SHORT secara otomatis mengikuti trend.
3. Macro Shield 4H BTC: Anti-Short saat BTC Pump & Anti-Long saat BTC Dump.
4. Auto-BEP Scanner: Setiap 15 detik memindai posisi terbuka, jika profit >= +25% ROE (+0.8R),
   SL otomatis digeser ke Entry + 0.05% (Modal 100% Aman & Terkunci).
5. Margin Flat: $0.20 USDT per order, Leverage 40x Isolated.
6. Push Notifikasi ke HP via ntfy (maruk_sinal & maruk_sinyal).
7. Terpisah 100% dari Bot 1 (Compounding Armada 8 Wallet).
"""

import os
import sys
import time
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.parse

# Set path agar modul lokal terbaca
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import sinyal_engine
import bingx_executor

WIB = timezone(timedelta(hours=7))

# ─── KONFIGURASI BOT 2 ────────────────────────────────────────────────────────
CONFIG = {
    "account_key": "akun_1",
    "margin_usd": 0.20,          # $0.20 USDT flat per order
    "leverage": 40,              # 40x Isolated
    "min_score": 75,             # Hanya sinyal valid skor tinggi (>= 75)
    "max_concurrent_limits": 15, # Maksimal 15 limit order antre serentak
    "scan_interval_sec": 120,    # Scan sinyal baru setiap 2 menit (120 detik)
    "bep_check_interval_sec": 45,# Cek & kunci BEP setiap 45 detik (aman dari rate limit BingX)
    "min_bep_roe": 15.0,         # Kunci BEP saat floating profit >= +15.0% ROE (konsisten dg backtest)
    "ntfy_topics": ["maruk_sinal", "maruk_sinyal", "maruk_sinyal_adee"],
}

STATE_FILE = BASE_DIR / "assets" / "bot2_sniper_state.json"

def log(msg, tag="INFO"):
    now_str = datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")
    print(f"[{now_str}] [{tag}] {msg}", flush=True)

def send_ntfy(title, message, priority="high", tags="rocket"):
    for topic in CONFIG["ntfy_topics"]:
        url = f"https://ntfy.sh/{topic}"
        try:
            safe_title = title.encode("ascii", "ignore").decode("ascii").strip()
            req = urllib.request.Request(
                url,
                data=message.encode("utf-8"),
                headers={"Title": safe_title, "Priority": priority, "Tags": tags},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8):
                pass
        except Exception:
            pass

def save_state(status_data):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(status_data, indent=2), encoding="utf-8")
    except Exception:
        pass

def get_btc_htf_trend():
    """Periksa trend BTC 4H untuk mencegah counter-trend konyol."""
    try:
        client = bingx_executor.get_bingx_client(CONFIG["account_key"])
        if not client:
            return "NEUTRAL"
        kl = client.fetch_ohlcv("BTC/USDT:USDT", timeframe="4h", limit=35)
        if len(kl) >= 30:
            closes = [c[4] for c in kl]
            k = 2.0 / (30 + 1)
            ema = sum(closes[:30]) / 30
            for p in closes[30:]:
                ema = p * k + ema * (1 - k)
            if closes[-1] > ema:
                return "BULLISH"
            elif closes[-1] < ema:
                return "BEARISH"
    except Exception as e:
        log(f"BTC HTF Trend check warning: {e}", "WARN")
    return "NEUTRAL"

# ─── THREAD 1: AUTO-BEP PATROL SCANNER (TIAP 15 DETIK) ───────────────────────
def bep_patrol_worker():
    log(f"Thread Auto-BEP Patrol Aktif! Memindai posisi terbuka tiap {CONFIG['bep_check_interval_sec']} detik...", "START")
    scan_count = 0
    while True:
        try:
            bep_res = bingx_executor.apply_bep_to_profit_positions(
                account_key=CONFIG["account_key"],
                min_roe=CONFIG["min_bep_roe"]
            )
            scan_count += 1
            if bep_res.get("success"):
                details = bep_res.get("details", [])
                skipped = bep_res.get("skipped", [])

                # Kirim ntfy dan log khusus jika ada yang baru berhasil dipindah ke BEP
                for d in details:
                    if "BERHASIL" in d:
                        log(f"🛡️ AUTO-BEP: {d}", "BEP")
                        send_ntfy(
                            title="🛡️ AUTO-BEP TERKUNCI (MODAL AMAN)",
                            message=f"{d} - Stop Loss dipindah ke Entry (Bebas Risiko Rugi)!",
                            tags="shield,white_check_mark"
                        )

                # Log ringkasan status patroli setiap siklus scan
                bep_count = len(details)
                wait_count = len(skipped)
                bep_names = ", ".join([d.split(":")[0].replace("🔒", "").replace("🛡️", "").strip() for d in details])
                log(f"🛡️ Patroli BEP #{scan_count}: {bep_count} koin terkunci BEP ({bep_names or 'belum ada'}), {wait_count} koin memantau target ROE +{CONFIG['min_bep_roe']}%.", "BEP_PATROL")
        except Exception as e:
            log(f"Error pada patroli BEP: {e}", "ERROR")
        time.sleep(CONFIG["bep_check_interval_sec"])

# ─── THREAD 2: AUTO LIMIT SCANNER & PLACER (TIAP 2 MENIT) ───────────────────
def main_scanner_loop():
    log("=" * 75, "BOOT")
    log("🚀 BOT 2: AUTO-PILOT LIMIT SNIPER 50 KOIN (MARGIN $0.20 | LEV 40X) DIMULAI", "BOOT")
    log(f"Parameter: Margin ${CONFIG['margin_usd']} | Lev {CONFIG['leverage']}x | Min Skor {CONFIG['min_score']}", "BOOT")
    log("=" * 75, "BOOT")

    # Jalankan Patroli Auto-BEP di background
    bep_thread = threading.Thread(target=bep_patrol_worker, daemon=True)
    bep_thread.start()

    cycle = 1
    while True:
        cycle_start = time.time()
        now_dt = datetime.now(WIB)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S WIB")
        log(f"--- SIKLUS #{cycle} [{now_str}] ---", "CYCLE")

        btc_trend = get_btc_htf_trend()
        log(f"Macro Trend BTC 4H: {btc_trend}", "MACRO")

        try:
            # 1. Scan 50 Koin BingX
            signals = sinyal_engine.refresh_scan()
            high_score_signals = [s for s in signals if s.get("score", 0) >= CONFIG["min_score"]]
            log(f"Hasil scan: {len(signals)} sinyal ditemukan ({len(high_score_signals)} sinyal skor >= {CONFIG['min_score']})", "SCAN")

            # 2. Filter Macro HTF: Anti-Short saat BTC Pump & Anti-Long saat BTC Dump
            filtered_signals = []
            for s in high_score_signals:
                dir_s = s.get("direction", "LONG").upper()
                if btc_trend == "BULLISH" and dir_s == "SHORT":
                    log(f"  ❌ Skip {s.get('symbol')} SHORT (BTC 4H Bullish / Sedang Pump)", "FILTER")
                    continue
                if btc_trend == "BEARISH" and dir_s == "LONG":
                    log(f"  ❌ Skip {s.get('symbol')} LONG (BTC 4H Bearish / Sedang Dump)", "FILTER")
                    continue
                filtered_signals.append(s)

            # 3. Otomatis Pasang Limit Order via BingX Executor
            if filtered_signals:
                log(f"Mengeksekusi {len(filtered_signals)} sinyal valid skor tinggi ke bursa BingX...", "EXEC")
                batch_res = bingx_executor.batch_place_all_valid_limits(
                    signals=filtered_signals,
                    account_key=CONFIG["account_key"],
                    min_score=CONFIG["min_score"],
                    max_orders=CONFIG["max_concurrent_limits"],
                    margin_usd=CONFIG["margin_usd"],
                    leverage=CONFIG["leverage"]
                )

                succ_list = batch_res.get("success_list", [])
                if succ_list:
                    log(f"✅ BERHASIL PASANG {len(succ_list)} LIMIT ORDER BARU:", "SUCCESS")
                    for sc in succ_list:
                        log(f"   -> {sc}", "SUCCESS")
                        send_ntfy(
                            title=f"🎯 LIMIT ORDER TERPASANG: {sc}",
                            message=(
                                f"💎 Setup: {sc}\n"
                                f"💵 Margin: ${CONFIG['margin_usd']} | Lev: {CONFIG['leverage']}x\n"
                                f"🎯 TP: +35% ROE | ❌ SL: -36% ROE | 🛡️ Auto-BEP: +15% ROE\n"
                                f"🕐 {now_dt.strftime('%H:%M WIB')}"
                            ),
                            tags="target,zap"
                        )
                else:
                    log(f"ℹ️ {batch_res.get('msg')}", "INFO")

            # Update State Telemetri untuk Web Dashboard
            save_state({
                "bot_status": "RUNNING",
                "last_cycle": now_str,
                "cycle_number": cycle,
                "btc_htf_trend": btc_trend,
                "margin_usd": CONFIG["margin_usd"],
                "leverage": CONFIG["leverage"],
                "min_score": CONFIG["min_score"],
                "high_score_signals_count": len(high_score_signals),
                "filtered_signals_count": len(filtered_signals),
            })

        except Exception as e:
            log(f"Error pada siklus bot: {e}", "ERROR")

        cycle += 1
        elapsed = time.time() - cycle_start
        wait_time = max(10, CONFIG["scan_interval_sec"] - elapsed)
        log(f"Siklus selesai dlm {elapsed:.1f}s. Menunggu {wait_time:.0f}s untuk siklus berikutnya...", "WAIT")
        time.sleep(wait_time)

if __name__ == "__main__":
    main_scanner_loop()
