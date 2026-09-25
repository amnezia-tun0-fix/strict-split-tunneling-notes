# Strict Split Tunneling — documentation entry point

A userspace per-connection UID filter for AmneziaVPN on Android, closing the bypass
reported in [amnezia-client#2457](https://github.com/amnezia-vpn/amnezia-client/issues/2457):
an app can call `SO_BINDTODEVICE("tun0")` and reach the tunnel whatever the split-tunnel
rules say, learning the VPN server's IP in the process.

**State:** the code is written and pushed to five forks, and a full APK builds from it
(Ubuntu under WSL). The AmneziaWG path, the one the issue is about, is **verified on a
device**: bypass attempts go from 6/6 to 0/6 with the toggle on. The Xray path is built but
unverified, because Xray does not connect from Russia.

**This directory is an umbrella, not a codebase.** The five sibling folders are clones of
forks, versioned separately and git-ignored here. Only these documents live in this repo —
see [method-delta.md](method-delta.md) for why.

## Documentation map

| File | What is inside |
|------|----------------|
| [overview.md](overview.md) | Purpose, **invariants**, stack, how the pieces connect |
| [status.md](status.md) | What works, **fragile points**, what is blocked and deferred |
| [journal.md](journal.md) | Chronicle, newest on top |
| [gotchas.md](gotchas.md) | `G##` — traps that have already cost time |
| [architecture.md](architecture.md) | `A##` — settled decisions |
| [conventions.md](conventions.md) | Writing code destined for someone else's PR |
| [references/upstream-watch.md](references/upstream-watch.md) | What upstream did, and what it cost us |
| [_meta.md](_meta.md) | Where the rules for these documents live |

## What to read when

- **Start of a session** → this file, then [status.md](status.md), then the top entries
  of [journal.md](journal.md).
- **Touching either filter** → [[A01]] for why the hook is where it is, then
  [[A02]] for what the Go side is and is not allowed to know.
- **Touching the AmneziaWG hook** → [[G06]] first. It sits in a gap upstream writes into,
  and a rebase can place it wrongly in a way that still compiles.
- **Anything crossing into Kotlin** → [[A02]], then [[G02]] for Xray (generated binding:
  ports are `Long`, method names lower-cased) or [[A09]] for AmneziaWG (hand-written JNI:
  ports are `Int`, and the thread rules matter).
- **Rebasing onto upstream** → [references/upstream-watch.md](references/upstream-watch.md)
  for what was already reviewed, then [[G01]] (which base is real) and [[G05]] (the
  translation catalogue is generated — never merge it line by line).
- **Trying to build an `.aar` or the app** → [[G04]]: a path-shaped `replace` never
  reaches the conan build; then [[A07]] for the pins and [[A08]] for the APK.
- **Adding or changing a setting** → [[A05]]; mirror the `killSwitch` chain exactly.
- **Wondering why something is denied** → [[G08]] first (`INVALID_UID` is mostly "not
  under our VPN"), [[A03]] for the fail-closed rule, [[G03]] for why Go cannot resolve it.
- **Writing into these documents** → `RULES.md` of the standard, via [_meta.md](_meta.md).
- **A session opens with a `gh_inbox:` list** → reviewers answer in several places (a review
  on one PR, a comment on another, the issue), and the list is everything new since the
  last check. Handle each item, then run `python tools/gh_inbox.py --mark`. The list is
  printed by a SessionStart hook in `.claude/settings.local.json`.

## Three facts to know up front

1. **The filter had to be written twice, and the second one is the important one.** The
   Xray and AmneziaWG datapaths share nothing but the tun file descriptor, so there are
   two hooks of different shapes — one per connection in a gVisor forwarder, one per
   packet in a read loop ([[A01]]). The reported vulnerability is about **AmneziaWG**, so
   the path that looks secondary is the one the issue is actually about. Its bridge is a
   hand-written JNI upcall rather than a gomobile binding ([[A09]]).
2. **Go cannot know who owns a packet.** Only Android can name the owning UID, and only
   for the app that is the active `VpnService`; `/proc/net/tcp` has been blind since
   Android 10 ([[G03]]). Everything structural follows from this: Go asks, Kotlin decides,
   and no packet of a flow leaves before the answer. On AmneziaWG the answer comes from
   workers while the flow's first packets are held, because asking on the tun reader
   let any app stall the tunnel ([[A02]], [[G15]]).
3. **A disabled filter must be indistinguishable from no filter.** Off means no filter is
   registered at all — nothing parsed, nothing allocated. That is the argument for
   merging this upstream, so a change that makes the disabled path cost something does
   not just regress performance, it dissolves the case for the feature ([[A05]], and
   invariant 1 in [overview.md](overview.md)).
