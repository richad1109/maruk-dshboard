"""Compact public signal board. Research stays behind the scenes."""
import time
import json
from pathlib import Path
from html import escape
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import streamlit as st
import mexc_signals as engine
import sniper_limit_engine

WIB=timezone(timedelta(hours=7))

def stamp(t):return datetime.fromtimestamp(t,WIB).strftime('%d %b %H:%M')
def clock_now():return datetime.now(WIB).strftime('%H:%M:%S WIB')
def display_price(value):
    return format(Decimal(format(float(value),'.8g')),'f')

def level_row(entry,tp,sl):
    values=[('Entry (Limit)',entry),('Take Profit',tp),('Stop Loss',sl)]
    cells=''.join(f'<div><span>{label}</span><strong>{escape(display_price(value))}</strong></div>' for label,value in values)
    st.markdown('<div class="compact-levels">'+cells+'</div>',unsafe_allow_html=True)

@st.cache_data(ttl=120,show_spinner=False)
def universe():
    return engine.catalog()

@st.cache_data(ttl=300,show_spinner=False)
def batch(items,rule='automatic-v1'):
    return engine.scan_multi(items)

def visible_signals(results,now=None):
    now=time.time() if now is None else now
    passed=[]
    for r in results:
        t=r.get('test',{})
        if (r.get('side') in (-1,1) and r.get('liquid') and r.get('qualified') and r.get('target90')
            and r.get('closed',now+1)<=now<r.get('expires',0) and t.get('n',0)>=100
            and t.get('wr',0)>=90 and t.get('lower',0)>=80 and (t.get('pf') or 0)>1 and (t.get('mean_r') or 0)>0):
            passed.append(r)
    out=[]
    for symbol in sorted({r['symbol'] for r in passed}):
        group=[r for r in passed if r['symbol']==symbol]
        if len({r['side'] for r in group})==1:out.append(max(group,key=lambda r:(r['test']['lower'],r['test']['n'])))
    return out

@st.cache_data(ttl=10,show_spinner=False)
def touch(signal):return engine.observe_touch(signal)

@st.cache_data(ttl=10,show_spinner=False)
def limit_radar_data():
    try:
        return sniper_limit_engine.scan_all()
    except Exception:
        return []

def limit_validation():
    try:return json.loads((Path(__file__).parent/'limit_validation.json').read_text())
    except (OSError,ValueError):return {}

