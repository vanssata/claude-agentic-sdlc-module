#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
hooks/memory-pre-push.py and `memory enable|disable` (spec §D10, §I5, R14,
R16, R17, A8, A10): the checks V1–V9 on the pushed blobs, per ref; the exit
codes; the shim installed only where no hook and no core.hooksPath exist.
"""
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_harness as gh  # noqa: E402  pylint: disable=wrong-import-position
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import memory_io as mio  # noqa: E402  pylint: disable=wrong-import-position
import memory_verify as mver  # noqa: E402  pylint: disable=wrong-import-position

ZERO = "0" * 40
FACTOR = float(os.environ.get("AI_TIMED_FACTOR", "1"))
DIALOG_SESSION = "sess-memory"
RECORDER = os.path.join(mh.ROOT, "hooks", "dialog-gate.py")
ASK_SINGLE = os.path.join(mh.ROOT, "tests", "fixtures", "dialog", "claude", "ask-single.json")
STAMP = "%Y-%m-%dT%H:%M:%SZ"
# The memory verbs that stay the human's whatever a pick says (R14): `what` as memory_human names it, and an argv
# argparse accepts, so that a refusal is memory_human's and not a usage error.
TERMINAL_ONLY = {
    "disable": ("memory", "disable"),
    "cleanup": ("memory", "cleanup", "--all", "--confirm-delete", "dev"),
    "pack": ("memory", "pack", "--period", "2026-Q4", "--confirm-delete", "dev"),
    "redact": ("memory", "redact", "r1", "--field", "text", "--why", "a test"),
    "migrate --move-logs": ("memory", "migrate", "--move-logs", "--confirm-delete", "dev"),
}


def dialog_session(project, session=DIALOG_SESSION):
    """Turn the dialog on in `project` for one agent session (R36) and return the environment that session's
    state.py calls carry. Project.run first drops every agent marker and AI_UNATTENDED and sets AI_RUNTIME=claude;
    this adds what rr_state/dialog.py dialog_on() reads: CLAUDECODE marks an agent, the session id is what a
    pick is bound to (SESSION_ENV), the runtime home's profile.json names the verified dialog tool (DIALOG_TOOL),
    and the session is attended. The result does not depend on the session that runs the suite, in an agent
    session or in plain CI."""
    home = os.path.join(project.tmp, "home")
    os.makedirs(os.path.join(home, "riskrails"), exist_ok=True)
    with open(os.path.join(home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
        json.dump({"plan": "max", "dialog": {"tool": "AskUserQuestion"}}, fh)
    project.write(".ai/policies/dialog.json",
                  json.dumps({"version": 1, "enabled": True, "window_seconds": 120, "stop_blocks_max": 2}))
    return {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": session, "CLAUDE_CONFIG_DIR": home,
            "CLAUDE_CODE_SESSION_ATTENDED": "1"}


def command_label(project, *argv):
    """The command a pick carries, written as labels.state_label writes it: this state.py, absolute, with --root,
    quoted — so the human's pick and the agent's call are one string."""
    return "python3 %s %s" % (shlex.quote(mh.STATE), shlex.join(["--root", project.root, *argv]))


def open_memory_decision(project, env, label):
    """The memory question of /rr-setup, opened the way the skill opens it (`decision open --kind setup --spec -`);
    the opener's stdout: DIALOG_PENDING, then the JSON the agent sends to the dialog tool."""
    spec = {"schema": 1, "decisions": [{
        "key": "memory", "header": "Memory",
        "question": "Project memory for p: on shares every closed task with the team. Turn it on?",
        "options": [{"kind": "choice", "label": "Off — keep files mode", "value": "off"},
                    {"kind": "command", "label": label}]}]}
    return project.ok("decision", "open", "--kind", "setup", "--spec", "-", stdin=json.dumps(spec), env=env).stdout


def record_pick(project, env, opened, label, call="toolu_memory"):
    """The human picks `label` in the dialog that `opened` printed, and the PostToolUse hook records it from a
    harness payload recorded in a real session (tests/fixtures/dialog/claude): nothing is written into the ledger
    by hand. (exit code, output) of the hook."""
    questions = json.loads(opened.splitlines()[1])["questions"]
    with open(ASK_SINGLE, encoding="utf-8") as fh:
        payload = json.load(fh)["payload"]
    payload.update(cwd=project.root, session_id=env["CLAUDE_CODE_SESSION_ID"], tool_use_id=call)
    for holder in ("tool_input", "tool_response"):
        payload[holder] = {"questions": questions, "answers": {questions[0]["question"]: label}}
    return gh.run([sys.executable, "-I", "-S", RECORDER], payload, env=mh.clean_env(env), cwd=project.root)


