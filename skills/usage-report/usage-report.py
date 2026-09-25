#!/usr/bin/env python3
"""Agent usage report — tokens, cost, time — for Claude Code and for Codex.

Zero model cost: run this instead of asking a model to re-derive the parsing
logic from the transcripts. Answers "what did this session cost", "how much did
today cost", "which model burned the tokens", "how much of it was subagents".

Both runtimes write local JSONL transcripts, but not the same ones, so there is
one parser per runtime and one shared aggregate. Everything downstream of
`Call` — pricing, grouping, the printed tables — is provider-neutral.

Usage:
    usage-report.py                       # current project, whichever runtimes have data
    usage-report.py --all                 # every project on this machine
    usage-report.py --today               # current UTC day
    usage-report.py --session ab          # session/thread id prefix
    usage-report.py --provider codex      # one runtime only
    usage-report.py --provider claude --root DIR   # explicit transcript dir
    usage-report.py --task T-2026-09-21-001 [--project DIR]
                                          # one /ai-task task: its window, tokens per
                                          # runtime, and each runtime's plan budget
    usage-report.py --budgets             # the installed plans' budget tables

--task and --budgets read the plan tables install.sh writes to
<home>/claude-agentic/profile.json. Budgets are reported, never enforced, and
the task's journal is only read.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import glob
import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict

CLAUDE_ROOT = os.path.expanduser(
    os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude") + "/projects"
)
CODEX_ROOT = os.path.expanduser(
    os.environ.get("CODEX_HOME", "~/.codex") + "/sessions"
)
PRICES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.json")


# --------------------------------------------------------------------- pricing

class Prices:
    """One provider's price table, loaded from prices.json."""

    def __init__(self, spec: dict):
        # Longest key first, so "gpt-5.6-sol" is tried before "gpt-5.6".
        self.rates = dict(spec["families"])
        self.families = sorted(self.rates, key=len, reverse=True)
        self.default = spec["default_family"]
        self.cw = spec.get("cache_write_multiplier", 2.0)
        self.cr = spec.get("cache_read_multiplier", 0.1)
        self.verified = bool(spec.get("rates_verified"))

    def family(self, model: str) -> str:
        m = (model or "").lower()
        for key in self.families:
            if key in m:
                return key
        return self.default

    def cost(self, model: str, inp: int, out: int, cw: int, cr: int) -> float:
        pin, pout = self.rates.get(self.family(model), self.rates[self.default])
        return (inp * pin + cw * pin * self.cw + cr * pin * self.cr + out * pout) / 1_000_000


def load_prices() -> dict[str, Prices]:
    with open(PRICES_PATH, encoding="utf-8") as fh:
        spec = json.load(fh)
    return {k: Prices(v) for k, v in spec.items() if not k.startswith("_")}


# ------------------------------------------------------------------ the record

class Call:
    """One billed model response, whichever runtime produced it.

    The parsers' only job is to turn a transcript into these; nothing after this
    point knows which runtime it came from.
    """

    __slots__ = ("provider", "session", "project", "day", "ts", "model",
                 "inp", "out", "cw", "cr", "is_subagent", "label")

    def __init__(self, provider, session, project, day, ts, model,
                 inp, out, cw, cr, is_subagent=False, label=""):
        self.provider = provider
        self.session = session
        self.project = project
        self.day = day
        self.ts = ts
        self.model = model
        self.inp = inp
        self.out = out
        self.cw = cw
        self.cr = cr
        self.is_subagent = is_subagent
        self.label = label


# ----------------------------------------------------------------- parse cache

CACHE_VERSION = 2


_CACHE_PATH: str | None = None


