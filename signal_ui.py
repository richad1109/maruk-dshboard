"""Read-only scenario room; market observations, conditional plans, explicit provenance."""
from datetime import datetime,timezone,timedelta
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import signal_room

WIB=timezone(timedelta(hours=7))


@st.cache_data(ttl=60,show_spinner=False)
def room_data():
    return signal_room.fetch()


def when(value):
    return datetime.fromtimestamp(value,WIB).strftime('%d %b %Y · %H:%M WIB')


def render():
    from maruk_ui import html,heading,price,kpi,empty
    initial=str(st.query_params.get('project','btc')).upper()
    initial=initial if initial in signal_room.COINS else 'BTC'
    controls=st.columns([1,2,1])
    with controls[0]:base=st.selectbox('Pasar analisis',list(signal_room.COINS),index=list(signal_room.COINS).index(initial),key='signal_coin')
    with controls[1]:st.caption('Candle tertutup · pembaruan 60 detik · tanpa eksekusi order')
    with controls[2]:
        if st.button('↻ Perbarui analisis',width='stretch'):room_data.clear()
    st.query_params['view']='sinyal-auto';st.query_params['project']=base.lower()

    @st.fragment(run_every=60)
    def panel():
        with st.spinner('Membaca candle, funding, dan sentimen publik…'):result=room_data()
        tiles=st.columns(3)
        for coin,col in zip(signal_room.COINS,tiles):
            item=result['reports'].get(coin)
            with col:
                kpi(coin+' / USDT · close 1H',price(item['technical']['close']) if item else '—',
                    item['state'] if item else 'Candle belum tersedia','chart')
        item=result['reports'].get(base)
        if not item:
            empty('Analisis '+base+' belum tersedia','Candle gagal dibaca, tidak lengkap, atau usang. Tidak ada arah atau harga pengganti.')
            return
        t=item['technical'];fund=result['funding'].get(base)
        css='long' if item['side']>0 else 'short' if item['side']<0 else 'neutral'
        html(f'<div class="signal-hero {css}"><div><span class="signal-eyebrow">KANTOR RAKUS / SCENARIO DESK / {base}</span><h2>{escape(t["bias"])}</h2><p>EMA20/50/100 pada 4H dan RSI14 pada 1H. Bias kondisi sekarang; skenario berikutnya memerlukan konfirmasi harga.</p><div class="signal-badge">{escape(item["state"])} · pemeriksaan teknikal</div></div><div class="signal-hero-price"><small>CLOSE 1H TERVERIFIKASI</small><strong>{price(t["close"])}</strong><span>{t["change24"]:+.2f}% / 24 jam dari candle</span></div></div>')
        st.caption('Sumber: BingX USDT perpetual · candle 1H selesai '+when(t['closed_at'])+' · candle 4H selesai '+when(t['four_closed_at'])+'. Harga close berbeda dari mark price berjalan.')
        cols=st.columns(4)
        metrics=[('RSI14 / 1H',f'{t["rsi"]:.1f}','Momentum 0–100'),
                 ('Momentum / 12H',f'{item["momentum12"]:+.2f}%','Dari tiga candle 4H'),
                 ('Efisiensi / KER20',f'{item["ker"]:.2f}','Filter kandidat ≥0,35'),
                 ('Volume relatif / 1H',f'{item["volume_ratio"]:.2f}×' if item['volume_ratio'] is not None else '—','Terhadap20 jam sebelumnya')]
        for col,(label,value,note) in zip(cols,metrics):
            with col:kpi(label,value,note,'activity')

        left,right=st.columns([2,1])
        with left:
            with st.container(border=True):
                heading(base+' / USDT','Candle1H · level dari data tertutup')
                rows=t['candles'];times=[datetime.fromtimestamp(r['time'],WIB) for r in rows]
                fig=go.Figure(go.Candlestick(x=times,open=[r['open'] for r in rows],high=[r['high'] for r in rows],
                    low=[r['low'] for r in rows],close=[r['close'] for r in rows],
                    increasing_line_color='#b9ef78',decreasing_line_color='#ff8394',name=base))
                fig.add_hline(y=t['resistance'],line_dash='dot',line_color='#b9ef78',annotation_text='Resistance24H')
                fig.add_hline(y=t['support'],line_dash='dot',line_color='#ff8394',annotation_text='Support24H')
                fig.update_layout(height=390,margin=dict(l=4,r=12,t=12,b=0),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#9aadc1'),xaxis=dict(rangeslider_visible=False,showgrid=False),
                    yaxis=dict(side='right',gridcolor='#23303c'),showlegend=False,uirevision='scenario-'+base)
                st.plotly_chart(fig,width='stretch',config={'displayModeBar':False})
                st.caption('Rentang memakai24 candle sebelum candle terakhir. Status sekarang: '+t['range_break']+'.')
        with right:
            with st.container(border=True):
                heading('Checklist kandidat','Aturan Bot Final · bukan status order')
                checks=[('|Momentum 12H| ≥2,5%',abs(item['momentum12'])>=2.5),('KER20 ≥0,35',item['ker']>=.35),
                        ('SL 2 ATR ≤2,5%',2*item['atr4']/t['close']<=.025)]
                if base!='BTC':
                    checks.extend([('Korelasi BTC ≥0,65',item['correlation'] is not None and item['correlation']>=.65),
                                   ('Arah sejalan BTC',bool(item['side']))])
                for label,passed in checks:
                    html(f'<div class="signal-check"><span>{escape(label)}</span><b class="{ "pass" if passed else "wait" }">{ "LOLOS" if passed else "TUNGGU" }</b></div>')
                if item['reasons']:
                    st.caption(' · '.join(item['reasons']))
                else:st.caption('Kondisi teknikal lolos. Saldo, cooldown, kuota, harga fill dan batas bursa belum diperiksa oleh panel ini.')
                st.caption('ATR14 / 4H: '+price(item['atr4'])+' · Korelasi BTC: '+(f'{item["correlation"]:.3f}' if item['correlation'] is not None else 'belum cukup data'))

        heading('Skenario berikutnya','Bersyarat; tidak diberi probabilitas yang belum diuji')
        cards=st.columns(3)
        for scenario,col in zip(item['scenarios'],cards):
            with col:
                if 'trigger' in scenario:
                    up=scenario['name'].startswith('Naik')
                    direction='di atas' if up else 'di bawah'
                    html(f'<div class="scenario-card {"bull" if up else "bear"}"><span>{escape(scenario["name"])}</span><h3>{price(scenario["trigger"])}</h3><p>Konfirmasi: close 1H {direction} level, lalu retest bertahan.</p><dl><dt>Zona lanjutan1 / 2</dt><dd>{price(scenario["target1"])} / {price(scenario["target2"])}</dd><dt>Invalidasi</dt><dd>Close kembali masuk rentang melewati {price(scenario["invalidation"])}</dd></dl></div>')
                else:
                    html(f'<div class="scenario-card"><span>Rentang / sideways</span><h3>Tunggu arah</h3><p>Selama close bertahan di antara support dan resistance.</p><dl><dt>Batas bawah / atas</dt><dd>{price(scenario["low"])} / {price(scenario["high"])}</dd><dt>Perubahan kondisi</dt><dd>Close keluar rentang dan retest terkonfirmasi.</dd></dl></div>')
        st.caption('Zona lanjutan1/2 = level pemicu ±1/2 ATR 1H. Ini ukuran volatilitas, bukan jaminan harga akan sampai atau peluang statistik. Retest belum diverifikasi otomatis.')

        tabs=st.tabs(['Rencana TP / SL','Derivatif & sentimen','Indikator & sumber'])
        with tabs[0]:
            heading('Dua rencana bersyarat','Referensi close terakhir; bukan instruksi entry sekarang')
            st.dataframe(pd.DataFrame([{'Arah':p['side'],'Entry referensi':price(p['entry']),'SL 2 ATR 4H':price(p['sl']),
                'TP 10R':price(p['tp']),'Jarak SL':f'{p["risk_pct"]:.2f}%','Status':'Kandidat teknikal' if p['selected'] else 'Belum dikonfirmasi'} for p in item['plans']]),hide_index=True,width='stretch')
            st.caption('TP 10R adalah aturan rencana, bukan prediksi harga. Funding, spread, fee, slippage, margin, kuota dan likuidasi tidak dinilai pada tabel ini. Order aktual dan TP/SL server dipantau di menu Bot Sakti.')
        with tabs[1]:
            if fund:
                cols=st.columns(3)
                with cols[0]:kpi('Mark price',price(fund['mark']),'Snapshot publik BingX','chart')
                with cols[1]:kpi('Funding terakhir',f'{fund["rate_pct"]:+.5f}%',('Interval '+str(fund['interval_hours'])+' jam') if fund['interval_hours'] is not None else 'Interval belum tersedia','activity')
                with cols[2]:kpi('Mark / index premium',f'{fund["premium_pct"]:+.4f}%','Bukan spread order book','layers')
                st.caption('Snapshot diambil '+when(fund['observed_at'])+' · timestamp pembaruan rate '+when(fund['updated_at'])+' · jadwal funding berikut: '+when(fund['next_at'])+'. Rate dapat berubah sebelum settlement; timestamp tick mark price tidak diberikan terpisah.')
            else:st.info('Snapshot funding belum dapat diverifikasi; rate dan mark price tidak ditampilkan.')
            sentiment=result.get('sentiment')
            if sentiment:
                latest=sentiment['latest']
                st.markdown('**Fear & Greed: '+str(latest['value'])+'/100 · '+escape(latest['label'])+'**')
                st.progress(latest['value']/100)
                st.markdown('Sumber: [Alternative.me · Crypto Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/) · '+when(latest['time'])+'. Indeks pasar kripto, bukan skor khusus '+base+'.')
                if sentiment['stale']:st.warning('Indeks sentimen sudah lebih dari48 jam; perhatikan tanggal sumber.')
            else:st.info('Indeks sentimen belum tersedia dari sumbernya.')
        with tabs[2]:
            st.dataframe(pd.DataFrame([{'Indikator':'EMA'+str(n)+' /4H','Nilai':price(t['ema'+str(n)])} for n in (20,50,100)]),hide_index=True,width='stretch')
            st.write('Sumber candle dan funding: endpoint publik BingX USDT perpetual. Riwayat dimuat: '+str(item['provenance']['hours'])+' candle 1H. Tidak ada candle berjalan yang dipakai untuk sinyal.')
            st.caption('Metode deterministik dari EMA, RSI, KER, ATR dan korelasi. Bukan hasil AI agent/quantum dan belum dikalibrasi menjadi probabilitas. Riwayat indikator panel lebih pendek dari cache bot Termux; sinyal dan eksekusinya tidak dijamin identik.')
            st.link_button('Dokumentasi pasar BingX','https://bingx-api.github.io/docs/#/en-us/swapV2/market-api.html',width='stretch')
        html('<div class="footnote"><span>KANTOR RAKUS / SCENARIO DESK</span><span>DATA PUBLIK · TANPA ORDER · '+escape(when(result['fetched']))+'</span></div>')
    panel()
