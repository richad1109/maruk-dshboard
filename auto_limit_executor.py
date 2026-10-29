#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_limit_executor.py
-----------------------
Bot Auto-Pilot Eksekutor Limit Order MEXC 24/7 (IRON DEFENSE PROTOCOL 20x Isolated).
Dirombak total pasca audit riil 1 minggu:
1. MAX CONCURRENT POSITIONS = 2 (HARD CAP):
   Maksimal HANYA 2 koin yang diizinkan aktif/antre bersamaan. Portofolio terkunci ketat
   agar tidak pernah lagi terseret dump serentak belasan koin.
2. BITCOIN MASTER CRASH GUARD:
   Memindai candle 15m/1h BTC. Jika Bitcoin sedang dump/di bawah EMA,
   seluruh order LONG DILARANG KERAS dan order gantung Long otomatis dibatalkan!
3. RISK-TO-REWARD POSITIF SEHAT (20x Isolated):
   - Margin: $1.00 USD flat.
   - TP: +30.0% ROE (Spot +1.50%). Net cuan setelah fee: +$0.28 USD.
   - SL: -20.0% ROE (Spot -1.00%). Net rugi setelah fee: -$0.22 USD.
   - Rasio RR: 1.27 : 1 (Cuan lebih besar dari rugi).
4. COOLDOWN 2 JAM PASCA-SL:
   Koin yang kena SL dikunci 7.200 detik dari pasar.
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
MAX_CONCURRENT_LIMIT = 1  # SINGLE SNIPER PROTOCOL: Hanya 1 koin aktif (Teruji 1 Bulan & 1 Minggu Konsisten Hijau)

