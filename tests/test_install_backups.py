#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R19: a backup never overwrites another. The stamp of a run is backups/<date> when that is free in
the home, else backups/<date>T<HHMMSS>, else the same with -2, -3; each home has its own. The
installer's clock is RISKRAILS_NOW, so no case reads the wall clock and none waits for a second.
"""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import ScratchCase, env_with, install, read, write  # noqa: E402  pylint: disable=wrong-import-position

CLOCK = "2026-03-04T05:06:07"


def run(home, clock, *args):
    """One install into home at the given time; the exit code must be 0."""
    env = env_with(HOME=home, RISKRAILS_NOW=clock)
    code, out = install("--yes", "--home", home, *args, env=env)
    assert code == 0, out
    return out


def tree(path):
    """{relative path: sha256} of every file under path."""
    found = {}
    for top, _dirs, names in os.walk(path):
        for name in names:
            full = os.path.join(top, name)
            with open(full, "rb") as fh:
                found[os.path.relpath(full, path)] = hashlib.sha256(fh.read()).hexdigest()
    return found


class BackupStamp(ScratchCase):

    def home(self, name):
        home = self.path(name)
        write(os.path.join(home, "CLAUDE.md"), "my notes\n")
        return home

    def backups(self, home):
        return sorted(os.listdir(os.path.join(home, "backups")))

    def test_01_the_first_run_of_a_day_keeps_backups_date(self):
        home = self.home("first")
        out = run(home, CLOCK, "--target", "claude", "--plan", "pro")
        self.assertEqual(self.backups(home), ["2026-03-04"])
        self.assertIn("backup: CLAUDE.md -> backups/2026-03-04/CLAUDE.md", out)
        self.assertEqual(read(os.path.join(home, "backups", "2026-03-04", "CLAUDE.md")), "my notes\n")

    def test_02_later_runs_get_the_time_then_a_counter_and_no_run_writes_into_another(self):
        home = self.home("later")
        run(home, CLOCK, "--target", "claude", "--plan", "pro")
        expected = ["2026-03-04"]
        for stamp in ("2026-03-04T050607", "2026-03-04T050607-2", "2026-03-04T050607-3"):
            before = {name: tree(os.path.join(home, "backups", name)) for name in expected}
            out = run(home, CLOCK, "--target", "claude", "--plan", "pro")
            expected.append(stamp)
            self.assertEqual(self.backups(home), sorted(expected))
            self.assertIn("backup: CLAUDE.md -> backups/%s/CLAUDE.md" % stamp, out)
            self.assertEqual({name: tree(os.path.join(home, "backups", name)) for name in before}, before,
                             "an earlier backup directory was written into by the run at %s" % stamp)

    def test_03_a_new_day_starts_again_at_backups_date(self):
        home = self.home("newday")
        run(home, CLOCK, "--target", "claude", "--plan", "pro")
        run(home, "2026-03-05T09:00:00", "--target", "claude", "--plan", "pro")
        self.assertEqual(self.backups(home), ["2026-03-04", "2026-03-05"])

    def test_04_each_home_has_its_own_stamp(self):
        claude, codex = self.home("both-claude"), self.path("both-codex")
        write(os.path.join(codex, "AGENTS.md"), "codex notes\n")
        run(claude, CLOCK, "--target", "claude", "--plan", "pro")
        env = env_with(HOME=claude, RISKRAILS_NOW=CLOCK)
        code, out = install("--yes", "--target", "both", "--plan", "pro", "--codex-plan", "pro",
                            "--home", claude, "--codex-home", codex, env=env)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.backups(claude), ["2026-03-04", "2026-03-04T050607"])
        self.assertEqual(self.backups(codex), ["2026-03-04"])
        self.assertIn("backup: AGENTS.md -> backups/2026-03-04/AGENTS.md", out)


if __name__ == "__main__":
    unittest.main()
