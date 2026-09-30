# Status

**Updated:** 2026-10-01

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
- **Two review rounds on #199 (@izhddm), verified on the device 2026-09-25.** Changes:
  - new flows are judged by 4 workers while their first packets are held, not on the tun
    reader ([[G15]]);
  - every TCP SYN is judged afresh, and UDP verdicts are cached per 5-tuple ([[G14]]);
  - the clock is a ticker, not a lookup counter ([[G12]]);
  - state is per device, and `Set` swaps it in one step;
  - the JNI lock no longer spans the call, and the guard lost its cache and its retry.

  Measured with `tools/churn_probe`: up to 5000 new flows/s, TCP connects keep a p50 of
  about 200 ms, as with the filter off; leak probes 0/6 on, 6/6 off, in both modes. Working
  branches at `0f0382e`, `4ac9414e`, `642a957f` (recipe `strict.6`, [[G19]]); the PR
  branches got them as new commits. Released as `v5.0.3.1-strict.3` (`3e9a6978`).
- **Xray path, built but not run.** `filter` in `amnezia-tun2socks`, `RegisterUidFilter` in
  `amnezia-libxray`, registration in `Xray.kt`. Go tests pass.
- **Kotlin and settings** (`amnezia-client`): `StrictSplitTunnelGuard.createOrNull` is shared
  by both protocols; the setting follows the `killSwitch`-shaped chain. The switch sits in
  the split-tunnelling drawer and Settings → Connection, enabled only for AmneziaWG/WireGuard
  and while disconnected ([[A05]]).
- **Build pipeline.** Recipes build `amnezia-libxray` (`1.0.3-strict.1`) and `awg-android`
  (`3.1.20260814-strict.7`) from our forks, pinned by commit; a test release now takes the
  recipe's number ([[A07]]). `deploy/build.sh` under WSL signs with the debug key ([[A08]]).
  Check the artefact, not the log.
- **Working branches** `feat/strict-tunnel-isolation` in all five forks build the APK;
  `amnezia-client` rebased onto `dev` 2026-09-23. `amneziawg-android` stays on
  `v3.1.20260814` so its recipe pin keeps resolving.
- **Submitted 2026-09-23**, AmneziaWG only, from `pr/strict-split-tunneling`: amneziawg-go#199
  (filter), amneziawg-android#104 (bridge), amnezia-client#3199 (setting), plus a comment on
  issue #2457. Each PR needs the previous one released. Texts as sent: `pr-drafts/`.
  Since 2026-09-26 #3199 says "Addresses #2457", so merging it leaves the issue open for Xray.
- **Experimental, not yet on a device:** `feat/private-dns-warning` in `amnezia-client`: at
  connect with Private DNS by hostname in include mode ([[A10]]), nothing, a notification, or
  no connection with error code 1001 ([[G18]]). One of the two is to be cut after trying both.
- **Related-work survey posted 2026-09-27** on #2457, and linked from a new section of the
  amneziawg-go#199 body: who else closes the `tun0` leak and who declined to. Text:
  `pr-drafts/16-*`, sources in `references/upstream-watch.md`.
- **Submitted 2026-09-26, independent of the series:** amneziawg-android#105. The Makefile's
  `-X` flag lacked `/v3`, so the UAPI socket never opened on Android.
- **Published notes:** `github.com/amnezia-tun0-fix/strict-split-tunneling-notes` — these
  documents, the probes and the screenshots, linked from the PRs. The embargo on the flaws
  told privately to TeapodStream and OlConnect was lifted by the user on 2026-09-28, and
  its pre-push hook removed: every document may be synced.
- **Articles, Russian drafts done 2026-09-28** in `articles/`: a survey and a deep dive.
  The user publishes them.
- **Test builds install next to the store app** since 2026-09-30, as
  `org.amnezia.vpn.strict` «AmneziaVPN Strict» ([[A11]]), and take commands from adb
  ([[A12]]). Released as `v5.0.3.1-strict.7` 2026-10-01 (tag on `28abcddc`, sha256
  `e000a327…`), linked from #2457; strict.3 is superseded (it has [[G24]]). Research builds: `exp/lab` in the forks (client local), `org.amnezia.vpn.exp`.
  How to run anything on the phone: `references/device-testing.md`. Findings of 2026-09-28:
  `evidence/research-2026-09-28/REPORT.md`.
- **Cloned apps in include mode** work since `9ce688c4` (PR #3199: `9663133a`): the guard
  matches app ids, not uids ([[G13]]). Verified 2026-09-24 on XSpace clones of two browsers;
  probe 0/6 on, 6/6 off. Released as `v5.0.3.1-strict.2` (tag on `9ce688c4`).

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
- **Comparing tun2socks against `main-amnezia`** is meaningless; the base is `v2.5.6` ([[G01]]).

## Known issues

Found 2026-09-28, all on the PR branch, fixes prototyped on `exp/lab`:
- [[G24]] — the VPN service can die (SIGSEGV) when the filter's workers exit: every
  disconnect, reconnect and toggle. In #199 and release strict.3. Fix `342f9ec`.
- [[G20]], [[G21]] — UDP loss at every verdict expiry and in a new flow's first burst;
  [[G22]], [[G23]] — inbound connections in include mode, UDP datagrams over the MTU.

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
