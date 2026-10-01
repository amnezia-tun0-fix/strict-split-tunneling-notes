# Status

**Updated:** 2026-10-02

State only — reasons in [architecture.md](architecture.md) and [gotchas.md](gotchas.md),
history in [journal.md](journal.md).

## Working

- **AmneziaWG path, verified on the device since 2026-09-20.** `uidfilter` in `amneziawg-go`,
  the JNI bridge `GoBackend.awgSetUidFilter` in `amneziawg-android` ([[A09]]), registration in
  `Wireguard.kt` (covers plain WireGuard too). Toggle on: 0/6 bypass attempts reach the
  server; off: 6/6, as before the fix. No JNI errors or crashes. Include mode
  measured on 2026-09-21: 0/6 on, 6/6 off, listed apps resolve and browse — except with
  Private DNS by hostname ([[A10]]). TCP is judged on SYN only since `a5218b5` ([[G09]]);
  unattributable packets (ICMP, fragments) are dropped since `90ec7a8` ([[G11]]). With the
  feature off the bridge is not called at all since `a6e305e5`, and since `6b20943` the hook
  is compiled out off Android and costs 14 ns per TCP packet, 62 ns per cached UDP one
  ([[G12]]).
- **Two review rounds on #199 (@izhddm), verified on the device 2026-09-25:** lookups by 4
  workers off the tun reader ([[G15]]), every SYN judged, UDP cached per 5-tuple ([[G14]]), a
  ticker clock ([[G12]]), state per device, the JNI lock off the call, no guard cache.
  Measured with `tools/churn_probe`: up to 5000 new flows/s, TCP connects keep a p50 of
  about 200 ms, as with the filter off; leak probes 0/6 on, 6/6 off, in both modes.
- **Xray path, built but not run.** `filter` in `amnezia-tun2socks`, `RegisterUidFilter` in
  `amnezia-libxray`, registration in `Xray.kt`. Go tests pass.
- **Kotlin and settings** (`amnezia-client`): `StrictSplitTunnelGuard.createOrNull` is shared
  by both protocols; the setting follows the `killSwitch`-shaped chain. The switch sits in
  the split-tunnelling drawer and Settings → Connection, enabled only for AmneziaWG/WireGuard
  and while disconnected ([[A05]]).
- **Build pipeline.** Recipes build `amnezia-libxray` (`1.0.3-strict.1`) and `awg-android`
  (`…-strict.8` on `release`, `…-strict.exp5` on `lab`) from our forks, pinned by commit; a
  test release takes the recipe's number ([[A07]]). `deploy/build.sh` under WSL signs with
  the debug key ([[A08]]).
  Check the artefact, not the log.
- **Branches are layers since 2026-10-02** ([[A13]]): in amneziawg-go, amneziawg-android and
  amnezia-client, `pr/strict-split-tunneling` → `release` (test releases) → `lab`
  (measurements), plus `followup/*` on `pr`. `tools/preflight.py` refuses a push that breaks
  the order. `release` matches strict.7 except pins and the label; strict.8 is not built yet.
  The Xray forks keep `feat/strict-tunnel-isolation`. Old histories: tags `archive/*`.
- **Submitted 2026-09-23**, AmneziaWG only, from `pr/strict-split-tunneling`: amneziawg-go#199
  (filter), amneziawg-android#104 (bridge), amnezia-client#3199 (setting), plus a comment on
  issue #2457. Each PR needs the previous one released. Texts as sent: `pr-drafts/`.
  Since 2026-09-26 #3199 says "Addresses #2457", so merging it leaves the issue open for Xray.
- **Experimental, not yet on a device:** `feat/private-dns-warning` in `amnezia-client`: at
  connect with Private DNS by hostname in include mode ([[A10]]), nothing, a notification, or
  no connection with error code 1001 ([[G18]]). One of the two is to be cut after trying both.
- **Related-work survey** posted on #2457 2026-09-27 (`pr-drafts/16-*`); amneziawg-android#105
  (2026-09-26, separate): the UAPI socket path lacked `/v3`.
- **Published notes:** `github.com/amnezia-tun0-fix/strict-split-tunneling-notes` — these
  documents, the probes and the screenshots, linked from the PRs. The embargo on the flaws
  told privately to TeapodStream and OlConnect was lifted by the user on 2026-09-28, and
  its pre-push hook removed. Synced 2026-10-01 up to G25 and A12, with the new probes.
