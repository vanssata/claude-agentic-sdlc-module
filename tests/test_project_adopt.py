#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
update.py --adopt: a project carrying a foreign AI-tool structure (Spec Kit,
Kiro, Cursor, Copilot, AI-DLC, Junie, Gemini, an oversized CLAUDE.md or
AGENTS.md) is detected, planned onto claude-agentic's layout, and nothing is
lost or written without the gates. Fixtures: tests/fixtures/adopt/README.md.

Every project lives in a temp directory with a pinned HOME; the plugin's shared
tree is this checkout's.
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
PU = os.path.join(ROOT, "skills", "project-update")
UPDATE = os.path.join(PU, "update.py")
HOOK_SCAFFOLD = os.path.join(ROOT, "hooks", "project-scaffold.sh")
SCAFFOLD = os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh")
FIX = os.path.join(ROOT, "tests", "fixtures", "adopt")

TWIN_OF = "test-project-adopt.sh"

FOREIGN = ("speckit", "kiro", "cursor", "copilot", "aidlc")
ALL_FIXTURES = FOREIGN + ("junie-gemini", "large-claude-md", "large-agents-md")
POINTER = "Read `.ai/policies/adopted/always.md` first."
# NOMARK: every agent-session marker and AI_UNATTENDED, so a case sets exactly the
# markers it names (the suite runs inside Claude Code and in CI).
NOMARK = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI", "CODEX_SANDBOX",
          "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION", "AI_UNATTENDED")
# R13 reads a shell `pass` as written, up to its first inner quote: these are the cases it
# records for the labels that name a directory and for the one with escaped quotes.
BASENAME_CASES = ("$(basename ", "$f under '$(basename ")
FALLBACK_CASE = r'\"split\": \"fallback\" in decisions.json chooses the fallback'

# The planner, run as update.py's own callers run it; sys.argv[2] is the mode.
ROUTER = """
import sys
import update, adopt
plan = update.Plan(sys.argv[1])
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adopt.plan_adopt(plan, adopt.load_table(), sys.argv[2], None, update.shipped_block, caps["skeleton"], files,
                 update.shipped_ai_files())
print(next(i for i in plan.items if i["action"] == "router")["content"].decode("utf-8"))
"""

ROWS_USED = """
import sys, os
import update, adopt
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
used = set()
for f in ("speckit", "kiro", "cursor", "copilot", "aidlc", "junie-gemini", "large-claude-md", "large-agents-md"):
    plan = update.Plan(os.path.join(sys.argv[1], f))
    used |= adopt.plan_adopt(plan, table, "migrate", None, update.shipped_block, caps["skeleton"]).rows_used
missing = [str(r["_n"]) + " " + r["tool"] + " " + r["source"] for r in table["rows"] if r["_n"] not in used]
print("\\n".join(missing))
"""

LOST = """
import sys, os
import update, adopt
root = sys.argv[1]
plan = update.Plan(root)
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adoption = adopt.plan_adopt(plan, table, "migrate", None, update.shipped_block, caps["skeleton"], files,
                            update.shipped_ai_files())
dest = ".ai/policies/adopted/cursorrules.md"
for i in plan.items:
    if i["target"] == dest:
        i["content"] = b"nothing kept\\n"
plan.final[dest] = b"nothing kept\\n"
status, lines, missing, missing_n = adopt.check_lines(plan, adoption)
print(status)
print(missing_n)
print(missing[0] if missing else "")
"""

BAD_TABLE = """
import adopt, sys
try:
    adopt.load_table(sys.argv[1])
except adopt.TableError:
    sys.exit(0)
sys.exit(1)
"""

ADDED = """
import sys, types
import update, adopt
real = adopt.section_of
adopt.section_of = lambda cand, move: (real(cand, move)[0] + "\\nAlways deploy on Fridays.", real(cand, move)[1])
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
args = types.SimpleNamespace(tool=None, mode="migrate", check=False, split=None, split_request=False, diff=False)
sys.exit(adopt.run(update.Plan(sys.argv[1]), args, update.shipped_block, caps["skeleton"], files,
                   update.shipped_ai_files()))
"""

PLACEHOLDERS = """
import adopt, sys
print(" ".join(n for n in sys.argv[1:] if adopt.placeholder_name(n)))
"""


def body(path):
    """A file's text, or "" when there is none — what a grep on a missing file finds."""
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        return fh.read()


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, content, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
        fh.write(content)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sha256(path):
    return hashlib.sha256(raw(path)).hexdigest()


def grep(pattern, out):
    """`grep -c`: the lines of out that match."""
    return sum(1 for line in out.splitlines() if re.search(pattern, line))


def has(pattern, out):
    return grep(pattern, out) > 0


def first(out):
    return out.split("\n", 1)[0]


def token(out):
    """The first line of out up to its first colon: ADOPT_REFUSED, ADOPT_INCOMPLETE."""
    return first(out).split(":", 1)[0]


def lines_of(path):
    return body(path).splitlines()


def tree_sha(d):
    """Every file and its content, .git excluded."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not (top == d and x == ".git")]
        out += [(os.path.relpath(os.path.join(top, f), d), raw(os.path.join(top, f)))
                for f in files if os.path.isfile(os.path.join(top, f))]
    return sorted(out)


def files_of(d):
    """`find . -path ./.git -prune -o -type f -print | sort`."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not (top == d and x == ".git")]
        out += [os.path.relpath(os.path.join(top, f), d) for f in files]
    return sorted(out)


def one(pattern):
    """The one path a glob names; a name that does not exist when it names none or several."""
    paths = glob.glob(pattern)
    return paths[0] if len(paths) == 1 else os.path.join(os.path.dirname(pattern), "<%d matches>" % len(paths))


def today():
    return time.strftime("%Y-%m-%d", time.gmtime())


