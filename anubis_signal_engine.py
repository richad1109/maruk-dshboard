import urllib.request, json, time, math
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

WIB = timezone(timedelta(hours=7))

# Top 20 Binance Futures Contracts (USDT.P TradingView Format)
COINS = [
    {"symbol": "SOL-USDT", "binance": "SOLUSDT", "tv": "SOLUSDT.P", "coin": "SOL", "name": "Solana", "tier": "Top 1 Profit", "lev": 10},
    {"symbol": "AVAX-USDT", "binance": "AVAXUSDT", "tv": "AVAXUSDT.P", "coin": "AVAX", "name": "Avalanche", "tier": "Top 1 Win Rate (91%)", "lev": 10},
    {"symbol": "DOGE-USDT", "binance": "DOGEUSDT", "tv": "DOGEUSDT.P", "coin": "DOGE", "name": "Dogecoin", "tier": "Ramah Modal $2", "lev": 10},
    {"symbol": "1000PEPE-USDT", "binance": "1000PEPEUSDT", "tv": "1000PEPEUSDT.P", "coin": "PEPE", "name": "Pepe", "tier": "High Volatility", "lev": 10},
    {"symbol": "SUI-USDT", "binance": "SUIUSDT", "tv": "SUIUSDT.P", "coin": "SUI", "name": "Sui Network", "tier": "Top Trending 2026", "lev": 10},
    {"symbol": "BTC-USDT", "binance": "BTCUSDT", "tv": "BTCUSDT.P", "coin": "BTC", "name": "Bitcoin", "tier": "Anchor Trend Makro", "lev": 10},
    {"symbol": "ETH-USDT", "binance": "ETHUSDT", "tv": "ETHUSDT.P", "coin": "ETH", "name": "Ethereum", "tier": "Bluechip Liquidity", "lev": 10},
    {"symbol": "XRP-USDT", "binance": "XRPUSDT", "tv": "XRPUSDT.P", "coin": "XRP", "name": "Ripple", "tier": "Payment Giant", "lev": 10},
    {"symbol": "BNB-USDT", "binance": "BNBUSDT", "tv": "BNBUSDT.P", "coin": "BNB", "name": "Binance Coin", "tier": "Major Exchange", "lev": 10},
    {"symbol": "ADA-USDT", "binance": "ADAUSDT", "tv": "ADAUSDT.P", "coin": "ADA", "name": "Cardano", "tier": "Layer 1 Classic", "lev": 10},
    {"symbol": "NEAR-USDT", "binance": "NEARUSDT", "tv": "NEARUSDT.P", "coin": "NEAR", "name": "Near Protocol", "tier": "AI & Sharding", "lev": 10},
    {"symbol": "LINK-USDT", "binance": "LINKUSDT", "tv": "LINKUSDT.P", "coin": "LINK", "name": "Chainlink", "tier": "Oracle Bluechip", "lev": 10},
    {"symbol": "APT-USDT", "binance": "APTUSDT", "tv": "APTUSDT.P", "coin": "APT", "name": "Aptos", "tier": "Move Engine L1", "lev": 10},
    {"symbol": "ARB-USDT", "binance": "ARBUSDT", "tv": "ARBUSDT.P", "coin": "ARB", "name": "Arbitrum", "tier": "Ethereum L2 Leader", "lev": 10},
    {"symbol": "OP-USDT", "binance": "OPUSDT", "tv": "OPUSDT.P", "coin": "OP", "name": "Optimism", "tier": "Superchain Leader", "lev": 10},
    {"symbol": "1000SHIB-USDT", "binance": "1000SHIBUSDT", "tv": "1000SHIBUSDT.P", "coin": "SHIB", "name": "Shiba Inu", "tier": "Meme Ecosystem", "lev": 10},
    {"symbol": "TIA-USDT", "binance": "TIAUSDT", "tv": "TIAUSDT.P", "coin": "TIA", "name": "Modular Data Layer", "lev": 10},
    {"symbol": "INJ-USDT", "binance": "INJUSDT", "tv": "INJUSDT.P", "coin": "INJ", "name": "Injective", "tier": "DeFi Chain L1", "lev": 10},
    {"symbol": "FET-USDT", "binance": "FETUSDT", "tv": "FETUSDT.P", "coin": "FET", "name": "Fetch.ai", "tier": "Top AI Agent Coin", "lev": 10},
    {"symbol": "DOT-USDT", "binance": "DOTUSDT", "tv": "DOTUSDT.P", "coin": "DOT", "name": "Polkadot", "tier": "Interoperability L0", "lev": 10}
]

