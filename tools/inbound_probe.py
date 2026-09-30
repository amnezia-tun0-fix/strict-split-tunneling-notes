#!/usr/bin/env python3
"""Inbound TCP and ICMP through the tunnel, towards the phone (SYN-ACK, kernel ICMP).

Two halves:
    python inbound_probe.py listen [--port 8080] [--secs 600]      # in Termux, a listed app
    python inbound_probe.py connect <label> <phone_tun_ip> [--port 8080] [-n 5]   # on the PC

The PC is another peer of the same AmneziaWG server, so it reaches the phone's
tunnel address directly. connect opens n TCP connections (3 s timeout each),
sends a line, and expects it echoed; then it pings the phone n times. A SYN
arriving through the tunnel is answered by the phone's kernel with a SYN-ACK,
and the filter judges that SYN-ACK like a new connection; an echo request is
answered with an echo reply, which the filter cannot attribute.
"""
import argparse
import datetime
import socket
import subprocess
import sys
import threading
import time

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["listen", "connect"])
ap.add_argument("rest", nargs="*")
ap.add_argument("--port", type=int, default=8080)
ap.add_argument("--secs", type=int, default=600)
ap.add_argument("-n", type=int, default=5)
a = ap.parse_args()


def serve(c):
    try:
        c.settimeout(5)
        d = c.recv(256)
        c.sendall(b"echo " + d)
    except OSError:
        pass
    finally:
        c.close()


if a.mode == "listen":
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", a.port))
    s.listen(16)
    s.settimeout(1)
    end = time.time() + a.secs
    print(f"listening on :{a.port} for {a.secs}s", flush=True)
    while time.time() < end:
        try:
            c, peer = s.accept()
        except socket.timeout:
            continue
        print(f"{datetime.datetime.now():%H:%M:%S} accepted {peer[0]}:{peer[1]}", flush=True)
        threading.Thread(target=serve, args=(c,), daemon=True).start()
    sys.exit(0)

label, ip = a.rest[0], a.rest[1]
ok = 0
lines = [f"inbound_probe label={label} {datetime.datetime.now():%Y-%m-%d %H:%M:%S} target={ip}:{a.port}"]
for i in range(a.n):
    t = time.monotonic()
    try:
        c = socket.create_connection((ip, a.port), timeout=3)
        c.settimeout(3)
        c.sendall(b"ping %d\n" % i)
        r = c.recv(64)
        c.close()
        dt = (time.monotonic() - t) * 1000
        good = r.startswith(b"echo ")
        ok += good
        lines.append(f"tcp {i}: {'OK' if good else 'BAD'} {dt:.0f} ms {r!r}")
    except OSError as e:
        lines.append(f"tcp {i}: FAIL {type(e).__name__} {e} after {(time.monotonic() - t) * 1000:.0f} ms")
lines.append(f"tcp ok {ok}/{a.n}")
ping = subprocess.run(["ping", "-n", str(a.n), "-w", "2000", ip], capture_output=True, text=True,
                      encoding="cp866", errors="replace")
got = sum(1 for l in ping.stdout.splitlines() if "TTL=" in l.upper())
lines.append(f"icmp echo replies {got}/{a.n}")
print("\n".join(lines))
