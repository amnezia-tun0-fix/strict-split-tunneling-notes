# Architecture

- **A01** · Filter in userspace, at the tun-read boundary, in both datapaths
- **A02** · The Go side asks, the Kotlin side decides
- **A03** · An unresolved owner is denied, not allowed
- **A04** · A per-flow decision cache, in a different layer for each datapath
- **A05** · The toggle mirrors killSwitch and is off by default
- **A06** · tun2socks is forked from tag v2.5.6, not from `main-amnezia`
- **A07** · Each fork is pinned by an immutable id, and conan consumes ours by version
- **A08** · Test builds go through the stock `--sign` path, signed with the Android debug key
- **A09** · The AmneziaWG bridge is a hand-written JNI upcall on the Go thread
- **A10** · Include mode with strict filtering does not support Private DNS by hostname

## Big picture

The fix is one idea applied twice: **ask, at the moment a packet leaves the tun device,
which app owns it, and drop it if that app is not allowed in the tunnel.** Everything
else follows from two facts. The owner can only be named by Android, not by Go ([[A02]]).
And the two datapaths share nothing but the tun file descriptor, so the hook has to be
written twice, in two different shapes ([[A01]]).

```
  packet leaves tun ──► [hook] ──► ask bridge ──► Kotlin resolves owner + policy
                          │                              │
                          └──◄── allow / deny ◄───────────┘
                     deny: RST (TCP) | drop (UDP, AWG)
```

`tun2socks` sees connections, so its hook sits in the gVisor forwarders and fires once
per connection. `amneziawg-go` sees raw packets, so its hook parses the 5-tuple itself
and leans on a cache to keep the bridge crossing rare ([[A04]]).

## A01. Filter in userspace, at the tun-read boundary, in both datapaths

**Context:** Android's per-app split tunnelling is enforced by routing, and routing is
advisory: since Linux 5.7 `SO_BINDTODEVICE` is available to unprivileged processes, so
any app can bind to `tun0` and reach the tunnel whichever way the user configured it.
The app then learns the VPN server's IP. The client cannot tighten the OS rules from
inside the app, so if the bypass is to be closed at all, it has to be closed in the code
that reads the tun device.

