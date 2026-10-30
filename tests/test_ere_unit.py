#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
hooks/guard/ere.py and hooks/guard/common.py, unit by unit.

The ERE translator is held against bash itself: each pattern and subject goes
through `[[ $s =~ $p ]]` under LC_ALL=C and C.UTF-8 (glibc regcomp/regexec),
and the port must agree, including on what glibc rejects as invalid. The deny
encoding is held against `jq -Rsc`, and the payload reader against the jq
filters read_payload ran.
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from guard import common, ere, paths  # noqa: E402  pylint: disable=wrong-import-position

TIMED_FACTOR = float(os.environ.get("AI_TIMED_FACTOR") or 1)

U3000 = "　"
# (subject, pattern): every construct the guards' patterns use, and the edges.
CASES = [
    ("a)", "a)"), (")", ")"), ("*a", "*a"), ("a", "a|*b"), ("a{", "a{"), ("{1}a", "{1}a"),
    ("a{1", "a{1"), ("a{,2}", "a{,2}"), ("aa", "a{,2}"), ("ab", "a{1,0}b"), ("a", "a**"),
    ("a", "a+*"), ("x", "()x"), ("x", "a||x"), ("x", "^*x"), ("b", "[z-a]"), ("a", "[a"),
    ("]", "[]]"), ("\\", "[\\]"), ("x", "[[:foo:]]"), ("nt", "\\n\\t"), ("a b", "a\\sb"),
    ("ab", "\\<ab\\>"), ("aa", "(a)\\1"), ("a", "\\1"), ("x", "x\\"), ("a", "a{32767}"),
    ("a", "a{32768}"), ("é", "^.$"), ("é", "^..$"), (U3000, "[[:space:]]"),
    (" ", "[[:space:]]"), ("Ä", "[[:alpha:]]"), ("é", "[a-z]"), ("B", "[a-z]"),
    ("a-", "[a-]"), ("-", "[-a]"), ("b", "[a-c-e]"), (".", "[[.-.]]"), ("a", "[[=a=]]"),
    ("x$", "x$"), ("a^b", "a^b"), ("ab", "a$|b"), ("a", "(^a)"), ("x", "\\x"), ("w", "\\w"),
    ("_", "\\W"), ("x y", "x[^[:space:]]y"), ("a" + U3000 + "b", "a[^[:space:]]b"),
    ("café", "caf[[:alpha:]]"), ("x y", "x[[:space:]]y"), ("x y", "x[[:blank:]]y"),
    ("git push x", "(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)"),
    ("cat ./.env", "(^|/)\\.env$"), ("a/.env x", "(^|/)\\.env$"),
    ("dump_1.sql", "(dump|backup|export)s?[-_.].*\\.(sql|sql\\.gz|csv)$"),
]


def bash_says(subject, pattern, lc):
    """0 match, 1 no match, 2 invalid — bash's own answer."""
    return subprocess.run(["bash", "-c", '[[ $1 =~ $2 ]]', "x", subject, pattern],
                          env=dict(os.environ, LC_ALL=lc), stderr=subprocess.DEVNULL,
                          check=False).returncode


def b(u):
    return u.encode("utf-8").decode("latin-1")


