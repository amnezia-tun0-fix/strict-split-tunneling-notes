# Journal

Append-only, newest on top. Why the work went the way it did — the substance lives in the
registers and is not restated here. `git log` in each fork has what changed line by line.

## Index

- **2026-09-23** — a signed test build published for anyone who wants to check the fix
- **2026-09-23** — first review on #199: the hook now compiles out off Android, and is faster on it
- **2026-09-23** — submitted: three PRs, a comment on the issue, and the notes published
- **2026-09-23** — a second PR for the same issue exists, and it caught an ICMP hole in ours
- **2026-09-23** — rebased and cut into three AmneziaWG-only PR branches
- **2026-09-22** — the switch moves out of the app list; the series becomes AmneziaWG only
- **2026-09-21** — include mode measured: 0/6, one bug fixed, one limit accepted
- **2026-09-20** — the AmneziaWG bridge works on the device: 0/6 with the toggle on
- **2026-09-20** — first run on a device; Xray is blocked, the target moves to AmneziaWG
- **2026-09-19** — the first APK from our branch
- **2026-09-19** — commit identities rewritten; every fork hash changed
- **2026-09-17** — the Xray build pipeline produces our own `.aar`
- **2026-09-17** — documentation set created
- **2026-09-16** — rebased all four branches onto current upstream
- **2026-07-26** — forks confirmed as the only surviving copy
- **2026-07-01** — filter implemented on both datapaths

## 2026-09-23 — a signed test build published for anyone who wants to check the fix

The PRs cannot be tried by the people in the issue, so there is now a release in the client
fork: `v5.0.3.1-strict.1`, built by the maintainer from `8bf9b552` and signed with a key
generated for this, not the Android debug key — the debug key is public, and anything signed
with it could be replaced by anyone.

Two rounds were needed. The first build carried the old filter: the client was current, but
the recipe pinned an `amneziawg-android` commit that pinned an older `amneziawg-go`. A chain
of three repositories has to be bumped from the bottom up, and the artefact has to be checked
for the change itself — here, the `tick` method that only the reworked cache has.

The clean install then made its own point. The official app cannot be updated by a build with
a different key, so it has to be removed first, and the first probe after restoring a backup
measured nothing: the app list was empty, the guard never registered, and the probe's own
traffic went through the tunnel. The lists are stored per route mode (`Conf/<mode>`), so an
older backup restores the mode you used then, not the one you use now. The release notes say
so. With the list back: 0/6 with strict on, ICMP timing out, 6/6 with it off.

Status: Working
Next: waiting — on the maintainers, and on anyone who tries the build

## 2026-09-23 — first review on #199: the hook now compiles out off Android, and is faster on it

@makekryl, the author of #174, reviewed the Go PR within the hour: the check stayed in
non-Android builds, where #174's build tags remove it, and the per-packet cost was
"severe". Half of that was right, and the other half was worth measuring.

The platforms part was a fair hit. `uidfilter.Supported` is now a build-time constant and
the hook reads `if uidfilter.Supported && !uidfilter.AllowOutboundPacket(...)`; `go tool nm`
shows the symbol in the android build only. The cost part turned out to be about the clock,
not the design: `time.Now()` was 81 ns of the cache's 114 ns per hit ([[G12]]). Reading it
once per 64 lookups, dropping the mutex — the cache belongs to the tun-read goroutine — and
keying on a byte instead of a string took a cached UDP packet from 152 ns to 65 ns and an
established TCP packet to 12 ns. The reply carries the numbers and the `nm` output, credits
the two ideas taken from #174, and notes in passing that a cache without a TTL meets the
UID 0 problem of [[G09]] on eviction.

A useful reminder that a reviewer who disagrees is still the fastest way to find what a
measurement would have told you anyway.

Gotchas: [[G12]]
Status: Working
Next: rebuild the test APK from the new code, then the release

## 2026-09-23 — submitted: three PRs, a comment on the issue, and the notes published

Out of our hands now: amneziawg-go#199 (the filter), amneziawg-android#104 (the bridge),
amnezia-client#3199 (the setting and the wiring), and a comment on issue #2457 that carries
the four findings and links the PRs. The notes in this directory are published as
`amnezia-tun0-fix/strict-split-tunneling-notes`, with the probes and the screenshots, and
each PR links it.

What the submission itself taught: neither `amneziawg-go` nor `amneziawg-android` runs CI on
pull requests, so nothing red greets a reviewer, and in both repos only the maintainers' own
PRs have been merged for months, with a dozen external ones open. The comment on the issue
is therefore the part most likely to be read. The client repo does merge external work.

