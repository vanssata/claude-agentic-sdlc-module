"""The schema-7 surface end to end: the light path is three state.py calls under
either runtime (R5, R19), the guarded path writes the handoff at its boundaries
only (R21) and asks nothing after the weight (R24), and a closed task leaves
the journal and task.md under reports/ (R8).

Skipped unless AI_E2E=1, so `unittest discover` in run-all.sh leaves it to
tests/test-end-to-end.sh, which runs it once, at the end.
"""
import os
import unittest

from test_ai_task_state import ZERO, Project


@unittest.skipUnless(os.environ.get("AI_E2E"), "end to end: AI_E2E=1 (tests/test-end-to-end.sh)")
class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.calls = 0

    def tearDown(self):
        self.p.close()

    def call(self, *args, **kwargs):
        self.calls += 1
        return self.p.ok(*args, **kwargs)

    def reports(self, task):
        return sorted(os.listdir(os.path.join(self.p.root, ".ai", "reports", task)))

    def test_light_path_is_three_calls_under_each_runtime(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                self.calls = 0
                out = self.call("start", "--goal", "copy fix (%s)" % runtime, "--workflow", "bugfix",
                                "--files", "src/widget.py", "--tests", "tests/test_widget.py", *ZERO,
                                runtime=runtime).stdout
                task = out.strip().split("\n")[-2].split()[0]
                self.p.write("src/widget.py", "x = '%s'\n" % runtime)
                self.call("verify", "--scope", "all", runtime=runtime)
                self.call("close", runtime=runtime)
                self.assertEqual(self.calls, 3)
                self.assertFalse(self.p.in_flight())
                events = self.p.events(task)
                self.assertEqual({e["runtime"] for e in events}, {runtime})
                self.assertEqual(events[-1]["event"], "task_closed")
                self.assertEqual(self.reports(task), ["events.jsonl", "task.md"])
                stops = [e for e in events if e["event"] in ("question_asked", "gate_requested")]
                self.assertEqual(stops, [], "a light task stops for no one")

    def test_guarded_path(self):
        self.call("start", "--goal", "two-step change", "--workflow", "feature", "--files", "src/widget.py",
                  "--tests", "tests/test_widget.py", "--steps", "s1:src/widget.py;s2:src/b.py", *ZERO,
                  "--mode", "guarded", "--by", "lead")
        task = self.p.state()["task_id"]
        self.p.write("src/widget.py", "x = 2\n")
        self.call("step-done", "s1")
        self.p.write("src/b.py", "y = 1\n")
        self.call("verify", "--scope", "all")
        self.call("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-",
                  stdin="FINDINGS\nnone\nVERDICT pass\n")
        self.call("close")
        events = self.p.events(task)
        names = [e["event"] for e in events]
        self.assertLessEqual(names.count("handoff_written"), 5)
        self.assertEqual(names[names.index("weight_set"):].count("question_asked"), 0)
        self.assertEqual([e["data"]["reason"] for e in events if e["event"] == "handoff_written"],
                         ["start", "verify", "review"])
        self.assertEqual(self.reports(task), ["events.jsonl", "task.md"])
        self.assertTrue(os.path.isfile(os.path.join(self.p.root, ".ai", "state", "logs", task, "state.json")))


if __name__ == "__main__":
    unittest.main()
