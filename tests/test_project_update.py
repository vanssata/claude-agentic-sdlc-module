#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
project-update: the parts of --update that stay when it regenerates its own files
(tests/test_regenerate.py holds the regeneration itself, the gate, the split and the
refusal): the CLI, a project of each runtime, the rules renderer, the [cleanup] rows,
the budget check, the hints, the weight mirror, and the readers of deeply nested JSON.

Every project is today's scaffold in a temp directory with a pinned HOME.
"""
import glob
import hashlib
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
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
SCAFFOLD = os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]

TWIN_OF = "test-project-update.sh"

HISTORY = os.path.join(ROOT, "skills", "project-update", "history")
HOOK_SCAFFOLD = os.path.join(ROOT, "hooks", "project-scaffold.sh")
TEMPLATES = os.path.join(ROOT, "skills", "ai-init", "templates")
BLOCK = os.path.join(TEMPLATES, "AGENTS.block.md")
NOMARK = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI", "CODEX_SANDBOX",
          "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION", "AI_UNATTENDED")
# R13 reads a shell `pass` up to its first inner quote, and `pass "$3"` in a helper by its
# parameter name: these are the cases it records for check_refused's rules and the journal count.


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Project:
    """Today's scaffold of one runtime, committed, for the cases that need a project on disk."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.home = os.path.join(self.tmp.name, "home")
        self.root = os.path.join(self.tmp.name, "p")
        os.makedirs(self.home)
        os.makedirs(self.root)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_CONFIG_DIR") and not k.startswith("RISKRAILS_")}
        self.env.update(HOME=self.home, RISKRAILS_SHARED=os.path.join(ROOT, "ai"))
        subprocess.run(["bash", SCAFFOLD, self.root, "--runtime", "claude"], env=self.env, check=True,
                       capture_output=True)
        settle(self.root)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(GIT + ["-C", self.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.root, "commit", "-qm", "scaffold"], check=True)

    def path(self, *parts):
        return os.path.join(self.root, ".ai", *parts)

    def update(self, *args):
        return subprocess.run([sys.executable, "-I", UPDATE, self.root] + list(args), env=self.env,
                              capture_output=True, text=True, check=False)

    def read(self, *parts):
        with open(self.path(*parts), "rb") as fh:
            return fh.read()

    def close(self):
        self.tmp.cleanup()


def settle(root):
    """The scaffold copies the plugin's own weight.json into a project and leaves weight.md rendered from
    it; the update offers that copy for removal (the table is read from the plugin) and renders the mirror
    from the table the project reads. A project that is to read "up to date" has been through both."""
    try:
        os.remove(os.path.join(root, ".ai", "policies", "weight.json"))
    except OSError:
        pass
    subprocess.run([sys.executable, "-I", STATE, "--root", root, "weight", "--mirror"], capture_output=True, check=False)


