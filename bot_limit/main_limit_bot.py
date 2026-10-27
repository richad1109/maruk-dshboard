#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_limit_bot.py
-----------------
Bot Pemindai & Live HUD Limit Order Sniper 20 Koin untuk Termux Android (Tab 2).
100% Independen dan Terpisah dari Bot Astra (Tab 1).
Fitur Utama:
1. Banner Total Floating Profit Portofolio 20 Koin ($ USD, % ROE, Rp IDR) di bagian paling atas.
2. Posisi yang sudah terjemput (mantul) DIKUNCI statusnya dan floating profit-nya bergerak real-time.
3. Begitu menyentuh TP (+35%) atau SL (-20%), hasil trade LANGSUNG dicatat ke Realized PnL dan bot otomatis menerbitkan setup limit baru yang fresh.
4. Auto-Refresh berjalan otomatis setiap 10 detik.
"""

import os
import sys
import io
import time
from pathlib import Path

try:
    import engine as sniper_limit_engine
except ImportError:
    try:
        import sniper_limit_engine
    except ImportError:
        sys.path.insert(0, str(Path(__file__).parent))
        import engine as sniper_limit_engine

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

REFRESH_SECONDS = 10

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def run_once():
    now_str = time.strftime('%Y-%m-%d %H:%M:%S WIB')
    
    results = sniper_limit_engine.scan_all()
    if not results:
        print(f"[{now_str}] ⚠️ Gagal mengambil data bursa, mencoba lagi...")
        return
        
    summary = sniper_limit_engine.get_portfolio_summary(results)
    
    total_floating_usd = summary['floating_usd']
    total_floating_roe = summary['floating_roe']
    tot_idr = summary['floating_idr']
    active_floating_count = summary['active_count']
    
    realized_usd = summary['realized_usd']
    realized_roe = summary['realized_roe']
    realized_idr = summary['realized_idr']
    tp_count = summary['tp_count']
    sl_count = summary['sl_count']
    total_closed = summary['total_closed']
    realized_wr = summary['realized_wr']
    avg_portfolio_wr = summary['avg_wr']
    waiting_count = summary['waiting_count']
    
    sign_tot = "+" if total_floating_usd >= 0 else ""
    sign_real = "+" if realized_usd >= 0 else ""
    
    print("=" * 125)
    print(f"🎯 BOT LIMIT ORDER SNIPER 20 KOIN - LIVE HUD TERMUX - {now_str}")
    print(f"Status Kemitraan: 100% TERPISAH dari Astra (Astra Tab 1 Aman & Independen)")
    print("=" * 125)
    print(f"💰 FLOATING PROFIT (AKTIF) : {sign_tot}${total_floating_usd:,.2f} USD ({sign_tot}{total_floating_roe:,.1f}% ROE) ~ {sign_tot}Rp {tot_idr:,.0f} [{active_floating_count} Koin Mantul Aktif]")
    print(f"💎 REALIZED PnL (SELESAI)  : {sign_real}${realized_usd:,.2f} USD ({sign_real}{realized_roe:,.1f}% ROE) ~ {sign_real}Rp {realized_idr:,.0f} [{total_closed} Trade Selesai: {tp_count} TP / {sl_count} SL]")
    print(f"🏆 WIN RATE (WR)           : {avg_portfolio_wr:.1f}% Rata-Rata Historis | WR Realisasi Sesi: {realized_wr:.1f}%")
    print(f"📊 Ringkasan Siaga Pasang  : ⏳ {waiting_count} Setup Baru Siap Pasang")
    print("=" * 125)
    print(f"{'KOIN':<6} | {'POTENSI':<19} | {'STATUS VALID':<22} | {'SENTUH LIMIT?':<22} | {'FLOATING / JARAK':<28} | {'WR':>5}")
    print("-" * 125)
    
    for r in results:
        pot_badge = "🟢 LONG " if "LONG" in r['potensi'] else "🔴 SHORT"
        last_out = r.get('last_outcome')
        if r.get('status') == 'TOUCHED':
            stat_label = "⚡ POSISI AKTIF"
            touch_lbl = "⚡ SEDANG MANTUL"
        elif last_out and isinstance(last_out, dict):
            out_str = "TP (+35%)" if last_out.get('outcome') == 'TP' else "SL (-20%)"
            stat_label = f"🔄 FRESH ({out_str})"
            touch_lbl = "⏳ MENUNGGU JEMPUTAN"
        else:
            stat_label = r['valid_label']
            touch_lbl = "⏳ MENUNGGU JEMPUTAN"

        print(f"{r['coin']:<6} | {pot_badge:<19} | {stat_label:<22} | {touch_lbl:<22} | {r['float_str']:<28} | {r['wr']:>4.1f}%")
        print(f"       └─ Mark: ${r['cur_p']:<10.4f} | Entry Limit: ${r['limit_p']:<10.4f} | SL: ${r['sl_p']:<10.4f} | TP: ${r['tp_p']:<10.4f} | Lev: {r['lev']}x")
        print("-" * 125)
        
    print("=" * 125)
    print(f"🔄 Auto-Refresh setiap {REFRESH_SECONDS} detik... (Tekan Ctrl+C untuk berhenti)")

def main():
    while True:
        try:
            clear_screen()
            run_once()
            time.sleep(REFRESH_SECONDS)
        except KeyboardInterrupt:
            print("\n\n👋 Bot Limit Order dihentikan. Sampai jumpa!")
            break
        except Exception as e:
            print(f"\n⚠️ Terjadi kesalahan: {e}. Mengulang dalam 5 detik...")
            time.sleep(5)

if __name__ == '__main__':
    main()
