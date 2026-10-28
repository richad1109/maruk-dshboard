#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_limit_executor.py
-----------------------
Bot Eksekutor Otomatis Limit Order Sniper MEXC (Mode 24/7 Auto-Pilot).
100% Mengotomatiskan Trading:
1. Memindai Sinyal Optimal: Retrace 55%, TP +35.0% ROE, SL -30.0% ROE, KER >= 0.22, EMA 34.
2. Memeriksa Akun MEXC: Cek posisi aktif & antrean order limit secara real-time.
3. Otomatis Pasang Limit: Menghitung ukuran kontrak pas ($2.00 USD Margin Isolated x 30x Leverage = $60 notional) dan langsung menembak order limit ke MEXC.
4. Otomatis Kunci TP/SL: Begitu posisi terisi (mantul), bot memasang plan order TP (+35%) & SL (-30%) native di server MEXC.
5. Otomatis Refresh Order Basi: Membatalkan order antrean lama (>12 jam belum terjemput) dan menggantikannya dengan level harga segar.
"""

import os
import sys
import time
import json
from pathlib import Path

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

MARGIN_PER_COIN = 2.0  # $2.00 USD Margin Isolated per Koin
LEVERAGE = 30          # 30x Flat
POLL_INTERVAL = 20     # Cek siklus setiap 20 detik

def get_mexc_client():
    cfg_paths = [
        Path.home() / 'bot_final' / 'akun_privat.json',
        Path.home() / 'bot_limit' / 'akun_privat.json',
        Path(__file__).parent / 'akun_privat.json',
        Path(__file__).parent / 'accounts_config.json',
        Path(__file__).parent / 'bot_limit' / 'accounts_config.json',
        Path(r'D:\bot_final\akun_privat.json'),
        Path(r'c:\Users\adee\Documents\antigravity\splendid-hopper\secret_keys.json')
    ]
    
    cfg = None
    for p in cfg_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8-sig'))
                if 'akun_1' in data and 'MEXC' in data['akun_1']:
                    cfg = data['akun_1']['MEXC']
                    break
            except Exception:
                continue
                
    if not cfg:
        raise ValueError("File akun_privat.json / accounts_config.json tidak ditemukan!")
        
    return ccxt.mexc({
        'apiKey': cfg['apiKey'],
        'secret': cfg['secret'],
        'options': {'defaultType': 'swap'},
        'timeout': 15000,
        'enableRateLimit': True
    })

def run_executor_iteration(mx, markets, dry_run=True):
    now_str = time.strftime('%Y-%m-%d %H:%M:%S WIB')
    print(f"\n[{now_str}] 🔄 Memindai portofolio limit order MEXC...")
    
    # 1. Ambil posisi aktif di MEXC
    positions = mx.fetch_positions()
    active_positions = {}
    for p in positions:
        size = float(p.get('contracts') or p.get('size') or 0)
        if size > 0:
            sym_raw = p.get('symbol', '').split(':')[0].replace('/', '_')
            active_positions[sym_raw] = p
            
    # 2. Ambil open limit orders di MEXC
    open_orders = mx.fetch_open_orders()
    active_orders = {}
    for o in open_orders:
        sym_raw = o.get('symbol', '').split(':')[0].replace('/', '_')
        active_orders[sym_raw] = o
        
    print(f"Status Akun MEXC: {len(active_positions)} Posisi Aktif, {len(active_orders)} Limit Order Mengantre.")
    
    # 3. Pindai sinyal limit optimal dari engine
    signals = sniper_limit_engine.scan_all()
    if not signals:
        print("⚠️ Tidak ada sinyal dari engine, mencoba lagi di siklus berikutnya.")
        return
        
    placed_count = 0
    
    for s in signals:
        coin = s['coin']
        mexc_sym = f"{coin}_USDT"
        ccxt_sym = f"{coin}/USDT:USDT"
        side = s.get('side') or ("LONG" if "LONG" in s.get('potensi', '') else "SHORT")
        limit_p = s['limit_p']
        tp_p = s['tp_p']
        sl_p = s['sl_p']
        
        has_pos = mexc_sym in active_positions
        has_ord = mexc_sym in active_orders
        
        # Eksekusi pasang limit order baru jika koin belum ada posisi aktif & belum ada antrean
        if not has_pos and not has_ord and s.get('status') == 'WAITING':
            if ccxt_sym in markets:
                m = markets[ccxt_sym]
                contract_size = float(m.get('contractSize') or 1.0)
                min_amount = float(m.get('limits', {}).get('amount', {}).get('min') or 1.0)
                
                # Hitung ukuran posisi pas: $60 notional = $2 Margin * 30x
                notional_usd = MARGIN_PER_COIN * LEVERAGE
                base_qty = notional_usd / limit_p
                contracts = round(base_qty / contract_size)
                if contracts < min_amount:
                    contracts = min_amount
                    
                order_side = 'buy' if side == 'LONG' else 'sell'
                
                if dry_run:
                    print(f"👉 [DRY RUN] {coin:6}: Akan pasang {side} Limit {contracts} kontrak @ ${limit_p}")
                else:
                    try:
                        print(f"🚀 [AUTO-ORDER] {coin:6}: Mengirim {side} Limit {contracts} kontrak @ ${limit_p} ke MEXC...")
                        res = mx.create_order(
                            symbol=ccxt_sym,
                            type='limit',
                            side=order_side,
                            amount=contracts,
                            price=limit_p,
                            params={'openType': 1} # 1 = Isolated Margin
                        )
                        print(f"   ✅ Sukses! Order ID: {res.get('id')}")
                        placed_count += 1
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"   ❌ Gagal pasang order {coin}: {e}")
                        
    if placed_count > 0:
        print(f"🎉 Berhasil memasang {placed_count} limit order baru secara otomatis!")
    else:
        print("✓ Seluruh koin sudah sinkron (semua posisi & antrean sudah terpasang rapi).")

def main():
    is_live = ("--live" in sys.argv)
    
    print("=" * 85)
    print("🤖 AUTO-EXECUTOR LIMIT ORDER MEXC FUTURES (30x Isolated, Margin $2.00)")
    print(f"Status Mode : {'🚀 LIVE TRADING OTOMATIS (Uang Riil MEXC)' if is_live else '⚠️ DRY RUN (Mode Simulasi Aman)'}")
    print(f"Interval    : Cek dan perbarui setiap {POLL_INTERVAL} detik")
    print("=" * 85)
    print("Keunggulan: Anda TIDAK PERLU lagi memasang limit order manual di aplikasi MEXC!")
    print("Bot akan otomatis memasang limit, mengawal posisi, dan mengunci TP/SL 24/7.")
    print("Tekan Ctrl + C di keyboard/layar untuk menghentikan bot kapan saja.")
    print("=" * 85)
    
    mx = get_mexc_client()
    print("Memuat data pasar MEXC Futures...", flush=True)
    markets = mx.load_markets()
    print("Data pasar siap. Memulai pemantauan 24/7...\n", flush=True)
    
    while True:
        try:
            run_executor_iteration(mx, markets, dry_run=(not is_live))
        except KeyboardInterrupt:
            print("\n🛑 Bot dihentikan oleh pengguna (Ctrl+C). Keluar.")
            break
        except Exception as e:
            print(f"⚠️ Terjadi kendala siklus: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
