# Upstream watch

What upstream has done since we forked, and what it cost us. One section per review.
Without this, every session re-checks the same range — or no session does.

Upstream is `github.com/amnezia-vpn/<repo>`; our forks are under
`github.com/amnezia-tun0-fix`. Each clone carries both as `upstream` and `origin`.

## 2026-09-27 — the localhost SOCKS channel, and prior art outside Amnezia

Checked while reviewing a third-party summary of the tun0 leak, which mixed real sources
with invented ones.

- **The localhost SOCKS channel is closed upstream.** Some Xray clients used to accept
  connections from any app on the device at an unauthenticated SOCKS inbound on
  `127.0.0.1:10808`, and that leaked the server address too. In Amnezia, `Xray.kt` has
  given that inbound a random loopback port and forced password auth since
  amnezia-vpn/amnezia-client#2456 (`92deee5f`, 2026-04-13). One gap is still there and
  unverified: an imported config that already names accounts keeps its own credentials,
  and `listen` is taken from the config as written. AmneziaWG has no local proxy at all.
- **Prior art: TeapodStream** (habr.com/ru/articles/1030930, May 2026; code in
  `Wendor/teapod-stream`, read at `2f8ad37d`). A gVisor tun2socks that asks
  `getConnectionOwnerUid` per connection and sends RST on deny. It falls into [[G08]] in
  one mode. `buildTunValidator` in `XrayVpnService.kt` passes an owner of `-1` whenever
  it is not in the list, so in "all except selected" an excluded app's bypass, which the
  platform reports as `INVALID_UID`, goes through. "Only selected", the default, denies
  it. This is a reading of the code; it has not been run on a device.
- **sing-box** turned #4009 (April 2026) into a `package_name_regex` rule item
  (`6746fcb`). A flow with no resolvable owner can be blocked only by a hand-written
  rule, `package_name_regex: [".*"]` with `invert` and `block`; there is no default and
  no switch in the app. #4009 also names why the lookup fails for a socket bound to an
  interface, the limit [[G17]] records from our side.
- **OlConnect** (github.com/Oleglog/OlConnect, v1.6.5). The source does call
  `getConnectionOwnerUid`, in `checkPacketAllowed` of `OlcrtcVpnService.kt`, but it
  returns "allow" for `INVALID_UID` in every mode, which lets the excluded app's bypass
  through ([[G08]]). It also always allows port 53, non-IPv4 packets and anything that is
  not TCP or UDP. Its cache is keyed on protocol and ports only ([[G14]]), and the check
  is wired into the OpenFlux session alone. This is a reading of the code, not a device
  run. Messages to both authors are drafted in `articles/notes/disclosure-drafts.md`.
- **Reported and closed as not planned:** 2dust/v2rayNG#5499 (2026-04-17, the same
  `curl --interface tun0` repro), and sing-box#3387 (2025-09-12, the earliest related
  report found, on a rooted phone, mechanism not named). hiddify-app#2120 is about the
  local SOCKS inbound, not `tun0`.
- **Nothing found** from WireGuard for Android, Mullvad, Proton VPN, Tailscale, WARP,
  Outline, Orbot or ics-openvpn, and no AOSP bug, CVE or bulletin. The Android 17
  per-app VPN screen is UI only. `Ginder-Singh/devicebindleak` claims the leak needs
  `allowBypass()`, which our device runs contradict; do not cite it.
- **The local SOCKS channel elsewhere:** opt-in auth or a way to switch the inbound off
  shipped in Karing 1.2.16, Throne 1.1.2, FlClash 0.8.97 and Exclave 0.17.35.
- **The summary's errors:** "Karing #1437" (KaringX/karing#1437 only reports the Habr
  finding), and a work profile (Shelter, Island) that supposedly cannot bind `tun0`:
  Android users share one network namespace, and RKNHardering detects `tun0` from inside
  Shelter (habr.com/ru/articles/1026500).

The public write-up of this survey is `pr-drafts/16-issue-comment-related-work.md`.
Nothing here changes our design.

## 2026-09-25 — a related PR by our reviewer: the Xray server address in VPN routes

amnezia-vpn/amnezia-client#3214 by @izhddm, not addressed to us. On Android 13+ `Xray.kt`
calls `excludeRoute(hostName/32)`. The platform turns that into a `throw` route in the VPN
network's `LinkProperties`, and any app with `ACCESS_NETWORK_STATE` can read it, excluded
apps included. That discloses the server's address with no packet sent. The PR deletes
the three lines. Xray's own sockets are already `protect()`ed through the dialer
controller, and on Android 10–12 `Protocol.kt` never applied the route anyway.

What it means for us:
- **AmneziaWG:** not affected. On our Poco the AWG connection's routes are `0.0.0.0/0`,
  `2000::/3` and the tunnel address, with no `throw` route and no endpoint.
- **Our Xray branch:** it carries the same `excludeRoute`. If the Xray path is ever
  submitted, it has to drop those lines too, or build on top of #3214.
- **OpenVPN** (`OpenVpn.kt`) excludes its remote the same way. The PR leaves it alone for
  want of a server to test, and so do we.