Android does try to stop it, and the kernel undoes that. `ip rule` on a phone has
`oif tun0 uidrange <VPN uids> lookup <vpn table>` for the VPN's own uids and nothing for
the rest. For any other uid `fib_lookup` fails, and `ip_route_output_key_hash_rcu` then
assumes the destination is on-link because the socket named an output interface, and
sends anyway. `ip route get <ip> oif tun0 uid 2000` shows `dev tun0` with no table.
A VPN app can change neither the rules nor the kernel, and the packets look the same
either way: same source address, no mark. (Explained by @izhddm in the review of
amneziawg-go#199.) This is the IPv4 output path. Per the same reviewer, the IPv6 path in
kernel 6.1 has no such fallback. Neither they nor we have tested IPv6: our tunnel had no
IPv6 address, and every probe through `tun0` failed with "Network is unreachable".

**Alternatives:** *Rely on `VpnService.addDisallowedApplication`* — that is precisely the
mechanism being bypassed. *Block at the socket layer* — an app cannot touch another
app's sockets. *iptables / netfilter rules* — needs root, which puts it outside the
product. *Do nothing and document it* — the reported consequence is disclosure of the
server IP, which is the one thing a censorship-resistant VPN cannot leak.

**Decision:** gate every new flow where packets enter the tunnel stack. In
`amnezia-tun2socks/core/tcp.go` and `core/udp.go` the gVisor forwarders already hand over
a 5-tuple before an endpoint exists, so the check goes there. In
`amneziawg-go/device/send.go` the TUN read loop has the whole IP packet in
`elem.packet`, so the check goes immediately after it is sliced.

**Consequences:** the real vector is closed for both protocols, including AmneziaWG 2.0,
which is what the issue is actually about. The cost is one owner lookup per new flow.
The hook had to be written twice and the two look different — a reviewer seeing only one
of them will think the other is missing. *Divergence from upstream:* each datapath gains
a small package and a few lines at one call site; both are additive, so porting upstream
fixes means re-applying two insertions, not resolving overlapping logic. The tun2socks
hook has already survived one upstream rebase untouched; the AmneziaWG one moved by one
line when upstream added `elem.padding` ([[G06]]).

## A02. The Go side asks, the Kotlin side decides

**Context:** the filter needs the UID that owns a connection. On Android that is
`ConnectivityManager.getConnectionOwnerUid`, available to the app that is the active
`VpnService` — a Java API. Go, running inside the same process, has no equivalent.

**Alternatives:** *Resolve in Go from `/proc/net/tcp`* — since Android 10 that file shows
only the caller's own sockets, so it is blind exactly where it matters ([[G03]]).
*Push the allowed-UID set down to Go and let it match* — Go would still have to map a
packet to a UID, which is the part it cannot do. *Have Go publish pending flows and let
Kotlin answer asynchronously* — the first packets pass while the answer is in flight, and
one HTTP response is all an attacker needs to read the server IP, so a race here is not a
performance detail but a hole.

**Decision:** Go owns the *mechanism* and nothing else. Each datapath exposes a small
`PacketFilter`-shaped interface with a single `Allow(network, srcIP, srcPort, dstIP,
dstPort) bool`, defaulting to nil — meaning allow everything. The *policy* —
resolving the owner and applying include/exclude — lives in Kotlin's
`StrictSplitTunnelGuard` (`amnezia-client/client/android/utils/.../net/`). No packet of a
flow leaves before its verdict. On the Xray path the forwarder simply waits for the call.
On the AmneziaWG path the call runs on a worker, and the flow's first packets are
copied and held until the answer arrives. That makes it asynchronous for the tun reader
but not for the flow ([[G15]]). What stays rejected is passing packets while the answer
is in flight, not answering off the reader.

**Consequences:** one contract, expressed through two different bridges — gomobile for
the Xray path (generated, typed) and hand-written cgo + JNI for AmneziaWG ([[A09]]).
Because the boundary is a contract rather than a
layer of either side, it is documented here and not on a subsystem page. gomobile maps
Go `int` to Java `long`, so the Kotlin override takes `Long` ports — a mismatch there
compiles on the Go side and fails only at binding time ([[G02]]).
*Divergence from upstream:* `amnezia-libxray` gains two exported functions and one
interface, following its existing `RegisterDialerController` pattern; upstream has not
touched that file, so the merge surface is minimal.

## A03. An unresolved owner is denied, not allowed

**Context:** `getConnectionOwnerUid` returns `INVALID_UID` when no socket matches the
5-tuple — and also when the owner is not under our VPN, which is the common case ([[G08]]).
The filter has to decide what that means.

**Alternatives:** *Fail open* — never breaks a legitimate app, but leaves a hole exactly
where an adversary would aim. The threat model here is a state actor with an interest in
learning the server's IP, so a documented "if the lookup fails, we let it through" is an
invitation. *Fail closed* — risks tearing down a legitimate connection if the lookup is
flaky.

**Decision:** deny. The reasoning that makes this safe: a packet reaching the tun with no
owning socket requires a raw socket, which requires `CAP_NET_RAW`, which requires root —
and a rooted device defeats any userspace control anyway, so it is out of scope. A
non-root app's traffic always has an owning socket, so a legitimate flow resolves. There
is no retry. The guard used to re-query once before denying, to absorb a race that was
never observed. [[G08]] showed that `INVALID_UID` is the platform's deliberate answer for
an owner outside the VPN. For an owner that cannot be found at all, the retry ran the
platform's most expensive lookup twice ([[G15]]). It was removed on 2026-09-25.

The same fail-closed rule covers overload. On the AmneziaWG path, when 256 flows are
already waiting for a verdict, packets of a new flow are dropped without asking, and
that drop is not cached ([[G15]]). It also covers a datagram whose socket was closed
before its owner was looked up, even from an allowed app ([[G16]]).

The same rule covers packets that carry no owner at all. While the filter is installed, the
AmneziaWG hook drops what it cannot attribute — non-TCP/UDP protocols, IPv4 fragments, IPv6
with extension headers — because an unprivileged ping socket bound to `tun0` otherwise
walks through ([[G11]]).

**Consequences:** the hole is closed without a realistic false-deny risk, provided a flow
is judged when it opens: a socket the app has already closed belongs to UID 0 ([[G09]]).
Traffic Android sends on its own behalf, not on an app's, is the one real casualty — see
[[A10]]. If a future
Android release changes the visibility rules, this becomes a connectivity bug that will
look like "the VPN randomly drops connections" — hence invariant 3 in
[overview.md](overview.md): loosening it is a decision for the user, not a fix.

## A04. A per-flow decision cache, in a different layer for each datapath

**Context:** crossing into Kotlin costs — a JNI transition plus a binder call into the
system server. How often that happens depends on the datapath, and the two differ.

**Decision:** put the cache where the crossing would otherwise be frequent.
*Xray path:* the gVisor forwarder already fires once per connection, so it needs no cache
at all. *AmneziaWG path:* the hook is per **packet**, so a bare call would cross the
bridge for every packet of every flow. For TCP the Go package `amneziawg-go/uidfilter`
judges only packets with SYN set, which makes it one decision per connection like the
Xray path: a connection whose SYN was denied never exists, so every later packet belongs
to an allowed one. Judging later packets was wrong, not just wasteful — see [[G09]].
Every SYN is judged and none is cached. For UDP it caches the verdict per **full
5-tuple**, TTL 10 s on a coarse clock ([[G12]]), capped at 4096 entries, and asks only
on a miss.

The cache and the flows waiting for a verdict belong to one device: a `uidfilter.Gate` in
`Device.tun`, owned by that device's tun reader and not locked. The filter, its workers
and the clock are process-wide, in a `holder`. A gate that sees a new holder starts
afresh, so `Set` changes the filter and invalidates every cache in one atomic store.

**Revised 2026-09-25**, after two reviews of amneziawg-go#199 by @izhddm. Both caches were
keyed on the source alone, and a verdict outlived its socket. A full 5-tuple narrows that
but does not close it, which is why TCP is no longer cached at all ([[G14]]). The cache
was also process-global, which assumed one tun reader per process. Kotlin's guard used
to keep a second cache, and now keeps no state.

**Consequences:** the expensive lookup happens about once per TCP connection and about
once per UDP flow per 10 s, and there is one cache, on the side of the bridge where the
packets are. What remains is a UDP window of at most the TTL: a socket that takes over a
5-tuple just closed by an allowed app inherits its verdict. That needs the same source
port and the same destination, and it is stated, not hidden ([[G14]]). A policy change
takes effect on the next packet, because the toggle is read at tunnel start and `Set`
replaces every gate's state.

## A05. The toggle mirrors killSwitch and is off by default

**Context:** the feature changes behaviour and costs something, so it needs to be the
user's choice; and a change destined for upstream should look like code upstream already
has.

**Decision:** reproduce the existing `killSwitchEnabled` chain end to end for
`strictSplitTunneling`: a key in `configKeys.h`, a getter/setter pair in
`secureAppSettingsRepository` (stored as `Conf/strictSplitTunneling`, default `false`),
a pass-through in `settingsController` including backup/restore, and a `Q_PROPERTY` in
`settingsUiController`. The flag travels to the service inside the Android VPN config and
is read as `config.optBoolean("strictSplitTunneling", false)` in `Wireguard.kt` (and
`Xray.kt` on the working branch). The Russian UI string is «Строгое раздельное
туннелирование».

**UI, revised 2026-09-22.** The first version put a `HeaderTypeWithSwitcher` on the app
split-tunnelling page; its large header squeezed the app list. The switch is now one
`SwitcherType` component, `Components/StrictSplitTunnelingSwitcher.qml`, placed in the
home split-tunnelling drawer and in Settings → Connection, both under the app
split-tunnelling row; the app page is identical to upstream again. It is enabled only
when app split tunneling is on, the default server's **protocol** is AmneziaWG or
WireGuard ([[G10]]), and the VPN is not connected — the setting is read at tunnel start,
as the rest of split tunneling is. Turning it on first shows a question drawer that
explains the trade-off, including the Private DNS limit of [[A10]].

**Consequences:** off by default means the filter is never registered, so the disabled
path is not merely cheap but absent — which is invariant 1 in [overview.md](overview.md).
The change touches nine files of the settings chain, and following the existing pattern
exactly is what keeps that diff reviewable. *Divergence from upstream:* every one of
those nine files is one upstream also edits, so this is where a future rebase will meet
conflicts — though the pattern itself survived 90 upstream commits unchanged, and the
one file that did conflict was the regenerated translation catalogue ([[G05]]).

## A06. tun2socks is forked from tag v2.5.6, not from `main-amnezia`

**Context:** `amnezia-tun2socks` has several branches and tags, and the obvious-looking
default branch is not the code that ships.

**Decision:** branch from tag `v2.5.6` (`6869b12`) — the version `amnezia-libxray`
declares in its `go.mod`, and simultaneously the newest code in the repository.

**Consequences:** the fork is built on the same commit the release consumes, so the
filter compiles against the gVisor API the `.aar` actually links. The first attempt used
`main-amnezia` and produced a build failure that looked like a dependency problem and was
really a base problem — the full trap is [[G01]]. *Divergence from upstream:* none
structurally; the branch is one commit ahead of a tag that upstream has not moved since
February 2026.

## A07. Each fork is pinned by an immutable id, and conan consumes ours by version

**Context:** three of the five repositories depend on one another. `amnezia-client` takes
`amnezia-libxray` through a conan recipe that downloads a release archive, and
`amnezia-libxray` takes `amnezia-tun2socks` through `go.mod`. Our changes live in forks of
all three, so a build that does not know about the forks quietly produces an app without
the feature — which is what blocked every on-device check until now. Two things are ruled
out from the start: depending on a developer's local checkout, and depending on a name
somebody can move.

**Alternatives:** *In `go.mod`* — a path `replace` to the sibling clone cannot work, the
build runs inside a conan cache where no sibling exists ([[G04]]). A fork **tag** works
until the tag is rebuilt after a rebase: `proxy.golang.org` keeps serving the content it
cached under that name forever, so the checksum database and the repository disagree, and
nothing says so. *In the recipe* — a second entry in `patches/`, carrying the bridge as a
patch over the upstream archive, keeps the upstream source URL but splits the truth
between a commit in the fork and a patch file that has to be regenerated in step with it.

**Decision:** pin by identifiers that cannot be moved, and let our conan package carry its
own identity. `go.mod` redirects `amnezia-tun2socks` to the fork by **pseudo-version**
(`v2.0.0-<utc>-<sha12>`, computed by `go mod tidy`), mirroring the `xray-core` redirect
upstream already keeps three lines above. The recipe's `source()` points at
`archive/<full sha>.zip` of our `amnezia-libxray` fork, and its `version` becomes
`1.0.3-strict.1`, required exactly from the root `conanfile.py`.

**Consequences:** an ordinary configure builds the feature in, with no manual step and no
environment variable. The separate recipe version also closes the prebuilt-remote risk
structurally rather than by luck — the project adds the Artifactory `client-prebuilts`
remote on every configure, but holds no package of that version, so there is nothing to
download in place of our build. Two standing costs follow. The `sha256` in the recipe must
be recomputed after every push to the libxray fork; it fails loudly, but it fails every
time. And GitHub's generated archives carry no byte-stability guarantee, so a future
mismatch is something to recognise rather than debug. *Divergence from upstream:* the
recipe edit and the root `requires` are **fork-only** and have no place in a PR. Once the
bridge is merged and upstream tags a release, both collapse into an ordinary version bump
and the `go.mod` redirect disappears entirely.

The AmneziaWG path follows the same pattern one level deeper. `amneziawg-android`'s
`libwg-go/go.mod` redirects `amneziawg-go` to our fork by pseudo-version.
`recipes/awg-android` clones the `amneziawg-android` fork and checks out a pinned commit,
under version `3.1.20260814-strict.N`. This recipe fetches with `git clone`, not an archive,
so there is no `sha256` to recompute. After a push to the fork `_commit` changes, and the
`strict.N` suffix goes up with it here and in the root `conanfile.py` (now `strict.5`).

## A08. Test builds go through the stock `--sign` path, signed with the Android debug key

**Context:** an installable APK has to be signed, and the release key lives in CI secrets
we do not have. `deploy/build.sh` offers one signing switch, `--sign`, which makes both
Gradle and `androiddeployqt` sign with whatever keystore the `QT_ANDROID_KEYSTORE_*`
variables name. The key is not baked into the project.

**Alternatives:** *a Debug build*, which Gradle signs on its own, departs from what CI
builds and needs a second set of prebuilts to match. *An unsigned Release plus a manual
`zipalign`/`apksigner` pass*, as the old `tag-deploy.yml` did, works but keeps a step
outside the build that nobody else runs.

**Decision:** Release, exactly the CI invocation, with the three variables pointing at the
standard Android debug keystore (`androiddebugkey` / `android`). The command is
`deploy/build.sh -t android --abi arm64-v8a --sign --build deploy/build/arm64-v8a` with
those variables exported; the result is `AmneziaVPN.apk` in the build tree, under
`client/android-build`.

**Consequences:** the build we test is byte-for-byte the build CI makes, apart from the
certificate. That certificate is also the cost: Android refuses to update an app signed by
a different key, so our APK **cannot be installed over the store build of AmneziaVPN**.
The store build has to be uninstalled first, and its configurations go with it, so export
them before on-device work. *Divergence from upstream:* none. This is a local choice of key,
not a change to any file.

## A09. The AmneziaWG bridge is a hand-written JNI upcall on the Go thread

**Context:** [[A02]] needs the AmneziaWG datapath to ask Kotlin who owns a new flow, and
to get the answer before any packet of that flow leaves. Unlike the Xray side there is no gomobile here: `libwg-go.so` is a cgo
`c-shared` library, its JNI entry points are written by hand in
`amneziawg-android/tunnel/tools/libwg-go/jni.c`, and `amnezia-client` keeps its own Kotlin
copy of the `GoBackend` declarations. The question arrives from one of `uidfilter`'s
worker goroutines ([[G15]]), on a Go thread the JVM has never seen.

**Alternatives:** *Push a UID set down to Go* — Go still cannot map a packet to a UID
([[G03]]). *Answer asynchronously from a Java thread polling a queue* — the race [[A02]]
already rules out. *Attach and detach the thread around every call* — correct, but pays an
attach per new flow on the hot path. *Look the callback class up with `FindClass` at call
time* — from a native-attached thread `FindClass` sees only the system class loader, so
app classes are invisible.

**Decision:** `api-android.go` gains `jniUidFilter`, a `uidfilter.PacketFilter` that calls a
C function in `jni.c`, and an exported `awgSetUidFilter(enabled)` that installs or clears
it. `jni.c` gains `GoBackend.awgSetUidFilter(UidFilter?)`: at registration, on a Java
thread, it takes a global reference to the object and resolves `allow` through
`GetObjectClass`, so the interface's class name does not matter to C. In the upcall the Go
thread is attached once, as a daemon, and a `pthread_key` destructor detaches it when the
thread exits. Every call runs inside `PushLocalFrame`/`PopLocalFrame`, since a thread that
never returns to Java never frees its local references. A mutex guards the registration
only. Under it the upcall takes a local reference to the filter, then calls Java without
the lock, so the four workers can wait on the platform at the same time. Until
2026-09-25 the lock was held across the call and serialized every lookup. Each worker is
pinned to its OS thread (`runtime.LockOSThread`), so exactly four threads get attached.
When `Set` replaces the filter, the workers exit, their threads exit with them, and the
pthread key detaches them. No reference, a failed attach, or a Java exception means deny
([[A03]]). Kotlin passes a
`fun interface UidFilter` whose ports are `Int`, because JNI here is written by hand and
takes `int`. [[G02]]'s `Long` belongs to gomobile only.

**Consequences:** both datapaths now share one policy object, `StrictSplitTunnelGuard`, built
by `createOrNull`, and differ only in the bridge. The filter is process-global, like the
Xray one, and `Awg` inherits it from `Wireguard`, so plain WireGuard is covered too. In
`Wireguard.start()` the filter is registered immediately before `awgTurnOn`, because the
reconnect path calls `turnOffVpn()` earlier in the same block and that clears it. With no
filter registered nothing crosses the bridge ([[A05]]). JNI mistakes compile silently and
fail only at run time. The first sign of trouble is in logcat, and CheckJNI is off in the
Release build ([[A08]]). *Divergence from upstream:* additive — one exported Go function,
one C entry point with its helpers, one Java declaration plus an interface; no existing
line of `api-android.go` or `jni.c` changes. The fork additionally pins `amneziawg-go` by
pseudo-version in `libwg-go/go.mod` and moves the Android path from `v3.1.20260814` to
`v3.1.20260828` + the filter, and `recipes/awg-android` clones the fork at a commit. Both
are fork-only ([[A07]]).

## A10. Include mode with strict filtering does not support Private DNS by hostname

**Context:** in include mode the system DNS resolver is not under our VPN, so the platform
hides the owner of its sockets ([[G08]]) and the guard denies them. With Private DNS set to
a provider hostname, the resolver first looks the hostname up in plain DNS over the
tunnel, and that lookup is denied. Android then flags the VPN network `PrivateDnsBroken`,
shows "no internet", and listed apps resolve nothing. In automatic mode only the DoT
attempts on `:853` are denied and Android falls back to plain DNS, which carries the app's
UID and passes. Measured on 2026-09-21, see the journal.

**Alternatives:** *Allow the VPN's DNS servers on `:53` and `:853`* — an app outside the
list binds to `tun0`, asks `whoami.cloudflare` there, and reads the server's IP back:
the same leak, one port over. *Allow ownerless traffic to those servers only* — the
excluded app's bypass is ownerless too, so this is the same hole. *Add the resolver to the
VPN* — `addAllowedApplication` takes packages, and the resolver has none.

**Decision:** no code change. Document the limitation: in include mode with strict
filtering, Private DNS must be off or automatic. Exclude mode is unaffected, because
system UIDs are inside its ranges.

**Consequences:** one combination of settings breaks DNS for the listed apps with an
honest "no internet" signal rather than silently. The PR text states the limitation. A UI
hint next to the toggle was considered and left out of this series. *Divergence from
upstream:* none.
