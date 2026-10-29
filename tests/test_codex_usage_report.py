#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The Codex half of usage-report.py. Codex does not repeat a response across
lines the way Claude Code does, but it does write three token counters into
every record — one for the response, two running totals — and summing the
wrong one silently multiplies the bill. These fixtures pin which one is read,
where the model name comes from, and how a spawned thread is attributed.

The script runs under `python3 -I` with a pinned HOME, as the shell suite drove it.
"""
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "usage-report", "usage-report.py")
PRICES = os.path.join(ROOT, "skills", "usage-report", "prices.json")

TWIN_OF = "test-codex-usage-report.sh"

# R13 reads the shell `pass` text as written, its escapes included.
STRING_FORM_CASE = r'{\"subagent\":\"review\"} is recognised'
CACHE_WRITE_CASE = r"1M cache-write tokens on terra cost \$2.50"

FAMILIES = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ur", sys.argv[1])
ur = importlib.util.module_from_spec(spec); spec.loader.exec_module(ur)
p = ur.load_prices()["codex"]
fams = json.load(open(sys.argv[2]))["codex"]["families"]
bad = [f"{k}->{p.family(k)}" for k in fams if p.family(k) != k]
bad += [f"{k}-x->{p.family(k + '-x')}" for k in fams if p.family(k + "-x") != k]
print(" ".join(bad) or "ok")
"""


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def meta(thread, cwd, session, source):
    return dumps({"type": "session_meta", "timestamp": "2026-09-01T10:00:00.000Z",
                  "payload": {"id": thread, "session_id": session, "cwd": cwd, "source": source,
                              "originator": "test"}}) + "\n"


def turn(turn_id, model, effort, cwd):
    return dumps({"type": "turn_context", "timestamp": "2026-09-01T10:00:01.000Z",
                  "payload": {"turn_id": turn_id, "model": model, "effort": effort, "cwd": cwd}}) + "\n"


def usage_record(response, turn_id, i, ci, cw, o, ri=99000000, ro=99000000):
    """The running totals default to something absurd on purpose: if the parser
    ever reads them instead of `usage`, the expected cost is off by miles."""
    running = {"input_tokens": ri, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "output_tokens": ro,
               "total_tokens": ri + ro}
    payload = {"response_id": response, "turn_id": turn_id, "thread_id": "t", "session_id": "t",
               "usage": {"input_tokens": i, "cached_input_tokens": ci, "cache_write_input_tokens": cw,
                         "output_tokens": o, "total_tokens": i + o},
               "turn_token_usage": running, "thread_token_usage": dict(running)}
    if response is None:
        del payload["response_id"]
    return {"type": "token_usage_record", "timestamp": "2026-09-01T10:00:02.000Z", "payload": payload}


def usage(*args, **kw):
    return dumps(usage_record(*args, **kw)) + "\n"


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(text)


class TestCodexUsageReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.home = self.path("home")
        os.makedirs(self.home)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_DIR", "CODEX_DIR", "USAGE_REPORT_CACHE")}
        self.env.update(HOME=self.home, USAGE_REPORT_CACHE=self.path("suite-cache.json"))  # the corpus runs cached
        self.day = self.path("sessions", "2026", "09", "01")
        os.makedirs(self.day)

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, *parts):
        return os.path.join(self.tmp.name, *parts)

    def rollout(self, name):
        return os.path.join(self.day, "rollout-2026-09-01T%s.jsonl" % name)

    def script(self, *args, **env):
        """rc and stdout+stderr, as `$(python3 "$SCRIPT" … 2>&1)` without the trailing newlines."""
        done = subprocess.run(["python3", "-I", SCRIPT] + list(args), env=dict(self.env, **env),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return done.returncode, done.stdout.rstrip("\n")

    def run_codex(self, *args, root=None, **env):
        return self.script("--provider", "codex", "--root", root or self.path("sessions"), "--all", *args, **env)[1]

    def test_the_sessions_corpus(self):
        # terra: $2/MTok in, $12/MTok out, cache read 0.1x, cache write 1.25x; sol: $4 in, $20 out.
        # == the per-response counter is billed, not the running total
        write(self.rollout("10-00-00-t"), meta("t", "/work", "t", "cli") + turn("turn1", "gpt-5.6-terra", "medium", "/work")
              + usage("r1", "turn1", 1000000, 0, 0, 100000, 9000000, 9000000)
              + usage("r2", "turn1", 1000000, 0, 0, 100000, 99000000, 99000000))
        # 2 x (1M in @ $2 + 100k out @ $12) = $4.00 + $2.40 = $6.40
        out = self.run_codex()
        with self.subTest("each response is billed once, from usage and not from the running totals"):
            self.assertIn("TOTAL  $6.40", out, "expected TOTAL $6.40")
        with self.subTest("the model and effort come from the turn context"):
            self.assertIn("gpt-5.6-terra (medium)", out, "model not resolved")

        # == cached input is not billed twice
        write(self.rollout("11-00-00-t2"), meta("t2", "/work", "t2", "cli")
              + turn("turn1", "gpt-5.6-terra", "medium", "/work") + usage("r1", "turn1", 1000000, 900000, 0, 0))
        os.remove(self.rollout("10-00-00-t"))
        # input_tokens includes the cached part: 100k fresh @ $2 + 900k cached @ $0.20 = $0.38
        out = self.run_codex()
        with self.subTest("cached tokens are charged at the cache rate, not the full input rate"):
            self.assertIn("TOTAL  $0.38", out, "expected TOTAL $0.38")
        with self.subTest("and the IN column shows fresh input only"):
            self.assertRegex(out, r"(?m)^codex +gpt-5.6-terra \(medium\) +100,000 ", "IN column wrong")

        # == a repeated response_id is counted once
        for name, thread in (("12-00-00-t3", "t3"), ("13-00-00-t4", "t4")):
            write(self.rollout(name), meta(thread, "/work", thread, "cli")
                  + turn("turn1", "gpt-5.6-terra", "medium", "/work") + usage("same", "turn1", 1000000, 0, 0, 0))
        os.remove(self.rollout("11-00-00-t2"))
        with self.subTest("a resumed thread replaying a response does not double-bill it"):
            self.assertIn("TOTAL  $2.00", self.run_codex(), "expected TOTAL $2.00")

        # == a spawned thread is attributed to subagents, by name
        os.remove(self.rollout("13-00-00-t4"))
        write(self.rollout("14-00-00-sub"), meta("sub", "/work", "parent", {"subagent": {"other": "ai-reviewer"}})
              + turn("turnS", "gpt-5.6-sol", "high", "/work") + usage("rs", "turnS", 1000000, 0, 0, 0))
        # terra 1M in = $2.00, sol 1M in = $4.00 -> total $6.00, subagents $4.00 (67%)
        out = self.run_codex()
        with self.subTest("both threads are counted"):
            self.assertIn("TOTAL  $6.00", out, "expected TOTAL $6.00")
        with self.subTest("the spawned thread is reported as a subagent"):
            self.assertIn("SUBAGENTS  $4.00 (67% of total)", out, "subagent share wrong")
        with self.subTest("and named, so the report says which agent spent it"):
            self.assertIn("ai-reviewer", out, "agent name missing")

        # == a string-form subagent source is recognised too
        write(self.rollout("15-00-00-sub2"), meta("sub2", "/work", "parent2", {"subagent": "review"})
              + turn("turnR", "gpt-5.6-sol", "high", "/work") + usage("rr", "turnR", 1000000, 0, 0, 0))
        out = self.run_codex()
        with self.subTest(STRING_FORM_CASE):
            # "review" alone is already in `ai-reviewer`: the row only the string form names.
            self.assertRegex(out, r"(?m)codex / review$", "string form missed")

        # == the cost column is labelled an estimate while the rates are unverified
        with open(PRICES, encoding="utf-8") as fh:
            verified = json.load(fh)["codex"].get("rates_verified")
        if verified is False:
            with self.subTest("an unverified price table is declared, not presented as fact"):
                self.assertIn("ESTIMATE for codex", out, "estimate note missing")
        else:
            with self.subTest("verified rates are reported without the estimate note"):
                self.assertNotIn("ESTIMATE for codex", out,
                                 "rates are verified but the report still calls them an estimate")

        # == --today filters by the record timestamp
        with self.subTest("a day with no records reports nothing rather than everything"):
            self.assertIn("no usage records matched", self.run_codex("--today"), "--today did not filter")

        # == the provider is sniffed from the directory when it is not given
        with self.subTest("rollout-*.jsonl is recognised as Codex"):
            self.assertRegex(self.script("--root", self.path("sessions"), "--all")[1], r"(?m)^codex ", "sniff failed")

        # == malformed records are skipped, not fatal
        write(self.rollout("16-00-00-t9"), 'not json at all\n{"type":"token_usage_record","payload":{}}\n'
              '{"type":"turn_context"}\n{}\n' + meta("t9", "/work", "t9", "cli")
              + turn("turn9", "gpt-5.6-terra", "medium", "/work") + usage("r9", "turn9", 1000000, 0, 0, 0))
        rc, out = self.script("--provider", "codex", "--root", self.path("sessions"), "--all")
        with self.subTest("a corrupt transcript does not crash the report"):
            self.assertEqual(rc, 0, out)
        with self.subTest("and the good records are still counted"):
            self.assertIn("gpt-5.6-terra", out, "good records lost")

        # == a usage record with no turn context falls back to the last model seen
        write(self.rollout("17-00-00-t10"), meta("t10", "/work", "t10", "cli")
              + turn("turnA", "gpt-5.6-sol", "high", "/work") + usage("rA", "unknown-turn", 1000000, 0, 0, 0))
        with self.subTest("an unannounced turn is attributed to the thread's last model, not to 'unknown'"):
            self.assertIn("gpt-5.6-sol (high)", self.run_codex(), "fallback model missing")

        # == the incremental parse cache, on a rollout file
        # A rollout file is appended to for as long as the thread lives, so the cache
        # earns its keep here — and must report exactly what an uncached run reports.
        cache, r = self.path("cache.json"), self.rollout("18-00-00-t11")
        write(r, meta("t11", "/work", "t11", "cli") + turn("turnC", "gpt-5.6-sol", "high", "/work")
              + usage("rc1", "turnC", 1000000, 0, 0, 0))
        cold = self.run_codex(USAGE_REPORT_CACHE=cache)
        with self.subTest("a cold run reports what an uncached run reports"):
            self.assertEqual(cold, self.run_codex(USAGE_REPORT_CACHE=""), "cold run differs")
        os.chmod(r, 0)
        try:
            with self.subTest("an unchanged rollout file is not read again at all"):
                self.assertEqual(self.run_codex(USAGE_REPORT_CACHE=cache), cold, "an unchanged rollout was re-read")
        finally:
            os.chmod(r, 0o644)
        write(r, usage("rc2", "turnC", 2000000, 0, 0, 0), "a")
        with self.subTest("an appended rollout file is folded from the offset, not from zero"):
            self.assertEqual(self.run_codex(USAGE_REPORT_CACHE=cache), self.run_codex(USAGE_REPORT_CACHE=""), "append")

    def test_an_empty_directory_is_not_an_error(self):
        """an empty root says so"""
        empty = self.path("empty")
        os.makedirs(empty)
        self.assertIn("no usage records matched", self.run_codex(root=empty), "empty root mishandled")

    def test_provider_both_reads_neither_runtimes_records_into_the_other(self):
        cl = self.path("claude-proj")
        write(os.path.join(cl, "s.jsonl"), '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"m1","model":'
              '"claude-sonnet-5","usage":{"input_tokens":1000000,"output_tokens":0,"cache_creation_input_tokens":0,'
              '"cache_read_input_tokens":0}}}\n')
        out = self.script("--root", cl, "--all")[1]
        with self.subTest("a Claude directory is sniffed as Claude"):
            self.assertRegex(out, r"(?m)^claude ", "claude sniff failed")
        with self.subTest("and produces no codex rows"):
            self.assertNotRegex(out, r"(?m)^codex ", "Claude records must not be attributed to codex")

    def test_an_unterminated_last_record_is_billed_once(self):
        # A rollout file whose last record has no newline after it, and no response_id:
        # the record is keyed by its position, so a state that folded the tail into
        # itself would append a new key on every rescan and the bill would grow.
        nl, nc = self.path("nonl"), self.path("nonl-cache.json")
        write(os.path.join(nl, "rollout-nonl.jsonl"), meta("t12", "/work", "t12", "cli")
              + turn("turnD", "gpt-5.6-sol", "high", "/work") + usage("rd1", "turnD", 1000000, 0, 0, 0)
              + dumps(usage_record(None, "turnD", 1000000, 0, 0, 0)))
        one, two, three = (self.run_codex(root=nl, USAGE_REPORT_CACHE=nc) for _ in range(3))
        ref = self.run_codex(root=nl, USAGE_REPORT_CACHE="")
        with self.subTest("an unterminated last record is reported, cached or not"):
            self.assertEqual(one, ref, "unterminated record")
        with self.subTest("and it is not folded into the stored state: three rescans, one bill"):
            self.assertEqual((two, three), (one, one), "unterminated record grew on a rescan")

    def test_malformed_rollout_lines_are_skipped(self):
        """wrong-shaped records are skipped; an exponent count and a numeric timestamp still fold"""
        md = self.path("malformed")
        write(os.path.join(md, "rollout-m.jsonl"), '[]\n"a string"\nnull\n'
              '{"type":"session_meta","payload":"not an object"}\n'
              '{"type":"turn_context","payload":["x"]}\n'
              '{"type":"token_usage_record","payload":{"usage":"not an object"}}\n'
              '{"type":"token_usage_record","timestamp":12345,"payload":{"response_id":"rx","usage":'
              '{"output_tokens":"1e5"}}}\n'
              + meta("m", "/work", "m", "cli") + turn("turnM", "gpt-5.6-terra", "medium", "/work")
              + usage("rM", "turnM", 1000000, 0, 0, 0))
        rc, out = self.script("--provider", "codex", "--root", md, "--all", USAGE_REPORT_CACHE="")
        # rM: 1M in @ $2 = $2.00; rx: 1e5 out @ $12 = $1.20, its non-string timestamp read as none.
        self.assertEqual(rc, 0, "malformed rollout\n" + out)
        self.assertIn("TOTAL  $3.20", out, "malformed rollout")

    def test_cache_writes_are_billed_at_the_published_rate(self):
        """cache writes are billed at the published 1.25x of input"""
        cw = self.path("cachewrite")
        write(os.path.join(cw, "rollout-w.jsonl"), meta("w", "/work", "w", "cli")
              + turn("turnW", "gpt-5.6-terra", "medium", "/work") + usage("rW", "turnW", 0, 0, 1000000, 0))
        # 1M cache write on terra: 1M x $2 x 1.25 = $2.50
        with self.subTest(CACHE_WRITE_CASE):
            self.assertIn("TOTAL  $2.50", self.run_codex(root=cw, USAGE_REPORT_CACHE=""), "cache write multiplier")

    def test_every_codex_family_resolves_to_its_own_row(self):
        """each family key, and a suffixed name, prices as itself"""
        done = subprocess.run(["python3", "-I", "-c", FAMILIES, SCRIPT, PRICES], env=self.env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, check=False)
        self.assertEqual(done.stdout.strip(), "ok", "family resolution")


if __name__ == "__main__":
    unittest.main()
