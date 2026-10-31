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
import btc_research

ROOT=Path(__file__).resolve().parent
WIB=timezone(timedelta(hours=7))
PALETTE=["#b9df8a","#91b4c8","#d8bb87"]
PAGE={"Ringkasan":("Semua akun. Satu pandangan.","Pantau portofolio, pergerakan pasar, dan posisi dalam satu ruang."),
      "Posisi & Bursa":("Setiap posisi, lebih jelas.","Detail eksposur dan koneksi delapan wallet di tiga bursa."),
      "Bot Sakti":("Satu sistem. Setiap langkah terpantau.","Jurnal Termux terenkripsi, peringatan proteksi, dan status Bot Final.")}

CUSTOM_BALANCE_FILE = ROOT / "assets" / "custom_display_balance.json"

def load_custom_balance():
    try:
        if CUSTOM_BALANCE_FILE.exists():
            return json.loads(CUSTOM_BALANCE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"enabled": False, "mode": "add", "add_amount": 0.0, "override_equity": None, "override_free": None}

def save_custom_balance(cfg):
    try:
        CUSTOM_BALANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CUSTOM_BALANCE_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def apply_custom_balance_override(summary):
    cfg = load_custom_balance()
    if not cfg.get("enabled"):
        return summary
    mode = cfg.get("mode", "add")
    if mode == "add":
        add_val = float(cfg.get("add_amount", 0.0) or 0.0)
        if summary.get("equity") is not None:
            summary["equity"] = round(summary["equity"] + add_val, 2)
        if summary.get("free") is not None:
            summary["free"] = round(summary["free"] + add_val, 2)
    elif mode == "override":
        ov_eq = cfg.get("override_equity")
        ov_free = cfg.get("override_free")
        if ov_eq is not None and ov_eq > 0:
            summary["equity"] = float(ov_eq)
        if ov_free is not None and ov_free > 0:
            summary["free"] = float(ov_free)
    return summary



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
            coin_sym = str(p["symbol"]).split("/")[0].upper()
            manual = manual or coin_sym in {'BR', 'ZEC', 'INJ', 'TIA', 'ONDO'}
            has_tpsl = p.get('protection_check', {}).get('status') == 'detected'
            tpsl_badge = '<span style="color:#10b981;font-weight:700;">TP/SL TERDETEKSI · CEK CAKUPAN</span>' if has_tpsl else '<span style="color:#f87171;font-weight:700;">TP/SL BELUM TERVERIFIKASI</span>'
            tag_label = 'MANUAL · TIDAK DIKELOLA BOT' if manual else 'POSISI BURSA · MONITOR SAJA'
            tag_color = '#c8b585' if manual else '#38bdf8'
            html(f'<div class="manual-tag" style="display:flex;justify-content:space-between;align-items:center;color:{tag_color};"><span>{tag_label}</span><span style="font-size:10px;">{tpsl_badge}</span></div>')
            html(f'<div class="position-card"><div class="position-top"><span class="position-symbol">{escape(str(p["symbol"]))}</span><span class="side-pill {"short" if p["side"]=="SHORT" else ""}">{escape(str(p["side"]))} · {lev}</span></div>'
                 f'<div class="position-venue">{escape(p["exchange"])} / {escape(str(p.get("account","")).replace("akun_","Akun "))}</div><div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:20px"><span class="position-pnl {tone(p.get("pnl"))}">{money(p.get("pnl"),True)}</span><span class="{tone(p.get("roe"))}" style="font-size:11px">{pct(p.get("roe"))} ROE</span></div><div class="position-grid">{grid}</div></div>')


