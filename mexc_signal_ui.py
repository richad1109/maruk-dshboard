"""Compact public signal board. Research stays behind the scenes."""
import time
import json
from pathlib import Path
from html import escape
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import streamlit as st
import mexc_signals as engine
import sniper_limit_engine

WIB = timezone(timedelta(hours=7))

def stamp(t):
    return datetime.fromtimestamp(t, WIB).strftime('%d %b %H:%M')

def clock_now():
    return datetime.now(WIB).strftime('%H:%M:%S WIB')

def display_price(value):
    return format(Decimal(format(float(value), '.8g')), 'f')

def html(raw_html: str):
    """Safely render HTML without any Markdown code block indentation artifacts."""
    clean = " ".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())
    st.markdown(clean, unsafe_allow_html=True)

def level_row(entry, tp, sl):
    values = [('Entry (Limit)', entry), ('Take Profit (+35%)', tp), ('Stop Loss (-30%)', sl)]
    cells = ''.join(f'<div><span>{label}</span><strong>{escape(display_price(value))}</strong></div>' for label, value in values)
    html(f'<div class="compact-levels">{cells}</div>')

@st.cache_data(ttl=120, show_spinner=False)
def universe():
    return engine.catalog()

@st.cache_data(ttl=300, show_spinner=False)
def batch(items, rule='automatic-v1'):
    return engine.scan_multi(items)

def visible_signals(results, now=None):
    now = time.time() if now is None else now
    passed = []
    for r in results:
        t = r.get('test', {})
        if (r.get('side') in (-1, 1) and r.get('liquid') and r.get('qualified') and r.get('target90')
            and r.get('closed', now + 1) <= now < r.get('expires', 0) and t.get('n', 0) >= 100
            and t.get('wr', 0) >= 90 and t.get('lower', 0) >= 80 and (t.get('pf') or 0) > 1 and (t.get('mean_r') or 0) > 0):
            passed.append(r)
    out = []
    for symbol in sorted({r['symbol'] for r in passed}):
        group = [r for r in passed if r['symbol'] == symbol]
        if len({r['side'] for r in group}) == 1:
            out.append(max(group, key=lambda r: (r['test']['lower'], r['test']['n'])))
    return out

@st.cache_data(ttl=10, show_spinner=False)
def touch(signal):
    return engine.observe_touch(signal)

@st.cache_data(ttl=10, show_spinner=False)
def limit_radar_data():
    try:
        data = sniper_limit_engine.scan_all()
        if data:
            return data
    except Exception:
        pass
    return []

def limit_validation():
    try:
        return json.loads((Path(__file__).parent / 'limit_validation.json').read_text())
    except (OSError, ValueError):
        return {}

