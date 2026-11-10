#!/usr/bin/env python3
"""R2, R21, R23: the one-version fallbacks and the migration ladder are gone.

`test_removed_paths_absent` names what regenerate-not-migrate deleted. `test_no_legacy_tokens`
scans the plugin for the names those fallbacks read (the old env prefix, the old home, the
old state file, the old commands) and fails on a hit that has no row in ALLOWED. Every row
carries its reason and the tokens it excuses; `test_the_allow_list_is_not_stale` fails when
a row excuses a token its files no longer hold, so the list can only shrink.

Command tokens are anchored (`(?<![\\w./-])/ai-task`) so that `skills/ai-task/...` is not a
hit, and the migration token is `project-update/migrations`, not a bare `migrations/` (a
user project's own db/migrations stays in the fixtures).
"""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REMOVED = (
    "skills/project-update/adopt.py",
    "skills/project-update/adopt-map.json",
    "skills/project-update/migrations",
    "tests/test_project_adopt.py",
    "tests/fixtures/adopt",
    "skills/ai-status",
    "skills/sdlc-intent",
    "skills/sdlc-plan",
    "skills/sdlc-spec",
    "skills/ai-task/SKILL.md",
    "skills/project-update/SKILL.md",
    "skills/ai-init/SKILL.md",
    "skills/project-init/SKILL.md",
    "skills/usage-report/SKILL.md",
    "skills/ai-audit/SKILL.md",
    "tests/test_migration_0006.py",
    "tests/test_migration_0010.py",
    "tests/test_migration_0011.py",
)
REMOVED_GLOBS = (
    "tests/fixtures/project-update/migrations-*",
    "tests/fixtures/project-update/schema-v*",
    "tests/fixtures/project-update/risk-tiers",
    "tests/fixtures/project-update/shared-old",
)

COMMANDS = ("ai-task", "ai-init", "project-update", "project-init", "ai-status", "ai-audit",
            "sdlc-intent", "sdlc-spec", "sdlc-plan", "usage-report")
# name -> pattern. The last five are OQ9's (D8 F); they are scanned over hooks/ and bin/ only (TOKEN_SCOPE).
TOKENS = {
    "CLAUDE_AGENTIC_": r"CLAUDE_AGENTIC_",
    "claude-agentic": r"claude-agentic",
    "claude_agentic": r"claude_agentic",
    "current.json": r"current\.json",
    "LEGACY_STATE": r"LEGACY_STATE",
    "LEGACY_REVIEW": r"LEGACY_REVIEW",
    "OLD_START": r"OLD_START",
    "--adopt": r"--adopt",
    "adopt.py": r"adopt\.py",
    "adopt-map": r"adopt-map",
    "project-update/migrations": r"project-update/migrations",
    "one version": r"one version",
    "fable-gate": r"fable-gate",
    "codex-model-gate": r"codex-model-gate",
    "dependency_instruction_patterns": r"dependency_instruction_patterns",
    "claude-routing": r"claude-routing",
    "Model allocation": r"Model allocation",
    # T-2026-11-03-2046's L3, M3 and L7: text that describes what 4.0 removed; scanned over the docs only (DOC_SCOPE).
    "gate variables": r"CLAUDE_FABLE_GATE|CODEX_MODEL_GATE",
    "[sdlc] rows": r"\[sdlc\]",
    "conflict rows": r"A `conflict` line|merge conflicts",
    "policy rows": r"Lines marked `policy`",
    "refused before 3.1.0": r"before\s+3\.1\.0\s+is\s+refused|older\s+than\s+3\.1\.0",
    "adopt.json": r"adopt\.json",
    "usage-report/SKILL.md": r"usage-report/SKILL\.md",
}
DOC_SCOPE = ("docs/", "skills/rr-setup/", "README.md")
TOKEN_SCOPE = {name: ("hooks/", "bin/") for name in
               ("fable-gate", "codex-model-gate", "dependency_instruction_patterns", "claude-routing", "Model allocation")}
TOKEN_SCOPE.update((name, DOC_SCOPE) for name in
                   ("gate variables", "[sdlc] rows", "conflict rows", "policy rows", "refused before 3.1.0",
                    "adopt.json", "usage-report/SKILL.md"))
