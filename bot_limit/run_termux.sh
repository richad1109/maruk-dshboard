#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Script Peluncur Bot Limit Order Sniper di Termux Android
# ==============================================================================

echo "========================================================"
echo "🎯 BOT LIMIT ORDER SNIPER MEXC (Setting Optimal 9.1x Profit)"
echo "========================================================"
echo "Pilih Mode Operasi:"
echo "1. 🚀 Mode Auto-Pilot 24/7 (Otomatis Pasang Limit di MEXC)"
echo "2. ⚠️ Mode Simulasi / Dry-Run (Cek Sinyal & Sizing Aman)"
echo "3. 📊 Mode Live HUD Terminal (Pantau Floating PnL & WR)"
echo "========================================================"
read -p "Pilihan Anda (1/2/3, default: 1): " choice

pip install requests urllib3 ccxt -q

if [ "$choice" == "2" ]; then
    echo "Menjalankan Mode Simulasi Dry-Run..."
    python auto_limit_executor.py
elif [ "$choice" == "3" ]; then
    echo "Menjalankan Live HUD Monitor..."
    python main_limit_bot.py
else
    echo "Menjalankan Auto-Pilot 24/7 Live MEXC..."
    python auto_limit_executor.py --live
fi
