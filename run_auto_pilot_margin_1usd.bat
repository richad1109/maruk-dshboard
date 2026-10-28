@echo off
title AUTO-PILOT MEXC LIMIT BOT (MARGIN $1.00 USD) - 24/7
color 0A
echo ==============================================================================
echo        ROBOT TRADING OTOMATIS 24/7 - APEX CASH COW PRO (MEXC CONTRACT)
echo ==============================================================================
echo  Formula Strategi : APEX CASH COW PRO (EMA 34+100, Fibo 48%%, KER >= 0.28)
echo  Ukuran Margin    : $1.00 USD Flat per Koin (Leverage 40x Flat Isolated)
echo  Take Profit (TP) : +22.0%% ROE (Quick-Strike Spot +0.55%%)
echo  Stop Loss (SL)   : -28.0%% ROE (Tight Protection Spot -0.70%%)
echo  Masa Tenang (CD) : 2 Jam Pasca-SL (Anti-Whipsaw Nol Kerugian Beruntun)
echo  Auto Re-Entry    : Koin CD Otomatis Ditembak Limit Order Begitu CD Habis!
echo ==============================================================================
echo.

cd /d "%~dp0"
python auto_limit_executor.py --live --margin 1.00

pause
