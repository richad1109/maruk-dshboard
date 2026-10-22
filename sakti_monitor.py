"""Whitelisted Bot Sakti telemetry. Never read API keys or perform trading."""
from __future__ import annotations
import json
import math
import time
from pathlib import Path

MANUAL={'akun_1/bingx':{'BTC','ETH','TIA','ONDO','BR'},
        **{f'akun_{n}/bitget':{'XRP'} for n in (1,2,3)}}


def numeric(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None


def sanitize(state):
    """Allowlist output; private credentials/identity/order IDs never escape."""
    if not isinstance(state,dict) or not isinstance(state.get('wallets'),dict):
        raise ValueError('Bukan state Bot Sakti')
    result={'schema':'sakti-monitor-v1','version':str(state.get('version',''))[:100],
        'phase':str(state.get('phase','unknown'))[:30], 'live':bool(state.get('live',False)),
        'processed':numeric(state.get('processed')), 'updated_at':numeric(state.get('updated_at')),
        'wallets':{},'alerts':[]}
    for key,w in state['wallets'].items():
        if key not in {f'akun_{a}/{v}' for a in (1,2,3) for v in ('bitget','mexc','bingx')} or key=='akun_3/mexc' or not isinstance(w,dict):continue
        out={'trades':[],'positions':{},'pending':bool(w.get('pending'))}
        for t in w.get('trades',[]):
            if isinstance(t,dict) and numeric(t.get('net_pnl')) is not None:
                out['trades'].append({k:numeric(t.get(k)) for k in ['closed','net_pnl','net_R']})
        for symbol,p in w.get('positions',{}).items():
            if not isinstance(p,dict):continue
            symbol=str(symbol)[:40]
            out['positions'][symbol]={k:numeric(p.get(k)) for k in ['side','quantity','entry','stop','take','leverage','margin','entered']}
            if p.get('protection_warning'):
                result['alerts'].append(dict(wallet=key,symbol=symbol,reason=str(p['protection_warning'])[:180],sl=numeric(p.get('stop')),tp=numeric(p.get('take'))))
        result['wallets'][key]=out
    if state.get('schema')=='sakti-monitor-v1' and isinstance(state.get('alerts'),list):
        for alert in state['alerts']:
            if isinstance(alert,dict) and alert.get('wallet') in result['wallets']:
                result['alerts'].append(dict(wallet=alert['wallet'],symbol=str(alert.get('symbol',''))[:40],
                    reason=str(alert.get('reason',''))[:180],sl=numeric(alert.get('sl')),tp=numeric(alert.get('tp'))))
    for name in ['target_result','last_target_estimate','target_trigger']:
        obj=state.get(name)
        if isinstance(obj,dict):
            result[name]={k:numeric(obj.get(k)) for k in ['hour','net_profit','estimated_net_profit','closed','threshold'] if k in obj}
    return result


def metrics(state, now=None):
    when=time.time() if now is None else now
    wallets=state.get('wallets',{})
    trades=[t for w in wallets.values() for t in w.get('trades',[]) if numeric(t.get('net_pnl')) is not None]
    rows=[]
    for key,w in wallets.items():
        known=[t['net_R'] for t in w.get('trades',[]) if numeric(t.get('closed')) is not None and t['closed']/1000+3600<=when and numeric(t.get('net_R')) is not None]
        healthy=len(known)>=4 and sum(known[-8:])/len(known[-8:])>0
        rows.append(dict(wallet=key,scale=1. if healthy else .25,known=len(known),positions=len(w.get('positions',{})),pending=bool(w.get('pending'))))
    net=sum(t['net_pnl'] for t in trades) if wallets else None
    latest=state.get('last_target_estimate',{}).get('net_profit')
    return dict(realized=net,trades=len(trades),wins=sum(t['net_pnl']>0 for t in trades),
        win_rate=100*sum(t['net_pnl']>0 for t in trades)/len(trades) if trades else None,
        estimated=numeric(latest),wallets=rows,alerts=state.get('alerts',[]))


def main():
    import argparse
    p=argparse.ArgumentParser(description='Ekspor monitoring Bot Sakti tanpa key; tanpa transaksi.')
    p.add_argument('--state',default=str(Path.home()/'bot_sakti/sakti_live_state.json'))
    p.add_argument('--out',default=str(Path.home()/'storage/downloads/sakti_monitor.json'))
    args=p.parse_args();source=Path(args.state)
    state=json.loads(source.read_text(encoding='utf-8-sig'));state['updated_at']=source.stat().st_mtime*1000
    output=sanitize(state);target=Path(args.out);target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(output,separators=(',',':')),encoding='utf8')
    print('Snapshot monitoring dibuat: '+str(target)+' (tanpa API key, tanpa transaksi)')


if __name__=='__main__':main()
