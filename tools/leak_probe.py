#!/usr/bin/env python3
"""E3 probe: can an app excluded from the VPN still reach the tunnel by binding to it?

Usage (in Termux):  python leak_probe.py <label> [server_ip]
Run as the app excluded from the tunnel (e.g. over `ssh poco-termux`).
Writes /sdcard/Download/e3_<label>.txt. Standard library only (+ curl if installed).
"""
import datetime
import fcntl
import os
import socket
import struct
import subprocess
import sys

SO_BINDTODEVICE = 25
SIOCGIFADDR = 0x8915
TIMEOUT = 6
HTTP_TARGETS = [("api.ipify.org", "/"), ("ifconfig.me", "/ip")]
HTTP6_TARGET = ("api6.ipify.org", "/")
STUN_SERVERS = [("stun.l.google.com", 19302), ("stun.cloudflare.com", 3478)]
DNS_WHOAMI = ("ns1.google.com", "o-o.myaddr.l.google.com")

label = sys.argv[1] if len(sys.argv) > 1 else "run"
server_ip = sys.argv[2] if len(sys.argv) > 2 else None
out_path = f"/sdcard/Download/e3_{label}.txt"
lines = []


def log(s=""):
    print(s, flush=True)
    lines.append(s)


def resolve(host, family):
    try:
        return socket.getaddrinfo(host, None, family, socket.SOCK_STREAM)[0][4][0]
    except Exception as e:
        return None


def err(e):
    if isinstance(e, OSError) and e.errno is not None:
        return f"ERR errno={e.errno} ({os.strerror(e.errno)})"
    return f"ERR {type(e).__name__}: {e}"


def make_sock(family, kind, dev=None, src=None):
    s = socket.socket(family, kind)
    s.settimeout(TIMEOUT)
    if dev:
        s.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, dev.encode() + b"\0")
    if src:
        s.bind((src, 0))
    return s


def http_ip(family, ip, host, path, dev=None, src=None):
    s = make_sock(family, socket.SOCK_STREAM, dev, src)
    try:
        s.connect((ip, 80))
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: curl/8.0\r\n"
                  f"Accept: */*\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        body = data.split(b"\r\n\r\n", 1)[-1].decode(errors="replace").strip()
        return body.splitlines()[-1].strip() if body else "EMPTY"
    finally:
        s.close()


def stun_ip(family, ip, port, dev=None, src=None):
    s = make_sock(family, socket.SOCK_DGRAM, dev, src)
    try:
        txid = os.urandom(12)
        s.sendto(struct.pack("!HHI", 1, 0, 0x2112A442) + txid, (ip, port))
        data, _ = s.recvfrom(2048)
        pos = 20
        while pos + 4 <= len(data):
            atype, alen = struct.unpack("!HH", data[pos:pos + 4])
            val = data[pos + 4:pos + 4 + alen]
            if atype in (0x0020, 0x0001):
                fam = val[1]
                if fam == 1:
                    raw = val[4:8]
                    if atype == 0x0020:
                        raw = bytes(a ^ b for a, b in zip(raw, struct.pack("!I", 0x2112A442)))
                    return socket.inet_ntop(socket.AF_INET, raw)
                if fam == 2:
                    raw = val[4:20]
                    if atype == 0x0020:
                        key = struct.pack("!I", 0x2112A442) + txid
                        raw = bytes(a ^ b for a, b in zip(raw, key))
                    return socket.inet_ntop(socket.AF_INET6, raw)
            pos += 4 + alen + ((4 - alen % 4) % 4)
        return "NO_MAPPED_ADDRESS"
    finally:
        s.close()


