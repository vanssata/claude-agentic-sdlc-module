#!/usr/bin/env python3
"""Deterministic sensors for /ai-task — measurement, never judgement.

Why a separate module: state.py owns every write to current.json and has no
subprocess use at all; the sensors shell out to git and to the project's own
commands, and they must also run without a task (/ai-status, `detect` during
/ai-init). So this module measures and reports, imports nothing from state.py,
and never opens current.json for writing. state.py imports it, not the reverse.

Everything is stdlib plus git and the commands written in .ai/policies/testing.md.
Nothing here spawns a model, reads the network, or prints more than a dozen lines:
a sensor that needed a model to interpret it would be a review, not a sensor.

A measurement is always bound to the tree it was taken on. Two trees, never
`git diff HEAD`: a task that started on a dirty worktree, a step that shares a
file with another step, and an untracked new file all give the wrong answer
otherwise. The trees come from a throwaway index, so the developer's own index
and worktree are never touched.

Usage:
  sensors.py snapshot [--root DIR]
  sensors.py diff     [--root DIR] [--from TREE] [--to TREE|--now] [--tier T2]
                      [--allowed "a,b"] [--scope step|task] [--format text|json]
  sensors.py rescore  [--root DIR] [--from TREE] [--to TREE|--now] [--declared T2]
  sensors.py run      --scope step|suite|e2e|single [--files "a,b"] [--test NAME]
                      [--at now|base] [--log FILE]
  sensors.py check    [--only lint,typecheck,…] [--no-bite] [--json FILE]
  sensors.py report   [--json FILE]
  sensors.py bite     [--restore]
  sensors.py detect   [--root DIR]

Exit codes: 0 green or not applicable · 1 usage or internal error ·
            2 at least one red · 3 at least one unavailable or stale, none red.
"""

import argparse
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

GREEN, RED, UNAVAILABLE, NOT_APPLICABLE, STALE = (
    "green", "red", "unavailable", "not_applicable", "stale")

OK, ERROR, REDCODE, UNKNOWNCODE = 0, 1, 2, 3

TIERS = ["T0", "T1", "T2", "T3", "T4", "T5"]

# Defaults for a project whose risk-tiers.json predates WP4. They are the same
# numbers the template ships, so a project that never updates still gets a
# measurement — it simply never gets a gate it did not ask for.
DEFAULT_DIFF_BUDGET = {
    "per_step": {"T0": {"max_lines": 300, "max_files": 15},
                 "T1": {"max_lines": 120, "max_files": 5},
                 "T2": {"max_lines": 200, "max_files": 8},
                 "T3": {"max_lines": 250, "max_files": 10},
                 "T4": {"max_lines": 150, "max_files": 6},
                 "T5": {"max_lines": 150, "max_files": 6}},
    "per_task": {"T0": {"max_lines": 600, "max_files": 30},
                 "T1": {"max_lines": 300, "max_files": 10},
                 "T2": {"max_lines": 400, "max_files": 15},
                 "T3": {"max_lines": 800, "max_files": 30},
                 "T4": {"max_lines": 400, "max_files": 15},
                 "T5": {"max_lines": 400, "max_files": 15}},
    "exclude": ["**/*.lock", "package-lock.json", "composer.lock",
                "**/__snapshots__/**", "**/*.snap", "**/*.min.*", "**/*.map",
                "**/generated/**", "**/*.generated.*",
                ".ai/state/**", ".ai/reports/**"],
    "unbudgeted_scopes": ["docs"],
}

DEFAULT_PATH_SCOPES = [
    {"scope": "pipeline", "min_tier": "T3",
     "paths": [".ai/policies/**", ".ai/workflows/**", ".claude/**", ".codex/**",
               "CLAUDE.md", "AGENTS.md"]},
    {"scope": "tests", "min_tier": "T1",
     "paths": ["tests/**", "spec/**", "**/*Test.php", "**/*.test.*",
               "**/*.spec.*", "**/test_*.py"]},
    {"scope": "docs", "min_tier": "T0",
     "paths": ["docs/**", "**/*.md", "**/*.rst", "**/*.txt"]},
    {"scope": "migrations", "min_tier": "T5",
     "paths": ["**/migrations/**", "**/Migrations/**", "db/migrate/**"]},
    {"scope": "infra", "min_tier": "T5",
     "paths": ["Dockerfile*", "docker-compose*", "k8s/**", "helm/**",
               "terraform/**", ".github/workflows/**"]},
    {"scope": "auth", "min_tier": "T4",
     "paths": ["**/Security/**", "**/Auth/**", "**/auth/**"]},
    {"scope": "payments", "min_tier": "T4",
     "paths": ["**/Payment/**", "**/Billing/**", "**/Tax/**", "**/Invoice/**"]},
    {"scope": "config", "min_tier": "T3", "paths": ["config/**", ".env*"]},
    {"scope": "dependencies", "min_tier": "T3",
     "paths": ["composer.json", "package.json", "pyproject.toml",
               "requirements*.txt", "go.mod"]},
]

# The sensor set a project gets when its risk-tiers.json predates WP4. It is the
# template's, and it is deliberately the strict reading: a project with no policy
# at all must not turn out to be the one project where every sensor is optional
# and therefore every review is skippable.
DEFAULT_SENSORS = {
    "skip_review_at_or_below": "T2",
    "required_for_skip": ["tests", "lint", "typecheck", "diff", "rescore",
                          "traceability", "duplicates", "bite"],
    "tests": {"timeout_seconds": 1800, "env_retries": 1, "max_suite_runs": 5,
              "log_max_bytes": 2097152},
    "lint": {"timeout_seconds": 600},
    "typecheck": {"timeout_seconds": 600},
    "bite": {"timeout_seconds": 600, "required_from": "T2"},
    "duplicates": {"min_lines": 8, "ignore_scopes": ["tests", "docs"]},
}

# marker file (glob, relative to the root) -> the testing.md line to propose.
# detect never runs any of these: a tool that downloads packages or warms a
# cache on its first run would turn a measurement into a surprise.
LINT_MARKERS = [
    (".php-cs-fixer.dist.php", "lint_command: vendor/bin/php-cs-fixer fix --dry-run --diff"),
    (".php-cs-fixer.php", "lint_command: vendor/bin/php-cs-fixer fix --dry-run --diff"),
    ("phpcs.xml", "lint_command: vendor/bin/phpcs"),
    ("phpcs.xml.dist", "lint_command: vendor/bin/phpcs"),
    ("eslint.config.js", "lint_command: npx eslint ."),
    ("eslint.config.mjs", "lint_command: npx eslint ."),
    (".eslintrc.json", "lint_command: npx eslint ."),
    (".eslintrc.js", "lint_command: npx eslint ."),
    ("ruff.toml", "lint_command: ruff check ."),
    (".ruff.toml", "lint_command: ruff check ."),
    (".pylintrc", "lint_command: python3 -m pylint $(git ls-files '*.py')"),
    (".golangci.yml", "lint_command: golangci-lint run"),
]

