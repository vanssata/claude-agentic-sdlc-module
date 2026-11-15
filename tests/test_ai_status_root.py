#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
/rr-status resolves the project the same way the guards do, and stays short.

skills/rr-status/status.py prints `root:` first. It exists so a reader can see
WHICH .ai/ governs the directory they are in — a .ai/ in an ancestor, or in
$HOME, silently arms the path and scope guards for every repository below it,
and that is not visible from anywhere else. The line is only worth anything
while it agrees with find_ai_root, so this suite compares it, case by case,
with both implementations: hooks/lib/ai-hook-common.sh, and
hooks/guard/common.py, which the guards run since redesign 3.1. Then the
length: at most twenty lines (redesign R31), with a task in flight and without
one.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from string import Template

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(PLUGIN, "skills", "rr-status", "status.py")
STATE = os.path.join(PLUGIN, "skills", "ai-task", "state.py")
ALIAS = os.path.join(PLUGIN, "skills", "ai-status", "SKILL.md")

_spec = importlib.util.spec_from_file_location("guard_common", os.path.join(PLUGIN, "hooks", "guard", "common.py"))
guard_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard_common)

TWIN_OF = "test-ai-status-root.sh"

# status.py's root and the shell guard's find_ai_root, one per line, from $PWD.
RESOLVED = """
set -uo pipefail
. "$1/hooks/lib/ai-hook-common.sh"
python3 -I "$2" | sed -n "s/^root: //p" | grep -v "^none" || printf "\\n"
AI_CWD=$PWD
find_ai_root "$PWD" || printf "\\n"
"""

LINE_KEY = re.compile(r"^([a-z ]+: |       \(b\) )")


def git(*args):
    subprocess.run(["git"] + list(args), capture_output=True, check=True)


def status(*args, cwd=None):
    done = subprocess.run([sys.executable, "-I", STATUS] + list(args), capture_output=True, text=True,
                          cwd=cwd, check=False)
    return done.returncode, done.stdout


class TestStatusRoot(unittest.TestCase):
    """The inner directory is a real repository, so a walk that stopped at the git
    root — the tempting shortcut, and the wrong one — is caught here rather than
    in someone's terminal."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for d in ("outer/repo/src/deep", "bare/src", "outer/.ai", "outer/repo/.ai"):
            os.makedirs(os.path.join(self.tmp, d))
        git("-C", os.path.join(self.tmp, "outer", "repo"), "init", "-q", "-b", "main")
        git("-C", os.path.join(self.tmp, "bare"), "init", "-q", "-b", "main")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rel(self, path):
        return path[len(self.tmp) + 1:] if path.startswith(self.tmp + "/") else path

    def resolved(self, rel):
        """(status.py, the shell guard, the Python guard), each relative to tmp or EMPTY."""
        d = os.path.join(self.tmp, rel)
        env = dict(os.environ, PWD=d)
        out = subprocess.run(["bash", "-c", RESOLVED, "_", PLUGIN, STATUS], capture_output=True, text=True,
                             cwd=d, env=env, check=False).stdout.split("\n")
        got = [out[0] if out else "", out[1] if len(out) > 1 else "", guard_common.find_ai_root(d, d) or ""]
        return tuple(self.rel(g) or "EMPTY" for g in got)

    def check(self, label, rel, expect):
        with self.subTest(Template("$label ($status)").substitute(label=label, status=expect)):
            got = self.resolved(rel)
            self.assertEqual(len(set(got)), 1, "%s: status.py and the guards disagree: %s" % (label, got))
            self.assertEqual(got[0], expect, "%s: all agree on the wrong root" % label)

    def test_status_and_find_ai_root_resolve_the_same_root(self):
        self.check("its own .ai/ at the repository root", "outer/repo", "outer/repo")
        self.check("its own .ai/, from a subdirectory", "outer/repo/src/deep", "outer/repo")
        shutil.rmtree(os.path.join(self.tmp, "outer", "repo", ".ai"))
        self.check("a .ai/ inherited from an ancestor", "outer/repo", "outer")
        self.check("inherited, from a subdirectory", "outer/repo/src/deep", "outer")
        self.check("no .ai/ anywhere above", "bare/src", "EMPTY")

    def test_root_flag(self):
        shutil.rmtree(os.path.join(self.tmp, "outer", "repo", ".ai"))
        _, out = status("--root", os.path.join(self.tmp, "outer", "repo", "src", "deep"))
        self.assertIn("root: %s\n" % os.path.join(self.tmp, "outer"), out,
                      "--root starts the same walk from another directory")

    def test_no_root(self):
        rc, out = status(cwd=os.path.join(self.tmp, "bare", "src"))
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^root: none", "no .ai/ above: root: none, exit 1")
        self.assertIn("run /rr-setup first", out, "and says what to do, as state.py does")
        self.assertNotIn("/ai-init", out)

    def test_no_task_in_flight(self):
        rc, out = status("--root", os.path.join(self.tmp, "outer"))
        self.assertEqual(rc, 0, out)
        self.assertLessEqual(len(out.splitlines()), 3, out)
        self.assertRegex(out, r"(?m)^task: none — no task in flight")
        self.assertRegex(out, r"(?m)^schema: project 0 · plugin [0-9]",
                         "root, no task in flight and schema: three lines")


class TestSchemaLine(unittest.TestCase):
    """R25: the plugin's schema is the .ai/VERSION template it ships, not a count of migrations."""

    def test_plugin_number_is_the_templates_version(self):
        with open(os.path.join(PLUGIN, "skills", "ai-init", "templates", ".ai", "VERSION"), encoding="utf-8") as fh:
            shipped = fh.read().strip()
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".ai"))
            for project, behind in (("3", True), (shipped, False)):
                with open(os.path.join(tmp, ".ai", "VERSION"), "w", encoding="utf-8") as fh:
                    fh.write(project + "\n")
                _, out = status("--root", tmp)
                self.assertIn("schema: project %s · plugin %s" % (project, shipped), out)
                self.assertEqual("behind: run /rr-setup --update" in out, behind, out)
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "skills", "project-update", "migrations")))


