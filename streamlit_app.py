import os
import sys
import time
import json
import socket
import urllib.request
import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go

# Streamlit Page Config
st.set_page_config(
    page_title="⚡ TITAN V5 - Live PnL Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Cyberpunk / Dark Glow Theme
st.markdown("""
<style>
    .stApp {
        background-color: #080c14;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    /* Sembunyikan Header Atas & Toolbar (Stop, Share, GitHub, Menu) */
    header, [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, div[data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    /* Sembunyikan Footer & Watermark Powered by Streamlit */
    footer, [data-testid="stFooter"], div[class*="viewerBadge"], .viewerBadge_container__1QSob, [data-testid="manage-app-button"] {
        display: none !important;
        visibility: hidden !important;
    }
    /* Rapikan padding konten paling atas */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 12px;
        backdrop-filter: blur(12px);
    }
    .glow-green {
        border-color: rgba(16, 185, 129, 0.4);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
    }
    .pos-card {
        background: #0d1527;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
    }
    .badge-long {
        background-color: #064e3b;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-short {
        background-color: #7f1d1d;
        color: #f87171;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# DNS Over HTTPS (DoH) fallback for cloud bypass if needed
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}

def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    url = f"https://1.1.1.1/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
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
                try: res.extend(_orig_getaddrinfo(ip, port, family, type, proto, flags))
                except: pass
            if res: return res
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

# API Keys from Streamlit Secrets or Environment Defaults
def get_secret(key, default):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return os.getenv(key, default)

BINGX_API_KEY = get_secret("BINGX_API_KEY", "Qj7bWpsS6Z2QpHWe2RZSjeJHPVOK3fXikkAj96qKk1VglGfiJwiTJwRtqGPHlMBWCM7UeutRdnvVfM2UQFR1w")
BINGX_SECRET = get_secret("BINGX_SECRET", "KMG9wbpdVtAoS7Hny9RssesIldiqav2PqqlQ9gdI5x2scLeoU2nXi770Uak0r2xL62IIzyr8gVaAEd0Zr9H8g")

MEXC_API_KEY = get_secret("MEXC_API_KEY", "mx0vgluY6in6XqNKrs")
MEXC_SECRET = get_secret("MEXC_SECRET", "cdd41089eba04fa3adb49b18b89918a0")

BITGET_API_KEY = get_secret("BITGET_API_KEY", "bg_7acb820c501a147ef31fd30ebae0fd3c")
BITGET_SECRET = get_secret("BITGET_SECRET", "b1745c9d60e4f521123ff313d3532994d706c161298add70e1f3e5e1284a9fee")
BITGET_PASSPHRASE = get_secret("BITGET_PASSPHRASE", "botmarukjosss")

@st.cache_resource
def init_exchanges():
    return {
        'BingX': ccxt.bingx({
            'apiKey': BINGX_API_KEY,
            'secret': BINGX_SECRET,
            'options': {'defaultType': 'swap'},
            'enableRateLimit': True,
            'timeout': 10000,
        }),
        'MEXC': ccxt.mexc({
            'apiKey': MEXC_API_KEY,
            'secret': MEXC_SECRET,
            'options': {'defaultType': 'swap'},
            'enableRateLimit': True,
            'timeout': 10000,
        }),
        'Bitget': ccxt.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_SECRET,
            'password': BITGET_PASSPHRASE,
            'options': {'defaultType': 'swap'},
            'enableRateLimit': True,
            'timeout': 10000,
        })
    }

exchanges = init_exchanges()

# Sidebar
with st.sidebar:
    st.title("⚡ Titan V5 Maruk")
    st.caption("Live Cloud Multi-Exchange Monitor")
    
    auto_refresh = st.checkbox("Auto Refresh (Setiap 5 detik)", value=True)
    refresh_rate = st.slider("Interval (detik)", min_value=3, max_value=30, value=5)
    
    if st.button("🔄 Refresh Manual"):
        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Akun Terhubung")
    st.write("🟢 **BingX Futures**")
    st.write("🟢 **MEXC Futures**")
    st.write("🟢 **Bitget Futures**")
    st.markdown("---")
    st.caption("Versi Cloud: 24/7 Persistent")

# Fetch Real-Time Data
tot_bal = 0.0
tot_pnl = 0.0
pos_list = []
ex_details = {}

live_mark_prices = {'BTC': 81750.0, 'ETH': 2470.0, 'XRP': 1.38, 'ADA': 0.234, 'AVAX': 10.15, 'LINK': 12.76}

for name, ex in exchanges.items():
    try:
        raw_pos = ex.fetch_positions()
        for p in raw_pos:
            sym_u = p.get('symbol', '')
            m_p = float(p.get('markPrice') or p.get('info', {}).get('fairPrice') or 0.0)
            for c in ['BTC', 'ETH', 'XRP', 'ADA', 'AVAX', 'LINK']:
                if c in sym_u and m_p > 0:
                    live_mark_prices[c] = m_p
    except:
        pass

for name, ex in exchanges.items():
    try:
        bal = ex.fetch_balance()
        usdt_total = bal.get('USDT', {}).get('total', 0.0) or bal.get('free', {}).get('USDT', 0.0) or 0.0
        usdt_free = bal.get('USDT', {}).get('free', 0.0) or usdt_total
        tot_bal += usdt_total
        ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2)}

        raw_pos = ex.fetch_positions()
        for p in raw_pos:
            contracts = abs(float(p.get('contracts') or p.get('amount') or 0.0))
            if contracts > 0:
                sym = p.get('symbol', 'UNKNOWN')
                clean_sym = sym.replace(':USDT', '').replace('/USDT', '')
                side = str(p.get('side', '')).upper()
                entry = float(p.get('entryPrice') or p.get('info', {}).get('openAvgPrice') or 0.0)
                lev = float(p.get('leverage') or 28)

                c_size = float(p.get('contractSize') or p.get('info', {}).get('contractSize') or 1.0)
                if name == 'MEXC':
                    if 'BTC' in sym: c_size = 0.0001
                    elif 'ETH' in sym: c_size = 0.01

                real_notional = contracts * c_size * entry
                margin = (real_notional / lev) if lev > 0 else 1.0

                mark = float(p.get('markPrice') or p.get('info', {}).get('fairPrice') or 0.0)
                if mark <= 0:
                    for c_key, c_val in live_mark_prices.items():
                        if c_key in clean_sym:
                            mark = c_val
                            break
                if mark <= 0: mark = entry

                pnl = float(p.get('unrealizedPnl') or p.get('info', {}).get('floatingPL') or p.get('info', {}).get('unrealisedPnl') or 0.0)
                if abs(pnl) <= 0.0001 and entry > 0 and mark > 0 and real_notional > 0:
                    diff = (mark - entry)/entry if side == 'LONG' else (entry - mark)/entry
                    pnl = real_notional * diff

                roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                tot_pnl += pnl

                pos_list.append({
                    'exchange': name,
                    'symbol': clean_sym + '/USDT',
                    'side': side,
                    'entry': entry,
                    'mark': mark,
                    'margin': margin,
                    'pnl': pnl,
                    'roe': roe,
                    'leverage': int(lev)
                })
    except Exception as err:
        ex_details[name] = {'total': 0.0, 'free': 0.0, 'error': str(err)}

# Top Metrics Row
st.title("⚡ TITAN V5 — LIVE TRADING DASHBOARD")
st.caption(f"Terakhir diperbarui: {time.strftime('%H:%M:%S WIB')} | Status Cloud: ONLINE 🟢")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Saldo Portofolio",
        value=f"${tot_bal:.2f} USDT",
        delta=f"Rp {tot_bal * 17000:,.0f}"
    )

with col2:
    st.metric(
        label="Total Floating PnL",
        value=f"+${tot_pnl:.2f} USDT" if tot_pnl >= 0 else f"-${abs(tot_pnl):.2f} USDT",
        delta=f"+{(tot_pnl/tot_bal*100) if tot_bal > 0 else 0:.1f}% ROE",
        delta_color="normal" if tot_pnl >= 0 else "inverse"
    )

with col3:
    st.metric(
        label="Posisi Aktif Berjalan",
        value=f"{len(pos_list)} Posisi",
        delta="3 Exchange (BingX, MEXC, Bitget)"
    )

with col4:
    btc_p = live_mark_prices.get('BTC', 81750.0)
    st.metric(
        label="BTC Macro Trend",
        value=f"${btc_p:,.1f}",
        delta="EMA 50: $83,200 (BEARISH)"
    )

st.markdown("---")

# Active Positions Table / Cards
st.subheader("🔥 Posisi Aktif Berjalan (Live Floating Profit)")

if pos_list:
    cols = st.columns(min(len(pos_list), 3))
    for idx, p in enumerate(pos_list):
        c = cols[idx % 3]
        with c:
            is_profit = p['pnl'] >= 0
            pnl_color = "#34d399" if is_profit else "#f87171"
            bg_color = "rgba(16, 185, 129, 0.1)" if is_profit else "rgba(239, 68, 68, 0.1)"
            border_color = "rgba(16, 185, 129, 0.3)" if is_profit else "rgba(239, 68, 68, 0.3)"
            
            st.markdown(f"""
            <div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 800; font-size: 1.1rem; color: #fff;">{p['symbol']}</span>
                    <span class="{'badge-long' if p['side'] == 'LONG' else 'badge-short'}">{p['side']} {p['leverage']}x</span>
                </div>
                <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;">
                    Exchange: <b style="color: #cbd5e1;">{p['exchange']}</b> | Margin: <b style="color: #cbd5e1;">${p['margin']:.2f}</b>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                    <div>
                        <div style="font-size: 0.75rem; color: #64748b;">Entry: ${p['entry']:.4f}</div>
                        <div style="font-size: 0.75rem; color: #64748b;">Mark: ${p['mark']:.4f}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.25rem; font-weight: 800; color: {pnl_color};">
                            {'+$' if is_profit else '-$'}{abs(p['pnl']):.2f}
                        </div>
                        <div style="font-size: 0.85rem; font-weight: 700; color: {pnl_color};">
                            {'+' if is_profit else ''}{p['roe']:.1f}% ROE
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Belum ada posisi futures yang aktif saat ini.")

st.markdown("---")

# Balances per Exchange
st.subheader("🏦 Saldo Per Exchange")
bal_cols = st.columns(3)
for idx, (name, d) in enumerate(ex_details.items()):
    with bal_cols[idx]:
        st.markdown(f"""
        <div style="background: #0f172a; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px;">
            <div style="font-weight: 700; font-size: 1rem; color: #38bdf8; margin-bottom: 6px;">{name} Futures</div>
            <div style="font-size: 1.5rem; font-weight: 800; color: #f1f5f9;">${d.get('total', 0.0):.2f} <span style="font-size: 0.9rem; color: #94a3b8;">USDT</span></div>
            <div style="font-size: 0.8rem; color: #64748b; margin-top: 4px;">Tersedia (Free): ${d.get('free', 0.0):.2f} USDT</div>
        </div>
        """, unsafe_allow_html=True)

# Auto refresh script loop
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
