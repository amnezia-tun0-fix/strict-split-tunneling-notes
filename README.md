# Strict split tunneling for AmneziaVPN — notes and probes

Working notes behind a fix for [amnezia-vpn/amnezia-client#2457](https://github.com/amnezia-vpn/amnezia-client/issues/2457): on Android, an app excluded from per-app split tunneling can bind a socket to `tun0` and reach the VPN server, which reveals the server's address.

This repository holds the reasoning, the traps found on the way and the probes used to measure the fix. The code lives in three pull requests:

| Repo | PR | What it carries |
|---|---|---|
| amneziawg-go | #TBD | the `uidfilter` package and the hook in the tun read loop |
| amneziawg-android | #TBD | the JNI bridge that asks the Java side who owns a connection |
| amnezia-client | #TBD | the "Strict split tunneling" setting and the wiring |

Not affiliated with Amnezia. These are one contributor's notes, published because a reviewer of those PRs may want the reasoning behind them.

## Start here

- [docs/start.md](docs/start.md) — what to read for which question
- [docs/architecture.md](docs/architecture.md) — the ten decisions, A01–A10: why the filter is in userspace, why Go asks and Kotlin decides, why an unresolved owner is denied
- [docs/gotchas.md](docs/gotchas.md) — eleven traps that cost time, including the four worth knowing before writing this kind of filter:
  - **G11** any app can ping through `tun0`, and ICMP has no owner to look up
  - **G08** `getConnectionOwnerUid` answers `INVALID_UID` for any app your VPN does not cover, not only when no socket matches
  - **G09** a socket the app has closed belongs to UID 0, so re-judging a flow drops its FIN
  - **G03** `/proc/net/tcp` shows a process only its own sockets since Android 10
- [docs/status.md](docs/status.md) — what works, what is fragile, what is deferred
- [docs/journal.md](docs/journal.md) — how it went, newest first

## Probes

Standard library Python, meant to run in Termux as an app that is **outside** the VPN. They print a summary and write it to `/sdcard/Download/`.

```sh
python leak_probe.py <label> [vpn_server_ip]   # TCP, UDP and curl bound to tun0
python icmp_probe.py <label> [target ...]      # ICMP echo from an unprivileged ping socket
python dns_probe.py  <label> [vpn_server_ip]   # DNS through the system resolver, as a listed app
```

`leak_probe.py` reports `LEAK(SERVER_IP)` when a bypass attempt reaches the far side from the VPN server's address. On the build with the fix, strict mode on gives 0 of 6 and ICMP times out; with it off, 6 of 6 and ping answers.

## The setting

| | |
|---|---|
| ![switch off](screenshots/1-switch-off.jpg) | ![enable dialog](screenshots/2-enable-dialog.jpg) |
| Off by default, under app split tunneling | Turning it on explains the trade-off |
| ![switch on](screenshots/3-switch-on.jpg) | ![locked](screenshots/4-locked-while-connected.jpg) |
| On | Locked while connected, like the rest of split tunneling |

## License

The documents and the probes are published under the MIT license (see [LICENSE](LICENSE)). The code in the pull requests follows the license of each upstream repository.
