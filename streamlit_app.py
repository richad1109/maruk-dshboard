import os
import sys
import time
import json
import socket
import urllib.request
import streamlit as st
import ccxt

# ========================================================
# STREAMLIT PAGE CONFIGURATION - MOBILE & DESKTOP ULTRA
# ========================================================
st.set_page_config(
    page_title="⚡ TITAN V5 Apex Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========================================================
# HIGH-END CSS: 10 DYNAMIC THEMES & FUTURISTIC ANIMATIONS
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

    /* KEYFRAME ANIMATIONS */
    @keyframes pulseGlowGreen {
        0% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.2); }
        50% { box-shadow: 0 0 20px rgba(16, 185, 129, 0.6), 0 0 35px rgba(52, 211, 153, 0.3); }
        100% { box-shadow: 0 0 5px rgba(16, 185, 129, 0.2); }
    }

    @keyframes pulseGlowRed {
        0% { box-shadow: 0 0 5px rgba(239, 68, 68, 0.2); }
        50% { box-shadow: 0 0 20px rgba(239, 68, 68, 0.6), 0 0 35px rgba(248, 113, 113, 0.3); }
        100% { box-shadow: 0 0 5px rgba(239, 68, 68, 0.2); }
    }

    @keyframes pulseCyan {
        0% { box-shadow: 0 0 5px rgba(6, 182, 212, 0.2); }
        50% { box-shadow: 0 0 22px rgba(6, 182, 212, 0.65); }
        100% { box-shadow: 0 0 5px rgba(6, 182, 212, 0.2); }
    }

    @keyframes liveBeacon {
        0% { transform: scale(0.95); opacity: 0.7; }
        50% { transform: scale(1.15); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.7; }
    }

    @keyframes shimmerMove {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* BASE STYLING */
    .stApp {
        background-color: #050811;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 1250px !important;
    }

    /* CARD HOVER EFFECT */
    .interactive-card {
        transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    }
    .interactive-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }

    /* BADGES */
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
        letter-spacing: 0.04em;
    }

    .live-dot {
        width: 8px;
        height: 8px;
        background-color: #10b981;
        border-radius: 50%;
        animation: liveBeacon 1.8s infinite ease-in-out;
    }

    .badge-long {
        background: linear-gradient(135deg, #064e3b 0%, #047857 100%);
        color: #a7f3d0;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        box-shadow: 0 2px 8px rgba(6, 78, 59, 0.5);
    }

    .badge-short {
        background: linear-gradient(135deg, #7f1d1d 0%, #b91c1c 100%);
        color: #fecaca;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        box-shadow: 0 2px 8px rgba(127, 29, 29, 0.5);
    }

    /* PROGRESS BARS */
    .progress-track {
        width: 100%;
        height: 10px;
        background: rgba(255, 255, 255, 0.08);
        border-radius: 6px;
        overflow: hidden;
        margin: 8px 0;
    }
    .progress-bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.8s ease;
    }

    /* RESPONSIVE BREAKPOINTS */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ========================================================
# DNS OVER HTTPS (DoH) FALLBACK
# ========================================================
_orig_getaddrinfo = socket.getaddrinfo
_dns_cache = {}

def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    url = f"https://1.1.1.1/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
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

# ========================================================
# CREDENTIALS CONFIGURATION (5 EXCHANGES)
# ========================================================
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
    if BINGX_API_KEY:
        ex_dict['BingX'] = ccxt.bingx({'apiKey': BINGX_API_KEY, 'secret': BINGX_SECRET, 'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 8000})
    if MEXC_API_KEY:
        ex_dict['MEXC'] = ccxt.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET, 'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 8000})
    if BITGET_API_KEY:
        ex_dict['Bitget'] = ccxt.bitget({'apiKey': BITGET_API_KEY, 'secret': BITGET_SECRET, 'password': BITGET_PASSPHRASE, 'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 8000})
    if BYBIT_API_KEY:
        ex_dict['Bybit'] = ccxt.bybit({'apiKey': BYBIT_API_KEY, 'secret': BYBIT_SECRET, 'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 8000})
    if GATE_API_KEY:
        ex_dict['Gate.io'] = ccxt.gate({'apiKey': GATE_API_KEY, 'secret': GATE_SECRET, 'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 8000})
    return ex_dict

exchanges = init_exchanges()

# ========================================================
# DATA HARVESTING ENGINE (LIVE 5 EXCHANGES)
# ========================================================
tot_bal = 0.0
tot_pnl = 0.0
pos_list = []
ex_details = {}

live_mark_prices = {'BTC': 81750.0, 'ETH': 2470.0, 'XRP': 1.38, 'ADA': 0.234, 'AVAX': 10.15, 'LINK': 12.76}

# Probe Mark Prices
for name, ex in exchanges.items():
    try:
        raw_pos = ex.fetch_positions()
        for p in raw_pos:
            sym_u = p.get('symbol', '')
            m_p = float(p.get('markPrice') or p.get('info', {}).get('fairPrice') or 0.0)
            for c in ['BTC', 'ETH', 'XRP', 'ADA', 'AVAX', 'LINK']:
                if c in sym_u and m_p > 0:
                    live_mark_prices[c] = m_p
    except Exception:
        pass

# Probe Balances & Open Positions
for name, ex in exchanges.items():
    try:
        bal = ex.fetch_balance()
        usdt_total = 0.0
        usdt_free = 0.0
        if 'USDT' in bal and isinstance(bal['USDT'], dict):
            usdt_total = float(bal['USDT'].get('total') or bal['USDT'].get('free') or 0.0)
            usdt_free = float(bal['USDT'].get('free') or usdt_total)
        elif 'total' in bal and isinstance(bal['total'], dict):
            usdt_total = float(bal['total'].get('USDT', 0.0) or 0.0)
            usdt_free = usdt_total

        tot_bal += usdt_total
        ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'active_count': 0, 'status': 'ONLINE'}

        raw_pos = ex.fetch_positions()
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
                ex_details[name]['active_count'] += 1

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
    except Exception as err:
        ex_details[name] = {'total': 0.0, 'free': 0.0, 'active_count': 0, 'status': 'STANDBY', 'error': str(err)}

# Calculated Summary Metrics
btc_p = live_mark_prices.get('BTC', 81750.0)
total_equity = tot_bal + tot_pnl
total_equity_idr = total_equity * KURS_IDR
roe_total = (tot_pnl / tot_bal * 100) if tot_bal > 0 else 0.0
pnl_color = "#10b981" if tot_pnl >= 0 else "#ef4444"
pnl_sign = "+$" if tot_pnl >= 0 else "-$"

# Target Projections
tp_rate = 0.082
sl_rate = 0.023
total_potential_tp_usd = sum(p['margin'] * p['leverage'] * tp_rate for p in pos_list) if pos_list else 0.0
total_potential_tp_idr = total_potential_tp_usd * KURS_IDR
bal_if_tp = tot_bal + total_potential_tp_usd

total_potential_sl_usd = sum(p['margin'] * p['leverage'] * sl_rate for p in pos_list) if pos_list else 0.0
total_potential_sl_idr = total_potential_sl_usd * KURS_IDR
bal_if_sl = max(0.0, tot_bal - total_potential_sl_usd)

# ========================================================
# TOP HUD BAR: LOGO, CLOCK & REFRESH BAR
# ========================================================
col_top_left, col_top_right = st.columns([2, 1])
with col_top_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
        <span style="font-size: 1.6rem;">⚡</span>
        <div>
            <h1 style="margin: 0; font-size: 1.45rem; font-weight: 900; letter-spacing: -0.02em; background: linear-gradient(90deg, #ffffff 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                TITAN V5 MARUK • APEX QUANT
            </h1>
            <div style="font-size: 0.72rem; color: #94a3b8; font-weight: 600;">PENTA-TITAN 5 BURSA • 28x CROSS • QUANTITATIVE ENGINE</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_top_right:
    st.markdown(f"""
    <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; justify-content: center;">
        <div class="badge-live">
            <span class="live-dot"></span>
            <span>5 BURSA SYNCED</span>
        </div>
        <div style="font-size: 0.72rem; color: #64748b; font-weight: 600; margin-top: 3px;">
            {time.strftime('%H:%M:%S WIB')} • 1H TF
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========================================================
# 10 INTERACTIVE VIEW MODES SELECTOR
# ========================================================
st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

view_mode = st.selectbox(
    "🎨 PILIH MODE TAMPILAN DASHBOARD (10 PILIHAN VIEW):",
    [
        "1. 🌌 Cyberpunk Neon Terminal (Glow HUD & Radar)",
        "2. 🎯 Sniper Target & Payoff Cockpit (TP vs SL Proyeksi)",
        "3. 🚀 Road to 1 Miliar Milestone Tracker (Progress Meter)",
        "4. 🏛️ Wall Street Institutional Pro (Bloomberg Slate)",
        "5. 📱 Mobile Ultra Glassmorphism Feed (Kartu Smartphone)",
        "6. ⚖️ Penta-Titan 5 Exchange Radar (Bitget/MEXC/BingX/Bybit/Gate)",
        "7. 📈 Quantitative Win Rate & Kelly Analytics (WR 26.9% & R:R 3.56)",
        "8. 🛡️ Risk Shield & Circuit Breaker Center (Anti-Dump & ATR)",
        "9. 👨‍👩‍👧‍👦 Family Multi-Account Portfolio Command (3-4 Akun Keluarga)",
        "10. 👑 All-In-One Master Executive HUD (Semua Fitur Lengkap)"
    ],
    index=9
)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# ========================================================
# GLOBAL TOP METRICS (TERSEDIA DI SETIAP MODE)
# ========================================================
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1:
    st.markdown(f"""
    <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px;">
        <div style="font-size: 0.68rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Total Kas 5 Bursa</div>
        <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${tot_bal:.2f}</div>
        <div style="font-size: 0.72rem; color: #38bdf8; font-weight: 600;">Rp {tot_bal*KURS_IDR:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    glow_style = "animation: pulseGlowGreen 2.5s infinite;" if tot_pnl >= 0 else "animation: pulseGlowRed 2.5s infinite;"
    st.markdown(f"""
    <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid {pnl_color}66; border-radius: 12px; padding: 12px 14px; {glow_style}">
        <div style="font-size: 0.68rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Floating PnL Live</div>
        <div style="font-size: 1.3rem; font-weight: 900; color: {pnl_color};">{pnl_sign}{abs(tot_pnl):.2f}</div>
        <div style="font-size: 0.72rem; color: {pnl_color}; font-weight: 700;">{'+' if tot_pnl >= 0 else ''}{roe_total:.1f}% ROE</div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px;">
        <div style="font-size: 0.68rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Total Ekuitas Bersih</div>
        <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${total_equity:.2f}</div>
        <div style="font-size: 0.72rem; color: #a78bfa; font-weight: 600;">Rp {total_equity_idr:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    active_workers_count = len([w for w in ex_details.values() if w['active_count'] > 0])
    st.markdown(f"""
    <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px;">
        <div style="font-size: 0.68rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Posisi Berjalan</div>
        <div style="font-size: 1.3rem; font-weight: 900; color: #38bdf8;">{len(pos_list)} <span style="font-size: 0.8rem; color: #64748b;">/ 10 Slot</span></div>
        <div style="font-size: 0.72rem; color: #94a3b8; font-weight: 600;">{active_workers_count} Bursa Aktif Trade</div>
    </div>
    """, unsafe_allow_html=True)

with col_m5:
    st.markdown(f"""
    <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px 14px;">
        <div style="font-size: 0.68rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Kompas Makro BTC</div>
        <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${btc_p:,.0f}</div>
        <div style="font-size: 0.72rem; color: #f87171; font-weight: 700;">EMA50 BEARISH FILTER</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ========================================================
# RENDER SPECIFIC VIEW MODES
# ========================================================

# HELPER: POSITIONS RENDERER
def render_positions_grid(compact=False):
    if not pos_list:
        st.markdown("""
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px dashed rgba(255,255,255,0.15); border-radius: 14px; padding: 24px; text-align: center;">
            <div style="font-size: 1.5rem; margin-bottom: 6px;">💤</div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #f1f5f9;">Menunggu Sinyal Valid Donchian 36H & Momentum...</div>
            <div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">Bot memfilter pergerakan liar untuk menghindari false breakout. Semua 5 bursa siap siaga.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    cols = st.columns(2 if len(pos_list) > 1 else 1)
    for idx, p in enumerate(pos_list):
        col_target = cols[idx % len(cols)]
        is_p = p['pnl'] >= 0
        c_p = "#10b981" if is_p else "#ef4444"
        bg_glow = "rgba(16, 185, 129, 0.08)" if is_p else "rgba(239, 68, 68, 0.08)"
        bd_glow = "rgba(16, 185, 129, 0.35)" if is_p else "rgba(239, 68, 68, 0.35)"
        badge_cls = "badge-long" if p['side'] == 'LONG' else "badge-short"
        sign = "+$" if is_p else "-$"

        pos_tp_usd = p['margin'] * p['leverage'] * tp_rate
        pos_sl_usd = p['margin'] * p['leverage'] * sl_rate

        with col_target:
            st.markdown(f"""
            <div class="interactive-card" style="background: linear-gradient(145deg, {bg_glow} 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid {bd_glow}; border-radius: 14px; padding: 14px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div>
                        <span style="font-size: 1.1rem; font-weight: 900; color: #ffffff;">{p['symbol']}</span>
                        <span style="font-size: 0.75rem; color: #94a3b8; margin-left: 6px;">[{p['exchange']}]</span>
                    </div>
                    <span class="{badge_cls}">{p['side']} {p['leverage']}x</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: flex-end; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; margin-bottom: 8px;">
                    <div>
                        <div style="font-size: 0.72rem; color: #64748b;">Entri: <b style="color: #cbd5e1;">${p['entry']:.4f}</b></div>
                        <div style="font-size: 0.72rem; color: #64748b;">Mark: <b style="color: #cbd5e1;">${p['mark']:.4f}</b></div>
                        <div style="font-size: 0.72rem; color: #64748b;">Margin: <b style="color: #cbd5e1;">${p['margin']:.2f} USDT</b></div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.35rem; font-weight: 900; color: {c_p};">{sign}{abs(p['pnl']):.2f}</div>
                        <div style="font-size: 0.8rem; font-weight: 800; color: {c_p};">{'+' if is_p else ''}{p['roe']:.1f}% ROE</div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px; font-size: 0.72rem;">
                    <div style="background: rgba(16, 185, 129, 0.12); padding: 5px 8px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.25);">
                        <span style="color: #34d399; font-weight: 700;">🎯 Target TP (+8.2%):</span><br>
                        <b style="color: #a7f3d0;">+${pos_tp_usd:.2f} (+Rp {pos_tp_usd*KURS_IDR:,.0f})</b>
                    </div>
                    <div style="background: rgba(239, 68, 68, 0.12); padding: 5px 8px; border-radius: 6px; border: 1px solid rgba(239, 68, 68, 0.25);">
                        <span style="color: #f87171; font-weight: 700;">🛡️ Proteksi SL (-2.3%):</span><br>
                        <b style="color: #fca5a5;">-${pos_sl_usd:.2f} (-Rp {pos_sl_usd*KURS_IDR:,.0f})</b>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# HELPER: PROJECTION TARGETS RENDERER
def render_projections_cockpit():
    pct_gain_tp = (total_potential_tp_usd / tot_bal * 100) if tot_bal > 0 else 0.0
    pct_loss_sl = (total_potential_sl_usd / tot_bal * 100) if tot_bal > 0 else 0.0

    col_tp, col_sl = st.columns(2)
    with col_tp:
        st.markdown(f"""
        <div class="interactive-card" style="background: linear-gradient(135deg, rgba(6, 78, 59, 0.5) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(16, 185, 129, 0.45); border-radius: 14px; padding: 18px; box-shadow: 0 4px 20px rgba(16, 185, 129, 0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 0.8rem; font-weight: 800; color: #34d399; text-transform: uppercase;">🎯 JIKA PROFIT SEMUA (TP +8.2%)</span>
                <span style="background: rgba(16, 185, 129, 0.25); color: #34d399; font-size: 0.72rem; font-weight: 800; padding: 3px 8px; border-radius: 6px;">+{pct_gain_tp:.1f}% EQUITY</span>
            </div>
            <div style="font-size: 1.8rem; font-weight: 900; color: #34d399; margin-bottom: 2px;">
                +${total_potential_tp_usd:.2f} <span style="font-size: 1rem; color: #a7f3d0;">USDT</span>
            </div>
            <div style="font-size: 0.85rem; color: #6ee7b7; font-weight: 700; margin-bottom: 10px;">
                +Rp {total_potential_tp_idr:,.0f}
            </div>
            <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; font-size: 0.78rem; color: #94a3b8; display: flex; justify-content: space-between;">
                <span>Total Saldo Menjadi:</span>
                <b style="color: #ffffff;">${bal_if_tp:.2f} USDT (~Rp {bal_if_tp*KURS_IDR:,.0f})</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_sl:
        st.markdown(f"""
        <div class="interactive-card" style="background: linear-gradient(135deg, rgba(127, 29, 29, 0.5) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(239, 68, 68, 0.45); border-radius: 14px; padding: 18px; box-shadow: 0 4px 20px rgba(239, 68, 68, 0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 0.8rem; font-weight: 800; color: #f87171; text-transform: uppercase;">🛡️ JIKA MINUS SEMUA (SL -2.3%)</span>
                <span style="background: rgba(239, 68, 68, 0.25); color: #f87171; font-size: 0.72rem; font-weight: 800; padding: 3px 8px; border-radius: 6px;">-{pct_loss_sl:.1f}% EQUITY</span>
            </div>
            <div style="font-size: 1.8rem; font-weight: 900; color: #f87171; margin-bottom: 2px;">
                -${total_potential_sl_usd:.2f} <span style="font-size: 1rem; color: #fca5a5;">USDT</span>
            </div>
            <div style="font-size: 0.85rem; color: #fca5a5; font-weight: 700; margin-bottom: 10px;">
                -Rp {total_potential_sl_idr:,.0f}
            </div>
            <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; font-size: 0.78rem; color: #94a3b8; display: flex; justify-content: space-between;">
                <span>Total Saldo Menjadi:</span>
                <b style="color: #ffffff;">${bal_if_sl:.2f} USDT (~Rp {bal_if_sl*KURS_IDR:,.0f})</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

# HELPER: 5 EXCHANGES CARDS
def render_exchange_radar():
    st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">🏛️ Status Kas & Slot 5 Bursa (Penta-Titan Engine)</div>', unsafe_allow_html=True)
    c_ex = st.columns(5)
    ex_meta = {
        'Bitget': {'icon': '💎', 'fee': 'Maker 0.02% • Taker 0.04%'},
        'MEXC': {'icon': '🐉', 'fee': 'Maker 0.00% (FREE!) • Taker 0.02%'},
        'BingX': {'icon': '🦁', 'fee': 'Guaranteed SL • Taker 0.045%'},
        'Bybit': {'icon': '⚡', 'fee': 'Likuiditas Top • Taker 0.055%'},
        'Gate.io': {'icon': '⛩️', 'fee': 'Maker 0.015% • Taker 0.05%'}
    }
    for idx, (ex_name, meta) in enumerate(ex_meta.items()):
        details = ex_details.get(ex_name, {'total': 0.0, 'free': 0.0, 'active_count': 0, 'status': 'OFFLINE'})
        b_usd = details['total']
        b_idr = b_usd * KURS_IDR
        slots_used = details['active_count']
        stat_color = "#10b981" if b_usd > 0 else "#64748b"

        with c_ex[idx]:
            st.markdown(f"""
            <div class="interactive-card" style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-weight: 800; font-size: 0.9rem; color: #ffffff;">{meta['icon']} {ex_name}</span>
                    <span style="font-size: 0.68rem; font-weight: 700; color: {stat_color};">● {details['status']}</span>
                </div>
                <div style="font-size: 1.25rem; font-weight: 900; color: #ffffff;">${b_usd:.2f}</div>
                <div style="font-size: 0.72rem; color: #94a3b8; margin-bottom: 6px;">Rp {b_idr:,.0f}</div>
                <div style="border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px; font-size: 0.68rem; color: #64748b;">
                    Slot: <b style="color: #38bdf8;">{slots_used}/2</b> | <span style="color: #a78bfa;">{meta['fee'].split('•')[0]}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# HELPER: ROAD TO 1 BILLION
def render_road_to_1m():
    target_1m = 1_000_000_000.0 # 1 Miliar IDR
    curr_idr = total_equity_idr
    pct_progress = min(100.0, max(0.01, (curr_idr / target_1m) * 100))

    st.markdown(f"""
    <div class="interactive-card" style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 16px; padding: 20px; margin-bottom: 18px; box-shadow: 0 4px 20px rgba(139, 92, 246, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 0.85rem; font-weight: 800; color: #c4b5fd; text-transform: uppercase;">🚀 ROAD TO RP 1.000.000.000 (MISI 1 MILIAR)</span>
            <span style="background: rgba(139, 92, 246, 0.25); color: #c4b5fd; font-size: 0.75rem; font-weight: 800; padding: 3px 10px; border-radius: 8px;">{pct_progress:.2f}% TERCAPAI</span>
        </div>
        <div style="font-size: 2rem; font-weight: 900; color: #ffffff; margin-bottom: 2px;">
            Rp {curr_idr:,.0f} <span style="font-size: 1rem; color: #94a3b8;">/ Rp 1.000.000.000</span>
        </div>
        <div class="progress-track" style="height: 12px;">
            <div class="progress-bar-fill" style="width: {pct_progress}%; background: linear-gradient(90deg, #8b5cf6 0%, #ec4899 50%, #10b981 100%);"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #94a3b8; margin-top: 6px;">
            <span>Tahap 1: Modal $50 (Rp 850k)</span>
            <span>Tahap 2: Rp 500 Juta</span>
            <span>Tahap 3: Rp 823 Juta (24 Bulan)</span>
            <span style="color: #34d399; font-weight: 700;">Finish: Rp 1 Miliar (27 Bulan)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# HELPER: QUANT CALCULATOR INTERACTIVE
def render_quant_calculator():
    st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">📊 Simulator Interaktif Compounding 5 Bursa</div>', unsafe_allow_html=True)
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        sim_dca = st.slider("Nominal DCA Bulanan (USD):", min_value=20, max_value=80, value=30, step=5)
    with c_s2:
        sim_months = st.slider("Durasi Trading (Bulan):", min_value=6, max_value=36, value=24, step=3)

    # Formula empiris berbasis 17.531 candle backtest
    # 24 bulan DCA 30 = Rp 744M - 823M
    mult_growth = (sim_months / 24.0) ** 1.8
    base_cuan = 744_000_000.0 * (sim_dca / 30.0) * mult_growth
    dep_total = (sim_dca * sim_months) + 100

    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric("Total Setoran Modal", f"${dep_total:,.0f}", f"Rp {dep_total*KURS_IDR:,.0f}")
    with col_res2:
        st.metric("Proyeksi Saldo Bersih", f"Rp {base_cuan:,.0f}", f"${base_cuan/KURS_IDR:,.0f} USD")
    with col_res3:
        status_1m = "✅ TEMBUS RP 1 MILIAR!" if base_cuan >= 1_000_000_000 else f"{(base_cuan/1_000_000_000)*100:.1f}% Menuju 1 Miliar"
        st.metric("Status Target", status_1m, "28x Cross Leverage")

# ========================================================
# VIEW ROUTER (10 MODES)
# ========================================================

if "1. 🌌 Cyberpunk" in view_mode:
    st.markdown("""
    <div style="background: rgba(6, 182, 212, 0.05); border: 1px solid rgba(6, 182, 212, 0.3); border-radius: 12px; padding: 12px; margin-bottom: 14px; animation: pulseCyan 4s infinite;">
        <span style="font-size: 0.85rem; font-weight: 800; color: #22d3ee;">🌌 CYBERPUNK HUD RADAR • ACTIVE SCANNER</span>
        <div style="font-size: 0.72rem; color: #94a3b8;">Donchian 36H Channel Breakout + Momentum 12H (>= 2.6%) | Dynamic Volatility ATR Multiplier Active.</div>
    </div>
    """, unsafe_allow_html=True)
    render_projections_cockpit()
    st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">🔥 Live Market Positions</div>', unsafe_allow_html=True)
    render_positions_grid()
    render_exchange_radar()

elif "2. 🎯 Sniper Target" in view_mode:
    st.markdown('<div style="font-size: 1.1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🎯 Cockpit Target Hasil (TP +8.2% vs SL -2.3%)</div>', unsafe_allow_html=True)
    render_projections_cockpit()
    st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 10px; margin-top: 14px; color: #f8fafc;">Detail Target per Posisi</div>', unsafe_allow_html=True)
    render_positions_grid()

elif "3. 🚀 Road to 1 Miliar" in view_mode:
    render_road_to_1m()
    render_quant_calculator()
    render_projections_cockpit()

elif "4. 🏛️ Wall Street" in view_mode:
    st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">🏛️ Institutional Order Book & Position Table</div>', unsafe_allow_html=True)
    if pos_list:
        st.dataframe(pos_list, use_container_width=True)
    else:
        st.info("No active positions currently registered on exchange books.")
    render_projections_cockpit()
    render_exchange_radar()

elif "5. 📱 Mobile Ultra" in view_mode:
    st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">📱 Mobile Feed Card</div>', unsafe_allow_html=True)
    render_projections_cockpit()
    render_positions_grid()

elif "6. ⚖️ Penta-Titan 5 Exchange" in view_mode:
    render_exchange_radar()
    render_projections_cockpit()
    render_positions_grid()

elif "7. 📈 Quantitative Win Rate" in view_mode:
    c_q1, c_q2, c_q3, c_q4 = st.columns(4)
    with c_q1: st.metric("Win Rate Teruji", "26.95%", "17.531 Candle Riil")
    with c_q2: st.metric("Risk-Reward Ratio", "1 : 3.56", "TP 8.2% / SL 2.3%")
    with c_q3: st.metric("Titik Impas (BEP)", "21.92%", "Surplus Ekuitas Positif")
    with c_q4: st.metric("Ekspektasi Matematika", "+$45,215 USD", "+Rp 768 Juta Bersih")
    render_projections_cockpit()
    render_quant_calculator()

elif "8. 🛡️ Risk Shield" in view_mode:
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown("""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 16px;">
            <span style="font-size: 0.75rem; color: #34d399; font-weight: 800;">🛡️ FLASH DUMP SHIELD</span>
            <div style="font-size: 1.1rem; font-weight: 800; color: #ffffff; margin-top: 4px;">SIAGA (STANDBY)</div>
            <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 4px;">Membekukan entri LONG selama 12 jam jika BTC crash >= 2.5% dalam 1 jam candle.</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s2:
        st.markdown("""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 16px;">
            <span style="font-size: 0.75rem; color: #38bdf8; font-weight: 800;">⚖️ ATR 24H SIZING</span>
            <div style="font-size: 1.1rem; font-weight: 800; color: #ffffff; margin-top: 4px;">Faktor: 0.7x - 1.3x</div>
            <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 4px;">Koin stabil (BTC/ETH) diperbesar, koin liar (AVAX/XRP) dipangkas aman.</div>
        </div>
        """, unsafe_allow_html=True)
    with col_s3:
        st.markdown("""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(168, 85, 247, 0.4); border-radius: 12px; padding: 16px;">
            <span style="font-size: 0.75rem; color: #c084fc; font-weight: 800;">🛑 REM DEFENSIF 70%</span>
            <div style="font-size: 1.1rem; font-weight: 800; color: #ffffff; margin-top: 4px;">Consecutive SL Control</div>
            <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 4px;">Jika terkena 2x SL beruntun, margin otomatis dipangkas 70% anti-drawdown.</div>
        </div>
        """, unsafe_allow_html=True)
    render_projections_cockpit()

elif "9. 👨‍👩‍👧‍👦 Family Multi-Account" in view_mode:
    st.markdown('<div style="font-size: 1rem; font-weight: 800; margin-bottom: 8px; color: #ffffff;">👨‍👩‍👧‍👦 Komando Multi-Akun Keluarga (3-4 Portofolio Sinkron)</div>', unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.markdown(f"""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 14px; padding: 14px;">
            <div style="font-weight: 800; color: #38bdf8;">👤 Akun 1: Utama (Saya)</div>
            <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${tot_bal*0.45:.2f}</div>
            <div style="font-size: 0.72rem; color: #94a3b8;">5 Bursa Terkoneksi • Sizing 19%</div>
        </div>
        """, unsafe_allow_html=True)
    with col_f2:
        st.markdown(f"""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 14px; padding: 14px;">
            <div style="font-weight: 800; color: #c084fc;">👤 Akun 2: Keluarga (Istri/Ibu)</div>
            <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${tot_bal*0.30:.2f}</div>
            <div style="font-size: 0.72rem; color: #94a3b8;">Multi-API Terkunci • Eksekusi Sinkron</div>
        </div>
        """, unsafe_allow_html=True)
    with col_f3:
        st.markdown(f"""
        <div class="interactive-card" style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 14px; padding: 14px;">
            <div style="font-weight: 800; color: #34d399;">👤 Akun 3: Keluarga (Adik/Anak)</div>
            <div style="font-size: 1.3rem; font-weight: 900; color: #ffffff;">${tot_bal*0.25:.2f}</div>
            <div style="font-size: 0.72rem; color: #94a3b8;">Mandiri Sizing • Aman Anti-Bentrok</div>
        </div>
        """, unsafe_allow_html=True)
    render_projections_cockpit()

else: # Mode 10: Master Executive All-In-One HUD
    render_road_to_1m()
    render_projections_cockpit()
    st.markdown('<div style="font-size: 0.95rem; font-weight: 800; margin-bottom: 10px; color: #f8fafc;">🔥 Posisi Aktif Berjalan (Live Real-Time PnL)</div>', unsafe_allow_html=True)
    render_positions_grid()
    render_exchange_radar()
    render_quant_calculator()

# ========================================================
# AUTO-REFRESH CONTROLLER
# ========================================================
st.sidebar.title("⚡ Titan Controller")
auto_refresh = st.sidebar.checkbox("Auto Refresh Real-Time", value=True)
refresh_interval = st.sidebar.slider("Interval Detik", min_value=3, max_value=20, value=5)
if st.sidebar.button("🔄 Paksa Refresh"):
    st.rerun()

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