def bias_cards():
    col_head_left, col_head_right = st.columns([2.5, 1.5])
    with col_head_right:
        st.markdown(f'''
        <div style="text-align: right; padding: 4px 0 8px 0;">
            <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid #10b981;">
                ● LIVE AUTO-REFRESH 10s · {clock_now()}
            </span>
        </div>
        ''', unsafe_allow_html=True)
        if st.button('↻ Refresh Sekarang', key='btn_refresh_now', use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    observations=limit_radar_data()
    if not observations:
        st.warning('Radar limit order sedang menyinkronkan data bursa…')
        return

    valid_count = sum(1 for r in observations if "SETUP VALID" in r['valid_label'])
    touched_count = sum(1 for r in observations if r['is_touched'])
    memindai_count = sum(1 for r in observations if "MEMINDAI" in r['valid_label'])
    longs = sum(1 for r in observations if "LONG" in r['potensi'])
    shorts = sum(1 for r in observations if "SHORT" in r['potensi'])
    
    label = 'DOMINAN LONG' if longs > shorts else 'DOMINAN SHORT' if shorts > longs else 'CAMPURAN / NETRAL'
    
    with col_head_left:
        st.markdown('### Radar Limit Order 20 Koin · ' + label)
        st.caption(f'Top 20 Likuiditas Kripto · {len(observations)} koin aktif | ⚡ {touched_count} Posisi Sedang Mantul (Floating) | ✅ {valid_count} Setup Valid Siaga Pasang | Margin $2.00 USD Isolated')
    
    columns=st.columns(3)
    for i,r in enumerate(observations):
        with columns[i%3]:
            with st.container(border=True):
                # 1. ATASNYA: BANNER FLOATING / STATUS SIKLUS MANTUL & PEMBARUAN SETUP BARU
                if "TP SEBELUMNYA" in r['touch_status']:
                    st.markdown(f'''
                    <div style="background: rgba(16, 185, 129, 0.20); border: 1px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; color: #10b981; font-size: 11px;">🎯 TP SEBELUMNYA HIT (+35% ROE)!</span>
                        <span style="font-weight: 700; color: #34d399; font-size: 11px;">⚡ Setup Baru Siaga ({r['diff_pct']:.2f}%)</span>
                    </div>
                    ''', unsafe_allow_html=True)
                elif "SL SEBELUMNYA" in r['touch_status']:
                    st.markdown(f'''
                    <div style="background: rgba(239, 68, 68, 0.18); border: 1px solid #ef4444; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; color: #f87171; font-size: 11px;">🛑 SL SEBELUMNYA KENA (-36% ROE)</span>
                        <span style="font-weight: 700; color: #f87171; font-size: 11px;">⚡ Setup Baru Siaga ({r['diff_pct']:.2f}%)</span>
                    </div>
                    ''', unsafe_allow_html=True)
                elif r['is_touched']:
                    st.markdown(f'''
                    <div style="background: rgba(16, 185, 129, 0.16); border: 1px solid #10b981; border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; color: #10b981; font-size: 11px;">⚡ LIMIT TERJEMPUT (MANTUL)</span>
                        <span style="font-weight: 800; color: #34d399; font-size: 12px; font-family: monospace;">{escape(r["float_str"])}</span>
                    </div>
                    ''', unsafe_allow_html=True)
                else:
                    st.markdown(f'''
                    <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 6px; padding: 6px 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: #f59e0b; font-size: 11px;">⏳ LIMIT BELUM KESENTUH</span>
                        <span style="font-weight: 700; color: #e2e8f0; font-size: 11.5px; font-family: monospace;">{escape(r["float_str"])}</span>
                    </div>
                    ''', unsafe_allow_html=True)

                # 2. HEADER: NAMA KOIN, POTENSI & STATUS VALIDASI
                col_a, col_b = st.columns([1.1, 1.9])
                with col_a:
                    st.markdown(f"#### {i+1}. {r['coin']} / USDT")
                    st.caption(f"Mark: ${r['cur_p']:,.4f}")
                with col_b:
                    is_long = "LONG" in r['potensi']
                    pot_bg = "#064e3b" if is_long else "#7f1d1d"
                    pot_col = "#34d399" if is_long else "#f87171"
                    pot_text = "🟢 POTENSI LONG" if is_long else "🔴 POTENSI SHORT"
                    
                    if r['is_touched']:
                        stat_badge = '<span style="background: rgba(16, 185, 129, 0.25); color: #34d399; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #10b981; margin-left: 3px;">⚡ TERISI</span>'
                    elif "SETUP VALID" in r['valid_label']:
                        stat_badge = '<span style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #3b82f6; margin-left: 3px;">✅ SETUP VALID</span>'
                    else:
                        stat_badge = '<span style="background: rgba(107, 114, 128, 0.2); color: #9ca3af; font-weight: 700; font-size: 9.5px; padding: 2px 6px; border-radius: 4px; border: 1px solid #4b5563; margin-left: 3px;">🔍 MEMINDAI...</span>'
                        
                    st.markdown(f'''
                    <div style="text-align: right; padding-top: 2px;">
                        <span style="background: {pot_bg}; color: {pot_col}; font-weight: 800; font-size: 10px; padding: 3px 6px; border-radius: 4px;">{pot_text}</span>
                        {stat_badge}
                    </div>
                    ''', unsafe_allow_html=True)

                # 3. LEVEL ENTRY (LIMIT), TP, SL
                st.caption(f"Rencana Limit Order (Lev {r['lev']}x Isolated · Margin $2.00)")
                level_row(r['limit_p'], r['tp_p'], r['sl_p'])

                # 4. WR & METRIC
                st.markdown(f'''
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #263140; padding-top: 6px; margin-top: 4px;">
                    <span style="font-size: 11px; font-weight: 700; color: #facc15;">🏆 WR Historis: {r['wr']:.1f}%</span>
                    <span style="font-size: 10px; color: #94a3b8;">{r['tier']}</span>
                </div>
                <div style="font-size: 9.5px; color: #64748b; margin-top: 2px;">
                    Target TP: +$0.70 USD (+35% ROE) · Stop Loss: -$0.72 USD (-36% ROE)
                </div>
                ''', unsafe_allow_html=True)

    st.caption('Pembaruan otomatis berjalan setiap 10 detik tanpa perlu refresh manual. Saat posisi menyentuh TP atau SL, sistem otomatis memindai dan memperbarui level Limit Order baru agar Anda selalu siap pasang posisi berikutnya.')

@st.fragment(run_every=10)
def render():
    st.query_params['view']='sinyal-kripto'
    bias_cards()
