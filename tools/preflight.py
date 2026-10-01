#!/usr/bin/env python3
"""Checks that a fork branch is fit to push, for the traps a clean build does not catch.

- G04: a `replace` onto our fork or onto a local path must never reach a `pr/*` branch.
  On `feat/*` branches it is how the recipes build, so there it is allowed.
- G06: in amneziawg-go the tunnel hook must sit right after `elem.padding = padding`.
  A rebase can put it one line higher, and that still compiles.
- A11: in amnezia-client the test build installs next to the store app under its own
  applicationId, label and FileProvider authority. A `pr/*` branch must keep upstream's.
- A12: the adb control of fork builds (AdbControl.kt) must never reach a `pr/*` branch.
- A13: in the three forks with a pull request, branches are layers: `pr/strict-split-tunneling`
  is contained in `release` and in every `followup/*`, and `release` in `lab`. A fix is made
  once, on the PR branch, and the layers above it are rebased onto it, never patched apart.

    python tools/preflight.py              # every local branch of the forks that is checked
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

# amnezia-client files and the upstream identity they must carry on a pr/* branch (A11)
IDENTITY = [
    ("client/android/build.gradle.kts", 'applicationId = "org.amnezia.vpn"'),
    ("client/android/AndroidManifest.xml", 'android:label="-- %%INSERT_APP_NAME%% --"'),
    ("client/android/AndroidManifest.xml", 'android:authorities="org.amnezia.vpn.qtprovider"'),
]

# A13: the layers of the forks that have a pull request, each contained in the next
PR_BRANCH = "pr/strict-split-tunneling"
LAYERED = {"amneziawg-go", "amneziawg-android", "amnezia-client"}
CHECKED = ("feat/", "pr/", "followup/", "release", "lab")

HOOK_SCRIPT = """#!/bin/sh
# Installed by tools/preflight.py --install in the umbrella repo. See G04, G06 and A11.
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


ADB_CONTROL = "client/android/src/org/amnezia/vpn/AdbControl.kt"


def bad_identity(repo, commit):
    found = []
    if ADB_CONTROL in git(repo, "ls-tree", "-r", "--name-only", commit).splitlines():
        found.append(f"{ADB_CONTROL}: the adb control is fork-only  (A12)")
    for path, line in IDENTITY:
        if line not in git(repo, "show", f"{commit}:{path}"):
            found.append(f"{path}: expected `{line}`: the side-by-side identity is fork-only  (A11)")
    return found


def is_ancestor(repo, a, b):
    return subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def has_branch(repo, branch):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet",
                           f"refs/heads/{branch}"], capture_output=True).returncode == 0


def bad_layer(repo, commit, branch):
    """A13: the layer below `branch` must be contained in it."""
    below = {"release": PR_BRANCH, "lab": "release"}.get(branch)
    if below is None and branch.startswith("followup/"):
        below = PR_BRANCH
    if below is None or not has_branch(repo, below) or is_ancestor(repo, below, commit):
        return []
    return [f"{branch} does not contain {below}: rebuild the layer with "
            f"`git rebase --onto {below} <old {below}> {branch}`  (A13)"]


def check(repo, commit, branch):
    problems = []
    if os.path.basename(os.path.abspath(repo)) in LAYERED:
        problems += bad_layer(repo, commit, branch)
    if branch.startswith("pr/"):
        problems += bad_replaces(repo, commit)
        if os.path.basename(os.path.abspath(repo)) == "amnezia-client":
            problems += bad_identity(repo, commit)
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
                   "refs/heads/").split("\n")
        for ref in filter(None, refs):
            branch, commit = ref.split()
            if not branch.startswith(CHECKED) or branch.endswith("-prerebase"):
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
        if not branch.startswith(CHECKED):
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