def text_of(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, content, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
        fh.write(content)


def put_json(path, doc):
    """As jq writes it: two-space indent, non-ASCII as is, a final newline."""
    put(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def sha256(path):
    return hashlib.sha256(raw(path)).hexdigest()


def grep(pattern, out):
    """`grep -c`: the lines of out that match."""
    return sum(1 for line in out.splitlines() if re.search(pattern, line))


def has(pattern, out):
    return grep(pattern, out) > 0


def tree_sum(d):
    """Path and content of every file outside .git."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not (top == d and x == ".git")]
        out += [(os.path.relpath(os.path.join(top, f), d), raw(os.path.join(top, f)))
                for f in files if os.path.isfile(os.path.join(top, f))]
    return sorted(out)


def mirror_hashes(md):
    return re.findall(r"sha256:([0-9a-f]*)", text_of(md))


def insert_line(content, n, line, after):
    """sed 'Na line' (after) or 'Ni line' (before)."""
    rows = content.splitlines(keepends=True)
    at = n if after else n - 1
    return "".join(rows[:at] + [line + "\n"] + rows[at:]) if len(rows) >= n else content


def only(pattern):
    """The one path a glob names; a name that does not exist when it names none or several."""
    paths = glob.glob(pattern)
    return paths[0] if len(paths) == 1 else os.path.join(os.path.dirname(pattern), "<%d matches>" % len(paths))





class TestCli(unittest.TestCase):
    """R1: the flags of the retired adopt and of the merge are gone; argparse exits 2 on each."""

    def test_removed_flags(self):
        p = Project()
        self.addCleanup(p.close)
        for flag in (["--adopt"], ["--mode", "migrate"], ["--tool", "cursor"], ["--split-request"], ["--split", "proposal"],
                     ["--diff"], ["--cleanup"], ["--adopt", "--apply"]):
            with self.subTest(flag=flag):
                done = p.update(*flag)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("unrecognized arguments", done.stderr)
                self.assertEqual(done.stdout, "")

    def test_the_rest_of_the_cli_is_unchanged(self):
        p = Project()
        self.addCleanup(p.close)
        self.assertEqual(p.update().returncode, 0)
        self.assertEqual(p.update("--check").returncode, 0)
        self.assertEqual(p.update("--budget").returncode, 2, "--budget needs --check")
        self.assertEqual(p.update("--confirm-delete", "tester").returncode, 2, "--confirm-delete needs --apply")

    def test_exit_codes_in_the_docstring(self):
        import importlib.util  # pylint: disable=import-outside-toplevel
        spec = importlib.util.spec_from_file_location("update_doc", UPDATE)
        doc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doc)
        for code in ("CONFIRM_REFUSED", "KEPT_UNREADABLE"):
            self.assertIn(code, doc.__doc__)
        self.assertNotIn("  4  ", doc.__doc__, "exit 4 is retired and never emitted")


class TestProjectUpdate(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """project-update on projects scaffolded from today's templates."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDownClass ends it
        cls.t = cls.tmp.name
        os.makedirs(os.path.join(cls.t, "home"))
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_HOME", "AI_UNATTENDED", "RISKRAILS_TEMPLATES", "CLAUDE_ROUTING_TEMPLATES",
                                "CLAUDE_CONFIG_DIR") and not k.startswith("RISKRAILS_")}
        cls.env.update(HOME=os.path.join(cls.t, "home"), RISKRAILS_SHARED=os.path.join(ROOT, "ai"))
        # The shared keys come from the ai/ tree itself, not from a list.
        cls.shared_keys = sorted("ai-init/.ai/" + os.path.relpath(os.path.join(d, f), os.path.join(ROOT, "ai"))
                                 for d, _, files in os.walk(os.path.join(ROOT, "ai")) for f in files)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- helpers ------------------------------------------------------------

    def run_(self, args, merge=False, unset=(), **extra):
        env = {k: v for k, v in self.env.items() if k not in unset}
        env.update(extra)
        done = subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, text=True, check=False)
        return done.returncode, done.stdout

    def upd(self, d, *args, merge=False, **extra):
        return self.run_([sys.executable, "-I", UPDATE, d] + list(args), merge=merge, **extra)

    def pty(self, args, unset=(), **extra):
        """The command with a terminal on stdin (util-linux script), stdout and stderr merged,
        \\r stripped; the exit status is the command's. SHELL is pinned because script -c runs it."""
        rc, out = self.run_(["script", "-qec", shlex.join(args), "/dev/null"], unset=unset, SHELL="/bin/bash",
                            **extra)
        return rc, out.replace("\r", "")

    def has_pty(self):
        try:
            return self.pty([sys.executable, "-c", "import os; print(os.isatty(0))"])[1].strip() == "True"
        except OSError:
            return False

    def dir(self, name):
        path = os.path.join(self.t, name)
        os.makedirs(path, exist_ok=True)
        return path

    def current_project(self, name, *args):
        d = self.dir(name)
        self.run_(["bash", HOOK_SCAFFOLD, d] + list(args))
        self.run_(["bash", SCAFFOLD, d] + list(args))
        settle(d)
        return d

    def agents_project(self, name, agents):
        d = self.dir(name)
        os.makedirs(os.path.join(d, ".codex"), exist_ok=True)
        self.current_project(name)
        subprocess.run(["git", "-C", d, "init", "-q"], env=self.env, check=True)
        put(os.path.join(d, "AGENTS.md"), agents)
        return d

    # -- the cases ----------------------------------------------------------

    def test_history_covers_every_template(self):
        """the shipped history covers every current template"""
        index = read_json(os.path.join(HISTORY, "index.json"))
        stale, shared = [], set()
        # The shared tree ai/ is recorded under the ai-init/.ai/ keys it shipped under,
        # by hash only: a shared copy is classified, never merged, so it needs no blob.
        for name, base in (("ai-init", TEMPLATES),
                           ("project-init", os.path.join(ROOT, "skills", "project-init", "templates")),
                           ("ai-init/.ai", os.path.join(ROOT, "ai"))):
            for d, _, files in os.walk(base):
                for f in files:
                    p = os.path.join(d, f)
                    key = "%s/%s" % (name, os.path.relpath(p, base))
                    if name == "ai-init/.ai":
                        shared.add(key)
                    h = sha256(p)
                    if h not in index.get(key, []) or (name != "ai-init/.ai" and
                                                       not os.path.exists(os.path.join(HISTORY, "blobs", h))):
                        stale.append(key)
        owned = {h for k, v in index.items() if k not in shared for h in v}
        stale += ["blob only a shared key references: " + b
                  for b in sorted(set(os.listdir(os.path.join(HISTORY, "blobs"))) - owned)]
        self.assertEqual(stale, [], "every template version is in history/ (else run tools/build-template-history.py)")
        self.assertGreaterEqual(len(self.shared_keys), 25, "the shared keys are read from ai/")

    def test_codex_project(self):
        """a Codex project gets its AGENTS.md block and .codex/ layer, and no stray CLAUDE.md"""
        p4 = self.current_project("proj4", "--runtime", "codex")
        self.assertTrue(os.path.lexists(os.path.join(p4, "AGENTS.md"))
                        and not os.path.lexists(os.path.join(p4, "CLAUDE.md")), "the fixture is a Codex-only project")
        put(os.path.join(p4, "AGENTS.md"), "\n# my codex notes\nkeep me\n", "a")
        os.remove(os.path.join(p4, ".codex", "memory", "README.md"))
        _, out = self.upd(p4, "--apply", merge=True)
        agents = text_of(os.path.join(p4, "AGENTS.md"))
        self.assertTrue("keep me" in agents and "riskrails:start" in agents,
                        "the AGENTS.md block is managed and the rest of the file kept\n" + out)
        self.assertEqual(grep("riskrails:start", agents), 1, "one AGENTS.md block remains")
        self.assertTrue(not os.path.lexists(os.path.join(p4, "CLAUDE.md"))
                        and not os.path.isdir(os.path.join(p4, ".claude")), "no Claude layer is added to a Codex project")
        self.assertTrue(os.path.isfile(os.path.join(p4, ".codex", "memory", "README.md")),
                        "a missing .codex/memory/README.md is recreated")
        self.assertTrue(os.path.isfile(os.path.join(p4, ".codex", "config.toml")), ".codex/config.toml is left in place")
        self.assertIn(".codex/memory/local/", text_of(os.path.join(p4, ".gitignore")),
                      "the Codex ignore entry is appended")
        self.upd(p4, "--apply")
        _, out = self.upd(p4)
        self.assertTrue(has("^0 automatic", out), "a second run on the Codex project is a no-op\n" + out)

    def test_dual_and_four_runtime_projects(self):
        """a dual-runtime project keeps both instruction files in step"""
        p5 = self.current_project("proj5", "--runtime", "both")
        self.upd(p5, "--apply")
        self.assertTrue(".ai/state/handoff.md" in text_of(os.path.join(p5, "CLAUDE.md"))
                        and "riskrails:start" in text_of(os.path.join(p5, "AGENTS.md")),
                        "both blocks are brought up to date over the one .ai/ tree")

        # a project that also declares Gemini and Junie gets their blocks too
        p6 = self.current_project("proj6", "--runtime", "claude,codex,gemini,junie")
        for f in ("GEMINI.md", ".junie/guidelines.md"):
            with self.subTest(Template("$f carries the managed block").substitute(f=f)):
                self.assertIn("riskrails:start", text_of(os.path.join(p6, f)))
        self.assertIn(".ai/policies/safety.md", text_of(os.path.join(p6, "GEMINI.md")),
                      "the Gemini block routes to the policies like every other runtime")
        self.upd(p6, "--apply")
        _, out = self.upd(p6)
        self.assertTrue(has("^0 automatic", out), "a four-runtime project is idempotent\n" + out)
        # an edited block is the user's, in a fourth runtime exactly as in the first
        put(os.path.join(p6, "GEMINI.md"), "\n<!-- riskrails:start -->\nmy own text\n<!-- riskrails:end -->\n")
        _, out = self.upd(p6)
        self.assertIn("regenerate? GEMINI.md", out, "an edited Gemini block waits for a human, never overwritten")
        self.assertIn("my own text", text_of(os.path.join(p6, "GEMINI.md")))
        self.upd(p6, "--apply")
        self.assertIn("my own text", text_of(os.path.join(p6, "GEMINI.md")), "an unconfirmed apply leaves it")

    def test_up_to_date_project_and_non_project(self):
        """an up-to-date project and a non-project"""
        p3 = self.current_project("proj3")
        _, out = self.upd(p3)
        self.assertTrue(has("^0 automatic", out), "a freshly scaffolded project is up to date\n" + out)
        self.assertEqual(self.upd(self.dir("empty"))[0], 2, "a repository without .ai/ or docs/sdlc/ is refused")

    def test_sdlc_only_project(self):
        """a docs/sdlc-only project has no schema and touches nothing under .ai/"""
        s6 = self.dir("sdlconly")
        self.run_(["bash", HOOK_SCAFFOLD, s6])
        self.assertFalse(os.path.exists(os.path.join(s6, ".ai")))
        _, out = self.upd(s6, "--apply", merge=True)
        self.assertFalse(has("schema|VERSION", out), "no schema for a docs/sdlc-only project\n" + out)
        self.assertFalse(os.path.exists(os.path.join(s6, ".ai")), "and no .ai/ is made for it")
        self.assertEqual(self.upd(s6, "--check")[0], 0)

    def test_unusable_version_stops_the_run(self):
        """an unusable .ai/VERSION stops the run, with a reason, having written nothing"""
        s1 = self.current_project("schemabad")
        newer = int(text_of(os.path.join(TEMPLATES, ".ai", "VERSION"))) + 1
        for bad in (str(newer), "abc", ""):
            put(os.path.join(s1, ".ai", "VERSION"), bad + "\n")
            snap = tree_sum(s1)
            rc, out = self.upd(s1, "--apply", merge=True)
            crc, chk = self.upd(s1, "--check")
            with self.subTest(Template("VERSION '$bad' exits 2 and --check says why").substitute(bad=bad)):
                self.assertTrue(rc == 2 and crc == 2 and chk.strip() and snap == tree_sum(s1), out + " / " + chk)

    def test_symlinked_target_aborts_the_apply(self):
        """a target that is not a regular file aborts the apply"""
        s4 = self.current_project("schemalink")
        testing = os.path.join(s4, ".ai", "policies", "testing.md")
        os.remove(testing)
        os.symlink(os.path.join(self.t, "elsewhere"), testing)
        rc, out = self.upd(s4, "--apply", merge=True)
        self.assertTrue(rc == 3 and not os.path.lexists(os.path.join(self.t, "elsewhere")),
                        "a symlinked target exits 3 and is not written through\n" + out)
        self.assertIn("nothing after it was written; run the dry run again", out, "and the abort says what to do")

    def test_rendered_rules(self):  # pylint: disable=too-many-statements
        """a rendered rule whose source is gone waits for a human, like any deletion (R9)"""
        rd = self.current_project("rules-gate", "--runtime", "claude")
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "instructions", "rules-project", ".ai"),
                        os.path.join(rd, ".ai"), dirs_exist_ok=True)
        os.makedirs(os.path.join(rd, "src", "Payment"))
        os.makedirs(os.path.join(rd, "tests", "Payment"))
        self.assertEqual(self.upd(rd, "--apply")[0], 0, "the rules could not be rendered")
        payment_md = os.path.join(rd, "src", "Payment", "CLAUDE.md")
        put(payment_md, "\n# mine\nkeep me\n", "a")
        os.remove(os.path.join(rd, ".ai", "rules", "payment.md"))
        _, out = self.upd(rd, merge=True)
        self.assertTrue(has(r"delete\? *.claude/rules/payment.md", out),
                        "the path-scoped copy is proposed, not deleted\n" + out)
        self.assertIn("needs --apply --confirm-delete NAME", out, "and says how a human confirms it")
        self.upd(rd, "--apply")
        rule = os.path.join(rd, ".claude", "rules", "payment.md")
        self.assertTrue(os.path.isfile(rule), "an --apply without the confirmation leaves it alone")
        self.assertIn("keep me", text_of(payment_md), "the human's text around a removed block survives")
        self.assertNotIn("riskrails:rule:payment", text_of(payment_md),
                         "the stale block was taken out without a gate: it is ours")
        self.upd(rd, "--apply", "--confirm-delete", "Ivan", AI_UNATTENDED="1")
        self.assertFalse(os.path.isfile(rule), "the confirmed deletion is performed")
        self.assertTrue(os.path.isfile(os.path.join(rd, ".ai", "reports", "project-update-" + time.strftime(
            "%Y-%m-%d", time.gmtime()), "original", ".claude", "rules", "payment.md")), "its original is kept")
        _, out = self.upd(rd, merge=True)
        self.assertTrue(has("^0 automatic", out), "and the project is then up to date\n" + out)

        # a nested worktree or repository is not this project's: its rule blocks are never touched
        rn = os.path.join(self.t, "rules-nested")
        shutil.copytree(rd, rn, symlinks=True)
        stale = "# theirs\n<!-- riskrails:rule:gone:start -->\nold\n<!-- riskrails:rule:gone:end -->\n"
        for sub in (".claude/worktrees/wt", "vendor-repo"):
            put(os.path.join(rn, sub, "src", "Payment", "CLAUDE.md"), stale)
        put(os.path.join(rn, ".claude", "worktrees", "wt", ".git"),
            "gitdir: /elsewhere/.git/worktrees/wt\n")                      # a worktree: .git is a file
        os.makedirs(os.path.join(rn, "vendor-repo", ".git"))                 # a repository: .git is a dir
        _, out = self.upd(rn, merge=True)
        self.assertFalse(has("worktrees/wt|vendor-repo", out), "the dry run names neither nested tree\n" + out)
        rc, out = self.upd(rn, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0: a nested tree's blocks are not pending\n" + out)
        self.upd(rn, "--apply")
        for sub in (".claude/worktrees/wt", "vendor-repo"):
            with self.subTest(Template("--apply leaves $sub/src/Payment/CLAUDE.md byte-identical").substitute(sub=sub)):
                self.assertEqual(text_of(os.path.join(rn, sub, "src", "Payment", "CLAUDE.md")), stale)

        # a rule naming a nested tree is not written there: the writer covers what the take-back walks (M1)
        rw = os.path.join(self.t, "rules-nested-writer")
        shutil.copytree(rd, rw, symlinks=True)
        put(os.path.join(rw, "libs", "sub", ".git"), "gitdir: ../../.git/modules/libs/sub\n")   # a submodule
        put(os.path.join(rw, ".claude", "worktrees", "wt", ".git"), "gitdir: /elsewhere/.git/worktrees/wt\n")
        os.makedirs(os.path.join(rw, ".claude", "worktrees", "wt", "src"))
        put(os.path.join(rw, ".ai", "rules", "sub.md"),
            "---\ndirs: [libs, libs/sub, .claude/worktrees/wt/src]\n---\n# Sub rules\n- new text\n")
        stale = "# theirs\n<!-- riskrails:rule:sub:start -->\nold\n<!-- riskrails:rule:sub:end -->\n"
        put(os.path.join(rw, "libs", "sub", "CLAUDE.md"), stale)
        _, out = self.upd(rw, merge=True)
        self.assertFalse(has(r"^  (create|regenerate) +(libs/sub|\.claude/worktrees/wt)/", out),
                         "the dry run plans no write inside either nested tree\n" + out)
        self.assertTrue(has("^  hint +libs/sub/CLAUDE.md: libs/sub is a nested git tree", out),
                        "a hint names libs/sub and why the rule is not rendered there")
        self.assertTrue(has("^  create +libs/CLAUDE.md ", out), "the rule's target outside the nested tree still renders")
        self.upd(rw, "--apply")
        self.assertEqual(text_of(os.path.join(rw, "libs", "sub", "CLAUDE.md")), stale,
                         "--apply leaves libs/sub/CLAUDE.md byte-identical")
        self.assertFalse(os.path.lexists(os.path.join(rw, ".claude", "worktrees", "wt", "src", "CLAUDE.md")),
                         "--apply creates nothing inside the worktree")
        libs = os.path.join(rw, "libs", "CLAUDE.md")
        self.assertTrue(os.path.isfile(libs) and "riskrails:rule:sub:start" in text_of(libs),
                        "--apply renders the control target libs/CLAUDE.md")
        rc, out = self.upd(rw, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0: a hint is not a pending update\n" + out)

        # a dirs: entry spelled with ./ or // targets the file the take-back walks (M1)
        rs = os.path.join(self.t, "rules-spelling")
        shutil.copytree(rd, rs, symlinks=True)
        os.makedirs(os.path.join(rs, "lib", "x"))
        os.makedirs(os.path.join(rs, "lib", "y"))
        put(os.path.join(rs, ".ai", "rules", "lib.md"),
            '---\ndirs: ["./lib", "lib//x", "lib/./y", lib]\n---\n# Lib rules\n- lib text\n')
        put(os.path.join(rs, ".ai", "rules", "top.md"), '---\ndirs: ["./"]\n---\n# Root rules\n- root text\n')
        _, out = self.upd(rs, merge=True)
        for t in ("lib/CLAUDE.md", "lib/x/CLAUDE.md", "lib/y/CLAUDE.md"):
            with self.subTest(Template("the dry run plans create $t").substitute(t=t)):
                self.assertTrue(has("^  create +%s " % re.escape(t), out), out)
        self.assertFalse(has(r"^  [a-z?]+ +[^ ]*(\./|//)", out), "no planned target is spelled with ./ or //")
        self.assertEqual(grep("^  create +lib/CLAUDE.md ", out), 1, "./lib and lib plan lib/CLAUDE.md once")
        self.assertTrue(has("^  regenerate +CLAUDE.md ", out), 'dirs: ["./"] still targets the root CLAUDE.md')
        rc, out = self.upd(rs, "--apply", merge=True)
        self.assertEqual(rc, 0, "--apply exits 0\n" + out)
        _, out = self.upd(rs, merge=True)
        self.assertTrue(has("^0 automatic", out),
                        "the run after --apply is up to date: no create/remove alternation\n" + out)
        rc, out = self.upd(rs, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0 after --apply\n" + out)
        lib = os.path.join(rs, "lib", "CLAUDE.md")
        self.assertEqual(grep("riskrails:rule:lib:start", text_of(lib)) if os.path.isfile(lib) else 0, 1,
                         "lib/CLAUDE.md holds one lib block: ./lib and lib collapse")
        self.assertIn("riskrails:rule:top:start", text_of(os.path.join(rs, "CLAUDE.md")),
                      "--apply renders the ./ rule into the root CLAUDE.md")
        rx = os.path.join(self.t, "rules-spelling-escape")
        shutil.copytree(rd, rx, symlinks=True)
        put(os.path.join(rx, ".ai", "rules", "esc.md"), "---\ndirs: [a/../b]\n---\n# Escape\n- text\n")
        _, out = self.upd(rx, merge=True)
        self.assertIn("must stay inside the project: a/../b", out,
                      "dirs: [a/../b] is still refused before it is normalised")

    GIT_LEAK = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")    # a stray one would point these tests' git at another tree

    def tracked_git(self, d, *args, out=False):
        """git in d with the stray GIT_* variables dropped; out=True returns the NUL-split stdout."""
        env = {k: v for k, v in self.env.items() if k not in self.GIT_LEAK}
        done = subprocess.run(GIT + ["-C", d] + list(args), env=env, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        return [x for x in done.stdout.split(b"\0") if x] if out else None

    def index_of(self, d):
        """The paths git tracks in d, as bytes."""
        return set(self.tracked_git(d, "ls-files", "-z", out=True))

    def run_printed(self, d, line):
        """Run, through a shell with cwd = d, the command a hint line prints between backticks."""
        command = next(c for c in re.findall(r"`(git [^`]*)`", line) if "rm --cached" in c)    # not `git commit -a`
        env = {k: v for k, v in self.env.items() if k not in self.GIT_LEAK}
        subprocess.run(["bash", "-c", command], cwd=d, env=env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return command

    def run_hint_command(self, d, out, name):
        """Run the command of the hint for `name` (the shown, escaped name); returns that command."""
        line = next(x for x in out.splitlines() if x.lstrip().startswith("hint") and (" %s: tracked" % name) in x)
        return self.run_printed(d, line)

    def test_tracked_but_ignored_state_file_is_reported(self):
        """a .ai/state file git holds although an ignore rule ignores it is a hint with the untrack command,
        not a pending update; untracked, or outside a git work tree, nothing is said; --apply writes nothing for it"""
        rel = ".ai/state/consent.jsonl"
        d = self.current_project("tracked-ignored")
        self.assertIn(".ai/state/*.jsonl", text_of(os.path.join(d, ".gitignore")),
                      "the scaffolded .gitignore ignores the state ledgers")
        self.tracked_git(d, "init", "-q")
        self.tracked_git(d, "commit", "-q", "--allow-empty", "-m", "init")
        put(os.path.join(d, rel), '{"v":1}\n')
        self.tracked_git(d, "add", "-f", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track the ledger")

        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertTrue(has(r"^  hint +\.ai/state/consent\.jsonl: tracked by git but ignored", out),
                        "a hint names the tracked, ignored state file\n" + out)
        self.assertNotIn("by .gitignore", out, "the rule may come from .git/info/exclude or core.excludesFile\n" + out)
        self.assertIn("git --literal-pathspecs rm --cached -- .ai/state/consent.jsonl", out,
                      "and the command that untracks it, by literal path\n" + out)
        rc, out = self.upd(d, "--check", merge=True, unset=self.GIT_LEAK)
        self.assertEqual(rc, 0, "--check exits 0: a hint is not a pending update\n" + out)

        before = (self.index_of(d), self.tracked_git(d, "status", "--porcelain", out=True))
        rc, out = self.upd(d, "--apply", merge=True, unset=self.GIT_LEAK)
        self.assertEqual(rc, 0, "--apply exits 0\n" + out)
        self.assertEqual(before, (self.index_of(d), self.tracked_git(d, "status", "--porcelain", out=True)),
                         "--apply neither untracks the file nor touches the tree for the hint")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertTrue(has("^0 automatic", out), "the run after --apply is up to date\n" + out)
        self.assertIn("tracked by git but ignored", out, "and the hint is still there: --apply does not act on it")

        self.run_hint_command(d, out, rel)
        self.assertNotIn(rel.encode(), self.index_of(d), "the printed command untracks the file")
        self.assertTrue(os.path.isfile(os.path.join(d, rel)), "and leaves it on disk")
        self.tracked_git(d, "commit", "-q", "-m", "untrack the ledger")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertFalse(has("tracked by git but ignored", out), "an untracked file draws no hint\n" + out)

        n = self.current_project("tracked-ignored-no-git")
        put(os.path.join(n, rel), '{"v":1}\n')
        rc, out = self.upd(n, merge=True, unset=self.GIT_LEAK + ("GIT_CEILING_DIRECTORIES",),
                           GIT_CEILING_DIRECTORIES=os.path.dirname(n))
        self.assertFalse(has("tracked by git but ignored", out), "outside a git work tree there is no hint\n" + out)
        self.assertNotIn("Traceback", out, "and no crash")

    def test_tracked_ignored_hints_say_to_run_the_command_from_the_project_root(self):
        """R-tracked-ignored-untrack-commands-are-cwd: the paths in the printed commands are project-relative,
        so every hint form (one file, the NUL-safe one, the count of the rest) says where to run them"""
        d = self.current_project("tracked-ignored-cwd")
        self.tracked_git(d, "init", "-q")
        names = [".ai/state/f%02d.jsonl" % i for i in range(11)] + [".ai/state/n\nl.jsonl"]
        for rel in names:
            put(os.path.join(d, rel), '{"v":1}\n')
            self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        lines = [x for x in out.splitlines() if "tracked by git but ignored" in x]
        self.assertEqual(len(lines), 11, "ten per-file hints and the count line\n" + out)
        self.assertTrue(any("more file(s)" in x for x in lines), out)
        for line in lines:
            with self.subTest(line=line[:60]):
                self.assertIn("from the project root", line)
                self.assertLess(line.index("from the project root"), re.search(r"`git (--literal|ls-files)", line).start(),
                                "before the command")

    def test_tracked_ignored_hint_quotes_the_path(self):
        """M1: the untrack command quotes a name with a space; a name with a control character is shown
        escaped and gets the NUL-safe command instead, so it neither forges a line nor prints a raw name;
        both printed commands, run, untrack what they say (L5: the NUL-safe one, every such file)"""
        d = self.current_project("tracked-ignored-odd-names")
        self.tracked_git(d, "init", "-q")
        spaced, forged, keep = ".ai/state/a b.jsonl", ".ai/state/n\nl; touch pwn #.jsonl", ".ai/state/keep.jsonl"
        every = {x.encode() for x in (spaced, forged, keep)}
        for rel in (spaced, forged, keep):
            put(os.path.join(d, rel), '{"v":1}\n')
            self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track odd names")

        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertIn("git --literal-pathspecs rm --cached -- '.ai/state/a b.jsonl'", out, "a space is quoted\n" + out)
        self.assertFalse(any(line.lstrip().startswith("l; touch pwn") for line in out.splitlines()),
                         "a newline in a name forges no line\n" + out)
        self.assertIn(".ai/state/n\\nl; touch pwn #.jsonl: tracked by git", out, "the name is shown escaped\n" + out)
        self.assertNotIn("rm --cached -- .ai/state/n", out, "no command with the raw name\n" + out)
        self.assertNotIn("rm --cached -- '.ai/state/n", out, "nor a quoted one that spans lines\n" + out)
        nul_safe = "git ls-files -z -ci --exclude-standard -- .ai/state | xargs -0 -r git --literal-pathspecs rm --cached --"
        self.assertIn(nul_safe, out, "the NUL-safe command instead\n" + out)
        self.assertIn("EVERY tracked, ignored file under .ai/state", out, "which says it untracks them all\n" + out)

        self.run_hint_command(d, out, ".ai/state/a b.jsonl")
        self.assertEqual(self.index_of(d) & every, every - {spaced.encode()},
                         "the quoted command untracks the spaced name only")
        self.run_hint_command(d, out, ".ai/state/n\\nl; touch pwn #.jsonl")
        self.assertEqual(self.index_of(d) & every, set(),
                         "the NUL-safe command untracks every tracked, ignored file under .ai/state")
        self.assertFalse(os.path.exists(os.path.join(d, "pwn")), "and runs nothing from the name")

    def test_tracked_ignored_hint_takes_a_name_literally(self):
        """L4: * ? [ ] in a name is that name, not a pathspec: untracking a[bc].jsonl leaves ab.jsonl tracked"""
        d = self.current_project("tracked-ignored-glob")
        self.tracked_git(d, "init", "-q")
        globbed, plain = ".ai/state/a[bc].jsonl", ".ai/state/ab.jsonl"
        for rel in (globbed, plain):
            put(os.path.join(d, rel), '{"v":1}\n')
            self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track both")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.run_hint_command(d, out, globbed)
        self.assertEqual(self.index_of(d) & {globbed.encode(), plain.encode()}, {plain.encode()},
                         "only a[bc].jsonl left the index; ab.jsonl is still tracked")

    def test_tracked_ignored_hint_is_capped_and_survives_a_non_utf8_name(self):
        """L3: ten per-file hints, then one that counts the rest and carries the command for all;
        a name that is not UTF-8 is shown escaped (never raises) and gets the NUL-safe command"""
        d = self.current_project("tracked-ignored-many")
        self.tracked_git(d, "init", "-q")
        names = [".ai/state/f%02d.jsonl" % i for i in range(12)]
        for rel in names:
            put(os.path.join(d, rel), '{"v":1}\n')
            self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track twelve")
        rc, out = self.upd(d, "--check", merge=True, unset=self.GIT_LEAK)
        self.assertEqual(rc, 0, out)
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertEqual(grep(r"^  hint +\.ai/state/f\d\d\.jsonl: tracked by git but ignored", out), 10,
                         "ten per-file hints\n" + out)
        self.assertEqual(grep(r"^  hint +\.ai/state: 2 more file\(s\) tracked by git but ignored", out), 1,
                         "and one that counts the other two\n" + out)
        self.assertIn("xargs -0 -r git --literal-pathspecs rm --cached --", out, "with the command for all\n" + out)
        self.run_printed(d, next(x for x in out.splitlines() if ": 2 more file(s)" in x))
        self.assertEqual(self.index_of(d) & {x.encode() for x in names}, set(), "which untracks all twelve")

        bad = os.fsencode(os.path.join(d, ".ai", "state")) + b"/bad\xff.jsonl"
        try:
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write('{"v":1}\n')
        except OSError:
            self.skipTest("this filesystem refuses a non-UTF-8 file name")
        self.tracked_git(d, "add", "-f", "--", bad)
        self.tracked_git(d, "commit", "-q", "-m", "track a non-UTF-8 name")
        rc, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertNotIn("Traceback", out, "a non-UTF-8 name does not crash the report\n" + out)
        self.assertIn(".ai/state/bad\\udcff.jsonl: tracked by git but ignored", out,
                      "it is shown escaped\n" + out)
        self.assertIn("xargs -0 -r git --literal-pathspecs rm --cached --", out, "and gets the NUL-safe command\n" + out)
        self.run_hint_command(d, out, ".ai/state/bad\\udcff.jsonl")
        self.assertNotIn(b".ai/state/bad\xff.jsonl", self.index_of(d), "which untracks it")

    def test_tracked_ignored_hint_in_a_project_below_a_git_root(self):
        """L1: a project that is a subdirectory of a git work tree: names stay relative to the project,
        and the printed command, run from the project root, untracks the file"""
        outer = self.dir("tracked-ignored-outer")
        d = self.current_project(os.path.join("tracked-ignored-outer", "proj"))
        self.tracked_git(outer, "init", "-q")
        rel = ".ai/state/consent.jsonl"
        put(os.path.join(d, rel), '{"v":1}\n')
        self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(outer, "commit", "-q", "-m", "track the ledger")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        self.assertTrue(has(r"^  hint +\.ai/state/consent\.jsonl: tracked by git but ignored", out),
                        "the name is relative to the project, not to the git root\n" + out)
        self.assertNotIn("proj/.ai/state", out, out)
        self.run_hint_command(d, out, rel)
        self.assertNotIn(b"proj/" + rel.encode(), self.index_of(outer), "the file left the index")

    def test_check_budget(self):
        """--check --budget: a root instruction file over its byte budget exits 1 (WP6 R21)"""
        b = self.current_project("budget", "--runtime", "claude")
        rc, out = self.upd(b, "--check", "--budget")
        self.assertTrue(rc == 0 and not out.strip(), "a fresh scaffold is within budget: exit 0, nothing printed\n" + out)
        self.assertEqual(self.upd(b, "--budget")[0], 2, "--budget without --check is a usage error")
        put(os.path.join(b, "CLAUDE.md"), "x" * 400 + "\n", "a")
        rc, out = self.upd(b, "--check", "--budget")
        self.assertTrue(rc == 1 and has(r"^CLAUDE\.md file [0-9]+ B over the skeleton budget of 2048 B$", out),
                        "a padded CLAUDE.md exits 1 and names the file and the budget\n" + out)
        self.assertNotIn(" block ", out, "only the offender is listed")
        # An installed plugin has skills/ but no instructions/: the budgets must still apply.
        inst = os.path.join(self.t, "installed", "skills")
        shutil.copytree(os.path.join(ROOT, "skills", "project-update"), os.path.join(inst, "project-update"))
        rc, out = self.run_([sys.executable, "-I", os.path.join(inst, "project-update", "update.py"), b, "--check",
                             "--budget"], merge=True)
        self.assertTrue(rc == 1 and "over the skeleton budget of 2048 B" in out and "Traceback" not in out,
                        "from a skills-only install the shipped budgets apply\n" + out)
        shipped = json.dumps(read_json(os.path.join(ROOT, "instructions", "runtimes.json"))["_budgets"],
                             sort_keys=True, separators=(",", ":"))
        _, default = self.run_([sys.executable, "-I", "-c", "import json, sys; sys.path.insert(0, sys.argv[1]); "
                                "import render_instructions as r; "
                                "print(json.dumps(r.DEFAULT_BUDGETS, sort_keys=True, separators=(',', ':')))",
                                os.path.join(ROOT, "skills", "project-update")])
        self.assertEqual(shipped, default.strip(), "DEFAULT_BUDGETS equals _budgets in runtimes.json")

    def test_budget_hint_for_a_pristine_block(self):
        """budget hint: an untouched block over the budget is the plugin's to trim, not the project's"""
        pt = os.path.join(self.t, "padded-tpl")
        shutil.copytree(TEMPLATES, pt, symlinks=True)
        padded = text_of(os.path.join(pt, "AGENTS.block.md"))
        i = padded.index("<!-- riskrails:end -->")
        put(os.path.join(pt, "AGENTS.block.md"),
            padded[:i] + "<!-- padding, over the project budget -->\n" * 60 + padded[i:])
        pb = self.agents_project("padded", "# mine\n\n" + text_of(os.path.join(pt, "AGENTS.block.md")))
        _, out = self.upd(pb, merge=True, RISKRAILS_TEMPLATES=pt)
        self.assertTrue(has("AGENTS.md: the managed block is [0-9]* B, budget [0-9]* B — the plugin ships it that size",
                            out), "an untouched block over budget is the plugin's\n" + out)
        self.assertNotIn("trimming it is yours", out, "no 'edited here' for the untouched block")
        # The same block with one line of the project's own inside it is the project's.
        agents = os.path.join(pb, "AGENTS.md")
        put(agents, insert_line(text_of(agents), 3, "my own rule, right inside the block", after=True))
        _, out = self.upd(pb, merge=True, RISKRAILS_TEMPLATES=pt)
        self.assertTrue(has("AGENTS.md: the managed block is .* trimming it is yours", out),
                        "an edited block over budget is the project's\n" + out)

    def test_the_nul_safe_untrack_command_does_nothing_when_nothing_is_tracked(self):
        """I2: xargs -r: with no tracked, ignored .ai/state file the printed command exits 0 and leaves the index"""
        d = self.current_project("tracked-ignored-empty-input")
        self.tracked_git(d, "init", "-q")
        rel = ".ai/state/a\nb.jsonl"
        put(os.path.join(d, rel), '{"v":1}\n')
        self.tracked_git(d, "add", "-f", "--", rel)
        self.tracked_git(d, "commit", "-q", "-m", "track")
        _, out = self.upd(d, merge=True, unset=self.GIT_LEAK)
        line = next(x for x in out.splitlines() if "tracked by git but ignored" in x and "xargs" in x)
        self.run_printed(d, line)
        self.tracked_git(d, "commit", "-q", "-m", "untrack")
        before = self.index_of(d)
        self.run_printed(d, line)  # check=True: a non-zero exit raises
        self.assertEqual(before, self.index_of(d), "nothing tracked, nothing changed")

    def task_dir(self, d, task_id, events, logs=()):
        """A task's journal (events: [(days ago, event, data)]), one report file and its run logs."""
        lines = [json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago * 86400)),
                             "task": task_id, "event": ev, "detail": (more[0] if more else ""), "data": data})
                 for ago, ev, data, *more in events]
        put(os.path.join(d, ".ai", "reports", task_id, "events.jsonl"), "\n".join(lines) + "\n")
        put(os.path.join(d, ".ai", "reports", task_id, "task.md"), "x\n")
        for name in logs:
            put(os.path.join(d, ".ai", "state", "logs", task_id, name), "log\n")

    def cleanup_project(self, name):
        d = self.current_project(name)
        self.task_dir(d, "T-2026-01-01-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": False})],
                      logs=("verify.log", "review.log", "state.json"))
        self.task_dir(d, "T-2026-01-02-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})],
                      logs=("verify.log", "state.json"))
        self.task_dir(d, "T-2026-01-03-001", [(9, "task_started", {}), (8, "step_started", {})], logs=("a.log",))
        self.task_dir(d, "T-2026-01-04-001", [(3, "task_started", {}), (2, "step_started", {})], logs=("b.log",))
        self.task_dir(d, "T-2026-01-05-001", [(40, "task_started", {})], logs=("c.log",))
        put_json(os.path.join(d, ".ai", "state", "state.json"), {"task_id": "T-2026-01-05-001"})
        # finished by other evidence than a whole task_closed line (M1)
        self.task_dir(d, "T-2026-01-06-001", [(40, "task_started", {}), (39, "gate_approved", {})], logs=("g.log",))
        self.task_dir(d, "T-2026-01-07-001", [(40, "task_started", {})], logs=("h.log",))
        put_json(os.path.join(d, ".ai", "state", "logs", "T-2026-01-07-001", "state.json"), {"result": "done"})
        # a torn task_closed line and no state.json: still unclosed
        self.task_dir(d, "T-2026-01-08-001", [(40, "task_started", {})], logs=("i.log",))
        put(os.path.join(d, ".ai", "reports", "T-2026-01-08-001", "events.jsonl"),
            '{"ts": "2000-01-01T00:00:00Z", "event": "task_closed", "da', "a")
        # abandoned by the detail alone
        self.task_dir(d, "T-2026-01-09-001", [(30, "task_started", {}), (29, "task_closed", {}, "abandoned")],
                      logs=("j.log", "state.json"))
        # a symlink in a closed task's logs is never followed or listed
        os.symlink(os.path.join(d, ".ai", "state", "logs", "T-2026-01-01-001", "verify.log"),
                   os.path.join(d, ".ai", "state", "logs", "T-2026-01-01-001", "link.log"))
        return d

    def test_cleanup_proposals(self):
        """the logs of a closed task, an abandoned and a long-idle unclosed task are proposed; a recent
        and the in-flight task are not; --check is unaffected"""
        d = self.cleanup_project("cleanup")
        before = tree_sum(d)
        _, out = self.upd(d)
        self.assertTrue(has(r"^  delete\?   \.ai/state/logs/T-2026-01-01-001/ \(2 files\) +\[cleanup\] "
                            r"log of closed task T-2026-01-01-001", out), "one line per task, *.log only\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-02-001/ \(2 files\) +\[cleanup\] abandoned task "
                            r"T-2026-01-02-001", out), out)
        self.assertTrue(has(r"delete\?   \.ai/state/logs/T-2026-01-02-001/ \(1 file\) +\[cleanup\] abandoned task"
                            r".*--confirm-cleanup NAME.*not recoverable through git", out),
                        "an abandoned task keeps its state.json; the row says git cannot restore the logs\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-09-001/ .*abandoned task", out),
                        "abandonment by the event detail alone\n" + out)
        self.assertEqual(grep(r"unclosed task T-2026-01-0[67]-001", out), 0,
                         "gate_approved, or a state.json result, finishes a task\n" + out)
        self.assertTrue(has(r"unclosed task T-2026-01-08-001", out), "a torn task_closed alone is unclosed\n" + out)
        self.assertEqual(grep(r"link\.log", out), 0, "a symlink is skipped\n" + out)
        self.assertEqual(grep(r"commit \.ai/ first", out), 0,
                         "cleanup rows alone do not raise the commit-first hint\n" + out)
        self.assertTrue(has(r"^\d+ automatic, \d+ cleanup file\(s\) awaiting --confirm-cleanup$", out),
                        "the summary names the flag the cleanup rows need\n" + out)
        self.assertNotIn("--confirm-delete", out, "cleanup rows alone never point at --confirm-delete\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-03-001/ \(2 files\) +\[cleanup\] unclosed task "
                            r"T-2026-01-03-001, last event \d{4}-\d\d-\d\d", out), out)
        self.assertEqual(grep(r"T-2026-01-04-001", out), 0, "an open task idle for 2 days is left alone\n" + out)
        self.assertEqual(grep(r"T-2026-01-05-001", out), 0, "the task in flight is never proposed\n" + out)
        self.assertEqual(self.upd(d, "--check")[0], 0)
        self.assertEqual(tree_sum(d), before, "a dry run writes nothing")

    def test_cleanup_skips_a_symlinked_report_dir_with_a_hint_and_apply_does_not_abort(self):
        """R-cleanup-proposes-a-symlinked-ai-reports: a .ai/reports/<id> that is a symlink is a hint, not a
        deletion proposal, so --apply --confirm-cleanup neither aborts nor deletes through it"""
        d = self.current_project("cleanup-symlinked-report")
        self.task_dir(d, "T-2026-01-02-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})])
        self.task_dir(d, "T-2026-01-03-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})])
        real = os.path.join(d, "elsewhere")
        os.rename(os.path.join(d, ".ai", "reports", "T-2026-01-02-001"), real)
        os.symlink(real, os.path.join(d, ".ai", "reports", "T-2026-01-02-001"))
        _, out = self.upd(d)
        self.assertFalse(has(r"delete\?? +\.ai/reports/T-2026-01-02-001", out), "no proposal for it\n" + out)
        self.assertTrue(has(r"^  hint +.*T-2026-01-02-001.*is a symlink", out), "a hint says why\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-03-001/", out), "the safe task is still proposed\n" + out)
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, "--apply does not abort\n" + out)
        self.assertTrue(os.path.isfile(os.path.join(real, "task.md")), "nothing deleted through the symlink")
        self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", "T-2026-01-03-001")), "the safe one is")

    def test_the_rule_writer_skips_what_the_take_back_never_walks(self):
        """R-the-rule-writer-still-reaches-directories: a dirs: entry under a RULES_SKIP name or through a
        symlinked directory is not written (a block there could never be taken back), and is a hint"""
        d = self.current_project("rules-writer-skip", "--runtime", "claude")
        os.makedirs(os.path.join(d, "node_modules", "pkg"))
        os.makedirs(os.path.join(d, "real", "sub"))
        os.makedirs(os.path.join(d, "ok"))
        os.symlink(os.path.join(d, "real"), os.path.join(d, "linked"))
        put(os.path.join(d, ".ai", "rules", "skip.md"),
            "---\ndirs: [node_modules/pkg, linked, linked/sub, ok]\n---\n# Skip rules\n- text\n")
        _, out = self.upd(d, merge=True)
        self.assertFalse(has(r"^  (create|regenerate) +(node_modules|linked)/", out), "no write there\n" + out)
        self.assertTrue(has(r"^  hint +node_modules/pkg/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  hint +linked/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  hint +linked/sub/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  create +ok/CLAUDE.md ", out), "the control target renders\n" + out)
        self.assertEqual(self.upd(d, "--apply")[0], 0)
        for rel in ("node_modules/pkg", "real", "real/sub"):
            self.assertFalse(os.path.lexists(os.path.join(d, rel, "CLAUDE.md")), rel)
        self.assertTrue(os.path.isfile(os.path.join(d, "ok", "CLAUDE.md")))

    def test_a_block_an_older_plugin_wrote_in_a_skipped_dir_is_named_in_the_hint(self):
        """R-rule-blocks-written-before-under-a-now-s-b44b: a rendered block already in an unwalked
        directory stays frozen (the take-back never walks there); the hint says to remove it by hand"""
        d = self.current_project("rules-writer-skip-old", "--runtime", "claude")
        os.makedirs(os.path.join(d, "ok"))
        os.makedirs(os.path.join(d, "node_modules", "pkg"))
        os.makedirs(os.path.join(d, "node_modules", "bare"))
        rule = os.path.join(d, ".ai", "rules", "skip.md")
        put(rule, "---\ndirs: [ok]\n---\n# Skip rules\n- text\n")
        self.assertEqual(self.upd(d, "--apply", merge=True)[0], 0)
        shutil.copy(os.path.join(d, "ok", "CLAUDE.md"), os.path.join(d, "node_modules", "pkg", "CLAUDE.md"))
        frozen = tree_sum(os.path.join(d, "node_modules"))
        put(rule, "---\ndirs: [node_modules/pkg, node_modules/bare]\n---\n# Skip rules\n- text\n")
        rc, out = self.upd(d, "--apply", merge=True)
        self.assertEqual(rc, 0, out)
        self.assertTrue(has(r"^  hint +node_modules/pkg/CLAUDE.md: .*not rendered there.*earlier rendering.*by hand", out), out)
        self.assertFalse(has(r"^  hint +node_modules/bare/CLAUDE.md: .*earlier rendering", out),
                         "no block there, no claim of one\n" + out)
        self.assertTrue(has(r"^  hint +node_modules/bare/CLAUDE.md: .*not rendered there", out), out)
        self.assertEqual(tree_sum(os.path.join(d, "node_modules")), frozen, "nothing is deleted or rewritten there")

    def test_the_rules_skip_comparison_ignores_case(self):
        """R-rules-skip-comparison-is-case-sensitive-a50b: dirs: [Vendor/x] with vendor/ on disk (a
        case-insensitive filesystem) is skipped by the writer as the take-back walk prunes it"""
        d = self.current_project("rules-writer-skip-case", "--runtime", "claude")
        os.makedirs(os.path.join(d, "vendor", "x"))
        os.makedirs(os.path.join(d, "ok"))
        put(os.path.join(d, ".ai", "rules", "skip.md"),
            "---\ndirs: [Vendor/x, PODS/y, ok]\n---\n# Skip rules\n- text\n")
        rc, out = self.upd(d, "--apply", merge=True)
        self.assertEqual(rc, 0, out)
        self.assertFalse(has(r"^  (create|regenerate) +(Vendor|PODS)/", out), "no write there\n" + out)
        self.assertTrue(has(r"^  hint +Vendor/x/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  hint +PODS/y/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  create +ok/CLAUDE.md ", out), "the control target renders\n" + out)
        for rel in ("vendor/x", "Vendor/x", "PODS/y"):
            self.assertFalse(os.path.lexists(os.path.join(d, rel, "CLAUDE.md")), rel)

    def test_the_take_back_walk_prunes_by_exact_name(self):
        """a block an older plugin wrote under Vendor/x (a RULES_SKIP name only by case) is walked
        and taken back as before: the casefold belongs to the writer, not to the walk"""
        d = self.current_project("rules-walk-case", "--runtime", "claude")
        os.makedirs(os.path.join(d, "ok"))
        put(os.path.join(d, ".ai", "rules", "skip.md"), "---\ndirs: [ok]\n---\n# Skip rules\n- text\n")
        self.assertEqual(self.upd(d, "--apply", merge=True)[0], 0)
        os.makedirs(os.path.join(d, "Vendor", "x"))
        shutil.copy(os.path.join(d, "ok", "CLAUDE.md"), os.path.join(d, "Vendor", "x", "CLAUDE.md"))
        rc, out = self.upd(d, merge=True)
        self.assertEqual(rc, 0, out)
        self.assertTrue(has(r"^  regenerate +Vendor/x/CLAUDE.md .*rule block skip removed", out), out)

    def test_the_hint_probe_survives_a_target_that_is_not_a_file(self):
        """a skipped target whose CLAUDE.md is a directory or a FIFO gives the plain hint, no traceback"""
        d = self.current_project("rules-skip-notfile", "--runtime", "claude")
        os.makedirs(os.path.join(d, "node_modules", "dirp", "CLAUDE.md"))
        os.makedirs(os.path.join(d, "node_modules", "fifo"))
        os.mkfifo(os.path.join(d, "node_modules", "fifo", "CLAUDE.md"))
        put(os.path.join(d, ".ai", "rules", "skip.md"),
            "---\ndirs: [node_modules/dirp, node_modules/fifo]\n---\n# Skip rules\n- text\n")
        rc, out = self.upd(d, merge=True)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Traceback", out)
        self.assertTrue(has(r"^  hint +node_modules/dirp/CLAUDE.md: .*not rendered there", out), out)
        self.assertTrue(has(r"^  hint +node_modules/fifo/CLAUDE.md: .*not rendered there", out), out)
        self.assertFalse(has(r"earlier rendering", out), out)

    def test_a_symlink_into_the_walked_project_adds_no_by_hand_clause(self):
        """linked -> real/ inside the project: the take-back walks real/ and removes the old block in
        the same run, so the hint does not ask for a removal by hand"""
        d = self.current_project("rules-skip-link-in", "--runtime", "claude")
        os.makedirs(os.path.join(d, "ok"))
        os.makedirs(os.path.join(d, "real"))
        rule = os.path.join(d, ".ai", "rules", "skip.md")
        put(rule, "---\ndirs: [ok]\n---\n# Skip rules\n- text\n")
        self.assertEqual(self.upd(d, "--apply", merge=True)[0], 0)
        shutil.copy(os.path.join(d, "ok", "CLAUDE.md"), os.path.join(d, "real", "CLAUDE.md"))
        os.symlink(os.path.join(d, "real"), os.path.join(d, "linked"))
        put(rule, "---\ndirs: [linked]\n---\n# Skip rules\n- text\n")
        rc, out = self.upd(d, merge=True)
        self.assertEqual(rc, 0, out)
        self.assertTrue(has(r"^  hint +linked/CLAUDE.md: .*not rendered there", out), out)
        self.assertFalse(has(r"by hand", out), out)
        self.assertTrue(has(r"^  regenerate +real/CLAUDE.md .*rule block skip removed", out), out)

    def test_cleanup_malformed_now_and_flight(self):
        """a malformed RISKRAILS_NOW is a usage error, not a traceback; the task named by the legacy
        current.json is in flight"""
        d = self.cleanup_project("cleanup-now")
        rc, out = self.upd(d, merge=True, RISKRAILS_NOW="yesterday")
        self.assertEqual(rc, 2, out)
        self.assertTrue("RISKRAILS_NOW" in out and "Traceback" not in out, out)
        self.assertEqual(len(out.strip().splitlines()), 1, "one line\n" + out)
        os.remove(os.path.join(d, ".ai", "state", "state.json"))
        put_json(os.path.join(d, ".ai", "state", "current.json"), {"task_id": "T-2026-01-03-001"})
        _, out = self.upd(d)
        self.assertEqual(grep(r"T-2026-01-03-001", out), 0, "current.json names the task in flight\n" + out)

    def test_cleanup_confirmed_deletes_and_prunes(self):
        """--apply --confirm-cleanup removes the proposed files and the directories they leave empty;
        --confirm-delete alone does not settle them"""
        d = self.cleanup_project("cleanup-apply")
        before = tree_sum(d)
        rc, out = self.upd(d, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(tree_sum(d), before, "--confirm-delete leaves every [cleanup] row\n" + out)
        self.assertEqual(self.upd(d, "--confirm-cleanup", "tester")[0], 2, "--confirm-cleanup needs --apply")
        self.assertEqual(self.upd(d, "--apply", "--confirm-cleanup", "")[0], 2, "an empty name is refused")
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester")
        self.assertEqual(rc, 5, "--confirm-cleanup without a human present is refused\n" + out)
        self.assertEqual(out.split("\n")[0].split(":")[0], "CONFIRM_REFUSED")
        self.assertEqual(tree_sum(d), before)
        if self.has_pty():
            tty = self.cleanup_project("cleanup-tty")
            rc, out = self.pty(["env", "CLAUDECODE=1", sys.executable, "-I", UPDATE, tty, "--apply",
                                "--confirm-cleanup", "tester"], unset=NOMARK)
            self.assertTrue(rc == 5 and "CLAUDECODE" in out, "an agent marker with a terminal is refused\n" + out)
            rc, out = self.pty([sys.executable, "-I", UPDATE, tty, "--apply", "--confirm-cleanup", "tester"],
                               unset=NOMARK)
            self.assertEqual(rc, 0, out)
            self.assertEqual(read_json(only(os.path.join(tty, ".ai", "reports", "project-update-*",
                                                         "migration.json")))["deletions"][0]["via"], "terminal")
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        report = glob.glob(os.path.join(d, ".ai", "reports", "project-update-*"))
        rec = read_json(os.path.join(report[0], "migration.json"))
        self.assertEqual((rec["deletions"][0]["confirmed_by"], rec["deletions"][0]["via"]),
                         ("tester", "unattended"))
        self.assertFalse(os.path.exists(os.path.join(report[0], "original")), "no original/ copy of a [cleanup]")
        logs = os.path.join(d, ".ai", "state", "logs")
        self.assertEqual(sorted(os.listdir(os.path.join(logs, "T-2026-01-01-001"))), ["link.log", "state.json"],
                         "the closed task's logs go, its state.json stays (and a symlink is never followed)")
        self.assertEqual(os.listdir(os.path.join(logs, "T-2026-01-02-001")), ["state.json"],
                         "an abandoned task's state.json stays")
        self.assertTrue(os.path.islink(os.path.join(logs, "T-2026-01-01-001", "link.log")), "the symlink stays")
        self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", "T-2026-01-02-001")))
        self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", "T-2026-01-03-001")))
        self.assertFalse(os.path.exists(os.path.join(logs, "T-2026-01-03-001")))
        self.assertTrue(os.path.exists(os.path.join(logs, "T-2026-01-04-001", "b.log")))
        self.assertTrue(os.path.exists(os.path.join(logs, "T-2026-01-05-001", "c.log")))
        self.assertTrue(os.path.isdir(os.path.join(d, ".ai", "reports")))

    def git_(self, d, *args):
        subprocess.run(GIT + ["-C", d] + list(args), env=self.env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    def abandoned(self, d, task_id):
        self.task_dir(d, task_id, [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})],
                      logs=("verify.log",))

    def test_cleanup_reports_are_tracked_not_git_ignored(self):
        """#5: a report dir git holds is worded 'tracked'; one it does not hold keeps the commit-first
        hint; both keep an original/ copy; the git-ignored logs keep their wording and no copy"""
        d = self.current_project("cleanup-git")
        subprocess.run(["git", "-C", d, "init", "-q"], env=self.env, check=True)
        put(os.path.join(d, ".gitignore"), ".ai/state/logs/\n")
        self.abandoned(d, "T-2026-01-01-001")
        self.git_(d, "add", "-A")
        self.git_(d, "commit", "-qm", "base")
        _, out = self.upd(d)
        self.assertFalse(has(r"commit \.ai/ first", out), "a committed report needs no hint\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-01-001/ \(2 files\) +\[cleanup\] abandoned task "
                            r"T-2026-01-01-001; tracked: git can restore a committed copy", out), out)
        self.assertTrue(has(r"delete\?   \.ai/state/logs/T-2026-01-01-001/ .*not recoverable through git", out), out)
        self.abandoned(d, "T-2026-01-02-001")            # written after the commit: untracked
        _, out = self.upd(d)
        self.assertTrue(has(r"hint +commit \.ai/ first", out), "an untracked report keeps the hint\n" + out)
        self.assertTrue(has(r"T-2026-01-02-001/ \(2 files\) .*uncommitted: git holds no copy", out), out)
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        orig = os.path.join(glob.glob(os.path.join(d, ".ai", "reports", "project-update-*"))[0], "original")
        for task_id in ("T-2026-01-01-001", "T-2026-01-02-001"):
            self.assertTrue(os.path.isfile(os.path.join(orig, ".ai", "reports", task_id, "task.md")),
                            "an original/ copy of a report file")
            self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", task_id)))
        self.assertFalse(os.path.exists(os.path.join(orig, ".ai", "state")), "no copy of git-ignored logs")

    def test_cleanup_unreadable_state_json_is_a_task_in_flight(self):
        """#11: an unparsable state.json proposes nothing as stale"""
        d = self.cleanup_project("cleanup-torn")
        put(os.path.join(d, ".ai", "state", "state.json"), "{ not json")
        _, out = self.upd(d)
        self.assertEqual(grep(r"\[cleanup\]", out), 0, "nothing is proposed while a task may be in flight\n" + out)

    SWAP = """
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "skills", "project-update"))
from rr_update import apply, build                       # noqa: E402
root = sys.argv[2]
plan = build.build_plan(root, confirm_cleanup="tester", cleanup_via="unattended")
reports = os.path.join(root, ".ai", "reports")
os.rename(os.path.join(reports, "T-2026-01-02-001"), os.path.join(reports, "moved"))
os.symlink("moved", os.path.join(reports, "T-2026-01-02-001"))     # same bytes, now behind a symlink
try:
    apply.apply(plan)
except apply.Abort as exc:
    print("ABORT", exc.why)
    sys.exit(0)
print("DELETED")
"""

    def test_cleanup_apply_refuses_a_path_swapped_to_a_symlink(self):
        """#70 (n): unsafe_target's check is repeated right before the delete"""
        d = self.cleanup_project("cleanup-swap")
        done = subprocess.run([sys.executable, "-I", "-c", self.SWAP, ROOT, d], env=self.env,
                              capture_output=True, text=True, check=False)
        self.assertTrue(done.stdout.startswith("ABORT") and "is a symlink" in done.stdout,
                        done.stdout + done.stderr)
        self.assertTrue(os.path.isfile(os.path.join(d, ".ai", "reports", "moved", "task.md")), "nothing deleted")