Expect no quick answer. The code is complete and measured, the limits are stated, and the
reasoning is public, which is what this stage could control.

Status: Working · everything not submitted is listed there
Next: nothing scheduled — an APK build for independent testing is possible if wanted

## 2026-09-23 — a second PR for the same issue exists, and it caught an ICMP hole in ours

Reading issue #2457 before writing the PR texts turned up amnezia-vpn/amneziawg-go#174 by
another contributor, open since 2026-08-10 with no review. It adds an Android-only filter
to `device/`, switched on through a UAPI key, and calls a C function that the Android
wrapper is expected to supply. That wrapper exists only as a patch attached to the PR. It
drops every packet it cannot identify.

That last choice exposed a hole in ours: we passed everything that was not TCP or UDP. An
app outside the VPN pinged through `tun0` from an unprivileged ping socket and got replies
with strict mode on ([[G11]]). The filter now drops what it cannot attribute. On the APK
from `510d83df`, echo through `tun0` times out with strict on and answers with it off. The
TCP/UDP probe gave 0/6 and 6/6, and browsing and video in listed apps were unaffected. The
`amneziawg-go` PR branch was re-squashed with the fix (`f9a0909`).

Writing the PR texts also found a second defect by reading the code against the claims:
`Wireguard.kt` called `awgSetUidFilter(null)` on every connect and disconnect, even with the
feature off. Merged before an `awg-android` release with the bridge, that would have broken
every AmneziaWG connection, and it made "free when off" untrue. The bridge is now called
only to clear a filter that was installed (`a6e305e5`). Final runs on that build: strict on
0/6 and ICMP timing out, strict off 6/6 and ICMP answering, no crashes.

`TestAWGDevicePing` in upstream's own `device` tests fails on a clean `master` three runs
out of three here, so it is not a signal about our change.

Decisions: [[A03]] extended · Gotchas: [[G11]]
Status: Working
Next: screenshots and review, then submission (B6)

## 2026-09-23 — rebased and cut into three AmneziaWG-only PR branches

Upstream moved in two of the three repos of the series (see
[upstream-watch](references/upstream-watch.md)). `amnezia-client` rebased onto `dev` without
a single conflict, although five of our files had moved. The APK from the rebased branch
gave 0/6 with strict mode on and 6/6 with it off.

Then the PR branches, each cut fresh from upstream rather than cleaned out of `feat`.
`amneziawg-go` squashes the filter and the SYN-only fix into one commit, because the fix
repairs our own unmerged code. `amneziawg-android` is the bridge alone. It cannot build
until upstream releases the filter, so its build was checked against our `amneziawg-go`
PR branch through a temporary `replace`, under `-Werror`. `amnezia-client` became three
commits: the guard, the setting with its switch, and the AmneziaWG wiring. The files are
taken from the tested `feat`, and the only difference from it is `Xray.kt` and the
recipes. Commit subjects follow upstream's `feat:` style without a scope.

Status: Working
Next: PR texts (B4)

## 2026-09-22 — the switch moves out of the app list; the series becomes AmneziaWG only

Two decisions by the user reshaped the PR. First, the series is AmneziaWG only: an Xray
change nobody could run on a device is easy for maintainers to shelve, and it would hold
the tested part back with it. The Xray branches stay in the forks and the AmneziaWG PR
will link them. Second, the user's review of the screen. The switch's large header left
a strip for the app list, and its long description said nothing about which protocols it
covers. The switch became one compact component in the split-tunnelling drawer and in
Settings → Connection. The app page is now identical to upstream. The switch is gated by
protocol, and a question drawer explains the trade-off when it is turned on ([[A05]]).

The first device build left the switch disabled on the user's server, silently. The
server runs AmneziaWG 2.0, whose container is `Awg2`, not `Awg` ([[G10]]). The user also
noticed the switch could be flipped while connected, unlike the rest of split tunneling;
it is now locked then. The final build registers the guard from the new switch and the
probe gives 0/6. The bottom tab bar sitting high with empty space below it is upstream's:
it looks the same on screens we never touched.

Decisions: [[A05]] revised · Gotchas: [[G10]]
Status: Working

## 2026-09-21 — include mode measured: 0/6, one bug fixed, one limit accepted

The include-mode question left open by the bridge stage, answered on the Poco F7 over
AmneziaWG. First the AOSP source of `getConnectionOwnerUid`: it returns `INVALID_UID` for
any owner our VPN does not cover, which explained the log line before a single run
([[G08]]). Then two configurations, with `tools/dns_probe.py` for DNS from a listed app and
the leak probe from an unlisted one.

