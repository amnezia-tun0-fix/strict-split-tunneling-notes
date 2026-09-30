#!/usr/bin/env python3
"""UDP traceroute without root, for an app inside the VPN (G11: plain traceroute).

Usage (in Termux):  python udp_traceroute.py <label> [dst=1.1.1.1] [--hops 12] [--tries 2]

Sends UDP probes to dst:33434+n with TTL 1..hops, as classic traceroute does, one
socket per probe (so a new flow for the filter each time, like traceroute's changing
destination port). The answers are ICMP errors, which an unprivileged socket reads
from its error queue (IP_RECVERR): time exceeded from routers on the way, port
unreachable from the destination. The ICMP comes in through the tunnel and the
filter judges only what goes out, so this should work with strict mode on.
"""
import argparse
import socket
import struct
import time

ap = argparse.ArgumentParser()
ap.add_argument("label")
ap.add_argument("dst", nargs="?", default="1.1.1.1")
ap.add_argument("--hops", type=int, default=12)
ap.add_argument("--tries", type=int, default=2)
ap.add_argument("--wait", type=float, default=2.0)
a = ap.parse_args()

IP_RECVERR = 11
MSG_ERRQUEUE = 0x2000
SO_EE_ORIGIN_ICMP = 2
ICMP_NAMES = {(11, 0): "time-exceeded", (3, 3): "port-unreachable"}

print(f"udp_traceroute label={a.label} dst={a.dst} hops={a.hops} tries={a.tries}")
reached = False
answered = 0
for ttl in range(1, a.hops + 1):
    line = []
    for t in range(a.tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        s.setsockopt(socket.IPPROTO_IP, IP_RECVERR, 1)
        t0 = time.monotonic()
        s.sendto(b"x" * 32, (a.dst, 33434 + ttl * a.tries + t))
        got = None
        while time.monotonic() - t0 < a.wait:
            try:
                s.settimeout(0.05)
                _, anc, _, _ = s.recvmsg(512, 512, MSG_ERRQUEUE)
            except (socket.timeout, BlockingIOError):
                continue
            except OSError:
                # the error is also reported on a plain recv; the queue still holds it
                continue
            for level, typ, data in anc:
                if level == socket.IPPROTO_IP and typ == IP_RECVERR and len(data) >= 16:
                    errno_, origin, itype, icode = struct.unpack("=IBBB", data[:7])
                    if origin == SO_EE_ORIGIN_ICMP:
                        off = data[16:]  # sockaddr_in of the offender
                        ip = socket.inet_ntoa(off[4:8]) if len(off) >= 8 else "?"
                        got = (ip, itype, icode, (time.monotonic() - t0) * 1000)
            if got:
                break
        s.close()
        if got:
            answered += 1
            ip, itype, icode, ms = got
            line.append(f"{ip} {ICMP_NAMES.get((itype, icode), f'icmp {itype}/{icode}')} {ms:.0f}ms")
            if (itype, icode) == (3, 3):
                reached = True
        else:
            line.append("*")
    print(f"{ttl:2d}  " + "  |  ".join(line), flush=True)
    if reached:
        break
print(f"answered {answered} probes, destination {'reached' if reached else 'not reached'}")
