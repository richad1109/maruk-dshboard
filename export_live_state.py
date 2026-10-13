import os
import sys
import time
import json
import socket
import subprocess
import requests
import ccxt
from concurrent.futures import ThreadPoolExecutor

if not hasattr(socket, '_orig_sys_getaddrinfo'):
    socket._orig_sys_getaddrinfo = socket.getaddrinfo

_dns_cache = {}
def doh_resolve(host):
    if host in _dns_cache:
        return _dns_cache[host]
    for url in ['https://dns.google/resolve', 'https://1.1.1.1/dns-query']:
        try:
            r = requests.get(url, params={'name': host, 'type': 'A'}, headers={'accept': 'application/dns-json'}, timeout=2.5)
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
            for ip in ips:
                try:
                    return socket._orig_sys_getaddrinfo(ip, port, family, type, proto, flags)
                except Exception:
                    pass
    return socket._orig_sys_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = custom_getaddrinfo

def fetch_fast_public_marks():
    marks = {}
    hdr = {"User-Agent": "Mozilla/5.0"}
    # 1. Gate.io Spot
    for coin in ["BTC", "ETH", "ADA", "XRP", "AVAX", "LINK"]:
        pair = f"{coin}_USDT"
        try:
            r = requests.get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair}", headers=hdr, timeout=2.5)
            if r.status_code == 200 and r.json():
                marks[f"{coin}/USDT"] = float(r.json()[0].get("last") or 0.0)
        except Exception:
            pass
    # 2. BingX Swap
    for coin in ["BTC", "ETH", "ADA", "XRP", "AVAX", "LINK"]:
        sym = f"{coin}-USDT"
        try:
            r = requests.get(f"https://open-api.bingx.com/openApi/swap/v2/quote/ticker?symbol={sym}", headers=hdr, timeout=2.5)
            if r.status_code == 200:
                lp = float(r.json().get("data", {}).get("lastPrice") or 0.0)
                if lp > 0:
                    marks[f"{coin}/USDT"] = lp
        except Exception:
            pass
    return marks

