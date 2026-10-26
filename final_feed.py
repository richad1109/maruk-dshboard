"""Read encrypted Bot Final telemetry. No order APIs; no credentials in URL."""
import base64
import hashlib
import json
import time
import requests
from cryptography.fernet import Fernet

URL='https://raw.githubusercontent.com/richad1109/bot-final-telemetry/monitor/monitor.enc'

def decrypt(content,accounts):
    c=accounts['akun_1']['Bitget']
    key=base64.urlsafe_b64encode(hashlib.sha256(('bot-final-monitor-v1|'+c['apiKey']+'|'+c['secret']).encode()).digest())
    result=json.loads(Fernet(key).decrypt(content))
    if result.get('schema')!='sakti-monitor-v1' or result.get('version') not in ('bot-final-btc-h96-t3-r1','bot-final-bds-h96-t3-r2'):
        raise ValueError('Telemetry schema/version mismatch')
    if not isinstance(result.get('wallets'),dict) or float(result.get('updated_at',0))>time.time()*1000+60000:
        raise ValueError('Invalid heartbeat')
    return result

def fetch(accounts):
    if not accounts.get('akun_1',{}).get('Bitget',{}).get('secret'):return {}
    response=requests.get(URL,params={'slot':int(time.time()//60)},timeout=8)
    response.raise_for_status()
    if len(response.content)>2_000_000:raise ValueError('Telemetry too large')
    return decrypt(response.content,accounts)
