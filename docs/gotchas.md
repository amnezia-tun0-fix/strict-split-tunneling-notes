# Gotchas

Traps that have already cost time and will again.

**Trigger:** debugging ran past 30 minutes with a non-obvious cause → write the entry
now, not later. Full format and guidance: `FORMATS.md` of the standard.

A trap that would break the same way in *any* project on this machine is not a `G##` —
it belongs to the shared environment store. See `_meta.md`.

- **G01** · `main-amnezia` looks like the current tun2socks branch and is a dead end
- **G02** · Ports arrive as `Long` on the Kotlin side of a gomobile interface
- **G03** · `/proc/net/tcp` shows nothing but the app's own sockets
- **G04** · A `replace` pointing at a sibling checkout never reaches the real build
- **G05** · Rebasing amnezia-client conflicts across the whole translation catalogue
- **G06** · The AmneziaWG hook lands one line above where it belongs
- **G07** · There is nowhere to put a Kotlin unit test in amnezia-client
- **G08** · `INVALID_UID` also means "this socket's owner is not under our VPN"
- **G09** · A socket the app has closed belongs to UID 0
- **G10** · AmneziaWG has two containers, and a check for one misses the other
- **G11** · Any app can ping through tun0, and ping has no owner to look up
- **G12** · `time.Now()` costs more than the cache lookup it guards
- **G13** · One entry in a VPN's app list covers every copy of the app, each with its own uid
- **G14** · A flow key outlives the socket it was made for
- **G15** · A lookup on the tun reader lets any app stall the whole tunnel
- **G16** · A datagram sent from a socket closed at once is dropped, even from an allowed app
- **G17** · An app inside the VPN loses TCP when it binds its socket to tun0
- **G18** · An error thrown when the Android VPN service starts never reaches the user as text
- **G19** · A verdict cache that resets on overflow lets any app evict allowed UDP flows
- **G20** · An active UDP flow loses packets every time its cached verdict expires
- **G21** · A burst that opens a UDP flow keeps only its first four packets
- **G22** · A connection into a listed app through the tunnel never completes in include mode
- **G23** · A UDP datagram larger than the tunnel MTU never leaves, even from an allowed app
- **G24** · The VPN service dies when the filter's workers exit, and leaves no tombstone
- **G25** · A build with another applicationId never finds its own running VPN service

## G01. `main-amnezia` looks like the current tun2socks branch and is a dead end

**Context:** choosing a base to fork `amnezia-tun2socks` from, before writing the filter.

**Symptom:** the branch named like a default (`main-amnezia`) is checked out by a fresh
clone, so it looks like the place to work. Building `amnezia-libxray` against a fork
based on it fails with `no required module provides package
gvisor.dev/gvisor/pkg/tcpip/link/rawfile` — which reads like a dependency problem and
is really a base problem. Worse, comparing the feature branch against `main-amnezia`
reports it as "1 commit behind", which invites a rebase onto it.

**Cause:** `main-amnezia` is tag `v2.5.4` from June 2024 and has **diverged**: one commit
unique to it against 99 it does not have. The code that actually ships is tag `v2.5.6`
(`6869b12`), which `amnezia-libxray`'s `go.mod` requires. Two further confusions sit on
top: `v2.5.6` and `v2.6.2` are **the same commit**, so the "newer" tag is an alias and
not an upgrade; and that commit is also `upstream/main`, so upstream has not moved since
February 2026. On the old base the gVisor API differs enough that the UDP hook does not
even compile — the forwarder callback there returns nothing, so `return false` is a type
error.

**Fix:** base on `v2.5.6`. Compare the feature branch against **that tag**, never against
`main-amnezia` — see [[A06]].

**How to spot it:** `git rev-list -n1 v2.5.6` and `git rev-list -n1 v2.6.2` printing the
same hash is the tell that the tags are aliases. If a diff against a branch shows ~100
commits of what is plainly upstream history, you are comparing against a divergent
branch, not measuring your own work.

## G02. Ports arrive as `Long` on the Kotlin side of a gomobile interface

**Context:** writing the Kotlin implementation of the `UidFilterController` interface
that Go declares and gomobile binds.

**Symptom:** a Kotlin `override fun allow(..., srcPort: Int, ...)` does not override
anything. The class fails to compile against the generated binding, or — worse, if the
signature happens to be satisfiable — the interface is silently not implemented.

**Cause:** gomobile maps Go's `int` to Java's `long`, because Go's `int` is 64-bit on the
platforms it targets. It also lower-cases the first letter of method names, so Go's
`Allow` is Java's `allow`. Neither is visible from the Go source, and the Go side
compiles happily either way — the mismatch only exists in the generated bindings.

**Fix:** declare ports as `Long` in the Kotlin override and convert at the call site.
The neighbouring `Logger` interface in the same `.aar` is the reference: Go's `Write`
appears as Kotlin's `write` returning `Long`.

**How to spot it:** unzip the built `.aar`, read `classes.jar`, and check the descriptor
of the generated interface. `(Ljava/lang/String;Ljava/lang/String;JLjava/lang/String;J)Z`
means two `String`s, a `long`, a `String`, a `long` → `boolean`. Doing this once, before
writing the Kotlin, is far cheaper than discovering it at build time.

**Portable:** yes — any Go↔Java binding generated by gomobile

## G03. `/proc/net/tcp` shows nothing but the app's own sockets

**Context:** looking for a way to resolve the owning UID of a connection from Go, to
avoid building a bridge back into Java.

**Symptom:** reading `/proc/net/tcp` from inside the app returns a plausible-looking
table that never contains the connection being looked for, so every lookup fails and —
under a fail-closed policy — everything is denied.

