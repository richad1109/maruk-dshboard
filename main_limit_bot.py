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
3. Posisi TIDAK AKAN PERNAH kembali ke status 'menunggu jemputan' selama masih aktif.
4. Begitu menyentuh Target TP (+35% ROE) atau Stop Loss (-36% ROE), otomatis menerbitkan setup Limit Order baru.
5. Auto-Refresh berjalan otomatis setiap 10 detik.
"""

import os
import sys
import io
import time
import sniper_limit_engine

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
        
    # Akumulasi Total Floating & Realized Profit Portofolio 20 Koin
    total_floating_usd = sum(r['float_usd'] for r in results if "SEDANG MANTUL" in r['valid_label'])
    total_floating_roe = sum(r['float_roe'] for r in results if "SEDANG MANTUL" in r['valid_label'])
    active_floating_count = sum(1 for r in results if "SEDANG MANTUL" in r['valid_label'])
    tp_count = sum(1 for r in results if "TP" in r['touch_status'])
    sl_count = sum(1 for r in results if "SL" in r['touch_status'])
    valid_count = sum(1 for r in results if "SETUP VALID" in r['valid_label'] or "PINDAI" in r['valid_label'])
    memindai_count = sum(1 for r in results if "MEMINDAI" in r['valid_label'])
    
    # Realized PnL & Win Rate
    realized_usd = (tp_count * 0.70) - (sl_count * 0.72)
    realized_roe = (tp_count * 35.0) - (sl_count * 36.0)
    realized_idr = realized_usd * 16300
    total_closed = tp_count + sl_count
    realized_wr = (tp_count / total_closed * 100) if total_closed > 0 else 0.0
    avg_portfolio_wr = sum(r['wr'] for r in results) / len(results) if results else 67.0
    
    sign_tot = "+" if total_floating_usd >= 0 else ""
    tot_idr = total_floating_usd * 16300
    sign_real = "+" if realized_usd >= 0 else ""
    
    print("=" * 125)
    print(f"🎯 BOT LIMIT ORDER SNIPER 20 KOIN - LIVE HUD TERMUX - {now_str}")
    print(f"Status Kemitraan: 100% TERPISAH dari Astra (Astra Tab 1 Aman & Independen)")
    print("=" * 125)
    print(f"💰 FLOATING PROFIT (AKTIF) : {sign_tot}${total_floating_usd:,.2f} USD ({sign_tot}{total_floating_roe:,.1f}% ROE) ~ {sign_tot}Rp {tot_idr:,.0f} [{active_floating_count} Koin Mantul]")
    print(f"💎 REALIZED PnL (SELESAI)  : {sign_real}${realized_usd:,.2f} USD ({sign_real}{realized_roe:,.1f}% ROE) ~ {sign_real}Rp {realized_idr:,.0f} [{total_closed} Setup Selesai: {tp_count} TP / {sl_count} SL]")
    print(f"🏆 WIN RATE (WR)           : {avg_portfolio_wr:.1f}% Rata-Rata Historis | WR Realisasi Sesi: {realized_wr:.1f}%")
    print(f"📊 Ringkasan Siaga Pasang  : ⏳ {valid_count} Koin Siaga Limit Baru | 🔍 {memindai_count} Koin Memindai")
    print("=" * 125)
    print(f"{'KOIN':<6} | {'POTENSI':<19} | {'STATUS VALID':<19} | {'SENTUH LIMIT?':<22} | {'FLOATING / JARAK':<28} | {'WR':>5}")
    print("-" * 125)
    
    for r in results:
        pot_badge = "🟢 LONG " if "LONG" in r['potensi'] else "🔴 SHORT"
        print(f"{r['coin']:<6} | {pot_badge:<19} | {r['valid_label']:<19} | {r['touch_status']:<22} | {r['float_str']:<28} | {r['wr']:>4.1f}%")
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
