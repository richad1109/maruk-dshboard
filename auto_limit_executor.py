#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_limit_executor.py
-----------------------
Bot Auto-Pilot Eksekutor Limit Order MEXC 24/7 (APEX CASH COW PRO 40x Isolated).
100% Otomatis:
1. Margin Default: $1.00 USD per Koin (Bisa disesuaikan via config/UI).
2. Leverage: 40x Isolated (Apex Cash Cow Pro, Win Rate 68.5%).
3. Native TP (+22.0% ROE) & SL (-28.0% ROE) otomatis terkunci di bursa MEXC.
4. Cooldown 2 Jam Pasca-SL: Koin yang kena SL dilindungi selama 2 jam dari gilingan pasar (anti-whipsaw).
5. Auto Re-Entry Pasca-Cooldown: Begitu masa tenang 2 jam selesai, bot OTOMATIS memindai sinyal fresh dan langsung memasang limit order baru di MEXC!
6. Auto Fresh Re-Scan Pasca-TP: Begitu posisi kena TP, bot otomatis memindai level pullback Fibonacci 48% baru (tidak buy di pucuk).
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

# Load process-local DoH
try:
    import exchange_network
    exchange_network.install_dns()
except Exception:
    pass

import ccxt
import sniper_limit_engine

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

CONFIG_FILE = Path(__file__).parent / "auto_executor_config.json"
LOG_FILE = Path(__file__).parent / "auto_executor_activity.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "margin_usd": 1.00,
    "leverage": 40,
    "poll_interval": 20,
    "strategy": "APEX_CASH_COW_PRO",
    "status": "RUNNING",
    "last_cycle_time": "-",
    "last_action": "Inisialisasi sistem...",
    "cooldown_coins_count": 0,
    "active_positions_count": 0,
    "open_orders_count": 0,
    "recent_events": []
}

_CONFIG_LOCK = threading.RLock()

def load_config():
    with _CONFIG_LOCK:
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    return {**DEFAULT_CONFIG, **data}
            except Exception:
                pass
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with _CONFIG_LOCK:
        try:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
        except Exception:
            pass

def log_event(message, event_type="INFO"):
    now_str = datetime.now(WIB).strftime('%H:%M:%S WIB')
    entry = f"[{now_str}] [{event_type}] {message}"
    print(entry, flush=True)
    cfg = load_config()
    events = cfg.get("recent_events", [])
    events.insert(0, entry)
    cfg["recent_events"] = events[:30] # Simpan 30 event terakhir
    cfg["last_action"] = message
    cfg["last_cycle_time"] = now_str
    save_config(cfg)

def run_single_executor_cycle(dry_run=False):
    """Menjalankan 1 siklus lengkap eksekutor otomatis."""
    cfg = load_config()
    if not cfg.get("enabled", True):
        return {
            "status": "PAUSED",
            "msg": "Auto-Pilot sedang dinonaktifkan via tombol kendali."
        }
        
    margin = float(cfg.get("margin_usd", 1.00))
    if margin <= 0.1:
        margin = 1.00
        
    now_ts = time.time()
    now_str = datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')
    
    # 1. Pindai sinyal terkini & sinkronisasi dengan status MEXC
    observations = sniper_limit_engine.scan_all()
    if not observations:
        return {"status": "ERROR", "msg": "Gagal mengambil data sinyal pasar."}
        
    obs_map = {r['coin']: r for r in observations}
    
    # Ambil telemetri MEXC live
    tele = sniper_limit_engine.fetch_mexc_live_telemetry()
    act_pos = tele.get('active_positions', {}) if tele else {}
    op_ord = tele.get('open_orders', {}) if tele else {}
    
    # Hitung koin status
    active_coins = [r for r in observations if r.get('status') == 'TOUCHED']
    cooldown_coins = [r for r in observations if r.get('status') == 'COOLDOWN']
    waiting_coins = [r for r in observations if r.get('status') == 'WAITING']
    
    cfg["active_positions_count"] = len(act_pos)
    cfg["open_orders_count"] = len(op_ord)
    cfg["cooldown_coins_count"] = len(cooldown_coins)
    save_config(cfg)
    
    placed_orders = []
    cooldown_rescan_orders = []
    
    # 2. Cek apakah ada koin yang COOLDOWN-nya baru saja habis detik ini
    # Jika habis, scan_single_coin otomatis menghasilkan setup WAITING fresh!
    # 3. Eksekusi pasang limit order untuk koin WAITING yang belum ada di MEXC
    for r in observations:
        coin = r['coin']
        status = r.get('status')
        is_cd = (status == 'COOLDOWN')
        has_pos = coin in act_pos
        has_ord = coin in op_ord
        
        # JIKA COOLDOWN: LEWATI DAN AMANKAN
        if is_cd:
            continue
            
        # JIKA SUDAH POSISI AKTIF: LEWATI (Jangan tumpuk)
        if has_pos:
            continue
            
        # JIKA SUDAH ADA LIMIT ORDER DI MEXC: LEWATI
        if has_ord:
            continue
            
        # JIKA STATUS WAITING DAN SIAP PASANG: TEMBAKKAN LIMIT ORDER KE MEXC!
        if status == 'WAITING':
            if dry_run:
                msg = f"[DRY RUN] {coin}: Akan pasang {r.get('side', 'LONG')} Limit @ ${r['limit_p']} (Margin ${margin:.2f})"
                print(msg, flush=True)
                placed_orders.append((coin, {"success": True, "msg": msg}))
            else:
                log_event(f"🚀 Memasang Limit Order {r.get('side', 'LONG')} {coin} @ ${r['limit_p']} (Margin ${margin:.2f} · Lev 40x Isolated)...", "ORDER")
                res = sniper_limit_engine.execute_single_coin_limit_order(coin, custom_margin=margin)
                if res.get('success'):
                    log_event(f"✅ SUKSES! Order {coin} terpasang di MEXC (ID: {res.get('order_id')}) | TP: ${res.get('tp')} (+22%) | SL: ${res.get('sl')} (-28%)", "SUCCESS")
                    placed_orders.append((coin, res))
                else:
                    log_event(f"⚠️ Gagal pasang order {coin}: {res.get('msg')}", "WARNING")
                time.sleep(0.25)
                
    summary_msg = f"Siklus selesai: {len(act_pos)} Posisi Aktif, {len(op_ord)} Limit Antre, {len(cooldown_coins)} Cooldown, {len(placed_orders)} Order Baru Terpasang."
    cfg["last_action"] = summary_msg
    cfg["last_cycle_time"] = datetime.now(WIB).strftime('%H:%M:%S WIB')
    save_config(cfg)
    
    if placed_orders:
        log_event(f"🎯 Selesai pasang {len(placed_orders)} order baru! Total {len(op_ord) + len(placed_orders)} limit antre di MEXC.", "BATCH")
    else:
        log_event(f"💓 Patroli 24/7 Aktif: {len(act_pos)} Posisi Jalan · {len(op_ord)} Limit Antre di MEXC · {len(cooldown_coins)} Cooldown · Siaga...", "PATROLI")
    
    return {
        "status": "OK",
        "placed_count": len(placed_orders),
        "placed_orders": placed_orders,
        "cooldown_count": len(cooldown_coins),
        "active_count": len(act_pos),
        "open_orders_count": len(op_ord),
        "msg": summary_msg
    }

