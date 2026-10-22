"""Read-only dashboard data. Unknown values remain unknown; no trading methods."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import json
import math
import os
import time

import ccxt
import requests
import sakti_monitor

ROOT = Path(__file__).resolve().parent
ACCOUNTS = ("akun_1", "akun_2", "akun_3")
EXCHANGES = ("Bitget", "MEXC", "BingX")
ACTIVE = [(a, e) for a in ACCOUNTS for e in EXCHANGES if (a, e) != ("akun_3", "MEXC")]
COINS = ("BTC", "ETH", "SOL", "BNB", "DOGE", "ADA", "AVAX", "DOT", "XRP", "LINK", "LTC", "TRX")


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def first(data, *keys):
    for key in keys:
        value = number(data.get(key))
        if value is not None:
            return value
    return None


def timestamp(value):
    if isinstance(value, (int, float)):
        return float(value)/1000 if value > 10**11 else float(value)
    if isinstance(value, str):
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:
            return None
    return None


def credentials(secret_values=None):
    """Cloud Secrets first. Local ignored JSON is a development fallback only."""
    secret_values = secret_values or {}
    raw = secret_values.get("accounts_json") or secret_values.get("ACCOUNTS_JSON") or os.getenv("MARUK_ACCOUNTS_JSON")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else dict(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    if secret_values.get("accounts"):
        return dict(secret_values["accounts"])
    path = Path(os.getenv("MARUK_ACCOUNTS_PATH", str(ROOT/"accounts_config.json")))
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {}
    return {}


def empty_ledger(account, exchange, status="unconfigured"):
    return dict(account=account, exchange=exchange, status=status, equity=None, free=None,
                floating=None, positions=[], updated=None, error=None)


def pair(value):
    return str(value).replace(":USDT", "").replace("_", "/").replace("-", "/").replace("USDT", "/USDT").replace("//", "/")


def normalize_position(exchange, raw, specs=None):
    if exchange == "BingX":
        signed = first(raw, "positionAmt", "positionAmount") or 0.
        direction = str(raw.get("positionSide", "")).upper()
        side = direction if direction in ("LONG", "SHORT") else ("LONG" if signed > 0 else "SHORT")
        quantity = abs(signed)
        entry = first(raw, "avgPrice", "entryPrice")
        mark = first(raw, "markPrice")
        margin = first(raw, "initialMargin", "margin")
        floating = first(raw, "unrealizedProfit", "unrealizedPnl")
        liquidation = first(raw, "liquidationPrice")
    elif exchange == "Bitget":
        quantity = abs(first(raw, "total", "size") or 0.)
        side = str(raw.get("holdSide", "")).upper()
        entry = first(raw, "openPriceAvg", "averageOpenPrice")
        mark = first(raw, "markPrice")
        margin = first(raw, "marginSize", "initialMargin")
        floating = first(raw, "unrealizedPL", "unrealizedPnl")
        liquidation = first(raw, "liquidationPrice")
    else:
        contracts = abs(first(raw, "holdVol") or 0.)
        size = number((specs or {}).get(raw.get("symbol")))
        quantity = contracts*size if size is not None else None
        if contracts <= 0:
            return None
        side = "LONG" if int(raw.get("positionType") or 1) == 1 else "SHORT"
        entry = first(raw, "holdAvgPrice", "openAvgPrice")
        mark = first(raw, "fairPrice", "markPrice")
        margin = first(raw, "im", "oim")
        floating = first(raw, "unRealizedPnl", "unrealisedPnl", "unrealizedPnl")
        liquidation = first(raw, "liquidatePrice", "liquidationPrice")
    if quantity is not None and quantity <= 0:
        return None
    return dict(exchange=exchange, symbol=pair(raw.get("symbol", "")), side=side,
        quantity=quantity, entry=entry, mark=mark, margin=margin,
        notional=quantity*mark if quantity is not None and mark is not None else None,
        pnl=floating, roe=100*floating/margin if floating is not None and margin else None,
        leverage=first(raw, "leverage"), liquidation=liquidation,
        stop=first(raw, "stopLossPrice"), take=first(raw, "takeProfitPrice"))


def checked(response, venue):
    if not isinstance(response, dict):
        raise ValueError("Invalid response")
    if response.get("success") is False or str(response.get("code", "0")) not in ("0", "00000"):
        raise ValueError("Exchange rejected response")
    return response.get("data")


@lru_cache(maxsize=4)
def mexc_specs(bucket):
    try:
        response = requests.get("https://contract.mexc.com/api/v1/contract/detail", timeout=6)
        response.raise_for_status()
        return {r["symbol"]:float(r["contractSize"]) for r in checked(response.json(), "MEXC")}
    except Exception:
        return {}


def query_ledger(account, venue, config, specs=None, client_factory=None):
    row = empty_ledger(account, venue)
    values = config.get(account, {}).get(venue, {})
    required = ("apiKey", "secret", "password") if venue == "Bitget" else ("apiKey", "secret")
    if any(not values.get(key) for key in required):
        return row
    options = {key:values[key] for key in required}
    options.update(timeout=7000, enableRateLimit=True, options={"defaultType":"swap", "maxRetriesOnFailure":0})
    try:
        client = client_factory(venue, options) if client_factory else getattr(ccxt, venue.lower())(options)
        if venue == "BingX":
            balance = checked(client.swapV2PrivateGetUserBalance(), venue).get("balance", {})
            positions = checked(client.swapV2PrivateGetUserPositions(), venue)
            equity, free = first(balance,"equity"), first(balance,"availableMargin")
            floating = first(balance,"unrealizedProfit")
        elif venue == "Bitget":
            balances = checked(client.privateMixGetV2MixAccountAccounts({"productType":"USDT-FUTURES"}), venue)
            balance = next((b for b in balances if b.get("marginCoin") == "USDT"), {})
            positions = checked(client.privateMixGetV2MixPositionAllPosition({"productType":"USDT-FUTURES", "marginCoin":"USDT"}),venue)
            equity, free = first(balance,"accountEquity","usdtEquity"), first(balance,"available")
            floating = first(balance,"unrealizedPL")
        else:
            balances = checked(client.contractPrivateGetAccountAssets(), venue)
            balance = next((b for b in balances if b.get("currency") == "USDT"), {})
            positions = checked(client.contractPrivateGetPositionOpenPositions(), venue)
            equity, free = first(balance,"equity"), first(balance,"availableBalance")
            floating = first(balance,"unrealized")
        if equity is None or free is None:
            raise ValueError("Missing account balance")
        parsed = [normalize_position(venue,p,specs) for p in positions or []]
        row["positions"] = [{**p,"account":account} for p in parsed if p is not None]
        if floating is None and all(p["pnl"] is not None for p in row["positions"]):
            floating = sum(p["pnl"] for p in row["positions"])
        row.update(status="live",equity=equity,free=free,floating=floating,updated=time.time())
    except Exception as error:
        # Signed URLs, headers and raw exchange exception text must never reach UI.
        row.update(status="error",error=type(error).__name__)
    return row


def read_state():
    paths = [os.getenv("SAKTI_STATE_PATH"), os.getenv("MARUK_STATE_PATH"), str(ROOT/"sakti_live_state.json"), str(ROOT/"riset8_live_state.json"), str(ROOT/"live_bot_state.json")]
    for value in paths:
        if value:
            try:
                state = json.loads(Path(value).read_text(encoding="utf-8-sig"))
                if isinstance(state,dict):
                    return state
            except (OSError, ValueError):
                pass
    return {}


def snapshot_ledgers(state):
    """An old export is a dated snapshot, never a live exchange connection."""
    root = state.get("accounts",state)
    rows = []
    for account, venue in ACTIVE:
        source = root.get(account,{})
        detail = source.get("ex_details",{}).get(venue,{})
        row = empty_ledger(account,venue,"snapshot")
        row.update(equity=first(detail,"total"), free=first(detail,"free"),
                   updated=timestamp(source.get("updated_at")))
        for old in source.get("pos_list",[]):
            if old.get("exchange") == venue:
                p = {k:old.get(k) for k in ["symbol","side","margin","leverage","entry","mark","notional","pnl","roe","liquidation","stop","take"]}
                p.update(exchange=venue,account=account,quantity=None)
                row["positions"].append(p)
        row["floating"] = sum(p["pnl"] for p in row["positions"]) if all(number(p["pnl"]) is not None for p in row["positions"]) else None
        if row["equity"] is not None:
            rows.append(row)
    return rows


def state_metadata(state):
    trades = []
    wallets = state.get("wallets",{})
    for key,wallet in wallets.items():
        if key == "akun_3/mexc":
            continue
        account,_,exchange = key.partition("/")
        for item in wallet.get("trades",[]):
            if number(item.get("net_pnl")) is not None:
                trades.append(dict(account=account,exchange=exchange,net_pnl=float(item["net_pnl"]),
                                   closed=timestamp(item.get("closed"))))
    runtime=sakti_monitor.sanitize(state) if isinstance(state.get('wallets'),dict) else None
    return dict(phase=state.get("phase"),trades=trades,runtime=runtime,
        reserved=sum(number(w.get("reserved")) or 0 for w in wallets.values()) if wallets else None,
        heartbeat=timestamp(state.get("updated_at") or state.get("heartbeat")))


def fetch_portfolio(config, state=None):
    state = read_state() if state is None else state
    specs = mexc_specs(int(time.time()//3600)) if any(config.get(a,{}).get("MEXC",{}).get("apiKey") for a in ACCOUNTS[:2]) else {}
    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        work = [pool.submit(query_ledger,a,e,config,specs) for a,e in ACTIVE]
        for job in as_completed(work):
            rows.append(job.result())
    cached = {(r["account"],r["exchange"]):r for r in snapshot_ledgers(state)}
    for i,row in enumerate(rows):
        if row["status"] != "live" and (row["account"],row["exchange"]) in cached:
            rows[i] = {**cached[row["account"],row["exchange"]],"error":row.get("error")}
    rows.sort(key=lambda r:ACTIVE.index((r["account"],r["exchange"])))
    return dict(mode="live" if all(r["status"] == "live" for r in rows) else "partial",
                fetched=time.time(),ledgers=rows,**state_metadata(state))


def totals(snapshot, account="all"):
    rows = [r for r in snapshot["ledgers"] if account == "all" or r["account"] == account]
    known = [r for r in rows if r["equity"] is not None]
    positions = [p for r in rows for p in r["positions"]]
    floating = [r["floating"] for r in rows]
    return dict(equity=sum(r["equity"] for r in known) if known else None,
        free=sum(r["free"] for r in rows if r["free"] is not None) if known else None,
        floating=sum(floating) if floating and all(v is not None for v in floating) else None,
        margin=sum(p["margin"] for p in positions if number(p["margin"]) is not None),
        positions=positions,rows=rows,complete=len(known) == len(rows),
        live=sum(r["status"] == "live" for r in rows),expected=len(rows),known=len(known))


def market_data(base="BTC"):
    result = dict(tickers=[],candles=[],source="BingX",fetched=None,error=None)
    try:
        response = requests.get("https://open-api.bingx.com/openApi/swap/v2/quote/ticker",timeout=7)
        response.raise_for_status()
        for row in checked(response.json(),"BingX"):
            coin = row.get("symbol","").split("-")[0]
            if coin in COINS and row.get('symbol')==coin+'-USDT':
                result["tickers"].append(dict(coin=coin,price=first(row,"lastPrice"),change=first(row,"priceChangePercent")))
        result["tickers"].sort(key=lambda r:COINS.index(r["coin"]))
        response = requests.get("https://open-api.bingx.com/openApi/swap/v3/quote/klines",
            params={"symbol":base+"-USDT","interval":"1h","limit":168},timeout=7)
        response.raise_for_status()
        for row in checked(response.json(),"BingX"):
            ts = first(row,"time")
            if ts and ts/1000+3600 <= time.time():
                result["candles"].append(dict(time=ts/1000,open=first(row,"open"),high=first(row,"high"),low=first(row,"low"),close=first(row,"close")))
        result["candles"].sort(key=lambda r:r["time"])
        result["fetched"] = time.time()
    except Exception as error:
        result["error"] = type(error).__name__
    return result
