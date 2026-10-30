#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Migration 0006: a schema-5 project stops carrying the shared policies, agent
contracts, workflows and templates. The router learns where they live first;
unedited copies are deleted only behind --confirm-delete; edited ones become
overrides; nothing is deleted through a symlink, outside the project, or
while an installed home lacks the shared file it would fall back to; git is
the rollback (T-2026-10-13-004, plan rev 2 Step 7).

Pinned: no real home is ever inspected, and the shared tree is this checkout's.
"""
import glob
import hashlib
import json
import os
import re
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
FIX = os.path.join(ROOT, "tests", "fixtures", "project-update")
OLDS = os.path.join(FIX, "shared-old")
MIG = os.path.join(ROOT, "skills", "project-update", "migrations", "0006_shared_files.py")
TEMPLATE_ROUTER = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "AGENTS.md")
GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]

TWIN_OF = "test-migration-0006.sh"

SHARED = sorted(".ai/" + os.path.relpath(os.path.join(d, f), os.path.join(ROOT, "ai"))
                for d, _, files in os.walk(os.path.join(ROOT, "ai")) for f in files)
# What a schema-5 project carried: the shared set less the two files added to
# the tree after 0006 shipped (redesign 2.3), which no project ever held.
CARRIED = [f for f in SHARED if f not in (".ai/using-riskrails.md", ".ai/workflows.md")]
REPORT = ".ai/reports/project-update-" + time.strftime("%Y-%m-%d", time.gmtime())
ROUTER_ITEM = r"^  (update|merge|conflict)  *\.ai/AGENTS\.md"
# R13 reads `pass "$(basename "$d"): …"` up to its inner quote, so the case it
# records for the per-router labels below is this fragment.
BASENAME = "$(basename "
# The pinned environment every git call runs in, as the shell suite exported HOME before any.
GIT_ENV = {}


def lines(pattern, out):
    """`grep -c`: the lines of out that match."""
    return sum(1 for line in out.splitlines() if re.search(pattern, line))


def has(pattern, out):
    return lines(pattern, out) > 0


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def per(d, text):
    """A per-directory label, as the shell suite wrote it with $(basename "$d")."""
    return text.replace(BASENAME + '"$d")', os.path.basename(d))


def tree_sum(d):
    """Path and sha of every file outside .git."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not (top == d and x == ".git")]
        out += ["%s %s" % (sha(os.path.join(top, f)), os.path.relpath(os.path.join(top, f), d))
                for f in files if os.path.isfile(os.path.join(top, f))]
    return sorted(out)


def tracked(d):
    """Exec bit, sha and path of every file git holds — what the git route restores
    (git keeps the exec bit; the rest of a mode is the umask's)."""
    names = subprocess.run(["git", "-C", d, "ls-files", "-z"], env=GIT_ENV, capture_output=True, text=True,
                           check=True).stdout.split("\0")
    return ["%s %s %s" % ("x" if os.access(os.path.join(d, n), os.X_OK) else "-", sha(os.path.join(d, n)), n)
            for n in names if n]


def present(d):
    return sum(os.path.isfile(os.path.join(d, f)) for f in CARRIED)


def sections(d):
    return read(os.path.join(d, ".ai", "AGENTS.md")).splitlines().count("## Shared files")


def version(d):
    return read(os.path.join(d, ".ai", "VERSION")).strip()


def router_first(out):
    """The router's line comes before the first delete? line."""
    rows = out.splitlines()
    r = next((i for i, l in enumerate(rows) if re.search(r"^  [a-z?]* *\.ai/AGENTS\.md ", l)), None)
    d = next((i for i, l in enumerate(rows) if l.startswith("  delete? ")), None)
    return r is not None and (d is None or r < d)


def git(d, *args):
    subprocess.run(GIT + ["-C", d] + list(args), env=GIT_ENV, check=True, capture_output=True)


def commit(d, message):
    git(d, "add", "-A")
    git(d, "commit", "-qm", message)


ADD_ROWS = """
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import adopt, update as U
plan = U.Plan(sys.argv[1])
assert adopt.add_router_rows(plan, ["| a tool the project adopted | `policies/adopted/x.md` |",
                                    "| the adopted specs | `docs/adopted/` |"]) == 2
open(os.path.join(sys.argv[1], ".ai", "AGENTS.md"), "wb").write(plan.items[-1]["content"])
"""

