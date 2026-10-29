#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The skills surface (R1): seven `rr-` skills named for the job — eight with
`rr-build-all`, the batch loop — the ten old names kept for one version as short
aliases, and no skill text that calls a `state.py` subcommand or an agent the
redesign removes.

`step_test_command` hands every test path to bash; the line above makes bash
re-run this file under python3.
"""
import glob
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")

NEW = ("rr-setup", "rr-spec", "rr-plan", "rr-build", "rr-build-all", "rr-review", "rr-ship", "rr-status")
# old name -> the body's first line after "deprecated → /"
ALIASES = {
    "ai-init": "rr-setup", "ai-audit": "rr-setup --audit", "project-init": "rr-setup",
    "project-update": "rr-setup --update", "sdlc-intent": "rr-spec", "sdlc-spec": "rr-spec",
    "sdlc-plan": "rr-plan", "ai-task": "rr-build", "ai-status": "rr-status",
    "usage-report": "rr-status --cost",
}
# The spec's "removed (19)" (§Interfaces, state.py surface).
REMOVED_COMMANDS = ("init get stage risk triage quick plan remediate step review-gate test-run step-split "
                    "set risks modules questions note events done archive").split()
# Every agent but the five that remain after 2.4: Explore, log-reader,
# ai-discovery, ai-reviewer, architect.
REMOVED_AGENTS = ("ai-context ai-expert ai-implementer ai-indexer ai-planner ai-release ai-risk ai-security "
                  "ai-tester ai-reviewer-balanced ai-risk-strong ai-planner-strong ai-expert-strong").split()
CALL_RE = re.compile(r"(?:state\.py|\$STATE)(?:\s+--root\s+\S+)?\s+(%s)(?![\w-])"
                     % "|".join(re.escape(c) for c in sorted(REMOVED_COMMANDS, key=len, reverse=True)))
AGENT_RE = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(re.escape(a) for a in REMOVED_AGENTS))


def read(name):
    with open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8") as fh:
        return fh.read()


def split(text):
    """(frontmatter fields, body lines) of a SKILL.md."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return {}, lines
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields, lines[end + 1:]


class TestInventory(unittest.TestCase):
    def test_eighteen_skills(self):
        found = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
        self.assertEqual(found, sorted(NEW + tuple(ALIASES)))

    def test_no_bare_status(self):
        self.assertFalse(os.path.exists(os.path.join(SKILLS, "status")), "skills/status moved to skills/rr-status")

    def test_status_script_moved(self):
        self.assertTrue(os.path.isfile(os.path.join(SKILLS, "rr-status", "status.py")))

    def test_names_match_directories(self):
        for name in NEW + tuple(ALIASES):
            with self.subTest(skill=name):
                self.assertEqual(split(read(name))[0].get("name"), name)


class TestAliases(unittest.TestCase):
    def test_alias_shape(self):
        for name, target in ALIASES.items():
            with self.subTest(alias=name):
                text = read(name)
                fields, body = split(text)
                self.assertLessEqual(len(text.rstrip("\n").split("\n")), 12, "at most 12 lines")
                self.assertLessEqual(len(fields.get("description", "").encode()), 80, "description ≤ 80 B")
                first = next((line for line in body if line.strip()), "")
                self.assertEqual(first, "deprecated → /%s" % target)
                self.assertIn("skills/%s/SKILL.md" % target.split()[0], text, "names the target's SKILL.md")


