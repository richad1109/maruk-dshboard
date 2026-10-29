"""Process-local DoH for official API hosts; default is public checks only.

No API credentials are sent to resolvers. HTTPS URLs, Host/SNI, certificate
verification and exchange authentication are unchanged. No system settings.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import runpy
import socket
import sys
import threading
import time
import requests

HOSTS = frozenset({"api.bitget.com", "api.mexc.com", "contract.mexc.com", "open-api.bingx.com"})
RESOLVERS = ("https://dns.google/resolve", "https://cloudflare-dns.com/dns-query")
ENDPOINTS = {
    "bitget": "https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES",
    "mexc": "https://api.mexc.com/api/v1/contract/detail",
    "bingx": "https://open-api.bingx.com/openApi/swap/v2/quote/contracts",
}
_original = socket.getaddrinfo
_cache = {}
_lock = threading.Lock()


def resolve(host):
    with _lock:
        cached = _cache.get(host)
        if cached and cached[0] > time.monotonic():
            return cached[1]
    for endpoint in RESOLVERS:
        try:
            # Independent request: no exchange session, API keys or signatures.
            response = requests.get(endpoint,
                params={"name": host, "type": "A", "edns_client_subnet": "0.0.0.0/0"},
                headers={"Accept": "application/dns-json"}, timeout=(4, 6))
            response.raise_for_status()
            data = response.json()
            if data.get("Status") != 0:
                continue
            answers, ttls = [], []
            for row in data.get("Answer", []):
                if row.get("type") != 1:
                    continue
                ip = ipaddress.ip_address(row["data"])
                if ip.version == 4 and ip.is_global:
                    answers.append(str(ip))
                    ttls.append(max(1, int(row.get("TTL", 60))))
            if answers:
                answers = list(dict.fromkeys(answers))
                with _lock:
                    _cache[host] = (time.monotonic()+min(300, min(ttls)), answers)
                return answers
        except (requests.RequestException, ValueError, KeyError, TypeError):
            continue
    # Fallback ke DNS sistem jika DoH publik terblokir/gagal
    try:
        sys_res = _original(host, 0, socket.AF_INET, socket.SOCK_STREAM)
        ips = list(dict.fromkeys([r[4][0] for r in sys_res if r[4]]))
        if ips:
            with _lock:
                _cache[host] = (time.monotonic() + 120, ips)
            return ips
    except Exception:
        pass
    # Hardcoded resilient fallback IPs for Indonesian ISPs
    hardcoded = {
        "api.mexc.com": ["195.35.23.222", "185.209.176.10", "149.28.140.237"],
        "contract.mexc.com": ["195.35.23.222", "185.209.176.10", "149.28.140.237"],
        "api.bitget.com": ["13.224.238.20", "13.224.238.106"],
        "open-api.bingx.com": ["18.67.76.51", "18.67.76.103"]
    }
    if host in hardcoded:
        return hardcoded[host]
    raise socket.gaierror(socket.EAI_AGAIN, "DNS terenkripsi gagal untuk host API resmi")


def api_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    name = host.decode("ascii") if isinstance(host, bytes) else host
    name = name.lower().rstrip(".") if isinstance(name, str) else name
    if name not in HOSTS:
        return _original(host, port, family, type, proto, flags)
    if family not in (0, socket.AF_UNSPEC, socket.AF_INET):
        raise socket.gaierror(socket.EAI_FAMILY, "Resolver API ini memakai IPv4")
    rows = []
    for ip in resolve(name):
        rows.extend(_original(ip, port, socket.AF_INET, type, proto, flags))
    return rows


def install_dns():
    if socket.getaddrinfo is api_getaddrinfo:
        return
    if socket.getaddrinfo is not _original:
        raise RuntimeError("Resolver lain sudah aktif; jangan menumpuk patch DNS")
    socket.getaddrinfo = api_getaddrinfo


def check_public():
    good = True
    for venue, url in ENDPOINTS.items():
        try:
            response = requests.get(url, timeout=(6, 8))
            response.raise_for_status()
            data = response.json()
            ok = str(data.get("code")) in {"0", "00000"} and data.get("success") is not False
            print(json.dumps({"bursa":venue,"dns":"DoH","http":response.status_code,
                              "status":"OK" if ok else "API_MENOLAK"}), flush=True)
            good = good and ok
        except Exception as error:
            print(json.dumps({"bursa":venue,"dns":"DoH","status":"GAGAL",
                              "jenis":type(error).__name__}), flush=True)
            good = False
    return good


def main():
    parser = argparse.ArgumentParser(description="Cek jaringan publik Bot Sakti; tanpa API key/transaksi.")
    parser.parse_args()
    install_dns()
    return 0 if check_public() else 2


if __name__ == "__main__":
    raise SystemExit(main())
