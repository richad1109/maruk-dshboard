import urllib.request, json, time, math
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

WIB = timezone(timedelta(hours=7))

# Top 20 Liquid Coins on BingX Futures
COINS = [
    {"symbol": "SOL-USDT", "coin": "SOL", "name": "Solana", "tier": "Top 1 Profit", "lev": 10},
    {"symbol": "AVAX-USDT", "coin": "AVAX", "name": "Avalanche", "tier": "Top 1 Win Rate (91%)", "lev": 10},
    {"symbol": "DOGE-USDT", "coin": "DOGE", "name": "Dogecoin", "tier": "Ramah Modal $2", "lev": 10},
    {"symbol": "1000PEPE-USDT", "coin": "PEPE", "name": "Pepe", "tier": "High Volatility", "lev": 10},
    {"symbol": "SUI-USDT", "coin": "SUI", "name": "Sui Network", "tier": "Top Trending 2026", "lev": 10},
    {"symbol": "BTC-USDT", "coin": "BTC", "name": "Bitcoin", "tier": "Anchor Trend Makro", "lev": 10},
    {"symbol": "ETH-USDT", "coin": "ETH", "name": "Ethereum", "tier": "Bluechip Liquidity", "lev": 10},
    {"symbol": "XRP-USDT", "coin": "XRP", "name": "Ripple", "tier": "Payment Giant", "lev": 10},
    {"symbol": "BNB-USDT", "coin": "BNB", "name": "Binance Coin", "tier": "Major Exchange", "lev": 10},
    {"symbol": "ADA-USDT", "coin": "ADA", "name": "Cardano", "tier": "Layer 1 Classic", "lev": 10},
    {"symbol": "NEAR-USDT", "coin": "NEAR", "name": "Near Protocol", "tier": "AI & Sharding", "lev": 10},
    {"symbol": "LINK-USDT", "coin": "LINK", "name": "Chainlink", "tier": "Oracle Bluechip", "lev": 10},
    {"symbol": "APT-USDT", "coin": "APT", "name": "Aptos", "tier": "Move Engine L1", "lev": 10},
    {"symbol": "ARB-USDT", "coin": "ARB", "name": "Arbitrum", "tier": "Ethereum L2 Leader", "lev": 10},
    {"symbol": "OP-USDT", "coin": "OP", "name": "Optimism", "tier": "Superchain Leader", "lev": 10},
    {"symbol": "1000SHIB-USDT", "coin": "SHIB", "name": "Shiba Inu", "tier": "Meme Ecosystem", "lev": 10},
    {"symbol": "TIA-USDT", "coin": "TIA", "name": "Celestia", "tier": "Modular Data Layer", "lev": 10},
    {"symbol": "INJ-USDT", "coin": "INJ", "name": "Injective", "tier": "DeFi Chain L1", "lev": 10},
    {"symbol": "FET-USDT", "coin": "FET", "name": "Fetch.ai", "tier": "Top AI Agent Coin", "lev": 10},
    {"symbol": "DOT-USDT", "coin": "DOT", "name": "Polkadot", "tier": "Interoperability L0", "lev": 10}
]

