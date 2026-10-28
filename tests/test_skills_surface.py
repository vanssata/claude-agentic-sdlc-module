#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The skills surface (R1): seven `rr-` skills named for the job, the ten old
names kept for one version as short aliases, and no skill text that calls a
`state.py` subcommand or an agent the redesign removes.

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

NEW = ("rr-setup", "rr-spec", "rr-plan", "rr-build", "rr-review", "rr-ship", "rr-status")
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
    def test_seventeen_skills(self):
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
