"""Searchable full MEXC contract universe with explicit research coverage."""
import time
from datetime import datetime,timezone,timedelta
import pandas as pd
import streamlit as st
import mexc_signals as engine
WIB=timezone(timedelta(hours=7))
def stamp(t):return datetime.fromtimestamp(t,WIB).strftime('%d %b %Y %H:%M WIB')
@st.cache_data(ttl=120,show_spinner=False)
def universe():
    # Catalog schema v2 includes the official TradFi classification.
    return engine.catalog()
@st.cache_data(ttl=300,show_spinner=False)
def batch(items,rule):return engine.scan(items,rule)
@st.fragment(run_every=60)
def render():
    st.query_params['view']='sinyal-kripto'
    st.markdown('### MEXC / Signal Research Desk')
    st.caption('Seluruh kontrak perpetual USDT aktif dari katalog MEXC · candle 1H tertutup · pembacaan publik tanpa API key pribadi atau pengiriman order.')
    try:
        with st.spinner('Mengambil katalog MEXC…'):coins=universe()
    except Exception as e:st.error('Katalog MEXC belum terbaca: '+type(e).__name__);return
    total=len(coins)
    include=st.toggle('Sertakan kontrak saham / komoditas MEXC',value=False)
    if not include:coins=[m for m in coins if not m.get('tradfi')]
    st.caption(f'{len(coins)} kontrak dalam pilihan dari {total} USDT aktif. Kategori mengikuti label TradFi resmi MEXC.')
    a,b,c=st.columns(3);a.metric('Kontrak tersedia',len(coins));b.metric('Timeframe','1 jam');c.metric('Target WR riset','90% · belum dijamin')
    rule=st.selectbox('Metode tetap',engine.RULES,help='Aturan ditetapkan sebelum periode uji; memilih metode setelah melihat hasil tetap menimbulkan bias seleksi.')
    selected=st.selectbox('Cari semua koin MEXC',[m['symbol'] for m in coins],key='mexc_symbol')
    st.caption('Pemindaian berurutan menurut volume 24 jam. Semua koin bisa dipilih, termasuk yang tidak mengizinkan order API. Katalog ini futures USDT, bukan seluruh aset spot.')
    key='mexc_scan_'+rule+str(include)
    if key not in st.session_state:st.session_state[key]={}
    results=st.session_state[key]
    if not results:
        with st.spinner('Pemindaian awal 12 kontrak terbesar…'):
            for item in batch(coins[:12],rule):results[item['symbol']]=item
    col1,col2=st.columns(2)
    do_selected=col1.button('Analisis koin terpilih',type='primary',width='stretch')
    do_batch=col2.button('Pindai 30 koin berikutnya',width='stretch')
    if do_selected or (results.get(selected,{}).get('expires',float('inf'))<time.time()):
        with st.spinner('Menguji candle riil MEXC…'):
            result=batch([next(m for m in coins if m['symbol']==selected)],rule)[0];results[selected]=result
    if do_batch:
        todo=[m for m in coins if m['symbol'] not in results][:30]
        with st.spinner(f'Memindai {len(todo)} kontrak · maksimal 3 koneksi…'):
            for result in batch(todo,rule):results[result['symbol']]=result
    st.progress(len(results)/max(1,len(coins)),text=f'Cakupan {len(results)} / {len(coins)} kontrak · belum dipindai bukan berarti tidak ada sinyal')
    if results:
        table=[]
        for r in results.values():
            t=r.get('test',{});table.append({'Koin':r['symbol'],'Status':'KEDALUWARSA' if r.get('expires',float('inf'))<time.time() else r.get('status','DATA GAGAL'),'Arah':{1:'LONG',-1:'SHORT',0:'—'}.get(r.get('side'),'—'),'WR uji %':round(t['wr'],2) if t else None,'Trade uji':t.get('n'),'PF uji':round(t['pf'],2) if t.get('pf') is not None else None,'Target 90%': 'Lolos sampel' if r.get('target90') else 'Belum terbukti'})
        st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch')
    r=results.get(selected)
    if not r:st.info('Pilih koin dan tekan Analisis. Hasil tidak dibuat ketika candle belum diperiksa.');return
    if r.get('error'):st.warning(r['message']);return
    if time.time()>r['expires']:st.warning('Hasil melewati masa berlaku. Analisis ulang sebelum memakai rencana harga ini.')
    st.markdown(f"### {selected.replace('_',' / ')} · {r['status']}")
    st.caption(f"Candle close {stamp(r['closed'])} · berlaku sampai {stamp(r['expires'])} · sumber MEXC")
    if r['side']:
        p,q,s=st.columns(3);p.metric('Referensi entry',f"{r['entry']:.8g}");q.metric('Take profit · 2R',f"{r['tp']:.8g}");s.metric('Stop loss · 1R',f"{r['sl']:.8g}")
        st.write('Arah: **'+('LONG' if r['side']==1 else 'SHORT')+'**. Entry adalah referensi close, bukan harga fill aktual. SL berjarak 2 ATR14 dan TP 4 ATR14; level dikunci saat entry pada simulasi.')
    else:st.info('Belum ada setup sesuai aturan pada candle terakhir. TP/SL tidak diterbitkan sebagai sinyal aktif.')
    reasons={'Trend pullback':'EMA20/50/100 searah; candle sebelumnya menyentuh EMA20, close kembali searah tren; RSI dan KER menyaring momentum.', 'Donchian breakout':'Close menembus high/low 24 candle sebelumnya, EMA20/50/100 searah dan KER ≥ 0,35.', 'Range reversal':'KER < 0,20, RSI ekstrem (<28 atau >72), lalu close berbalik dari candle sebelumnya.'}
    st.write('**Alasan / aturan:** '+reasons[rule]);st.caption(f"RSI14 {r['rsi']:.1f} · KER20 {r['ker']:.3f} · ATR14 {r['atr']:.8g}")
    if not r['liquid']:st.warning('Likuiditas belum lolos: perlu volume 24 jam ≥ US$1 juta dan spread ≤ 0,10%.')
    st.markdown('#### Bukti historis · bukan janji akurasi')
    st.caption(f"{r['bars']} candle · {stamp(r['start'])} – {stamp(r['end'])}. Bagian awal 70% untuk pengamatan; 30% terakhir dipisahkan sebagai uji kronologis. Riwayat ini sekitar 83 hari, bukan validasi 1–2 tahun.")
    rows=[]
    for label,k in [('Awal 70%','train'),('Uji akhir 30%','test')]:
        t=r[k];rows.append({'Periode':label,'Trade':t['n'],'Menang bersih':t['wins'],'WR %':round(t['wr'],2),'Batas bawah 95% WR':round(t['lower'],2),'Profit factor R':round(t['pf'],3) if t['pf'] is not None else None,'Ekspektasi R/trade':round(t['mean_r'],3) if t['mean_r'] is not None else None})
    st.dataframe(rows,hide_index=True,width='stretch')
    if not r['qualified']:st.warning('Belum lolos validasi minimum: perlu ≥30 trade uji, PF >1 dan ekspektasi bersih positif. Tidak diberi label sinyal teruji.')
    if not r['target90']:st.info('WR 90% belum terbukti. Label target baru lolos bila ≥100 trade uji, WR ≥90%, batas bawah Wilson 95% ≥80%, dan ekspektasi positif. Ini tetap bukan jaminan WR berikutnya.')
    with st.expander('Biaya, mekanisme replay, dan batas bukti',expanded=False):
        st.write(f"Fee taker katalog saat ini {100*r['fee']:.4f}% per sisi; slippage asumsi {100*r['slip']:.3f}% per sisi; funding adverse asumsi {100*r['funding']:.3f}%/8 jam, diprorata waktu. Fee historis akun dan funding historis belum direkonstruksi; ini bukan biaya aktual lengkap.")
        st.write('Sinyal close → fill open candle berikutnya, satu posisi per koin, timeout 24 jam, jeda 4 candle setelah exit. Jika TP dan SL tersentuh dalam candle sama, SL dihitung lebih dahulu. Gap SL memakai harga open yang lebih buruk. Hasil berbasis return per notional/R, tanpa leverage, compounding, DCA, atau model likuidasi. Kontrak tersedia hari ini menimbulkan survivorship bias. Uji kronologis bukan uji forward; mencoba banyak koin/metode menimbulkan bias seleksi.')
        st.markdown('[Dokumentasi API MEXC](https://www.mexc.com/api-docs/futures/market-endpoints) · [Katalog kontrak sumber](https://api.mexc.com/api/v1/contract/detail)')
    with st.expander('Daftar trade periode uji'):
        trades=[{**t,'entry_at':stamp(t['entry_at']),'exit_at':stamp(t['exit_at'])} for t in r['test']['trades']]
        st.dataframe(trades,hide_index=True,width='stretch') if trades else st.caption('Belum ada trade pada periode uji.')