def cache_path() -> str:
    """Where the incremental parse cache lives. USAGE_REPORT_CACHE overrides it;
    setting that to an empty string turns the cache off altogether.

    Resolved once and remembered. `--task` chdirs into the project while the
    parsers run and back again before the flush, so resolving a relative path
    per call would read one file and write another. Resolving it once, from the
    directory the command was run in, is the answer a relative path deserves."""
    global _CACHE_PATH                  # pylint: disable=global-statement
    if _CACHE_PATH is None:
        env = os.environ.get("USAGE_REPORT_CACHE")
        if env is not None:
            _CACHE_PATH = os.path.abspath(os.path.expanduser(env)) if env else ""
        else:
            base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
            _CACHE_PATH = os.path.join(base, "claude-agentic", "usage-report.json")
    return _CACHE_PATH


_CACHE: dict | None = None


def cache_open(args) -> dict | None:
    """The cache for this run, read from disk once. None means "do not cache":
    --no-cache, an empty USAGE_REPORT_CACHE, or a file this version cannot read.
    A miss is never an error — the parsers simply read every line."""
    global _CACHE                       # pylint: disable=global-statement
    if getattr(args, "no_cache", False) or not cache_path():
        return None
    if _CACHE is None:
        _CACHE = {"version": CACHE_VERSION, "files": {}}
        try:
            with open(cache_path(), encoding="utf-8") as fh:
                disk = json.load(fh)
            if disk.get("version") == CACHE_VERSION and isinstance(disk.get("files"), dict):
                _CACHE["files"] = disk["files"]
        except (OSError, ValueError):
            pass
    return _CACHE


