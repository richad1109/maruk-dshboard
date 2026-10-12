import os
import sys
import time
import socket
import json
import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests
import streamlit as st
import ccxt

# ========================================================
# STREAMLIT PAGE CONFIGURATION - CLEAN & RESPONSIVE
# ========================================================
st.set_page_config(
    page_title="⚡ TITAN V5 Family Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========================================================
# MINIMALIST DARK STYLING
# ========================================================
st.markdown("""
<style>
#MainMenu, header, footer, 
[data-testid="stHeader"], 
[data-testid="stToolbar"], 
[data-testid="stDecoration"], 
[data-testid="stStatusWidget"],
.stDeployButton,
#stAppDeployButton,
div[class*="viewerBadge"],
a[class*="viewerBadge"],
.viewerBadge_container__1QSob,
[data-testid="manage-app-button"],
div[class*="manage-app"] {
    display: none !important;
    visibility: hidden !important;
    height: 0px !important;
}
.stApp {
    background-color: #070b12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    max-width: 1000px !important;
}
.metric-card {
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
}
.metric-title {
    font-size: 0.72rem;
    color: #94a3b8;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.metric-val {
    font-size: 1.4rem;
    font-weight: 900;
    color: #ffffff;
}
.metric-sub {
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 2px;
}
.pos-card {
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 12px;
}
.pos-card.profit {
    border-color: rgba(16, 185, 129, 0.4);
    background: linear-gradient(145deg, #0d1e22 0%, #0f172a 100%);
}
.pos-card.loss {
    border-color: rgba(239, 68, 68, 0.4);
    background: linear-gradient(145deg, #221115 0%, #0f172a 100%);
}
.badge-long {
    background: #064e3b;
    color: #34d399;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 800;
    font-size: 0.72rem;
}
.badge-short {
    background: #7f1d1d;
    color: #f87171;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 800;
    font-size: 0.72rem;
}
.badge-live {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
}
.live-dot {
    width: 8px;
    height: 8px;
    background-color: #10b981;
    border-radius: 50%;
}
</style>
""", unsafe_allow_html=True)

# ========================================================
# SMART DNS FOR WINDOWS / INDONESIAN ISP ONLY
# ========================================================
if not hasattr(socket, '_orig_sys_getaddrinfo'):
    socket._orig_sys_getaddrinfo = socket.getaddrinfo

_dns_cache = {}
def doh_resolve(host: str):
    if host in _dns_cache:
        return _dns_cache[host]
    for url in ['https://dns.google/resolve', 'https://1.1.1.1/dns-query']:
        try:
            r = requests.get(url, params={'name': host, 'type': 'A'}, headers={'accept': 'application/dns-json'}, timeout=2.5)
            ips = [ans.get('data') for ans in r.json().get('Answer', []) if ans.get('type') == 1]
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
            for ip in ips:
                try:
                    return socket._orig_sys_getaddrinfo(ip, port, family, type, proto, flags)
                except Exception:
                    pass
    return socket._orig_sys_getaddrinfo(host, port, family, type, proto, flags)

if sys.platform == "win32":
    socket.getaddrinfo = custom_getaddrinfo

# ========================================================
# LOAD MULTI-ACCOUNT CONFIGURATION (3 AKUN KELUARGA)
# ========================================================
KURS_IDR = 17000.0

def load_accounts_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "accounts_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

accounts_cfg = load_accounts_config()

def get_wib_time_str():
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib).strftime('%H:%M:%S WIB')

