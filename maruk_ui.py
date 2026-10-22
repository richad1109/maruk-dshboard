"""Maruk Terminal: eight-wallet, read-only portfolio interface."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import os
import time
import json
import hashlib

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import maruk_data as data
import sakti_monitor

ROOT=Path(__file__).resolve().parent
WIB=timezone(timedelta(hours=7))
PALETTE=["#b9df8a","#91b4c8","#d8bb87"]
PAGE={"Ringkasan":("Semua akun. Satu pandangan.","Pantau portofolio, pergerakan pasar, dan posisi dalam satu ruang."),
      "Posisi & Bursa":("Setiap posisi, lebih jelas.","Detail eksposur dan koneksi delapan wallet di tiga bursa."),
      "Bot Sakti":("Satu sistem. Setiap langkah terpantau.","Jurnal, peringatan proteksi, dan parameter Health25–20×."),
      "Kantor 3D":("Welcome to your trading floor.","Tiga meja. Delapan wallet. Satu ruang untuk melihat semuanya."),
      "Market Intel":("Konteks sebelum keputusan.","Pergerakan pasar dan asisten untuk membaca konteks makro.")}


def icon(name):
    paths={"wallet":'<path d="M20 7H5a2 2 0 0 1 0-4h13v4M5 7H3v13h17V7M20 12h-5v4h5"/>',
      "activity":'<path d="M2 12h4l3-8 5 16 3-8h5"/>',
      "layers":'<path d="m3 7 9-5 9 5-9 5-9-5m0 5 9 5 9-5M3 17l9 5 9-5"/>',
      "chart":'<path d="M4 3v17h17M7 15l4-5 4 3 5-7"/>',
      "scan":'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 12h18"/>',
      "shield":'<path d="m12 2 8 4v6c0 6-8 10-8 10S4 18 4 12V6l8-4m-4 10 3 3 5-6"/>'}
    return '<svg viewBox="0 0 24 24" aria-hidden="true">'+paths.get(name,paths["chart"])+"</svg>"


def html(value):st.markdown(value,unsafe_allow_html=True)


def money(value,signed=False):
    if value is None:return "—"
    return ("+" if signed and value>0 else "−" if value<0 else "")+f"${abs(value):,.2f}"


def price(value):
    if value is None:return "—"
    return f"${value:,.2f}" if abs(value)>=1000 else f"${value:,.4f}" if abs(value)>=1 else f"${value:,.6f}"


def pct(value):return "—" if value is None else f"{value:+.2f}%"


def tone(value):return "positive" if value is not None and value>0 else "negative" if value is not None and value<0 else ""


def age(value):
    if value is None:return "waktu belum tersedia"
    seconds=max(0,int(time.time()-value))
    if seconds<60:return f"{seconds} dtk lalu"
    if seconds<3600:return f"{seconds//60} menit lalu"
    if seconds<86400:return f"{seconds//3600} jam lalu"
    return datetime.fromtimestamp(value,WIB).strftime("%d %b %Y · %H:%M WIB")


def secrets():
    try:return st.secrets.to_dict()
    except (FileNotFoundError,st.errors.StreamlitSecretNotFoundError):return {}


@st.cache_data(ttl=15,show_spinner=False)
def portfolio(_credentials,credential_key=""):return data.fetch_portfolio(_credentials)


@st.cache_data(ttl=30,show_spinner=False)
def market(base):return data.market_data(base)


def heading(title,note=""):
    html(f'<div class="section-head"><h3>{escape(title)}</h3><span>{escape(note)}</span></div>')


def empty(title,description):
    html(f'<div class="empty-state">{icon("scan")}<strong>{escape(title)}</strong><p>{escape(description)}</p></div>')


def kpi(label,value,note,kind="wallet",color=""):
    html(f'<div class="kpi"><div class="kpi-label">{escape(label)}<span class="kpi-icon">{icon(kind)}</span></div><div class="kpi-value {color}">{escape(value)}</div><div class="kpi-note">{escape(note)}</div></div>')


def ticker_strip(info):
    if not info["tickers"]:return
    items=""
    for row in info["tickers"][:6]:
        items+=f'<div class="ticker-item"><div class="ticker-symbol">{escape(row["coin"])} <span style="color:#57697e">/ USDT</span></div><div class="ticker-price">{price(row["price"])} <span class="ticker-change {tone(row["change"])}">{pct(row["change"])}</span></div></div>'
    html('<div class="ticker-strip">'+items+'</div>')


def chart(info,base):
    with st.container(border=True):
        html(f'<div class="surface-heading"><span class="title">{escape(base)} / USDT</span><span class="detail">Market overview · 1H</span></div>')
        ticker=next((t for t in info["tickers"] if t["coin"]==base),{})
        html(f'<span class="market-price">{price(ticker.get("price"))}</span><span class="market-change {tone(ticker.get("change"))}">{pct(ticker.get("change"))} <span style="color:#6b7e92">24h</span></span>')
        candles=info["candles"]
        if not candles:empty("Grafik belum tersedia","Menunggu candle publik dari bursa. Harga ilustrasi tidak dipakai sebagai pengganti data live.")
        else:
            times=[datetime.fromtimestamp(c["time"],WIB) for c in candles]
            closes=[c["close"] for c in candles]
            fig=go.Figure(go.Scatter(x=times,y=closes,mode="lines",line=dict(color="#b9df8a",width=2),
                fill="tozeroy",fillcolor="rgba(166,207,125,.055)",hovertemplate="%{x|%d %b %H:%M WIB}<br>$%{y:,.3f}<extra></extra>"))
            lo,hi=min(closes),max(closes);pad=(hi-lo)*.2 or lo*.02
            fig.update_layout(height=265,margin=dict(l=0,r=7,t=16,b=0),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans",color="#8092a8",size=10),showlegend=False,hovermode="x unified",
                xaxis=dict(showgrid=False,tickformat="%d %b",zeroline=False,showline=False),
                yaxis=dict(side="right",gridcolor="#23303c",zeroline=False,range=[lo-pad,hi+pad],tickprefix="$"),
                hoverlabel=dict(bgcolor="#1a2633",bordercolor="#405345",font_size=11),uirevision=base)
            st.plotly_chart(fig,width="stretch",config=dict(displayModeBar=False,scrollZoom=False))
        html(f'<div class="chart-caption">{escape(info["source"])} · candle 1 jam tertutup · {escape(age(info["fetched"]))}</div>')


def allocation(summary):
    with st.container(border=True):
        html('<div class="surface-heading"><span class="title">Distribusi dana</span><span class="detail">Per bursa</span></div>')
        values=[sum(r["equity"] for r in summary["rows"] if r["exchange"]==v and r["equity"] is not None) for v in data.EXCHANGES]
        if sum(values)>0:
            fig=go.Figure(go.Pie(values=values,labels=data.EXCHANGES,hole=.79,sort=False,
                marker=dict(colors=PALETTE,line=dict(color="#10161f",width=5)),textinfo="none",hovertemplate="%{label}<br>$%{value:,.2f}<extra></extra>"))
            fig.update_layout(height=198,margin=dict(l=20,r=20,t=10,b=0),showlegend=False,paper_bgcolor="rgba(0,0,0,0)",
                annotations=[dict(text=f'<b>{summary["known"]}</b><br><span style="font-size:10px;color:#798a9e">wallet terbaca</span>',x=.5,y=.5,
                                  font=dict(size=28,color="#e5edf6",family="Manrope"),showarrow=False)])
            st.plotly_chart(fig,width="stretch",config=dict(displayModeBar=False))
        else:html('<div style="height:190px;display:flex;align-items:center;justify-content:center;color:#65788e;font-size:12px">Menunggu saldo bursa</div>')
        for venue,value,color in zip(data.EXCHANGES,values,PALETTE):
            count=sum(r["equity"] is not None for r in summary["rows"] if r["exchange"]==venue)
            html(f'<div class="allocation-key"><span class="allocation-label"><span class="legend-dot" style="--accent:{color}"></span>{venue}</span><span class="allocation-value">{money(value) if count else "—"}</span></div>')


def account_cards(snapshot):
    heading("Tiga akun. Satu portofolio.","Bitget · MEXC · BingX")
    for i,col in enumerate(st.columns(3)):
        with col:
            summary=data.totals(snapshot,data.ACCOUNTS[i])
            live=summary["live"] if snapshot["mode"]!="demo" else summary["expected"]
            label="PRATINJAU" if snapshot["mode"]=="demo" else f'{live}/{summary["expected"]} LIVE'
            bars=''.join(f'<span style="height:{v}px"></span>' for v in [10,16,12,22,15,19,23,17,21])
            html(f'<div class="account-card"><div class="account-top"><span class="account-id"><span class="account-avatar">0{i+1}</span>Akun {i+1}</span><span class="chip {"neutral" if live<summary["expected"] else ""}">{label}</span></div>'
                 f'<div class="account-value">{money(summary["equity"])}</div><div class="account-muted">Equity futures · USDT</div><div class="account-bottom"><span>{len(summary["positions"])} posisi · <span class="{tone(summary["floating"])}">{money(summary["floating"],True)}</span></span><div class="micro-bars" aria-hidden="true">{bars}</div></div></div>')


def position_cards(positions,limit=None):
    if not positions:
        empty("Belum ada posisi yang terbaca","Posisi akan muncul saat data bursa atau sinkronisasi bot tersedia.")
        return
    cols=st.columns(2)
    for i,p in enumerate(positions[:limit] if limit else positions):
        with cols[i%2]:
            values=[("Entry",price(p.get("entry"))),("Mark",price(p.get("mark"))),("Margin",money(p.get("margin"))),
                    ("Stop loss",price(p.get("stop"))),("Take profit",price(p.get("take"))),("Likuidasi",price(p.get("liquidation")))]
            grid=''.join(f'<div><span>{label}</span><strong>{value}</strong></div>' for label,value in values)
            lev=f'{p["leverage"]:g}×' if p.get("leverage") else '—'
            wallet=str(p.get("account",""))+"/"+p["exchange"].lower()
            manual=str(p["symbol"]).split("/")[0] in sakti_monitor.MANUAL.get(wallet,set())
            html('<div class="manual-tag">'+('MANUAL · TIDAK DIKELOLA BOT' if manual else 'POSISI BURSA · MONITOR SAJA')+'</div>')
            html(f'<div class="position-card"><div class="position-top"><span class="position-symbol">{escape(str(p["symbol"]))}</span><span class="side-pill {"short" if p["side"]=="SHORT" else ""}">{escape(str(p["side"]))} · {lev}</span></div>'
                 f'<div class="position-venue">{escape(p["exchange"])} / {escape(str(p.get("account","")).replace("akun_","Akun "))}</div><div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:20px"><span class="position-pnl {tone(p.get("pnl"))}">{money(p.get("pnl"),True)}</span><span class="{tone(p.get("roe"))}" style="font-size:11px">{pct(p.get("roe"))} ROE</span></div><div class="position-grid">{grid}</div></div>')


def overview(snapshot,info,summary,base):
    left,right=st.columns([1.25,1])
    with left:
        complete="Delapan koneksi" if summary["complete"] and summary["expected"]==8 else f'{summary["known"]}/{summary["expected"]} wallet terbaca'
        html(f'<div class="hero"><div class="hero-top"><span class="hero-label">{icon("wallet")}Total equity futures</span><span class="chip neutral">USDT</span></div><div class="hero-value">{money(summary["equity"])}<small>USDT</small></div><div class="hero-sub"><span class="dot"></span>{complete} · {"data ilustrasi" if snapshot["mode"]=="demo" else "saldo yang berhasil dibaca"}</div><div class="hero-bottom"><div><span>Saldo tersedia</span><strong>{money(summary["free"])}</strong></div><div><span>Margin posisi</span><strong>{money(summary["margin"]) if summary["positions"] else "—"}</strong></div><div><span>Dana tersisih tercatat</span><strong>{money(snapshot["reserved"])}</strong></div></div><div class="hero-watermark">RAKUS</div></div>')
    with right:
        office()
    cols=st.columns(4)
    with cols[0]:kpi("Floating PnL",money(summary["floating"],True),"Posisi bursa yang terbaca","activity",tone(summary["floating"]))
    with cols[1]:kpi("Posisi terbaca",str(len(summary["positions"])),"Termasuk posisi manual · monitor saja","layers")
    with cols[2]:kpi("Koneksi bursa",f'{summary["live"]}/{summary["expected"]}',"MEXC akun 3 dinonaktifkan","shield")
    closed=[t for t in snapshot["trades"] if st.session_state.get("account","all")=="all" or t["account"]==st.session_state["account"]]
    with cols[3]:kpi("Realized PnL bot",money(sum(t["net_pnl"] for t in closed),True) if closed else "—","Dari jurnal · tidak termasuk DCA","chart",tone(sum(t["net_pnl"] for t in closed)) if closed else "")
    ticker_strip(info)
    left,right=st.columns([2.25,1])
    with left:chart(info,base)
    with right:allocation(summary)
    account_cards(snapshot)
    heading("Posisi aktif","Floating PnL dari sumber yang ditampilkan")
    position_cards(summary["positions"],limit=4)


def office():
    # Static authored HTML only; no credentials or exchange data enters JS.
    st.iframe(ROOT/'assets/office.html',height=367,tab_index=0,alt='Kantor Rakus 3D interaktif')


def positions_page(snapshot,summary):
    heading("Koneksi delapan wallet","Status live dan snapshot dibedakan")
    labels={"live":"LIVE","snapshot":"SNAPSHOT","error":"GAGAL TERHUBUNG","unconfigured":"BELUM DIATUR","demo":"PRATINJAU"}
    rows=[{"Akun":r["account"].replace("akun_","Akun "),"Bursa":r["exchange"],"Status":labels[r["status"]],
        "Equity (USDT)":r["equity"],"Tersedia (USDT)":r["free"],"Floating (USDT)":r["floating"],"Posisi":len(r["positions"]),"Diperbarui":age(r["updated"])} for r in summary["rows"]]
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch",column_config={k:st.column_config.NumberColumn(format="$%.2f") for k in ["Equity (USDT)","Tersedia (USDT)","Floating (USDT)"]})
    direction=st.selectbox("Filter arah",["Semua arah","LONG","SHORT"],key="position_direction")
    heading("Detail posisi","Tanda — berarti data tidak diberikan sumber")
    selected=summary["positions"] if direction=="Semua arah" else [p for p in summary["positions"] if p["side"]==direction]
    position_cards(selected)
    st.caption("SL/TP yang tampil adalah harga yang terbaca, bukan konfirmasi bahwa order proteksinya sudah diverifikasi dashboard.")


def strategy_page(snapshot):
    heading("Bot Sakti / Health25", "20× isolated · maksimum 2 posisi per wallet")
    runtime=st.session_state.get("sakti_upload") or snapshot.get("runtime")
    with st.expander("Hubungkan jurnal dari Termux",expanded=not bool(runtime)):
        st.write("Saldo dan posisi dibaca langsung dari bursa. Jurnal hasil trade, target dan peringatan bot memerlukan state Bot Sakti dari HP.")
        uploaded=st.file_uploader("Unggah sakti_monitor.json atau sakti_live_state.json",type=['json'],key='sakti_file')
        if uploaded:
            try:
                if uploaded.size>2_000_000:raise ValueError('File terlalu besar')
                runtime=sakti_monitor.sanitize(json.loads(uploaded.getvalue()))
                st.session_state['sakti_upload']=runtime
                st.success("Snapshot jurnal diterima. Ini snapshot unggahan, bukan koneksi proses Termux live.")
            except (ValueError,TypeError,KeyError):st.error("File bukan state Bot Sakti yang valid. Jangan unggah konfigurasi API.")
        st.caption("Untuk sinkronisasi file di server, gunakan SAKTI_STATE_PATH. Tidak ada tombol close/cancel pada dashboard ini.")
    if runtime:
        metrics=sakti_monitor.metrics(runtime)
        phase={'c8':'Health25','cashout':'Menutup posisi bot untuk target','stopped':'Target stop · entry berhenti'}.get(runtime.get('phase'),'Fase belum dikenal')
        html('<div class="data-notice">JURNAL TERSINKRON · '+escape(phase)+' · status dari snapshot, bukan bukti proses HP sedang hidup.</div>')
        cols=st.columns(3)
        with cols[0]:kpi('Realized PnL bot',money(metrics['realized'],True),'Fee/funding sesuai jurnal','activity',tone(metrics['realized']))
        with cols[1]:kpi('Win rate jurnal',f"{metrics['win_rate']:.1f}%" if metrics['win_rate'] is not None else '—',f"{metrics['trades']} trade selesai",'chart')
        with cols[2]:kpi('Estimasi net target',money(metrics['estimated']), 'Target US$50.000 · DCA bukan profit','shield')
        if metrics['estimated'] is not None:st.progress(min(1.,max(0.,metrics['estimated']/50000)),text='Kemajuan estimasi net profit ke US$50.000')
        if metrics['alerts']:
            st.error(f"{len(metrics['alerts'])} peringatan proteksi. Periksa posisi pada aplikasi bursa; dashboard tidak menutupnya.")
            st.dataframe(pd.DataFrame(metrics['alerts']).rename(columns={'wallet':'Wallet','symbol':'Koin','reason':'Peringatan','sl':'SL diminta','tp':'TP diminta'}),hide_index=True,width='stretch')
        else:st.info("Tidak ada peringatan aktif di snapshot jurnal. Ini bukan pemeriksaan order TP/SL langsung oleh dashboard.")
        rows=[{'Wallet':r['wallet'],'Budget saat ini':f"{r['scale']:.0%}",'Trade matang':r['known'],'Posisi bot':r['positions'],'Intent belum selesai':r['pending']} for r in metrics['wallets']]
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    else:empty("Jurnal Termux belum tersinkron", "Saldo bursa tetap live. Net PnL bot, win rate dan peringatan tidak diisi dengan angka contoh.")
    heading("Aturan eksekusi", "Parameter Bot Sakti R2")
    left,right=st.columns([1.2,1])
    with left:
        html('<div class="rail"><small>01 / SIGNAL</small><h4>Trend, confirmed.</h4><p>EMA20/100 pada candle UTC4H tertutup, KER ≥0,25. Arah entry harus sejalan dengan BTC terhadap EMA50. Exit berlawanan tetap aktif.</p></div><div class="rail"><small>02 / ADAPT</small><h4>Exposure mengikuti hasil.</h4><p>Budget margin 25% sebelum empat trade matang atau rata-rata delapan net-R terakhir tidak positif. Pulih ke budget penuh saat syarat terpenuhi. Trade baru dihitung setelah satu jam.</p></div><div class="rail"><small>03 / LOCK</small><h4>Net US$50.000 → stop.</h4><p>Estimasi target pada penutupan jam memicu close posisi bot. Sesudah flat, entry berhenti dan kas tetap di futures. Tidak ada transfer otomatis atau mode Growth.</p></div>')
    with right:
        html('<div class="rule-grid"><div class="rule"><span>Leverage / mode</span><strong>20× / isolated</strong></div><div class="rule"><span>Posisi / wallet</span><strong>Maksimal 2</strong></div><div class="rule"><span>SL / TP</span><strong>1 ATR / 3R</strong></div><div class="rule"><span>Trailing</span><strong>2 ATR · per jam</strong></div><div class="rule"><span>Cooldown</span><strong>6 jam / koin</strong></div><div class="rule"><span>Durasi maksimum</span><strong>168 jam</strong></div></div>')
        st.caption("Margin mengikuti equity dan dipotong batas bursa serta collateral tersedia. Budget bukan fixed risk 2%. Hasil backtest tidak menjamin target atau DD LIVE.")
    heading("Posisi manual dilindungi", "Monitor saja · tidak ada eksekusi dari web")
    st.write("BingX akun 1: ETH, BTC, TIA, ONDO, BR. Bitget akun 1–3: XRP. Semua tetap milikmu; dashboard tidak mengirim order atau pembatalan.")
    heading("Jurnal penutupan", "PnL dari catatan bot, bukan kenaikan saldo akibat DCA")
    if snapshot['trades']:
        frame=pd.DataFrame(snapshot['trades']);frame['Waktu WIB']=pd.to_datetime(frame['closed'],unit='s',utc=True).dt.tz_convert('Asia/Jakarta')
        st.dataframe(frame[['Waktu WIB','account','exchange','net_pnl']].sort_values('Waktu WIB',ascending=False),hide_index=True,width='stretch')


def intel_page(info,base,settings):
    chart(info,base)
    left,right=st.columns([1.2,1])
    with left:
        with st.container(border=True):
            heading("Macro desk","Sumber primer, tanpa angka statis")
            st.write("Pantau inflasi, tenaga kerja, dan keputusan suku bunga melalui sumber resminya.")
            st.link_button("Federal Reserve · Kalender FOMC","https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",width="stretch")
            st.link_button("BLS · Kalender rilis data","https://www.bls.gov/schedule/",width="stretch")
            st.caption("Kalender otomatis belum terhubung. Actual dan forecast tidak ditampilkan sebelum ada sumber yang terverifikasi.")
    with right:
        with st.container(border=True):
            heading("Asisten konteks","Analisis atas informasi yang kamu berikan")
            key=settings.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
            with st.form("macro_question"):
                question=st.text_area("Pertanyaan / data rilis",placeholder="Contoh: bagaimana CPI di bawah perkiraan dapat memengaruhi BTC?",height=100)
                submitted=st.form_submit_button("Analisis konteks",width="stretch")
            if submitted:
                if not key:st.info("Asisten belum terhubung. GROQ_API_KEY perlu diatur di Secrets.")
                elif not question.strip():st.info("Masukkan pertanyaan atau data yang ingin dianalisis.")
                else:
                    try:
                        response=requests.post("https://api.groq.com/openai/v1/chat/completions",timeout=20,headers={"Authorization":"Bearer "+key},
                            json={"model":settings.get("GROQ_MODEL","openai/gpt-oss-20b"),"messages":[{"role":"system","content":"Jawab dalam bahasa Indonesia, singkat. Jelaskan skenario dan ketidakpastian. Anda tidak memiliki data makro real-time. Jangan mengarang angka, rilis, prediksi pasti, atau menyebut posisi aman. Ini konteks, bukan sinyal eksekusi bot."},{"role":"user","content":question}],"max_tokens":400,"temperature":.2})
                        response.raise_for_status()
                        st.session_state["macro_answer"]=response.json()["choices"][0]["message"]["content"]
                    except Exception:st.error("Asisten belum dapat dihubungi. Coba lagi nanti.")
            if st.session_state.get("macro_answer"):st.markdown(st.session_state["macro_answer"])
            st.caption("Jawaban tidak mengeksekusi trade dan tidak memiliki akses data makro terbaru secara otomatis.")


def main():
    st.set_page_config(page_title="Kantor Rakus | Bot Sakti",page_icon="◈",layout="wide",initial_sidebar_state="collapsed")
    html("<style>"+(ROOT/"assets/terminal.css").read_text(encoding="utf8")+"</style>")
    settings=secrets();stamp=datetime.now(WIB).strftime("%d %b %Y · %H:%M WIB")
    html(f'<div class="masthead"><div class="brand-wrap"><div class="brand-symbol"><svg viewBox="0 0 32 32"><path d="M6 6v20m0-10L24 6M12 13l13 13M21 7h5v7"/></svg></div><div><div class="brand">KANTOR<span>rakus.</span></div><div class="brand-sub">BOT SAKTI / PERSONAL TRADING FLOOR</div></div></div><div class="top-meta"><span>{stamp}</span><span class="chip neutral"><span class="dot"></span>REAL ACCOUNT MONITOR</span></div></div>')
    nav=st.radio("Navigasi",list(PAGE),horizontal=True,key="navigation")
    html('<div class="nav-line"></div>')
    title,description=PAGE[nav]
    html(f'<div class="page-intro"><div><div class="eyebrow">KANTOR RAKUS / {escape(nav.upper())}</div><h1>{title}</h1><p>{description}</p></div><div class="page-count">03 ACCOUNTS<br><span style="color:#bac9d7;display:block;margin-top:6px">08 WALLETS / 03 EXCHANGES</span></div></div>')
    controls=st.columns([1.3,1,1.2,.7])
    with controls[0]:account_label=st.selectbox("Tampilan akun",["Semua akun","Akun 1","Akun 2","Akun 3"],key="account_filter")
    st.session_state['account']='all' if account_label=='Semua akun' else 'akun_'+account_label[-1]
    with controls[1]:base=st.selectbox("Pasar",['BTC','ETH','SOL','BNB','DOGE','ADA'],key='market_filter')
    with controls[2]:auto=st.toggle("Pembaruan otomatis · 15 dtk",value=True,key='auto_refresh')
    with controls[3]:
        if st.button('↻ Refresh',width='stretch'):portfolio.clear();market.clear()
    @st.fragment(run_every=15 if auto else None)
    def body():
        config=data.credentials(settings)
        fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        with st.spinner('Membaca delapan wallet riil…'):
            snapshot=portfolio(config,fingerprint);info=market(base)
        if st.session_state.get('sakti_upload'):
            snapshot={**snapshot,**data.state_metadata(st.session_state['sakti_upload'])}
        summary=data.totals(snapshot,st.session_state['account'])
        if summary['live']<summary['expected']:
            count=sum(r['status']=='snapshot' for r in summary['rows'])
            html(f'<div class="data-notice">{summary["live"]}/{summary["expected"]} koneksi LIVE · {count} snapshot tersimpan. Data yang tidak terbaca ditandai —, bukan saldo nol.</div>')
        if nav=='Ringkasan':overview(snapshot,info,summary,base)
        elif nav=='Posisi & Bursa':positions_page(snapshot,summary)
        elif nav=='Bot Sakti':strategy_page(snapshot)
        elif nav=='Kantor 3D':
            office();account_cards(snapshot)
            st.caption('Kantor 3D adalah visual ruang kerja. Saldo dan status akun di bawahnya berasal dari koneksi bursa yang ditampilkan. Geser ruang atau gunakan tombol panah; animasi dapat dijeda.')
        else:intel_page(info,base,settings)
        html(f'<div class="footnote"><span>KANTOR RAKUS · BOT SAKTI / HEALTH25</span><span>MONITOR SAJA · TANPA ORDER / CANCEL · {datetime.now(WIB).strftime("%H:%M:%S WIB")}</span></div>')
    body()
