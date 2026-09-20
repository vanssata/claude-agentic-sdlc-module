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
  sensors.py detect   [--root DIR]

Exit codes: 0 green or not applicable · 1 usage or internal error ·
            2 at least one red · 3 at least one unavailable or stale, none red.
"""

import argparse
import fnmatch
import json
import os
import re
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
    return {"diff_budget": merged_budget, "path_scopes": scopes,
            "sensors": data.get("sensors") if isinstance(data.get("sensors"), dict) else {},
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

def measure(root, from_tree, to_tree, policy, tier="T2", allowed=None, scope="step"):
    """Everything step-done needs, in one pass over the file list."""
    result = {"status": UNAVAILABLE, "from": from_tree, "to": to_tree,
              "scope": scope, "tier": tier, "files": 0, "added": 0, "deleted": 0,
              "lines": 0, "excluded_lines": 0, "unbudgeted_lines": 0,
              "unscoped": [], "binary": [], "scopes": [], "over": [],
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
        if allowed is not None and not scope_any(path, allowed):
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
    result = measure(root, from_tree, to_tree, policy, tier=args.tier,
                     allowed=allowed or None, scope=args.scope)
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
    p.add_argument("--scope", default="step", choices=["step", "task"])
    p.add_argument("--format", default="text", choices=["text", "json"])
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("rescore")
    p.add_argument("--from", dest="from_tree"); p.add_argument("--to", dest="to_tree")
    p.add_argument("--now", action="store_true")
    p.add_argument("--declared", default="T2")
    p.set_defaults(func=cmd_rescore)

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