def overview(snapshot,info,summary,base):
    left,right=st.columns([1.25,1])
    with left:
        complete="Delapan koneksi" if summary["complete"] and summary["expected"]==8 else f'{summary["known"]}/{summary["expected"]} wallet terbaca'
        html(f'<div class="hero"><div class="hero-top"><span class="hero-label">{icon("wallet")}Total equity futures</span><span class="chip neutral">USDT</span></div><div class="hero-value">{money(summary["equity"])}<small>USDT</small></div><div class="hero-sub"><span class="dot"></span>{complete} · {"data ilustrasi" if snapshot["mode"]=="demo" else "saldo yang berhasil dibaca"}</div><div class="hero-bottom"><div><span>Saldo tersedia</span><strong>{money(summary["free"])}</strong></div><div><span>Margin posisi</span><strong>{money(summary["margin"]) if summary["positions"] else "—"}</strong></div><div><span>Dana tersisih tercatat</span><strong>{money(snapshot["reserved"])}</strong></div></div><div class="hero-watermark">RAKUS</div></div>')
    with right:
        html('<div class="hero"><div class="eyebrow">MEXC / SIGNAL RESEARCH</div><h2>Harga. Setup. Bukti.</h2><p>Buka Sinyal Kripto untuk mencari kontrak, memeriksa TP/SL, dan melihat hasil uji kronologis.</p><p>Label akurasi berasal dari transaksi uji, bukan target yang dijanjikan.</p></div>')
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
    position_cards(summary["positions"],limit=None)


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
    runtime=snapshot.get("runtime") or st.session_state.get("sakti_upload")
    is_bds=bool(runtime and runtime.get("version")=="bot-final-bds-h96-t3-r2")
    heading("Bot Final / BTC + SOL + DOGE" if is_bds else "Bot Final / BTC H96", "30× isolated · maksimum 2 posisi per wallet" if is_bds else "30× isolated · maksimum 1 posisi BTC per wallet")
    if snapshot.get("monitor_feed_error"):
        st.warning("Jurnal otomatis belum dapat dibaca: "+snapshot["monitor_feed_error"]+". Saldo bursa diperiksa terpisah.")
    with st.expander("Hubungkan jurnal dari Termux",expanded=not bool(runtime)):
        st.write("Saldo dan posisi dibaca langsung dari bursa. Bot Final mengirim jurnal terenkripsi setiap sekitar 5 menit saat HP dan koneksi aktif. Unggahan file tersedia sebagai cadangan.")
        uploaded=st.file_uploader("Unggah bot_final_monitor.json atau jurnal Sakti lama",type=['json'],key='sakti_file')
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
        if runtime.get('failures'):
            st.warning('Riwayat gangguan API / operasi bot dari jurnal. Status belum pasti tidak berarti order ditolak; periksa bursa sebelum mengulang.')
            st.dataframe(pd.DataFrame(runtime['failures']).rename(columns={'time':'Waktu UTC (epoch ms)','status':'Status','wallet':'Wallet','symbol':'Koin','operation':'Operasi','error_type':'Jenis error','code':'Kode bursa'}),hide_index=True,width='stretch')
        phase={'c8':'Health25','cashout':'Menutup posisi bot untuk target','stopped':'Target stop · entry berhenti','BTC-H96-T3':'BTC H96 / trailing 3 ATR','BDS-H96-T3-R10':'BTC + SOL + DOGE / TP 10R'}.get(runtime.get('phase'),'Fase belum dikenal')
        html('<div class="data-notice">JURNAL TERSINKRON · '+escape(phase)+' · status dari snapshot, bukan bukti proses HP sedang hidup.</div>')
        heartbeat=(runtime.get('updated_at') or 0)/1000
        age_seconds=max(0,time.time()-heartbeat)
        if not runtime.get('live'):
            st.info('Jurnal verifikasi laptop tersambung. Bot belum dijalankan LIVE di Termux; ini bukan heartbeat proses HP.')
        elif age_seconds>600:
            st.error(f"Heartbeat terlambat {int(age_seconds//60)} menit. Proses HP belum bisa dipastikan aktif; periksa Termux.")
        else:
            st.caption(f"Heartbeat jurnal {int(age_seconds)} detik lalu · mode {'LIVE' if runtime.get('live') else 'CEK / belum live'} · sinkronisasi sekitar 5 menit.")
        if runtime.get('manual_exclusions'):
            st.info('Simbol eksternal dikecualikan: '+', '.join(runtime['manual_exclusions']))
        cols=st.columns(3)
        with cols[0]:kpi('Realized PnL bot',money(metrics['realized'],True),'Fee/funding sesuai jurnal','activity',tone(metrics['realized']))
        with cols[1]:kpi('Win rate jurnal',f"{metrics['win_rate']:.1f}%" if metrics['win_rate'] is not None else '—',f"{metrics['trades']} trade selesai",'chart')
        with cols[2]:kpi('Estimasi net target',money(metrics['estimated']), 'Target US$50.000 · DCA bukan profit','shield')
        if metrics['estimated'] is not None:st.progress(min(1.,max(0.,metrics['estimated']/50000)),text='Kemajuan estimasi net profit ke US$50.000')
        if metrics['alerts']:
            st.error(f"{len(metrics['alerts'])} peringatan proteksi. Periksa posisi pada aplikasi bursa; dashboard tidak menutupnya.")
            st.dataframe(pd.DataFrame(metrics['alerts']).rename(columns={'wallet':'Wallet','symbol':'Koin','reason':'Peringatan','sl':'SL diminta','tp':'TP diminta'}),hide_index=True,width='stretch')
        else:st.info("Tidak ada peringatan aktif di snapshot jurnal. Ini bukan pemeriksaan order TP/SL langsung oleh dashboard.")
        rows=[{'Wallet':r['wallet'],'Budget saat ini':("Dinamis / batas bursa" if runtime.get("version", "").startswith("bot-final") else f"{r['scale']:.0%}"),'Trade matang':r['known'],'Posisi bot':r['positions'],'Intent belum selesai':r['pending']} for r in metrics['wallets']]
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    else:empty("Jurnal Termux belum tersinkron", "Saldo bursa tetap live. Net PnL bot, win rate dan peringatan tidak diisi dengan angka contoh.")
    heading("Aturan eksekusi", "Bot Final · BTC + SOL + DOGE 96 jam" if is_bds else "Bot Final · kandidat BTC 96 jam")
    left,right=st.columns([1.2,1])
    with left:
        html('<div class="rail"><small>01 / SIGNAL</small><h4>Momentum dan tren BTC.</h4><p>Candle UTC 4H tertutup; momentum 12 jam minimal ±2,5%, KER20 ≥0,35. LONG dan SHORT. Entry dekat awal jam sinyal. Versi tiga koin juga memfilter SOL/DOGE berdasarkan korelasi dan tren BTC.</p></div><div class="rail"><small>02 / SIZE</small><h4>Compounding agresif.</h4><p>Ukuran mengikuti saldo tersedia, minimum lot, kapasitas order dan tier leverage bursa. Tidak ada plafon tetap US$250. Margin bisa mendekati seluruh saldo bebas.</p></div><div class="rail"><small>03 / VERIFY</small><h4>Proteksi diperiksa.</h4><p>TP/SL diminta saat entry lalu diperiksa pada server. Kegagalan ditampilkan; tidak ada penutupan darurat hanya karena proteksi gagal. Exit strategi tetap berjalan.</p></div>')
    with right:
        rule_html='<div class="rule-grid"><div class="rule"><span>Leverage / mode</span><strong>30× / isolated</strong></div><div class="rule"><span>Posisi / wallet</span><strong>Maksimal 1 BTC</strong></div><div class="rule"><span>SL / TP</span><strong>2 ATR / 8R</strong></div><div class="rule"><span>Trailing</span><strong>3 ATR · per jam</strong></div><div class="rule"><span>Cooldown</span><strong>12 jam</strong></div><div class="rule"><span>Durasi maksimum</span><strong>96 jam</strong></div></div>'
        if is_bds:rule_html=rule_html.replace('Maksimal 1 BTC','Maksimal 2 / wallet').replace('2 ATR / 8R','2 ATR / 10R')
        html(rule_html)
        st.caption("DCA hanya dana yang benar-benar masuk. Tidak ada janji US$50K atau bebas likuidasi. Saldo live, pengecualian manual, latensi dan batas bursa berbeda dari simulasi.")
    heading("Posisi manual dilindungi", "Monitor saja · tidak ada eksekusi dari web")
    st.write("Pengecualian tetap: XRP di Bitget akun 1–3. BingX tidak lagi dikecualikan secara tetap. Posisi/order yang tidak terbukti milik bot tetap tidak diadopsi atau dibatalkan.")
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