class TestEreAgainstBash(unittest.TestCase):
    def test_c_locale_is_bytewise(self):
        for subject, pattern in CASES:
            with self.subTest(pattern=pattern, subject=subject):
                want = bash_says(subject, pattern, "C") == 0
                self.assertEqual(ere.search(b(pattern), b(subject), "b"), want)

    def test_utf8_locale_reads_characters(self):
        for subject, pattern in CASES:
            with self.subTest(pattern=pattern, subject=subject):
                want = bash_says(subject, pattern, "C.UTF-8") == 0
                self.assertEqual(ere.search(pattern, subject, "u"), want)

    def test_invalid_patterns_are_rejected_as_glibc_rejects_them(self):
        for subject, pattern in CASES:
            with self.subTest(pattern=pattern):
                self.assertEqual(ere.valid(b(pattern)), bash_says(subject, pattern, "C") != 2)

    def test_captures_are_bash_rematch(self):
        refspec = (".*git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([[:space:]]+--?[a-z-]+"
                   "(=[^[:space:]]+)?)*[[:space:]]+[^-][^[:space:];&|]*[[:space:]]+([^[:space:];&|]+).*")
        for line in ("git push a b; git push c d", "git push -u origin HEAD x",
                     "git push --force-with-lease=main origin x", "git push origin a b c",
                     "git -C /tmp push origin main"):
            with self.subTest(line=line):
                out = subprocess.run(["bash", "-c", '[[ $1 =~ $2 ]] && printf %s "${BASH_REMATCH[4]}"',
                                      "x", line, refspec], capture_output=True, text=True,
                                     check=False).stdout
                got = ere.match_groups(refspec, line, "b")
                self.assertEqual(got[4] if got else "", out)


class TestEreShapes(unittest.TestCase):
    def test_classes_per_mode(self):
        self.assertTrue(ere.search("[[:space:]]", U3000, "u"))
        self.assertFalse(ere.search("[[:space:]]", b(U3000), "b"))
        self.assertFalse(ere.search("[[:space:]]", "\x1c", "u"))   # Python's \s would take it

    def test_invalid_byte_in_utf8(self):
        bad = b"\xff".decode("utf-8", "surrogateescape")
        self.assertFalse(ere.search(".", bad, "u"))
        self.assertFalse(ere.search("[^a]", bad, "u"))
        self.assertTrue(ere.search(".", "\xff", "b"))

    def test_nested_quantifiers_stay_linear_and_agree_with_bash(self):
        import time  # pylint: disable=import-outside-toplevel
        for pattern, subject in (("(a+)+$", "a" * 30 + "b"), ("(a|aa)+$", "a" * 40 + "b"),
                                 ("(x+x+)+y", "x" * 40), ("(a?){30}a{30}", "a" * 30), ("(a+)+$", "aaa"),
                                 ("^(ab|a)*b$", "ababab"), ("(^|/)(x|y)*z$", "xyxz")):
            for mode, lc in (("b", "C"), ("u", "C.UTF-8")):
                with self.subTest(pattern=pattern, mode=mode):
                    t0 = time.perf_counter()
                    got = ere.search(pattern, subject, mode)
                    self.assertLess(time.perf_counter() - t0, 0.5 * TIMED_FACTOR)
                    self.assertEqual(got, bash_says(subject, pattern, lc) == 0)

    def test_ere_escape_keeps_the_shells_backslash_quirk(self):
        # '\\' in the shell's single-quoted case pattern is two characters:
        # a lone backslash was never escaped, and the port must not escape it.
        self.assertEqual(common.ere_escape("a\\b.c"), "a\\b\\.c")
        self.assertEqual(common.ere_escape("x(y)"), "x\\(y\\)")

    def test_a_long_line_stays_linear(self):
        import time  # pylint: disable=import-outside-toplevel
        line = "echo " + "a" * 200000 + " x"
        t0 = time.perf_counter()
        for pattern in (".*\\.(sql|sql\\.gz)([[:space:]]|$)", "[^/]*\\.json([[:space:]]|$)"):
            self.assertFalse(ere.search(pattern, line, "b"))
        self.assertLess(time.perf_counter() - t0, 0.5 * TIMED_FACTOR)


class TestEreMatch(unittest.TestCase):
    def setUp(self):
        loc = common.Locale.__new__(common.Locale)
        loc.utf8, loc.collate_c, loc._u = True, True, {}  # pylint: disable=protected-access
        self.m = common.Matcher(loc)

    def test_line_by_line(self):
        self.assertFalse(self.m.ere_match("git.*push", "git status\necho push"))
        self.assertTrue(self.m.ere_match("^push", "git status\npush"))
        self.assertFalse(self.m.ere_match("x", ""))
        self.assertTrue(self.m.ere_match("^$", "a\n\nb"))

    def test_past_4096_characters_it_is_bytewise(self):
        pad = "a" * 4100
        self.assertTrue(self.m.ere_match("x[[:space:]]y", "x y" + pad))
        self.assertFalse(self.m.ere_match("x[[:space:]]y", b("x" + U3000 + "y") + pad))
        self.assertTrue(self.m.ere_match("x[[:space:]]y", b("x" + U3000 + "y") + "a" * 10))

    def test_an_invalid_pattern_never_matches(self):
        self.assertFalse(self.m.ere_match("*a", "*a"))
        self.assertFalse(self.m.ere_match("*a", "*a" + "b" * 5000))