**Cause:** since Android 10 the procfs network tables are filtered per UID: a process
sees only its own sockets. The privileged view is reachable only through
`ConnectivityManager.getConnectionOwnerUid`, which the system grants to the app that is
the currently active `VpnService`. There is no Go equivalent, and a raw netlink
`SOCK_DIAG` query does not carry that privilege either.

**Fix:** do not resolve the owner in Go at all. Cross into Kotlin and ask the platform —
this is the whole reason the bridge exists, [[A02]].

**How to spot it:** a UID lookup that works on an old device or an emulator image and
returns nothing on anything modern. The API level, not the code, is the variable.

**Portable:** yes — Android networking introspection from native code

## G04. A `replace` pointing at a sibling checkout never reaches the real build

**Context:** getting the filter into a built `.aar`, so the Kotlin side has something to
compile against and the shipped app picks the change up on its own.

**Symptom:** two shapes, a year apart. The older one is silent — the build succeeds and
produces an `.aar` without the changes, because the `replace` is simply gone from
`go.mod` afterwards. The newer one is loud — once the build runs under conan it fails
with `replacement directory ../amnezia-tun2socks does not exist`.

**Cause:** the silent shape was `prepare_go()` in `build.sh`, which used to run
`rm -f go.mod; go mod init; go mod tidy` and regenerate the module file from scratch.
Upstream reduced it to a bare `go mod tidy` in `0c352e2` (2026-07-10), so that failure
mode is gone and the check it called for no longer tells you anything. What remains is
structural and permanent: conan unpacks the recipe's `source()` into its own cache, and
no sibling checkout exists there. A path-based `replace` is a statement about one
developer's disk, and the build that produces the shipped artefact never runs on it.

**Fix:** redirect the module to the fork and pin it by **pseudo-version** — not by a
path, and not by a tag, which can be moved after `proxy.golang.org` has cached it.
`go mod edit -replace=<old>=<fork>@<full sha>` followed by `go mod tidy` computes the
canonical form. This mirrors the `xray-core` redirect upstream already keeps three lines
above in the same file. The whole chain is [[A07]].

**How to spot it:** `git diff go.mod` after a build used to be the check and is now
worthless. Check the artefact instead — unzip the `.aar` and look for the expected class.
Any `replace` whose right-hand side begins with `.` or `/` will not survive contact with
a build that is not yours. The fork redirect is fork-only as well: a `pr/*` branch must
carry neither shape. The pre-push hook from `tools/preflight.py` refuses such a push.

## G05. Rebasing amnezia-client conflicts across the whole translation catalogue

**Context:** rebasing the feature branch onto an upstream that had moved 90 commits.

**Symptom:** every source file rebases cleanly, and
`client/translations/amneziavpn_ru_RU.ts` produces a conflict spanning thousands of
lines, with the relevant context hundreds of lines away from where it used to be.

**Cause:** the `.ts` catalogues are generated by `lupdate`, and upstream regenerates them
wholesale. Line numbers in every `<location>` shift, contexts move, and the file is
effectively rewritten between releases — so a three-line hunk of ours has no stable
surroundings to anchor to.

**Fix:** do not resolve it line by line. Take the upstream version of the file whole
(`git checkout --ours` during a rebase), then re-add the handful of `<message>` blocks by
hand into the right `<context>`. The `<location line=…>` numbers can be approximate —
the next `lupdate` rewrites them anyway. Validate afterwards: the file must still parse
as XML.

**How to spot it:** a conflict whose diff is measured in thousands of lines in a file
nobody edited by hand. That is a generated artefact, and generated artefacts are
regenerated, not merged.

## G06. The AmneziaWG hook lands one line above where it belongs

**Context:** rebasing `amneziawg-go` onto upstream after it moved to the 3.x series.

**Symptom:** the hook still applies and still compiles, but it now runs before a field
the upstream sets on the same element — so it operates on a half-initialised structure.
Nothing fails loudly.

**Cause:** the hook is anchored between `elem.packet = bufs[i][offset : offset+sizes[i]]`
and the `// lookup peer` comment. Upstream inserted `elem.padding = padding` into exactly
that gap when it added header protection. Git's three-line context overlaps the
insertion, so the merge can place our block on either side of the new line.

**Fix:** the hook goes **after** `elem.padding = padding`. Semantics are unaffected —
`elem.packet` is already sliced — but keeping the element fully initialised before the
filter runs is the safer order and matches the surrounding code. Also note the module
was renamed to `github.com/amnezia-vpn/amneziawg-go/v3`, so the import line needs `/v3`.

**How to spot it:** after any rebase of this repo, read the ten lines around the anchor
rather than trusting a clean `git status`. This is a conflict git can resolve *plausibly*
and wrongly. `python tools/preflight.py` checks the order on every local branch, and its
pre-push hook refuses to push a branch where the hook does not follow the anchor.

## G07. There is nowhere to put a Kotlin unit test in amnezia-client

**Context:** wanting to test the UID policy in `StrictSplitTunnelGuard` the way the Go
filters are tested.

**Symptom:** there is no obvious place to add a test, and adding one the usual way drags
in test infrastructure the project does not have.

**Cause:** the Android modules of `amnezia-client` carry no unit-test setup at all — no
`src/test` anywhere, no JUnit in `gradle/libs.versions.toml`, no `testImplementation` in
any module. This is deliberate on upstream's part, not an oversight to correct in a
feature PR.

