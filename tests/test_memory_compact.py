#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
memory_compact (spec §D3, R3, R4, R5, A3): every journal line is accounted
for once; human wording is kept byte for byte from its source; evidence runs
keep a bounded, redacted excerpt; legacy shapes (backfilled, state-only,
multi-instance, questions, gates, reviews, v7) compact with full coverage.
"""
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_compact as mc  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position

LEGACY = os.path.join(mh.FIXTURES, "legacy-reports")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        for name in sorted(os.listdir(LEGACY)):
            shutil.copytree(os.path.join(LEGACY, name), self.p.path(".ai/reports/" + name))
        self.reader = mc.FsReader(self.p.root)

    def compact(self, task, sources="tracked"):
        return mc.compact_instances(self.reader, task, sources)


class TestCoverage(Fixture):
    def test_every_fixture_is_fully_accounted_for(self):
        for task in sorted(os.listdir(LEGACY)):
            found = self.compact(task)
            self.assertTrue(found, task)
            journal = self.reader.read(".ai/reports/%s/events.jsonl" % task)
            lines = len([l for l in (journal or b"").split(b"\n") if l.strip()])
            self.assertEqual(sum(c.coverage["lines"] for c in found), lines, task)
            for c in found:
                self.assertEqual(c.coverage["accounted"], c.coverage["lines"], (task, c.coverage))
                self.assertEqual(c.coverage["skipped"], 0)
                self.assertEqual(c.problems, [])
                for e in c.entries + [c.seal]:
                    self.assertEqual(mf.validate(e), [], (task, e["kind"]))
                    for field in mf.REQUIRED[e["kind"]]:
                        self.assertIn(field, e)
                self.assertEqual(c.seal["entries"], len(c.entries))
                self.assertEqual(c.seal["digest"], mf.seal_digest([e["rid"] for e in c.entries]))

    def test_export_import_export_is_byte_identical(self):
        for task in sorted(os.listdir(LEGACY)):
            entries = [e for c in self.compact(task) for e in c.entries + [c.seal]]
            header = mf.package_header("2026-Q4", "dev", "abcd", "2026-10-28T00:00:00Z")
            data = mf.render_package(header, entries)
            h, back, errors = mf.parse_package(data, "2026-Q4.dev.abcd.jsonl")
            self.assertEqual(errors, [])
            self.assertEqual(mf.render_package(h, [mf.strip_private(e) for e in back]), data, task)
            self.assertEqual(self.compact(task)[0].seal, self.compact(task)[0].seal)    # deterministic

    def test_multi_instance_journal_splits(self):
        found = self.compact("T-2026-10-15-001")
        self.assertEqual([c.seal["result"] for c in found], ["restarted", "closed"])
        self.assertEqual([c.seal["inst"] for c in found], [1, 2])

    def test_backfilled_and_state_only(self):
        backfilled = self.compact("T-2026-09-21-001")
        self.assertEqual(len(backfilled), 1)
        self.assertTrue(backfilled[0].seal["goal"])                 # from the committed state.json
        self.assertTrue(backfilled[0].seal["files"])                # the plan's allowed_files
        state_only = self.compact("T-2026-09-23-001")
        self.assertEqual(state_only[0].coverage["lines"], 0)
        self.assertTrue(all(e["actor"] == "migration" for e in state_only[0].entries))
        self.assertTrue(state_only[0].entries)

    def test_dropped_events_are_counted(self):
        seal = self.compact("T-2026-10-28-009")[0].seal
        journal = self.reader.read(".ai/reports/T-2026-10-28-009/events.jsonl").decode()
        self.assertEqual(seal["counts"]["dropped"]["handoff_written"], journal.count('"handoff_written"'))

    def test_unknown_event_and_torn_line_are_kept(self):
        path = self.p.path(".ai/reports/T-2026-10-26-002/events.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-10-26T10:00:00.000Z", "task": "T-2026-10-26-002", "event": "brand_new",
                                 "actor": "agent", "runtime": "codex", "stage": "build", "detail": "x",
                                 "data": {"k": 1}}) + "\n")
            fh.write('{"ts": "2026-10-26T10:00:01Z", "event": "no\n')
        c = self.compact("T-2026-10-26-002")[-1]
        unknown = [e for e in c.entries if e.get("note_kind") == "unknown-event"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["raw"]["event"], "brand_new")
        self.assertEqual(unknown[0]["runtime"], "codex")
        self.assertEqual(c.coverage["skipped"], 1)
        self.assertEqual(c.seal["counts"]["skipped"], 1)
        self.assertTrue(any("torn" in p for p in c.problems))


class TestVerbatim(Fixture):
    def test_questions_and_gates_equal_task_md(self):
        md = mc.parse_task_md(self.p.read(".ai/reports/T-2026-10-28-009/task.md"))
        c = self.compact("T-2026-10-28-009")[0]
        q = [e for e in c.entries if e["kind"] == "question"][0]
        self.assertEqual(q["question"], md["questions"]["Q1"]["question"])
        self.assertEqual(q["options"], md["questions"]["Q1"]["options"])
        self.assertEqual(q["answer"]["choice"], "A")
        self.assertIn("task.md#Q1", q["src"])
        g = [e for e in c.entries if e["kind"] == "approval"][0]
        self.assertEqual((g["gate_id"], g["decision"], g["by"], g["via"]), ("G1", "approved", "Ivan Kakurov",
                                                                          "terminal"))
        review = [e for e in c.entries if e["kind"] == "review"][0]
        self.assertEqual(sorted(f["label"] for f in review["findings"]),
                         sorted(["H1", "M1", "M2", "L1", "L2", "L3", "L4", "I1", "I2", "I3", "I4"]))
        self.assertEqual(review["closed"], [{"labels": ["H1"], "by_run": 11}])

    def test_a_6kb_answer_survives_the_journal_cap(self):
        p = mh.Project("big", tmp=self.p.tmp)
        answer = "Ж" * 1000 + " " + "word " * 800
        task, _ = p.rich_task("a long answer", answer_text=answer.strip())
        events = [json.loads(l) for l in p.read(".ai/reports/%s/events.jsonl" % task).splitlines()]
        answered = [e for e in events if e["event"] == "question_answered"][0]
        self.assertEqual(answered["data"], {"truncated": True})           # the 4 KB journal cap bit
        found = mc.compact_instances(mc.FsReader(p.root), task, "close")
        q = [e for e in found[-1].entries if e["kind"] == "question"][0]
        self.assertEqual(q["answer"]["text"], answer.strip())
        self.assertEqual(q["answer"]["choice"], "X")
        approval = [e for e in found[-1].entries if e["kind"] == "approval"][0]
        self.assertEqual(approval["note"], "looks right")
        note = [e for e in found[-1].entries if e["kind"] == "note"][0]
        self.assertEqual((note["text"], note["why"]), ("keep the old key", "callers depend on it"))
        scope = [e for e in found[-1].entries if e["kind"] == "scope"][0]
        self.assertEqual(scope["why"], "the answer needs a doc line")
        # Review M1: the cut answer line belongs to Q1 (its detail names it), with its own actor.
        self.assertEqual([e["qid"] for e in found[-1].entries if e["kind"] == "question"], ["Q1"])
        self.assertEqual(q["answer"]["actor"], answered["actor"])
        self.assertIn("events.jsonl:%d" % (events.index(answered) + 1), q["src"])

    def test_cut_lines_are_recovered_never_invented(self):
        """Review M1: a 5 000-character amend why and reject why, and a note with
        only a detail, keep their text and their attribution."""
        p = mh.Project("cut", tmp=self.p.tmp)
        task = p.start("cut lines", "--mode", "full", "--by", "tester")
        why = "w" * 5000
        p.ok("start", "--amend", "--files", "+docs/cut.md", "--why", why)
        p.ok("event", "note", "--detail", "only a detail, no data")
        p.ok("event", "note", "--data", json.dumps({"kind": "decision", "text": "T" * 5000}))
        p.ok("verify", "--scope", "all")
        p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=mh.CLEAN)
        p.ok("close")
        reason = "r" * 5000
        p.ok("reject", "--by", "vanssa", "--why", reason, human=True)
        p.ok("close", "--abandon")
        events = [json.loads(l) for l in p.read(".ai/reports/%s/events.jsonl" % task).splitlines()]
        self.assertEqual(sum(1 for e in events if e.get("data") == {"truncated": True}), 3)
        c = mc.compact_instances(mc.FsReader(p.root), task, "close")[-1]
        self.assertEqual(c.coverage["accounted"], c.coverage["lines"])
        scope = [e for e in c.entries if e["kind"] == "scope"][0]
        # an agent's why: recovered from the archived state, then capped at 2 000 and listed (§D3)
        self.assertEqual((scope["added"], scope["why"], scope["truncated"]), (["docs/cut.md"], why[:2000], ["why"]))
        approvals = [e for e in c.entries if e["kind"] == "approval"]
        self.assertEqual([(a["gate_id"], a["decision"]) for a in approvals], [("G1", "rejected")])
        self.assertEqual((approvals[0]["why"], approvals[0]["actor"]), (reason, "human"))
        notes = [e for e in c.entries if e["kind"] == "note"]
        self.assertEqual(notes[0]["text"], "only a detail, no data")
        # a cut note with no detail: nothing is invented, the lost fields are named (re-review M1)
        self.assertEqual((notes[1]["text"], notes[1]["note_kind"]), (None, None))
        self.assertEqual(notes[1]["unrecorded"], ["note_kind", "text", "why"])
        lost = mc.compact_instances(mc.FsReader(p.root), task, "tracked")[-1]
        scope = [e for e in lost.entries if e["kind"] == "scope"][0]
        self.assertEqual((scope["added"], scope["why"]), (["docs/cut.md"], why[:2000]))   # task.md's amended line

    def test_agent_text_is_capped_and_listed(self):
        p = mh.Project("cap", tmp=self.p.tmp)
        task = p.start("capped")
        p.ok("event", "note", "--data", json.dumps({"kind": "decision", "text": "x" * 2500, "why": "y"}))
        p.ok("close", "--abandon")
        c = mc.compact_instances(mc.FsReader(p.root), task, "close")[-1]
        note = [e for e in c.entries if e["kind"] == "note"][0]
        self.assertEqual(len(note["text"]), 2000)
        self.assertEqual(note["truncated"], ["text"])


class TestExcerpt(unittest.TestCase):
    def test_bounded_failures_first_redacted(self):
        log = "\n".join(["\x1b[31mline %d\x1b[0m" % i for i in range(40)] +
                        ["FAIL: test_a (t.A)", "ERROR: test_b (t.B)", "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWX12"] +
                        ["tail %d" % i for i in range(20)])
        text = mc.excerpt(log, True, 1024)
        lines = text.split("\n")
        self.assertEqual(lines[:2], ["FAIL: test_a (t.A)", "ERROR: test_b (t.B)"])
        self.assertEqual(lines[-1], "tail 19")
        self.assertNotIn("\x1b", text)
        self.assertNotIn("ghp_", text)
        self.assertLessEqual(len(mc.excerpt(log * 50, False, 300).encode()), 300)
        self.assertIsNone(mc.excerpt(log, True, 0))

    def test_close_keeps_the_evidence_runs(self):
        p = mh.Project()
        self.addCleanup(p.close)
        task = p.start("evidence")
        p.flag("stepred")
        p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py", "--expect", "fail")
        p.flag("stepred", False)
        p.write("src/widget.py", "x = 9\n")
        p.ok("verify", "--scope", "all")
        p.ok("close")
        c = mc.compact_instances(mc.FsReader(p.root), task, "close")[-1]
        runs = [e for e in c.entries if e["kind"] == "verify"]
        self.assertEqual([(r["scope"], r["expected_fail"]) for r in runs],
                         [("step", True), ("suite", False)])              # light mode runs no e2e
        self.assertTrue(all(r["log"].startswith("log:.ai/state/logs/") for r in runs))
        self.assertTrue(all(r["command"] for r in runs))
        self.assertEqual(len(c.seal["verify_runs"]), 2)


if __name__ == "__main__":
    unittest.main()
