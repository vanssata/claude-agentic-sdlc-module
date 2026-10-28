#!/usr/bin/env python3
"""Tree snapshots, tree diffs and the project's own commands, for state.py.

Why a separate module: state.py owns every write to state.json and has no
subprocess use at all; this module shells out to git and to the commands written
in .ai/policies/testing.md, imports nothing from state.py, and never opens
state.json for writing. state.py imports it, not the reverse. Since redesign
2.6 it measures nothing else: the size budget, the re-score and the static
sensors (bite, duplicates, traceability, plan sections, lint, typecheck, detect)
are gone, and two facts decide a review (R6).

Everything is stdlib plus git. Nothing here spawns a model or reads the network.

A diff is always between two trees, never `git diff HEAD`: a task that started
on a dirty worktree, a step that shares a file with another step, and an
untracked new file all give the wrong answer otherwise. The trees come from a
throwaway index, so the developer's own index and worktree are never touched.

Usage:
  sensors.py snapshot [--root DIR]
  sensors.py diff     [--root DIR] [--from TREE] [--to TREE|--now] [--format text|json]
  sensors.py run      --scope step|suite|e2e|single [--files "a,b"] [--test NAME] [--log FILE]

Exit codes: 0 green or not applicable · 1 usage or internal error ·
            2 red · 3 unavailable.
"""

import argparse
import contextlib
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

GREEN, RED, UNAVAILABLE, NOT_APPLICABLE = "green", "red", "unavailable", "not_applicable"

OK, ERROR, REDCODE, UNKNOWNCODE = 0, 1, 2, 3


def find_root(start):
    """.ai/ if there is one, else the git top level, else where we were told.

    A missing .ai/ is not an error here the way it is in state.py: a tree
    snapshot or a command run needs no task.
    """
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    code, out = git(os.path.abspath(start), ["rev-parse", "--show-toplevel"])
    if code == 0 and out.strip():
        return out.strip()
    return os.path.abspath(start)


# --------------------------------------------------------------------------- git