def forge_pick(project, argv, session=DIALOG_SESSION):
    """A live pick of the command `argv`, written by hand: its line in the ledger and the decision it belongs to, as
    the recorder and state.py write them, in place of whatever was there. For a command the label allowlist
    refuses to offer, which no dialog could record. The pick."""
    label, now = command_label(project, *argv), time.time()
    pick = {"v": 1, "type": "pick", "id": "C1", "decision": "D1", "option": 2, "order": 1, "label": label,
            "session": session, "tool_use_id": "toolu_forged", "transcript": "", "runtime": "claude",
            "at": time.strftime(STAMP, time.gmtime(now)), "expires_at": time.strftime(STAMP, time.gmtime(now + 120))}
    decision = {"id": "D1", "kind": "setup", "task": None, "runtime": "claude", "session": session, "tree": "",
                "opened_at": pick["at"], "opened_by": "the test", "header": "Memory", "multi_select": False,
                "question": "Forged: %s" % " ".join(argv),
                "options": [{"kind": "choice", "label": "Off — keep files mode", "value": "off", "effect": "set", "n": 1},
                            {"kind": "command", "label": label, "n": 2}]}
    project.write(".ai/state/decision.json", json.dumps({"version": 1, "open": [decision]}))
    project.write(".ai/state/consent.jsonl", json.dumps(pick) + "\n")
    return pick


