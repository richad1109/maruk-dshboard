import os
import sys
import time
import socket
import json
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

KURS_IDR = 17000.0

def fmt_price(val: float) -> str:
    if val >= 1000:
        return f"${val:,.1f}"
    elif val >= 10:
        return f"${val:,.2f}"
    return f"${val:,.4f}"

def get_wib_time_str():
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib).strftime('%H:%M:%S WIB')

# ========================================================
# PARALLEL REAL-TIME PRICE ENGINE (90ms, US & ID COMPATIBLE)
# ========================================================
def _fetch_url_json(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=2.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=2)
def fetch_live_prices_v6() -> dict:
    prices = {}
    urls = {
        "gate_btc": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT",
        "gate_eth": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=ETH_USDT",
        "kraken": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD",
        "coingecko": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
        "bingx_btc": "https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol=BTC-USDT",
        "bingx_eth": "https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol=ETH-USDT",
        "bingx_ltr": "https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol=LIGHTER-USDT",
    }
    results = {}
    with ThreadPoolExecutor(max_workers=7) as pool:
        future_map = {pool.submit(_fetch_url_json, u): k for k, u in urls.items()}
        for fut, k in future_map.items():
            try:
                results[k] = fut.result(timeout=2.2)
            except Exception:
                results[k] = None

    # 1. CoinGecko fallback
    cg = results.get("coingecko")
    if isinstance(cg, dict):
        if cg.get("bitcoin", {}).get("usd"):
            prices["BTC/USDT"] = float(cg["bitcoin"]["usd"])
        if cg.get("ethereum", {}).get("usd"):
            prices["ETH/USDT"] = float(cg["ethereum"]["usd"])

    # 2. Kraken US Official Exchange Ticker (override if available)
    kr = results.get("kraken")
    if isinstance(kr, dict) and isinstance(kr.get("result"), dict):
        res_k = kr["result"]
        for k_pair, k_val in res_k.items():
            if "XBT" in k_pair and isinstance(k_val, dict) and k_val.get("c"):
                prices["BTC/USDT"] = float(k_val["c"][0])
            elif "ETH" in k_pair and isinstance(k_val, dict) and k_val.get("c"):
                prices["ETH/USDT"] = float(k_val["c"][0])

    # 3. Gate.io Spot (override with exact USDT pair)
    g_btc = results.get("gate_btc")
    if isinstance(g_btc, list) and g_btc and g_btc[0].get("last"):
        prices["BTC/USDT"] = float(g_btc[0]["last"])
    g_eth = results.get("gate_eth")
    if isinstance(g_eth, list) and g_eth and g_eth[0].get("last"):
        prices["ETH/USDT"] = float(g_eth[0]["last"])

    # 4. BingX Swap (if not US-blocked, gives exact futures mark/last price + LIGHTER/USDT)
    for k_bx, sym_name in [("bingx_btc", "BTC/USDT"), ("bingx_eth", "ETH/USDT"), ("bingx_ltr", "LIGHTER/USDT")]:
        bx = results.get(k_bx)
        if isinstance(bx, dict) and isinstance(bx.get("data"), dict):
            lp = float(bx["data"].get("lastPrice") or 0.0)
            if lp > 0:
                prices[sym_name] = lp

    return prices