def dns_ip(family, ip, dev=None, src=None):
    s = make_sock(family, socket.SOCK_DGRAM, dev, src)
    try:
        qid = os.urandom(2)
        q = qid + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        for part in DNS_WHOAMI[1].split("."):
            q += bytes([len(part)]) + part.encode()
        q += b"\x00\x00\x10\x00\x01"
        s.sendto(q, (ip, 53))
        data, _ = s.recvfrom(4096)
        ancount = struct.unpack("!H", data[6:8])[0]
        pos = 12
        while data[pos] != 0:
            pos += data[pos] + 1
        pos += 5
        for _ in range(ancount):
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while data[pos] != 0:
                    pos += data[pos] + 1
                pos += 1
            rtype, _, _, rdlen = struct.unpack("!HHIH", data[pos:pos + 10])
            pos += 10
            if rtype == 16:
                return data[pos + 1:pos + 1 + data[pos]].decode(errors="replace")
            pos += rdlen
        return "NO_TXT"
    finally:
        s.close()


def try_(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        return err(e)


def is_ip(v):
    for fam in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(fam, v)
            return True
        except (OSError, ValueError):
            pass
    return False


def verdict(v, base):
    if not is_ip(v):
        return "FAIL"
    if server_ip and v == server_ip:
        return "LEAK(SERVER_IP)"
    if base and v == base:
        return "SAME"
    return "LEAK" if base else "GOT_IP"


def if_ipv4(name):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        r = fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack("256s", name[:15].encode()))
        return socket.inet_ntoa(r[20:24])
    except OSError:
        return None
    finally:
        s.close()


def if_ipv6_all():
    res = {}
    try:
        with open("/proc/net/if_inet6") as f:
            for ln in f:
                p = ln.split()
                if len(p) >= 6 and p[3] == "00":  # global scope
                    addr = ":".join(p[0][i:i + 4] for i in range(0, 32, 4))
                    res.setdefault(p[5], []).append(socket.inet_ntop(
                        socket.AF_INET6, socket.inet_pton(socket.AF_INET6, addr)))
    except Exception as e:
        res["_error"] = [err(e)]
    return res


def list_ifaces():
    names, notes = set(), []
    try:
        names.update(n for _, n in socket.if_nameindex())
    except Exception as e:
        notes.append(f"if_nameindex: {err(e)}")
    try:
        names.update(os.listdir("/sys/class/net"))
    except Exception as e:
        notes.append(f"/sys/class/net: {err(e)}")
    try:
        r = subprocess.run(["ip", "-o", "link"], capture_output=True, text=True, timeout=5)
        for ln in r.stdout.splitlines():
            parts = ln.split(":")
            if len(parts) > 1:
                names.add(parts[1].strip().split("@")[0])
    except Exception as e:
        notes.append(f"ip -o link: {err(e)}")
    return sorted(names), notes


def curl(args):
    try:
        r = subprocess.run(["curl", "-s", "-4", "-m", str(TIMEOUT)] + args + ["http://api.ipify.org"],
                           capture_output=True, text=True, timeout=TIMEOUT + 4)
        out = r.stdout.strip()
        return out if out else f"ERR curl exit={r.returncode}"
    except FileNotFoundError:
        return "ERR curl not installed"
    except Exception as e:
        return err(e)


def row(name, value, base):
    log(f"  {name:<34} {verdict(value, base):<16} {value}")


log(f"# e3 probe label={label} time={datetime.datetime.now().isoformat(timespec='seconds')} uid={os.getuid()}")
ifaces, notes = list_ifaces()
v6 = if_ipv6_all()
log(f"interfaces: {' '.join(ifaces)}")
for n in notes:
    log(f"  note: {n}")
for n in ifaces:
    a4 = if_ipv4(n)
    a6 = v6.get(n, [])
    if a4 or a6:
        log(f"  {n}: v4={a4} v6={','.join(a6) or '-'}")
if "_error" in v6:
    log(f"  /proc/net/if_inet6: {v6['_error'][0]}")

