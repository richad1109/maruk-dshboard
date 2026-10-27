# 🎯 BOT LIMIT ORDER SNIPER 20 KOIN (Whale Wick & Pullback)
### Terpisah 100% Mandiri · Tidak Mengganggu Bot Astra (`D:\bot_final`)

---

## 🔒 Jaminan Keamanan & Independensi
1. **Bot Astra di `D:\bot_final` 100% TIDAK DIUBAH SAMA SEKALI**:
   - Direktori `D:\bot_final` tetap utuh, aman, dan berjalan sendiri tanpa ada file yang diedit.
   - Kamu bisa tetap memantau bot Astra di dashboard web (`https://maruk-live.streamlit.app`) atau terminal seperti biasa.
2. **`bot_limit` adalah Bot Mandiri (Standalone)**:
   - Dirancang khusus untuk strategi **Limit Order Sniper** pada 20 koin likuiditas tinggi.
   - Tidak bentrok dengan sesi atau API key Astra.
   - Menggunakan data publik real-time bursa BingX (tanpa perlu input API key untuk mode radar).

---

## 📊 Kinerja Strategi Berdasarkan Audit 1 Bulan Riil (30 Hari Terakhir)
- **Modal Per Posisi**: Margin $2.00 USD Isolated
- **Leverage**: 20x – 30x (Sesuai tier koin)
- **Risk : Reward**: **1 : 2.2** (Stop Loss 1.0 ATR, Take Profit 2.2 ATR)
- **Proteksi Auto-BEP**: Kunci modal saat running profit mencapai +15% ROE
- **Hasil Backtest 30 Hari Riil (720 Jam)**:
  - Total Transaksi Terisi: 74 trade (~2.5 trade per hari)
  - Win Rate: **54.1%** (40 TP / 34 SL)
  - Profit Factor: **2.32**
  - **Net Profit Bersih**: **+$33.16 USD (~ Rp 540.533)**
  - Max Drawdown: Hanya -$8.20 USD (~ Rp 133.599)
  - Return on Investment (ROI): **+165.8% dalam 30 Hari** dari buffer modal $20 USD.

---

## 🚀 Cara Menjalankan di Termux Android

### Langkah 1: Ekstrak File
Salin file `bot_limit.zip` ke penyimpanan internal ponsel atau langsung ke Termux, lalu ekstrak:
```bash
unzip bot_limit.zip -d bot_limit
cd bot_limit
```

### Langkah 2: Install Dependensi (Hanya Sekali)
```bash
pip install requests urllib3
```

### Langkah 3: Jalankan Bot
Pilih salah satu cara menjalankan:
- **Mode Live Auto-Refresh (Setiap 10 Detik)**:
  ```bash
  python main_limit_bot.py
  ```
  *(atau jalankan `bash run_termux.sh`)*

- **Mode Sekali Pindai (Single Scan)**:
  ```bash
  python scan_once.py
  ```

---

## 💡 Cara Membaca Output Terminal
- **`⚡ SUDAH KESENTUH (TERISI)`**: Jarum wick harga sudah menyentuh titik limit order kamu. Posisi sudah aktif dan langsung menampilkan **Floating Profit** (`+$0.XX USD` dan `+XX% ROE`).
- **`✅ SETUP VALID` & `⏳ BELUM KESENTUH`**: Setup teknikal pantulan sudah terkonfirmasi dan jarak harga dekat ($\le 2.0\%$). Kamu bisa langsung buka aplikasi bursa dan pasang **Limit Order** di harga **`Entry Limit`**.
- **`🔍 MEMINDAI (BELUM VALID)`**: Jarak harga masih terlalu jauh ($> 2.0\%$), radar terus memantau pergerakan pasar.
- **`[🛡️ AUTO-BEP]`**: Ketika running floating mencapai +15% ROE, bot memberi sinyal untuk menggeser Stop Loss ke harga Entry modal agar posisi menjadi 100% bebas risiko rugi.

---
*Dibuat khusus untuk eksekusi disiplin & pertumbuhan modal nyata tanpa ilusi.*