TYPECHECK_MARKERS = [
    ("phpstan.neon", "typecheck_command: vendor/bin/phpstan analyse --no-progress"),
    ("phpstan.neon.dist", "typecheck_command: vendor/bin/phpstan analyse --no-progress"),
    ("psalm.xml", "typecheck_command: vendor/bin/psalm --no-progress"),
    ("tsconfig.json", "typecheck_command: npx tsc --noEmit"),
    ("mypy.ini", "typecheck_command: mypy ."),
    (".mypy.ini", "typecheck_command: mypy ."),
    ("pyrightconfig.json", "typecheck_command: npx pyright"),
]

# pyproject.toml and package.json carry the tool in a section, not in a name.
PYPROJECT_SECTIONS = [("[tool.ruff", "lint_command: ruff check ."),
                      ("[tool.mypy", "typecheck_command: mypy .")]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(message, code=ERROR):
    print("sensors.py: %s" % message, file=sys.stderr)
    sys.exit(code)


def find_root(start):
    """.ai/ if there is one, else the git top level, else where we were told.

    detect runs during /ai-init, before .ai/ exists, so a missing .ai/ is not
    an error here the way it is in state.py.
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
        done = subprocess.run(command, cwd=root, env=merged, timeout=timeout,
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
            shutil.copyfile(real_index, temp_index)
        else:
            os.remove(temp_index)
        env = {"GIT_INDEX_FILE": temp_index}
        if git(root, ["add", "-A", "--", "."], env=env)[0] != 0:
            return None
        git(root, ["rm", "-r", "--cached", "--quiet", "--ignore-unmatch", "--",
                   ".ai/state", ".ai/reports"], env=env)
        code, out = git(root, ["write-tree"], env=env)
        return out.strip() if code == 0 and out.strip() else None
    finally:
        for leftover in (temp_index, temp_index + ".lock"):
            try:
                os.remove(leftover)
            except OSError:
                pass


def tree_exists(root, tree):
    if not tree:
        return False
    return git(root, ["cat-file", "-e", "%s^{tree}" % tree])[0] == 0


def numstat(root, from_tree, to_tree):
    """[{path, added, deleted, binary}] between two trees, NUL-separated so a
    path with a space, a quote or a newline survives. Renames are off: a rename
    is an add plus a delete, which is what a budget should count."""
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


# ------------------------------------------------------------------- matching

def glob_to_regex(pattern):
    """Policy globs: `**` crosses directories, `*` does not, `**/` also matches
    zero directories (so `**/*.md` covers README.md), a trailing `/` is a
    directory prefix. This is the gitignore-shaped reading a human writing a
    policy file expects — it is NOT the shell's, see scope_match."""
    out, i = [], 0
    if pattern.endswith("/"):
        pattern = pattern.rstrip("/") + "/**"
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:[^/]*/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = pattern[i + 1:end]
                body = ("^" + body[1:]) if body.startswith("!") else body
                out.append("[%s]" % body)
                i = end + 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


_GLOB_CACHE = {}


def glob_match(path, pattern):
    compiled = _GLOB_CACHE.get(pattern)
    if compiled is None:
        compiled = _GLOB_CACHE[pattern] = glob_to_regex(pattern)
    return compiled.match(path) is not None


def glob_any(path, patterns):
    for pattern in patterns or []:
        if glob_match(path, pattern):
            return pattern
    return None


def scope_match(path, pattern):
    """The scope guard's semantics, exactly: bash `[[ $path == $pattern ]]`,
    where `*` crosses `/`, plus the directory-prefix rule. A file the guard
    allows must never be refused here, so this reads the plan the same way
    hooks/ai-scope-guard.sh does — a second reading would be a second policy."""
    if fnmatch.fnmatchcase(path, pattern):
        return True
    directory = pattern.rstrip("/")
    return bool(directory) and path.startswith(directory + "/")


def scope_any(path, patterns):
    for pattern in patterns or []:
        if pattern.strip() and scope_match(path, pattern):
            return pattern
    return None


# -------------------------------------------------------------------- policy

def policy_path(root):
    return os.path.join(root, ".ai", "policies", "risk-tiers.json")


