# Testing on the phone

How measurements and checks on the Android phone are run in this project: which builds are
on it, how to drive them without taps, how to reach Termux, which probe answers which
question, and how a run is made trustworthy. Written after the study of 2026-09-28
(`evidence/research-2026-09-28/REPORT.md`, local only), so that the next session starts
from here instead of rediscovering it.

## Three builds, side by side

| App | Package | Built from | What it is for |
|---|---|---|---|
| AmneziaVPN | `org.amnezia.vpn` | the store | the user's daily VPN; not ours to touch |
| AmneziaVPN Strict | `org.amnezia.vpn.strict` | `feat/strict-tunnel-isolation` of all five forks | test releases `v5.0.3.1-strict.N` ([[A11]]); PR code plus the follow-up branches plus adb control ([[A12]]) |
| AmneziaVPN exp | `org.amnezia.vpn.exp` | `exp/lab` of amneziawg-go and amneziawg-android (pushed) and of amnezia-client (local only) | research: switchable prototypes, counters, a live filter switch |

They install next to each other, and Android runs one VPN at a time: connecting one drops
the other. Each keeps its own servers and keys; the user imports a key into a new app.

- **Test release:** the user runs `bash -l ~/build_release.sh` in WSL (asks for the keystore
  password; builds `origin/feat/strict-tunnel-isolation`, about 15 minutes; the APK lands in
  `~/AmneziaVPN-strict-split-tunneling-arm64-v8a.apk`). Nothing else runs in WSL meanwhile.
  A release takes the number of the `awg-android` recipe it is built on ([[A07]]).
- **Experimental build:** `bash tools/build_exp.sh exp/lab <out-dir>` in WSL, debug key,
  about 6 minutes, 15 when `awg-android` changes. A change in amneziawg-go travels as in
  [[A07]]: commit and push `exp/lab` → pseudo-version in `libwg-go/go.mod` of amneziawg-android
  `exp/lab` (`go.sum` via `GOPROXY=direct GOSUMDB=off GOFLAGS=-mod=mod go mod download
  github.com/amnezia-vpn/amneziawg-go/v3`) → `_commit` and `version` (`…-strict.expN`) in
  `recipes/awg-android/conanfile.py` and the root `conanfile.py` of the client.
- **Check the artefact, not the log:** `unzip -p <apk> lib/arm64-v8a/libwg-go.so | grep -a -c
  <sha12 of the amneziawg-go commit>`; for the exp build also `uidfilter-exp-v1`.
- **Install:** `adb install --user 0 -r <apk>`. HyperOS asks on the screen: the phone must be
  unlocked and the user taps «Установить»; with the screen off the install is cancelled at
  once.

## Driving the app from adb

`tools/awgctl.sh` wraps [[A12]]; it targets `org.amnezia.vpn.strict` unless
`AWG_PKG=org.amnezia.vpn.exp`:

```
tools/awgctl.sh "cmd=status"
tools/awgctl.sh "cmd=reconnect mode=include add=com.termux strict=1"
tools/awgctl.sh "cmd=disconnect"
AWG_PKG=org.amnezia.vpn.exp tools/awgctl.sh strict 0     # exp only: remove the filter live
```

- The command changes the config the service saved last and saves it on connect. The app's
  settings screen does not see it; a connect from the UI sends the UI's own config.
- `reconnect` applies a change to a running tunnel. `connect` does nothing while connected.
- The screen must be on: `am start` brings the app to the front.
- Set `ANDROID_SERIAL` (or `adb -s`) when adb lists the phone twice, by address and by mDNS.

The exp build adds, through system properties read once a second:
- `debug.awg.uf` — prototypes and knobs, comma-separated: `rv`, `raN`, `sa`, `icmp`, `frag`,
  `wN` (workers, taken when the filter is installed), `hN` (packets held per flow). Empty is
  the PR behaviour.
- `debug.awg.strict=0|1` — removes or restores the filter in the running tunnel; the only way
  to toggle it hundreds of times (the [[G24]] stress runs).
- Counters every 5 s under the logcat tag `AmneziaWG/uidfilter`, lines starting
  `uidfilter-exp-v1:`, as deltas; `python tools/uf_counters.py <log> [from] [to]` sums them
  and reads latency percentiles off the buckets. A holder replaced sooner than 5 s never
  reports.

## Termux as an ordinary app

Termux is the app whose place in the split-tunnel list decides what a probe tests: listed
(include mode) or not excluded (exclude mode) makes it an allowed app, the opposite makes it
the excluded app that tries to bypass.

- Reach it with `adb forward tcp:8022 tcp:8022`, then `ssh poco-termux '<command>'`; commands
  run as Termux's uid.
- If `ssh` says `Connection closed by 127.0.0.1 port 8022`, Termux was killed and sshd with
  it: `adb shell am start -n com.termux/.app.TermuxActivity`, then
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
| `churn_probe flows|connect|dns` | cost of new flows for everyone else | `-bind tun0` for a bypassing sender, `-hold` to keep sockets open ([[G15]], [[G16]]) |
| `udp_flow_probe.py` | loss on one long UDP flow; large datagrams | bursts of DNS queries on one socket; `--size 1400 --dst 9.9.9.9` for fragments; `--bind tun0` |
| `inbound_probe.py` | connections and ping *into* the phone through the tunnel | `listen` in Termux, `connect` on the PC, which is another peer of the same server |
| `udp_traceroute.py` | does plain traceroute work? | reads ICMP errors from the socket's error queue, no root |

1.1.1.1 and 8.8.8.8 do not answer DNS queries padded past 400–700 bytes; for large UDP use
9.9.9.9 and a same-size control without the filter.

## Making a run trustworthy

- A control for every claim: the same probe with the filter removed (exp: `debug.awg.strict=0`;
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
