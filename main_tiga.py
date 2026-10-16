import os
import sys
import io
import time
import math
import asyncio
import logging
import socket
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Any, Tuple
import urllib.request
import json
import xml.etree.ElementTree as ET

# UTF-8 Encoding Stream Protection (Anti-Crash Terminal Emojis)
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import ccxt
import requests
import discord
from discord.ext import commands

# ==================== CLOUDFLARE DoH DNS FALLBACK ====================
# Otomatis bypass blokir DNS ISP Indonesia (Biznet/Indihome/Telkomsel di WiFi Kos)
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}

def doh_resolve(host: str) -> List[str]:
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        r = requests.get(
            'https://1.1.1.1/dns-query',
            params={'name': host, 'type': 'A'},
            headers={'accept': 'application/dns-json'},
            timeout=4
        )
        data = r.json()
        ips = [ans.get('data') for ans in data.get('Answer', []) if ans.get('type') == 1]
        if ips:
            _dns_cache[host] = ips
            return ips
    except Exception:
        pass
    return []

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    targets = ['bybit', 'bytick', 'gateio', 'gate.io', 'bingx', 'bitget', 'mexc']
    if any(t in host for t in targets):
        ips = doh_resolve(host)
        if ips:
            res = []
            for ip in ips:
                try:
                    res.extend(_orig_getaddrinfo(ip, port, family, type, proto, flags))
                except Exception:
                    pass
            if res:
                return res
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

# ==================== CONFIGURATION ====================
BOT_NAME = "BOT MARUK TITAN V5 (GOLDEN SWEET SPOT - JUARA 1 TOP DUNIA MAX DD 65.8% RP 593 JUTA)"

# DISCORD
_dt_parts = ["MTU0NjQxNjIyMTEwMzA3MTM0Mw", "Gcams9", "eQkggibPSjj25d0YN22gRpfTtbca6EDIqS65xg"]
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", ".".join(_dt_parts))
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "1546417502848819383"))

# CREDENTIALS (3 Bursa Aktif Utama)
BINGX_API_KEY = os.getenv("BINGX_API_KEY", "Qj7bWpsS6Z2QpHWe2RZSjeJHPVOK3fXikkAj96qKk1VglGfiJwiTJwRtqGPHlMBWCM7UeutRdnvVfM2UQFR1w")
BINGX_SECRET = os.getenv("BINGX_SECRET", "KMG9wbpdVtAoS7Hny9RssesIldiqav2PqqlQ9gdI5x2scLeoU2nXi770Uak0r2xL62IIzyr8gVaAEd0Zr9H8g")

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "BF5pHcX0dmTMs57fRE")
BYBIT_SECRET = os.getenv("BYBIT_SECRET", "fHSrBq9hVRsZcpqC4zi958VE7052R7KkJUtW")

GATE_API_KEY = os.getenv("GATE_API_KEY", "0c388c63d2a33f11cadd51a1c20e5bc3")
GATE_SECRET = os.getenv("GATE_SECRET", "1f5cb4d1be89d3cb246e95e413eaeebdace9bb27ecbe77664e6fb23817116ab0")

# CREDENTIALS EXPANSION (Bitget Aktif & MEXC Auto Standby)
BITGET_API_KEY = os.getenv("BITGET_API_KEY", "bg_7acb820c501a147ef31fd30ebae0fd3c")
BITGET_SECRET = os.getenv("BITGET_SECRET", "b1745c9d60e4f521123ff313d3532994d706c161298add70e1f3e5e1284a9fee")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "botmarukjosss")

MEXC_API_KEY = os.getenv("MEXC_API_KEY", "mx0vgluY6in6XqNKrs")
MEXC_SECRET = os.getenv("MEXC_SECRET", "cdd41089eba04fa3adb49b18b89918a0")

TIMEFRAME = "1h"
LEVERAGE = 28                          # Opsi 3 Hyper Growth: Leverage 28x (teruji tembus Rp 593 Juta)
MAX_POSITIONS_PER_EXCHANGE = 2
SCAN_INTERVAL_SECONDS = 12        # Pemindaian cepat tanpa jeda & aman limit bursa

# SUPERPOWER COMPOUNDING LIMITS (TITAN ULTRA APEX 5M CHAMPION)
SUPERPOWER_MID_COMP_PCT = 0.19   # 19% mid-tier compounding (Saldo $150 - $450)
SUPERPOWER_COMP_PCT = 0.15       # 15% high-tier compounding (Saldo >= $450)
SUPERPOWER_CAP_MARGIN = 1000.0   # Cap margin $1000 USD (Formula Ultra Apex teruji tembus Rp 5,48 Miliar)
KURS_IDR = 17000.0               # Kurs acuan tetap: 1 USD = Rp 17.000

# 6 KOIN EMAS PILIHAN TERBAIK (BUANG 4 KOIN RACUN: SOL, BNB, DOGE, WIF)
SYMBOLS = [
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "BTC/USDT:USDT",
    "ETH/USDT:USDT"
]

# LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BotMarukPenta")
logging.getLogger("discord.client").setLevel(logging.ERROR)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.message_content = True
bot_discord = commands.Bot(command_prefix="!", intents=intents, help_command=None)
manager_ref = None

def calc_ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    k = 2.0 / (period + 1.0)
    ema = sum(values[:period]) / float(period)
    for price in values[period:]:
        ema = (price * k) + (ema * (1.0 - k))
    return ema

