#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Characterization of skills/ai-task/memory_sync.py, packages mode (small-oop-modules, WP4 s1;
constitution C2, C3): what `state.py memory ...`, the pre-push shim and the validator entry print,
return and write does not move while the file is split into sibling memory_* modules behind an
unchanged entry (R1, R5, R13). Recorded on the untouched tree, before anything moves.

The suite imports no memory module: every run is a subprocess (`python3 -I state.py --root <project>
...`, `python3 -I <memory_sync.py> ...`, `python3 -I <hooks/memory-pre-push.py> ...`, `git push`), on
a scratch git project with a bare remote, under a temporary directory with a temporary HOME. It never
runs against this repository.

What is recorded, per run: the command, its exit code, stdout and stderr; then a listing of
.ai/memory/ and .ai/local/memory/ (a few commands add .ai/reports/ and .ai/state/logs/): the path and
the sha256 of the file's text after NORMALISE. Four goldens under tests/fixtures/memory/goldens/sync/:

  commands.txt   one project, in order: `memory enable` (and the written .git/hooks/pre-push, whole,
                 with its mode), two light tasks closed (the export lines), status, show (md and
                 --json), export, verify --all, --fresh-clone, --range, a push through the installed
                 hook, risk add / close, risks, a note redacted, cleanup, restore, pack, disable
  validator.txt  the validator by path: `python3 -I skills/ai-task/memory_sync.py` and
                 hooks/memory-pre-push.py with --range, --tree, the hook form on stdin (a known remote
                 ref, a new branch, a tag, a deletion), clean and with one tampered package (exit 1),
                 an unknown rev (exit 3), files mode (silent), `memory verify --range` over the same
  migrate.txt    a copy of tests/fixtures/memory/legacy-reports: migrate --report, --apply --risks,
                 --move-logs from an agent session (exit 5) and as a human, verify --all
  refusals.txt   the refusals: an agent session for the human's commands (exit 5), a usage or
                 argument error (exit 2), nothing to act on (exit 1)

The goldens pin two things on purpose. The shim text (the written .git/hooks/pre-push, with
<PLUGIN>/skills/ai-task/memory_sync.py among its candidates): the shim must keep pointing at the entry
(decision D2). And two residuals that stay as they are (plan WP4, Risks): `export` skips every key
that already has a seal, and `memory enable` through a dialog pick leaves no committed record.

Regenerating the goldens (only for a change that is meant to move a recorded field, never to make a
refactoring pass):

  UPDATE_GOLDENS=1 python3 -I tests/run_suite.py tests/test_memory_sync_characterization.py

Without the switch a missing or different golden fails, with a unified diff.