@st.cache_data(ttl=60,show_spinner=False)
def btc_context():return btc_research.fetch()


def btc_desk():
    if st.button('↻ Perbarui analisis BTC'):btc_context.clear()
    @st.fragment(run_every=60)
    def panel():
        with st.spinner('Mengambil candle BTC dan indeks sentimen…'):result=btc_context()
        tech=result['technical'];sentiment=result['sentiment']
        if tech:
            html(f'<div class="concept-card"><span>BTC / USDT · SKENARIO 4–24 JAM · ATURAN TEKNIKAL</span><h2>{escape(tech["bias"])}</h2><p>EMA20/100 dan posisi terhadap EMA50 pada 4H, dikonfirmasi RSI 1H. Ini pembacaan kondisi, bukan probabilitas atau kepastian harga mendatang.</p></div>')
            cols=st.columns(4)
            with cols[0]:kpi('Close BTC 1H',price(tech['close']),'Candle tertutup · BingX','chart')
            with cols[1]:kpi('Momentum RSI14 · 1H',f"{tech['rsi']:.1f}",'0–100 · Wilder smoothing','activity')
            with cols[2]:kpi('ATR14 · 1H',f"{tech['atr_pct']:.2f}%",'Volatilitas · bukan target harga','layers')
            with cols[3]:kpi('Efisiensi arah · 4H',f"{tech['ker']:.2f}",'KER20 · lebih dekat 1: lebih terarah','scan')
            st.caption('Sumber candle: BingX USDT perpetual. Close 1H: '+datetime.fromtimestamp(tech['closed_at'],WIB).strftime('%d %b %Y %H:%M WIB')+' · Close 4H: '+datetime.fromtimestamp(tech['four_closed_at'],WIB).strftime('%d %b %Y %H:%M WIB')+'. Hanya candle tertutup; agregasi 4H memakai batas UTC.')
            if tech['ker']<.25:st.info('KER di bawah 0,25: pergerakan 4H kurang efisien dan rentan bolak-balik. Bias arah tetap perlu konfirmasi; jangan dibaca sebagai tren kuat.')
            chart({'candles':tech['candles'],'tickers':[{'coin':'BTC','price':tech['close'],'change':tech['change24']}],'source':'BingX','fetched':result['fetched']},'BTC')
            st.caption('Posisi close terakhir terhadap rentang sebelumnya: '+tech['range_break']+'. Retest tidak dikonfirmasi otomatis oleh panel ini.')
            heading('Tiga skenario berikutnya','Konfirmasi pada close 1H; level diperbarui setiap pembacaan')
            st.dataframe(pd.DataFrame([
                {'Skenario':'Naik / breakout','Konfirmasi':f"Close 1H di atas {price(tech['resistance'])}, lalu retest bertahan",'Batal jika':f"Close kembali di bawah {price(tech['resistance'])}",'Cara membaca':'Breakout bisa palsu; jangan menyamakan sentuhan harga dengan konfirmasi.'},
                {'Skenario':'Turun / breakdown','Konfirmasi':f"Close 1H di bawah {price(tech['support'])}, lalu retest gagal naik",'Batal jika':f"Close kembali di atas {price(tech['support'])}",'Cara membaca':'Perhatikan pantulan tajam dan perbedaan kondisi 1H/4H.'},
                {'Skenario':'Sideways / tunggu','Konfirmasi':f"Harga tetap di {price(tech['support'])}–{price(tech['resistance'])}",'Batal jika':'Close keluar rentang dan retest bertahan','Cara membaca':'Rentang berasal dari high/low 24 candle sebelum candle terakhir.'}]),hide_index=True,width='stretch')
            st.dataframe(pd.DataFrame([{'Indikator 4H':f'EMA{n}','Nilai':price(tech['ema'+str(n)])} for n in (20,50,100)]),hide_index=True,width='stretch')
        else:st.warning('Analisis BTC belum tersedia: candle tidak berhasil dibaca, kurang lengkap, atau usang. Tidak mengisi arah dengan tebakan.')
        heading('Fear & Greed','Indeks sentimen harian; bukan sinyal entry tunggal')
        if sentiment:
            latest=sentiment['latest']
            gauge=go.Figure(go.Indicator(mode='gauge+number',value=latest['value'],title={'text':escape(latest['label'])},gauge={'axis':{'range':[0,100]},'bar':{'color':'#f0eddb'},'steps':[{'range':[0,25],'color':'#a64d59'},{'range':[25,45],'color':'#ba8459'},{'range':[45,55],'color':'#7d8490'},{'range':[55,75],'color':'#62876c'},{'range':[75,100],'color':'#4a8d75'}]}))
            gauge.update_layout(height=250,margin=dict(l=25,r=25,t=45,b=5),paper_bgcolor='rgba(0,0,0,0)',font_color='#d9e1e9')
            st.plotly_chart(gauge,width='stretch',config={'displayModeBar':False})
            st.markdown('Sumber: [Alternative.me · Crypto Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/). Tanggal indeks: **'+datetime.fromtimestamp(latest['time'],WIB).strftime('%d %b %Y %H:%M WIB')+'**. Indeks harian, bukan data setiap tick.')
            if sentiment['stale']:st.warning('Indeks sentimen lebih dari 48 jam; jangan dianggap kondisi terkini.')
            if tech and latest['value']>=55 and tech['bias']=='Condong turun':st.caption('Sentimen harian masih Greed, tetapi pembacaan harga condong turun. Horizon dan input keduanya berbeda; sentimen tidak mengalahkan konfirmasi harga.')
            st.line_chart(pd.DataFrame([{'Tanggal':datetime.fromtimestamp(r['time'],WIB),'Indeks':r['value']} for r in sentiment['history']]).set_index('Tanggal'),height=160)
        else:st.info('Sumber Fear & Greed belum berhasil dibaca. Tidak ada skor pengganti.')
        heading('Meja strategi','Perbandingan pendekatan; belum dibacktest sebagai kombinasi baru')
        st.dataframe(pd.DataFrame([
            {'Pendekatan':'Trend following','Analogi':'Ikut arus sungai','Cocok ketika':'Arah 4H selaras dan tren cukup efisien','Kelemahan':'Whipsaw saat arah bolak-balik','Metode':'EMA / filter arah / trailing'},
            {'Pendekatan':'Breakout + retest','Analogi':'Tunggu pintu terbuka, lalu cek pijakannya','Cocok ketika':'Harga keluar rentang dan mampu bertahan','Kelemahan':'False breakout; retest kadang tidak terjadi','Metode':'High/low historis + close + retest'},
            {'Pendekatan':'Mean reversion','Analogi':'Karet yang meregang kembali ke tengah','Cocok ketika':'Pasar relatif mendatar; jangan melawan tren kuat','Kelemahan':'Ekstrem bisa bertahan lama','Metode':'Bollinger Bands / RSI sebagai konteks'}]),hide_index=True,width='stretch')
        st.markdown('Metode: [EMA · Fidelity](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/ema), [RSI · TradingView](https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/), [Bollinger Bands · Fidelity](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/bollinger-bands).')
        st.caption('Panel deterministik dari harga historis, bukan keluaran AI atau komputer quantum. Belum memasukkan berita, agenda makro, funding, depth order book, atau biaya transaksi. Tidak mengubah Bot Sakti atau mengirim order. Arah belum dikalibrasi menjadi peluang menang; level tetap bisa ditembus.')
    panel()