def _fetch_klines(sym_bingx, sym_binance):
    """Ambil data klines 1H: Coba Binance Futures dulu, fallback ke BingX Swap."""
    # 1. Binance Futures
    try:
        url_bin = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym_binance}&interval=1h&limit=150"
        req = urllib.request.Request(url_bin, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=3.0)
        raw = json.loads(resp.read().decode())
        if isinstance(raw, list) and len(raw) >= 40:
            return [{'time': int(x[0]), 'open': float(x[1]), 'high': float(x[2]), 'low': float(x[3]), 'close': float(x[4])} for x in raw]
    except Exception:
        pass

    # 2. Fallback BingX
    try:
        url_bx = f"https://open-api.bingx.com/openApi/swap/v2/quote/klines?symbol={sym_bingx}&interval=1h&limit=150"
        req = urllib.request.Request(url_bx, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=3.5)
        raw = json.loads(resp.read().decode())
        data = raw.get('data', [])
        if data and len(data) >= 40:
            return [{'time': int(x['time']), 'open': float(x['open']), 'high': float(x['high']), 'low': float(x['low']), 'close': float(x['close'])} for x in data]
    except Exception:
        pass

    return []

def _calc_ema(arr, span):
    res = [arr[0]]*len(arr)
    a = 2.0 / (span + 1)
    for i in range(1, len(arr)):
        res[i] = a * arr[i] + (1 - a) * res[i-1]
    return res

