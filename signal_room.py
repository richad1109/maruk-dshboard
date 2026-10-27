"""Public-price scenario desk. Deterministic calculations; no execution or forecast odds."""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import math
import time
import requests
import btc_research

HOUR=3600
COINS=('BTC','SOL','DOGE')
HOST='https://open-api.bingx.com'


def four_hour(rows,now):
    buckets=defaultdict(list)
    for row in {r['time']:r for r in rows}.values():
        if row['time']+HOUR<=now:buckets[int(row['time']//(4*HOUR))].append(row)
    out=[]
    for bucket,g in sorted(buckets.items()):
        g=sorted(g,key=lambda r:r['time'])
        if len(g)==4 and all(r['time']==bucket*4*HOUR+i*HOUR for i,r in enumerate(g)):
            out.append(dict(time=g[0]['time'],close=g[-1]['close'],open=g[0]['open'],
                            high=max(r['high'] for r in g),low=min(r['low'] for r in g)))
    return out


def correlation(a,b):
    x={r['time']:r['close'] for r in a};y={r['time']:r['close'] for r in b}
    times=sorted(set(x)&set(y))[-181:]
    if len(times)<181 or any(t-p!=4*HOUR for p,t in zip(times,times[1:])):return None
    xx=[math.log(x[t]/x[p]) for p,t in zip(times,times[1:])]
    yy=[math.log(y[t]/y[p]) for p,t in zip(times,times[1:])]
    n=len(xx);sx=sum(xx);sy=sum(yy)
    den=math.sqrt(max(0,n*sum(v*v for v in xx)-sx*sx)*max(0,n*sum(v*v for v in yy)-sy*sy))
    return max(-1.,min(1.,(n*sum(u*v for u,v in zip(xx,yy))-sx*sy)/den)) if den else 0.


def report(coin,rows,btc_rows=None,now=None):
    now=time.time() if now is None else now
    tech=btc_research.analyze(rows,now)
    closed=sorted({r['time']:r for r in rows if r['time']+HOUR<=now}.values(),key=lambda r:r['time'])
    four=four_hour(closed,now);closes=[r['close'] for r in four]
    tr=[max(r['high']-r['low'],abs(r['high']-(four[i-1]['close'] if i else r['close'])),
            abs(r['low']-(four[i-1]['close'] if i else r['close']))) for i,r in enumerate(four)]
    atr4=btc_research.wilder(tr);mom=closes[-1]/closes[-4]-1
    rsi=tech['rsi'];last=tech['close'];support=tech['support'];resistance=tech['resistance']
    travel=sum(abs(b-a) for a,b in zip(closes[-21:],closes[-20:]))
    ker=abs(closes[-1]-closes[-21])/travel if travel else 0.
    raw=(1 if mom>=.025 else -1 if mom<=-.025 else 0) if ker>=.35 else 0
    corr=1. if coin=='BTC' else None;btc_regime=None
    if coin=='BTC':
        btc_regime=1 if closes[-1]>tech['ema50'] and mom>0 else -1 if closes[-1]<tech['ema50'] and mom<0 else 0
    elif btc_rows:
        # BTC must pass the same freshness/gap validation before it can confirm an altcoin.
        try:
            btc_research.analyze(btc_rows,now)
            bf=four_hour(btc_rows,now);bc=[r['close'] for r in bf]
            if bf[-1]['time']==four[-1]['time']:
                corr=correlation(four,bf);bm=bc[-1]/bc[-4]-1;be=btc_research.ema(bc,50)
                btc_regime=1 if bc[-1]>be and bm>0 else -1 if bc[-1]<be and bm<0 else 0
        except ValueError:
            pass  # Own-market context remains usable; no BTC confirmation is invented.
    confirmed=raw if coin=='BTC' or (corr is not None and corr>=.65 and raw==btc_regime) else 0
    stop_distance=2*atr4;stop_pct=stop_distance/last
    reasons=[]
    if abs(mom)<.025:reasons.append('Momentum 12H belum mencapai ±2,5%')
    if ker<.35:reasons.append('KER20 di bawah 0,35')
    if coin!='BTC' and (corr is None or corr<.65):reasons.append('Korelasi BTC belum lolos 0,65 atau riwayat belum cukup')
    if coin!='BTC' and raw and raw!=btc_regime:reasons.append('Arah belum sejalan dengan tren BTC')
    if stop_pct>.025:reasons.append('Jarak SL 2 ATR melebihi 2,5%')
    eligible=bool(confirmed and stop_pct<=.025)
    if eligible:state='Kandidat LONG' if confirmed>0 else 'Kandidat SHORT'
    else:state='Tunggu konfirmasi'
    volumes=[float(r['volume']) for r in closed[-21:] if r.get('volume') is not None]
    volume_ratio=None
    if len(volumes)==21 and all(math.isfinite(v) and v>=0 for v in volumes) and sum(volumes[:-1])>0:
        volume_ratio=volumes[-1]/(sum(volumes[:-1])/20)
    plans=[]
    for side,label in ((1,'LONG'),(-1,'SHORT')):
        take=last+side*10*stop_distance;stop=last-side*stop_distance
        if take>0 and stop>0:
            plans.append(dict(side=label,entry=last,sl=stop,tp=take,risk_pct=100*stop_pct,
                              rr=10,selected=eligible and confirmed==side))
    return dict(coin=coin,technical=tech,state=state,eligible=eligible,side=confirmed,
        reasons=reasons,atr4=atr4,momentum12=100*mom,ker=ker,correlation=corr,btc_regime=btc_regime,
        rsi=rsi,volume_ratio=volume_ratio,plans=plans,
        scenarios=[dict(name='Naik / breakout',trigger=resistance,invalidation=resistance,
                        target1=resistance+tech['atr'],target2=resistance+2*tech['atr']),
                   dict(name='Turun / breakdown',trigger=support,invalidation=support,
                        target1=max(0.,support-tech['atr']),target2=max(0.,support-2*tech['atr'])),
                   dict(name='Rentang / sideways',low=support,high=resistance)],
        provenance={'venue':'BingX','market':'USDT perpetual','closed_at':tech['closed_at'],
                    'four_closed_at':tech['four_closed_at'],'hours':len(closed),'fetched':now})


def get_candles(coin):
    response=requests.get(HOST+'/openApi/swap/v3/quote/klines',params={'symbol':coin+'-USDT','interval':'1h','limit':1000},timeout=12)
    response.raise_for_status();payload=response.json()
    if str(payload.get('code'))!='0':raise ValueError('Public candle rejected')
    rows=[]
    for r in payload['data']:
        row=dict(time=int(r['time'])/1000,**{k:float(r[k]) for k in ('open','high','low','close')})
        if r.get('volume') is not None:row['volume']=float(r['volume'])
        rows.append(row)
    return rows


def get_funding(coin,now=None):
    now=time.time() if now is None else now
    response=requests.get(HOST+'/openApi/swap/v2/quote/premiumIndex',params={'symbol':coin+'-USDT'},timeout=10)
    response.raise_for_status();payload=response.json()
    if str(payload.get('code'))!='0':raise ValueError('Public premium index rejected')
    d=payload['data']
    if d.get('symbol')!=coin+'-USDT':raise ValueError('Wrong premium-index symbol')
    mark=float(d['markPrice']);index=float(d['indexPrice']);rate=float(d['lastFundingRate'])
    updated=float(d['updateTime'])/1000
    if not all(math.isfinite(v) for v in (mark,index,rate,updated)) or mark<=0 or index<=0:
        raise ValueError('Invalid public prices')
    interval=float(d['fundingIntervalHours']) if d.get('fundingIntervalHours') is not None else None
    if interval is not None and (not math.isfinite(interval) or interval<=0):raise ValueError('Invalid funding interval')
    # updateTime belongs to the periodically updated rate. Do not treat it as
    # a tick timestamp for markPrice; record our observation time separately.
    if updated>now+60 or now-updated>max(900,(interval or 0)*HOUR+900):raise ValueError('Funding rate is stale')
    return dict(mark=mark,index=index,rate_pct=rate*100,next_at=int(d['nextFundingTime'])/1000,
                interval_hours=interval,updated_at=updated,observed_at=now,premium_pct=100*(mark/index-1),source='BingX')


def fetch():
    result=dict(reports={},funding={},errors={},sentiment=None,fetched=time.time())
    candles={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={('candles',c):pool.submit(get_candles,c) for c in COINS}
        tasks.update({('funding',c):pool.submit(get_funding,c) for c in COINS})
        tasks[('sentiment','all')]=pool.submit(btc_research.fetch_sentiment)
        for (kind,coin),future in tasks.items():
            try:
                value=future.result()
                if kind=='candles':candles[coin]=value
                elif kind=='funding':result['funding'][coin]=value
                else:result['sentiment']=value
            except Exception as error:result['errors'][kind+'/'+coin]=type(error).__name__
    for coin,rows in candles.items():
        try:result['reports'][coin]=report(coin,rows,candles.get('BTC'),time.time())
        except Exception as error:result['errors']['report/'+coin]=type(error).__name__
    return result
