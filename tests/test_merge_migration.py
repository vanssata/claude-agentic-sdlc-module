#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Behaviour that only exists because this plugin absorbed claude-routing: the
superseded agent, the legacy unmarked CLAUDE.md section, and the two scaffolds
composing into one project layout without duplicating anything.

Every install goes into a temp CLAUDE_DIR with a pinned HOME, through
`bash install.sh` as the shell suite drove it.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install.sh")

TWIN_OF = "test-merge-migration.sh"

CREATED = ("docs/sdlc/README.md", "docs/sdlc/intent/TEMPLATE.md", "docs/sdlc/specs/TEMPLATE.md",
           "docs/sdlc/plans/TEMPLATE.md", "docs/sdlc/adr/TEMPLATE.md", ".claude/settings.json",
           ".claude/memory/README.md", ".ai/AGENTS.md", ".ai/policies/risk-tiers.json", "CLAUDE.md", ".gitignore")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def tree_digest(root):
    """What `find -type f | sort | xargs md5sum | md5sum` compares: every file's path and content."""
    digest = hashlib.md5()
    paths = [os.path.join(d, f) for d, _, files in os.walk(root) for f in files]
    for path in sorted(p for p in paths if os.path.isfile(p)):
        with open(path, "rb") as fh:
            digest.update(path.encode() + b"\0" + hashlib.md5(fh.read()).digest())
    return digest.hexdigest()


