#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
usage-report.py --task reads a schema-6 and a schema-7 journal (R18): the old
one prints its tier, the new one its mode beside the compat tier.

TestUsageReport translates test-usage-report.sh: one API response is written as
several transcript lines that repeat the same message id and usage — it must be
counted once, not per line. The script runs under `python3 -I` with a pinned HOME.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "usage-report", "usage-report.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "usage-report")
TASK = "T-FIXTURE"

TWIN_OF = "test-usage-report.sh"


class TestTaskJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.project = os.path.join(self.tmp.name, "project")
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(os.path.join(self.project, ".ai", "reports", TASK))
        os.makedirs(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, fixture):
        journal = os.path.join(self.project, ".ai", "reports", TASK, "events.jsonl")
        shutil.copyfile(os.path.join(FIXTURES, fixture), journal)
        env = dict(os.environ, CLAUDE_CONFIG_DIR=os.path.join(self.home, ".claude"),
                   CODEX_HOME=os.path.join(self.home, ".codex"),
                   USAGE_REPORT_CACHE=os.path.join(self.tmp.name, "cache.json"))
        done = subprocess.run([sys.executable, "-I", SCRIPT, "--task", TASK, "--project", self.project],
                              capture_output=True, text=True, env=env, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout.split("\n")

    def test_schema_6_prints_the_tier(self):
        head = self.report("schema-6.jsonl")[0]
        self.assertTrue(head.startswith("task %s tier T4 window 2026-09-01T10:00:00+00:00..2026-09-01T11:00:00"
                                        % TASK), head)
        self.assertNotIn("mode", head)

    def test_schema_7_prints_the_mode_and_the_compat_tier(self):
        out = self.report("schema-7.jsonl")
        self.assertTrue(out[0].startswith("task %s mode full_irreversible (tier T6) window" % TASK), out[0])
        # Both runtimes that wrote the journal are reported, each against the T-label's budget.
        self.assertEqual([line.split()[0] for line in out if line.startswith(("claude ", "codex "))],
                         ["claude", "codex"])


# R13 reads the shell `pass` text as written, its escaped quotes included.
V2_CACHE_CASE = r'a version-2 cache that read \"1e5\" as 0 is dropped, not trusted'
EXPONENT_CASE = r'an exponent-form count (\"1e5\") is read as 100,000'

LINE = ('{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"%s","model":"%s","usage":{"input_tokens":0,'
        '"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":%s}}}\n')
TLINE = ('{"timestamp":"%s","message":{"id":"%s","model":"claude-opus-5","usage":{"input_tokens":%s,'
         '"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":%s}}}\n')
CLINE = ('{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"%s","model":"claude-sonnet-5","usage":{"input_tokens":0,'
         '"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n')
TLINE_AT = ('{"timestamp":"%s","message":{"id":"%s","model":"claude-sonnet-5","usage":{"input_tokens":0,'
            '"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n')
EVENT = '{"ts":"%s","task":"%s","event":"%s","actor":"agent","runtime":"claude","data":%s}\n'
WINDOW_TOKENS = r"(?m)^claude   tokens in 400,000 cache 1,900,000 out 100,000 total 2,400,000"
SHELL_TASK = "T-2026-09-01-001"


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(text)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class TestUsageReport(unittest.TestCase):
    """The shell suite's cases, one method per `==` section."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.home = self.path("pinned-home")
        os.makedirs(self.home)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_DIR", "CODEX_DIR", "USAGE_REPORT_CACHE")}
        self.env.update(HOME=self.home, USAGE_REPORT_CACHE=self.path("suite-cache.json"))  # the corpus runs cached

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, *parts):
        return os.path.join(self.tmp.name, *parts)

    def run_script(self, *args, cwd=None, **env):
        """rc and stdout+stderr, as `$(python3 "$SCRIPT" … 2>&1)` without the trailing newlines."""
        done = subprocess.run(["python3", "-I", SCRIPT] + list(args), cwd=cwd, env=dict(self.env, **env),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return done.returncode, done.stdout.rstrip("\n")

    def out(self, *args, **env):
        return self.run_script(*args, **env)[1]

    def resolve_profile(self, plan, fable, dest):
        done = subprocess.run(["python3", "-I", os.path.join(ROOT, "scripts", "resolve-profile.py"), plan,
                               "--fable", fable, "--print", "agentic"], env=self.env, stdout=subprocess.PIPE,
                              text=True, check=True)
        write(dest, done.stdout)

    def task_fixture(self):
        """$H, $P and the transcript directory of the --task cases."""
        h, p, t = self.path("home"), self.path("project"), SHELL_TASK
        os.makedirs(os.path.join(p, ".ai", "reports", t))
        self.resolve_profile("max", "yes", os.path.join(h, ".claude", "riskrails", "profile.json"))
        write(os.path.join(p, ".ai", "reports", t, "events.jsonl"),
              EVENT % ("2026-09-01T10:00:00.000Z", t, "task_started", "{}")
              + EVENT % ("2026-09-01T10:05:00.000Z", t, "tier_set", '{"tier":"T2"}')
              + EVENT % ("2026-09-01T10:10:00.000Z", t, "tier_raised", '{"from":"T2","to":"T3"}')
              + EVENT % ("2026-09-01T11:00:00.000Z", t, "task_closed", "{}"))
        tr = os.path.join(h, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", p))
        write(os.path.join(tr, "sess.jsonl"),
              TLINE % ("2026-09-01T09:59:00Z", "before", 5000000, 0, 0)
              + TLINE % ("2026-09-01T10:30:00Z", "in1", 400000, 100000, 1500000)
              + TLINE % ("2026-09-01T10:45:00.5Z", "in2", 0, 0, 400000)
              + TLINE % ("2026-09-01T11:30:00Z", "after", 9000000, 0, 0))
        dirs = {"CLAUDE_CONFIG_DIR": os.path.join(h, ".claude"), "CODEX_HOME": os.path.join(h, ".codex")}
        return h, p, tr, dirs

    def test_a_response_split_over_three_lines_is_counted_once(self):
        proj = self.path("proj")
        # thinking block, text block, tool_use block with the final output count
        write(os.path.join(proj, "sess1.jsonl"),
              LINE % ("msg_a", "claude-sonnet-5", 10, 1000000) + LINE % ("msg_a", "claude-sonnet-5", 10, 1000000)
              + LINE % ("msg_a", "claude-sonnet-5", 100000, 1000000))
        # sonnet: 1M cache read * $2 * 0.1 = $0.20; 100k output * $10 = $1.00
        with self.subTest("duplicated lines are billed once, at the final output count"):
            out = self.out("--root", proj)
            self.assertIn("TOTAL  $1.20", out, "expected TOTAL $1.20")
        # == subagent transcripts are reported as their own share
        write(os.path.join(proj, "sess1", "subagents", "agent-x1.jsonl"),
              LINE % ("msg_b", "claude-opus-5", 0, 1000000))  # $0.50
        out = self.out("--root", proj)
        with self.subTest("the subagent response is added once"):
            self.assertIn("TOTAL  $1.70", out, "expected TOTAL $1.70")
        with self.subTest("the subagent share is reported"):
            self.assertIn("SUBAGENTS  $0.50 (29% of total)", out, "expected SUBAGENTS $0.50")

    def test_task_window_tokens_per_runtime_and_the_plan_budget(self):
        """--task: one task's window, tokens per runtime and the plan budget (R14)"""
        _, p, _, dirs = self.task_fixture()
        journal = os.path.join(p, ".ai", "reports", SHELL_TASK, "events.jsonl")
        before = sha256(journal)
        out = self.out("--task", SHELL_TASK, "--project", p, **dirs)
        with self.subTest("the window runs from task_started to task_closed, the tier is the final one"):
            self.assertRegex(out, r"(?m)^task %s tier T3 window 2026-09-01T10:00:00\+00:00\.\.2026-09-01T11:00:00"
                                  r"\+00:00" % SHELL_TASK, "task header")
        with self.subTest("only the calls inside the window count, per provider"):
            self.assertRegex(out, WINDOW_TOKENS, "window tokens")
        with self.subTest("the runtime's plan budget for the final tier, and the share used"):
            self.assertIn("budget max T3 6.0M · used 2.4M (40%)", out, "budget line")
        with self.subTest("the journal is only read"):
            self.assertEqual(sha256(journal), before, "the journal changed")
        with self.subTest("an unknown task exits 1 and says why"):
            rc, out = self.run_script("--task", "T-none", "--project", p, **dirs)
            self.assertEqual(rc, 1, out)
            self.assertIn("no journal for T-none", out)

    def test_an_unclosed_task_ends_at_its_last_event_not_at_now(self):
        """#41: no task_closed -> the window ends at the last event and the header says so"""
        _, p, tr, dirs = self.task_fixture()
        t = SHELL_TASK
        write(os.path.join(p, ".ai", "reports", t, "events.jsonl"),
              EVENT % ("2026-09-01T10:00:00.000Z", t, "task_started", "{}")
              + EVENT % ("2026-09-01T10:05:00.000Z", t, "tier_set", '{"tier":"T3"}')
              + EVENT % ("2026-09-01T11:00:00.000Z", t, "gate_checked", "{}"))
        out = self.out("--task", t, "--project", p, **dirs)
        self.assertRegex(out, r"(?m)^task %s tier T3 window 2026-09-01T10:00:00\+00:00\.\.2026-09-01T11:00:00"
                              r"\+00:00 \(unclosed: window ends at the last event\)" % t, out)
        self.assertRegex(out, WINDOW_TOKENS, "the 'after' call (11:30) must not be counted")

    def test_identifiers_that_are_not_strings(self):
        """identifiers that are not strings do not take the report down with them"""
        # A transcript that writes message.id, requestId, response_id or a turn id as a
        # number: main reports the file, so the cache's stored rows must too.
        ns = self.path("numid")
        write(os.path.join(ns, "a.jsonl"), LINE.replace('"id":"%s"', '"id":%s') % (12345, "claude-sonnet-5", 100000, 0))
        cache = self.path("numid-cache.json")
        nout = self.out("--root", ns, USAGE_REPORT_CACHE=cache)
        with self.subTest("a numeric message id is reported, not a traceback"):
            self.assertIn("TOTAL  $1.00", nout, "numeric message id")
        with self.subTest("and the entry it wrote is served back, not rejected every run"):
            self.assertEqual(self.out("--root", ns, USAGE_REPORT_CACHE=cache), nout, "numeric id, warm run")

    def test_a_relative_cache_path_resolves_to_one_directory(self):
        """a relative cache path resolves to one directory, not two (--task)"""
        # task_report chdirs into the project for the parsers and back again before the
        # flush. If the path is resolved per call, the cache is read in one directory
        # and written in another and never warms: the second run re-reads the
        # transcript, which is what the unreadable file below turns into a failure.
        _, p, tr, dirs = self.task_fixture()
        z = self.path("relcwd")
        os.makedirs(z)
        self.run_script("--task", SHELL_TASK, "--project", p, cwd=z, USAGE_REPORT_CACHE="relcache.json", **dirs)
        sess = os.path.join(tr, "sess.jsonl")
        os.chmod(sess, 0)
        try:
            warm = self.out("--task", SHELL_TASK, "--project", p, cwd=z, USAGE_REPORT_CACHE="relcache.json", **dirs)
        finally:
            os.chmod(sess, 0o644)
        with self.subTest("the second --task run reads the cache it wrote, transcript untouched"):
            self.assertRegex(warm, WINDOW_TOKENS, "a relative cache path did not warm under --task")
        with self.subTest("and nothing is dropped into the project directory"):
            self.assertFalse(os.path.exists(os.path.join(p, "relcache.json")),
                             "a cache file was written inside the project")

    def test_budgets_prints_each_installed_plans_tables(self):
        h, _, _, dirs = self.task_fixture()
        self.resolve_profile("codex-plus", "no", os.path.join(h, ".codex", "riskrails", "profile.json"))
        out = self.out("--budgets", **dirs)
        with self.subTest("both runtimes' plans are listed"):
            self.assertRegex(out, r"(?m)^claude: Max \(max\)", "budgets header")
            self.assertRegex(out, r"(?m)^codex: Plus \(plus\)", "budgets header")
        with self.subTest("with the EXPERT rule"):
            self.assertIn("EXPERT         asks first, at most 1 per task", out, "EXPERT line")
        with self.subTest("no fan-out or direct-mode line (2.4)"):
            self.assertNotRegex(out, r"fan-out|direct mode", "the fan-out and direct-mode lines went with 2.4")
        with self.subTest("and the token table"):
            self.assertIn("tokens / task  T0 0.4M  T1 0.8M  T2 2M  T3 6M  T4 10M  T5 16M", out, "token table")
        with self.subTest("no profile installed: exit 1"):
            none = self.path("none")
            rc, _ = self.run_script("--budgets", CLAUDE_CONFIG_DIR=none, CODEX_HOME=none)
            self.assertEqual(rc, 1, "budgets without a profile")

    def test_the_incremental_parse_cache_reads_only_what_it_has_not_read_before(self):
        # Every case here asserts the cached run against the same run with the cache
        # off: the cache may change what is read, never what is reported.
        c, cp = self.path("cache.json"), self.path("cproj")
        s = os.path.join(cp, "s.jsonl")
        os.makedirs(cp)
        with open(SCRIPT, encoding="utf-8") as fh:
            version = int(re.search(r"(?m)^CACHE_VERSION = (\d+)", fh.read()).group(1))

        def cached():
            return self.out("--root", cp, USAGE_REPORT_CACHE=c)

        def plain():
            return self.out("--root", cp, USAGE_REPORT_CACHE="")

        def cache_json():
            with open(c, encoding="utf-8") as fh:
                return json.load(fh)

        def poison(state, ver=version):
            st = os.stat(s)
            write(c, json.dumps({"version": ver, "files": {os.path.abspath(s): {
                "kind": "claude", "mtime": st.st_mtime, "size": st.st_size,
                "offset": st.st_size, "head": "0" * 16, "state": json.loads(state)}}}))

        write(s, CLINE % ("c1", 100000) + CLINE % ("c2", 100000))
        cold = cached()
        with self.subTest("a cold run reports what an uncached run reports"):
            self.assertEqual(cold, plain(), "cold run differs")
        with self.subTest("the whole file is recorded as folded"):
            entry = next(iter(cache_json()["files"].values()))
            size = os.stat(s).st_size
            self.assertEqual((entry["offset"], entry["size"]), (size, size), "offset/size not the file's size")

        os.chmod(s, 0)
        try:
            with self.subTest("an unchanged transcript is not read again at all"):
                self.assertEqual(cached(), cold, "an unchanged transcript was re-read")
        finally:
            os.chmod(s, 0o644)

        write(s, CLINE % ("c3", 100000), "a")
        with self.subTest("an appended transcript is folded from the offset, not from zero"):
            self.assertEqual(cached(), plain(), "append")

        write(s, '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"c4","model":"claude-son', "a")
        with self.subTest("a half-written last line is not folded"):
            self.assertEqual(cached(), plain(), "partial line")
        write(s, 'net-5","usage":{"input_tokens":0,"output_tokens":100000,"cache_creation_input_tokens":0,'
                 '"cache_read_input_tokens":0}}}\n', "a")
        with self.subTest("and is counted once once it is complete"):
            self.assertEqual(cached(), plain(), "completed line")

        # Grown *and* different from the first byte: without the head check this one
        # resumes from the old offset and bills the old records again.
        before = os.stat(s).st_size
        write(s, "".join(CLINE % ("dd%d" % i, 200000) for i in range(1, 8)))
        with self.subTest("the rewrite fixture is larger than what it replaced"):
            self.assertGreater(os.stat(s).st_size, before, "rewrite fixture is not larger")
        with self.subTest("a rewritten transcript is parsed from zero, not resumed"):
            self.assertEqual(cached(), plain(), "rewrite")
        write(s, CLINE % ("e1", 100000))  # shrunk
        with self.subTest("a truncated transcript is parsed from zero"):
            self.assertEqual(cached(), plain(), "truncate")

        os.remove(s)
        write(os.path.join(cp, "other.jsonl"), CLINE % ("f1", 100000))
        cached()
        with self.subTest("a transcript that is gone is dropped from the cache"):
            self.assertEqual(len(cache_json()["files"]), 1, "stale entry kept")

        write(c, "not json at all")
        with self.subTest("an unreadable cache is ignored, not fatal"):
            self.assertEqual(cached(), plain(), "corrupt cache")
        # A perfectly well-formed entry for this very file, under another version
        # number and with numbers of its own: if the version is not checked, the report
        # quotes them.
        write(s, CLINE % ("v1", 100000))
        poison('{"n": 1, "recs": {"v9": {"*": ["2026-09-01", "2026-09-01T10:00:00Z", "claude-sonnet-5", 0, 900000,'
               ' 0, 0]}}}', 999)
        with self.subTest("a cache written by another version is ignored"):
            self.assertEqual(cached(), plain(), "version mismatch")
        # Version 2 stored an exponent-form count as 0; that row must not outlive the fix.
        write(s, CLINE.replace('"output_tokens":%s', '"output_tokens":"%s"') % ("e2", "1e5"))
        poison('{"n": 1, "recs": {"e2": {"*": ["2026-09-01", "2026-09-01T10:00:00Z", "claude-sonnet-5", 0, 0, 0,'
               ' 0]}}}', 2)
        with self.subTest(V2_CACHE_CASE):
            self.assertEqual(cached(), plain(), "stale v2 cache")

        write(s, CLINE % ("g1", 100000))  # the prune case above removed it
        # Two layers, and each needs an entry the other one would not stop.
        # 1. The wrong shape, on a file that has not changed: nothing is folded, so only
        #    the shape check stands between the state and the report.
        poison('{"n": 0, "recs": "not a dict"}')
        with self.subTest("a wrong-shaped state is dropped before it is used, unchanged file and all"):
            self.assertEqual(cached(), plain(), "wrong-shaped state")
        # 2. The right shape, rubbish inside it, on a file the fold will not touch:
        #    only a check on the records themselves stands between it and the report.
        poison('{"n": 0, "recs": {"m": "not a bucket"}}')
        with self.subTest("a state with rubbish in an untouched record is dropped too"):
            self.assertEqual(cached(), plain(), "unfoldable state")
        poison('{"n": 0, "recs": {"m": {"*": ["2026-09-01", "t", "claude-sonnet-5", 0, "not a count", 0, 0]}}}')
        with self.subTest("and so is a record whose token counts are not numbers"):
            self.assertEqual(cached(), plain(), "bad row")

        os.remove(c)
        self.run_script("--root", cp, "--no-cache", USAGE_REPORT_CACHE=c)
        with self.subTest("--no-cache neither reads nor writes the cache"):
            self.assertFalse(os.path.exists(c), "--no-cache wrote the cache")

    def test_today_reads_the_same_slot_cached_or_not(self):
        # --today reads a per-day slot out of the fold state; a cached state must serve
        # it exactly as a fresh one does.
        td = self.path("today")
        s = os.path.join(td, "s.jsonl")
        now = datetime.datetime.now(datetime.timezone.utc)
        stamp = "%Y-%m-%dT%H:%M:%SZ"
        yst = (now - datetime.timedelta(days=1)).strftime(stamp)
        now = now.strftime(stamp)

        def tcached():
            return self.out("--root", td, "--today", USAGE_REPORT_CACHE=self.path("today-cache.json"))

        def tplain():
            return self.out("--root", td, "--today", USAGE_REPORT_CACHE="")

        # Yesterday's block is the larger one, so the per-day winner and the overall
        # winner are different rows: a parser that keeps one winner per response and
        # filters afterwards reports nothing for today, and $1.00 is what separates the
        # two implementations. Comparing cached against uncached cannot: both would lose
        # the slots together.
        write(s, TLINE_AT % (yst, "straddle", 300000) + TLINE_AT % (now, "straddle", 100000))
        first = tcached()
        with self.subTest("--today bills today's own winner, not the response's largest block"):
            self.assertIn("TOTAL  $1.00", first, "--today total")
        with self.subTest("--today off a cold cache picks the same slot as an uncached run"):
            self.assertEqual(first, tplain(), "--today cold")
        with self.subTest("--today off a warm cache picks the same slot"):
            self.assertEqual(tcached(), tplain(), "--today warm")
        write(s, TLINE_AT % (now, "later", 100000), "a")
        with self.subTest("--today after an append picks the same slot"):
            self.assertEqual(tcached(), tplain(), "--today append")

    def test_a_last_line_with_no_newline(self):
        # A transcript whose last line has no newline after it: the record still counts,
        # and it counts once, cached or not.
        nl = self.path("nonl")
        write(os.path.join(nl, "s.jsonl"), CLINE % ("n1", 100000) + (CLINE % ("n2", 100000)).rstrip("\n"))
        cache = self.path("nonl-cache.json")
        out = self.out("--root", nl, USAGE_REPORT_CACHE=cache)
        with self.subTest("a last line with no newline is still counted"):
            self.assertIn("TOTAL  $2.00", out, "unterminated last line")
        with self.subTest("and counted once on a rescan, cached or not"):
            self.assertEqual(self.out("--root", nl, USAGE_REPORT_CACHE=cache), out, "unterminated last line, rescan")
            self.assertEqual(self.out("--root", nl, USAGE_REPORT_CACHE=""), out, "unterminated last line, rescan")

    def test_the_other_runtimes_fold_state_is_never_handed_to_this_one(self):
        x, xc = self.path("xprov"), self.path("xprov-cache.json")
        write(os.path.join(x, "rollout-x.jsonl"),
              '{"type":"session_meta","timestamp":"2026-09-01T10:00:00Z","payload":{"id":"tx","session_id":"tx",'
              '"cwd":"/w","source":"cli"}}\n'
              '{"type":"token_usage_record","timestamp":"2026-09-01T10:00:02Z","payload":{"response_id":"rx",'
              '"turn_id":"t","usage":{"input_tokens":1000000,"cached_input_tokens":0,"cache_write_input_tokens":0,'
              '"output_tokens":0}}}\n')
        self.run_script("--provider", "codex", "--root", x, "--all", USAGE_REPORT_CACHE=xc)
        with self.subTest("a cache entry from the other runtime's fold is a miss, not a crash"):
            rc, out = self.run_script("--provider", "claude", "--root", x, "--all", USAGE_REPORT_CACHE=xc)
            self.assertEqual(rc, 0, "cross-provider cache entry\n" + out)
            self.assertNotIn("traceback", out.lower(), "cross-provider cache entry")
        with self.subTest("and the runtime that owns the directory still reports it"):
            out = self.out("--provider", "codex", "--root", x, "--all", USAGE_REPORT_CACHE=xc)
            self.assertRegex(out, r"(?m)^codex ", "codex after a claude read")
        # Two guards reject that entry, and the load-bearing one is the shape check:
        # the two folds' states have disjoint key sets, so `kind` is the cheap first cut
        # and cannot be pinned on its own by any state this program can produce. What is
        # pinned here is that an entry records the fold that wrote it.
        with self.subTest("an entry records the fold that wrote it"):
            with open(xc, encoding="utf-8") as fh:
                entry = next(iter(json.load(fh)["files"].values()))
            self.assertEqual(entry["kind"], "codex", "entry kind")

    def test_odd_token_counts_and_malformed_lines(self):
        od = self.path("odd")
        s = os.path.join(od, "s.jsonl")
        # Exponent and float spellings are still counts: 1e5 output tokens on sonnet is $1.00.
        write(s, CLINE.replace('"output_tokens":%s', '"output_tokens":"%s"') % ("e1", "1e5"))
        with self.subTest(EXPONENT_CASE):
            self.assertIn("TOTAL  $1.00", self.out("--root", od, USAGE_REPORT_CACHE=""), "exponent count")
        write(s, '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"e1","model":"claude-sonnet-5","usage":'
                 '{"input_tokens":"nan","output_tokens":1e999,"cache_creation_input_tokens":"x",'
                 '"cache_read_input_tokens":null}}}\n')
        with self.subTest("nan, infinity and words count as nothing, without a crash"):
            rc, out = self.run_script("--root", od, USAGE_REPORT_CACHE="")
            self.assertEqual(rc, 0, "non-finite counts\n" + out)
            self.assertRegex(out, r"(?im)^no usage records matched", "non-finite counts")
        write(s, "[]\n" '"a string"\n' "42\n" "null\n" '{"message":"not an object"}\n'
                 '{"message":{"usage":["not","an","object"]}}\n'
                 '{"message":{"id":{"x":1},"usage":{"output_tokens":5}},"timestamp":12345}\n'
                 + LINE % ("ok", "claude-sonnet-5", 100000, 0))
        with self.subTest("valid JSON of the wrong shape is skipped, the good line still counts"):
            rc, out = self.run_script("--root", od, USAGE_REPORT_CACHE="")
            self.assertEqual(rc, 0, "malformed lines\n" + out)
            self.assertIn("TOTAL  $1.00", out, "malformed lines")
        with self.subTest("and the same through the cache"):
            rc, out = self.run_script("--root", od, USAGE_REPORT_CACHE=self.path("odd-cache.json"))
            self.assertEqual(rc, 0, "malformed lines, cached\n" + out)
            self.assertIn("TOTAL  $1.00", out, "malformed lines, cached")


if __name__ == "__main__":
    unittest.main()
