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
            sniper_limit_engine.load_persistent_state(force_reload=True)
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
        st.caption('Sinkronisasi Langsung MEXC Futures (Akun 1) · Margin Rata ~$1.05 - $1.30 · Leverage 30x Flat')

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
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8; font-weight: 700;">💰 FLOATING PROFIT (BERJALAN DI MEXC)</div>
<div style="font-size: 24px; font-weight: 900; color: {tot_col}; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{sign_tot}&#36;{total_floating_usd:,.4f} USD <span style="font-size: 15px; font-weight: 700;">({sign_tot}{total_floating_roe:,.1f}%)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">Estimasi: <strong style="color: {tot_col};">{sign_tot}Rp {tot_idr:,.0f}</strong> ({active_floating_count} koin mantul aktif di MEXC)</div>
</div>
<div style="background: rgba(59, 130, 246, 0.14); border: 1.5px solid #3b82f6; border-radius: 10px; padding: 12px 16px;">
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #93c5fd; font-weight: 700;">💎 REALIZED PnL (SELESAI DI MEXC HARI INI)</div>
<div style="font-size: 24px; font-weight: 900; color: {real_col}; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{sign_real}&#36;{realized_usd:,.4f} USD <span style="font-size: 15px; font-weight: 700;">({sign_real}{realized_roe:,.1f}%)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">Total Selesai: <strong style="color: {real_col};">{sign_real}Rp {realized_idr:,.0f}</strong> ({total_closed} trade: {tp_count} TP / {sl_count} SL)</div>
</div>
<div style="background: rgba(245, 158, 11, 0.14); border: 1.5px solid #f59e0b; border-radius: 10px; padding: 12px 16px;">
<div style="font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: #fde68a; font-weight: 700;">🏆 WIN RATE (WR) PORTOFOLIO</div>
<div style="font-size: 24px; font-weight: 900; color: #fbbf24; font-family: monospace; letter-spacing: -0.5px; margin-top: 2px;">{avg_portfolio_wr:.1f}% <span style="font-size: 13px; font-weight: 700; color: #94a3b8;">(Historis)</span></div>
<div style="font-size: 11.5px; color: #cbd5e1; margin-top: 2px;">WR Sesi Hari Ini: <strong style="color: #60a5fa;">{realized_wr:.1f}%</strong> ({tp_count} TP / {sl_count} SL)</div>
</div>
</div>
<div style="display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap; border-top: 1px solid #1e293b; padding-top: 12px;">
<div style="display: flex; gap: 8px; flex-wrap: wrap;">
<span style="background: rgba(16, 185, 129, 0.22); border: 1px solid #10b981; color: #34d399; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">● SINKRONISASI MEXC LIVE (100% RIIL)</span>
<span style="background: rgba(16, 185, 129, 0.22); border: 1px solid #10b981; color: #34d399; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">⚡ {active_floating_count} Koin Mantul Aktif</span>
<span style="background: rgba(59, 130, 246, 0.22); border: 1px solid #3b82f6; color: #60a5fa; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">🎯 {tp_count} Sukses Hit TP</span>
<span style="background: rgba(239, 68, 68, 0.22); border: 1px solid #ef4444; color: #f87171; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">🛑 {sl_count} Hit Stop Loss</span>
<span style="background: rgba(245, 158, 11, 0.22); border: 1px solid #f59e0b; color: #f59e0b; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">⏳ {valid_count} Limit Antre</span>
</div>
<div style="font-size: 11px; color: #64748b;">*Data live disinkronkan langsung dari API MEXC Contract Akun 1 · Leverage 30x Flat · TP +35% ROE · SL -30% ROE</div>
</div>
</div>
''')

    # =========================================================================
    # PANEL ATAS 1: KOIN YANG SUDAH HIT TAKE PROFIT (TP) HARI INI & JAMNYA
    # =========================================================================
    tp_trades = summary.get('tp_trades', [])
    sl_trades = summary.get('sl_trades', [])

    if tp_trades:
        tp_cards_html = []
        for t in tp_trades:
            tp_cards_html.append(f'''
