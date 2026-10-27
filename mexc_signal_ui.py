"""Compact public signal board. Research stays behind the scenes."""
import time
from html import escape
from datetime import datetime,timezone,timedelta
import streamlit as st
import mexc_signals as engine
WIB=timezone(timedelta(hours=7))

def stamp(t):return datetime.fromtimestamp(t,WIB).strftime('%d %b %H:%M')
@st.cache_data(ttl=120,show_spinner=False)
def universe():
    # Catalog v2 includes the official TradFi classification.
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
    # Opposing qualifying methods mean no clear direction; omit rather than invent consensus.
    out=[]
    for symbol in sorted({r['symbol'] for r in passed}):
        group=[r for r in passed if r['symbol']==symbol]
        if len({r['side'] for r in group})==1:out.append(max(group,key=lambda r:(r['test']['lower'],r['test']['n'])))
    return out

@st.cache_data(ttl=30,show_spinner=False)
def touch(signal):return engine.observe_touch(signal)

@st.fragment(run_every=60)
def render():
    st.query_params['view']='sinyal-kripto'
    now=time.time()
    try:
        coins=[m for m in universe() if not m.get('tradfi')]
    except Exception:
        st.warning('Data MEXC belum tersambung. Sinyal tidak diterbitkan sampai data pulih.');return
    state=st.session_state.setdefault('compact_mexc_v1',{'cursor':0,'results':{},'updated':0})
    refresh=st.button('↻ Perbarui sinyal',key='refresh_mexc_compact')
    if refresh or now-state['updated']>=60:
        start=state['cursor'] if state['cursor']<len(coins) else 0
        todo=coins[start:start+24]
        with st.spinner('Memeriksa pasar MEXC…'):
            scanned=batch(todo)
        for r in scanned:state['results'][r['symbol']]=r
        state['cursor']=start+len(todo);state['updated']=time.time()
    results=[r for group in state['results'].values() for r in group.get('candidates',[])]
    active=visible_signals(results)
    registry=st.session_state.setdefault('mexc_published_cards',{})
    for r in active:
        identity=f"{r['symbol']}:{r['closed']}:{r['side']}"
        if identity not in registry:registry[identity]={**r,'published':time.time(),'outcome':{'status':'AKTIF','at':None}}
    labels={'AKTIF':'SINYAL AKTIF','TP':'✓ TP TERSENTUH','SL':'✕ SL TERSENTUH','AMBIGU':'TP & SL · URUTAN TIDAK PASTI','KEDALUWARSA':'MASA BERLAKU SELESAI'}
    reasons={'Trend pullback':'Pantulan terkonfirmasi searah tren.','Donchian breakout':'Penembusan rentang searah momentum.','Range reversal':'Pembalikan harga di dalam rentang.'}
    st.markdown(f'<div class="signal-hero"><div><div class="eyebrow">MEXC / SINYAL KRIPTO</div><h2>{"Peluang terpilih." if active else "NETRAL · menunggu peluang."}</h2><p>{len(active)} sinyal lolos · diperiksa {stamp(state["updated"])} WIB</p></div></div>',unsafe_allow_html=True)
    if not registry:st.info('Belum ada koin yang lolos syarat WR historis ≥90% dengan sampel cukup. Kartu muncul otomatis ketika ada sinyal yang memenuhi syarat.')
    columns=st.columns(2)
    recent=sorted(registry.values(),key=lambda r:r['published'],reverse=True)[:20]
    for i,r in enumerate(recent):
        unknown=False
        if r['outcome']['status']=='AKTIF':
            try:r['outcome']=touch(r)
            except Exception:unknown=True
        outcome=r['outcome'];status=outcome['status'];color='#a8d18d' if status=='TP' else '#f09292' if status=='SL' else '#b6c5d5'
        with columns[i%2]:
            with st.container(border=True):
                st.markdown(f"### {escape(r['symbol'].replace('_',' / '))} · {'LONG' if r['side']==1 else 'SHORT'}")
                st.markdown(f'<strong style="color:{color}">{labels[status]}</strong>',unsafe_allow_html=True)
                a,b,c=st.columns(3);a.metric('Entry',f"{r['entry']:.8g}");b.metric('TP',f"{r['tp']:.8g}");c.metric('SL',f"{r['sl']:.8g}")
                st.write(reasons.get(r['rule'],'Kondisi teknikal terkonfirmasi.'))
                st.caption(f"WR uji {r['test']['wr']:.1f}% · {r['test']['n']} transaksi · berlaku sampai {stamp(r['expires'])} WIB")
                if outcome.get('at'):st.caption('Level teramati pada candle 1 menit '+stamp(outcome['at'])+' WIB')
                if unknown:st.warning('Pemeriksaan harga gagal; status TP/SL belum diketahui.')
    st.caption('Pantauan level harga, bukan bukti order terisi. WR historis ≥90% tidak menjamin hasil berikutnya. Pembaruan setiap 60 detik selama halaman terbuka.')
    with st.expander('Status data & validasi',expanded=False):
        errors=sum(bool(r.get('error')) for r in state['results'].values())
        st.write(f"{len(state['results'])} / {len(coins)} kontrak kripto sudah diperiksa pada sesi ini; {errors} gagal dibaca. Pemindaian berjalan bertahap menurut volume. Bagian yang belum diperiksa tidak dianggap tanpa sinyal.")
        st.caption('Kartu dipantau sejak diterbitkan dalam sesi browser ini; riwayat sesi dapat hilang saat browser/server dimulai ulang. Pemeriksaan memakai candle 1 menit penuh setelah penerbitan, sehingga sentuhan pada menit pertama dapat terlewat. Jika TP/SL kena di menit yang sama, urutannya tidak diasumsikan.')
        st.write('Sinyal hanya tampil jika data masih berlaku, likuiditas lolos, minimal 100 transaksi uji, WR ≥90%, batas bawah Wilson 95% ≥80%, PF >1, dan ekspektasi bersih positif. Hasil terakhir yang kedaluwarsa disembunyikan. Arah yang bertentangan tidak diterbitkan.')
        st.write('Uji kronologis 70% awal / 30% akhir dari sekitar 83 hari candle 1H. Fee memakai katalog saat ini; slippage 0,05% per sisi dan funding adverse 0,01%/8 jam adalah asumsi, bukan riwayat biaya aktual lengkap. SL didahulukan bila TP/SL tersentuh pada candle yang sama. Uji forward dan validasi 1–2 tahun belum tersedia; pemilihan banyak koin/metode dapat menimbulkan bias seleksi.')
        st.caption('Sumber: API publik MEXC. Tidak memakai kredensial trading pribadi untuk analisis ini.')