**Fix:** do not bolt scaffolding onto a PR that is about something else. Keep the
decision logic pure and injectable instead — `StrictSplitTunnelGuard` takes its UID
resolver as a parameter precisely so the policy can be exercised without Android — and
verify by review plus a compile of the affected modules.

**How to spot it:** `gradlew :utils:compileReleaseKotlin` works, and there is no
`:utils:test` task worth running.

## G08. `INVALID_UID` also means "this socket's owner is not under our VPN"

**Context:** reading the guard's `deny ... owner uid unresolved` lines in logcat, and a
brief include-mode run in which DNS-over-TLS flows to `1.1.1.1:853` were denied.

**Symptom:** the log says the lookup failed, which reads as a flaky platform call or a
race. In exclude mode it fires for every bypass attempt of an excluded app; in include
mode it fires for traffic that is not from any app at all.

**Cause:** the lookup does not fail. `ConnectivityService.getConnectionOwnerUid` (AOSP,
`main`) finds the socket and then filters the answer for a non-privileged caller:

```java
if (uid == INVALID_UID) return uid;  // Not found.
if (hasNetworkStackPermission()) return uid;
final NetworkAgentInfo vpn = getVpnForUid(uid);
if (vpn == null || !isVpnServiceVpn(vpn)
        || vpn.networkCapabilities.getOwnerUid() != mDeps.getCallingUid()) {
    return INVALID_UID;
}
```

So a VPN app learns an owner only if **its own VPN applies to that UID**. Everything else —
an excluded app, an app outside the include list, the system DNS resolver when it is not
covered — comes back as `INVALID_UID`, the same value as "no such socket".

**Fix:** know that the guard's `INVALID_UID` branch is the one doing the work, not
`uid !in appUids`. In exclude mode that is correct: excluded apps are denied either way. In
include mode it also catches system traffic routed into the tunnel, which is how Private
DNS gets denied — see `status.md`. Never "fix" it by allowing `INVALID_UID` ([[A03]]): that
is exactly the excluded app's bypass.

