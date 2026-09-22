# _meta — where the rules for these docs live

The rules for maintaining this documentation are **not copied here**. Two sources of
truth drift apart, which is the disease the method exists to cure.

Standard: https://github.com/Fast-and-Pythonic/ai-docs-method — audited against v2.1
on 2026-09-17.

Local method: [method-delta.md](method-delta.md). This project **does**
deviate — it is an umbrella over several forks rather than one codebase. Where the two
disagree, the local method wins. See `D1` there.

| You need | Read |
|----------|------|
| What is mandatory, triggers, session protocol | `RULES.md` of the standard |
| How to format a `G##` / `A##`, links, indexes | `FORMATS.md` |
| Which files this project's size warrants | `RULES.md` §6, "Tiers and scaling" |
| Why the docs sit outside the forks | [method-delta.md](method-delta.md) |

## Project settings

**Profile:** engineering
**Tier:** M — three areas a session has to hold at once: the Go filters in the two
datapaths, the Android layer (Kotlin resolver plus the C++/QML toggle), and the build
pipeline (conan → gomobile → `.aar` → JNI). No `subsystems/` pages yet; the first area
whose notes outgrow a register entry earns one.
**Language:** English, including these documents, decided when they were created on
2026-09-17. The code this project produces is destined for a PR to a public upstream,
so the documentation around it is written in the language that PR will be read in.
Russian appears only as quoted data — the UI string «Строгое раздельное туннелирование»
is quoted verbatim in [[A05]] because it is the literal text in the `.ts` file.

## Stop and ask

Beyond the standard's own rule about invariants: **anything that changes behaviour while
the feature is switched off** stops the session. The whole argument for merging this
upstream is that a disabled filter is indistinguishable from no filter — see the
invariants in [overview.md](overview.md).

## The three things most often broken here

1. **Project knowledge mixed with machine knowledge.** A trap that would break the same
   way in any project on this machine — a PowerShell quoting quirk, a Windows git
   setting — belongs to the shared environment store, not here. Ask first: would this
   break in another project on this machine? If yes, it is not a `G##`.
2. **`status.md` absorbing the chronicle.** State goes in `status.md`, the reasoning in
   an `A##`, and the story of how it was reached in `journal.md`. The 80-line limit is
   there to refuse the chronicle, not to save space.
3. **Register indexes written by hand.** Run `make_index.py`; a hand-made index drifts
   by the next session.

## Checking

```
python <standard>/tools/lint_docs.py  --config tools/lint_docs.toml
python <standard>/tools/make_index.py --config tools/lint_docs.toml
```

Both work from any directory. This umbrella directory is under git, so nothing here is
demoted to advice — but note that `git log` covers only the documentation: the code
history lives in the five fork clones, which are versioned separately.