class TestDenyEncoding(unittest.TestCase):
    def test_same_bytes_as_jq(self):
        reason = b'a"\\\x01\x08\x0c\n\r\t\x1f\x7f\xc3\xa9\xff/z \xe2\x80\x94 \xe3\x80'
        want = subprocess.run(
            ["jq", "-Rsc", '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",'
                           'permissionDecisionReason:.}}'],
            input=reason, capture_output=True, check=False).stdout
        self.assertEqual(common.deny_json(reason.decode("latin-1")), want)


class TestPayload(unittest.TestCase):
    def payload(self, raw):
        return common.Payload(raw if isinstance(raw, bytes) else raw.encode(), "/pwd")

    def test_fast_path(self):
        p = self.payload('{"tool_name":"shell","cwd":"/x\\n","tool_input":{"command":"ls\\n\\n"}}')
        self.assertEqual((p.tool, p.tool_raw, p.cwd, p.bash_command()), ("Bash", "shell", "/x", "ls"))

    def test_a_non_string_command_prints_as_jq_r(self):
        p = self.payload('{"tool_name":"shell","cwd":"/x","tool_input":{"command":["bash","-lc","ls"]}}')
        self.assertEqual(p.bash_command(), '[\n  "bash",\n  "-lc",\n  "ls"\n]')

    def test_slow_path_reads_every_value(self):
        p = self.payload('{"tool_name":"Bash"}{"tool_name":"Read","cwd":7}')
        self.assertEqual((p.tool_raw, p.cwd), ("Bash\nRead", "7"))

    def test_fails_open(self):
        for raw in (b"", b"\n\n", b"not json", b"[1,2]", b'"x"', b"{} garbage", b"true"):
            with self.subTest(raw=raw):
                with self.assertRaises(common.Allow):
                    self.payload(raw)

    def test_no_cwd_is_pwd(self):
        self.assertEqual(self.payload('{"tool_name":"Bash"}').cwd, "/pwd")

    def test_target_paths(self):
        p = self.payload('{"tool_name":"MultiEdit","tool_input":{"file_path":"a","path":"b\\nc",'
                         '"edits":[{"file_path":"d"},{"file_path":3},"x"]}}')
        self.assertEqual(p.target_paths(), ["a", "b", "c", "d"])
        patch = ("*** Begin Patch\n*** Update File: src/a.php\n*** Move to: README.md\n"
                 "*** Delete File: .env\n*** End Patch")
        p = self.payload(common.jq_dump({"tool_name": "apply_patch", "tool_input": {"command": patch}}))
        self.assertEqual(p.target_paths(), ["src/a.php", "README.md", ".env"])


class TestFindPrint(unittest.TestCase):
    def test_prints_in_name_order_not_readdir_order(self):
        # find_print sorts each directory by name; without the sort the order is the
        # filesystem's readdir order (hash order on ext4), so this list would differ
        # from the sorted one on most trees and the creation order below would show.
        with tempfile.TemporaryDirectory() as root:
            for name in ("b", "a", "c", ".d"):
                os.mkdir(os.path.join(root, name))
            open(os.path.join(root, "b", "z"), "w").close()
            open(os.path.join(root, "b", "y"), "w").close()
            got = [os.fsdecode(p) for p in paths.find_print(root, 3, ())]
        rel = [os.path.relpath(p, root) for p in got]
        self.assertEqual(rel, [".", ".d", "a", "b", "b/y", "b/z", "c"])


if __name__ == "__main__":
    unittest.main()
