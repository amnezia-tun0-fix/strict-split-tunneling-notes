# Journal

Append-only, newest on top. Why the work went the way it did — the substance lives in the
registers and is not restated here. `git log` in each fork has what changed line by line.

## Index

- **2026-10-02** — the cache @makekryl questioned, measured: speed equal, the difference is under a flood
- **2026-10-02** — the fork branches become layers, so the lab build measures release code
- **2026-10-01** — strict.7 released, next to the store app, with the crash fix
- **2026-09-28** — a study of how to improve the filter found a crash in our own bridge
- **2026-09-28** — writing two articles found a flaw in two other clients and one in ours
- **2026-09-27** — a survey of other clients, after a machine summary got half of them wrong
- **2026-09-26** — a warm-up PR, and why a Private DNS warning is not a one-liner
- **2026-09-26** — two rebase traps now refuse the push instead of relying on a reader
- **2026-09-25** — strict.3 released: the reworked filter, for anyone who installed strict.2
- **2026-09-25** — a second review: the lookup leaves the tun reader, measured on the phone
- **2026-09-24** — cloned apps were blocked in include mode: the guard compared uids
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

## 2026-10-02 — the cache @makekryl questioned, measured: speed equal, the difference is under a flood

@makekryl asked on #199 whether the verdict cache needs expiry, refresh and its eviction
rule, or whether a plain FIFO would do and be faster. The user wanted the answer measured.
The lab build gained five caches behind one switch (`c=`): the PR's, the FIFO, the PR's
without refresh, refresh with packets held, and the FIFO with every TCP packet through it,
as #174 does. 61 runs on the phone, each mode twice in ABBA order, with the filter removed
live as the control, plus benchmarks on the phone and the PC.

The speed question closed first and against the premise: a cached UDP packet costs 47–60 ns
in either cache, and the refresh is not on that path. Its cost is one owner lookup per
active allowed flow every 2 s. #174's design costs five times more per TCP packet.

The flood gave a result that pointed the wrong way. New flows of an allowed app fared better
with the FIFO (97–99% answered against 88–96%), and the cause was not the cache's speed: a
benchmark showed its eviction cheaper than the FIFO's. It was repeats. Android draws source
ports from about 28,000, so a flood to one address repeats 5-tuples within seconds, and a
FIFO that keeps 3300 denials answers them without a lookup. Spreading the flood over random
destination ports made the two equal. What the PR's eviction rule does buy showed only with
a bursty allowed flow: 97.8% answered with the FIFO, 99.7–99.9% with the PR's cache.

The plan's suspicion, that the refresh lets a taken-over 5-tuple pass until the verdict
expires, did not hold: the test denies it 2.0 s after the inherited verdict. The same test
found [[G26]] instead. The first build of the session failed on a known WSL trap: started
as `wsl -e bash -c`, the shell is not a login one and skips `~/.profile`, where the Android SDK
is set. The trap had been written down; the plan's command line still lacked `-l`, so
`build_exp.sh` now reads `~/.profile` itself. The user also granted that the agent drives
the phone itself over adb and Termux (`references/device-testing.md`).

The user had [[G26]] fixed in the PR, keeping the reply back for now. The first attempt
discarded a late refresh as stale, and an existing test caught what that would cost: a flow
sending every 2 s collects each refresh exactly 2 s late, so it would never be renewed and
would stall at the expiry, the loss the refresh was added to remove. A late refresh now
renews the entry from its lookup time and starts the next lookup at once. Rebuilding the
layers turned up an unrelated flaky test on `followup/fragments`: nothing kept the worker
from judging the flow between its two fragment checks, and under `-race` most batches of 20
runs failed, before the fix as after. It now waits on a gate (0 of 40 batches).

One attempt to close the FIFO's only advantage, its better showing against a naive flood,
was measured and dropped. `pr2` evicts denials only down to seven eighths instead of all of
them; it kept more denials (2300 against 1400) and looked level with the FIFO in an evening
series on a hot, dark phone, but a repeat on a cool phone with the screen on put it level
with the release cache instead (90.4% against 90.8%, the FIFO 94.0%). The evening series
also lost its first half: an adb `connect` with the screen locked brought the tunnel up with
the saved app list, so the "allowed" probe ran outside the VPN; `run.sh` now checks the
tunnel's uid coverage before every run.

