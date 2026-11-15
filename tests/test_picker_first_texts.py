"""R10: rr-build 5 and rr-spec 2 ask through the question tool first, relay with --via picker."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def section(skill, heading):
    with open(os.path.join(ROOT, "skills", skill, "SKILL.md"), encoding="utf-8") as fh:
        text = fh.read()
    body = re.split(r"^## ", text, flags=re.M)
    hit = [b for b in body if b.startswith(heading)]
    return " ".join(hit[0].split())


class TestPickerFirstTexts(unittest.TestCase):
    def test_each_skill_asks_through_the_question_tool_first(self):
        for skill, heading in (("rr-build", "5."), ("rr-spec", "2.")):
            with self.subTest(skill):
                text = section(skill, heading)
                for phrase in ("DIALOG_PENDING", "no decision pending", "--via picker"):
                    self.assertIn(phrase, text)
                self.assertLess(text.index("question tool"), text.index("[Answer]:"))
                self.assertRegex(text, r"(file|record)[^.]*(stays|is) the\s+record|stays the record")


if __name__ == "__main__":
    unittest.main()
