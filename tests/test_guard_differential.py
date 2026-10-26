#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The frozen shell guards beside the port: same payload, same tree, same bytes.

tests/fixtures/guard-port/ holds the three shell guards and their library as
they were when the port was made. Each payload goes through the frozen guard
and through `hooks/ai-guard.py --only <check>`, and the two records — exit
code and full output — must be byte-identical.

The golden corpus pins the C locale already (test_guard_characterization), so
here it runs again under C.UTF-8, where bash matched characters and glibc's
[[:space:]] took 15 more code points. The extra cases aim at what a backtracking
engine and a decoded string could get wrong, under both locales: the multibyte
blanks, `sh -c` spellings, BASH_REMATCH captures (refspec, ln source, the
string a sh -c runs), raw bytes that are not UTF-8 in the payload and in file
names, and lines past the 4096 and 16384 cut-offs.
"""
import concurrent.futures
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_guard_characterization as tc  # noqa: E402  pylint: disable=wrong-import-position

BLANKS = [" ", " ", " ", " ", " ", " ", " ", " ", " ",
          " ", " ", " ", " ", " ", "　", " "]
STATE = ".ai/state/current.json"


def extra_runs(tree):
    """(label, payload bytes, checks) aimed at the port's own risks."""
    r = tree.root
    bp = tc.bash_payload
    runs = []
    for b in BLANKS:
        runs.append(("IFS=U+%04X sh -c rm state" % ord(b),
                     bp("set -- '/bin/sh%s-c%srm -f %s'; IFS='%s'; $1" % (b, b, STATE, b), r), (tc.PATH,)))
        runs.append(("echo /bin/sh U+%04X blanks" % ord(b),
                     bp("echo /bin/sh%s-c%s'rm -f %s'" % (b, b, STATE), r), (tc.PATH,)))
    for head in ("bash --norc -c", "bash -o posix -c", "sh -c --", "sh -c 2>/dev/null", "'sh' -c", "\\sh -c",
                 "bash -c -o posix", "find . -name 'sh' -exec sh -c", "sudo -u 'sh' -c x bash -c",
                 "bash 2>'/tmp/a b' -c", "sh -c 2>\"$HOME\"/x", "bash -e -u -x -v -e -u -x -v -e -c",
                 "eval", "sh -c 'echo; bash -c \"rm -f %s\"' ;" % STATE):
        for target in (STATE, "a.txt"):
            runs.append(("%s rm %s" % (head, target), bp("%s 'rm -f %s'" % (head, target), r), (tc.PATH,)))
    pad = "a" * 5000
    big = "b" * 17000
    with open(tc.SH_C_20K, encoding="utf-8") as fh:
        sh20k = fh.read()
    for label, cmd in (
            ("refspec: last push wins", "git push a b; git push origin main"),
            ("refspec: options and HEAD", "git push -u origin HEAD"),
            ("refspec: src:dst", "git push origin feature/x:refs/heads/main"),
            ("refspec: two lines", "git push origin feature/x\ngit push origin main"),
            ("ln: two lines", "ln -s src/Service.php a\nln -sf .env b"),
            ("ln: flags", "ln -s -f -n ../.env config/x"),
            ("long: echo then cat", "echo %s; cat .env" % pad),
            ("long: glued state path", "echo %s/%s" % (pad, STATE)),
            ("long: rm operand", "rm -f %s/x %s" % (pad, STATE)),
            ("long: confirm-delete under the cap", "python3 update.py --apply %s --confirm-delete bob" % pad),
            ("long: confirm-delete over the cap", "python3 update.py --apply %s --confirm-delete bob" % big),
            ("long: --co and --ap without a head", "echo --color %s --apx" % big),
            ("unicode: path with accents", "cat déjà/.env"),
            ("unicode: blank before path", "cat　.env"),
            ("unicode: U+3000 between git words", "git　push　--force"),
            ("unicode: U+2007 between git words", "git push --force"),
            ("unicode: U+3000 before a reader's path", "cat　%s" % STATE),
            ("heredoc then rm", "cat > /tmp/x <<'EOF'\nrm -f %s\nEOF\nrm -f %s" % (STATE, STATE)),
            ("commit message then push", "git commit -m 'git push --force' && git push origin main"),
            ("interp writes state", "python3 -c \"open('%s','w').write('x')\"" % STATE),
            ("interp reads state", "python3 -c \"print(open('%s').read())\"" % STATE),
            ("20 KB sh -c fixture", sh20k),
            # A lone backslash in a token: the shell's ere_escape left it unescaped (review H1).
            ("backslash: reader of secrets", "cat secrets/\\db.txt"),
            ("backslash: tee into state", "tee .ai/state/\\current.json"),
            ("backslash: touch state", "touch .ai/state/\\current.json"),
            ("backslash: redirect into state", "echo x > .ai/state/\\current.json"),
            ("backslash: sed -i state", "sed -i s/a/b/ .ai/state/\\current.json"),
            ("backslash: two before a key", "cat \\\\.ssh/id_rsa"),
            ("backslash: ln source", "ln -s .ai/state/\\current.json x"),
    ):
        runs.append((label, bp(cmd, r), (tc.GIT, tc.PATH)))
    for label, raw in (
            ("raw: invalid byte in command", b'{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"cat \xff.env"}}'),
            ("raw: invalid byte in path", b'{"tool_name":"Read","cwd":"%s","tool_input":{"file_path":"\xfe/.env"}}'),
            ("raw: truncated sequence", b'{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"rm -f \xe3\x80 .ai/state/current.json"}}'),
            ("raw: two documents", b'{"tool_name":"Bash","cwd":"%s"} {"tool_name":"Bash","tool_input":{"command":"cat .env"}}'),
            ("raw: escaped control chars", b'{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"cat\\u000b.env\\u0085"}}'),
    ):
        runs.append((label, raw.replace(b"%s", r.encode()), (tc.GIT, tc.PATH, tc.SCOPE)))
    runs.append(("rm -rf of a home holding an undecodable file name",
                 bp("rm -rf ../home", r), (tc.PATH,)))
    runs.append(("Edit of a lone surrogate escape (jq reads U+FFFD)",
                 json.dumps({"tool_name": "Edit", "cwd": r,
                             "tool_input": {"file_path": r + "/.claude/agents/\udcff.md"}}).encode(),
                 (tc.PATH, tc.SCOPE)))
    return runs


