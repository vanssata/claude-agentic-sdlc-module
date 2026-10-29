#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
memory_format: the canonical bytes, the rid and the seal digest, validation,
package names and parsing, periods, the token estimate, redaction, the path
matcher, the ranker's budget and the matcher (spec §D3, §D8, §I1, §I2).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position


def entry(**fields):
    base = {"v": 1, "task": "T-2026-10-28-1739-compact-memory", "inst": 1, "seq": 0, "kind": "note",
            "ts": "2026-10-28T17:39:00Z", "actor": "agent", "by": None, "runtime": "claude",
            "src": ["events.jsonl:4"], "note_kind": "decision", "text": "keep the key", "why": "callers", "error": None}
    base.update(fields)
    return mf.with_rid(base)


class TestCanonical(unittest.TestCase):
    def test_canonical_bytes_golden(self):
        self.assertEqual(mf.canonical({"b": 1, "a": "жълт", "c": [1, {"z": None, "y": True}]}),
                         '{"a":"жълт","b":1,"c":[1,{"y":true,"z":null}]}'.encode("utf-8"))

    def test_rid_is_the_hash_without_the_rid(self):
        e = entry()
        self.assertRegex(e["rid"], mf.RID_RE)
        self.assertEqual(e["rid"], mf.make_rid(e))
        self.assertEqual(e["rid"], "r1-" + __import__("hashlib").sha256(
            mf.canonical({k: v for k, v in e.items() if k != "rid"})).hexdigest()[:24])
        self.assertNotEqual(e["rid"], entry(text="keep the key!")["rid"])

    def test_digest_ignores_order(self):
        self.assertEqual(mf.seal_digest(["r1-b", "r1-a"]), mf.seal_digest(["r1-a", "r1-b"]))
        self.assertTrue(mf.seal_digest([]).startswith("sha256:"))


