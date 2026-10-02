# Testing on the phone

How measurements and checks on the Android phone are run in this project: which builds are
on it, how to drive them without taps, how to reach Termux, which probe answers which
question, and how a run is made trustworthy. Written after the study of 2026-09-28
(`evidence/research-2026-09-28/REPORT.md`, local only), so that the next session starts
from here instead of rediscovering it.

## What the agent does on the phone by itself

The user granted this on 2026-10-02, for this project: the agent drives the phone over adb
and Termux on its own, without asking first, and says in one line what it did. That
includes the screen actions the global default would have it ask about: waking the screen,
`am start`, `input text` / `keyevent` / `tap`, `uiautomator dump` to find a button. Typical
uses: starting `sshd` in Termux, confirming the install dialog, connecting, reconnecting and
disconnecting the test builds, setting `debug.awg.*` properties, running probes in Termux and
in `adb shell`, installing lab and test builds.

The user is asked only for what the agent cannot or must not do itself: unlocking a screen
with a PIN (never enter it), anything in the store app `org.amnezia.vpn`, and changes to the
phone's own settings or the user's data outside the test builds. Asking for a step the agent
could do over adb only costs the user a trip to the phone.

## Three builds, side by side

| App | Package | Built from | What it is for |
|---|---|---|---|
| AmneziaVPN | `org.amnezia.vpn` | the store | the user's daily VPN; not ours to touch |
| strct-AmnzVPN | `org.amnezia.vpn.strict` | `release` of amneziawg-go, amneziawg-android, amnezia-client; `feat/strict-tunnel-isolation` of the Xray forks | test releases `v5.0.3.1-strict.N` ([[A11]]); PR code plus the follow-up branches plus adb control ([[A12]]) |
| lab-strct-AmnzVPN | `org.amnezia.vpn.exp` | `lab` of the same three forks | measurements: release code plus counters, switches, a live filter switch |

Branches are layers, each built on the one below: `pr/strict-split-tunneling` → `release` →
`lab` ([[A13]]). A lab build therefore runs exactly the released filter, plus instruments.
The lab app keeps the old `.exp` applicationId so it updates in place.

They install next to each other, and Android runs one VPN at a time: connecting one drops
the other. Each keeps its own servers and keys; the user imports a key into a new app.

- **Test release:** the user runs `bash -l ~/build_release.sh` in WSL (asks for the keystore
  password; builds `origin/release`, about 15 minutes; the APK lands in
  `~/AmneziaVPN-strict-split-tunneling-arm64-v8a.apk`). Nothing else runs in WSL meanwhile.
  A release takes the number of the `awg-android` recipe it is built on ([[A07]]).
- **Lab build:** `bash tools/build_exp.sh lab <out-dir>` in WSL, debug key,
  about 6 minutes, 15 when `awg-android` changes. A change in amneziawg-go travels as in
  [[A07]]: commit and push `lab` → pseudo-version in `libwg-go/go.mod` of amneziawg-android
  `lab` (`go.sum` via `GOPROXY=direct GOSUMDB=off GOFLAGS=-mod=mod go mod download
  github.com/amnezia-vpn/amneziawg-go/v3`) → `_commit` and `version` (`…-strict.expN`) in
  `recipes/awg-android/conanfile.py` and the root `conanfile.py` of the client.
- **Check the artefact, not the log:** `unzip -p <apk> lib/arm64-v8a/libwg-go.so | grep -a -c
  <sha12 of the amneziawg-go commit>`; for the lab build also `uidfilter-exp-v1`.
- **Install:** `adb install --user 0 -r <apk>`. HyperOS may ask on the screen: wake it
  (`input keyevent KEYCODE_WAKEUP`), find «Установить» with `uiautomator dump` and tap it.
  With the screen off the install is cancelled at once; on 2026-10-02 an update in place
  went through with no dialog.

## Driving the app from adb

`tools/awgctl.sh` wraps [[A12]]; it targets `org.amnezia.vpn.strict` unless
`AWG_PKG=org.amnezia.vpn.exp`:

```
tools/awgctl.sh "cmd=status"
tools/awgctl.sh "cmd=reconnect mode=include add=com.termux strict=1"
tools/awgctl.sh "cmd=disconnect"
AWG_PKG=org.amnezia.vpn.exp tools/awgctl.sh strict 0     # lab only: remove the filter live
```

- The command changes the config the service saved last and saves it on connect. The app's
  settings screen does not see it; a connect from the UI sends the UI's own config.
- `reconnect` applies a change to a running tunnel. `connect` does nothing while connected.
- Check what the tunnel covers before measuring: `dumpsys connectivity | grep "VPN CONNECTED"`,
  its `Uids:` list. On 2026-10-02 a `connect` with the screen locked came up with the saved
  include list instead of the one sent, and a series measured an "allowed" `adb shell` outside
  the tunnel (`allow=0` in the counters). `checkvpn` in `evidence/cache-study-2026-10/run.sh`
  refuses to run unless uid 2000 is inside and Termux outside.
- With the screen locked the adb control is unreliable. The same evening a `connect` of the
  test release crashed its UI process (`UnsatisfiedLinkError` in
  `QtAndroidController.onStatus`: a service event reached the activity before Qt's native
  library); the VPN service stayed up. Wake and unlock first where possible.
- Keep Termux's `termux-wake-lock` during flood runs, and expect a dark screen to slow owner
  lookups by about a third (2500/s against 3700/s); compare modes only within one series.
- The screen must be on: `am start` brings the app to the front.
- Set `ANDROID_SERIAL` (or `adb -s`) when adb lists the phone twice, by address and by mDNS.

