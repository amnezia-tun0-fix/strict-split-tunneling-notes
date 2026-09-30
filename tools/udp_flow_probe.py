#!/usr/bin/env python3
"""Loss on one long-lived UDP flow through the tunnel (G20).

Usage (in Termux, an app inside the VPN):
    python udp_flow_probe.py <label> [--dur 60] [--burst 20] [--period 0.1]
                             [--dst 1.1.1.1] [--size 0]

One UDP socket, one 5-tuple for the whole run. Every period it sends a burst of
DNS queries back to back, each with its own id, and a reader thread records the
answers. The filter caches a UDP verdict for 10 s and does not refresh it on
hits, so every 10 s the flow is judged again; while it is, only 4 packets are
held. The report shows losses per second, so loss that comes in bursts about
10 s apart stands out from the network's own loss.

--size N pads each query with an EDNS(0) option (padding, or --opt CODE) to an
N-byte UDP payload. Above the tunnel MTU the kernel fragments the datagram (the fragment
test); 0 means no padding.

Prints a summary and writes it to /sdcard/Download/udpflow_<label>.txt.
"""
import argparse
import collections
import datetime
import socket
import struct
import threading
import time

ap = argparse.ArgumentParser()
ap.add_argument("label")
ap.add_argument("--dur", type=float, default=60)
ap.add_argument("--burst", type=int, default=20)
ap.add_argument("--period", type=float, default=0.1)
ap.add_argument("--dst", default="1.1.1.1")
ap.add_argument("--size", type=int, default=0)
ap.add_argument("--opt", type=int, default=12, help="EDNS option code used as filler (12 = padding)")
ap.add_argument("--grace", type=float, default=2.0)
ap.add_argument("--bind", default="", help="SO_BINDTODEVICE, e.g. tun0: an excluded app's bypass")
a = ap.parse_args()

QNAME = b"\x07example\x03com\x00"


def query(qid):
    hdr = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 1 if a.size else 0)
    q = hdr + QNAME + struct.pack(">HH", 1, 1)
    if a.size:
        # OPT RR: root name, type 41, udp size 1232, ext rcode/flags 0, rdata = padding option
        base = len(q) + 1 + 2 + 2 + 4 + 2 + 4
        pad = max(0, a.size - base)
        rdata = struct.pack(">HH", a.opt, pad) + b"\x00" * pad
        q += b"\x00" + struct.pack(">HHIH", 41, 1232, 0, len(rdata)) + rdata
    return q


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if a.bind:
    s.setsockopt(socket.SOL_SOCKET, 25, a.bind.encode() + bytes(1))  # SO_BINDTODEVICE
s.connect((a.dst, 53))
local = s.getsockname()
s.settimeout(0.5)

sent = {}  # seq -> send time (monotonic)
answered = {}  # seq -> rtt
stop = threading.Event()
oversize = 0


def reader():
    while not stop.is_set():
        try:
            d = s.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            continue
        if len(d) < 2:
            continue
        qid = struct.unpack(">H", d[:2])[0]
        t = time.monotonic()
        seq = qid  # ids are seq % 65536; runs stay below that
        if seq in sent and seq not in answered:
            answered[seq] = t - sent[seq]


th = threading.Thread(target=reader, daemon=True)
th.start()

t0 = time.monotonic()
wall0 = datetime.datetime.now()
seq = 0
send_err = 0
nxt = t0
while time.monotonic() - t0 < a.dur:
    for _ in range(a.burst):
        pkt = query(seq & 0xFFFF)
        sent[seq] = time.monotonic()
        try:
            s.send(pkt)
        except OSError:
            send_err += 1
        seq += 1
    nxt += a.period
    d = nxt - time.monotonic()
    if d > 0:
        time.sleep(d)
time.sleep(a.grace)
stop.set()
th.join(1)

per_sec = collections.OrderedDict()
for q, ts in sent.items():
    sec = int(ts - t0)
    tot, lost = per_sec.get(sec, (0, 0))
    per_sec[sec] = (tot + 1, lost + (q not in answered))

lost_total = sum(1 for q in sent if q not in answered)
rtts = sorted(answered.values())


def pct(p):
    return rtts[min(len(rtts) - 1, int(p * len(rtts)))] * 1000 if rtts else float("nan")


out = []
out.append(f"udp_flow_probe label={a.label} start={wall0:%Y-%m-%d %H:%M:%S} dst={a.dst}:53 "
           f"local_port={local[1]} bind={a.bind or '-'} dur={a.dur}s burst={a.burst} period={a.period}s size={len(query(0))}B")
out.append(f"sent={len(sent)} answered={len(answered)} lost={lost_total} "
           f"({100.0 * lost_total / max(1, len(sent)):.2f}%) send_err={send_err}")
out.append(f"rtt_ms p50={pct(0.5):.1f} p90={pct(0.9):.1f} p99={pct(0.99):.1f} max={pct(1.0):.1f}")
lossy = [(sec, tot, lost) for sec, (tot, lost) in per_sec.items() if lost]
out.append("seconds with loss (sec:lost/sent): " +
           (" ".join(f"{sec}:{lost}/{tot}" for sec, tot, lost in lossy) or "none"))
# where in its burst each lost query sat: G20 drops the tail of a burst
pos = collections.Counter(q % a.burst for q in sent if q not in answered)
out.append("lost by position in burst: " +
           (" ".join(f"{k}:{pos[k]}" for k in sorted(pos)) or "none"))
text = "\n".join(out)
print(text)
try:
    with open(f"/sdcard/Download/udpflow_{a.label}.txt", "w") as f:
        f.write(text + "\n")
except OSError as e:
    print("could not write report:", e)
