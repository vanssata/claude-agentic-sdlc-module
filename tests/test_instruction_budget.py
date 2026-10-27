#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
What a session pays for in instruction text before it does any work.

R5: a light task reads `rr-build`, `weight.json` and the Verification block of
`testing.md` — together at most 400 lines. R28: the SessionStart cost — both
managed blocks, a 30-line handoff and `using-superpowers` — stays under 10 KB.
R32: the stub sends runners and verbatim extraction to FAST and readers that
judge to BALANCED, inside the 2560 B global budget.

`step_test_command` hands every test path to bash; the line above makes bash
re-run this file under python3.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "skills", "project-update", "render_instructions.py")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
TEMPLATE_AI = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai")
INSTALL = os.path.join(ROOT, "install.sh")
SUPERPOWERS_BYTES = 3686          # using-superpowers, as SQ12 measured it (3.6 KB)
GLOBAL_BUDGET = 2560
SESSION_START_BUDGET = 10240

TWIN_OF = "test-instruction-budget.sh"


def lines_of(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().rstrip("\n").split("\n")


def render(scope, runtime):
    return subprocess.run([sys.executable, "-I", RENDER, "render", "--scope", scope, "--runtime", runtime,
                           "--kind", "block", "--var", "PLAN_LABEL=Max", "--var", "READ_LINES=4000"],
                          check=True, capture_output=True, text=True).stdout


def handoff_of_a_started_task():
    """The handoff `state.py start` writes in a scaffolded scratch project."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(TEMPLATE_AI, os.path.join(tmp, ".ai"))
        with open(os.path.join(tmp, "a.txt"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "base"], check=True)
        subprocess.run([sys.executable, "-I", STATE, "--root", tmp, "start", "--goal",
                        "a goal of ordinary length for a task in flight", "--workflow", "feature",
                        "--files", "a.txt"], check=True, capture_output=True, text=True)
        with open(os.path.join(tmp, ".ai", "state", "handoff.md"), encoding="utf-8") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestLightTaskReads(unittest.TestCase):
    def test_r5_build_weight_verification(self):
        build = lines_of(os.path.join(ROOT, "skills", "rr-build", "SKILL.md"))
        weight = lines_of(os.path.join(TEMPLATE_AI, "policies", "weight.json"))
        testing = lines_of(os.path.join(TEMPLATE_AI, "policies", "testing.md"))
        start = testing.index("## Verification")
        end = next((i for i in range(start + 1, len(testing)) if testing[i].startswith("## ")), len(testing))
        total = len(build) + len(weight) + (end - start)
        self.assertLessEqual(total, 400, "rr-build %d + weight.json %d + Verification %d lines"
                             % (len(build), len(weight), end - start))


class TestSessionStart(unittest.TestCase):
    def test_session_start_cost(self):
        handoff = handoff_of_a_started_task()
        self.assertLessEqual(len(handoff.rstrip("\n").split("\n")), 30, "the handoff is at most 30 lines")
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                total = (len(render("global", runtime).encode()) + len(render("project", runtime).encode())
                         + len(handoff.encode()) + SUPERPOWERS_BYTES)
                self.assertLessEqual(total, SESSION_START_BUDGET, "%s SessionStart %d B" % (runtime, total))


class TestReaderTiers(unittest.TestCase):
    def test_r32_readers_by_judgement(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                block = render("global", runtime)
                fast = [line for line in block.split("\n") if "FAST" in line]
                self.assertTrue(any("runners" in line and "verbatim" in line for line in fast),
                                "FAST for runners and verbatim extraction")
                self.assertTrue(any("BALANCED" in line and "judge" in line for line in block.split("\n")),
                                "BALANCED for readers that judge")
                self.assertLessEqual(len(block.encode()), GLOBAL_BUDGET)


# R13 reads a shell `pass` up to its first inner quote, its escapes as written:
# these are the cases it records for the render sizes, the project block sizes and the stub phrases.
RENDER_SIZE_CASE = "render --scope $1 --runtime $2: $(printf '%s' "
PROJECT_BLOCK_CASE = "project block ($runtime) $(wc -c < "
STUB_PHRASE_CASE = r"the stub says \"$phrase\""

BLOCK_TEMPLATE = os.path.join(ROOT, "skills", "ai-init", "templates", "CLAUDE.block.md")
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
OVER_BUDGET_HINT = "trim instructions/stub.md or move the rule to routing.md / a policy"
SCAFFOLDED = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".junie/guidelines.md")
USER_TEXT = "# mine\n\n" + "a line the user wrote.\n" * 950
BLOCK_OF = """
import sys; sys.path.insert(0, sys.argv[1]); import render_instructions as r
for name in ("Codex-agentic", "codex-agentic"):
    text = "above\\n<!-- %s:start -->\\nbody\\n<!-- %s:end -->\\nbelow\\n" % (name, name)
    assert r.block_of(text) == "<!-- %s:start -->\\nbody\\n<!-- %s:end -->" % (name, name), name
assert r.block_of("<!-- claude-agentic:start -->\\nlone\\n<!-- Codex-agentic:start -->\\nx\\n<!-- Codex-agentic:end -->\\n") is None
assert r.block_of("<!-- Codex-agentic:start -->\\nno end\\n") is None
assert r.block_of("<!-- Codex-agentic:end -->\\n<!-- Codex-agentic:start -->\\n") is None
cur = "<!-- claude-agentic:start -->\\nbody\\n<!-- claude-agentic:end -->"
assert r.block_of("x\\n" + cur + "\\n<!-- Codex-agentic:start -->\\ny\\n<!-- Codex-agentic:end -->\\n") == cur
assert r.block_of("x\\n" + cur + "\\ny\\n") == cur
"""


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(text)


class TestInstructionBudget(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """The instruction stubs: one source, no drift, and a size every always-loaded
    file has to stay under. The scripts run under `python3 -I` and the installs and
    scaffolds through bash, all with a pinned HOME, as the shell suite drove them."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDownClass ends it
        cls.t = cls.tmp.name
        os.makedirs(os.path.join(cls.t, "home"))
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_HOME", "CODEX_DIR", "CLAUDE_DIR", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS",
                                "CLAUDE_CONFIG_DIR", "CLAUDE_AGENTIC_SHARED", "CLAUDE_AGENTIC_TEMPLATES",
                                "CLAUDE_ROUTING_TEMPLATES") and not k.startswith("RENDER_")}
        cls.env["HOME"] = os.path.join(cls.t, "home")
        # A freshly scaffolded project — in a path with a space. The four instruction
        # files are kept as scaffold-ai.sh left them, before project-scaffold.sh runs.
        cls.space = os.path.join(cls.t, "with space")
        cls.proj = os.path.join(cls.space, "proj")
        os.makedirs(cls.proj)
        cls.sh(["git", "init", "-q", "."], cwd=cls.proj)
        cls.sh(["bash", os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh"), cls.proj,
                "--runtime", "claude,codex,gemini,junie"])
        cls.fresh = {f: os.path.getsize(os.path.join(cls.proj, f)) if os.path.isfile(os.path.join(cls.proj, f))
                     else None for f in SCAFFOLDED}
        cls.sh(["bash", os.path.join(ROOT, "hooks", "project-scaffold.sh"), cls.proj, "--runtime", "claude"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def sh(cls, args, cwd=None, **extra):
        """rc and stdout+stderr, without the trailing newlines `$(…)` strips."""
        done = subprocess.run(args, cwd=cwd, env=dict(cls.env, **extra), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, check=False)
        return done.returncode, done.stdout.rstrip("\n")

    def render(self, *args, **extra):
        return self.sh(["python3", "-I", RENDER] + list(args), **extra)

    def stdout_of(self, *args):
        done = subprocess.run(["python3", "-I", RENDER] + list(args), env=self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, check=False)
        return done.stdout

    def measure(self, *args):
        """The fields of `measure`'s line: … <kind> <bytes> B."""
        return self.stdout_of("measure", *args).split()

    def path(self, *parts):
        return os.path.join(self.t, *parts)

    def test_one_source_the_committed_templates_are_rendered(self):
        """build --check: no template drifted from instructions/stub.md"""
        rc, out = self.render("build", "--check")
        self.assertEqual(rc, 0, "build --check: a template drifted from instructions/stub.md\n" + out)
        # A template that is edited by hand must be caught, or the check proves nothing.
        templates, project_init = self.path("templates"), self.path("project-init")
        shutil.copytree(os.path.join(ROOT, "skills", "ai-init", "templates"), templates, symlinks=True)
        shutil.copytree(os.path.join(ROOT, "skills", "project-init", "templates"), project_init, symlinks=True)
        write(os.path.join(templates, "CLAUDE.block.md"), "\n- an edit nobody put in the stub\n", "a")
        with self.subTest("build --check: a hand-edited template is drift"):
            rc, out = self.render("build", "--check", "--templates", templates, "--project-init", project_init)
            self.assertEqual(rc, 1, "exit %d: %s" % (rc, out))
            self.assertIn("CLAUDE.block.md", out)
        # and build writes it back
        self.render("build", "--templates", templates, "--project-init", project_init)
        with self.subTest("build: the edit is rendered away"):
            self.assertEqual(read(os.path.join(templates, "CLAUDE.block.md")), read(BLOCK_TEMPLATE))

    def test_every_scope_and_runtime_the_stub_declares_renders(self):
        for scope, runtime, kind in [(s, r, k) for s, k in (("project", "block"), ("skeleton", "skeleton"),
                                                            ("skeleton-sdlc", "skeleton"))
                                     for r in ("claude", "codex", "gemini", "junie")]:
            with self.subTest(RENDER_SIZE_CASE, scope=scope, runtime=runtime):
                rc, out = self.render("render", "--scope", scope, "--runtime", runtime, "--kind", kind)
                self.assertEqual(rc, 0, "render --scope %s --runtime %s\n%s" % (scope, runtime, out))
                self.assertTrue(out)

    def test_project_placeholder_survives_the_render(self):
        """skeleton keeps {{PROJECT}}"""
        # The scaffold fills it in, not the renderer.
        self.assertIn("{{PROJECT}}", self.stdout_of("render", "--scope", "skeleton", "--runtime", "claude",
                                                    "--kind", "skeleton"))

    def test_an_unknown_placeholder_is_an_error(self):
        """an unresolved {{X}} exits 1 with its line"""
        rc, out = self.render("render", "--scope", "global", "--runtime", "claude", "--kind", "block", RENDER_PLAN="")
        self.assertEqual(rc, 1, "exit %d: %s" % (rc, out))
        self.assertIn("unresolved placeholder", out)

    def test_measure_reports_the_managed_block(self):
        """measure: the block ($want B) out of a larger file"""
        tf = self.path("CLAUDE.md")
        write(tf, "# mine\n\nkeep this.\n\n" + read(BLOCK_TEMPLATE))
        want = self.measure(BLOCK_TEMPLATE)[-2]
        got = self.measure(tf)
        self.assertEqual((got[-2], got[-3]), (want, "block"), "want %s, got %s" % (want, got))
        with self.subTest("measure --whole: the file"):
            self.assertEqual(self.measure(tf, "--whole")[-3], "file")
        with self.subTest("measure --budget: over budget exits 1"):
            self.assertNotEqual(self.render("measure", tf, "--budget", "100")[0], 0)

    def test_the_project_block_stays_under_2048_b_in_every_runtime(self):
        for runtime in ("claude", "codex", "gemini", "junie"):
            out = self.path(runtime + ".block.md")
            self.render("render", "--scope", "project", "--runtime", runtime, "--kind", "block", "--out", out)
            with self.subTest(PROJECT_BLOCK_CASE, runtime=runtime):
                self.assertEqual(self.render("measure", out, "--budget", "2048")[0], 0,
                                 "over budget: the %s project block is %d B, budget 2048 B (project)\n%s"
                                 % (runtime, os.path.getsize(out), OVER_BUDGET_HINT))

    def test_a_freshly_scaffolded_instruction_file_stays_under_2048_b(self):
        """a fresh $f is $size B <= 2048"""
        # In a path with a space: setUpClass scaffolds into "with space/proj".
        for f, size in self.fresh.items():
            with self.subTest(f=f):
                self.assertIsNotNone(size, "%s scaffolded" % f)
                self.assertLessEqual(size, 2048, "over budget: %s is %s B, budget 2048 B (project)\n%s"
                                     % (f, size, OVER_BUDGET_HINT))

    def test_the_stub_alone_is_enough_to_work_safely(self):
        """the stub alone is enough to work safely (R5)"""
        stub = self.stdout_of("render", "--scope", "global", "--runtime", "claude", "--kind", "block",
                              "--var", "PLAN_LABEL=Max", "--var", "READ_LINES=4000")
        for phrase in ("/rr-build <request>", ".ai/AGENTS.md", "SCOPE_CHANGE_REQUIRED", "/rr-setup",
                       "human approval", "source of truth", "one batch", "routing.md"):
            with self.subTest(STUB_PHRASE_CASE, phrase=phrase):
                self.assertIn(phrase, stub, "the stub no longer says %r: it is what makes the stub safe alone" % phrase)

    def test_the_stub_names_tiers_never_models(self):
        """no model name in instructions/stub.md"""
        stub = read(os.path.join(ROOT, "instructions", "stub.md"))
        hits = [line for line in stub.splitlines()
                if re.search(r"\b(haiku|sonnet|opus|fable|terra|sol|astra)\b", line, re.I | re.A)
                or re.search(r"gpt-[0-9]", line, re.I)]
        self.assertEqual(hits[:3], [], "a model name reached instructions/stub.md")

    def test_the_constitution_ships_prefilled_and_inside_its_cap(self):
        const = os.path.join(self.proj, "docs", "sdlc", "constitution.md")
        if os.path.isfile(const):
            with self.subTest("the scaffolded constitution is within 15 principles and 4096 B"):
                self.assertEqual(self.render("constitution", const)[0], 0, "the scaffolded constitution is over its cap")
            with self.subTest("C1-C5 ship prefilled"):
                self.assertRegex(read(const), r"(?m)^C5\.", "C1-C5 missing")
        else:
            with self.subTest("the constitution template is within 15 principles and 4096 B"):
                template = os.path.join(ROOT, "skills", "project-init", "templates", "constitution.md")
                self.assertEqual(self.render("constitution", template)[0], 0, "the constitution template is over its cap")
        for f in ("skills/rr-spec/SKILL.md", "skills/rr-plan/SKILL.md"):
            with self.subTest("$f reads the constitution", f=f):
                self.assertIn("docs/sdlc/constitution.md", read(os.path.join(ROOT, f)),
                              "%s does not read the constitution" % f)

    def test_the_router_points_at_files_that_exist_and_routes(self):
        """the router points at files that exist, and routes rather than explains (R7)"""
        router_path = os.path.join(self.proj, ".ai", "AGENTS.md")
        self.assertTrue(os.path.isfile(router_path), "the router was not scaffolded")
        router = read(router_path)
        with self.subTest("every path the router names exists in a scaffolded project"):
            refs = sorted({r for r in re.findall(r"`([a-zA-Z0-9_./<>-]*)`", router)
                           if re.search(r"\.(md|json)$", r) and "/" in r})
            missing = []
            for ref in refs:
                probe = re.sub(r"<[a-z-]*>", "*", ref) if "<" in ref else ref
                if not any(glob.glob(os.path.join(base, probe)) for base in
                           (os.path.join(self.proj, ".ai"), self.proj, os.path.join(ROOT, "ai"))):
                    missing.append(ref)
            self.assertEqual(missing, [], "the router points at files that do not exist")
        with self.subTest("the router routes; the steps live in the rr- skills"):
            self.assertNotIn("ADVERSARIAL REVIEW", router, "the stage diagram is still in the router")
        # The shared tree is named by an insertion before the routing table, never
        # inside it, so adopt keeps appending rows to the table (H1).
        lines = router.splitlines()
        with self.subTest("the router has one '## Shared files' section"):
            self.assertEqual(lines.count("## Shared files"), 1, "the router needs '## Shared files' exactly once")
        section, nexthead = [], ""
        if "## Shared files" in lines:
            for line in lines[lines.index("## Shared files") + 1:]:
                if line.startswith("## "):
                    nexthead = line
                    break
                section.append(line)
        with self.subTest("the section sits right before the routing table"):
            self.assertEqual(nexthead, "## Doing X → read Y", "the section must precede '## Doing X → read Y'")
        with self.subTest("the Shared files section is prose only"):
            self.assertFalse([line for line in section if line.startswith("|")], "the Shared files section has a table line")
        with self.subTest("the router is $size B <= 4096 (advisory)"):
            self.assertLessEqual(os.path.getsize(router_path), 4096, "the router is over its advisory cap 4096 B")
        with self.subTest("the review pass lives in the /rr-review skill"):
            self.assertIn("$STATE review --verdict", read(os.path.join(ROOT, "skills", "rr-review", "SKILL.md")),
                          "the review pass was lost from /rr-review")

    def test_rules_render_into_the_directories_they_name(self):
        """.ai/rules/ renders into the directories it names, and only there (R9)"""
        rp = os.path.join(self.space, "rules")
        os.makedirs(rp)
        self.sh(["bash", os.path.join(ROOT, "hooks", "project-scaffold.sh"), rp, "--runtime", "both"])
        self.sh(["bash", os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh"), rp, "--runtime", "both"])
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "instructions", "rules-project", ".ai"),
                        os.path.join(rp, ".ai"), dirs_exist_ok=True)
        os.makedirs(os.path.join(rp, "tests", "Payment"))
        write(os.path.join(rp, "src", "Payment", "CLAUDE.md"), "# Payment\n\nmy own note\n")
        rc, out = self.sh(["python3", "-I", UPDATE, rp, "--apply"])
        self.assertEqual(rc, 0, "the rules round trip could not be applied\n" + out)
        for f in ("src/Payment/CLAUDE.md", "src/Payment/AGENTS.md", "tests/Payment/CLAUDE.md",
                  "tests/Payment/AGENTS.md", ".claude/rules/payment.md"):
            with self.subTest("$f was rendered", f=f):
                self.assertTrue(os.path.isfile(os.path.join(rp, f)), "%s was not rendered" % f)
        payment = read(os.path.join(rp, "src", "Payment", "CLAUDE.md"))
        with self.subTest("one file carries both rules that name its directory"):
            self.assertIn("claude-agentic:rule:payment:start", payment)
            self.assertIn("claude-agentic:rule:imports:start", payment)
        with self.subTest("the text outside the markers survives the render"):
            self.assertIn("my own note", payment, "the render ate the project's own text")
        scoped = read(os.path.join(rp, ".claude", "rules", "payment.md"))
        with self.subTest("the path-scoped copy opens with its frontmatter, as Claude Code reads it"):
            self.assertEqual(scoped.split("\n", 1)[0], "---", ".claude/rules/payment.md must start with ---")
        with self.subTest("and says which file to edit instead"):
            self.assertIn("generated from .ai/rules/payment.md", scoped, "the generated copy does not name its source")
        self.assertFalse(os.path.isfile(os.path.join(rp, "tests", "Payment", ".claude")),
                         "a rule wrote outside the directories it names")
        with self.subTest("re-rendering is a no-op: the round trip is idempotent"):
            out = self.sh(["python3", "-I", UPDATE, rp])[1]
            self.assertRegex(out, r"(?m)^0 automatic", "the second render is not a no-op")
        os.remove(os.path.join(rp, ".ai", "rules", "imports.md"))
        with self.subTest("a removed source takes its rendered blocks with it"):
            out = self.sh(["python3", "-I", UPDATE, rp])[1]
            self.assertIn("rule block imports removed", out, "a removed rule left its blocks behind")

    def test_a_real_install_keeps_the_global_block_under_budget(self):
        """a real install: the global block stays under 2560 B and routing.md is written"""
        for label, target, args in (("max-fable", "claude", ["--plan", "max", "--fable", "yes"]),
                                    ("max-plain", "claude", ["--plan", "max", "--fable", "no"]),
                                    ("pro", "claude", ["--plan", "pro"]),
                                    ("team-max", "claude", ["--plan", "team-max", "--fable", "yes"]),
                                    ("team-pro", "claude", ["--plan", "team-pro"]),
                                    ("codex-plus", "codex", ["--codex-plan", "plus"]),
                                    ("codex-pro", "codex", ["--codex-plan", "pro"])):
            d = os.path.join(self.space, label)
            os.makedirs(d)
            if target == "claude":
                rc, out = self.sh(["bash", INSTALL, "--target", "claude"] + args, CLAUDE_DIR=d)
                file = os.path.join(d, "CLAUDE.md")
            else:
                rc, out = self.sh(["bash", INSTALL, "--target", "codex"] + args, CODEX_DIR=d,
                                  CLAUDE_DIR=os.path.join(d, "claude"))
                file = os.path.join(d, "AGENTS.md")
            with self.subTest("$label: global block $size B <= 2560", label=label):
                self.assertEqual(rc, 0, "install %s\n%s" % (label, "\n".join(out.splitlines()[-3:])))
                size = int(self.measure(file)[-2])
                self.assertLessEqual(size, GLOBAL_BUDGET, "over budget: %s block is %d B, budget 2560 B (global)\n%s"
                                     % (os.path.basename(file), size, OVER_BUDGET_HINT))
            if rc != 0:
                continue
            with self.subTest("$label: routing.md installed", label=label):
                self.assertTrue(os.path.isfile(os.path.join(d, "claude-agentic", "routing.md")),
                                "%s: routing.md missing" % label)
            with self.subTest("$label: the size line is printed", label=label):
                self.assertRegex(out, r"managed block .* B \(budget", "%s: no size line" % label)

    def test_a_users_own_20_kib_of_text_is_measured_never_touched(self):
        userdir = os.path.join(self.space, "userfile")
        write(os.path.join(userdir, "CLAUDE.md"), USER_TEXT)
        rc, out = self.sh(["bash", INSTALL, "--target", "claude", "--plan", "max", "--fable", "yes"], CLAUDE_DIR=userdir)
        with self.subTest("a 20 KiB user file does not fail the install"):
            self.assertEqual(rc, 0, "install exited %d\n%s" % (rc, "\n".join(out.splitlines()[-3:])))
        with self.subTest("the size line names the user's share"):
            self.assertIn("the rest is yours", out, "no size line for the large file")
        with self.subTest("every line the user wrote survives byte-identical"):
            text = read(os.path.join(userdir, "CLAUDE.md"))
            start = text.find("<!-- claude-agentic:start -->")
            outside = text[:start] if start >= 0 else text
            self.assertEqual(outside.count("a line the user wrote.\n"), 950, "the user's text was changed")

    def test_codex_is_told_once_near_its_32_kib_limit(self):
        """Codex is told once when the whole file gets close to its 32 KiB limit"""
        # Codex reads at most 32 KiB of project documents, and the plugin owns only the
        # block. Half of that is where saying something is still useful; below it, a
        # line about a limit nobody is near is noise.
        big, small = os.path.join(self.space, "codex-big"), os.path.join(self.space, "codex-small")
        write(os.path.join(big, "AGENTS.md"), USER_TEXT)
        os.makedirs(small)
        with self.subTest("a 20 KiB AGENTS.md gets the advisory"):
            out = self.sh(["bash", INSTALL, "--target", "codex", "--codex-plan", "pro"], CODEX_DIR=big,
                          CLAUDE_DIR=os.path.join(big, "claude"))[1]
            self.assertIn("Codex reads at most 32 KiB", out, "no advisory for a 20 KiB AGENTS.md")
        with self.subTest("a fresh AGENTS.md is left alone about the limit"):
            out = self.sh(["bash", INSTALL, "--target", "codex", "--codex-plan", "pro"], CODEX_DIR=small,
                          CLAUDE_DIR=os.path.join(small, "claude"))[1]
            self.assertNotIn("Codex reads at most 32 KiB", out, "a fresh AGENTS.md got the advisory")

    def test_project_update_hints_at_an_over_budget_block(self):
        """/project-update hints at an over-budget block and an oversized constitution"""
        # Downstream the budget is advisory: /project-update measures, names the byte
        # count and says whose the file is to trim. It never rewrites an edited block.
        hint = os.path.join(self.space, "hints")
        shutil.copytree(self.proj, hint, symlinks=True)
        claude = os.path.join(hint, "CLAUDE.md")
        text = read(claude)
        end = text.find("<!-- claude-agentic:end -->")
        write(claude, text[:end] + "- a rule this project added inside the markers.\n" * 60 + text[end:])
        write(os.path.join(hint, "docs", "sdlc", "constitution.md"),
              "# Constitution\n\n" + "".join("C%d. a principle this project does not negotiate.\n" % n
                                               for n in range(1, 21)))
        out = self.sh(["python3", "-I", UPDATE, hint])[1]
        tail = "\n".join(out.splitlines()[-5:])
        with self.subTest("the over-budget block is named with its byte count"):
            self.assertRegex(out, r"CLAUDE.md: the managed block is .* B, budget 2048 B",
                             "no budget hint for an over-budget block\n" + tail)
        with self.subTest("the hint says an edited block is the project's to trim"):
            self.assertIn("trimming it is yours", out, "the budget hint does not say whose the block is\n" + tail)
        with self.subTest("the constitution cap is advisory here, and named"):
            self.assertIn("docs/sdlc/constitution.md: 20 principles, at most 15", out, "no constitution hint\n" + tail)
        with self.subTest("an edited block is still never rewritten"):
            self.assertNotRegex(out, r"(?m)^  update .*CLAUDE.md", "the plugin planned a write over an edited block")

    def test_a_legacy_codex_agentic_marker_pair_is_the_managed_block_too(self):
        """measure: the legacy block ($want B) out of a larger file"""
        legacy_block = self.path("legacy-block")
        write(legacy_block, re.sub(r"claude-agentic:(start|end)", r"Codex-agentic:\1", read(BLOCK_TEMPLATE)))
        lb = self.path("legacy.md")
        write(lb, "# mine\n\nkeep this.\n\n" + read(legacy_block) + "\n# below\nmore of mine\n")
        want = self.measure(legacy_block)[-2]
        got = self.measure(lb)
        self.assertEqual((got[-2], got[-3]), (want, "block"), "measure: a legacy pair is not seen as the block")
        with self.subTest("block_of: both legacy spellings, verbatim; half a current pair is none"):
            rc, out = self.sh(["python3", "-I", "-c", BLOCK_OF, os.path.join(ROOT, "skills", "project-update")])
            self.assertEqual(rc, 0, "block_of on legacy markers\n" + out)


if __name__ == "__main__":
    unittest.main()