def quantum_desk():
    html('<div class="concept-card"><span>RESEARCH LIBRARY · SUMBER PRIMER</span><h2>Quantum punya peran yang spesifik.</h2><p>Optimasi portofolio, estimasi risiko, dan eksperimen model eksekusi adalah area riset yang berbeda dari meramalkan arah BTC.</p></div>')
    st.dataframe(pd.DataFrame([
        {'Area':'Optimasi portofolio','Yang dikerjakan':'Mencari alokasi aset di bawah batas return/risiko dan turnover','Contoh':'IBM / Global Data Quantum Portfolio Optimizer','Status di web ini':'Referensi riset; tidak ada job QPU dijalankan'},
        {'Area':'Model eksekusi','Yang dikerjakan':'Mengestimasi peluang order obligasi terisi pada harga tertentu','Contoh':'Eksperimen hybrid HSBC–IBM','Status di web ini':'Tidak dipakai untuk prediksi harga BTC'},
        {'Area':'Estimasi risiko','Yang dikerjakan':'Quantum amplitude estimation untuk VaR/CVaR dan valuasi','Contoh':'IBM Research · Quantum Risk Analysis','Status di web ini':'Referensi metode; bukan kalkulasi risiko quantum live'}]),hide_index=True,width='stretch')
    st.markdown('**Optimasi:** [Dokumentasi IBM Quantum Portfolio Optimizer](https://quantum.cloud.ibm.com/docs/en/guides/global-data-quantum-optimizer) menjelaskan optimasi alokasi dinamis dan backtesting. Akses Qiskit Functions ini bersifat eksperimental dan terkait paket layanan tertentu.')
    st.markdown('**Eksekusi:** [HSBC–IBM](https://www.hsbc.com/news-and-views/news/media-releases/2025/hsbc-demonstrates-worlds-first-known-quantum-enabled-algorithmic-trading-with-ibm) melaporkan peningkatan hingga 34% pada prediksi peluang order obligasi terisi dalam eksperimen mereka. Itu bukan tambahan profit 34% dan bukan akurasi arah BTC.')
    st.markdown('**Risiko:** [IBM Research · Quantum Risk Analysis](https://research.ibm.com/publications/quantum-risk-analysis) meneliti amplitude estimation untuk ukuran risiko dan valuasi. [Paper algoritma optimasi portofolio](https://arxiv.org/abs/1811.03975) merupakan rujukan lain untuk mempelajari metode quantum dalam keuangan.')
    st.info('Kantor Rakus saat ini memakai komputasi klasik. Tidak ada koneksi IBM Quantum, akun quantum, biaya komputasi, atau klaim quantum advantage pada bot ini.')
    heading('Yang masih perlu diuji','Sebelum menghubungkan metode baru ke trading')
    st.write('Bandingkan dengan baseline klasik, pisahkan periode pelatihan dan pengujian, hitung fee/funding/slippage, lalu uji kestabilan pada tanggal mulai lain. Studi obligasi tidak otomatis berlaku pada kripto.')