def cache_flush() -> None:
    """Write the cache back, atomically, dropping the transcripts that are gone.
    A cache that cannot be written is not worth failing a report over."""
    if _CACHE is None:
        return
    _CACHE["files"] = {k: v for k, v in _CACHE["files"].items() if os.path.exists(k)}
    path = cache_path()
    tmp = ""
    try:
        d = os.path.dirname(path) or "."
        os.makedirs(d, mode=0o700, exist_ok=True)
        # The entries hold project paths, session ids and token counts derived
        # from transcripts the runtimes keep at 0600; the cache stays as narrow.
        # mkstemp is O_EXCL with an unguessable name and mode 0600, so a
        # predictable path in a shared directory cannot be pre-created or
        # pointed somewhere else by a symlink.
        fd, tmp = tempfile.mkstemp(dir=d, prefix=os.path.basename(path) + ".",
                                   suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(_CACHE, fh)
        os.replace(tmp, path)
        tmp = ""
    except OSError:
        pass
    finally:
        # A unique temp name means an interrupted flush would otherwise leave a
        # full copy of the cache behind, every time, with nothing to overwrite
        # it. It goes on any exception, not only the one we expect.
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _head_sig(path: str, n: int = 256) -> str:
    """A fingerprint of the file's first bytes, so a transcript that was
    rewritten rather than appended to is not resumed from a stale offset."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read(n)).hexdigest()[:16]
    except OSError:
        return ""


def _row_ok(row, spec) -> bool:
    return (isinstance(row, list) and len(row) == len(spec)
            and all(isinstance(v, t) for v, t in zip(row, spec)))


def _state_ok(state, template: dict) -> bool:
    """Whether a state off the disk is the shape this fold works on. The
    template is an empty state from the same fold, so the check follows the fold
    rather than restating it."""
    return (isinstance(state, dict) and set(state) == set(template)
            and all(type(state[k]) is type(template[k]) for k in template))


def claude_valid(state: dict) -> bool:
    """Whether the records inside a claude state are the rows the parser reads
    back out of it. The fold only ever touches the records it is folding, so a
    state is checked here, on load, or its untouched half reaches the report
    unchecked — and `--today` and the merge read every row, not only the new."""
    return all(isinstance(bucket, dict)
               and all(_row_ok(r, (str, str, str, int, int, int, int))
                       for r in bucket.values())
               for bucket in state["recs"].values())


def codex_valid(state: dict) -> bool:
    """The same, for a codex state: a model row per turn, the fallback row, and
    one pending row per usage record."""
    return (all(_row_ok(r, (str, str)) for r in state["turn_model"].values())
            and _row_ok(state["last_model"], (str, str))
            and all(_row_ok(r, (str, str, str, str, int, int, int, int))
                    for r in state["pending"]))


def _fold_lines(state: dict, fold, blob: bytes) -> int:
    """Fold the complete lines in `blob`; return how many bytes they occupy.
    A trailing fragment is left for the caller: a transcript caught mid-write
    must not be folded half a record."""
    cut = blob.rfind(b"\n") + 1
    for raw in blob[:cut].split(b"\n")[:-1]:
        fold(state, raw.decode("utf-8", "replace"))
    return cut


def fold_file(path: str, kind: str, empty, fold, valid, cache: dict | None) -> dict:
    """Fold one transcript into its state, reading only what has not been read.

    The entry keeps the file's mtime and size, how many bytes were folded into
    the state, and the state itself — which is why the fold states are plain
    JSON. Same mtime and size: nothing is read at all. Grown since: only the
    bytes past the offset, and only up to the last complete line. Anything else
    — shrunk, a different first block, or a state some other fold wrote — is
    parsed from zero.

    A directory can be read as either runtime (`--root` with an explicit
    `--provider`, or a sniff that changes its answer as files arrive), so a
    state from the other fold must never be handed to this one. The load-bearing
    check is the shape check, which compares the state against an empty one from
    this fold: the two runtimes' states have disjoint key sets. `kind` is the
    cheap first cut in front of it, for a third fold that might not be so
    different. `valid` is then that fold's own check on the records inside the
    state. All three run before anything is read or folded: the cache costs a
    reparse when it is wrong, never a wrong report.
    """
    try:
        st = os.stat(path)
    except OSError:
        return empty()

    key = os.path.abspath(path)
    entry = (cache or {}).get("files", {}).get(key)
    state, start, head = None, 0, ""
    if (isinstance(entry, dict) and entry.get("kind") == kind
            and isinstance(entry.get("offset"), int)
            and 0 <= entry["offset"] <= st.st_size):
        if entry.get("mtime") == st.st_mtime and entry.get("size") == st.st_size:
            state, start, head = entry.get("state"), entry["offset"], entry.get("head", "")
        elif entry.get("head") and entry["head"] == _head_sig(path):
            state, start, head = entry.get("state"), entry["offset"], entry["head"]
    if not (_state_ok(state, empty()) and valid(state)):
        state, start, head = empty(), 0, ""

    tail = b""
    if start < st.st_size:
        with open(path, "rb") as fh:
            fh.seek(start)
            blob = fh.read()
        used = _fold_lines(state, fold, blob)
        start += used
        tail = blob[used:]
        head = _head_sig(path)

    if cache is not None:
        cache["files"][key] = {"kind": kind, "mtime": st.st_mtime,
                               "size": st.st_size, "offset": start,
                               "head": head, "state": state}

    if tail.strip():
        # A last line with no newline after it: a file still being written, or
        # one that simply ends that way. It is not folded into the state the
        # cache keeps — the next run will see it again, completed or not — but
        # it is folded into what this run reports, so ending a file without a
        # newline does not lose its last record.
        state = copy.deepcopy(state)
        fold(state, tail.decode("utf-8", "replace"))
    return state


# ------------------------------------------------------------- Claude Code

def claude_project_root(path: str) -> str:
    """Transcript dir for a project path, using Claude Code's mangling
    (every non-alphanumeric character -> '-')."""
    mangled = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))
    return os.path.join(CLAUDE_ROOT, mangled)


def claude_empty() -> dict:
    """The fold's state for one transcript: a line counter and the responses
    seen so far. Plain JSON types throughout, so it can be handed to something
    that stores it between runs."""
    return {"n": 0, "recs": {}}


def _num(value) -> int:
    """A token count as the state stores it. A transcript that writes one as a
    float or a string still folds, and the stored row still matches what the
    validator and the parser expect to read back."""
    try:
        return int(value or 0)
    except (OverflowError, TypeError, ValueError):
        return 0


def claude_fold(state: dict, line: str) -> None:
    """Add one transcript line to the state.

    One API response is written as several transcript lines — one per content
    block (thinking, text, tool_use) — each repeating the same message id and
    usage. Keep the line with the final (largest) output_tokens, or every
    response is billed two or three times over.

    Those lines are written as the blocks stream, so they do not all carry the
    same timestamp and a response can straddle a UTC midnight. `--today` used to
    be applied before this choice was made, which is not the same as applying it
    after: the winner among *today's* lines is not always the winner overall. So
    each response keeps a winner per day as well as one overall, under "*", and
    the filter picks the slot it needs. Days are "YYYY-MM-DD" and never collide
    with it.
    """
    n = state["n"]
    state["n"] = n + 1
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return
    msg = rec.get("message") or {}
    usage = msg.get("usage") or {}
    if not usage:
        return
    ts = rec.get("timestamp") or ""
    # A line with no id of its own is keyed by its position in the file; the
    # counter lives in the state so the key does not depend on where a read
    # happened to start.
    key = str(msg.get("id") or rec.get("requestId") or f"#{n}")
    row = [ts[:10], ts, str(msg.get("model") or "unknown"),
           _num(usage.get("input_tokens")),
           _num(usage.get("output_tokens")),
           _num(usage.get("cache_creation_input_tokens")),
           _num(usage.get("cache_read_input_tokens"))]
    bucket = state["recs"].setdefault(key, {})
    for slot in ("*", row[0]):
        prev = bucket.get(slot)
        if prev is None or row[4] > prev[4]:
            bucket[slot] = row


def parse_claude(root: str, args) -> list[Call]:
    cache = cache_open(args)
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    merged: dict[str, dict[str, list]] = {}
    owner: dict[tuple[str, str], tuple[str, str]] = {}
    for path in files:
        session = os.path.basename(path).removesuffix(".jsonl")
        if args.session and not session.startswith(args.session):
            continue
        project = (os.path.relpath(path, CLAUDE_ROOT).split(os.sep)[0]
                   if path.startswith(CLAUDE_ROOT) else root)
        state = fold_file(path, "claude", claude_empty, claude_fold,
                          claude_valid, cache)
        for key, bucket in state["recs"].items():
            # A positional key is only unique inside its own file.
            gkey = f"{path}:{key}" if key.startswith("#") else key
            dst = merged.setdefault(gkey, {})
            for slot, row in bucket.items():
                prev = dst.get(slot)
                if prev is None or row[4] > prev[4]:
                    dst[slot] = row
                    owner[(gkey, slot)] = (session, project)

    slot = today if args.today else "*"
    out_calls = []
    for gkey, bucket in merged.items():
        row = bucket.get(slot)
        if row is None:
            continue
        day, ts, model, inp, out, cw, cr = row
        session, project = owner[(gkey, slot)]
        out_calls.append(Call("claude", session, project, day, ts, model,
                              inp, out, cw, cr,
                              is_subagent=session.startswith("agent-")))
    return out_calls


# ------------------------------------------------------------------- Codex

def _subagent_name(source) -> str:
    """session_meta.payload.source is "cli"/"vscode" for a top-level session, or
    {"subagent": "review"} / {"subagent": {"other": "guardian"}} for a spawned one."""
    if not isinstance(source, dict):
        return ""
    sub = source.get("subagent")
    if isinstance(sub, str):
        return sub
    if isinstance(sub, dict):
        for v in sub.values():
            if isinstance(v, str):
                return v
        return "subagent"
    return ""


def codex_empty(thread: str) -> dict:
    """The fold's state for one rollout file. Plain JSON types, like the Claude
    one: the thread's identity, the model seen per turn, and the usage records.

    No per-day slots here, unlike claude_empty(): a response is one record, not
    several lines that can straddle a midnight, so `--today` stays where it was."""
    return {"thread": thread, "cwd": "", "sub": "", "is_sub": False,
            "turn_model": {}, "last_model": ["unknown", ""], "pending": []}


def codex_fold(state: dict, line: str) -> None:
    """Add one rollout line to the state.

    Unlike Claude Code there is no per-content-block repetition: each response is
    one `token_usage_record` whose `usage` is that response alone
    (`turn_token_usage` and `thread_token_usage` in the same record are running
    totals — summing those would count every earlier response again).

    The model is not on the usage record. It is on the `turn_context` record for
    the same `turn_id`, which is written before the turn runs; the last one seen
    is the fallback for a usage record whose turn was not announced in this file.
    """
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return
    kind = rec.get("type")
    payload = rec.get("payload") or {}

    if kind == "session_meta":
        state["cwd"] = str(payload.get("cwd") or "")
        state["thread"] = str(payload.get("id") or state["thread"])
        state["sub"] = _subagent_name(payload.get("source"))
        # A spawned thread carries its parent's session_id; a top-level
        # thread's session_id is its own id.
        state["is_sub"] = bool(state["sub"]) or (
            bool(payload.get("session_id"))
            and payload.get("session_id") != state["thread"]
        )
    elif kind == "turn_context":
        model = payload.get("model") or "unknown"
        effort = payload.get("effort") or ""
        model, effort = str(model), str(effort)
        if payload.get("turn_id"):
            state["turn_model"][str(payload["turn_id"])] = [model, effort]
        state["last_model"] = [model, effort]
        state["cwd"] = str(payload.get("cwd") or state["cwd"])
    elif kind == "token_usage_record":
        usage = payload.get("usage") or {}
        if not usage:
            return
        state["pending"].append([
            str(payload.get("response_id") or f"#{len(state['pending'])}"),
            str(payload.get("turn_id") or ""),
            (rec.get("timestamp") or "")[:10],
            rec.get("timestamp") or "",
            _num(usage.get("input_tokens")),
            _num(usage.get("cached_input_tokens")),
            _num(usage.get("cache_write_input_tokens")),
            _num(usage.get("output_tokens")),
        ])


def parse_codex(root: str, args) -> list[Call]:
    """Codex writes one rollout file per thread, and a subagent gets its own file.
    `response_id` is the dedup key, because a resumed thread can replay records
    into a second file."""
    cache = cache_open(args)
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    cwd = os.path.abspath(os.getcwd())

    seen: dict[str, Call] = {}
    for path in files:
        default_thread = os.path.basename(path).removesuffix(".jsonl")
        state = fold_file(path, "codex", lambda t=default_thread: codex_empty(t),
                          codex_fold, codex_valid, cache)

        thread_id = state["thread"] or default_thread
        if args.session and not thread_id.startswith(args.session):
            continue
        project = state["cwd"] or root
        if not args.all and not args.root and os.path.abspath(project) != cwd:
            continue

        for rid, turn, stamp, ts, total_in, cached, cw, out in state["pending"]:
            if args.today and stamp != today:
                continue
            gkey = f"{path}:{rid}" if str(rid).startswith("#") else rid
            if gkey in seen:
                continue
            model, effort = state["turn_model"].get(turn, state["last_model"])
            seen[gkey] = Call(
                "codex", thread_id, project, stamp, ts,
                model + (f" ({effort})" if effort else ""),
                # input_tokens is the whole prompt including the cached part;
                # billing the cached tokens at the full rate as well would
                # double-count them.
                max(total_in - cached, 0),
                out, cw, cached,
                is_subagent=state["is_sub"],
                label=state["sub"],
            )
    return list(seen.values())


# --------------------------------------------------------------- plan budgets

RUNTIMES = ("claude", "codex")


def runtime_home(runtime: str) -> str:
    if runtime == "codex":
        return os.path.expanduser(os.environ.get("CODEX_HOME", "~/.codex"))
    return os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude"))


def read_profile(runtime: str) -> dict:
    try:
        with open(os.path.join(runtime_home(runtime), "claude-agentic", "profile.json"),
                  encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def print_budgets() -> int:
    found = False
    for runtime in RUNTIMES:
        prof = read_profile(runtime)
        budgets = prof.get("budgets")
        if not isinstance(budgets, dict):
            continue
        found = True
        fan = budgets.get("fan_out") or {}
        expert = budgets.get("expert") or {}
        tokens = (budgets.get("tokens") or {}).get("per_task") or {}
        print(f"{runtime}: {prof.get('label') or prof.get('plan')} ({prof.get('plan')})")
        print(f"  fan-out        {fan.get('max_parallel_agents')} agents, "
              f"{fan.get('max_parallel_on_strong')} on STRONG/EXPERT"
              + (", serial" if fan.get("serial") else ""))
        print(f"  direct mode    up to {(budgets.get('direct_mode') or {}).get('max_tier')}")
        print(f"  EXPERT         {'without asking' if expert.get('without_asking') else 'asks first'}, "
              f"at most {expert.get('max_per_task')} per task")
        print("  tokens / task  " + "  ".join(f"{t} {v}M" for t, v in sorted(tokens.items())))
    if not found:
        print("no plan profile installed (install.sh writes <home>/claude-agentic/profile.json)")
        return 1
    print("\nBudgets are reported, never enforced. Calibrate them from --task.")
    return 0


def parse_ts(value: str):
    """An aware datetime; a stamp without an offset (Codex writes some) is UTC,
    so comparing it with the journal's window cannot raise TypeError."""
    try:
        ts = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)