Decisions: none · Gotchas: [[G26]] added and fixed
Status: Working
Next: the user approves the reply in `pr-drafts/23-reply-makekryl-cache.md`; real-use data (question 6)

## 2026-10-02 — the fork branches become layers, so the lab build measures release code

@makekryl answered on #199 that the verdict cache could be a plain FIFO without expiry,
and the user wanted the reply backed by a large comparison on the phone. Planning it showed
that the lab build could not carry it: `exp/lab` held prototypes of fixes whose final form
was already in the PR, and `feat` repeated the PR's commits under other hashes. Three
parallel histories per fork, kept in step by hand.

At the user's request the branches were put in order first ([[A13]]). `release` and `lab`
are rebuilt as layers on `pr`; the old ones are kept under `archive/*` tags. The check of the
rebuild was the tree, not the log: `release` of amneziawg-go is byte-identical to the old
`feat`, and the other two differ only in pins. amneziawg-android's `release` now sits on
upstream `master` like its `pr`, three commits the recipe does not build. The lab
instruments were carried onto the release code; the prototypes that became release code
were left behind. `preflight.py` now refuses a push that breaks the order, and the first
change made under the new scheme, the short launcher labels the user asked for
(«strct-AmnzVPN», «lab-strct-AmnzVPN»), went through it: a commit on `release`, `lab`
rebased on top.

On the phone the lab build gave the usual answer, 0/6 with the filter and 6/6 with it
removed live (`evidence/branches-2026-10-02/`). It also showed that an adb `reconnect` can
stop the service it has just restarted; the code is release's, so strict.7 has it too. 49
reconnects in a row did not repeat it; sending the app to the background right after one
did, 6 of 6. With the service's debug log on, the cause was plain: the state handler acts on
`DISCONNECTED` only after a suspending store, by which time the reconnect has cleared its
guard. Fixed on `release` (`07504e31`), 10 of 10 after. The first guess was this, and was
set aside on a reading of the code that missed the suspension.

While updating the documents, G20–G25 still said "Fix: open" two days after the fixes
went into #199; corrected.

Decisions: [[A13]]; [[A07]], [[A09]], [[A11]], [[A12]] amended · Gotchas: [[G20]]–[[G25]] amended
Status: Working
Next: the cache comparison for the reply to @makekryl, by `~/.claude/plans/cache-study-makekryl.md`

## 2026-10-01 — strict.7 released, next to the store app, with the crash fix

The fixes of the study went out as the user chose: four commits on the amneziawg-go#199
branch (the crash, the refresh before expiry, 16 held packets, the queue reference), and
two more on follow-up branches linked from the new "Known limitations" section of its
description, since a PR that grows is a PR nobody reads. The user expects the maintainers
to write their own fix at best, so the value of the branches is as a reference and a list
of traps, not a merge.

Two things changed how test builds work. The build that replaced the store app kept
testers away, so `feat` now builds `org.amnezia.vpn.strict` next to it ([[A11]]). And the
research showed that taps cost more than they are worth, so the adb control moved from the
experimental build into `feat` ([[A12]]); the counters and the live filter switch stayed
behind, to keep the filter code of a release identical to the PR. `tools/preflight.py`
refuses both on a `pr/*` branch. Release numbers had drifted from the recipe numbers they
were built on, and our own texts mixed them up ("strict.3–6"); from strict.7 a release
takes the recipe's number ([[A07]]).

The first build of the release failed in two minutes and printed DONE anyway. From WSL,
HTTPS to conan, the Go proxy and Google stalled while HTTP worked: a path MTU black hole
through the Windows VPN, the third network trap of WSL here (environment store). The build
script now checks the hosts first and never hands out an apk older than its own start.

strict.7 (`28abcddc`, sha256 `e000a327…`) was checked as the published file, next to the
store app: nothing through `tun0` with the switch on, everything with it off, eleven
reconnects from adb without a crash. Published: the #199 branch and description, the
release, comments on #199 and #2457, and the first #2457 comment now links strict.7.
`references/device-testing.md` collects how all of this is done on the phone.

Decisions: [[A11]], [[A12]]; [[A07]], [[A08]] amended · Gotchas: [[G25]] amended
Status: Working · strict.7 released
Next: waiting — on the maintainers and on testers of strict.7

## 2026-09-28 — a study of how to improve the filter found a crash in our own bridge