class TestMemoryPolicy(unittest.TestCase):
    """compact-project-memory (plan Risks): .ai/policies/memory.json is the
    project's, written by `memory enable`; no template ships it, and --update
    leaves it and the record byte for byte as they are."""

    def test_update_leaves_memory_json_and_the_record_alone(self):
        p = Project()
        try:
            policy = b'{\n  "schema": 1,\n  "mode": "packages",\n  "period": "month",\n  "cleanup": false\n}\n'
            with open(p.path("policies", "memory.json"), "wb") as fh:
                fh.write(policy)
            os.makedirs(p.path("memory"))
            with open(p.path("memory", "2026-10.dev.abcd.jsonl"), "wb") as fh:
                fh.write(b'{"author":"dev","batch":"abcd","created":"2026-10-01T00:00:00Z","format":1,'
                         b'"period":"2026-10","pkg":"riskrails-memory"}\n')
            subprocess.run(GIT + ["-C", p.root, "add", "-A"], check=True)
            subprocess.run(GIT + ["-C", p.root, "commit", "-qm", "memory on"], check=True)
            done = p.update("--apply")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(p.read("policies", "memory.json"), policy)
            self.assertEqual(os.listdir(p.path("memory")), ["2026-10.dev.abcd.jsonl"])
            self.assertNotIn("memory.json", done.stdout)
            self.assertFalse(os.path.exists(os.path.join(TEMPLATES, ".ai", "policies", "memory.json")))
        finally:
            p.close()


