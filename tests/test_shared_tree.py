#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The shared tree: ai/ holds the policies, agent contracts, workflows and
templates every project reads from the plugin (T-2026-10-13-004). safety.md
and security.md stay project-owned (Q5=A), and no .json is shared: risk-tiers
and path-guard are project policy.

Since the cut-over (0006) a shared file lives only here: the scaffold no
longer carries it, and 0006 retires the project copies. The sections share one
scratch tree, in the shell suite's order: test_NN_ names keep it.
"""
import fnmatch
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, write  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-shared-tree.sh"

PLUGIN = os.path.realpath(PLUGIN)
TPL = os.path.join(PLUGIN, "skills", "ai-init", "templates", ".ai")
RES = os.path.join(PLUGIN, "scripts", "ai-path")
AI = os.path.join(PLUGIN, "ai")

SHARED = """agents/context.md
agents/discovery.md
agents/implementer.md
agents/manager.md
agents/planner.md
agents/release.md
agents/reviewer.md
agents/risk.md
agents/security.md
agents/tester.md
policies/context-management.md
policies/database.md
policies/git.md
policies/model-routing.md
policies/production.md
policies/release.md
policies/review-economy.md
policies/tooling.md
templates/architecture-decision.md
templates/impact-report.md
templates/implementation-plan.md
templates/release-report.md
templates/review-report.md
templates/task-context.md
workflows/bugfix.md
workflows/feature.md
workflows/hotfix.md
workflows/investigation.md
workflows/refactoring.md
using-riskrails.md
workflows.md""".split("\n")

MIGRATION_SHARED = r'''import importlib.util, sys
spec = importlib.util.spec_from_file_location("m6", sys.argv[1]); m = importlib.util.module_from_spec(spec)
sys.path.insert(0, sys.argv[2]); spec.loader.exec_module(m)
print("\n".join(sorted(p[len(".ai/"):] for p in m.SHARED)))'''

# Python prints "ok <what>" or "FAIL <what> | <detail>"; each line becomes one assertion.
HELPER_PASS = "${line#ok }"
HELPERS = r'''
import os, shutil, sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import update as U
from migrations import SchemaError
W = os.environ["W"]

def check(ok, what, detail=""):
    print(("ok %s" % what) if ok else ("FAIL %s | %s" % (what, detail)))

mod = types.SimpleNamespace(VERSION=6, MOVES=[])
def ctx(root, history=None):
    return U.MigrationContext(U.Plan(root), mod, 5, None, history or U.History(U.HISTORY))

proj = os.path.join(W, "uproj"); os.makedirs(os.path.join(proj, ".ai"))
open(os.path.join(proj, "AGENTS.md"), "w").close()  # declares codex
open(os.path.join(proj, "CLAUDE.md"), "w").close()  # and claude
c = ctx(proj)
P = ".ai/workflows/feature.md"
cur = c.template(P)
check(cur == open(os.path.join(os.environ["PLUGIN_ROOT"], "ai", "workflows", "feature.md"), "rb").read(),
      "template() returns the shipped bytes")
try:
    c.template(".ai/workflows/nothing.md"); check(False, "template() of an unknown path raises")
except SchemaError:
    check(True, "template() of an unknown path raises")

# Shared keys keep their hashes, not their blobs: the old bytes are a fixture.
old = open(os.path.join(os.environ["PLUGIN_ROOT"], "tests", "fixtures", "project-update", "shared-old",
                        "workflows", "feature.md"), "rb").read()
check(old != cur, "the fixture holds an older feature.md", "oldest equals current")
check(c.history.versions("ai-init/" + P) == [], "a shared key ships no blob")
check(c.is_shipped(P, cur), "the current bytes are shipped")
check(c.is_shipped(P, old), "an older shipped version is shipped")
check(not c.is_shipped(P, cur + b"x"), "an edited copy is not shipped")
check(c.is_shipped(P, cur.replace(b"\n", b"\r\n")), "a CRLF checkout of a shipped version is shipped")
check(not c.is_shipped(".ai/project/notes.md", cur), "a path the plugin never shipped is not shipped")

bare = os.path.join(W, "history-noblobs"); os.makedirs(bare)
shutil.copy(os.path.join(U.HISTORY, "index.json"), bare)
h = U.History(bare)
check(h.versions("ai-init/" + P) == [], "the bare history has no blobs")
check(U.sha(old) in h.hashes("ai-init/" + P), "hashes() answers from index.json alone")
check(ctx(proj, h).is_shipped(P, old), "is_shipped needs no blob")

files = U.shared_files()
check(len(files) == 31 and files.get(P) == cur, "shared_files() maps the 31 to .ai/<rel>", len(files))

paths = sorted(files)
def refused():
    try:
        ctx(proj).require_shared(paths); return None
    except SchemaError as exc:
        return str(exc)
check(refused() is None, "require_shared: no other home on this machine is not checked")
codex = os.path.join(W, "h", ".codex"); os.makedirs(os.path.join(codex, "skills", "project-update"))
msg = refused()
check(msg is not None and codex in msg and "--target codex" in msg,
      "require_shared: a codex home with the plugin but no tree refuses", msg)
tree = os.path.join(codex, "riskrails", "ai")
shutil.copytree(U.SHARED, tree)
os.remove(os.path.join(tree, "policies", "git.md")); os.remove(os.path.join(tree, "agents", "risk.md"))
msg = refused()
check(msg is not None and " 2 of the 31 " in msg, "require_shared: a partial tree refuses with the count", msg)
shutil.rmtree(tree); shutil.copytree(U.SHARED, tree)
check(refused() is None, "require_shared: a full tree in every installed home passes")
saved = U.SHARED
U.SHARED = os.path.join(W, "local-shared"); shutil.copytree(saved, U.SHARED)
os.remove(os.path.join(U.SHARED, "templates", "review-report.md"))
msg = refused()
check(msg is not None and "templates/review-report.md" in msg, "require_shared: the local tree names the missing file", msg)
U.SHARED = saved

outside = os.path.join(W, "outside"); os.makedirs(outside)
open(os.path.join(outside, "feature.md"), "w").close()
os.symlink(outside, os.path.join(proj, ".ai", "workflows"))
os.makedirs(os.path.join(proj, ".ai", "policies"))
open(os.path.join(proj, ".ai", "policies", "real.md"), "w").close()
os.symlink("real.md", os.path.join(proj, ".ai", "policies", "git.md"))
c = ctx(proj)
why = c.unsafe_target(P)
check(why is not None and "symlink" in why, "unsafe_target: a file under a symlinked directory", why)
why = c.unsafe_target(".ai/policies/git.md")
check(why is not None and "symlink" in why, "unsafe_target: a symlinked file", why)
check(c.unsafe_target(".ai/policies/real.md") is None, "unsafe_target: a regular file is safe")
note = c.override_note(".ai/policies/git.md")
check("no longer receives its changes" in note and os.path.join(U.SHARED, "policies", "git.md") in note,
      "override_note names the shared copy", note)

repo = os.path.join(W, "repo"); os.makedirs(os.path.join(repo, ".ai"))
check(not U.git_dirty_ai(repo), "git_dirty_ai: outside a work tree is False")
import subprocess
subprocess.run(["git", "init", "-q", repo], check=True)
check(not U.git_dirty_ai(repo), "git_dirty_ai: an empty .ai/ is clean")
open(os.path.join(repo, ".ai", "x.md"), "w").close()
check(U.git_dirty_ai(repo), "git_dirty_ai: an untracked .ai/ file is dirty")
'''

ADOPT_ROWS = r'''
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import adopt, update as U
plan = U.Plan(os.path.join(os.environ["W"], "scaf"))
row = "| a tool the project adopted | `policies/adopted/x.md` |"
print(adopt.add_router_rows(plan, [row]))
lines = plan.items[-1]["content"].decode().split("\n") if plan.items else []
i = lines.index(row) if row in lines else -1
print(i > 0 and lines[i - 1].startswith("|") and "## Shared files" in lines and lines.index("## Shared files") < i)
'''


def lbl(template, **values):
    for key in sorted(values, key=len, reverse=True):
        template = template.replace("$" + key, str(values[key]))
    return template


def read_text(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        return fh.read()


def run(argv, cwd=None, env=None, stdin=None, merge=True):
    """Run a command; (exit code, stdout[+stderr]) with a trailing newline cut, as a shell `$(...)` does."""
    proc = subprocess.run(argv, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, check=False)
    out = proc.stdout + proc.stderr if merge else proc.stdout
    return proc.returncode, out.rstrip("\n")


def files_under(root, kind):
    found = []
    for base, dirs, names in os.walk(root):
        for name in (names if kind == "f" else names + dirs):
            full = os.path.join(base, name)
            if kind == "f" and (os.path.islink(full) or not os.path.isfile(full)):
                continue
            found.append(os.path.relpath(full, root))
    return found


class SharedTree(ScratchCase):
    def check(self, label, cond, detail=""):
        with self.subTest(label):
            self.assertTrue(cond, detail or label)

    def resolve(self, cwd, *args):
        """scripts/ai-path run from cwd; (exit code, stdout) with stderr dropped."""
        return run([RES, *args], cwd=cwd, merge=False)

    def test_01_the_shared_file_set(self):
        self.check("the literal list names 31 files", len(SHARED) == 31, "the literal list is not 31 files")
        actual = sorted(files_under(AI, "f"))
        self.check("ai/ holds exactly the 31 shared files", actual == sorted(SHARED),
                   "ai/ differs from the shared list: %s" % sorted(set(actual) ^ set(SHARED)))
        for f in ("policies/safety.md", "policies/security.md"):
            self.check(lbl("$f stays project-owned", f=f), not os.path.exists(os.path.join(AI, f)), lbl("$f must not be shared", f=f))
        self.check("no .json is shared", not [n for n in files_under(AI, "d") if fnmatch.fnmatch(os.path.basename(n), "*.json")],
                   "a .json file is in ai/")

    def test_02_one_home_per_file_the_shared_tree_not_the_scaffold(self):
        both = [f for f in SHARED if os.path.exists(os.path.join(TPL, f))]
        self.check("no shared path is also a scaffold template", not both, "a path is in both trees: %s" % both)
        for f in ("policies/safety.md", "policies/security.md"):
            self.check(lbl("$f is still scaffolded", f=f), os.path.isfile(os.path.join(TPL, f)), lbl("$f must stay in the scaffold", f=f))
        _, mig = run(["python3", "-I", "-c", MIGRATION_SHARED,
                      os.path.join(PLUGIN, "skills", "project-update", "migrations", "0006_shared_files.py"),
                      os.path.join(PLUGIN, "skills", "project-update")], cwd=PLUGIN)
        self.check("0006.SHARED equals the shared tree (M1)", mig == "\n".join(sorted(SHARED)),
                   "0006.SHARED differs from ai/\n" + mig)

    def test_03_the_resolver_scripts_ai_path(self):
        proj, none = self.path("proj"), self.path("none")
        os.makedirs(os.path.join(proj, ".ai", "policies"))
        os.makedirs(os.path.join(proj, "src", "deep"))
        os.makedirs(none)
        os.makedirs(os.path.join(proj, ".ai", "workflows", "feature.md"))
        write(os.path.join(proj, ".ai", "policies", "git.md"), "override\n")
        git = os.path.join(proj, ".ai", "policies", "git.md")
        _, out = self.resolve(proj, "policies/git.md")
        self.check("a project file overrides the shared one", out == git, "override\n" + out)
        _, out = self.resolve(proj, ".ai/policies/git.md")
        self.check("a leading .ai/ is stripped", out == git, "leading .ai/\n" + out)
        _, out = self.resolve(proj, "policies/tooling.md")
        self.check("without a project copy the shared file is printed", out == os.path.join(AI, "policies", "tooling.md"), "fallback\n" + out)
        _, out = self.resolve(os.path.join(proj, "src", "deep"), "policies/git.md")
        self.check("from a subdirectory the project override is found", out == git, "upward search\n" + out)
        _, out = self.resolve(proj, "workflows/feature.md")
        self.check("a directory at the path is not an override", out == os.path.join(AI, "workflows", "feature.md"), "directory as override\n" + out)
        _, out = self.resolve(none, "--root", proj, "policies/git.md")
        self.check("--root names the project", out == git, "--root\n" + out)
        rc, out = self.resolve(proj, "policies/nothing.md")
        self.check("a missing file exits 1, nothing on stdout", rc == 1 and out == "", "missing file: rc=%s\n%s" % (rc, out))
        rc, out = self.resolve(none, "policies/git.md")
        self.check("no project exits 1, nothing on stdout", rc == 1 and out == "", "no project: rc=%s\n%s" % (rc, out))
        rc, _ = self.resolve(proj, "../etc/passwd")
        self.check("a .. component exits 2", rc == 2, "traversal: rc=%s" % rc)
        rc, _ = self.resolve(proj, "policies/../../x")
        self.check("an inner .. component exits 2", rc == 2, "inner traversal: rc=%s" % rc)
        rc, _ = self.resolve(proj, "/etc/passwd")
        self.check("an absolute path exits 2", rc == 2, "absolute: rc=%s" % rc)

    def test_04_the_resolver_in_the_installed_layout(self):
        proj = self.path("proj")
        home_rr = self.path("home", "riskrails")
        os.makedirs(home_rr)
        shutil.copytree(AI, os.path.join(home_rr, "ai"))
        shutil.copy(RES, os.path.join(home_rr, "ai-path"))
        installed = os.path.join(home_rr, "ai-path")
        _, out = run([installed, "policies/tooling.md"], cwd=proj)
        self.check("installed: the tree beside the script is used", out == os.path.join(home_rr, "ai", "policies", "tooling.md"),
                   "installed layout\n" + out)
        env = dict(os.environ, CLAUDE_AGENTIC_SHARED=AI)
        _, out = run([installed, "policies/tooling.md"], cwd=proj, env=env)
        self.check("CLAUDE_AGENTIC_SHARED outranks the installed tree", out == os.path.join(AI, "policies", "tooling.md"), "env override\n" + out)

    def test_05_tree_hash(self):
        installed = self.path("home", "riskrails", "ai-path")
        _, h1 = run([installed, "--tree-hash"], cwd=PLUGIN, merge=False)
        _, h2 = run([installed, "--tree-hash"], cwd=PLUGIN, merge=False)
        self.check("the tree hash is stable", h1 != "" and h1 == h2, "tree hash unstable\n%s / %s" % (h1, h2))
        self.check("an equal tree has an equal hash", h1 == run([RES, "--tree-hash"], cwd=PLUGIN, merge=False)[1], "copy hashes differently")
        with open(self.path("home", "riskrails", "ai", "policies", "git.md"), "a", encoding="utf-8") as fh:
            fh.write("x")
        self.check("a one-byte edit changes the hash", h1 != run([installed, "--tree-hash"], cwd=PLUGIN, merge=False)[1],
                   "hash ignored a one-byte edit")

    def test_06_update_py_helpers_for_the_cut_over(self):
        env = dict(os.environ, HOME=self.path("h"), CODEX_HOME="", CLAUDE_AGENTIC_SHARED=AI, PLUGIN_ROOT=PLUGIN, W=self.tmp)
        _, helpers = run(["python3", "-I", "-"], cwd=PLUGIN, env=env, stdin=HELPERS)
        self.assertIn("ok ", helpers, "helper check crashed\n" + helpers)
        for line in helpers.split("\n"):
            if not line:
                continue
            with self.subTest(HELPER_PASS, line=line):
                if line.startswith("ok "):
                    continue
                self.fail(line[len("FAIL "):] if line.startswith("FAIL ") else "helper check crashed\n" + line)

    def test_07_adopt_rows_land_in_the_routing_table_of_a_scaffolded_router(self):
        os.makedirs(self.path("scaf"), exist_ok=True)
        run(["bash", os.path.join(PLUGIN, "skills", "ai-init", "scaffold-ai.sh"), self.path("scaf")], cwd=PLUGIN)
        env = dict(os.environ, PLUGIN_ROOT=PLUGIN, W=self.tmp)
        _, rows = run(["python3", "-I", "-"], cwd=PLUGIN, env=env, stdin=ADOPT_ROWS)
        self.check("add_router_rows appends after the routing table, below the Shared files section", rows == "1\nTrue",
                   "add_router_rows on the new router\n" + rows)

    def test_08_consumers_name_the_rule(self):
        for a in ("ai-discovery", "ai-reviewer"):
            text = read_text(os.path.join(PLUGIN, "agents", a + ".md.tmpl"))
            count = sum(1 for line in text.split("\n") if "{{AI_SHARED}}/<path>" in line)
            self.check(lbl("agents/$a.md.tmpl states the rule once", a=a), count == 1,
                       lbl("agents/$a.md.tmpl should state the shared-path rule once", a=a))
        self.check("rr-build names the resolver",
                   '"$AI_HOME/riskrails/ai-path" <path>' in read_text(os.path.join(PLUGIN, "skills", "rr-build", "SKILL.md")),
                   "rr-build SKILL.md should name the resolver")
        self.check("rr-review records its verdict through state.py review",
                   "$STATE review --verdict" in read_text(os.path.join(PLUGIN, "skills", "rr-review", "SKILL.md")),
                   "rr-review lost the review call")


if __name__ == "__main__":
    unittest.main()