The user asked for the fullest study of how the filter could be better, every hypothesis
run where it could be. A side-by-side build, `org.amnezia.vpn.exp`, carried switchable
prototypes and counters. Driving it by taps cost screenshots, so at the user's suggestion it
learned to take commands from adb (`tools/awgctl.sh`), including taking the filter out of a
running tunnel. That made "no filter" a control run in the same tunnel.

Every finding was measured three ways: as the PR has it, with a prototype, and with no
filter. Four limits of the PR code showed on the phone: loss at each verdict expiry (G20),
a new flow's first burst (G21), inbound connections in include mode (G22) and fragmented
UDP (G23). A new prototype, refresh-ahead (`raN`), cured G20 without ever passing a packet
on an expired verdict, which the older `rv` could not. All prototypes at once still let
nothing through from an excluded app. A bypass the code suggested, inbound connections to
an excluded app, turned out to be stopped by Android's routing before the filter. So did
the idea that more workers would help under a flood: the filter dropped nothing there.

The largest finding was not on the list. A reconnect sent from adb killed the service with
SIGSEGV, and there was no tombstone to read. It was cornered by timing and by Go's source.
It came tens of milliseconds after the filter was removed, when the workers exit. Go blocks
every signal on a thread it is ending, and the JNI bridge detaches that very thread from
the JVM. Toggling the filter under load reproduced it; not locking the workers fixed it,
0 in 300 against 1 in 60 (G24). The lock is in #199 and in the released test builds.
Report with the proposed order of work: `evidence/research-2026-09-28/REPORT.md`.

Gotchas: [[G21]]–[[G25]]; [[G11]], [[G17]], [[G19]], [[G20]] amended · Decisions: [[A09]] revised
Status: Known issues — G20–G24, fixes on `exp/lab`
Next: the user's choice of fixes for #199, first G24; a test release with it

## 2026-09-28 — writing two articles found a flaw in two other clients and one in ours

The user asked for two Habr articles, a survey of how clients handled the leak and a
deep dive into our fix, in Russian first and in English afterwards. Drafts, notes and
illustrations live in `articles/`. The style rules and a checker went into a personal
skill (`tech-article-style`), built from Habr articles written before ChatGPT.

