import os
import sys
import time
import json
import socket
import requests
import ccxt

if not hasattr(socket, '_orig_sys_getaddrinfo'):
    socket._orig_sys_getaddrinfo = socket.getaddrinfo

_dns_cache = {}
def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        r = requests.get('https://1.1.1.1/dns-query', params={'name': host, 'type': 'A'}, headers={'accept': 'application/dns-json'}, timeout=3)
        ips = [ans.get('data') for ans in r.json().get('Answer', []) if ans.get('type') == 1]
        if ips:
            _dns_cache[host] = ips
            return ips
    except Exception:
        pass
    return []

def custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    targets = ['bybit', 'bytick', 'gateio', 'gate.io', 'bingx', 'bitget', 'mexc']
    if any(t in host.lower() for t in targets):
        ips = doh_resolve(host)
        if ips:
            res = []
            for ip in ips:
                try:
                    res.extend(socket._orig_sys_getaddrinfo(ip, port, family, type, proto, flags))
                except Exception:
                    pass
            if res:
                return res
    return socket._orig_sys_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

def generate_live_state():
    cfg_path = os.path.join(os.path.dirname(__file__), "accounts_config.json")
    with open(cfg_path, "r") as f:
        cfg = json.load(f)

    full_state = {}
    cfg_base = {'options': {'defaultType': 'swap'}, 'enableRateLimit': True, 'timeout': 10000}

    for acc_key, profile in cfg.items():
        tot_bal = 0.0
        tot_pnl = 0.0
        pos_list = []
        ex_details = {}

        ex_names = ["Bitget", "MEXC", "BingX", "Bybit", "Gate.io"]
        for name in ex_names:
            creds = profile.get(name, {})
            api_k = creds.get("apiKey", "").strip()
            sec_k = creds.get("secret", "").strip()
            pass_k = creds.get("password", "").strip()

            if not api_k or not sec_k:
                ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'}
                continue

            usdt_total = 0.0
            usdt_free = 0.0
            status_str = "ONLINE"
            ex = None
            raw_pos = []

            try:
                if name == "Bitget":
                    ex = ccxt.bitget({'apiKey': api_k, 'secret': sec_k, 'password': pass_k, **cfg_base})
                    ex.has['fetchCurrencies'] = False
                    bal = ex.fetch_balance(params={'type': 'swap'})
                    usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or (bal.get('total', {}) or {}).get('USDT', 0.0) or 0.0)
                    usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                elif name == "MEXC":
                    ex = ccxt.mexc({'apiKey': api_k, 'secret': sec_k, **cfg_base})
                    ex.has['fetchCurrencies'] = False
                    bal = ex.fetch_balance(params={'type': 'swap'})
                    usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or (bal.get('total', {}) or {}).get('USDT', 0.0) or 0.0)
                    usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                elif name == "BingX":
                    ex = ccxt.bingx({'apiKey': api_k, 'secret': sec_k, **cfg_base})
                    ex.has['fetchCurrencies'] = False
                    bal = ex.fetch_balance({'type': 'swap'})
                    usdt_total = float(bal.get('USDT', {}).get('total', 0.0) or 0.0)
                    usdt_free = float(bal.get('USDT', {}).get('free', 0.0) or usdt_total)
                elif name == "Bybit":
                    ex = ccxt.bybit({'apiKey': api_k, 'secret': sec_k, **cfg_base})
                    ex.has['fetchCurrencies'] = False
                    bal = ex.fetch_balance({'type': 'linear'})
                    usdt_total = float((bal.get('total', {}) or {}).get('USDT', 0.0) or 0.0)
                    usdt_free = float((bal.get('free', {}) or {}).get('USDT', 0.0) or usdt_total)
                elif name == "Gate.io":
                    ex = ccxt.gate({'apiKey': api_k, 'secret': sec_k, **cfg_base})
                    ex.has['fetchCurrencies'] = False
                    bal = ex.fetch_balance(params={'type': 'swap', 'settle': 'usdt'})
                    usdt_total = float((bal.get('total', {}) or {}).get('USDT', 0.0) or 0.0)
                    usdt_free = float((bal.get('free', {}) or {}).get('USDT', 0.0) or usdt_total)
            except Exception as e_b:
                status_str = f"ERR: {str(e_b)[:25]}"

            tot_bal += usdt_total
            ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': status_str}

            # Fetch positions
            if ex and not status_str.startswith("ERR"):
                try:
                    if name == "Bitget":
                        raw_pos = ex.fetch_positions(params={'productType': 'USDT-FUTURES'})
                    elif name == "MEXC":
                        raw_pos = ex.fetch_positions()
                    elif name == "BingX":
                        raw_pos = ex.fetch_positions()
                    elif name == "Bybit":
                        raw_pos = ex.fetch_positions(params={'settle': 'USDT'})
                    elif name == "Gate.io":
                        raw_pos = ex.fetch_positions(params={'settle': 'usdt'})
                except Exception:
                    raw_pos = []

            for p in raw_pos:
                contracts = abs(float(p.get('contracts') or p.get('amount') or (p.get('info', {}).get('holdVol') if isinstance(p.get('info'), dict) else 0) or 0.0))
                if contracts > 0:
                    sym = p.get('symbol', 'UNKNOWN')
                    clean_sym = sym.replace(':USDT', '').replace('/USDT', '')
                    side = str(p.get('side', '')).upper()
                    entry = float(p.get('entryPrice') or p.get('info', {}).get('openAvgPrice') or p.get('info', {}).get('avgPrice') or 0.0)
                    mark = float(p.get('markPrice') or p.get('info', {}).get('fairPrice') or entry or 0.0)
                    lev = float(p.get('leverage') or 28)

                    c_size = float(p.get('contractSize') or (p.get('info', {}).get('contractSize') if isinstance(p.get('info'), dict) else 1.0) or 1.0)
                    if name == 'MEXC':
                        if 'BTC' in sym: c_size = 0.0001
                        elif 'ETH' in sym: c_size = 0.01

                    real_notional = float(p.get('notional') or (contracts * c_size * entry if entry > 0 else 0.0))
                    margin = float(p.get('initialMargin') or p.get('collateral') or (p.get('info', {}).get('initialMargin') if isinstance(p.get('info'), dict) else 0) or 0.0)
                    if margin <= 0 and real_notional > 0 and lev > 0:
                        margin = real_notional / lev
                    if margin <= 0: margin = 1.0

                    pnl = float(p.get('unrealizedPnl') or (p.get('info', {}).get('unrealizedProfit') if isinstance(p.get('info'), dict) else 0) or 0.0)
                    if abs(pnl) <= 0.0001 and entry > 0 and mark > 0 and real_notional > 0:
                        diff = (mark - entry)/entry if side == 'LONG' else (entry - mark)/entry
                        pnl = real_notional * diff

                    roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                    tot_pnl += pnl

                    pos_list.append({
                        'exchange': name,
                        'symbol': clean_sym + '/USDT',
                        'side': side,
                        'entry': entry,
                        'mark': mark,
                        'margin': margin,
                        'notional': real_notional,
                        'pnl': pnl,
                        'roe': roe,
                        'leverage': int(lev)
                    })

        full_state[acc_key] = {
            'total_bal': round(tot_bal, 2),
            'total_pnl': round(tot_pnl, 2),
            'pos_list': pos_list,
            'ex_details': ex_details,
            'updated_at': time.strftime("%Y-%m-%d %H:%M:%S")
        }

    out_file = os.path.join(os.path.dirname(__file__), "live_bot_state.json")
    with open(out_file, "w") as out:
        json.dump(full_state, out, indent=2)

    print(f"State generated successfully at {out_file}!")
    for k, v in full_state.items():
        print(f"[{k}] Bal: ${v['total_bal']} | PnL: ${v['total_pnl']} | Pos: {len(v['pos_list'])} | Details: {v['ex_details']}")

if __name__ == "__main__":
    generate_live_state()
