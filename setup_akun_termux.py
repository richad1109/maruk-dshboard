#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_akun_termux.py
--------------------
Asisten Interaktif Input API Key MEXC di Termux HP Android.
User tidak perlu edit file JSON secara manual. Cukup jalankan script ini,
paste API Key & Secret Key, dan file akun_privat.json akan dibuat otomatis.
"""

import json
import sys
from pathlib import Path

def setup():
    print("=" * 60)
    print("🚀 PANDUAN CEPAT SETUP API KEY MEXC DI TERMUX HP")
    print("=" * 60)
    print("File konfigurasi akun_privat.json akan dibuat otomatis.")
    print("Pastikan API Key memiliki izin 'Contract / Futures Trading'.\n")

    api_key = input("👉 Masukkan API Key MEXC : ").strip()
    if not api_key:
        print("❌ Error: API Key tidak boleh kosong!")
        sys.exit(1)

    secret_key = input("👉 Masukkan Secret Key MEXC: ").strip()
    if not secret_key:
        print("❌ Error: Secret Key tidak boleh kosong!")
        sys.exit(1)

    config = {
        "akun_1": {
            "MEXC": {
                "apiKey": api_key,
                "secret": secret_key
            }
        }
    }

    # Simpan di folder project saat ini
    target_path = Path(__file__).parent / "akun_privat.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Simpan juga cadangan di Home folder Termux (~/akun_privat.json)
    try:
        home_path = Path.home() / "akun_privat.json"
        with open(home_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

    print("\n✅ File akun_privat.json BERHASIL DISIMPAN!")
    print(f"📁 Lokasi: {target_path}")

    # Uji Koneksi MEXC Live
    print("\n⏳ Menguji koneksi ke MEXC Futures...")
    try:
        import ccxt
        client = ccxt.mexc({
            'apiKey': api_key,
            'secret': secret_key,
            'options': {'defaultType': 'swap'},
            'timeout': 15000,
            'enableRateLimit': True
        })
        bal = client.fetch_balance()
        usdt_free = bal.get('USDT', {}).get('free', 0)
        usdt_total = bal.get('USDT', {}).get('total', 0)
        print(f"🎉 KONEKSI 100% SUKSES TERSAMBUNG KE BURSA MEXC!")
        print(f"💰 Saldo USDT Tersedia : ${usdt_free:.2f} USDT")
        print(f"📊 Total Ekuitas USDT  : ${usdt_total:.2f} USDT")
        print("=" * 60)
        print("💡 SEKARANG JALANKAN BOT AUTO-PILOT DENGAN:")
        print("   python auto_limit_executor.py --live --margin 1.00")
        print("=" * 60)
    except Exception as e:
        print(f"⚠️ Peringatan koneksi: {e}")
        print("Periksa kembali apakah API Key dan Secret Key yang Anda masukkan sudah benar.")

if __name__ == "__main__":
    setup()
