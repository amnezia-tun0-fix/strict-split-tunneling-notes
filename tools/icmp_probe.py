#!/usr/bin/env python3
"""E6 probe: can an app send ICMP echo through tun0 with an unprivileged ping socket?

Usage (in Termux):  python icmp_probe.py <label> [target_ip ...]
A reply to an echo sent while bound to tun0 means the packet left through the VPN, so the
target saw the VPN server's address. Standard library only.
"""
import os
import socket
import struct
import sys
import time

SO_BINDTODEVICE = 25
label = sys.argv[1] if len(sys.argv) > 1 else "run"
targets = sys.argv[2:] or ["1.1.1.1", "8.8.8.8"]


def echo(dst, dev=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
    s.settimeout(4)
    try:
        if dev:
            s.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, dev.encode() + b"\0")
        payload = os.urandom(16)
        s.sendto(struct.pack("!BBHHH", 8, 0, 0, 0, 1) + payload, (dst, 0))
        t = time.monotonic()
        data, addr = s.recvfrom(2048)
        return f"REPLY from {addr[0]} in {(time.monotonic() - t) * 1000:.0f} ms"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {e}"
    finally:
        s.close()


for dst in targets:
    for dev in (None, "tun0"):
        print(f"{label} icmp {dst:15} via {dev or 'default':7} {echo(dst, dev)}", flush=True)