def bias_cards():
    col_head_left, col_head_right = st.columns([2.6, 1.4])
    with col_head_right:
        html(f'<div style="text-align: right; padding: 2px 0 6px 0;"><span style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid #10b981;">● AUTO-REFRESH 10s · {clock_now()}</span></div>')
        if st.button('↻ Refresh Sekarang', key='btn_refresh_now', use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    observations = limit_radar_data()
    if not observations:
        st.warning('Radar limit order sedang menyinkronkan data bursa MEXC Futures...')
        return

    # SUMMARY RESMI & PERSISTEN DARI ENGINE
    summary = sniper_limit_engine.get_portfolio_summary(observations)
    total_floating_usd = summary['floating_usd']
    total_floating_roe = summary['floating_roe']
    tot_idr = summary['floating_idr']
    active_floating_count = summary['active_count']

    realized_usd = summary['realized_usd']
    realized_roe = summary['realized_roe']
    realized_idr = summary['realized_idr']
    tp_count = summary['tp_count']
    sl_count = summary['sl_count']
    total_closed = summary['total_closed']
    realized_wr = summary['realized_wr']
    avg_portfolio_wr = summary['avg_wr']

    valid_count = summary['waiting_count']
    longs = sum(1 for r in observations if "LONG" in r.get('potensi', ''))
    shorts = sum(1 for r in observations if "SHORT" in r.get('potensi', ''))
    label = 'DOMINAN LONG' if longs > shorts else 'DOMINAN SHORT' if shorts > longs else 'CAMPURAN / NETRAL'

    with col_head_left:
        st.markdown('### Radar Limit Order 20 Koin · ' + label)
        st.caption('Top 20 Likuiditas Kripto · Margin &#36;2.00 USD Isolated per Posisi · Leverage 30x Flat')

    # =========================================================================
    # BANNER UTAMA: TOTAL FLOATING, REALIZED PnL & WIN RATE PORTOFOLIO
    # =========================================================================
    sign_tot = "+" if total_floating_usd >= 0 else ""
    tot_bg = "rgba(16, 185, 129, 0.16)" if total_floating_usd >= 0 else "rgba(239, 68, 68, 0.16)"
    tot_border = "#10b981" if total_floating_usd >= 0 else "#ef4444"
    tot_col = "#34d399" if total_floating_usd >= 0 else "#f87171"

    sign_real = "+" if realized_usd >= 0 else ""
    real_col = "#34d399" if realized_usd >= 0 else "#f87171"

    html(f'''
<div style="background: rgba(15, 23, 42, 0.75); border: 2px solid #334155; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px;">
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 14px;">
<div style="background: {tot_bg}; border: 1.5px solid {tot_border}; border-radius: 10px; padding: 12px 16px;">
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8; font-weight: 700;">💰 FLOATING PROFIT (BERJALAN)</div>
<div style="font-size: 24px; font-weight: 900; color: {tot_col}; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{sign_tot}&#36;{total_floating_usd:,.2f} USD <span style="font-size: 15px; font-weight: 700;">({sign_tot}{total_floating_roe:,.1f}%)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">Estimasi: <strong style="color: {tot_col};">{sign_tot}Rp {tot_idr:,.0f}</strong> ({active_floating_count} koin mantul aktif)</div>
</div>
<div style="background: rgba(59, 130, 246, 0.14); border: 1.5px solid #3b82f6; border-radius: 10px; padding: 12px 16px;">
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #93c5fd; font-weight: 700;">💎 REALIZED PnL (SELESAI TP/SL)</div>
<div style="font-size: 24px; font-weight: 900; color: {real_col}; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{sign_real}&#36;{realized_usd:,.2f} USD <span style="font-size: 15px; font-weight: 700;">({sign_real}{realized_roe:,.1f}%)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">Total Selesai: <strong style="color: {real_col};">{sign_real}Rp {realized_idr:,.0f}</strong> ({total_closed} trade: {tp_count} TP / {sl_count} SL)</div>
</div>
<div style="background: rgba(245, 158, 11, 0.14); border: 1.5px solid #f59e0b; border-radius: 10px; padding: 12px 16px;">
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #fde68a; font-weight: 700;">🏆 WIN RATE (WR) PORTOFOLIO</div>
<div style="font-size: 24px; font-weight: 900; color: #fbbf24; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{avg_portfolio_wr:.1f}% <span style="font-size: 13px; font-weight: 700; color: #94a3b8;">(Historis)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">WR Sesi Selesai: <strong style="color: #60a5fa;">{realized_wr:.1f}%</strong> ({tp_count} TP / {sl_count} SL)</div>
</div>
</div>
<div style="display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap; border-top: 1px solid #1e293b; padding-top: 12px;">
<div style="display: flex; gap: 8px; flex-wrap: wrap;">
<span style="background: rgba(16, 185, 129, 0.22); border: 1px solid #10b981; color: #34d399; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">⚡ {active_floating_count} Koin Mantul Aktif</span>
<span style="background: rgba(59, 130, 246, 0.22); border: 1px solid #3b82f6; color: #60a5fa; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">🎯 {tp_count} Sukses Hit TP</span>
<span style="background: rgba(239, 68, 68, 0.22); border: 1px solid #ef4444; color: #f87171; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">🛑 {sl_count} Hit Stop Loss</span>
<span style="background: rgba(245, 158, 11, 0.22); border: 1px solid #f59e0b; color: #f59e0b; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">⏳ {valid_count} Setup Baru Siap Pasang</span>
</div>
<div style="font-size: 11px; color: #64748b;">*Margin &#36;2.00 per posisi isolated · Leverage 30x Flat · TP +35% ROE (+&#36;0.70) · SL -30% ROE (-&#36;0.60)</div>
</div>
</div>
''')

    # =========================================================================
    # GRID KARTU 20 KOIN (JELAS, TANPA KONFLIK & FRESH SETUP)
    # =========================================================================
    columns = st.columns(3)
    for i, r in enumerate(observations):
        with columns[i % 3]:
            with st.container(border=True):
                is_touched = (r.get('status') == 'TOUCHED')
                last_out = r.get('last_outcome')

                # 1. BANNER ATAS KARTU
                if is_touched:
                    # Posisi aktif terisi & sedang mantul
                    sign = "+" if r['float_usd'] >= 0 else ""
                    f_col = "#34d399" if r['float_usd'] >= 0 else "#f87171"
                    html(f'''
<div style="background: rgba(16, 185, 129, 0.16); border: 1.5px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #10b981; font-size: 11px;">⚡ LIMIT TERJEMPUT (MANTUL)</span>
<span style="font-weight: 800; color: {f_col}; font-size: 12px; font-family: monospace;">{r["float_str"]}</span>
</div>
''')
                elif last_out and isinstance(last_out, dict):
                    # Baru selesai TP/SL dan LANGSUNG menerbitkan setup limit baru fresh
                    if last_out.get('outcome') == 'TP':
                        html(f'''
<div style="background: rgba(16, 185, 129, 0.18); border: 1.5px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #34d399; font-size: 11px;">🎯 HIT TP (+35%) · SETUP BARU FRESH</span>
<span style="font-weight: 700; color: #94a3b8; font-size: 11px; font-family: monospace;">{r["float_str"]}</span>
</div>
''')
                    else:
                        html(f'''
<div style="background: rgba(239, 68, 68, 0.18); border: 1.5px solid #ef4444; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #f87171; font-size: 11px;">🛑 HIT SL (-30%) · SETUP BARU FRESH</span>
<span style="font-weight: 700; color: #94a3b8; font-size: 11px; font-family: monospace;">{r["float_str"]}</span>
</div>
''')
                else:
                    # Menunggu jemputan biasa
                    html(f'''
<div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 600; color: #f59e0b; font-size: 11px;">⏳ MENUNGGU JEMPUTAN LIMIT</span>
<span style="font-weight: 700; color: #e2e8f0; font-size: 11.5px; font-family: monospace;">{r["float_str"]}</span>
</div>
''')

                # 2. HEADER: NAMA KOIN, POTENSI & STATUS BADGE
                col_a, col_b = st.columns([1.1, 1.9])
                with col_a:
                    st.markdown(f"#### {i+1}. {r['coin']} / USDT")
                    st.caption(f"Mark: &#36;{r['cur_p']:,.4f}")
                with col_b:
                    is_long = "LONG" in r['potensi']
                    pot_bg = "#064e3b" if is_long else "#7f1d1d"
                    pot_col = "#34d399" if is_long else "#f87171"
                    pot_text = "🟢 POTENSI LONG" if is_long else "🔴 POTENSI SHORT"

                    if is_touched:
                        stat_badge = '<span style="background: rgba(16, 185, 129, 0.25); color: #34d399; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #10b981; margin-left: 3px;">⚡ POSISI AKTIF</span>'
                    elif last_out and isinstance(last_out, dict):
                        stat_badge = '<span style="background: rgba(59, 130, 246, 0.25); color: #60a5fa; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #3b82f6; margin-left: 3px;">🔄 SETUP BARU</span>'
                    elif "SETUP VALID" in r['valid_label']:
                        stat_badge = '<span style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #3b82f6; margin-left: 3px;">✅ SETUP VALID</span>'
                    else:
                        stat_badge = '<span style="background: rgba(107, 114, 128, 0.2); color: #9ca3af; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #4b5563; margin-left: 3px;">🔍 MEMINDAI</span>'

                    html(f'<div style="text-align: right; padding-top: 2px;"><span style="background: {pot_bg}; color: {pot_col}; font-weight: 800; font-size: 10px; padding: 3px 6px; border-radius: 4px;">{pot_text}</span>{stat_badge}</div>')

                # 3. LEVEL ENTRY (LIMIT), TP, SL (SELALU FRESH & SIAP PASANG)
                st.caption(f"Rencana Limit Order (Lev {r['lev']}x Isolated · Margin &#36;2.00)")
                level_row(r['limit_p'], r['tp_p'], r['sl_p'])

                # 4. WR & METRIK
                html(f'''
<div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #263140; padding-top: 6px; margin-top: 4px;">
<span style="font-size: 11px; font-weight: 700; color: #facc15;">🏆 WR Historis: {r["wr"]:.1f}%</span>
<span style="font-size: 10px; color: #94a3b8;">{r["tier"]}</span>
</div>
<div style="font-size: 9.5px; color: #64748b; margin-top: 2px;">Target TP: +&#36;0.70 USD (+35% ROE) · Stop Loss: -&#36;0.40 USD (-20% ROE)</div>
''')

    st.caption('Pembaruan otomatis berjalan setiap 10 detik. Saat order menyentuh TP atau SL, riwayat keuntungan/kerugian langsung dicatat ke Realized PnL dan bot otomatis memindai setup limit baru yang segar agar Anda selalu siap pasang posisi berikutnya.')

@st.fragment(run_every=10)
def render():
    bias_cards()
