import os
import sys
import time
import socket
import urllib.request
import json
import streamlit as st
import ccxt

# ========================================================
# STREAMLIT PAGE CONFIGURATION - SIMPLE, CLEAN & FAST
# ========================================================
st.set_page_config(
    page_title="⚡ TITAN V5 Live PnL",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========================================================
# MINIMALIST MODERN CSS (MOBILE FIRST, DARK & CLEAN)
# ========================================================
st.markdown("""
<style>
    /* HIDE STREAMLIT CHROME & WATERMARKS */
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

    /* CARD STYLES */
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

    /* POSITION CARD */
    .pos-card {
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
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
# DNS OVER HTTPS (DoH) & API SECRETS
# ========================================================
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}

def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    url = f"https://1.1.1.1/dns-query?name={host}&type=A"
import requests

def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        r = requests.get('https://1.1.1.1/dns-query', params={'name': host, 'type': 'A'}, headers={'accept': 'application/dns-json'}, timeout=4)
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
            res = []
            for ip in ips:
                try: res.extend(_orig_getaddrinfo(ip, port, family, type, proto, flags))
                except: pass
            if res: return res
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

def get_secret(key, default=""):
    try: return st.secrets.get(key, default)
    except Exception: return os.getenv(key, default)

BINGX_API_KEY = get_secret("BINGX_API_KEY", "Qj7bWpsS6Z2QpHWe2RZSjeJHPVOK3fXikkAj96qKk1VglGfiJwiTJwRtqGPHlMBWCM7UeutRdnvVfM2UQFR1w")
BINGX_SECRET = get_secret("BINGX_SECRET", "KMG9wbpdVtAoS7Hny9RssesIldiqav2PqqlQ9gdI5x2scLeoU2nXi770Uak0r2xL62IIzyr8gVaAEd0Zr9H8g")

MEXC_API_KEY = get_secret("MEXC_API_KEY", "mx0vgluY6in6XqNKrs")
MEXC_SECRET = get_secret("MEXC_SECRET", "cdd41089eba04fa3adb49b18b89918a0")

BITGET_API_KEY = get_secret("BITGET_API_KEY", "bg_7acb820c501a147ef31fd30ebae0fd3c")
BITGET_SECRET = get_secret("BITGET_SECRET", "b1745c9d60e4f521123ff313d3532994d706c161298add70e1f3e5e1284a9fee")
BITGET_PASSPHRASE = get_secret("BITGET_PASSPHRASE", "botmarukjosss")

BYBIT_API_KEY = get_secret("BYBIT_API_KEY", "BF5pHcX0dmTMs57fRE")
BYBIT_SECRET = get_secret("BYBIT_SECRET", "fHSrBq9hVRsZcpqC4zi958VE7052R7KkJUtW")

GATE_API_KEY = get_secret("GATE_API_KEY", "0c388c63d2a33f11cadd51a1c20e5bc3")
GATE_SECRET = get_secret("GATE_SECRET", "1f5cb4d1be89d3cb246e95e413eaeebdace9bb27ecbe77664e6fb23817116ab0")

KURS_IDR = 17000.0

@st.cache_resource
def init_exchanges():
    ex_dict = {}
    cfg = {'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 5000}
    if BINGX_API_KEY: ex_dict['BingX'] = ccxt.bingx({'apiKey': BINGX_API_KEY, 'secret': BINGX_SECRET, **cfg})
    if MEXC_API_KEY: ex_dict['MEXC'] = ccxt.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET, **cfg})
    if BITGET_API_KEY: ex_dict['Bitget'] = ccxt.bitget({'apiKey': BITGET_API_KEY, 'secret': BITGET_SECRET, 'password': BITGET_PASSPHRASE, **cfg})
    if BYBIT_API_KEY: ex_dict['Bybit'] = ccxt.bybit({'apiKey': BYBIT_API_KEY, 'secret': BYBIT_SECRET, **cfg})
    if GATE_API_KEY: ex_dict['Gate.io'] = ccxt.gate({'apiKey': GATE_API_KEY, 'secret': GATE_SECRET, **cfg})
    return ex_dict

exchanges = init_exchanges()

# ========================================================
# DATA HARVESTING (FAST CACHED)
# ========================================================
@st.cache_data(ttl=5)
def get_dashboard_data():
    tot_bal = 0.0
    tot_pnl = 0.0
    pos_list = []
    ex_details = {}
    live_mark_prices = {'BTC': 81750.0, 'ETH': 2470.0, 'XRP': 1.38, 'ADA': 0.234, 'AVAX': 10.15, 'LINK': 12.76}

    for name, ex in exchanges.items():
        try:
            usdt_total = 0.0
            usdt_free = 0.0
            raw_pos = []

            if name == "Bitget":
                bal = ex.fetch_balance(params={'type': 'swap'})
                usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or bal.get('total', {}).get('USDT', 0.0) or 0.0)
                usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                raw_pos = ex.fetch_positions(params={'productType': 'USDT-FUTURES'})
            elif name == "MEXC":
                bal = ex.fetch_balance(params={'type': 'swap'})
                usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or bal.get('total', {}).get('USDT', 0.0) or 0.0)
                usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                raw_pos = ex.fetch_positions()
            elif name == "BingX":
                bal = ex.fetch_balance({'type': 'swap'})
                usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or 0.0)
                usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                raw_pos = ex.fetch_positions()
            elif name == "Bybit":
                bal = ex.fetch_balance({'type': 'linear'})
                usdt_total = float(bal.get('total', {}).get('USDT', 0.0) or 0.0)
                usdt_free = float(bal.get('free', {}).get('USDT', 0.0) or usdt_total)
                raw_pos = ex.fetch_positions(params={'settle': 'USDT'})
            elif name == "Gate.io":
                bal = ex.fetch_balance(params={'type': 'swap', 'settle': 'usdt'})
                usdt_total = float(bal.get('total', {}).get('USDT', 0.0) or 0.0)
                usdt_free = float(bal.get('free', {}).get('USDT', 0.0) or usdt_total)
                raw_pos = ex.fetch_positions(params={'settle': 'usdt'})
            else:
                bal = ex.fetch_balance()
                usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or 0.0)
                usdt_free = usdt_total
                raw_pos = ex.fetch_positions()

            tot_bal += usdt_total
            ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2)}

            for p in raw_pos:
                contracts = abs(float(p.get('contracts') or p.get('amount') or (p.get('info', {}).get('holdVol') if isinstance(p.get('info'), dict) else 0) or 0.0))
                if contracts > 0:
                    sym = p.get('symbol', 'UNKNOWN')
                    clean_sym = sym.replace(':USDT', '').replace('/USDT', '')
                    side = str(p.get('side', '')).upper()
                    entry = float(p.get('entryPrice') or p.get('info', {}).get('openAvgPrice') or 0.0)
                    lev = float(p.get('leverage') or 28)

                    c_size = float(p.get('contractSize') or (p.get('info', {}).get('contractSize') if isinstance(p.get('info'), dict) else 1.0) or 1.0)
                    if name == 'MEXC':
                        if 'BTC' in sym: c_size = 0.0001
                        elif 'ETH' in sym: c_size = 0.01

                    real_notional = contracts * c_size * entry if entry > 0 else 0.0
                    margin = float(p.get('initialMargin') or p.get('collateral') or 0.0)
                    if margin <= 0 and real_notional > 0 and lev > 0:
                        margin = real_notional / lev
                    if margin <= 0: margin = 1.0

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
                        'notional': real_notional,
                        'pnl': pnl,
                        'roe': roe,
                        'leverage': int(lev)
                    })
        except Exception:
            ex_details[name] = {'total': 0.0, 'free': 0.0}

    return tot_bal, tot_pnl, pos_list, ex_details, live_mark_prices

tot_bal, tot_pnl, pos_list, ex_details, live_mark_prices = get_dashboard_data()

# ========================================================
# HEADER UTAMA
# ========================================================
col_h1, col_h2 = st.columns([2, 1])
with col_h1:
    st.markdown("""
    <div style="margin-bottom: 8px;">
        <h2 style="margin: 0; font-size: 1.4rem; font-weight: 900; color: #ffffff;">⚡ TITAN V5 BOT MARUK</h2>
        <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600;">Penta-Titan 5 Bursa • 28x Leverage • Target TP 8.2% & SL 2.3%</div>
    </div>
    """, unsafe_allow_html=True)

with col_h2:
    st.markdown(f"""
    <div style="text-align: right;">
        <span class="badge-live"><span class="live-dot"></span> LIVE ONLINE</span>
        <div style="font-size: 0.72rem; color: #64748b; margin-top: 4px;">{time.strftime('%H:%M:%S WIB')}</div>
    </div>
    """, unsafe_allow_html=True)

# ========================================================
# 1. EMPAT KARTU UTAMA (RINGKAS & JELAS)
# ========================================================
pnl_color = "#34d399" if tot_pnl >= 0 else "#f87171"
pnl_sign = "+$" if tot_pnl >= 0 else "-$"
roe_total = (tot_pnl / tot_bal * 100) if tot_bal > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Saldo Kas</div>
        <div class="metric-val">${tot_bal:.2f}</div>
        <div class="metric-sub" style="color: #38bdf8;">Rp {tot_bal*KURS_IDR:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card" style="border-color: {pnl_color}55;">
        <div class="metric-title">Floating PnL Live</div>
        <div class="metric-val" style="color: {pnl_color};">{pnl_sign}{abs(tot_pnl):.2f}</div>
        <div class="metric-sub" style="color: {pnl_color};">{'+' if tot_pnl >= 0 else ''}{roe_total:.1f}% ROE</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Posisi Aktif</div>
        <div class="metric-val">{len(pos_list)} <span style="font-size: 0.8rem; color: #64748b;">Posisi</span></div>
        <div class="metric-sub" style="color: #94a3b8;">5 Bursa Standby</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Win Rate & Rasio</div>
        <div class="metric-val" style="color: #38bdf8;">26.95%</div>
        <div class="metric-sub" style="color: #a78bfa;">Risk-Reward 1 : 3.56</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ========================================================
# 2. PROYEKSI HASIL (KALAU TP BERAPA & KALAU SL BERAPA)
# ========================================================
tp_rate = 0.082
sl_rate = 0.023
total_tp_usd = sum(p['margin'] * p['leverage'] * tp_rate for p in pos_list) if pos_list else 0.0
total_tp_idr = total_tp_usd * KURS_IDR
bal_if_tp = tot_bal + total_tp_usd

total_sl_usd = sum(p['margin'] * p['leverage'] * sl_rate for p in pos_list) if pos_list else 0.0
total_sl_idr = total_sl_usd * KURS_IDR
bal_if_sl = max(0.0, tot_bal - total_sl_usd)

st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🎯 Proyeksi Target Hasil (Kalau TP Berapa & SL Berapa)</div>', unsafe_allow_html=True)

col_tp, col_sl = st.columns(2)
with col_tp:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, #0f172a 100%); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 14px; padding: 16px;">
        <div style="font-size: 0.75rem; font-weight: 800; color: #34d399; text-transform: uppercase;">✅ JIKA PROFIT SEMUA (TP +8.2%)</div>
        <div style="font-size: 1.8rem; font-weight: 900; color: #34d399; margin: 4px 0;">+${total_tp_usd:.2f} <span style="font-size: 0.9rem; color: #a7f3d0;">USDT</span></div>
        <div style="font-size: 0.85rem; font-weight: 700; color: #6ee7b7; margin-bottom: 8px;">+Rp {total_tp_idr:,.0f}</div>
        <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; font-size: 0.78rem; color: #94a3b8;">
            Total Saldo Menjadi: <b style="color: #ffffff;">${bal_if_tp:.2f} USDT (Rp {bal_if_tp*KURS_IDR:,.0f})</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_sl:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(127, 29, 29, 0.45) 0%, #0f172a 100%); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 14px; padding: 16px;">
        <div style="font-size: 0.75rem; font-weight: 800; color: #f87171; text-transform: uppercase;">🛑 JIKA MINUS SEMUA (SL -2.3%)</div>
        <div style="font-size: 1.8rem; font-weight: 900; color: #f87171; margin: 4px 0;">-${total_sl_usd:.2f} <span style="font-size: 0.9rem; color: #fca5a5;">USDT</span></div>
        <div style="font-size: 0.85rem; font-weight: 700; color: #fca5a5; margin-bottom: 8px;">-Rp {total_sl_idr:,.0f}</div>
        <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; font-size: 0.78rem; color: #94a3b8;">
            Total Saldo Menjadi: <b style="color: #ffffff;">${bal_if_sl:.2f} USDT (Rp {bal_if_sl*KURS_IDR:,.0f})</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# ========================================================
# 3. DAFTAR POSISI AKTIF BERJALAN
# ========================================================
st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🔥 Posisi Aktif Berjalan</div>', unsafe_allow_html=True)

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
            st.markdown(f"""
            <div class="pos-card {p_cls}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div>
                        <span style="font-size: 1.1rem; font-weight: 900; color: #ffffff;">{p['symbol']}</span>
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
                        <div style="font-size: 1.3rem; font-weight: 900; color: {c_text};">{sign}{abs(p['pnl']):.2f}</div>
                        <div style="font-size: 0.75rem; font-weight: 700; color: {c_text};">{'+' if is_p else ''}{p['roe']:.1f}% ROE</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 6px; font-size: 0.7rem;">
                    <div style="color: #34d399;">🎯 TP: <b>+${p_tp_usd:.2f}</b> (+Rp {p_tp_usd*KURS_IDR:,.0f})</div>
                    <div style="color: #f87171; text-align: right;">🛡️ SL: <b>-${p_sl_usd:.2f}</b> (-Rp {p_sl_usd*KURS_IDR:,.0f})</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background: #0f172a; border: 1px dashed rgba(255,255,255,0.12); border-radius: 12px; padding: 20px; text-align: center; color: #94a3b8; font-size: 0.85rem;">
        💤 Tidak ada posisi yang aktif saat ini. Bot sedang menunggu sinyal Donchian 36H & Momentum valid.
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# ========================================================
# 4. SALDO DI MASING-MASING 5 BURSA (RINGKAS)
# ========================================================
st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🏛️ Saldo di Masing-Masing 5 Bursa</div>', unsafe_allow_html=True)

col_ex = st.columns(5)
ex_icons = {'Bitget': '💎', 'MEXC': '🐉', 'BingX': '🦁', 'Bybit': '⚡', 'Gate.io': '⛩️'}

for idx, (ex_name, icon) in enumerate(ex_icons.items()):
    info = ex_details.get(ex_name, {'total': 0.0, 'free': 0.0})
    b_val = info['total']
    with col_ex[idx]:
        st.markdown(f"""
        <div class="metric-card" style="padding: 10px 12px;">
            <div style="font-size: 0.8rem; font-weight: 800; color: #ffffff;">{icon} {ex_name}</div>
            <div style="font-size: 1.15rem; font-weight: 900; color: #38bdf8; margin: 2px 0;">${b_val:.2f}</div>
            <div style="font-size: 0.68rem; color: #94a3b8;">Rp {b_val*KURS_IDR:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

# ========================================================
# REFRESH BUTTON (SEDERHANA)
# ========================================================
st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
if st.button("🔄 Segarkan Data Real-Time Sekarang", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
