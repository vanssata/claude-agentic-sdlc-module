#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
scaffold-ai.sh must be safe to run repeatedly: it creates what is missing and
never touches what exists. That property is what lets /rr-setup be re-run on a
project whose .ai/ has been edited by hand.

The twin of test-scaffold-idempotency.sh (R13): the same cases, through the
same shims — skills/ai-init/scaffold-ai.sh and hooks/project-scaffold.sh —
which now exec the Python ports. A subTest label carries the shell case's name
as the shell suite wrote it, `$f` and all.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest

TWIN_OF = "test-scaffold-idempotency.sh"

TESTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TESTS)
SCAFFOLD = os.path.join(PLUGIN_ROOT, "skills", "ai-init", "scaffold-ai.sh")
SCAFFOLD2 = os.path.join(PLUGIN_ROOT, "hooks", "project-scaffold.sh")
TEMPLATES = os.path.join(PLUGIN_ROOT, "skills", "ai-init", "templates")


def run(script, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("AI_RUNTIMES", "AI_PROJECT_TEMPLATES",
                                                             "CLAUDE_ROUTING_TEMPLATES")}
    env["CLAUDE_AGENTIC_TEMPLATES"] = TEMPLATES
    p = subprocess.run(["bash", script] + list(args), capture_output=True, text=True, env=env,
                       stdin=subprocess.DEVNULL, check=False, timeout=60)
    return p.returncode, p.stdout + p.stderr


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def files(top):
    return [os.path.join(d, f) for d, _, fs in os.walk(top) for f in fs]


def tree_hash(top):
    out = []
    for p in sorted(files(top)):
        with open(p, "rb") as fh:
            out.append((os.path.relpath(p, top), hashlib.sha256(fh.read()).hexdigest()))
    return out


class ScaffoldIdempotencyTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def project(self, name):
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        return d

    def test_first_and_second_run(self):
        root = self.project("project")
        _, out = run(SCAFFOLD, root)
        self.assertIn("created in", out, "first run creates the tree")
        actual = len(files(os.path.join(root, ".ai")))
        self.assertEqual(len(files(os.path.join(TEMPLATES, ".ai"))), actual, "every template file was copied ($ACTUAL)")
        for f in ("AGENTS.md", "policies/risk-tiers.json", "policies/safety.md", "policies/security.md",
                  "project/overview.md", "state/README.md", "rules/README.md", "VERSION"):
            with self.subTest(".ai/$f exists", f=f):
                self.assertTrue(os.path.isfile(os.path.join(root, ".ai", f)))
        # The shared files are read from the plugin (0006): a scaffold carries none of them.
        shared = [os.path.relpath(p, os.path.join(PLUGIN_ROOT, "ai")) for p in files(os.path.join(PLUGIN_ROOT, "ai"))]
        copied = [f for f in shared if os.path.exists(os.path.join(root, ".ai", f))]
        with self.subTest("none of the $(printf '%s\\n' "):
            self.assertTrue(shared)
            self.assertEqual([], copied, "none of the shared files is scaffolded")
        self.assertRegex(read(os.path.join(root, ".ai", "VERSION")), r"^[0-9]+\n?$",
                         "a fresh scaffold starts at the shipped schema")
        self.assertIn(".ai/state/*.json", read(os.path.join(root, ".gitignore")), ".gitignore excludes the state file")
        self.assertIn("riskrails:start", read(os.path.join(root, "CLAUDE.md")),
                      "CLAUDE.md carries the managed block")

        # second run
        _, out = run(SCAFFOLD, root)
        self.assertIn("nothing to do", out, "second run reports nothing to do")

        # A project scaffolded before .ai/VERSION existed is schema 0, and must stay
        # schema 0 until /project-update migrates it.
        os.remove(os.path.join(root, ".ai", "VERSION"))
        run(SCAFFOLD, root)
        self.assertFalse(os.path.exists(os.path.join(root, ".ai", "VERSION")),
                         "a rerun over an existing .ai/ does not invent a schema version")
        gi = [l for l in read(os.path.join(root, ".gitignore")).splitlines() if "claude-agentic" in l]
        self.assertEqual(1, len(gi), ".gitignore snippet is not duplicated")
        self.assertEqual(1, read(os.path.join(root, "CLAUDE.md")).count("riskrails:start"),
                         "the CLAUDE.md block is not duplicated")

        # hand-edited files survive
        write(os.path.join(root, ".ai", "project", "overview.md"), "# my own notes\n")
        with open(os.path.join(root, "CLAUDE.md"), "a", encoding="utf-8") as fh:
            fh.write("custom\n")
        run(SCAFFOLD, root)
        self.assertIn("my own notes", read(os.path.join(root, ".ai", "project", "overview.md")),
                      "a hand-edited template is not overwritten")
        self.assertIn("custom", read(os.path.join(root, "CLAUDE.md")), "hand-edited CLAUDE.md content survives")

    def test_comma_list(self):
        """a comma list scaffolds exactly the runtimes it names"""
        four = self.project("four")
        run(SCAFFOLD, four, "--runtime", "claude,gemini")
        for f in ("CLAUDE.md", "GEMINI.md"):
            with self.subTest("$f carries the block", f=f):
                self.assertIn("riskrails:start", read(os.path.join(four, f)))
        for f in ("AGENTS.md", ".junie/guidelines.md"):
            with self.subTest("$f was not created", f=f):
                self.assertFalse(os.path.exists(os.path.join(four, f)))
        rc, out = run(SCAFFOLD, four, "--runtime", "nope")
        self.assertNotEqual(0, rc)
        self.assertIn("comma list", out, "an unknown runtime is refused by name")

    def test_shipped_risk_tiers(self):
        """the shipped risk-tier mirror matches its JSON"""
        root = self.project("project")
        run(SCAFFOLD, root)
        with open(os.path.join(TEMPLATES, ".ai", "policies", "risk-tiers.json"), "rb") as fh:
            want = hashlib.sha256(fh.read()).hexdigest()
        self.assertIn("sha256:" + want, read(os.path.join(TEMPLATES, ".ai", "policies", "risk-tiers.md")),
                      "risk-tiers.md carries the sha256 of the shipped risk-tiers.json")
        tiers = json.loads(read(os.path.join(root, ".ai", "policies", "risk-tiers.json")))
        self.assertEqual("solo", tiers["pipeline_profile"], "the scaffolded profile is solo")
        self.assertIn("security_review", tiers["pipeline_profiles"]["solo"]["delegated_stages"]["T5"],
                      "solo still delegates the security review at T5")
        self.assertGreaterEqual(len(tiers["tiers"]), 7, "the shipped table has seven tiers, T0 to T6")
        self.assertIs(False, tiers["diff_budget"]["enforce"], "the shipped diff budget is advisory (enforce: false)")

    def test_existing_files_are_extended(self):
        """an existing CLAUDE.md is extended, not replaced; an existing .gitignore is appended to"""
        root2 = self.project("project2")
        write(os.path.join(root2, "CLAUDE.md"), "# Existing project\n\n## Commands\n\nmake test\n")
        run(SCAFFOLD, root2)
        self.assertIn("make test", read(os.path.join(root2, "CLAUDE.md")), "existing CLAUDE.md content is kept")
        self.assertIn("riskrails:start", read(os.path.join(root2, "CLAUDE.md")), "the block is appended to it")

        root3 = self.project("project3")
        write(os.path.join(root3, ".gitignore"), "vendor/\nnode_modules/")   # deliberately no trailing newline
        run(SCAFFOLD, root3)
        lines = read(os.path.join(root3, ".gitignore")).splitlines()
        self.assertIn("vendor/", lines[:2], "existing .gitignore entries are kept")
        self.assertIn("node_modules/", lines, "a missing trailing newline does not corrupt the last entry")

    def test_dual_runtime(self):
        """both instruction files can coexist over one shared .ai/"""
        root4 = self.project("project4")
        run(SCAFFOLD, root4, "--runtime", "both")
        self.assertIn("riskrails:start", read(os.path.join(root4, "CLAUDE.md")), "CLAUDE.md carries the block")
        self.assertIn("riskrails:start", read(os.path.join(root4, "AGENTS.md")), "AGENTS.md carries the block")
        self.assertEqual([".ai"], [n for n in os.listdir(root4) if n == ".ai"], "there is exactly one .ai/ tree")
        self.assertIn("rr-build", read(os.path.join(root4, "AGENTS.md")), "AGENTS.md names the same pipeline entry point")
        _, out = run(SCAFFOLD, root4, "--runtime", "both")
        self.assertIn("nothing to do", out, "a dual-runtime scaffold is idempotent too")
        self.assertEqual(1, read(os.path.join(root4, "AGENTS.md")).count("riskrails:start"),
                         "the AGENTS.md block is not duplicated")

    def test_codex_only(self):
        """a Codex-only project gets no stray CLAUDE.md"""
        root5 = self.project("project5")
        run(SCAFFOLD, root5, "--runtime", "codex")
        self.assertTrue(os.path.exists(os.path.join(root5, "AGENTS.md")), "AGENTS.md is created")
        self.assertFalse(os.path.exists(os.path.join(root5, "CLAUDE.md")), "no CLAUDE.md is created")
        self.assertTrue(os.path.isfile(os.path.join(root5, ".ai", "policies", "risk-tiers.json")),
                        "the shared .ai/ tree is still created")

    def test_auto_detection(self):
        """auto-detection follows what the project already declares"""
        root6 = self.project("project6")
        write(os.path.join(root6, "AGENTS.md"), "# existing\n")
        run(SCAFFOLD, root6)
        self.assertIn("riskrails:start", read(os.path.join(root6, "AGENTS.md")), "an existing AGENTS.md is extended")
        self.assertIn("# existing", read(os.path.join(root6, "AGENTS.md")), "its content survives")
        self.assertFalse(os.path.exists(os.path.join(root6, "CLAUDE.md")), "no CLAUDE.md is added")

    def test_unknown_runtime(self):
        """an unknown runtime is rejected"""
        rc, out = run(SCAFFOLD, os.path.join(self.tmp, "project7"), "--runtime", "everything")
        with self.subTest("--runtime everything is rejected"):
            self.assertNotEqual(0, rc, out)

    def test_project_scaffold(self):
        """project-scaffold.sh covers the same ground"""
        root8 = self.project("project8")
        run(SCAFFOLD2, root8, "--runtime", "both")
        for f in ("docs/sdlc/README.md", "docs/sdlc/constitution.md", ".claude/settings.json",
                  ".claude/memory/README.md", ".codex/config.toml", ".codex/memory/README.md", "CLAUDE.md", "AGENTS.md"):
            with self.subTest("$f scaffolded", f=f):
                self.assertTrue(os.path.exists(os.path.join(root8, f)))
        templates = [p for p in files(os.path.join(root8, "docs", "sdlc")) if os.path.basename(p) == "TEMPLATE.md"]
        self.assertEqual([], templates, "the plugin supplies the SDLC templates; a fresh scaffold creates no TEMPLATE.md")
        for d in ("intent", "specs", "plans", "adr"):
            with self.subTest("no docs/sdlc/%s/TEMPLATE.md" % d, d=d):
                self.assertFalse(os.path.exists(os.path.join(root8, "docs", "sdlc", d, "TEMPLATE.md")))
        before = tree_hash(root8)
        _, out = run(SCAFFOLD2, root8, "--runtime", "both")
        self.assertEqual(before, tree_hash(root8), "a second project scaffold changes no file")
        self.assertIn("nothing to do", out, "it reports nothing to do")

    def test_legacy_codex_agentic_pair(self):
        """a legacy Codex-agentic pair is the managed block: nothing is appended beside it"""
        block = read(os.path.join(TEMPLATES, "AGENTS.block.md"))
        for name in ("Codex-agentic", "codex-agentic"):
            r9 = self.project("legacy-" + name)
            write(os.path.join(r9, "AGENTS.md"),
                  "# mine\n\nkeep this.\n\n" + re.sub(r"riskrails:(start|end)", name + r":\1", block))
            _, out = run(SCAFFOLD, r9, "--runtime", "codex")
            text = read(os.path.join(r9, "AGENTS.md"))
            with self.subTest("$name: one block, the legacy pair is not doubled", name=name):
                self.assertEqual(1, text.count("agentic:start -->"), out)
            with self.subTest("$name: no block is reported as appended", name=name):
                self.assertNotIn("AGENTS.md (agent workflow block appended)", out)
            with self.subTest("$name: the file is left as it was", name=name):
                self.assertIn("<!-- %s:start -->" % name, text)
                self.assertIn("keep this.", text)


if __name__ == "__main__":
    unittest.main()