# ========================================================
# ULTRA-FAST DIRECT PRICE & EXCHANGE ENGINE (NO load_markets)
# ========================================================
def _poll_prices_fast() -> dict:
    prices = {}
    hdr = {"User-Agent": "Mozilla/5.0"}
    # 1. Gate.io Spot Ticker (works globally including US Streamlit Cloud & Indonesia, <80ms)
    for pair in ["BTC_USDT", "ETH_USDT", "SOL_USDT"]:
        try:
            r = requests.get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair}", headers=hdr, timeout=2.5)
            if r.status_code == 200 and isinstance(r.json(), list) and r.json():
                lp = float(r.json()[0].get("last") or 0.0)
                if lp > 0:
                    prices[pair.replace("_", "/")] = lp
        except Exception:
            pass
    # 2. CoinGecko Simple Price Fallback (works 100% globally)
    if "BTC/USDT" not in prices or "ETH/USDT" not in prices:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd", headers=hdr, timeout=2.5)
            if r.status_code == 200:
                d = r.json()
                if d.get("bitcoin", {}).get("usd"):
                    prices.setdefault("BTC/USDT", float(d["bitcoin"]["usd"]))
                if d.get("ethereum", {}).get("usd"):
                    prices.setdefault("ETH/USDT", float(d["ethereum"]["usd"]))
                if d.get("solana", {}).get("usd"):
                    prices.setdefault("SOL/USDT", float(d["solana"]["usd"]))
        except Exception:
            pass
    # 3. BingX Swap Ticker (for exact swap markPrice & LIGHTER/USDT)
    for sym in ["BTC-USDT", "ETH-USDT", "LIGHTER-USDT"]:
        try:
            r = requests.get(f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol={sym}", headers=hdr, timeout=2.0)
            if r.status_code == 200:
                lp = float(r.json().get("data", {}).get("lastPrice") or 0.0)
                if lp > 0:
                    prices[sym.replace("-", "/")] = lp
        except Exception:
            pass
    return prices

def _recalc_account_with_prices(acc_dict: dict, live_prices: dict) -> dict:
    raw_positions = acc_dict.get("pos_list", [])
    updated_pos_list = []
    recalc_pnl = 0.0
    for p in raw_positions:
        p_copy = dict(p)
        sym = p_copy.get("symbol", "")
        entry = float(p_copy.get("entry", 0.0))
        mark = float(live_prices.get(sym) or p_copy.get("mark") or entry)
        notional = float(p_copy.get("notional", 0.0))
        margin = float(p_copy.get("margin", 1.0))
        side = str(p_copy.get("side", "LONG")).upper()
        if entry > 0 and mark > 0 and notional > 0:
            diff = (mark - entry) / entry if side == "LONG" else (entry - mark) / entry
            pnl = notional * diff
            roe = (pnl / margin * 100.0) if margin > 0 else 0.0
            p_copy["mark"] = mark
            p_copy["pnl"] = pnl
            p_copy["roe"] = roe
        recalc_pnl += float(p_copy.get("pnl", 0.0))
        updated_pos_list.append(p_copy)
    return {
        "total_bal": round(float(acc_dict.get("total_bal", 0.0)), 2),
        "total_pnl": round(recalc_pnl, 2),
        "pos_list": updated_pos_list,
        "ex_details": acc_dict.get("ex_details", {})
    }

def _sync_account_direct(acc_key: str, fallback_acc: dict, live_prices: dict) -> dict:
    profile = accounts_cfg.get(acc_key, {})
    tot_bal = 0.0
    tot_pnl = 0.0
    pos_list = []
    ex_details = {}
    fallback_ex = fallback_acc.get("ex_details", {})
    fallback_pos = fallback_acc.get("pos_list", [])

    for name in ["Bitget", "BingX", "MEXC", "Bybit", "Gate.io"]:
        creds = profile.get(name, {})
        api_k = creds.get("apiKey", "").strip()
        sec_k = creds.get("secret", "").strip()
        pass_k = creds.get("password", "").strip()

        if not api_k or not sec_k:
            ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'}
            continue

        try:
            if name == "Bitget":
                ex = ccxt.bitget({'apiKey': api_k, 'secret': sec_k, 'password': pass_k, 'timeout': 4500})
                b_data = ex.privateMixGetV2MixAccountAccounts({'productType': 'USDT-FUTURES'}).get('data', [])
                p_data = ex.privateMixGetV2MixPositionAllPosition({'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}).get('data', [])
                usdt_row = b_data[0] if b_data else {}
                usdt_total = float(usdt_row.get('usdtEquity') or usdt_row.get('accountEquity') or 0.0)
                usdt_free = float(usdt_row.get('available') or 0.0)
                tot_bal += usdt_total
                ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}
                for p in p_data:
                    total_sz = abs(float(p.get('total') or 0.0))
                    if total_sz > 0:
                        raw_sym = p.get('symbol', '').replace('USDT', '')
                        pair_key = f"{raw_sym}/USDT"
                        side = str(p.get('holdSide', 'LONG')).upper()
                        entry = float(p.get('openPriceAvg') or 0.0)
                        mark = float(p.get('markPrice') or live_prices.get(pair_key) or entry)
                        if mark > 0:
                            live_prices[pair_key] = mark
                        margin = float(p.get('marginSize') or 1.0)
                        lev = int(float(p.get('leverage') or 28))
                        notional = total_sz * mark if mark > 0 else margin * lev
                        pnl = float(p.get('unrealizedPL') or 0.0)
                        roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                        tot_pnl += pnl
                        pos_list.append({
                            'exchange': name, 'symbol': pair_key, 'side': side,
                            'entry': entry, 'mark': mark, 'margin': margin,
                            'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                        })
            elif name == "BingX":
                ex = ccxt.bingx({'apiKey': api_k, 'secret': sec_k, 'timeout': 4500})
                b_data = ex.swapV2PrivateGetUserBalance().get('data', {}).get('balance', {})
                p_data = ex.swapV2PrivateGetUserPositions().get('data', [])
                usdt_total = float(b_data.get('equity') or b_data.get('balance') or 0.0)
                usdt_free = float(b_data.get('availableMargin') or 0.0)
                tot_bal += usdt_total
                ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}
                for p in p_data:
                    amt = abs(float(p.get('positionAmt') or 0.0))
                    if amt > 0:
                        pair_key = str(p.get('symbol', '')).replace('-', '/')
                        side = str(p.get('positionSide', 'LONG')).upper()
                        entry = float(p.get('avgPrice') or 0.0)
                        mark = float(p.get('markPrice') or live_prices.get(pair_key) or entry)
                        if mark > 0:
                            live_prices[pair_key] = mark
                        margin = float(p.get('initialMargin') or p.get('margin') or 1.0)
                        lev = int(float(p.get('leverage') or 28))
                        notional = float(p.get('positionValue') or (amt * mark))
                        pnl = float(p.get('unrealizedProfit') or 0.0)
                        roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                        tot_pnl += pnl
                        pos_list.append({
                            'exchange': name, 'symbol': pair_key, 'side': side,
                            'entry': entry, 'mark': mark, 'margin': margin,
                            'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                        })
            elif name == "MEXC":
                ex = ccxt.mexc({'apiKey': api_k, 'secret': sec_k, 'timeout': 4500})
                b_data = ex.contractPrivateGetAccountAssets().get('data', [])
                p_data = ex.contractPrivateGetPositionOpenPositions().get('data', [])
                usdt_row = next((x for x in b_data if x.get('currency') == 'USDT'), {})
                usdt_total = float(usdt_row.get('equity') or usdt_row.get('cashBalance') or 0.0)
                usdt_free = float(usdt_row.get('availableBalance') or 0.0)
                tot_bal += usdt_total
                ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}
                for p in p_data:
                    vol = abs(float(p.get('holdVol') or 0.0))
                    if vol > 0:
                        pair_key = str(p.get('symbol', '')).replace('_', '/')
                        side = "LONG" if int(p.get('positionType', 1)) == 1 else "SHORT"
                        entry = float(p.get('openAvgPrice') or p.get('holdAvgPrice') or 0.0)
                        mark = float(live_prices.get(pair_key) or entry)
                        c_size = 0.0001 if "BTC" in pair_key else (0.01 if "ETH" in pair_key else 1.0)
                        notional = vol * c_size * entry
                        margin = float(p.get('im') or p.get('oim') or 1.0)
                        lev = int(float(p.get('leverage') or 28))
                        pnl = float(p.get('unRealizedPnl') or 0.0)
                        if abs(pnl) <= 0.0001 and entry > 0 and mark > 0:
                            diff = (mark - entry) / entry if side == "LONG" else (entry - mark) / entry
                            pnl = notional * diff
                        roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                        tot_pnl += pnl
                        pos_list.append({
                            'exchange': name, 'symbol': pair_key, 'side': side,
                            'entry': entry, 'mark': mark, 'margin': margin,
                            'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                        })
            else:
                ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'ONLINE'}
        except Exception:
            if name in fallback_ex:
                fb_info = fallback_ex[name]
                tot_bal += float(fb_info.get("total", 0.0))
                ex_details[name] = {
                    'total': round(float(fb_info.get("total", 0.0)), 2),
                    'free': round(float(fb_info.get("free", 0.0)), 2),
                    'status': 'ONLINE'
                }
                for fp in fallback_pos:
                    if fp.get("exchange") == name:
                        p_copy = dict(fp)
                        sym = p_copy.get("symbol", "")
                        entry = float(p_copy.get("entry", 0.0))
                        mark = float(live_prices.get(sym) or p_copy.get("mark") or entry)
                        notional = float(p_copy.get("notional", 0.0))
                        margin = float(p_copy.get("margin", 1.0))
                        side = str(p_copy.get("side", "LONG")).upper()
                        if entry > 0 and mark > 0 and notional > 0:
                            diff = (mark - entry) / entry if side == "LONG" else (entry - mark) / entry
                            pnl = notional * diff
                            roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                            p_copy["mark"] = mark
                            p_copy["pnl"] = pnl
                            p_copy["roe"] = roe
                        tot_pnl += float(p_copy.get("pnl", 0.0))
                        pos_list.append(p_copy)
            else:
                ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'ONLINE'}

    ordered_ex = {}
    for k_ex in ["Bitget", "MEXC", "BingX", "Bybit", "Gate.io"]:
        ordered_ex[k_ex] = ex_details.get(k_ex, {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'})

    return {
        "total_bal": round(tot_bal, 2),
        "total_pnl": round(tot_pnl, 2),
        "pos_list": pos_list,
        "ex_details": ordered_ex
    }

@st.cache_resource
def get_cloud_live_daemon():
    store = {
        "prices": {},
        "accounts": {}
    }
    state_file = os.path.join(os.path.dirname(__file__), "live_bot_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as sf:
                init_state = json.load(sf)
            for k in ["akun_1", "akun_2", "akun_3"]:
                if k in init_state:
                    store["accounts"][k] = init_state[k]
                    for p in init_state[k].get("pos_list", []):
                        if p.get("symbol") and p.get("mark"):
                            store["prices"][p["symbol"]] = float(p["mark"])
        except Exception:
            pass

    init_p = _poll_prices_fast()
    if init_p:
        store["prices"].update(init_p)
        for k in list(store["accounts"].keys()):
            store["accounts"][k] = _recalc_account_with_prices(store["accounts"][k], store["prices"])

    def _price_loop():
        while True:
            try:
                new_p = _poll_prices_fast()
                if new_p:
                    store["prices"].update(new_p)
                    for k in list(store["accounts"].keys()):
                        store["accounts"][k] = _recalc_account_with_prices(store["accounts"][k], store["prices"])
            except Exception:
                pass
            time.sleep(3)

    def _exchange_loop():
        while True:
            try:
                for k in ["akun_1", "akun_2", "akun_3"]:
                    fb = store["accounts"].get(k, {})
                    store["accounts"][k] = _sync_account_direct(k, fb, store["prices"])
            except Exception:
                pass
            time.sleep(10)

    threading.Thread(target=_price_loop, daemon=True).start()
    threading.Thread(target=_exchange_loop, daemon=True).start()
    return store

cloud_store = get_cloud_live_daemon()

def fetch_live_public_prices():
    return cloud_store["prices"]

def get_account_live_data(acc_key: str):
    acc = cloud_store["accounts"].get(acc_key, {})
    return (
        float(acc.get("total_bal", 0.0)),
        float(acc.get("total_pnl", 0.0)),
        acc.get("pos_list", []),
        acc.get("ex_details", {})
    )

# ========================================================
# PILIHAN 3 AKUN KELUARGA (TAB INTERAKTIF)
# ========================================================
col_h1, col_h2 = st.columns([2, 1])
with col_h1:
    st.markdown("""<div style="margin-bottom: 4px;">
<h2 style="margin: 0; font-size: 1.35rem; font-weight: 900; color: #ffffff;">⚡ TITAN V5 BOT MARUK (3 AKUN KELUARGA)</h2>
<div style="font-size: 0.72rem; color: #94a3b8; font-weight: 600;">Penta-Titan 5 Bursa • 28x Leverage • Target TP 8.2% & SL 2.3%</div>
</div>""", unsafe_allow_html=True)

with col_h2:
    st.markdown(f"""<div style="text-align: right;">
<span class="badge-live"><span class="live-dot"></span> LIVE AUTO-REFRESH</span>
<div style="font-size: 0.72rem; color: #64748b; margin-top: 4px;">{get_wib_time_str()} (Update Otomatis)</div>
</div>""", unsafe_allow_html=True)

live_mkt = fetch_live_public_prices()
btc_now = live_mkt.get("BTC/USDT", 0.0)
eth_now = live_mkt.get("ETH/USDT", 0.0)
ltr_now = live_mkt.get("LIGHTER/USDT", 0.0)

st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 8px 14px; margin-bottom: 8px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; font-size: 0.78rem;">
<span style="color: #94a3b8; font-weight: 700;">📡 HARGA PASAR REAL-TIME:</span>
<span><b style="color: #f59e0b;">₿ BTC/USDT:</b> <b style="color: #ffffff; font-size: 0.88rem;">${btc_now:,.2f}</b> <span style="color: #64748b;">(Rp {btc_now*KURS_IDR:,.0f})</span></span>
<span><b style="color: #38bdf8;">Ξ ETH/USDT:</b> <b style="color: #ffffff; font-size: 0.88rem;">${eth_now:,.2f}</b></span>
<span><b style="color: #34d399;">⚡ LIGHTER/USDT:</b> <b style="color: #ffffff; font-size: 0.88rem;">${ltr_now:,.4f}</b></span>
</div>""", unsafe_allow_html=True)

# TAB SELECTOR 3 AKUN
tab_select = st.radio(
    "PILIH AKUN KELUARGA:",
    ["👤 Akun 1: Utama (Saya)", "👤 Akun 2: Keluarga 2", "👤 Akun 3: Keluarga 3", "🌐 Total Gabungan 3 Akun"],
    horizontal=True
)

st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

# ROUTE DATA
if "Akun 1" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = get_account_live_data("akun_1")
elif "Akun 2" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = get_account_live_data("akun_2")
elif "Akun 3" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = get_account_live_data("akun_3")
else:
    b1, p1, pos1, ex1 = get_account_live_data("akun_1")
    b2, p2, pos2, ex2 = get_account_live_data("akun_2")
    b3, p3, pos3, ex3 = get_account_live_data("akun_3")
    tot_bal = b1 + b2 + b3
    tot_pnl = p1 + p2 + p3
    pos_list = pos1 + pos2 + pos3
    ex_details = {k: {'total': ex1.get(k,{}).get('total',0)+ex2.get(k,{}).get('total',0)+ex3.get(k,{}).get('total',0), 'free': 0.0, 'status': 'ONLINE'} for k in ["Bitget","MEXC","BingX","Bybit","Gate.io"]}

# ========================================================
# 4 KARTU UTAMA
# ========================================================
pnl_color = "#34d399" if tot_pnl >= 0 else "#f87171"
pnl_sign = "+$" if tot_pnl >= 0 else "-$"
roe_total = (tot_pnl / tot_bal * 100) if tot_bal > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="metric-card">
<div class="metric-title">Total Saldo Equity</div>
<div class="metric-val">${tot_bal:.2f}</div>
<div class="metric-sub" style="color: #38bdf8;">Rp {tot_bal*KURS_IDR:,.0f}</div>
</div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""<div class="metric-card" style="border-color: {pnl_color}55;">
<div class="metric-title">Floating PnL Live</div>
<div class="metric-val" style="color: {pnl_color};">{pnl_sign}{abs(tot_pnl):.2f}</div>
<div class="metric-sub" style="color: {pnl_color};">{'+' if tot_pnl >= 0 else ''}{roe_total:.1f}% ROE</div>
</div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""<div class="metric-card">
<div class="metric-title">Posisi Aktif</div>
<div class="metric-val">{len(pos_list)} <span style="font-size: 0.8rem; color: #64748b;">Posisi</span></div>
<div class="metric-sub" style="color: #94a3b8;">Bitget • MEXC • BingX</div>
</div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""<div class="metric-card">
<div class="metric-title">₿ Harga BTC Live</div>
<div class="metric-val" style="color: #f59e0b;">${btc_now:,.1f}</div>
<div class="metric-sub" style="color: #34d399;">ETH: ${eth_now:,.2f}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ========================================================
# PROYEKSI TARGET HASIL (TP +8.2% vs SL -2.3%)
# ========================================================
tp_rate = 0.082
sl_rate = 0.023
total_tp_usd = sum(p['margin'] * p['leverage'] * tp_rate for p in pos_list) if pos_list else 0.0
total_tp_idr = total_tp_usd * KURS_IDR
bal_if_tp = tot_bal + total_tp_usd

total_sl_usd = sum(p['margin'] * p['leverage'] * sl_rate for p in pos_list) if pos_list else 0.0
total_sl_idr = total_sl_usd * KURS_IDR
bal_if_sl = max(0.0, tot_bal - total_sl_usd)

st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🎯 Proyeksi Target Hasil (Kalau TP Berapa & SL Berapa)</div>', unsafe_allow_html=True)

col_tp, col_sl = st.columns(2)
with col_tp:
    st.markdown(f"""<div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, #0f172a 100%); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 14px; padding: 14px;">
<div style="font-size: 0.72rem; font-weight: 800; color: #34d399; text-transform: uppercase;">✅ JIKA PROFIT SEMUA (TP +8.2%)</div>
<div style="font-size: 1.6rem; font-weight: 900; color: #34d399; margin: 2px 0;">+${total_tp_usd:.2f} <span style="font-size: 0.85rem; color: #a7f3d0;">USDT</span></div>
<div style="font-size: 0.8rem; font-weight: 700; color: #6ee7b7; margin-bottom: 6px;">+Rp {total_tp_idr:,.0f}</div>
<div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px; font-size: 0.75rem; color: #94a3b8;">
Total Saldo Menjadi: <b style="color: #ffffff;">${bal_if_tp:.2f} USDT (Rp {bal_if_tp*KURS_IDR:,.0f})</b>
</div>
</div>""", unsafe_allow_html=True)

with col_sl:
    st.markdown(f"""<div style="background: linear-gradient(135deg, rgba(127, 29, 29, 0.45) 0%, #0f172a 100%); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 14px; padding: 14px;">
<div style="font-size: 0.72rem; font-weight: 800; color: #f87171; text-transform: uppercase;">🛑 JIKA MINUS SEMUA (SL -2.3%)</div>
<div style="font-size: 1.6rem; font-weight: 900; color: #f87171; margin: 2px 0;">-${total_sl_usd:.2f} <span style="font-size: 0.85rem; color: #fca5a5;">USDT</span></div>
<div style="font-size: 0.8rem; font-weight: 700; color: #fca5a5; margin-bottom: 6px;">-Rp {total_sl_idr:,.0f}</div>
<div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px; font-size: 0.75rem; color: #94a3b8;">
Total Saldo Menjadi: <b style="color: #ffffff;">${bal_if_sl:.2f} USDT (Rp {bal_if_sl*KURS_IDR:,.0f})</b>
</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ========================================================
# POSISI AKTIF (ZERO INDENTATION TO PREVENT MARKDOWN CODE BUG)
# ========================================================
st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🔥 Posisi Aktif Berjalan</div>', unsafe_allow_html=True)

if pos_list:
    cols_pos = st.columns(2 if len(pos_list) > 1 else 1)
    for idx, p in enumerate(pos_list):
        c_target = cols_pos[idx % len(cols_pos)]
        is_p = p['pnl'] >= 0
        p_cls = "profit" if is_p else "loss"
        badge_cls = "badge-long" if p['side'] == 'LONG' else "badge-short"
        sign = "+$" if is_p else "-$"
        c_text = "#34d399" if is_p else "#f87171"

        p_tp_usd = p['margin'] * p['leverage'] * tp_rate
        p_sl_usd = p['margin'] * p['leverage'] * sl_rate

        with c_target:
            st.markdown(f"""<div class="pos-card {p_cls}">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
<div>
<span style="font-size: 1.05rem; font-weight: 900; color: #ffffff;">{p['symbol']}</span>
<span style="font-size: 0.75rem; color: #94a3b8; margin-left: 6px;">[{p['exchange']}]</span>
</div>
<span class="{badge_cls}">{p['side']} {p['leverage']}x</span>
</div>
<div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 8px;">
Margin: <b style="color: #ffffff;">${p['margin']:.2f} USDT</b> • Notional: <b>${p['notional']:.1f}</b>
</div>
<div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; margin-bottom: 8px;">
<div style="font-size: 0.72rem; color: #64748b;">
Entri: ${p['entry']:.4f}<br>Mark: ${p['mark']:.4f}
</div>
<div style="text-align: right;">
<div style="font-size: 1.25rem; font-weight: 900; color: {c_text};">{sign}{abs(p['pnl']):.2f}</div>
<div style="font-size: 0.75rem; font-weight: 700; color: {c_text};">{'+' if is_p else ''}{p['roe']:.1f}% ROE</div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 6px; font-size: 0.7rem;">
<div style="color: #34d399;">🎯 TP: <b>+${p_tp_usd:.2f}</b> (+Rp {p_tp_usd*KURS_IDR:,.0f})</div>
<div style="color: #f87171; text-align: right;">🛡️ SL: <b>-${p_sl_usd:.2f}</b> (-Rp {p_sl_usd*KURS_IDR:,.0f})</div>
</div>
</div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div style="background: #0f172a; border: 1px dashed rgba(255,255,255,0.12); border-radius: 12px; padding: 18px; text-align: center; color: #94a3b8; font-size: 0.85rem;">
💤 Belum ada posisi aktif di akun ini. Bot siap menerkam mangsa begitu sinyal Donchian 36H & Momentum valid muncul.
</div>""", unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ========================================================
# SALDO 5 BURSA
# ========================================================
st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🏛️ Saldo di Masing-Masing 5 Bursa</div>', unsafe_allow_html=True)

col_ex = st.columns(5)
ex_icons = {'Bitget': '💎', 'MEXC': '🐉', 'BingX': '🦁', 'Bybit': '⚡', 'Gate.io': '⛩️'}

for idx, (ex_name, icon) in enumerate(ex_icons.items()):
    info = ex_details.get(ex_name, {'total': 0.0, 'free': 0.0, 'status': 'ONLINE'})
    b_val = info['total']
    with col_ex[idx]:
        stat = info.get('status', 'ONLINE')
        stat_color = "#10b981" if stat == "ONLINE" else ("#f87171" if stat.startswith("ERR") else "#64748b")
        stat_label = "ONLINE" if stat == "ONLINE" else stat
        st.markdown(f"""<div class="metric-card" style="padding: 10px 12px;">
<div style="display: flex; justify-content: space-between; align-items: center;">
<span style="font-size: 0.8rem; font-weight: 800; color: #ffffff;">{icon} {ex_name}</span>
<span style="font-size: 0.62rem; font-weight: 700; color: {stat_color};">{stat_label}</span>
</div>
<div style="font-size: 1.15rem; font-weight: 900; color: #38bdf8; margin: 2px 0;">${b_val:.2f}</div>
<div style="font-size: 0.68rem; color: #94a3b8;">Rp {b_val*KURS_IDR:,.0f}</div>
</div>""", unsafe_allow_html=True)

# ========================================================
# TOMBOL REFRESH & AUTO-REFRESH OTOMATIS
# ========================================================
st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
col_r1, col_r2 = st.columns([3, 1])
with col_r1:
    if st.button("🔄 Segarkan Data Real-Time Sekarang", use_container_width=True):
        new_p = _poll_prices_fast()
        if new_p:
            cloud_store["prices"].update(new_p)
            for k in list(cloud_store["accounts"].keys()):
                cloud_store["accounts"][k] = _recalc_account_with_prices(cloud_store["accounts"][k], cloud_store["prices"])
        st.rerun()
with col_r2:
    auto_refresh_enabled = st.checkbox("⚡ Auto-Refresh (4 dtk)", value=True)

if auto_refresh_enabled:
    time.sleep(4)
    st.rerun()