def load_policy(root):
    """The project's risk-tiers.json, with WP4's keys defaulted. A project that
    has not run /project-update yet measures with the shipped numbers rather
    than not measuring at all."""
    data = {}
    try:
        with open(policy_path(root), encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            data = loaded
    except (OSError, ValueError):
        data = {}
    budget = data.get("diff_budget")
    if not isinstance(budget, dict):
        budget = {}
    merged_budget = dict(DEFAULT_DIFF_BUDGET)
    merged_budget.update({k: v for k, v in budget.items() if not k.startswith("_")})
    scopes = data.get("path_scopes")
    if not isinstance(scopes, list) or not scopes:
        scopes = DEFAULT_PATH_SCOPES
    sensor_config = dict(DEFAULT_SENSORS)
    if isinstance(data.get("sensors"), dict):
        sensor_config.update({k: v for k, v in data["sensors"].items()
                              if not k.startswith("_")})
    return {"diff_budget": merged_budget, "path_scopes": scopes,
            "sensors": sensor_config,
            "remediation_rounds": data.get("remediation_rounds", 2),
            "source": policy_path(root) if data else "defaults"}


def tier_index(tier):
    return TIERS.index(tier) if tier in TIERS else -1


def tier_max(a, b):
    return a if tier_index(a) >= tier_index(b) else b


def budget_for(policy, scope, tier):
    table = policy["diff_budget"].get("per_step" if scope == "step" else "per_task", {})
    entry = table.get(tier) if isinstance(table, dict) else None
    if not isinstance(entry, dict):
        entry = {}
    return {"max_lines": entry.get("max_lines"), "max_files": entry.get("max_files")}


def scope_of(path, path_scopes):
    """First match wins, in the order the policy lists them — that is why
    `pipeline` is written above `docs` and `tests` above `payments`."""
    for entry in path_scopes:
        if not isinstance(entry, dict):
            continue
        if glob_any(path, entry.get("paths")):
            return entry.get("scope") or "source", entry.get("min_tier") or "T0"
    return "source", "T0"


# ----------------------------------------------------------------- measuring

def measure(root, from_tree, to_tree, policy, tier="T2", allowed=None, scope="step",
            deferred_to=None, not_mine=None):
    """Everything step-done needs, in one pass over the file list.

    `allowed` is the step's own files, read the way the scope guard reads them.
    `deferred_to` is every other step's files and `not_mine` this step's own
    forbidden files: a change there is planned work that belongs to a different
    step, so it is neither counted against this step's budget nor called a
    scope violation. That is what makes a split after a refusal mean something
    — the files move to the sibling step, this step is told they are not its
    business, and it is then measured over what is left. `not_mine` is checked
    first, because a split narrows a step whose own glob still matches the
    files it gave away.
    """
    result = {"status": UNAVAILABLE, "from": from_tree, "to": to_tree,
              "scope": scope, "tier": tier, "files": 0, "added": 0, "deleted": 0,
              "lines": 0, "excluded_lines": 0, "unbudgeted_lines": 0,
              "unscoped": [], "deferred": [], "binary": [], "scopes": [], "over": [],
              "budget": budget_for(policy, scope, tier), "measured_at": now(),
              "detail": ""}
    if not from_tree or not to_tree:
        result["detail"] = "no base tree recorded"
        return result
    if not is_repo(root):
        result["detail"] = "not a git repository"
        return result
    for tree in (from_tree, to_tree):
        if not tree_exists(root, tree):
            result["detail"] = "tree %s is gone (pruned?)" % tree[:9]
            return result
    files = numstat(root, from_tree, to_tree)
    if files is None:
        result["detail"] = "git diff failed"
        return result

    excluded = policy["diff_budget"].get("exclude") or []
    unbudgeted = policy["diff_budget"].get("unbudgeted_scopes") or []
    scopes, per_file = [], []
    for item in files:
        path, lines = item["path"], item["added"] + item["deleted"]
        if item["binary"]:
            result["binary"].append(path)
        if glob_any(path, excluded):
            result["excluded_lines"] += lines
            continue
        name, min_tier = scope_of(path, policy["path_scopes"])
        if name not in scopes:
            scopes.append(name)
        if name in unbudgeted:
            result["unbudgeted_lines"] += lines
            continue
        if not_mine and scope_any(path, not_mine):
            result["deferred"].append(path)
            continue
        if allowed is not None and not scope_any(path, allowed):
            if deferred_to and scope_any(path, deferred_to):
                result["deferred"].append(path)
                continue
            result["unscoped"].append(path)
        result["files"] += 1
        result["added"] += item["added"]
        result["deleted"] += item["deleted"]
        per_file.append((path, lines, name, min_tier))
    result["lines"] = result["added"] + result["deleted"]
    result["scopes"] = scopes
    result["per_file"] = per_file

    budget = result["budget"]
    if budget.get("max_lines") is not None and result["lines"] > budget["max_lines"]:
        result["over"].append("%d lines > %d" % (result["lines"], budget["max_lines"]))
    if budget.get("max_files") is not None and result["files"] > budget["max_files"]:
        result["over"].append("%d files > %d" % (result["files"], budget["max_files"]))
    result["status"] = RED if (result["over"] or result["unscoped"]) else GREEN
    return result


def rescore(declared, measurement, policy):
    """max(declared, the tier every touched scope demands, declared+1 when the
    task is over its budget). It never returns anything lower than `declared`:
    downgrade_rule says only a human lowers a tier, in writing."""
    out = {"status": UNAVAILABLE, "tier": declared, "reasons": [],
           "declared": declared, "over_budget": False}
    if measurement["status"] == UNAVAILABLE:
        out["detail"] = measurement.get("detail") or "diff unavailable"
        return out
    tier = declared if declared in TIERS else "T0"
    for path, _lines, name, min_tier in measurement.get("per_file", []):
        if tier_index(min_tier) > tier_index(tier):
            tier = min_tier
            out["reasons"].append("%s (%s)" % (name, path))
    if measurement["over"] and measurement["scope"] == "task":
        out["over_budget"] = True
        raised = TIERS[min(tier_index(tier) + 1, len(TIERS) - 1)]
        if raised != tier:
            out["reasons"].append("over the task budget: %s" % "; ".join(measurement["over"]))
            tier = raised
    out["tier"] = tier
    out["status"] = RED if tier_index(tier) > tier_index(declared) else GREEN
    return out


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
    handle = open(log_path, "wb") if log_path else subprocess.DEVNULL
    try:
        done = subprocess.run(command, cwd=root, shell=True, timeout=timeout,
                              stdout=handle if log_path else subprocess.DEVNULL,
                              stderr=subprocess.STDOUT if log_path else subprocess.DEVNULL)
        code = done.returncode
        detail = ""
    except subprocess.TimeoutExpired:
        code, detail = None, "timed out after %ds" % timeout
    except OSError as exc:
        code, detail = None, "could not run: %s" % exc
    finally:
        if log_path:
            handle.close()
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


# ------------------------------------------------- running against the base tree

def lock_path(root):
    return os.path.join(root, ".ai", "state", "bite.lock")


def changed_paths(root, from_tree, to_tree, source_only=True, scopes=None):
    files = numstat(root, from_tree, to_tree) or []
    paths = []
    for item in files:
        path = item["path"]
        if source_only and scopes is not None:
            name, _min_tier = scope_of(path, scopes)
            if name in ("tests", "docs"):
                continue
        paths.append(path)
    return paths


def revert_to(root, tree, paths):
    """Put these paths back as `tree` has them, without touching the index.

    A file the tree does not have is one the change added, and reverting it
    means removing it. Everything here is recoverable from `tree_after`, which
    the caller wrote down before calling — see restore_from.
    """
    if not paths:
        return True
    if git(root, ["restore", "--source=%s" % tree, "--worktree", "--"] + paths)[0] == 0:
        return True
    # git < 2.23, or a path the tree does not carry: do it one at a time, and
    # delete what the tree does not have rather than leaving a half-revert.
    ok = True
    for path in paths:
        if git(root, ["cat-file", "-e", "%s:%s" % (tree, path)])[0] == 0:
            if git(root, ["checkout", tree, "--", path])[0] != 0:
                ok = False
        else:
            try:
                os.remove(os.path.join(root, path))
            except OSError:
                pass
    return ok


def restore_from(root, tree, paths):
    """The counterpart, and the reason a revert is safe: every path goes back to
    the tree the caller snapshotted before it touched anything."""
    return revert_to(root, tree, paths)


def write_lock(root, data):
    try:
        os.makedirs(os.path.dirname(lock_path(root)), exist_ok=True)
        with open(lock_path(root), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def read_lock(root):
    try:
        with open(lock_path(root), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def clear_lock(root):
    try:
        os.remove(lock_path(root))
    except OSError:
        pass


def run_at_base(root, command, base_tree, log_path, timeout=600, log_max_bytes=2097152,
                scopes=None):
    """Run a command against the code as it was before this task touched it.

    The worktree is reverted in place, from immutable tree objects, and restored
    from the tree that was snapshotted first. A lock file holds that tree and
    the paths, so an interrupted run is recoverable rather than a mystery — and
    the restore is asserted by tree hash, not assumed.
    """
    result = {"status": UNAVAILABLE, "detail": "", "exit": None, "duration_s": 0,
              "log": log_path, "command": command, "restored": None, "reverted": []}
    if not base_tree or not is_repo(root):
        result["detail"] = "no base tree, or not a git repository"
        return result
    before = snapshot_tree(root)
    if not before:
        result["detail"] = "could not snapshot the worktree"
        return result
    paths = changed_paths(root, base_tree, before, scopes=scopes)
    if not paths:
        result["status"] = NOT_APPLICABLE
        result["detail"] = "nothing changed outside tests and docs"
        result["restored"] = before
        return result
    write_lock(root, {"tree_after": before, "paths": paths, "at": now(),
                      "why": "running the tests against the base tree"})
    print("recovery: if this is interrupted, run "
          "`python3 sensors.py --root . bite --restore` to put the worktree back",
          file=sys.stderr)
    try:
        result["reverted"] = paths
        if not revert_to(root, base_tree, paths):
            result["detail"] = "could not revert the worktree"
            return result
        run = run_command(root, command, log_path, timeout=timeout,
                          log_max_bytes=log_max_bytes)
        result.update({k: run[k] for k in ("exit", "duration_s", "log", "command")})
        result["status"] = run["status"]
        result["detail"] = run["detail"]
    finally:
        restore_from(root, before, paths)
        result["restored"] = snapshot_tree(root)
        if result["restored"] == before:
            clear_lock(root)
        else:
            result["detail"] = ((result["detail"] + "; ") if result["detail"] else "") + \
                "the worktree did not restore to %s — see %s" % (before[:9], lock_path(root))
            result["status"] = UNAVAILABLE
    return result


# ------------------------------------------------------------------- detect

def detect(root):
    """What a human could write into testing.md, derived from marker files.
    Nothing is executed, and nothing is written: the proposal is the output."""
    found = {"lint": [], "typecheck": []}
    for marker, line in LINT_MARKERS:
        if os.path.exists(os.path.join(root, marker)):
            found["lint"].append((marker, line))
    for marker, line in TYPECHECK_MARKERS:
        if os.path.exists(os.path.join(root, marker)):
            found["typecheck"].append((marker, line))
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = ""
        for section, line in PYPROJECT_SECTIONS:
            if section in text:
                found["lint" if line.startswith("lint") else "typecheck"].append(
                    ("pyproject.toml %s]" % section, line))
    package = os.path.join(root, "package.json")
    if os.path.exists(package):
        try:
            with open(package, encoding="utf-8") as fh:
                scripts = (json.load(fh) or {}).get("scripts") or {}
        except (OSError, ValueError):
            scripts = {}
        if "lint" in scripts:
            found["lint"].append(("package.json scripts.lint", "lint_command: npm run lint"))
        for name in ("typecheck", "type-check", "tsc"):
            if name in scripts:
                found["typecheck"].append(("package.json scripts.%s" % name,
                                           "typecheck_command: npm run %s" % name))
                break
    return found


# ----------------------------------------------------------- static sensors
# Each returns {"status": …, "detail": …} and knows nothing about the others.
# The rule they share: a sensor is green only when it measured something. Not
# finding a tool is `unavailable`, which keeps the review the tier asked for —
# the one thing it must never do is look like a pass.

def read_state(root):
    """Read-only. sensors.py never writes the task state; state.py owns it."""
    try:
        with open(os.path.join(root, ".ai", "state", "current.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def sensor_tests(root, state, tree):
    runs = [r for r in ((state.get("tests") or {}).get("runs") or [])
            if r.get("scope") == "suite"]
    if not runs:
        if not command_for(root, "suite"):
            return {"status": UNAVAILABLE, "detail": "verify_command is not in testing.md"}
        return {"status": UNAVAILABLE,
                "detail": "no suite run yet — state.py test-run --scope suite"}
    last = runs[-1]
    if last.get("exit") != 0:
        return {"status": RED, "detail": "suite run %d exited %s, log %s"
                % (last.get("n"), last.get("exit"), last.get("log")),
                "log": last.get("log")}
    if tree and last.get("tree") and last["tree"] != tree:
        return {"status": STALE,
                "detail": "the last green run was on %s, the worktree is at %s"
                          % (last["tree"][:9], tree[:9]), "log": last.get("log")}
    return {"status": GREEN, "detail": "verify_command exit 0 in %ds, run %s, log %s"
            % (last.get("duration_s", 0), last.get("n"), last.get("log")),
            "log": last.get("log")}


def sensor_command(root, kind, policy, task_id):
    """lint and typecheck: the same shape, and the same refusal to guess."""
    field = "%s_command" % kind
    value = (read_commands(root).get(field) or "").strip()
    if value == "none":
        return {"status": NOT_APPLICABLE, "detail": "%s: none (testing.md)" % field}
    if not value:
        proposals = detect(root).get("lint" if kind == "lint" else "typecheck") or []
        if proposals:
            marker, line = proposals[0]
            return {"status": UNAVAILABLE,
                    "detail": "%s missing — detected %s" % (field, marker),
                    "proposal": line}
        return {"status": UNAVAILABLE,
                "detail": '%s missing — write it, or `%s: none`, in .ai/policies/testing.md'
                          % (field, field)}
    config = (policy.get("sensors") or {}).get(kind) or {}
    log = os.path.join(root, ".ai", "reports", task_id or "", "%s.log" % kind)
    run = run_command(root, value, log, timeout=config.get("timeout_seconds", 600))
    if run["exit"] == 0:
        return {"status": GREEN, "detail": "%s exit 0 in %ds" % (value, run["duration_s"]),
                "log": os.path.relpath(log, root)}
    if run["exit"] is None:
        return {"status": UNAVAILABLE, "detail": run["detail"] or "could not run %s" % value}
    if run["exit"] == 127:
        return {"status": UNAVAILABLE, "detail": "%s: command not found" % value}
    return {"status": RED, "detail": "%s exited %s, log %s"
            % (value, run["exit"], os.path.relpath(log, root)),
            "log": os.path.relpath(log, root)}


def test_exists(root, name):
    """A named test resolves when the path is there, or the glob finds a file,
    or a file of that basename exists somewhere. A filter name nobody can
    resolve is not proof that a test was written."""
    if not name:
        return False
    if os.path.exists(os.path.join(root, name)):
        return True
    import glob as _glob
    if _glob.glob(os.path.join(root, name)):
        return True
    base = os.path.basename(name)
    if base != name:
        return False
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "vendor", "node_modules", ".venv", ".ai")]
        if base in files:
            return True
    return False


def sensor_traceability(root, state, measurement, policy):
    """A step that changed source and named no test is a step whose evidence is
    somebody else's. Cheap to check, and review-economy §6 says checks like this
    never go to a thinking model."""
    plan = (state.get("approved_plan") or {}).get("steps") or []
    if not plan:
        return {"status": UNAVAILABLE, "detail": "no approved plan"}
    touched_source = False
    untraced, missing = [], []
    scopes = policy["path_scopes"]
    for step in plan:
        if step.get("kind") == "remediation" or step.get("status") != "done":
            continue
        diff = step.get("diff") or {}
        source = False
        for path in (diff.get("paths") or []) or []:
            name, _tier = scope_of(path, scopes)
            source = source or name not in ("tests", "docs")
        if not diff.get("paths"):
            source = bool(diff.get("files"))
        if not source:
            continue
        touched_source = True
        tests = step.get("required_tests") or []
        if not tests:
            untraced.append(step["step_id"])
            continue
        for name in tests:
            if not test_exists(root, name):
                missing.append("%s: %s" % (step["step_id"], name))
    if not touched_source:
        return {"status": NOT_APPLICABLE, "detail": "no finished step changed source"}
    if untraced:
        return {"status": RED, "detail": "steps with no test named: %s" % ", ".join(untraced),
                "untraced": untraced}
    if missing:
        return {"status": RED, "detail": "named tests that do not resolve: %s"
                % "; ".join(missing[:5]), "untraced": missing}
    done = [s["step_id"] for s in plan if s.get("status") == "done"]
    return {"status": GREEN, "detail": "%d/%d finished steps name tests that exist"
            % (len(done), len(done))}


def normalise(line):
    return re.sub(r"\s+", " ", line.strip())


def sensor_duplicates(root, from_tree, to_tree, policy):
    """The same block written twice in this change. Not a style opinion: it is
    the cheapest half of what a reviewer would have to read the diff to find."""
    config = (policy.get("sensors") or {}).get("duplicates") or {}
    window = config.get("min_lines", 8)
    ignore = config.get("ignore_scopes") or ["tests", "docs"]
    if not from_tree or not to_tree:
        return {"status": UNAVAILABLE, "detail": "diff unavailable"}
    files = numstat(root, from_tree, to_tree)
    if files is None:
        return {"status": UNAVAILABLE, "detail": "diff unavailable"}
    blocks, added_any = {}, False
    for item in files:
        path = item["path"]
        if item["binary"]:
            continue
        name, _tier = scope_of(path, policy["path_scopes"])
        if name in ignore:
            continue
        if item["added"]:
            added_any = True
        try:
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as fh:
                lines = [normalise(l) for l in fh.read().split("\n")]
        except OSError:
            continue
        lines = [(i + 1, l) for i, l in enumerate(lines) if len(l) > 3]
        for i in range(0, max(0, len(lines) - window + 1)):
            chunk = lines[i:i + window]
            key = "\n".join(l for _n, l in chunk)
            blocks.setdefault(key, []).append("%s:%d" % (path, chunk[0][0]))
    if not added_any:
        return {"status": NOT_APPLICABLE, "detail": "nothing added outside tests and docs"}
    found = [places for places in blocks.values() if len(places) > 1]
    if found:
        first = found[0]
        return {"status": RED,
                "detail": "%d block(s) of >= %d lines appear twice: %s"
                          % (len(found), window, " ~ ".join(first[:2])),
                "blocks": [places[:2] for places in found[:5]]}
    return {"status": GREEN, "detail": "0 blocks >= %d lines repeat" % window}


MUST_FAIL_WORKFLOWS = ("feature", "bugfix", "hotfix")


def required_tests_of(state):
    """What the plan said would prove each step, split by what it must do
    against the code as it was: a characterization test describes behaviour
    that already exists, so it must PASS at the base; a feature or bugfix test
    describes behaviour that does not exist yet, so it must FAIL there."""
    must_fail, must_pass = [], []
    workflow = state.get("workflow") or "feature"
    for step in ((state.get("approved_plan") or {}).get("steps") or []):
        if step.get("status") != "done" or step.get("kind") == "remediation":
            continue
        target = must_pass if (step.get("kind") == "characterization"
                               or workflow == "refactoring") else must_fail
        for name in step.get("required_tests") or []:
            if name not in target:
                target.append(name)
    return must_fail, must_pass


def bite(root, state, policy, tree=None):
    """Run the tests the plan named against the code before this task touched it.

    A suite that passes proves the code is healthy. It does not prove the tests
    reach the change — a test that never touches the new code passes just as
    green before the change as after it, and a review skipped on that evidence
    was skipped on nothing. So: revert, run, restore, and check each test did
    what its kind promises.

    The worktree is reverted in place from tree objects and restored from the
    tree snapshotted first; the lock file and `bite --restore` are the recovery
    path, and the restored tree hash is asserted, not assumed.
    """
    result = {"status": UNAVAILABLE, "detail": "", "must_fail": None, "must_pass": None,
              "restored": None}
    workflow = state.get("workflow")
    if workflow == "investigation":
        return {"status": NOT_APPLICABLE, "detail": "an investigation changes nothing to prove"}
    command = command_for(root, "step")
    if not command:
        result["detail"] = "step_test_command is not in testing.md"
        return result
    base = (state.get("diff") or {}).get("base_tree")
    if not base or not is_repo(root):
        result["detail"] = "no base tree recorded for this task"
        return result
    must_fail, must_pass = required_tests_of(state)
    if not must_fail and not must_pass:
        result["detail"] = "no finished step named a test — traceability says the same"
        return result
    config = (policy.get("sensors") or {}).get("bite") or {}
    timeout = config.get("timeout_seconds", 600)
    task_id = state.get("task_id") or ""

    before = snapshot_tree(root)
    if not before:
        result["detail"] = "could not snapshot the worktree"
        return result
    paths = changed_paths(root, base, before, scopes=policy["path_scopes"])
    if not paths:
        return {"status": NOT_APPLICABLE, "detail": "no source changed outside tests and docs",
                "restored": before}
    write_lock(root, {"tree_after": before, "paths": paths, "at": now(),
                      "why": "the must-bite check is running"})
    print("recovery: if this is interrupted, run `sensors.py --root . bite --restore`",
          file=sys.stderr)
    runs = {}
    try:
        if not revert_to(root, base, paths):
            result["detail"] = "could not revert the worktree"
            return result
        for label, names in (("must_fail", must_fail), ("must_pass", must_pass)):
            if not names:
                continue
            log = os.path.join(root, ".ai", "reports", task_id, "bite-%s.log" % label)
            runs[label] = run_command(root, expand_files(command, names), log,
                                      timeout=timeout)
    finally:
        restore_from(root, before, paths)
        result["restored"] = snapshot_tree(root)
    if result["restored"] != before:
        result["status"] = UNAVAILABLE
        result["detail"] = ("the worktree did not restore to %s — it is at %s; the lock is kept "
                            "at %s" % (before[:9], (result["restored"] or "?")[:9],
                                       os.path.relpath(lock_path(root), root)))
        return result
    clear_lock(root)

    problems, notes = [], []
    for label, names in (("must_fail", must_fail), ("must_pass", must_pass)):
        run = runs.get(label)
        if not names:
            continue
        result[label] = {"tests": len(names), "exit": run["exit"] if run else None}
        if run is None or run["exit"] is None:
            result["status"] = UNAVAILABLE
            result["detail"] = (run or {}).get("detail") or "the test run at the base tree failed"
            return result
        if label == "must_fail" and run["exit"] == 0:
            problems.append("%d test(s) pass without the change: they do not reach it (%s)"
                            % (len(names), ", ".join(names[:3])))
        elif label == "must_pass" and run["exit"] != 0:
            problems.append("%d characterization test(s) fail against the code they describe (%s)"
                            % (len(names), ", ".join(names[:3])))
        else:
            notes.append("%s: %d test(s), exit %s at base" % (label, len(names), run["exit"]))
    if problems:
        return dict(result, status=RED, detail="; ".join(problems))
    return dict(result, status=GREEN,
                detail="%s; tree restored %s" % ("; ".join(notes), before[:9]))


def sensor_bite(root, state, policy, tests_result, tree):
    """Only ever run after the suite is green on this tree: the check asks
    whether the tests reach the change, and that question means nothing while
    they are failing for some other reason."""
    config = (policy.get("sensors") or {}).get("bite") or {}
    required_from = config.get("required_from", "T2")
    declared = state.get("risk_tier") or "T0"
    if tier_index(declared) < tier_index(required_from):
        return {"status": NOT_APPLICABLE,
                "detail": "not required below %s (sensors.bite.required_from)" % required_from}
    if (tests_result or {}).get("status") != GREEN:
        return {"status": UNAVAILABLE,
                "detail": "the suite is not green on this tree — nothing to ask yet"}
    return bite(root, state, policy, tree)


PLAN_HEADINGS = ["## Files that change", "## Order of work", "## Risks", "## Proof", "## Rollback"]


def sensor_plan_sections(root, state):
    ref = ((state.get("approved_plan") or {}).get("ref") or "").strip()
    if not ref or ref.startswith("inline"):
        return {"status": NOT_APPLICABLE, "detail": "inline plan"}
    path = ref if os.path.isabs(ref) else os.path.join(root, ref)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {"status": UNAVAILABLE, "detail": "cannot read %s" % ref}
    missing = [h for h in PLAN_HEADINGS if h not in text]
    if missing:
        return {"status": RED, "detail": "%s is missing: %s" % (ref, ", ".join(missing))}
    return {"status": GREEN, "detail": "%s carries every section" % ref}


# --------------------------------------------------------- the whole report

SENSOR_ORDER = ["tests", "lint", "typecheck", "diff", "rescore", "traceability",
                "duplicates", "plan_sections", "bite"]

LABEL = {GREEN: "green", RED: "RED", UNAVAILABLE: "UNAVAIL",
         NOT_APPLICABLE: "n/a", STALE: "STALE"}


def sensors_file(root, state):
    return os.path.join(root, ".ai", "reports", state.get("task_id") or "", "sensors.json")


def ledger_file(root, state):
    return os.path.join(root, ".ai", "reports", state.get("task_id") or "", "review-ledger.md")


def append_ledger(root, state, rows):
    """review-economy §2: a fact verified once is never verified again by a
    thinking model. The reviewer reads these rows before it plans its own work."""
    path = ledger_file(root, state)
    if not rows:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        new = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as fh:
            if new:
                fh.write("# Review ledger — %s\n\n"
                         "<!-- Append-only. Every review agent reads this before it plans its\n"
                         "     own work; a CONFIRMED row is out of budget for later passes. -->\n\n"
                         "| claim | verified by | outcome | pass |\n|---|---|---|---|\n"
                         % (state.get("task_id") or "?"))
            for row in rows:
                fh.write("%s\n" % row)
    except OSError:
        pass


def check(root, state, policy, skip_bite=False, only=None):
    """Every sensor, on the tree as it is now. The results a gate reads."""
    tree = snapshot_tree(root)
    declared = state.get("risk_tier") or "T0"
    task_id = state.get("task_id") or ""
    base = (state.get("diff") or {}).get("base_tree")
    measurement = measure(root, base, tree, policy, tier=declared, scope="task")
    scored = rescore(declared, measurement, policy)

    results = {}
    wanted = only or SENSOR_ORDER
    if "tests" in wanted:
        results["tests"] = sensor_tests(root, state, tree)
    if "lint" in wanted:
        results["lint"] = sensor_command(root, "lint", policy, task_id)
    if "typecheck" in wanted:
        results["typecheck"] = sensor_command(root, "typecheck", policy, task_id)
    if "diff" in wanted:
        results["diff"] = {
            "status": measurement["status"],
            "detail": measurement.get("detail") or
                      ("%d files / %d lines (%s task budget %s / %s)"
                       % (measurement["files"], measurement["lines"], declared,
                          (measurement["budget"] or {}).get("max_files"),
                          (measurement["budget"] or {}).get("max_lines"))),
            "files": measurement["files"], "lines": measurement["lines"],
            "unscoped": measurement["unscoped"]}
    if "rescore" in wanted:
        results["rescore"] = {
            "status": scored["status"],
            "detail": ("%s — scopes: %s" % (scored["tier"], ", ".join(measurement["scopes"]) or "none")
                       if scored["status"] != UNAVAILABLE else scored.get("detail", "")),
            "tier": scored["tier"], "reasons": scored["reasons"]}
    if "traceability" in wanted:
        results["traceability"] = sensor_traceability(root, state, measurement, policy)
    if "duplicates" in wanted:
        results["duplicates"] = sensor_duplicates(root, base, tree, policy)
    if "plan_sections" in wanted:
        results["plan_sections"] = sensor_plan_sections(root, state)
    if "bite" in wanted and not skip_bite:
        results["bite"] = sensor_bite(root, state, policy, results.get("tests", {}), tree)
    for result in results.values():
        result.setdefault("tree", tree)

    config = policy.get("sensors") or {}
    required = config.get("required_for_skip") or []
    ceiling = config.get("skip_review_at_or_below", "T2")
    blocking = []
    if not task_id:
        blocking.append("no task in flight: there is nothing to skip a review of")
    for name in required:
        status = (results.get(name) or {}).get("status", UNAVAILABLE)
        if status not in (GREEN, NOT_APPLICABLE):
            blocking.append("%s: %s" % (name, status))
    if tier_index(declared) > tier_index(ceiling):
        blocking.append("tier %s is above %s" % (declared, ceiling))
    if scored["status"] != UNAVAILABLE and tier_index(scored["tier"]) > tier_index(ceiling):
        blocking.append("the diff re-scores to %s" % scored["tier"])
    report = {"schema": 1, "task": task_id, "tree": tree, "declared_tier": declared,
              "rescored_tier": scored.get("tier"), "checked_at": now(),
              "sensors": results,
              "verdict": {"all_green": not blocking, "blocking": blocking,
                          "review": "skipped" if not blocking else "required"}}
    return report


def write_report(root, state, report, path=None):
    path = path or sensors_file(root, state)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
    except OSError:
        return None
    rows = []
    for name in SENSOR_ORDER:
        result = report["sensors"].get(name)
        if not result or result["status"] not in (GREEN, RED):
            continue
        rows.append("| %s on %s: %s | sensors.py %s | %s | sensor |"
                    % (name, (report["tree"] or "?")[:9],
                       one_line(result.get("detail", "")), name,
                       "CONFIRMED" if result["status"] == GREEN else "DEFECT, open"))
    append_ledger(root, state, rows)
    return path


def one_line(text):
    return re.sub(r"\s+", " ", (text or "")).strip()[:160]


def print_report(report, root):
    print("sensors @ %s (declared %s, rescored %s)"
          % ((report["tree"] or "?")[:9], report["declared_tier"], report["rescored_tier"]))
    for name in SENSOR_ORDER:
        result = report["sensors"].get(name)
        if not result:
            continue
        print("  %-13s %-8s %s" % (name, LABEL.get(result["status"], result["status"]),
                                   one_line(result.get("detail", ""))))
        if result.get("proposal"):
            print("  %-13s %-8s add to .ai/policies/testing.md: %s"
                  % ("", "", result["proposal"]))
    print("review: %s%s" % (report["verdict"]["review"],
                            "" if report["verdict"]["all_green"]
                            else " — " + "; ".join(report["verdict"]["blocking"][:4])))


# ---------------------------------------------------------------------- CLI

def print_diff(result, policy):
    if result["status"] == UNAVAILABLE:
        print("diff          UNAVAIL  %s" % (result["detail"] or "unavailable"))
        return UNKNOWNCODE
    budget = result["budget"]
    print("diff          %-8s %d files / %d lines (%s budget %s / %s)%s"
          % ("green" if result["status"] == GREEN else "RED",
             result["files"], result["lines"], result["tier"],
             budget.get("max_files"), budget.get("max_lines"),
             "" if not result["excluded_lines"] and not result["unbudgeted_lines"]
             else ", %d excluded, %d unbudgeted"
                  % (result["excluded_lines"], result["unbudgeted_lines"])))
    if result["scopes"]:
        print("              scopes: %s" % ", ".join(result["scopes"]))
    if result["deferred"]:
        print("              deferred to another step: %d file(s)" % len(result["deferred"]))
    for line in result["over"]:
        print("              over: %s" % line)
    for path in result["unscoped"][:10]:
        print("              unscoped: %s" % path)
    if len(result["unscoped"]) > 10:
        print("              unscoped: … and %d more" % (len(result["unscoped"]) - 10))
    return OK if result["status"] == GREEN else REDCODE


def resolve_trees(root, args):
    from_tree = args.from_tree
    if not from_tree:
        try:
            with open(os.path.join(root, ".ai", "state", "current.json"),
                      encoding="utf-8") as fh:
                from_tree = ((json.load(fh) or {}).get("diff") or {}).get("base_tree")
        except (OSError, ValueError):
            from_tree = None
    to_tree = None if args.now else args.to_tree
    if not to_tree:
        to_tree = snapshot_tree(root)
    return from_tree, to_tree


def cmd_snapshot(args, root):
    tree = snapshot_tree(root)
    if not tree:
        print("unavailable: not a git repository, or git could not write a tree")
        return UNKNOWNCODE
    print(tree)
    return OK


def cmd_diff(args, root):
    policy = load_policy(root)
    from_tree, to_tree = resolve_trees(root, args)
    allowed = [f.strip() for f in (args.allowed or "").split(",") if f.strip()]
    deferred = [f.strip() for f in (args.deferred or "").split(",") if f.strip()]
    result = measure(root, from_tree, to_tree, policy, tier=args.tier,
                     allowed=allowed or None, scope=args.scope,
                     deferred_to=deferred or None)
    if args.format == "json":
        result.pop("per_file", None)
        print(json.dumps(result, indent=2, sort_keys=True))
        return {GREEN: OK, RED: REDCODE}.get(result["status"], UNKNOWNCODE)
    return print_diff(result, policy)


def cmd_rescore(args, root):
    policy = load_policy(root)
    from_tree, to_tree = resolve_trees(root, args)
    measurement = measure(root, from_tree, to_tree, policy, tier=args.declared,
                          scope="task")
    result = rescore(args.declared, measurement, policy)
    if result["status"] == UNAVAILABLE:
        print("rescore       UNAVAIL  %s" % result.get("detail", "diff unavailable"))
        return UNKNOWNCODE
    if result["status"] == GREEN:
        print("rescore       green    %s — scopes: %s"
              % (result["tier"], ", ".join(measurement["scopes"]) or "none"))
        return OK
    print("rescore       RED      %s -> %s: %s"
          % (args.declared, result["tier"], "; ".join(result["reasons"][:3])))
    return REDCODE


def cmd_check(args, root):
    state = read_state(root)
    policy = load_policy(root)
    only = [x.strip() for x in (args.only or "").split(",") if x.strip()] or None
    report = check(root, state, policy, skip_bite=args.no_bite, only=only)
    write_report(root, state, report, args.json or None)
    print_report(report, root)
    statuses = [r["status"] for r in report["sensors"].values()]
    if RED in statuses:
        return REDCODE
    if UNAVAILABLE in statuses or STALE in statuses:
        return UNKNOWNCODE
    return OK


def cmd_report(args, root):
    state = read_state(root)
    path = args.json or sensors_file(root, state)
    try:
        with open(path, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, ValueError):
        print("no sensor report yet — run: sensors.py check")
        return UNKNOWNCODE
    tree = snapshot_tree(root)
    if tree and report.get("tree") and tree != report["tree"]:
        # Nothing is re-measured here: a result taken on another tree is not a
        # result about this one, and saying so is the whole job of this command.
        for result in report["sensors"].values():
            if result.get("status") in (GREEN, RED):
                result["status"] = STALE
                result["detail"] = "measured on %s, the worktree is at %s" % (
                    (report["tree"] or "?")[:9], tree[:9])
        report["verdict"] = {"all_green": False,
                             "blocking": ["the worktree moved since the check"],
                             "review": "required"}
    print_report(report, root)
    return OK if report["verdict"]["all_green"] else UNKNOWNCODE


def cmd_run(args, root):
    policy = load_policy(root)
    config = (policy.get("sensors") or {}).get("tests") or {}
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
    if args.at == "base":
        state_file = os.path.join(root, ".ai", "state", "current.json")
        base = None
        try:
            with open(state_file, encoding="utf-8") as fh:
                base = ((json.load(fh) or {}).get("diff") or {}).get("base_tree")
        except (OSError, ValueError):
            base = None
        result = run_at_base(root, command, args.base or base, log,
                             timeout=config.get("timeout_seconds", 1800),
                             log_max_bytes=config.get("log_max_bytes", 2097152),
                             scopes=policy["path_scopes"])
    else:
        result = run_command(root, command, log,
                             timeout=config.get("timeout_seconds", 1800),
                             log_max_bytes=config.get("log_max_bytes", 2097152))
    label = {GREEN: "green", RED: "RED", NOT_APPLICABLE: "n/a"}.get(result["status"], "UNAVAIL")
    print("%-13s %-8s exit %s in %ds%s"
          % (args.scope, label, result["exit"], result["duration_s"],
             " at the base tree" if args.at == "base" else ""))
    if result["detail"]:
        print("              %s" % result["detail"])
    if result["log"]:
        print("              log: %s" % os.path.relpath(result["log"], root))
    return {GREEN: OK, NOT_APPLICABLE: OK, RED: REDCODE}.get(result["status"], UNKNOWNCODE)


def cmd_bite(args, root):
    if not args.restore:
        state = read_state(root)
        policy = load_policy(root)
        result = bite(root, state, policy)
        print("bite          %-8s %s" % (LABEL.get(result["status"], result["status"]),
                                         one_line(result.get("detail", ""))))
        return {GREEN: OK, NOT_APPLICABLE: OK, RED: REDCODE}.get(result["status"], UNKNOWNCODE)
    lock = read_lock(root)
    if not lock:
        print("nothing to restore: no %s" % os.path.relpath(lock_path(root), root))
        return OK
    restore_from(root, lock["tree_after"], lock.get("paths") or [])
    current = snapshot_tree(root)
    if current == lock["tree_after"]:
        clear_lock(root)
        print("restored to %s" % current[:9])
        return OK
    print("could not restore to %s — the worktree is at %s; the lock is kept"
          % (lock["tree_after"][:9], (current or "?")[:9]))
    return REDCODE


def cmd_detect(args, root):
    found = detect(root)
    for kind in ("lint", "typecheck"):
        if found[kind]:
            marker, line = found[kind][0]
            print('%s: detected %s — add to .ai/policies/testing.md:' % (kind, marker))
            print("  %s" % line)
        else:
            print('%s: nothing detected — write "%s_command: none" in '
                  ".ai/policies/testing.md if the project has none" % (kind, kind))
    return OK


def build_parser():
    parser = argparse.ArgumentParser(prog="sensors.py", description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("snapshot"); p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("diff")
    p.add_argument("--from", dest="from_tree"); p.add_argument("--to", dest="to_tree")
    p.add_argument("--now", action="store_true")
    p.add_argument("--tier", default="T2"); p.add_argument("--allowed", default="")
    p.add_argument("--deferred", default="", help="other steps' files: planned elsewhere")
    p.add_argument("--scope", default="step", choices=["step", "task"])
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("rescore")
    p.add_argument("--from", dest="from_tree"); p.add_argument("--to", dest="to_tree")
    p.add_argument("--now", action="store_true")
    p.add_argument("--declared", default="T2")
    p.set_defaults(func=cmd_rescore)

    p = sub.add_parser("run")
    p.add_argument("--scope", required=True, choices=["step", "suite", "e2e", "single"])
    p.add_argument("--files", default=""); p.add_argument("--test", default="")
    p.add_argument("--at", default="now", choices=["now", "base"])
    p.add_argument("--base", default=""); p.add_argument("--log", default="")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("check")
    p.add_argument("--only", default=""); p.add_argument("--no-bite", action="store_true",
                                                         dest="no_bite")
    p.add_argument("--json", default=""); p.set_defaults(func=cmd_check)

    p = sub.add_parser("report"); p.add_argument("--json", default="")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("bite"); p.add_argument("--restore", action="store_true")
    p.set_defaults(func=cmd_bite)

    p = sub.add_parser("detect"); p.set_defaults(func=cmd_detect)
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
