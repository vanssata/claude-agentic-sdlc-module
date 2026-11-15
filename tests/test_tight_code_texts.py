"""R23-R27: the tight-code sentences are in their files, in the right section."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIMPLEST = "Write the simplest version that passes the step's tests."
NEW_DEP = "A new dependency is not yours to add."
PADDING = "padding, last and on a first pass only"
DEP_ITEM = "a new dependency without its line in the plan"
READ_FIRST_LINE = "- <file:line> — <why a human reads this before approving>   # at most five"
CLOSING = "In existing code the file's conventions win; the last three lines hold for the\nfunctions you add."


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def section(text, heading, stop="\n## "):
    """The text from `heading` to the next `stop`."""
    start = text.index(heading)
    end = text.find(stop, start + len(heading))
    return text[start:] if end < 0 else text[start:end]


class TightCodeTexts(unittest.TestCase):
    def test_implementer_bullets(self):
        body = section(read("ai/agents/implementer.md"), "## While implementing")
        self.assertIn(SIMPLEST, body)
        self.assertIn(NEW_DEP, body)
        self.assertIn("`SCOPE_CHANGE_REQUIRED` naming the manifest and the reason.", body)

    def test_reviewer_lists_carry_both_items(self):
        lists = [
            section(read("ai/agents/reviewer.md"), "## Look specifically for"),
            section(read("agents/ai-reviewer.md.tmpl"), "## Look for"),
        ]
        for body in lists:
            flat = " ".join(body.split())
            self.assertIn(DEP_ITEM, flat)
            self.assertIn(PADDING, flat)
            self.assertIn("each titled `padding:`", flat)
            self.assertLess(flat.index(DEP_ITEM), flat.index(PADDING))

    def test_padding_is_last_in_both_lists(self):
        md = section(read("ai/agents/reviewer.md"), "## Look specifically for")
        items = [i for i in md.split("\n- ") if i.strip()]
        self.assertTrue(items[-1].startswith(PADDING))
        tmpl = section(read("agents/ai-reviewer.md.tmpl"), "## Look for")
        self.assertTrue(" ".join(tmpl.split()).split(" · ")[-1].startswith(PADDING))

    def test_read_first_after_verdict_full_mode_only(self):
        out = section(read("agents/ai-reviewer.md.tmpl"), "## Output", "\n## QUESTIONS_NEEDED")
        self.assertIn("## READ FIRST", out)
        self.assertGreater(out.index("## READ FIRST"), out.index("## VERDICT"))
        self.assertIn(READ_FIRST_LINE, out)
        self.assertIn("In full mode only, after VERDICT", out)
        self.assertIn("unverified: <what the review could not check", out)

    def test_coding_template_general(self):
        body = section(read("skills/ai-init/templates/.ai/policies/coding.md"), "## General")
        self.assertIn("- A function does one thing and its name says which.", body)
        self.assertIn("- Inputs come in as parameters", body)
        self.assertIn("- An error message says what failed, what was expected, what was found, and", body)
        self.assertIn(CLOSING, body)

    def test_rr_ship_names_read_first(self):
        text = read("skills/rr-ship/SKILL.md")
        self.assertIn("the review's `READ FIRST` lines", text)
        self.assertIn("findings, the rollback, and that command **verbatim**", text)


if __name__ == "__main__":
    unittest.main()