| Run | Private DNS | Strict | Result |
|---|---|---|---|
| I-1a, Termux listed | off | on | DNS 5/5, exit via server, browser fine |
| I-1b | automatic | on | DNS 5/5; DoT on `:853` denied, Android falls back |
| I-1c | `one.one.one.one` | on | **DNS 0/5**, VPN flagged `PrivateDnsBroken` |
| I-1c | `one.one.one.one` | off | DNS 5/5 — the control |
| I-2, Termux unlisted | `one.one.one.one` | on | **0/6** reach the server |
| I-2 | `one.one.one.one` | off | 6/6 reach the server, as before the fix |

The leak is closed in include mode too. Two side effects came up. The resolver's own DNS
traffic is ownerless to us, so Private DNS by hostname breaks. No safe fix exists: every way
to let it through also lets through an unlisted app's bypass. That limit is accepted and
documented ([[A10]]). The other was a bug. The guard denied hundreds of Chrome's flows per
minute, and it took socket-table polling from `adb shell` to see why: they were FINs of
connections Chrome had already closed, which the kernel files under UID 0 ([[G09]]). The
AmneziaWG hook now judges TCP only on SYN, the same one-decision-per-connection model as
the Xray path.

Browsers with their own DNS-over-HTTPS (Chrome, Brave) kept working in I-1c, which is why
the broken case is easy to miss. Raw results and logcat are in `evidence/e5-include/`.

Re-measured on the APK from `8c12a715` (SYN-only filter), 2026-09-22: include mode on — 0/6,
and no denials at all during minutes of browsing in Chrome, where the old build had logged
hundreds; exclude mode on — 0/6; exclude mode off — 6/6 with the guard silent. No JNI
errors or crashes.

Decisions: [[A10]], [[A03]] and [[A04]] amended · Gotchas: [[G08]], [[G09]]
Status: Working

## 2026-09-20 — the AmneziaWG bridge works on the device: 0/6 with the toggle on

Done: the Go→C→JNI bridge in `amneziawg-android` ([[A09]]), the wiring in `Wireguard.kt`, and
a recipe that builds `awg-android` from our fork. The APK from `d83e61ca` was measured on
the Poco F7 with the same probe and the same setup as the "before" runs: AmneziaWG, exclude
mode, Termux and Chrome excluded.

| Run | Toggle | Bound to `tun0` by `SO_BINDTODEVICE` (TCP, 3×UDP, 2×curl) | Bound to the tun address | Unbound |
|---|---|---|---|---|
| AWG-ON (before) | on | 6/6 reach SERVER | time out | HOME |
| AWG-ON-after | on | **0/6** — all time out | time out | HOME |
| AWG-OFF-after | off | 6/6 reach SERVER | time out | HOME |

The OFF run matters as much as the ON run: it shows that the thing measured is our filter
and nothing else, and that a disabled filter changes nothing. Browsers inside and outside
the tunnel behaved normally with the filter on. There were no JNI errors or native crashes
in the logcat of the whole session, which covered several reconnects and mode switches.
Raw results are in `evidence/e5-awg/`.

The bridge worked on the first build. The design had anticipated the runtime traps: the
Go thread is attached once and detached by a key destructor, every call gets its own local
frame, and the callback method is resolved on a Java thread. Most of the stage's time went
into the build: `awg-android` had never been built from source here, and it took three
minutes once started. One run was lost to a WSL shell that did not read `~/.profile`,
which is recorded in the shared environment store.

Two things the logs showed need understanding before a PR. The guard logs every denial as
"owner uid unresolved", and on the device this is apparently also how Android answers for
an app outside the VPN. So the line does not mean the lookup failed. More important: during
a short switch to include mode, the guard denied DNS-over-TLS flows to `1.1.1.1:853`. If
those sockets belong to the system resolver rather than to an included app, strict mode
breaks Private DNS in include mode. Both are recorded in [status.md](status.md).

Decisions: [[A09]], [[A07]] extended to `awg-android`
Status: Working

## 2026-09-20 — first run on a device; Xray is blocked, the target moves to AmneziaWG

Done: the APK installs on the test phone (Android 16, HyperOS), a probe script for the
leak test exists, and its calibration run, with no VPN, behaved as expected.

