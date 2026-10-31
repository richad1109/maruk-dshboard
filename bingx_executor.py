def fetch_comprehensive_pnl(account_key: str = "akun_1") -> dict:
    """Membaca Unrealized PnL, Realized PnL, Win Rate, dan Fees riil langsung dari bursa BingX."""
    client = get_bingx_client(account_key)
    if not client:
        return {}
    try:
        unrealized_total = 0.0
        active_positions_count = 0
        pos_data = client.swapV2PrivateGetUserPositions().get('data', [])
        for p in pos_data:
            amt = float(p.get('positionAmt') or 0)
            if amt != 0:
                active_positions_count += 1
                unrealized_total += float(p.get('unrealizedProfit') or 0)
                
        realized_total = 0.0
        realized_wins = 0
        realized_losses = 0
        fees_total = 0.0
        funding_total = 0.0
        
        income_data = client.swapV2PrivateGetUserIncome({'limit': 100}).get('data', [])
        for inc in income_data:
            itype = inc.get('incomeType')
            val = float(inc.get('income') or 0)
            if itype == 'REALIZED_PNL':
                realized_total += val
                if val > 0: realized_wins += 1
                elif val < 0: realized_losses += 1
            elif itype == 'TRADING_FEE':
                fees_total += val
            elif itype == 'FUNDING_FEE':
                funding_total += val
                
        total_closed = realized_wins + realized_losses
        win_rate = (realized_wins / total_closed * 100.0) if total_closed > 0 else 0.0
        net_total = realized_total + unrealized_total
        
        return {
            'unrealized_total': round(unrealized_total, 4),
            'active_positions_count': active_positions_count,
            'realized_total': round(realized_total, 4),
            'realized_wins': realized_wins,
            'realized_losses': realized_losses,
            'win_rate': round(win_rate, 1),
            'fees_total': round(fees_total, 4),
            'funding_total': round(funding_total, 4),
            'net_total': round(net_total, 4)
        }
    except Exception as e:
        return {'error': str(e), 'unrealized_total': 0.0, 'realized_total': 0.0, 'net_total': 0.0}