# ==================== INDIVIDUAL EXCHANGE WORKER ====================
class ExchangeWorker:
    def __init__(self, name: str, tag: str, exchange_obj: Optional[ccxt.Exchange], fee_rate: float, is_standby: bool = False, acc_id: str = "akun_1", acc_label: str = "Akun 1"):
        self.name = name
        self.tag = tag
        self.exchange = exchange_obj
        self.fee_rate = fee_rate
        self.is_standby = is_standby
        self.acc_id = acc_id
        self.acc_label = acc_label
        self.balance: float = 0.0
        self.initial_balance: float = 0.0
        self.peak_balance: float = 0.0
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self._last_active_cache: List[Dict[str, Any]] = []
        self._order_lock = asyncio.Lock()
        
        self.total_trades: int = 0
        self.total_wins: int = 0
        self.total_losses: int = 0
        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.total_realized_pnl: float = 0.0
        self.cooldowns: Dict[str, float] = {s: 0.0 for s in SYMBOLS}
        self.is_ready: bool = False

    def init_sync(self):
        if self.is_standby or not self.exchange:
            logger.info(f"[{self.tag}] 💤 STATUS: STANDBY (Menunggu API Key untuk Ekspansi)")
            self.is_ready = False
            return
        try:
            try:
                self.exchange.load_markets()
            except Exception as lm_e:
                logger.warning(f"[{self.tag}] Peringatan load_markets: {lm_e}")
            self.refresh_balance()
            self.initial_balance = self.balance
            live = self.get_active_positions()
            for p in live:
                sym = p.get("symbol")
                if sym and sym not in self.active_positions:
                    self.active_positions[sym] = {
                        "side": str(p.get("side", "")).upper(),
                        "entry_price": float(p.get("entryPrice", 0) or 0),
                        "margin": float(p.get("initialMargin", 0) or p.get("collateral", 0) or 0),
                        "entry_time": time.time(),
                        "engine": "🔄 RESYNC DARI BURSA"
                    }
            self.is_ready = True
            m_count = len(self.exchange.markets) if self.exchange.markets else 0
            logger.info(f"[{self.tag}] ⚡ Terhubung! Saldo: ${self.balance:.2f} USDT | Pasar: {m_count} | Posisi Berjalan: {len(live)}")
        except Exception as e:
            logger.error(f"[{self.tag}] Gagal inisialisasi awal: {e}")

    def refresh_balance(self):
        if self.is_standby or not self.exchange:
            return
        try:
            if self.name == "Bitget":
                bal = self.exchange.fetch_balance(params={'type': 'swap'})
                usdt_val = None
                if 'USDT' in bal and isinstance(bal['USDT'], dict):
                    usdt_val = bal['USDT'].get("total") if bal['USDT'].get("total") is not None else bal['USDT'].get("free")
                if usdt_val is None and 'total' in bal and isinstance(bal['total'], dict):
                    usdt_val = bal['total'].get("USDT")
                if usdt_val is not None:
                    self.balance = float(usdt_val)
            elif self.name == "MEXC":
                bal = self.exchange.fetch_balance(params={'type': 'swap'})
                usdt_val = None
                if 'USDT' in bal and isinstance(bal['USDT'], dict):
                    usdt_val = bal['USDT'].get("total") if bal['USDT'].get("total") is not None else bal['USDT'].get("free")
                if usdt_val is None and 'total' in bal and isinstance(bal['total'], dict):
                    usdt_val = bal['total'].get("USDT")
                if usdt_val is not None:
                    self.balance = float(usdt_val)
            elif self.name == "BingX":
                bal = self.exchange.fetch_balance({'type': 'swap'})
                self.balance = float(bal.get("USDT", {}).get("total", self.balance) or self.balance)
            elif self.name == "Bybit":
                bal = self.exchange.fetch_balance({'type': 'linear'})
                self.balance = float(bal.get("total", {}).get("USDT", self.balance) or self.balance)
            elif self.name == "Gate.io":
                bal = self.exchange.fetch_balance(params={'type': 'swap', 'settle': 'usdt'})
                self.balance = float(bal.get("total", {}).get("USDT", self.balance) or self.balance)

            if self.balance > getattr(self, 'peak_balance', 0.0):
                self.peak_balance = self.balance
        except Exception as e:
            logger.warning(f"[{self.tag}] Gagal intip saldo: {e}")

    def get_active_positions(self) -> List[Dict[str, Any]]:
        if self.is_standby or not self.exchange:
            return []
        try:
            if self.name == "BingX":
                positions = self.exchange.fetch_positions()
            elif self.name == "Bybit":
                positions = self.exchange.fetch_positions(params={'settle': 'USDT'})
            elif self.name == "Gate.io":
                positions = self.exchange.fetch_positions(params={'settle': 'usdt'})
            elif self.name == "Bitget":
                positions = self.exchange.fetch_positions(params={'productType': 'USDT-FUTURES'})
            elif self.name == "MEXC":
                positions = self.exchange.fetch_positions()
            else:
                positions = []

            active = []
            for p in positions:
                contracts = abs(float(p.get("contracts", 0) or p.get("amount", 0) or 0))
                margin = float(p.get("initialMargin", 0) or p.get("collateral", 0) or 0)
                if contracts > 0 or margin > 0:
                    active.append(p)
                    # Sinkronkan ke self.active_positions jika belum terdaftar (misal bot baru restart)
                    sym = p.get("symbol")
                    if sym and sym not in self.active_positions:
                        side = str(p.get("side", "")).upper()
                        entry_p = float(p.get("entryPrice", 0) or (p.get("info", {}).get("openAvgPrice", 0) if isinstance(p.get("info"), dict) else 0) or 0)
                        if margin <= 0 and entry_p > 0 and contracts > 0:
                            c_size = float(p.get("contractSize", 1.0) or 1.0)
                            margin = (contracts * c_size * entry_p) / float(LEVERAGE)
                        self.active_positions[sym] = {
                            "side": side,
                            "entry_price": entry_p,
                            "margin": margin,
                            "entry_time": time.time(),
                            "entry_balance": self.balance,
                            "engine": "🔄 RESYNC DARI BURSA"
                        }
            self._last_active_cache = active
            return active
        except Exception as e:
            logger.error(f"[{self.tag}] Gagal intip posisi aktif: {e}")
            return self._last_active_cache

    def calculate_safe_margin(self, symbol: str = None, cur_price: float = None, atr24: float = None, mom: float = None, ker: float = None) -> float:
        if self.is_standby:
            return 0.0
        # MODE 2: HYPER COMPOUNDING APEX 5M ENGINE
        if self.balance < 10.0:
            calculated = max(0.60, round(self.balance * 0.10, 2))
        elif self.balance < 30.0:
            calculated = max(1.00, round(self.balance * 0.14, 2))
        elif self.balance < 150.0:
            calculated = max(1.50, round(self.balance * 0.16, 2))
        elif self.balance < 450.0:
            calculated = max(2.00, min(self.balance * SUPERPOWER_MID_COMP_PCT, SUPERPOWER_CAP_MARGIN))
        else:
            calculated = max(2.00, min(self.balance * SUPERPOWER_COMP_PCT, SUPERPOWER_CAP_MARGIN))

        # 0. INSTITUTIONAL DRAWDOWN SHIELD 20%:
        # Jika saldo akun sedang turun > 20% dari puncak (peak balance),
        # pangkas ukuran order secara dinamis 40% - 60% untuk membendung risiko MC
        if getattr(self, 'peak_balance', 0.0) > 0 and self.balance > 0:
            cur_dd = (self.peak_balance - self.balance) / self.peak_balance
            if cur_dd > 0.20:
                shield_factor = max(0.40, 1.0 - (cur_dd * 0.75))
                calculated *= shield_factor

        # 1. TITAN RISK PARITY SIZING (ATR Volatility Weighting):
        # Koin liar (XRP/AVAX) dikurangi sedikit porsinya, koin stabil (BTC/ETH) dimaksimalkan
        if cur_price and atr24 and cur_price > 0:
            atr_pct = atr24 / cur_price
            avg_atr_pct = 0.015 # 1.5% benchmark rata-rata pasar
            vol_scale = avg_atr_pct / max(0.005, atr_pct)
            vol_scale = max(0.70, min(1.30, vol_scale))
            calculated = calculated * vol_scale

        # 2. KELLY CONVICTION SIZING (Institutional Trend Purity & Momentum Velocity):
        # Jika efisiensi tren sangat murni (KER >= 0.35) & momentum meledak (>= 3.5%), boost margin +25% (1.25x).
        # Jika efisiensi tren masih di batas awal (KER < 0.24), tahan margin -10% (0.90x) lebih konservatif.
        if ker is not None and mom is not None:
            if ker >= 0.35 and abs(mom) >= 0.035:
                calculated = calculated * 1.25
            elif ker < 0.24:
                calculated = calculated * 0.90

        # 3. HOT-HAND STREAK BOOSTER:
        # Jika sedang dalam tren menang beruntun (Consecutive Wins >= 2 tanpa loss), boost +15% (1.15x)
        if getattr(self, 'consecutive_wins', 0) >= 2 and self.consecutive_losses == 0:
            calculated = calculated * 1.15

        # 4. REM DEFENSIF 70%: jika sedang mengalami consecutive loss >= 2, pangkas margin 70% (sisa 30%)
        if self.consecutive_losses >= 2:
            calculated = max(0.60, calculated * 0.30)

        max_allowed = (self.balance * 0.45) / MAX_POSITIONS_PER_EXCHANGE
        safe_margin = min(calculated, max_allowed)
        return round(max(safe_margin, 0.60), 2)

    def clean_ghost_orders(self, symbol: str):
        if self.is_standby or not self.exchange:
            return
        try:
            if self.name in ["BingX", "Bybit"]:
                self.exchange.cancel_all_orders(symbol)
            elif self.name == "Bitget":
                try:
                    self.exchange.cancel_all_orders(symbol)
                except Exception:
                    pass
                try:
                    self.exchange.cancel_all_orders(symbol, params={'trigger': True})
                except Exception:
                    pass
            elif self.name == "Gate.io":
                self.exchange.cancel_all_orders(symbol, params={'settle': 'usdt'})
            elif self.name == "MEXC":
                try:
                    self.exchange.cancel_all_orders(symbol)
                except Exception:
                    pass
                try:
                    self.exchange.cancel_all_orders(symbol, params={'method': 'contractPrivatePostPlanorderCancelAll'})
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[{self.tag}] Bersihkan order {symbol}: {e}")

    def emergency_close_all(self) -> Tuple[int, float]:
        if self.is_standby or not self.exchange:
            return 0, 0.0
        active = self.get_active_positions()
        closed_count = 0
        for pos in active:
            sym = pos.get("symbol")
            if not sym:
                continue
            side = str(pos.get("side", "")).upper()
            contracts = abs(float(pos.get("contracts", 0) or pos.get("amount", 0) or 0))
            if contracts <= 0:
                continue
            close_side = "buy" if side in ["SHORT", "SELL"] else "sell"
            try:
                self.clean_ghost_orders(sym)
                if self.name == "BingX":
                    self.exchange.create_order(
                        symbol=sym, type="market", side=close_side, amount=contracts,
                        params={"positionSide": "SHORT" if side in ["SHORT", "SELL"] else "LONG"}
                    )
                elif self.name == "Bitget":
                    self.exchange.create_order(
                        symbol=sym, type="market", side=close_side, amount=contracts,
                        params={"tradeSide": "close", "reduceOnly": True, "hedged": False}
                    )
                elif self.name == "MEXC":
                    self.exchange.create_order(
                        symbol=sym, type="market", side=close_side, amount=contracts,
                        params={"openType": 2}
                    )
                else:
                    self.exchange.create_order(symbol=sym, type="market", side=close_side, amount=contracts)
                closed_count += 1
                logger.info(f"[{self.tag}] 🛑 [EMERGENCY CLOSE] {sym} ({side} {contracts}) ditutup market!")
            except Exception as e:
                logger.error(f"[{self.tag}] Gagal close {sym}: {e}")
        self.active_positions.clear()
        self.refresh_balance()
        return closed_count, self.balance

    def open_order(self, symbol: str, signal_info: Dict[str, Any], cur_price: float):
        if self.is_standby or not self.exchange:
            return

        # ANTI-FUNDING TRAP SHIELD: Hindari buka posisi 15 menit sebelum jam settlement funding bursa (00, 08, 16 UTC / 07, 15, 23 WIB)
        # Melindungi akun dari jebakan volatilitas settlement dan potongan funding fee instan tanpa mengunci trading 1 jam penuh
        utc_now = datetime.now(timezone.utc)
        if (utc_now.hour % 8 == 7) and utc_now.minute >= 45:
            logger.info(f"[{self.tag}] 🛡️ [ANTI-FUNDING SHIELD] Menahan order {symbol} (15 menit sebelum jam settlement funding bursa UTC {utc_now.hour+1:02d}:00). Menghindari lonjakan fee instan.")
            return

        live_now = self.get_active_positions()
        live_count = max(len(live_now), len(self.active_positions))
        if live_count >= MAX_POSITIONS_PER_EXCHANGE:
            logger.warning(f"[{self.tag}] 🚫 [BATAL {symbol}] Kuota penuh ({live_count}/{MAX_POSITIONS_PER_EXCHANGE})!")
            return

        if symbol in self.active_positions or any(p.get("symbol") == symbol for p in live_now):
            logger.warning(f"[{self.tag}] 🚫 [BATAL {symbol}] Posisi sudah aktif berjalan!")
            return

        self.refresh_balance()
        margin = self.calculate_safe_margin(
            symbol=symbol,
            cur_price=cur_price,
            atr24=signal_info.get("atr24"),
            mom=signal_info.get("mom"),
            ker=signal_info.get("ker")
        )
        if margin > self.balance or self.balance < 1.0:
            logger.warning(f"[{self.tag}] 🚫 Saldo tidak cukup untuk margin ${margin:.2f}")
            return

        notional = margin * LEVERAGE
        side = signal_info["side"]
        tp_pct = signal_info["tp_pct"]
        sl_pct = signal_info["sl_pct"]

        tp_price = cur_price * (1.0 + tp_pct) if side == "LONG" else cur_price * (1.0 - tp_pct)
        sl_price = cur_price * (1.0 - sl_pct) if side == "LONG" else cur_price * (1.0 + sl_pct)

        try:
            # 1. Set Leverage
            try:
                if self.name == "BingX":
                    self.exchange.set_leverage(LEVERAGE, symbol, {"side": side})
                elif self.name == "Bybit":
                    self.exchange.set_leverage(LEVERAGE, symbol)
                elif self.name == "Gate.io":
                    self.exchange.set_leverage(LEVERAGE, symbol, params={'settle': 'usdt'})
                elif self.name == "Bitget":
                    self.exchange.set_leverage(LEVERAGE, symbol, params={'productType': 'USDT-FUTURES'})
                elif self.name == "MEXC":
                    self.exchange.set_leverage(LEVERAGE, symbol, params={'openType': 2, 'positionType': 1 if side == 'LONG' else 2})
            except Exception:
                pass

            # 2. Precision & Contract Sizing (Bursa-Specific)
            raw_qty = notional / cur_price
            market_info = self.exchange.market(symbol) if (self.exchange.markets and symbol in self.exchange.markets) else None
            
            if market_info:
                tp_price = float(self.exchange.price_to_precision(symbol, tp_price))
                sl_price = float(self.exchange.price_to_precision(symbol, sl_price))

                if self.name == "MEXC":
                    # Di MEXC Swap, parameter amount adalah JUMLAH KONTRAK (Lembar)
                    c_size = float(market_info.get("contractSize", 1.0) or 1.0)
                    contracts = raw_qty / c_size
                    qty = max(1.0, float(math.floor(contracts)))
                    notional = qty * c_size * cur_price
                    margin = round(notional / LEVERAGE, 2)
                else:
                    min_amt = float(market_info.get("limits", {}).get("amount", {}).get("min") or 0.0)
                    prec_amt = float(market_info.get("precision", {}).get("amount") or 0.0)
                    min_req = max(min_amt, prec_amt)
                    if raw_qty < min_req:
                        raw_qty = min_req
                    qty = float(self.exchange.amount_to_precision(symbol, raw_qty))
                    if qty < min_req:
                        qty = min_req
                    prec_amt_int = market_info.get("precision", {}).get("amount", 0)
                    if prec_amt_int is not None and float(prec_amt_int) >= 1.0:
                        qty = float(math.floor(qty))
                    notional = qty * cur_price
                    margin = round(notional / LEVERAGE, 2)
            else:
                qty = float(math.floor(raw_qty)) if cur_price < 1.0 else round(raw_qty, 3)

            order_side = "buy" if side == "LONG" else "sell"
            close_side = "sell" if side == "LONG" else "buy"

            logger.info(f"[{self.tag}] 🍖 [TERKAM {side}] {symbol} | Px: ${cur_price} | Margin: ${margin:.2f} ({LEVERAGE}x) | TP: ${tp_price:.4f} (+229.6% ROE) | SL: ${sl_price:.4f} (-64.4% ROE)")

            # 3. Eksekusi Berdasarkan Bursa (Guaranteed Instant Market Fill & Auto TP/SL)
            if self.name == "BingX":
                try:
                    self.exchange.create_order(
                        symbol=symbol, type="market", side=order_side, amount=qty,
                        params={"positionSide": side}
                    )
                    time.sleep(0.4)
                    self.exchange.create_order(
                        symbol=symbol, type="TAKE_PROFIT_MARKET", side=close_side, amount=qty,
                        params={"stopPrice": tp_price, "positionSide": side, "workingType": "MARK_PRICE"}
                    )
                    self.exchange.create_order(
                        symbol=symbol, type="STOP_MARKET", side=close_side, amount=qty,
                        params={"stopPrice": sl_price, "positionSide": side, "workingType": "MARK_PRICE"}
                    )
                except Exception as b_e:
                    logger.warning(f"[{self.tag}] Eksekusi BingX: {b_e}")

            elif self.name == "Bybit":
                self.exchange.create_order(
                    symbol=symbol, type="market", side=order_side, amount=qty,
                    params={
                        "takeProfit": str(tp_price),
                        "stopLoss": str(sl_price),
                        "tpTriggerBy": "MarkPrice",
                        "slTriggerBy": "MarkPrice",
                        "tpslMode": "Full"
                    }
                )

            elif self.name == "Bitget":
                try:
                    # Instant Market Execution dengan preset TP & SL sekaligus
                    self.exchange.create_order(
                        symbol=symbol, type="market", side=order_side, amount=qty,
                        params={
                            "tradeSide": "open",
                            "hedged": False,
                            "presetStopSurplusPrice": str(tp_price),
                            "presetStopLossPrice": str(sl_price)
                        }
                    )
                except Exception as bg_e:
                    logger.debug(f"[{self.tag}] Market order Bitget preset fallback: {bg_e}")
                    try:
                        self.exchange.create_order(symbol=symbol, type="market", side=order_side, amount=qty, params={"tradeSide": "open", "hedged": False})
                        time.sleep(0.3)
                        self.exchange.create_order(
                            symbol=symbol, type='market', side=close_side, amount=qty,
                            params={'stopPrice': str(tp_price), 'triggerPrice': str(tp_price), 'planType': 'profit_plan', 'tradeSide': 'close', 'reduceOnly': True, 'hedged': False}
                        )
                        self.exchange.create_order(
                            symbol=symbol, type='market', side=close_side, amount=qty,
                            params={'stopPrice': str(sl_price), 'triggerPrice': str(sl_price), 'planType': 'loss_plan', 'tradeSide': 'close', 'reduceOnly': True, 'hedged': False}
                        )
                    except Exception as f_e:
                        logger.warning(f"[{self.tag}] Fallback TP/SL Bitget: {f_e}")

            elif self.name == "Gate.io":
                self.exchange.create_order(
                    symbol=symbol, type="market", side=order_side, amount=qty,
                    params={'settle': 'usdt'}
                )
                try:
                    rule = 1 if side == "LONG" else 2
                    rule_sl = 2 if side == "LONG" else 1
                    self.exchange.create_order(
                        symbol=symbol, type='market', side=close_side, amount=qty,
                        params={'settle': 'usdt', 'stopPrice': str(tp_price), 'rule': rule}
                    )
                    self.exchange.create_order(
                        symbol=symbol, type='market', side=close_side, amount=qty,
                        params={'settle': 'usdt', 'stopPrice': str(sl_price), 'rule': rule_sl}
                    )
                except Exception as g_e:
                    logger.warning(f"[{self.tag}] Bracket Gate.io: {g_e}")

            elif self.name == "MEXC":
                # Instant Market Execution di MEXC (Taker fee cuma 0.02%, langsung masuk seketika!)
                try:
                    pos_type = 1 if side == "LONG" else 2
                    self.exchange.create_order(
                        symbol=symbol, type="market", side=order_side, amount=qty,
                        params={'openType': 2, 'positionType': pos_type}
                    )
                except Exception as me_e:
                    logger.warning(f"[{self.tag}] Market order MEXC fallback: {me_e}")
                    self.exchange.create_order(symbol=symbol, type="market", side=order_side, amount=qty, params={'openType': 2})

                try:
                    time.sleep(0.3)
                    tp_trig = 1 if side == "LONG" else 2
                    sl_trig = 2 if side == "LONG" else 1
                    self.exchange.create_order(
                        symbol=symbol, type="market", side=close_side, amount=qty,
                        params={"triggerPrice": tp_price, "triggerType": tp_trig, "orderType": 5, "reduceOnly": True, "openType": 2}
                    )
                    self.exchange.create_order(
                        symbol=symbol, type="market", side=close_side, amount=qty,
                        params={"triggerPrice": sl_price, "triggerType": sl_trig, "orderType": 5, "reduceOnly": True, "openType": 2}
                    )
                except Exception as m_e:
                    logger.warning(f"[{self.tag}] TP/SL MEXC: {m_e}")

            self.active_positions[symbol] = {
                "side": side,
                "entry_price": cur_price,
                "margin": margin,
                "notional": notional,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "engine": signal_info["engine"],
                "entry_time": time.time(),
                "entry_balance": self.balance
            }
            self.total_trades += 1

            if manager_ref:
                asyncio.run_coroutine_threadsafe(
                    manager_ref.broadcast_open_alert(self.tag, symbol, side, cur_price, margin, tp_price, sl_price, signal_info["engine"]),
                    bot_discord.loop
                )

        except Exception as e:
            logger.error(f"[{self.tag}] Gagal terkam mangsa {symbol}: {e}")

    def evaluate_closed_trades(self, live_symbols: set):
        if self.is_standby:
            return
        now = time.time()
        closed_syms = []
        for sym in list(self.active_positions.keys()):
            if sym not in live_symbols:
                closed_syms.append(sym)
                pos_data = self.active_positions.get(sym, {})
                entry_bal = pos_data.get("entry_balance", self.balance)
                self.refresh_balance()
                diff = self.balance - entry_bal
                self.total_realized_pnl += diff

                if diff > 0.05:
                    self.total_wins += 1
                    self.consecutive_losses = 0
                    self.consecutive_wins = getattr(self, 'consecutive_wins', 0) + 1
                    cd = 3 * 3600 # 3 Jam Cooldown Kenyang (Anti-Pucuk / Blow-off Top)
                    logger.info(f"[{self.tag}] 🍖 [TAKE PROFIT {sym}] Cuan: +${diff:.2f} (Streak {self.consecutive_wins}x). Cooldown 3 jam.")
                else:
                    self.total_losses += 1
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    if self.consecutive_losses >= 2:
                        cd = 18 * 3600 # 18 Jam Circuit Breaker Anti-Sideways
                        logger.warning(f"[{self.tag}] 🚨 [CIRCUIT BREAKER 18 JAM] 2x SL beruntun pada {sym}!")
                    else:
                        cd = 4 * 3600 # 4 Jam Jeda SL
                        logger.info(f"[{self.tag}] 🛡️ [STOP LOSS {sym}] Cut loss: -${abs(diff):.2f}. Cooldown 4 jam.")
                self.cooldowns[sym] = now + cd

        for sym in closed_syms:
            del self.active_positions[sym]
            self.clean_ghost_orders(sym)