- **Scope:** this is a passive channel next to the active one strict mode closes (#2457).
  The two are complementary, and neither closes the other.

Also filed by @izhddm: xtclovver/RKNHardering#88, the detector side of the same finding.

The same evening the author's account started returning 404, and #3214, #88 and the
reviews on #199 and #3199 became unreachable with it. The texts we relied on are kept
locally in `evidence/izhddm-2026-09-25/`. Check again before citing any of them by link.

## 2026-09-23 — reviewed before cutting the AmneziaWG PR branches

| Repo | Range reviewed | Verdict |
|---|---|---|
| `amnezia-client` | `eab14fd9..94b51df2` (9 commits) | rebased `feat`, no conflicts |
| `amneziawg-go` | none — still `b5928ef` (tag `v3.1.20260828`) | unchanged |
| `amneziawg-android` | `5c16489e..ff15093b` (3 commits) | `feat` left in place |

`amnezia-client` touched five files we also touch — the settings controllers,
`configKeys.h` and the Russian catalogue — and the rebase still applied cleanly, catalogue
included; `git range-diff` shows all ten commits unchanged. `de93650a` rewrote f-strings in
three conan recipes for Python below 3.12; none of them is one of ours. The other commits
are version bumps, CI pins, a config format version and a clickable notification.

`amneziawg-android` changed a banner, the manifest, a workflow and the version. Its tags
now read `v3.1.3` and `v3.1.4`, after `v3.1.20260814`; the client's `awg-android` recipe
clones `--branch v{version}`, so the version the client pins is literally the tag name. Our
`feat` branch was not rebased: nothing we touch moved, and rebasing would orphan the commit
the fork recipe pins. The PR branch is cut from the new `master` instead.

### To check next time

- Which `amneziawg-android` tag follows `v3.1.4`, and whether upstream client bumps
  `awg-android` to it — that bump is where our client PR's dependency lands.
- The four items of 2026-09-17 still stand; `RoutineReadFromTUN` was not touched.

## 2026-09-17 — re-checked before building the Xray pipeline

| Repo | Range reviewed | Verdict |
|---|---|---|
| `amnezia-client` | `eab14fd9..de36a81b` (5 commits) | no rebase needed |
| `amnezia-libxray` | none — still `e8cc06d` (= tag `v1.0.3`) | unchanged |
| `amnezia-tun2socks` | none — still `6869b12` | unchanged |
| `amneziawg-go` | none — still `b5928ef` | unchanged |
| `amneziawg-android` | none — still `5c16489` | unchanged |

Only `amnezia-client` moved, and none of the five commits touches a file we touch: the
test suite was migrated into the main repository, plus a clickable notification, Windows
certificate signing, and two CI pins. Two build-chain lines changed and neither affects
us — `recipes_bootstrap.cmake` gained a `.venv/Scripts` hint for Windows, and
`deploy/build.sh` gained an `AMNEZIA_BUILD_TESTS` pass-through. The
`recipes/amnezia-libxray/` recipe is untouched: still version 1.0.3, still carrying the
`conandata.yml` + `patches/` mechanism our route depends on, and its single patch
(16 KB page support) still applies to our fork because we do not touch `build.sh`.

Worth recording because it is easy to misread: the NDK the Android CI job pins,
`27.0.11718014`, is **r27-beta1** and sits under `android-sdk-preview-license`. Any
stable NDK from the 27 line ships clang 18 and therefore produces the same conan
`compiler.version`, so matching the CI job does not require matching that exact package.

### To check next time

- Whether upstream bumped the `amnezia-libxray` recipe past 1.0.3. Our recipe now carries
  its own version and its own source URL ([[A07]]), so an upstream bump is no longer
  something we inherit — it is something we have to re-apply deliberately.
- Whether upstream `amneziawg-go` touched `RoutineReadFromTUN` again; that loop is where
  our only hook in that repo lives.
- Whether `amnezia-tun2socks` finally moved off `6869b12`. If it does, re-check that the
  gVisor forwarder signatures still match what our hooks assume, and recompute the
  pseudo-version pinned in `amnezia-libxray/go.mod`.
- Whether the `awg-*` recipes gained a `patches/` mechanism; the AmneziaWG stage needs one
  and there is none today.

## 2026-09-16 — reviewed before rebasing all four branches

| Repo | Range reviewed | Verdict |
|---|---|---|
| `amnezia-client` | `0f684721..eab14fd9` (90 commits) | rebased; one conflict |
| `amneziawg-go` | `1cc9427..b5928ef` (15 commits) | rebased; two small conflicts |
| `amnezia-libxray` | `a45a836..e8cc06d` (5 commits) | rebased; conflict in `go.mod` only |
| `amnezia-tun2socks` | none — unchanged since 2026-02-20 | no rebase needed |

**`amnezia-client`.** The `killSwitch` settings chain we mirror survived all 90 commits
untouched at every one of our six insertion points, and `PageSettingsAppSplitTunneling.qml`
was not edited at all. `Xray.kt` changed in exactly one commit, in a hunk that does not
overlap ours. The only real conflict was the regenerated translation catalogue ([[G05]]).
Upstream also raised the `amnezia-libxray` conan recipe from 1.0.0 to **1.0.3 and added a
patch mechanism** — `conandata.yml`, `apply_conandata_patches`, a `patches/` directory.
That is the supported home for our bridge patch and unblocks the route to a real build.

**`amneziawg-go`.** Upstream moved to the AWG 3.x series: header protection, random
trailers, a reworked encryption routine, and the **module renamed to
`github.com/amnezia-vpn/amneziawg-go/v3`**. Our hook's anchor survived, but upstream now
writes `elem.padding = padding` into the gap it sits in ([[G06]]), and the import line
needed `/v3`. No filtering mechanism of upstream's own appeared, so there is nothing to
reconcile with ours.

**`amnezia-libxray`.** Upstream switched to importing `github.com/xtls/xray-core` and
redirecting it to their fork with a `replace` — the same technique we use for tun2socks,
which means the pattern is now idiomatic here rather than a local hack. Our `replace`
occupies the same textual position, so the two collide on rebase and both are kept.
`controller.go` was not touched.

**`amnezia-tun2socks`.** `upstream/main`, tag `v2.5.6` and tag `v2.6.2` are all the same
commit, `6869b12`, unchanged since February 2026. There is nothing newer to move to;
the apparently newer tag is an alias ([[G01]]).
