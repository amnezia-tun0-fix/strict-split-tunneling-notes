# DELTA — how this project diverges from the standard

Section references point at the standard at https://github.com/Fast-and-Pythonic/ai-docs-method
(audited against v2.1). Every divergence carries a justification: diverging "because it
suits us better" is not allowed, or the standard stops meaning anything.

---

## D1. The documents live in an umbrella directory, not in the project's repository

**Standard:** one project is one repository with one `ai_docs/` at its root. The migration
checklist says "Create `ai_docs/` at the project root"; the linter config takes a single
`root` and a single `docs` beneath it; path checks resolve inside that one tree.

**Locally:** the work is one feature spread across **four forks of other people's
repositories** — `amnezia-client`, `amnezia-libxray`, `amnezia-tun2socks`, `amneziawg-go`
— plus a fifth that will be touched later. There is no repository that contains the
project. So `ai_docs/` sits in the umbrella directory that holds the five clones, which is
itself a small git repository containing only documentation and tooling; the five clones
are git-ignored there and keep their own histories. This repository is a published copy of
those documents.

**Why:** the code in those forks exists to become a pull request to upstream Amnezia.
Documentation about *our* process — why we chose a fork point, which of our rebases went
wrong, what we have not verified yet — is noise in someone else's repository and would
have to be stripped before submitting, which means it would rot or be deleted. Putting it
in any one fork would also be a lie about its scope: no single fork contains the feature,
and the most interesting knowledge is precisely about the boundaries between them
(`[[A02]]` is a contract spanning two repositories). The alternative the standard
implies — one `ai_docs/` per fork — would split six entries across four places and
duplicate the cross-cutting ones.

**Side effect:** two useful consequences and one cost. The umbrella repository gives the
documentation a history of its own, independent of any fork's rebases — and this branch
has already been force-pushed once. It also gives a natural home for tooling that belongs
to no single fork. The cost: `git log` here covers only the documentation, so the H-rules
that lean on commit history apply to the docs and not to the code they describe; code
history has to be read in whichever fork holds it.

---

## Legitimate exceptions

Places where this project's `ai_docs/` breaks the standard **on purpose** — recorded so a
future session does not "tidy them up".

- **Paths into the fork clones are not paths into this repository.** Files such as
  `amneziawg-go/device/send.go` are named throughout these documents and exist on disk,
  but belong to a repository this one ignores. This is intentional and is the whole point
  of `D1`; `tools/lint_docs.toml` carries an `allow` entry for the one such path that does
  not exist yet.

## Demoted to advice

- **Nothing.** The umbrella directory is under git, so the hard rules that depend on
  version history are enforced for the documents themselves. Note the narrower scope
  described under `D1`: they are enforced for the documents, not for the code.
