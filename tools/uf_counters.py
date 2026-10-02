#!/usr/bin/env python3
"""Sum the uidfilter-exp-v1 counters of an experimental build over a time window.

Usage:  python uf_counters.py <logcat file> [HH:MM:SS-from] [HH:MM:SS-to]

The experimental amneziawg-go logs, under AmneziaWG/uidfilter every 5 s, the
counters that changed since the last report, as deltas. This adds them up, and
prints the lookup-latency histograms (lat_allow_*, lat_deny_*) with percentiles
read off the buckets.

The lab build since strict.exp6 also logs, every report, what the verdict cache
held (`uidfilter-exp-v1: cache mode=...`): entries by verdict, age and port
class. Those snapshots are summarised as mean and maximum per field.
"""
import collections
import re
import sys

path = sys.argv[1]
lo = sys.argv[2] if len(sys.argv) > 2 else "00:00:00"
hi = sys.argv[3] if len(sys.argv) > 3 else "99:99:99"

tot = collections.Counter()
opts = collections.Counter()
cmodes = collections.Counter()
snaps = collections.defaultdict(list)
lat_max = {"allow": 0, "deny": 0}
reports = 0
for line in open(path, encoding="utf-8", errors="replace"):
    m = re.match(r"\S+ (\d\d:\d\d:\d\d)\.\d+ .*uidfilter-exp-v1: cache (.*)", line)
    if m:
        if lo <= m.group(1) <= hi:
            for k, v in re.findall(r"(\w+)=(\S+)", m.group(2)):
                if k == "mode":
                    snaps["mode=" + v].append(1)
                elif "/" in v:
                    for i, n in enumerate(v.split("/")):
                        snaps[f"{k}[{i}]"].append(int(n))
                elif k == "port_allow":
                    for cls, n in (kv.split(":") for kv in v.split(",")):
                        snaps[f"port_allow_{cls}"].append(int(n))
                else:
                    snaps[k].append(int(v.rstrip("s")))
        continue
    m = re.match(r"\S+ (\d\d:\d\d:\d\d)\.\d+ .*uidfilter-exp-v1: \d+s (.*)", line)
    if not m or not (lo <= m.group(1) <= hi):
        continue
    reports += 1
    for k, v in re.findall(r"(\w+)=(\S+)", m.group(2)):
        if k == "opts":
            opts[v] += 1
        elif k == "cmode":
            cmodes[v] += 1
        elif k in ("lat_max_allow", "lat_max_deny"):
            kind = k.rsplit("_", 1)[1]
            lat_max[kind] = max(lat_max[kind], int(v.rstrip("us")))
        elif k in ("workers", "pending", "cache", "max_rounds"):
            continue
        else:
            tot[k] += int(v)

print(f"window {lo}..{hi}: {reports} reports, opts {dict(opts)}, cache modes {dict(cmodes)}")
for k in sorted(k for k in tot if not k.startswith("lat_")):
    print(f"  {k}={tot[k]}")
for kind in ("allow", "deny"):
    buckets = sorted(((k, v) for k, v in tot.items() if k.startswith(f"lat_{kind}_lt")),
                     key=lambda kv: float("inf") if kv[0].endswith("infus") else int(kv[0][len(f"lat_{kind}_lt"):-2]))
    n = sum(v for _, v in buckets)
    if not n:
        continue
    acc, marks = 0, {}
    for k, v in buckets:
        acc += v
        for p in (0.5, 0.9, 0.99):
            if p not in marks and acc >= p * n:
                marks[p] = k[len(f"lat_{kind}_lt"):]
    hist = " ".join(f"<{k[len(f'lat_{kind}_lt'):]}:{v}" for k, v in buckets)
    print(f"  lookup {kind}: n={n} p50<{marks[0.5]} p90<{marks[0.9]} p99<{marks[0.99]} max={lat_max[kind]}us | {hist}")
if snaps:
    n = max(len(v) for k, v in snaps.items() if not k.startswith("mode="))
    print(f"  cache snapshots: {n}, {', '.join(k for k in snaps if k.startswith('mode='))}"
          " (age buckets <2s/<10s/<60s/<600s/older)")
    for k, v in snaps.items():
        if not k.startswith("mode="):
            print(f"    {k}: mean {sum(v) / len(v):.1f}, max {max(v)}")