SWEEP = """
import hashlib, json, os, subprocess, sys
sys.dont_write_bytecode = True
root = os.environ["PLUGIN_ROOT"]
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import update as U
hist = U.HISTORY
index = json.load(open(os.path.join(hist, "index.json")))
history = U.History(hist)
shared = sorted(U.shared_files())
today = {p: open(os.path.join(root, "ai", p[len(".ai/"):]), "rb").read() for p in shared}
shared_keys = {"ai-init/" + p for p in shared}
owned = {h for k, v in index.items() if k not in shared_keys for h in v}
total, unrecorded, blobbed = 0, [], []
for p in shared:
    key = "ai-init/" + p
    known = history.hashes(key)
    total += len(known)
    if not known or known != set(index.get(key, [])) or hashlib.sha256(today[p]).hexdigest() not in known:
        unrecorded.append(p)
    # A shared version keeps its hash and loses its blob, unless a project-owned
    # key ships the same bytes.
    blobbed += ["%s %s" % (p, h[:12]) for h in known - owned if os.path.exists(os.path.join(hist, "blobs", h))]
for p in unrecorded:
    print("FAIL no hash on record (or not today's) for: " + p)
for b in blobbed:
    print("FAIL a blob only a shared key references is still shipped: " + b)

# The byte-level path: the old versions kept as fixtures in shared-old/, then
# today's shared tree, each through build_plan as a project carries them.
proj = os.path.join(os.environ["W"], "sweep")
os.makedirs(proj)
subprocess.run(["bash", os.path.join(root, "skills", "ai-init", "scaffold-ai.sh"), proj, "--runtime", "claude"],
               check=True, stdout=subprocess.DEVNULL)
open(os.path.join(proj, ".ai", "VERSION"), "w").write("5\\n")
old = dict(today)
for p in shared:
    f = os.path.join(os.environ["OLDS"], p[len(".ai/"):])
    if os.path.isfile(f):
        old[p] = open(f, "rb").read()

def put(p, data):
    os.makedirs(os.path.dirname(os.path.join(proj, p)), exist_ok=True)
    open(os.path.join(proj, p), "wb").write(data)

bad, flipped_bad = [], []
for r, carried in enumerate((old, today)):
    for p in shared:
        put(p, carried[p])
    plan = U.build_plan(proj)
    dels = {i["target"] for i in plan.items if i["action"] == "delete?"}
    bad += ["%s r%d" % (p, r) for p in shared if p not in dels]
    for p in shared:
        put(p, carried[p][:-1] + bytes([carried[p][-1] ^ 1]))
    plan = U.build_plan(proj)
    dels = {i["target"] for i in plan.items if i["action"] == "delete?"}
    over = "\\n".join(plan.hints)
    flipped_bad += ["%s r%d" % (p, r) for p in shared if p in dels or "%s overrides" % p not in over]
print("hash sweep: %d keys, %d versions; %d not on record; %d with a blob; bytes: 2 rounds, %d old fixtures; "
      "%d not deleted; flipped: %d not an override"
      % (len(shared), total, len(unrecorded), len(blobbed), sum(old[p] != today[p] for p in shared),
         len(bad), len(flipped_bad)))
for b in bad:
    print("FAIL shipped version not proposed for deletion: " + b)
for b in flipped_bad:
    print("FAIL flipped version not an override: " + b)
"""


