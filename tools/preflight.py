#!/usr/bin/env python3
"""Checks that a fork branch is fit to push, for the traps a clean build does not catch.

- G04: a `replace` onto our fork or onto a local path must never reach a `pr/*` branch.
  On `feat/*` branches it is how the recipes build, so there it is allowed.
- G06: in amneziawg-go the tunnel hook must sit right after `elem.padding = padding`.
  A rebase can put it one line higher, and that still compiles.

    python tools/preflight.py              # every local feat/* and pr/* branch of the forks
    python tools/preflight.py --install    # add the pre-push hook to all five forks

The pre-push hook calls `--pre-push` from inside a fork with git's ref lines on stdin
and refuses the push if a pushed branch fails. It reads the pushed commits, not the
working tree. `git push --no-verify` skips it, so that stays a deliberate act.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORKS = ["amneziawg-go", "amneziawg-android", "amnezia-client",
         "amnezia-tun2socks", "amnezia-libxray"]
ZERO = "0" * 40

# `replace X => Y` where Y is our fork or a filesystem path (G04), one-line or in a block
REPLACE = re.compile(r"=>\s*(\S+)")
HOOK = "uidGate.AllowOutboundPacket("
ANCHOR = "elem.padding = padding"

HOOK_SCRIPT = """#!/bin/sh
# Installed by tools/preflight.py --install in the umbrella repo. See G04 and G06.
exec python "$(git rev-parse --show-toplevel)/../tools/preflight.py" --pre-push
"""


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                         encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def bad_replaces(repo, commit):
    found = []
    for path in git(repo, "ls-tree", "-r", "--name-only", commit).splitlines():
        if path != "go.mod" and not path.endswith("/go.mod"):
            continue
        for n, line in enumerate(git(repo, "show", f"{commit}:{path}").splitlines(), 1):
            code = line.split("//")[0]
            m = REPLACE.search(code)
            if not m:
                continue
            target = m.group(1)
            if "amnezia-tun0-fix" in target or target.startswith((".", "/")) \
                    or re.match(r"[A-Za-z]:[\\/]", target):
                found.append(f"{path}:{n}: {line.strip()}  (G04)")
    return found


def bad_hook(repo, commit):
    src = git(repo, "show", f"{commit}:device/send.go").splitlines()
    hits = [i for i, line in enumerate(src) if HOOK in line]
    if len(hits) != 1:
        return [f"device/send.go: expected one {HOOK} call, found {len(hits)}  (G06)"]
    # the last line of code above the hook's comment block must be the anchor
    i = hits[0] - 1
    while i >= 0 and (not src[i].strip() or src[i].strip().startswith("//")):
        i -= 1
    if i < 0 or src[i].strip() != ANCHOR:
        above = src[i].strip() if i >= 0 else "(start of file)"
        return [f"device/send.go:{hits[0] + 1}: the hook must follow `{ANCHOR}`, "
                f"but follows `{above}`  (G06)"]
    return []


def check(repo, commit, branch):
    problems = []
    if branch.startswith("pr/"):
        problems += bad_replaces(repo, commit)
    if os.path.basename(os.path.abspath(repo)) == "amneziawg-go":
        problems += bad_hook(repo, commit)
    return problems


def report(name, branch, problems):
    if problems:
        print(f"FAIL {name} {branch}")
        for p in problems:
            print(f"     {p}")
    else:
        print(f"ok   {name} {branch}")


def all_branches():
    failed = False
    for name in FORKS:
        repo = os.path.join(ROOT, name)
        if not os.path.isdir(repo):
            continue
        refs = git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)",
                   "refs/heads/feat/", "refs/heads/pr/").split("\n")
        for ref in filter(None, refs):
            branch, commit = ref.split()
            if branch.endswith("-prerebase"):  # local snapshots, never pushed
                continue
            problems = check(repo, commit, branch)
            report(name, branch, problems)
            failed |= bool(problems)
    return failed


def pre_push():
    repo = git(".", "rev-parse", "--show-toplevel").strip()
    name = os.path.basename(repo)
    failed = False
    for line in sys.stdin:
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO:  # a deletion carries nothing to check
            continue
        branch = parts[2].removeprefix("refs/heads/")
        if not branch.startswith(("feat/", "pr/")):
            continue
        problems = check(repo, parts[1], branch)
        report(name, branch, problems)
        failed |= bool(problems)
    if failed:
        print("preflight: push refused. Fix the branch, or push with --no-verify on purpose.")
    return failed


def install():
    for name in FORKS:
        repo = os.path.join(ROOT, name)
        if not os.path.isdir(repo):
            continue
        hooks = git(repo, "rev-parse", "--git-path", "hooks").strip()
        path = os.path.join(repo, hooks) if not os.path.isabs(hooks) else hooks
        target = os.path.join(path, "pre-push")
        if os.path.exists(target):
            with open(target, encoding="utf-8") as f:
                if "preflight.py" not in f.read():
                    print(f"skip {name}: a foreign pre-push hook exists, merge by hand")
                    continue
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(HOOK_SCRIPT)
        os.chmod(target, 0o755)
        print(f"installed {name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pre-push", action="store_true", help="run as git's pre-push hook")
    ap.add_argument("--install", action="store_true", help="add the hook to the forks")
    args = ap.parse_args()
    if args.install:
        install()
        return 0
    return 1 if (pre_push() if args.pre_push else all_branches()) else 0


if __name__ == "__main__":
    sys.exit(main())
