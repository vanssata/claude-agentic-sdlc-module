#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The shared prompts name tiers, never models (WP5 R15, I8). A model is a plan's
choice: profiles/*.json decide it, install.sh renders it, and at run time
`state.py profile --tier <TIER>` prints it. A model name written into a prompt
is wrong on every other plan and every other runtime, so the prompts carry
FAST / BALANCED / STRONG / EXPERT and the placeholders that install fills in.

The dry runs go through `bash install.sh` as the shell suite drove them, with a
pinned HOME and a CLAUDE_DIR / CODEX_DIR that does not exist.
"""
import glob
import os
import re
import subprocess
import tempfile
import unittest
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install.sh")

TWIN_OF = "test-shared-prompts-model-free.sh"

# R13 reads the shell `pass` text as written, `$(…)` included.
SCOPE_CASE = r"the shared-prompt scope ($(printf '%s\n' $files | wc -l) files) names no model"

# The I8 patterns, as the shell suite's three greps: the first ignores case.
I8 = (re.compile(r"\b(haiku|sonnet|opus|opusplan|fable)\b", re.I | re.A),
      re.compile(r"\b(Terra|Sol|Astra)\b", re.A),
      re.compile(r"gpt-[0-9]|claude-(opus|sonnet|haiku|fable)-"))
R10 = re.compile(r"light ≤|guarded 3")
WEIGHT_TABLE = re.compile(r"/policies/weight\.(json|md)$")


def files_under(top):
    """`find <top> -type f`, relative to ROOT."""
    out = []
    for d, _, names in os.walk(os.path.join(ROOT, top)):
        for n in names:
            path = os.path.join(d, n)
            if os.path.isfile(path) and not os.path.islink(path):
                out.append(os.path.relpath(path, ROOT))
    return out


def scope():
    """The shared-prompt scope (I8). profiles/, install.sh, scripts/, hooks/, tests/,
    docs/, README.md, prices.json, the frozen history and agents/superseded/ are
    out of it on purpose: that is where models are *supposed* to be named."""
    files = ["instructions/stub.md", "instructions/routing.md"]
    files += [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "agents", "*.md.tmpl"))]
    files += [p for p in files_under("skills")
              if p.endswith(".md") and not p.startswith("skills/project-update/history/")]
    files += files_under("skills/ai-init/templates") + files_under("skills/project-init/templates")
    files += files_under("ai")
    return sorted(set(files))


def lines_of(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        return fh.read().splitlines()


def grep(patterns, paths, base=ROOT):
    """file:line:text for every line any pattern matches."""
    found = set()
    for path in paths:
        full = os.path.join(base, path)
        if not os.path.isfile(full):
            continue
        for n, line in enumerate(lines_of(full), 1):
            if any(p.search(line) for p in patterns):
                found.add("%s:%d:%s" % (path, n, line))
    return sorted(found)


def sed_range(text, start, end):
    """`sed -n '/start/,/end/p'`: every range, both ends included, open to EOF."""
    out, inside = [], False
    for line in text.splitlines():
        if not inside and re.search(start, line):
            inside = True
            out.append(line)
            continue
        if inside:
            out.append(line)
            if re.search(end, line):
                inside = False
    return out


def env_for(**extra):
    tmp_home = extra.pop("HOME")
    env = {k: v for k, v in os.environ.items()
           if k not in ("CODEX_HOME", "CODEX_DIR", "CLAUDE_DIR", "AI_UNATTENDED", "CLAUDE_CONFIG_DIR",
                        "CLAUDE_AGENTIC_SHARED", "CLAUDE_ROUTING_TEMPLATES", "CLAUDE_AGENTIC_TEMPLATES")
           and not k.startswith("RISKRAILS_")}
    env["HOME"] = tmp_home
    env.update(extra)
    return env


class TestSharedPromptsModelFree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def dry_run(self, *args, **extra):
        done = subprocess.run(["bash", INSTALL] + list(args) + ["--dry-run"], cwd=ROOT,
                              env=env_for(HOME=self.home, **extra), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, check=False)
        return done.stdout

    def write_block(self, name, lines):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return name

    def test_no_model_name_in_the_shared_prompts(self):
        """the shared-prompt scope (N files) names no model"""
        files = scope()
        found = grep(I8, files)
        self.assertEqual(found[:40], [], "%s: model names in shared prompts (%d lines)" % (SCOPE_CASE, len(found)))

    def test_mode_thresholds_live_in_the_weight_table_alone(self):
        """no shared prompt restates a mode threshold"""
        # A threshold copied into a prompt goes stale the day weight.json changes. Only
        # the table, its generated mirror and docs/weight.md (outside this scope) say it.
        found = [h for h in grep([R10], scope()) if not WEIGHT_TABLE.search(h.split(":", 1)[0])]
        self.assertEqual(found[:10], [], "mode thresholds outside weight.json / weight.md")
        with self.subTest("and the pattern catches the weight line's wording"):
            self.assertTrue(R10.search("light ≤2 · guarded 3–7"), "the R10 pattern no longer matches the weight line")

    def test_rendered_claude_block_is_model_free_on_every_plan(self):
        for plan in ("pro", "team-pro", "team-max", "max", "max20"):
            out = self.dry_run("--target", "claude", "--plan", plan,
                               CLAUDE_DIR=os.path.join(self.tmp.name, "none"))
            block = sed_range(out, r"^== CLAUDE.md managed block:", r"^== routing.md")[1:-1]
            with self.subTest(Template("--plan $plan: the CLAUDE.md block names no model").substitute(plan=plan)):
                self.assertTrue(block, "--plan %s: no managed block in the dry run" % plan)
                b = grep(I8, [self.write_block("block-" + plan, block)], base=self.tmp.name)
                self.assertEqual(b[:5], [], "--plan %s: models in the block" % plan)
            routing = "\n".join(sed_range(out, r"^== routing.md \(on demand\)", r"^== profile.json"))
            with self.subTest(Template("--plan $plan: routing.md renders completely").substitute(plan=plan)):
                self.assertNotIn("{{", routing, "--plan %s: routing.md has an unrendered placeholder" % plan)

    def test_rendered_agents_block_is_model_free_on_every_codex_plan(self):
        for plan in ("plus", "pro"):
            out = self.dry_run("--target", "codex", "--codex-plan", plan,
                               CODEX_DIR=os.path.join(self.tmp.name, "none-cx"))
            block = sed_range(out, r"^== AGENTS.md managed block:", r"^== routing.md")[1:-1]
            with self.subTest(Template("--codex-plan $plan: the AGENTS.md block names no model").substitute(plan=plan)):
                b = grep(I8, [self.write_block("cblock-" + plan, block)], base=self.tmp.name)
                self.assertEqual(b[:5], [], "--codex-plan %s: models in the block" % plan)


if __name__ == "__main__":
    unittest.main()