- **Articles in Russian** in `articles/`: a survey and a deep dive, each in a compact and,
  since 2026-10-01, an expanded version (`*.long.ru.md`). The user publishes them.
- **Test builds install next to the store app** since 2026-09-30, as
  `org.amnezia.vpn.strict` ([[A11]]; «strct-AmnzVPN» from strict.8), and take commands from
  adb ([[A12]]). Released as `v5.0.3.1-strict.7` 2026-10-01 (tag on `28abcddc`, sha256
  `e000a327…`), linked from #2457; strict.3 is superseded (it has [[G24]]). Lab build
  «lab-strct-AmnzVPN» (`org.amnezia.vpn.exp`) from `lab`, installed 2026-10-02 (`8ef4b961`):
  leak probe 0/6 with the filter, 6/6 with it removed live, counters in logcat.
  How to run anything on the phone: `references/device-testing.md`. Findings of 2026-09-28:
  `evidence/research-2026-09-28/REPORT.md`.
- **Cloned apps in include mode** work since 2026-09-24: the guard matches app ids, not uids
  ([[G13]]); 0/6 on, 6/6 off on XSpace clones of two browsers.

## Fragile points

- **The AmneziaWG hook anchor** (`amneziawg-go/device/send.go`): a rebase can place the hook
  *above* `elem.padding = padding` and it still compiles. See [[G06]]. Checked by
  `tools/preflight.py` and its pre-push hook.
- **The `sha256` in `recipes/amnezia-libxray/conanfile.py`**: every push to the libxray fork
  invalidates it. The `awg-android` recipe has only `_commit` to update. See [[A07]].
- **The `replace` lines in both forks' `go.mod`**: fork-only, must never reach a PR; a
  path-shaped one never reaches the real build. See [[G04]]. A push of a `pr/*` branch
  carrying one is refused by the pre-push hook.
- **`amneziavpn_ru_RU.ts`**: generated wholesale by `lupdate`; never merge it line by line.
  See [[G05]].
- **The two Go↔Kotlin contracts differ**: gomobile gives `Long` ports and lower-cased names
  ([[G02]]), the hand-written JNI takes `Int` and a fixed method signature ([[A09]]).
- **Held packets are sent from a worker goroutine**, through
  `Device.ReleaseOutboundPacket`, not from the tun reader. It mirrors the reader's peer
  lookup and staging; a change to that part of `RoutineReadFromTUN` upstream has to be
  mirrored there. See [[G15]].
- **The guard's denials are logged at debug level** since `3e9a6978`. On a release build,
  turn on saving logs in the app before counting denials in logcat.
- **"owner uid unresolved" in the guard's log** is usually not a failed lookup: Android
  returns `INVALID_UID` for any owner our VPN does not apply to (AOSP source). See [[G08]].
- **`awgVersion()` reports `v3.1.20260814`** in the fork build although the linked code is
  newer: it reads the required version, not the replacement.

## Known issues

- **`cmd=reconnect` from adb can stop the service it just restarted** (seen on the lab build
  2026-10-02, the code is release's `AdbControl`, so strict.7 has it too): the new tunnel
  starts and closes 1 ms later, the VPN service is destroyed, `tun0` is gone. Likely cause:
  `adbReconnecting` is cleared right after `connect()`, and the state handler, seeing a late
  `DISCONNECTED` while the UI is not bound, calls `stopService()`. Not confirmed. Workaround:
  `cmd=disconnect`, then `cmd=connect`. Candidate fix: clear the flag in the state handler
  on `CONNECTED` instead (`evidence/branches-2026-10-02/`).

## Blocked

- **On-device verification of the Xray path.** Xray does not connect from Russia at all (the
  same key fails in the store build), and a leak test needs a working tunnel.
- **IPv6 through the tunnel.** Untested ([[A01]]): our AmneziaWG server has IPv4 only, so
  the tunnel carries no IPv6. Needs a server with an IPv6 address.

## Deferred

- **Translations beyond Russian.** The new UI strings exist only in the Russian catalogue
  until someone runs `lupdate`.
- **English versions of the two articles.** Postponed by the user, to do at any time.
- **The Xray path.** Not submitted: it cannot be run on a device from here. The branches are
  linked from amnezia-client#3199 for anyone who can test them.