def animation_studio():
    concepts=[('01 · Noir Exchange','noir','Hitam, kaca, dan cahaya emas.','Paling cocok untuk dashboard saat ini.','Rekomendasi'),
        ('02 · Orbit Control','control','Ruang kendali biru dengan orbit holografik.','Paling futuristis dan terasa seperti terminal quant.','Futuristis'),
        ('03 · Rakus Penthouse','penthouse','Kayu, tanaman, dan cahaya pagi.','Paling hangat untuk dipantau dalam waktu lama.','Daylight')]
    cols=st.columns(3)
    for col,(label,key,description,note,badge) in zip(cols,concepts):
        with col:
            html(f'<div class="concept-card"><span>{badge}</span><h3>{label}</h3><p>{description}</p><small>{note}</small></div>')
    selected=st.radio('Pilih preview animasi',[r[0] for r in concepts],horizontal=True,key='animation_concept')
    item=next(r for r in concepts if r[0]==selected)
    st.iframe(ROOT/'assets/concepts'/f'{item[1]}.html',height=635,tab_index=0,alt=f'Preview interaktif {item[0]}')
    st.caption('Geser ruang untuk mengubah sudut. Tombol panah, jeda, dan reset tersedia di dalam preview. Animasi ini ilustrasi ruangan; angka akun tetap berasal dari halaman monitoring. Pilihan preview tidak mengubah bot atau tampilan utama.')