class TestMigration0006(unittest.TestCase):  # pylint: disable=too-many-public-methods
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDownClass ends it
        cls.w = cls.tmp.name
        os.makedirs(os.path.join(cls.w, "home"))
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS", "CLAUDE_CONFIG_DIR")
                   and not k.startswith("RISKRAILS_")}
        cls.env.update(HOME=os.path.join(cls.w, "home"), CLAUDE_AGENTIC_SHARED=os.path.join(ROOT, "ai"))
        GIT_ENV.clear()
        GIT_ENV.update(cls.env)
        cls.cur = int(subprocess.run(
            [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import migrations; "
             "print(migrations.CURRENT)", os.path.join(ROOT, "skills", "project-update")],
            env=cls.env, capture_output=True, text=True, check=True).stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- helpers ------------------------------------------------------------

    def run_(self, args, merge=True, cwd=None, **extra):
        env = dict(self.env, **extra)
        done = subprocess.run(args, env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, text=True, check=False)
        return done.returncode, done.stdout

    def upd(self, d, *args, merge=True, **extra):
        return self.run_([sys.executable, "-I", UPDATE, d] + list(args), merge=merge, **extra)

    def confirm(self, d):
        return self.upd(d, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1")

    def path(self, *parts):
        return os.path.join(self.w, *parts)

    def v5_project(self, name, rt="claude"):
        """A committed schema-5 project as the cut-over finds it — today's scaffold, every
        shared file as it was carried, three of them at their oldest shipped version, the
        schema-5 router and VERSION 5."""
        d = self.path(name)
        os.makedirs(d)
        subprocess.run(["bash", SCAFFOLD, d, "--runtime", rt], env=self.env, stdout=subprocess.DEVNULL, check=True)
        shutil.copytree(os.path.join(ROOT, "ai"), os.path.join(d, ".ai"), dirs_exist_ok=True)
        for f in ("using-riskrails.md", "workflows.md"):
            os.remove(os.path.join(d, ".ai", f))
        for f in ("workflows/feature.md", "agents/manager.md", "policies/model-routing.md"):
            shutil.copy(os.path.join(OLDS, f), os.path.join(d, ".ai", f))
        shutil.copy(os.path.join(OLDS, "AGENTS.v5.md"), os.path.join(d, ".ai", "AGENTS.md"))
        shutil.copytree(os.path.join(FIX, "schema-v5", ".ai"), os.path.join(d, ".ai"), dirs_exist_ok=True)
        subprocess.run(["git", "init", "-q", d], env=GIT_ENV, check=True)
        commit(d, "schema 5")
        return d

    def add_rows(self, d):
        """Two rows the way --adopt writes them."""
        subprocess.run([sys.executable, "-I", "-c", ADD_ROWS, d], env=dict(self.env, PLUGIN_ROOT=ROOT), check=True)

    def router(self, d):
        return os.path.join(d, ".ai", "AGENTS.md")

    # -- the cases ----------------------------------------------------------

    def test_the_migration_itself(self):
        self.assertEqual(len(SHARED), 31, "the shared tree holds 31 files")
        mig = read(MIG)
        self.assertFalse(has(r"claude|codex", mig), "0006 names no runtime (L1)")
        # A schema-5 project ends at the plugin's schema, which later migrations raise (0007).
        self.assertGreaterEqual(self.cur, 6, Template("the registry reaches schema 6 or later ($CUR)")
                                .substitute(CUR=self.cur))
        self.assertEqual(read(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "VERSION")).strip(),
                         str(self.cur), "a fresh scaffold starts at the plugin's schema")

    def test_r1_dry_run_gate_and_confirmed_run(self):
        """R1: the shipped schema-5 router; dry run and the gate"""
        cur = str(self.cur)
        r1 = self.v5_project("r1")
        os.chmod(os.path.join(r1, ".ai", "templates", "review-report.md"), 0o755)
        git(r1, "commit", "-qam", "an exec bit to keep")
        before = tree_sum(r1)
        rc, out = self.upd(r1)
        self.assertTrue(rc == 0 and before == tree_sum(r1), "the dry run exits 0 and writes nothing\n" + out)
        self.assertTrue(has("^  schema    5 -> %s " % cur, out), "the dry run names the schema step")
        self.assertEqual(lines(r"^  delete\? ", out), 29, "all 29 shipped copies are proposed, the oldest versions too")
        self.assertTrue(has(r"^  update  *\.ai/AGENTS\.md  *\[0006\] unchanged since it was installed", out),
                        "the shipped router is replaced")
        self.assertFalse(has(r"policies/(safety|security)\.md", out), "safety.md and security.md are never named")
        self.assertFalse(has("commit .ai/ first", out), "a committed .ai/ gets no commit-first hint")
        rc, out = self.upd(r1, "--check", merge=False)
        self.assertTrue(rc == 1 and has(
            "^project is behind the installed plugin: schema 5 -> %s, " % cur +
            r"(.*, )?29 deletion\(s\) a human must confirm, the schema stays at 5 until they are settled"
            r" — run /rr-setup --update$", out), "--check names the deletions and the held schema\n" + out)
        self.upd(r1, "--apply")
        self.assertEqual((version(r1), sections(r1), present(r1)), ("5", 1, 29),
                         "a plain --apply writes the router, deletes nothing and keeps VERSION 5")
        rc, out = self.upd(r1, "--apply", "--confirm-delete", "tester", CLAUDECODE="1")
        self.assertTrue(rc == 5 and present(r1) == 29,
                        "inside an agent session without a terminal --confirm-delete exits 5\n" + out)
        rc, out = self.confirm(r1)
        self.assertTrue(rc == 0 and present(r1) == 0, "the confirmed run deletes all 29\n" + out)
        self.assertEqual(version(r1), cur, Template("and the schema reaches $CUR").substitute(CUR=cur))
        bad = []
        for f in CARRIED:
            shipped = subprocess.run(["git", "-C", r1, "show", "HEAD:" + f], env=GIT_ENV, capture_output=True,
                                     check=False).stdout
            original = os.path.join(r1, REPORT, "original", f)
            if not os.path.isfile(original):
                bad.append(f)
                continue
            with open(original, "rb") as fh:
                if fh.read() != shipped:
                    bad.append(f)
        self.assertEqual(bad, [], "every original is kept byte-identical")
        self.assertEqual(os.stat(os.path.join(r1, REPORT, "original", ".ai", "templates", "review-report.md")).st_mode
                         & 0o777, 0o755, "with its mode")
        rec = json.loads(read(os.path.join(r1, REPORT, "migration.json")))
        self.assertTrue(len(rec["deletions"]) == 29
                        and sorted({x["confirmed_by"] for x in rec["deletions"]}) == ["tester"]
                        and sorted({x["via"] for x in rec["deletions"]}) == ["unattended"]
                        and str(rec["to"]) == cur,
                        "migration.json records each deletion, who confirmed it and how")
        _, out = self.upd(r1)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a second run has nothing to do\n" + out)
        self.assertEqual(self.upd(r1, "--check")[0], 0, Template("--check exits 0 at schema $CUR").substitute(CUR=cur))

        # L5: the empty directories stay, and the shared copy applies
        agents = os.path.join(r1, ".ai", "agents")
        self.assertTrue(os.path.isdir(agents) and not os.listdir(agents), "an empty .ai/agents/ remains")
        _, out = self.run_([os.path.join(ROOT, "scripts", "ai-path"), "agents/manager.md"], merge=False, cwd=r1)
        self.assertEqual(out.strip(), os.path.join(ROOT, "ai", "agents", "manager.md"),
                         "ai-path resolves to the shared copy")

        # M6: a migrated project — a copy that comes back, an edited one
        shutil.copy(os.path.join(ROOT, "ai", "policies", "git.md"), os.path.join(r1, ".ai", "policies", "git.md"))
        write(os.path.join(r1, ".ai", "policies", "tooling.md"),
              read(os.path.join(ROOT, "ai", "policies", "tooling.md")) + "our own rule\n")
        _, out = self.upd(r1)
        self.assertTrue(has(r"^  delete\?  *\.ai/policies/git\.md  *\[shared\] identical to a shipped version", out),
                        "a re-added shipped copy is offered for deletion again\n" + out)
        self.assertEqual(lines("override the plugin.s shared copy and no longer receive its changes: "
                               ".ai/policies/tooling.md", out), 1, "an edited copy is named once, as an override")
        self.assertTrue(has("commit .ai/ first", out), "an uncommitted .ai/ gets the commit-first hint (M4)")
        self.upd(r1, "--apply")
        self.assertTrue(version(r1) == cur and os.path.isfile(os.path.join(r1, ".ai", "policies", "git.md")),
                        Template("VERSION stays $CUR and nothing is deleted unconfirmed").substitute(CUR=cur))
        self.confirm(r1)
        self.assertTrue(not os.path.lexists(os.path.join(r1, ".ai", "policies", "git.md"))
                        and "our own rule" in read(os.path.join(r1, ".ai", "policies", "tooling.md")),
                        "the confirmed run deletes the shipped copy and keeps the override")

    def test_edited_crlf_and_project_only_files(self):
        e = self.v5_project("edited")
        with open(os.path.join(e, ".ai", "policies", "git.md"), "a", encoding="utf-8") as fh:
            fh.write("x")
        bugfix = os.path.join(e, ".ai", "workflows", "bugfix.md")
        with open(bugfix, "rb") as fh:
            data = fh.read()
        *rows, tail = data.split(b"\n")          # sed 's/$/\r/': a CR before every line end
        with open(bugfix, "wb") as fh:
            fh.write(b"".join(r + b"\r\n" for r in rows) + (tail + b"\r" if tail else b""))
        write(os.path.join(e, ".ai", "workflows", "custom.md"), "ours\n")
        os.makedirs(os.path.join(e, ".ai", "policies", "adopted"))
        write(os.path.join(e, ".ai", "policies", "adopted", "x.md"), "adopted\n")
        commit(e, "edits")
        crlf = sha(bugfix)
        _, out = self.upd(e)
        self.assertTrue(has("hint      .ai/policies/git.md overrides the plugin.s shared copy", out),
                        "a one-byte edit is an override\n" + out)
        self.assertEqual(lines(r"^  delete\? ", out), 28, "the other 28 are proposed, the CRLF copy among them")
        self.confirm(e)
        self.assertTrue(os.path.isfile(os.path.join(e, ".ai", "policies", "git.md")) and not os.path.lexists(bugfix),
                        "the edited copy stays; the CRLF copy is deleted (L4)")
        self.assertEqual(sha(os.path.join(e, REPORT, "original", ".ai", "workflows", "bugfix.md")), crlf,
                         "the CRLF original is kept byte-identical")
        self.assertTrue(read(os.path.join(e, ".ai", "workflows", "custom.md")) == "ours\n"
                        and read(os.path.join(e, ".ai", "policies", "adopted", "x.md")) == "adopted\n",
                        "a project-only workflow and an adopted policy are untouched")
        self.assertEqual(version(e), str(self.cur), "an override does not hold the schema")
        _, out = self.upd(e)
        self.assertTrue(has("^0 automatic, 0 conflict", out)
                        and has("no longer receive its changes: .ai/policies/git.md", out),
                        "a second run changes nothing and names the override\n" + out)

    def test_router_fixtures(self):
        """the router fixtures"""
        r2 = self.v5_project("r2")
        self.add_rows(r2)
        r3 = self.v5_project("r3")
        rows = read(self.router(r3)).split("\n")
        last = max(i for i, l in enumerate(rows) if l.startswith("|"))
        rows[last] = re.sub(r" \|$", " (our own wording) |", rows[last])
        write(self.router(r3), "\n".join(rows))
        self.add_rows(r3)
        r4 = self.v5_project("r4")
        write(self.router(r4), re.sub(r"(?m)^## Doing X → read Y$", "## Where to look", read(self.router(r4))))
        r5 = self.v5_project("r5")
        os.remove(self.router(r5))
        for d in (r2, r3, r4, r5):
            commit(d, "router")
        for d in (r2, r3, r4, r5):
            _, out = self.upd(d)
            with self.subTest(per(d, '$(basename "$d"): the router item precedes the first delete?')):
                self.assertTrue(router_first(out), out)
        _, out = self.upd(r5)
        self.assertTrue(has(r"^  create  *\.ai/AGENTS\.md  *\[0006\]", out), "r5: a missing router is created")
        _, out = self.upd(r2)
        self.assertTrue(has("Shared files section added; your router edits kept", out),
                        "r2: an adopted router gets the section inserted")
        for d in (r2, r3, r4, r5):
            self.confirm(d)
            with self.subTest(per(d, '$(basename "$d"): after the confirmed run the section is there exactly once')):
                self.assertEqual((sections(d), present(d), version(d)), (1, 0, str(self.cur)))
        for d in (r2, r3):
            text = read(self.router(d))
            with self.subTest(per(d, '$(basename "$d"): the adopt rows survive')):
                self.assertIn("| a tool the project adopted | `policies/adopted/x.md` |", text)
                self.assertIn("| the adopted specs | `docs/adopted/` |", text)
            rows = text.splitlines()
            with self.subTest(per(d, '$(basename "$d"): the section sits before the routing table')):
                self.assertLess(rows.index("## Shared files"), rows.index("## Doing X → read Y"))
        self.assertTrue(has(r"\(our own wording\) \|$", read(self.router(r3))), "r3: the edited last row survives")
        rows = read(self.router(r4)).splitlines()
        self.assertTrue("## Where to look" in rows
                        and rows.index("## Shared files") > rows.index("## Keeping this directory true"),
                        "r4: with the heading renamed the section is appended, the rename kept")
        _, out = self.upd(r4)
        self.assertTrue(sections(r4) == 1 and not has(ROUTER_ITEM, out),
                        "r4: the next run neither doubles the section nor conflicts\n" + out)

    def test_r7_moved_section(self):
        """R7: a router whose section a human moved is merged around the section"""
        # At schema 6, a human moved the section to the end. The rest of the router is
        # merged without it, so the move is neither doubled nor a conflict.
        r7 = self.v5_project("r7")
        self.confirm(r7)
        t = read(self.router(r7))
        s, e = t.index("\n## Shared files"), t.index("\n## Doing X → read Y")
        write(self.router(r7), t[:s] + t[e:] + t[s:e])
        commit(r7, "section moved")
        moved = read(self.router(r7))
        _, out = self.upd(r7, "--apply")
        self.assertFalse(has(r"^  (update|conflict)  *\.ai/AGENTS\.md", out),
                         "r7: the moved section is neither doubled nor a conflict\n" + out)
        # The section stays where the human put it, at the end: the router is byte-identical.
        ours = read(self.router(r7))
        self.assertEqual(ours.count("\n## Shared files\n"), 1, "r7: one section\n" + ours)
        self.assertEqual(ours, moved, "r7: the human's router is kept, with one section")

    def test_r8_own_non_negotiable_or_edited_last_line(self):
        """R8: a router with its own non-negotiable, or an edited last line, stays quiet after 0006"""
        for kind in ("appended", "edited"):
            d = self.v5_project("r8-" + kind)
            t = read(self.router(d))
            i = t.index("\n\n## Doing X → read Y")
            t = t[:i] + "\n- our own non-negotiable" + t[i:] if kind == "appended" else t[:i] + " (ours)" + t[i:]
            write(self.router(d), t)
            commit(d, kind)
            self.confirm(d)
            with self.subTest(Template("r8-$kind: migrated, one section").substitute(kind=kind)):
                self.assertEqual((sections(d), version(d)), (1, str(self.cur)))
            commit(d, "migrated")
            for run in (1, 2):
                _, out = self.upd(d, "--apply")
                with self.subTest(Template("r8-$kind: run $run after the migration leaves the router alone")
                                  .substitute(kind=kind, run=run)):
                    self.assertFalse(has(ROUTER_ITEM, out), out)

    def test_r10_older_edited_router_gets_later_changes(self):
        """R10: a router edited on an older version receives the plugin's later changes"""
        # The blob is a router the plugin shipped before the schema-5 one; the human
        # added a note to it. The confirmed 0006 run inserts the section and merges
        # the plugin's later router changes in the same pass; nothing stays stale.
        r10 = self.v5_project("r10")
        blob = os.path.join(ROOT, "skills", "project-update", "history", "blobs",
                            "21319ce04158178b1d66ee8514e32c43bb1b4cd9cee11a456a9a863a5998c6ce")
        with open(blob, "rb") as fh, open(self.router(r10), "wb") as out:
            out.write(fh.read() + b"\n## our routing note\nalways ask us first\n")
        commit(r10, "older router, edited")
        self.confirm(r10)
        commit(r10, "migrated")
        strip = lambda t: re.sub(r"(?ms)^## Shared files$.*?(?=^## )", "", t)  # noqa: E731
        ours = read(self.router(r10))
        label = "r10: one section, the note kept, every other line as the plugin ships it"
        self.assertEqual(ours.count("\n## Shared files\n"), 1, label)
        self.assertIn("always ask us first", ours, label)
        self.assertEqual(strip(ours).replace("\n## our routing note\nalways ask us first\n", ""),
                         strip(read(TEMPLATE_ROUTER)), label)
        _, out = self.upd(r10)
        self.assertFalse(has(ROUTER_ITEM, out), "r10: and the run after that is quiet\n" + out)

    def test_r9_edited_crlf_router(self):
        """R9: an edited CRLF router gets the section before the table, in CRLF"""
        r9 = self.v5_project("r9")
        with open(self.router(r9), "rb") as fh:
            t = fh.read()
        i = t.index("\n\n## Doing X → read Y".encode())
        with open(self.router(r9), "wb") as fh:
            fh.write((t[:i] + b"\n- ours" + t[i:]).replace(b"\n", b"\r\n"))
        commit(r9, "crlf")
        self.confirm(r9)
        with open(self.router(r9), "rb") as fh:
            t = fh.read()
        label = "r9: section before the table, line endings all CRLF"
        self.assertEqual(t.count(b"\r\n"), t.count(b"\n"), label + ": mixed endings")
        self.assertEqual(t.count(b"## Shared files\r\n"), 1, label)
        self.assertLess(t.index(b"## Shared files"), t.index("## Doing X → read Y".encode()), label)

    def test_undeclared_files_are_never_deletion_candidates(self):
        """undeclared files in the shared tree are never deletion candidates"""
        x = self.path("extra-tree")
        shutil.copytree(os.path.join(ROOT, "ai"), x)
        templates = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai")
        shutil.copy(os.path.join(templates, "policies", "security.md"), os.path.join(x, "policies", "security.md"))
        shutil.copy(os.path.join(templates, "VERSION"), os.path.join(x, "VERSION"))
        xp = self.v5_project("extra")
        self.confirm(xp)
        commit(xp, "migrated")
        _, out = self.upd(xp, CLAUDE_AGENTIC_SHARED=x)
        self.assertFalse(has(r"^  delete\?  *\.ai/(VERSION|policies/security\.md)", out),
                         "a planted policies/security.md or VERSION is not offered for deletion\n" + out)
        self.assertTrue(has("outside the shared set, ignored", out), "the extra files are named in a hint")
        _, n = self.run_([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import update; "
                          "print(len(update.declared_shared()))", os.path.join(ROOT, "skills", "project-update")],
                         merge=False)
        self.assertEqual(n.strip(), "31", "the declared shared set is 0006's 31")

    def test_r6_symlinked_router_stops_the_run(self):
        """R6: a symlinked router stops the confirmed run before any deletion"""
        r6 = self.v5_project("r6")
        os.rename(self.router(r6), os.path.join(r6, ".ai", "router-real.md"))
        os.symlink("router-real.md", self.router(r6))
        commit(r6, "symlink")
        rc, out = self.confirm(r6)
        self.assertTrue(rc == 3 and has("aborted at update .ai/AGENTS.md", out), "exit 3 at the router item\n" + out)
        self.assertEqual((present(r6), version(r6)), (29, "5"), "every shared copy is still there, VERSION 5")

    def test_q5_gemini_keeps_safety_and_security(self):
        """Q5: a Gemini project keeps safety.md and security.md"""
        gm = self.v5_project("gemini", "gemini")
        _, out = self.upd(gm)
        self.assertFalse(has(r"policies/(safety|security)\.md", out), "gemini: neither is named")
        self.confirm(gm)
        self.assertTrue(os.path.isfile(os.path.join(gm, ".ai", "policies", "safety.md"))
                        and os.path.isfile(os.path.join(gm, ".ai", "policies", "security.md")) and present(gm) == 0,
                        "gemini: both remain after the confirmed run, the shared copies are gone")

    def test_m2_no_deletion_while_a_fallback_is_missing(self):
        """M2: no deletion while a fallback is missing"""
        m2 = self.v5_project("m2")
        before = tree_sum(m2)
        rc, out = self.upd(m2, CLAUDE_AGENTIC_SHARED="/nonexistent")
        self.assertTrue(rc == 2 and before == tree_sum(m2), "no shared tree: exit 2, nothing written\n" + out)
        rc, out = self.upd(m2, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1",
                           CLAUDE_AGENTIC_SHARED="/nonexistent")
        self.assertTrue(rc == 2 and before == tree_sum(m2), "and the confirmed run writes nothing either\n" + out)
        partial = self.path("partial")
        shutil.copytree(os.path.join(ROOT, "ai"), partial)
        os.remove(os.path.join(partial, "policies", "git.md"))
        rc, out = self.upd(m2, CLAUDE_AGENTIC_SHARED=partial)
        self.assertTrue(rc == 2 and "policies/git.md" in out, "a local tree missing one file exits 2 and names it\n" + out)
        mc = self.v5_project("m2codex", "codex")
        os.makedirs(self.path("h2", ".codex", "skills", "project-update"))
        rc, out = self.upd(mc, HOME=self.path("h2"))
        self.assertTrue(rc == 2 and self.path("h2", ".codex") in out,
                        "a declared home with the plugin but no tree exits 2 and names the home\n" + out)
        rc, out = self.upd(mc, HOME=self.path("h3"))
        self.assertEqual(rc, 0, "with no such home on this machine it proceeds\n" + out)

    def test_m9_never_through_a_symlink_never_outside(self):
        """M9: never through a symlink, never outside the project"""
        m9 = self.v5_project("m9")
        outside = self.path("outside-workflows")
        os.rename(os.path.join(m9, ".ai", "workflows"), outside)
        os.symlink(outside, os.path.join(m9, ".ai", "workflows"))
        git_md = os.path.join(m9, ".ai", "policies", "git.md")
        shutil.copy(git_md, os.path.join(m9, ".ai", "project", "git-real.md"))
        os.remove(git_md)
        os.symlink("../project/git-real.md", git_md)
        commit(m9, "links")
        _, out = self.upd(m9)
        self.assertEqual(lines("hint      .ai/workflows/.* is a symlink, so this update never deletes it", out), 5,
                         "a symlinked directory: a hint per file, no deletion\n" + out)
        self.assertTrue(has("hint      .ai/policies/git.md: .ai/policies/git.md is a symlink", out),
                        "a symlinked file: a hint")
        self.assertFalse(has(r"^  delete\?  *\.ai/(workflows/|policies/git\.md)", out),
                         "neither is proposed for deletion")
        self.confirm(m9)
        self.assertTrue(len(os.listdir(outside)) == 5 and os.path.islink(git_md)
                        and os.path.isfile(os.path.join(m9, ".ai", "project", "git-real.md")),
                        "after the confirmed run the outside files and the link are intact")

    def test_m3_hash_sweep(self):
        """M3: the hash sweep — every shared version stays on record without its blob; real bytes are
        deleted, a flipped byte never is"""
        _, sweep = self.run_([sys.executable, "-I", "-c", SWEEP], PLUGIN_ROOT=ROOT, W=self.w, OLDS=OLDS)
        self.assertTrue(
            has(r"^hash sweep: 31 keys, [0-9]+ versions; 0 not on record; 0 with a blob; bytes: 2 rounds, "
                r"3 old fixtures; 0 not deleted; flipped: 0 not an override$", sweep)
            and not has(r"^FAIL|Traceback", sweep),
            "every shared version is on record by hash alone; real bytes are deleted; one flipped byte makes it an"
            " override\n" + "\n".join(sweep.splitlines()[:20]))

    def test_rollback_rehearsal(self):
        """rollback rehearsal: git first"""
        cur = str(self.cur)
        rb = self.v5_project("rb")
        os.chmod(os.path.join(rb, ".ai", "agents", "risk.md"), 0o755)
        git(rb, "commit", "-qam", "an exec bit")
        snap = tracked(rb)
        deletes = lambda out: sorted(l for l in out.splitlines() if l.startswith("  delete? "))  # noqa: E731
        first = deletes(self.upd(rb)[1])
        self.confirm(rb)
        reg5 = self.path("reg5")
        os.makedirs(reg5)
        for f in glob.glob(os.path.join(ROOT, "skills", "project-update", "migrations", "000[1-5]_*.py")):
            shutil.copy(f, reg5)
        rc, _ = self.upd(rb, "--check", CLAUDE_AGENTIC_MIGRATIONS=reg5)
        self.assertEqual(rc, 2, "a 0001-0005 plugin refuses the migrated project (exit 2)")
        git(rb, "checkout", "-q", "HEAD", "--", ".ai")
        self.assertEqual(snap, tracked(rb),
                         "git checkout restores every file byte- and exec-bit-identical, router included")
        self.assertEqual(version(rb), "5", "and VERSION 5")
        rc, _ = self.upd(rb, "--check", CLAUDE_AGENTIC_MIGRATIONS=reg5)
        self.assertIn(rc, (0, 1), Template("the 0001-0005 plugin reads the restored project (exit $rc)")
                      .substitute(rc=rc))
        again = deletes(self.upd(rb)[1])
        self.assertTrue(first and first == again, "the new plugin re-plans the same delete? list")
        self.confirm(rb)
        for d in glob.glob(os.path.join(rb, ".ai", "reports", "project-update-*")):
            for item in json.loads(read(os.path.join(d, "migration.json")))["deletions"]:
                shutil.copy2(os.path.join(d, "original", item["path"]), os.path.join(rb, item["path"]))
        clean = subprocess.run(["git", "-C", rb, "diff", "--quiet", "--"] + CARRIED, env=GIT_ENV, check=False).returncode == 0
        self.assertTrue(present(rb) == 29 and clean, "the jq fallback restores every deletion")
        self.assertTrue(sections(rb) == 1 and version(rb) == cur,
                        Template("but leaves the router new and VERSION $CUR — its limit: git is the rollback")
                        .substitute(CUR=cur))


if __name__ == "__main__":
    unittest.main()
