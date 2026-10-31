"""
bingx_executor.py
=================
Eksekutor Order BingX Futures Resmi:
- Eksekusi Limit Order + Take Profit (TP1/TP2/TP3) + Stop Loss otomatis
- Dukungan Akun 1, Akun 2, Akun 3
- Pencatatan status persisten sukses di disk & state
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
    # 1. Streamlit Cloud Native Secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and len(st.secrets) > 0:
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
            # Baca posisi aktif via endpoint swapV2 resmi (agar posisi manual seperti ENS & KAS 100% terbaca)
            raw_pos_resp = client.swapV2PrivateGetUserPositions()
            pos = raw_pos_resp.get("data", [])
            for p in pos:
                amt = float(p.get("positionAmt") or 0)
                if amt != 0:
                    sym_raw = p.get("symbol", "")
                    base = sym_raw.split("-")[0].replace("1000", "")
                    side = str(p.get("positionSide", "SHORT")).upper()
                    active_map[sym_raw] = {"account": acc_k, "side": side, "type": "POSITION", "contracts": abs(amt)}
                    active_map[sym_raw.replace("-USDT", "")] = {"account": acc_k, "side": side, "type": "POSITION", "contracts": abs(amt)}
                    active_map[base] = {"account": acc_k, "side": side, "type": "POSITION", "contracts": abs(amt)}
            # Baca open orders (limit antre)
            orders = client.fetch_open_orders()
            for o in orders:
                sym_clean = o["symbol"].split(":")[0].replace("/", "-")
                base = sym_clean.split("-")[0]
                if sym_clean not in active_map:
                    active_map[sym_clean] = {"account": acc_k, "side": o.get("side"), "type": "ORDER", "price": o.get("price")}
                if base not in active_map:
                    active_map[base] = {"account": acc_k, "side": o.get("side"), "type": "ORDER", "price": o.get("price")}
        except Exception:
            pass
    return active_map

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
            client.set_leverage(leverage, ccxt_symbol, params={"side": "BOTH"})
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
