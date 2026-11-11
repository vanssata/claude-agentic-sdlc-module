#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Characterization of skills/project-update/update.py (small-oop-modules, WP3 s1; constitution C3):
what the entry prints, returns and leaves on disk does not move while the file is split into
a package behind an unchanged entry (R1, R5). Recorded on the untouched tree, before anything moves.

What is recorded, per run: the argv, the exit code, stdout and stderr; after an `--apply` run
also every file of the project tree (outside .git) with its sha256 and its executable bit.
Four goldens under tests/fixtures/update/goldens/:

  help.txt     `--help`
  plan.txt     for each of the four trees of tests/fixtures/regenerate (fresh, v3.1.0, v3.1.0-edited,
               dual): the dry run, `--check`, `--check --budget`
  apply.txt    `--apply` (with `--confirm-delete` as a human at a terminal, AI_UNATTENDED=1) on
               v3.1.0, v3.1.0-edited and dual, `--apply` alone on fresh; each followed by the tree
               listing and a second dry run and `--check` on the applied tree (current)
  errors.txt   exit 2 (`--budget` without `--check`, `--confirm-delete` without `--apply`, a
               placeholder name, a newer .ai/VERSION, templates not found, neither .ai/ nor
               docs/sdlc/), exit 3 (a target that is a symlink aborts the apply), exit 5
               (`--confirm-delete` under an agent marker: CONFIRM_REFUSED), exit 6 (a kept
               weight.project.json the renderer cannot take: KEPT_UNREADABLE)

Every run executes `python3 -I <update.py> <project> ...` as a subprocess, on a scratch copy
under a temporary directory with a temporary HOME, never against this repository. The trees are
laid out as tests/test_regenerate.py lays them out (the helpers are copied, not imported, so the
suites stay apart) and committed in a git repository of their own, with git's identity and dates
pinned. The environment is built from nothing: PATH, a temporary HOME, USER, TZ=UTC, LC_ALL,
COLUMNS, PYTHONDONTWRITEBYTECODE, git's identity and dates; no agent marker (CLAUDECODE, CODEX_*),
no RISKRAILS_* or CLAUDE_* variable. A run that needs one adds it on purpose and the golden shows
it (AI_UNATTENDED=1 for a human at a terminal, CLAUDECODE=1 for the refusal, RISKRAILS_TEMPLATES
for the missing templates).

Regenerating the goldens (only for a change that is meant to move a recorded field, never to make
a refactoring pass):

  UPDATE_GOLDENS=1 python3 -I tests/run_suite.py tests/test_update_characterization.py

Without the switch a missing or different golden fails, with a unified diff.

