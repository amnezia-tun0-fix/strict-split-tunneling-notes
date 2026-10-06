# The filter's verdict cache: ours against a FIFO

October 2026. Measurements for the discussion in [amneziawg-go#199](https://github.com/amnezia-vpn/amneziawg-go/pull/199).

## Why

For every new flow the filter asks Android which app owns the socket. That is expensive, so the verdict on a UDP flow is cached. In #199 the cache works like this: a verdict lives 10 seconds; if the flow is still active, it is checked again in the background after 2 seconds; when the cache is full, denials are thrown out first.

@makekryl (the author of #174) proposed something simpler, a FIFO without expiry: taking over someone else's 5-tuple is unlikely, and a FIFO should be faster. We decided to measure instead of arguing.

## What was compared

A cache switch was added to a test build. The mode is chosen when the filter is installed.

| Mode | What it is |
|---|---|
| `pr` | the cache from #199 |
| `fifo` | @makekryl's proposal: no expiry and no re-check, 4096 entries, holds both approvals and denials |
| `f174` | `fifo`, with every TCP packet going through the cache as well, as in #174 (5000 entries there, 4096 here) |
| `noref` | 10 s expiry without the background re-check |
| `hold` | re-check after 2 s, but the flow's packets are held while it runs |
| `pr2` | `pr`, but a full cache throws out denials only down to 7/8 of its size, not all of them (added later, see below) |

## How it was measured

- **Phone:** Poco F7, Android 16, AmneziaWG. Benchmarks on the phone and on a laptop (i5-4210U).
- **Roles.** The VPN covers every app except Termux. Termux is the excluded app that tries to get into the tunnel through `SO_BINDTODEVICE("tun0")` and floods it. `adb shell` is an ordinary allowed app, and its flows are what we measure.
- **Control:** the same tunnel with the filter removed.
- **Order.** Each mode is run twice in ABBA order (A, B, C, C, B, A), so that drift of the phone (heat, background work) does not end up in the difference between modes. A run lasts 60 seconds.
- **Checks.** Before every run, a script checks that the VPN covers `adb shell` and not Termux. The mode of every run is checked against the filter's log.
- **Conditions.** Series taken in different conditions give different absolute numbers: a hot phone with its screen off answers the owner question about a third slower. So modes are compared only within one series.
- **Builds.** The day series ran on the first test build; the evening and night series on a later one that also carries the fix described under "Found along the way". That fix matters only on a quiet tunnel, not under a flood.

About 90 runs on the phone in all, plus benchmarks and unit tests.

## Results

### 1. Speed: no difference on UDP, a difference on TCP

The cost of checking one packet, median of 10 rounds, nanoseconds:

| Packet | phone `pr` | phone `fifo` | laptop `pr` | laptop `fifo` |
|---|---|---|---|---|
| UDP, verdict in the cache | 48 | 47 | 79 | 80 |
| UDP, 256 flows, cache nearly full | 60 | 55 | 92 | 92 |
| TCP, established connection | **11** | 50 (`f174`) | **15** | 74 (`f174`) |

On UDP the two are equal: the background re-check is not in the packet's path.

On TCP the #174 scheme costs five times more, because every packet looks up its 5-tuple in the cache. In #199 only the flags are read and the verdict is made on the SYN. A connection whose SYN was denied is never established, so every other packet passes at once.

### 2. The cost of the background re-check

One extra question to Android every 2 seconds per active allowed UDP flow. For 16 long flows that is about 6 questions a second, around 20 ms of background worker time a second.

Why it is there shows on flows that send bursts of 20 packets, as video or a call does; two such flows were run at once. While a verdict is being re-checked, the filter holds at most 16 packets of a flow, and the rest are lost:

| Mode | Lost by the filter per minute, both flows | Answered |
|---|---|---|
| `pr` | 8 (4 from the first burst of each flow, the same everywhere) | 99.9% |
| `fifo` | 8 | 99.6–99.7% |
| `noref` (no re-check) | 40–44 | 99.4% |
| `hold` (re-check with packets held) | 153–168 | 99.2% |

`pr` and `fifo` do not lose the bursty flow: the first re-checks the verdict in advance, the second never re-checks it.

### 3. How long a verdict lives after its socket closes

A unit test with a controlled clock: an allowed socket closes, and a denied one takes over its 5-tuple.

| Mode | How long the denied socket passes on the other's verdict |
|---|---|
| `pr` | 2 s (1 s if the flow had been active before) |
| `noref` | up to 10 s |
| `fifo`, `f174` | until 4096 newer flows push the entry out |

The same holds in the other direction: a FIFO keeps a denial until it is pushed out. If an allowed app later gets a 5-tuple an excluded app used, it stays blocked just as long.

### 4. Flood: an excluded app floods `tun0` with denied flows

Termux opens 5000 new flows a second. Meanwhile the allowed app keeps a long flow and opens 100 new DNS flows a second. The main series was taken on a cooled phone with the screen on; averages of two runs:

| What was measured | `pr` | `pr2` | `fifo` | no filter |
|---|---|---|---|---|
| new DNS flows, flood to one address and port | 90.8% | 90.4% | **94.0%** | 99.8% |
| new DNS flows, flood with a random destination port | **81.9%** | 80.3% | 78.7% | — |
| bursty long flow, flood with a random port | **99.9%** | **99.8%** | 97.1% | — |
| steady long flow (50 packets/s) | 99.1–100% in every mode | | | |

What follows from it:

- **A FIFO holds bursty flows worse.** Under a flood it pushes out the verdict of a long allowed flow about once a second. Each re-check loses the tail of a burst: 2.2% and 2.9% in the two series that measured the FIFO here, against 0.1–0.3% with `pr`, which throws out denials first when full.
- **Against a naive flood the FIFO is better by about 3 points.** Android takes source ports from about 28,000, and at 5000 flows a second to one address the 5-tuples repeat every few seconds. A FIFO remembers about 3300 denials and answers the repeats without asking Android; `pr` remembers about 1400. If the flood changes the destination port, there are no repeats, and the advantage disappears.
- **Every mode loses new flows under a flood.** During the flood Android answers the owner question about 4400 times a second, and a flood of 5000 flows fills the queue of flows waiting for a verdict, whatever the cache. At 1000 flows a second no mode loses anything (99.5–99.8%).

**An attempt to close the gap on a naive flood: `pr2`.** It keeps more denials (about 2300) without touching approvals. In an evening series on a hot phone it seemed to catch up with the FIFO, but a repeat in good conditions gave 90.4% against 90.8% for `pr`, within the noise. It does not reach the FIFO because expired entries and approvals take up the room. It was not added to #199.

### 5. Security

The leak probe and the ICMP probe from the excluded app: 0 of 6 attempts with `pr`, `fifo`, `f174`, `noref` and `hold`, and ICMP does not pass (`pr2`, added later, was not probed). Without the filter: 6 of 6, and ICMP is answered. The cache has no effect on the protection.

## Found along the way

A verdict a background worker reached got into the cache when the reading thread collected it, and was aged from that moment, not from when the question was asked. On a quiet tunnel that stretched a verdict's lifetime. On a live phone collecting takes milliseconds, but the stated bound did not hold. Fixed in [`4215308`](https://github.com/amnezia-tun0-fix/amneziawg-go/commit/4215308) (#199), described as G26 in the [gotchas](../gotchas.md).

## What was not measured

What the cache holds during ordinary use of a phone: how many entries a FIFO keeps and how old they are, how many of them are denials, how many re-checks a second `pr` makes. The test build has the counters for it; the run is deferred.

Everything was taken on one phone. Absolute percentages under a flood depend on its state; what carries over is the difference between modes, not the numbers themselves.

## How to reproduce

- Build: the `lab` branches of the forks [amneziawg-go](https://github.com/amnezia-tun0-fix/amneziawg-go/tree/lab), amneziawg-android and amnezia-client, app `org.amnezia.vpn.exp`.
- Mode: `adb shell setprop debug.awg.uf c=fifo` (or `pr`, `f174`, `noref`, `hold`, `pr2`), then `setprop debug.awg.strict 0` and `1`, which reinstalls the filter with the new cache.
- Probes ([`churn_probe`](../../tools/churn_probe)):
  - flood from the excluded app: `churn_probe flows -rate 5000 -dur 50s -bind tun0 [-dports 10000]`;
  - new flows of the allowed app: `churn_probe dns -rate 100 -dur 60s`;
  - a long flow: `churn_probe stream -rate 50 -dur 60s`, bursty with `-flows 2 -rate 200 -burst 20`.
- The filter's counters are in logcat under the tag `AmneziaWG/uidfilter`; [`uf_counters.py`](../../tools/uf_counters.py) sums them.
- Benchmarks: `go test -bench 'ExpCachedUDP|ExpEstablishedTCP|ExpCacheFlood' ./uidfilter` on the `lab` branch.

## In short

In speed, a FIFO and the cache from #199 are equal. The extra complexity of #199 buys a bounded lifetime of verdicts in both directions and bursty allowed flows that hold up under a flood. A FIFO wins only against a naive flood to one address.
