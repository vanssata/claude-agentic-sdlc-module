#!/usr/bin/env python3
"""R35: the plugin is RiskRails (display) and riskrails (machine name).

The old name is left only where a deny pattern or a refusal names it, or where
the text is a project file this plugin renders rather than ships. Every
allow-listed file must still hold the old name, so the list cannot go stale.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = ("hooks", "skills", "ai", "instructions", "agents", "scripts", "profiles",
         "settings.common.json", "codex")
OLD = re.compile(r"claude-agentic|claude_agentic|CLAUDE_AGENTIC")
SKIP_DIRS = {"__pycache__", "history"}   # history/ is every template version ever shipped

ALLOWED = {
    "hooks/ai-path-guard-defaults.json": "a deny: the old home stays protected while it is a symlink; removing it weakens a refusal",
    "skills/project-update/update.py": "OLD_MARKERS: the old marker pair --update refuses, a literal check (D4)",
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

    def test_the_allow_list_is_not_stale(self):
        stale = sorted(rel for rel in ALLOWED if not os.path.isfile(os.path.join(ROOT, rel)) or not holds_old(rel))
        self.assertEqual(stale, [], "an allow-listed file no longer needs the old name")


if __name__ == "__main__":
    unittest.main()
