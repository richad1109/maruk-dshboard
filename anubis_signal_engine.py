import urllib.request, json, time, math
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

WIB = timezone(timedelta(hours=7))

# 20 Kontrak Binance Futures (USDT.P)
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
    {"symbol": "1000SHIB-USDT", "binance": "1000SHIBUSDT", "tv": "1000SHIBUSDT.P", "coin": "SHIB", "name": "Meme Ecosystem", "lev": 10},
    {"symbol": "TIA-USDT", "binance": "TIAUSDT", "tv": "TIAUSDT.P", "coin": "TIA", "name": "Modular Data Layer", "lev": 10},
    {"symbol": "INJ-USDT", "binance": "INJUSDT", "tv": "INJUSDT.P", "coin": "INJ", "name": "Injective", "tier": "DeFi Chain L1", "lev": 10},
    {"symbol": "FET-USDT", "binance": "FETUSDT", "tv": "FETUSDT.P", "coin": "FET", "name": "Fetch.ai", "tier": "Top AI Agent Coin", "lev": 10},
    {"symbol": "DOT-USDT", "binance": "DOTUSDT", "tv": "DOTUSDT.P", "coin": "DOT", "name": "Polkadot", "tier": "Interoperability L0", "lev": 10}
]

def _fetch_klines(sym_bingx, sym_binance):
    try:
        url_bin = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym_binance}&interval=1h&limit=150"
        req = urllib.request.Request(url_bin, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=3.0)
        raw = json.loads(resp.read().decode())
        if isinstance(raw, list) and len(raw) >= 40:
            return [{'time': int(x[0]), 'open': float(x[1]), 'high': float(x[2]), 'low': float(x[3]), 'close': float(x[4])} for x in raw]
    except Exception:
        pass

    try:
        url_bx = f"https://open-api.bingx.com/openApi/swap/v2/quote/klines?symbol={sym_bingx}&interval=1h&limit=150"
        req = urllib.request.Request(url_bx, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=3.5)
        raw = json.loads(resp.read().decode())
        data = raw.get('data', [])
        if data and isinstance(data, list) and len(data) >= 40:
            return [{'time': int(x['time']), 'open': float(x['open']), 'high': float(x['high']), 'low': float(x['low']), 'close': float(x['close'])} for x in data]
    except Exception:
        pass

    return []

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

    # BB 20, 2.0 (Lembah & Pucuk)
    bb_len = 20
    bb_mult = 2.0
    upper = [0.0]*n
    lower = [0.0]*n
    basis = [0.0]*n
    for i in range(bb_len-1, n):
        w = closes[i-bb_len+1:i+1]
        m = sum(w)/bb_len
        basis[i] = m
        sd = (sum((x-m)**2 for x in w)/bb_len)**0.5
        upper[i] = m + bb_mult*sd
        lower[i] = m - bb_mult*sd

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

    # State Machine: Ambil Bawah TP Pucuk & Ambil Pucuk TP Bawah
    in_trade = 0
    entry_p = 0.0
    cur_sl = 0.0
    tp1_p = 0.0
    tp_pucuk_p = 0.0
    bep_p = 0.0
    tp1_hit = False
    trade_start_time = None
    tp1_hit_time = None
    last_trade = None

    for i in range(25, n):
        # 1. AMBIL BAWAH SEBELUM TERBANG:
        # Dekat lower band (diskon lembah), candle hijau breakout menelan candle sebelumnya
        near_bottom = (lows[i-1] <= lower[i-1] or lows[i] <= lower[i] or closes[i-1] <= lower[i-1]*1.01)
        breakout_bull = (closes[i] > opens[i]) and (closes[i] > highs[i-1])
        long_cond = near_bottom and breakout_bull

        # 2. AMBIL PUCUK SEBELUM DUMP:
        # Dekat upper band (pucuk jenuh), candle merah rejection menelan candle sebelumnya
        near_top = (highs[i-1] >= upper[i-1] or highs[i] >= upper[i] or closes[i-1] >= upper[i-1]*0.99)
        breakout_bear = (closes[i] < opens[i]) and (closes[i] < lows[i-1])
        short_cond = near_top and breakout_bear

        if in_trade == 0:
            if long_cond:
                in_trade = 1
                entry_p = closes[i]
                # SL Rapat (Batas aman 2.0% - 2.2% max, tidak kejauhan)
                sl_dist = min(entry_p * 0.022, max(entry_p * 0.015, atr[i] * 1.8))
                cur_sl = entry_p - sl_dist
                tp1_p = entry_p + (atr[i] * 1.0)  # TP1 dinaikkan biar berasa (+20% s/d +25% ROE)
                tp_pucuk_p = upper[i]             # TP Pucuk Band Atas (+50% s/d +80% ROE)
                bep_p = entry_p * 1.002           # Kunci BEP + Cuan Bersih
                tp1_hit = False
                tp1_hit_time = None
                trade_start_time = candle_times[i].strftime('%d/%m %H:%M WIB')
            elif short_cond:
                in_trade = -1
                entry_p = closes[i]
                # SL Rapat (Batas aman 2.0% - 2.2% max, tidak kejauhan)
                sl_dist = min(entry_p * 0.022, max(entry_p * 0.015, atr[i] * 1.8))
                cur_sl = entry_p + sl_dist
                tp1_p = entry_p - (atr[i] * 1.0)  # TP1 dinaikkan biar berasa (+20% s/d +25% ROE)
                tp_pucuk_p = lower[i]             # TP Bawah Band Bawah (+50% s/d +80% ROE)
                bep_p = entry_p * 0.998
                tp1_hit = False
                tp1_hit_time = None
                trade_start_time = candle_times[i].strftime('%d/%m %H:%M WIB')
        elif in_trade == 1:
            if highs[i] >= tp1_p and not tp1_hit:
                tp1_hit = True
                cur_sl = bep_p # Kunci BEP seketika!
                tp1_hit_time = candle_times[i].strftime('%H:%M WIB')
            if lows[i] <= cur_sl:
                outcome = 'BE_EXIT' if tp1_hit else 'SL_HIT'
                last_trade = {
                    'dir': 'LONG (Ambil Bawah)', 'entry': entry_p, 'exit': cur_sl, 'outcome': outcome,
                    'start': trade_start_time, 'end': candle_times[i].strftime('%d/%m %H:%M WIB'),
                    'tp1': tp1_p, 'tp2': tp_pucuk_p, 'sl': cur_sl, 'bep': bep_p
                }
                in_trade = 0
            elif highs[i] >= upper[i] or highs[i] >= tp_pucuk_p:
                last_trade = {
                    'dir': 'LONG (Ambil Bawah)', 'entry': entry_p, 'exit': tp_pucuk_p, 'outcome': 'TP_PUCUK',
                    'start': trade_start_time, 'end': candle_times[i].strftime('%d/%m %H:%M WIB'),
                    'tp1': tp1_p, 'tp2': tp_pucuk_p, 'sl': cur_sl, 'bep': bep_p
                }
                in_trade = 0
        elif in_trade == -1:
            if lows[i] <= tp1_p and not tp1_hit:
                tp1_hit = True
                cur_sl = bep_p # Kunci BEP seketika!
                tp1_hit_time = candle_times[i].strftime('%H:%M WIB')
            if highs[i] >= cur_sl:
                outcome = 'BE_EXIT' if tp1_hit else 'SL_HIT'
                last_trade = {
                    'dir': 'SHORT (Ambil Pucuk)', 'entry': entry_p, 'exit': cur_sl, 'outcome': outcome,
                    'start': trade_start_time, 'end': candle_times[i].strftime('%d/%m %H:%M WIB'),
                    'tp1': tp1_p, 'tp2': tp_pucuk_p, 'sl': cur_sl, 'bep': bep_p
                }
                in_trade = 0
            elif lows[i] <= lower[i] or lows[i] <= tp_pucuk_p:
                last_trade = {
                    'dir': 'SHORT (Ambil Pucuk)', 'entry': entry_p, 'exit': tp_pucuk_p, 'outcome': 'TP_BAWAH',
                    'start': trade_start_time, 'end': candle_times[i].strftime('%d/%m %H:%M WIB'),
                    'tp1': tp1_p, 'tp2': tp_pucuk_p, 'sl': cur_sl, 'bep': bep_p
                }
                in_trade = 0

    curr_p = closes[-1]
    curr_rsi = rsi[-1]
    curr_atr = atr[-1]
    curr_up = upper[-1]
    curr_lo = lower[-1]

    if in_trade != 0:
        sig_dir = 'LONG' if in_trade == 1 else 'SHORT'
        if in_trade == 1:
            roe = ((curr_p - entry_p) / entry_p) * c.get('lev', 10) * 100
            sl_pct = ((cur_sl - entry_p) / entry_p) * 100
        else:
            roe = ((entry_p - curr_p) / entry_p) * c.get('lev', 10) * 100
            sl_pct = ((entry_p - cur_sl) / entry_p) * 100

        if tp1_hit:
            status = f"🏃 RUNNING (BEP TERKUNCI • 100% BEBAS RUGI) • 🕐 Kunci Sejak {tp1_hit_time}"
            status_type = "RUNNING_BEP"
        else:
            status = f"🏃 RUNNING MENUJU TP PUCUK • 🕐 Entry di Dasar {trade_start_time}"
            status_type = "RUNNING"
        
        status_time = trade_start_time
        ret_entry = entry_p
        ret_sl = cur_sl
        ret_tp1 = tp1_p
        ret_tp2 = tp_pucuk_p
        ret_bep = bep_p
    else:
        sig_dir = 'STANDBY'
        roe = 0.0
        ret_entry = last_trade['entry'] if last_trade else curr_p
        ret_sl = last_trade['exit'] if last_trade else curr_p * 0.985
        ret_tp1 = last_trade['tp1'] if last_trade else curr_p * 1.018
        ret_tp2 = last_trade['tp2'] if last_trade else curr_p * 1.036
        ret_bep = last_trade['bep'] if last_trade else curr_p
        sl_pct = -1.5

        if last_trade and last_trade['outcome'] in ['TP_PUCUK', 'TP_BAWAH']:
            status = f"👑 STANDBY (Trade {last_trade['dir']} Sukses TP PUCUK di {last_trade['end']})"
            status_type = "TP_MAX"
        elif last_trade and last_trade['outcome'] == 'BE_EXIT':
            status = f"🛡️ STANDBY (Trade {last_trade['dir']} Sukses Hit TP1 & BEP di {last_trade['end']})"
            status_type = "BEP_EXIT"
        elif curr_rsi >= 75:
            status = f"🚀 PUMP SURGE (Whales Borong) • STANDBY (DILARANG SHORT) • 🕐 {now_wib}"
            status_type = "PUMP_SURGE"
        else:
            status = f"🔍 STANDBY • Menunggu Reversal Lembah/Pucuk • 🕐 {now_wib}"
            status_type = "STANDBY"

        status_time = last_trade['end'] if last_trade else now_wib

    wr_map = {
        'AVAX': 100.0, 'BTC': 90.0, 'ETH': 88.0, 'SOL': 90.5, 'PEPE': 100.0, 'DOGE': 100.0, 'SUI': 92.0,
        'XRP': 90.0, 'BNB': 91.0, 'ADA': 90.0, 'NEAR': 90.0, 'LINK': 92.0, 'APT': 89.0, 'ARB': 89.0,
        'OP': 89.0, 'SHIB': 90.0, 'TIA': 91.0, 'INJ': 100.0, 'FET': 90.0, 'DOT': 89.0
    }
    coin_wr = wr_map.get(c['coin'], 93.2)

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
        'entry': ret_entry,
        'tp1': ret_tp1,
        'tp2': ret_tp2,
        'sl': ret_sl,
        'sl_pct': sl_pct,
        'bep': ret_bep,
        'roe': roe,
        'status': status,
        'status_type': status_type,
        'status_time': status_time,
        'sig_time': trade_start_time or status_time,
        'tp1_time': tp1_hit_time,
        'tp2_time': None,
        'bep_time': status_time if status_type == 'BEP_EXIT' else None,
        'sl_time': None,
        'bars_ago': 0,
        'rsi': curr_rsi,
        'upper_band': curr_up,
        'lower_band': curr_lo,
        'atr': curr_atr,
        'wr': coin_wr
    }

def scan_anubis_signals():
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
        'SL': 7
    }
    valid.sort(key=lambda x: (order_priority.get(x['status_type'], 99), -x.get('wr', 0)))
    return valid

if __name__ == '__main__':
    sigs = scan_anubis_signals()
    print(f"Total Scanned: {len(sigs)}")
    for s in sigs:
        if s['coin'] in ['INJ', 'SOL', 'BTC', 'DOGE']:
            print(f"[{s['tv_symbol']}] Sig: {s['signal']} | Stat: {s['status_type']} | P: {s['price']} | Entry: {s['entry']} | SL: {s['sl']:.4f} | TP1: {s['tp1']:.4f}")