class TestPopulatedTask(unittest.TestCase):
    """A populated task stays within twenty lines."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        p = cls.p = os.path.join(cls.tmp, "proj")
        os.makedirs(os.path.join(p, "src"))
        os.makedirs(os.path.join(p, ".ai", "policies"))
        git("-C", p, "init", "-q", "-b", "main")
        git("-C", p, "config", "user.email", "t@example.com")
        git("-C", p, "config", "user.name", "t")
        with open(os.path.join(p, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("base\n")
        git("-C", p, "add", "-A")
        git("-C", p, "commit", "-qm", "base")
        with open(os.path.join(p, ".ai", "VERSION"), "w", encoding="utf-8") as fh:
            fh.write("7\n")
        files = ",".join("src/f%d.py" % i for i in range(1, 31))
        cls.state("start", "--goal", "a goal long enough to wrap\nand written over\nthree lines",
                  "--workflow", "feature", "--files", files, "--declare", "behaviour=0:fixture",
                  "--declare", "domain=0:fixture", "--declare", "novelty=0:fixture")
        cls.state("ask", "one question", "--option", "A: yes", "--option", "B: no")
        cls.state("ask", "two question", "--option", "A: yes", "--option", "B: no")
        cls.rc, cls.out = status("--root", p)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def state(cls, *args):
        env = {k: v for k, v in os.environ.items() if k != "AI_UNATTENDED"}
        subprocess.run([sys.executable, STATE, "--root", cls.p] + list(args), capture_output=True,
                       env=env, check=False)

    def test_at_most_twenty_lines(self):
        n = len(self.out.splitlines())
        with self.subTest(Template("a populated task: $n lines, at most 20").substitute(n=n)):
            self.assertEqual(self.rc, 0, self.out)
            self.assertLessEqual(n, 20, self.out)

    def test_it_shows_every_key(self):
        for prefix in ("root: " + self.p, "task: T-", "mode: light · W ", "stage: build",
                       "files: 30 in scope — src/f1.py", "verify: suite not_run · runs 0/2", "review: ",
                       "questions: 2 pending", "task: T-2026", "schema: project 7 · plugin", "last event: "):
            with self.subTest(Template("it shows: $prefix").substitute(prefix=prefix)):
                self.assertIn(prefix, self.out)

    def test_every_line_starts_with_its_key(self):
        """facts: prints (a) and (b) on two lines, the second indented under the first."""
        self.assertEqual([line for line in self.out.splitlines() if not LINE_KEY.match(line)], [],
                         "a multi-line goal stays on its own line (every line starts with its key)")

    def test_a_long_file_list_is_shortened(self):
        self.assertIn("(+26 more)", self.out, "a long file list is shortened, not wrapped")


class TestWaiting(unittest.TestCase):
    """R12: line 1 says who the task waits on — decisions, then the gate, then questions —
    and a decision waits by the rule the statusline and the guards use."""

    OPTIONS = [{"n": 1, "kind": "choice", "label": "Not now"}, {"n": 2, "kind": "command", "label": "state.py x"}]

    def setUp(self):
        self.p = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.p, ignore_errors=True)
        os.makedirs(os.path.join(self.p, "src"))
        os.makedirs(os.path.join(self.p, ".ai", "policies"))
        git("-C", self.p, "init", "-q", "-b", "main")
        git("-C", self.p, "config", "user.email", "t@example.com")
        git("-C", self.p, "config", "user.name", "t")
        with open(os.path.join(self.p, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("base\n")
        with open(os.path.join(self.p, ".ai", "VERSION"), "w", encoding="utf-8") as fh:
            fh.write("7\n")
        git("-C", self.p, "add", "-A")
        git("-C", self.p, "commit", "-qm", "base")

    def state(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "AI_UNATTENDED"}
        subprocess.run([sys.executable, STATE, "--root", self.p] + list(args), capture_output=True,
                       env=env, check=False)

    def start(self):
        self.state("start", "--goal", "g", "--workflow", "feature", "--files", "src/a.py",
                   "--declare", "behaviour=0:fixture", "--declare", "domain=0:fixture",
                   "--declare", "novelty=0:fixture")

    def write(self, name, data):
        os.makedirs(os.path.join(self.p, ".ai", "state"), exist_ok=True)
        with open(os.path.join(self.p, ".ai", "state", name), "w", encoding="utf-8") as fh:
            fh.write(data)

    def decisions(self, *named):
        self.write("decision.json", json.dumps({"version": 1, "open": [
            {"id": i, "header": h, "options": self.OPTIONS} for i, h in named]}))

    def ledger(self, *entries):
        self.write("consent.jsonl", "".join(json.dumps(dict(e, v=1)) + "\n" for e in entries))

    def read_state_file(self, name):
        with open(os.path.join(self.p, ".ai", "state", name), "rb") as fh:
            return fh.read()

    def gate(self, **extra):
        data = json.loads(self.read_state_file("state.json"))
        data["human_approval"] = {"requested_at": "2026-01-01T00:00:00Z", "gate_id": "G1"}
        self.write("state.json", json.dumps(dict(data, **extra)))

    def lines(self):
        rc, out = status("--root", self.p)
        self.assertEqual(rc, 0, out)
        return out.splitlines()

    def waiting(self):
        done = subprocess.run([sys.executable, "-I", STATE, "--root", self.p, "status", "--json"],
                              capture_output=True, text=True, check=False)
        return json.loads(done.stdout)["waiting"]

    def test_decisions(self):
        self.start()
        self.decisions(("D3", "Approve"), ("D4", "Commit"))
        self.assertEqual(self.lines()[0], "waiting on you: D3 Approve, D4 Commit — the dialog "
                                          "('state.py decision show' sends it again)")
        self.assertEqual(self.waiting(), {"on": "you", "decisions": ["D3", "D4"], "gate": None, "questions": []})

    def test_gate(self):
        self.start()
        self.gate()
        self.assertEqual(self.lines()[0], "waiting on you: gate G1 — approve in the dialog "
                                          "('state.py close' offers it) or in your own terminal")
        self.assertEqual(self.waiting()["gate"], "G1")

    def test_questions(self):
        self.start()
        self.state("ask", "one", "--option", "A: yes", "--option", "B: no")
        self.state("ask", "two", "--option", "A: yes", "--option", "B: no")
        first = self.lines()[0]
        self.assertRegex(first, r"^waiting on you: Q1, Q2 — answer in the dialog or the chat, "
                                r"or fill \[Answer\]: in \.ai/reports/T-[^/]+/task\.md$")
        self.assertEqual(self.waiting()["questions"], ["Q1", "Q2"])

    def test_agent(self):
        self.start()
        first = self.lines()[0]
        self.assertRegex(first, r"^waiting on the agent: build — edit, then ")
        self.assertEqual(self.waiting(), {"on": "agent", "decisions": [], "gate": None, "questions": []})

    def test_several_wait_decisions_then_gate_then_questions(self):
        self.start()
        self.state("ask", "one", "--option", "A: yes", "--option", "B: no")
        self.gate()
        self.decisions(("D1", "Approve"))
        first = self.lines()[0]
        self.assertLess(first.index("D1 Approve"), first.index("gate G1"))
        self.assertLess(first.index("gate G1"), first.index("Q1 —"))
        self.assertTrue(first.startswith("waiting on you: "), first)

    def test_a_decision_that_is_settled_or_fully_used_does_not_wait(self):
        self.start()
        self.decisions(("D1", "Settled"), ("D2", "Used"), ("D3", "Open"))
        pick = {"type": "pick", "tool_use_id": "t", "order": 1, "option": 2}
        self.ledger(dict(pick, decision="D1", id="P1"), {"type": "settle", "decision": "D1"},
                    dict(pick, decision="D2", id="P2"), {"type": "use", "id": "P2"})
        self.assertIn("waiting on you: D3 Open — the dialog", self.lines()[0])
        self.assertEqual(self.waiting()["decisions"], ["D3"])
        self.decisions(("D2", "Used"))
        self.assertTrue(self.lines()[0].startswith("waiting on the agent: "), self.lines()[0])

    def test_no_task_no_decision_is_todays_output(self):
        self.decisions()
        self.assertEqual(self.lines(), ["root: %s" % self.p, "task: none — no task in flight",
                                        status("--root", self.p)[1].splitlines()[2]])
        self.assertTrue(self.lines()[2].startswith("schema: project 7 · plugin "))
        self.assertEqual(self.waiting()["on"], "nobody")

    def test_no_task_but_an_open_decision(self):
        self.decisions(("D1", "Approve"))
        lines = self.lines()
        self.assertEqual(lines[0], "waiting on you: D1 Approve — the dialog ('state.py decision show' sends it again)")
        self.assertEqual(lines[1:3], ["root: %s" % self.p, "task: none — no task in flight"])

    def test_the_fullest_status_stays_within_twenty_lines(self):
        self.start()
        for i in range(5):
            self.state("ask", "q%d" % i, "--option", "A: yes", "--option", "B: no")
        self.gate(batch={"on": True, "by": "Rita"})
        self.decisions(*[("D%d" % i, "Header") for i in range(1, 7)])
        self.assertLessEqual(len(self.lines()), 20)

    def test_status_writes_nothing(self):
        self.start()
        self.decisions(("D1", "Used"))
        self.ledger({"type": "pick", "decision": "D1", "tool_use_id": "t", "order": 1, "option": 2, "id": "P1"},
                    {"type": "use", "id": "P1"})
        before = {n: self.read_state_file(n) for n in ("decision.json", "consent.jsonl")}
        self.lines()
        after = {n: self.read_state_file(n) for n in before}
        self.assertEqual(before, after, "a used decision is shown as not waiting but is not pruned by status")


class TestLegacyBudgets(unittest.TestCase):
    """status.py's own read (a task that is not schema 7) shows the budgets
    state.py enforces: weight.json's, the batch section's while the batch loop is on."""

    def run_status(self, batch_on):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, ".ai", "policies"))
        os.makedirs(os.path.join(tmp, ".ai", "state"))
        with open(os.path.join(tmp, ".ai", "policies", "weight.json"), "w", encoding="utf-8") as fh:
            json.dump({"axes": {}, "modes": {}, "review_rounds_max": 7, "tests": {"max_suite_runs": 9},
                       "batch": {"review_rounds_max": 4, "max_suite_runs": 6}}, fh)
        task = {"schema": 6, "task_id": "T-1", "goal": "g", "tests": {"suite_runs": 1}, "reviews": 1}
        if batch_on:
            task["batch"] = {"on": True}
        with open(os.path.join(tmp, ".ai", "state", "state.json"), "w", encoding="utf-8") as fh:
            json.dump(task, fh)
        return status("--root", tmp)[1]

    def test_standard_budgets_come_from_weight_json(self):
        out = self.run_status(False)
        self.assertIn("suite runs 1/9", out)
        self.assertIn("(1 of 7)", out)

    def test_batch_budgets_while_the_batch_loop_is_on(self):
        out = self.run_status(True)
        self.assertIn("suite runs 1/6", out)
        self.assertIn("(1 of 4)", out)


class TestFallbackReadsSchema7Counters(unittest.TestCase):
    """report() is the fallback when `state.py status` fails; on a schema-7 state it
    reads verify.suite_runs and review.passes, not the legacy counters."""

    def test_schema_7_counters_are_shown(self):
        spec = importlib.util.spec_from_file_location("status_mod", STATUS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(os.path.join(tmp, ".ai", "policies"))
        os.makedirs(os.path.join(tmp, ".ai", "state"))
        task = {"schema": 7, "task_id": "T-1", "goal": "g", "verify": {"suite_runs": 2},
                "review": {"passes": 1}}
        with open(os.path.join(tmp, ".ai", "state", "state.json"), "w", encoding="utf-8") as fh:
            json.dump(task, fh)
        out = "\n".join(mod.report(tmp)[0])
        self.assertIn("suite runs 2/", out)
        self.assertIn("(1 of ", out)


class TestAlias(unittest.TestCase):
    """The ai-status alias is gone (R19); rr-status stands alone."""

    @staticmethod
    def description(text):
        m = re.search(r"(?m)^description: (.*)$", text)
        return m.group(1) if m else ""

    def test_the_alias_is_gone(self):
        self.assertFalse(os.path.exists(os.path.dirname(ALIAS)), "skills/ai-status is deleted")

    def test_rr_status_description(self):
        with open(os.path.join(PLUGIN, "skills", "rr-status", "SKILL.md"), encoding="utf-8") as fh:
            desc = self.description(fh.read())
        self.assertLessEqual(len(desc.encode()) + 1, 1024, "rr-status/SKILL.md's description fits 1024 bytes")

    def test_no_bare_status_skill(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "skills", "status")),
                         "there is no bare skills/status any more")


if __name__ == "__main__":
    unittest.main()