The stage stopped on something outside the code. Xray would not connect, and the same key
failed in the store build on a second phone, so the network in Russia blocks it rather than
our build breaking it. A leak test needs a working tunnel: with no upstream the bypass
fails whether the filter is there or not, and the run would prove nothing. AmneziaWG does
connect. Over it, with the toggle on, the excluded app still reached the server by binding
to the tun interface, which is correct for now, since the toggle is wired only to Xray.
That observation is the "before" half of the AmneziaWG proof, and it came for free.

So the order changes. The AmneziaWG bridge, deferred until a device was at hand, becomes
the next stage, and the on-device proof will be made on the protocol the issue is actually
about. The Xray filter keeps its tests and its build and waits for a network where it can
be exercised.

Two things about the device matter for the probe. An ordinary app can no longer list
network interfaces: `if_nameindex`, `/sys/class/net` and `/proc/net/if_inet6` all return
`EACCES`. The probe therefore tries interface names by brute force, because the bypass
earlier went through `tun1`, not `tun0`. And one UDP echo service, Google STUN, does not
answer from the home network even without a VPN, so the UDP check needs a second service.

The "before" half was then recorded formally, over AmneziaWG with Termux excluded from
the tunnel, using `tools/leak_probe.py` run as Termux over SSH:

| Run | Toggle | Bound to `tun0` by `SO_BINDTODEVICE` (TCP, 3×UDP, 2×curl) | Bound to the tun address | Unbound |
|---|---|---|---|---|
| AWG-OFF | off | 6/6 reach SERVER | time out | HOME |
| AWG-ON | on | 6/6 reach SERVER | time out | HOME |

Two things follow for the fix. The vector is the device binding specifically: binding to
the tun **address** goes nowhere, because Android routes by UID, not by source address.
And UDP leaks exactly like TCP, so the AmneziaWG filter has to cover both. Being per-packet
on the tun read, it does by construction, and the "after" runs will show whether that holds.

Status: Blocked

## 2026-09-19 — the first APK from our branch

Done: `deploy/build.sh -t android --abi arm64-v8a --sign` in Ubuntu under WSL produced a
signed arm64-v8a APK from `0d4ae36f`, in about forty minutes from a cold cache.

It worked on the first run, which the roadmap had not dared to expect. The LF checkout did
what the Windows attempt had pointed to: every recipe revision matched the remote, so
openssl, libssh, awg-android and openvpn-pt-android downloaded, and the only thing built
from source was our libxray. The one missing piece was in the SDK rather than the
project. `client/cmake/android.cmake` pins target SDK 36 and build-tools 36.0.0, and the
environment had 35.

Signing took no invention. `--sign` only reads a keystore from environment variables, so
pointing them at the Android debug key gives the CI build with a different certificate
([[A08]]). The cost is on the device side, where the store build must go first.

One check nearly misled. The `libgojni.so` in the APK does not hash-match the one in the
`.aar`, because AGP strips native libraries when packaging a release. After the same strip
the two are identical. This belongs to the environment, not the project, so it is recorded
there.

Decisions: [[A08]]
Status: Working

## 2026-09-19 — commit identities rewritten; every fork hash changed

Done: every commit of ours in the four forks now carries the GitHub noreply address as both
author and committer, and was force-pushed. Hashes cited in older entries no longer exist on
the forks:

| Repo | Before | After |
|---|---|---|
| `amnezia-libxray` | `33d273d`, `2850389` | `7e3ad76`, `b9ac455` |
| `amneziawg-go` | `e712861` | `672fdc3` |
| `amnezia-client` | `af10f461`, `93038e19`, `bd66b9ba` | `2c831559`, `3e06d2ce`, `0d4ae36f` |

The forks are public, and a personal address had reached them twice — as the author of the
two stage-one commits and, less visibly, as the committer of every commit rebased on
2026-09-16. Trees are unchanged apart from one thing the rewrite forced: the client recipe
pins the libxray commit and the `sha256` of its archive, so rewriting libxray meant
re-pinning the recipe each time. That is the standing cost [[A07]] names, paid twice in one
day; the archive's file contents were identical and only its top directory name changed.
The local backup branches of the old tips were deleted the same day; the old
commits now exist only as unreferenced objects.

Status: Working

## 2026-09-17 — the Xray build pipeline produces our own `.aar`

Done: the conan recipe in `amnezia-client` now builds `amnezia-libxray` from our fork, and
`go.mod` there pins the tun2socks fork by pseudo-version. A stock `conan create` produces a
`libxray.aar` that contains `registerUidFilter`, and the Kotlin modules compile against it.