class TestValidate(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(mf.validate(entry()), [])

    def test_each_problem_is_named(self):
        e = entry()
        tampered = dict(e, text="changed")
        self.assertIn("rid is not the hash of the entry", mf.validate(tampered))
        self.assertTrue(any("missing" in p for p in mf.validate({k: v for k, v in e.items() if k != "src"})))
        self.assertTrue(any("actor" in p for p in mf.validate(entry(actor="robot"))))
        self.assertTrue(any("unknown kind" in p for p in mf.validate(entry(kind="memo"))))
        self.assertTrue(any("task is null" in p for p in mf.validate(entry(task=None))))
        self.assertEqual(mf.validate(entry(kind="risk", task=None, rkey="R-x-0000", title="t", where=[],
                                           label="RISK", what="w", likelihood=None, fix=None, status="open",
                                           status_why=None, found_by=None, text=None)), [])
        self.assertTrue(any("risk label" in p for p in mf.validate(entry(
            kind="risk", task=None, rkey="R-x-0000", title="t", where=[], label="GUESS", what="w", likelihood=None,
            fix=None, status="open", status_why=None, found_by=None, text=None))))
        self.assertTrue(any("ts" in p for p in mf.validate(entry(ts="yesterday"))))
        self.assertTrue(any("question: missing" in p for p in mf.validate(entry(kind="question"))))


class TestPackages(unittest.TestCase):
    def test_names(self):
        self.assertEqual(mf.package_name("2026-Q4", "vanssa", "k3q7"), "2026-Q4.vanssa.k3q7.jsonl")
        self.assertEqual(mf.parse_package_name("2026-Q4.vanssa.jsonl"),
                         {"period": "2026-Q4", "author": "vanssa", "batch": None})
        self.assertIsNone(mf.parse_package_name("2026-Q5.vanssa.jsonl"))
        self.assertIsNone(mf.parse_package_name("2026-Q4.Vanssa.k3q7.jsonl"))
        with self.assertRaises(ValueError):
            mf.package_name("2026-Q4", "vanssa", "ilou")       # not base32

    def test_round_trip_and_errors(self):
        header = mf.package_header("2026-Q4", "dev", "abcd", "2026-10-28T00:00:00Z")
        data = mf.render_package(header, [entry(seq=1), entry()])
        h, entries, errors = mf.parse_package(data, "2026-Q4.dev.abcd.jsonl")
        self.assertEqual((h, errors), (header, []))
        self.assertEqual(mf.render_package(h, [mf.strip_private(e) for e in entries]), data)
        lines = data.split(b"\n")
        self.assertEqual(mf.parse_package(b"\xef\xbb\xbf" + data)[2][0], (1, "starts with a UTF-8 BOM"))
        crlf = b"\r\n".join(lines[:-1]) + b"\r\n"
        self.assertIn((2, "CRLF line ending"), mf.parse_package(crlf)[2])
        spaced = lines[0] + b"\n" + lines[1].replace(b'","', b'", "', 1) + b"\n"
        self.assertIn((2, "not in canonical form (sorted keys, no spaces)"), mf.parse_package(spaced)[2])
        self.assertIn((1, "file name does not match its header"),
                      mf.parse_package(data, "2026-Q4.other.abcd.jsonl")[2])
        self.assertEqual(mf.parse_package(data[:-1])[2][-1][1], "no LF after the last line")


class TestSmall(unittest.TestCase):
    def test_periods(self):
        self.assertEqual(mf.period_of("2026-10-28T17:39:00Z", "month"), "2026-10")
        self.assertEqual(mf.period_of("2026-10-28T17:39:00Z", "quarter"), "2026-Q4")
        self.assertEqual(mf.period_of("2026-03-31T23:59:59Z", "quarter"), "2026-Q1")
        self.assertEqual(mf.period_of("2026-10-28T17:39:00Z", "year"), "2026")

    def test_tokens(self):
        self.assertEqual(mf.est_tokens("x" * 35), 10)
        self.assertEqual(mf.est_tokens("ж" * 7), 4)

    def test_redaction(self):
        text = ("token=ghp_ABCDEFGHIJKLMNOPQRSTUVWX12 AKIAABCDEFGHIJKLMNOP password: hunter2secret "
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz sk-ant-api03-abcdefghijklmnop "
                "https://user:pa55w0rd@example.com/x ok")
        out = mf.redact(text)
        for secret in ("ghp_ABCDEF", "AKIAABCD", "hunter2secret", "abcdefghijklmnopqrstuvwxyz", "sk-ant-api03",
                       "pa55w0rd"):
            self.assertNotIn(secret, out)
        self.assertTrue(out.endswith(" ok"))
        self.assertEqual(mf.redact("FAIL: test_x (a.b) ... 3 != 4"), "FAIL: test_x (a.b) ... 3 != 4")

    def test_paths(self):
        self.assertTrue(mf.path_matches("skills/ai-task/state.py:722", "skills/ai-task/state.py"))
        self.assertTrue(mf.path_matches("skills/**", "skills/ai-task/state.py"))
        self.assertTrue(mf.path_matches("skills/ai-task/state.py", "skills/*/state.py"))
        self.assertTrue(mf.path_matches("skills/ai-task", "skills/ai-task/state.py"))
        self.assertTrue(mf.path_matches("skills/ai-task/state.py", "skills/ai-task/"))
        self.assertFalse(mf.path_matches("skills/ai-task/state.py", "skills/ai-task/sensors.py"))
        self.assertFalse(mf.path_matches("skills/ai", "skills/ai-task/state.py"))

    def test_tokenize_and_match(self):
        self.assertEqual(mf.tokenize("Ключ_на кеша, cache-key!"), ["ключ", "на", "кеша", "cache", "key"])
        e = entry(text="Ключът на кеша зависи от locale")
        self.assertTrue(mf.match_search(e, mf.tokenize("ключ лок"), {}) is False)
        self.assertTrue(mf.match_search(e, mf.tokenize("ключ loc"), {}))
        self.assertTrue(mf.match_search(e, [], {"kind": "note", "since": "2026-10", "until": "2026-10-28"}))
        self.assertFalse(mf.match_search(e, [], {"until": "2026-10-27"}))
        self.assertFalse(mf.match_search(e, [], {"by": "vanssa"}))


class TestRank(unittest.TestCase):
    def items(self, n):
        seals = {}
        entries = []
        for i in range(n):
            task = "T-2026-10-%02d-1200-task-%d" % (i % 28 + 1, i)
            seal = entry(task=task, kind="task", seq=1, result="closed", goal="goal %d %s" % (i, "word " * 20),
                         workflow="feature", mode="light", w=1, axes=None, started_at="2026-10-01T00:00:00Z",
                         closed_at="2026-10-%02dT12:00:00Z" % (i % 28 + 1), files=["src/a.py"], steps=[],
                         stages=[], changes=[], code={}, facts={}, verify_runs=[], counts={}, people={},
                         runtimes=["claude"], entries=1, digest="sha256:x", source="close", schema=7, version=1)
            seals[mf.key_of(seal)] = seal
            entries += [entry(task=task), seal]
        return mf.candidate_items(entries, seals)[0]

    def test_budget_bounds_the_bytes(self):
        items = self.items(200)
        for budget in (300, 1500, 5000):
            text, result = mf.rank_recall(items, ["src/a.py"], budget, 40)
            self.assertLessEqual(len(text.encode("utf-8")), budget * 3.5, budget)
            self.assertEqual(result["more"], len(items) - len(result["items"]))
            self.assertIn("--offset %d" % len(result["items"]), text)

    def test_a_budget_below_one_line_gives_the_header_and_more(self):
        text, result = mf.rank_recall(self.items(5), ["src/a.py"], 1, 40)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["more"], 10)
        self.assertTrue(text.startswith("# Recall — 1 files · 0 of 10 items"))
        self.assertIn("… 10 more: state.py recall --files \"src/a.py\" --offset 0", text)

    def test_nothing_recorded(self):
        text, _ = mf.rank_recall(self.items(3), ["docs/none.md"], 1500, 40, excluded_task="T-x")
        self.assertEqual(text, "# Recall — 1 files · nothing recorded for these files · current task T-x excluded\n")

    def test_tiers_order(self):
        text, _ = mf.rank_recall(self.items(3), ["src/a.py"], 1500, 40)
        kinds = [line.split("]")[0] for line in text.splitlines()[1:]]
        self.assertEqual(kinds, ["- [decision agent"] * 3 + ["- [task"] * 3)


if __name__ == "__main__":
    unittest.main()