<div style="background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10b981; border-radius: 8px; padding: 10px 14px; min-width: 220px; flex: 1;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
    <strong style="color: #34d399; font-size: 14px;">🎯 {t['coin']} / USDT</strong>
    <span style="background: #064e3b; color: #6ee7b7; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">{t['side']}</span>
  </div>
  <div style="font-size: 16px; font-weight: 900; color: #34d399; font-family: monospace;">+${t['pnl_usd']:.4f} USD <span style="font-size: 12px; font-weight: 700;">({t['roe']:+.2f}%)</span></div>
  <div style="font-size: 11px; color: #94a3b8; margin-top: 3px;">Entry: ${t['entry_price']} ➔ Exit: ${t['exit_price']}</div>
  <div style="font-size: 11px; color: #cbd5e1; margin-top: 4px; border-top: 1px dashed rgba(16, 185, 129, 0.3); padding-top: 4px;">
    🕒 Jam TP: <strong style="color: #fde047;">{t['time_str']}</strong>
  </div>
</div>
''')
        cards_str = "".join(tp_cards_html)
        html(f'''
<div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #10b981; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
    <div>
      <span style="font-size: 13.5px; font-weight: 800; color: #34d399; letter-spacing: 0.5px;">🎯 DAFTAR KOIN SUDAH HIT TAKE PROFIT (TP) HARI INI</span>
      <div style="font-size: 11px; color: #94a3b8; margin-top: 1px;">Selesai Otomatis di MEXC Futures · Target +35% ROE Tercapai · Realized PnL Bertambah</div>
    </div>
    <span style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; font-weight: 800; font-size: 11.5px; padding: 3px 10px; border-radius: 6px;">● {len(tp_trades)} KOIN SUKSES TP</span>
  </div>
  <div style="display: flex; gap: 12px; flex-wrap: wrap;">
    {cards_str}
  </div>
</div>
''')

    # Ringkasan Transparan Stop Loss jika ada (Jujur dan Realistis)
    if sl_trades:
        sl_items = []
        for s in sl_trades:
            sl_items.append(f"<span style='background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 3px 8px; border-radius: 5px; font-size: 11px;'>🛑 <strong>{s['coin']}</strong>: -${abs(s['pnl_usd']):.4f} ({s['roe']:+.2f}%) @ {s['time_str']}</span>")
        sl_summary_html = " ".join(sl_items)
        html(f'''
<div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; padding: 8px 14px; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
  <span style="font-size: 11px; font-weight: 700; color: #fca5a5;">🛑 RIWAYAT STOP LOSS HARI INI ({len(sl_trades)} Trade Terpotong Jujur dari Realized PnL):</span>
  <div style="display: flex; gap: 6px; flex-wrap: wrap;">{sl_summary_html}</div>
</div>
''')

    # =========================================================================
    # PANEL ATAS 2: RADAR SINYAL LIMIT BARU & STATUS VERIFIKASI DI MEXC
    # =========================================================================
    new_signals = summary.get('new_signals', [])
    if new_signals:
        sig_rows_html = []
        for s in new_signals:
            is_mexc = s.get('is_mexc_order', False)
            order_id = s.get('order_id', '-')
            t_str = s.get('order_time_str', '-')
            
            if is_mexc:
                status_badge = f'<span style="background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; font-weight: 800; font-size: 11px; padding: 4px 8px; border-radius: 6px;">🟢 SUDAH LIMIT DI MEXC (ID: {order_id})</span>'
            else:
                status_badge = '<span style="background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; color: #fbbf24; font-weight: 800; font-size: 11px; padding: 4px 8px; border-radius: 6px;">🟡 BELUM LIMIT / SIAP PASANG</span>'

            side_col = "#34d399" if "LONG" in s.get('potensi', 'LONG') else "#f87171"
            side_bg = "#064e3b" if "LONG" in s.get('potensi', 'LONG') else "#7f1d1d"

            sig_rows_html.append(f'''