class Repo(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.base = self.p.commit("memory on")
        self.task, _ = self.p.light_task("first change")
        self.head = self.p.commit("first task")

    def package(self):
        name = sorted(os.listdir(self.p.path(".ai/memory")))[0]
        return ".ai/memory/" + name

    def lines(self):
        return self.p.read(self.package(), binary=True).split(b"\n")[:-1]

    def put(self, lines, message="edit"):
        self.p.write(self.package(), b"\n".join(lines) + b"\n", mode="wb")
        return self.p.commit(message)

    def check(self, old, new):
        done = mh.hook_run(self.p.root, "--range", "%s..%s" % (old, new))
        return done.returncode, done.stderr


class TestChecks(Repo):
    def test_a_valid_range_is_clean(self):
        self.assertEqual(self.check(self.base, self.head), (0, ""))

    def test_v1_crlf_and_bom_name_the_line(self):
        lines = self.lines()
        lines[2] = lines[2] + b"\r"
        code, err = self.check(self.head, self.put(lines))
        self.assertEqual(code, 1)
        self.assertRegex(err, r"memory-pre-push: %s\.\.\w+: V1: %s:3: CRLF line ending — fix: " % (
            self.head, self.package().replace(".", r"\.")))
        self.assertIn("checked 1 packages", err)
        lines = self.lines()
        lines[0] = b"\xef\xbb\xbf" + lines[0].rstrip(b"\r")
        code, err = self.check(self.head, self.put([l.rstrip(b"\r") for l in lines]))
        self.assertIn(":1: starts with a UTF-8 BOM", err)

    def test_v2_a_lost_record(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        kept = [l for l in lines if json.loads(l).get("rid") != json.loads(lines[1]).get("rid")]
        del seal
        code, err = self.check(self.head, self.put(kept))
        self.assertEqual(code, 1)
        self.assertIn(": V2: .ai/memory/: 1 record(s) of", err)

    def test_v3_two_unchained_seals(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        other = mf.with_rid(dict(seal, goal="another goal"))
        code, err = self.check(self.head, self.put(lines + [mf.canonical(other)]))
        self.assertEqual(code, 1)
        self.assertIn(": V3: ", err)
        self.assertIn("%s#1 has 2 seals not chained by supersedes" % self.task, err)

    def test_v4_a_digest_that_does_not_match(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        bad = mf.with_rid(dict(seal, digest="sha256:" + "0" * 64))
        code, err = self.check(self.head, self.put(lines[:-1] + [mf.canonical(bad)]))
        self.assertEqual(code, 1)
        self.assertIn(": V4: ", err)

    def test_v5_a_closed_task_without_its_record(self):
        q = mh.Project("files", tmp=self.p.tmp)
        task, _ = q.light_task("closed before enable")
        q.ok("memory", "enable", "--author", "dev", human=True)
        head = q.commit("enable")
        done = mh.hook_run(q.root, "--tree", head)
        self.assertEqual(done.returncode, 1)
        self.assertIn("V5: .ai/reports/%s/events.jsonl: %s#1 is closed but has no seal — fix: state.py memory "
                      "export %s" % (task, task, task), done.stderr)

    def test_v5_legacy_tasks_without_a_seal_are_not_findings(self):
        os.makedirs(self.p.path(".ai/reports/T-2026-10-28-009"))
        for name in ("events.jsonl", "task.md"):
            with open(os.path.join(mh.FIXTURES, "legacy-reports", "T-2026-10-28-009", name), encoding="utf-8") as fh:
                self.p.write(".ai/reports/T-2026-10-28-009/" + name, fh.read())
        self.assertEqual(self.check(self.head, self.p.commit("legacy dir")), (0, ""))
        self.assertIn("legacy, not migrated: 1", self.p.ok("memory", "status").stdout)

    def test_v6_logs_and_local_data(self):
        self.p.write(".ai/reports/%s/suite-1.log" % self.task, "log\n")
        code, err = self.check(self.head, self.p.commit("a log"))
        self.assertEqual(code, 1)
        self.assertIn(": V6: .ai/reports/%s/suite-1.log: a log is committed" % self.task, err)
        self.p.git("rm", "-q", "--cached", ".ai/reports/%s/suite-1.log" % self.task)
        self.p.git("add", "-f", ".ai/local/memory/batches.json")
        code, err = self.check(self.head, self.p.commit("local data"))
        self.assertIn(": V6: .ai/local/memory/batches.json: local data is committed", err)

    def test_v7_with_cleanup_on(self):
        self.p.memory_json(cleanup=True)
        code, err = self.check(self.head, self.p.commit("cleanup on"))
        self.assertEqual(code, 1)
        self.assertIn(": V7: .ai/reports/%s/: cleanup is on and %s is sealed" % (self.task, self.task), err)

    def test_v8_size(self):
        self.p.memory_json(package_max_bytes=200)
        code, err = self.check(self.head, self.p.commit("tiny limit"))
        self.assertEqual(code, 1)
        self.assertIn("over twice package_max_bytes", err)
        self.p.memory_json(package_max_bytes=len(self.p.read(self.package(), binary=True)) - 1)
        code, err = self.check(self.head, self.p.commit("warn only"))
        self.assertEqual(code, 0, err)
        self.assertIn("V8-warn", err)

    def test_files_mode_is_silent_and_errors_fail_closed(self):
        self.p.memory_json(mode="files")
        self.assertEqual(self.check(self.head, self.p.commit("off")), (0, ""))
        code, err = self.check("nosuchrev", "alsono")
        self.assertEqual(code, 3)
        self.assertIn("state.py memory verify --all", err)
        self.assertIn("git push --no-verify", err)

    def test_the_hook_form_per_ref(self):
        remote = os.path.join(self.p.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", remote], check=True)
        self.p.git("remote", "add", "origin", remote)
        self.p.git("push", "-q", "--no-verify", "origin", self.base + ":refs/heads/main")
        self.p.git("fetch", "-q", "origin")
        lines = self.lines()
        bad = self.put(lines[:1] + [lines[1] + b"\r"] + lines[2:])
        stdin = "".join(["refs/heads/main %s refs/heads/main %s\n" % (self.head, self.base),
                         "refs/heads/new %s refs/heads/new %s\n" % (bad, ZERO),
                         "refs/tags/v1 %s refs/tags/v1 %s\n" % (bad, ZERO),
                         "(delete) %s refs/heads/gone %s\n" % (ZERO, self.base)])
        done = mh.hook_run(self.p.root, "origin", remote, stdin=stdin)
        self.assertEqual(done.returncode, 1)
        self.assertIn("memory-pre-push: refs/heads/new: V1:", done.stderr)
        self.assertNotIn("refs/heads/main:", done.stderr)
        self.assertNotIn("refs/tags/v1", done.stderr)
        self.assertEqual(mh.hook_run(self.p.root, "origin", remote, stdin=stdin.splitlines()[0] + "\n")
                         .returncode, 0)

    def test_v9_a_pending_export_stops_a_local_push(self):
        os.makedirs(self.p.path(".ai/local/memory/outbox"), exist_ok=True)
        self.p.write(".ai/local/memory/outbox/T-x~1.jsonl", "{}\n")
        stdin = "refs/heads/main %s refs/heads/main %s\n" % (self.head, self.base)
        done = mh.hook_run(self.p.root, "origin", "url", stdin=stdin)
        self.assertEqual(done.returncode, 1)
        self.assertIn("V9: .ai/local/memory/outbox: an export is pending", done.stderr)
        self.assertEqual(self.check(self.base, self.head), (0, ""))          # --range: V9 off

    def test_a_real_push_runs_the_installed_hook(self):
        remote = os.path.join(self.p.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", remote], check=True)
        self.p.git("remote", "add", "origin", remote)
        self.assertEqual(self.p.git("push", "-q", "origin", "main", check=False).returncode, 0)
        lines = self.lines()
        self.put(lines[:1] + lines[2:])
        done = self.p.git("push", "-q", "origin", "main", check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("V2", done.stderr)

    def test_v6_sqlite_outside_ai_is_the_projects(self):
        """Review M6: only the index's own kind of file under .ai/ is refused."""
        self.p.write("tests/fixtures/db/app.sqlite3", "SQLite format 3\n")
        self.assertEqual(self.check(self.head, self.p.commit("a fixture db")), (0, ""))
        self.p.write(".ai/index.sqlite3", "SQLite format 3\n")
        code, err = self.check(self.head, self.p.commit("an index"))
        self.assertEqual(code, 1)
        self.assertIn(": V6: .ai/index.sqlite3: local data is committed", err)

    def test_journals_are_read_in_one_batch(self):
        """Review M5: one `cat-file --batch` for all journals, not one per journal."""
        for n in range(6):
            self.p.light_task("task %d" % n, change="x = %d\n" % (n + 10))
        head = self.p.commit("six more")
        calls = []
        real = mio.subprocess.run

        def counting(args, *a, **kw):
            if "cat-file" in args and "--batch" in args:
                calls.append(args)
            return real(args, *a, **kw)  # pylint: disable=subprocess-run-check
        mio.subprocess.run = counting
        try:
            findings, stats = mver.validate_range(self.p.root, self.head, head)
        finally:
            mio.subprocess.run = real
        self.assertEqual(findings, [])
        self.assertEqual(stats["tasks"], 7)
        self.assertLessEqual(len(calls), 3, calls)                      # T's packages, O's, T's journals


class TestTimed(unittest.TestCase):
    def test_a_59_task_history_validates_quickly(self):
        spec = importlib.util.spec_from_file_location("bench", os.path.join(mh.ROOT, "tools", "benchmark-memory.py"))
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        p = mh.Project()
        self.addCleanup(p.close)
        p.memory_json()
        bench.write_packages(p.root, bench.generate(59, seed=2))
        head = p.commit("59 tasks")
        started = time.time()
        done = mh.hook_run(p.root, "--tree", head)
        elapsed = time.time() - started
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertLess(elapsed, 0.5 * FACTOR + 0.4, "%.3f s (the sanity bound is 500 ms plus interpreter start)"
                        % elapsed)


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)

    def hook(self):
        return self.p.path(".git/hooks/pre-push")

    @staticmethod
    def ledger(project):
        """consent.jsonl, a dict per line."""
        if not project.exists(".ai/state/consent.jsonl"):
            return []
        return [json.loads(line) for line in project.read(".ai/state/consent.jsonl").splitlines()]

    @staticmethod
    def kept(project):
        """What a refused run leaves as it found it: the ledger and the decision file byte for byte, the tree's files."""
        return tuple(project.read(".ai/state/" + name) if project.exists(".ai/state/" + name) else None
                     for name in ("consent.jsonl", "decision.json")) + (project.tree_listing(),)

    @staticmethod
    def live(project, env):
        """The ids of the picks the dialog route could still consume, as `state.py consent` lists them."""
        return [pick["id"] for pick in json.loads(project.ok("consent", "--json", env=env).stdout)["live"]]

    def refused(self, project, env, what, argv):
        """`argv` from the agent is the human's: exit 5 with the usual refusal, nothing printed, nothing written, the
        ledger as it was."""
        before = self.kept(project)
        done = project.run(*argv, env=env)
        self.assertEqual((done.returncode, done.stdout), (5, ""), (argv, done.stderr))
        self.assertIn("APPROVAL_REFUSED — 'memory %s' is the human's" % what, done.stderr)
        self.assertIn("inside an agent session (CLAUDECODE", done.stderr)
        self.assertEqual(self.kept(project), before, argv)
        return done

    def test_enable_and_disable_need_the_human(self):
        for args in (("memory", "enable"), ("memory", "disable")):
            done = self.p.run(*args)
            self.assertEqual(done.returncode, 5, args)
            self.assertIn("APPROVAL_REFUSED", done.stderr)
        self.assertFalse(self.p.exists(".ai/policies/memory.json"))
        self.assertFalse(os.path.exists(self.hook()))

    def test_enable_refused_dialog_on_no_pick(self):
        """interactive-setup-options R14, characterization (C2): with the dialog on and no pick in the ledger, an
        agent's `memory enable` is still the human's: exit 5, nothing written, no decision opened."""
        env = dialog_session(self.p)
        consent = json.loads(self.p.ok("consent", "--json", env=env).stdout)
        self.assertEqual((consent["dialog"], consent["live"], consent["tail"]), (True, [], []))
        written = self.p.tree_listing()
        for args in (("memory", "enable"), ("memory", "enable", "--index", "sqlite")):
            done = self.p.run(*args, env=env)
            self.assertEqual(done.returncode, 5, (args, done.stdout, done.stderr))
            self.assertIn("APPROVAL_REFUSED", done.stderr)
            self.assertIn("inside an agent session (CLAUDECODE", done.stderr)
            self.assertFalse(self.p.exists(".ai/policies/memory.json"), args)
            self.assertFalse(os.path.exists(self.hook()), args)
            self.assertFalse(os.path.exists(mio.local_path(self.p.root, "config.json")), args)
            self.assertEqual(self.p.tree_listing(), written, args)

    def test_enable_via_dialog_pick(self):
        """interactive-setup-options R14: the human picks `memory enable …` in the dialog /rr-setup opens and the agent
        runs the label verbatim. It runs as the human's route and says so on its first line, prints what a human's run
        prints, switches memory on and installs the hook; the pick is spent, and the decision it settled is closed."""
        env = dialog_session(self.p)
        argv = ("memory", "enable", "--author", "dev", "--period", "quarter")
        label = command_label(self.p, *argv)
        opened = open_memory_decision(self.p, env, label)
        self.assertTrue(opened.startswith("DIALOG_PENDING D1 "), opened)
        self.assertEqual(record_pick(self.p, env, opened, label), (0, ""))
        [pick] = [line for line in self.ledger(self.p) if line["type"] == "pick"]
        self.assertEqual((pick["id"], pick["decision"], pick["label"]), ("C1", "D1", label))
        self.assertEqual(shlex.split(label)[2:], ["--root", self.p.root, *argv], "the label is the argv the agent runs")
        self.assertEqual(self.live(self.p, env), ["C1"])
        self.assertFalse(self.p.exists(".ai/policies/memory.json"))
        done = self.p.run(*argv, env=env)
        self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
        human = mh.Project("human", tmp=self.p.tmp).ok(*argv, human=True).stdout          # the unattended route
        self.assertEqual(human.splitlines()[:2], ["memory: packages mode on (%s); every teammate's next close exports"
                                                  % mio.POLICY_REL, "pre-push: installed"])
        self.assertNotIn("via dialog", human)
        self.assertEqual(done.stdout, "memory: via dialog (consent C1, decision D1)\n" + human)
        policy = json.loads(self.p.read(".ai/policies/memory.json"))
        self.assertEqual((policy["mode"], policy["period"]), ("packages", "quarter"))
        self.assertTrue(os.access(self.hook(), os.X_OK))
        self.assertIn(mio.HOOK_MARKER, self.p.read(".git/hooks/pre-push"))
        ledger = self.ledger(self.p)
        self.assertEqual([line["type"] for line in ledger], ["offer", "pick", "use", "settle"])
        self.assertEqual(ledger[2]["id"], "C1")
        self.assertEqual((ledger[3]["decision"], ledger[3]["pick"]), ("D1", "C1"))
        self.assertEqual(self.live(self.p, env), [])
        self.assertFalse(self.p.exists(".ai/state/decision.json"))

    def test_enable_pick_used_once(self):
        """interactive-setup-options R14: a pick is one command, once. With the pick live, any other argv — an option
        added or left out, another value, another order, another project — is refused (exit 5) and leaves it live and
        unspent; the exact command then runs, and run again it is refused."""
        env = dialog_session(self.p)
        argv = ("memory", "enable", "--author", "dev", "--period", "quarter")
        label = command_label(self.p, *argv)
        self.assertEqual(record_pick(self.p, env, open_memory_decision(self.p, env, label), label), (0, ""))
        elsewhere = mh.Project("elsewhere", tmp=self.p.tmp)               # the same pick, in another project
        dialog_session(elsewhere)
        for name in ("consent.jsonl", "decision.json"):
            elsewhere.write(".ai/state/" + name, self.p.read(".ai/state/" + name))
        others = {"an option added": argv + ("--index", "sqlite"), "an option left out": argv[:-2],
                  "another value": ("memory", "enable", "--author", "dev", "--period", "month"),
                  "another author": ("memory", "enable", "--author", "mallory", "--period", "quarter"),
                  "another order": ("memory", "enable", "--period", "quarter", "--author", "dev")}
        for name, other in others.items():
            with self.subTest(argv=name):
                self.refused(self.p, env, "enable", other)
                self.assertEqual(self.live(self.p, env), ["C1"])
        with self.subTest(argv="another project"):
            self.refused(elsewhere, env, "enable", argv)
            self.assertEqual(self.live(elsewhere, env), ["C1"])
        self.assertEqual([line["type"] for line in self.ledger(self.p)], ["offer", "pick"])
        done = self.p.run(*argv, env=env)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertEqual([line["id"] for line in self.ledger(self.p) if line["type"] == "use"], ["C1"])
        self.assertEqual(self.live(self.p, env), [])
        written = (self.p.read(".ai/policies/memory.json"), self.p.read(".git/hooks/pre-push"))
        self.refused(self.p, env, "enable", argv)
        self.assertEqual((self.p.read(".ai/policies/memory.json"), self.p.read(".git/hooks/pre-push")), written)
        self.assertEqual([line["id"] for line in self.ledger(self.p) if line["type"] == "use"], ["C1"])

    def test_disable_stays_terminal(self):
        """interactive-setup-options R14: only `memory enable` answers to a pick. With a live pick that is exactly the
        command, an agent's disable, cleanup, pack, redact and migrate --move-logs are still the human's: exit 5, the
        pick unspent. No dialog can record such a pick (the label allowlist refuses it), so each is forged; the
        control comes first — the same forgery lets `memory enable` through, which the rest need on anyway."""
        env = dialog_session(self.p)
        enable = ("memory", "enable", "--author", "dev")
        forge_pick(self.p, enable)
        done = self.p.run(*enable, env=env)
        self.assertEqual(done.returncode, 0, (done.stdout, done.stderr))
        self.assertEqual(done.stdout.splitlines()[0], "memory: via dialog (consent C1, decision D1)")
        for what, argv in TERMINAL_ONLY.items():
            with self.subTest(what=what):
                forge_pick(self.p, argv)
                self.assertEqual(self.live(self.p, env), ["C1"])
                self.refused(self.p, env, what, argv)
                self.assertEqual(self.live(self.p, env), ["C1"])
                self.assertEqual([line["type"] for line in self.ledger(self.p)], ["pick"])

    def test_install_idempotent_and_removed(self):
        self.assertIn("pre-push: installed", self.p.ok("memory", "enable", human=True).stdout)
        self.assertTrue(os.access(self.hook(), os.X_OK))
        with open(self.hook(), encoding="utf-8") as fh:
            self.assertIn(mio.HOOK_MARKER, fh.read())
        self.assertIn("pre-push: current", self.p.ok("memory", "enable", human=True).stdout)
        policy = json.loads(self.p.read(".ai/policies/memory.json"))
        self.assertEqual((policy["mode"], policy["period"], policy["cleanup"]), ("packages", "quarter", False))
        out = self.p.ok("memory", "disable", human=True).stdout
        self.assertIn("pre-push: removed", out)
        self.assertFalse(os.path.exists(self.hook()))
        self.assertEqual(json.loads(self.p.read(".ai/policies/memory.json"))["mode"], "files")

    def test_a_foreign_hook_is_kept_and_the_snippet_printed(self):
        os.makedirs(os.path.dirname(self.hook()), exist_ok=True)
        self.p.write(".git/hooks/pre-push", "#!/bin/sh\necho mine\n")
        out = self.p.ok("memory", "enable", human=True).stdout
        self.assertIn("pre-push: foreign", out)
        self.assertIn('rr_in=$(mktemp) && cat > "$rr_in"', out)
        self.assertEqual(self.p.read(".git/hooks/pre-push"), "#!/bin/sh\necho mine\n")
        self.p.ok("memory", "disable", human=True)
        self.assertEqual(self.p.read(".git/hooks/pre-push"), "#!/bin/sh\necho mine\n")

    def test_core_hooks_path_is_respected(self):
        self.p.git("config", "core.hooksPath", ".githooks")
        out = self.p.ok("memory", "enable", human=True).stdout
        self.assertIn("pre-push: hookspath", out)
        self.assertFalse(self.p.exists(".githooks/pre-push"))
        self.assertFalse(os.path.exists(self.hook()))

    def run_shim(self, stdin=""):
        return subprocess.run(["sh", self.hook(), "origin", "url"], input=stdin, capture_output=True, text=True,
                              check=False, cwd=self.p.root,
                              env=mh.clean_env({"HOME": self.p.tmp, "CODEX_HOME": self.p.tmp}))

    def test_the_shim_without_a_validator_warns_and_passes(self):
        self.p.ok("memory", "enable", human=True)
        text = self.p.read(".git/hooks/pre-push").replace(mio.VALIDATOR, "/nonexistent/memory-pre-push.py")
        self.p.write(".git/hooks/pre-push", text.replace(mio.SELF, "/nonexistent/memory_sync.py"))
        done = self.run_shim()
        self.assertEqual(done.returncode, 0)
        self.assertIn("validator not found — this push is not checked", done.stderr)
        status = self.p.ok("memory", "status", env={"HOME": self.p.tmp, "CODEX_HOME": self.p.tmp}).stdout
        self.assertIn("validator missing — pushes are NOT checked", status)

    def test_without_the_hook_file_the_shim_runs_the_module(self):
        """Review M8: a Codex install copies skills/ai-task/ but not every hook."""
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        text = self.p.read(".git/hooks/pre-push").replace(mio.VALIDATOR, "/nonexistent/memory-pre-push.py")
        self.p.write(".git/hooks/pre-push", text)
        base = self.p.commit("memory on")
        self.p.light_task("checked through the module")
        head = self.p.commit("task")
        name = sorted(os.listdir(self.p.path(".ai/memory")))[0]
        lines = self.p.read(".ai/memory/" + name, binary=True).split(b"\n")
        self.p.write(".ai/memory/" + name, b"\n".join(lines[:1] + lines[2:]), mode="wb")
        bad = self.p.commit("drops a record")
        self.assertEqual(self.run_shim("refs/heads/main %s refs/heads/main %s\n" % (head, base)).returncode, 0)
        done = self.run_shim("refs/heads/main %s refs/heads/main %s\n" % (bad, head))
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn(": V2: ", done.stderr)
        self.assertNotIn("not checked", done.stderr)
        self.assertNotIn("validator missing", self.p.ok("memory", "status").stdout)


LOCAL_IGNORE = ".ai/state/\n.ai/local/\n.ai/memory/\n.ai/reports/\n"
NOT_NEEDED = "pre-push: not needed — the record is local (.ai/memory/ is git-ignored)"


class TestLocalRecord(unittest.TestCase):
    """The record is local exactly when .ai/memory/ is git-ignored: no hook, no validator, nothing for git to share;
    `memory enable --share git` is the opt-in and `--share local` the way back (terminal only)."""

    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.write(".gitignore", LOCAL_IGNORE)
        self.p.commit("local record")

    def hook(self):
        return self.p.path(".git/hooks/pre-push")

    def pending(self):
        os.makedirs(self.p.path(".ai/local/memory/outbox"), exist_ok=True)
        self.p.write(".ai/local/memory/outbox/T-x~1.jsonl", "{}\n")

    def push_check(self):
        head = self.p.commit("work")
        stdin = "refs/heads/main %s refs/heads/main %s\n" % (head, ZERO)
        return mh.hook_run(self.p.root, "origin", "url", stdin=stdin)

    def test_enable_installs_no_hook_and_says_the_record_is_local(self):
        done = self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.assertIn("record: local", done.stdout)
        self.assertFalse(os.path.exists(self.hook()))
        self.assertIn(NOT_NEEDED, self.p.ok("memory", "status").stdout)

    def test_a_closed_task_exports_locally_and_git_sees_nothing(self):
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        task, _ = self.p.light_task("first change")
        self.assertTrue(self.p.files_under(".ai/memory"))
        self.assertIn(task, self.p.ok("recall", "--files", "src/widget.py").stdout)
        listed = self.p.git("status", "--porcelain", "--untracked-files=all").stdout
        self.assertNotIn(".ai/memory", listed)
        self.assertNotIn(".ai/reports", listed)

    def test_the_validator_is_silent_with_an_export_pending(self):
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.pending()
        done = self.push_check()
        self.assertEqual((done.returncode, done.stderr), (0, ""))

    def test_share_git_then_share_local(self):
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.pending()
        self.p.ok("memory", "enable", "--author", "dev", "--share", "git", human=True)
        self.assertEqual(self.p.read(".gitignore").splitlines()[-2:], ["!.ai/memory/", "!.ai/reports/"])
        self.assertIn(mio.HOOK_MARKER, self.p.read(".git/hooks/pre-push"))
        done = self.push_check()
        self.assertEqual(done.returncode, 1)
        self.assertIn("V9", done.stderr)
        self.p.ok("memory", "enable", "--author", "dev", "--share", "local", human=True)
        self.assertEqual(self.p.read(".gitignore").splitlines()[-2:], [".ai/memory/", ".ai/reports/"])
        self.assertFalse(os.path.exists(self.hook()))

    def test_fresh_clone_of_a_local_record_says_there_is_none(self):
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        done = self.p.run("memory", "verify", "--fresh-clone")
        self.assertEqual(done.returncode, 2, (done.stdout, done.stderr))
        self.assertIn("the record is local (.ai/memory/ is git-ignored): a fresh clone has none — "
                      "'state.py memory enable --share git' shares it", done.stdout + done.stderr)

    def test_range_and_tree_check_a_tracked_record_whatever_the_checkout_ignores(self):
        """Only the hook form is silent for a local record. A shared project that committed the two ignore lines
        still has tracked packages: --range and --tree (the CI form) validate what the commits carry."""
        self.p.write(".gitignore", ".ai/state/\n.ai/local/\n")
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.p.light_task("first change")
        old = self.p.commit("record shared")
        self.p.write(".gitignore", LOCAL_IGNORE)
        name = ".ai/memory/" + sorted(os.listdir(self.p.path(".ai/memory")))[0]
        lines = self.p.read(name, binary=True).split(b"\n")[:-1]
        lines[2] = lines[2] + b"\r"
        self.p.write(name, b"\n".join(lines) + b"\n", mode="wb")
        new = self.p.commit("local lines, damaged package")
        self.assertFalse(mio.shared(self.p.root))
        for argv in (("--range", "%s..%s" % (old, new)), ("--tree", new)):
            done = mh.hook_run(self.p.root, *argv)
            self.assertEqual(done.returncode, 1, (argv, done.stderr))
            self.assertIn("V1", done.stderr)
        stdin = "refs/heads/main %s refs/heads/main %s\n" % (new, old)
        done = mh.hook_run(self.p.root, "origin", "url", stdin=stdin)
        self.assertEqual((done.returncode, done.stderr), (0, ""))

    def test_a_dialog_pick_cannot_carry_share_git(self):
        """The label allowlist offers only `memory enable [--author S] [--period P] [--index …]`: a label with
        --share never reaches the ledger, so the opt-in stays the human's own terminal."""
        env = dialog_session(self.p)
        label = command_label(self.p, "memory", "enable", "--author", "dev", "--share", "git")
        spec = {"schema": 1, "decisions": [{
            "key": "memory", "header": "Memory", "question": "Share the record through git?",
            "options": [{"kind": "choice", "label": "Off — keep files mode", "value": "off"},
                        {"kind": "command", "label": label}]}]}
        opened = self.p.run("decision", "open", "--kind", "setup", "--spec", "-", stdin=json.dumps(spec), env=env)
        self.assertNotEqual(opened.returncode, 0, opened.stdout)
        done = self.p.run("memory", "enable", "--author", "dev", "--share", "git", env=env)
        self.assertEqual(done.returncode, 5, (done.stdout, done.stderr))
        self.assertNotIn("!.ai/memory/", self.p.read(".gitignore"))


if __name__ == "__main__":
    unittest.main()