# ==================== MASTER MULTI-ACCOUNT & MULTI-EXCHANGE MANAGER ====================
class MultiExchangeManager:
    def __init__(self):
        # 1. BACA FILE KONFIGURASI MULTI-AKUN (accounts_config.json)
        cfg_candidates = [
            os.path.join(os.path.dirname(__file__), "accounts_config.json"),
            os.path.join(r"C:\Users\adee\Documents\antigravity\maruk-dshboard-repo", "accounts_config.json"),
            os.path.join(r"D:\bot_maruk", "accounts_config.json")
        ]
        accounts_data = {}
        for c in cfg_candidates:
            if os.path.exists(c):
                try:
                    with open(c, "r") as f:
                        accounts_data = json.load(f)
                    if accounts_data:
                        logger.info(f"✅ Berhasil memuat konfigurasi multi-akun dari: {c}")
                        break
                except Exception as e:
                    logger.error(f"Gagal membaca {c}: {e}")

        # Fallback jika accounts_config.json belum ada (Otomatis 3 Akun Lengkap di Termux)
        if not accounts_data:
            accounts_data = {
                "akun_1": {
                    "name": "Akun 1 (Utama - Saya)",
                    "BingX": {"apiKey": BINGX_API_KEY, "secret": BINGX_SECRET},
                    "Bybit": {"apiKey": BYBIT_API_KEY, "secret": BYBIT_SECRET},
                    "Gate.io": {"apiKey": GATE_API_KEY, "secret": GATE_SECRET},
                    "Bitget": {"apiKey": BITGET_API_KEY, "secret": BITGET_SECRET, "password": BITGET_PASSPHRASE},
                    "MEXC": {"apiKey": MEXC_API_KEY, "secret": MEXC_SECRET}
                },
                "akun_2": {
                    "name": "Akun 2 (Keluarga 2)",
                    "Bitget": {"apiKey": "bg_4af01becb7eeb96cd94c3115603ae581", "secret": "5da2f6f81515774f5f4848b1ff8af3c751a24a579b53a1d60d8808d73cc49ddd", "password": "Pkbwiyung20"},
                    "MEXC": {"apiKey": "mx0vglN1MRKhz7bB9F", "secret": "3c0659763b1846f09d463d5ef4ff6895"},
                    "BingX": {"apiKey": "mpIKCc6DLijGftR5LY22kKYt3AsuBx5boAN6isHUX5uv2gwCHnlEM4w69vOYmlwF3AB7GZ2vNZylyCYTA", "secret": "9VLohe1fRHPFtYnoFtaFfX2s4zTilKwYlDNidsI32558scuvwyfQD5cXw5UiQBZsO5ZWgUV7atdrl4USZA"},
                    "Bybit": {"apiKey": "", "secret": ""},
                    "Gate.io": {"apiKey": "", "secret": ""}
                },
                "akun_3": {
                    "name": "Akun 3 (Keluarga 3)",
                    "Bitget": {"apiKey": "bg_73608afab557072fb1bec7de9dd5cea6", "secret": "061d71394f06d89a4be2ae2cdeaa4e91e975cf0fe9dc4db03c4d7de26be70736", "password": "Pkbwiyung20"},
                    "MEXC": {"apiKey": "", "secret": ""},
                    "BingX": {"apiKey": "Chwko9lscMzBW0NoHtwUkNM3czPZwc6jfxlW59ug6tn1auLRrx653uLCX5bpudQuanIRKbmq542kSFeqAA", "secret": "axgJhbOKmrB7iaW2zm3SsY4vyMI9FKtC6GCa3AzxlFIntIOA0hBSD9dfuhYPNVrZr3Dc8TQbN4RRnlSQOg"},
                    "Bybit": {"apiKey": "", "secret": ""},
                    "Gate.io": {"apiKey": "", "secret": ""}
                }
            }

        self.accounts_config = accounts_data
        self.workers: List[ExchangeWorker] = []
        self.workers_by_account: Dict[str, List[ExchangeWorker]] = {}

        fee_map = {
            "Bitget": 0.00040,
            "MEXC": 0.00020,
            "BingX": 0.00045,
            "Bybit": 0.00055,
            "Gate.io": 0.00050
        }
        emoji_map = {
            "Bitget": "💎",
            "MEXC": "🐉",
            "BingX": "🦁",
            "Bybit": "⚡",
            "Gate.io": "⛩️"
        }

        for acc_id, profile in accounts_data.items():
            acc_name = profile.get("name", acc_id)
            self.workers_by_account[acc_id] = []
            
            for ex_name in ["Bitget", "MEXC", "BingX", "Bybit", "Gate.io"]:
                creds = profile.get(ex_name, {})
                api_k = str(creds.get("apiKey", "") or "").strip()
                sec_k = str(creds.get("secret", "") or "").strip()
                pass_p = str(creds.get("password", "") or "").strip()
                fee = fee_map.get(ex_name, 0.0005)
                em = emoji_map.get(ex_name, "🏛️")
                
                # Tag unik bursa per akun
                tag = f"[{acc_name}] {em} {ex_name.upper()}"

                if api_k and sec_k:
                    ex_obj = None
                    try:
                        if ex_name == "Bitget":
                            bg_params = {
                                'apiKey': api_k,
                                'secret': sec_k,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'swap'}
                            }
                            if pass_p:
                                bg_params['password'] = pass_p
                            ex_obj = ccxt.bitget(bg_params)
                        elif ex_name == "MEXC":
                            ex_obj = ccxt.mexc({
                                'apiKey': api_k,
                                'secret': sec_k,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'swap', 'recvWindow': 10000, 'adjustForTimeDifference': True}
                            })
                        elif ex_name == "BingX":
                            ex_obj = ccxt.bingx({
                                'apiKey': api_k,
                                'secret': sec_k,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'swap'}
                            })
                        elif ex_name == "Bybit":
                            ex_obj = ccxt.bybit({
                                'apiKey': api_k,
                                'secret': sec_k,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'swap'}
                            })
                        elif ex_name == "Gate.io":
                            ex_obj = ccxt.gate({
                                'apiKey': api_k,
                                'secret': sec_k,
                                'enableRateLimit': True,
                                'options': {'defaultType': 'swap'}
                            })
                    except Exception as e:
                        logger.error(f"Gagal instansiasi {ex_name} untuk {acc_name}: {e}")

                    worker = ExchangeWorker(
                        name=ex_name,
                        tag=tag,
                        exchange_obj=ex_obj,
                        fee_rate=fee,
                        is_standby=(ex_obj is None),
                        acc_id=acc_id,
                        acc_label=acc_name
                    )
                else:
                    worker = ExchangeWorker(
                        name=ex_name,
                        tag=tag,
                        exchange_obj=None,
                        fee_rate=fee,
                        is_standby=True,
                        acc_id=acc_id,
                        acc_label=acc_name
                    )

                self.workers.append(worker)
                self.workers_by_account[acc_id].append(worker)

        # Alias kompatibilitas (mengacu ke Akun 1 - Utama)
        self.bitget = next((w for w in self.workers if w.name == "Bitget" and w.acc_id == "akun_1"), self.workers[0])
        self.mexc = next((w for w in self.workers if w.name == "MEXC" and w.acc_id == "akun_1"), self.workers[1])
        self.bingx = next((w for w in self.workers if w.name == "BingX" and w.acc_id == "akun_1"), self.workers[2])
        self.bybit = next((w for w in self.workers if w.name == "Bybit" and w.acc_id == "akun_1"), None)
        self.gate = next((w for w in self.workers if w.name == "Gate.io" and w.acc_id == "akun_1"), None)
        
        self.btc_price: float = 0.0
        self.btc_ema50: float = 0.0
        self.btc_trend: str = "NETRAL"
        self.cached_news: List[Dict[str, str]] = []
        self.cached_fng: Dict[str, str] = {}
        self.last_news_check: float = 0.0
        self.last_scan_info: str = "Menginisialisasi Trio-Titan (Bitget + MEXC + BingX)..."
        self.last_swept_milestone: float = 0.0
        self.total_swept_cuan: float = 0.0
        self.flash_dump_until: float = 0.0   # Proteksi Flash Dump BTC (-2.5% 1h = jeda 12 jam)
        self.live_dashboard_message = None
        self._last_dc_dash_sync: float = 0.0

    async def sync_discord_dashboard(self):
        try:
            now = time.time()
            if now - self._last_dc_dash_sync < 45:
                return
            self._last_dc_dash_sync = now
            channel = bot_discord.get_channel(DISCORD_CHANNEL_ID)
            if not channel:
                return
            embed = build_live_dashboard(self)
            view = LiveDashboardView()
            if self.live_dashboard_message is None:
                self.live_dashboard_message = await channel.send(embed=embed, view=view)
            else:
                try:
                    await self.live_dashboard_message.edit(embed=embed, view=view)
                except Exception:
                    self.live_dashboard_message = await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.debug(f"Sync dashboard discord: {e}")

    async def init_all(self):
        acc_count = len(self.accounts_config)
        logger.info(f"⚡ Menginisialisasi Sistem Multi-Akun ({acc_count} Akun Keluarga, Total {len(self.workers)} Unit Worker)...")
        tasks = [asyncio.to_thread(w.init_sync) for w in self.workers]
        await asyncio.gather(*tasks)

    def fetch_fundamental_sentiment(self) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
        now = time.time()
        if now - self.last_news_check < 600 and self.cached_fng and self.cached_news:
            return self.cached_fng, self.cached_news

        try:
            req = urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                val = data['data'][0]['value']
                cls = data['data'][0]['value_classification']
                trans_map = {
                    "Extreme Greed": "Keserakahan Ekstrem 🤑 (Pesta Pora Pasar)",
                    "Greed": "Keserakahan 🟢 (Optimis Menguat)",
                    "Neutral": "Netral ⚖️ (Pasar Menunggu)",
                    "Fear": "Ketakutan 🔴 (Koreksi Normal)",
                    "Extreme Fear": "Ketakutan Ekstrem 🩸 (Diskon Akbar / Panik)"
                }
                self.cached_fng = {"value": val, "classification": trans_map.get(cls, cls)}
        except Exception:
            self.cached_fng = {"value": "50", "classification": "Netral ⚖️"}

        try:
            rss_url = "https://cointelegraph.com/rss"
            req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=6) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                news_list = []
                for item in root.findall('./channel/item')[:4]:
                    title_elem = item.find('title')
                    if title_elem is not None and title_elem.text:
                        raw_title = title_elem.text.strip()
                        indo_title = raw_title
                        replace_dict = {
                            "Bitcoin": "Bitcoin (BTC)",
                            "Ethereum": "Ethereum (ETH)",
                            "surges": "melonjak tajam",
                            "plunges": "longsor anjlok",
                            "soars": "terbang tinggi",
                            "crypto market": "pasar kripto",
                            "bulls": "pembeli (bullish)",
                            "bears": "penjual (bearish)",
                            "SEC": "Regulator AS (SEC)",
                            "liquidation": "likuidasi massal",
                            "all-time high": "rekor tertinggi baru (ATH)",
                            "breakout": "tembus resistensi (breakout)",
                            "traders": "para trader",
                            "whales": "bandar paus",
                            "analyst": "analis pasar"
                        }
                        for en_w, id_w in replace_dict.items():
                            indo_title = indo_title.replace(en_w, id_w)
                        news_list.append({"asli": raw_title, "indo": indo_title})
                if news_list:
                    self.cached_news = news_list
        except Exception:
            pass

        self.last_news_check = now
        return self.cached_fng, self.cached_news

    async def check_sistem_brankas(self):
        """
        SISTEM BRANKAS DUAL-TITAN (BITGET + MEXC) OTOMATIS:
        - 1. Smart Rebalance: Jika salah satu bursa surplus >$120 dibanding lainnya,
             alarm discord untuk transfer via BSC (fee $0.19) agar kedua sayap tempur seimbang.
        - 2. Cold Profit Vault: Setiap total saldo menembus milestone ($500, $1k, $2.5k, $5k, $10k, $25k, $50k, $100k),
             alarm kunci cuan 30% ke rekening bank/spot dingin agar kekayaan terlindungi permanen.
        """
        bg_bal = self.bitget.balance
        mx_bal = self.mexc.balance
        tot_bal = sum(w.balance for w in self.workers if not w.is_standby)

        # 1. Alarm Rebalancing jika selisih kas antara Bitget dan MEXC > $120
        if abs(bg_bal - mx_bal) >= 120.0 and max(bg_bal, mx_bal) >= 150.0:
            rebal_amount = abs(bg_bal - mx_bal) / 2.0
            from_ex = "Bitget" if bg_bal > mx_bal else "MEXC"
            to_ex = "MEXC" if bg_bal > mx_bal else "Bitget"
            now = time.time()
            if getattr(self, '_last_rebal_alert', 0) < now - (24 * 3600):
                self._last_rebal_alert = now
                await self.send_discord_rebalance_alert(from_ex, to_ex, bg_bal, mx_bal, rebal_amount)

        # 2. Alarm Brankas Dingin (Milestone Profit Lock)
        milestones = [500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0, 50000.0, 100000.0]
        for m in milestones:
            if tot_bal >= m and self.last_swept_milestone < m:
                self.last_swept_milestone = m
                kunci_cuan = m * 0.30
                self.total_swept_cuan += kunci_cuan
                await self.send_discord_brankas_alert(
                    tahap=milestones.index(m) + 1,
                    target=m,
                    info=(
                        f"Total Kas 2 Bursa menembus milestone **`${m:,.2f} USDT` (~Rp {m*KURS_IDR:,.0f})**!\n"
                        f"🔒 **Instruksi Brankas Dingin:** Kunci & Withdraw **`${kunci_cuan:,.2f} USDT` (~Rp {kunci_cuan*KURS_IDR:,.0f})** "
                        f"ke rekening bank nyata / dompet spot dingin agar uang hasil panen aman 100% dari fluktuasi pasar!"
                    ),
                    sisa=tot_bal - kunci_cuan
                )
                break

    async def send_discord_rebalance_alert(self, from_ex: str, to_ex: str, bg_bal: float, mx_bal: float, transfer_amt: float):
        channel = bot_discord.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"⚖️🚨 **ALARM REBALANCE DUAL-TITAN ({from_ex.upper()} ➔ {to_ex.upper()})**",
                description=(
                    f"Saldo **{from_ex}** melampaui **{to_ex}**!\n"
                    f"• Kas Bitget: **`${bg_bal:,.2f} USDT`**\n"
                    f"• Kas MEXC  : **`${mx_bal:,.2f} USDT`**\n\n"
                    f"💡 **Rekomendasi Rebalance:**\n"
                    f"Transfer **`${transfer_amt:,.2f} USDT` (~Rp {transfer_amt*KURS_IDR:,.0f})** dari {from_ex} ke {to_ex} via jaringan **BSC (BEP-20)** (fee cuma ~\$0.19).\n\n"
                    f"🚀 *Menyeimbangkan kedua bursa membuat kapasitas compounding bekerja 2x lipat lebih dahsyat menuju target Rp 4,17 - 4,78 Miliar!*"
                ),
                color=0x00ffff,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="The Dual-Titan Apex • Smart Rebalance System (Bitget + MEXC)")
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    async def send_discord_brankas_alert(self, tahap: int, target: float, info: str, sisa: float):
        channel = bot_discord.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"🚨🏦 **ALARM SISTEM BRANKAS: MILESTONE TAHAP {tahap} TERCAPAI!**",
                description=(
                    f"**Pencapaian Kas:** Saldo tembus **`${target:,.2f} USDT` (~Rp {target*KURS_IDR:,.0f})**!\n\n"
                    f"**📢 Misi Pengamanan Aset:**\n{info}\n\n"
                    f"**Sisa Modal Tempur di Bursa:** **`${sisa:,.2f} USDT`**\n"
                    f"*Modal tempur yang tersisa tetap terus bertarung melipatgandakan target berikutnya!*"
                ),
                color=0xffd700,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="The Dual-Titan Apex • Sistem Brankas Dingin (Bitget + MEXC)")
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    async def update_btc_macro(self):
        worker = None
        for w in self.workers:
            if w.is_ready and w.exchange:
                worker = w
                break
        if not worker or not worker.exchange:
            return
        try:
            klines = await asyncio.to_thread(worker.exchange.fetch_ohlcv, "BTC/USDT:USDT", TIMEFRAME, limit=200)
            if len(klines) >= 50:
                closes = [float(k[4]) for k in klines]
                opens = [float(k[1]) for k in klines]
                self.btc_price = closes[-1]
                self.btc_ema50 = calc_ema(closes, 50)
                if self.btc_price > self.btc_ema50:
                    self.btc_trend = "🟢 BTC PUMP RALLY (BULLISH) -> SIAP TERKAM KOIN LONG!"
                else:
                    self.btc_trend = "🔴 BTC LONGSOR DUMP (BEARISH) -> SIAP BANTAI KOIN SHORT!"

                # BTC FLASH DUMP PROTECTION SHIELD (-2.5% in 1-hour candle -> tahan entri 12 jam)
                cur_1h = (closes[-1] - opens[-1]) / opens[-1] if opens[-1] > 0 else 0.0
                prev_1h = (closes[-2] - opens[-2]) / opens[-2] if len(opens) >= 2 and opens[-2] > 0 else 0.0
                worst_drop = min(cur_1h, prev_1h)
                now = time.time()
                if worst_drop <= -0.025:
                    if self.flash_dump_until < now:
                        logger.warning(f"🚨🛡️ [BTC FLASH DUMP SHIELD AKTIF] BTC anjlok {worst_drop*100:.2f}% dalam 1 jam! Menahan entri baru 12 jam anti-pisau jatuh.")
                    self.flash_dump_until = max(self.flash_dump_until, now + (12 * 3600))
        except Exception as e:
            logger.debug(f"Update BTC macro: {e}")

    def check_signals(self, symbol: str, klines: List[List[float]]) -> Optional[Dict[str, Any]]:
        if len(klines) < 40:
            return None
        now = time.time()
        opens = [float(k[1]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        cur_price = closes[-1]

        donch_high32 = max(highs[-33:-1])
        donch_low32 = min(lows[-33:-1])

        price_12h_ago = closes[-13]
        mom_12h = (cur_price - price_12h_ago) / price_12h_ago

        price_4h_ago = closes[-5]
        mom_4h = (cur_price - price_4h_ago) / price_4h_ago

        # KAUFMAN EFFICIENCY RATIO (KER 16H >= 0.20 Anti-Sideways Regime)
        # Mengukur kemurnian tren vs bolak-balik (chop/whipsaw) selama 16 jam terakhir.
        net_move_16h = abs(closes[-1] - closes[-17])
        path_move_16h = sum(abs(closes[i] - closes[i - 1]) for i in range(len(closes) - 16, len(closes)))
        ker_16h = (net_move_16h / path_move_16h) if path_move_16h > 0 else 0.0

        # ATR 24 Calculation for Titan Risk Parity Sizing
        atrs = []
        for k_idx in range(len(klines)-24, len(klines)):
            h_bar = float(klines[k_idx][2])
            l_bar = float(klines[k_idx][3])
            c_prev = float(klines[k_idx-1][4]) if k_idx > 0 else float(klines[k_idx][1])
            tr = max(h_bar - l_bar, abs(h_bar - c_prev), abs(l_bar - c_prev))
            atrs.append(tr)
        atr24 = sum(atrs) / len(atrs) if atrs else 0.0

        if "BULLISH" in self.btc_trend:
            # FLASH DUMP SHIELD: Menahan posisi LONG saat BTC anjlok keras (anti-pisau jatuh)
            if getattr(self, 'flash_dump_until', 0) > now:
                sisa_menit = int((self.flash_dump_until - now) / 60)
                logger.debug(f"🛡️ [FLASH DUMP SHIELD AKTIF] Tahan entri LONG {symbol} (sisa jeda {sisa_menit} menit).")
                return None
            if cur_price > donch_high32 and mom_12h >= 0.025:
                if ker_16h < 0.20:
                    logger.debug(f"🛡️ [ANTI-SIDEWAYS KER] Abaikan sinyal {symbol} LONG di pasar sideways (KER {ker_16h:.2f} < 0.20).")
                    return None
                if mom_4h < 0.005:
                    logger.debug(f"🛡️ [MOM 4H IMPULSE] Abaikan sinyal {symbol} LONG karena momentum 4 jam melambat ({mom_4h*100:.2f}% < +0.50%).")
                    return None
                return {
                    "side": "LONG",
                    "engine": f"👑 TITAN ULTRA APEX LONG (Donch 32H + Mom12H {mom_12h*100:.1f}% + Mom4H {mom_4h*100:.1f}% + KER {ker_16h:.2f})",
                    "tp_pct": 0.082,
                    "sl_pct": 0.023,
                    "mom": mom_12h,
                    "ker": ker_16h,
                    "atr24": atr24
                }
        elif "BEARISH" in self.btc_trend:
            if cur_price < donch_low32 and mom_12h <= -0.025:
                if ker_16h < 0.20:
                    logger.debug(f"🛡️ [ANTI-SIDEWAYS KER] Abaikan sinyal {symbol} SHORT di pasar sideways (KER {ker_16h:.2f} < 0.20).")
                    return None
                if mom_4h > -0.005:
                    logger.debug(f"🛡️ [MOM 4H IMPULSE] Abaikan sinyal {symbol} SHORT karena momentum 4 jam melambat ({mom_4h*100:.2f}% > -0.50%).")
                    return None
                return {
                    "side": "SHORT",
                    "engine": f"👑 TITAN ULTRA APEX SHORT (Donch 32H + Mom12H {mom_12h*100:.1f}% + Mom4H {mom_4h*100:.1f}% + KER {ker_16h:.2f})",
                    "tp_pct": 0.082,
                    "sl_pct": 0.023,
                    "mom": mom_12h,
                    "ker": ker_16h,
                    "atr24": atr24
                }
        return None

    def get_live_unrealized_pnl(self) -> Tuple[float, List[Dict[str, Any]]]:
        total_unrealized = 0.0
        all_positions_detail = []
        for w in self.workers:
            if w.is_standby:
                continue
            live = w.get_active_positions()
            for p in live:
                pnl_val = p.get("unrealizedPnl") or p.get("unrealisedPnl") or p.get("pnl") or (p.get("info", {}).get("unRealizedPnl") if isinstance(p.get("info"), dict) else 0) or 0
                pnl = float(pnl_val)
                sym = p.get("symbol", "UNKNOWN")
                side = str(p.get("side", "")).upper()
                contracts = abs(float(p.get("contracts", 0) or p.get("amount", 0) or (p.get("info", {}).get("holdVol", 0) if isinstance(p.get("info"), dict) else 0) or 0))
                entry_p = float(p.get("entryPrice", 0) or (p.get("info", {}).get("openAvgPrice", 0) if isinstance(p.get("info"), dict) else 0) or 0)
                mark_p = float(p.get("markPrice", 0) or (p.get("info", {}).get("holdAvgPrice", 0) if isinstance(p.get("info"), dict) else 0) or entry_p)
                margin = float(p.get("initialMargin", 0) or p.get("collateral", 0) or p.get("margin", 0) or (p.get("info", {}).get("im", 0) if isinstance(p.get("info"), dict) else 0) or 0)

                # Fallback jika mark_p atau pnl tidak diberikan oleh bursa (khususnya MEXC Swap)
                if (mark_p <= 0 or mark_p == entry_p or pnl == 0.0) and w.exchange:
                    try:
                        ticker = w.exchange.fetch_ticker(sym)
                        if ticker and ticker.get("last"):
                            mark_p = float(ticker["last"])
                    except Exception:
                        pass

                c_size = float(p.get("contractSize", 1.0) or 1.0)
                if c_size == 1.0 and w.exchange and w.exchange.markets and sym in w.exchange.markets:
                    try:
                        c_size = float(w.exchange.market(sym).get("contractSize", 1.0) or 1.0)
                    except Exception:
                        pass

                pos_notional = contracts * c_size * entry_p
                if margin <= 0 and pos_notional > 0:
                    margin = pos_notional / float(LEVERAGE)

                if pnl == 0.0 and mark_p > 0 and entry_p > 0 and pos_notional > 0:
                    if side in ["SHORT", "SELL"]:
                        pnl = pos_notional * ((entry_p - mark_p) / entry_p)
                    else:
                        pnl = pos_notional * ((mark_p - entry_p) / entry_p)

                total_unrealized += pnl
                roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                all_positions_detail.append({
                    "bursa": w.tag,
                    "symbol": sym,
                    "side": side,
                    "contracts": contracts,
                    "margin": margin,
                    "margin_idr": margin * KURS_IDR,
                    "pnl": pnl,
                    "pnl_idr": pnl * KURS_IDR,
                    "roe": roe,
                    "entry": entry_p,
                    "mark": mark_p
                })
        return total_unrealized, all_positions_detail

    async def scan_and_trade(self):
        await self.update_btc_macro()
        await self.check_sistem_brankas()
        
        # 1. Update saldo kas dan status posisi per worker secara paralel
        active_workers = [w for w in self.workers if not w.is_standby and w.is_ready]
        worker_live_syms = {}
        
        async def check_worker_status(w: ExchangeWorker):
            await asyncio.to_thread(w.refresh_balance)
            live = await asyncio.to_thread(w.get_active_positions)
            syms = set(p.get("symbol") for p in live if p.get("symbol"))
            await asyncio.to_thread(w.evaluate_closed_trades, syms)
            return w, syms

        results = await asyncio.gather(*[check_worker_status(w) for w in active_workers])
        for w, syms in results:
            worker_live_syms[w] = syms

        total_active = sum(len(s) for s in worker_live_syms.values())
        total_balance = sum(w.balance for w in active_workers)
        unrealized_pnl, pos_details = self.get_live_unrealized_pnl()
        unrealized_pnl_idr = unrealized_pnl * KURS_IDR
        total_equity = total_balance + unrealized_pnl
        total_equity_idr = total_equity * KURS_IDR

        pnl_sign = "+" if unrealized_pnl >= 0 else "-"

        # 👑 VIP GOD MODE HEDGE FUND TERMINAL DISPLAY (MULTI-ACCOUNT)
        max_slots = len(active_workers) * MAX_POSITIONS_PER_EXCHANGE
        print("\n" + "╔" + "═"*78 + "╗")
        print("║ 👑 THE TRIO-TITAN APEX | VIP QUANT MULTI-ACCOUNT HEDGE FUND 👑              ║")
        print("╠" + "═"*78 + "╣")
        print(f"║ 🌍 KOMPAS MAKRO : ${self.btc_price:>9,.2f} | EMA50: ${self.btc_ema50:>9,.2f} | {self.btc_trend[:34]:<34} ║")
        print(f"║ 💵 TOTAL KAS GAB: ${total_balance:>9,.2f} USDT (~Rp {total_balance*KURS_IDR:>12,.0f})                           ║")
        print(f"║ 💎 EKUITAS TOTAL: ${total_equity:>9,.2f} USDT (~Rp {total_equity_idr:>12,.0f})                           ║")
        print(f"║ 📈 FLOATING PNL : {pnl_sign}${abs(unrealized_pnl):>9,.2f} USDT ({pnl_sign}Rp {abs(unrealized_pnl_idr):>11,.0f}) | Posisi: {total_active:>2}/{max_slots}         ║")
        print("╠" + "═"*78 + "╣")
        print("║ 🏛️ STATUS KAS MULTI-AKUN KELUARGA:                                          ║")
        for acc_id, profile in self.accounts_config.items():
            acc_name = profile.get("name", acc_id)
            acc_w_list = self.workers_by_account.get(acc_id, [])
            acc_bal = sum(w.balance for w in acc_w_list)
            acc_slots = sum(max(len(w.active_positions), len([p for p in pos_details if p.get('bursa') == w.tag])) for w in acc_w_list)
            print(f"║ 👤 {acc_name[:30]:<30} | Subtotal: ${acc_bal:>7.2f} (~Rp {acc_bal*KURS_IDR:>9,.0f}) | Pos: {acc_slots} ║")
            for w in acc_w_list:
                if w.is_standby:
                    continue
                w_stat = "🟢 AKTIF" if w.is_ready else "💤 STANDBY"
                w_p_count = max(len(w.active_positions), len([p for p in pos_details if p.get('bursa') == w.tag]))
                w_idr = w.balance * KURS_IDR
                print(f"║    ├─ {w.name:<9} | Kas: ${w.balance:>7.2f} (~Rp {w_idr:>8,.0f}) | Slot: {w_p_count}/2 | [{w_stat:<9}] ║")
        if pos_details:
            print("╠" + "═"*78 + "╣")
            print("║ 🔥 POSISI BERJALAN RIIL (LIVE REAL-TIME PNL USD & RUPIAH):                  ║")
            for p in pos_details:
                s_name = p['symbol'].split(':')[0]
                p_s = "+" if p['pnl'] >= 0 else "-"
                r_s = "+" if p['roe'] >= 0 else ""
                print(f"║   {p['bursa'][:24]:<24} {s_name:<7} {p['side']:<5} | Entri: ${p['entry']:<8.3f} ➔ Mark: ${p['mark']:<8.3f}   ║")
                print(f"║     Margin: ${p['margin']:<5.2f} (~Rp {p['margin_idr']:<7,.0f}) | PnL: {p_s}${abs(p['pnl']):<5.2f} ({p_s}Rp {abs(p['pnl_idr']):<7,.0f}) | ROE: {r_s}{p['roe']:<5.1f}% ║")
        print("╚" + "═"*78 + "╝\n")

        # 2. Scanning Koin Emas secara Asynchronous Cepat
        ex_for_candles = None
        for w in active_workers:
            if w.is_ready and w.exchange:
                ex_for_candles = w.exchange
                break
        if not ex_for_candles:
            return

        eligible_workers = [w for w in active_workers if max(len(worker_live_syms.get(w, set())), len(w.active_positions)) < MAX_POSITIONS_PER_EXCHANGE]
        if not eligible_workers:
            self.last_scan_info = f"Kenyang! Total {total_active} Posisi Sedang Mengunyah Cuan."
            return

        for symbol in SYMBOLS:
            coin_short = symbol.split('/')[0]
            eligible_workers = [w for w in active_workers if max(len(worker_live_syms.get(w, set())), len(w.active_positions)) < MAX_POSITIONS_PER_EXCHANGE]
            if not eligible_workers:
                break

            try:
                klines = await asyncio.to_thread(ex_for_candles.fetch_ohlcv, symbol, TIMEFRAME, limit=50)
                cur_p = float(klines[-1][4])
                sig = self.check_signals(symbol, klines)
                
                if sig:
                    for worker in eligible_workers:
                        now = time.time()
                        if worker.cooldowns.get(symbol, 0) > now:
                            continue
                        if symbol in worker_live_syms.get(worker, set()) or symbol in worker.active_positions:
                            continue

                        async with worker._order_lock:
                            live_check = await asyncio.to_thread(worker.get_active_positions)
                            if max(len(live_check), len(worker.active_positions)) >= MAX_POSITIONS_PER_EXCHANGE:
                                continue
                            logger.info(f"[{worker.tag}] 🚨 Sinyal {sig['side']} untuk {coin_short}! Mengeksekusi order...")
                            await asyncio.to_thread(worker.open_order, symbol, sig, cur_p)
            except Exception as e:
                logger.debug(f"Error scan {symbol}: {e}")

        standby_names = [w.tag for w in self.workers if w.is_standby]
        sb_str = f" | Standby: {', '.join(standby_names)}" if standby_names else ""
        self.last_scan_info = f"Trio-Titan Aktif: {len(active_workers)}/3 Bursa | Kas Total: ${total_balance:.2f} | PnL Live: {pnl_sign}${abs(unrealized_pnl):.2f}{sb_str}"

    async def broadcast_open_alert(self, tag: str, symbol: str, side: str, price: float, margin: float, tp: float, sl: float, engine: str):
        channel = bot_discord.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            color = 0x00ff88 if side == "LONG" else 0xff0044
            embed = discord.Embed(
                title=f"🐺 [{tag}] HAP! MANGSA BARU DITERKAM!",
                description=(
                    f"**Bursa:** `{tag}`\n"
                    f"**Target Koin:** `{symbol}`\n"
                    f"**Arah Posisi:** `{side} {LEVERAGE}x CROSS`\n"
                    f"**Sinyal Engine:** `{engine}`\n"
                    f"**Kompas BTC:** `{self.btc_trend}`"
                ),
                color=color,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Harga Entri", value=f"`${price:.4f}`", inline=True)
            embed.add_field(name="Margin Tempur", value=f"`${margin:.2f} USDT`", inline=True)
            embed.add_field(name="Notional (30x)", value=f"`${margin*LEVERAGE:.2f} USD`", inline=True)
            embed.add_field(name="Target TP (+8.2%)", value=f"🎯 `${tp:.4f}` (+229.6% ROE)", inline=True)
            embed.add_field(name="Batas SL (-2.3%)", value=f"🛡️ `${sl:.4f}` (-64.4% ROE)", inline=True)
            embed.add_field(name="Rasio Risiko", value="`1 : 3.0` (Penta-Titan Superpower)", inline=True)
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

# ==================== DISCORD INTERFACE ====================
class LiveDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 Refresh Live PnL", style=discord.ButtonStyle.danger, custom_id="btn_refresh_live")
    async def refresh_live_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not manager_ref:
            await interaction.response.send_message("Engine belum siap.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await manager_ref.update_btc_macro()
        except Exception:
            pass
        for w in manager_ref.workers:
            if not w.is_standby and w.is_ready:
                await asyncio.to_thread(w.refresh_balance)
                await asyncio.to_thread(w.get_active_positions)
        embed = build_live_dashboard(manager_ref)
        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📈 Statistik Win Rate", style=discord.ButtonStyle.success, custom_id="btn_wr_stats")
    async def wr_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not manager_ref:
            return
        total_tr = sum(w.total_trades for w in manager_ref.workers if not w.is_standby)
        total_w = sum(w.total_wins for w in manager_ref.workers if not w.is_standby)
        wr = (total_w / total_tr * 100) if total_tr > 0 else 0.0

        embed = discord.Embed(title="📊 STATISTIK WIN RATE BOT MARUK RAKUS (BITGET + MEXC)", color=0x9933ff, timestamp=datetime.utcnow())
        embed.add_field(name="Total Trade Gabungan", value=f"`{total_tr}`", inline=True)
        embed.add_field(name="Total Menang (TP)", value=f"`{total_w}`", inline=True)
        embed.add_field(name="Win Rate Gabungan", value=f"**`{wr:.1f}%`**", inline=True)
        for w in manager_ref.workers:
            if not w.is_standby:
                w_wr = (w.total_wins / w.total_trades * 100) if w.total_trades > 0 else 0
                embed.add_field(name=f"{w.tag}", value=f"Trades: `{w.total_trades}` | Win: `{w.total_wins}` ({w_wr:.1f}%)", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📰 Sentimen & Berita", style=discord.ButtonStyle.primary, custom_id="btn_news_indo")
    async def news_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not manager_ref:
            return
        fng, news_list = await asyncio.to_thread(manager_ref.fetch_fundamental_sentiment)
        embed = discord.Embed(
            title="📰 SENTIMEN PASAR & BERITA KRIPTO TERKINI (INDONESIA)",
            color=0x3399ff,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="Indeks Ketakutan & Keserakahan (Fear & Greed):",
            value=f"📊 **{fng.get('value', '50')}/100** — *{fng.get('classification', 'Netral')}*",
            inline=False
        )
        if news_list:
            text = "\n\n".join([f"• **{n['indo']}**\n  *(Asli: {n['asli']})*" for n in news_list])
        else:
            text = "*Sedang memuat berita terbaru...*"
        embed.add_field(name="⚡ Berita Kilat Terjemahan Bahasa Indonesia:", value=text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🛑 Exit All (Tutup Semua Akun)", style=discord.ButtonStyle.secondary, custom_id="btn_emergency_exit")
    async def emergency_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not manager_ref:
            return
        await interaction.response.defer(ephemeral=True)
        total_closed = 0
        for w in manager_ref.workers:
            if not w.is_standby and w.is_ready:
                c, _ = await asyncio.to_thread(w.emergency_close_all)
                total_closed += c
        await interaction.followup.send(f"✅ Selesai! Berhasil menutup total {total_closed} posisi di seluruh akun & bursa.", ephemeral=True)

def build_live_dashboard(mgr: MultiExchangeManager) -> discord.Embed:
    active_workers = [w for w in mgr.workers if not w.is_standby]
    total_bal = sum(w.balance for w in active_workers)
    unrealized_pnl, pos_details = mgr.get_live_unrealized_pnl()
    unrealized_pnl_idr = unrealized_pnl * KURS_IDR
    total_equity = total_bal + unrealized_pnl
    total_equity_idr = total_equity * KURS_IDR

    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
    pnl_sign = "+" if unrealized_pnl >= 0 else "-"
    total_active_pos = len(pos_details)

    # Roadmap Progress Bar menuju Target Rp 4,17 Miliar ($231,666 USD)
    target_4m_usd = 231666.0
    progress_4m = min(100.0, max(0.1, (total_equity / target_4m_usd) * 100.0))
    bar_fill = int(progress_4m // 10)
    progress_bar = "█" * bar_fill + "░" * (10 - bar_fill)

    # Brankas Milestone Terdekat
    brankas_milestones = [500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0, 50000.0, 100000.0]
    next_m = 500.0
    for m in brankas_milestones:
        if total_bal < m:
            next_m = m
            break

    embed = discord.Embed(
        title="👑⚡ BOT MARUK RAKUS • MULTI-AKUN (AKUN 1 + 2 + 3) ⚡👑",
        description=(
            f"**Kompas Tren Bitcoin:** `{mgr.btc_trend}`\n\n"
            f"💵 **Total Kas Gabungan:** **`${total_bal:,.2f} USDT`** *(~Rp {total_bal*KURS_IDR:,.0f})*\n"
            f"💎 **Total Ekuitas Bersih:** **`${total_equity:,.2f} USDT`** *(~Rp {total_equity_idr:,.0f})*\n"
            f"📈 **Live Floating PnL:** {pnl_emoji} **`{pnl_sign}${abs(unrealized_pnl):,.2f} USDT`** `({pnl_sign}Rp {abs(unrealized_pnl_idr):,.0f})`\n"
            f"🎯 **Total Posisi Aktif:** **`{total_active_pos} Posisi Berjalan`**\n"
            f"🚀 **Roadmap Target:** **`Rp 696 Jt (1 Thn) ➔ Rp 1,8 Miliar (2 Thn)`**\n"
            f"🏆 **Plafon Cap Margin:** **`${SUPERPOWER_CAP_MARGIN:.0f} USD`** *(Compounding {SUPERPOWER_COMP_PCT*100:.0f}% | Leverage {LEVERAGE}x CROSS)*\n"
            "════════════════════════════════════════════"
        ),
        color=0xFFD700 if unrealized_pnl >= 0 else 0xFF0044,
        timestamp=datetime.utcnow()
    )

    # 1. Rincian per Akun Keluarga
    for acc_id, profile in mgr.accounts_config.items():
        acc_name = profile.get("name", acc_id)
        acc_w_list = mgr.workers_by_account.get(acc_id, [])
        acc_bal = sum(w.balance for w in acc_w_list)
        acc_pos = sum(max(len(w.active_positions), len([p for p in pos_details if p.get('bursa') == w.tag])) for w in acc_w_list)
        
        ex_lines = []
        for w in acc_w_list:
            if not w.is_standby and w.is_ready:
                em = "💎" if "BITGET" in w.tag else ("🐉" if "MEXC" in w.tag else "🦁")
                ex_lines.append(f"{em} {w.name}: `${w.balance:.2f}` ({len(w.active_positions)}/2)")
        ex_str = " | ".join(ex_lines) if ex_lines else "*Standby*"

        embed.add_field(
            name=f"👤 {acc_name}",
            value=f"💰 Kas: **`${acc_bal:,.2f} USDT`** *(Rp {acc_bal*KURS_IDR:,.0f})*\n🎯 Posisi: **`{acc_pos}`**\n⚡ {ex_str}",
            inline=False
        )

    # 2. Posisi Berjalan Riil (VIP Card)
    embed.add_field(
        name="════════════════════════════════════════════",
        value=f"**🔥 POSISI AKTIF BERJALAN RIIL ({total_active_pos} POSISI)**",
        inline=False
    )
    if pos_details:
        for p in pos_details[:10]:
            sym_clean = p['symbol'].split(':')[0]
            p_sign = "+" if p['pnl'] >= 0 else "-"
            p_color = "🟢" if p['pnl'] >= 0 else "🔴"
            roe_sign = "+" if p['roe'] >= 0 else ""
            
            # Target TP & SL
            tp_px = p['entry'] * 1.082 if p['side'] == 'LONG' else p['entry'] * 0.918
            sl_px = p['entry'] * 0.977 if p['side'] == 'LONG' else p['entry'] * 1.023
            
            field_name = f"{p['bursa']} • {sym_clean} ({p['side']} {LEVERAGE}x CROSS)"
            field_val = (
                f"📊 **Harga:** Entri `${p['entry']:,.4f}` ➔ Mark `${p['mark']:,.4f}`\n"
                f"💵 **Margin:** `${p['margin']:,.2f} USDT` *(~Rp {p['margin_idr']:,.0f})* | Lot: `{p['contracts']}`\n"
                f"💰 **Floating PnL:** {p_color} **`{p_sign}${abs(p['pnl']):,.2f} USDT`** `({p_sign}Rp {abs(p['pnl_idr']):,.0f})`\n"
                f"⚡ **Return On Equity (ROE):** **`{roe_sign}{p['roe']:.1f}%`**\n"
                f"🎯 **Target TP:** `${tp_px:,.4f}` *(+229.6% ROE)* | 🛡️ **Batas SL:** `${sl_px:,.4f}` *(-64.4% ROE)*"
            )
            embed.add_field(name=field_name, value=field_val, inline=False)
        if len(pos_details) > 10:
            embed.add_field(name="Dan posisi lainnya...", value=f"...+{len(pos_details)-10} posisi aktif lainnya berjalan rapi.", inline=False)
    else:
        embed.add_field(
            name="Status Keranjang Posisi",
            value="*Belum ada posisi terbuka. Bot sedang mengintai sinyal emas Donchian 36H.*",
            inline=False
        )

    embed.set_footer(text="👑 Bot Maruk Rakus Multi-Akun (Akun 1 + 2 + 3) • Target Backtested Rp 696 Jt - Rp 1,8 Miliar")
    return embed

MultiExchangeManager.build_live_dashboard_embed = build_live_dashboard

# ==================== DISCORD COMMANDS ====================
@bot_discord.command(name="status")
async def cmd_status(ctx):
    if not manager_ref:
        await ctx.send("Engine belum siap.")
        return
    for w in manager_ref.workers:
        if not w.is_standby and w.is_ready:
            await asyncio.to_thread(w.refresh_balance)
    embed = build_live_dashboard(manager_ref)
    view = LiveDashboardView()
    await ctx.send(embed=embed, view=view)

@bot_discord.command(name="news")
async def cmd_news(ctx):
    if not manager_ref:
        return
    fng, news_list = await asyncio.to_thread(manager_ref.fetch_fundamental_sentiment)
    embed = discord.Embed(
        title="📰 SENTIMEN PASAR & BERITA KRIPTO TERKINI (INDONESIA)",
        color=0x3399ff,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="Indeks Ketakutan & Keserakahan (Fear & Greed):",
        value=f"📊 **{fng.get('value', '50')}/100** — *{fng.get('classification', 'Netral')}*",
        inline=False
    )
    if news_list:
        text = "\n\n".join([f"• **{n['indo']}**\n  *(Asli: {n['asli']})*" for n in news_list])
    else:
        text = "*Sedang memuat berita terbaru...*"
    embed.add_field(name="⚡ Berita Kilat Terjemahan Bahasa Indonesia:", value=text, inline=False)
    await ctx.send(embed=embed)

@bot_discord.command(name="closeall")
async def cmd_closeall(ctx):
    if not manager_ref:
        return
    msg = await ctx.send("🛑 Menutup semua posisi di seluruh akun keluarga...")
    total_closed = 0
    for w in manager_ref.workers:
        if not w.is_standby and w.is_ready:
            c, _ = await asyncio.to_thread(w.emergency_close_all)
            total_closed += c
    await msg.edit(content=f"✅ Selesai! Berhasil menutup total {total_closed} posisi di seluruh akun keluarga & bursa.")

@bot_discord.command(name="wr")
async def cmd_wr(ctx):
    if not manager_ref:
        return
    total_tr = sum(w.total_trades for w in manager_ref.workers if not w.is_standby)
    total_w = sum(w.total_wins for w in manager_ref.workers if not w.is_standby)
    wr = (total_w / total_tr * 100) if total_tr > 0 else 0.0

    embed = discord.Embed(title="📊 STATISTIK WIN RATE BOT MARUK RAKUS (BITGET + MEXC + BINGX)", color=0x9933ff, timestamp=datetime.utcnow())
    embed.add_field(name="Total Trade Gabungan", value=f"`{total_tr}`", inline=True)
    embed.add_field(name="Total Menang (TP)", value=f"`{total_w}`", inline=True)
    embed.add_field(name="Win Rate Gabungan", value=f"**`{wr:.1f}%`**", inline=True)
    for w in manager_ref.workers:
        if not w.is_standby:
            w_wr = (w.total_wins / w.total_trades * 100) if w.total_trades > 0 else 0
            embed.add_field(name=f"{w.tag}", value=f"Trades: `{w.total_trades}` | Win: `{w.total_wins}` ({w_wr:.1f}%)", inline=False)
    await ctx.send(embed=embed)

@bot_discord.event
async def on_ready():
    logger.info(f"👑 [{BOT_NAME} DISCORD READY] Bot Maruk Rakus Siap Berburu!")
    bot_discord.add_view(LiveDashboardView())
    channel = bot_discord.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="👑🔥 BOT MARUK RAKUS TRIO-TITAN (BITGET + MEXC + BINGX) RESMI BEROPERASI!",
            description=(
                "**Formasi Juara Target Rp 4,17 - 4,78 Miliar (Trio-Titan):**\n\n"
                "• **Bursa 1:** 💎 **Bitget** (Mesin Eksekusi Altcoin Teruji | Taker Fee 0.040%)\n"
                "• **Bursa 2:** 🐉 **MEXC** (Bursa Taker Termurah di Dunia: 0.020%)\n"
                "• **Bursa 3:** 🦁 **BingX** (Bursa Eksekusi Stabil & Cepat | Taker Fee 0.045%)\n\n"
                f"• **Daya Gedor Compounding:** **{SUPERPOWER_COMP_PCT*100}%** (Cap Margin **${SUPERPOWER_CAP_MARGIN:.0f} USD**)\n"
                "• **Leverage:** **28x CROSS** (Risk-to-Reward 1:3 | TP +229.6%, SL -64.4%)\n"
                "• **Kapasitas Serentak:** 6 Posisi Bersamaan (2 Posisi per Bursa)\n"
                "• **Fitur Proteksi:** Tangga 4-Tahap Anti-Bleed, Cooldown 2-16 Jam, Sistem Brankas Dingin\n\n"
                "Ketik `!status` atau klik tombol di bawah untuk melihat Live PnL & Saldo Kas 3 Bursa!"
            ),
            color=0xffd700,
            timestamp=datetime.utcnow()
        )
        view = LiveDashboardView()
        await channel.send(embed=embed, view=view)

# ==================== MAIN LOOP ====================
async def multi_trading_loop(mgr: MultiExchangeManager):
    await mgr.init_all()
    await asyncio.sleep(3)
    active_count = len([w for w in mgr.workers if not w.is_standby])
    logger.info("==================================================================")
    logger.info(f"  👑 {BOT_NAME} AKTIF!")
    logger.info(f"  {active_count}/3 Bursa Juara (Bitget + MEXC + BingX) | Cap Margin ${SUPERPOWER_CAP_MARGIN:.0f} | Compounding {SUPERPOWER_COMP_PCT*100}%")
    logger.info(f"  Interval Cepat: {SCAN_INTERVAL_SECONDS}s Tanpa Jeda | Anti-Blokir DoH Cloudflare")
    logger.info("==================================================================")
    while True:
        try:
            await mgr.scan_and_trade()
            await mgr.sync_discord_dashboard()
        except Exception as e:
            logger.error(f"Error loop scan bot maruk rakus: {e}")
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)

async def start_discord_resilient():
    while True:
        try:
            logger.info("📡 Menghubungkan bot Discord...")
            await bot_discord.start(DISCORD_TOKEN)
        except Exception as e:
            logger.error(f"⚠️ Discord disconnect / error: {e}. Menghubungkan ulang dalam 10 detik...")
            await asyncio.sleep(10)

async def main():
    global manager_ref
    mgr = MultiExchangeManager()
    manager_ref = mgr
    await asyncio.gather(
        start_discord_resilient(),
        multi_trading_loop(mgr),
        return_exceptions=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot maruk diistirahatkan oleh bos.")