Checking the survey against source code changed its point. TeapodStream and OlConnect
both ask the platform for the owner, and both let `INVALID_UID` through: TeapodStream in
"all except selected" mode, OlConnect always ([[G08]]). Neither was run on a device. The
user chose to tell the authors privately before the survey is published. OlConnect has no
private channel, so a detail-free issue (Oleglog/OlConnect#3) asks the author to turn on
private vulnerability reporting. The TeapodStream author has a public e-mail, and the
user sends that one. Drafts are in `articles/notes/disclosure-drafts.md`.

An architect review of the deep dive against the code found that our own cache drops
allowed UDP verdicts when an app floods it ([[G19]]). G15 had said allowed flows never
suffer. That is true for established TCP only, and G15 is corrected. The review also
restored the mode caveat of `ip route get` in [[A01]] and narrowed "traceroute" in
[[G11]] to its ICMP form. The article states G19 as a limitation. The code fix is left
to the user, since it adds a commit to #199 while it is under review.

Gotchas: [[G19]]; [[G11]], [[G15]] corrected · Decisions: [[A01]] amended
Later the same night G19 was fixed (`0f0382e`, on the PR branch as `2a9f1f1`) and checked
on the phone after three failed builds. Those were not the code: WSL was stopped by the
Windows commit limit (environment store, EG72), and a memory cap in `.wslconfig` cured it.
`churn_probe` learned to run from Termux, where the linker shifts its arguments, so the
denied flood could come from an excluded app. The published notes stay at G18 until the
two authors reply, and a pre-push hook in the clone enforces it.

Status: Working · G19 fixed and verified
Next: the authors' replies, then the survey can be published; the English versions

## 2026-09-27 — a survey of other clients, after a machine summary got half of them wrong

The user brought an AI-written overview of the leak. Its mechanics were right and its
sources were not: a Karing link led to an unrelated issue, and the Amnezia row described
our unmerged series as shipped upstream. It also added a SOCKS rework nobody did. Four
research agents then covered Xray and sing-box clients, WireGuard and commercial clients
with AOSP, Russian sources, and Chinese and Persian ones. Where two of them disagreed
(sing-box's answer to #4009, OlConnect), the primary page settled it.

The picture: two other projects filter by owner (TeapodStream, OlConnect). sing-box can
block an unknown owner only through a hand-written rule, and v2rayNG closed the same repro
as not planned. Nobody else, Google included, has said anything. The survey went out as a
comment on #2457, linked from the #199 body, so a maintainer asking about alternatives
finds it there. Details are in [upstream-watch.md](references/upstream-watch.md).

Status: Working · survey posted
Next: waiting — on the maintainers; the user's choice on the Private DNS warning

## 2026-09-26 — a warm-up PR, and why a Private DNS warning is not a one-liner

The one-line Makefile fix that sat in Deferred went out as amneziawg-android#105. Before
sending it, the effect had to be shown and not just argued. Our own logcat from every
device run since 09-20 already had `UAPIOpen: mkdir /var: read-only file system`, noise
we had read past. A probe calling `ipc.UAPIOpen` settled what the flag does. Run as
Termux, the old path failed on `/var`, and the `/v3` path created the socket. Run from
`adb shell` it proved nothing: SELinux denies the `shell` domain a socket in
`/data/local/tmp`, which says nothing about an app. The same review changed #3199 from
"Fixes #2457" to "Addresses #2457", so merging it will not close the issue while Xray is
open.

The Private DNS warning ([[A10]]) looked cheap, and detecting the case is:
`LinkProperties.getPrivateDnsServerName()` is non-null exactly in hostname mode (API 28).
Telling the user is not. A reason thrown from the service never reaches the screen as
text ([[G18]]). So the choice is between an Android-side notification and building
upstream's missing error channel. It is left to the user, together with a device check
that needs Private DNS switched to a hostname on the phone.

Gotchas: [[G18]]
Status: Working · #105 submitted, #3199 text edited
Next: the user's choice on the Private DNS warning; waiting on the maintainers

## 2026-09-26 — two rebase traps now refuse the push instead of relying on a reader

[[G06]] and [[G04]] had only a "how to spot it" line. The first is a hook git can put
one line too high while everything still compiles. The second is a fork `replace` that
belongs on `feat/*` and would look like a swapped dependency in a security PR. Either
would be missed by a session that skipped the entry, and the next push after a rebase
is exactly when that happens. `tools/preflight.py` now checks both, and its pre-push
hook in all five forks refuses a failing push. It reads the pushed commit, not the
working tree. Tested on a scratch clone: a path `replace` on `pr/*` and a hook above the
anchor were refused, while the same `replace` on `feat/*` and a clean branch passed.

The same session found the upstream heads of all three PR repos already contained in
our PR branches, so nothing needs a rebase.

Status: Working
Next: waiting — on the maintainers

## 2026-09-25 — strict.3 released: the reworked filter, for anyone who installed strict.2

The build linked from #2457 still had both problems the review found, a tunnel that any
app could stall and verdicts that outlived their sockets. So the reworked branches went
out as a third test build rather than waiting for the maintainers.

It was built from `3e9a6978`, one commit past the build measured earlier in the day,
which only lowers the guard's log level. It was checked again as the artefact itself,
not assumed from the earlier run: include 0/6 on, exclude 0/6 on and 6/6 off, 1000 new
flows/s at a p50 of about 200 ms. Logcat showed no deny lines during blocked probes,
which is the log change working. The file uploaded to the release is byte-identical to
the one installed for the check (sha256 `0479e16d…`, the digest GitHub reports).

The announcement on #2457 also mentions amnezia-client#3214. It is a different channel
to the same server address, found by the same reviewer.

Later that evening the reviewer's account started returning 404 on GitHub. Their reviews,
comments and #3214 vanished with it, while our replies to them stayed. Local copies are in
`evidence/izhddm-2026-09-25/`. Nothing in the code depends on them: every change was
measured on our own phone as well.

Status: Working
Next: waiting — on the maintainers, on anyone who tries strict.3, and on whether the
reviewer's posts come back

## 2026-09-25 — a second review: the lookup leaves the tun reader, measured on the phone

@izhddm built the whole series on a Galaxy S24 FE, confirmed that the bypass is closed for
TCP, connected UDP and unconnected UDP, and then found what the first review did not.
Their mechanism of the leak, the kernel's on-link fallback when `fib_lookup` fails for a
socket with an output interface, now sits in [[A01]].

They made three points, and each one held against the code. The owner lookup ran on the
tun reader, so churn in new flows slowed every flow, and an app outside the VPN could
stall the tunnel on purpose ([[G15]]). The cache key left out the destination, so a
verdict outlived its socket ([[G14]]). `Set` stored the filter and the cache in two steps.
Their measurements were taken as enough to act on without reproducing them first, and
that turned out to be half right (below).

The fix follows their suggestion closely: hold, don't drop, and don't pass. Holding costs
a copy per packet on a miss, and dropping would cost every new TCP connection a 1 s SYN
retransmit. What took thought was keeping the cache lock-free. The workers never touch
it. They mark a pending flow as decided, and the reader moves decided verdicts into its
own cache on its next miss. A flow's held packets leave before the reader can see its
verdict, so order within the flow survives. Building the key from the raw address bytes,
with the length in the key, made the longer key cheaper than the old one.

The same review removed the guard's retry on `INVALID_UID` ([[A03]]). It was insurance
against a race that [[G08]] had already explained away, and it doubled the cost of
exactly the flows an attacker sends.

Later the same day, before anything was pushed, the reviewer corrected themselves. Their
flood had closed each socket right after sending, so it mostly measured owners that could
not be found, the platform's most expensive answer, and not allowed traffic. Their
follow-up also found three things we had built on. The clock trick of [[G12]] went stale
when the tunnel was idle. A full 5-tuple can be reused too ([[G14]]). The cache assumed
one tun reader per process. The code had not reached a device yet, so the second commit
(`cdee4ba`) went on top of the first: a ticker clock, every SYN judged afresh, per-device
state, byte and time limits on holding, and a lock that stops a verdict from being sent
after its filter was replaced. Holding also has a cost that cannot be designed away. A
datagram whose socket is closed before the lookup is dropped, even from an allowed app
([[G16]]).

The phone then settled what the numbers were worth. `churn_probe` gained `-hold`, to
reproduce both of their scenarios, and a `dns` mode that counts answered new flows,
because the connect latency alone cannot show silent drops. At 1000 new flows/s,
`strict.2` gave a p50 of 471 ms with sockets held, and 1.1 s with 2 of 40 connects failed
with sockets closed. The new build held about 200 ms at every rate up to 5000/s, as with
the filter off. In include mode the probe gave 0/6 too, and two minutes of browsing
produced three denials, each a single SYN with no retransmit. Those were connections the
browser cancelled before the lookup ([[G16]]). DNS lost 6–13% at high rates with and without the filter alike, so that
loss is the path, not the filter. Leak probes from the excluded app gave 0/6 with the
switch on and 6/6 with it off.

Gotchas: [[G12]], [[G14]], [[G15]], [[G16]]
Status: Working · verified on the device and published: PR branches pushed as new
commits, the three PR texts updated, the reply posted on #199, the notes synced
Next: waiting — on @izhddm and the maintainers; a `strict.3` test build only if asked

## 2026-09-24 — cloned apps were blocked in include mode: the guard compared uids

The maintainer found it on their own phone a day after the test build went out: a browser
listed in "only the apps from the list" worked, its XSpace clone loaded nothing, and only
with the switch on. The guard's log was silent, which was itself the clue — every deny it
logged was for an unresolved owner, and the clone's owner resolved fine.

`dumpsys connectivity` showed why: the VPN's ranges held each listed app four times — the
original, the clone in user 999, and the SDK sandbox of each. The platform routes all of
them into the tunnel; the guard knew only the uid `getPackageUid` returns and denied the
rest ([[G13]]). Matching app ids instead fixed it (`9ce688c4`). `UserHandle.getAppId` is
hidden API, so the guard carries the AOSP constants, and it now logs denials by the list as
well, so the next mismatch of this kind shows up in logcat.

Verified by building the local commit before pushing it — `build_release.sh --local` takes
the commit from the Windows checkout instead of GitHub. With the build: both clones load
pages, the probe from an unlisted app gives 0/6 with strict on and 6/6 with it off, ICMP
through `tun0` times out and answers respectively. Exclude mode was not re-run: an excluded
app's copies are outside the VPN, so they resolve to `INVALID_UID` and never reach the
changed comparison. The PR branch took the fix as a fourth commit, not a force-push.

Status: Working
Released the same day as `v5.0.3.1-strict.2`, from the verified APK. A new comment on #2457
announces it, and the first comment now links strict.2 instead of strict.1.

Next: waiting — on the maintainers, and on anyone who tries the build

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