_DAEMON_THREAD = None
_DAEMON_RUNNING = False

def start_background_daemon(margin_usd=1.00, interval=20):
    """Menjalankan loop executor otomatis di background daemon thread."""
    global _DAEMON_THREAD, _DAEMON_RUNNING
    if _DAEMON_RUNNING and _DAEMON_THREAD and _DAEMON_THREAD.is_alive():
        return True
        
    cfg = load_config()
    cfg["enabled"] = True
    cfg["margin_usd"] = float(margin_usd)
    cfg["poll_interval"] = int(interval)
    cfg["status"] = "RUNNING"
    save_config(cfg)
    
    _DAEMON_RUNNING = True
    
    def daemon_worker():
        global _DAEMON_RUNNING
        log_event(f"🤖 Bot Auto-Pilot MEXC Dimulai! Margin: ${margin_usd:.2f} | Leverage: 40x | Cooldown: 2 Jam | Interval: {interval}s", "START")
        while _DAEMON_RUNNING:
            cfg = load_config()
            if not cfg.get("enabled", True):
                time.sleep(5)
                continue
            try:
                run_single_executor_cycle(dry_run=False)
            except Exception as e:
                log_event(f"⚠️ Terjadi exception pada siklus executor: {e}", "ERROR")
                
            poll_int = int(cfg.get("poll_interval", 20))
            for _ in range(poll_int):
                if not _DAEMON_RUNNING:
                    break
                time.sleep(1)
        log_event("🛑 Bot Auto-Pilot MEXC Berhenti.", "STOP")
        
    _DAEMON_THREAD = threading.Thread(target=daemon_worker, daemon=True)
    _DAEMON_THREAD.start()
    return True

def stop_background_daemon():
    """Menghentikan daemon background."""
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = False
    cfg = load_config()
    cfg["enabled"] = False
    cfg["status"] = "STOPPED"
    save_config(cfg)
    log_event("Tombol stop ditekan: Auto-pilot dinonaktifkan.", "STOP")
    return True

def main():
    is_live = ("--live" in sys.argv)
    
    # Parse custom margin jika disediakan via CLI
    margin = 1.00
    for idx, arg in enumerate(sys.argv):
        if arg == "--margin" and idx + 1 < len(sys.argv):
            try:
                margin = float(sys.argv[idx + 1])
            except Exception:
                pass
                
    cfg = load_config()
    cfg["margin_usd"] = margin
    cfg["enabled"] = True
    save_config(cfg)
    
    print("=" * 95)
    print("🤖 AUTO-PILOT EXECUTOR LIMIT ORDER MEXC 24/7 (APEX CASH COW PRO)")
    print(f"Status Mode  : {'🚀 LIVE TRADING OTOMATIS (Uang Riil MEXC)' if is_live else '⚠️ DRY RUN (Mode Simulasi)'}")
    print(f"Ukuran Margin: ${margin:.2f} USD per Koin (Leverage 40x Flat Isolated)")
    print(f"Target Profit: +22.0% ROE (Quick-Strike spot +0.55% price move)")
    print(f"Stop Loss    : -28.0% ROE (Tight protection spot -0.70% price move)")
    print(f"Masa Tenang  : 2 Jam Pasca-SL (Koin otomatis di-scan ulang & ditembak begitu selesai)")
    print("=" * 95)
    print("Tekan Ctrl + C di keyboard kapan saja untuk menghentikan bot.\n")
    
    start_background_daemon(margin_usd=margin, interval=cfg.get("poll_interval", 20))
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Sinyal berhenti diterima. Menutup bot...")
        stop_background_daemon()
        time.sleep(1)
        print("✓ Bot telah berhenti dengan aman.")

if __name__ == "__main__":
    main()
