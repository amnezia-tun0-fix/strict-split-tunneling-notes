# Overview

## Purpose

Android's per-app split tunnelling is advisory: since Linux 5.7 an unprivileged app may
call `SO_BINDTODEVICE("tun0")` and push traffic into the tunnel regardless of the rules
the user set. The app then sees the VPN server's IP — which is what
[amnezia-client#2457](https://github.com/amnezia-vpn/amnezia-client/issues/2457) reports,
and it affects AmneziaWG 2.0, not only Xray.

This project adds **Strict Split Tunneling**: a userspace per-connection UID filter at
the tun-read boundary of both datapaths, behind a user-facing toggle that is off by
default. No one in the Amnezia ecosystem had fixed this; these forks are the first.

## Invariants

1. **A disabled filter is indistinguishable from no filter.** When the toggle is off, no
   filter is installed, nothing is parsed per packet and nothing is allocated. This is
   the whole argument for merging the change upstream; breaking it dissolves the case.
2. **The Go side never decides policy.** It knows nothing about UIDs, package names or
   include/exclude modes — it hands a 5-tuple across the bridge and obeys the answer. All
   policy lives in Kotlin, where the platform API for resolving a connection's owner is.
3. **An unresolved owner is denied, not allowed.** Loosening this is a security decision,
   not a tuning knob: it stops the session and goes to the user. See [[A03]].
4. **The forks stay PR-shaped.** Every change is a minimal insertion in the upstream's
   own style. Documentation, tooling and scratch work live in this umbrella directory,
   never inside a fork.

## Stack

- **Go** — the two datapath filters and the gomobile bridge. Built for `android/arm64`
  and friends; verified locally by cross-compiling to `linux/arm64`.
- **Kotlin** — the Android service layer: resolves the owning UID and applies the policy.
- **C++ / QML (Qt 6.10.3)** — the desktop-and-mobile client core and its settings UI,
  where the toggle lives.
- **Build chain:** conan recipes → `gomobile bind` → `libxray.aar`; a separate cgo/JNI
  path builds `libwg-go.so` for AmneziaWG.

## Structure

This directory is an umbrella. The five folders below are clones of forks under
`github.com/amnezia-tun0-fix`, each versioned in its own repository and git-ignored here.

```
AmneziaVPN_repos/
├── ai_docs/              these documents
├── ai_docs_method/       how this project departs from the standard (D1)  → docs/method-delta.md
├── tools/                linter config and the on-device probes
├── amnezia-client/       Kotlin service layer + C++/QML client and the toggle
├── amnezia-libxray/      gomobile bridge: exposes the filter to Android
├── amnezia-tun2socks/    Xray datapath — filter hook in the gVisor forwarders
├── amneziawg-go/         AmneziaWG datapath — filter hook in the TUN read loop
└── amneziawg-android/    JNI bridge for AmneziaWG
```

Every fork carries the same branch name, `feat/strict-tunnel-isolation`, plus a local
`…-prerebase` backup of the state before the last rebase.

## How the pieces connect

```
        app socket                    ┌──────────── Kotlin ────────────┐
            │                         │ StrictSplitTunnelGuard         │
            ▼                         │  getConnectionOwnerUid (API29+)│
      Android tun fd                  │  + split-tunnel policy         │
            │                         └───────▲────────────────────────┘
   ┌────────┴────────┐                        │ allow(5-tuple) -> bool
   │                 │                        │
   ▼                 ▼                 ┌──────┴──────┐
tun2socks        amneziawg-go          │   bridge    │
(Xray path)      (AmneziaWG path)      │ gomobile /  │
per-connection   per-packet, cached,   │ cgo + JNI   │
   │             judged off the reader └─────────────┘
   │                 │
   ▼                 ▼
 SOCKS5 → xray    crypto → UDP
```

Both datapaths read from the **same** Android tun fd but are otherwise unrelated, which
is why the filter had to be added twice — see [[A01]].

## Current state

The AmneziaWG path is verified on a device and submitted upstream as three PRs; the Xray
path is built but cannot be run from here. Detail in [status.md](status.md).

## Build and check

Go work is verifiable on any machine with a Go toolchain; the Android and Qt halves are
not. What each layer can and cannot prove locally is in [conventions.md](conventions.md).

```bash
cd amnezia-tun2socks && go test ./filter/...
cd amneziawg-go      && go test ./uidfilter/...
GOOS=linux GOARCH=arm64 go build ./...   # in any of the three Go repos
```