class TestWeightMd(unittest.TestCase):
    """weight.md is always rendered from the plugin's table and weight.project.json (spec :161)."""

    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.close)

    def md(self):
        return self.p.read("policies", "weight.md")

    def test_a_project_overlay_is_rendered_into_the_mirror(self):
        put_json(self.p.path("policies", "weight.project.json"),
                 {"version": 1, "tests": {"max_suite_runs": 9}})
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn('"max_suite_runs": 9', self.md().decode())
        self.assertIn("weight.project.json", self.md().decode(), "the header names its source")
        self.assertIn("up to date", self.p.update().stdout, "and the second run has nothing left")

    def test_a_missing_mirror_is_created(self):
        os.remove(self.p.path("policies", "weight.md"))
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.isfile(self.p.path("policies", "weight.md")))

    def test_a_stale_generated_mirror_is_regenerated_without_a_gate(self):
        text = self.md().decode().replace("sha256: ", "sha256: 0")
        put(self.p.path("policies", "weight.md"), text)
        out = self.p.update("--apply").stdout
        self.assertRegex(out, r"(?m)^  regenerate +\.ai/policies/weight\.md")
        self.assertNotIn("regenerate?", out)

    def test_a_hand_written_mirror_waits_for_the_gate(self):
        put(self.p.path("policies", "weight.md"), "# my own weight notes\n")
        out = self.p.update("--apply").stdout
        self.assertRegex(out, r"(?m)^  regenerate\? +\.ai/policies/weight\.md")
        self.assertEqual(self.md(), b"# my own weight notes\n", "an unconfirmed apply leaves it")
        done = subprocess.run([sys.executable, "-I", UPDATE, self.p.root, "--apply", "--confirm-delete", "tester"],
                              env=dict(self.p.env, AI_UNATTENDED="1"), capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("# Weight table", self.md().decode())
        original = glob.glob(self.p.path("reports", "project-update-*", "original", ".ai", "policies", "weight.md"))
        self.assertEqual(raw(original[0]), b"# my own weight notes\n")

    def test_an_overlay_the_renderer_cannot_take_is_refused_before_anything_is_written(self):
        put_json(self.p.path("policies", "weight.project.json"), {"version": 1, "modes": 3})
        before = self.md()
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 6, done.stdout)
        self.assertTrue(done.stdout.startswith("KEPT_UNREADABLE: .ai/policies/weight.project.json: "))
        self.assertEqual(self.md(), before)