**How to spot it:** a deny for a flow whose owner is known to be outside the VPN (the
excluded app, the resolver's `:853`) is this, not a bug. A genuinely failed lookup would
also hit apps that *are* under the VPN, though an allowed app that closes its socket at
once ([[G16]]) or binds TCP to `tun0` ([[G17]]) gets the same answer. Since amnezia-client
`3e9a6978` the guard logs denials at debug level. A release build prints them only with
saving logs turned on in the app.

## G09. A socket the app has closed belongs to UID 0

**Context:** the first include-mode run with the filter on, 2026-09-21. Chrome was in the
list and browsing worked.

**Symptom:** from the moment Chrome started, the guard denied hundreds of flows per
minute to ordinary sites on `:443`, all "owner unresolved". They look like an app bypassing
the tunnel, but nothing shows up in `SYN_SENT`: polling `/proc/net/tcp` for the tun
address finds only listed apps and sockets in `FIN_WAIT1`, `LAST_ACK` and `CLOSING` owned
by UID 0 — to the same addresses the guard denied.

**Cause:** once an app calls `close()`, the kernel orphans the socket and it no longer has
an owner; `sock_diag`, and so `getConnectionOwnerUid`, reports UID 0. The AmneziaWG hook
judged every packet and cached the verdict for 10s, so a connection idle longer than that
had its FIN judged afresh. In include mode UID 0 is outside the VPN, the platform answers
`INVALID_UID` ([[G08]]), and the FIN was dropped. In exclude mode UID 0 is inside the VPN,
which is why the first device runs never showed it.

**Fix:** judge a TCP flow only on packets with SYN set ([[A04]]). The Xray path was never
affected: gVisor's forwarder asks once, when the connection opens.

**How to spot it:** from `adb shell`, `/proc/net/tcp` shows every UID, and a UID of 0 on a
closing state is this. A real bypass leaves a socket in `SYN_SENT` with the app's UID.

## G10. AmneziaWG has two containers, and a check for one misses the other

**Context:** enabling the strict switch only for the protocols that enforce it, by
testing the default server's container in `ServersUiController`.

**Symptom:** the switch stays disabled on a server that plainly runs AmneziaWG and
connects through the AmneziaWG datapath. No warning anywhere: the release build does not
log QML binding problems, and the property simply returns `false`.

**Cause:** `DockerContainer` has both `Awg` and `Awg2` (AmneziaWG 2.0). Current servers
use `Awg2`, and a test written as `container == Awg || container == WireGuard` misses it.
Upstream's own `isDefaultServerDefaultContainerHasSplitTunneling` reads the same way, which
is what made the pattern look safe to copy.

**Fix:** ask for the protocol, not the container: `ContainerUtils::defaultProtocol()` maps
`Awg` and `Awg2` to `Proto::Awg`, the same way `vpnProtocol.cpp` picks the datapath.

**How to spot it:** any `DockerContainer::Awg` comparison in new code. Test on a server
installed recently, not only on an old one.

## G11. Any app can ping through tun0, and ping has no owner to look up

**Context:** comparing our filter with another contributor's proposal
(amnezia-vpn/amneziawg-go#174) before writing the PR texts, 2026-09-23. That proposal drops
every packet it cannot identify; ours passed everything that was not TCP or UDP.

**Symptom:** with strict mode on and the TCP/UDP probe at 0/6, an app outside the VPN still
gets ICMP echo replies through `tun0`, at tunnel latency. Nothing in the guard's log: it is
never asked.

**Cause:** Android lets any app open an unprivileged ICMP ping socket
(`socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP)`); no root, no permission. `SO_BINDTODEVICE`
works on it like on any socket, and the echo reaches a host the app controls from the VPN
server's address. `getConnectionOwnerUid` answers for TCP and UDP only, so an owner-based
filter cannot judge it — and "cannot judge" had been implemented as "allow".

**Fix:** while a filter is installed, drop what cannot be attributed: other protocols,
IPv4 fragments, IPv6 with extension headers ([[A03]]). The cost: ping and ICMP traceroute
(`-I`) stop working inside the tunnel for listed apps in strict mode, and so does the
ICMP the phone's kernel sends on its own: a ping from another peer to the phone's tunnel
address got 0 of 5 echo replies, twice (2026-09-28, `evidence/research-2026-09-28/m3-inbound.txt`).
Large UDP datagrams are the other casualty ([[G23]]). Plain traceroute sends UDP and keeps
working: from Termux, UDP probes with rising TTL reached 1.1.1.1 in 10 hops, the answers
read from the socket's error queue (`tools/udp_traceroute.py`, `m6-udp-traceroute.txt`).
Measured: echo via `tun0` times
out with the filter on, answers with it off (`tools/icmp_probe.py`, `evidence/e6-icmp/`).

**How to spot it:** the leak probe tests TCP and UDP; run `icmp_probe.py` next to it. Any
"pass what we cannot parse" branch in a filter meant to be fail-closed is this trap.

## G12. `time.Now()` costs more than the cache lookup it guards

**Context:** a reviewer of amneziawg-go#199 called the per-packet cost of the filter severe.
Measuring it rather than arguing turned up something else.

**Symptom:** the per-flow cache looked cheap — a map lookup on a small key — and measured
114 ns per hit, while parsing the packet took 8.5 ns. The obvious suspects (the map, the
mutex) were not the problem.

**Cause:** `time.Now()` alone was 81 ns of those 114 (linux/amd64, i5-4210U). The cache
read the clock on every lookup to check the entry's TTL, so the guard cost more than what
it guarded. Go's clock is not free: it is a vDSO call, and on some hosts, WSL included,
noticeably slower than on bare metal.

**Fix:** do not read the clock per item; read a coarse clock that something else keeps
current. The first fix read the clock once per 64 lookups and was wrong: nothing advanced
it while the tunnel was idle, so after a pause longer than the TTL an expired verdict was
honoured for up to 63 more packets (found by @izhddm, 2026-09-25). Since `cdee4ba` the
filter's holder runs a ticker that advances an `atomic.Int64` once a second, monotonic and
forward only, and a lookup costs one atomic load. The TTL is off by at most a second.
Dropping the mutex and making the key's protocol a byte took the cached-UDP path from 152
to 65 ns per packet, and the ticker keeps it at about 62 ns.

**How to spot it:** any hot path that checks an expiry, a deadline or a rate limit per
item. Benchmark `time.Now()` on its own first, since it sets the floor for the whole check.
And if the clock is refreshed by the work itself, ask what it reads after a long pause.

**Portable:** yes — any Go hot path with a clock read per item

## G13. One entry in a VPN's app list covers every copy of the app, each with its own uid

**Context:** the maintainer's own phone on the test build `v5.0.3.1-strict.1`, 2026-09-23:
Brave and Chrome Beta listed in "only the apps from the list", both also cloned into MIUI's
XSpace ("dual apps").

**Symptom:** with strict mode on, the original browser loads pages and its clone cannot even
resolve a name (`DNS_PROBE_STARTED`); with strict mode off, the clone works through the
tunnel. The guard's log is silent: zero "owner unresolved" lines.

**Cause:** Android applies a listed package to all its copies, and each copy runs under its
own uid, `user * 100000 + appId`. The VPN's ranges in `dumpsys connectivity` for two listed
apps with app ids 10382 and 10383: `99910382-99910383` (the XSpace clones, user 999),
`20382-20383` and `99920382-99920383` (their SDK sandboxes, app id + 10000, Android 13+).
So the platform routes the clone into the tunnel and `getConnectionOwnerUid` resolves it to
`99910383`. The guard held the base uid from `getPackageUid(name, 0)` and compared
whole uids, so it denied the clone — without a log line, because only unresolved owners
were logged.

**Fix:** compare app ids: `uid % 100000`, with the sandbox range 20000–29999 folded onto
its app (`9ce688c4` in amnezia-client). `UserHandle.getAppId` would do the first part but
is hidden API, and `Process.getAppUidForSdkSandboxUid` is public only from API 35, so the
guard carries the AOSP constants. Denials by the list are logged now, with the uid.

**How to spot it:** a listed app works and its clone, second-space or work-profile copy
does not. `adb shell pm list packages -U` prints every uid a package has
(`com.chrome.beta uid:10383,99910383`); compare them with the VPN's ranges.

**Portable:** yes — any per-app policy on Android that compares uids instead of app ids

## G14. A flow key outlives the socket it was made for

**Context:** the review of amneziawg-go#199 by @izhddm, 2026-09-25, with a test written
against our branch, and their follow-up the same day.

**Symptom:** after an allowed UDP flow from port 40000, a packet from port 40000 to a
destination the filter would deny passes without the filter being asked. A SYN on a
reused port does the same. The reverse also happens: an allowed app that gets a port an
excluded app has just used sees its packets dropped for up to 10 s.

**Cause:** both caches, Go's verdict cache and the Kotlin guard's uid cache, were keyed
on protocol, source address and source port, with a 10 s TTL. A source port identifies a
socket only while that socket lives. Once the socket closes, the kernel hands the port to
the next socket, which may belong to another app. By accident this is rare, since
ephemeral ports are random, but an app can `bind()` a port on purpose. A full 5-tuple
narrows this and does not close it: a new socket can take over the same 5-tuple once the
old one is closed. Any positive cache with a TTL is a window of stale authorisation.

**Fix:** key on the full 5-tuple, and do not cache TCP at all. Every SYN is judged
afresh, and since TCP is judged only on SYN, that costs one lookup per connection, as
before (`cdee4ba`). UDP verdicts stay cached per 5-tuple for 10 s. Taking over a UDP flow
within that window needs the same source port *and* the same destination, right after
an allowed app has closed that very flow. The Kotlin cache is gone (amnezia-client
`37a34134`).

**How to spot it:** any per-flow cache keyed on less than the flow. Ask what happens
when the missing part of the key changes while the rest stays, and what a new owner of
the same key inherits.

**Portable:** yes — any cache of per-connection facts keyed by local port

## G15. A lookup on the tun reader lets any app stall the whole tunnel

**Context:** the same review, measured on a Galaxy S24 FE, Android 16, over AmneziaWG 2,
and re-measured on our Poco F7 (Android 16, kernel 6.6) with `tools/churn_probe`.

**Symptom:** TCP connects through the tunnel slow down while another process opens new
UDP flows. The reviewer's corrected numbers: with sockets held open, so that every owner
resolves and every flow is allowed, 300/s costs nothing visible and 1000/s gives a p50 of
328 ms against 106 ms. With sockets closed right after sending, so that owners are mostly
not found, 300/s already gives a p50 of 263 ms, and at 1000/s 3 of 40 connects time out.
On ours with `strict.2`, 1000 flows/s gave a p50 of 471 ms (max 1.9 s) with sockets held,
and 1085 ms (max 4.3 s, 2 of 40 failed) with sockets closed.

**Cause:** `AllowOutboundPacket` asked the filter synchronously on the goroutine that
reads tun, so every cache miss stopped reading for everyone. The cost behind a miss
depends on the answer. `InetDiagMessage.getConnectionOwnerUid` opens a netlink socket
per call and tries AF_INET6 before AF_INET. An owner outside the VPN is found by exact
match and then hidden as `INVALID_UID` ([[G08]]), which costs two cheap requests. An
owner that is **not found**, for instance because the socket was closed right after
sending, adds two `NLM_F_DUMP` requests that walk the whole UDP table. The guard's retry
on `INVALID_UID` then ran all of it twice. An app can pick that path on purpose just by
closing its socket after `sendto`. The JNI lock held across the call would have
serialized any pool as well. (The first review called a denied flow the expensive case,
and the follow-up corrected it.)

**Fix:** the tun reader never calls the filter now. On a miss it copies the packet into a
per-flow pending list, hands the key to 4 workers and returns to reading. The limits per
device: 4 packets per flow, 1 MiB, 256 flows, and 2 s at most per packet. The verdict
releases or drops what was held, in order, through `Device.ReleaseOutboundPacket`.
Holding matters more than dropping: a dropped first packet costs every new TCP connection
a 1 s SYN retransmit and every DNS query a retry. With the table full, new flows are
dropped and not cached. Established TCP never is, since its packets carry no SYN; an
allowed UDP flow can be, once its verdict leaves the cache ([[G19]]). The JNI lock covers only the
registration, and the retry is gone ([[A03]]). Measured afterwards on the same phone: a
p50 of about 200 ms at every rate up to 5000 flows/s, sockets held or closed, the same as
with the filter off. DNS queries from fresh sockets were answered at the same rate with
and without the filter.

**How to spot it:** any slow call on the path that reads packets. Measure the latency of
other flows while new ones are churning, not only the cost of the call, and make the
churn hit the slowest answer as well as the common one.

**Portable:** yes — any packet loop that makes a blocking call per new flow

## G16. A datagram sent from a socket closed at once is dropped, even from an allowed app

**Context:** the follow-up review of amneziawg-go#199, 2026-09-25: counting the guard's
deny lines during a flood from an app **inside** the VPN.

**Symptom:** at 300 flows/s, 6870 of 7501 flows were denied as "owner unresolved",
although the sending app was allowed. `churn_probe flows` without `-hold` shows the same
on ours: about 6000 denies per run at 300/s, and none with `-hold 2s`.

**Cause:** the owner is looked up after the packet has been read from tun, and by then a
fire-and-forget sender may already have closed its socket. The platform can name only
the owner of a socket that exists, so the answer is `INVALID_UID`, and [[A03]] denies
it. Judging off the reader ([[G15]]) lengthens the gap under load but did not create it:
the synchronous design had the same gap.

**Fix:** none, by design. Allowing unresolved owners is exactly the bypass ([[A03]]).
Such a datagram is dropped, and the hold limit of 2 s bounds how long any packet waits.
Senders that expect an answer keep the socket open until it arrives, so they are not
affected: DNS, STUN, QUIC and the like.

**How to spot it:** "owner unresolved" denies for an app that is allowed, on UDP, in
bursts. Check whether the app closes its socket right after sending. The TCP form is a
single denied SYN with no retransmit behind it. A browser opens connections ahead of time
and cancels some at once, and a few of those show up during ordinary browsing in include
mode (3 in two minutes on 2026-09-25). A real bypass attempt retransmits and is denied
again every second.

**Portable:** no

## G17. An app inside the VPN loses TCP when it binds its socket to tun0

**Context:** the review of amnezia-client#3199 by @izhddm, 2026-09-25, in "all except
listed apps" mode with `adb shell` inside the VPN, confirmed in their re-test of the
reworked branches the same day. Reproduced by us on 2026-09-28 in "only listed apps" mode,
from a listed Termux: `curl --interface tun0` timed out 2 of 2, the same request unbound
answered in 0.8 s, and 19 of 19 DNS queries bound to `tun0` were answered
(`evidence/research-2026-09-28/m7-g17.txt`).

**Symptom:** with strict mode on, TCP with `SO_BINDTODEVICE("tun0")` from an app that *is*
allowed into the tunnel is denied every time as "owner unresolved" (3 of 3). The same
connect without binding works, and UDP bound to `tun0` works as well.
`curl --interface tun0` from an allowed Termux is exactly this case, and it looks like a
broken VPN.

**Cause:** the platform's lookup. `InetDiagMessage` sends the exact-match request with
`ifIndex = 0`, and the kernel's `inet_match` does not match a socket bound to a device
when the request names no interface. So a device-bound TCP socket is never found, and
the answer is `INVALID_UID` ([[A03]]). UDP is found anyway, by the wildcard dump that
follows the failed exact request, because the dump does not compare the interface.

**Fix:** none on the app side. `ConnectivityManager.getConnectionOwnerUid` takes no
interface, so nothing in the public API reaches the right request. It is stated as a
limitation in amnezia-client#3199. Allowing unresolved TCP would reopen the bypass.

**How to spot it:** an allowed app fails only on TCP, only when it binds to `tun0` (look
for `--interface`, `SO_BINDTODEVICE`, "bind to network interface" options), and every SYN
retransmit is denied again.

**Portable:** yes — any use of `getConnectionOwnerUid` for a socket bound to a device

## G18. An error thrown when the Android VPN service starts never reaches the user as text

**Context:** designing a clear message for include mode with strict filtering and Private
DNS by hostname ([[A10]]), 2026-09-26.

**Symptom:** a `VpnStartException("…")` thrown from a protocol's start looks like the
natural way to tell the user why a connection was refused. The user sees only a generic
connection error, and the message ends up in logcat.

**Cause:** `AmneziaVpnService.onError` sends the text to the activity as
`ServiceEvent.ERROR` with `MSG_ERROR`. `AmneziaActivity` logs it and calls
`QtAndroidController.onServiceError()`, which takes no arguments, next to upstream's own
`// todo: add error reporting to Qt`. The Qt side gets the bare `serviceError()` signal.

**Fix:** to show a specific reason, either extend that channel end to end (JNI signature,
`AndroidController`, an error code for QML — upstream's unfinished work, not a side
effect of a feature PR) or tell the user from the Android side, with a notification or a
toast from the service.

**How to spot it:** grep `todo: add error reporting to Qt` in `AmneziaActivity.kt`. If
it is gone, upstream has built the channel and the first option has become cheap.

## G19. A verdict cache that resets on overflow lets any app evict allowed UDP flows

**Context:** a review of `amneziawg-go/uidfilter` against the text of an article about
the fix, 2026-09-28. Found in the code and reproduced with a unit test on a scratch copy;
not measured on a device.

**Symptom:** none visible yet. The reproduction: an allowed UDP flow, then 4200 denied
flows; the cache resets, the allowed flow's verdict is gone, and with 256 flows already
pending its next packet is dropped and never sent.

**Cause:** `decisionCache.put` holds 4096 entries, denied verdicts included. When it is
full of live entries it drops the whole map, allowed verdicts with it. With a 10 s TTL,
about 410 new flows per second keep it full. Any app can produce that through `tun0`,
including one outside the VPN whose flows are all denied. An evicted allowed flow goes
back through `hold`, and if `maxPendingFlows` is reached its packet is dropped
("judged once there is room"). The same happens at every TTL boundary under load. It
does not leak anything: every path still fails closed. It degrades QUIC and calls of
allowed apps.

**Fix:** `0f0382e` on `feat` (`2a9f1f1` on the PR branch). A full cache evicts expired
and denied entries first, and allowed ones only while they alone fill more than seven
eighths of it. A hit refreshes nothing: a sliding TTL would let a socket that took over
a closed allowed flow's 5-tuple keep its verdict for as long as it sends ([[G14]]).
`TestCacheFloodKeepsAllowed` and `TestCacheFullOfAllowedEvictsPart` cover it. On the phone
(recipe `strict.6`): with an excluded app flooding `tun0` at 5000 denied flows/s, fresh DNS
queries of an allowed app were answered 97.7% of the time against 99.5% without the flood,
and TCP connects kept a p50 of 216 ms (`evidence/e8-churn/strict6-ON-denied-flood.txt`).
Repeated with counters on 2026-09-28: 4 workers judge the 5000 denied flows/s at a median
under 1 ms, and in four runs the filter dropped no DNS packet at all (99.0–99.8% answered,
drifting run by run, with 4 or 8 workers alike). Its only drops came at the onset of a flood,
once: 364 flows turned away by a full pending table in the first 5 s
(`evidence/research-2026-09-28/m11-flood.txt`).

**How to spot it:** a cache that holds both outcomes and resets wholesale, next to a
queue with a hard cap. Ask what an attacker who can only produce denied entries does to
the allowed ones.

**Portable:** yes — any bounded verdict cache that an untrusted party can fill

## G20. An active UDP flow loses packets every time its cached verdict expires

**Context:** a review of `amneziawg-go/uidfilter` with tests that pin down current
behaviour, 2026-09-28 (`TestProofExpiredVerdictDropsBurst` on the fork's
`exp/proof-tests`).

**Symptom:** none reported. In the test, an allowed UDP flow sends a burst of 20 packets
right after its cached verdict expires: 4 are sent after the lookup, 16 are dropped. On
the phone (2026-09-28, `tools/udp_flow_probe.py`, one socket sending 20 DNS queries every
100 ms for 60 s): 16 of 200 queries lost about every 10 s, 0.8–1.0% in all, always the
tail of a burst, and the counters showed `udp_expired_rejudged=1 drop_held_cap=16` each
time (`evidence/research-2026-09-28/m1-udp-flow.txt`).

**Cause:** a UDP verdict is cached for `cacheTTL` (10 s) and not refreshed by hits
([[G19]] explains why). When it expires, the next packet of the flow goes through `hold`
as if the flow were new, and while the lookup runs only `maxHeldPerFlow` (4) packets are
kept. Every packet past the fourth is dropped, although the flow was allowed before the
lookup and is allowed after it. This happens to every active UDP flow once per TTL: QUIC,
calls, games. With the pending table full, all its packets are dropped until there is
room ([[G19]], [[G15]]).

**Fix:** `raN` with N = 2, in amneziawg-go#199 since 2026-09-30 (`9c673ef`; `release` and
strict.7 carry it). How it was chosen: two prototypes on the former `exp/lab`, both measured on the phone with
the same probe (`m1-udp-flow.txt`, `m1-udp-flow-ra2.txt`; the filter removed: 0.14%, no
10 s rhythm, `ctl-strictOFF.txt`):
- `rv` keeps passing the flow on its expired allowed verdict while it is judged again, for
  at most `maxHoldTime`. Loss 0.14% and 0.32% against 0.8–1.0% without it, the rhythm
  gone. It lets a socket that took over the 5-tuple ([[G14]]) pass up to 2 s longer.
- `raN` (`7682a4d`) judges an active allowed flow again in the background once its
  verdict is N seconds old, while it is still valid. Nothing waits and nothing passes on a
  verdict older than `cacheTTL`, and a socket that takes over the 5-tuple is denied about N
  seconds after the lookup it inherited instead of up to `cacheTTL`. With `ra2`: 0.41% and
  0.22%, the rhythm gone, one background lookup every 2–3 s for the active flow, at most
  6 ms each; the one burst of 16 lost in a run fell in a 5 s window where the counters show
  no drop at all. The cached-UDP path costs the same within noise (shuffled benchmarks,
  `BenchmarkExpCachedUDP*`).

Holding more packets per flow keeps the rule that nothing passes without a fresh verdict
but stalls the flow for the lookup and still drops under load.

**How to spot it:** loss on long-lived UDP flows in strict mode, in bursts about 10 s
apart. The lab build logs `refresh_started` and `drop_held_cap` under the tag
`AmneziaWG/uidfilter`.

**Portable:** yes — any verdict cache with a TTL in front of a per-flow hold with a cap

## G21. A burst that opens a UDP flow keeps only its first four packets

**Context:** device measurements with the experimental build, 2026-09-28
(`tools/udp_flow_probe.py`, counters of the fork's former `exp/lab`).

**Symptom:** a new UDP socket in a listed app sends 20 datagrams back to back: 4 arrive,
16 are lost, in 3 of 3 runs. Every run of the long-flow probe loses the same 16 in its
first second, whatever the options. With 16 packets held per flow the loss is 4 of 20,
also 3 of 3 (`evidence/research-2026-09-28/m8-first-burst.txt`).

**Cause:** the first packet of a flow waits for its owner lookup, 2–5 ms on this phone,
and only `maxHeldPerFlow` (4) packets are held meanwhile; the rest are dropped
(`drop_held_cap`). The cap was chosen for a SYN and its retransmit or a DNS query and its
retry. A sender that puts more than four datagrams on a new flow before its first answer
loses the tail and waits for its own retransmit timer.

**Fix:** the cap is 16, in amneziawg-go#199 since 2026-09-30 (`35f643f`). It costs memory
only inside the existing 1 MiB bound per device, and packets older than `maxHoldTime` are
dropped anyway. The lab build takes the cap from its `hN` option.

**How to spot it:** loss only at the start of UDP flows, never later; `drop_held_cap` in
the first report after a flow opens.

**Portable:** yes — any per-flow hold with a packet cap in front of a slow verdict

## G22. A connection into a listed app through the tunnel never completes in include mode

**Context:** device measurements with the experimental build, 2026-09-28. The PC is
another peer of the same server (10.8.1.2) and connects to a listener in the phone's
Termux (10.8.1.8).

**Symptom:** "only listed apps" mode, Termux listed, strict on: 0 of 5 connects, in 2 of 2
runs; the listener never sees them. With the filter removed, 5 of 5. Every SYN-ACK the phone
sends is denied, retransmits included: 27 judged for 5 connects
(`evidence/research-2026-09-28/m3-inbound.txt`, `ctl-strictOFF.txt`).

**Cause:** the AmneziaWG hook judges every TCP packet with SYN set, and a SYN-ACK has it.
The platform is asked about the connection's 5-tuple, which at that point belongs to a
request socket, and the kernel reports request sockets with uid 0 (`inet_req_diag_fill`,
kernel v6.6). In include mode uid 0 is outside the VPN, the answer is
`INVALID_UID` ([[G08]]), and the SYN-ACK is dropped ([[A03]]). In exclude mode uid 0 is
inside and the SYN-ACK passes. An excluded app cannot use that to accept connections
through the tunnel: Android routes its SYN-ACK away from `tun0`, with the filter or
without it, and the filter never sees one (`m9-inbound-exclude.txt`).

**Fix:** on the branch `followup/inbound-synack` of amneziawg-go (`286bc02`), kept out of
#199 so it does not grow, and in `release` and strict.7. It asks about the listener instead, the same
local address with an unspecified remote, which the kernel's exact lookup resolves to the
listening socket — owned by the app that will get the connection. 5 of 5, in 2 of 2 runs.
A SYN-ACK from a connecting socket, in TCP simultaneous open, is then denied: it has no
listener.

**How to spot it:** inbound connections through the tunnel fail only in include mode with
strict on; `synack_judged` grows in the experimental build.

**Portable:** yes — any filter that asks the platform for the owner of a SYN-ACK

## G23. A UDP datagram larger than the tunnel MTU never leaves, even from an allowed app

**Context:** device measurements with the experimental build, 2026-09-28. The tunnel MTU
is 1280.

**Symptom:** a listed Termux sends 1400-byte DNS queries to 9.9.9.9: none of 20 answered,
in 2 of 2 runs. The same queries at 1200 bytes: 20 of 20. With the `frag` prototype the
1400-byte ones got 16 and 20 of 20 (`evidence/research-2026-09-28/m2-fragments-quad9.txt`).
1.1.1.1 and 8.8.8.8 are no use for this test: they stopped answering padded queries
somewhere between 400 and 700 bytes even unfragmented (`m2-fragments.txt`).

**Cause:** the kernel fragments a datagram larger than the MTU before it reaches `tun0`,
and the filter drops IPv4 fragments as packets it cannot attribute ([[G11]], [[A03]]): only
the first fragment carries the ports. The counters show two `unattr_frag` per datagram.

**Fix:** on the branch `followup/fragments` of amneziawg-go (`362d674`), kept out of #199,
and in `release` and strict.7. It judges the first fragment like any
packet of its flow, and lets the later fragments with the same source, destination,
protocol and identification follow it for `maxHoldTime`; a later fragment whose first
one was not seen is still dropped. An app cannot choose the identification, and
fragments without their first one cannot be reassembled, so this gives an excluded app
nothing. IPv6 fragments are not handled by it.

**How to spot it:** an app works with small datagrams and fails with large ones;
`unattr_frag` grows in the experimental build.

**Portable:** yes — any fail-closed filter that needs ports to decide

## G24. The VPN service dies when the filter's workers exit, and leaves no tombstone

**Context:** device runs with the experimental build, 2026-09-28: a reconnect sent from adb,
then the filter removed and put back in a running tunnel, over and over.

**Symptom:** `Process … exited due to signal 11 (Segmentation fault)` for the service
process, 28–97 ms after the filter is removed (`Set(nil)`). No backtrace in logcat, and
`/data/tombstones` is not touched. Three times: on a reconnect; once in 100 toggles under
a stream of 500 denied flows/s, and never in 60 toggles without it; on the first toggle
after a flood of 5000 flows/s.

**Cause:** each worker was locked to its OS thread (`runtime.LockOSThread`). A locked
goroutine that exits takes its thread with it, and before handing the thread back to
pthread Go blocks every signal except 32–34 (`sigblock(true)` in `runtime.mexit`,
`sigsetAllExiting` in `signal_unix.go`). The thread's pthread key destructor then detaches
it from the JVM ([[A09]]), with SIGSEGV still blocked. If the JVM faults on that path — as
ART does by design and handles itself, for instance in an implicit suspend check while a
GC waits — the blocked signal kills the process with the default action, and debuggerd
never runs. The ART side is inferred from the symptom, not read in its source. It takes a
JVM suspend request during the detach, so the more Java work the service does, the more
often it happens. Workers exit whenever the filter is replaced or removed: on every
disconnect, every reconnect (a network change included, which calls `turnOffVpn`), and
every strict toggle.

**Fix:** workers are not locked: `342f9ec` on the former `exp/lab`, in amneziawg-go#199
since 2026-09-30 (`ba14bc1`), released in strict.7. When one exits its
thread goes back to the Go scheduler and stays attached, so no thread is ever detached with
signals blocked. Checked on the phone with 32 workers and a steady 3000 flows/s: 0 deaths in
300 toggles, against 1 in 60 without the fix under the same load
(`evidence/research-2026-09-28/m12-crash.txt`). The lock has been in `work()` since the
off-reader rework ([[G15]]), so it is in amneziawg-go#199, in the released test build `v5.0.3.1-strict.3` (recipe
`strict.5`) and in the unreleased recipe `strict.6` build.

**How to spot it:** signal 11 of the VPN service process right after a disconnect, a
reconnect or a strict toggle, and no tombstone. In code: a goroutine that calls into Java,
is locked to its thread, and can exit.

**Portable:** yes — any cgo library that attaches Go threads to the JVM and detaches them
in a thread-exit destructor

## G25. A build with another applicationId never finds its own running VPN service

**Context:** the side-by-side experimental build `org.amnezia.vpn.exp`, 2026-09-28.

**Symptom:** with the tunnel up, the app is swiped away from recents; reopened, it shows
the tunnel as off and its connect button does nothing, while the VPN keeps running.

**Cause:** `VpnProto` names the service processes `org.amnezia.vpn:amneziaAwgService` and
so on, and `AmneziaVpnService.isRunning` compares that with the process names
`ActivityManager` reports, which carry the real applicationId
(`org.amnezia.vpn.exp:amneziaAwgService`). The check fails, and the reopened activity never
binds to the service. Upstream ships one applicationId and does not have this.

**Fix:** compare the package name plus the suffix: first on the former local `exp/lab`
(`ae9eaf3a`), since 2026-09-30 in the test release with the side-by-side identity
(`17434ae5` on the old `feat`, now a fork-only commit of `release`, [[A11]]).

**How to spot it:** any build with a changed applicationId; `processName` in `VpnProto.kt`.
