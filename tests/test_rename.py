#!/usr/bin/env python3
"""R35: the plugin is RiskRails (display) and riskrails (machine name).

The old name is left only where a reader still accepts it for one version, or
where the text is a project file this plugin renders rather than ships. Every
allow-listed file must still hold the old name, so the list cannot go stale.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = ("hooks", "skills", "ai", "instructions", "agents", "scripts", "profiles",
         "settings.common.json", "codex")
OLD = re.compile(r"claude-agentic|claude_agentic|CLAUDE_AGENTIC")
SKIP_DIRS = {"__pycache__", "history"}   # history/ is every template version ever shipped

ALLOWED = {
    # compat readers, one version
    "hooks/ai-path-guard-defaults.json": "the old home stays protected while it is a symlink",
    "scripts/ai-path": "CLAUDE_AGENTIC_SHARED read when RISKRAILS_SHARED is unset",
    "scripts/resolve-profile.py": "the claude_agentic profile key read when riskrails is absent",
    "skills/project-update/migrations/0008_renames.py": "the migration that renames the old markers",
    "skills/project-update/migrations/__init__.py": "CLAUDE_AGENTIC_MIGRATIONS read when the new one is unset",
    "skills/project-update/render_instructions.py": "legacy block and rule markers read and rewritten",
    "skills/project-update/update.py": "legacy markers, old env names and the old shared tree",
    "skills/project-update/adopt.py": "CLAUDE_AGENTIC_TEST read when RISKRAILS_TEST is unset",
    "skills/rr-setup/scaffold_ai.py": "a legacy block is the managed block; old env name",
    "skills/ai-task/state.py": "profile.json under the old home, for a skills tree not reinstalled",
    "hooks/runtime-gate.py": "profile.json under the old home, for a skills tree not reinstalled",
    "skills/usage-report/usage-report.py": "profile.json under the old home, for a skills tree not reinstalled",
    # rendered into this repository by /rr-setup --update from .ai/rules/, not shipped
    "hooks/CLAUDE.md": "rendered rule block", "hooks/AGENTS.md": "rendered rule block",
    "skills/CLAUDE.md": "rendered rule block", "skills/AGENTS.md": "rendered rule block",
    # a project's .gitignore matches these lines verbatim; a new header would be appended beside the old
    "skills/ai-init/templates/gitignore.snippet": "the .gitignore header projects already carry",
    "skills/project-init/templates/gitignore.snippet": "the .gitignore header projects already carry",
}


def files():
    for top in SCOPE:
        path = os.path.join(ROOT, top)
        if os.path.isfile(path):
            yield top
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                yield os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")


def holds_old(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return OLD.search(fh.read().decode("utf-8", "replace")) is not None


class TestRename(unittest.TestCase):
    def test_no_old_name_outside_the_allow_list(self):
        found = sorted(rel for rel in files() if rel not in ALLOWED and holds_old(rel))
        self.assertEqual(found, [], "claude-agentic outside the compat readers")

    def test_env_names_new_first_then_old(self):
        tmp = tempfile.mkdtemp()
        try:
            for name in ("new", "old"):
                os.makedirs(os.path.join(tmp, name, "policies"))
                open(os.path.join(tmp, name, "policies", "git.md"), "w").close()
            os.makedirs(os.path.join(tmp, "p", ".ai"))
            base = {k: v for k, v in os.environ.items() if k not in ("RISKRAILS_SHARED", "CLAUDE_AGENTIC_SHARED")}
            for label, env, want in (
                    ("the new name is read", {"RISKRAILS_SHARED": tmp + "/new"}, "new"),
                    ("the old name is read when the new one is unset", {"CLAUDE_AGENTIC_SHARED": tmp + "/old"}, "old"),
                    ("the new name wins over the old",
                     {"RISKRAILS_SHARED": tmp + "/new", "CLAUDE_AGENTIC_SHARED": tmp + "/old"}, "new")):
                with self.subTest(label):
                    out = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "ai-path"),
                                          "--root", tmp + "/p", "policies/git.md"], env=dict(base, **env),
                                         capture_output=True, text=True, check=False)
                    self.assertEqual(out.stdout.strip(), os.path.join(tmp, want, "policies", "git.md"), out.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_allow_list_is_not_stale(self):
        stale = sorted(rel for rel in ALLOWED if not os.path.isfile(os.path.join(ROOT, rel)) or not holds_old(rel))
        self.assertEqual(stale, [], "an allow-listed file no longer needs the old name")


if __name__ == "__main__":
    unittest.main()
