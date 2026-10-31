#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The schema-7 surface end to end: the light path is three state.py calls under
either runtime (R5, R19), the guarded path writes the handoff at its boundaries
only (R21) and asks nothing after the weight (R24), and a closed task leaves
the journal and task.md under reports/ (R8).

Skipped unless AI_E2E=1, so the fast `unittest discover` leaves it out; run it once
with AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import PLUGIN, decision, run  # noqa: E402  pylint: disable=wrong-import-position
from test_ai_task_state import ZERO, Project  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-end-to-end.sh"
# The shell suite's last case ran this module under unittest and passed with its
# "Ran N tests" line; the whole module runs under AI_E2E=1.
# The label as test_suite_parity reads it: up to the first inner double quote.
SHELL_MECHANICS = ("test_end_to_end.py: $(grep -oE '^Ran [0-9]+ tests?' <<<",)


@unittest.skipUnless(os.environ.get("AI_E2E"), "end to end: AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py")
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

    def test_a_task_that_asks_still_leaves_two_files(self):
        """R8 phase 3: a question and the gate, both answered in task.md, and no third file."""
        self.call("start", "--goal", "asks first", "--workflow", "feature", "--files", "src/widget.py",
                  "--tests", "tests/test_widget.py", *ZERO, "--mode", "full", "--by", "lead")
        task = self.p.state()["task_id"]
        self.call("ask", "Which wording?", "--option", "A: short", "--option", "B: long", "--recommend", "A")
        task_md = os.path.join(self.p.root, ".ai", "reports", task, "task.md")

        def fill(qid, answer):
            with open(task_md, encoding="utf-8") as fh:
                lines = fh.read().split("\n")
            start = lines.index(next(line for line in lines if line.startswith("## %s." % qid)))
            end = next(i for i in range(start, len(lines)) if lines[i].startswith("[Answer]:"))
            lines[end] = "[Answer]: " + answer
            with open(task_md, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))

        fill("Q1", "A")
        self.call("questions", "--sync", "--by", "ivan", human=True)
        self.p.write("src/widget.py", "x = 3\n")
        self.call("verify", "--scope", "all")
        self.call("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-",
                  stdin="FINDINGS\nnone\nVERDICT pass\n")
        self.assertIn("ready for approval", self.call("close").stdout)
        fill("G1", "A")
        self.call("questions", "--sync", "--by", "ivan", human=True)
        self.call("close")
        self.assertFalse(self.p.in_flight())
        self.assertEqual(self.reports(task), ["events.jsonl", "task.md"])
        with open(task_md, encoding="utf-8") as fh:
            text = fh.read()
        self.assertRegex(text, r"(?m)^\[Answer\]: A — by ivan via file at ")
        self.assertIn("## Q1. Which wording?", text)


def patch(*paths):
    """One apply_patch payload updating each path."""
    return "*** Begin Patch\n%s*** End Patch\n" % "".join(
        "*** Update File: %s\n@@\n-old\n+new\n" % p for p in paths)