# ========================================================
# LOAD & RECALCULATE ACCOUNT DATA IN <0.1 SECONDS
# ========================================================
@st.cache_data(ttl=2)
def get_all_accounts_live_v6():
    live_prices = fetch_live_prices_v6()
    state_data = {}

    # 1. Load local live_bot_state.json immediately (0.001s)
    state_file = os.path.join(os.path.dirname(__file__), "live_bot_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as sf:
                state_data = json.load(sf)
        except Exception:
            state_data = {}

    # 2. Check GitHub raw state (with fast 1.5s timeout) in case remote was updated
    try:
        r = requests.get(
            f"https://raw.githubusercontent.com/richad1109/maruk-dshboard/main/live_bot_state.json?t={int(time.time()//5)}",
            headers={"Cache-Control": "no-cache"},
            timeout=1.5
        )
        if r.status_code == 200:
            rem = r.json()
            if isinstance(rem, dict) and "akun_1" in rem:
                r_ts = rem.get("akun_1", {}).get("updated_at", "")
                l_ts = state_data.get("akun_1", {}).get("updated_at", "")
                if r_ts >= l_ts:
                    state_data = rem
    except Exception:
        pass

    # Extract any missing coin marks from state_data
    for acc_k in ["akun_1", "akun_2", "akun_3"]:
        for p in state_data.get(acc_k, {}).get("pos_list", []):
            sym = p.get("symbol", "")
            if sym and sym not in live_prices and p.get("mark"):
                live_prices[sym] = float(p["mark"])

    # Recalculate every position's Mark, PnL, and ROE with real-time prices
    final_accounts = {}
    for acc_k in ["akun_1", "akun_2", "akun_3"]:
        acc = state_data.get(acc_k, {})
        raw_positions = acc.get("pos_list", [])
        updated_pos = []
        recalc_pnl = 0.0
        old_pnl = float(acc.get("total_pnl", 0.0))
        base_bal = float(acc.get("total_bal", 0.0)) - old_pnl

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
            updated_pos.append(p_copy)

        live_equity = round(base_bal + recalc_pnl, 2)
        final_accounts[acc_k] = (
            live_equity,
            round(recalc_pnl, 2),
            updated_pos,
            acc.get("ex_details", {})
        )

    return live_prices, final_accounts

live_mkt, all_acc_data = get_all_accounts_live_v6()
btc_now = live_mkt.get("BTC/USDT", 83788.1)
eth_now = live_mkt.get("ETH/USDT", 2559.57)
ltr_now = live_mkt.get("LIGHTER/USDT", 3.847)

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

st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 8px 14px; margin-bottom: 8px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; font-size: 0.78rem;">
<span style="color: #94a3b8; font-weight: 700;">📡 HARGA PASAR REAL-TIME:</span>
<span><b style="color: #f59e0b;">₿ BTC/USDT:</b> <b style="color: #ffffff; font-size: 0.88rem;">${btc_now:,.1f}</b> <span style="color: #64748b;">(Rp {btc_now*KURS_IDR:,.0f})</span></span>
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

# ROUTE DATA (INSTANT 0.001s FROM MEMORY)
if "Akun 1" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = all_acc_data["akun_1"]
elif "Akun 2" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = all_acc_data["akun_2"]
elif "Akun 3" in tab_select:
    tot_bal, tot_pnl, pos_list, ex_details = all_acc_data["akun_3"]
else:
    b1, p1, pos1, ex1 = all_acc_data["akun_1"]
    b2, p2, pos2, ex2 = all_acc_data["akun_2"]
    b3, p3, pos3, ex3 = all_acc_data["akun_3"]
    tot_bal = round(b1 + b2 + b3, 2)
    tot_pnl = round(p1 + p2 + p3, 2)
    pos_list = pos1 + pos2 + pos3
    ex_details = {k: {'total': round(ex1.get(k,{}).get('total',0)+ex2.get(k,{}).get('total',0)+ex3.get(k,{}).get('total',0), 2), 'free': 0.0, 'status': 'ONLINE'} for k in ["Bitget","MEXC","BingX","Bybit","Gate.io"]}

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
<div class="metric-sub" style="color: #38bdf8;">ETH: ${eth_now:,.2f}</div>
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
# POSISI AKTIF (ZERO INDENTATION & SMART PRICE FORMAT)
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
        e_str = fmt_price(float(p['entry']))
        m_str = fmt_price(float(p['mark']))

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
<div style="font-size: 0.72rem; color: #94a3b8;">
Entri: <b style="color: #cbd5e1;">{e_str}</b><br>Mark: <b style="color: #f8fafc;">{m_str}</b>
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
        st.cache_data.clear()
        st.rerun()
with col_r2:
    auto_refresh_enabled = st.checkbox("⚡ Auto-Refresh (4 dtk)", value=True)

if auto_refresh_enabled:
    time.sleep(4)
    st.rerun()