targets4 = [(h, p, resolve(h, socket.AF_INET)) for h, p in HTTP_TARGETS]
stuns4 = [(h, port, resolve(h, socket.AF_INET)) for h, port in STUN_SERVERS]
dns4 = resolve(DNS_WHOAMI[0], socket.AF_INET)
t6 = resolve(HTTP6_TARGET[0], socket.AF_INET6)
stun6 = resolve(STUN_SERVERS[0][0], socket.AF_INET6)
log(f"resolved: {[(h, ip) for h, _, ip in targets4]} stun4={[(h, ip) for h, _, ip in stuns4]} dns={dns4} {HTTP6_TARGET[0]}={t6} stun6={stun6}")

log("")
log("== baseline (no binding)")
base = None
for h, p, ip in targets4:
    v = try_(http_ip, socket.AF_INET, ip, h, p) if ip else "ERR unresolved"
    if base is None and is_ip(v):
        base = v
    row(f"tcp4 {h}", v, None)
base_udp = None
for h, port, ip in stuns4:
    v = try_(stun_ip, socket.AF_INET, ip, port) if ip else "ERR unresolved"
    row(f"udp4 stun {h}", v, None)
    if base_udp is None and is_ip(v):
        base_udp = v
v = try_(dns_ip, socket.AF_INET, dns4) if dns4 else "ERR unresolved"
row("udp4 dns whoami", v, None)
if base_udp is None and is_ip(v):
    base_udp = v
base6 = try_(http_ip, socket.AF_INET6, t6, *HTTP6_TARGET) if t6 else "ERR unresolved"
row("tcp6 api6.ipify.org", base6, None)
log(f"baseline v4 = {base}")

tuns = sorted(set([n for n in ifaces if n.startswith("tun")] + [f"tun{i}" for i in range(10)]))
h0, p0, ip0 = targets4[0]
for dev in tuns:
    a4 = if_ipv4(dev)
    a6 = v6.get(dev, [])
    log("")
    present = "yes" if (dev in ifaces or a4) else ("no" if ifaces else "unknown")
    log(f"== {dev}  (present={present}, v4={a4}, v6={','.join(a6) or '-'})")
    row("tcp4 SO_BINDTODEVICE", try_(http_ip, socket.AF_INET, ip0, h0, p0, dev=dev), base)
    if a4:
        row(f"tcp4 bind {a4}", try_(http_ip, socket.AF_INET, ip0, h0, p0, src=a4), base)
    bu = base_udp or base
    for h, port, ip in stuns4:
        if ip:
            row(f"udp4 stun {h.split('.')[1]} BINDTODEVICE", try_(stun_ip, socket.AF_INET, ip, port, dev=dev), bu)
    if dns4:
        row("udp4 dns whoami BINDTODEVICE", try_(dns_ip, socket.AF_INET, dns4, dev=dev), bu)
        if a4:
            row(f"udp4 dns whoami bind {a4}", try_(dns_ip, socket.AF_INET, dns4, src=a4), bu)
    if t6:
        b6 = base6 if is_ip(base6) else None
        row("tcp6 SO_BINDTODEVICE", try_(http_ip, socket.AF_INET6, t6, *HTTP6_TARGET, dev=dev), b6)
        for a in a6:
            row(f"tcp6 bind {a}", try_(http_ip, socket.AF_INET6, t6, *HTTP6_TARGET, src=a), b6)
    if stun6:
        row("udp6 stun SO_BINDTODEVICE", try_(stun_ip, socket.AF_INET6, stun6, STUN_SERVERS[0][1], dev=dev), None)
    row(f"curl --interface {dev}", curl(["--interface", dev]), base)
    row(f"curl --interface if!{dev}", curl(["--interface", f"if!{dev}"]), base)
    if a4:
        row(f"curl --interface host!{a4}", curl(["--interface", f"host!{a4}"]), base)

leaks = [l for l in lines if " LEAK" in l]
log("")
log(f"SUMMARY label={label} baseline={base} leaks={len(leaks)}")
for l in leaks:
    log(f"  {l.strip()}")
try:
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwritten: {out_path}")
except Exception as e:
    print(f"\nCANNOT WRITE {out_path}: {err(e)} (run termux-setup-storage)")
