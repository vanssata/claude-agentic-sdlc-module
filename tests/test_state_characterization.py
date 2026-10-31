#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Characterization of skills/ai-task/state.py (small-oop-modules, s1; constitution C1, C2):
what the entry prints, returns and leaves on disk does not move while the file is split
into a package behind an unchanged entry (R1, R5, R6a).

What is recorded, per scripted run: every command's argv, exit code, stdout and stderr,
and at the end of the run every file under the scratch project's .ai/, byte for byte
(state.json, events.jsonl, task.md, decision.json, consent.jsonl, the logs). Five goldens
under tests/fixtures/state/goldens/:

  help.txt     `--help` of the top level and of every (nested) subcommand, enumerated from
               the parser that `import state` builds, not from a list kept here
  light.txt    a light task start to close, with the questions file, refusals and queries
  guarded.txt  a guarded task: a red verify, close refused until one review, an amend
  full.txt     a full task: the STRONG review, the approval gate, a rejection, a second pass
  dialog.txt   the dialog on: an approval opened by close, a commit decision, the human's
               pick recorded, `approve` accepted through the pick (R6a: the label names the
               entry's basename and path, so a module path in a label would be refused)

Every run executes `python3 -I <state.py>` as a subprocess, in a scratch git repository
under a temporary directory with a temporary HOME, never against this repository's .ai/.
The environment is built from nothing: PATH, a temporary HOME, USER, AI_RUNTIME=claude,
TZ=UTC, COLUMNS, git's identity and commit/author date pinned, no agent marker, no
session id, no CLAUDE_CONFIG_DIR / CODEX_HOME. The dialog run adds CLAUDECODE, the session
id and CLAUDE_CONFIG_DIR (the temporary home) on purpose.

Regenerating the goldens (only for a change that is meant to move a recorded field, never
to make a refactoring pass):

  UPDATE_GOLDENS=1 python3 -I tests/run_suite.py tests/test_state_characterization.py

Without the switch a missing or different golden fails, with a unified diff.

The goldens depend on the Python (argparse's help wording) and git the suite runs on.

NORMALISE is exactly what is erased before the compare, in this order, and nothing else
(FC8: the review reads this list before the diff):

  STATE_PY    the path of the entry state.py, abspath and realpath, an exact string replace
              by the token <STATE_PY>. Never a path regex: a label or a refusal that prints
              a module path (rr_state/x.py) stays visible and differs from the golden
  ROOT        the scratch project directory, abspath and realpath, exact, -> <ROOT>
  TMP         the temporary directory that holds the project, HOME and flags, exact,
              -> <TMP>
  PLUGIN_ROOT this checkout (the directory above skills/), exact, -> <PLUGIN_ROOT>; applied
              after STATE_PY, so only a path that is not the entry's is shortened and
              `<PLUGIN_ROOT>/skills/ai-task/rr_state/x.py` still shows the module
  TASK_IDS    each task id this run created (read from .ai/reports/), exact, -> <ID1>,
              <ID2> in order of creation; an id that is not one of these stays visible
  ISO_TS      an ISO-8601 UTC timestamp 2026-10-31T12:00:00Z (optional fraction) -> <TS>
  TREE40      the 40-hex value of a JSON key that ends in `tree` ("tree", "base_tree",
              "e2e_tree", "approved_tree"): the snapshot tree is hashed with the task's own
              files in it, which carry timestamps -> <TREE40>. base_commit stays
  TREE9       a 9-character hex word with at least one digit: the same tree, abbreviated in
              prose and tables (`suite green on 3d57d9554`) -> <TREE9>
  DURATION    the duration after a verify run's exit code, `exit 0 in 3s` -> `exit 0 <DURATION>`

Nothing else is erased: not the exit codes, not the order of lines, not a path outside the
exact ones above, not a number that is not one of these. Add a rule to NORMALISE and to this list
together; test_docstring_lists_every_rule fails otherwise.
"""
import argparse
import difflib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "ai-task")
STATE = os.path.join(SKILL_DIR, "state.py")
GOLDENS = os.path.join(ROOT, "tests", "fixtures", "state", "goldens")
UPDATE = bool(os.environ.get("UPDATE_GOLDENS"))

COMMIT_DATE = "2026-01-02T03:04:05+0000"
SESSION = "sess-golden"
HUMAN = "Rita Human"
DIALOG_ON = json.dumps({"version": 1, "enabled": True, "window_seconds": 120, "stop_blocks_max": 2})
ZERO = ["--declare", "behaviour=0:synthetic", "--declare", "domain=0:synthetic",
        "--declare", "novelty=0:synthetic"]
CLEAN = "FINDINGS\nnone\n"
FINDINGS = "FINDINGS\n[HIGH] H1 the cache key ignores the locale\nin_scope: yes\n[LOW] L1 naming\nVERDICT pass_with_findings\n"

# (name, pattern, replacement). The exact replacements (STATE_PY, ROOT, TMP, TASK_IDS) are in
# Normaliser.apply; this table is the regular-expression part, and no pattern here may match
# a path (test_no_rule_erases_a_module_path).
NORMALISE = (
    ("ISO_TS", re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"), "<TS>"),
    ("TREE40", re.compile(r"(?<=tree\": \")[0-9a-f]{40}(?=\")"), "<TREE40>"),
    ("TREE9", re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{9}\b"), "<TREE9>"),
    ("DURATION", re.compile(r"(?<=\bexit \d )in \d+(?:\.\d+)?s\b"), "<DURATION>"),
)
EXACT_RULES = ("STATE_PY", "ROOT", "TMP", "PLUGIN_ROOT", "TASK_IDS")


class Normaliser:
    """Applies NORMALISE to the text of one run: the exact strings first, longest first."""

    def __init__(self, root, tmp, ids=()):
        self.exact = []
        for token, paths in (("<STATE_PY>", {STATE, os.path.realpath(STATE)}),
                             ("<ROOT>", {root, os.path.realpath(root)}),
                             ("<TMP>", {tmp, os.path.realpath(tmp)}),
                             ("<PLUGIN_ROOT>", {ROOT, os.path.realpath(ROOT)})):
            self.exact += [(path, token) for path in paths]
        self.exact.sort(key=lambda pair: -len(pair[0]))
        self.ids = list(ids)

    def apply(self, text):
        # An exact replace of the project and of the temporary directory would also rewrite
        # the prefix of <ROOT>/..., which is the point: the longest paths go first.
        for path, token in self.exact:
            text = text.replace(path, token)
        for n, task_id in enumerate(self.ids, 1):
            text = text.replace(task_id, "<ID%d>" % n)
        for _name, pattern, replacement in NORMALISE:
            text = pattern.sub(replacement, text)
        return text


def pinned_env(home, extra=None):
    """The whole environment of a state.py process: nothing is inherited but PATH."""
    env = {"PATH": os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin", "HOME": home,
           "USER": "golden-user", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
           "COLUMNS": "80", "LINES": "24", "AI_RUNTIME": "claude",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "golden", "GIT_AUTHOR_EMAIL": "golden@example.invalid",
           "GIT_COMMITTER_NAME": "golden", "GIT_COMMITTER_EMAIL": "golden@example.invalid",
           "GIT_AUTHOR_DATE": COMMIT_DATE, "GIT_COMMITTER_DATE": COMMIT_DATE}
    env.update(extra or {})
    return env


def stamp(at):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at))


class Scratch:
    """A scratch project: .ai/ with a testing.md whose commands read flag files, one code
    file and its test, committed in a git repository of its own (the approach of
    tests/test_ai_task_state.py's Project, kept here so this file stands alone)."""

    def __init__(self, files=None, extra_env=None):
        self.tmp = tempfile.mkdtemp(prefix="state-golden-")
        self.root = os.path.join(self.tmp, "p")
        self.flags = os.path.join(self.tmp, "flags")
        self.home = os.path.join(self.tmp, "home")
        for path in (self.flags, self.home, os.path.join(self.root, ".ai", "policies")):
            os.makedirs(path)
        self.env = pinned_env(self.home, extra_env)
        # The commands name the flag directory through the environment, so the committed
        # testing.md, and with it the initial commit's id, do not depend on the temp path.
        self.env["GOLDEN_FLAGS"] = self.flags
        self.write(".ai/policies/testing.md",
                   "verify_command: sh -c 'test ! -e \"$GOLDEN_FLAGS/red\"' {files}\n"
                   "step_test_command: sh -c 'test ! -e \"$GOLDEN_FLAGS/stepred\"' {files}\n"
                   "e2e_command: sh -c 'test ! -e \"$GOLDEN_FLAGS/e2ered\"'\n")
        base = {"src/widget.py": "x = 1\n", "tests/test_widget.py": "assert True\n"}
        base.update(files or {})
        for rel, text in base.items():
            self.write(rel, text)
        self.git("init", "-q", self.root, cwd=self.tmp)
        self.git("add", "-A")
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        self.log = []

    def git(self, *args, cwd=None):
        subprocess.run(["git"] + list(args), check=True, cwd=cwd or self.root, env=self.env,
                       capture_output=True)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def flag(self, name, on=True):
        path = os.path.join(self.flags, name)
        if on:
            open(path, "w", encoding="utf-8").close()  # pylint: disable=consider-using-with
        elif os.path.exists(path):
            os.remove(path)
        self.log.append("# flag %s %s\n" % (name, "on" if on else "off"))

    def edit(self, rel, text):
        self.write(rel, text)
        self.log.append("# write %s\n" % rel)

    def run(self, *args, stdin="", human=False, env=None, root_option=True):
        """One state.py call, recorded. human sets AI_UNATTENDED (the launcher's route)."""
        full = dict(self.env, **(env or {}))
        if human:
            full["AI_UNATTENDED"] = "1"
        argv = (["--root", self.root] if root_option else []) + list(args)
        done = subprocess.run([sys.executable, "-I", STATE] + argv, input=stdin, capture_output=True,
                              text=True, env=full, cwd=self.root, check=False)
        shown = " ".join(shlex.quote(a) for a in argv)
        extras = "".join(" %s=%s" % (k, v) for k, v in sorted((env or {}).items()))
        self.log.append("$ state.py %s%s%s%s\nexit %d\n--- stdout\n%s--- stderr\n%s" % (
            shown, " <<<stdin" if stdin else "", " [human]" if human else "", extras,
            done.returncode, done.stdout, done.stderr))
        if not self.log[-1].endswith("\n"):
            self.log[-1] += "\n"
        self.log[-1] += "\n"
        return done

    def task_ids(self):
        reports = os.path.join(self.root, ".ai", "reports")
        found = sorted(os.listdir(reports)) if os.path.isdir(reports) else []
        return sorted(found, key=lambda name: (self.created(name), name))

    def created(self, task_id):
        """The journal's first timestamp: the order the tasks were started in."""
        events = os.path.join(self.root, ".ai", "reports", task_id, "events.jsonl")
        try:
            with open(events, encoding="utf-8") as fh:
                return json.loads(fh.readline()).get("ts", 0)
        except (OSError, ValueError, AttributeError):
            return 0

    def files_dump(self):
        """Every file under .ai/, in path order, byte for byte (text)."""
        out = []
        base = os.path.join(self.root, ".ai")
        for here, dirs, names in os.walk(base):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(here, name)
                rel = os.path.relpath(path, self.root)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    body = fh.read()
                out.append("=== %s\n%s%s" % (rel, body, "" if body.endswith("\n") or not body else "\n"))
        return "".join(out)

    def transcript(self, files=True):
        text = "".join(self.log)
        if files:
            text += "\n##### files under .ai/ at the end\n" + self.files_dump()
        return Normaliser(self.root, self.tmp, self.task_ids()).apply(text)

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class DialogScratch(Scratch):
    """The dialog on (R36): dialog.json, a profile whose dialog tool is AskUserQuestion under the
    temporary CLAUDE_CONFIG_DIR, an agent session the pick is bound to. pick() stands in for the
    recorder hook, which writes consent.jsonl."""

    def __init__(self):
        super().__init__({".ai/policies/dialog.json": DIALOG_ON}, {
            "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": SESSION, "CLAUDE_CODE_SESSION_ATTENDED": "1"})
        self.env["CLAUDE_CONFIG_DIR"] = self.home
        self.git("config", "user.name", HUMAN)
        os.makedirs(os.path.join(self.home, "riskrails"))
        with open(os.path.join(self.home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
            json.dump({"plan": "max", "profile": "max", "dialog": {"tool": "AskUserQuestion"}}, fh)
        self.picks = 0

    def decisions(self):
        with open(os.path.join(self.root, ".ai", "state", "decision.json"), encoding="utf-8") as fh:
            return json.load(fh)["open"]

    def label(self, decision_id, option):
        decision = next(d for d in self.decisions() if d["id"] == decision_id)
        return next(o["label"] for o in decision["options"] if o["n"] == option)

    def pick(self, decision_id, option):
        """The ledger line the recorder writes when the human picks `option` of a decision."""
        self.picks += 1
        now = time.time()
        line = {"v": 1, "type": "pick", "id": "C%d" % self.picks, "decision": decision_id, "option": option,
                "order": 1, "label": self.label(decision_id, option), "session": SESSION,
                "tool_use_id": "toolu_C%d" % self.picks, "transcript": "", "runtime": "claude",
                "at": stamp(now), "expires_at": stamp(now + 120)}
        with open(os.path.join(self.root, ".ai", "state", "consent.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
        self.log.append("# the human picks option %d of %s: %s\n" % (option, decision_id, line["label"]))
        return line["label"]


def start(p, *extra, files="src/widget.py", goal="tweak the widget", **kwargs):
    return p.run("start", "--goal", goal, "--workflow", "feature", "--files", files,
                 "--tests", "tests/test_widget.py", *ZERO, *extra, **kwargs)


def script_light(p):
    p.run("status")                                    # no task yet
    p.run("close")
    start(p)
    start(p)                                           # one task at a time
    p.run("status")
    p.run("status", "--json")
    p.run("steps")
    p.run("steps", "--json")
    p.run("weight", "--files", "src/widget.py", "--goal", "tweak the widget")
    p.run("weight", "--files", "src/widget.py", "--json")
    p.run("event", "note", "--detail", "a note for the journal", "--data", '{"k": 1}')
    p.run("event", "no_such_event")
    p.run("ask", "Which cache key?", "--option", "A: per locale", "--option", "B: global",
          "--recommend", "A", "--context", "src/widget.py:1")
    p.run("questions")
    p.run("questions", "--format", "json")
    p.run("questions", "--pending")
    p.run("answer", "Q1=A", "--by", "ivan")
    p.run("answer", "Q9=A", "--by", "ivan")
    p.run("questions", "--sync")
    p.run("handoff", "--print")
    p.run("decision", "show")
    p.run("consent", "audit")
    p.run("approve", "--by", "ivan")                   # no human here
    p.run("step-done", "no-such-step")
    p.edit("src/widget.py", "x = 2\n")
    p.run("verify", "--scope", "step", "--files", "src/widget.py")
    p.flag("red")
    p.run("verify", "--scope", "all")
    p.flag("red", False)
    p.run("verify", "--scope", "all")
    p.run("status")
    p.run("step-done", "task")
    p.run("close")
    p.run("status")
    p.run("profile", "detect", "--json")


def script_guarded(p):
    start(p, "--mode", "guarded", "--by", "test")
    p.edit("src/widget.py", "x = 2\n")
    p.run("close")                                     # nothing verified yet
    p.run("verify", "--scope", "all")
    p.run("close")                                     # one review is missing
    p.run("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
    p.run("close")
    p.run("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-", stdin=FINDINGS)
    p.run("status")
    p.edit("src/other.py", "y = 1\n")
    p.run("close")                                     # a file outside the task
    p.run("start", "--amend", "--files", "+src/other.py", "--why", "a second file")
    p.run("verify", "--scope", "all")
    p.run("close")
    p.run("status")
    p.run("recall", "--files", "src/widget.py")
    p.run("memory", "status")
    p.run("handoff", "--print", "--for", "review")


def script_full(p):
    start(p, "--mode", "full", "--by", "test")
    p.edit("src/widget.py", "x = 2\n")
    p.run("verify", "--scope", "all")
    p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
    p.run("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
    p.run("close")                                     # asks for the approval
    p.run("close")                                     # the open question blocks
    p.run("status")
    p.run("questions")
    p.run("approve", "--by", "ivan")                   # no human here
    p.run("reject", "--by", "ivan", "--why", "not this tree", human=True)
    p.run("close")
    p.run("approve", "--by", "ivan", human=True)
    p.run("approve", "--by", "ivan", human=True)       # already approved
    p.edit("src/widget.py", "x = 3\n")                 # the tree moved after the approval
    p.run("verify", "--scope", "all")
    p.run("close")
    p.run("approve", "--by", "ivan", "--note", "second look", human=True)
    p.run("close")
    p.run("status")
    start(p, "--mode", "full_irreversible", "--by", "test", goal="drop the table")
    p.run("verify", "--scope", "all")
    p.run("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
    p.run("close")
    p.run("approve", "--by", "ivan", human=True)       # --confirm is needed
    p.run("approve", "--by", "ivan", "--confirm", "drop the table", human=True)
    p.run("close", "--abandon")
    p.run("handoff", "--print")


def script_dialog(p):
    p.run("approve", "--by", HUMAN)                    # the dialog on, no task, no pick
    start(p, "--mode", "full", "--by", "test")
    p.edit("src/widget.py", "x = 2\n")
    p.run("verify", "--scope", "all", "--by", HUMAN)
    p.run("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
    p.run("close")                                     # opens the approval decision D1
    p.run("decision", "show")
    p.run("decision", "show", "--json")
    p.run("decision", "open", "--kind", "commit", "--command", "git commit -m 'golden' -- src/widget.py")
    p.run("decision", "show", "--id", "D2")
    p.run("approve", "--by", HUMAN)                    # no pick yet
    label = p.pick("D1", 2)
    argv = shlex.split(label)[2:]                      # python3 <state.py> <argv...>
    p.run(*argv, root_option=False)                    # the pick accepted: the label names this entry
    p.run("approve", "--by", HUMAN)                    # the pick is spent
    p.run("consent", "audit")
    p.run("consent", "audit", "--json")
    p.run("close")
    p.run("decision", "show")
    p.run("decision", "settle", "--id", "D2", "--why", "not now")
    p.run("decision", "fallback", "--id", "D2", "--why", "golden")
    p.run("decision", "show")
    p.run("status")


def enumerate_parsers():
    """(path, ...) of the top-level parser and of every subcommand, nested ones too, from the
    parser `import state` builds: main() is run up to parse_args, which is replaced by a
    capture. Nothing is parsed, nothing runs."""
    sys.path.insert(0, SKILL_DIR)
    try:
        state = importlib.import_module("state")
    finally:
        sys.path.remove(SKILL_DIR)
    seen = []

    def capture(self, *_args, **_kwargs):
        seen.append(self)
        raise SystemExit(0)

    with mock.patch.object(argparse.ArgumentParser, "parse_args", capture):
        try:
            state.main()
        except SystemExit:
            pass
    if not seen:
        raise AssertionError("state.main() built no parser")
    paths = [()]

    def walk(parser, prefix):
        for action in parser._actions:  # pylint: disable=protected-access
            if isinstance(action, argparse._SubParsersAction):  # pylint: disable=protected-access
                for name, child in action.choices.items():
                    paths.append(prefix + (name,))
                    walk(child, prefix + (name,))

    walk(seen[0], ())
    return paths


def script_help():
    """The text of every --help, run as `python3 -I state.py <path> --help`."""
    p = Scratch()
    try:
        for path in enumerate_parsers():
            p.run(*(list(path) + ["--help"]), root_option=False)
        return p.transcript(files=False)
    finally:
        p.close()


RUNS = {"light": (Scratch, script_light), "guarded": (Scratch, script_guarded),
        "full": (Scratch, script_full), "dialog": (DialogScratch, script_dialog)}


def record(name):
    """The normalised transcript of one scripted run, in a scratch project of its own."""
    if name == "help":
        return script_help()
    factory, script = RUNS[name]
    p = factory()
    try:
        script(p)
        return p.transcript()
    finally:
        p.close()


class Characterization(unittest.TestCase):
    maxDiff = None

    def compare(self, name):
        text = record(name)
        path = os.path.join(GOLDENS, name + ".txt")
        if UPDATE:
            os.makedirs(GOLDENS, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return
        self.assertTrue(os.path.exists(path), "no golden %s: record it with UPDATE_GOLDENS=1" % path)
        with open(path, encoding="utf-8") as fh:
            golden = fh.read()
        if text != golden:
            diff = list(difflib.unified_diff(golden.splitlines(), text.splitlines(), "golden/%s.txt" % name,
                                             "now/%s" % name, lineterm="", n=2))
            self.fail("%s differs from its golden (%d diff lines):\n%s" % (name, len(diff), "\n".join(diff[:120])))

    def test_help(self):
        self.compare("help")

    def test_light(self):
        self.compare("light")

    def test_guarded(self):
        self.compare("guarded")

    def test_full(self):
        self.compare("full")

    def test_dialog_on(self):
        self.compare("dialog")


class TestNormalise(unittest.TestCase):
    """FC8: the list is what the docstring says, and it cannot hide a module path."""

    def test_docstring_lists_every_rule(self):
        doc = sys.modules[__name__].__doc__
        for name in [rule[0] for rule in NORMALISE] + list(EXACT_RULES):
            self.assertRegex(doc, r"(?m)^  %s " % name, name)

    def test_the_entry_path_is_an_exact_token(self):
        norm = Normaliser("/tmp/x/p", "/tmp/x")
        module = os.path.join(SKILL_DIR, "rr_state", "cli.py")
        self.assertEqual(norm.apply("python3 %s approve" % STATE), "python3 <STATE_PY> approve")
        self.assertEqual(norm.apply(module), "<PLUGIN_ROOT>/skills/ai-task/rr_state/cli.py")
        self.assertEqual(norm.apply(STATE + ".bak"), "<STATE_PY>.bak")

    def test_no_rule_erases_a_module_path(self):
        for sample in (os.path.join(SKILL_DIR, "rr_state", "cli.py"), "/tmp/x/rr_state/locks.py:123",
                       "python3 /h/skills/ai-task/rr_state/dialog.py --root /p approve --by me"):
            for name, pattern, _replacement in NORMALISE:
                self.assertIsNone(pattern.search(sample), (name, sample))

    def test_task_ids_are_exact(self):
        norm = Normaliser("/tmp/x/p", "/tmp/x", ["T-2026-01-02-0304-aa", "T-2026-01-02-0305-bb"])
        self.assertEqual(norm.apply("T-2026-01-02-0305-bb after T-2026-01-02-0304-aa and T-2026-01-02-0306-cc"),
                         "<ID2> after <ID1> and T-2026-01-02-0306-cc")


if __name__ == "__main__":
    unittest.main()
