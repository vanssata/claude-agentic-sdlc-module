"""Packages mode: configuration, export at close, verification, the pre-push
validator's checks, the git hook, migration, cleanup, restore, redaction and
pack (spec compact-project-memory §D4–§D6, §D9–§D13, §I4–§I6).

Files mode (no .ai/policies/memory.json, or mode "files") never reaches the
writers here: no .ai/memory/, no .ai/local/memory/, no hook (R15). state.py
is the only caller of the writers; the path guard refuses an agent's direct
write to either directory (R19). Nothing here reads a package to grant or
refuse anything.
The rest lives in the sibling modules beside it: memory_io, memory_config, memory_packages,
memory_verify, memory_hook, memory_risks, memory_cleanup, memory_migrate, memory_export and
memory_status; this module keeps the pre-push entry that the git hook runs by path.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_io as mio  # noqa: E402  pylint: disable=wrong-import-position
import memory_verify as mver  # noqa: E402  pylint: disable=wrong-import-position


# ------------------------------------------------------------------ the pre-push entry (§I5)
def _git_out(repo, *args):
    code, out, _ = mio.git(repo, *args)
    return code, out.strip()


def base_for_new_branch(repo, remote, lsha):
    """The merge-base with <remote>/HEAD, else with the nearest <remote>/* ref."""
    code, base = _git_out(repo, "merge-base", lsha, "refs/remotes/%s/HEAD" % remote)
    if code == 0 and base:
        return base
    code, refs = _git_out(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/%s/" % remote)
    best, best_time = None, -1
    for ref in refs.splitlines() if code == 0 else []:
        code, base = _git_out(repo, "merge-base", lsha, ref)
        if code != 0 or not base:
            continue
        code, stamp = _git_out(repo, "show", "-s", "--format=%ct", base)
        if code == 0 and stamp.isdigit() and int(stamp) > best_time:
            best, best_time = base, int(stamp)
    return best


def pre_push(argv, stdin):
    """The validator: the hook form (<remote> <url>, refs on stdin), --range or
    --tree; prints findings to stderr and returns 0 or 1."""
    repo = os.getcwd()
    if "--repo" in argv:
        i = argv.index("--repo")
        repo = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    jobs, local = [], False
    if argv[:1] == ["--range"] and len(argv) == 2 and ".." in argv[1]:
        old, new = argv[1].split("..", 1)
        new_sha = mver.rev(repo, new)
        if not new_sha:
            raise mio.MemoryError_("%s is not a commit" % new, 3)
        jobs.append((argv[1], mver.rev(repo, old), new_sha))
    elif argv[:1] == ["--tree"] and len(argv) == 2:
        sha = mver.rev(repo, argv[1])
        if not sha:
            raise mio.MemoryError_("%s is not a commit" % argv[1], 3)
        jobs.append((argv[1], None, sha))
    else:
        local = True
        remote = argv[0] if argv else "origin"
        for line in stdin.read().splitlines():
            parts = line.split()
            if len(parts) != 4:
                continue
            lref, lsha, _, rsha = parts
            if lsha == mio.ZERO_SHA or lref.startswith("refs/tags/"):
                continue                  # a deletion or a tag: nothing of ours travels
            known = rsha != mio.ZERO_SHA and _git_out(repo, "cat-file", "-e", rsha + "^{commit}")[0] == 0
            jobs.append((lref, rsha if known else base_for_new_branch(repo, remote, lsha), lsha))
    failing, shown, packages, tasks, ms = [], 0, 0, 0, 0
    for ref, old, new in jobs:
        findings, stats = mver.validate_range(repo, old, new, local=local)
        if findings is None:
            continue                      # files mode at T: not ours to check
        for f in findings[:mio.FINDINGS_MAX]:
            print("memory-pre-push: %s" % mver.format_finding(f, ref), file=sys.stderr)
        if len(findings) > mio.FINDINGS_MAX:
            print("… %d more — state.py memory verify --range %s..%s" % (
                len(findings) - mio.FINDINGS_MAX, (old or new)[:12], new[:12]), file=sys.stderr)
        failing += [f for f in findings if not f.check.endswith("-warn")]
        shown += len(findings)
        packages += stats.get("packages", 0)
        tasks += stats.get("tasks", 0)
        ms += stats.get("ms", 0)
    if shown:
        print("checked %d packages, %d tasks in %d ms" % (packages, tasks, ms), file=sys.stderr)
    return 1 if failing else 0


def pre_push_cli(argv):
    """Exit 0, 1, or 3 when the validator itself fails — closed, with the way out."""
    try:
        return pre_push(argv, sys.stdin)
    except Exception as exc:  # pylint: disable=broad-except  # fail closed
        print("memory-pre-push: validator error: %s — run 'state.py memory verify --all'; a human may push "
              "with 'git push --no-verify'" % exc, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(pre_push_cli(sys.argv[1:]))
