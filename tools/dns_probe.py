#!/usr/bin/env python3
"""E5 probe: does the system resolver work for an app inside the tunnel?

Usage (in Termux):  python dns_probe.py <label> [server_ip]
Run as an app that IS routed through the VPN (include mode, app in the list).
Each lookup is a fresh name (<random>.1.2.3.4.nip.io -> 1.2.3.4), so no cache can
answer it: a pass means a real query left the device through the system resolver,
which is where Private DNS applies. Writes /sdcard/Download/e5dns_<label>.txt.
"""
import datetime
import os
import socket
import sys
import time

N = 5
label = sys.argv[1] if len(sys.argv) > 1 else "run"
server_ip = sys.argv[2] if len(sys.argv) > 2 else None
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


def lookup(name):
    t = time.monotonic()
    try:
        ip = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        res = "OK " + ip if ip == "1.2.3.4" else "WRONG " + ip
    except Exception as e:
        res = f"FAIL {type(e).__name__}: {e}"
    return res, time.monotonic() - t


def public_ip():
    try:
        ip = socket.getaddrinfo("api.ipify.org", 80, socket.AF_INET)[0][4][0]
        s = socket.create_connection((ip, 80), timeout=8)
        s.sendall(b"GET / HTTP/1.1\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n")
        data = b""
        while chunk := s.recv(4096):
            data += chunk
        s.close()
        return data.split(b"\r\n\r\n", 1)[-1].decode().strip()
    except Exception as e:
        return f"FAIL {type(e).__name__}: {e}"


log(f"# dns_probe {label} {datetime.datetime.now().isoformat(timespec='seconds')}")
ok = 0
for i in range(N):
    name = f"{os.urandom(4).hex()}.1.2.3.4.nip.io"
    res, dt = lookup(name)
    ok += res.startswith("OK")
    log(f"{name:40} {res:30} {dt:5.2f}s")
ip = public_ip()
tag = " (SERVER)" if server_ip and ip == server_ip else ""
log(f"public ip: {ip}{tag}")
log(f"RESULT {label}: dns {ok}/{N}, ip {ip}{tag}")

with open(f"/sdcard/Download/e5dns_{label}.txt", "w") as f:
    f.write("\n".join(lines) + "\n")