class TestNewSkills(unittest.TestCase):
    def test_size(self):
        for name in NEW:
            with self.subTest(skill=name):
                text = read(name)
                self.assertLessEqual(len(text.rstrip("\n").split("\n")), 300, "at most 300 lines")
                description = split(text)[0].get("description", "")
                self.assertTrue(description, "has a description")
                self.assertLessEqual(len(description.encode()), 1024, "description ≤ 1024 B")

    def test_no_removed_subcommand(self):
        for name in NEW:
            with self.subTest(skill=name):
                hits = ["%d: %s" % (n, line.strip()) for n, line in enumerate(read(name).split("\n"), 1)
                        if CALL_RE.search(line)]
                self.assertEqual(hits, [], "calls a removed state.py subcommand")

    def test_no_removed_agent(self):
        for name in NEW:
            with self.subTest(skill=name):
                hits = ["%d: %s" % (n, line.strip()) for n, line in enumerate(read(name).split("\n"), 1)
                        if AGENT_RE.search(line)]
                self.assertEqual(hits, [], "names an agent 2.4 removes")

    def test_ship_names_the_dialog_commands(self):
        """R36 7c: rr-ship lists the decision commands state.py now has; each
        one it names must be a subcommand state.py accepts."""
        text = read("rr-ship").replace("\n  ", " ")
        state_py = os.path.join(SKILLS, "ai-task", "state.py")
        for phrase in ("$STATE decision show --json", "$STATE decision settle --id", "$STATE decision open --kind commit",
                       "$STATE decision fallback --id", "$STATE consent"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        usage = {name: subprocess.run([sys.executable, "-I", state_py, name, "--help"], capture_output=True,
                                      text=True, check=False) for name in ("decision", "consent")}
        self.assertTrue(all(done.returncode == 0 for done in usage.values()))
        self.assertIn("{show,open,settle,fallback}", usage["decision"].stdout)
        self.assertIn("{audit}", usage["consent"].stdout)

    def test_build_all_names_live_commands(self):
        """The batch loop's skill names the state.py commands it runs, and each
        one is a subcommand state.py accepts (docs/sdlc/specs/batch-build.md R12)."""
        text = read("rr-build-all").replace("\n  ", " ").replace(" \\\n", " ")
        for phrase in ("$STATE steps --ready", "$STATE batch off --by", "--batch --by", "$STATE step-done",
                       "$STATE start --amend --files", "$STATE verify --scope all --after-fix",
                       "$STATE review --closes", "agents/implementer.md", "batch.review_rounds_max",
                       "batch.max_suite_runs", "batch.parallel", "batch.tier", "batch.default"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertNotIn("Sonnet", text, "tiers, never models (Codex runs the same text)")
        state_py = os.path.join(SKILLS, "ai-task", "state.py")
        usage = {name: subprocess.run([sys.executable, "-I", state_py, name, "--help"], capture_output=True,
                                      text=True, check=False) for name in ("steps", "batch", "start")}
        self.assertTrue(all(done.returncode == 0 for done in usage.values()))
        self.assertIn("--ready", usage["steps"].stdout)
        self.assertIn("{on,off}", usage["batch"].stdout)
        self.assertIn("--no-batch", usage["start"].stdout)

    def test_medium_and_low_findings_go_to_the_register(self):
        """R8 (2a): pass_with_findings fixes the in-scope HIGHs; each MEDIUM and LOW is one
        `memory risk add`; only a BLOCKER, a HIGH or a regression buys an --after-fix run."""
        for name, marker in (("rr-review", "- **pass_with_findings:**"), ("rr-build-all", "- **pass_with_findings**")):
            text = read(name)
            start = text.index(marker)
            bullet = re.split(r"\n- \*\*|\n\n", text[start + 2:], maxsplit=1)[0]
            with self.subTest(skill=name):
                self.assertIn("memory risk add", bullet)
                self.assertIn("MEDIUM", bullet)
                self.assertIn("regression", bullet)
                self.assertNotIn("the MEDIUMs worth it", text)

    def test_the_reviewer_is_bounded(self):
        """R11 (3): the reviewer runs only the named tests and stops at about 40 tool calls in
        light and guarded, about 80 in full; what it did not reach is listed, not hidden."""
        with open(os.path.join(ROOT, "agents", "ai-reviewer.md.tmpl"), encoding="utf-8") as fh:
            tmpl = fh.read()
        for needle in ("step_test_command", "40 tool calls", "80", "not reached (budget)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, tmpl)
        self.assertNotIn("Verify by execution where execution is possible", tmpl)
        text = read("rr-review")
        brief = text[text.index("## 2. Brief"):text.index("## 3.")]
        self.assertIn("40 tool calls", brief)
        self.assertIn("80", brief)

    def test_the_chains_are_named(self):
        """R15 (5): the calls that always follow each other are one `&&` line; `review && close`
        only after `pass` (concern 13: `review` exits 0 for every verdict)."""
        def section(text, head, nxt):
            return text[text.index(head):text.index(nxt, text.index(head))]

        build = section(read("rr-build"), "## 4.", "## 5.")
        self.assertIn("step-done <id> && $STATE verify --scope all", build)
        self.assertRegex(build, r"(?i)last step")
        review = read("rr-review")
        review = review[review.index("## 4."):]
        self.assertRegex(review, r"--verdict pass\b[^\n]*&& \$STATE close")
        self.assertRegex(review, r"`pass` only")
        chain = 'verify --scope step --files "<doc_tests>" && $STATE verify --scope e2e && $STATE close'
        self.assertIn(chain, section(read("rr-ship"), "## 1.", "## 2."))
        self.assertIn("only documents changed since run", section(read("rr-ship"), "## 1.", "## 2."))
        # M3: `close` prints that text under `review required`, never `verify required`.
        rows = [r for r in section(read("rr-ship"), "## 1.", "## 2.").splitlines()
                if "only documents changed since run" in r and r.startswith("|")]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("review required", rows[0])
        self.assertNotIn("verify required", rows[0])
        build_all = read("rr-build-all")
        self.assertIn("step-done <id> && $STATE verify --scope all", section(build_all, "## 4.", "## 5."))
        self.assertIn(chain, section(build_all, "## 6.", "## Switching"))

    def test_the_checks_bite(self):
        # The two patterns must catch the forms the old text used, or a clean
        # pass above proves nothing.
        for line in ("$STATE quick --goal x", "python3 state.py --root /p test-run --scope all",
                     "`state.py set review_status passed`", "$STATE questions --sync", "$STATE step s1"):
            self.assertRegex(line, CALL_RE)
        for line in ("$STATE step-done s1", "state.py review --verdict pass", "state.py verify --scope all",
                     "state.py start --amend", "$STATE handoff --print", "$STATE decision show --json",
                     "$STATE consent audit"):
            self.assertNotRegex(line, CALL_RE)
        self.assertRegex("`ai-reviewer-balanced` on Codex", AGENT_RE)
        self.assertNotRegex("one `ai-reviewer` on STRONG", AGENT_RE)


if __name__ == "__main__":
    unittest.main()
