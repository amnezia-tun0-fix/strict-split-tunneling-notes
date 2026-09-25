# Conventions

Every line this project writes goes into someone else's repository and is meant to be
merged there. That single fact decides most of what follows.

## Writing in a fork

- **Match the file you are editing, not a house style.** Four codebases are involved —
  Go, Kotlin, C++ and QML — each with its own conventions. Read the surrounding twenty
  lines before adding any.
- **Additive, minimal, local.** Prefer a small insertion at one call site over a
  refactor that would be better in the abstract. A diff a maintainer can read in one
  sitting has a chance of being merged; a tidier architecture does not.
- **Never reformat code you did not write.** No reordering imports, no whitespace
  cleanups, no "while I was here". Formatting noise buries the actual change and is the
  fastest way to have a PR ignored.
- **Copy the local pattern when one exists.** The settings toggle mirrors `killSwitch`
  line for line ([[A05]]), and the bridge mirrors `RegisterDialerController`. This is
  not laziness — it is what made those diffs survive 90 upstream commits.
- **Comments explain why, not what.** A hook in someone else's loop needs one sentence
  saying what it is for and what happens when the feature is off. Anything longer
  belongs in an `A##` here, not in their file.

## What can be checked locally, and what cannot

| Layer | Locally verifiable | How |
|---|---|---|
| Go (all three repos) | fully | tests, cross-build, vet |
| Kotlin (`amnezia-client`) | compilation only | Gradle, against a locally rebuilt `.aar` |
| C++ / QML | no | needs Qt-for-Android, absent on this machine |
| Runtime behaviour | no | needs a built APK and a device |

Treat "compiles" and "works" as different claims, and say which one you have. For the
C++/QML chain the honest check is a review against the pattern being mirrored, plus a
grep confirming the setting's name is spelled identically at every layer from the
QSettings key through to the Kotlin reader.

## Build and check

```bash
# Go — run in amnezia-tun2socks, amneziawg-go, amnezia-libxray
go test ./...
GOOS=linux GOARCH=arm64 go build ./...     # the target platform
go vet ./...

# Kotlin — needs JDK 17 and an .aar containing the bridge
cd amnezia-client/client/android
./gradlew :utils:compileReleaseKotlin :xray:compileReleaseKotlin
```

`amnezia-libxray` only builds with a `replace` pointing at the local `amnezia-tun2socks`
checkout — and `build.sh` deletes it, so use `gomobile bind` directly for local builds
([[G04]]).

**What counts as broken:** a failing Go test or vet; a Kotlin module that no longer
compiles; a diff against the fork's base that contains anything beyond the intended
change.

## Workflow

- **Before a commit:** confirm the branch's diff against its *base* contains only the
  intended files. After a rebase this is the check that catches upstream hunks dragged in
  while resolving conflicts.
- **Branches:** `feat/strict-tunnel-isolation` in every fork, plus a `…-prerebase` backup
  before any rebase. Push with `--force-with-lease`, never plain `--force`.
- **Rebase, do not merge.** The PR should be a short line of deliberate commits.
- **Files to touch carefully:** `amneziawg-go/device/send.go` — the hook sits in a gap
  upstream writes into ([[G06]]). `amnezia-libxray/go.mod` — the `replace` is
  development-only and must not reach a release build.
- **Files never edited by hand:** `client/translations/*.ts` beyond the few `<message>`
  blocks that are ours — they are `lupdate` output ([[G05]]). Register indexes in these
  documents — `make_index.py` generates them.
- **Never auto-format:** anything inside the five fork clones.
- **Replies on GitHub start with the addressee's handle** (`@izhddm …`). A PR's
  conversation is flat, and an answer to a review or a general comment cannot be
  threaded, so without the handle a maintainer reading from the end cannot tell who is
  being answered. Only line comments thread. A handle added by editing a posted comment
  sends no notification, so put it in the draft. Drafts live in `pr-drafts/`, and the
  PR-branch commit hashes they cite differ from the working branch ones.

## These documents

English, including the prose. Russian only as quoted data — a UI string, a test fixture.
Absolute paths in prose go in backticks: the local project root contains a space, and the
linter cannot tell where an unquoted path ends.