TOKENS.update(("/" + c, r"(?<![\w./-])/" + c + r"\b") for c in COMMANDS)
PATTERNS = {name: re.compile(pattern) for name, pattern in TOKENS.items()}

SCAN = ("skills", "hooks", "bin", "scripts", "ai", "agents", "instructions", "codex", "profiles", "tests",
        "README.md", "docs")
SKIP_DIRS = {"__pycache__", "history", "node_modules", "sdlc", ".git"}
SKIP_FILES = ("tests/test_no_fallbacks.py", "CHANGELOG.md")
SKIP_PREFIXES = ("docs/redesign-analysis-", "docs/time-analysis-")



class Group(tuple):
    """A set of tokens a row excuses as a whole: the row is stale only when none is held."""


ALL = Group(TOKENS)
ALIASES = Group("/" + c for c in COMMANDS)

# Why a row stays: every row is a KEEP, with its reason.
DENY = "KEEP a deny pattern: writing current.json (or the old home) stays refused; only the READ fallback went"
PINS_DENY = "KEEP pins the deny patterns for current.json / the old home (the guards still refuse a write)"
INERT = "KEEP pins that a legacy current.json is no longer read (the state file is state.json)"
FROZEN = "KEEP a frozen copy of the thing the port was made from (the differential test's other side)"
OLD_TREE = "KEEP a frozen old-release tree: the input of the regenerate tests, or recorded history"
D4 = "KEEP update's own refusal of an old shape (D4, R12): a literal check, nothing is read or converted"
GITIGNORE = "KEEP the .gitignore header projects already carry; a new header would be appended beside it"
R8 = "KEEP byte-identical by R8: the --confirm-delete guard fixtures"

PRE_WP5 = ("KEEP finding 7: the installer rewrites a pre-WP5 settings.json (statusline wrapper, hook entries) and retires "
           "the shim; removing it leaves a hook that points at a retired file")

ALLOWED = (
    # (path or directory/, tokens it may hold, reason)
    ("bin/riskrails.js", ("fable-gate", "codex-model-gate"), PRE_WP5),
    ("bin/riskrails.js", ("claude-routing",), "KEEP the routing template's file name (claude-routing.md) and the warning "
     "about a predecessor block left outside the managed block; nothing is migrated"),
    ("bin/riskrails.js", ("Model allocation",), "KEEP the warning that a hand-written routing section outside the managed block is superseded"),
    ("hooks/ai-path-guard-defaults.json", ("claude-agentic", "current.json"), DENY),
    ("tests/fixtures/path-guard/", ("current.json",), PINS_DENY),
    ("tests/fixtures/path-guard/", ("--adopt",), R8),
    ("tests/fixtures/codex-hooks/", ("--adopt",), R8),
    ("tests/fixtures/guard-characterization/", ("current.json", "/project-update"),
     "KEEP the guard golden: the deny message names /project-update and the state file"),
    ("tests/test_ai_path_guard.py", ("claude-agentic", "current.json", "--adopt"), PINS_DENY),
    ("tests/test_guard_characterization.py", ("current.json",), PINS_DENY + "; the frozen shell reads it"),
    ("tests/test_guard_differential.py", ("current.json",), PINS_DENY),
    ("tests/test_ai_scope_guard.py", ("current.json",), INERT),
    ("skills/project-update/update.py", ("claude-agentic", "current.json"), D4),
    ("tests/test_regenerate.py", ("claude-agentic", "current.json"), D4),
    ("tests/test_project_update.py", ("current.json", "--adopt"), D4 + "; the removed flags exit 2"),
    ("tests/test_rename.py", ("claude-agentic", "claude_agentic"), "KEEP the rename test names the old spelling"),
    ("tests/test_scaffold_idempotency.py", ("claude-agentic", "/project-update"), GITIGNORE),
    ("skills/ai-init/templates/gitignore.snippet", ("claude-agentic",), GITIGNORE),
    ("skills/project-init/templates/gitignore.snippet", ("claude-agentic",), GITIGNORE),
    ("tests/fixtures/guard-port/", ALL, FROZEN),
    ("tests/fixtures/scaffold-port/", ALL, FROZEN),
    ("tests/fixtures/regenerate/", ALL, OLD_TREE),
    ("tests/fixtures/memory/", ALL, OLD_TREE + " (journals and reports as they were written)"),
    ("hooks/guard/paths.py", ("/project-update",), "KEEP deny message text pinned by the guard golden"),
    ("README.md", ("claude-agentic",), "KEEP the repository's URL (claude-agentic-sdlc-module) in the version badge"),
    ("docs/ai-sdlc-adoption-plan.md", ("claude-agentic", "one version"), "KEEP a dated audit output, not a doc of the current behaviour"),
    ("tests/test_ai_status_root.py", ("/ai-init",), "KEEP asserts that the no-root message no longer names /ai-init"),
    ("skills/ai-init/templates/.ai/policies/coding.md", ("/ai-init",), "KEEP byte-identical to 3.1.0: test_regenerate pins that this file needs no regenerate "
     "row, and a one-word comment fix would add one; changes with the next edit of the file"),
    ("tests/test_ai_task_state.py", ("current.json", "claude-agentic"), INERT + "; and the old-home profile"),
    ("tests/test_install_dry_run.py", ("claude-agentic",), "KEEP pins that a plan under claude-agentic/ is not read"),
    ("tests/test_dialog_contract.py", ("claude-agentic",), "KEEP pins that a profile under the old home is no tool"),
    ("tests/test_scaffold_differential.py", ("CLAUDE_AGENTIC_",), FROZEN + ": the shell reads the old env name"),
)