The lab build adds, through system properties read once a second:
- `debug.awg.uf` — knobs, comma-separated: `icmp` (pass ICMP only the kernel sends), `wN`
  (workers, taken when the filter is installed), `hN` (packets held per flow). Empty is the
  release behaviour. The prototypes of the former `exp/lab` (`rv`, `raN`, `sa`, `frag`) are
  release code now or dropped; their names are ignored. Since `strict.exp6`, `c=MODE` picks
  the verdict cache, taken when the filter is installed: `pr` (release), `fifo` (no expiry,
  as proposed on #199), `noref` (10 s, no refresh), `hold` (refresh with packets held),
  `f174` (`fifo` plus every TCP packet, as #174), `pr2` (`pr` evicting denials only down to 7/8, `strict.exp8`). Switch with `debug.awg.strict=0`, then `1`;
  the report's `cmode=` shows the mode in force. Results: `evidence/cache-study-2026-10/`.
- `debug.awg.strict=0|1` — removes or restores the filter in the running tunnel; the only way
  to toggle it hundreds of times (the [[G24]] stress runs).
- Counters every 5 s under the logcat tag `AmneziaWG/uidfilter`, lines starting
  `uidfilter-exp-v1:`, as deltas; `python tools/uf_counters.py <log> [from] [to]` sums them
  and reads latency percentiles off the buckets. A holder replaced sooner than 5 s never
  reports. Each report also logs `uidfilter-exp-v1: cache ...`, a snapshot of the cache
  without addresses (entries by verdict, age bucket, port class); `uf_counters.py` averages
  them. `cache_evictions` and `fifo_evicted_*` are process-wide: the first report of a new
  holder carries the total so far, so subtract the previous run's sum.

## Termux as an ordinary app

Termux is the app whose place in the split-tunnel list decides what a probe tests: listed
(include mode) or not excluded (exclude mode) makes it an allowed app, the opposite makes it
the excluded app that tries to bypass.

- Reach it with `adb forward tcp:8022 tcp:8022`, then `ssh poco-termux '<command>'`; commands
  run as Termux's uid.
- If `ssh` says `Connection closed by 127.0.0.1 port 8022`, Termux was killed and sshd with
  it; the agent restarts it itself: `adb shell input keyevent KEYCODE_WAKEUP`,
  `adb shell am start -n com.termux/.app.TermuxActivity`, then
  `adb shell input text "sshd%s-o%sListenAddress=127.0.0.1"`, `adb shell input keyevent 66`,
  the same for `termux-wake-lock`.
- Anything that must outlive the SSH session: `setsid nohup <cmd> > log 2>&1 < /dev/null &`.
- `pkill -f "[i]nbound_probe.py listen"`: without the bracket the pattern matches the SSH
  command line itself and kills the session.
- Probes are copied with `ssh poco-termux 'cat > name.py' < tools/name.py`.

`adb shell` runs as uid 2000: outside the VPN in include mode, inside it in exclude mode. Its
copy of `churn_probe` lives in `/data/local/tmp`.

## Which probe answers which question

| Probe | Question | Notes |
|---|---|---|
| `leak_probe.py <label> <server ip>` | does an excluded app reach the server through `tun0`? | 6 attempts; the report is in `/sdcard/Download/e3_<label>.txt`; strip the `baseline=` home address before quoting |
| `icmp_probe.py` | does ICMP echo pass via `tun0`? | [[G11]] |
| `dns_probe.py` | does the system resolver work for a listed app? | [[A10]] |
| `churn_probe flows|connect|dns` | cost of new flows for everyone else | `-bind tun0` for a bypassing sender, `-hold` to keep sockets open ([[G15]], [[G16]]); `-dports N` spreads a flood over N destination ports, without which its 5-tuples repeat every ~28000 flows and a cache of denials absorbs them |
| `churn_probe stream` | loss on long UDP flows, from `adb shell` | `-flows N`, `-burst 20` for QUIC-like bursts ([[G20]]); answers per second and the longest gap |
| `udp_flow_probe.py` | loss on one long UDP flow; large datagrams | bursts of DNS queries on one socket; `--size 1400 --dst 9.9.9.9` for fragments; `--bind tun0` |
| `inbound_probe.py` | connections and ping *into* the phone through the tunnel | `listen` in Termux, `connect` on the PC, which is another peer of the same server |
| `udp_traceroute.py` | does plain traceroute work? | reads ICMP errors from the socket's error queue, no root |

1.1.1.1 and 8.8.8.8 do not answer DNS queries padded past 400–700 bytes; for large UDP use
9.9.9.9 and a same-size control without the filter.

## Making a run trustworthy

- A control for every claim: the same probe with the filter removed (lab: `debug.awg.strict=0`;
  release: `reconnect strict=0`), and where a prototype is compared, with the option on and
  off.
- ABBA order, at least two runs per variant, and say so when a result comes from one run.
  Drift across a session is real: DNS answer rates slid from 99.8% to 99.0% over four runs
  whatever the worker count.
- Record logcat from the start of a run into a file; the HyperOS ring buffer loses app lines
  in minutes. Restart the recording after a reinstall or a crash: `adb logcat` exits.
- A process that dies with signal 11 and leaves no tombstone had the signal blocked
  ([[G24]]); look at what happened in the preceding tens of milliseconds.
- Raw output goes to `evidence/<topic>/` (git-ignored, local only).
- Tests on the PC: `go test -race` in WSL (on Windows, device tests ask the firewall each
  run). `TestAWGDevicePing` in `device` is flaky in WSL on a clean upstream too; run the
  package with `-skip TestAWGDevicePing` and do not read its failure as ours.

## Returning the phone

Clear the properties (`setprop debug.awg.ctl ""`, the same for `debug.awg.uf` and
`debug.awg.strict`), stop background probes in Termux, disconnect test builds, and note every
change made to the phone's settings or app lists in the report.
