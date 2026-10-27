"""MEXC public-only scanner. Fixed rules, chronological holdout, no order methods."""
import math
import time
from concurrent.futures import ThreadPoolExecutor
import requests
from btc_research import ema, wilder

BASE='https://api.mexc.com/api/v1/contract/'
RULES=('Trend pullback','Donchian breakout','Range reversal')

def get(path,params=None):
    import exchange_network
    exchange_network.install_dns()
    r=requests.get(BASE+path,params=params,timeout=(5,15));r.raise_for_status();p=r.json()
    if not p.get('success') or str(p.get('code'))!='0':raise ValueError('API publik MEXC menolak data')
    return p['data']

def catalog():
    contracts=get('detail'); tickers={r['symbol']:r for r in get('ticker')}
    rows=[]
    for c in contracts:
        if c.get('quoteCoin')!='USDT' or c.get('state')!=0:continue
        t=tickers.get(c['symbol'],{});bid=float(t.get('bid1') or 0);ask=float(t.get('ask1') or 0)
        rows.append(dict(symbol=c['symbol'],tradfi='mc-trade-zone-tradfi' in c.get('conceptPlate',[]),volume=float(t.get('amount24') or 0),
            spread=100*(ask-bid)/((ask+bid)/2) if ask>=bid>0 else None,
            last=float(t.get('lastPrice') or 0),funding=t.get('fundingRate'),fee=c.get('takerFeeRate'),
            api_allowed=c.get('apiAllowed'),timestamp=t.get('timestamp')))
    return sorted(rows,key=lambda r:r['volume'],reverse=True)

def candles(symbol):
    d=get('kline/'+symbol,{'interval':'Min60','start':int(time.time())-2000*3600,'end':int(time.time())})
    return [dict(time=int(t),**{k:float(d[k][i]) for k in ('open','high','low','close','vol')}) for i,t in enumerate(d['time'])]

def clean(rows,now):
    rows=sorted({r['time']:r for r in rows if r['time']+3600<=now}.values(),key=lambda r:r['time'])
    if len(rows)<400:raise ValueError('Riwayat kurang dari 400 candle tertutup')
    if now-rows[-1]['time']-3600>7200:raise ValueError('Data candle usang')
    for i,r in enumerate(rows):
        if any(not math.isfinite(r[k]) or r[k]<=0 for k in ('open','high','low','close')):raise ValueError('Harga invalid')
        if r['high']<max(r['open'],r['close'],r['low']) or r['low']>min(r['open'],r['close']):raise ValueError('OHLC invalid')
        if i and r['time']-rows[i-1]['time']!=3600:raise ValueError('Candle berlubang')
    return rows

def features(rows):
    out=[]; e20=e50=e100=rows[0]['close'];atr=0;up=down=0
    for i,r in enumerate(rows):
        c=r['close'];prev=rows[max(0,i-1)]['close'];delta=c-prev
        e20+=(c-e20)*2/21;e50+=(c-e50)*2/51;e100+=(c-e100)*2/101
        tr=max(r['high']-r['low'],abs(r['high']-prev),abs(r['low']-prev));atr=tr if i==0 else (atr*13+tr)/14
        up=(up*13+max(delta,0))/14;down=(down*13+max(-delta,0))/14
        rsi=100-100/(1+up/down) if down else 100 if up else 50
        prior=rows[max(0,i-24):i];recent=rows[max(0,i-20):i+1]
        path=sum(abs(b['close']-a['close']) for a,b in zip(recent,recent[1:]));ker=abs(c-recent[0]['close'])/path if path else 0
        out.append(dict(atr=atr,e20=e20,e50=e50,e100=e100,rsi=rsi,ker=ker,
            high=max((x['high'] for x in prior),default=c),low=min((x['low'] for x in prior),default=c)))
    return out

def side_at(rows,f,i,rule):
    if i<100:return 0
    r=rows[i];a=f[i];c=r['close'];previous=rows[i-1]
    trend=1 if a['e20']>a['e50']>a['e100'] else -1 if a['e20']<a['e50']<a['e100'] else 0
    if rule=='Donchian breakout':return 1 if c>a['high'] and trend==1 and a['ker']>=.35 else -1 if c<a['low'] and trend==-1 and a['ker']>=.35 else 0
    if rule=='Trend pullback':return 1 if trend==1 and previous['low']<=f[i-1]['e20'] and c>a['e20'] and 50<a['rsi']<68 and a['ker']>.2 else -1 if trend==-1 and previous['high']>=f[i-1]['e20'] and c<a['e20'] and 32<a['rsi']<50 and a['ker']>.2 else 0
    return 1 if a['ker']<.2 and a['rsi']<28 and c>previous['close'] else -1 if a['ker']<.2 and a['rsi']>72 and c<previous['close'] else 0