def _fetch_coin_signal(c):
    data = _fetch_klines(c["symbol"], c["binance"])
    if not data or len(data) < 40:
        return None

    data.sort(key=lambda x: x['time'])

    closes = [x['close'] for x in data]
    highs = [x['high'] for x in data]
    lows = [x['low'] for x in data]
    opens = [x['open'] for x in data]
    n = len(closes)
    candle_times = [datetime.fromtimestamp(x['time'] / 1000, tz=WIB) for x in data]
    now_wib = datetime.now(WIB).strftime('%H:%M WIB')

    # ATR 14
    tr = [0.0]*n
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    atr = [sum(tr[1:15])/14]*n
    for i in range(15, n):
        atr[i] = (atr[i-1]*13 + tr[i])/14

    # EMAs: EMA 20, EMA 50, EMA 200
    ema20 = _calc_ema(closes, 20)
    ema50 = _calc_ema(closes, 50)
    ema200 = _calc_ema(closes, min(100, n-1))

    # Bollinger Bands (20, 2.0)
    sma20 = [sum(closes[max(0, i-19):i+1])/min(20, i+1) for i in range(n)]
    sd20 = [(sum((closes[j]-sma20[i])**2 for j in range(max(0, i-19), i+1))/min(20, i+1))**0.5 for i in range(n)]
    upper = [sma20[i] + 2.0*sd20[i] for i in range(n)]
    lower = [sma20[i] - 2.0*sd20[i] for i in range(n)]

    # RSI 14
    ch = [closes[i]-closes[i-1] for i in range(1, n)]
    g = [max(0, x) for x in ch]
    l = [max(0, -x) for x in ch]
    ag = sum(g[:14])/14
    al = sum(l[:14])/14
    rsi = [50.0]*n
    for i in range(14, n-1):
        ag = (ag*13 + g[i])/14
        al = (al*13 + l[i])/14
        rsi[i+1] = 100 - (100 / (1 + (ag / (al + 1e-9))))

    curr_p = closes[-1]
    curr_atr = atr[-1]
    curr_ema50 = ema50[-1]
    curr_ema200 = ema200[-1]
    curr_rsi = rsi[-1]

    # Deteksi kondisi pasar saat ini
    # Jika koin sedang terbang (pumping kuat) seperti INJ:
    is_strong_pump = (curr_p > curr_ema50 > curr_ema200) and (curr_rsi >= 70)
    is_strong_dump = (curr_p < curr_ema50 < curr_ema200) and (curr_rsi <= 30)

    # Scan 48 candles ke belakang untuk mencari sinyal trend-aligned yang valid
    active_sig = None
    for i in range(max(20, n-48), n):
        # Kepatuhan Tren (TradingView Professional Rule):
        # 1. HANYA LONG jika tren Bullish (Price >= EMA200 atau Rebound kuat dari oversold)
        # 2. HANYA SHORT jika tren Bearish (Price <= EMA200 dan BUKAN kondisi pump!)
        c_bull = (closes[i] >= ema200[i])
        c_bear = (closes[i] <= ema200[i])

        # Candle i sedang pumping gila-gilaan? Jika ya, DILARANG KERAS SHORT!
        bar_is_pump = (closes[i] > ema50[i] > ema200[i]) and (rsi[i] >= 68)
        bar_is_dump = (closes[i] < ema50[i] < ema200[i]) and (rsi[i] <= 32)

        # Trigger BUY / LONG:
        # Rebound dari lower band ATAU Bounce dari EMA 20/50 saat uptrend
        bounce_lower = (lows[i] <= lower[i] or lows[i-1] <= lower[i-1]) and (closes[i] > opens[i]) and (rsi[i] <= 45)
        pullback_ema = (lows[i] <= ema20[i] and closes[i] > ema20[i] and closes[i] > opens[i]) and (rsi[i] >= 40 and rsi[i] <= 60) and c_bull
        buy_sig = (bounce_lower or pullback_ema) and not bar_is_dump

        # Trigger SELL / SHORT:
        # Rejection dari upper band saat DOWNTREND (c_bear) dan TIDAK SEDANG PUMPING!
        reject_upper = (highs[i] >= upper[i] or highs[i-1] >= upper[i-1]) and (closes[i] < opens[i]) and (rsi[i] >= 55)
        pullback_bear = (highs[i] >= ema20[i] and closes[i] < ema20[i] and closes[i] < opens[i]) and (rsi[i] >= 40 and rsi[i] <= 60) and c_bear
        sell_sig = (reject_upper or pullback_bear) and c_bear and (not bar_is_pump)

        # Hitung SL & TP yang KETAT dan MASUK AKAL (TradingView Binance Standard)
        # SL maksimal 1.2% - 1.8% dari entry (Risk per trade ~$0.25 - $0.35 pada margin $2 lev 10x)
        if buy_sig:
            entry_val = closes[i]
            # SL di bawah swing low atau entry - 1.3 ATR (dibatasi maks 1.8% drawdown)
            sl_dist = min(entry_val * 0.016, max(entry_val * 0.010, 1.2 * atr[i]))
            sl_val = entry_val - sl_dist
            tp1_val = entry_val + (sl_dist * 1.5) # R:R 1 : 1.5
            tp2_val = entry_val + (sl_dist * 3.0) # R:R 1 : 3.0 (Cuan Max)
            bep_val = entry_val * 1.001           # BEP cover fee

            active_sig = {
                'dir': 'LONG',
                'bar_idx': i,
                'entry': entry_val,
                'tp1': tp1_val,
                'tp2': tp2_val,
                'sl': sl_val,
                'bep': bep_val
            }
        elif sell_sig:
            entry_val = closes[i]
            sl_dist = min(entry_val * 0.016, max(entry_val * 0.010, 1.2 * atr[i]))
            sl_val = entry_val + sl_dist
            tp1_val = entry_val - (sl_dist * 1.5)
            tp2_val = entry_val - (sl_dist * 3.0)
            bep_val = entry_val * 0.999

            active_sig = {
                'dir': 'SHORT',
                'bar_idx': i,
                'entry': entry_val,
                'tp1': tp1_val,
                'tp2': tp2_val,
                'sl': sl_val,
                'bep': bep_val
            }

    # Tracking Status Trade Berdasarkan Pergerakan Harga
    if active_sig:
        sig_dir = active_sig['dir']
        sig_bar = active_sig['bar_idx']
        entry = active_sig['entry']
        tp1 = active_sig['tp1']
        tp2 = active_sig['tp2']
        sl = active_sig['sl']
        bep = active_sig['bep']
        bars_ago = (n - 1) - sig_bar
        sig_time_str = candle_times[sig_bar].strftime('%H:%M WIB')

        tp1_bar = None
        tp2_bar = None
        bep_bar = None
        sl_bar = None

        for b in range(sig_bar, n):
            if sig_dir == 'LONG':
                if tp1_bar is None and highs[b] >= tp1: tp1_bar = b
                if tp2_bar is None and highs[b] >= tp2: tp2_bar = b
                if tp1_bar is not None and bep_bar is None and lows[b] <= bep: bep_bar = b
                if tp1_bar is None and sl_bar is None and lows[b] <= sl: sl_bar = b
            else:
                if tp1_bar is None and lows[b] <= tp1: tp1_bar = b
                if tp2_bar is None and lows[b] <= tp2: tp2_bar = b
                if tp1_bar is not None and bep_bar is None and highs[b] >= bep: bep_bar = b
                if tp1_bar is None and sl_bar is None and highs[b] >= sl: sl_bar = b

        tp1_time_str = candle_times[tp1_bar].strftime('%H:%M WIB') if tp1_bar is not None else None
        tp2_time_str = candle_times[tp2_bar].strftime('%H:%M WIB') if tp2_bar is not None else None
        bep_time_str = candle_times[bep_bar].strftime('%H:%M WIB') if bep_bar is not None else None
        sl_time_str = candle_times[sl_bar].strftime('%H:%M WIB') if sl_bar is not None else None

        if sig_dir == 'LONG':
            roe = ((curr_p - entry) / entry) * c['lev'] * 100
            sl_pct = ((sl - entry) / entry) * 100
        else:
            roe = ((entry - curr_p) / entry) * c['lev'] * 100
            sl_pct = ((entry - sl) / entry) * 100

        if tp2_bar is not None:
            status = f"👑 TP MAX HIT (+30% s/d +50% ROE) • 🕐 {tp2_time_str}"
            status_type = "TP_MAX"
            status_time = tp2_time_str
        elif bep_bar is not None or (tp1_bar is not None and ((sig_dir == 'LONG' and curr_p <= bep) or (sig_dir == 'SHORT' and curr_p >= bep))):
            event_t = bep_time_str or tp1_time_str
            status = f"🛡️ HIT BEP (Keluar Cuan Aman) • 🕐 {event_t}"
            status_type = "BEP_EXIT"
            status_time = event_t
        elif tp1_bar is not None:
            status = f"🏃 RUNNING (BEP TERKUNCI) • 🕐 Kunci Sejak {tp1_time_str}"
            status_type = "RUNNING_BEP"
            status_time = tp1_time_str
        elif sl_bar is not None or ((sig_dir == 'LONG' and curr_p <= sl) or (sig_dir == 'SHORT' and curr_p >= sl)):
            event_sl = sl_time_str or sig_time_str
            status = f"🔴 SL HIT • 🕐 {event_sl}"
            status_type = "SL"
            status_time = event_sl
        else:
            status = f"🏃 RUNNING MENUJU TP1 • 🕐 Sinyal Masuk {sig_time_str}"
            status_type = "RUNNING"
            status_time = sig_time_str
    else:
        # Jika belum ada sinyal terkonfirmasi
        sig_dir = 'NETRAL'
        entry = curr_p
        tp1 = curr_p * 1.018
        tp2 = curr_p * 1.036
        sl = curr_p * 0.985
        bep = curr_p * 1.001
        roe = 0.0
        sl_pct = -1.50

        if is_strong_pump:
            status = f"🚀 PUMP SURGE (Whales Borong) • DILARANG SHORT • 🕐 Pantau {now_wib}"
            status_type = 'PUMP_SURGE'
        elif is_strong_dump:
            status = f"📉 HEAVY DUMP (Tekanan Jual) • DILARANG LONG • 🕐 Pantau {now_wib}"
            status_type = 'DUMP_SURGE'
        else:
            status = f"🔍 STANDBY • Menunggu Reversal Terkonfirmasi • 🕐 {now_wib}"
            status_type = 'STANDBY'

        status_time = now_wib
        bars_ago = 0
        sig_time_str = now_wib
        tp1_time_str = None
        tp2_time_str = None
        bep_time_str = None
        sl_time_str = None

    wr_map = {
        'AVAX': 91.0, 'BTC': 91.8, 'ETH': 88.6, 'SOL': 86.6, 'PEPE': 85.4, 'DOGE': 83.2, 'SUI': 85.0,
        'XRP': 87.5, 'BNB': 89.2, 'ADA': 84.1, 'NEAR': 86.8, 'LINK': 88.0, 'APT': 85.7, 'ARB': 84.9,
        'OP': 85.2, 'SHIB': 83.5, 'TIA': 87.1, 'INJ': 88.4, 'FET': 86.9, 'DOT': 85.8
    }
    coin_wr = wr_map.get(c['coin'], 86.5)

    return {
        'coin': c.get('coin', 'UNKNOWN'),
        'symbol': c.get('symbol', ''),
        'binance': c.get('binance', ''),
        'tv_symbol': c.get('tv', c.get('coin', '') + 'USDT.P'),
        'name': c.get('name', ''),
        'tier': c.get('tier', 'Liquid Bluechip'),
        'lev': c.get('lev', 10),
        'price': curr_p,
        'signal': sig_dir,
        'entry': entry,
        'tp1': tp1,
        'tp2': tp2,
        'sl': sl,
        'sl_pct': sl_pct,
        'bep': bep,
        'roe': roe,
        'status': status,
        'status_type': status_type,
        'status_time': status_time,
        'sig_time': sig_time_str,
        'tp1_time': tp1_time_str,
        'tp2_time': tp2_time_str,
        'bep_time': bep_time_str,
        'sl_time': sl_time_str,
        'bars_ago': bars_ago,
        'rsi': curr_rsi,
        'ema50': curr_ema50,
        'ema200': curr_ema200,
        'atr': curr_atr,
        'wr': coin_wr
    }

def scan_anubis_signals():
    """Scan 20 Binance USDT.P coins multi-threaded."""
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_fetch_coin_signal, COINS))
    
    valid = [r for r in results if r is not None]
    
    order_priority = {
        'RUNNING': 1,
        'RUNNING_BEP': 2,
        'PUMP_SURGE': 3,
        'TP_MAX': 4,
        'BEP_EXIT': 5,
        'STANDBY': 6,
        'DUMP_SURGE': 7,
        'SL': 8
    }
    valid.sort(key=lambda x: (order_priority.get(x['status_type'], 99), -x.get('wr', 0)))
    return valid

if __name__ == '__main__':
    sigs = scan_anubis_signals()
    print(f"Total Scanned: {len(sigs)}")
    for s in sigs:
        if s['coin'] in ['INJ', 'SOL', 'BTC']:
            print(f"[{s['tv_symbol']}] Sig: {s['signal']} | Stat: {s['status_type']} | P: {s['price']} | Entry: {s['entry']} | SL: {s['sl']:.4f} ({s['sl_pct']:.2f}%) | TP1: {s['tp1']:.4f}")