def generate_live_state():
    cfg_path = os.path.join(os.path.dirname(__file__), "accounts_config.json")
    with open(cfg_path, "r") as f:
        cfg = json.load(f)

    out_file = os.path.join(os.path.dirname(__file__), "live_bot_state.json")
    prev_state = {}
    if os.path.exists(out_file):
        try:
            with open(out_file, "r") as pf:
                prev_state = json.load(pf)
        except Exception:
            prev_state = {}

    known_marks = fetch_fast_public_marks()
    full_state = {}

    for acc_key, profile in cfg.items():
        tot_bal = 0.0
        tot_pnl = 0.0
        pos_list = []
        ex_details = {}
        prev_acc = prev_state.get(acc_key, {})
        prev_ex = prev_acc.get("ex_details", {})
        prev_pos = prev_acc.get("pos_list", [])

        for name in ["Bitget", "BingX", "MEXC", "Bybit", "Gate.io"]:
            creds = profile.get(name, {})
            api_k = creds.get("apiKey", "").strip()
            sec_k = creds.get("secret", "").strip()
            pass_k = creds.get("password", "").strip()

            if not api_k or not sec_k:
                ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'}
                continue

            try:
                if name == "Bitget":
                    ex = ccxt.bitget({'apiKey': api_k, 'secret': sec_k, 'password': pass_k, 'timeout': 6000})
                    b_data = ex.privateMixGetV2MixAccountAccounts({'productType': 'USDT-FUTURES'}).get('data', [])
                    p_data = ex.privateMixGetV2MixPositionAllPosition({'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'}).get('data', [])
                    usdt_row = b_data[0] if b_data else {}
                    usdt_total = float(usdt_row.get('usdtEquity') or usdt_row.get('accountEquity') or 0.0)
                    usdt_free = float(usdt_row.get('available') or 0.0)
                    tot_bal += usdt_total
                    ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}

                    for p in p_data:
                        total_sz = abs(float(p.get('total') or 0.0))
                        if total_sz > 0:
                            raw_sym = p.get('symbol', '').replace('USDT', '')
                            pair_key = f"{raw_sym}/USDT"
                            side = str(p.get('holdSide', 'LONG')).upper()
                            entry = float(p.get('openPriceAvg') or 0.0)
                            mark = float(p.get('markPrice') or known_marks.get(pair_key) or entry)
                            if mark > 0:
                                known_marks[pair_key] = mark
                            margin = float(p.get('marginSize') or 1.0)
                            lev = int(float(p.get('leverage') or 28))
                            notional = total_sz * mark if mark > 0 else margin * lev
                            pnl = float(p.get('unrealizedPL') or 0.0)
                            roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                            tot_pnl += pnl
                            pos_list.append({
                                'exchange': name, 'symbol': pair_key, 'side': side,
                                'entry': entry, 'mark': mark, 'margin': margin,
                                'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                            })

                elif name == "BingX":
                    ex = ccxt.bingx({'apiKey': api_k, 'secret': sec_k, 'timeout': 6000})
                    b_data = ex.swapV2PrivateGetUserBalance().get('data', {}).get('balance', {})
                    p_data = ex.swapV2PrivateGetUserPositions().get('data', [])
                    usdt_total = float(b_data.get('equity') or b_data.get('balance') or 0.0)
                    usdt_free = float(b_data.get('availableMargin') or 0.0)
                    tot_bal += usdt_total
                    ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}

                    for p in p_data:
                        amt = abs(float(p.get('positionAmt') or 0.0))
                        if amt > 0:
                            pair_key = str(p.get('symbol', '')).replace('-', '/')
                            side = str(p.get('positionSide', 'LONG')).upper()
                            entry = float(p.get('avgPrice') or 0.0)
                            mark = float(p.get('markPrice') or known_marks.get(pair_key) or entry)
                            if mark > 0:
                                known_marks[pair_key] = mark
                            margin = float(p.get('initialMargin') or p.get('margin') or 1.0)
                            lev = int(float(p.get('leverage') or 28))
                            notional = float(p.get('positionValue') or (amt * mark))
                            pnl = float(p.get('unrealizedProfit') or 0.0)
                            roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                            tot_pnl += pnl
                            pos_list.append({
                                'exchange': name, 'symbol': pair_key, 'side': side,
                                'entry': entry, 'mark': mark, 'margin': margin,
                                'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                            })

                elif name == "MEXC":
                    ex = ccxt.mexc({'apiKey': api_k, 'secret': sec_k, 'timeout': 6000})
                    b_data = ex.contractPrivateGetAccountAssets().get('data', [])
                    p_data = ex.contractPrivateGetPositionOpenPositions().get('data', [])
                    usdt_row = next((x for x in b_data if x.get('currency') == 'USDT'), {})
                    usdt_total = float(usdt_row.get('equity') or usdt_row.get('cashBalance') or 0.0)
                    usdt_free = float(usdt_row.get('availableBalance') or 0.0)
                    tot_bal += usdt_total
                    ex_details[name] = {'total': round(usdt_total, 2), 'free': round(usdt_free, 2), 'status': 'ONLINE'}

                    for p in p_data:
                        vol = abs(float(p.get('holdVol') or 0.0))
                        if vol > 0:
                            pair_key = str(p.get('symbol', '')).replace('_', '/')
                            side = "LONG" if int(p.get('positionType', 1)) == 1 else "SHORT"
                            entry = float(p.get('openAvgPrice') or p.get('holdAvgPrice') or 0.0)
                            mark = float(known_marks.get(pair_key) or entry)
                            c_size = 0.0001 if "BTC" in pair_key else (0.01 if "ETH" in pair_key else 1.0)
                            notional = vol * c_size * entry
                            margin = float(p.get('im') or p.get('oim') or 1.0)
                            lev = int(float(p.get('leverage') or 28))
                            pnl = float(p.get('unRealizedPnl') or 0.0)
                            if abs(pnl) <= 0.0001 and entry > 0 and mark > 0:
                                diff = (mark - entry) / entry if side == "LONG" else (entry - mark) / entry
                                pnl = notional * diff
                            roe = (pnl / margin * 100.0) if margin > 0 else 0.0
                            tot_pnl += pnl
                            pos_list.append({
                                'exchange': name, 'symbol': pair_key, 'side': side,
                                'entry': entry, 'mark': mark, 'margin': margin,
                                'notional': notional, 'pnl': pnl, 'roe': roe, 'leverage': lev
                            })

                elif name in ["Bybit", "Gate.io"]:
                    ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'ONLINE'}
            except Exception:
                if name in prev_ex:
                    ex_details[name] = prev_ex[name]
                    tot_bal += float(prev_ex[name].get("total", 0.0))
                    for old_p in prev_pos:
                        if old_p.get("exchange") == name:
                            p_copy = dict(old_p)
                            sym = p_copy.get("symbol", "")
                            mark = float(known_marks.get(sym) or p_copy.get("mark") or p_copy.get("entry", 0.0))
                            p_copy["mark"] = mark
                            tot_pnl += float(p_copy.get("pnl", 0.0))
                            pos_list.append(p_copy)
                else:
                    ex_details[name] = {'total': 0.0, 'free': 0.0, 'status': 'ONLINE'}

        ordered_ex = {}
        for k_ex in ["Bitget", "MEXC", "BingX", "Bybit", "Gate.io"]:
            ordered_ex[k_ex] = ex_details.get(k_ex, {'total': 0.0, 'free': 0.0, 'status': 'STANDBY'})

        full_state[acc_key] = {
            'total_bal': round(tot_bal, 2),
            'total_pnl': round(tot_pnl, 2),
            'pos_list': pos_list,
            'ex_details': ordered_ex,
            'updated_at': time.strftime("%Y-%m-%d %H:%M:%S")
        }

    with open(out_file, "w") as out:
        json.dump(full_state, out, indent=2)

    print(f"State generated successfully at {out_file}!")
    for k, v in full_state.items():
        print(f"[{k}] Bal: ${v['total_bal']} | PnL: ${v['total_pnl']} | Pos: {len(v['pos_list'])} | Marks: {known_marks}")
    return full_state

def git_push_state():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        subprocess.run(["git", "add", "live_bot_state.json"], cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        res = subprocess.run(["git", "commit", "-m", f"chore: live state sync {time.strftime('%H:%M:%S')}"], cwd=repo_dir, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12, env=env)
            print(f"[{time.strftime('%H:%M:%S')}] Pushed updated live_bot_state.json to GitHub!")
    except Exception as e:
        print(f"Git push error: {e}")

if __name__ == "__main__":
    generate_live_state()
    if "--push" in sys.argv:
        git_push_state()