def replay(rows,f,rule,start,end,fee,slip,funding):
    trades=[];i=max(100,start)
    while i<end-1:
        side=side_at(rows,f,i,rule)
        if not side:i+=1;continue
        risk=2*f[i]['atr'];entry=rows[i+1]['open']*(1+side*slip)
        sl=entry-side*risk;tp=entry+side*2*risk;exit_i=min(i+24,end-1);exit_price=rows[exit_i]['close'];reason='TIME'
        for j in range(i+1,exit_i+1):
            r=rows[j];hit_sl=r['low']<=sl if side==1 else r['high']>=sl;hit_tp=r['high']>=tp if side==1 else r['low']<=tp
            if hit_sl:exit_price=min(sl,r['open']) if side==1 else max(sl,r['open']);exit_i=j;reason='SL';break
            if hit_tp:exit_price=tp;exit_i=j;reason='TP';break
        exit_price*=1-side*slip
        # Adverse funding proxy per held hour; actual historical rate is NOT asserted.
        net=side*(exit_price-entry)/entry-fee*(1+exit_price/entry)-funding*(exit_i-i)/8
        trades.append(dict(entry_at=rows[i+1]['time'],exit_at=rows[exit_i]['time']+3600,side='LONG' if side==1 else 'SHORT',entry=entry,exit=exit_price,reason=reason,net_pct=net*100,R=net/(risk/entry)))
        i=exit_i+4
    n=len(trades);wins=sum(t['net_pct']>0 for t in trades);wr=wins/n if n else 0;z=1.96
    lower=(wr+z*z/(2*n)-z*math.sqrt(wr*(1-wr)/n+z*z/(4*n*n)))/(1+z*z/n) if n else 0
    gain=sum(max(t['R'],0) for t in trades);loss=-sum(min(t['R'],0) for t in trades)
    return dict(n=n,wins=wins,wr=100*wr,lower=100*lower,pf=gain/loss if loss else None,mean_r=sum(t['R'] for t in trades)/n if n else None,trades=trades)

def evaluate(rows,meta,rule=RULES[0],now=None,slip=.0005,funding=.0001):
    now=time.time() if now is None else now;rows=clean(rows,now);f=features(rows);split=max(200,int(len(rows)*.7))
    fee=meta.get('fee')
    if fee is None:raise ValueError('Fee kontrak belum tersedia')
    fee=float(fee)
    if not math.isfinite(fee) or not 0<=fee<=.01:raise ValueError("Fee kontrak invalid")
    train=replay(rows,f,rule,100,split,fee,slip,funding);test=replay(rows,f,rule,split,len(rows),fee,slip,funding)
    side=side_at(rows,f,len(rows)-1,rule);entry=rows[-1]['close'];risk=2*f[-1]['atr']
    if risk>=entry:side=0
    liquid=meta.get('volume',0)>=1000000 and meta.get('spread') is not None and meta['spread']<=.1
    qualified=test['n']>=30 and test['pf'] is not None and test['pf']>1 and test['mean_r']>0
    target90=qualified and test['n']>=100 and test['wr']>=90 and test['lower']>=80
    return dict(symbol=meta['symbol'],rule=rule,side=side,entry=entry,sl=entry-side*risk if side else None,tp=entry+side*2*risk if side else None,
        atr=f[-1]['atr'],rsi=f[-1]['rsi'],ker=f[-1]['ker'],closed=rows[-1]['time']+3600,expires=rows[-1]['time']+7200,
        train=train,test=test,qualified=qualified,liquid=liquid,target90=target90,
        status='KANDIDAT TERUJI' if side and qualified and liquid else 'SETUP BELUM TERVALIDASI' if side else 'TUNGGU',
        start=rows[0]['time'],split=rows[split]['time'],end=rows[-1]['time']+3600,bars=len(rows),fee=fee,slip=slip,funding=funding)

def scan_one(meta,rule):
    try:return evaluate(candles(meta['symbol']),meta,rule)
    except Exception as e:return dict(symbol=meta['symbol'],error=type(e).__name__,message=str(e) if isinstance(e,ValueError) else 'Data publik gagal dibaca; coba lagi')

def scan(items,rule):
    with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(lambda m:scan_one(m,rule),items))

def scan_multi(items):
    """Fetch each coin once; evaluate fixed rules without changing holdout thresholds."""
    def one(meta):
        try:
            rows=candles(meta['symbol'])
            return dict(symbol=meta['symbol'],candidates=[evaluate(rows,meta,rule) for rule in RULES])
        except Exception as e:
            return dict(symbol=meta['symbol'],error=type(e).__name__,candidates=[])
    with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(one,items))

def touch_status(signal,rows):
    """Level observation after publication, never an exchange fill claim."""
    start=math.ceil(signal['published']/60)*60
    for r in sorted(rows,key=lambda r:r['time']):
        if r['time']<start:continue
        if r['time']>=signal['expires']:break
        long=signal['side']==1
        tp=r['high']>=signal['tp'] if long else r['low']<=signal['tp']
        sl=r['low']<=signal['sl'] if long else r['high']>=signal['sl']
        if tp or sl:return dict(status='AMBIGU' if tp and sl else 'TP' if tp else 'SL',at=r['time'])
    return dict(status='AKTIF' if time.time()<signal['expires'] else 'KEDALUWARSA',at=None)

def observe_touch(signal):
    # Up to one hour validity, safely below 2000-minute endpoint cap.
    d=get('kline/'+signal['symbol'],{'interval':'Min1','start':int(signal['published']),'end':int(time.time())})
    rows=[dict(time=int(t),high=float(d['high'][i]),low=float(d['low'][i])) for i,t in enumerate(d['time'])]
    return touch_status(signal,rows)
