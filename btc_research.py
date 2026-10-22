"""Public market observations and transparent, uncalibrated technical scenarios."""
import math
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import requests

HOUR=3600


def ema(values, period):
    result=values[0]
    for value in values[1:]:result+=(value-result)*2/(period+1)
    return result


def wilder(values,period=14):
    result=sum(values[:period])/period
    for value in values[period:]:result=(result*(period-1)+value)/period
    return result


def analyze(rows,now=None):
    now=time.time() if now is None else now
    by_time={r['time']:r for r in rows if r['time']+HOUR<=now}
    rows=sorted(by_time.values(),key=lambda r:r['time'])
    if len(rows)<480:raise ValueError('Riwayat candle kurang dari 480 jam')
    if any(not math.isfinite(float(r[k])) or float(r[k])<=0 for r in rows for k in ('open','high','low','close')):
        raise ValueError('Harga candle tidak valid')
    if any(r['high']<max(r['open'],r['close'],r['low']) or r['low']>min(r['open'],r['close']) for r in rows):
        raise ValueError('OHLC tidak konsisten')
    if any(b['time']-a['time']!=HOUR for a,b in zip(rows,rows[1:])):
        raise ValueError('Riwayat candle berlubang')
    if now-(rows[-1]['time']+HOUR)>2*HOUR:raise ValueError('Candle terbaru sudah usang')
    groups=defaultdict(list)
    for row in rows:groups[int(row['time']//(4*HOUR))].append(row)
    four=[]
    for bucket,group in sorted(groups.items()):
        if len(group)==4 and group[0]['time']==bucket*4*HOUR:
            four.append(dict(time=group[0]['time'],open=group[0]['open'],high=max(r['high'] for r in group),low=min(r['low'] for r in group),close=group[-1]['close']))
    if len(four)<100:raise ValueError('Candle 4H lengkap belum mencukupi')
    c=[r['close'] for r in rows];f=[r['close'] for r in four]
    delta=[b-a for a,b in zip(c,c[1:])]
    up=wilder([max(d,0) for d in delta]);down=wilder([max(-d,0) for d in delta])
    rsi=100-100/(1+up/down) if down else (100 if up else 50)
    tr=[max(r['high']-r['low'],abs(r['high']-rows[i-1]['close']),abs(r['low']-rows[i-1]['close'])) for i,r in enumerate(rows) if i]
    atr=wilder(tr);e20=ema(f,20);e50=ema(f,50);e100=ema(f,100)
    distance=sum(abs(b-a) for a,b in zip(f[-21:],f[-20:]))
    ker=abs(f[-1]-f[-21])/distance if distance else 0
    # Prior 24 completed hours; current completed bar can actually break this range.
    low=min(r['low'] for r in rows[-25:-1]);high=max(r['high'] for r in rows[-25:-1])
    if f[-1]>e50 and e20>e100 and rsi>=50: bias='Condong naik'
    elif f[-1]<e50 and e20<e100 and rsi<50:bias='Condong turun'
    else:bias='Campuran / tunggu konfirmasi'
    return dict(close=c[-1],closed_at=rows[-1]['time']+HOUR,four_closed_at=four[-1]['time']+4*HOUR,
        ema20=e20,ema50=e50,ema100=e100,rsi=rsi,atr=atr,atr_pct=100*atr/c[-1],ker=ker,
        support=low,resistance=high,bias=bias,change24=100*(c[-1]/c[-25]-1),
        candles=rows[-168:],range_break='Atas' if c[-1]>high else 'Bawah' if c[-1]<low else 'Dalam rentang')


def fetch_candles():
    response=requests.get('https://open-api.bingx.com/openApi/swap/v3/quote/klines',params={'symbol':'BTC-USDT','interval':'1h','limit':1000},timeout=12)
    response.raise_for_status();payload=response.json()
    if str(payload.get('code'))!='0':raise ValueError('Bursa menolak candle publik')
    rows=[dict(time=int(r['time'])/1000,**{k:float(r[k]) for k in ('open','high','low','close')}) for r in payload['data']]
    return analyze(rows)


def fetch_sentiment():
    response=requests.get('https://api.alternative.me/fng/',params={'limit':8},timeout=8)
    response.raise_for_status();payload=response.json()
    if payload.get('metadata',{}).get('error'):raise ValueError('Sumber sentimen gagal')
    rows=[dict(value=int(r['value']),label=str(r['value_classification']),time=int(r['timestamp'])) for r in payload['data']]
    if not rows or any(not 0<=r['value']<=100 for r in rows):raise ValueError('Indeks sentimen tidak valid')
    rows.sort(key=lambda r:r['time'],reverse=True)
    return dict(latest=rows[0],history=rows,stale=time.time()-rows[0]['time']>48*HOUR)


def fetch():
    result={'technical':None,'sentiment':None,'technical_error':None,'sentiment_error':None,'fetched':time.time()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks={key:pool.submit(method) for key,method in [('technical',fetch_candles),('sentiment',fetch_sentiment)]}
        for key,future in tasks.items():
            try:result[key]=future.result()
            except Exception as error:result[key+'_error']=type(error).__name__
    return result