class TestProjectAdopt(unittest.TestCase):  # pylint: disable=too-many-public-methods
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDownClass ends it
        cls.t = cls.tmp.name
        os.makedirs(os.path.join(cls.t, "home"))
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS", "CLAUDE_CONFIG_DIR",
                                "CLAUDE_AGENTIC_TEMPLATES", "CLAUDE_ROUTING_TEMPLATES", "CLAUDE_AGENTIC_TEST",
                                "ADOPT_STOP_AFTER", "ADOPT_TODAY")}
        cls.env.update(HOME=os.path.join(cls.t, "home"), CLAUDE_AGENTIC_SHARED=os.path.join(ROOT, "ai"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- helpers ------------------------------------------------------------

    def run_(self, args, merge=False, unset=(), cwd=None, **extra):
        env = {k: v for k, v in self.env.items() if k not in unset}
        env.update(extra)
        done = subprocess.run(args, env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, text=True,
                              errors="replace", check=False)
        return done.returncode, done.stdout

    def upd(self, d, *args, merge=False, **extra):
        return self.run_([sys.executable, "-I", UPDATE, d] + list(args), merge=merge, **extra)

    def confirm(self, d, *extra_args, name="tester", **extra):
        """A cleanup confirmed as a launcher would: AI_UNATTENDED=1, no terminal."""
        extra.setdefault("AI_UNATTENDED", "1")
        return self.upd(d, "--adopt", "--cleanup", "--apply", "--confirm-delete", name, *extra_args, **extra)

    def py(self, code, *args, merge=False, **extra):
        """A snippet against the project-update modules, as `cd skills/project-update && python3 -` ran it."""
        return self.run_([sys.executable, "-I", "-c", "import sys; sys.dont_write_bytecode = True; "
                          "sys.path.insert(0, %r)\n" % PU + code] + list(args), merge=merge, **extra)

    def router(self, d, mode="migrate"):
        return self.py(ROUTER, d, mode)[1].rstrip("\n")

    def pty(self, args, **extra):
        """The command with a terminal on stdin (util-linux script), stdout and stderr merged,
        \\r stripped; the exit status is the command's. SHELL is pinned because script -c runs it."""
        rc, out = self.run_(["script", "-qec", shlex.join(args), "/dev/null"], unset=NOMARK, SHELL="/bin/bash",
                            **extra)
        return rc, out.replace("\r", "")

    def has_pty(self):
        try:
            return self.pty([sys.executable, "-c", "import os; print(os.isatty(0))"])[1].strip() == "True"
        except OSError:
            return False

    def path(self, *parts):
        return os.path.join(self.t, *parts)

    def git(self, d, *args, check=True):
        return subprocess.run(["git", "-C", d] + list(args), env=self.env, capture_output=True, text=True,
                              check=check)

    def scaffold(self, d, rt):
        """A fresh claude-agentic project, as the skills make it."""
        os.makedirs(d, exist_ok=True)
        self.run_(["bash", HOOK_SCAFFOLD, d, "--runtime", rt])
        self.run_(["bash", SCAFFOLD, d, "--runtime", rt])
        return d

    def commit(self, d, message="fixture"):
        """A git work tree with everything committed."""
        if not os.path.lexists(os.path.join(d, ".git")):
            self.git(d, "init", "-q")
            self.git(d, "config", "user.email", "t@example.com")
            self.git(d, "config", "user.name", "t")
        self.git(d, "add", "-A")
        self.git(d, "commit", "-qm", message, check=False)

    def adopt_fixture(self, name, dest, fixtures=FIX):
        """The fixture materialised as a real project — `dot-` components become `.`,
        `fixture-X.md` becomes `X.md` (appended to the scaffolded file when fixture.json
        says so), then committed."""
        fx = os.path.join(fixtures, name)
        spec = read_json(os.path.join(fx, "fixture.json"))
        self.scaffold(dest, spec["runtime"])
        for top, _, files in os.walk(fx):
            for f in files:
                if f in ("README.md", "fixture.json", "split-proposal.fixture.json"):
                    continue
                rel = os.path.relpath(os.path.join(top, f), fx)
                out = re.sub(r"(^|/)dot-", r"\1.", rel)
                out = re.sub(r"(^|/)fixture-([A-Z]+\.md)$", r"\1\2", out)
                target = os.path.join(dest, out)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if (spec.get("instruction_append") or {}).get(out):
                    put(target, raw(os.path.join(top, f)), "ab")
                else:
                    shutil.copy2(os.path.join(top, f), target)
        self.commit(dest)
        return dest

    def fixture(self, name, label):
        return self.adopt_fixture(name, self.path(label))

    def plain(self, name):
        """The shared, never-applied copy of a fixture under plain/."""
        d = self.path("plain", name)
        if not os.path.isdir(d):
            self.adopt_fixture(name, d)
        return d

    def cleaned(self, label):
        """The cursor fixture adopted and committed, ready for --cleanup."""
        d = self.fixture("cursor", label)
        self.upd(d, "--adopt", "--apply")
        self.commit(d, "adopted")
        return d

    def assert_refused(self, d, what):
        """exit 5, ADOPT_REFUSED on line 1, and nothing written."""
        before = tree_sha(d)
        rc, out = self.upd(d, "--adopt", "--apply")
        with self.subTest("$2: refused, exit 5, nothing written".replace("$2", what)):
            self.assertTrue(rc == 5 and token(out) == "ADOPT_REFUSED" and tree_sha(d) == before,
                            "rc=%d\n%s" % (rc, out))

    def assert_cleanup_refused(self, d, what):
        """Confirmed as a launcher would, still exit 5, ADOPT_REFUSED on line 1, nothing removed."""
        before = tree_sha(d)
        rc, out = self.confirm(d)
        with self.subTest("$2: cleanup refused, exit 5, nothing removed".replace("$2", what)):
            self.assertTrue(rc == 5 and token(out) == "ADOPT_REFUSED" and tree_sha(d) == before,
                            "rc=%d\n%s" % (rc, out))

    def record(self, d):
        return read_json(one(os.path.join(d, ".ai", "reports", "adopt-*", "adopt.json")))

    def plant_record(self, d, date, sll, sd, srcsha):
        rec = {"version": 1, "mode": "migrate", "adopted_at": date + "T00:00:00Z", "plugin_schema": 5,
               "tools": {"cursor": {"files": 1}},
               "sources": [{"path": ".cursorrules", "sha": srcsha, "tool": "cursor", "transform": "copy",
                            "dest": ".ai/policies/adopted/cursorrules.md", "dest_sha": "sha256:x", "cleanup": True}],
               "dropped": 0, "ignored": [], "unmapped": [], "original_bytes": 0,
               "checks": {"no_line_lost": {"status": sll, "checked_at": date + "T00:00:00Z"},
                          "no_dangling": {"status": sd, "checked_at": date + "T00:00:00Z"}},
               "cleanup": {"offered": True, "confirmed_by": None, "at": None, "unattended": None, "tty": None,
                           "deleted": []}}
        put(os.path.join(d, ".ai", "reports", "adopt-" + date, "adopt.json"), json.dumps(rec))

    def proposal(self, d, name, defect=None):
        """The fixture's canned proposal as a real I5 document for the file on disk
        (tests/fixtures/adopt/README.md), into the record directory; defect plants one."""
        fx = os.path.join(FIX, "large-claude-md" if name == "CLAUDE.md" else "large-agents-md")
        text = body(os.path.join(d, name))
        lines = text.split("\n")[:-1]
        off = len(lines) - len(body(os.path.join(fx, "fixture-" + name)).split("\n")[:-1])
        start = next(i for i, l in enumerate(lines, 1) if "riskrails:start" in l)
        canned = read_json(os.path.join(fx, "split-proposal.fixture.json"))
        sh = lambda r: [r[0] + off, r[1] + off]  # noqa: E731
        doc = {"version": 1, "source": name,
               "source_sha": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
               "keep": [[1, start - 1]] + [sh(r) for r in canned["keep"]],
               "moves": [dict(m, lines=sh(m["lines"])) for m in canned["moves"]],
               "dropped": [dict(x, lines=sh(x["lines"])) for x in canned["dropped"]]}
        if defect:
            defect(doc)
        put(os.path.join(d, ".ai", "reports", "adopt-" + today(), "split-proposal.json"),
            json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n")

    def forge(self, d, edit):
        """A hand edit of the committed adopt.json, committed."""
        path = one(os.path.join(d, ".ai", "reports", "adopt-*", "adopt.json"))
        doc = read_json(path)
        edit(doc)
        put(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        self.commit(d, "forged")

    # -- the cases ----------------------------------------------------------

    def test_fixtures_are_stored_encoded(self):
        """fixtures are stored encoded (the path guard and the runtimes never see a real name)"""
        unencoded = [os.path.join(top, n) for top, dirs, files in os.walk(FIX) for n in dirs + files
                     if n.startswith(".") or n in ("CLAUDE.md", "AGENTS.md", "GEMINI.md")]
        self.assertEqual(unencoded, [], "no dot-file and no real instruction file under tests/fixtures/adopt")
        for d in sorted(glob.glob(os.path.join(FIX, "*", ""))):
            name = os.path.basename(os.path.dirname(d))
            with self.subTest(name + " README names its source"):
                self.assertTrue(has("^Source: ", body(os.path.join(d, "README.md"))))

    def test_mapping_table(self):
        """the mapping table loads, and a bad one is refused"""
        self.assertEqual(self.py("import adopt; adopt.load_table()")[0], 0, "adopt-map.json is a valid table")
        put(self.path("bad.json"), '{"version":1,"tools":{"x":{"signature":["x/"],"roots":["x/"]}},'
                                   '"rows":[{"tool":"x","source":"x/*","transform":"shred"}]}')
        self.assertEqual(self.py(BAD_TABLE, self.path("bad.json"))[0], 0, "an unknown transform is a table error")

    def test_r1_r2_each_structure_is_detected_and_planned(self):
        """R1, R2: each foreign structure is detected and planned, and the dry run writes nothing"""
        for base in ("with space", "plain"):
            for f in FOREIGN:
                p = self.plain(f) if base == "plain" else self.adopt_fixture(f, self.path(base, f))
                before = tree_sha(p)
                rc, out = self.upd(p, "--adopt")
                with self.subTest("%s under '%s': dry run exits 0" % (f, base)):
                    self.assertEqual(rc, 0, out)
                with self.subTest(Template("$f: one detect line").substitute(f=f), base=base):
                    self.assertTrue(has("^  detect +%s " % f, out), out)
                with self.subTest(Template("$f: at least one source planned").substitute(f=f), base=base):
                    self.assertTrue(has("^  adopt ", out), out)
                with self.subTest(Template("$f: migrate is the default mode (R3)").substitute(f=f), base=base):
                    self.assertIn("mode: migrate", first(out))
                with self.subTest(Template("$f: the tree is byte-identical after the dry run").substitute(f=f),
                                  base=base):
                    self.assertEqual(tree_sha(p), before)
        _, out = self.upd(self.plain("speckit"), "--adopt")
        self.assertTrue(has("^  adopt     .specify/memory/constitution.md -> docs/sdlc/constitution.md .*append-section",
                            out), "the Spec Kit constitution is appended to ours, not a conflict\n" + out)
        self.assertTrue(has("^  dropped   .claude/skills/speckit-plan/SKILL.md", out),
                        "a current Spec Kit skill is dropped")
        _, out = self.upd(self.plain("cursor"), "--adopt")
        self.assertTrue(has(r".cursor/rules/frontend/react.mdc -> .ai/rules/frontend-react.md .*"
                            r"dirs: \[src/components, src/hooks\]", out),
                        "a glob-scoped Cursor rule becomes a .ai/rules/ rule with dirs\n" + out)
        self.assertTrue(has("^  ignored   .cursor/mcp.json", out), "Cursor configuration is ignored, not adopted")
        _, out = self.upd(self.plain("kiro"), "--adopt")
        self.assertTrue(has("^  adopt     .kiro/steering/tech.md -> .ai/policies/adopted/always.md .*rule: always", out),
                        "a Kiro steering file without frontmatter is always included (A4)\n" + out)
        self.assertTrue(has("^  ignored   .kiro/steering/aws-aidlc-rules/", out),
                        "AI-DLC installed for Kiro stays out of the steering row")

    def test_nested_worktree_is_not_this_projects(self):
        """a nested worktree is not this project's: its foreign files are never detected"""
        n = self.scaffold(self.path("nested-wt"), "claude")
        self.commit(n)
        wt = os.path.join(n, ".claude", "worktrees", "wt")
        self.assertEqual(self.git(n, "worktree", "add", "-q", "-b", "wt", wt, check=False).returncode, 0,
                         "git worktree add failed: the case below would prove nothing")
        self.assertTrue(os.path.isfile(os.path.join(wt, ".git")), "the fixture is a real worktree: its .git is a file")
        put(os.path.join(wt, ".cursorrules"), "# theirs\nuse tabs\n")
        put(os.path.join(wt, ".cursor", "rules", "x.mdc"), "---\nalwaysApply: true\n---\nuse tabs\n")
        self.commit(wt)
        _, out = self.upd(n, "--adopt", merge=True)
        self.assertFalse(has("ADOPT_INCOMPLETE|^  unmapped ", out), "no ADOPT_INCOMPLETE and no unmapped row\n" + out)
        self.assertNotIn("worktrees/wt", out, "and no file of the nested worktree is named")

    def test_every_row_is_exercised(self):
        """every row of the table is exercised by a fixture"""
        for f in ALL_FIXTURES:
            self.plain(f)
        _, out = self.py(ROWS_USED, self.path("plain"), merge=True)
        self.assertEqual(out.strip(), "", "every mapping row matched a file in its fixture")

    def test_the_four_instruction_files(self):
        """the four instruction files: foreign without the managed block, a split candidate only when too big"""
        for rt in ("claude", "codex", "gemini", "junie", "claude,codex"):
            s = self.scaffold(self.path("fresh-" + rt), rt)
            rc, out = self.upd(s, "--adopt")
            with self.subTest(Template("a fresh $rt scaffold is not foreign").substitute(rt=rt)):
                self.assertTrue(rc == 0 and has("^  no foreign structure detected$", out), "rc=%d\n%s" % (rc, out))
        s = self.path("fresh-claude")
        put(os.path.join(s, "CLAUDE.md"), "n" * 200 + "\n", "a")
        rc, out = self.upd(s, "--adopt")
        self.assertTrue(has(r"^  split\?    CLAUDE.md", out) and "unmapped" not in out,
                        "the scaffold plus 200 B of notes is a split candidate, not unmapped\n" + out)
        self.assertTrue(rc == 4 and has("^ADOPT_INCOMPLETE: .*a split needs a proposal", first(out)),
                        "I1: the dry run exits 4 while a split awaits its proposal, as --apply would")
        s = self.path("fresh-codex")
        put(os.path.join(s, "AGENTS.md"), "n" * 200 + "\n", "a")
        self.assertTrue(has(r"^  split\?    AGENTS.md", self.upd(s, "--adopt")[1]), "the same for AGENTS.md")
        _, out = self.upd(self.plain("junie-gemini"), "--adopt")
        self.assertTrue(has("^  detect +gemini +GEMINI.md", out) and has("^  detect +junie ", out),
                        "GEMINI.md and .junie/guidelines.md without the block are foreign\n" + out)
        self.assertNotIn("split?", out, "and at this size neither is a split candidate")
        self.assertTrue(has(r"^  split\?    CLAUDE.md", self.upd(self.plain("large-claude-md"), "--adopt")[1]),
                        "large-claude-md lists split?")
        self.assertTrue(has(r"^  split\?    AGENTS.md", self.upd(self.plain("large-agents-md"), "--adopt")[1]),
                        "large-agents-md lists split?")

    def test_r4_unmapped_fails_loudly(self):
        """R4: what no row maps fails loudly, and a human's decision settles it"""
        k = self.fixture("kiro", "kiro-hooks")
        put(os.path.join(k, ".kiro", "hooks", "lint-on-save.json"), '{"hooks": []}\n')
        rc, out = self.upd(k, "--adopt")
        self.assertEqual(rc, 4, "an unmapped Kiro hook exits 4\n" + out)
        self.assertEqual(token(out), "ADOPT_INCOMPLETE", "ADOPT_INCOMPLETE on the first line")
        self.assertTrue(has("^  unmapped  .kiro/hooks/lint-on-save.json .*decisions.json", out),
                        "and it names the file and where to decide")
        put(os.path.join(k, ".ai", "reports", "adopt-2000-01-01", "decisions.json"),
            '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"drop",'
            '"why":"Kiro agent hook; no equivalent here"}}}\n')
        rc, out = self.upd(k, "--adopt")
        self.assertTrue(rc == 0 and has("^  dropped   .kiro/hooks/lint-on-save.json .*no equivalent here", out),
                        "a decision in an older adopt-* directory settles it\n" + out)
        n = self.scaffold(self.path("nested"), "claude")
        put(os.path.join(n, "packages", "x", ".cursor", "rules", "a.mdc"), "---\nalwaysApply: true\n---\n\n- Use pnpm.\n")
        rc, out = self.upd(n, "--adopt")
        self.assertTrue(rc == 4 and has("^  unmapped  packages/x/.cursor/rules/a.mdc .*below the root", out),
                        "a nested .cursor/rules/ is unmapped, exit 4\n" + out)
        i = self.scaffold(self.path("ignore-only"), "claude")
        put(os.path.join(i, ".kiro", "settings", "mcp.json"), "{}\n")
        rc, out = self.upd(i, "--adopt")
        self.assertTrue(rc == 0 and has("^  ignored   .kiro/settings/mcp.json", out) and has("^0 automatic", out),
                        "a tree with only ignored files prints them and 0 automatic\n" + out)

    def test_r18_rows_stay_inside_their_roots(self):
        """R18, re-review C: rows stay inside their tool's roots; a file under two tools goes to the one that maps it"""
        x = self.fixture("speckit", "speckit-app")
        put(os.path.join(x, "src", "lib", "speckit_x.py"), "SPECKIT = 1\n")
        _, out = self.upd(x, "--adopt")
        self.assertNotIn("src/lib/speckit_x.py", out, "src/lib/speckit_x.py is neither a source nor dropped")
        c = self.fixture("cursor", "speckit-cursor")
        put(os.path.join(c, ".specify", "memory", "constitution.md"), "# Constitution\n\n### I. Tests first\n")
        put(os.path.join(c, ".cursor", "commands", "speckit.plan.md"), "Run the plan script.\n")
        put(os.path.join(c, ".cursor", "skills", "speckit-plan", "SKILL.md"), "---\nname: speckit-plan\n---\n\nPlan.\n")
        rc, out = self.upd(c, "--adopt")
        self.assertTrue(rc == 0 and has(r"^  dropped   .cursor/commands/speckit.plan.md .*\[speckit\]", out)
                        and "unmapped" not in out,
                        "Spec Kit's .cursor/commands/ file is dropped by speckit, nothing unmapped\n" + out)

    def test_r23_secret_value_is_never_printed(self):
        """R23: a secret-looking line is named by file:line, its value never printed"""
        z = self.fixture("cursor", "secret")
        value = "sk-%dabcdefgh" % int(time.time())
        put(os.path.join(z, ".cursorrules"), "API_KEY=%s\n" % value, "a")
        self.commit(z)
        _, out = self.upd(z, "--adopt")
        self.assertTrue(has("^  hint      .cursorrules:4 .*looks like a secret", out),
                        "the hint names .cursorrules:4\n" + out)
        self.assertNotIn(value, out, "and the value is not in the output")

    def test_r3_mode_is_explicit(self):
        """R3: the mode is explicit"""
        p = self.plain("cursor")
        _, out = self.upd(p, "--adopt", "--mode", "coexist")
        self.assertIn("mode: coexist", first(out), "--mode coexist is shown in the header")
        self.assertFalse(has("^  adopt ", out), "coexist plans no move")
        self.assertEqual(self.upd(p, "--adopt", "--mode", "merge")[0], 2, "an unknown mode is a usage error")
        self.assertEqual(self.upd(p, "--mode", "coexist")[0], 2, "--mode without --adopt is a usage error")

    def test_i9_router_rows(self):
        """I9 router rows: appended once, idempotent by exact text"""
        r = self.fixture("cursor", "router")
        _, out = self.upd(r, "--adopt")
        # A5: cursorrules (policies/adopted/), the path-scoped rule (rules/), and one row per on-demand
        # rule under policies/adopted/ (testing.mdc, typescript.mdc); the always rule has no row (A4).
        self.assertTrue(has(r"^  router    .ai/AGENTS.md +\+4 row\(s\)$", out), "the dry run plans +4 router rows\n" + out)
        content = self.router(r)
        self.assertIn("| anything, first (rules adopted from Cursor) | policies/adopted/ |", content,
                      "the cursorrules row names the directory relative to .ai")
        self.assertIn("| an adopted Cursor file | rules/ |", content, "a rule with no explicit router text gets a default")
        # Simulate an already-applied router edit: write the planned content, then re-plan.
        put(os.path.join(r, ".ai", "AGENTS.md"), content + "\n")
        _, out = self.upd(r, "--adopt")
        self.assertFalse(has("^  router", out), "a second run adds no router item: idempotent by text")

    def test_r9_r10_no_line_lost(self):
        """R9, R10: no-line-lost passes on every fixture, and a genuinely missing line fails it"""
        for f in ALL_FIXTURES:
            d = self.fixture(f, "lines-" + f)
            _, out = self.upd(d, "--adopt")
            with self.subTest(Template("$f: check no-line-lost PASS").substitute(f=f)):
                self.assertTrue(has("^  check +no-line-lost +PASS", out), out)
        _, out = self.py(LOST, self.path("lines-cursor"))
        rows = out.split("\n") + ["", "", ""]
        self.assertEqual(rows[0], "fail", "a genuinely lost line fails the check\n" + out)
        self.assertTrue(re.match("[1-9]", rows[1]), "and counts how many")
        self.assertTrue(re.match(".cursorrules:", rows[2]), "and names file:line")

    def test_a1_a2_speckit_machinery_and_glob_decisions(self):
        """A1, A2: the current Spec Kit machinery is mapped, and a glob decision settles a whole directory"""
        a1 = self.fixture("speckit", "a1")
        _, out = self.upd(a1, "--adopt")
        self.assertNotIn("unmapped", out, "nothing unmapped in the current Spec Kit layout")
        for f in ("extensions.yml", "init-options.json", "integrations/claude.manifest.json", "presets/x/preset.md",
                  "workflows/x.md"):
            with self.subTest(Template(".specify/$f is dropped as tool machinery").substitute(f=f)):
                self.assertTrue(has("^  dropped   .specify/%s .*Spec Kit tool machinery" % f, out), out)
        self.assertTrue(has("^  dropped   .specify/integrations/speckit.manifest.json .*Spec Kit tool machinery", out),
                        "speckit.manifest.json is machinery, not an agent command by a filename coincidence")
        self.assertTrue(has("^  adopt     specs/001-user-auth/checklists/requirements.md -> "
                            "docs/sdlc/specs/001-user-auth-checklists-requirements.md", out),
                        "a /speckit.checklist file is copied under docs/sdlc/specs/")
        put(os.path.join(a1, "specs", "001-user-auth", "contracts", "api.yaml"), "openapi: 3.1.0\n")
        put(os.path.join(a1, "specs", "002-cart", "contracts", "api.yaml"), "openapi: 3.1.0\n")
        self.commit(a1)
        decisions = os.path.join(a1, ".ai", "reports", "adopt-2000-01-01", "decisions.json")
        put(decisions, '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"drop",'
                       '"why":"contracts live in the API repo"}}}\n')
        _, out = self.upd(a1, "--adopt")
        self.assertTrue(grep("^  dropped   specs/00[12]-[a-z-]*/contracts/api.yaml .*API repo", out) == 2
                        and "unmapped" not in out, "one glob key settles both contracts files\n" + out)
        put(decisions, '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"drop","why":"glob"},'
                       '"specs/002-cart/contracts/api.yaml":{"action":"ignore","why":"exact"}}}\n')
        _, out = self.upd(a1, "--adopt")
        self.assertTrue(has("^  ignored   specs/002-cart/contracts/api.yaml .*exact", out)
                        and has("^  dropped   specs/001-user-auth/contracts/api.yaml .*glob", out),
                        "an exact key wins over a glob\n" + out)
        put(decisions, '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"copy",'
                       '"dest":"docs/sdlc/specs/contracts.md"}}}\n')
        rc, out = self.upd(a1, "--adopt")
        self.assertTrue(rc == 4 and has("^  unmapped  specs/001-user-auth/contracts/api.yaml .*a glob decision cannot copy",
                                        out), "a glob copy is refused: one destination cannot take many files\n" + out)

    def test_a3_references_are_rewritten_or_named(self):
        """A3: references inside migrated text are rewritten, or named as warnings"""
        a3 = self.fixture("speckit", "a3")
        self.upd(a3, "--apply")
        self.commit(a3, "plain update")
        rc, out = self.upd(a3, "--adopt")
        self.assertTrue(rc == 0 and has("^  check +no-dangling +PASS", out),
                        "a real-shaped Spec Kit tree passes no-dangling\n" + out)
        self.assertTrue(has("no-dangling +PASS .*docs/sdlc/plans/001-user-auth-tasks.md:[0-9]+ -> specs/", out),
                        "the directory reference in tasks.md is a named warning")
        self.assertTrue(has("no-dangling +PASS .*docs/sdlc/constitution.md:[0-9]+ -> .specify/", out),
                        "the Sync Impact Report's .specify/templates/ is a named warning")
        rc, out = self.upd(a3, "--adopt", "--apply")
        self.assertTrue(rc == 0 and "Feature specification from `docs/sdlc/specs/001-user-auth.md`"
                        in body(os.path.join(a3, "docs", "sdlc", "plans", "001-user-auth.md")),
                        "plan.md's spec path is rewritten to its new home\n" + out)
        self.assertTrue(any('"reason": "rewritten: path reference"' in body(p)
                            for p in glob.glob(os.path.join(a3, ".ai", "reports", "adopt-*", "dropped.jsonl"))),
                        "the rewrite is logged in dropped.jsonl")
        self.assertTrue(has("^  check +no-line-lost +PASS", out), "no-line-lost still holds after the rewrite")
        self.commit(a3, "adopted")
        _, out = self.upd(a3, "--adopt")
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a second --adopt after the rewrite plans nothing (R15)")
        self.assertEqual(len(re.findall("docs/sdlc/constitution.md:[0-9]+ -> .specify/", out)), 2,
                         "both Sync Impact Report lines are named, not only the first in the file")
        put(os.path.join(a3, "docs", "sdlc", "plans", "001-user-auth-tasks.md"),
            "Our own note: the old spec is `specs/001-user-auth/spec.md`.\n", "a")
        self.commit(a3, "own note")
        rc, out = self.upd(a3, "--adopt")
        self.assertTrue(rc == 4 and has("no-dangling +FAIL: docs/sdlc/plans/001-user-auth-tasks.md:[0-9]+ -> specs/",
                                        out),
                        "a warned adopted line first in a file does not hide the project's own stale line below it")
        h3 = self.fixture("speckit", "a3-own")
        put(os.path.join(h3, ".ai", "policies", "coding.md"), "\nOur own note: see `specs/001-user-auth/spec.md`.\n", "a")
        self.commit(h3)
        rc, out = self.upd(h3, "--adopt")
        self.assertTrue(rc == 4 and has("no-dangling +FAIL: .ai/policies/coding.md:[0-9]+ -> specs/", out),
                        "the project's own stale reference still fails hard\n" + out)

    def test_a4_always_rule(self):
        """A4: an always rule goes into always.md, and every instruction file points at it"""
        a4 = self.fixture("cursor", "a4")
        self.run_(["bash", HOOK_SCAFFOLD, a4, "--runtime", "codex"])
        self.run_(["bash", SCAFFOLD, a4, "--runtime", "claude,codex"])
        self.upd(a4, "--apply")
        self.commit(a4, "two runtimes")
        _, out = self.upd(a4, "--adopt", "--apply")
        always = os.path.join(a4, ".ai", "policies", "adopted", "always.md")
        self.assertTrue(has(r"^## Adopted from Cursor \(general\.mdc\)$", body(always))
                        and "Use pnpm, never npm or yarn." in body(always),
                        "the alwaysApply rule is in always.md\n" + out)
        for f in ("CLAUDE.md", "AGENTS.md"):
            with self.subTest(Template("$f points at it, and carries none of its text").substitute(f=f)):
                self.assertTrue(POINTER in lines_of(os.path.join(a4, f))
                                and "Use pnpm, never npm or yarn." not in body(os.path.join(a4, f)), out)
        self.assertNotIn("split?", out, "no instruction file goes over its budget")
        self.assertFalse(os.path.lexists(os.path.join(a4, ".ai", "policies", "adopted", "cursor-general.md")),
                         "and no cursor-general.md of its own")
        self.assertTrue(has("^  check +no-line-lost +PASS", out), "no-line-lost holds")
        self.commit(a4, "adopted")
        _, out = self.upd(a4, "--adopt")
        self.assertTrue(has("^0 automatic", out)
                        and lines_of(always).count("## Adopted from Cursor (general.mdc)") == 1
                        and lines_of(os.path.join(a4, "CLAUDE.md")).count(POINTER) == 1,
                        "a second run appends nothing\n" + out)
        b4 = self.fixture("cursor", "a4-budget")
        put(os.path.join(b4, ".cursor", "rules", "big.mdc"),
            "---\ndescription: Everything\nalwaysApply: true\n---\n\n" + "".join(
                "- Convention number %d applies to every change in this repository.\n" % i for i in range(1, 401)))
        self.commit(b4)
        rc, out = self.upd(b4, "--adopt", "--apply")
        self.assertTrue(rc == 0 and "split?" not in out
                        and "Convention number 400 " in body(os.path.join(b4, ".ai", "policies", "adopted", "always.md")),
                        "a 25 KB always rule does not touch the instruction file's budget\n" + out)
        # M-new-2: --tool names cursor only, yet CLAUDE.md gets the pointer, so its budget is checked too.
        b5 = self.fixture("cursor", "a4-budget-tool")
        self.upd(b5, "--apply")
        claude = os.path.join(b5, "CLAUDE.md")
        size = len(raw(claude))
        put(claude, "\n" + "x" * (2048 - 20 - size - 1), "a")
        self.commit(b5, "CLAUDE.md 20 B under the skeleton budget")
        rc, out = self.upd(b5, "--adopt", "--tool", "cursor")
        self.assertTrue(rc == 4 and has(r"split\?.*CLAUDE.md|CLAUDE.md.*split\?", out),
                        "--tool cursor: the pointer that takes CLAUDE.md over its budget makes it a split?\n" + out)

    def test_a5_router_rows_carry_a_trigger(self):
        """A5: router rows carry a trigger; coexist has one row per directory"""
        rows = self.router(self.fixture("cursor", "a5"))
        self.assertIn("| How to write and run tests; apply when adding or changing tests | "
                      "policies/adopted/cursor-testing.md |", rows,
                      "an on-demand rule's row is triggered by its description and names its file")
        self.assertIn("| TypeScript conventions | policies/adopted/cursor-typescript.md |", rows,
                      "the glob-only rule gets its own row too")
        c5 = self.fixture("speckit", "a5-coexist")
        _, out = self.upd(c5, "--adopt", "--mode", "coexist")
        m = re.search(r"^  router +.ai/AGENTS.md +\+([0-9]+)", out, re.M)
        n = int(m.group(1)) if m else None
        tracked = self.git(c5, "ls-files", ".specify", "specs", ".claude", ".github", ".gemini").stdout.split()
        dirs = len({os.path.dirname(p) or "." for p in tracked})
        self.assertTrue(n is not None and n <= dirs, Template("coexist adds $n row(s) for $dirs directories, "
                                                              "not one per file").substitute(n=n, dirs=dirs))
        rows = self.router(c5, "coexist")
        self.assertFalse([l for l in rows.splitlines() if "specs/001-user-auth/" in l and "globs" in l],
                         "no globs suffix on a spec row")
        _, rows = self.upd(self.fixture("cursor", "a5-coexist-cursor"), "--adopt", "--mode", "coexist", "--diff")
        self.assertTrue([l for l in rows.splitlines()
                         if re.search(r"^\+\|.*\.cursor/rules/", l) and "its globs are not applied" in l],
                        "the Cursor rules row keeps the globs suffix\n" + rows)

    # STRONG review of package B: what a later pass over the same files must keep

    def test_b1_reference_to_an_always_rule(self):
        """B1: a reference to an always rule goes where the rule really went."""
        v1 = self.fixture("cursor", "rv-always-ref")
        put(os.path.join(v1, ".cursorrules"), "See `.cursor/rules/general.mdc` for the conventions.\n", "a")
        self.commit(v1)
        rc, out = self.upd(v1, "--adopt", "--apply")
        adopted = os.path.join(v1, ".ai", "policies", "adopted")
        self.assertTrue(rc == 0 and "See `.ai/policies/adopted/always.md` for the conventions."
                        in body(os.path.join(adopted, "cursorrules.md")),
                        "a reference to an always rule is rewritten to always.md, a file that exists\n" + out)
        self.assertIn("_Project-wide conventions_", lines_of(os.path.join(adopted, "always.md")),
                      "the always rule's description is kept above its text")

    def test_b2_pointer_survives_a_split(self):
        """B2: the pointer survives a split and is paid for out of the budget."""
        v2 = self.fixture("cursor", "rv-pointer-split")
        claude = os.path.join(v2, "CLAUDE.md")
        put(claude, "n" * 120 + "\n", "a")
        self.commit(v2)
        rc, out = self.upd(v2, "--adopt")
        self.assertTrue(rc == 4 and has(r"^  split\?    CLAUDE.md", out),
                        "a file the pointer would take over the budget is a split? candidate\n" + out)
        rc, out = self.upd(v2, "--adopt", "--apply", "--split", "fallback")
        self.assertTrue(rc == 0 and POINTER in lines_of(claude)
                        and "always.md" not in body(os.path.join(v2, ".ai", "policies", "adopted", "claude-md.md")),
                        "--split fallback keeps the pointer in CLAUDE.md and moves only the project's lines\n" + out)
        self.commit(v2, "adopted")
        _, out = self.upd(v2, "--adopt")
        self.assertTrue(has("^0 automatic", out), "and the next --adopt plans nothing (R15)\n" + out)
        put(claude, "m" * 1000 + "\n", "a")
        self.commit(v2, "the file grows again")
        rc, out = self.upd(v2, "--adopt", "--apply", "--split", "fallback")
        self.assertTrue(rc == 0 and has(r"CLAUDE.md -> CLAUDE.md .*split \(fallback\)", out)
                        and POINTER in lines_of(claude)
                        and not any("always.md" in body(p) for p in
                                    glob.glob(os.path.join(v2, ".ai", "policies", "adopted", "claude-md*.md"))),
                        "a later split of a file already carrying the pointer keeps it, and copies it nowhere\n" + out)

    def test_b3_two_always_rules_with_one_basename(self):
        """B3: two always rules with one basename."""
        v3 = self.fixture("cursor", "rv-same-name")
        put(os.path.join(v3, ".cursor", "rules", "a", "index.mdc"), "---\nalwaysApply: true\n---\n\n- Rule from a.\n")
        put(os.path.join(v3, ".cursor", "rules", "b", "index.mdc"), "---\nalwaysApply: true\n---\n\n- Rule from b.\n")
        self.commit(v3)
        rc, out = self.upd(v3, "--adopt", "--apply")
        always = os.path.join(v3, ".ai", "policies", "adopted", "always.md")
        rows = lines_of(always)
        self.assertTrue(rc == 0 and "## Adopted from Cursor (a/index.mdc)" in rows
                        and "## Adopted from Cursor (b/index.mdc)" in rows
                        and "Rule from a." in body(always) and "Rule from b." in body(always),
                        "two always rules named index.mdc keep a heading and a body each\n" + out)

    def test_b4_foreign_heading_naming_a_path(self):
        """B4: a foreign heading that names a path is the tool's wording too."""
        v4 = self.fixture("speckit", "rv-heading")
        put(os.path.join(v4, "specs", "001-user-auth", "plan.md"), "\n## Layout under `specs/001-user-auth/`\n", "a")
        self.commit(v4)
        rc, out = self.upd(v4, "--adopt")
        self.assertTrue(rc == 0 and has("no-dangling +PASS .*docs/sdlc/plans/001-user-auth.md:[0-9]+ -> specs/", out),
                        "a foreign heading with a directory path is a named warning\n" + out)

    def adopted_with_reference(self, fixture, label, where, reference):
        """A fixture whose foreign file names a file a later run moves: updated, adopted, committed."""
        d = self.fixture(fixture, label)
        put(os.path.join(d, where), "\nSee also `%s`.\n" % reference, "a")
        self.commit(d)
        self.upd(d, "--apply")
        self.commit(d, "plain update")
        self.upd(d, "--adopt", "--apply")
        self.commit(d, "adopted")
        return d

    def second_feature(self, d, path):
        put(os.path.join(d, path), "# Cart\n\nThe cart holds items.\n")
        self.commit(d, "second feature")

    def test_b5_a_later_run_moves_a_named_file(self):
        """B5: a later run moves a file an earlier-adopted document already named."""
        v5 = self.adopted_with_reference("speckit", "rv-later", "specs/001-user-auth/research.md",
                                         "specs/002-cart/spec.md")
        self.second_feature(v5, "specs/002-cart/spec.md")
        rc, out = self.upd(v5, "--adopt", "--apply")
        self.assertTrue(rc == 0 and not has("^  conflict", out) and "See also `docs/sdlc/specs/002-cart.md`."
                        in body(os.path.join(v5, "docs", "sdlc", "specs", "001-user-auth-research.md")),
                        "a later run updates the reference in an untouched destination instead of a conflict\n" + out)
        # B5b (M-new-1): the same for a file named in an append-section destination and in always.md.
        v5b = self.adopted_with_reference("speckit", "rv-later-append", ".specify/memory/constitution.md",
                                          "specs/002-cart/spec.md")
        self.second_feature(v5b, "specs/002-cart/spec.md")
        rc, out = self.upd(v5b, "--adopt", "--apply")
        constitution = os.path.join(v5b, "docs", "sdlc", "constitution.md")
        self.assertTrue(rc == 0 and "See also `docs/sdlc/specs/002-cart.md`." in body(constitution)
                        and lines_of(constitution).count("## Adopted from Spec Kit (constitution.md)") == 1,
                        "a later run updates the reference in an append-section destination\n" + out)
        v5d = self.adopted_with_reference("speckit", "rv-later-own-line", ".specify/memory/constitution.md",
                                          "specs/002-cart/spec.md")
        constitution = os.path.join(v5d, "docs", "sdlc", "constitution.md")
        put(constitution, "\nC11. Every cart change updates `specs/002-cart/spec.md` by hand.\n", "a")
        self.commit(v5d, "own principle")
        self.second_feature(v5d, "specs/002-cart/spec.md")
        own = next(i for i, l in enumerate(lines_of(constitution), 1) if l.startswith("C11. "))
        rc, out = self.upd(v5d, "--adopt")
        self.assertTrue(rc == 4 and has("no-dangling +FAIL: docs/sdlc/constitution.md:%d -> specs/" % own, out)
                        and not has("FAIL: .*constitution.md:[0-9]+ -> specs/.*constitution.md:[0-9]+ -> specs/", out)
                        and "append-section; references to newly moved files updated" in out,
                        "the project's own line naming a moved file stays as written and fails hard; "
                        "the adopted one is rewritten, and the plan says so")
        v5c = self.adopted_with_reference("kiro", "rv-later-always", ".kiro/steering/tech.md",
                                          ".kiro/specs/cart/requirements.md")
        self.second_feature(v5c, ".kiro/specs/cart/requirements.md")
        rc, out = self.upd(v5c, "--adopt", "--apply")
        always = body(os.path.join(v5c, ".ai", "policies", "adopted", "always.md"))
        self.assertTrue(rc == 0 and ".kiro/specs/cart/requirements.md" not in always and "See also `" in always,
                        "a later run updates the reference in always.md\n" + out)

    def test_b6_old_coexist_rows_are_superseded(self):
        """B6: coexist rows written per file before 2026-09-27 are superseded, not kept beside the new ones."""
        v6 = self.fixture("speckit", "rv-old-rows")
        self.upd(v6, "--apply")
        self.commit(v6, "plain update")
        router = os.path.join(v6, ".ai", "AGENTS.md")
        lines = body(router).split("\n")
        last = max(i for i, l in enumerate(lines) if l.startswith("|"))
        old = ["| an adopted Spec Kit spec | specs/001-user-auth/spec.md (kept in place; its globs are not applied by "
               "this runtime) |",
               "| an adopted Spec Kit file | specs/001-user-auth/tasks.md (kept in place; its globs are not applied by "
               "this runtime) |"]
        put(router, "\n".join(lines[:last + 1] + old + lines[last + 1:]))
        self.commit(v6, "old coexist rows")
        rc, out = self.upd(v6, "--adopt", "--mode", "coexist", "--apply")
        self.assertTrue(rc == 0 and "specs/001-user-auth/spec.md (kept in place" not in body(router)
                        and "| specs/001-user-auth/ (kept in place" in body(router)
                        and has("^  router .*-2 superseded", out),
                        "the old per-file coexist rows give way to the directory row\n" + out)

    def test_l2_non_utf8_source_is_copied_byte_for_byte(self):
        """L2: a source that is not UTF-8 is copied byte for byte, never re-encoded."""
        v7 = self.fixture("speckit", "rv-latin1")
        source = os.path.join(v7, "specs", "001-user-auth", "research.md")
        put(source, b"caf\xe9 see `specs/001-user-auth/spec.md`\n", "wb")
        self.commit(v7)
        self.upd(v7, "--apply")
        self.commit(v7, "plain update")
        _, out = self.upd(v7, "--adopt", "--apply")
        dest = os.path.join(v7, "docs", "sdlc", "specs", "001-user-auth-research.md")
        self.assertTrue(os.path.isfile(dest) and raw(source) == raw(dest),
                        "a non-UTF-8 source is copied unchanged, not rewritten lossily\n" + out)

    def test_r11_hard_and_warn_scope(self):
        """R11: a hard-scope stale reference fails no-dangling, the same in warn scope only warns"""
        d = self.fixture("cursor", "dangling")
        put(os.path.join(d, ".ai", "policies", "coding.md"), "\nSee `@.cursorrules` for the legacy rules.\n", "a")
        self.commit(d)
        rc, out = self.upd(d, "--adopt")
        self.assertTrue(has(r"^  check +no-dangling +FAIL: .ai/policies/coding.md:[0-9]+ -> .cursorrules$", out),
                        "a hard-scope reference to .cursorrules fails no-dangling\n" + out)
        self.assertTrue(rc == 4 and has("^ADOPT_INCOMPLETE: .*no-dangling FAIL", first(out)),
                        "I1: a failed check is exit 4 in the dry run, not a PASS-looking exit 0")
        w = self.fixture("cursor", "warn-only")
        count = lambda out: int(re.search(r"no-dangling +PASS \(([0-9]+)", out).group(1))  # noqa: E731
        baseline = count(self.upd(w, "--adopt")[1])
        put(os.path.join(w, "src", "README.md"), "# Notes\n\nSee `@.cursorrules` for the legacy rules.\n")
        self.commit(w)
        _, out = self.upd(w, "--adopt")
        self.assertTrue(has("^  check +no-dangling +PASS", out) and count(out) == baseline + 1,
                        "the same reference in src/README.md adds one warning, not a failure\n" + out)
        self.assertTrue(has(r"^  check +no-dangling +PASS \([0-9]+ warning\(s\) outside the new structure: "
                            r".*src/README.md:3 -> .cursorrules", out), "the warning is named by file:line, not only counted")

    def test_r14_coexist_plans_only_the_router(self):
        """R14: coexist plans only the router edit; no-line-lost is not applicable, no-dangling checks the linked paths exist"""
        co = self.fixture("cursor", "coexist")
        _, out = self.upd(co, "--adopt", "--mode", "coexist")
        self.assertEqual(grep("^  router|^  adopt|^  conflict", out), 1,
                         "coexist plans exactly one write: the router edit")
        self.assertTrue(has("^  check +no-line-lost +not applicable", out), "no-line-lost is not applicable in coexist")
        self.assertTrue(has("^  check +no-dangling +PASS", out), "no-dangling passes: every linked path exists")
        # Simulate an already-linked coexist run: write the router content this dry run
        # planned, so the .cursorrules link is on record, then take the file away.
        put(os.path.join(co, ".ai", "AGENTS.md"), self.router(co, "coexist") + "\n")
        os.remove(os.path.join(co, ".cursorrules"))
        self.commit(co)
        _, out = self.upd(co, "--adopt", "--mode", "coexist")
        self.assertTrue(has("^  check +no-dangling +FAIL", out), "a missing linked path fails no-dangling in coexist")

    def test_i11_adopt_check_lines(self):
        """I11: --adopt --check prints exactly one of the five lines"""
        n = self.scaffold(self.path("check-none"), "claude")
        self.commit(n)
        rc, out = self.upd(n, "--adopt", "--check")
        self.assertTrue(out.rstrip("\n") == "no foreign structure detected" and rc == 0,
                        "no record, nothing foreign: line 1, exit 0")
        rc, out = self.upd(self.fixture("cursor", "check-undetected"), "--adopt", "--check")
        self.assertTrue(has(r"^foreign structure detected: cursor \(.*file", out) and rc == 1,
                        "no record, foreign structure present: line 3, exit 1")
        g = self.fixture("cursor", "check-good")
        self.plant_record(g, "2000-01-01", "pass", "pass", "sha256:" + sha256(os.path.join(g, ".cursorrules")))
        rc, out = self.upd(g, "--adopt", "--check")
        self.assertTrue(has(r"^adopted 2000-01-01: cursor — up to date; [0-9]+ file\(s\) await cleanup$", out)
                        and rc == 0, "a matching record, both checks pass: line 2, exit 0")
        rg = self.fixture("cursor", "check-regen")
        self.plant_record(rg, "2000-01-01", "pass", "pass", "sha256:" + "0" * 61)
        rc, out = self.upd(rg, "--adopt", "--check")
        self.assertTrue(has("^foreign files regenerated since the adopt of 2000-01-01: .cursorrules", out) and rc == 1,
                        "the source sha no longer matches: line 4, exit 1")
        ic = self.fixture("cursor", "check-incomplete")
        self.plant_record(ic, "2000-01-01", "fail", "pass", "sha256:" + sha256(os.path.join(ic, ".cursorrules")))
        rc, out = self.upd(ic, "--adopt", "--check")
        self.assertTrue(has("^adoption of 2000-01-01 incomplete: no-line-lost FAIL", out) and rc == 1,
                        "a failed check: line 5, exit 1")
        self.assertEqual(self.upd(g, "--check")[0], 0, "the plain --check line is unchanged by any of this (OQ10)")
        cx = self.fixture("cursor", "check-coexist")
        self.plant_record(cx, "2000-01-01", "pass", "pass", "sha256:" + sha256(os.path.join(cx, ".cursorrules")))
        path = os.path.join(cx, ".ai", "reports", "adopt-2000-01-01", "adopt.json")
        doc = read_json(path)
        doc["mode"] = "coexist"
        doc["cleanup"]["offered"] = False
        put(path, json.dumps(doc, indent=2) + "\n")
        rc, out = self.upd(cx, "--adopt", "--check")
        self.assertTrue(out.rstrip("\n") == "adopted 2000-01-01: cursor — up to date" and rc == 0,
                        "a coexist record offers no cleanup (R14)")

    def test_r5_apply_refuses_until_ready(self):
        """R5: --adopt --apply refuses, exit 5, until the project is ready"""
        na = self.path("no-ai")
        put(os.path.join(na, ".cursorrules"), "Use tabs.\n")
        self.commit(na)
        self.assert_refused(na, "no .ai/")
        ng = self.fixture("cursor", "no-git")
        shutil.rmtree(os.path.join(ng, ".git"))
        self.assert_refused(ng, "not a git work tree")
        dt = self.fixture("cursor", "dirty")
        put(os.path.join(dt, "notes.txt"), "wip\n")
        self.assert_refused(dt, "an untracked file outside the record")
        tf = self.fixture("cursor", "task")
        put(os.path.join(tf, ".ai", "state", "current.json"), '{"task_id":"T-1","current_stage":"plan"}\n')
        self.assert_refused(tf, "a task in flight")
        bh = self.fixture("cursor", "behind")
        os.remove(os.path.join(bh, ".ai", "policies", "security.md"))
        self.commit(bh)
        self.assert_refused(bh, "the project behind the plugin")
        rc, out = self.upd(self.fixture("large-claude-md", "split-apply"), "--adopt", "--apply")
        self.assertTrue(rc == 4 and has("^ADOPT_INCOMPLETE: .*CLAUDE.md: a split needs a proposal", first(out)),
                        "a split candidate with no proposal exits 4 and writes nothing (R8)\n" + out)

    def test_r6_r15_apply_once_keep_originals(self):  # pylint: disable=too-many-statements
        """R6, R15: apply once, keep the originals, and a second run changes nothing"""
        a = self.fixture("speckit", "applied")
        # Spec Kit's .gemini/commands/ makes the project declare Gemini, so the plain
        # update is pending first — R5 refuses until it is applied, as a user would.
        self.assert_refused(a, "Spec Kit's .gemini/ declares a runtime the project has not scaffolded yet")
        self.upd(a, "--apply")
        self.commit(a, "plain update")
        spec = os.path.join(a, "specs", "001-user-auth", "spec.md")
        os.chmod(spec, 0o640)
        filler = "r" * 1048577
        put(os.path.join(a, "specs", "001-user-auth", "research.md"),
            "\n".join(filler[i:i + 80] for i in range(0, len(filler), 80)))       # fold -w 80
        self.commit(a)
        rc, out = self.upd(a, "--adopt", "--apply")
        self.assertEqual(rc, 0, "speckit applies, exit 0\n" + out)
        rec = one(os.path.join(a, ".ai", "reports", "adopt-*"))
        original = os.path.join(rec, "original", "specs", "001-user-auth", "spec.md")
        self.assertTrue(os.path.isfile(original) and os.stat(original).st_mode & 0o777 == 0o640,
                        "the original is kept with its mode")
        self.assertTrue(os.path.isfile(os.path.join(rec, "original", "docs", "sdlc", "constitution.md")),
                        "the project file this run rewrites (constitution.md) is kept too")
        self.assertTrue(not os.path.lexists(os.path.join(rec, "original", "specs", "001-user-auth", "research.md"))
                        and "skipped (git has them): specs/001-user-auth/research.md" in out,
                        "a file over 1 MiB is not copied, and says so")
        doc = read_json(os.path.join(rec, "adopt.json"))
        self.assertTrue((doc.get("original_skipped") or [None])[0] == "specs/001-user-auth/research.md"
                        and doc.get("original_bytes", 0) > 0, "adopt.json records the bytes kept and the file skipped")
        self.assertTrue(doc.get("status") == "applied" and len(doc["checks"]["no_line_lost"].get("checked_at") or "") > 0,
                        "the checks ran on disk and are timestamped (R12)")
        dropped = os.path.join(rec, "dropped.jsonl")
        self.assertTrue(os.path.getsize(os.path.join(rec, "report.md")) > 0 and os.path.isfile(dropped)
                        and raw(dropped).count(b"\n") > 0, "report.md and dropped.jsonl are written")
        self.assertFalse(os.path.lexists(os.path.join(rec, "migration.json")), "no migration.json under adopt-*")
        self.assertEqual(self.upd(a, "--check")[0], 0, "plain --check exits 0 right after the apply")
        self.commit(a, "adopted")
        before = tree_sha(a)
        _, out = self.upd(a, "--adopt")
        self.assertTrue(has("^0 automatic", out) and tree_sha(a) == before,
                        "a second --adopt plans nothing and writes nothing\n" + out)
        _, out = self.upd(a)
        self.assertFalse(has("^  conflict  .ai/AGENTS.md", out), "the plain dry run keeps the router rows as project edits")
        put(spec, "extra\n", "a")
        self.commit(a, "regen")
        rc, out = self.upd(a, "--adopt", "--check")
        self.assertTrue(has("^foreign files regenerated since the adopt of .*specs/001-user-auth/spec.md", out) and rc == 1,
                        "a changed source makes --adopt --check say regenerated (R16)\n" + out)
        self.assertTrue(has("^  hint      foreign files regenerated", self.upd(a)[1]),
                        "and the plain dry run carries it as a hint (D5)")
        _, out = self.upd(a, "--adopt")
        self.assertTrue(has(r"^  check +no-line-lost +FAIL: 1 line\(s\): specs/001-user-auth/spec.md:[0-9]+$", out),
                        "F9: the conflicted destination's lines count, so only the new line is named lost\n" + out)
        rc, out = self.upd(a, "--adopt", "--cleanup")
        self.assertTrue(rc == 5 and "restore the adopted version from git" in out
                        and "run /project-update --adopt --apply again" not in out,
                        "F9: cleanup on a changed source gives a way out, not another --apply\n" + out)
        self.assertTrue(has("^  hint      foreign structure detected: cursor", self.upd(self.plain("cursor"))[1]),
                        "an un-adopted foreign structure is a hint in the plain dry run (D5)")

    def test_r15_interrupted_apply_resumes(self):
        """R15: an interrupted apply resumes, and only its own writes count as allowed dirt"""
        for phase in (1, 2):
            i = self.fixture("cursor", "interrupt-%d" % phase)
            rc, out = self.upd(i, "--adopt", "--apply", CLAUDE_AGENTIC_TEST="1", ADOPT_STOP_AFTER=str(phase))
            with self.subTest(Template("stopped after phase $phase: exit 3, the record says partial")
                              .substitute(phase=phase)):
                self.assertTrue(rc == 3 and self.record(i).get("status") == "partial", "rc=%d\n%s" % (rc, out))
            _, out = self.upd(i, "--adopt", "--check")
            with self.subTest("--adopt --check calls it incomplete", phase=phase):
                self.assertIn("incomplete: the apply was interrupted", out)
            rc, out = self.upd(i, "--adopt", "--apply")
            with self.subTest("the re-run completes past the clean-tree gate and passes both checks", phase=phase):
                self.assertTrue(rc == 0 and self.record(i).get("status") == "applied"
                                and has("^  check +no-line-lost +PASS", out), "rc=%d\n%s" % (rc, out))
        i = self.fixture("cursor", "interrupt-dirty")
        self.upd(i, "--adopt", "--apply", CLAUDE_AGENTIC_TEST="1", ADOPT_STOP_AFTER="1")
        put(os.path.join(i, "notes.txt"), "wip\n")
        self.assert_refused(i, "a dirty path that is not a planned destination, while resuming")
        g = self.fixture("cursor", "stop-switch")
        self.plant_record(g, "2000-01-01", "pass", "pass", "sha256:" + sha256(os.path.join(g, ".cursorrules")))
        self.upd(g, "--adopt", "--apply", merge=True, ADOPT_STOP_AFTER="1")
        self.assertTrue(os.listdir(os.path.join(g, ".ai", "reports")),
                        "without CLAUDE_AGENTIC_TEST the stop switch is ignored")

    def test_r14_coexist_apply_writes_only_the_router(self):
        """R14: coexist --apply writes only the router rows and the record"""
        ca = self.fixture("cursor", "coexist-apply")
        rc, out = self.upd(ca, "--adopt", "--apply", "--mode", "coexist")
        status = self.git(ca, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
        changed = sorted(l.split()[1] for l in status if not l.split()[1].startswith(".ai/reports/adopt-"))
        with self.subTest("coexist changed only .ai/AGENTS.md (and its record)"):
            self.assertTrue(rc == 0 and changed == [".ai/AGENTS.md"], "rc=%d changed: %s\n%s" % (rc, changed, out))
        self.assertIn("(kept in place; its globs are not applied by this runtime)", body(os.path.join(ca, ".ai", "AGENTS.md")),
                      "its rows say the files are kept in place")

    def test_r7_r8_split_request_fallback_decision(self):
        """R7, R8: the instruction-file split — request, fallback, proposal, diff"""
        sq = self.fixture("large-claude-md", "split-request")
        before = files_of(sq)
        rc, out = self.upd(sq, "--adopt", "--split-request")
        requests = glob.glob(os.path.join(sq, ".ai", "reports", "adopt-*", "split-request.json"))
        after = [f for f in files_of(sq) if not f.endswith("/split-request.json")]
        dirt = [l for l in self.git(sq, "status", "--porcelain").stdout.splitlines() if not l.startswith("?? .ai/reports/")]
        self.assertTrue(rc == 0 and requests and before == after and not dirt,
                        "--split-request writes split-request.json and nothing else\n" + out)
        req = read_json(requests[0])
        self.assertEqual((req["source"], req["keep_budget_bytes"] > 0, len(req["outline"]) > 0, req["block"][0] > 0),
                         ("CLAUDE.md", True, True, True), "the request has the outline, the block and the keep budget")
        self.assertNotIn("Money is an integer", body(requests[0]), "and no line of body text")
        self.proposal(sq, "CLAUDE.md")
        self.commit(sq)
        prop = one(os.path.join(sq, ".ai", "reports", "adopt-*", "split-proposal.json"))
        mtime = os.stat(prop).st_mtime_ns
        _, out = self.upd(sq, "--adopt", "--split-request")
        self.assertTrue("a proposal for this sha exists, reused" in out and os.stat(prop).st_mtime_ns == mtime,
                        "a matching proposal is reused, not re-requested (mtime unchanged)\n" + out)

        fb = self.fixture("large-claude-md", "split-fallback")
        rc, out = self.upd(fb, "--adopt", "--split", "fallback")
        self.assertTrue(rc == 0 and has(r"^  adopt     CLAUDE.md -> .ai/policies/adopted/claude-md.md .*split \(fallback\)",
                                        out),
                        "--split fallback plans every line to .ai/policies/adopted/claude-md.md\n" + out)
        rc, out = self.upd(fb, "--adopt", "--apply", "--split", "fallback")
        self.assertTrue(rc == 0 and has("^  check +no-line-lost +PASS", out) and has("^  check +no-dangling +PASS", out),
                        "the fallback applies with both checks PASS\n" + out)
        self.assertEqual(grep(r"^\| .* \| policies/adopted/ \|$", body(os.path.join(fb, ".ai", "AGENTS.md"))), 1,
                         "and one router row")
        self.assertEqual(self.upd(fb, "--check", "--budget")[0], 0, "the split CLAUDE.md is within the skeleton budget")
        self.assertTrue("Money is an integer number of cents" in body(os.path.join(fb, ".ai", "policies", "adopted",
                                                                                   "claude-md.md"))
                        and "Money is an integer" not in body(os.path.join(fb, "CLAUDE.md")),
                        "the notes moved verbatim, out of CLAUDE.md")
        doc = self.record(fb)
        self.assertTrue([s.get("cleanup") for s in doc["sources"] if s.get("path") == "CLAUDE.md"] == [False]
                        and doc["split"]["CLAUDE.md"]["by"] == "fallback",
                        "the instruction file is recorded, split by fallback, never for cleanup (R17)")
        df = self.fixture("large-claude-md", "split-decided")
        put(os.path.join(df, ".ai", "reports", "adopt-2000-01-01", "decisions.json"), '{"version":1,"split":"fallback"}\n')
        self.commit(df)
        rc, out = self.upd(df, "--adopt")
        self.assertTrue(rc == 0 and "split (fallback)" in out, FALLBACK_CASE.replace('\\"', '"') + "\n" + out)
        rc, out = self.upd(df, "--adopt", "--split", "proposal")
        self.assertTrue(rc == 4 and "no split-proposal.json matches" in first(out),
                        "--split proposal with no proposal exits 4\n" + out)

    def test_r7_r8_split_by_proposal(self):  # pylint: disable=too-many-locals
        """R7, R8: a proposal splits CLAUDE.md and AGENTS.md onto the same destinations"""
        dests = {}
        for name, f in (("CLAUDE.md", "large-claude-md"), ("AGENTS.md", "large-agents-md")):
            s = self.fixture(f, "split-" + f)
            self.proposal(s, name)
            self.commit(s)
            rc, out = self.upd(s, "--adopt", "--diff")
            with self.subTest(Template("$f: --diff prints ---/+++ for each target").substitute(f=f)):
                self.assertTrue(rc == 0 and grep(r"^\+\+\+ b/", out) == grep("^--- a/", out)
                                and has(r"^\+\+\+ b/%s$" % re.escape(name), out)
                                and has(r"^\+\+\+ b/.ai/rules/payment.md$", out), out)
            rc, out = self.upd(s, "--adopt", "--apply")
            with self.subTest(Template("$f: the proposal applies, both checks PASS").substitute(f=f)):
                self.assertTrue(rc == 0 and has("^  check +no-line-lost +PASS", out), out)
            dests[f] = sorted(m.group(1) for m in re.finditer(r"^  adopt     %s -> ([^ ]+) .*$" % re.escape(name), out,
                                                               re.M) if m.group(1) != name)
            with self.subTest(Template("$f: $name is within the skeleton budget after the split")
                              .substitute(f=f, name=name)):
                self.assertEqual(self.upd(s, "--check", "--budget")[0], 0)
            with self.subTest(Template("$f: and the project is current").substitute(f=f)):
                self.assertEqual(self.upd(s, "--check")[0], 0)
            with self.subTest(Template("$f: the payment rule has dirs and renders into src/Payment/$name")
                              .substitute(f=f, name=name)):
                self.assertTrue("dirs: [src/Payment]" in lines_of(os.path.join(s, ".ai", "rules", "payment.md"))
                                and "declined card" in body(os.path.join(s, "src", "Payment", name)))
            with self.subTest(Template("$f: an outline heading is used once, not repeated").substitute(f=f)):
                self.assertEqual(lines_of(os.path.join(s, ".ai", "policies", "adopted", "conventions.md"))
                                 .count("## Conventions"), 1)
            with self.subTest(Template("$f: overview.md gets its lines under a generated heading").substitute(f=f)):
                self.assertIn("takes orders and payments", body(os.path.join(s, ".ai", "project", "overview.md")))
            with self.subTest(Template("$f: no-line-added is recorded PASS (R9)").substitute(f=f)):
                self.assertEqual(self.record(s)["checks"]["no_line_added"]["status"], "pass")
            self.commit(s, "split")
            _, out = self.upd(s, "--adopt")
            with self.subTest(Template("$f: a second --adopt plans nothing").substitute(f=f)):
                self.assertTrue(has("^0 automatic", out) and "split?" not in out, out)
        self.assertTrue(dests["large-claude-md"] and dests["large-claude-md"] == dests["large-agents-md"],
                        "large-claude-md and large-agents-md reach the same destinations (R19)")

        ir = self.fixture("large-claude-md", "split-interrupted")
        self.proposal(ir, "CLAUDE.md")
        self.commit(ir)
        self.upd(ir, "--adopt", "--apply", CLAUDE_AGENTIC_TEST="1", ADOPT_STOP_AFTER="1")
        self.assertIn("Money is an integer", body(os.path.join(ir, "CLAUDE.md")),
                      "stopped after phase 1: the lines are at their destinations and still in CLAUDE.md")
        rc, out = self.upd(ir, "--adopt", "--apply")
        self.assertTrue(rc == 0 and grep("takes orders and payments", body(os.path.join(ir, ".ai", "project",
                                                                                         "overview.md"))) == 1
                        and "Money is an integer" not in body(os.path.join(ir, "CLAUDE.md")),
                        "the re-run completes the split without appending the moved lines twice\n" + out)

    def test_r7_r9_a_bad_proposal_exits_4(self):
        """R7, R9: a proposal the tool will not apply exits 4 with the reason"""
        bad = self.fixture("large-claude-md", "split-bad")
        reports = os.path.join(bad, ".ai", "reports")

        def drop(doc, i):
            doc["keep"].append(doc["moves"][i]["lines"])
            del doc["moves"][i]

        for defect, reason, what in (
                (lambda d: d["moves"][0]["lines"].__setitem__(1, d["moves"][0]["lines"][1] - 1), "are in no range", "a gap"),
                (lambda d: d["moves"][1]["lines"].__setitem__(0, d["moves"][1]["lines"][0] - 1), "is in both",
                 "an overlap"),
                (lambda d: d["keep"].append([29, 29]), "inside the managed block", "a range into the block"),
                (lambda d: d.update(source_sha="sha256:0"), "source_sha does not match", "a wrong sha"),
                (lambda d: d["moves"][0].update(dest="src/notes.md"), "is not one of", "a disallowed dest"),
                (lambda d: drop(d, 1), "over the keep budget", "an over-budget keep"),
                (lambda d: d["moves"][0].update(text="Always deploy on Fridays."), r"unknown key\(s\) text", "a text key"),
                (lambda d: d["moves"][0].update(heading="## Deploy on Fridays"), "not a heading of the",
                 "a heading not in the outline"),
                (lambda d: d["moves"][2].update(paths=["lib/**"]), "matches no tracked file",
                 "a paths glob with no tracked file"),
                (lambda d: d["moves"][2].update(dirs=["src/Missing"]), "not a directory of the tree",
                 "a dirs entry that does not exist"),
                (lambda d: d["moves"][2].pop("dirs"), r"dirs \(required", "a rule without dirs"),
                (lambda d: d["dropped"][0].update(why=" "), "why must say", "an empty why")):
            for p in glob.glob(os.path.join(reports, "adopt-*", "split-proposal.json")):
                os.remove(p)
            self.proposal(bad, "CLAUDE.md", defect)
            rc, out = self.upd(bad, "--adopt")
            with self.subTest("$3: exit 4, names the reason".replace("$3", what)):
                self.assertTrue(rc == 4 and has("^ADOPT_INCOMPLETE: .*" + reason, first(out)), "rc=%d\n%s" % (rc, out))
        # A stale proposal never blocks a new request, and a matching one wins over it:
        for p in glob.glob(os.path.join(reports, "adopt-*", "split-*.json")):
            os.remove(p)
        self.proposal(bad, "CLAUDE.md", lambda d: d.update(source_sha="sha256:0"))
        _, out = self.upd(bad, "--adopt", "--split-request")
        self.assertIn("request written", out, "a stale proposal does not stop a new --split-request")
        os.makedirs(os.path.join(reports, "adopt-2000-01-01"))
        os.rename(os.path.join(reports, "adopt-" + today(), "split-proposal.json"),
                  os.path.join(reports, "adopt-2000-01-01", "split-proposal.json"))
        self.proposal(bad, "CLAUDE.md")
        rc, out = self.upd(bad, "--adopt")
        self.assertTrue(rc == 0 and "split (proposal)" in out, "the matching proposal wins over the stale one\n" + out)
        shutil.rmtree(os.path.join(reports, "adopt-2000-01-01"))
        for p in glob.glob(os.path.join(reports, "adopt-*", "split-proposal.json")):
            os.remove(p)
        self.proposal(bad, "CLAUDE.md")
        rc, out = self.py(ADDED, bad)
        self.assertTrue(rc == 4 and has("no-line-added FAIL: .* come from no source: .ai/project/overview.md:", first(out)),
                        "a destination line that comes from no source fails R9, exit 4\n" + out)

    def test_wp3_r13_edited_block_through_the_split(self):
        """WP3 R13's case: a hand-edited block goes through the split and ends as the shipped block"""
        he = self.fixture("large-claude-md", "split-edited")
        claude = os.path.join(he, "CLAUDE.md")
        put(claude, re.sub(r"(?m)^<!-- riskrails:end -->$",
                           "- Our own rule, written into the block by hand.\n<!-- riskrails:end -->", body(claude)))
        self.commit(he)
        rc, out = self.upd(he, "--adopt", "--apply", "--split", "fallback")
        shipped = self.py('import update; print(update.shipped_block("claude"))')[1].rstrip("\n")
        block = self.py("import render_instructions as r; print(r.block_of(open(sys.argv[1]).read()))", claude)[1]
        self.assertTrue(rc == 0 and block.rstrip("\n") == shipped, "the edited block is replaced by the shipped one\n" + out)
        self.assertIn("Our own rule, written into the block by hand",
                      body(os.path.join(he, ".ai", "policies", "adopted", "claude-md.md")),
                      "and the hand-written line moved with the rest, not lost")
        self.assertTrue(os.path.isfile(os.path.join(one(os.path.join(he, ".ai", "reports", "adopt-*")), "original",
                                                    "CLAUDE.md")), "the original CLAUDE.md is kept")

    def test_r13_r14_cleanup(self):  # pylint: disable=too-many-locals
        """R13, R14: cleanup deletes only after both checks hold again and a human confirms"""
        cl = self.cleaned("cleanup")
        before = tree_sha(cl)
        rc, out = self.upd(cl, "--adopt", "--cleanup")
        want = sorted(s["path"] for s in self.record(cl)["sources"] if s.get("cleanup"))
        got = sorted(l.split()[1] for l in out.splitlines() if l.split()[:1] == ["delete?"])
        self.assertTrue(rc == 0 and want and got == want and tree_sha(cl) == before,
                        "the cleanup dry run lists exactly the cleanup: true sources and writes nothing\n" + out)
        self.assertTrue(has(r"^  check +no-dangling +PASS \(recomputed", out), "both checks are recomputed for the listing")
        rc, out = self.upd(cl, "--adopt", "--cleanup", "--apply", merge=True)
        self.assertEqual(rc, 2, "--cleanup --apply without --confirm-delete is a usage error\n" + out)
        rc, out = self.upd(cl, "--adopt", "--cleanup", "--apply", "--confirm-delete", "tester")
        self.assertTrue(rc == 5 and first(out).startswith("ADOPT_REFUSED") and tree_sha(cl) == before,
                        "--confirm-delete with no terminal and no AI_UNATTENDED: exit 5, nothing removed\n" + out)
        rc, out = self.confirm(cl, CLAUDECODE="1")
        rec = one(os.path.join(cl, ".ai", "reports", "adopt-*"))
        gone = sum(not os.path.lexists(os.path.join(cl, f)) for f in want)
        kept = sum(os.path.isfile(os.path.join(rec, "original", f)) for f in want)
        self.assertTrue(rc == 0 and gone == len(want), "AI_UNATTENDED=1: every listed file is deleted\n" + out)
        self.assertEqual(kept, len(want), "and original/ still holds every one of them")
        cleanup = read_json(os.path.join(rec, "adopt.json"))["cleanup"]
        self.assertTrue(cleanup.get("unattended") is True and cleanup.get("confirmed_by") == "tester"
                        and cleanup.get("tty") is False and len(cleanup.get("at") or "") > 0,
                        "adopt.json.cleanup records who, when, unattended and tty")
        self.assertEqual(cleanup.get("via"), "unattended",
                         "and via: unattended — AI_UNATTENDED passed the gate inside an agent session")
        self.assertTrue("deleted unattended" in body(os.path.join(rec, "report.md")) and "(deleted unattended)" in out,
                        "report.md and the output say deleted unattended")
        self.assertTrue(not os.path.isdir(os.path.join(cl, ".cursor", "rules"))
                        and os.path.isfile(os.path.join(cl, ".cursor", "mcp.json")),
                        "a directory left empty inside the tool's roots goes with its files; an ignored file keeps its own")
        self.assertFalse([f for _, _, files in os.walk(os.path.join(cl, ".ai", "reports")) for f in files
                          if f == "migration.json"], "cleanup writes no migration.json")
        self.commit(cl, "cleanup")
        rc, out = self.upd(cl, "--adopt", "--check")
        self.assertTrue(rc == 0 and has("^adopted [0-9-]+: cursor — up to date$", out),
                        "--adopt --check after cleanup says up to date\n" + out)
        self.git(cl, "checkout", "-q", "HEAD~1", "--", ".cursorrules")
        rc, out = self.upd(cl, "--adopt", "--check")
        self.assertTrue(rc == 1 and has(r"^foreign files regenerated since the adopt of .*\.cursorrules", out),
                        "a .cursorrules that reappears byte for byte says regenerated (R16)\n" + out)

    def test_f3_an_agent_session_cannot_confirm(self):
        """F3: an agent session cannot pass --confirm-delete, even with a terminal"""
        if not self.has_pty():
            self.skipTest("no pty here (script -qec gives no terminal): the F3 terminal cases did not run")
        tt = self.cleaned("cleanup-tty")
        before = tree_sha(tt)
        cleanup = [sys.executable, "-I", UPDATE, tt, "--adopt", "--cleanup", "--apply", "--confirm-delete", "tester"]
        rc, out = self.pty(["env", "CLAUDECODE=1"] + cleanup)
        self.assertTrue(rc == 5 and token(out) == "ADOPT_REFUSED" and tree_sha(tt) == before and "CLAUDECODE" in out,
                        "CLAUDECODE=1 with a terminal: exit 5, ADOPT_REFUSED names CLAUDECODE, nothing removed\n" + out)
        rc, out = self.pty(["env", "CODEX_THREAD_ID=x"] + cleanup)
        self.assertTrue(rc == 5 and token(out) == "ADOPT_REFUSED" and tree_sha(tt) == before
                        and "CODEX_THREAD_ID" in out,
                        "CODEX_THREAD_ID alone with a terminal: exit 5, names it, nothing removed\n" + out)
        # adopt.py stands alone: its own gate says no under a marker, whatever stdin is.
        gate = lambda marker, code: self.pty(["env"] + marker + [  # noqa: E731
            sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); import adopt; %s" % (PU, code)])[1].strip()
        self.assertEqual(gate(["CODEX_SANDBOX="], "print(adopt.human_gate()[0])"), "False",
                         "adopt.human_gate() refuses an empty-valued marker under a terminal")
        out = gate(["CODEX_VERSION=0.1"], "g = adopt.human_gate(); print(g[0], g[2])")
        self.assertTrue(out.split(" ", 1)[0] == "False" and "(CODEX_VERSION is set)" in out,
                        "adopt.human_gate() refuses CODEX_VERSION alone: 'is set'")
        self.assertIn("(CLAUDECODE, CODEX_CI are set)", gate(["CLAUDECODE=1", "CODEX_CI=1"], "print(adopt.human_gate()[2])"),
                      "two markers: the refusal names both and says 'are set'")
        rc, out = self.pty(cleanup)
        self.assertTrue(rc == 0 and not os.path.lexists(os.path.join(tt, ".cursorrules")),
                        "a terminal and no marker: the cleanup runs\n" + out)
        record = self.record(tt)["cleanup"]
        self.assertTrue(record.get("via") == "terminal" and record.get("unattended") is False and record.get("tty") is True,
                        "and adopt.json.cleanup says via: terminal, unattended: false, tty: true")

    def test_cleanup_refusals(self):
        """a cleanup on a later day, and every reason a cleanup is refused"""
        ld = self.cleaned("cleanup-later")
        reports = os.path.join(ld, ".ai", "reports")
        dirs = len([d for d in os.listdir(reports) if d.startswith("adopt-")])
        rc, out = self.confirm(ld, CLAUDE_AGENTIC_TEST="1", ADOPT_TODAY="2099-01-01")
        self.assertTrue(rc == 0 and not os.path.lexists(os.path.join(reports, "adopt-2099-01-01"))
                        and len([d for d in os.listdir(reports) if d.startswith("adopt-")]) == dirs
                        and len(self.record(ld)["cleanup"].get("deleted") or []) > 0,
                        "a cleanup on a later day writes into the adopt's own directory, none new\n" + out)

        r = self.cleaned("cleanup-changed")
        put(os.path.join(r, ".cursorrules"), "Use spaces.\n", "a")
        self.commit(r)
        self.assert_cleanup_refused(r, "a source changed after adopt")
        r = self.cleaned("cleanup-task")
        put(os.path.join(r, ".ai", "state", "current.json"),
            '{"task_id":"T-1","current_stage":"plan"}\n')   # the stage-plan task of the R5 case
        self.assert_cleanup_refused(r, "a task in flight at stage plan")
        r = self.cleaned("cleanup-dirty")
        put(os.path.join(r, "notes.txt"), "wip\n")
        self.assert_cleanup_refused(r, "an untracked file anywhere in the tree")
        r = self.fixture("cursor", "cleanup-uncommitted")
        self.upd(r, "--adopt", "--apply")
        self.assert_cleanup_refused(r, "the adopt itself not yet committed")
        r = self.cleaned("cleanup-stale")
        put(os.path.join(r, "docs", "sdlc", "specs", "notes.md"), "Read .cursorrules before you start.\n")
        self.commit(r)
        _, out = self.confirm(r)
        self.assert_cleanup_refused(r, "a stale reference planted after adopt")
        self.assertIn("no-dangling FAIL", first(out), "and the refusal names no-dangling")
        r = self.fixture("cursor", "cleanup-coexist")
        self.upd(r, "--adopt", "--apply", "--mode", "coexist")
        self.commit(r)
        rc, out = self.upd(r, "--adopt", "--cleanup")
        self.assertTrue(rc == 5 and first(out).startswith("ADOPT_REFUSED: coexist keeps the foreign files"),
                        "coexist cleanup: exit 5, coexist keeps the foreign files (R14)\n" + out)
        self.assert_cleanup_refused(r, "coexist, even confirmed")

    def test_speckit_cleanup(self):
        """Spec Kit's cleanup: its .claude/ commands go, the instruction files never"""
        sk = self.fixture("speckit", "cleanup-speckit")
        # A skill that ships more than its SKILL.md: the nested directory must go too.
        put(os.path.join(sk, ".claude", "skills", "speckit-plan", "scripts", "helper.sh"), "echo plan\n")
        self.commit(sk, "nested skill file")
        self.upd(sk, "--apply")
        self.commit(sk, "plain update")
        self.upd(sk, "--adopt", "--apply")
        self.commit(sk, "adopted")
        rc, out = self.upd(sk, "--adopt", "--cleanup")
        self.assertTrue(rc == 0 and has(r"^  delete\? +\.claude/commands/speckit", out)
                        and not has(r"^  delete\? +(CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.junie/guidelines\.md) ", out),
                        "Spec Kit's .claude/ commands are listed, the instruction files never (R17)\n" + out)
        rc, out = self.confirm(sk)
        self.assertTrue(rc == 0 and not os.path.lexists(os.path.join(sk, ".specify"))
                        and os.path.isfile(os.path.join(sk, "CLAUDE.md")) and os.path.isdir(os.path.join(sk, ".claude")),
                        "with no task in flight they are deleted; .specify/ goes, CLAUDE.md and .claude/ stay\n" + out)
        self.assertTrue(not os.path.lexists(os.path.join(sk, ".claude", "skills", "speckit-plan"))
                        and os.path.isdir(os.path.join(sk, ".claude", "skills")),
                        "the emptied .claude/skills/speckit-plan/ goes with its files, scripts/ included; "
                        ".claude/skills/ stays")
        self.assertFalse(any("Run `/project-update --adopt --cleanup` to review" in body(p)
                             for p in glob.glob(os.path.join(sk, ".ai", "reports", "adopt-*", "report.md"))),
                         "after the cleanup report.md no longer invites a review")

    def test_confirmer_name_and_stale_task_dir(self):
        """the confirmer's name is a name, and a stale task directory is explained"""
        ph = self.cleaned("placeholder")
        before = tree_sha(ph)
        for name in ("<your name>", "  <name>  ", "Your Name"):
            rc, out = self.confirm(ph, name=name, merge=True)
            with self.subTest(Template("--confirm-delete '$name' is refused as a placeholder, nothing removed")
                              .substitute(name=name)):
                self.assertTrue(rc == 2 and "placeholder" in out and tree_sha(ph) == before, "rc=%d\n%s" % (rc, out))
        _, real = self.py(PLACEHOLDERS, "Ana Your-Name", "I prefer your name convention", "O<Brien", "Ivan Kakurov")
        self.assertEqual(real.strip(), "", "a real name that merely contains the words is not a placeholder")
        rc, out = self.upd(ph, "--apply", "--confirm-delete", "<your name>", merge=True, AI_UNATTENDED="1")
        self.assertTrue(rc == 2 and "placeholder" in out, "the plain --apply --confirm-delete refuses it too\n" + out)
        td = self.fixture("cursor", "task-dir")
        put(os.path.join(td, ".ai", "reports", "T-2000-01-01-001", "notes.md"), "left behind\n")
        rc, out = self.upd(td, "--adopt", "--apply")
        self.assertTrue(rc == 5 and "leaves its .ai/reports/<task-id>/ untracked" in out,
                        "a stale task report dir: the refusal says why and what to do\n" + out)

    def test_review_cleanup_stays_inside_the_project(self):  # pylint: disable=too-many-locals
        """review: cleanup and decisions never reach outside the project, and never lose what git cannot restore"""
        outside = self.path("outside.txt")
        put(outside, "keep me\n")
        osha = "sha256:" + sha256(outside)

        def source(path, sha):
            return lambda doc: doc["sources"].append({"path": path, "sha": sha, "tool": "cursor", "transform": "copy",
                                                      "cleanup": True})

        r = self.cleaned("forge-parent")
        self.forge(r, source("../outside.txt", osha))
        self.assert_cleanup_refused(r, "an adopt.json source with ../")
        r = self.cleaned("forge-abs")
        self.forge(r, source(outside, osha))
        self.assert_cleanup_refused(r, "an adopt.json source with an absolute path")
        self.assertTrue(os.path.isfile(outside), "and the file outside the project is still there")
        r = self.cleaned("forge-stranger")
        button = os.path.join(r, "src", "components", "Button.tsx")
        self.forge(r, source("src/components/Button.tsx", "sha256:" + sha256(button)))
        self.assert_cleanup_refused(r, "an adopt.json source the mapping does not offer for cleanup")
        self.assertTrue(os.path.isfile(button), "and the project's own source file stays")
        r = self.fixture("cursor", "cleanup-ignored")
        put(os.path.join(r, ".gitignore"), ".cursor/rules/local.mdc\n", "a")
        self.commit(r, "ignore")
        shutil.copy(os.path.join(r, ".cursor", "rules", "testing.mdc"), os.path.join(r, ".cursor", "rules", "local.mdc"))
        self.upd(r, "--adopt", "--apply")
        self.commit(r, "adopted")
        _, out = self.confirm(r)
        self.assert_cleanup_refused(r, "a git-ignored cleanup source")
        self.assertTrue("git does not track" in first(out) and os.path.isfile(os.path.join(r, ".cursor", "rules",
                                                                                          "local.mdc")),
                        "it names the untracked file, which stays\n" + out)
        r = self.cleaned("cleanup-resumed")
        self.forge(r, lambda doc: doc["cleanup"].update(
            {"confirmed_by": "first", "at": "2000-01-01T00:00:00Z", "via": "terminal", "unattended": False, "tty": True,
             "deleted": ["gone-earlier.md"]}))
        self.confirm(r)
        cleanup = self.record(r)["cleanup"]
        history = (cleanup.get("history") or [{}])[0]
        self.assertTrue((cleanup.get("deleted") or [None])[0] == "gone-earlier.md" and history.get("confirmed_by") == "first"
                        and cleanup.get("confirmed_by") == "tester" and history.get("via") == "terminal",
                        "a second cleanup keeps the first one's deletions and who confirmed them")
        report = body(os.path.join(one(os.path.join(r, ".ai", "reports", "adopt-*")), "report.md"))
        self.assertTrue("confirmed by first" in report and "over 2 run(s)" in report,
                        "and report.md names both runs, not only the last")
        r = self.cleaned("forge-nopath")
        self.forge(r, lambda doc: doc["sources"].append({"sha": "sha256:x", "tool": "cursor", "cleanup": False}))
        rc, out = self.upd(r, "--adopt", "--cleanup", merge=True)
        self.assertTrue(rc == 0 and "Traceback" not in out, "a record entry without a path is skipped, not a traceback\n" + out)

        k2 = self.fixture("kiro", "decision-escape")
        put(os.path.join(k2, ".kiro", "hooks", "lint-on-save.json"), '{"hooks": []}\n')
        os.makedirs(os.path.join(k2, ".ai", "reports", "adopt-2000-01-01"))
        self.commit(k2)
        decisions = os.path.join(k2, ".ai", "reports", "adopt-2000-01-01", "decisions.json")
        put(decisions, '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"copy","dest":"../escape.md"}}}\n')
        rc, out = self.upd(k2, "--adopt")
        self.assertTrue(rc == 4 and has("^  unmapped  .kiro/hooks/lint-on-save.json .*not an allowed destination", out),
                        "a decisions.json copy to ../ stays unmapped, exit 4\n" + out)
        rc, out = self.upd(k2, "--adopt", "--apply")
        self.assertTrue(rc == 4 and not os.path.lexists(self.path("escape.md")),
                        "and --apply writes nothing outside the project\n" + out)
        put(decisions, '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"copy",'
                       '"dest":"docs/sdlc/specs/kiro-hooks/lint-on-save.json"}}}\n')
        rc, out = self.upd(k2, "--adopt")
        self.assertTrue(rc == 0 and "lint-on-save.json -> docs/sdlc/specs/kiro-hooks/lint-on-save.json" in out,
                        "a copy under docs/sdlc/specs/ is accepted (I6)\n" + out)

        b = self.fixture("cursor", "broken-decisions")
        put(os.path.join(b, ".ai", "reports", "adopt-2000-01-01", "decisions.json"), '{"version":')
        rc, out = self.upd(b, merge=True)
        self.assertTrue(rc == 0 and "Traceback" not in out and has("^  hint      adopt state unreadable", out),
                        "a truncated decisions.json is a hint in the plain dry run, not a traceback\n" + out)
        rc, out = self.upd(b, "--adopt", "--check", merge=True)
        self.assertTrue(rc == 1 and len(out.rstrip("\n").split("\n")) == 1 and out.startswith("adopt state unreadable"),
                        "and --adopt --check prints one line, exit 1\n" + out)

    def test_own_toolbox_is_left_alone(self):
        """a project's own toolbox (redesign 2.5): setup.py inventories it, --adopt leaves it alone"""
        self.assertEqual(sorted(read_json(os.path.join(PU, "adopt-map.json"))["own"]),
                         ["_doc", "guards", "inventory", "verify"], "adopt-map.json carries the own section")
        o = self.adopt_fixture("new-shop-like", self.path("own toolbox"),
                               fixtures=os.path.join(ROOT, "tests", "fixtures", "setup"))
        rc, out = self.upd(o, "--adopt", merge=True)
        self.assertTrue(rc == 0 and "Traceback" not in out and not has(r"unmapped|\.claude/|bin/", out),
                        "--adopt on the new-shop-like toolbox: the own section is not a foreign tool, nothing unmapped\n"
                        + out)
        rc, out = self.upd(o, "--adopt", "--apply", merge=True)
        self.assertTrue(rc == 0 and os.path.isdir(os.path.join(o, ".claude", "skills", "deploy-staging"))
                        and os.path.isfile(os.path.join(o, "bin", "run-tests.sh"))
                        and not os.path.lexists(os.path.join(o, ".ai", "policies", "toolbox.md")),
                        "--adopt --apply keeps .claude/ and bin/ in place and writes no toolbox.md (setup.py's job)\n" + out)
        dirt = [l for l in self.git(o, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
                if not re.match(r"\?\? \.ai/(reports|state)/", l)]
        self.assertEqual(dirt, [], "and changes no file outside its own record")


if __name__ == "__main__":
    unittest.main()