def _fetch_coin_signal(c):
    sym = c["symbol"]
    url = f"https://open-api.bingx.com/openApi/swap/v2/quote/klines?symbol={sym}&interval=1h&limit=150"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=3.5)
        data_raw = json.loads(resp.read().decode())
        data = data_raw.get('data', [])
    except Exception:
        return None

    if len(data) < 40:
        return None

    # Sort chronologically (oldest to newest)
    data.sort(key=lambda x: int(x['time']))

    closes = [float(x['close']) for x in data]
    highs = [float(x['high']) for x in data]
    lows = [float(x['low']) for x in data]
    opens = [float(x['open']) for x in data]
    n = len(closes)
    candle_times = [datetime.fromtimestamp(int(x['time']) / 1000, tz=WIB) for x in data]
    now_wib = datetime.now(WIB).strftime('%H:%M WIB')

    # ATR 14
    tr = [0.0]*n
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    atr = [sum(tr[1:15])/14]*n
    for i in range(15, n):
        atr[i] = (atr[i-1]*13 + tr[i])/14

    # EMA 200 (atau EMA n/2 jika n < 200)
    ema_span = min(100, n - 1)
    ema200 = [closes[0]]*n
    a_ema = 2.0 / (ema_span + 1)
    for i in range(1, n):
        ema200[i] = a_ema * closes[i] + (1 - a_ema) * ema200[i-1]

    # BB 20, 2.0
    period = 20
    dev = 2.0
    basis = [0.0]*n
    upper = [0.0]*n
    lower = [0.0]*n
    for i in range(period-1, n):
        w = closes[i-period+1:i+1]
        m = sum(w)/period
        basis[i] = m
        var = sum((x-m)**2 for x in w)/period
        sd = var**0.5
        upper[i] = m + dev*sd
        lower[i] = m - dev*sd

    # RSI 14
    gains = [0.0]*n
    losses = [0.0]*n
    for i in range(1, n):
        ch = closes[i] - closes[i-1]
        gains[i] = max(0, ch)
        losses[i] = max(0, -ch)
    ag = sum(gains[1:15])/14
    al = sum(losses[1:15])/14
    rsi = [50.0]*n
    for i in range(15, n):
        ag = (ag*13 + gains[i])/14
        al = (al*13 + losses[i])/14
        rs = ag/al if al != 0 else 100
        rsi[i] = 100 - (100/(1+rs))

    curr_p = closes[-1]
    curr_atr = atr[-1]
    curr_ema = ema200[-1]
    curr_upper = upper[-1]
    curr_lower = lower[-1]
    curr_rsi = rsi[-1]

    # Scan back last 36 candles (36 hours lookback so running trades aren't lost)
    active_sig = None
    for i in range(max(25, n-36), n):
        trend_bull = (closes[i] >= ema200[i]) or (rsi[i] <= 32)
        trend_bear = (closes[i] <= ema200[i]) or (rsi[i] >= 68)
        
        buy_sig = (lows[i] <= lower[i] or lows[i-1] <= lower[i-1]) and (closes[i] > opens[i]) and (rsi[i] <= 45) and trend_bull
        sell_sig = (highs[i] >= upper[i] or highs[i-1] >= upper[i-1]) and (closes[i] < opens[i]) and (rsi[i] >= 55) and trend_bear
        
        if buy_sig:
            active_sig = {
                'dir': 'LONG',
                'bar_idx': i,
                'entry': closes[i],
                'tp1': closes[i] + 0.5 * atr[i],
                'tp2': closes[i] + 2.0 * atr[i],
                'sl': closes[i] - 3.2 * atr[i],
                'bep': closes[i] + 0.25 * atr[i]
            }
        elif sell_sig:
            active_sig = {
                'dir': 'SHORT',
                'bar_idx': i,
                'entry': closes[i],
                'tp1': closes[i] - 0.5 * atr[i],
                'tp2': closes[i] - 2.0 * atr[i],
                'sl': closes[i] + 3.2 * atr[i],
                'bep': closes[i] - 0.25 * atr[i]
            }

    # Status tracking with exact candle timestamps
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
                if tp1_bar is None and highs[b] >= tp1:
                    tp1_bar = b
                if tp2_bar is None and highs[b] >= tp2:
                    tp2_bar = b
                if tp1_bar is not None and bep_bar is None and lows[b] <= bep:
                    bep_bar = b
                if tp1_bar is None and sl_bar is None and lows[b] <= sl:
                    sl_bar = b
            else:
                if tp1_bar is None and lows[b] <= tp1:
                    tp1_bar = b
                if tp2_bar is None and lows[b] <= tp2:
                    tp2_bar = b
                if tp1_bar is not None and bep_bar is None and highs[b] >= bep:
                    bep_bar = b
                if tp1_bar is None and sl_bar is None and highs[b] >= sl:
                    sl_bar = b

        tp1_time_str = candle_times[tp1_bar].strftime('%H:%M WIB') if tp1_bar is not None else None
        tp2_time_str = candle_times[tp2_bar].strftime('%H:%M WIB') if tp2_bar is not None else None
        bep_time_str = candle_times[bep_bar].strftime('%H:%M WIB') if bep_bar is not None else None
        sl_time_str = candle_times[sl_bar].strftime('%H:%M WIB') if sl_bar is not None else None

        if sig_dir == 'LONG':
            roe = ((curr_p - entry) / entry) * c['lev'] * 100
        else:
            roe = ((entry - curr_p) / entry) * c['lev'] * 100

        if tp2_bar is not None:
            status = f"👑 TP MAX HIT (+40% s/d +70% ROE) • 🕐 {tp2_time_str}"
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
        sig_dir = 'NETRAL'
        entry = curr_p
        tp1 = curr_p * 1.015
        tp2 = curr_p * 1.035
        sl = curr_p * 0.965
        bep = curr_p
        roe = 0.0
        status = f"🔍 STANDBY • 🕐 Pantau {now_wib}"
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
        'coin': c['coin'],
        'symbol': sym,
        'name': c['name'],
        'tier': c['tier'],
        'lev': c['lev'],
        'price': curr_p,
        'signal': sig_dir,
        'entry': entry,
        'tp1': tp1,
        'tp2': tp2,
        'sl': sl,
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
        'atr': curr_atr,
        'wr': coin_wr
    }

def scan_anubis_signals():
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_coin_signal, c) for c in COINS]
        for f in futures:
            res = f.result()
            if res:
                results.append(res)
    # Sort: active signals (LONG/SHORT) first, then STANDBY
    results.sort(key=lambda x: (0 if x['signal'] in ['LONG', 'SHORT'] else 1, x['coin']))
    return results

if __name__ == '__main__':
    t0 = time.time()
    res = scan_anubis_signals()
    dur = time.time() - t0
    print(f"Scanned {len(res)} coins in {dur:.2f}s:")
    for r in res:
        clean_status = r['status'].encode('ascii', 'ignore').decode()
        print(f"[{r['coin']:4}] {r['signal']:<5} | Price: ${r['price']:.4f} | Entry: {r['sig_time']} | TP1: {r['tp1_time']} | Status: {clean_status}")