def find_project(start: str) -> str | None:
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def task_report(args) -> int:
    """One task's window from its journal, the tokens each runtime spent in it,
    and each involved runtime's budget for the task's final tier."""
    project = find_project(args.project or os.getcwd())
    journal = os.path.join(project or "", ".ai", "reports", args.task, "events.jsonl")
    if not project or not os.path.isfile(journal):
        print(f"no journal for {args.task} (looked for {journal})")
        return 1
    events = []
    with open(journal, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    stamps = [parse_ts(e.get("ts")) for e in events if parse_ts(e.get("ts"))]
    if not stamps:
        print(f"the journal of {args.task} has no timestamps")
        return 1
    start = min(stamps)
    closed = [parse_ts(e.get("ts")) for e in events if e.get("event") == "task_closed"]
    end = max(c for c in closed if c) if any(closed) else dt.datetime.now(dt.timezone.utc)
    tier = "untiered"
    involved = []
    for e in events:
        data = e.get("data") or {}
        if e.get("event") in ("tier_set", "tier_raised"):
            tier = data.get("tier") or data.get("to") or tier
        for rt in (e.get("runtime"), data.get("from") if e.get("event") == "runtime_handoff" else None,
                   data.get("to") if e.get("event") == "runtime_handoff" else None):
            if rt in RUNTIMES and rt not in involved:
                involved.append(rt)

    here = os.getcwd()
    os.chdir(project)                     # the Codex parser keeps the threads of cwd
    try:
        calls = []
        for rt in involved or list(RUNTIMES):
            root = claude_project_root(project) if rt == "claude" else CODEX_ROOT
            if not os.path.isdir(root):
                continue
            calls += parse_claude(root, args) if rt == "claude" else parse_codex(root, args)
    finally:
        os.chdir(here)
    cache_flush()

    used: dict[str, list] = {rt: [0, 0, 0] for rt in involved}
    for c in calls:
        ts = parse_ts(c.ts)
        if ts is None or not start <= ts <= end:
            continue
        acc = used.setdefault(c.provider, [0, 0, 0])
        acc[0] += c.inp
        acc[1] += c.cw + c.cr
        acc[2] += c.out

    print(f"task {args.task} tier {tier} window {start.isoformat(timespec='seconds')}"
          f"..{end.isoformat(timespec='seconds')}")
    print("  (by time window: any other session in this project inside it is counted too)")
    for rt in involved or sorted(used):
        inp, cache, out = used.get(rt, [0, 0, 0])
        total = inp + cache + out
        print(f"{rt:<8} tokens in {inp:,} cache {cache:,} out {out:,} total {total:,}")
        prof = read_profile(rt)
        limit = (((prof.get("budgets") or {}).get("tokens") or {}).get("per_task") or {}).get(tier)
        if limit:
            print(f"         budget {prof.get('plan')} {tier} {float(limit):.1f}M · used "
                  f"{total / 1e6:.1f}M ({total / (float(limit) * 1e6):.0%})")
        else:
            print(f"         budget: no {rt} plan table for {tier}")
    return 0


# --------------------------------------------------------------- the report

def sniff_provider(root: str) -> str:
    """Which runtime wrote the transcripts in this directory.

    Codex names its files `rollout-<stamp>-<id>.jsonl` and tags every record with
    a `type`; Claude Code writes one `message` object per line. Undecidable — an
    empty or unreadable directory — answers claude, which is what a bare --root
    meant before this script knew about Codex.
    """
    files = sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))
    if any(os.path.basename(f).startswith("rollout-") for f in files):
        return "codex"
    for path in files[:5]:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "message" in rec:
                        return "claude"
                    if rec.get("type") in ("session_meta", "token_usage_record", "turn_context"):
                        return "codex"
        except OSError:
            continue
    return "claude"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", action="store_true", help="restrict to the current UTC day")
    ap.add_argument("--session", metavar="PREFIX", help="restrict to one session/thread id prefix")
    ap.add_argument("--all", action="store_true", help="scan every project, not just the current one")
    ap.add_argument("--root", help="explicit transcript directory (needs a single --provider)")
    ap.add_argument("--provider", choices=("auto", "claude", "codex", "both"), default="auto",
                    help="which runtime's transcripts to read (default: auto — whichever are present)")
    ap.add_argument("--task", metavar="ID", help="one /ai-task task: window, tokens per runtime, budget")
    ap.add_argument("--project", metavar="DIR", help="the project holding .ai/ (default: search upwards)")
    ap.add_argument("--no-cache", action="store_true",
                    help="ignore and do not write the incremental parse cache")
    ap.add_argument("--budgets", action="store_true", help="print the installed plans' budget tables")
    args = ap.parse_args()

    cache_path()        # resolved from the directory the command was run in
    if args.budgets:
        return print_budgets()
    if args.task:
        return task_report(args)

    prices = load_prices()

    roots = {"claude": CLAUDE_ROOT, "codex": CODEX_ROOT}
    if args.provider in ("claude", "codex"):
        wanted = [args.provider]
    elif args.provider == "both":
        wanted = ["claude", "codex"]
    else:
        wanted = [p for p in ("claude", "codex") if os.path.isdir(roots[p])]

    if args.root:
        # --root names one directory, so it selects one runtime. An explicit
        # --provider wins; otherwise sniff the directory, and fall back to
        # claude — which is what --root meant before Codex was supported.
        if args.provider in ("claude", "codex"):
            picked = args.provider
        else:
            picked = sniff_provider(args.root)
        wanted = [picked]
        roots[picked] = args.root

    missing = [p for p in wanted if not os.path.isdir(roots[p])]
    for p in missing:
        print(f"note: no {p} transcripts under {roots[p]}")
    wanted = [p for p in wanted if p not in missing]
    if not wanted:
        print("no transcripts to read")
        return 1

    calls: list[Call] = []
    for p in wanted:
        if p == "claude":
            root = roots["claude"]
            if not args.all and not args.root:
                root = claude_project_root(os.getcwd())
                if not os.path.isdir(root):
                    print(f"note: no claude transcripts for this project ({root})")
                    continue
            calls += parse_claude(root, args)
        else:
            calls += parse_codex(roots["codex"], args)
    cache_flush()

    if not calls:
        print("no usage records matched")
        return 0

    def cost_of(c: Call) -> float:
        return prices[c.provider].cost(c.model, c.inp, c.out, c.cw, c.cr)

    per_model: dict[tuple[str, str], list] = defaultdict(lambda: [0, 0, 0, 0, 0.0])
    per_day: dict[str, list] = defaultdict(lambda: [0.0, 0])
    per_session: dict[tuple[str, str], list] = defaultdict(lambda: [None, None, 0.0, ""])
    per_project: dict[str, float] = defaultdict(float)
    per_provider: dict[str, list] = defaultdict(lambda: [0.0, 0.0])   # total, subagents
    total = subagents = 0.0

    for c in calls:
        cost = cost_of(c)
        acc = per_model[(c.provider, c.model)]
        acc[0] += c.inp
        acc[1] += c.out
        acc[2] += c.cw
        acc[3] += c.cr
        acc[4] += cost

        total += cost
        per_provider[c.provider][0] += cost
        if c.is_subagent:
            subagents += cost
            per_provider[c.provider][1] += cost
        per_day[c.day][0] += cost
        per_day[c.day][1] += 1
        per_project[c.project] += cost

        s = per_session[(c.provider, c.session)]
        if s[0] is None or (c.ts and c.ts < s[0]):
            s[0] = c.ts
        if s[1] is None or (c.ts and c.ts > s[1]):
            s[1] = c.ts
        s[2] += cost
        if c.label and not s[3]:
            s[3] = c.label

    if total == 0.0:
        print("no usage records matched")
        return 0

    print(f"{'PROVIDER':<9}{'MODEL':<30}{'IN':>12}{'OUT':>12}{'CACHE W':>13}{'CACHE R':>13}{'COST':>10}")
    for (prov, model), (inp, out, cw, cr, cost) in sorted(per_model.items(), key=lambda kv: -kv[1][4]):
        print(f"{prov:<9}{model[:28]:<30}{inp:>12,}{out:>12,}{cw:>13,}{cr:>13,}{cost:>10.2f}")

    if len(per_provider) > 1:
        print(f"\n{'PROVIDER':<12}{'COST':>10}{'SUBAGENTS':>12}{'SHARE':>8}")
        for prov, (c, sub) in sorted(per_provider.items(), key=lambda kv: -kv[1][0]):
            print(f"{prov:<12}{c:>10.2f}{sub:>12.2f}{c / total:>7.0%}")

    if (args.all or "codex" in wanted) and len(per_project) > 1:
        print(f"\n{'PROJECT':<50}{'COST':>10}")
        for proj, c in sorted(per_project.items(), key=lambda kv: -kv[1])[:20]:
            name = str(proj)
            name = name if len(name) <= 48 else "…" + name[-47:]
            print(f"{name:<50}{c:>10.2f}")

    print(f"\n{'DAY':<14}{'CALLS':>8}{'COST':>10}")
    for day in sorted(per_day):
        c, n = per_day[day]
        print(f"{day:<14}{n:>8}{c:>10.2f}")

    print(f"\n{'SESSION':<38}{'FIRST':<22}{'COST':>10}  WHAT")
    for (prov, session), (first, _last, c, label) in sorted(
        per_session.items(), key=lambda kv: -kv[1][2]
    )[:30]:
        if c == 0.0:
            continue
        print(f"{session[:36]:<38}{(first or '')[:19]:<22}{c:>10.2f}  {prov}{' / ' + label if label else ''}")

    print(f"\nSUBAGENTS  ${subagents:,.2f} ({subagents / total:.0%} of total)")
    print(f"TOTAL  ${total:,.2f}")

    unverified = sorted({p for p in wanted if not prices[p].verified})
    if unverified:
        print(f"\nnote: the cost column is an ESTIMATE for {', '.join(unverified)} — "
              f"prices.json has rates_verified=false for it. The token columns are measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
