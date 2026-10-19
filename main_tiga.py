import os
import sys
import io
import time
import math
import asyncio
import logging
import socket
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import json
import requests
import ccxt

# UTF-8 Encoding Stream Protection (Anti-Crash Terminal Emojis di Termux)
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    try: sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception: pass

# ==================== CLOUDFLARE DoH DNS FALLBACK ====================
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}

def doh_resolve(host: str) -> List[str]:
    if host in _dns_cache:
        return _dns_cache[host]
    for url in ['https://dns.google/resolve', 'https://1.1.1.1/dns-query']:
        try:
            r = requests.get(
                url,
                params={'name': host, 'type': 'A'},
                headers={'accept': 'application/dns-json'},
                timeout=2.0
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
    if any(t in host.lower() for t in targets):
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

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BotMarukTermux")

# ==================== PARAMETER STRATEGI (DUAL-ENGINE ASYMMETRIC APEX) ====================
TIMEFRAME = "1h"
LEVERAGE = 20
TP_PCT = 0.082          # Default fallback TP
SL_PCT = 0.023          # Default fallback SL
MAX_POSITIONS_PER_EXCHANGE = 1  # 1 Slot per bursa: memangkas fee churn hingga -60% & cadangan margin tebal
SCAN_INTERVAL_SECONDS = 12
KURS_IDR = 17000.0

# 6 KOIN EMAS TERBAIK
SYMBOLS = [
    "XRP/USDT:USDT",
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT"
]

def calc_ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    k = 2.0 / (period + 1.0)
    ema = sum(values[:period]) / float(period)
    for price in values[period:]:
        ema = (price * k) + (ema * (1.0 - k))
    return ema

def calc_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(len(closes) - period, len(closes)):
        chg = closes[i] - closes[i - 1]
        gains.append(max(0.0, chg))
        losses.append(max(0.0, -chg))
    avg_gain = sum(gains) / float(period)
    avg_loss = sum(losses) / float(period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

# ==================== WORKER PER BURSA ====================
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
        self.last_balance: float = 0.0
        self.peak_balance: float = 0.0
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.total_trades: int = 0
        self.total_wins: int = 0
        self.total_losses: int = 0
        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.cooldowns: Dict[str, float] = {}
        self.is_ready: bool = False

    def init_sync(self):
        if self.is_standby or not self.exchange:
            self.is_ready = False
            return
        try:
            self.refresh_balance()
            self.last_balance = self.balance
            self.set_exchange_leverage()
            self.is_ready = True
            logger.info(f"[{self.tag}] ✅ Terhubung | Saldo: ${self.balance:.2f} USDT (~Rp {self.balance*KURS_IDR:,.0f})")
        except Exception as e:
            logger.warning(f"[{self.tag}] Gagal sync awal: {e}")
            self.is_ready = False

    def set_exchange_leverage(self):
        """Kunci leverage 20x secara native di API bursa Bitget & BingX (Fix audit Astra)"""
        if self.is_standby or not self.exchange: return
        for sym_raw in ["BTC", "ETH", "XRP", "ADA", "AVAX", "LINK"]:
            try:
                if self.name == "Bitget":
                    self.exchange.privateMixPostV2MixAccountSetLeverage({
                        'symbol': f"{sym_raw}USDT", 'productType': 'USDT-FUTURES',
                        'marginCoin': 'USDT', 'leverage': str(LEVERAGE)
                    })
                elif self.name == "BingX":
                    self.exchange.swapV2PrivatePostTradeSetLeverage({
                        'symbol': f"{sym_raw}-USDT", 'leverage': LEVERAGE, 'side': 'BOTH'
                    })
            except Exception:
                pass

    def refresh_balance(self):
        if self.is_standby or not self.exchange: return
        try:
            if self.name == "BingX":
                res = self.exchange.swapV2PrivateGetUserBalance()
                bal_data = res.get('data', {}).get('balance', {})
                self.balance = float(bal_data.get('equity') or bal_data.get('balance') or 0.0)
            elif self.name == "Bitget":
                res = self.exchange.privateMixGetV2MixAccountAccounts({'productType': 'USDT-FUTURES'})
                b_list = res.get('data', [])
                if b_list:
                    self.balance = float(b_list[0].get('usdtEquity') or b_list[0].get('accountEquity') or 0.0)
            elif self.name == "MEXC":
                res = self.exchange.contractPrivateGetAccountAssets()
                b_list = res.get('data', [])
                for b in b_list:
                    if b.get('currency') == 'USDT':
                        self.balance = float(b.get('equity') or b.get('cashBalance') or 0.0)
                        break
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
        except Exception:
            pass

    def get_active_positions(self) -> Optional[List[Dict[str, Any]]]:
        """Ambil posisi aktif bursa. Kembalikan None jika API gagal agar tidak picu order liar (Fix audit Astra)"""
        if self.is_standby or not self.exchange: return []
        pos_list = []
        try:
            if self.name == "BingX":
                res = self.exchange.swapV2PrivateGetUserPositions().get('data', [])
                for p in res:
                    amt = abs(float(p.get('positionAmt') or 0.0))
                    if amt > 0:
                        sym = str(p.get('symbol', '')).replace('-', '/')
                        pos_list.append({
                            'symbol': sym,
                            'side': str(p.get('positionSide', 'LONG')).upper(),
                            'entry': float(p.get('avgPrice') or 0.0),
                            'mark': float(p.get('markPrice') or p.get('avgPrice') or 0.0),
                            'margin': float(p.get('initialMargin') or p.get('margin') or 1.0),
                            'leverage': int(float(p.get('leverage') or LEVERAGE)),
                            'pnl': float(p.get('unrealizedProfit') or 0.0)
                        })
            elif self.name == "Bitget":
                res = self.exchange.privateMixGetV2MixPositionAllPosition({'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}).get('data', [])
                for p in res:
                    sz = abs(float(p.get('total') or 0.0))
                    if sz > 0:
                        raw = str(p.get('symbol', '')).replace('USDT', '')
                        pos_list.append({
                            'symbol': f"{raw}/USDT",
                            'side': str(p.get('holdSide', 'LONG')).upper(),
                            'entry': float(p.get('openPriceAvg') or 0.0),
                            'mark': float(p.get('markPrice') or p.get('openPriceAvg') or 0.0),
                            'margin': float(p.get('marginSize') or 1.0),
                            'leverage': int(float(p.get('leverage') or LEVERAGE)),
                            'pnl': float(p.get('unrealizedPL') or 0.0)
                        })
            elif self.name == "MEXC":
                res = self.exchange.contractPrivateGetPositionOpenPositions().get('data', [])
                for p in res:
                    vol = abs(float(p.get('holdVol') or 0.0))
                    if vol > 0:
                        sym = str(p.get('symbol', '')).replace('_', '/')
                        m_val = float(p.get('im') or p.get('oim') or 1.0)
                        pos_list.append({
                            'symbol': sym,
                            'side': "LONG" if int(p.get('positionType', 1)) == 1 else "SHORT",
                            'entry': float(p.get('openAvgPrice') or p.get('holdAvgPrice') or 0.0),
                            'mark': float(p.get('openAvgPrice') or 0.0),
                            'margin': m_val,
                            'leverage': int(float(p.get('leverage') or LEVERAGE)),
                            'pnl': float(p.get('unRealizedPnl') or 0.0)
                        })
            return pos_list
        except Exception as e:
            logger.error(f"[{self.tag}] ⚠️ Gagal sinkronisasi posisi bursa: {e}")
            return None

    def check_position_closure(self, current_positions: List[Dict[str, Any]]):
        """Deteksi penutupan posisi di bursa untuk perbarui win/loss streak dan cooldown (Fix audit Astra)"""
        if not current_positions and not self.active_positions: return
        current_syms = set(p['symbol'].split('/')[0].split(':')[0].upper() for p in current_positions)
        closed_syms = []
        for tracked_sym in list(self.active_positions.keys()):
            coin = tracked_sym.split('/')[0].split(':')[0].upper()
            if coin not in current_syms:
                closed_syms.append(tracked_sym)
                if self.balance >= self.last_balance:
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    self.total_wins += 1
                    logger.info(f"[{self.tag}] 🏆 Posisi {coin} TERTUTUP PROFIT! Win streak: {self.consecutive_wins}")
                else:
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    self.total_losses += 1
                    self.cooldowns[coin] = time.time() + (2 * 3600)
                    logger.warning(f"[{self.tag}] 🛑 Posisi {coin} TERTUTUP LOSS. Loss streak: {self.consecutive_losses} | Cooldown 2 jam aktif.")
        for s in closed_syms:
            del self.active_positions[s]
        self.last_balance = self.balance

    def is_in_drawdown_halt(self) -> bool:
        """Circuit breaker: Hard halt jika drawdown mencapai 20% demi keselamatan modal (Fix audit Astra)"""
        if self.peak_balance > 0 and self.balance > 0:
            cur_dd = (self.peak_balance - self.balance) / self.peak_balance
            if cur_dd >= 0.20:
                logger.warning(f"[{self.tag}] 🛑 [CIRCUIT BREAKER] Drawdown akun {cur_dd*100:.1f}% >= 20%! Entri ditahan demi keselamatan modal.")
                return True
        return False

    def emergency_close(self, symbol: str, side: str, qty: float):
        """Tutup pasar darurat jika Stop Loss gagal dipasang di bursa (Fix audit Astra)"""
        coin = symbol.split('/')[0]
        try:
            if self.name == "Bitget":
                self.exchange.privateMixPostV2MixOrderPlaceOrder({
                    'productType': 'USDT-FUTURES', 'symbol': f"{coin}USDT",
                    'side': 'sell' if side == 'LONG' else 'buy',
                    'orderType': 'market', 'size': str(qty), 'tradeSide': 'close',
                    'marginMode': 'crossed', 'marginCoin': 'USDT'
                })
            elif self.name == "MEXC":
                mx_vol = max(1, int(round(qty)))
                self.exchange.contractPrivatePostOrderSubmit({
                    'symbol': f"{coin}_USDT",
                    'side': 4 if side == 'LONG' else 2,
                    'type': 5, 'vol': mx_vol, 'openType': 2
                })
            elif self.name == "BingX":
                self.exchange.swapV2PrivatePostTradeOrder({
                    'symbol': f"{coin}-USDT",
                    'side': 'SELL' if side == 'LONG' else 'BUY',
                    'positionSide': side, 'type': 'MARKET', 'quantity': float(qty)
                })
            logger.info(f"[{self.tag}] 🛑 Emergency close {symbol} {side} berhasil dieksekusi.")
        except Exception as e_ec:
            logger.error(f"[{self.tag}] 🚨 Gagal emergency close {symbol}: {e_ec}")

    def calc_order_sizing(self, cur_price: float, sl_pct: float, risk_pct: float = 0.02) -> Tuple[float, float]:
        """
        Fixed Risk-Based Position Sizing (Fix audit Astra):
        Maksimal kerugian dikunci pada 2.0% dari saldo saat Stop Loss tersambar!
        Rumus Quant: Target Notional = (Saldo * Risk_Pct) / SL_Pct
        """
        b = self.balance
        # 1. Hot-hand / loss brake adjustment
        adjusted_risk = risk_pct
        if self.consecutive_losses >= 2:
            adjusted_risk = risk_pct * 0.50  # Pangkas risiko separuh jika 2 loss beruntun
        elif self.consecutive_wins >= 2:
            adjusted_risk = min(0.03, risk_pct * 1.25)

        max_risk_usd = b * adjusted_risk
        target_notional = max_risk_usd / max(0.01, sl_pct)

        # Min notional bursa $5.0, max notional b * LEVERAGE * 0.35 (jangan over-leverage)
        notional = max(5.0, min(target_notional, b * LEVERAGE * 0.35))
        margin = round(notional / LEVERAGE, 2)
        raw_qty = notional / cur_price
        return margin, raw_qty

    def open_order(self, symbol: str, side: str, cur_price: float, mom12: float, ker_val: float, atr24: float, tp_pct: float = 0.082, sl_pct: float = 0.023, strategy_label: str = "NORMAL"):
        if self.is_standby or not self.exchange: return
        try:
            if self.is_in_drawdown_halt():
                return

            margin, raw_qty = self.calc_order_sizing(cur_price, sl_pct, risk_pct=0.02)
            if self.balance < margin:
                return

            notional = margin * LEVERAGE
            coin = symbol.split('/')[0]

            # Presisi Kuantitas Koin Nyata (Fix audit Astra)
            if coin == "BTC":
                qty = max(0.0001, round(raw_qty, 4))
            elif coin == "ETH":
                qty = max(0.01, round(raw_qty, 2))
            elif coin in ["AVAX", "LINK"]:
                qty = max(0.1, round(raw_qty, 1))
            else: # XRP, ADA
                qty = max(1, int(raw_qty))

            tp_price = round(cur_price * (1.0 + tp_pct), 4) if side == "LONG" else round(cur_price * (1.0 - tp_pct), 4)
            sl_price = round(cur_price * (1.0 - sl_pct), 4) if side == "LONG" else round(cur_price * (1.0 + sl_pct), 4)

            logger.info(f"[{self.tag}] 🎯 TERKAM [{strategy_label}] {side} {coin} | Margin: ${margin:.2f} (Qty: {qty}) | Px: ${cur_price:.4f} | TP: ${tp_price} | SL: ${sl_price}")

            # 1. Eksekusi Entry Market Order
            if self.name == "Bitget":
                sym_bg = f"{coin}USDT"
                self.exchange.privateMixPostV2MixOrderPlaceOrder({
                    'productType': 'USDT-FUTURES', 'symbol': sym_bg,
                    'side': 'buy' if side == 'LONG' else 'sell',
                    'orderType': 'market', 'size': str(qty), 'tradeSide': 'open',
                    'marginMode': 'crossed', 'marginCoin': 'USDT'
                })
            elif self.name == "MEXC":
                sym_mx = f"{coin}_USDT"
                if coin == "BTC": mx_vol = max(1, int(round(raw_qty / 0.0001)))
                elif coin == "ETH": mx_vol = max(1, int(round(raw_qty / 0.01)))
                elif coin in ["AVAX", "LINK"]: mx_vol = max(1, int(round(raw_qty / 0.1)))
                else: mx_vol = max(1, int(round(raw_qty)))

                self.exchange.contractPrivatePostOrderSubmit({
                    'symbol': sym_mx, 'side': 1 if side == 'LONG' else 3,
                    'type': 5, 'vol': mx_vol, 'openType': 2, 'leverage': LEVERAGE
                })
            elif self.name == "BingX":
                sym_bx = f"{coin}-USDT"
                self.exchange.swapV2PrivatePostTradeOrder({
                    'symbol': sym_bx, 'side': 'BUY' if side == 'LONG' else 'SELL',
                    'positionSide': side, 'type': 'MARKET', 'quantity': float(qty)
                })

            # 2. Pasang STOP LOSS Native dengan Verifikasi & Retry (Fix audit Astra)
            sl_verified = False
            for attempt in range(2):
                try:
                    time.sleep(0.3)
                    if self.name == "Bitget":
                        self.exchange.privateMixPostV2MixOrderPlacePlanOrder({
                            'productType': 'USDT-FUTURES', 'symbol': sym_bg,
                            'planType': 'normal_plan', 'triggerPrice': str(sl_price), 'triggerType': 'mark_price',
                            'executePrice': '0', 'orderType': 'market', 'size': str(qty),
                            'side': 'sell' if side == 'LONG' else 'buy', 'tradeSide': 'close',
                            'marginMode': 'crossed', 'marginCoin': 'USDT'
                        })
                    elif self.name == "MEXC":
                        self.exchange.contractPrivatePostPlanorderPlace({
                            'symbol': sym_mx, 'side': 4 if side == 'LONG' else 2, 'openType': 2,
                            'triggerPrice': sl_price, 'triggerType': 2 if side == 'LONG' else 1, 'trend': 1,
                            'orderType': 5, 'executeCycle': 1, 'vol': mx_vol
                        })
                    elif self.name == "BingX":
                        self.exchange.swapV2PrivatePostTradeOrder({
                            'symbol': sym_bx, 'side': 'SELL' if side == 'LONG' else 'BUY', 'positionSide': side,
                            'type': 'STOP_MARKET', 'stopPrice': sl_price, 'quantity': float(qty)
                        })
                    sl_verified = True
                    break
                except Exception as e_sl:
                    logger.warning(f"[{self.tag}] Percobaan {attempt+1} pasang SL gagal: {e_sl}")
                    time.sleep(0.5)

            # Fail-Safe Emergency: Jika SL gagal terpasang, langsung tutup posisi demi keselamatan modal!
            if not sl_verified:
                logger.critical(f"[{self.tag}] 🚨 STOP LOSS GAGAL TERPASANG DI BURSA! Menutup posisi darurat demi keselamatan modal...")
                self.emergency_close(symbol, side, qty)
                return

            # 3. Pasang TAKE PROFIT Native
            try:
                time.sleep(0.2)
                if self.name == "Bitget":
                    self.exchange.privateMixPostV2MixOrderPlacePlanOrder({
                        'productType': 'USDT-FUTURES', 'symbol': sym_bg,
                        'planType': 'normal_plan', 'triggerPrice': str(tp_price), 'triggerType': 'mark_price',
                        'executePrice': '0', 'orderType': 'market', 'size': str(qty),
                        'side': 'sell' if side == 'LONG' else 'buy', 'tradeSide': 'close',
                        'marginMode': 'crossed', 'marginCoin': 'USDT'
                    })
                elif self.name == "MEXC":
                    self.exchange.contractPrivatePostPlanorderPlace({
                        'symbol': sym_mx, 'side': 4 if side == 'LONG' else 2, 'openType': 2,
                        'triggerPrice': tp_price, 'triggerType': 1 if side == 'LONG' else 2, 'trend': 1,
                        'orderType': 5, 'executeCycle': 1, 'vol': mx_vol
                    })
                elif self.name == "BingX":
                    self.exchange.swapV2PrivatePostTradeOrder({
                        'symbol': sym_bx, 'side': 'SELL' if side == 'LONG' else 'BUY', 'positionSide': side,
                        'type': 'TAKE_PROFIT_MARKET', 'stopPrice': tp_price, 'quantity': float(qty)
                    })
            except Exception as e_tp:
                logger.warning(f"[{self.tag}] Info bracket order TP: {e_tp}")

            self.active_positions[symbol] = {
                'side': side, 'margin': margin, 'entry': cur_price,
                'tp': tp_price, 'sl': sl_price, 'open_time': time.time()
            }
            self.total_trades += 1
        except Exception as e:
            logger.error(f"[{self.tag}] Gagal open order {symbol}: {e}")

# ==================== MASTER MULTI-ACCOUNT MANAGER ====================
class MultiAccountMaster:
    def __init__(self):
        cfg_candidates = [
            os.path.join(os.path.dirname(__file__), "accounts_config.json"),
            os.path.join(os.path.dirname(__file__), "..", "maruk-dshboard-repo", "accounts_config.json"),
            "accounts_config.json"
        ]
        accounts_data = {}
        for c in cfg_candidates:
            if os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        accounts_data = json.load(f)
                    if accounts_data:
                        logger.info(f"✅ Berhasil memuat konfigurasi multi-akun dari: {c}")
                        break
                except Exception as e:
                    logger.error(f"Gagal membaca {c}: {e}")

        self.accounts_config = accounts_data
        self.workers: List[ExchangeWorker] = []
        self.workers_by_account: Dict[str, List[ExchangeWorker]] = {}

        fee_map = {"Bitget": 0.00060, "MEXC": 0.00080, "BingX": 0.00050, "Bybit": 0.00055, "Gate.io": 0.00050}

        for acc_id, profile in self.accounts_config.items():
            acc_name = profile.get("name", acc_id)
            self.workers_by_account[acc_id] = []

            for ex_name in ["Bitget", "MEXC", "BingX", "Bybit", "Gate.io"]:
                creds = profile.get(ex_name, {})
                api_k = creds.get("apiKey", "").strip()
                sec_k = creds.get("secret", "").strip()
                pass_k = creds.get("password", "").strip()
                tag = f"[{acc_name}] {ex_name}"
                fee = fee_map.get(ex_name, 0.0004)

                if api_k and sec_k:
                    ex_obj = None
                    try:
                        if ex_name == "Bitget":
                            ex_obj = ccxt.bitget({'apiKey': api_k, 'secret': sec_k, 'password': pass_k, 'timeout': 5000, 'options': {'defaultType': 'swap'}})
                        elif ex_name == "MEXC":
                            ex_obj = ccxt.mexc({'apiKey': api_k, 'secret': sec_k, 'timeout': 5000, 'options': {'defaultType': 'swap'}})
                        elif ex_name == "BingX":
                            ex_obj = ccxt.bingx({'apiKey': api_k, 'secret': sec_k, 'timeout': 5000, 'options': {'defaultType': 'swap'}})
                    except Exception as e:
                        logger.error(f"Gagal init {tag}: {e}")

                    worker = ExchangeWorker(name=ex_name, tag=tag, exchange_obj=ex_obj, fee_rate=fee, is_standby=(ex_obj is None), acc_id=acc_id, acc_label=acc_name)
                else:
                    worker = ExchangeWorker(name=ex_name, tag=tag, exchange_obj=None, fee_rate=fee, is_standby=True, acc_id=acc_id, acc_label=acc_name)

                self.workers.append(worker)
                self.workers_by_account[acc_id].append(worker)

        self.btc_price = 0.0
        self.btc_ema50 = 0.0
        self.btc_trend = "NETRAL"
        self.flash_dump_until = 0.0
        self.last_state_push = 0.0

    async def init_all(self):
        logger.info(f"⚡ Menginisialisasi {len(self.workers)} Unit Worker di 3 Akun...")
        tasks = [asyncio.to_thread(w.init_sync) for w in self.workers]
        await asyncio.gather(*tasks)

    async def update_btc_macro(self):
        worker = next((w for w in self.workers if w.is_ready and w.exchange and w.name == "Bitget"), None)
        if not worker:
            worker = next((w for w in self.workers if w.is_ready and w.exchange), None)
        if not worker or not worker.exchange: return

        try:
            kl = await asyncio.to_thread(worker.exchange.fetch_ohlcv, "BTC/USDT:USDT", TIMEFRAME, limit=100)
            if len(kl) >= 50:
                closes = [float(k[4]) for k in kl]
                opens = [float(k[1]) for k in kl]
                self.btc_price = closes[-1]
                self.btc_ema50 = calc_ema(closes, 50)
                self.btc_trend = "BULLISH" if self.btc_price > self.btc_ema50 else "BEARISH"

                # Flash Dump Shield (-2.5% in 1H candle)
                ret_1h = (closes[-1] - opens[-1]) / opens[-1] if opens[-1] > 0 else 0.0
                now = time.time()
                if ret_1h <= -0.025:
                    if self.flash_dump_until < now:
                        logger.warning(f"🚨🛡️ [FLASH DUMP SHIELD] BTC anjlok {ret_1h*100:.2f}% dalam 1 jam! Tahan entri 12 jam.")
                    self.flash_dump_until = max(self.flash_dump_until, now + (12 * 3600))
        except Exception:
            pass

    def check_signals(self, symbol: str, klines: List[List[float]]) -> Optional[Dict[str, Any]]:
        if len(klines) < 40: return None
        now = time.time()
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        cur_p = closes[-1]

        donch_h32 = max(highs[-33:-1])
        donch_l32 = min(lows[-33:-1])

        p12 = closes[-13]
        mom12 = (cur_p - p12) / p12
        p4 = closes[-5]
        mom4 = (cur_p - p4) / p4

        # Kaufman Efficiency Ratio (KER 16H >= 0.20)
        net_16 = abs(closes[-1] - closes[-17])
        path_16 = sum(abs(closes[i] - closes[i-1]) for i in range(len(closes)-16, len(closes)))
        ker16 = (net_16 / path_16) if path_16 > 0 else 0.0

        # ATR 24
        atrs = []
        for i in range(len(klines)-24, len(klines)):
            h, l, cp = float(klines[i][2]), float(klines[i][3]), float(klines[i-1][4])
            atrs.append(max(h - l, abs(h - cp), abs(l - cp)))
        atr24 = sum(atrs) / len(atrs) if atrs else 0.0

        coin = symbol.split('/')[0].split(':')[0].upper()
        if coin in ["BTC", "ETH"]:
            # DUAL-ENGINE 1: Institutional Dip-Buyer Sniper (BTC & ETH)
            rsi14 = calc_rsi(closes, 14)
            if self.btc_trend == "BULLISH":
                if self.flash_dump_until > now: return None
                if rsi14 <= 30.0:
                    return {"side": "LONG", "mom": mom12, "ker": ker16, "atr24": atr24, "tp_pct": 0.055, "sl_pct": 0.020, "strategy": "BTC_DIP_SNIPER"}
            elif self.btc_trend == "BEARISH":
                if rsi14 >= 70.0:
                    return {"side": "SHORT", "mom": mom12, "ker": ker16, "atr24": atr24, "tp_pct": 0.055, "sl_pct": 0.020, "strategy": "BTC_DIP_SNIPER"}
            return None
        else:
            # DUAL-ENGINE 2: Momentum Trend-Surfer (XRP, ADA, AVAX, LINK)
            if self.btc_trend == "BULLISH":
                if self.flash_dump_until > now: return None
                if cur_p > donch_h32 and mom12 >= 0.028 and mom4 >= 0.005 and ker16 >= 0.20:
                    return {"side": "LONG", "mom": mom12, "ker": ker16, "atr24": atr24, "tp_pct": 0.140, "sl_pct": 0.028, "strategy": "TREND_SURFER"}
            elif self.btc_trend == "BEARISH":
                if cur_p < donch_l32 and mom12 <= -0.028 and mom4 <= -0.005 and ker16 >= 0.20:
                    return {"side": "SHORT", "mom": mom12, "ker": ker16, "atr24": atr24, "tp_pct": 0.140, "sl_pct": 0.028, "strategy": "TREND_SURFER"}
            return None

    def export_and_sync_web(self):
        """Export live state ke live_bot_state.json untuk dashboard Streamlit"""
        now = time.time()
        full_state = {}
        for acc_id, profile in self.accounts_config.items():
            tot_bal = 0.0
            tot_pnl = 0.0
            pos_list = []
            ex_details = {}

            workers = self.workers_by_account.get(acc_id, [])
            for w in workers:
                if w.is_standby or not w.is_ready:
                    ex_details[w.name] = {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'}
                    continue
                tot_bal += w.balance
                ex_details[w.name] = {'total': round(w.balance, 2), 'free': round(w.balance, 2), 'status': 'ONLINE'}
                for p in w.get_active_positions():
                    pos_list.append({
                        'exchange': w.name, 'symbol': p['symbol'], 'side': p['side'],
                        'entry': p['entry'], 'mark': p['mark'], 'margin': p['margin'],
                        'notional': p['margin'] * p['leverage'], 'pnl': p['pnl'],
                        'roe': (p['pnl'] / p['margin'] * 100.0) if p['margin'] > 0 else 0.0,
                        'leverage': p['leverage']
                    })
                    tot_pnl += p['pnl']

            full_state[acc_id] = {
                'total_bal': round(tot_bal, 2),
                'total_pnl': round(tot_pnl, 2),
                'pos_list': pos_list,
                'ex_details': ex_details,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        out_path = os.path.join(os.path.dirname(__file__), "live_bot_state.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(full_state, f, indent=2)
        except Exception:
            pass

        # Push ke GitHub setiap 60 detik jika ada perubahan
        if now - self.last_state_push >= 60:
            self.last_state_push = now
            repo_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                subprocess.run(["git", "add", "live_bot_state.json"], cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                subprocess.run(["git", "commit", "-m", "chore: auto sync termux state"], cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
            except Exception:
                pass

    async def run_loop(self):
        await self.init_all()
        print("\n" + "="*70)
        print("🚀 BOT MARUK TERMUX APEX MULTI-AKUN (NO-DISCORD, WEB MONITOR ACTIVE)")
        print("="*70 + "\n")

        while True:
            try:
                await self.update_btc_macro()
                active_workers = [w for w in self.workers if not w.is_standby and w.is_ready]

                # 1. Refresh balances & check positions
                for w in active_workers:
                    await asyncio.to_thread(w.refresh_balance)

                tot_bal = sum(w.balance for w in active_workers)
                all_active = []
                for w in active_workers:
                    w_pos = await asyncio.to_thread(w.get_active_positions)
                    if w_pos is not None:
                        w.check_position_closure(w_pos)
                        for p in w_pos:
                            all_active.append((w, p))

                tot_pnl = sum(p['pnl'] for _, p in all_active)
                trend_emoji = "🟢 BULLISH" if self.btc_trend == "BULLISH" else "🔴 BEARISH"

                # Terminal Dashboard
                t_now = datetime.now().strftime("%H:%M:%S")
                print(f"[{t_now}] BTC: ${self.btc_price:,.1f} ({trend_emoji}) | Kas: ${tot_bal:.2f} (~Rp {tot_bal*KURS_IDR:,.0f}) | PnL: ${tot_pnl:+.2f} | Posisi: {len(all_active)}", flush=True)
                if all_active:
                    for w, p in all_active:
                        print(f"   ├─ [{w.acc_label}] [{w.name}] {p['symbol']} {p['side']} {p['leverage']}x | PnL: ${p['pnl']:+.2f} | Entry: ${p['entry']:.4f}", flush=True)

                # 2. Scanning Sinyal Koin Emas
                ex_scan = next((w.exchange for w in active_workers if w.exchange), None)
                if ex_scan:
                    for symbol in SYMBOLS:
                        try:
                            kl = await asyncio.to_thread(ex_scan.fetch_ohlcv, symbol, TIMEFRAME, limit=40)
                            sig = self.check_signals(symbol, kl)
                            if sig:
                                cur_p = float(kl[-1][4])
                                cur_coin = symbol.split('/')[0].split(':')[0].upper()
                                # Cari worker yang punya slot kosong (< MAX_POSITIONS_PER_EXCHANGE)
                                for w in active_workers:
                                    if w.is_in_drawdown_halt():
                                        continue
                                    if w.cooldowns.get(cur_coin, 0) > time.time():
                                        continue
                                    w_positions = w.get_active_positions()
                                    if w_positions is None:
                                        continue
                                    if len(w_positions) < MAX_POSITIONS_PER_EXCHANGE:
                                        w_coins = [p['symbol'].split('/')[0].split(':')[0].upper() for p in w_positions]
                                        if cur_coin not in w_coins:
                                            await asyncio.to_thread(
                                                w.open_order, symbol, sig['side'], cur_p, sig['mom'], sig['ker'], sig['atr24'],
                                                sig.get('tp_pct', TP_PCT), sig.get('sl_pct', SL_PCT), sig.get('strategy', 'NORMAL')
                                            )
                        except Exception as e:
                            logger.debug(f"Scan error {symbol}: {e}")

                # 3. Export data untuk Web Dashboard Streamlit
                self.export_and_sync_web()

            except Exception as e:
                logger.error(f"Error loop: {e}")

            await asyncio.sleep(SCAN_INTERVAL_SECONDS)

def main():
    master = MultiAccountMaster()
    try:
        asyncio.run(master.run_loop())
    except KeyboardInterrupt:
        print("\n[STOP] Bot dihentikan oleh user.")

if __name__ == "__main__":
    main()