<tr style="border-bottom: 1px solid #1e293b;">
  <td style="padding: 8px 10px; font-weight: 800; font-size: 12px; color: #f8fafc;">⚡ {s['coin']}</td>
  <td style="padding: 8px 10px;"><span style="background: {side_bg}; color: {side_col}; font-weight: 800; font-size: 9.5px; padding: 2px 6px; border-radius: 4px;">{s.get('side', 'LONG')}</span></td>
  <td style="padding: 8px 10px; font-family: monospace; font-weight: 700; color: #38bdf8;">${s['limit_p']}</td>
  <td style="padding: 8px 10px; font-family: monospace; color: #34d399;">${s['tp_p']}</td>
  <td style="padding: 8px 10px; font-family: monospace; color: #f87171;">${s['sl_p']}</td>
  <td style="padding: 8px 10px; color: #fde047; font-size: 11px; font-weight: 700;">🕒 {t_str}</td>
  <td style="padding: 8px 10px; text-align: right;">{status_badge}</td>
</tr>
''')
        rows_str = "".join(sig_rows_html)
        html(f'''
<div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #3b82f6; border-radius: 12px; padding: 14px 18px; margin-bottom: 22px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
    <div>
      <span style="font-size: 13.5px; font-weight: 800; color: #60a5fa; letter-spacing: 0.5px;">⚡ RADAR SINYAL LIMIT BARU & VERIFIKASI STATUS ORDER DI MEXC</span>
      <div style="font-size: 11px; color: #94a3b8; margin-top: 1px;">Pantauan Langsung Orderbook MEXC Akun 1 · Deteksi Otomatis Apakah Sudah Pasang Limit / Belum</div>
    </div>
    <span style="background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; color: #93c5fd; font-weight: 800; font-size: 11.5px; padding: 3px 10px; border-radius: 6px;">● {len(new_signals)} SINYAL LIMIT AKTIF</span>
  </div>
  <div style="overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 11px;">
      <thead>
        <tr style="border-bottom: 1.5px solid #334155; color: #94a3b8; text-transform: uppercase; font-size: 9.5px;">
          <th style="padding: 6px 10px;">Koin</th>
          <th style="padding: 6px 10px;">Arah</th>
          <th style="padding: 6px 10px;">Entry Limit</th>
          <th style="padding: 6px 10px;">Take Profit</th>
          <th style="padding: 6px 10px;">Stop Loss</th>
          <th style="padding: 6px 10px;">Jam Order/Sinyal</th>
          <th style="padding: 6px 10px; text-align: right;">Status di MEXC</th>
        </tr>
      </thead>
      <tbody>
        {rows_str}
      </tbody>
    </table>
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
                is_mexc_order = r.get('is_mexc_order', False)
                order_id = r.get('order_id')
                t_ord = r.get('order_time_str', '-')
                last_out = r.get('last_outcome')

                # 1. BANNER ATAS KARTU
                if is_touched:
                    # Posisi aktif terisi & sedang mantul di MEXC
                    sign = "+" if r['float_usd'] >= 0 else ""
                    f_col = "#34d399" if r['float_usd'] >= 0 else "#f87171"
                    html(f'''
<div style="background: rgba(16, 185, 129, 0.16); border: 1.5px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #10b981; font-size: 11px;">⚡ LIMIT MANTUL (MEXC LIVE)</span>
<span style="font-weight: 800; color: {f_col}; font-size: 12px; font-family: monospace;">{r["float_str"]}</span>
</div>
''')
                elif is_mexc_order:
                    # Order limit antre terpasang di MEXC
                    html(f'''
<div style="background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 800; color: #34d399; font-size: 11px;">🟢 SUDAH LIMIT DI MEXC</span>
<span style="font-weight: 700; color: #cbd5e1; font-size: 11px; font-family: monospace;">ID: {order_id}</span>
</div>
''')
                elif last_out and isinstance(last_out, dict):
                    # Baru selesai TP/SL dan LANGSUNG menerbitkan setup limit baru fresh
                    if last_out.get('outcome') == 'TP':
                        pnl_txt = f"+${last_out.get('pnl_usd', 0.70):.2f}"
                        html(f'''
<div style="background: rgba(16, 185, 129, 0.18); border: 1.5px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #34d399; font-size: 11px;">🎯 HIT TP (+35%) · REALIZED BERTAMBAH</span>
<span style="font-weight: 800; color: #34d399; font-size: 11.5px; font-family: monospace;">{pnl_txt}</span>
</div>
''')
                    else:
                        pnl_txt = f"-${abs(last_out.get('pnl_usd', 0.60)):.2f}"
                        html(f'''
<div style="background: rgba(239, 68, 68, 0.18); border: 1.5px solid #ef4444; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
<span style="font-weight: 700; color: #f87171; font-size: 11px;">🛑 HIT SL (-30%) · REALIZED TERPOTONG</span>
<span style="font-weight: 800; color: #f87171; font-size: 11.5px; font-family: monospace;">{pnl_txt}</span>
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
                    elif is_mexc_order:
                        stat_badge = '<span style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #10b981; margin-left: 3px;">🟢 SUDAH LIMIT</span>'
                    elif last_out and isinstance(last_out, dict):
                        stat_badge = '<span style="background: rgba(59, 130, 246, 0.25); color: #60a5fa; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #3b82f6; margin-left: 3px;">🔄 SETUP BARU</span>'
                    else:
                        stat_badge = '<span style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #f59e0b; margin-left: 3px;">🟡 SIAP PASANG</span>'

                    html(f'<div style="text-align: right; padding-top: 2px;"><span style="background: {pot_bg}; color: {pot_col}; font-weight: 800; font-size: 10px; padding: 3px 6px; border-radius: 4px;">{pot_text}</span>{stat_badge}</div>')

                # 3. LEVEL ENTRY (LIMIT), TP, SL (SELALU FRESH & SIAP PASANG)
                margin_str = f"Margin &#36;{r.get('margin', 1.30):.2f}"
                pos_str = "Posisi Aktif MEXC" if is_touched else "Limit Order Antre MEXC" if is_mexc_order else "Sinyal Limit Siap Pasang"
                st.caption(f"{pos_str} (Lev {r['lev']}x Isolated · {margin_str}) · 🕒 {t_ord}")
                level_row(r['limit_p'], r['tp_p'], r['sl_p'])

                # 4. WR & METRIK
                tp_usd = r.get('margin', 1.30) * 0.35
                sl_usd = r.get('margin', 1.30) * 0.30
                html(f'''
<div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #263140; padding-top: 6px; margin-top: 4px;">
<span style="font-size: 11px; font-weight: 700; color: #facc15;">🏆 WR Historis: {r["wr"]:.1f}%</span>
<span style="font-size: 10px; color: #94a3b8;">{r["tier"]}</span>
</div>
<div style="font-size: 9.5px; color: #64748b; margin-top: 2px;">Target TP: +&#36;{tp_usd:.2f} USD (+35% ROE) · Stop Loss: -&#36;{sl_usd:.2f} USD (-30% ROE)</div>
''')

    st.caption('Pembaruan otomatis berjalan setiap 10 detik. Saat order menyentuh TP atau SL, riwayat keuntungan/kerugian langsung dicatat ke Realized PnL dan bot otomatis memindai setup limit baru yang segar agar Anda selalu siap pasang posisi berikutnya.')

@st.fragment(run_every=10)
def render():
    bias_cards()
