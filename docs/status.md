# Status

**Updated:** 2026-09-22

State only — the reasons live in [architecture.md](architecture.md) and
[gotchas.md](gotchas.md), the history in [journal.md](journal.md).

## Working

- **AmneziaWG path, verified on the device on 2026-09-20.** `uidfilter` in `amneziawg-go`,
  the JNI bridge `GoBackend.awgSetUidFilter` in `amneziawg-android` ([[A09]]), and
  registration in `Wireguard.kt` (covers plain WireGuard too). With the toggle on, 0/6 bypass
  attempts reach the server; with it off, 6/6 do, as before the fix. Browsers inside and
  outside the tunnel work normally, and logcat shows no JNI errors or crashes. Include mode
  measured on 2026-09-21: 0/6 on, 6/6 off, listed apps resolve and browse — except with
  Private DNS by hostname ([[A10]]). TCP is judged on SYN only since `a5218b5` ([[G09]]);
  unattributable packets (ICMP, fragments) are dropped since `90ec7a8` ([[G11]]). With the
  feature off the bridge is not called at all since `a6e305e5`.
- **Xray path, built but not run.** `filter` in `amnezia-tun2socks`, `RegisterUidFilter` in
  `amnezia-libxray` (generated binding checked against the Kotlin side), registration in
  `Xray.kt`. Go tests pass and vet is clean.
- **Kotlin and settings** (`amnezia-client`): `StrictSplitTunnelGuard.createOrNull` is shared
  by both protocols; the setting follows the `killSwitch`-shaped chain. The switch sits in
  the split-tunnelling drawer and Settings → Connection, enabled only for AmneziaWG/WireGuard
  and while disconnected ([[A05]]); checked on the device 2026-09-22, probe 0/6.
- **Build pipeline.** Recipes build `amnezia-libxray` (`1.0.3-strict.1`) and `awg-android`
  (`3.1.20260814-strict.3`) from our forks, pinned by commit ([[A07]]). `deploy/build.sh`
  in Ubuntu under WSL produces a debug-signed arm64-v8a APK ([[A08]]). The bridge symbols
  and classes are checked in the artefact itself, not in the log.
- **Working branches** `feat/strict-tunnel-isolation` are pushed in all five forks and build
  the APK. `amnezia-client` was rebased onto `dev` on 2026-09-23 (probe 0/6 on, 6/6 off);
  `amneziawg-android` stays on `v3.1.20260814` so its recipe pin keeps resolving.
- **PR branches** `pr/strict-split-tunneling`, AmneziaWG only, no fork-only commits, cut
  from current upstream: `amneziawg-go` (1 commit, `f9a0909`), `amneziawg-android` (1), `amnezia-client`
  (3, `93f9d458..4b3355e0`, same files as the tested `feat` minus `Xray.kt` and recipes).
  Each depends on the previous one being released. Texts are in `pr-drafts/`. Not submitted.

## Fragile points

- **The AmneziaWG hook anchor** (`amneziawg-go/device/send.go`): a rebase can place the hook
  *above* `elem.padding = padding` and it still compiles. See [[G06]].
- **The `sha256` in `recipes/amnezia-libxray/conanfile.py`**: every push to the libxray fork
  invalidates it. The `awg-android` recipe has only `_commit` to update. See [[A07]].
- **The `replace` lines in `amnezia-libxray/go.mod` and `amneziawg-android/tunnel/tools/libwg-go/go.mod`**:
  fork-only, must never reach a PR; a path-shaped one never reaches the real build. See [[G04]].
- **`amneziavpn_ru_RU.ts`**: generated wholesale by `lupdate`; never merge it line by line.
  See [[G05]].
- **The two Go↔Kotlin contracts differ**: gomobile gives `Long` ports and lower-cased names
  ([[G02]]), the hand-written JNI takes `Int` and a fixed method signature ([[A09]]).
- **"owner uid unresolved" in the guard's log** is usually not a failed lookup: Android
  returns `INVALID_UID` for any owner our VPN does not apply to (AOSP source). See [[G08]].
- **`awgVersion()` reports `v3.1.20260814`** in the fork build, although the linked code is
  `v3.1.20260828` + filter: it reads the required version, not the replacement.
- **Comparing tun2socks against `main-amnezia`** gives a meaningless "behind by N". The
  base is tag `v2.5.6`. See [[G01]].

## Blocked

- **On-device verification of the Xray path.** Xray does not connect from Russia at all —
  the same key fails in the store build — and a leak test needs a working tunnel.

## Deferred

- **Translations beyond Russian.** The two new UI strings exist only in the Russian
  catalogue until someone runs `lupdate`, which needs Qt.
- **A PR to upstream.** Evidence exists for both modes (`evidence/e5-awg/`,
  `evidence/e5-include/`). The Xray path goes in unmeasured on a device, stated as such.
