#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_limit_bot.py
-----------------
Bot Pemindai & Notifikasi Limit Order Sniper 20 Koin (Live HUD).
Berjalan otomatis di Termux Android Tab 2 (100% Terpisah & Independen dari Astra).
Menampilkan secara transparan:
1. BANNER TOTAL FLOATING PROFIT PORTOFOLIO 20 KOIN DI BAGIAN ATAS
2. Status: ✅ SETUP VALID vs 🔍 MEMINDAI (BELUM VALID) vs ⚡ TERISI JEMPUTAN
3. Status Sentuhan: ⚡ SUDAH KESENTUH (TERISI) vs ⏳ BELUM KESENTUH (MENUNGGU)
4. Floating Profit / Jarak Jemputan di atas setiap kartu/baris
5. Pembaruan otomatis setup baru setelah posisi kena TP atau SL
6. Auto-Refresh setiap 10 Detik
"""

import os
import sys
import io
import time
from concurrent.futures import ThreadPoolExecutor
from config import COINS_CONFIG, MARGIN_PER_TRADE, REFRESH_SECONDS
from engine import analyze_coin

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def run_once():
    now_str = time.strftime('%Y-%m-%d %H:%M:%S WIB')
    
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(analyze_coin, COINS_CONFIG))
        
    results = [r for r in results if r is not None]
    
    # Hitung Akumulasi Total Floating Profit Portofolio 20 Koin
    total_floating_usd = sum(r['float_usd'] for r in results if r['is_touched'])
    total_floating_roe = sum(r['float_roe'] for r in results if r['is_touched'])
    active_floating_count = sum(1 for r in results if "SEDANG MANTUL" in r['valid_status'])
    tp_count = sum(1 for r in results if "TP" in r['touch_status'])
    sl_count = sum(1 for r in results if "SL" in r['touch_status'])
    valid_count = sum(1 for r in results if "SETUP VALID" in r['valid_status'] or "PINDAI" in r['valid_status'])
    memindai_count = sum(1 for r in results if "MEMINDAI" in r['valid_status'])
    
    sign_tot = "+" if total_floating_usd >= 0 else ""
    tot_idr = total_floating_usd * 16300
    
    print("=" * 125)
    print(f"🎯 BOT LIMIT ORDER SNIPER 20 KOIN - LIVE HUD TERMUX - {now_str}")
    print(f"Status Kemitraan: 100% TERPISAH dari Astra (D:\\bot_final aman & berjalan di Tab 1)")
    print("=" * 125)
    print(f"💰 TOTAL FLOATING PROFIT PORTOFOLIO : {sign_tot}${total_floating_usd:,.2f} USD ({sign_tot}{total_floating_roe:,.1f}% ROE) ~ {sign_tot}Rp {tot_idr:,.0f}")
    print(f"📊 Ringkasan Status                   : ⚡ {active_floating_count} Koin Mantul Floating | 🎯 {tp_count} Sukses TP | 🛑 {sl_count} Kena SL | ⏳ {valid_count} Siaga Limit Baru")
    print("=" * 125)
    print(f"{'KOIN':<6} | {'POTENSI':<19} | {'STATUS VALID':<19} | {'SENTUH LIMIT?':<22} | {'FLOATING / JARAK':<28} | {'WR':>5}")
    print("-" * 125)
    
    for r in results:
        pot_badge = "🟢 LONG " if "LONG" in r['potensi'] else "🔴 SHORT"
        print(f"{r['coin']:<6} | {pot_badge:<19} | {r['valid_status']:<19} | {r['touch_status']:<22} | {r['float_str']:<28} | {r['wr']:>4.1f}%")
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