The goldens depend on the Python (argparse's help wording) and the git the suite runs on; not on
where argparse breaks a usage line (USAGE).

NORMALISE is exactly what is erased before the compare, in this order, and nothing else
(FC8: the review reads this list before the diff):

  UPDATE_PY   the path of the entry update.py, abspath and realpath, an exact string replace
              by the token <UPDATE_PY>. Never a path regex: a message that prints a module path
              (rr_update/x.py) stays visible and differs from the golden
  ROOT        the scratch project directory, abspath and realpath, exact, -> <ROOT>
  TMP         the temporary directory that holds the project and HOME, exact, -> <TMP>
  PLUGIN_ROOT this checkout (the directory above skills/), exact, -> <PLUGIN_ROOT>; applied
              after UPDATE_PY, so only a path that is not the entry's is shortened and
              `<PLUGIN_ROOT>/skills/project-update/rr_update/x.py` still shows the module
  USAGE       an argparse usage block, `usage: ...` and its indented continuation lines, joined
              into one line with single spaces: 3.12 and 3.13+ wrap it at different words. The
              words and their order stay; the line after a blank or an unindented line
              (`update.py: error: ...`) is not part of it
  RUN_DATE    the UTC date the run started on, and the date it ended on when the run crossed
              midnight, exact (YYYY-MM-DD), -> <DATE>: the directory `project-update-<date>`
              and the dates written into a migration report. Applied after the regular
              expressions; an ISO timestamp therefore keeps its time as <TS> first
  ISO_TS      an ISO-8601 UTC timestamp 2026-10-31T12:00:00Z (optional fraction) -> <TS>;
              applied before RUN_DATE

  REPORT_HASH the sha256 of .ai/reports/project-update-<date>/migration.json, which holds the run's
              `applied_at` and `at` timestamps (proved unstable between two runs): in the listing
              the hash is of the file's text after UPDATE_PY .. ISO_TS .. RUN_DATE, and the mode
              column reads `-~`. Every other file is hashed as it is

Nothing else is erased: not the exit codes, not the order of lines, not a path outside the exact
ones above, not a hash or a mode. Unless a file's bytes carry a run-time value, its sha256 stays
(test_hashes_are_stable_between_two_runs proves it by running every scenario twice). Add a rule to
NORMALISE and to this list together; test_docstring_lists_every_rule fails otherwise.
"""
import difflib
import hashlib
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True  # no __pycache__ beside the files the test imports

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "regenerate")
GOLDENS = os.path.join(ROOT, "tests", "fixtures", "update", "goldens")
AI_TEMPLATES = os.path.join(ROOT, "skills", "ai-init", "templates")
PI_TEMPLATES = os.path.join(ROOT, "skills", "project-init", "templates")
UPDATE_GOLDENS = bool(os.environ.get("UPDATE_GOLDENS"))
TREES = ("fresh", "v3.1.0", "v3.1.0-edited", "dual")
COMMIT_DATE = "2026-01-02T03:04:05+0000"

# (name, pattern, replacement): the regular-expression part of NORMALISE; the exact replacements
# (UPDATE_PY, ROOT, TMP, PLUGIN_ROOT, RUN_DATE) are in Normaliser.apply. No pattern here may
# match a path (test_no_rule_erases_a_module_path).
NORMALISE = (
    ("USAGE", re.compile(r"(?m)^(usage: .*)((?:\n[ ]+\S.*)+)"),
     lambda m: " ".join([m.group(1).rstrip()] + [line.strip() for line in m.group(2).split("\n")[1:]])),
    ("ISO_TS", re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"), "<TS>"),
)
EXACT_RULES = ("UPDATE_PY", "ROOT", "TMP", "PLUGIN_ROOT", "RUN_DATE", "REPORT_HASH")
MIGRATION = re.compile(r"^\.ai/reports/project-update-[^/]+/migration\.json$")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def utc_date():
    return time.strftime("%Y-%m-%d", time.gmtime())


class Normaliser:
    """Applies NORMALISE to the text of one scenario: the exact strings first, longest first."""

    def __init__(self, root, tmp, dates=()):
        self.exact = []
        for token, paths in (("<UPDATE_PY>", {UPDATE, os.path.realpath(UPDATE)}),
                             ("<ROOT>", {root, os.path.realpath(root)}),
                             ("<TMP>", {tmp, os.path.realpath(tmp)}),
                             ("<PLUGIN_ROOT>", {ROOT, os.path.realpath(ROOT)})):
            self.exact += [(path, token) for path in paths]
        self.exact.sort(key=lambda pair: -len(pair[0]))
        self.dates = list(dates)

    def apply(self, text):
        for path, token in self.exact:
            text = text.replace(path, token)
        for _name, pattern, replacement in NORMALISE:
            text = pattern.sub(replacement, text)
        for date in self.dates:
            text = text.replace(date, "<DATE>")
        return text


def pinned_env(home, extra=None):
    """The whole environment of an update.py process: nothing is inherited but PATH."""
    env = {"PATH": os.environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin", "HOME": home,
           "USER": "golden-user", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
           "COLUMNS": "80", "LINES": "24", "PYTHONDONTWRITEBYTECODE": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "golden", "GIT_AUTHOR_EMAIL": "golden@example.invalid",
           "GIT_COMMITTER_NAME": "golden", "GIT_COMMITTER_EMAIL": "golden@example.invalid",
           "GIT_AUTHOR_DATE": COMMIT_DATE, "GIT_COMMITTER_DATE": COMMIT_DATE}
    env.update(extra or {})
    return env


class Scratch:
    """One project under test, in a temporary directory with a temporary HOME, and the log of the runs
    made on it (the trees are laid out as tests/test_regenerate.py's Tree does)."""

    def __init__(self, kind, weight):
        self.weight = weight
        self.started_on = utc_date()  # update.py writes today's UTC date (RUN_DATE)
        self.tmp = tempfile.mkdtemp(prefix="update-golden-")
        self.home = os.path.join(self.tmp, "home")
        self.root = os.path.join(self.tmp, "p")
        os.makedirs(self.home)
        os.makedirs(self.root)
        self.env = pinned_env(self.home)
        getattr(self, "build_" + kind.replace(".", "_").replace("-", "_"))()
        self.git("init", "-q", self.root)
        self.git("-C", self.root, "add", "-A")
        self.git("-C", self.root, "commit", "-qm", "start", "--allow-empty")
        self.log = []

    # ---- the four trees
    def lay(self, name):
        shutil.copytree(os.path.join(FIXTURES, name), self.root, dirs_exist_ok=True)

    def build_fresh(self):
        shutil.copytree(os.path.join(AI_TEMPLATES, ".ai"), os.path.join(self.root, ".ai"))
        os.remove(self.path(".ai", "policies", "weight.json"))  # the plugin's table is read from the plugin
        self.lay("fresh")
        minimal = raw(os.path.join(AI_TEMPLATES, "CLAUDE.minimal.md")).replace(b"{{PROJECT}}", b"p")
        put(self.path("CLAUDE.md"), minimal.rstrip(b"\n") + b"\n\n" + raw(os.path.join(AI_TEMPLATES, "CLAUDE.block.md"))
            + b"\nOur text after the block.\n")
        put(self.path(".claude", "memory", "README.md"), raw(os.path.join(PI_TEMPLATES, "memory-README.md")))
        put(self.path("docs", "sdlc", "README.md"), raw(os.path.join(PI_TEMPLATES, "sdlc-README.md")))
        put(self.path(".gitignore"), raw(os.path.join(AI_TEMPLATES, "gitignore.snippet"))
            + raw(os.path.join(PI_TEMPLATES, "gitignore.snippet")))
        put(self.path(".ai", "policies", "weight.md"), self.weight.mirror(self.weight.load_policy(self.root)[0]).encode("utf-8"))

    def build_v3_1_0(self):
        self.lay("v3.1.0")

    def build_v3_1_0_edited(self):
        self.lay("v3.1.0")
        self.lay("v3.1.0-edited")

    def build_dual(self):
        self.lay("v3.1.0")
        self.lay("dual")

    # ---- helpers
    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def git(self, *args):
        subprocess.run(["git"] + list(args), check=True, env=self.env, capture_output=True, cwd=self.tmp)

    def run(self, *args, env=None, drop=()):
        """One update.py call on this project, recorded. `env` adds variables, `drop` removes some."""
        full = dict(self.env, **(env or {}))
        for name in drop:
            full.pop(name, None)
        argv = [self.root] + list(args)
        done = subprocess.run([sys.executable, "-I", UPDATE] + argv, env=full, cwd=self.tmp, capture_output=True,
                              text=True, check=False)
        shown = " ".join(shlex.quote(a) for a in argv)
        extras = "".join(" %s=%s" % (k, v) for k, v in sorted((env or {}).items()))
        self.log.append("$ update.py %s%s\nexit %d\n--- stdout\n%s--- stderr\n%s" % (
            shown, extras, done.returncode, done.stdout, done.stderr))
        if not self.log[-1].endswith("\n"):
            self.log[-1] += "\n"
        self.log[-1] += "\n"
        return done

    def human_apply(self):
        """--apply --confirm-delete, as a human at a terminal (AI_UNATTENDED stands in for one)."""
        return self.run("--apply", "--confirm-delete", "tester", env={"AI_UNATTENDED": "1"})

    def listing(self):
        """Every file outside .git: path, sha256, the executable bit; a symlink by its target."""
        out = ["##### files of the project tree after the run\n"]
        for here, dirs, names in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for name in sorted(names):
                full = os.path.join(here, name)
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                if os.path.islink(full):
                    out.append("%s  link -> %s\n" % (rel, os.readlink(full)))
                    continue
                mode = "x" if os.stat(full).st_mode & 0o111 else "-"
                data = raw(full)
                if MIGRATION.search(rel):  # REPORT_HASH: the hash of the report as NORMALISE leaves it
                    data = self.normaliser().apply(data.decode("utf-8")).encode("utf-8")
                    mode += "~"
                out.append("%s  %s %s\n" % (hashlib.sha256(data).hexdigest(), mode, rel))
        self.log.append("".join(out) + "\n")

    def normaliser(self):
        dates = sorted({self.started_on, utc_date()})  # two when the run crossed midnight
        return Normaliser(self.root, self.tmp, dates)

    def transcript(self):
        return self.normaliser().apply("".join(self.log))

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Recorder:
    """Builds the text of one golden from the scenarios that belong to it."""

    def __init__(self, weight):
        self.weight = weight
        self.parts = []

    def scenario(self, title, kind, steps):
        scratch = Scratch(kind, self.weight)
        try:
            steps(scratch)
            self.parts.append("########## %s\n%s" % (title, scratch.transcript()))
        finally:
            scratch.close()

    def text(self):
        return "".join(self.parts)


def record_help(weight):
    rec = Recorder(weight)
    rec.scenario("--help", "v3.1.0", lambda p: p.run("--help"))
    return rec.text()


def record_plan(weight):
    rec = Recorder(weight)
    for kind in TREES:
        def steps(p):
            p.run()
            p.run("--check")
            p.run("--check", "--budget")
        rec.scenario("tree %s: dry run, --check, --check --budget" % kind, kind, steps)
    return rec.text()


def record_apply(weight):
    rec = Recorder(weight)
    for kind in ("v3.1.0", "v3.1.0-edited", "dual", "fresh"):
        def steps(p, kind=kind):
            if kind == "fresh":
                p.run("--apply")
            else:
                p.human_apply()
            p.listing()
            p.run()
            p.run("--check")
        how = "--apply" if kind == "fresh" else "--apply --confirm-delete"
        rec.scenario("tree %s: %s, the tree, a second dry run, --check" % (kind, how), kind, steps)
    return rec.text()


def record_errors(weight):
    rec = Recorder(weight)

    def usage(p):
        p.run("--budget")
        p.run("--confirm-delete", "tester")
        p.run("--apply", "--confirm-delete", "")
        p.run("--apply", "--confirm-delete", "<your name>")
        p.run("--confirm-cleanup", "tester")
    rec.scenario("exit 2: usage errors", "v3.1.0", usage)

    def newer(p):
        newest = int(raw(os.path.join(AI_TEMPLATES, ".ai", "VERSION")).decode().strip()) + 1
        put(p.path(".ai", "VERSION"), "%d\n" % newest)
        p.run()
        p.run("--check")
        p.run("--apply")
    rec.scenario("exit 2: a newer .ai/VERSION than the plugin", "v3.1.0", newer)

    def unusable(p):
        put(p.path(".ai", "VERSION"), "abc\n")
        p.run("--check")
    rec.scenario("exit 2: an unusable .ai/VERSION", "v3.1.0", unusable)

    def no_templates(p):
        p.run(env={"RISKRAILS_TEMPLATES": os.path.join(p.tmp, "no-templates")})
    rec.scenario("exit 2: templates not found", "v3.1.0", no_templates)

    def no_layer(p):
        shutil.rmtree(p.path(".ai"))
        shutil.rmtree(p.path("docs"), ignore_errors=True)
        p.run()
    rec.scenario("exit 2: neither .ai/ nor docs/sdlc/", "v3.1.0", no_layer)

    def symlinked(p):
        target = p.path(".ai", "policies", "coding.md")
        os.remove(target)
        os.symlink(os.path.join(p.tmp, "elsewhere"), target)
        p.run("--apply")
        p.listing()
    rec.scenario("exit 3: a symlinked target aborts the apply", "fresh", symlinked)

    def agent(p):
        p.run("--apply", "--confirm-delete", "tester", env={"CLAUDECODE": "1"})
        p.run("--apply", "--confirm-cleanup", "tester", env={"CLAUDECODE": "1", "CODEX_HOME": p.home})
        p.run("--apply", "--confirm-delete", "tester")
    rec.scenario("exit 5: --confirm-* without a human (an agent marker, and no terminal at all)", "v3.1.0", agent)

    def unreadable(p):
        put(p.path(".ai", "policies", "weight.project.json"), '{"version": 1, "modes": 3}\n')
        p.run("--apply")
        p.run()
        p.run("--check")
        p.listing()
    rec.scenario("exit 6: a kept file the renderer cannot take", "fresh", unreadable)
    return rec.text()


GOLDEN_SOURCES = (("help", record_help), ("plan", record_plan), ("apply", record_apply), ("errors", record_errors))


class TestGoldens(unittest.TestCase):
    weight = None

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))  # weight.py imports its sibling lazily
        cls.weight = load("weight_under_golden", os.path.join(ROOT, "skills", "ai-task", "weight.py"))

    def compare(self, name, text):
        path = os.path.join(GOLDENS, name + ".txt")
        if UPDATE_GOLDENS:
            os.makedirs(GOLDENS, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return
        self.assertTrue(os.path.exists(path), "%s has no golden; UPDATE_GOLDENS=1 writes it" % name)
        with open(path, encoding="utf-8") as fh:
            golden = fh.read()
        if text != golden:
            diff = list(difflib.unified_diff(golden.splitlines(), text.splitlines(), "golden/%s.txt" % name,
                                             "now/%s" % name, lineterm="", n=2))
            self.fail("%s differs from its golden (%d diff lines):\n%s" % (name, len(diff), "\n".join(diff[:120])))

    def test_help(self):
        self.compare("help", record_help(self.weight))

    def test_plan(self):
        self.compare("plan", record_plan(self.weight))

    def test_apply(self):
        self.compare("apply", record_apply(self.weight))

    def test_errors(self):
        self.compare("errors", record_errors(self.weight))

    def test_hashes_are_stable_between_two_runs(self):
        """No field of the listing carries a run-time value: two independent runs give one text."""
        if UPDATE_GOLDENS:
            self.skipTest("regenerating")
        self.assertEqual(record_apply(self.weight), record_apply(self.weight))


class TestNormalise(unittest.TestCase):
    """FC8: the list is what the docstring says, and it cannot hide a module path."""

    def test_docstring_lists_every_rule(self):
        doc = sys.modules[__name__].__doc__
        for name in [rule[0] for rule in NORMALISE] + list(EXACT_RULES):
            self.assertRegex(doc, r"(?m)^  %s " % name, name)

    def test_the_entry_path_is_an_exact_token(self):
        norm = Normaliser("/tmp/x/p", "/tmp/x")
        module = os.path.join(ROOT, "skills", "project-update", "rr_update", "cli.py")
        self.assertEqual(norm.apply("python3 %s --apply" % UPDATE), "python3 <UPDATE_PY> --apply")
        self.assertEqual(norm.apply(module), "<PLUGIN_ROOT>/skills/project-update/rr_update/cli.py")
        self.assertEqual(norm.apply(UPDATE + ".bak"), "<UPDATE_PY>.bak")

    def test_no_rule_erases_a_module_path(self):
        for sample in (os.path.join(ROOT, "skills", "project-update", "rr_update", "cli.py"),
                       "/tmp/x/rr_update/plan.py:123", "python3 /h/skills/project-update/rr_update/apply.py /p"):
            for name, pattern, _replacement in NORMALISE:
                self.assertIsNone(pattern.search(sample), (name, sample))

    def test_run_dates_are_exact(self):
        norm = Normaliser("/tmp/x/p", "/tmp/x", dates=["2026-10-31", "2026-11-01"])
        self.assertEqual(norm.apply("project-update-2026-10-31 · 2026-11-01 · 2026-01-02 · 2026-10-31T12:00:00Z"),
                         "project-update-<DATE> · <DATE> · 2026-01-02 · <TS>")

    def test_usage_wraps_alike_on_every_python(self):
        """3.12 and 3.13+ break an argparse usage line at different words; joined, they are one."""
        norm = Normaliser("/tmp/x/p", "/tmp/x")
        py312 = "usage: update.py [-h] [--apply] [--check]\n                 [--budget] [root]\n\nnext\n"
        py314 = "usage: update.py [-h] [--apply] [--check] [--budget]\n                 [root]\n\nnext\n"
        joined = "usage: update.py [-h] [--apply] [--check] [--budget] [root]\n\nnext\n"
        self.assertEqual(norm.apply(py312), joined)
        self.assertEqual(norm.apply(py314), joined)
        self.assertEqual(norm.apply("usage: a b\nupdate.py: error: x\n"), "usage: a b\nupdate.py: error: x\n")


if __name__ == "__main__":
    unittest.main()
