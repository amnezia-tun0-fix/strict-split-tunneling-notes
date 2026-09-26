# Status

**Updated:** 2026-09-26

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

  Measured with `tools/churn_probe`: at up to 5000 new flows/s, TCP connects kept a p50 of
  about 200 ms, as with the filter off; `strict.2` reached 1.1 s at 1000/s. Leak probes
  from an excluded app: 0/6 on, 6/6 off, ICMP via `tun0` timed out and answered
  respectively; in include mode 0/6 with strict on, and browsing worked. No JNI errors. Working
  branches at `cdee4ba`, `38e28430`, `cec802df` (recipe `strict.5`). Published
  2026-09-25: the PR branches as new commits (`5864fd3`, `94c30d75`, `4d00910f`, no
  force-push), the three PR texts updated, and a reply to @izhddm on #199 with the numbers.
  Released as `v5.0.3.1-strict.3` (tag on `3e9a6978`, sha256 `0479e16d…`) after its
  own device check: 0/6 on in both modes, 6/6 off, 1000 flows/s at a p50 of about 200 ms.
  Announced on #2457, and the first comment there now links strict.3.
- **Xray path, built but not run.** `filter` in `amnezia-tun2socks`, `RegisterUidFilter` in
  `amnezia-libxray`, registration in `Xray.kt`. Go tests pass.
- **Kotlin and settings** (`amnezia-client`): `StrictSplitTunnelGuard.createOrNull` is shared
  by both protocols; the setting follows the `killSwitch`-shaped chain. The switch sits in
  the split-tunnelling drawer and Settings → Connection, enabled only for AmneziaWG/WireGuard
  and while disconnected ([[A05]]).
- **Build pipeline.** Recipes build `amnezia-libxray` (`1.0.3-strict.1`) and `awg-android`
  (`3.1.20260814-strict.5`) from our forks, pinned by commit ([[A07]]); `deploy/build.sh`
  under WSL signs with the debug key ([[A08]]). Check the artefact, not the log.
- **Working branches** `feat/strict-tunnel-isolation` in all five forks build the APK;
  `amnezia-client` rebased onto `dev` 2026-09-23. `amneziawg-android` stays on
  `v3.1.20260814` so its recipe pin keeps resolving.
- **Submitted 2026-09-23**, AmneziaWG only, from `pr/strict-split-tunneling`: amneziawg-go#199
  (filter), amneziawg-android#104 (bridge), amnezia-client#3199 (setting), plus a comment on
  issue #2457. Each PR needs the previous one released. Texts as sent: `pr-drafts/`.
  Since 2026-09-26 #3199 says "Addresses #2457", so merging it leaves the issue open for Xray.
- **Submitted 2026-09-26, independent of the series:** amneziawg-android#105. The Makefile's
  `-X` flag lacked `/v3`, so the UAPI socket never opened on Android.
- **Published notes:** `github.com/amnezia-tun0-fix/strict-split-tunneling-notes` — these
  documents, the probes and the screenshots, linked from the PRs.
- **Test build** `v5.0.3.1-strict.1` in the `amnezia-client` fork's releases: tag on
  `8bf9b552`, signed with our own key, verified after a clean install — 0/6 on, 6/6 off.
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

None open.

## Blocked

- **On-device verification of the Xray path.** Xray does not connect from Russia at all (the
  same key fails in the store build), and a leak test needs a working tunnel.

## Deferred

- **Translations beyond Russian.** The new UI strings exist only in the Russian catalogue
  until someone runs `lupdate`.
- **The Xray path.** Not submitted: it cannot be run on a device from here. The branches are
  linked from amnezia-client#3199 for anyone who can test them.
