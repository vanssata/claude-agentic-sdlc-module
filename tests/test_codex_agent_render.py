#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
scripts/render-codex-agents.py: every rendered Codex custom agent must parse as
TOML, carry the three fields Codex requires, and resolve to the tier its role
needs. The last part is the point of the suite: Codex resolves a subagent's
model from the spawn value, then the [agents] default, then the parent — and a
custom agent file that omits `model` would let an escalation land back on the
BALANCED default. Asserting the effective model per role is what catches that.

The renderer runs under `python3 -I` with a pinned HOME, as the shell suite drove it.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest

try:
    import tomllib
except ImportError:  # 3.10: the renderer itself needs tomllib
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "scripts", "render-codex-agents.py")
PROFILES = os.path.join(ROOT, "profiles")

TWIN_OF = "test-codex-agent-render.sh"

# R13 reads the shell `pass` text as written, the escaped `\$` included.
CODEX_HOME_DEFAULT_CASE = r"the default is \$CODEX_HOME/claude-agentic/ai"

ROSTER = ["Explore", "ai-discovery", "ai-reviewer", "architect", "log-reader"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def tree(root):
    """Every file under root, by relative path, with its bytes: what `diff -rq` compares."""
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            path = os.path.join(d, n)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, root)] = fh.read()
    return out