def run_pair(tree, runs, lc, workers=8):
    """[(label, check, frozen record, port record)] for one batch of runs."""
    env = tree.env(lc)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = []
        for label, payload, checks in runs:
            for check in checks:
                jobs.append((label, check,
                             pool.submit(tc.run_guard, tc.frozen_argv(check), payload, env, tc.TESTS),
                             pool.submit(tc.run_guard, tc.port_argv(check), payload, env, tc.TESTS)))
        out = []
        for label, check, a, b in jobs:
            out.append((label, check, tc.record(tc.NAMES[check], label, *a.result(), tree.tmp),
                        tc.record(tc.NAMES[check], label, *b.result(), tree.tmp)))
    return out


class TestGuardDifferential(unittest.TestCase):
    def assert_same(self, pairs, lc):
        diffs = [(label, check, a, b) for label, check, a, b in pairs if a != b]
        if diffs:
            label, check, a, b = diffs[0]
            self.fail("%d of %d runs differ under %s; first: %s | %s\n  shell: %r\n  port:  %r"
                      % (len(diffs), len(pairs), lc, check, label[:80], a[:400], b[:400]))

    def test_golden_corpus_under_utf8(self):
        tree = tc.Tree()
        try:
            pairs = []
            for setup, runs in tc.Corpus(tree).phases():
                if setup:
                    setup()
                pairs += run_pair(tree, runs, "C.UTF-8")
        finally:
            tree.close()
        self.assertGreater(len(pairs), 1200)
        self.assert_same(pairs, "C.UTF-8")

    def test_scope_list_of_slash_globs(self):
        # The "Allowed for this step" list expands each glob against the guard's
        # working directory (tests/): a trailing slash or a doubled one is kept
        # as bash keeps it (review M1).
        tree = tc.Tree()
        try:
            runs = []
            for globs in (["fixtures/*/nonexistent/"], ["fixtures/*/lib/"], ["fixtures//g*"], ["*/nonexistent/"],
                          ["fixtures/guard-port/*.sh", "docs/"]):
                state = tc.changed(tree.state, {"step": {"allowed_files": globs, "forbidden_files": []}})
                tree.set_state(state)
                runs = [("allowed %s" % globs, tc.file_payload("Edit", "file_path", tree.root + "/README.md",
                                                               tree.root), (tc.SCOPE,))]
                for lc in ("C", "C.UTF-8"):
                    pairs = run_pair(tree, runs, lc)
                    with self.subTest(globs=globs, locale=lc):
                        self.assertIn(b"SCOPE_CHANGE_REQUIRED", pairs[0][3])
                        self.assert_same(pairs, lc)
        finally:
            tree.close()

    def test_a_nested_quantifier_in_a_user_pattern_stays_linear(self):
        # glibc matched (a+)+$ in linear time; a backtracking engine takes
        # minutes on 30 a's and a b (review M2).
        import time  # pylint: disable=import-outside-toplevel
        tree = tc.Tree()
        try:
            tc.dump(os.path.join(tree.root, ".ai/policies/path-guard.json"),
                    {"deny_patterns": ["(a+)+$", "(x+x+)+y", "(a|aa)+$"]})
            runs = [("nested: cat %s" % s, tc.bash_payload("cat " + s, tree.root), (tc.PATH,))
                    for s in ("a" * 30 + "b", "a" * 30, "x" * 40, "x" * 3 + "y", "a" * 4096 + "b")]
            for lc in ("C", "C.UTF-8"):
                t0 = time.perf_counter()
                tc.run_guard(tc.port_argv(tc.PATH), runs[0][1], tree.env(lc), tc.TESTS)
                self.assertLess(time.perf_counter() - t0, 2.0)
                self.assert_same(run_pair(tree, runs, lc), lc)
        finally:
            tree.close()

    def test_extra_cases_under_both_locales(self):
        for lc in ("C", "C.UTF-8"):
            tree = tc.Tree()
            try:
                hooks = os.path.join(tree.home, ".claude", "hooks")
                with open(os.path.join(hooks.encode(), b"ai-\xff"), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
                os.makedirs(os.path.join(tree.root.encode(), b"d\xc3\xa9j\xc3\xa0"))
                tc.dump(os.path.join(hooks, "ai-git-guard.json"), json.loads('{"protected_branches":["main"]}'))
                pairs = run_pair(tree, extra_runs(tree), lc)
            finally:
                tree.close()
            with self.subTest(locale=lc):
                self.assert_same(pairs, lc)


if __name__ == "__main__":
    unittest.main()
