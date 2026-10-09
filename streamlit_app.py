import os
import sys
import time
import json
import socket
import urllib.request
import streamlit as st
import ccxt

# Streamlit Page Config - Mobile Optimized
st.set_page_config(
    page_title="⚡ TITAN V5 Live PnL",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Responsive & Clean CSS (Mobile-First + Dark Cyberpunk)
st.markdown("""
<style>
    /* HIDE ALL STREAMLIT CHROME & WATERMARKS */
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

    /* Base Styling */
    .stApp {
        background-color: #070b12;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 1200px !important;
    }

    /* Responsive Grid Layouts */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        margin-bottom: 20px;
    }

    .pos-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 14px;
        margin-bottom: 24px;
    }

    .bal-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 12px;
        margin-bottom: 20px;
    }

    /* Cards */
    .metric-box {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .metric-title {
        font-size: 0.75rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }

    .metric-val {
        font-size: 1.35rem;
        font-weight: 800;
        color: #ffffff;
    }

    .metric-sub {
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 4px;
    }

    /* Position Card */
    .pos-box {
        background: #0f172a;
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
    }

    .pos-box.profit {
        border-color: rgba(16, 185, 129, 0.35);
        background: linear-gradient(145deg, #0e1e24 0%, #0d1527 100%);
    }

    .badge-long {
        background-color: #064e3b;
        color: #34d399;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.75rem;
    }

    .badge-short {
        background-color: #7f1d1d;
        color: #f87171;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.75rem;
    }

    @media (max-width: 640px) {
        .metric-val { font-size: 1.15rem; }
        .pos-grid { grid-template-columns: 1fr; }
        .bal-grid { grid-template-columns: 1fr; }
    }
</style>
""", unsafe_allow_html=True)

# DNS Over HTTPS (DoH) Fallback
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

# API Keys
def get_secret(key, default):
    try: return st.secrets.get(key, default)
    except Exception: return os.getenv(key, default)

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

# Sidebar Controls
with st.sidebar:
    st.title("⚡ Titan V5")
    auto_refresh = st.checkbox("Auto Refresh", value=True)
    refresh_rate = st.slider("Interval (detik)", min_value=3, max_value=30, value=5)
    if st.button("🔄 Refresh Manual"):
        st.rerun()

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

btc_p = live_mark_prices.get('BTC', 81750.0)

# Top Bar Header
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
    <div>
        <h2 style="margin: 0; font-size: 1.4rem; font-weight: 800; color: #fff;">⚡ TITAN V5 MARUK</h2>
        <div style="font-size: 0.75rem; color: #94a3b8;">Multi-Exchange Futures Dashboard</div>
    </div>
    <div style="text-align: right;">
        <span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; margin-right: 4px;"></span>
        <span style="font-size: 0.75rem; color: #34d399; font-weight: 700;">CLOUD ONLINE</span>
        <div style="font-size: 0.7rem; color: #64748b;">{time.strftime('%H:%M:%S WIB')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Top 4 Metrics Grid (Responsive CSS Grid)
roe_total = (tot_pnl / tot_bal * 100) if tot_bal > 0 else 0.0
pnl_color = "#34d399" if tot_pnl >= 0 else "#f87171"

st.markdown(f"""
<div class="metric-grid">
    <div class="metric-box">
        <div class="metric-title">Total Saldo</div>
        <div class="metric-val">${tot_bal:.2f}</div>
        <div class="metric-sub" style="color: #94a3b8;">Rp {tot_bal * 17000:,.0f}</div>
    </div>
    <div class="metric-box">
        <div class="metric-title">Floating PnL</div>
        <div class="metric-val" style="color: {pnl_color};">{'+$' if tot_pnl >= 0 else '-$'}{abs(tot_pnl):.2f}</div>
        <div class="metric-sub" style="color: {pnl_color};">{'+' if tot_pnl >= 0 else ''}{roe_total:.1f}% ROE</div>
    </div>
    <div class="metric-box">
        <div class="metric-title">Posisi Aktif</div>
        <div class="metric-val">{len(pos_list)}</div>
        <div class="metric-sub" style="color: #38bdf8;">BingX • MEXC • Bitget</div>
    </div>
    <div class="metric-box">
        <div class="metric-title">BTC Price</div>
        <div class="metric-val">${btc_p:,.0f}</div>
        <div class="metric-sub" style="color: #fb7185;">EMA 50: $83,200 (BEAR)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Active Positions (Responsive Grid)
st.markdown('<div style="font-size: 1.05rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">🔥 Posisi Aktif Berjalan</div>', unsafe_allow_html=True)

if pos_list:
    cards_html = '<div class="pos-grid">'
    for p in pos_list:
        is_p = p['pnl'] >= 0
        c_pnl = "#34d399" if is_p else "#f87171"
        badge_cls = "badge-long" if p['side'] == 'LONG' else "badge-short"
        sign = "+$" if is_p else "-$"
        roe_sign = "+" if is_p else ""
        cards_html += f'<div class="pos-box profit"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;"><span style="font-weight: 800; font-size: 1.1rem; color: #ffffff;">{p["symbol"]}</span><span class="{badge_cls}">{p["side"]} {p["leverage"]}x</span></div><div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 12px;"><span>{p["exchange"]}</span> • Margin: <b style="color: #f1f5f9;">${p["margin"]:.2f}</b></div><div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 10px;"><div><div style="font-size: 0.72rem; color: #64748b;">Entry: ${p["entry"]:.4f}</div><div style="font-size: 0.72rem; color: #64748b;">Mark: ${p["mark"]:.4f}</div></div><div style="text-align: right;"><div style="font-size: 1.25rem; font-weight: 800; color: {c_pnl};">{sign}{abs(p["pnl"]):.2f}</div><div style="font-size: 0.8rem; font-weight: 700; color: {c_pnl};">{roe_sign}{p["roe"]:.1f}% ROE</div></div></div></div>'
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)
else:
    st.info("Tidak ada posisi yang sedang aktif.")

# Exchange Balances (Responsive Grid)
st.markdown('<div style="font-size: 1.05rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">🏦 Saldo Per Exchange</div>', unsafe_allow_html=True)

bal_html = '<div class="bal-grid">'
for name, d in ex_details.items():
    bal_html += f'<div style="background: #0f172a; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 14px;"><div style="font-weight: 700; font-size: 0.85rem; color: #38bdf8; margin-bottom: 4px;">{name} Futures</div><div style="font-size: 1.35rem; font-weight: 800; color: #f8fafc;">${d.get("total", 0.0):.2f} <span style="font-size: 0.75rem; color: #94a3b8;">USDT</span></div><div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">Tersedia: ${d.get("free", 0.0):.2f} USDT</div></div>'
bal_html += '</div>'
st.markdown(bal_html, unsafe_allow_html=True)

# Auto Refresh loop
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