@unittest.skipIf(tomllib is None, "python3 has no tomllib (needs 3.11+)")
class TestCodexAgentRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.home = self.path("home")
        os.makedirs(self.home)
        self.env = {k: v for k, v in os.environ.items() if k not in ("CODEX_HOME", "CODEX_DIR", "CLAUDE_DIR",
                                                                     "CLAUDE_CONFIG_DIR", "CLAUDE_AGENTIC_SHARED")}
        self.env["HOME"] = self.home
        self.out = self.path("agents")
        self.first = self.render("--out", self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, *parts):
        return os.path.join(self.tmp.name, *parts)

    def render(self, *args, env=None):
        return subprocess.run(["python3", "-I", RENDER, "--src", ROOT] + list(args), env=env or self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)

    def agent(self, name, out=None):
        with open(os.path.join(out or self.out, name + ".toml"), "rb") as fh:
            return tomllib.load(fh)

    def field(self, name, key):
        return str(self.agent(name).get(key, ""))

    def test_render(self):
        """renderer exits 0"""
        self.assertEqual(self.first.returncode, 0, "renderer should exit 0\n" + self.first.stdout)

    def test_r11_exactly_the_five_agents(self):
        """rendered Explore, ai-discovery, ai-reviewer, architect, log-reader"""
        got = sorted((n[:-len(".toml")] for n in os.listdir(self.out) if n.endswith(".toml")), key=str.encode)
        self.assertEqual(got, ROSTER, "the rendered roster is wrong")
        with self.subTest("no tier twin is rendered"):
            twins = [n for n in os.listdir(self.out) if re.search(r"-(strong|balanced)\.toml$", n)]
            self.assertEqual(twins, [], "a tier twin was rendered")

    def test_every_file_is_valid_toml_with_the_three_required_fields(self):
        """all files parse and carry name/description/developer_instructions"""
        problems = []
        for name in sorted(n for n in os.listdir(self.out) if n.endswith(".toml")):
            try:
                with open(os.path.join(self.out, name), "rb") as fh:
                    data = tomllib.load(fh)
            except Exception as exc:  # pylint: disable=broad-except  # any parse failure is the finding
                problems.append("%s: not valid TOML: %s" % (name, exc))
                continue
            for key in ("name", "description", "developer_instructions"):
                if not isinstance(data.get(key), str) or not data[key].strip():
                    problems.append("%s: missing or empty %s" % (name, key))
            if data.get("name") != name[:-len(".toml")]:
                problems.append("%s: name %r != filename" % (name, data.get("name")))
            if "{{" in data.get("developer_instructions", "") or "{{" in data.get("description", ""):
                problems.append("%s: unrendered placeholder" % name)
        self.assertEqual(problems, [], "invalid rendered agents")

    def test_readers_resolve_to_terra_at_low_effort(self):
        for a in ("Explore", "ai-discovery", "log-reader"):
            with self.subTest("$a runs on Terra", agent=a):
                self.assertEqual(self.field(a, "model"), "gpt-5.6-terra", "%s should run on Terra" % a)
            with self.subTest("$a runs at low effort", agent=a):
                self.assertEqual(self.field(a, "model_reasoning_effort"), "low", "%s should run at low effort" % a)

    def test_reviewer_and_designer_resolve_to_sol(self):
        for a in ("ai-reviewer", "architect"):
            with self.subTest("$a runs on Sol", agent=a):
                self.assertEqual(self.field(a, "model"), "gpt-5.6-sol", "%s should run on Sol" % a)
            with self.subTest("$a runs at high effort", agent=a):
                self.assertEqual(self.field(a, "model_reasoning_effort"), "high", "%s should run at high effort" % a)
        with self.subTest("ai-reviewer carries the security focus"):
            self.assertRegex(self.field("ai-reviewer", "developer_instructions"), r"(?m)^## Focus: security",
                             "ai-reviewer is missing its Focus: security section")

    def test_plus_profile_keeps_xhigh_off(self):
        outp = self.path("plus")
        done = self.render("--out", outp, "--profile", os.path.join(PROFILES, "codex-plus.json"))
        with self.subTest("the plus profile renders"):
            self.assertEqual(done.returncode, 0, "the plus profile should render\n" + done.stdout)
        with self.subTest("no plus agent runs at xhigh"):
            self.assertFalse([p for p, data in tree(outp).items() if b"xhigh" in data], "no plus agent may run at xhigh")
        pro = json.loads(read(os.path.join(PROFILES, "codex-pro.json"))).get("roles")
        for p in ("codex-plus", "codex-pro", "codex-balanced-max"):
            with self.subTest("$p has the same roster as codex-pro", profile=p):
                self.assertEqual(json.loads(read(os.path.join(PROFILES, p + ".json"))).get("roles"), pro,
                                 "%s roster differs from codex-pro" % p)

    def test_a_variant_of_role_still_renders(self):
        """a variant reuses its parent's body, on its own tier"""
        # The mechanism stays, no profile ships one.
        profile = json.loads(read(os.path.join(PROFILES, "codex-pro.json")))
        profile["roles"]["ai-reviewer-strong"] = {"variant_of": "ai-reviewer", "tier": "EXPERT",
                                                  "sandbox_mode": "read-only", "description_prefix": "Twin.",
                                                  "escalation_note": "You are the twin."}
        with open(self.path("variant.json"), "w", encoding="utf-8") as fh:
            json.dump(profile, fh)
        out = self.path("variant")
        done = self.render("--out", out, "--profile", self.path("variant.json"))
        self.assertEqual(done.returncode, 0, "variant_of no longer renders\n" + done.stdout)
        twin, parent = self.agent("ai-reviewer-strong", out), self.agent("ai-reviewer", out)
        self.assertEqual(twin["developer_instructions"], "You are the twin.\n\n" + parent["developer_instructions"],
                         "variant_of no longer renders")
        self.assertEqual(twin["model"], "gpt-6-astra", "variant_of no longer renders")

    def test_read_only_roles_get_a_read_only_sandbox(self):
        for a in ("ai-reviewer", "ai-discovery", "Explore", "architect", "log-reader"):
            with self.subTest("$a is sandboxed read-only", agent=a):
                self.assertEqual(self.field(a, "sandbox_mode"), "read-only", "%s should be read-only" % a)

    def test_rendering_twice_produces_identical_files(self):
        """the renderer is deterministic"""
        out2 = self.path("agents2")
        self.render("--out", out2)
        self.assertEqual(tree(self.out), tree(out2), "two renders differ")

    def test_ai_shared_fills_the_placeholder(self):
        ai1 = self.path("ai1")
        done = self.render("--out", ai1, "--ai-shared", "/opt/x/ai")
        self.assertEqual(done.returncode, 0, "render with --ai-shared should exit 0\n" + done.stdout)
        for a in ("ai-discovery", "ai-reviewer"):
            with self.subTest("$a names the shared tree", agent=a):
                self.assertIn("/opt/x/ai/<path>", read(os.path.join(ai1, a + ".toml")),
                              "%s does not name /opt/x/ai/<path>" % a)
        with self.subTest(CODEX_HOME_DEFAULT_CASE):
            ch = self.path("ch")
            done = self.render("--out", self.path("ai2"), env=dict(self.env, CODEX_HOME=ch))
            self.assertEqual(done.returncode, 0, "the --ai-shared default is wrong\n" + done.stdout)
            self.assertIn(ch + "/claude-agentic/ai/<path>", read(self.path("ai2", "ai-reviewer.toml")),
                          "the --ai-shared default is wrong")
        with self.subTest("without CODEX_HOME the default is ~/.codex/claude-agentic/ai"):
            h = self.path("h")
            done = self.render("--out", self.path("ai3"), env=dict(self.env, HOME=h))
            self.assertEqual(done.returncode, 0, "the --ai-shared fallback is wrong\n" + done.stdout)
            self.assertIn(h + "/.codex/claude-agentic/ai/<path>", read(self.path("ai3", "ai-reviewer.toml")),
                          "the --ai-shared fallback is wrong")
        with self.subTest("no placeholder survives"):
            self.assertFalse([p for p, data in tree(ai1).items() if b"{{" in data], "a placeholder survived")


if __name__ == "__main__":
    unittest.main()