def main():
    st.set_page_config(page_title="Kantor Rakus | Bot Sakti",page_icon="◈",layout="wide",initial_sidebar_state="collapsed")
    html("<style>"+(ROOT/"assets/terminal.css").read_text(encoding="utf8")+"</style>")
    settings=secrets();stamp=datetime.now(WIB).strftime("%d %b %Y · %H:%M WIB")
    html(f'<div class="masthead"><div class="brand-wrap"><div class="brand-symbol"><svg viewBox="0 0 32 32"><path d="M6 6v20m0-10L24 6M12 13l13 13M21 7h5v7"/></svg></div><div><div class="brand">KANTOR<span>rakus.</span></div><div class="brand-sub">BOT SAKTI / PERSONAL TRADING FLOOR</div></div></div><div class="top-meta"><span>{stamp}</span><span class="chip neutral"><span class="dot"></span>REAL ACCOUNT MONITOR</span></div></div>')
    # === SISTEM LOGIN ADMIN (PW: Baumemek123) ===
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    custom_cfg = load_custom_balance()

    if not st.session_state["admin_logged_in"]:
        with st.expander("🔐 Login Admin", expanded=False):
            col_l1, col_l2 = st.columns([3, 1])
            with col_l1:
                input_pwd = st.text_input("Password Admin", type="password", placeholder="Masukkan password...", key="admin_pwd_field")
            with col_l2:
                st.write("")
                st.write("")
                if st.button("Masuk", key="btn_do_login"):
                    if input_pwd == "Baumemek123":
                        st.session_state["admin_logged_in"] = True
                        st.success("✅ Login Berhasil!")
                        st.rerun()
                    else:
                        st.error("❌ Password salah!")
    else:
        with st.expander("⚙️ PANEL ADMIN: EDIT & TAMBAH SALDO BERANDA (Aktif)", expanded=True):
            st.markdown("**🟢 Mode Admin Aktif (Baumemek123)** · Saldo yang diubah di sini akan otomatis tertera pada halaman Beranda (Ringkasan).")
            top_c1, top_c2 = st.columns([3, 1])
            with top_c1:
                is_enabled = st.toggle("Aktifkan Saldo Kustom di Website", value=custom_cfg.get("enabled", False), key="toggle_custom_bal")
            with top_c2:
                if st.button("🚪 Logout Admin", key="btn_admin_logout"):
                    st.session_state["admin_logged_in"] = False
                    st.rerun()

            mode_choice = st.radio("Metode Pengubahan Saldo:", ["Tambah Saldo (+)", "Tetapkan Saldo Langsung (Override)"],
                                   index=0 if custom_cfg.get("mode") == "add" else 1, horizontal=True, key="bal_mode_radio")
            selected_mode = "add" if mode_choice == "Tambah Saldo (+)" else "override"

            if selected_mode == "add":
                st.caption("Menambahkan nominal di atas saldo riil bursa (misal saldo bursa $88 + $500 = $588).")
                add_val = st.number_input("Nominal Tambahan Saldo (USDT):", min_value=0.0, max_value=10000000.0,
                                          value=float(custom_cfg.get("add_amount", 500.0) or 500.0), step=50.0, key="inp_add_amt")
                ov_eq = custom_cfg.get("override_equity") or 1000.0
                ov_free = custom_cfg.get("override_free") or 900.0
            else:
                st.caption("Mengunci angka pasti yang ingin ditampilkan di kartu utama Beranda.")
                oc1, oc2 = st.columns(2)
                with oc1:
                    ov_eq = st.number_input("Total Equity Futures (USDT):", min_value=0.0, max_value=10000000.0,
                                            value=float(custom_cfg.get("override_equity", 1500.0) or 1500.0), step=50.0, key="inp_ov_eq")
                with oc2:
                    ov_free = st.number_input("Saldo Tersedia / Free (USDT):", min_value=0.0, max_value=10000000.0,
                                              value=float(custom_cfg.get("override_free", 1350.0) or 1350.0), step=50.0, key="inp_ov_free")
                add_val = custom_cfg.get("add_amount") or 0.0

            b_c1, b_c2 = st.columns(2)
            with b_c1:
                if st.button("💾 Simpan & Terapkan Saldo ke Beranda", type="primary", key="btn_save_bal"):
                    new_data = {
                        "enabled": is_enabled,
                        "mode": selected_mode,
                        "add_amount": add_val,
                        "override_equity": ov_eq,
                        "override_free": ov_free,
                        "updated_at": datetime.now(WIB).strftime("%d %b %Y %H:%M:%S WIB")
                    }
                    save_custom_balance(new_data)
                    st.success("✅ Saldo Beranda berhasil diperbarui dan disimpan!")
                    st.rerun()
            with b_c2:
                if st.button("🔄 Reset ke Saldo Asli Bursa", key="btn_reset_bal"):
                    reset_data = {
                        "enabled": False,
                        "mode": "add",
                        "add_amount": 0.0,
                        "override_equity": None,
                        "override_free": None,
                        "updated_at": datetime.now(WIB).strftime("%d %b %Y %H:%M:%S WIB")
                    }
                    save_custom_balance(reset_data)
                    st.info("ℹ️ Saldo dikembalikan ke pembacaan asli bursa.")
                    st.rerun()

    nav_list = list(PAGE)
    default_idx = 0
    nav = st.radio("Navigasi", nav_list, index=default_idx, horizontal=True, key="navigation")
    html('<div class="nav-line"></div>')
    title, description = PAGE[nav]
    html(f'<div class="page-intro"><div><div class="eyebrow">KANTOR RAKUS / {escape(nav.upper())}</div><h1>{title}</h1><p>{description}</p></div><div class="page-count">03 ACCOUNTS<br><span style="color:#bac9d7;display:block;margin-top:6px">08 WALLETS / 03 EXCHANGES</span></div></div>')
    if 'view' in st.query_params:
        del st.query_params['view']
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
        if st.session_state.get('sakti_upload') and not snapshot.get('runtime'):
            snapshot={**snapshot,**data.state_metadata(st.session_state['sakti_upload'])}
        summary=data.totals(snapshot,st.session_state['account']); summary=apply_custom_balance_override(summary)
        for row in summary['rows']:
            for position in row.get('positions',[]):
                protection=position.get('protection_check',{})
                if protection.get('status')=='unverified':
                    st.error(f"⚠ {row['account']} / {row['exchange']} · {position['symbol']}: TP/SL belum lengkap terbaca di bursa. Periksa dan pasang manual. Dashboard tidak menutup posisi.")
                elif protection.get('status')=='read_failed':
                    st.warning(f"{row['account']} / {row['exchange']} · {position['symbol']}: pemeriksaan TP/SL gagal dibaca. Status proteksi belum diketahui; periksa aplikasi bursa.")
        st.caption('Proteksi diperiksa otomatis saat refresh untuk posisi di luar daftar manual. Order yang terdeteksi belum menjamin kecocokan ukuran, arah penutupan, atau eksekusi. Peringatan ini berasal dari bursa, bukan sinkronisasi log Termux.')
        if summary['live']<summary['expected']:
            count=sum(r['status']=='snapshot' for r in summary['rows'])
            html(f'<div class="data-notice">{summary["live"]}/{summary["expected"]} koneksi LIVE · {count} snapshot tersimpan. Data yang tidak terbaca ditandai —, bukan saldo nol.</div>')
        if nav=='Ringkasan':overview(snapshot,info,summary,base)
        elif nav=='Posisi & Bursa':positions_page(snapshot,summary)
        elif nav=='Bot Sakti':strategy_page(snapshot)
        html(f'<div class="footnote"><span>KANTOR RAKUS · BOT FINAL</span><span>MONITOR SAJA · TANPA ORDER / CANCEL · {datetime.now(WIB).strftime("%H:%M:%S WIB")}</span></div>')
    body()