def scanned():
    for top in SCAN:
        path = os.path.join(ROOT, top)
        if os.path.isfile(path):
            yield top
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                yield os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")


def hits():
    """{file: {token, ...}} for every scanned text file that holds a legacy token."""
    found = {}
    for rel in scanned():
        if rel in SKIP_FILES or rel.startswith(SKIP_PREFIXES):
            continue
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        tokens = {name for name, pattern in PATTERNS.items()
                  if rel.startswith(TOKEN_SCOPE.get(name, ("",))) and pattern.search(text)}
        if tokens:
            found[rel] = tokens
    return found


def covers(path, rel):
    return rel.startswith(path) if path.endswith("/") else rel == path


class TestNoFallbacks(unittest.TestCase):
    def test_removed_paths_absent(self):
        present = [p for p in REMOVED if os.path.lexists(os.path.join(ROOT, p))]
        present += [os.path.relpath(p, ROOT) for g in REMOVED_GLOBS for p in glob.glob(os.path.join(ROOT, g))]
        self.assertEqual(present, [], "R2: deleted by regenerate-not-migrate")

    def test_no_legacy_tokens(self):
        loose = []
        for rel, tokens in sorted(hits().items()):
            allowed = set()
            for path, excused, _ in ALLOWED:
                if covers(path, rel):
                    allowed.update(excused)
            if tokens - allowed:
                loose.append("%s: %s" % (rel, ", ".join(sorted(tokens - allowed))))
        self.assertEqual(loose, [], "a legacy token outside the allow-list")

    def test_every_row_has_a_reason(self):
        self.assertEqual([r[0] for r in ALLOWED if not r[2].strip()], [])

    def test_the_allow_list_is_not_stale(self):
        found = hits()
        stale = []
        for path, excused, _ in ALLOWED:
            held = [token for token in excused
                    if any(token in tokens for rel, tokens in found.items() if covers(path, rel))]
            if isinstance(excused, Group):
                if not held:
                    stale.append("%s: none of the group" % path)
            else:
                stale.extend("%s: %s" % (path, token) for token in excused if token not in held)
        self.assertEqual(stale, [], "an allow-list row excuses a token its files no longer hold")

    def test_the_anchored_command_tokens(self):
        pattern = PATTERNS["/ai-task"]
        self.assertIsNone(pattern.search("skills/ai-task/state.py"))
        self.assertIsNone(pattern.search("./ai-task"))
        self.assertIsNotNone(pattern.search("run /ai-task fix it"))
        self.assertIsNotNone(pattern.search("(/ai-task)"))
        self.assertIsNone(PATTERNS["project-update/migrations"].search("db/migrations/x.sql"))


if __name__ == "__main__":
    unittest.main()