NORMALISE is exactly what is erased before the compare, in this order, and nothing else
(FC8: the review reads this list before the diff). The exact strings come first and are never a path
regex: a generic path pattern would hide a moved SELF in the shim text.

  PLUGIN      this checkout (the directory above skills/), abspath and realpath, an exact string
              replace by the token <PLUGIN>
  ROOT        the scratch project directory, abspath and realpath, exact, -> <ROOT>
  TMP         the temporary directory that holds the project, the bare remote and HOME, exact,
              -> <TMP>
  RUN_DATE    the UTC date the run started on, and the one it ended on, exact (YYYY-MM-DD) -> <DATE>
              (a risk's "found" line; applied after TS, which keeps a timestamp's time as <TS> first)
  ZERO_SHA    forty zeros (git's null sha, kept apart from the others) -> <ZERO>
  TS          an ISO-8601 UTC timestamp 2026-10-31T12:00:00Z (optional fraction) -> <TS>
  TASK_ID     T-2026-11-11-1949-slug and the old T-2026-10-20-003 -> <ID>
  PERIOD      a package period 2026-Q4 -> <PERIOD>
  BATCH       the random suffix of a batch name, in `<author>.<4 chars>.jsonl` and `"batch":"..."`
              (random.SystemRandom, not seedable) -> <B>
  SHA64       64 hex digits (a digest, a log hash) -> <SHA64>
  SHA40       40 hex digits (a commit, a tree) -> <SHA40>
  RID         a record id `r1-` and 24 hex digits -> <RID>
  SHORT_SHA   an abbreviated sha, 9 or 12 hex digits with a digit among them -> <SHA9> / <SHA12>
  MS          `in 12 ms` and `"ms": 12` -> `in <N> ms` / `"ms": <N>`
  STAMP       the compact UTC stamp 20261111T195749Z of a backup's name (migrate --apply) -> <STAMP>
  TAR         not an erasure: a backup .tar (migrate --apply) holds file mtimes, so the listing hashes
              the member names and the sha256 of each member's normalised text, not the archive's bytes
  LINE_ORDER  not an erasure: the record lines of a .jsonl file are sorted (a package's header line
              stays first) before the listing hashes them, because state.py orders them by rid, a hash
              of the timestamps NORMALISE erases. The golden pins the set of lines, not their order
  GIT_NOISE   not an erasure of ours: from the stderr of a `git push` run through the hook, git's own
              lines (`error: ...`, `hint: ...`, `To <url>`) are dropped: their wording is git's, the
              hook's lines (`memory-pre-push: ...`) stay
  BYTES       `5 428 bytes` (the size of a package: it holds the scratch paths) -> `<N> bytes`

Nothing else is erased: not the exit codes, not the order of lines, not a path outside the exact
ones above, not a mode. The listing's sha256 is of the text after NORMALISE, so a file whose bytes
carry a run-time value other than these makes the golden unstable (test_the_run_is_repeatable runs
the first scenario twice). Add a rule to NORMALISE and to this list together; test_docstring_lists_
every_rule fails otherwise.
"""
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

sys.dont_write_bytecode = True  # no __pycache__ beside the files the test imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position

ROOT = mh.ROOT
SYNC = os.path.join(ROOT, "skills", "ai-task", "memory_sync.py")
GOLDENS = os.path.join(ROOT, "tests", "fixtures", "memory", "goldens", "sync")
LEGACY = os.path.join(mh.FIXTURES, "legacy-reports")
UPDATE_GOLDENS = bool(os.environ.get("UPDATE_GOLDENS"))
ZERO = "0" * 40
PINNED = {"USER": "golden-user", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "COLUMNS": "80",
          "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
GIT_NOISE = re.compile(r"(error|hint|To) ")
RULES = ("PLUGIN", "ROOT", "TMP", "RUN_DATE", "ZERO_SHA", "TS", "TASK_ID", "PERIOD", "BATCH", "SHA64", "SHA40",
         "RID", "SHORT_SHA", "MS", "BYTES", "STAMP", "TAR", "LINE_ORDER", "GIT_NOISE")

# (name, pattern, replacement): the regular-expression part of NORMALISE, in order. No pattern here
# may match a path (test_no_rule_erases_a_path); the exact replacements are in Normaliser.apply.
PATTERNS = (
    ("ZERO_SHA", re.compile(r"\b0{40}\b"), "<ZERO>"),
    ("TS", re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"), "<TS>"),
    ("TASK_ID", re.compile(r"T-\d{4}-\d{2}-\d{2}-(?:\d{4}-[a-z0-9-]*[a-z0-9]|\d{3})"), "<ID>"),
    ("PERIOD", re.compile(r"\b\d{4}-Q[1-4]\b"), "<PERIOD>"),
    ("BATCH", re.compile(r"(\.[a-z0-9-]+\.)[a-z0-9]{4}(\.jsonl)|(\"batch\": ?\")[a-z0-9]{4}\""),
     lambda m: "%s<B>%s" % (m.group(1), m.group(2)) if m.group(1) else '%s<B>"' % m.group(3)),
    ("STAMP", re.compile(r"\b\d{8}T\d{6}Z\b"), "<STAMP>"),
    ("SHA64", re.compile(r"\b[0-9a-f]{64}\b"), "<SHA64>"),
    ("SHA40", re.compile(r"\b[0-9a-f]{40}\b"), "<SHA40>"),
    ("RID", re.compile(r"\br\d+-[0-9a-f]{24}\b"), "<RID>"),
    ("SHORT_SHA", re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{9}\b"), "<SHA9>"),
    ("SHORT_SHA", re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{12}\b"), "<SHA12>"),
    ("MS", re.compile(r"\bin \d+ ms\b"), "in <N> ms"),
    ("MS", re.compile(r"\"ms\": ?\d+"), '"ms": <N>'),
    ("BYTES", re.compile(r"\d[\d ]* bytes\b"), "<N> bytes"),
)


def utc_date():
    return time.strftime("%Y-%m-%d", time.gmtime())


class Normaliser:
    """Applies NORMALISE to the text of one run: the exact strings first, longest first."""

    def __init__(self, root, tmp, dates):
        self.exact = []
        for token, paths in (("<PLUGIN>", {ROOT, os.path.realpath(ROOT)}),
                             ("<ROOT>", {root, os.path.realpath(root)}),
                             ("<TMP>", {tmp, os.path.realpath(tmp)})):
            self.exact += [(path, token) for path in paths]
        self.exact.sort(key=lambda pair: -len(pair[0]))
        self.dates = sorted(set(dates))

    def apply(self, text):
        for path, token in self.exact:
            text = text.replace(path, token)
        for _name, pattern, replacement in PATTERNS:
            text = pattern.sub(replacement, text)
        for date in self.dates:
            text = text.replace(date, "<DATE>")
        return text


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sorted_records(text, header):
    """LINE_ORDER: a .jsonl file's record lines in sorted order (a package's header line stays first):
    state.py writes them ordered by rid, a hash of the record's timestamps, so their order moves from
    run to run once the timestamps are erased."""
    lines = text.split("\n")
    first = lines[:1] if header else []
    return "\n".join(first + sorted(lines[len(first):]))


class Scenario:
    """One scratch project with a bare remote under a temporary directory, the log of the runs made on
    it, and the listing after each."""

    def __init__(self, legacy=False):
        self.dates = [utc_date()]
        self.tmp = tempfile.mkdtemp(prefix="memsync-golden-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.saved = {k: os.environ.get(k) for k in list(PINNED) + ["HOME"]}
        os.environ.update(PINNED, HOME=self.home)
        self.p = mh.Project("p", tmp=self.tmp)
        self.remote = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", self.remote], check=True)
        self.p.git("remote", "add", "origin", self.remote)
        if legacy:
            for task in sorted(os.listdir(LEGACY)):
                shutil.copytree(os.path.join(LEGACY, task), self.p.path(".ai/reports/" + task))
            self.p.write(".ai/project/known-risks.md", LEGACY_RISKS)
            self.p.commit("legacy reports")
        self.norm = Normaliser(self.p.root, self.tmp, self.dates)
        self.log = []

    def close(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- recording
    def text(self, text):
        self.dates.append(utc_date())
        self.norm = Normaliser(self.p.root, self.tmp, self.dates)
        return self.norm.apply(text)

    def listing(self, *extra):
        """The path and the sha256 of the normalised text of every file under .ai/memory/ and
        .ai/local/memory/ (and of `extra`), sorted by the normalised path."""
        rows = []
        for rel in (".ai/memory", ".ai/local/memory") + extra:
            for path in self.p.files_under(rel):
                if path.endswith(".tar"):
                    rows.append((self.text(path), sha256(self.tar_members(path))))
                    continue
                data = self.text(self.p.read(path, binary=True).decode("utf-8", "replace"))
                if path.endswith(".jsonl"):
                    data = sorted_records(data, header=path.startswith(".ai/memory/"))
                rows.append((self.text(path), sha256(data)))
        out = ["--- listing (path, sha256 of the normalised text)\n"]
        out += ["%s  %s\n" % row for row in sorted(rows)]
        return "".join(out)

    def tar_members(self, rel):
        """TAR: the member names of an archive and the sha256 of each member's normalised text."""
        out = []
        with tarfile.open(self.p.path(rel)) as tar:
            for member in tar.getmembers():
                body = tar.extractfile(member).read().decode("utf-8", "replace") if member.isfile() else ""
                out.append("%s %s" % (self.text(member.name), sha256(self.text(body))))
        return "\n".join(sorted(out))

    def record(self, label, done, extra=()):
        """Log one finished process: the command, exit, stdout, stderr (if any), the listing."""
        body = "$ %s\nexit %d\n--- stdout\n%s" % (label, done.returncode, done.stdout)
        if done.stdout and not done.stdout.endswith("\n"):
            body += "\n"
        if done.stderr:
            body += "--- stderr\n%s" % done.stderr
            if not done.stderr.endswith("\n"):
                body += "\n"
        self.log.append(self.text(body) + self.listing(*extra) + "\n")
        return done

    def note(self, text):
        self.log.append(self.text("##### %s\n\n" % text))

    # ---- runs
    def state(self, *args, human=False, extra=(), env=None):
        done = self.p.run(*args, human=human, env=env)
        who = "human" if human else "agent"
        return self.record("state.py %s %s" % (" ".join(shlex.quote(a) for a in args), "(%s)" % who), done, extra)

    def tool(self, label, script, *args, cwd=None, stdin=""):
        done = subprocess.run([sys.executable, "-I", script, *args], cwd=cwd or self.p.root, input=stdin,
                              capture_output=True, text=True, check=False, env=mh.clean_env())
        feed = " < %s" % shlex.quote(stdin.strip().replace("\n", " ; ")) if stdin.strip() else (
            " < (empty stdin)" if not args or args[0] == "origin" else "")
        return self.record("python3 -I %s %s%s" % (label, " ".join(shlex.quote(a) for a in args), feed), done)

    def git(self, label, *args):
        done = self.p.git(*args, check=False, env=mh.clean_env())
        done.stderr = "".join(line for line in done.stderr.splitlines(True) if not GIT_NOISE.match(line))
        return self.record("git %s" % label, done)

    def head(self):
        return self.p.git("rev-parse", "HEAD").stdout.strip()

    def hook_text(self):
        path = self.p.path(".git/hooks/pre-push")
        if not os.path.exists(path):
            self.log.append("##### .git/hooks/pre-push: absent\n\n")
            return
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.log.append("##### .git/hooks/pre-push, mode %o, whole:\n%s\n" % (os.stat(path).st_mode & 0o777,
                                                                          self.text(text)))

    def write_golden(self, name):
        text = "".join(self.log)
        path = os.path.join(GOLDENS, name)
        if UPDATE_GOLDENS:
            os.makedirs(GOLDENS, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return None
        if not os.path.exists(path):
            return "no golden %s (UPDATE_GOLDENS=1 writes it)" % path
        with open(path, encoding="utf-8") as fh:
            want = fh.read()
        if want == text:
            return None
        return "".join(difflib.unified_diff(want.splitlines(True), text.splitlines(True), "golden/" + name,
                                            "run/" + name))


LEGACY_RISKS = ("# Known risks\n\n<!-- notes -->\n\n## First thing\n\n- **Found**: 2026-10-01, by T-2026-10-01-001\n"
                "- **Where**: `src/widget.py:1`\n- **What could go wrong**: it breaks\n- **Status**: open\n\n"
                "## Second thing\n\n- **Where**: `hooks/x.py`\n- **Status**: accepted — callers\n"
                "- **Label**: KNOWN FACT\n")


def batch_file(scn):
    names = sorted(os.listdir(scn.p.path(".ai/memory")))
    return names[0]


def two_tasks(scn):
    """Two light tasks closed in packages mode, the second with a note; returns their ids."""
    one, out = scn.p.light_task("tweak the widget")
    scn.log.append(scn.text("##### light task 1 closed: stdout of `state.py close`\n%s\n" % out))
    two = scn.p.start("tweak the widget again")
    scn.p.ok("event", "note", "--data", json.dumps({"kind": "decision", "text": "keep the old key",
                                                    "why": "callers depend on it"}))
    scn.p.write("src/widget.py", "x = 3\n")
    scn.p.ok("verify", "--scope", "all")
    out = scn.p.ok("close").stdout
    scn.log.append(scn.text("##### light task 2 closed (with a note): stdout of `state.py close`\n%s\n" % out))
    return one, two


def run_commands():
    """The first golden: the whole life of one packages-mode project."""
    scn = Scenario()
    base = scn.head()
    scn.state("memory", "enable", "--author", "dev", human=True)
    scn.hook_text()
    one, two = two_tasks(scn)
    scn.listing()
    scn.record("state.py memory status (after the tasks, before any commit)",
               scn.p.run("memory", "status"))
    scn.p.commit("two tasks")
    scn.state("memory", "status")
    scn.state("memory", "status", "--json")
    scn.state("memory", "show", one)
    scn.state("memory", "show", two, "--md")
    scn.state("memory", "show", two, "--json")
    scn.state("memory", "export")
    scn.state("memory", "export", "--pending")
    scn.state("memory", "verify", "--all")
    scn.state("memory", "verify", one)
    scn.state("memory", "verify", "--all", "--json")
    scn.state("memory", "verify", "--fresh-clone")
    scn.state("memory", "verify", "--range", "%s..HEAD" % base)
    scn.state("memory", "verify", "--range", "%s..HEAD" % base, "--json")
    # a close that dies inside the export (A9: B2 before the write, B4 inside it) leaves the task pending;
    # `memory export` finishes it (the export lines)
    for n, point in enumerate(("B2", "B4")):
        scn.p.start("crash at %s" % point)
        scn.p.write("src/widget.py", "x = %d\n" % (n + 10))
        scn.p.ok("verify", "--scope", "all")
        scn.record("state.py close (agent, AI_MEMORY_CRASH_AT=%s)" % point,
                   scn.p.run("close", env={"AI_MEMORY_CRASH_AT": point}))
        scn.state("memory", "status")
        scn.state("memory", "export")
        scn.state("memory", "export")
    scn.state("memory", "verify", "--all")
    scn.p.commit("two crashed closes, exported")
    scn.git("push origin main (the installed hook runs)", "push", "-q", "origin", "main")
    scn.state("memory", "risk", "add", "--title", "Cache key ignores the locale", "--where", "src/widget.py:1",
              "--label", "KNOWN FACT", "--what", "two locales share one cache entry", "--likely", "medium",
              "--fix", "add the locale to the key")
    scn.state("memory", "risks")
    scn.state("memory", "risks", "--status", "all", "--json")
    rkey = [json.loads(line)["rkey"] for line in
            scn.p.run("memory", "risks", "--json").stdout.splitlines()][0]
    scn.state("memory", "risk", "close", rkey, "--status", "accepted", "--why", "callers depend on it")
    scn.state("memory", "risks", "--status", "all")
    scn.state("memory", "export", "--pending")
    scn.p.commit("a risk")
    scn.state("memory", "verify", "--all")
    # cleanup moves the reports of exported tasks out of the tree; restore brings one back
    scn.p.memory_json(cleanup=True)
    scn.p.commit("cleanup on")
    extra = (".ai/reports", ".ai/state/logs")
    scn.state("memory", "cleanup", "--all", "--confirm-delete", "dev", human=True, extra=extra)
    scn.state("memory", "restore", one, extra=extra)
    scn.state("memory", "restore", "--all", extra=extra)
    note = [e for e in package_entries(scn.p) if e["kind"] == "note"][0]
    scn.state("memory", "redact", note["rid"], "--field", "text", "--why", "a secret", human=True)
    scn.state("memory", "verify", "--all")
    scn.p.commit("redacted")
    # pack: the one batch is made a batch of a closed period (its header and its name), then packed
    age_batch(scn.p, "2025-Q1")
    scn.p.commit("an old batch")
    scn.state("memory", "pack", "--period", "2025-Q1", "--confirm-delete", "dev", human=True)
    scn.state("memory", "verify", "--all")
    scn.state("memory", "status")
    scn.state("memory", "disable", human=True)
    scn.hook_text()
    scn.state("memory", "status")
    return scn


def package_entries(p):
    """The records of every package, headers left out."""
    out = []
    for name in sorted(os.listdir(p.path(".ai/memory"))):
        out += [json.loads(line) for line in p.read(".ai/memory/" + name).splitlines()[1:]]
    return out


def age_batch(p, period):
    """Rewrites the project's only batch as a batch of `period` (header and file name)."""
    name = sorted(os.listdir(p.path(".ai/memory")))[0]
    lines = p.read(".ai/memory/" + name, binary=True).split(b"\n")
    header = json.loads(lines[0])
    header["period"] = period
    lines[0] = json.dumps(header, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    new = "%s.%s.%s.jsonl" % (period, header["author"], header["batch"])
    p.write(".ai/memory/" + new, b"\n".join(lines), mode="wb")
    os.remove(p.path(".ai/memory/" + name))


def run_validator():
    """The second golden: the validator by path, the hook form, a tampered package."""
    scn = Scenario()
    scn.state("memory", "enable", "--author", "dev", human=True)
    scn.p.commit("enable")
    base = scn.head()
    scn.git("push origin main (nothing of ours yet)", "push", "-q", "origin", "main")
    two_tasks(scn)
    good = scn.p.commit("two tasks")
    scn.git("fetch origin", "fetch", "-q", "origin")
    hook = mh.HOOK
    for label, script in (("<PLUGIN>/skills/ai-task/memory_sync.py", SYNC),
                          ("<PLUGIN>/hooks/memory-pre-push.py", hook)):
        scn.note("the validator %s" % label)
        scn.tool(label, script, "--range", "%s..%s" % (base, good))
        scn.tool(label, script, "--range", "%s..HEAD" % base)
        scn.tool(label, script, "--tree", "HEAD")
        scn.tool(label, script, "--tree", good)
        scn.tool(label, script, "--repo", scn.p.root, "--tree", "HEAD", cwd=scn.tmp)
        scn.tool(label, script, "origin", scn.remote, stdin="refs/heads/main %s refs/heads/main %s\n" % (good, base))
        scn.tool(label, script, "origin", scn.remote, stdin="refs/heads/new %s refs/heads/new %s\n" % (good, ZERO))
        scn.tool(label, script, "origin", scn.remote, stdin="refs/tags/v1 %s refs/tags/v1 %s\n" % (good, ZERO))
        scn.tool(label, script, "origin", scn.remote, stdin="(delete) %s refs/heads/gone %s\n" % (ZERO, base))
        scn.tool(label, script, "origin", scn.remote, stdin="")
        scn.tool(label, script, "--range", "%s..nosuchrev" % base)
        scn.tool(label, script, "--tree", "nosuchrev")
        scn.tool(label, script, "--range", "nodots")
        scn.tool(label, script, "origin", scn.remote, stdin="refs/heads/main %s refs/heads/main %s\n" % ("1" * 40, base))
    # one tampered package: a carriage return at the end of a record line (V1)
    scn.note("one tampered package, on a branch of its own")
    scn.p.git("checkout", "-q", "-b", "tamper")
    name = batch_file(scn)
    lines = scn.p.read(".ai/memory/" + name, binary=True).split(b"\n")
    lines[1] += b"\r"
    scn.p.write(".ai/memory/" + name, b"\n".join(lines), mode="wb")
    bad = scn.p.commit("tampered")
    scn.p.git("checkout", "-q", "main")
    for label, script in (("<PLUGIN>/skills/ai-task/memory_sync.py", SYNC),
                          ("<PLUGIN>/hooks/memory-pre-push.py", hook)):
        scn.tool(label, script, "--range", "%s..%s" % (good, bad))
        scn.tool(label, script, "--range", "%s..%s" % (base, bad))
        scn.tool(label, script, "--tree", bad)
        scn.tool(label, script, "origin", scn.remote, stdin="refs/heads/tamper %s refs/heads/tamper %s\n" % (bad, ZERO))
        scn.tool(label, script, "origin", scn.remote,
                 stdin="refs/heads/main %s refs/heads/main %s\nrefs/heads/tamper %s refs/heads/tamper %s\n"
                 % (good, base, bad, ZERO))
    scn.state("memory", "verify", "--range", "%s..%s" % (good, bad))
    scn.state("memory", "verify", "--range", "%s..%s" % (good, bad), "--json")
    scn.git("push origin tamper (the installed hook refuses)", "push", "-q", "origin", "tamper")
    scn.git("push origin main (the installed hook lets it through)", "push", "-q", "origin", "main")
    # files mode at the tip: the validator is silent
    scn.p.git("checkout", "-q", "-b", "off")
    scn.p.memory_json(mode="files")
    off = scn.p.commit("files mode")
    scn.note("files mode at the tip")
    scn.tool("<PLUGIN>/skills/ai-task/memory_sync.py", SYNC, "--range", "%s..%s" % (good, off))
    scn.tool("<PLUGIN>/skills/ai-task/memory_sync.py", SYNC, "--tree", off)
    return scn


def run_migrate():
    """The third golden: migrate on a copy of legacy-reports."""
    scn = Scenario(legacy=True)
    scn.state("memory", "enable", "--author", "dev", human=True)
    scn.p.commit("legacy reports, memory on")
    scn.state("memory", "status")
    scn.state("memory", "migrate", "--report")
    scn.record("(the report) .ai/local/memory/migration-report.md",
               subprocess.CompletedProcess([], 0, scn.p.read(".ai/local/memory/migration-report.md"), ""))
    scn.state("memory", "migrate", "--apply", "--risks")
    # memory_migrate.backup names the tar to the second: wait for the next one, so the run always has two tars
    time.sleep(1.0 - time.time() % 1.0 + 0.05)
    scn.state("memory", "migrate", "--apply")
    scn.state("memory", "verify", "--all")
    scn.state("memory", "risks", "--status", "all")
    scn.p.commit("migrated")
    scn.state("memory", "verify", "--fresh-clone")
    scn.state("memory", "migrate", "--move-logs", "--confirm-delete", "dev")
    scn.state("memory", "migrate", "--move-logs", "--confirm-delete", "someone", human=True)
    scn.state("memory", "migrate", "--move-logs", human=True)
    scn.state("memory", "migrate", "--move-logs", "--confirm-delete", "dev", human=True,
              extra=(".ai/state/logs",))
    scn.state("memory", "status")
    return scn


def run_refusals():
    """The fourth golden: refusals."""
    scn = Scenario()
    scn.state("memory", "status")
    scn.state("memory", "export")
    scn.state("memory", "enable", "--author", "dev")
    scn.state("memory", "enable", "--author", "Bad Author!", human=True)
    scn.state("memory", "enable", "--author", "dev", human=True)
    scn.state("memory", "enable", "--author", "dev", human=True)
    one, _ = scn.p.light_task("tweak the widget")
    scn.p.commit("one task")
    scn.state("memory", "disable")
    scn.state("memory", "cleanup", "--all", "--confirm-delete", "dev")
    scn.state("memory", "cleanup", "--all", human=True)
    scn.state("memory", "cleanup", "--all", "--confirm-delete", "someone", human=True)
    scn.state("memory", "cleanup", "--confirm-delete", "dev", human=True)
    scn.state("memory", "cleanup", one, "--confirm-delete", "dev", human=True)
    scn.state("memory", "restore")
    scn.state("memory", "pack", "--period", "2025-Q1", "--confirm-delete", "dev")
    scn.state("memory", "pack", "--period", "2025-Q1", "--confirm-delete", "dev", human=True)
    scn.state("memory", "pack", "--period", "2999-Q1", "--confirm-delete", "dev", human=True)
    scn.state("memory", "pack", "--period", "nonsense", "--confirm-delete", "dev", human=True)
    scn.state("memory", "redact", "r1-000000000000000000000000", "--field", "text", "--why", "x")
    scn.state("memory", "redact", "r1-000000000000000000000000", "--field", "text", "--why", "x", human=True)
    scn.state("memory", "redact", "r1-000000000000000000000000", "--field", "task", "--why", "x", human=True)
    scn.state("memory", "migrate", "--move-logs", "--confirm-delete", "dev")
    scn.state("memory", "verify", "--range", "nodots")
    scn.state("memory", "verify", "--range", "nosuch..alsonot")
    scn.state("memory", "verify", "T-2026-01-01-001")
    scn.state("memory", "export", "not-an-id")
    scn.state("memory", "show", "T-2026-01-01-001")
    scn.state("memory", "show", "not-an-id")
    scn.state("memory", "risk", "add", "--title", "t", "--label", "NOT A LABEL", "--what", "w")
    scn.state("memory", "risk", "add", "--title", "t", "--label", "KNOWN FACT", "--what", "w", "--status", "bogus")
    scn.state("memory", "risk", "close", "k-none", "--status", "fixed", "--why", "x")
    scn.state("memory", "risk", "close", "k-none", "--status", "open", "--why", "x")
    scn.state("memory", "disable", human=True)
    scn.state("memory", "migrate", "--report")
    return scn


SCENARIOS = {"commands.txt": run_commands, "validator.txt": run_validator, "migrate.txt": run_migrate,
             "refusals.txt": run_refusals}


class TestGoldens(unittest.TestCase):
    maxDiff = None

    def check(self, name):
        scn = SCENARIOS[name]()
        self.addCleanup(scn.close)
        problem = scn.write_golden(name)
        self.assertIsNone(problem, problem)
        return scn

    def test_commands(self):
        self.check("commands.txt")

    def test_validator(self):
        self.check("validator.txt")

    def test_migrate(self):
        self.check("migrate.txt")

    def test_refusals(self):
        self.check("refusals.txt")

    def test_the_run_is_repeatable(self):
        """Two runs of the first scenario write the same text: NORMALISE leaves no run-time value."""
        first, second = run_commands(), run_commands()
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        self.assertEqual("".join(first.log), "".join(second.log))

    def test_the_shim_points_at_the_entry(self):
        """Decision D2: the shim's candidates include <PLUGIN>/skills/ai-task/memory_sync.py, spelled
        as the exact token, and the golden holds the text whole."""
        with open(os.path.join(GOLDENS, "commands.txt"), encoding="utf-8") as fh:
            golden = fh.read()
        self.assertIn('"<PLUGIN>/skills/ai-task/memory_sync.py" "$HOME/.claude/skills/ai-task/memory_sync.py"', golden)
        self.assertIn('for v in "<PLUGIN>/hooks/memory-pre-push.py"', golden)


class TestNormaliser(unittest.TestCase):
    def test_docstring_lists_every_rule(self):
        names = {name for name, _, _ in PATTERNS} | {"PLUGIN", "ROOT", "TMP", "RUN_DATE", "TAR", "LINE_ORDER", "GIT_NOISE"}
        self.assertEqual(names, set(RULES))
        for name in RULES:
            self.assertRegex(__doc__, r"(?m)^  %s " % name)

    def test_no_rule_erases_a_path(self):
        """The exact strings are the only rules that may shorten a path; a pattern leaves one whole."""
        norm = Normaliser("/nowhere/p", "/nowhere", [])
        for text in ("<PLUGIN>/skills/ai-task/memory_sync.py", "/opt/x/skills/ai-task/memory_io.py",
                     "/home/u/.claude/skills/ai-task/memory_sync.py", "$HOME/.claude/hooks/memory-pre-push.py"):
            self.assertEqual(norm.apply(text), text)

    def test_the_patterns(self):
        norm = Normaliser("/nowhere/p", "/nowhere", ["2026-11-11"])
        for text, want in (
                ("T-2026-11-11-1949-two closed", "<ID> closed"),
                ("T-2026-10-20-003 and 2026-Q4.dev.69d5.jsonl", "<ID> and <PERIOD>.dev.<B>.jsonl"),
                ('{"batch":"69d5","ms": 12}', '{"batch":"<B>","ms": <N>}'),
                ("%s %s r1-%s" % ("a" * 40, "0" * 40, "1" * 24), "<SHA40> <ZERO> <RID>"),
                ("1f699e14e and 1f699e14e1b3 in 3 ms, 5 428 bytes", "<SHA9> and <SHA12> in <N> ms, <N> bytes"),
                ("found 2026-11-11, at 2026-11-11T19:53:41.032Z", "found <DATE>, at <TS>")):
            self.assertEqual(norm.apply(text), want)


if __name__ == "__main__":
    unittest.main()