def git(root, args, env=None, timeout=120):
    """Fixed argv, never a shell. Returns (exit code, stdout); stderr is dropped
    because every caller turns a failure into `unavailable` with its own words."""
    command = ["git", "--no-pager", "-c", "core.quotepath=off"] + args
    merged = dict(os.environ)
    merged["GIT_OPTIONAL_LOCKS"] = "0"
    if env:
        merged.update(env)
    try:
        # check=False on purpose: a non-zero git exit is an answer here
        # ("unavailable"), never an exception to climb out of.
        done = subprocess.run(command, cwd=root, env=merged, timeout=timeout, check=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return done.returncode, done.stdout.decode("utf-8", "replace")


def is_repo(root):
    code, out = git(root, ["rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def head_commit(root):
    code, out = git(root, ["rev-parse", "HEAD"])
    return out.strip() if code == 0 else None


def snapshot_tree(root):
    """The current worktree as a tree object, without touching the real index.

    A copy of the index is made in a temp file, everything is added to *that*
    index, the task's own bookkeeping is dropped from it, and the tree is
    written. The objects are unreachable and a normal `git gc` prunes them.
    Returns None when this is not a usable git repository.
    """
    if not is_repo(root):
        return None
    code, git_dir = git(root, ["rev-parse", "--absolute-git-dir"])
    if code != 0 or not git_dir.strip():
        return None
    real_index = os.path.join(git_dir.strip(), "index")
    handle, temp_index = tempfile.mkstemp(prefix="ai-sensors-index-")
    os.close(handle)
    try:
        if os.path.exists(real_index):
            # copy2, not copyfile: the copy keeps the index's mtime, which is what
            # git's racy-entry check compares against. A fresh mtime made a
            # same-size edit from the index's own second read as unchanged.
            shutil.copy2(real_index, temp_index)
        else:
            os.remove(temp_index)
        env = {"GIT_INDEX_FILE": temp_index}
        if git(root, ["add", "-A", "--", "."], env=env)[0] != 0:
            return None
        git(root, ["rm", "-r", "--cached", "--quiet", "--ignore-unmatch", "--",
                   ".ai/state", ".ai/reports", ".ai/memory"], env=env)
        code, out = git(root, ["write-tree"], env=env)
        return out.strip() if code == 0 and out.strip() else None
    finally:
        for leftover in (temp_index, temp_index + ".lock"):
            try:
                os.remove(leftover)
            except OSError:
                pass


def numstat(root, from_tree, to_tree):
    """[{path, added, deleted, binary}] between two trees, NUL-separated so a
    path with a space, a quote or a newline survives. Renames are off: a rename
    is an add plus a delete, as diff_files reports it."""
    code, out = git(root, ["diff", "--numstat", "--no-renames", "-z",
                           from_tree, to_tree])
    if code != 0:
        return None
    fields = out.split("\0")
    files, i = [], 0
    while i < len(fields):
        head = fields[i]
        if not head.strip():
            i += 1
            continue
        parts = head.split("\t")
        if len(parts) < 3:
            i += 1
            continue
        added, deleted, path = parts[0], parts[1], parts[2]
        if path == "":                    # a rename/copy pair: <a>\0<b>\0
            i += 2
            path = fields[i] if i < len(fields) else ""
        binary = added == "-" or deleted == "-"
        files.append({"path": path,
                      "added": 0 if binary else int(added or 0),
                      "deleted": 0 if binary else int(deleted or 0),
                      "binary": binary})
        i += 1
    return files


def diff_files(root, from_tree, to_tree):
    """[{path, status}] between two trees, status A, M, D or T (name-status,
    renames off, so a rename is a D plus an A and a deletion is never lost).
    None when either tree is missing: an unmeasured diff is not an empty one."""
    if not from_tree or not to_tree:
        return None
    code, out = git(root, ["diff", "--name-status", "--no-renames", "-z", from_tree, to_tree])
    if code != 0:
        return None
    fields = [f for f in out.split("\0") if f != ""]
    return [{"path": path, "status": status[:1]}
            for status, path in zip(fields[0::2], fields[1::2])]


# ------------------------------------------------------------------- matching


def scope_match(path, pattern):
    """The scope guard's semantics, exactly: bash `[[ $path == $pattern ]]`,
    where `*` crosses `/`, plus the directory-prefix rule. A file the guard
    allows must never be refused here, so this reads the plan the same way
    hooks/guard/scope.py does — a second reading would be a second policy."""
    if fnmatch.fnmatchcase(path, pattern):
        return True
    directory = pattern.rstrip("/")
    return bool(directory) and path.startswith(directory + "/")


def scope_any(path, patterns):
    for pattern in patterns or []:
        if pattern.strip() and scope_match(path, pattern):
            return pattern
    return None


# ------------------------------------------------------------------- running

TESTING_FIELDS = ("verify_command", "step_test_command", "e2e_command",
                  "lint_command", "typecheck_command", "single_test")

SCOPE_FIELD = {"suite": "verify_command", "step": "step_test_command",
               "e2e": "e2e_command", "single": "single_test"}


def testing_path(root):
    return os.path.join(root, ".ai", "policies", "testing.md")


def read_commands(root):
    """The project's own commands, as a human wrote them into testing.md.

    A line's value is everything after the colon, minus a trailing comment; the
    template ships the fields with an explanatory comment and no value, and that
    reads as "not written down yet", which is not the same as `none`.
    """
    commands = {}
    try:
        with open(testing_path(root), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return commands
    for field in TESTING_FIELDS:
        match = re.search(r"(?m)^%s:[ \t]*(.*)$" % re.escape(field), text)
        if not match:
            continue
        value = match.group(1).strip()
        if value.startswith("#"):
            value = ""
        commands[field] = value
    return commands


def command_for(root, scope):
    return (read_commands(root).get(SCOPE_FIELD.get(scope, ""), "") or "").strip()


def cap_log(path, limit):
    """A log is for a human and for grep, not for a context window. Past the
    limit the middle goes, because a failure shows itself at both ends."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if limit and size > limit:
        half = limit // 2
        with open(path, "rb") as fh:
            head = fh.read(half)
            fh.seek(size - half)
            tail = fh.read(half)
        with open(path, "wb") as fh:
            fh.write(head)
            fh.write(b"\n\n... %d bytes cut from the middle of this log ...\n\n" % (size - limit))
            fh.write(tail)


def run_command(root, command, log_path, timeout=1800, log_max_bytes=2097152):
    """One command, to the end, with its output in a file.

    No fail-fast flag is added and none is removed: the policy says the command
    itself must not stop at the first failure, because the caller fixes every
    failure as one batch. The session sees the exit code and a few lines; the
    log is what an agent reads, and only when the run was red.
    """
    if not command:
        return {"status": UNAVAILABLE, "detail": "no command", "exit": None,
                "duration_s": 0, "log": None, "command": ""}
    if command.strip() == "none":
        return {"status": NOT_APPLICABLE, "detail": "written as none", "exit": None,
                "duration_s": 0, "log": None, "command": command}
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    started = datetime.now(timezone.utc)
    with contextlib.ExitStack() as stack:
        sink = stack.enter_context(open(log_path, "wb")) if log_path else subprocess.DEVNULL
        try:
            # check=False: the exit code is the verdict the caller records.
            # stdin is /dev/null: a human's 'verify --by' runs from their own
            # terminal, and a suite must not prompt on it or detect it.
            done = subprocess.run(command, cwd=root, shell=True, timeout=timeout, check=False,
                                  stdin=subprocess.DEVNULL, stdout=sink,
                                  stderr=subprocess.STDOUT if log_path else subprocess.DEVNULL)
            code = done.returncode
            detail = ""
        except subprocess.TimeoutExpired:
            code, detail = None, "timed out after %ds" % timeout
        except OSError as exc:
            code, detail = None, "could not run: %s" % exc
    if log_path:
        cap_log(log_path, log_max_bytes)
    duration = int((datetime.now(timezone.utc) - started).total_seconds())
    return {"status": GREEN if code == 0 else (RED if code is not None else UNAVAILABLE),
            "detail": detail, "exit": code, "duration_s": duration,
            "log": log_path, "command": command}


def expand_files(command, files):
    """`{files}` where the runner takes paths; appended where it does not say."""
    paths = " ".join(shlex.quote(f) for f in files or [])
    if not paths:
        return command
    if "{files}" in command:
        return command.replace("{files}", paths)
    return "%s %s" % (command, paths)


# ---------------------------------------------------------------------- CLI


def resolve_trees(root, args):
    from_tree = args.from_tree
    if not from_tree:
        state = os.path.join(root, ".ai", "state", "state.json")
        if not os.path.isfile(state):
            state = os.path.join(root, ".ai", "state", "current.json")  # R34: legacy name, one version
        try:
            with open(state, encoding="utf-8") as fh:
                from_tree = ((json.load(fh) or {}).get("diff") or {}).get("base_tree")
        except (OSError, ValueError):
            from_tree = None
    to_tree = None if args.now else args.to_tree
    if not to_tree:
        to_tree = snapshot_tree(root)
    return from_tree, to_tree


def cmd_snapshot(_args, root):
    tree = snapshot_tree(root)
    if not tree:
        print("unavailable: not a git repository, or git could not write a tree")
        return UNKNOWNCODE
    print(tree)
    return OK


def cmd_diff(args, root):
    from_tree, to_tree = resolve_trees(root, args)
    files = diff_files(root, from_tree, to_tree)
    if files is None:
        print("unavailable: %s" % ("no base tree recorded" if not from_tree else
                                   "git could not compare the trees"))
        return UNKNOWNCODE
    if args.format == "json":
        print(json.dumps({"from": from_tree, "to": to_tree, "files": files}, indent=2, sort_keys=True))
        return OK
    for item in files:
        print("%s\t%s" % (item["status"], item["path"]))
    return OK


def tests_config(root):
    """The runner's caps from weight.json `tests`, the template's numbers otherwise."""
    try:
        with open(os.path.join(root, ".ai", "policies", "weight.json"), encoding="utf-8") as fh:
            config = (json.load(fh) or {}).get("tests") or {}
    except (OSError, ValueError, AttributeError):
        config = {}
    return config if isinstance(config, dict) else {}


def cmd_run(args, root):
    config = tests_config(root)
    command = command_for(root, args.scope)
    if not command:
        print("%-13s UNAVAIL  %s is not written down in .ai/policies/testing.md"
              % (args.scope, SCOPE_FIELD.get(args.scope, args.scope)))
        return UNKNOWNCODE
    files = [f.strip() for f in (args.files or "").split(",") if f.strip()]
    if args.test:
        command = command.replace("{test}", args.test)
        if "{test}" not in command_for(root, args.scope):
            command = "%s %s" % (command, shlex.quote(args.test))
    command = expand_files(command, files)
    log = args.log or os.path.join(root, ".ai", "reports", "tests-%s.log" % args.scope)
    result = run_command(root, command, log,
                         timeout=config.get("timeout_seconds", 1800),
                         log_max_bytes=config.get("log_max_bytes", 2097152))
    label = {GREEN: "green", RED: "RED", NOT_APPLICABLE: "n/a"}.get(result["status"], "UNAVAIL")
    print("%-13s %-8s exit %s in %ds" % (args.scope, label, result["exit"], result["duration_s"]))
    if result["detail"]:
        print("              %s" % result["detail"])
    if result["log"]:
        print("              log: %s" % os.path.relpath(result["log"], root))
    return {GREEN: OK, NOT_APPLICABLE: OK, RED: REDCODE}.get(result["status"], UNKNOWNCODE)


def build_parser():
    parser = argparse.ArgumentParser(prog="sensors.py", description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("snapshot"); p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("diff")
    p.add_argument("--from", dest="from_tree"); p.add_argument("--to", dest="to_tree")
    p.add_argument("--now", action="store_true")
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("run")
    p.add_argument("--scope", required=True, choices=["step", "suite", "e2e", "single"])
    p.add_argument("--files", default=""); p.add_argument("--test", default="")
    p.add_argument("--log", default="")
    p.set_defaults(func=cmd_run)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return ERROR
    root = find_root(args.root)
    return args.func(args, root)


if __name__ == "__main__":
    sys.exit(main())