DEEP_READERS = r"""
import datetime, json, os, sys, traceback
sys.path.insert(0, sys.argv[1])
from rr_update import cleanup, history, kept, plan
root, deep = sys.argv[2], "[" * 100000


def put(rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def probe(name, fn):
    try:
        out[name] = repr(fn())
    except history.SchemaError as exc:
        out[name] = "SchemaError: %s" % exc
    except Exception:  # pylint: disable=broad-except
        out[name] = "Traceback: " + traceback.format_exc().splitlines()[-1]


out = {}
hist = os.path.join(root, "history")
put("history/index.json", deep)
probe("History index.json", lambda: history.History(hist).index)
put(".ai/state/state.json", deep)
probe("check_kept state.json", lambda: kept.check_kept(root))
probe("cleanup_update state.json", lambda: (cleanup.cleanup_update(
    plan.Plan(root), now=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)), "ran"))
put(".ai/reports/T-1/events.jsonl", deep + "\n" + json.dumps({"ts": "2026-01-01T00:00:00Z", "event": "x"}))
put(".ai/state/logs/T-1/state.json", deep)
probe("task_journal events.jsonl + logs state.json", lambda: cleanup.task_journal(root, "T-1"))
print(json.dumps(out))
"""


class TestDeepJsonReaders(unittest.TestCase):
    """Risk d4d1: CPython raises RecursionError, not ValueError, on JSON nested
    past its parser's limit (100000 levels, measured); every project-update
    reader takes it the way it takes malformed JSON, with no Traceback."""

    def test_every_reader_takes_a_too_deep_file_as_malformed(self):
        with tempfile.TemporaryDirectory() as root:
            done = subprocess.run([sys.executable, "-I", "-c", DEEP_READERS, os.path.dirname(UPDATE), root],
                                  capture_output=True, text=True, check=False)
        self.assertNotIn("Traceback", done.stderr, done.stderr)
        got = json.loads(done.stdout)
        want = {"History index.json": "{}",
                "cleanup_update state.json": "(None, 'ran')",
                "task_journal events.jsonl + logs state.json":
                    "(False, False, datetime.datetime(2026, 1, 1, 0, 0, tzinfo=datetime.timezone.utc))"}
        for name, value in want.items():
            with self.subTest(reader=name):
                self.assertEqual(got[name], value)
        with self.subTest(reader="check_kept state.json"):
            self.assertRegex(got["check_kept state.json"], r"^\[\('\.ai/state/state\.json', 'is not valid JSON.*'\)\]$")


if __name__ == "__main__":
    unittest.main()