class Env:
    """A scratch directory and an environment that reaches nothing of the real user's."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        home = os.path.join(self.tmp.name, "home")
        os.makedirs(home)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CODEX_HOME", "CODEX_DIR", "CLAUDE_DIR", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS",
                                 "CLAUDE_CONFIG_DIR", "CLAUDE_AGENTIC_SHARED", "CLAUDE_ROUTING_TEMPLATES",
                                 "CLAUDE_AGENTIC_TEMPLATES") and not k.startswith("RISKRAILS_")}
        self.env["HOME"] = home

    def dir(self, name):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(path, exist_ok=True)
        return path

    def run(self, args, **extra):
        env = dict(self.env, **extra)
        done = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return done.stdout

    def install(self, claude_dir):
        return self.run(["bash", INSTALL, "--plan", "max", "--fable", "yes"], CLAUDE_DIR=claude_dir)

    def close(self):
        self.tmp.cleanup()


class TestInstallMigrations(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_superseded_reviewer_agent(self):
        """the superseded reviewer agent"""
        d = self.env.dir("a")
        os.makedirs(os.path.join(d, "agents"))
        shutil.copy(os.path.join(ROOT, "agents", "superseded", "reviewer.md"), os.path.join(d, "agents", "reviewer.md"))
        out = self.env.install(d)
        self.assertTrue(os.path.isfile(os.path.join(d, "agents", "reviewer.md.superseded")),
                        "an unmodified reviewer.md is retired\n" + out)
        self.assertFalse(os.path.isfile(os.path.join(d, "agents", "reviewer.md")),
                         "and no longer competes with ai-reviewer")
        self.assertTrue(os.path.isfile(os.path.join(d, "agents", "ai-reviewer.md")), "ai-reviewer takes its place")

    def test_edited_reviewer_is_kept(self):
        d = self.env.dir("b")
        os.makedirs(os.path.join(d, "agents"))
        mine = os.path.join(d, "agents", "reviewer.md")
        with open(mine, "w", encoding="utf-8") as fh:
            fh.write(read(os.path.join(ROOT, "agents", "superseded", "reviewer.md")) + "my own extra rule\n")
        out = self.env.install(d)
        self.assertTrue(os.path.isfile(mine), "an edited reviewer.md is kept")
        self.assertIn("my own extra rule", read(mine), "with the user's edit intact")
        self.assertIn("you have edited it", out, "and the conflict is reported")

    def test_upgrade_reaches_a_changed_registration(self):
        """an upgrade reaches a registration this version changed"""
        d = self.env.dir("upgrade")
        settings = os.path.join(d, "settings.json")
        with open(settings, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {
                "SessionStart": [{"matcher": "compact", "hooks": [
                    {"type": "command", "command": '"$HOME/.claude/hooks/context-guard.py"', "timeout": 15}]}],
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "my-own-guard.sh"}]}]}},
                fh)
        out = self.env.install(d)
        hooks = json.loads(read(settings))["hooks"]
        guards = [e for e in hooks["SessionStart"] if any("context-guard" in h["command"] for h in e["hooks"])]
        self.assertEqual(len(guards), 1, "the existing context-guard SessionStart entry is not duplicated\n" + out)
        self.assertEqual(guards[0]["matcher"], "startup|resume|clear|compact",
                         "and its matcher is the one this version registers")
        own = [e for e in hooks["PreToolUse"] if any(h["command"] == "my-own-guard.sh" for h in e["hooks"])]
        self.assertEqual(len(own), 1, "a hook the user registered themselves is untouched")

    def test_unmarked_routing_section_is_migrated(self):
        """a pre-plugin unmarked routing section is migrated"""
        d = self.env.dir("c")
        md = os.path.join(d, "CLAUDE.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# Model allocation by task and scope\n\nold hand-written rules\n\n# Something else of mine\n\nkeep me\n")
        out = self.env.install(d)
        self.assertIn("migrated an unmarked", out, "the unmarked section is migrated")
        text = read(md)
        self.assertNotIn("old hand-written rules", text, "its superseded rules are removed")
        self.assertIn("keep me", text, "unrelated sections are kept")
        self.assertEqual(text.count("riskrails:start"), 1, "one managed block results")


class TestScaffoldsCompose(unittest.TestCase):
    """both scaffolds compose into one project"""

    @classmethod
    def setUpClass(cls):
        cls.env = Env()
        cls.claude = cls.env.dir("d")
        cls.env.install(cls.claude)
        cls.repo = cls.env.dir("repo")
        cls.scaffold()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    @classmethod
    def scaffold(cls):
        cls.env.run(["bash", os.path.join(cls.claude, "hooks", "project-scaffold.sh"), cls.repo],
                    CLAUDE_ROUTING_TEMPLATES=os.path.join(cls.claude, "skills", "project-init", "templates"))
        cls.env.run(["bash", os.path.join(cls.claude, "skills", "ai-init", "scaffold-ai.sh"), cls.repo],
                    CLAUDE_AGENTIC_TEMPLATES=os.path.join(cls.claude, "skills", "ai-init", "templates"))

    def test_files_created(self):
        for f in CREATED:
            with self.subTest(Template("$f created").substitute(f=f)):
                self.assertTrue(os.path.lexists(os.path.join(self.repo, f)), f + " missing")

    def test_project_files(self):
        claude_md = read(os.path.join(self.repo, "CLAUDE.md"))
        self.assertEqual(claude_md.count("riskrails:start"), 1, "the project CLAUDE.md carries one agent block")
        self.assertIn("/rr-build", claude_md, "and points at the pipeline as the default route")
        gitignore = read(os.path.join(self.repo, ".gitignore"))
        self.assertRegex(gitignore, r".claude/settings.local.json", ".gitignore covers the sdlc layout")
        self.assertRegex(gitignore, r".ai/state/\*.json", "and the .ai state file")
        self.assertEqual(sum("claude-agentic" in line for line in gitignore.splitlines()), 2,
                         "with one section each, not duplicated")

    def test_combined_scaffold_is_idempotent(self):
        """running both scaffolds again changes nothing"""
        before = tree_digest(self.repo)
        self.scaffold()
        self.assertEqual(tree_digest(self.repo), before, "the combined scaffold is idempotent")

    def test_every_agent_declares_its_tier(self):
        """every agent this plugin ships declares its tier"""
        # The sources are templates now; what must declare a tier is what gets installed.
        agents = sorted(glob.glob(os.path.join(self.claude, "agents", "*.md")))
        self.assertTrue(agents)
        for f in agents:
            text = read(f)
            with self.subTest(agent=os.path.basename(f)):
                self.assertRegex(text, re.compile(r"^effort:", re.M), "every agent declares effort:")
                self.assertRegex(text, re.compile(r"^model:", re.M),
                                 "declares no model: (it would resolve to the Sonnet default)")
        self.assertIn("{{ARCHITECT_MODEL_LINE}}", read(os.path.join(ROOT, "agents", "architect.md.tmpl")),
                      "architect's model line is rendered per plan")
        self.assertRegex(read(os.path.join(self.claude, "agents", "architect.md")),
                         re.compile(r"^model: fable\[1m\]", re.M),
                         "on max with Fable, architect alone is pinned to fable[1m]")
        self.assertIn("model: opus", read(os.path.join(self.claude, "agents", "ai-reviewer.md")).splitlines(),
                      "on max, ai-reviewer is pinned to opus")
        self.assertFalse(os.path.lexists(os.path.join(self.claude, "agents", "ai-expert.md")),
                         "ai-expert is not installed (redesign 2.4)")


if __name__ == "__main__":
    unittest.main()