The stage had one real fork in the road, and it turned out to rest on a mis-stated fact.
The reason a local `replace` could not work was written down as "`build.sh` deletes
`go.mod`", and that had stopped being true in July. The durable reason is that conan builds
inside its own cache, where a sibling checkout does not exist. Correcting that made the
choice obvious: the question was never how to keep a path alive through the build, it was
which immutable id to pin. A tag loses to a pseudo-version because `proxy.golang.org` keeps
serving whatever it cached under that name, so a tag rebuilt after a rebase disagrees with
the module cache and says nothing.

The prebuilt-remote risk the roadmap flagged dissolved rather than being managed: giving
our recipe its own version leaves the Artifactory remote with no package that could be
substituted for our build. Pointing `source()` at the fork rather than adding a second
entry to `patches/` kept one source of truth, at the price of a `sha256` that has to be
recomputed on every push to the fork.

Two things worth not repeating. The NDK the Android CI job pins is an r27 **beta** under
the preview licence, and matching it exactly is unnecessary — cmake-conan reduces clang to
its major version, so any NDK in the 27 line produces the same package id. And the
verification that matters is reading `classes.jar` out of the packaged `.aar`; the build
log says "done" either way.

The stock prebuilts-only configure confirmed the integration and surfaced the next
stage's first obstacle. Our package came out of the cache as intended, but every other
recipe the project keeps locally was marked for a source build while zlib, whose recipe
comes from conancenter, downloaded. The package ids matched the remote exactly; the recipe
revisions did not, because the Windows checkout had turned the recipes' LF into CRLF.
Exporting an LF copy of the openssl recipe reproduced the remote's revision byte for byte.
The configure was stopped there rather than left compiling openssl for Android on Windows.

Decisions: [[A07]] · Gotchas: [[G04]] rewritten
Status: Working

## 2026-09-17 — documentation set created

Done: `ai_docs/` established under the umbrella directory, with both registers filled from
knowledge that until now existed only in conversation.

The project had run for two and a half months, survived a Windows reinstall and a rebase
onto an upstream that had moved 90 commits, and none of what had been learned was written
down anywhere a fresh session could read. Placing the docs outside the forks was the one
real decision: the forks are destined for a PR, and documentation about our own process
has no place in someone else's repository. That departs from the standard, which assumes
one project is one repository, so it is recorded as `D1` rather than left to be
discovered and tidied away.

Decisions: [[A01]]–[[A06]] written up · Gotchas: [[G01]]–[[G07]] written up
Status: Working

## 2026-09-16 — rebased all four branches onto current upstream

Done: branches checked out locally again and rebased; `libxray` `33d273d`, `amneziawg-go`
`e712861`, `amnezia-client` `af10f461`+`93038e19`; tun2socks needed no rebase at all.

The surprise was tun2socks: its feature branch was already on the newest code in the
repository, and the "1 commit behind" reading came from comparing against a branch that
has been a dead end since 2024. That cost an hour and became [[G01]]. The other two
conflicts were the ones reconnaissance had predicted — an import path in `send.go` after
the module moved to `/v3`, and the regenerated translation catalogue. Git resolved the
`send.go` hook placement itself and, this time, correctly; that it *could* have been
wrong is why [[G06]] exists.

Gotchas: [[G01]], [[G05]], [[G06]] · Decisions: [[A06]]
Status: Working

## 2026-07-26 — forks confirmed as the only surviving copy

Done: verified after a Windows reinstall that all commits were present in the forks on
GitHub, with matching SHAs.

The local clones had lived on a drive that no longer existed. Everything was recoverable
only because the branches had been pushed — which had not been part of the original plan
and was done almost as an afterthought. The lesson stuck: work that exists in one place
is not backed up, it is merely not lost yet.

Status: Working

## 2026-07-01 — filter implemented on both datapaths

Done: the Go mechanism, the libxray bridge, the Kotlin resolver and the settings toggle,
in that order, each verified as far as the toolchain allowed.

Two things shaped the design. The owner of a connection can only be named by Android, so
Go had to become a caller rather than a decider — that is [[A02]] and it settled the
whole structure. And the first attempt was written on the wrong tun2socks base, which
surfaced as a dependency error and was really a fork-point error; rebasing onto `v2.5.6`
fixed it and produced [[A06]]. The AmneziaWG JNI bridge was consciously left out: it is
the one piece whose failure modes need a device, and writing it blind would have produced
code nobody could check.

Decisions: [[A01]]–[[A05]] · Gotchas: [[G02]], [[G03]], [[G04]], [[G07]]
Status: Working — except the AmneziaWG bridge, deferred by design