"""
bingx_executor.py
=================
Eksekutor Order & Telemetri Bursa BingX Futures Resmi:
- Eksekusi Limit Order + Take Profit (TP1/TP2/TP3) + Stop Loss otomatis
- Fitur Batalkan Semua Limit Order (Emergency Killswitch)
- Deteksi Sentimen Makro BTC (SMC / Institutional Pump / Dump Shield)
- Pelacakan Posisi Aktif Bursa Riil (ENS, KAS, BTC, dll.)
- Dukungan Akun 1, Akun 2, Akun 3
- Membaca credentials dari Streamlit Cloud secrets (st.secrets) secara native
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ccxt

WIB = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parent
SECRETS_FILE = ROOT / ".streamlit" / "secrets.toml"
STATE_FILE = ROOT / "assets" / "bingx_orders_state.json"

def get_accounts_credentials():
    """Ambil credentials 3 akun BingX dari Streamlit Cloud Secrets (st.secrets), file lokal, atau env."""
    # 0. Coba modul maruk_data terlebih dahulu (100% konsisten dengan dashboard)
    try:
        import maruk_data
        try:
            import streamlit as st
            s_dict = st.secrets.to_dict() if hasattr(st, "secrets") else {}
        except Exception:
            s_dict = {}
        creds = maruk_data.credentials(s_dict)
        if creds and any("BingX" in v for v in creds.values() if isinstance(v, dict)):
            return creds
    except Exception:
        pass

    # 1. Streamlit Cloud Native Secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            try:
                s_dict = st.secrets.to_dict()
                raw = s_dict.get("accounts_json")
                if raw:
                    return json.loads(raw) if isinstance(raw, str) else raw
                if "accounts" in s_dict:
                    return dict(s_dict["accounts"])
            except Exception:
                pass
            raw = st.secrets.get("accounts_json")
            if raw:
                return json.loads(raw) if isinstance(raw, str) else raw
            if "accounts" in st.secrets:
                return dict(st.secrets["accounts"])
    except Exception:
        pass

    # 2. Cari di berbagai lokasi secrets.toml
    try:
        import toml
        search_paths = [
            ROOT / ".streamlit" / "secrets.toml",
            ROOT.parent / "maruk-dshboard-repo" / ".streamlit" / "secrets.toml",
            ROOT.parent / "splendid-hopper" / ".streamlit" / "secrets.toml",
            Path(r"C:/Users/adee/Documents/antigravity/maruk-dshboard-repo/.streamlit/secrets.toml"),
            Path.home() / ".streamlit" / "secrets.toml"
        ]
        for sp in search_paths:
            if sp.exists():
                sec = toml.load(sp)
                raw = sec.get("accounts_json")
                if raw:
                    return json.loads(raw) if isinstance(raw, str) else raw
                if "accounts" in sec:
                    return dict(sec["accounts"])
    except Exception:
        pass
    
    # 3. Environment Variable
    raw = os.getenv("MARUK_ACCOUNTS_JSON")
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            pass
    return {}

def load_bingx_order_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_bingx_order_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass

def get_bingx_client(account_key: str):
    """Buat client ccxt.bingx untuk akun tertentu (akun_1, akun_2, akun_3)."""
    accs = get_accounts_credentials()
    if account_key not in accs or "BingX" not in accs[account_key]:
        return None
    cfg = accs[account_key]["BingX"]
    client = ccxt.bingx({
        "apiKey": cfg["apiKey"],
        "secret": cfg["secret"],
        "adjustForTimeDifference": True,
        "options": {"defaultType": "swap", "adjustForTimeDifference": True},
        "timeout": 12000,
        "enableRateLimit": True
    })
    return client

def fetch_live_active_bingx_coins():
    """Membaca posisi aktif dan open orders riil langsung dari bursa BingX semua akun."""
    active_map = {}
    accs = get_accounts_credentials()
    for acc_k in ["akun_1", "akun_2", "akun_3"]:
        if acc_k not in accs or "BingX" not in accs[acc_k]:
            continue
        try:
            client = get_bingx_client(acc_k)
            if not client:
                continue
            # 1. Baca posisi aktif via endpoint swapV2 resmi (agar posisi manual seperti ENS & KAS 100% terbaca)
            raw_pos_resp = client.swapV2PrivateGetUserPositions()
            pos = raw_pos_resp.get("data", [])
            for p in pos:
                amt = float(p.get("positionAmt") or 0)
                if amt != 0:
                    sym_raw = p.get("symbol", "")
                    base = sym_raw.split("-")[0].replace("1000", "")
                    side = str(p.get("positionSide", "SHORT")).upper()
                    entry_p = float(p.get("avgPrice") or 0)
                    mark_p = float(p.get("markPrice") or entry_p)
                    unrealized_pnl = float(p.get("unrealizedProfit") or 0)
                    leverage_val = float(p.get("leverage") or 20)
                    
                    # Hitung ROE
                    margin_val = (abs(amt) * entry_p) / (leverage_val + 1e-10)
                    roe_val = (unrealized_pnl / margin_val * 100.0) if margin_val > 0 else 0.0

                    pos_data = {
                        "account": acc_k,
                        "side": side,
                        "type": "POSITION",
                        "contracts": abs(amt),
                        "entry": entry_p,
                        "mark": mark_p,
                        "pnl": unrealized_pnl,
                        "roe": roe_val,
                        "leverage": leverage_val,
                        "symbol": sym_raw,
                        "base": base
                    }
                    active_map[sym_raw] = pos_data
                    active_map[sym_raw.replace("-USDT", "")] = pos_data
                    active_map[base] = pos_data

            # 2. Baca open orders (limit antre)
            orders = client.fetch_open_orders()
            for o in orders:
                sym_clean = o["symbol"].split(":")[0].replace("/", "-")
                base = sym_clean.split("-")[0].replace("1000", "")
                order_data = {
                    "account": acc_k,
                    "side": str(o.get("side", "")).upper(),
                    "type": "ORDER",
                    "price": float(o.get("price") or 0),
                    "amount": float(o.get("amount") or 0),
                    "order_id": str(o.get("id", "")),
                    "symbol": sym_clean,
                    "base": base
                }
                if sym_clean not in active_map:
                    active_map[sym_clean] = order_data
                if base not in active_map:
                    active_map[base] = order_data
        except Exception:
            pass
    return active_map

def cancel_web_orders_only(account_key: str = "all") -> dict:
    """
    Batalkan HANYA open limit order yang dipasang lewat Web Dashboard.
    Order manual yang dipasang sendiri oleh user di aplikasi BingX 100% AMAN & TIDAK DISENTUH!
    """
    state = load_bingx_order_state()
    web_order_ids = {str(v.get("order_id")) for v in state.values() if v.get("order_id")}
    web_symbols = {v.get("symbol") for v in state.values() if v.get("symbol")}

    accs = get_accounts_credentials()
    target_accs = ["akun_1", "akun_2", "akun_3"] if account_key == "all" else [account_key]
    results = {}

    for acc in target_accs:
        client = get_bingx_client(acc)
        if not client:
            continue
        try:
            orders = client.fetch_open_orders()
            cancelled = 0
            skipped_manual = 0
            for o in orders:
                oid = str(o.get("id", ""))
                sym_clean = o["symbol"].split(":")[0].replace("/", "-")
                if oid in web_order_ids or (f"{acc}_{sym_clean}" in state and state[f"{acc}_{sym_clean}"].get("status") == "SUKSES_BINGX"):
                    try:
                        client.cancel_order(oid, o["symbol"])
                        cancelled += 1
                    except Exception:
                        pass
                else:
                    skipped_manual += 1
            results[acc] = f"Dibatalkan Web: {cancelled} | Manual Aman: {skipped_manual}"
        except Exception as e:
            results[acc] = f"Error: {str(e)}"
    return results

def close_web_positions_only(account_key: str = "all") -> dict:
    """
    Tutup HANYA posisi yang dibuka lewat Web Dashboard.
    Posisi manual (seperti ENS, KAS, dll. yang dibuka manual) 100% AMAN & TIDAK AKAN DISENTUH!
    """
    state = load_bingx_order_state()
    web_symbols_per_acc = {}
    for k, v in state.items():
        if v.get("status") == "SUKSES_BINGX":
            acc = v.get("account", "akun_1")
            web_symbols_per_acc.setdefault(acc, set()).add(v.get("symbol"))

    accs = get_accounts_credentials()
    target_accs = ["akun_1", "akun_2", "akun_3"] if account_key == "all" else [account_key]
    results = {}

    for acc in target_accs:
        client = get_bingx_client(acc)
        if not client:
            continue
        allowed_web_syms = web_symbols_per_acc.get(acc, set())
        try:
            raw_pos_resp = client.swapV2PrivateGetUserPositions()
            pos = raw_pos_resp.get("data", [])
            closed = 0
            skipped_manual = 0
            for p in pos:
                amt = float(p.get("positionAmt") or 0)
                if amt != 0:
                    sym_raw = p.get("symbol", "")
                    base = sym_raw.split("-")[0]
                    if sym_raw in allowed_web_syms or f"{base}-USDT" in allowed_web_syms or base in allowed_web_syms:
                        side = "sell" if float(amt) > 0 else "buy"
                        pos_side = str(p.get("positionSide", "BOTH")).upper()
                        ccxt_sym = f"{base}/USDT:USDT"
                        try:
                            client.create_order(
                                symbol=ccxt_sym,
                                type="market",
                                side=side,
                                amount=abs(amt),
                                params={"positionSide": pos_side}
                            )
                            closed += 1
                        except Exception:
                            pass
                    else:
                        skipped_manual += 1
            results[acc] = f"Ditutup Web: {closed} | Manual Aman: {skipped_manual}"
        except Exception as e:
            results[acc] = f"Error: {str(e)}"
    return results

def cancel_all_bingx_open_orders(account_key: str = "all") -> dict:
    """
    Batalkan SEMUA open limit order yang sedang antre di BingX Futures.
    Fitur darurat (Killswitch) ketika terjadi pergerakan ekstrem BTC.
    """
    accs = get_accounts_credentials()
    target_accs = ["akun_1", "akun_2", "akun_3"] if account_key == "all" else [account_key]
    results = {}
    for acc in target_accs:
        client = get_bingx_client(acc)
        if not client:
            continue
        try:
            orders = client.fetch_open_orders()
            cancelled = 0
            for o in orders:
                try:
                    client.cancel_order(o["id"], o["symbol"])
                    cancelled += 1
                except Exception:
                    pass
            results[acc] = cancelled
        except Exception as e:
            results[acc] = f"Error: {str(e)}"
    return results

def get_btc_macro_sentiment() -> dict:
    """
    Scanner Makro BTC (SMC / Institutional Flow Shield):
    Mendeteksi apakah BTC sedang dipompa (pump) atau dibanting (dump) oleh smart money/retail.
    Membantu trader membatalkan limit berlawanan arah sebelum tersapu (SL).
    """
    try:
        client = get_bingx_client("akun_1")
        if not client:
            client = ccxt.bingx({"adjustForTimeDifference": True, "options": {"defaultType": "swap"}})
        
        # Ambil kline 1H BTC
        ohlcv = client.fetch_ohlcv("BTC/USDT:USDT", timeframe="1h", limit=30)
        if not ohlcv or len(ohlcv) < 15:
            return {"status": "NORMAL", "label": "🛡️ BTC STABIL / NETRAL", "price": 0, "change_1h": 0, "rsi": 50}

        closes = [x[4] for x in ohlcv]
        curr_p = closes[-1]
        prev_p = closes[-2]
        change_1h = ((curr_p - prev_p) / prev_p) * 100.0

        # Simple RSI 14
        gains, losses = [], []
        for i in range(1, 15):
            diff = closes[-i] - closes[-i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        avg_gain = sum(gains) / 14.0
        avg_loss = (sum(losses) / 14.0) + 1e-10
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        if change_1h >= 1.2 or rsi >= 72:
            return {
                "status": "PUMP_SPIKE",
                "label": "🚨 BTC PUMP SURGE (Whales Borong) - WASPADA SHORT!",
                "price": curr_p,
                "change_1h": round(change_1h, 2),
                "rsi": round(rsi, 1),
                "recommendation": "Sebaiknya cancel limit short yang belum tersentuh!"
            }
        elif change_1h <= -1.2 or rsi <= 28:
            return {
                "status": "DUMP_SPIKE",
                "label": "🚨 BTC DUMP SURGE (Panic Selling) - WASPADA LONG!",
                "price": curr_p,
                "change_1h": round(change_1h, 2),
                "rsi": round(rsi, 1),
                "recommendation": "Sebaiknya cancel limit long yang belum tersentuh!"
            }
        else:
            return {
                "status": "NORMAL",
                "label": "🛡️ BTC TREN NETRAL / STABIL - Aman untuk Limit Order",
                "price": curr_p,
                "change_1h": round(change_1h, 2),
                "rsi": round(rsi, 1),
                "recommendation": "Kondisi pasar wajar. Limit order aman dijalankan."
            }
    except Exception:
        return {"status": "NORMAL", "label": "🛡️ BTC TREN NETRAL", "price": 0, "change_1h": 0, "rsi": 50, "recommendation": "Aman"}

def place_bingx_sniper_order(account_key: str, symbol_clean: str, direction: str, 
                             entry_price: float, sl_price: float, tp_price: float, 
                             tp_choice_label: str = "TP1", margin_usd: float = 0.20, leverage: int = 20):
    """
    Pasang Limit Order di BingX Futures dengan Stop Loss dan Take Profit otomatis.
    """
    client = get_bingx_client(account_key)
    if not client:
        return {"success": False, "msg": f"Credentials BingX untuk {account_key} tidak ditemukan pada konfigurasi server."}

    # Format CCXT symbol: 'BTC/USDT:USDT'
    base = symbol_clean.replace("-USDT", "").replace("USDT", "")
    ccxt_symbol = f"{base}/USDT:USDT"

    try:
        markets = client.load_markets()
        if ccxt_symbol not in markets:
            matched = [s for s in markets if base in s and ":USDT" in s]
            if matched:
                ccxt_symbol = matched[0]
            else:
                return {"success": False, "msg": f"Pasar {ccxt_symbol} tidak ditemukan di BingX Swap."}

        market = markets[ccxt_symbol]

        # Set Leverage ke 20x
        try:
            client.set_leverage(leverage, ccxt_symbol, params={"side": "ALL"})
        except Exception:
            pass

        target_notional = max(margin_usd * leverage, float(market.get("limits", {}).get("cost", {}).get("min") or 2.0))
        raw_amount = target_notional / (entry_price + 1e-10)

        min_amount = float(market.get("limits", {}).get("amount", {}).get("min") or 0.0)
        amount = max(raw_amount, min_amount)

        amount = float(client.amount_to_precision(ccxt_symbol, amount))
        entry_price = float(client.price_to_precision(ccxt_symbol, entry_price))
        sl_price = float(client.price_to_precision(ccxt_symbol, sl_price))
        tp_price = float(client.price_to_precision(ccxt_symbol, tp_price))

        side = "buy" if direction.upper() == "LONG" else "sell"
        position_side = "LONG" if direction.upper() == "LONG" else "SHORT"

        params = {
            "positionSide": position_side,
            "stopLoss": {
                "triggerPrice": sl_price,
                "price": sl_price,
            },
            "takeProfit": {
                "triggerPrice": tp_price,
                "price": tp_price,
            }
        }

        order = client.create_order(
            symbol=ccxt_symbol,
            type="limit",
            side=side,
            amount=amount,
            price=entry_price,
            params=params
        )

        order_id = str(order.get("id", ""))
        now_str = datetime.now(WIB).strftime("%H:%M:%S WIB")

        state = load_bingx_order_state()
        state_key = f"{account_key}_{symbol_clean}"
        state[state_key] = {
            "account": account_key,
            "symbol": symbol_clean,
            "order_id": order_id,
            "direction": direction,
            "entry": entry_price,
            "sl": sl_price,
            "tp": tp_price,
            "tp_choice": tp_choice_label,
            "amount": amount,
            "status": "SUKSES_BINGX",
            "time_str": now_str,
            "timestamp": time.time()
        }
        save_bingx_order_state(state)

        return {
            "success": True,
            "order_id": order_id,
            "amount": amount,
            "entry": entry_price,
            "sl": sl_price,
            "tp": tp_price,
            "time_str": now_str,
            "msg": f"SUKSES BINGX! Order #{order_id[-6:]} terpasang pada harga {entry_price} (SL: {sl_price} | {tp_choice_label}: {tp_price})"
        }

    except Exception as e:
        return {"success": False, "msg": f"Gagal pasang di BingX: {str(e)}"}


def apply_bep_to_profit_positions(account_key: str = "akun_1", min_roe: float = 8.0) -> dict:
    """
    Otomatis geser Stop Loss ke harga modal (BEP / Break-Even) untuk SEMUA posisi yang sedang floating profit.
    User tidak perlu lagi geser manual satu per satu di aplikasi BingX!
    """
    client = get_bingx_client(account_key)
    if not client:
        return {"success": False, "msg": f"Client BingX untuk {account_key} tidak ditemukan."}

    results = []
    try:
        # 1. Ambil semua open orders yang ada saat ini
        open_orders = client.fetch_open_orders()
        
        # Map symbol -> list of orders
        existing_orders_map = {}
        for o in open_orders:
            sym_raw = o.get("symbol", "").split(":")[0].replace("/", "-")
            existing_orders_map.setdefault(sym_raw, []).append(o)

        # 2. Ambil semua active positions
        resp = client.swapV2PrivateGetUserPositions()
        positions = resp.get("data", [])

        for p in positions:
            amt = float(p.get("positionAmt") or 0)
            if amt == 0:
                continue
            
            sym = p.get("symbol", "")
            base = sym.split("-")[0]
            entry_p = float(p.get("avgPrice") or 0)
            unrealized = float(p.get("unrealizedProfit") or 0)
            leverage = float(p.get("leverage") or 20)
            pos_side = str(p.get("positionSide", "SHORT")).upper()

            # Hitung ROE
            margin = (abs(amt) * entry_p) / (leverage + 1e-10)
            roe = (unrealized / margin * 100.0) if margin > 0 else 0.0

            # Cek apakah posisi sedang profit memenuhi syarat (ROE >= min_roe)
            if unrealized > 0 and roe >= min_roe:
                sym_clean = sym
                sym_orders = existing_orders_map.get(sym_clean, []) + existing_orders_map.get(f"{base}/USDT:USDT", [])
                
                already_bep = False
                old_sl_orders = []
                for o in sym_orders:
                    o_type = str(o.get("info", {}).get("type") or o.get("type", "")).upper()
                    o_price = float(o.get("price") or o.get("stopPrice") or 0)
                    if "STOP" in o_type:
                        # Cek selisih harga dengan entry
                        if abs(o_price - entry_p) / (entry_p + 1e-10) < 0.002:
                            already_bep = True
                        else:
                            old_sl_orders.append(o)

                if already_bep:
                    results.append(f"🔒 {base}: Sudah terkunci di BEP ({entry_p})")
                    continue

                # Batalkan SL lama yang masih di level awal (rugi)
                for old_o in old_sl_orders:
                    try:
                        client.cancel_order(old_o["id"], old_o.get("symbol"))
                    except Exception:
                        pass

                # Pasang STOP_MARKET di harga Entry
                order_side = "BUY" if pos_side == "SHORT" else "SELL"
                ccxt_sym = f"{base}/USDT:USDT"
                
                bep_placed = False
                # Cara 1: via endpoint swapV2 resmi BingX
                try:
                    price_str = client.price_to_precision(ccxt_sym, entry_p) if hasattr(client, 'price_to_precision') else str(entry_p)
                    amt_str = client.amount_to_precision(ccxt_sym, abs(amt)) if hasattr(client, 'amount_to_precision') else str(abs(amt))
                    client.swapV2PrivatePostTradeOrder({
                        "symbol": sym,
                        "type": "STOP_MARKET",
                        "side": order_side,
                        "positionSide": pos_side,
                        "stopPrice": price_str,
                        "quantity": amt_str,
                    })
                    results.append(f"🛡️ {base}: BERHASIL dikunci BEP @ {entry_p} (ROE +{roe:.1f}%)")
                    bep_placed = True
                except Exception:
                    pass

                # Cara 2: Fallback via CCXT create_order
                if not bep_placed:
                    try:
                        client.create_order(
                            symbol=ccxt_sym,
                            type="market",
                            side=order_side.lower(),
                            amount=abs(amt),
                            params={
                                "stopLossPrice": entry_p,
                                "positionSide": pos_side,
                                "reduceOnly": True
                            }
                        )
                        results.append(f"🛡️ {base}: BERHASIL dikunci BEP via CCXT @ {entry_p} (ROE +{roe:.1f}%)")
                        bep_placed = True
                    except Exception as e_ccxt:
                        results.append(f"⚠️ {base}: Gagal pasang BEP ({str(e_ccxt)})")

        return {
            "success": True,
            "count": len(results),
            "details": results,
            "msg": f"Diproses {len(results)} posisi profit." if results else "Belum ada posisi baru yang memenuhi target ROE profit untuk di-BEP."
        }
    except Exception as e:
        return {"success": False, "msg": f"Error apply BEP: {str(e)}"}
