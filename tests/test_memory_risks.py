#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Risk records (spec §D9, R12, R24's parser half, A12): known-risks.md parses
and renders byte for byte; `memory risk add|close` writes known-risks.md in
files mode — refusing when the task in flight does not name it (C4) — and
risk entries in packages mode, through the journal while a task is in flight.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_compact as mc  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position

KNOWN = os.path.join(mh.ROOT, ".ai", "project", "known-risks.md")
ADD = ["memory", "risk", "add", "--title", "Widget cache key ignores locale", "--where", "src/widget.py:1",
       "--label", "INFERENCE", "--what", "a stale key after a locale switch", "--likely", "rare, visible",
       "--fix", "key by locale"]


class TestParser(unittest.TestCase):
    def test_this_repository_renders_byte_for_byte(self):
        with open(KNOWN, encoding="utf-8") as fh:
            known = fh.read()
        self.assertEqual(mc.render_known_risks(*mc.parse_known_risks(known)), known)
        # since the migration (packages mode) this repository's risks live in the record
        text = mh.subprocess.run([sys.executable, "-I", mh.STATE, "--root", mh.ROOT, "memory", "risks", "--md"],
                                 capture_output=True, text=True, check=True, env=mh.clean_env()).stdout
        risks, leftovers = mc.parse_known_risks(text)
        self.assertGreater(len(risks), 10)
        self.assertEqual(mc.render_known_risks(risks, leftovers), text)
        for risk in risks:
            self.assertIn(risk["label"], mf.LABELS)
            self.assertIn(risk["status"], mf.RISK_STATUS)
            self.assertRegex(risk["rkey"], r"^R-[a-z0-9-]{1,40}-[0-9a-f]{4}$")
        self.assertFalse(any(r["title"] == "<short title>" for r in risks))     # the commented template

    def test_sections_fields_and_derived_label(self):
        text = ("# Known risks\n\n<!--\n## <short title>\n-->\n\n## A thing\n\n- **Found**: 2026-10-01, by "
                "T-2026-10-01-001\n- **Where**: `a.py:3`, `b.py`\n- **What could go wrong**: it breaks\n"
                "- **Status**: accepted — callers depend on it\n\n## Another\n\n- **Label**: KNOWN FACT\n"
                "- **Status**: closed in T-2\n")
        risks, leftovers = mc.parse_known_risks(text)
        self.assertEqual([r["title"] for r in risks], ["A thing", "Another"])
        self.assertEqual(risks[0]["where"], ["a.py:3", "b.py"])
        self.assertEqual((risks[0]["label"], risks[0]["label_derived"]), ("RISK", True))
        self.assertEqual((risks[1]["label"], risks[1]["label_derived"]), ("KNOWN FACT", False))
        self.assertEqual([r["status"] for r in risks], ["accepted", "fixed"])
        self.assertEqual(risks[0]["found_by"], "T-2026-10-01-001")
        self.assertEqual(mc.render_known_risks(risks, leftovers), text)


class TestFilesMode(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.write(".ai/project/known-risks.md", "# Known risks\n")
        self.p.commit("risks")

    def test_add_and_close_without_a_task(self):
        out = self.p.ok(*ADD).stdout
        rkey = out.split()[1]
        text = self.p.read(".ai/project/known-risks.md")
        self.assertIn("## Widget cache key ignores locale", text)
        self.assertIn("- **Label**: INFERENCE", text)
        self.assertIn("- **Where**: `src/widget.py:1`", text)
        self.assertIn("by no task", text)
        self.assertEqual(self.p.run(*ADD).returncode, 2)                      # one title, one risk
        listed = self.p.ok("memory", "risks").stdout
        self.assertIn(rkey, listed)
        self.p.ok("memory", "risk", "close", rkey, "--status", "fixed", "--why", "keyed by locale in T-x")
        self.assertIn("- **Status**: fixed — keyed by locale in T-x", self.p.read(".ai/project/known-risks.md"))
        self.assertNotIn(rkey, self.p.ok("memory", "risks").stdout)
        self.assertIn(rkey, self.p.ok("memory", "risks", "--status", "all").stdout)
        self.assertFalse(self.p.exists(".ai/memory"))

    def test_a_task_that_does_not_name_known_risks_is_refused(self):
        self.p.start("narrow", files="src/widget.py")
        done = self.p.run(*ADD)
        self.assertEqual(done.returncode, 6)
        self.assertIn("SCOPE_CHANGE_REQUIRED", done.stderr)
        self.assertIn('start --amend --files "+.ai/project/known-risks.md"', done.stderr)
        self.p.ok("start", "--amend", "--files", "+.ai/project/known-risks.md", "--why", "record a risk")
        self.p.ok(*ADD)
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("close")                                                    # fact (b) stays green


class TestPackagesMode(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.ok("memory", "enable", "--author", "dev", human=True)

    def test_in_flight_through_the_journal_then_closed_standalone(self):
        task = self.p.start("found a risk", files="src/widget.py")
        out = self.p.ok(*ADD).stdout
        rkey = out.split()[1]
        self.assertIn("recorded in %s's journal" % task, out)
        events = self.p.read(".ai/reports/%s/events.jsonl" % task)
        self.assertIn('"risk_recorded"', events)
        self.assertIn(rkey, self.p.ok("memory", "risks").stdout)               # live, before close
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("close")
        recall = self.p.ok("recall", "--files", "src/widget.py").stdout
        self.assertIn("[risk open INFERENCE] src/widget.py:1 — Widget cache key ignores locale", recall)
        self.p.ok("memory", "risk", "close", rkey, "--status", "accepted", "--why", "callers depend on it")
        listed = self.p.ok("memory", "risks", "--status", "all", "--json").stdout.splitlines()
        latest = [l for l in listed if rkey in l]
        self.assertEqual(len(latest), 1)
        self.assertIn('"status":"accepted"', latest[0])
        self.assertIn('"supersedes":"r1-', latest[0])
        self.assertNotIn("[risk open", self.p.ok("recall", "--files", "src/widget.py").stdout)
        self.assertIn("[risk accepted", self.p.ok("recall", "--files", "src/widget.py").stdout)
        md = self.p.ok("memory", "risks", "--status", "all", "--md").stdout
        self.assertIn("## Widget cache key ignores locale", md)
        self.assertIn("- **Status**: accepted — callers depend on it", md)

    def test_bad_label_and_status(self):
        bad = list(ADD)
        bad[bad.index("INFERENCE")] = "GUESS"
        self.assertEqual(self.p.run(*bad).returncode, 2)
        self.assertEqual(self.p.run("memory", "risk", "close", "R-x-0000", "--status", "open", "--why", "w")
                         .returncode, 2)


if __name__ == "__main__":
    unittest.main()