@unittest.skipUnless(os.environ.get("AI_E2E"), "end to end: AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py")
class TestInstalledPipeline(unittest.TestCase):
    """The whole thing, wired together the way it runs in practice: install into a
    scratch CLAUDE_DIR, scaffold a throwaway repository, then drive one task
    through the state machine while the guards are armed against it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "claude")
        self.cdir = os.path.join(self.tmp, "codex")
        self.repo = os.path.join(self.tmp, "shop")
        for d in (self.dir, self.cdir, "shop/src/Payment", "shop/src/Order", "shop/tests/Payment"):
            os.makedirs(os.path.join(self.tmp, d), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sh(self, *args, env=None):
        return subprocess.run(list(args), capture_output=True, text=True, env=dict(os.environ, **(env or {})),
                              check=False)

    def write(self, rel, text):
        with open(os.path.join(self.repo, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def state(self, *args, home=None):
        return self.sh(sys.executable, os.path.join(home or self.dir, "skills", "ai-task", "state.py"),
                       "--root", self.repo, *args)

    def call(self, guard, tool, tool_input):
        """(decision, output) of a guard on one PreToolUse payload in the repo."""
        _, out = run(guard, {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": self.repo,
                             "tool_input": tool_input})
        return decision(out), out

    def decide(self, guard, tool, tool_input):
        return self.call(guard, tool, tool_input)[0]

    def edit(self, rel):
        return {"file_path": os.path.join(self.repo, rel)}

    def check(self, label, ok, detail=""):
        with self.subTest(label):
            self.assertTrue(ok, "%s %s" % (label, detail))

    def test_installed_pipeline(self):  # pylint: disable=too-many-locals,too-many-statements
        repo, hooks, chooks = self.repo, os.path.join(self.dir, "hooks"), os.path.join(self.cdir, "hooks")

        # install
        self.sh("node", os.path.join(PLUGIN, "bin", "riskrails.js"), "--plan", "max", "--fable", "yes",
                env={"CLAUDE_DIR": self.dir})
        self.check("installed into a scratch CLAUDE_DIR",
                   os.path.isfile(os.path.join(self.dir, "skills", "ai-init", "scaffold-ai.sh")))

        # scaffold a project
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                     ("config", "user.name", "t")):
            self.sh("git", "-C", repo, *args)
        self.write("src/Payment/Gateway.php", "<?php class Gateway {}\n")
        self.write("src/Payment/LegacyGateway.php", "<?php class LegacyGateway {}\n")
        self.write("src/Order/OrderProcessor.php", "<?php class OrderProcessor {}\n")
        self.write(".env", "SECRET=live_key_do_not_read\n")
        self.sh("git", "-C", repo, "add", "src")
        self.sh("git", "-C", repo, "commit", "-qm", "initial")
        self.sh("bash", os.path.join(self.dir, "skills", "ai-init", "scaffold-ai.sh"), repo,
                env={"CLAUDE_AGENTIC_TEMPLATES": os.path.join(self.dir, "skills", "ai-init", "templates")})
        self.check(".ai/ scaffolded into the project", os.path.isfile(os.path.join(repo, ".ai", "AGENTS.md")))
        self.check("the weight table is in place",
                   os.path.isfile(os.path.join(repo, ".ai", "policies", "weight.json")))
        self.check("the retired risk tiers are not shipped",
                   not os.path.exists(os.path.join(repo, ".ai", "policies", "risk-tiers.json")))

        # One registered command runs all three checks (3.5): the one settings.json names.
        path_guard = scope_guard = git_guard = ["python3", "-I", "-S", os.path.join(hooks, "ai-guard.py")]
        self.check("no shell guard is installed", not any(
            os.path.lexists(os.path.join(hooks, "ai-%s-guard.sh" % g)) for g in ("git", "path", "scope")))

        # the path guard is now live in this project
        self.check("reading .env is refused once the project has .ai/",
                   self.decide(path_guard, "Read", self.edit(".env")) == "deny")
        self.check("reading source is unaffected",
                   self.decide(path_guard, "Read", self.edit("src/Payment/Gateway.php")) == "allow")

        # a task through the pipeline
        done = self.state("start", "--goal", "add a handling fee to the payment gateway", "--workflow", "feature",
                          "--files", "src/Payment/Gateway.php,tests/Payment/*.php",
                          "--tests", "tests/Payment/FeeTest.php",
                          "--declare", "behaviour=1:a fee on every payment",
                          "--declare", "novelty=0:an existing gateway")
        self.check("start registers the task and arms the scope guard", done.returncode == 0, done.stderr)
        self.assertEqual(done.returncode, 0)
        state_file = os.path.join(repo, ".ai", "state", "state.json")
        if not os.path.exists(state_file):
            state_file = os.path.join(repo, ".ai", "state", "current.json")
        with open(state_file, encoding="utf-8") as fh:
            current = json.load(fh)
        task = current["task_id"]
        self.check("a payment path weighs in at full mode", current["mode"] == "full",
                   json.dumps(current.get("weight", {}).get("lines")))

        # the scope guard enforces the step
        self.check("editing an allowed file is permitted",
                   self.decide(scope_guard, "Edit", self.edit("src/Payment/Gateway.php")) == "allow")
        self.check("writing the required test is permitted",
                   self.decide(scope_guard, "Write", dict(self.edit("tests/Payment/FeeTest.php"), content="x"))
                   == "allow")
        self.check("editing an out-of-scope file is refused",
                   self.decide(scope_guard, "Edit", self.edit("src/Order/OrderProcessor.php")) == "deny")
        self.check("a file beside the task's, unnamed, is refused",
                   self.decide(scope_guard, "Edit", self.edit("src/Payment/LegacyGateway.php")) == "deny")
        _, out = self.call(scope_guard, "Edit", self.edit("src/Order/OrderProcessor.php"))
        self.check("the refusal carries the SCOPE_CHANGE_REQUIRED signal", "SCOPE_CHANGE_REQUIRED" in out, out)

        # the same task, from Codex: a second runtime installed over the same project
        # must land on the same state file and enforce the same step — the pipeline
        # is shared, only the adapter differs.
        self.sh("node", os.path.join(PLUGIN, "bin", "riskrails.js"), env={"CODEX_DIR": self.cdir})
        self.check("installed into a scratch CODEX_DIR", os.path.isfile(os.path.join(chooks, "ai-guard.py")))
        self.check("the Codex agent roster is rendered",
                   os.path.isfile(os.path.join(self.cdir, "agents", "ai-reviewer.toml")))
        self.check("no Claude-only hook is installed into Codex",
                   not os.path.lexists(os.path.join(chooks, "cap-large-read.py")))
        # Codex has UserPromptSubmit, PreCompact and SessionStart, so the context guard
        # crosses: the handoff, the questions and session.json are the same on both
        # sides. What does not cross is the transcript-derived snapshot, which is built
        # from a Claude transcript — the script knows which runtime it is in from its
        # own location.
        self.check("the context guard is installed into Codex too",
                   os.path.lexists(os.path.join(chooks, "context-guard.py")))
        with open(os.path.join(self.cdir, "hooks.json"), encoding="utf-8") as fh:
            registered = json.load(fh)["hooks"]
        commands = [h["command"] for groups in registered.values() for group in groups for h in group["hooks"]]
        self.check("and registered on its three events there",
                   len([c for c in commands if "context-guard" in c]) == 3, sorted(registered))

        codex_scope = codex_path = codex_git = ["python3", "-I", "-S", os.path.join(chooks, "ai-guard.py")]

        # The state the Claude half of this test wrote is the state Codex reads.
        out = self.state("status", home=self.cdir).stdout
        self.check("Codex reads the task the Claude session started", ("\ntask: %s" % task) in "\n" + out, out)
        out = self.state("status", "--json", home=self.cdir).stdout
        self.check("and the same mode", json.loads(out or "{}").get("mode") == "full", out)

        gateway, order = os.path.join(repo, "src/Payment/Gateway.php"), os.path.join(repo, "src/Order/OrderProcessor.php")
        ap = lambda guard, *paths: self.call(guard, "apply_patch", {"command": patch(*paths)})  # noqa: E731
        self.check("an in-scope apply_patch is permitted", ap(codex_scope, gateway)[0] == "allow")
        self.check("an out-of-scope apply_patch is refused", ap(codex_scope, order)[0] == "deny")
        self.check("one out-of-scope file rejects the whole patch", ap(codex_scope, gateway, order)[0] == "deny")
        self.check("an unnamed file is refused through apply_patch too",
                   ap(codex_scope, os.path.join(repo, "src/Payment/LegacyGateway.php"))[0] == "deny")
        out = ap(codex_scope, order)[1]
        self.check("and the Codex refusal carries the same signal", "SCOPE_CHANGE_REQUIRED" in out, out)
        self.check("the path guard refuses a patch that touches .env",
                   ap(codex_path, os.path.join(repo, ".env"))[0] == "deny")
        self.check("the git guard refuses a force push from Codex as well",
                   self.decide(codex_git, "Bash", {"command": "git push --force origin main"}) == "deny")

        # finishing the task. The full path to the gate needs a verify_command this
        # fixture does not have; TestEndToEnd and test_ai_task_state.py::TestGate drive it.
        done = self.state("close", "--abandon")
        self.check("close --abandon ends the task", done.returncode == 0 and not os.path.exists(state_file),
                   done.stderr)

        # the scope guard disarms when no step is current
        self.check("out-of-scope edits are free again once the task closes",
                   self.decide(scope_guard, "Edit", self.edit("src/Order/OrderProcessor.php")) == "allow")

        # the git guard still refuses the dangerous half
        for label, command, expect in (
                ("force push is refused", "git push --force origin main", "deny"),
                ("pushing to main is refused", "git push origin main", "deny"),
                ("'git add .' with an untracked .env is refused", "git add .", "deny"),
                ("ordinary git commands are unaffected", "git status", "allow")):
            self.check(label, self.decide(git_guard, "Bash", {"command": command}) == expect)

        # the audit trail survives
        archived = os.path.join(repo, ".ai", "state", "logs", task, "state.json")
        result = None
        if os.path.isfile(archived):
            with open(archived, encoding="utf-8") as fh:
                result = json.load(fh).get("result")
        self.check("the closed task's state is kept under .ai/state/logs/", result == "abandoned")
        events = []
        journal = os.path.join(repo, ".ai", "reports", task, "events.jsonl")
        if os.path.isfile(journal):
            with open(journal, encoding="utf-8") as fh:
                events = [json.loads(line) for line in fh if line.strip()]
        self.check("and the journal says how it ended",
                   bool(events) and events[-1]["event"] == "task_closed"
                   and events[-1].get("data", {}).get("abandoned") is True)
        self.check("and task.md is the record", os.path.isfile(os.path.join(repo, ".ai", "reports", task, "task.md")))

        # no application code was touched by any of this
        out = self.sh("git", "-C", repo, "status", "--porcelain", "--", "src").stdout
        self.check("src/ is untouched", out == "", out)


@unittest.skipUnless(os.environ.get("AI_E2E"), "end to end: AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py")
class TestCompactMemory(unittest.TestCase):
    """compact-project-memory M12: enable → start → close → record → pre-push →
    fresh clone → show, through state.py, the installed hook and git."""

    def test_the_record_travels_with_the_push(self):
        import memory_harness as mh  # pylint: disable=import-outside-toplevel
        p = mh.Project()
        self.addCleanup(p.close)
        remote = os.path.join(p.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", remote], check=True)
        p.git("remote", "add", "origin", remote)
        self.assertIn("pre-push: installed", p.ok("memory", "enable", "--author", "dev", human=True).stdout)
        p.commit("memory on")
        task, out = p.rich_task("travels with the push")
        self.assertIn("record: .ai/memory/", out)
        self.assertIn("%s sealed" % task, out)
        p.commit("the task")
        pushed = p.git("push", "-q", "origin", "main", check=False)
        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        shown = p.ok("memory", "show", task).stdout
        clone = mh.Project("clone", tmp=p.tmp, clone_of=remote)
        self.assertEqual(clone.ok("memory", "show", task).stdout, shown)
        self.assertEqual(p.run("memory", "verify", "--fresh-clone").returncode, 0)
        self.assertIn('"Which cache key?" → A "by locale" by vanssa', clone.ok("recall", "--files",
                                                                                "src/widget.py").stdout)
        name = os.listdir(p.path(".ai/memory"))[0]
        lines = p.read(".ai/memory/" + name, binary=True).split(b"\n")
        p.write(".ai/memory/" + name, b"\n".join(lines[:1] + lines[2:]), mode="wb")
        p.commit("drops a record")
        refused = p.git("push", "-q", "origin", "main", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("V2", refused.stderr)


if __name__ == "__main__":
    unittest.main()
