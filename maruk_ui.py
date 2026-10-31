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
import sinyal_engine
import bingx_executor

ROOT=Path(__file__).resolve().parent
WIB=timezone(timedelta(hours=7))
PALETTE=["#b9df8a","#91b4c8","#d8bb87"]
PAGE={"Ringkasan":("Semua akun. Satu pandangan.","Pantau portofolio, pergerakan pasar, dan posisi dalam satu ruang."),
      "Posisi & Bursa":("Setiap posisi, lebih jelas.","Detail eksposur dan koneksi delapan wallet di tiga bursa."),
      "Bot Sakti":("Satu sistem. Setiap langkah terpantau.","Jurnal Termux terenkripsi, peringatan proteksi, dan status Bot Final."),
      "Sinyal":("50 koin. Sniper presisi.","Sinyal limit order multi-konfirmasi dari BingX. Skor 1-100, status real-time, TP1/2/3 otomatis.")}

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



# ═══════════════════════════════════════════════════════════════════════
# HALAMAN SINYAL — Multi-Confirmation Sniper Limit Order Signal Room
# ═══════════════════════════════════════════════════════════════════════
def sinyal_page(summary=None):
    """Halaman Analisa Sinyal Limit Order Kripto BingX Berbasis Multi-Konfirmasi Teknikal Kuantitatif."""
    LEVERAGE_DISPLAY = 20   # asumsi leverage untuk kalkulasi ROE
    MARGIN_DISPLAY   = 0.20  # asumsi margin per trade (USD)

    # ── CSS Kartu Sinyal ────────────────────────────────────────────────
    st.markdown("""
<style>
.sig-card{background:#111a22;border:1px solid #1e2d3d;border-radius:12px;padding:16px 18px;margin-bottom:10px;position:relative;overflow:hidden}
.sig-card:hover{border-color:#2a4060}
.sig-card-long{border-left:4px solid #00e676}
.sig-card-short{border-left:4px solid #f44336}
.sig-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.sig-sym{font-size:18px;font-weight:700;color:#e8f0fe;letter-spacing:1px}
.sig-dir-long{background:#00e676;color:#000;font-size:11px;font-weight:800;padding:3px 10px;border-radius:20px}
.sig-dir-short{background:#f44336;color:#fff;font-size:11px;font-weight:800;padding:3px 10px;border-radius:20px}
.sig-score-bar-wrap{background:#1e2d3d;border-radius:6px;height:6px;width:100%;margin:6px 0 10px}
.sig-score-bar{border-radius:6px;height:6px;transition:width .3s}
.sig-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-top:8px}
.sig-cell{background:#0d1520;border-radius:8px;padding:8px 10px}
.sig-cell-label{color:#4e6b8a;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.sig-cell-val{color:#c8d8e8;font-size:13px;font-weight:700;margin-top:2px}
.sig-cell-val.green{color:#00e676}
.sig-cell-val.red{color:#f44336}
.sig-cell-val.gold{color:#ffd700}
.sig-status{display:inline-block;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;margin-left:8px}
.sig-reasons{margin-top:8px;padding-top:8px;border-top:1px solid #1e2d3d}
.sig-reason-item{color:#5a7a9a;font-size:11px;padding:1px 0}
.sig-meta{display:flex;gap:12px;margin-top:6px;flex-wrap:wrap}
.sig-meta-item{color:#3a5a7a;font-size:10px}
.sig-valid{color:#4a8a6a;font-size:10px;font-weight:600}
.empty-state{background:#0d1520;border:1px dashed #1e2d3d;border-radius:12px;padding:40px;text-align:center;color:#3a5a7a}
.scan-summary{background:#0d1520;border:1px solid #1e2d3d;border-radius:10px;padding:14px 18px;margin-bottom:16px;display:flex;gap:24px;flex-wrap:wrap}
.scan-summary-item{color:#4e6b8a;font-size:12px}
.scan-summary-item strong{color:#c8d8e8;font-size:15px;display:block}
</style>
""", unsafe_allow_html=True)

    WIB_TZ = timezone(timedelta(hours=7))
    now_wib = datetime.now(WIB_TZ)

    # ── 1. SCANNER MAKRO BTC & KONTROL DARURAT ───────────────────────────
    btc_sent = bingx_executor.get_btc_macro_sentiment()
    b_stat = btc_sent.get("status", "NORMAL")
    b_lbl = btc_sent.get("label", "🛡️ BTC TREN NETRAL")
    b_price = btc_sent.get("price", 0)
    b_chg = btc_sent.get("change_1h", 0)
    b_rsi = btc_sent.get("rsi", 50)
    b_rec = btc_sent.get("recommendation", "Aman")

    col_macro, col_kill = st.columns([3, 1.2])
    with col_macro:
        if b_stat in ("PUMP_SPIKE", "DUMP_SPIKE"):
            st.error(f"**{b_lbl}** · BTC: ${b_price:,.1f} (1H Change: {b_chg:+}% | RSI: {b_rsi}) · *{b_rec}*")
        else:
            st.info(f"**{b_lbl}** · BTC: ${b_price:,.1f} (1H Change: {b_chg:+}% | RSI: {b_rsi}) · *{b_rec}*")

    with col_kill:
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            if st.button("🛑 Cancel Limit Web", type="secondary", use_container_width=True, help="Batalkan limit order antre yang dipasang via Web. Order manual di BingX 100% AMAN!"):
                with st.spinner("Membatalkan limit order web..."):
                    c_res = bingx_executor.cancel_web_orders_only("all")
                    st.warning(f"Hasil: {c_res}")
                    time.sleep(1)
                    st.rerun()
        with col_k2:
            if st.button("⚡ Tutup Posisi Web", type="secondary", use_container_width=True, help="Tutup darurat posisi yang dibuka via Web. Posisi manual (seperti ENS, dll.) 100% AMAN!"):
                with st.spinner("Menutup posisi web..."):
                    c_res = bingx_executor.close_web_positions_only("all")
                    st.warning(f"Hasil: {c_res}")
                    time.sleep(1)
                    st.rerun()

    # ── 2. HEADER KONTROL, FILTER & PENGURUTAN (WR & PnL) ────────────────
    c1, c2, c3, c4 = st.columns([1.5, 1.8, 1.2, 1])
    with c1:
        filter_dir = st.selectbox("Filter Arah", ["Semua", "LONG", "SHORT"], key="sinyal_dir_filter")
    with c2:
        sort_by = st.selectbox("Urutkan Berdasarkan", [
            "🏆 Skor Kualitas (WR Tertinggi)",
            "📈 PnL / ROE Tertinggi (Paling Cuan)",
            "📉 PnL Terendah (Dari Minus)",
            "⚡ Jarak Terdekat ke Limit"
        ], key="sinyal_sort_by")
    with c3:
        filter_min_score = st.slider("Skor Minimum", 50, 100, 60, 5, key="sinyal_score_filter")
    with c4:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        do_scan = st.button("🔄 Scan 100+ Koin", type="primary", use_container_width=True, key="sinyal_scan_btn")

    # ── 3. AMBIL / REFRESH SINYAL MURNI ────────────────────────────────
    cache_key = "sinyal_signals"
    scan_time_key = "sinyal_scan_time"

    if do_scan or cache_key not in st.session_state:
        cached = sinyal_engine.get_cached_signals(max_age_minutes=30)
        if cached is not None and not do_scan:
            st.session_state[cache_key] = cached
            st.session_state[scan_time_key] = (sinyal_engine.load_cache() or {}).get("scanned_at", time.time())
        else:
            progress_bar = st.progress(0, text="🔍 Scanning 100+ koin kripto BingX...")
            def on_progress(done, total):
                pct = done / max(total, 1)
                try:
                    progress_bar.progress(pct, text=f"🔍 Scanning... {done}/{total} koin")
                except Exception:
                    pass

            with st.spinner(""):
                signals = sinyal_engine.refresh_scan(progress_callback=on_progress)

            progress_bar.empty()
            st.session_state[cache_key] = signals
            st.session_state[scan_time_key] = time.time()

    all_signals = list(st.session_state.get(cache_key, []))
    scan_ts = st.session_state.get(scan_time_key, 0)
    scan_age_min = int((time.time() - scan_ts) / 60) if scan_ts else 0

    # ── 4. CEK STATUS AKTIF DI BURSA BINGX (UNTUK BADGE SAJA) ──────────
    live_bx = {}
    try:
        live_bx = bingx_executor.fetch_live_active_bingx_coins()
    except Exception:
        pass

    # ── 5. UPDATE HARGA REAL-TIME CEPAT & STATUS ───────────────────────
    bulk_prices = sinyal_engine.fetch_all_tickers()

    status_counts = {"SCANNING": 0, "AKTIF": 0, "MENDEKATI": 0,
                     "TP1_HIT": 0, "TP2_HIT": 0, "TP3_HIT": 0,
                     "KENA_SL": 0, "TELAT": 0, "EXPIRED": 0}

    for s in all_signals:
        sym = s["symbol"]
        base = sym.replace("-USDT", "").replace("1000", "")
        cp = bulk_prices.get(sym) or bulk_prices.get(base) or s.get("current_price") or 0.0
        s["_live_price"] = cp

        is_active_bursa = False
        if sym in live_bx or base in live_bx:
            info_bx = live_bx.get(sym) or live_bx.get(base)
            if info_bx.get("type") == "POSITION":
                is_active_bursa = True
                s["_is_real_pos"] = True
                s["_real_roe"] = info_bx.get("roe", 0)
                s["_real_pnl"] = info_bx.get("pnl", 0)
                s["_real_acc"] = str(info_bx.get("account", "akun_1")).replace("akun_", "Akun ")

        if is_active_bursa:
            st_key = "AKTIF"
        else:
            st_key = sinyal_engine.get_signal_status(s, cp)

        s["_live_status"] = st_key
        status_counts[st_key] = status_counts.get(st_key, 0) + 1

    # Kalkulasi ROE untuk setiap sinyal untuk pengurutan
    for s in all_signals:
        is_pos = s.get("_is_real_pos", False)
        if is_pos and "_real_roe" in s:
            f_roe = s["_real_roe"]
        else:
            d = s["direction"]
            lp = s.get("_live_price", s.get("current_price", s["entry"]))
            en = s["entry"]
            if d == "LONG":
                f_roe = ((lp - en) / (en + 1e-10)) * LEVERAGE_DISPLAY * 100
            else:
                f_roe = ((en - lp) / (en + 1e-10)) * LEVERAGE_DISPLAY * 100
        s["_calc_roe"] = f_roe

    # Pengurutan dinamis sesuai pilihan (WR / Skor / PnL)
    if "WR Tertinggi" in sort_by:
        all_signals.sort(key=lambda x: (x["score"], x.get("_calc_roe", 0)), reverse=True)
    elif "PnL / ROE Tertinggi" in sort_by:
        all_signals.sort(key=lambda x: x.get("_calc_roe", 0), reverse=True)
    elif "PnL Terendah" in sort_by:
        all_signals.sort(key=lambda x: x.get("_calc_roe", 0), reverse=False)
    elif "Jarak Terdekat" in sort_by:
        all_signals.sort(key=lambda x: abs(((x.get("_live_price", x["entry"]) - x["entry"]) / (x["entry"] + 1e-10)) * 100))

    long_count = sum(1 for s in all_signals if s.get("direction") == "LONG")
    short_count = sum(1 for s in all_signals if s.get("direction") == "SHORT")

    # ── 6. RINGKASAN SCAN ANALISA ───────────────────────────────────────
    st.markdown(f"""
<div class="scan-summary">
  <div class="scan-summary-item"><strong>{len(all_signals)}</strong>Sinyal Valid Teranalisa</div>
  <div class="scan-summary-item"><strong style="color:#00e676">{long_count}</strong>LONG</div>
  <div class="scan-summary-item"><strong style="color:#f44336">{short_count}</strong>SHORT</div>
  <div class="scan-summary-item"><strong style="color:#4caf50">{status_counts.get('AKTIF',0)}</strong>Posisi Aktif</div>
  <div class="scan-summary-item"><strong style="color:#f0c040">{status_counts.get('MENDEKATI',0)}</strong>Mendekati Limit</div>
  <div class="scan-summary-item"><strong style="color:#00e676">{status_counts.get('TP1_HIT',0)+status_counts.get('TP2_HIT',0)+status_counts.get('TP3_HIT',0)}</strong>TP Hit</div>
  <div class="scan-summary-item"><strong style="color:#f44336">{status_counts.get('KENA_SL',0)}</strong>SL Hit</div>
  <div class="scan-summary-item"><strong style="color:#5a7a9a">{scan_age_min}m</strong>Usia Cache</div>
</div>
""", unsafe_allow_html=True)

    # ── 7. TAB FILTER STATUS ───────────────────────────────────────────
    status_map = {
        "🔍 Semua":       None,
        "⏳ Menunggu/Scan": ["SCANNING"],
        "✅ Posisi Aktif":  ["AKTIF", "MENDEKATI"],
        "🎯 TP Cuan":     ["TP1_HIT", "TP2_HIT", "TP3_HIT"],
        "❌ Kena SL":     ["KENA_SL"],
        "⏰ Telat":        ["TELAT"],
        "💀 Expired":     ["EXPIRED"],
    }

    def count_tab(statuses):
        if statuses is None:
            return len([
                s for s in all_signals
                if (s.get("_is_real_pos") or s["score"] >= filter_min_score)
                and (filter_dir == "Semua" or s["direction"] == filter_dir)
            ])
        return len([
            s for s in all_signals
            if s.get("_live_status") in statuses
            and (s.get("_is_real_pos") or s["score"] >= filter_min_score)
            and (filter_dir == "Semua" or s["direction"] == filter_dir)
        ])

    tab_labels = [f"{k} ({count_tab(v)})" for k, v in status_map.items()]
    selected_tab_idx = st.radio(
        "Filter Status", tab_labels, horizontal=True, key="sinyal_status_tab",
        label_visibility="collapsed"
    )
    selected_tab_key = selected_tab_idx.split(" (")[0]
    selected_statuses = status_map.get(selected_tab_key)

    if selected_statuses is None:
        filtered = [
            s for s in all_signals
            if (s.get("_is_real_pos") or s["score"] >= filter_min_score)
            and (filter_dir == "Semua" or s["direction"] == filter_dir)
        ]
    else:
        filtered = [
            s for s in all_signals
            if s.get("_live_status") in selected_statuses
            and (s.get("_is_real_pos") or s["score"] >= filter_min_score)
            and (filter_dir == "Semua" or s["direction"] == filter_dir)
        ]

    if not filtered:
        st.markdown("""
<div class="empty-state">
  <div style="font-size:40px">🔍</div>
  <div style="font-size:16px;margin-top:10px;color:#5a7a9a">Belum ada sinyal yang memenuhi kriteria</div>
  <div style="font-size:12px;margin-top:6px;color:#3a5a7a">Tekan "Scan 100+ Koin" untuk memperbarui analisa pasar BingX</div>
</div>
""", unsafe_allow_html=True)
        return

    # ── 8. RENDER KARTU ANALISA SINYAL MURNI ───────────────────────────
    bx_state = bingx_executor.load_bingx_order_state()

    for sig in filtered:
        sym = sig["symbol"]
        coin = sym.replace("-USDT", "").replace("1000", "")
        direction = sig["direction"]
        score = sig["score"]
        entry = sig["entry"]
        sl = sig["sl"]
        bep_val = sig.get("bep", "—")
        tp1 = sig["tp1"]
        tp2 = sig["tp2"]
        tp3 = sig["tp3"]
        live_price = sig.get("_live_price", sig.get("current_price", entry))
        live_status = sig.get("_live_status", "SCANNING")
        rsi_4h = sig.get("rsi_4h", 50)
        rsi_1h = sig.get("rsi_1h", 50)
        ker = sig.get("ker", 0.3)
        rr = sig.get("rr", 1.5)
        reasons = sig.get("reasons", [])
        valid_wib = sig.get("valid_until_wib", "—")
        gen_ts  = sig.get("generated_at", time.time())
        gen_wib = datetime.fromtimestamp(gen_ts, WIB_TZ).strftime("%H:%M WIB")
        vol_ratio = sig.get("vol_ratio", 1.0)

        # Badge koin aktif di BingX (HANYA jika posisi memang sedang jalan di BingX)
        active_bx_badge = ""
        is_pos_bingx = sig.get("_is_real_pos", False)
        acc_label = sig.get("_real_acc", "Akun 1")

        if is_pos_bingx:
            active_bx_badge = f'<span style="background:#00e67622;color:#00e676;border:1px solid #00e676;font-size:11px;font-weight:800;padding:2px 8px;border-radius:12px;margin-left:8px">🟢 AKTIF BINGX ({acc_label})</span>'
        elif coin in live_bx or sym in live_bx:
            info_bx = live_bx.get(coin) or live_bx.get(sym)
            acc_name = str(info_bx.get("account", "akun_1")).replace("akun_", "Akun ")
            tipe = "POSISI" if info_bx.get("type") == "POSITION" else "LIMIT ORDER"
            active_bx_badge = f'<span style="background:#00e67622;color:#00e676;border:1px solid #00e676;font-size:11px;font-weight:800;padding:2px 8px;border-radius:12px;margin-left:8px">🟢 AKTIF BINGX ({acc_name})</span>'
        else:
            for acc_k, acc_lbl in [("akun_1", "Akun 1"), ("akun_2", "Akun 2"), ("akun_3", "Akun 3")]:
                rec = bx_state.get(f"{acc_k}_{sym}")
                if rec and rec.get("status") == "SUKSES_BINGX":
                    active_bx_badge = f'<span style="background:#00e67622;color:#00e676;border:1px solid #00e676;font-size:11px;font-weight:800;padding:2px 8px;border-radius:12px;margin-left:8px">🟢 AKTIF BINGX ({acc_lbl})</span>'
                    break

        # Floating ROE (hanya muncul saat posisi aktif)
        if is_pos_bingx and "_real_roe" in sig:
            float_pct = sig["_real_roe"]
            float_usd = sig.get("_real_pnl", 0.0)
        else:
            if direction == "LONG":
                float_pct = ((live_price - entry) / (entry + 1e-10)) * LEVERAGE_DISPLAY * 100
            else:
                float_pct = ((entry - live_price) / (entry + 1e-10)) * LEVERAGE_DISPLAY * 100
            float_usd  = (abs(float_pct) / 100) * MARGIN_DISPLAY

        float_sign = "+" if float_pct >= 0 else ""
        float_color = "#00e676" if float_pct >= 0 else "#f44336"
        float_icon  = "📈" if float_pct >= 0 else "📉"

        if is_pos_bingx or live_status in ("AKTIF", "MENDEKATI", "TP1_HIT", "TP2_HIT", "TP3_HIT", "KENA_SL"):
            float_html = (
                f'<span style="color:{float_color};font-size:13px;font-weight:700;margin-left:10px">' +
                f'{float_icon} {float_sign}{float_pct:.1f}% ROE&nbsp;' +
                f'<span style="font-size:11px;opacity:.8">({float_sign}${float_usd:.2f})</span></span>'
            )
        else:
            float_html = ""

        # Score bar color
        if score >= 90:
            bar_color = "#ffd700"
        elif score >= 80:
            bar_color = "#00e676"
        elif score >= 70:
            bar_color = "#7ec8e3"
        else:
            bar_color = "#4e6b8a"

        dir_class = "sig-dir-long" if direction == "LONG" else "sig-dir-short"
        card_class = "sig-card-long" if direction == "LONG" else "sig-card-short"

        if hasattr(sinyal_engine, "status_label"):
            status_lbl, status_color = sinyal_engine.status_label(live_status)
        else:
            status_lbl, status_color = (live_status, "#7ec8e3")

        if direction == "LONG":
            dist_to_entry = ((live_price - entry) / (entry + 1e-10) * 100)
            dist_str = f"▲{dist_to_entry:.2f}% dari entry" if dist_to_entry > 0 else f"✅ Di entry"
        else:
            dist_to_entry = ((entry - live_price) / (entry + 1e-10) * 100)
            dist_str = f"▲{dist_to_entry:.2f}% ke entry" if dist_to_entry > 0 else f"✅ Di entry"

        reasons_html = "".join(f'<div class="sig-reason-item">• {r}</div>' for r in reasons)

        card_html = f"""
<div class="sig-card {card_class}">
  <div class="sig-top">
    <div>
      <span class="sig-sym">{coin}</span>{active_bx_badge}{float_html}
      <span class="{dir_class}">{direction}</span>
      <span class="sig-status" style="background:{status_color}22;color:{status_color};border:1px solid {status_color}55">{status_lbl}</span>
    </div>
    <div style="text-align:right">
      <div style="color:{bar_color};font-size:22px;font-weight:800;line-height:1">{score}</div>
      <div style="color:#3a5a7a;font-size:10px">SKOR</div>
    </div>
  </div>
  <div class="sig-score-bar-wrap"><div class="sig-score-bar" style="width:{score}%;background:{bar_color}"></div></div>
  <div class="sig-grid">
    <div class="sig-cell">
      <div class="sig-cell-label">💎 Entry Limit BingX</div>
      <div class="sig-cell-val">{entry}</div>
      <div style="color:#3a5a7a;font-size:10px">{dist_str}</div>
      <div style="color:#00e676;font-size:10px;margin-top:4px;font-weight:600">💵 Margin Min: $0.20</div>
    </div>
    <div class="sig-cell">
      <div class="sig-cell-label">❌ Stop Loss (Proteksi)</div>
      <div class="sig-cell-val red">{sl}</div>
      <div style="color:#3a5a7a;font-size:10px">Risk: 1.2 ATR</div>
      <div style="color:#f44336;font-size:10px;margin-top:4px">Max Rugi: -$0.20</div>
    </div>
    <div class="sig-cell">
      <div class="sig-cell-label">🎯 TP1 (Tutup 70%)</div>
      <div class="sig-cell-val green">{tp1}</div>
      <div style="color:#00e676;font-size:10px;margin-top:2px">Kunci Cuan: +$0.21</div>
      <div class="sig-cell-val" style="color:#00bcd4;font-size:11px;margin-top:4px">🎯 TP2 (30%): {tp2}</div>
    </div>
    <div class="sig-cell">
      <div class="sig-cell-label">🛡️ Level BEP (+0.8R)</div>
      <div class="sig-cell-val" style="color:#00e5ff">{bep_val}</div>
      <div style="color:#00e5ff;font-size:10px;margin-top:2px">Kunci SL ke Entry ($0 Rugi)</div>
      <div style="color:#ffd700;font-size:11px;margin-top:4px">💰 TP3: {tp3}</div>
    </div>
  </div>
  <div class="sig-reasons">
    <div style="color:#3a5a7a;font-size:10px;margin-bottom:4px">KONFIRMASI ANALISA TEKNIS:</div>
    {reasons_html}
  </div>
  <div class="sig-meta">
    <div class="sig-meta-item">RSI 4H: <strong style="color:#7ec8e3">{rsi_4h}</strong></div>
    <div class="sig-meta-item">RSI 1H: <strong style="color:#7ec8e3">{rsi_1h}</strong></div>
    <div class="sig-meta-item">KER: <strong style="color:#7ec8e3">{ker}</strong></div>
    <div class="sig-meta-item">Vol: <strong style="color:#7ec8e3">{vol_ratio}x</strong></div>
    <div class="sig-valid">🕐 Aktif dari: {gen_wib} &nbsp;|&nbsp; ⏱ Valid s/d: {valid_wib}</div>
  </div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)

        # ── 9. PANEL EKSEKUSI LIMIT ORDER BINGX ───────────────────────────
        exp_label = f"⚡ Eksekusi Langsung {coin} ke Bursa BingX (Limit + SL + TP Otomatis)"
        with st.expander(exp_label, expanded=False):
            col_b1, col_b2, col_b3 = st.columns([1.5, 1.2, 1.3])
            
            with col_b1:
                target_tp_choice = st.radio(
                    f"Target TP {coin}",
                    [f"TP1 ({tp1})", f"TP2 ({tp2})", f"TP3 ({tp3})"],
                    horizontal=True,
                    key=f"tp_choice_{sym}"
                )
                chosen_label = target_tp_choice.split(" ")[0]
                chosen_tp_val = tp1 if chosen_label == "TP1" else (tp2 if chosen_label == "TP2" else tp3)

            with col_b2:
                target_account = st.selectbox(
                    "Pilih Akun",
                    ["Akun 1", "Akun 2", "Akun 3"],
                    key=f"acc_choice_{sym}"
                )
                acc_key = target_account.lower().replace(" ", "_")

            with col_b3:
                st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
                btn_order = st.button(
                    f"🚀 Pasang di {target_account}", 
                    key=f"btn_bx_{sym}_{acc_key}",
                    type="primary",
                    use_container_width=True
                )

            order_record_key = f"{acc_key}_{sym}"
            active_record = bx_state.get(order_record_key)

            if active_record and active_record.get("status") == "SUKSES_BINGX":
                st.success(
                    f"✅ **SUKSES BINGX!** Terpasang di {target_account} (#{active_record.get('order_id', '')[-6:]}) "
                    f"pada Entry {active_record.get('entry')} | SL: {active_record.get('sl')} | "
                    f"{active_record.get('tp_choice')}: {active_record.get('tp')} · [{active_record.get('time_str')}]"
                )

            if btn_order:
                with st.spinner(f"Mengirim Limit Order {coin} ke BingX ({target_account})..."):
                    res = bingx_executor.place_bingx_sniper_order(
                        account_key=acc_key,
                        symbol_clean=sym,
                        direction=direction,
                        entry_price=float(entry),
                        sl_price=float(sl),
                        tp_price=float(chosen_tp_val),
                        tp_choice_label=chosen_label,
                        margin_usd=0.20,
                        leverage=20
                    )
                    if res.get("success"):
                        st.balloons()
                        st.success(f"🎉 **{res.get('msg')}**")
                        st.rerun()
                    else:
                        st.error(f"❌ {res.get('msg')}")

    st.markdown(
        f"<div style='color:#2a4060;font-size:11px;text-align:center;padding:16px'>Sinyal limit order berbasis analisis teknikal multi-konfirmasi. "
        f"Data dari BingX Futures API. Diperbarui: {now_wib.strftime('%H:%M:%S WIB')}</div>",
        unsafe_allow_html=True
    )
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
        elif nav=='Sinyal':sinyal_page(summary)
        html(f'<div class="footnote"><span>KANTOR RAKUS · BOT FINAL</span><span>MONITOR SAJA · TANPA ORDER / CANCEL · {datetime.now(WIB).strftime("%H:%M:%S WIB")}</span></div>')
    body()
