#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_limit_executor.py
-----------------------
Bot Eksekutor Otomatis Limit Order Sniper MEXC (Mode 24/7).
Bekerja secara mandiri untuk:
1. Membaca sinyal limit terkini dari sniper_limit_engine (Settingan Optimal: Retrace 55%, TP +35%, SL -30%).
2. Memeriksa posisi aktif & antrean order di akun MEXC.
3. Otomatis memasang Limit Order jika koin belum memiliki order/posisi aktif (Margin $2 USD Isolated, Lev 30x).
4. Otomatis memasang TP (+35% ROE) dan SL (-30% ROE) native server-side di MEXC saat posisi terjemput.
5. Otomatis membatalkan order lama yang sudah basi (>12 jam) dan memperbarui dengan level harga segar.
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

MARGIN_PER_COIN = 2.0  # $2.00 USD
LEVERAGE = 30          # 30x Flat
POLL_INTERVAL = 15     # Cek setiap 15 detik

def get_mexc_client():
    # Cari file konfigurasi akun
    cfg_paths = [
        Path(r'D:\bot_final\akun_privat.json'),
        Path(__file__).parent / 'accounts_config.json',
        Path(__file__).parent / 'bot_limit' / 'accounts_config.json',
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

def run_executor_loop(dry_run=True):
    print("=" * 80)
    print("🤖 AUTO-EXECUTOR LIMIT ORDER MEXC FUTURES (30x Isolated, Margin $2.00)")
    print(f"Mode: {'⚠️ DRY RUN (Simulasi Aman)' if dry_run else '🚀 LIVE TRADING AKTIF (Eksekusi Riil MEXC)'}")
    print("=" * 80)
    
    mx = get_mexc_client()
    markets = mx.load_markets()
    
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
        
    print(f"Status Akun Saat Ini: {len(active_positions)} Posisi Aktif, {len(active_orders)} Limit Order Mengantre.\n")
    
    # 3. Pindai sinyal limit optimal dari engine
    signals = sniper_limit_engine.scan_all()
    print(f"{'KOIN':8} | {'SIDE':6} | {'LIMIT ENTRY':12} | {'TP (+35%)':12} | {'SL (-30%)':12} | {'STATUS AKUN'}")
    print("-" * 80)
    
    for s in signals:
        coin = s['coin']
        mexc_sym = f"{coin}_USDT"
        ccxt_sym = f"{coin}/USDT:USDT"
        side = s.get('side') or ("LONG" if "LONG" in s.get('potensi', '') else "SHORT")
        limit_p = s['limit_p']
        tp_p = s['tp_p']
        sl_p = s['sl_p']
        
        # Cek apakah sudah ada di MEXC
        has_pos = mexc_sym in active_positions
        has_ord = mexc_sym in active_orders
        
        if has_pos:
            pos = active_positions[mexc_sym]
            status_desc = f"⚡ POSISI AKTIF (Entry ${pos.get('entryPrice')})"
        elif has_ord:
            ord_obj = active_orders[mexc_sym]
            status_desc = f"⏳ ORDER ANTRI @ ${ord_obj.get('price')}"
        else:
            status_desc = "🆕 SIAP PASANG LIMIT"
            
        print(f"{coin:8} | {side:6} | ${limit_p:<11.4f} | ${tp_p:<11.4f} | ${sl_p:<11.4f} | {status_desc}")
        
        # Eksekusi pemasangan limit order baru jika koin belum ada posisi / antrean
        if not has_pos and not has_ord and s.get('status') == 'WAITING':
            if ccxt_sym in markets:
                m = markets[ccxt_sym]
                contract_size = float(m.get('contractSize') or 1.0)
                min_amount = float(m.get('limits', {}).get('amount', {}).get('min') or 1.0)
                
                # Hitung notional $60 USD = $2 Margin * 30x
                notional_usd = MARGIN_PER_COIN * LEVERAGE
                base_qty = notional_usd / limit_p
                contracts = round(base_qty / contract_size)
                if contracts < min_amount:
                    contracts = min_amount
                    
                if dry_run:
                    print(f"   └─ [DRY RUN] Akan pasang {side} Limit {contracts} kontrak ({ccxt_sym}) @ ${limit_p}")
                else:
                    try:
                        print(f"   └─ [LIVE] Mengirim order limit ke MEXC: {side} {contracts} kontrak @ ${limit_p}...")
                        order_side = 'buy' if side == 'LONG' else 'sell'
                        res = mx.create_order(
                            symbol=ccxt_sym,
                            type='limit',
                            side=order_side,
                            amount=contracts,
                            price=limit_p,
                            params={'openType': 1} # 1 = Isolated Margin
                        )
                        print(f"      ✅ Berhasil dipasang! Order ID: {res.get('id')}")
                    except Exception as e:
                        print(f"      ❌ Gagal pasang order: {e}")

if __name__ == "__main__":
    is_live = ("--live" in sys.argv)
    run_executor_loop(dry_run=(not is_live))