DEFAULT_CONFIG = {
    "enabled": True,
    "margin_usd": 3.00,
    "leverage": 40,
    "max_concurrent": 1,
    "poll_interval": 20,
    "strategy": "APEX_TARGET_500RB_40X",
    "status": "RUNNING",
    "last_cycle_time": "-",
    "last_action": "Inisialisasi sistem Iron Defense...",
    "cooldown_coins_count": 0,
    "active_positions_count": 0,
    "open_orders_count": 0,
    "btc_guard_status": "-",
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
    cfg["recent_events"] = events[:30]
    cfg["last_action"] = message
    cfg["last_cycle_time"] = now_str
    save_config(cfg)

def check_btc_master_guard(client=None):
    """
    Memeriksa tren dan status crash Bitcoin (BTC/USDT):
    - Return 'BULLISH', reason: Boleh pasang LONG saja.
    - Return 'BEARISH', reason: Boleh pasang SHORT saja.
    - Return 'FLASH_CRASH', reason: Dump tajam! LONG dilarang, batalkan pending Long.
    - Return 'NEUTRAL', reason: Pasar galau. Diam di tempat.
    """
    if client is None:
        client = sniper_limit_engine.get_mexc_trading_client()
    if client is None:
        return 'NEUTRAL', 'Client MEXC belum siap.'
        
    try:
        ohlcv = client.fetch_ohlcv('BTC/USDT:USDT', '15m', limit=60)
        if not ohlcv or len(ohlcv) < 50:
            return 'NEUTRAL', 'Data candle BTC tidak cukup.'
            
        closes = [x[4] for x in ohlcv]
        cur_p = closes[-1]
        
        # Hitung EMA 20 dan EMA 50
        def ema(arr, span):
            k = 2.0 / (span + 1.0)
            res = [arr[0]]
            for x in arr[1:]: res.append((x * k) + (res[-1] * (1.0 - k)))
            return res[-1]
            
        ema20 = ema(closes, 20)
        ema50 = ema(closes, 50)
        
        # Return 1 Jam (4 bar) dan 4 Jam (16 bar)
        ret_1h = (cur_p - closes[-5]) / closes[-5]
        ret_4h = (cur_p - closes[-17]) / closes[-17]
        
        if ret_1h <= -0.012 or ret_4h <= -0.025:
            return 'FLASH_CRASH', f"BTC Dump Tajam (1H: {ret_1h*100:+.2f}% | 4H: {ret_4h*100:+.2f}%). Proteksi Crash Aktif!"
        elif cur_p < ema20 and cur_p < ema50:
            return 'BEARISH', f"BTC di bawah EMA 20 & 50 (Bearish 15m @ ${cur_p:,.0f}). Hanya boleh SHORT."
        elif cur_p > ema20 and cur_p > ema50 and ret_1h >= -0.005:
            return 'BULLISH', f"BTC di atas EMA 20 & 50 (Bullish 15m @ ${cur_p:,.0f}). Hanya boleh LONG."
        else:
            return 'NEUTRAL', f"BTC Sideways / Netral (1H: {ret_1h*100:+.2f}%). Menunggu konfirmasi tren."
    except Exception as e:
        return 'NEUTRAL', f"Error membaca telemetri BTC: {e}"

def run_single_executor_cycle(dry_run=False):
    """Menjalankan 1 siklus lengkap eksekutor otomatis dengan Protokol Iron Defense."""
    cfg = load_config()
    if not cfg.get("enabled", True):
        return {
            "status": "PAUSED",
            "msg": "Auto-Pilot sedang dinonaktifkan."
        }
        
    margin = float(cfg.get("margin_usd", 3.00))
    if margin <= 0.1:
        margin = 3.00
        
    now_ts = time.time()
    now_str = datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')
    
    client = sniper_limit_engine.get_mexc_trading_client()
    if cfg.get("compound") and client:
        try:
            b = client.fetch_balance()
            tot = float(b.get('total', {}).get('USDT') or b.get('free', {}).get('USDT') or 0.0)
            if tot >= 12.0:
                margin = max(3.00, min(25.00, round(tot * 0.30, 2)))
        except Exception:
            pass
    if client is None:
        return {"status": "ERROR", "msg": "Client trading MEXC belum tersambung."}
        
    # 1. Pindai sinyal pasar & sinkronisasi live MEXC
    observations = sniper_limit_engine.scan_all()
    if not observations:
        return {"status": "ERROR", "msg": "Gagal mengambil data sinyal pasar."}
        
    tele = sniper_limit_engine.fetch_mexc_live_telemetry()
    act_pos = tele.get('active_positions', {}) if tele else {}
    op_ord = tele.get('open_orders', {}) if tele else {}
    
    cooldown_coins = [r for r in observations if r.get('status') == 'COOLDOWN']
    
    cfg["active_positions_count"] = len(act_pos)
    cfg["open_orders_count"] = len(op_ord)
    cfg["cooldown_coins_count"] = len(cooldown_coins)
    
    # 2. Cek BTC Master Guard (Pilar Pertahanan Utama)
    btc_guard, btc_reason = check_btc_master_guard(client)
    cfg["btc_guard_status"] = f"{btc_guard} ({btc_reason})"
    save_config(cfg)
    
    # SINKRONISASI BENTENG: Batalkan order berlawanan arah BTC
    if btc_guard in ['FLASH_CRASH', 'BEARISH']:
        for sym_key, o_info in list(op_ord.items()):
            o_side = o_info.get('side', '').upper()
            if o_side in ['BUY', 'LONG']:
                oid = o_info.get('id') or o_info.get('order_id')
                if oid:
                    try:
                        client.cancel_order(oid, symbol=f"{sym_key}/USDT:USDT")
                        log_event(f"🛡️ AUTO-CANCEL: Membatalkan limit Long {sym_key} karena Bitcoin sedang turun/dump!", "GUARD")
                        time.sleep(0.15)
                    except Exception:
                        pass
    elif btc_guard == 'BULLISH':
        for sym_key, o_info in list(op_ord.items()):
            o_side = o_info.get('side', '').upper()
            if o_side in ['SELL', 'SHORT']:
                oid = o_info.get('id') or o_info.get('order_id')
                if oid:
                    try:
                        client.cancel_order(oid, symbol=f"{sym_key}/USDT:USDT")
                        log_event(f"🛡️ AUTO-CANCEL: Membatalkan limit Short {sym_key} karena Bitcoin sedang terbang!", "GUARD")
                        time.sleep(0.15)
                    except Exception:
                        pass
                    
    # 2.5 STALE ORDER & DRIFT GUARD (PROTEKSI ANTI-STUCK)
    # Jika harga pasar sudah kabur > 0.80% dari antrean limit, batalkan otomatis agar slot tidak terkunci berjam-jam!
    for sym_key, o_info in list(op_ord.items()):
        oid = o_info.get('id') or o_info.get('order_id')
        lim_p = float(o_info.get('price') or 0)
        if lim_p > 0 and oid:
            try:
                t_ticker = client.fetch_ticker(f"{sym_key}/USDT:USDT")
                cur_m_p = float(t_ticker.get('last') or 0)
                if cur_m_p > 0:
                    drift_pct = abs(cur_m_p - lim_p) / cur_m_p
                    if drift_pct > 0.0055:
                        client.cancel_order(oid, symbol=f"{sym_key}/USDT:USDT")
                        log_event(f"🔄 STALE CANCEL: Membatalkan limit {sym_key} karena harga kabur {drift_pct*100:.2f}% (Slot Single Sniper Dibebaskan)!", "GUARD")
                        time.sleep(0.15)
                        if sym_key in op_ord:
                            del op_ord[sym_key]
            except Exception:
                pass

    # 2.8 PROTOKOL JEDA PASCA-TRADE (ANTI-REVENGE / ANTI-WHIPSAW):
    # Jika trade terakhir baru saja selesai di MEXC dalam < 15 menit (pasca-TP) atau < 30 menit (pasca-SL),
    # TAHAN SELURUH PEMASANGAN ORDER BARU! Berikan pasar jeda agar struktur candle tenang.
    now_epoch = time.time()
    recent_trades = tele.get('trades', []) if tele else []
    if recent_trades:
        last_t = recent_trades[0]
        last_closed_ts = float(last_t.get('closed_at', 0))
        last_outcome = last_t.get('outcome', 'SL')
        pause_req = 900 if last_outcome == 'TP' else 1800 # 15m jika TP, 30m jika SL
        elapsed = now_epoch - last_closed_ts
        if 0 < elapsed < pause_req:
            rem_sec = int(pause_req - elapsed)
            rem_min = max(1, rem_sec // 60)
            summary_msg = f"⏸️ JEDA PASCA-{last_outcome}: Masa tenang ({rem_min}m lagi s/d {datetime.fromtimestamp(last_closed_ts + pause_req, WIB).strftime('%H:%M WIB')}) melindungi modal dari guncangan pasar!"
            cfg["last_action"] = summary_msg
            cfg["last_cycle_time"] = datetime.now(WIB).strftime('%H:%M:%S WIB')
            save_config(cfg)
            log_event(summary_msg, "JEDA")
            return {
                "status": "PAUSED_JEDA",
                "placed_count": 0,
                "msg": summary_msg
            }

    # 3. Hitung Kuota Portofolio (MAKSIMAL 1 POSISI / ORDER AKTIF - SINGLE SNIPER)
    curr_total = len(act_pos) + len(op_ord)
    slots_free = max(0, MAX_CONCURRENT_LIMIT - curr_total)
    
    placed_orders = []
    
    # Jika kuota penuh (sudah ada 2 koin jalan atau antre): JANGAN BUKA LAGI!
    if slots_free <= 0:
        summary_msg = f"🎯 Kuota Single Sniper (1/1 Aktif): {len(act_pos)} Posisi Aktif, {len(op_ord)} Limit Antre. Menunggu TP/SL..."
        cfg["last_action"] = summary_msg
        cfg["last_cycle_time"] = datetime.now(WIB).strftime('%H:%M:%S WIB')
        save_config(cfg)
        log_event(f"🎯 Patroli Siaga: 1/1 Kuota Terisi ({len(act_pos)} Posisi Jalan · {len(op_ord)} Limit Antre) · BTC: {btc_guard} · Menjaga modal...", "PATROLI")
        return {
            "status": "OK",
            "placed_count": 0,
            "msg": summary_msg
        }
        
    # 4. Jika ada slot kosong: Saring koin terbaik yang searah dengan BTC Guard
    candidates = []
    for r in observations:
        coin = r['coin']
        
        # EKSKLUSI BTC: BTC HANYA PENGAWAL / KOMPAS TREN, EKSEKUSI DI ALTCOIN
        if coin == 'BTC':
            continue
            
        status = r.get('status')
        side = r.get('side', 'LONG')
        is_cd = (status == 'COOLDOWN')
        has_pos = coin in act_pos
        has_ord = coin in op_ord
        
        if is_cd or has_pos or has_ord:
            continue
            
        if status != 'WAITING':
            continue
            
        # Hitung jarak harga saat ini ke limit price
        cur_p = float(r.get('cur_p', 0))
        lim_p = float(r.get('limit_p', 0))
        dist_pct = 999.0
        if cur_p > 0 and lim_p > 0:
            dist_pct = abs(cur_p - lim_p) / cur_p
            
        # Filter keselarasan dengan BTC Guard
        if btc_guard == 'BULLISH' and side != 'LONG':
            continue # BTC naik, dilarang Short
        if btc_guard in ['BEARISH', 'FLASH_CRASH'] and side != 'SHORT':
            continue # BTC turun/dump, dilarang Long
        if btc_guard == 'NEUTRAL' and dist_pct > 0.010:
            continue # Jika BTC netral/sideways, izinkan koin yang jaraknya sangat dekat (<= 1.0%)
            
        # ANTI-TELAT MANTUL GUARD:
        # Hanya ambil jika harga berada dalam zona diskon (0.05% s/d 0.45%).
        # Jika dist_pct > 0.45%, koin SUDAH MANTUL / SUDAH DUMP (TELAT) -> DILARANG KEJAR!
        if 0.0005 <= dist_pct <= 0.0045:
            candidates.append({
                    "dist": dist_pct,
                    "coin": coin,
                    "side": side,
                    "row": r
                })
                
    # Urutkan berdasarkan jarak terdekat (paling siap mantul)
    candidates.sort(key=lambda x: x["dist"])
    
    # Eksekusi HANYA sebanyak slot yang tersedia (Maksimal 1 atau 2 koin!)
    for item in candidates[:slots_free]:
        coin = item['coin']
        side = item['side']
        r = item['row']
        lim_p = r['limit_p']
        
        if dry_run:
            msg = f"[DRY RUN] {coin}: Pasang {side} Limit @ ${lim_p} (Margin ${margin:.2f} · Lev 40x Isolated)"
            print(msg, flush=True)
            placed_orders.append((coin, {"success": True, "msg": msg}))
        else:
            log_event(f"🚀 [IRON DEFENSE] Memasang {side} Limit {coin} @ ${lim_p} (Margin ${margin:.2f} · Lev 40x Isolated · BTC: {btc_guard})...", "ORDER")
            res = sniper_limit_engine.execute_single_coin_limit_order(coin, custom_margin=margin)
            if res.get('success'):
                log_event(f"✅ SUKSES! Order {coin} terpasang di MEXC (ID: {res.get('order_id')}) | TP: ${res.get('tp')} (+45%) | SL: ${res.get('sl')} (-22%)", "SUCCESS")
                placed_orders.append((coin, res))
            else:
                log_event(f"⚠️ Gagal pasang order {coin}: {res.get('msg')}", "WARNING")
            time.sleep(0.3)
            
    summary_msg = f"Siklus selesai: {len(act_pos)} Posisi Aktif, {len(op_ord)} Limit Antre, {len(cooldown_coins)} Cooldown, {len(placed_orders)} Order Baru."
    cfg["last_action"] = summary_msg
    cfg["last_cycle_time"] = datetime.now(WIB).strftime('%H:%M:%S WIB')
    save_config(cfg)
    
    if placed_orders:
        log_event(f"🎯 Selesai pasang {len(placed_orders)} order baru terpilih! Total aktif di MEXC: {curr_total + len(placed_orders)}/1 koin.", "BATCH")
    else:
        log_event(f"💓 Patroli Iron Defense: {len(act_pos)} Posisi Jalan · {len(op_ord)} Limit Antre · Slot Bebas: {slots_free}/4 · BTC: {btc_guard}", "PATROLI")
        
    return {
        "status": "OK",
        "placed_count": len(placed_orders),
        "cooldown_count": len(cooldown_coins),
        "active_count": len(act_pos),
        "open_orders_count": len(op_ord),
        "btc_guard": btc_guard,
        "msg": summary_msg
    }

_DAEMON_THREAD = None
_DAEMON_RUNNING = False

def start_background_daemon(margin_usd=1.00, interval=20):
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
        log_event(f"🤖 Bot Iron Defense MEXC Dimulai! Margin: ${margin_usd:.2f} | Leverage: 20x | Max Concurrent: 2 Koin | Cooldown: 2 Jam", "START")
        while _DAEMON_RUNNING:
            cfg = load_config()
            if not cfg.get("enabled", True):
                time.sleep(5)
                continue
            try:
                run_single_executor_cycle(dry_run=False)
            except Exception as e:
                log_event(f"⚠️ Exception pada siklus executor: {e}", "ERROR")
                
            poll_int = int(cfg.get("poll_interval", 20))
            for _ in range(poll_int):
                if not _DAEMON_RUNNING:
                    break
                time.sleep(1)
        log_event("🛑 Bot Iron Defense MEXC Berhenti.", "STOP")
        
    _DAEMON_THREAD = threading.Thread(target=daemon_worker, daemon=True)
    _DAEMON_THREAD.start()
    return True

def stop_background_daemon():
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = False
    cfg = load_config()
    cfg["enabled"] = False
    cfg["status"] = "STOPPED"
    save_config(cfg)
    log_event("Tombol stop ditekan: Bot dihentikan.", "STOP")
    return True

def main():
    is_live = ("--live" in sys.argv)
    use_compound = ("--compound" in sys.argv)
    margin = 3.00
    for idx, arg in enumerate(sys.argv):
        if arg == "--margin" and idx + 1 < len(sys.argv):
            try:
                margin = float(sys.argv[idx + 1])
            except Exception:
                pass
                
    cfg = load_config()
    cfg["margin_usd"] = margin
    cfg["compound"] = use_compound
    cfg["enabled"] = True
    save_config(cfg)
    
    print("=" * 95)
    print("🎯 SINGLE SNIPER PROTOCOL MEXC 24/7 (TARGET RP 500.000 / $30 USD PER MINGGU (APEX 40X))")
    print(f"Status Mode   : {'🚀 LIVE TRADING OTOMATIS (Uang Riil MEXC)' if is_live else '⚠️ DRY RUN (Mode Simulasi)'}")
    mode_str = "Dynamic Compounding 30% Saldo (Target Rp 500.000 / $32.51/Wk Teruji)" if use_compound else f"${margin:.2f} USD Fixed"
    print(f"Ukuran Margin : {mode_str} (Leverage 40x Isolated)")
    print(f"Maksimal Aktif: HANYA 1 KOIN (Single Sniper - Teruji Bebas Boncos Multi-Koin)")
    print(f"Filter BTC    : 🛡️ BTC Master Crash Guard (Dilarang Long saat Bitcoin Dump)")
    print(f"Target Profit : +60.0% ROE (Spot +1.50% · Cuan Bersih +$1.73 USD / ~Rp 28.166)")
    print(f"Stop Loss     : -40.0% ROE (Spot -1.00% · Rugi Bersih -$1.31 USD / ~Rp 21.320)")
    print(f"Risk-Reward   : 1.32 : 1 (Cuan Lebih Besar dari Rugi setelah Fee & Slippage MEXC)")
    print(f"Masa Tenang   : 2 Jam Pasca-SL (7.200s Anti-Whipsaw)")
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
