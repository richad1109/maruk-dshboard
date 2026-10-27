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

@st.cache_data(ttl=30,show_spinner=False)
def touch(signal):return engine.observe_touch(signal)

@st.cache_data(ttl=30,show_spinner=False)
def limit_radar_data():
    try:
        return sniper_limit_engine.scan_all()
    except Exception:
        return []

def limit_validation():
    try:return json.loads((Path(__file__).parent/'limit_validation.json').read_text())
    except (OSError,ValueError):return {}

def bias_cards():
    observations=limit_radar_data()
    if not observations:
        st.warning('Radar limit order sedang menyinkronkan data bursa…')
        return

    valid_count = sum(1 for r in observations if "SETUP VALID" in r['valid_label'])
    memindai_count = sum(1 for r in observations if "MEMINDAI" in r['valid_label'])
    touched_count = sum(1 for r in observations if r['is_touched'])
    longs = sum(1 for r in observations if "LONG" in r['potensi'])
    shorts = sum(1 for r in observations if "SHORT" in r['potensi'])
    
    label = 'DOMINAN LONG' if longs > shorts else 'DOMINAN SHORT' if shorts > longs else 'CAMPURAN / NETRAL'
    
    st.markdown('### Radar Limit Order 20 Koin · ' + label)
    st.caption(f'Top 20 Likuiditas Kripto · {len(observations)} koin terpantau | ✅ {valid_count} Setup Valid Siaga | ⚡ {touched_count} Limit Terisi Mantul | 🔍 {memindai_count} Memindai | Aturan: Margin $2.00 USD Isolated')
    
    columns=st.columns(3)
    for i,r in enumerate(observations):
        with columns[i%3]:
            with st.container(border=True):
                # 1. ATASNYA: FLOATING PROFIT BANNER / STATUS SENTUHAN LIMIT
                if r['is_touched']:
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

    st.caption('Setup Limit Order memanfaatkan zona pantulan likuiditas wick (Whale Sweep). Limit tidak mengejar pasar (market order), melainkan menunggu jemputan harga di titik diskon/ekstrem dengan Stop Loss ketat di luar noise wick dan target TP realistis 1:1 R:R (+35% ROE). Angka Win Rate didasarkan pada audit backtest 2 tahun riil.')

@st.fragment(run_every=60)
def render():
    st.query_params['view']='sinyal-kripto'
    bias_cards()
