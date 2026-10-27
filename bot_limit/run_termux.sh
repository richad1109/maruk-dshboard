#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Script Peluncur Bot Limit Order Sniper di Termux Android
# ==============================================================================

echo "========================================================"
echo "🎯 Menyiapkan Bot Limit Order Sniper 20 Koin..."
echo "========================================================"

# Pastikan dependencies terpasang
pip install requests urllib3 -q

# Jalankan bot utama
python main_limit_bot.py
