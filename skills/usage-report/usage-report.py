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
import datetime as dt
import glob
import json
import os
import re
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


# ------------------------------------------------------------- Claude Code

def claude_project_root(path: str) -> str:
    """Transcript dir for a project path, using Claude Code's mangling
    (every non-alphanumeric character -> '-')."""
    mangled = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))
    return os.path.join(CLAUDE_ROOT, mangled)


def parse_claude(root: str, args) -> list[Call]:
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    # One API response is written as several transcript lines — one per content
    # block (thinking, text, tool_use) — each repeating the same message id and
    # usage. Count each response once, keeping the line with the final (largest)
    # output_tokens, or every response is billed two or three times over.
    calls: dict[str, tuple] = {}
    for path in files:
        session = os.path.basename(path).removesuffix(".jsonl")
        if args.session and not session.startswith(args.session):
            continue
        project = (os.path.relpath(path, CLAUDE_ROOT).split(os.sep)[0]
                   if path.startswith(CLAUDE_ROOT) else root)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage") or {}
                if not usage:
                    continue
                stamp = (rec.get("timestamp") or "")[:10]
                if args.today and stamp != today:
                    continue
                key = msg.get("id") or rec.get("requestId") or f"{path}:{n}"
                out = usage.get("output_tokens", 0) or 0
                prev = calls.get(key)
                if prev is None or out > (prev[5].get("output_tokens", 0) or 0):
                    calls[key] = (session, project, stamp, rec.get("timestamp") or "",
                                  msg.get("model") or "unknown", usage)

    out_calls = []
    for session, project, stamp, ts, model, usage in calls.values():
        out_calls.append(Call(
            "claude", session, project, stamp, ts, model,
            usage.get("input_tokens", 0) or 0,
            usage.get("output_tokens", 0) or 0,
            usage.get("cache_creation_input_tokens", 0) or 0,
            usage.get("cache_read_input_tokens", 0) or 0,
            is_subagent=session.startswith("agent-"),
        ))
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


def parse_codex(root: str, args) -> list[Call]:
    """Codex writes one rollout file per thread, and a subagent gets its own file.

    Unlike Claude Code there is no per-content-block repetition: each response is
    one `token_usage_record` whose `usage` is that response alone (`turn_token_usage`
    and `thread_token_usage` in the same record are running totals — summing those
    would count every earlier response again). `response_id` is still used as the
    dedup key, because a resumed thread can replay records into a second file.

    The model is not on the usage record. It is on the `turn_context` record for
    the same `turn_id`, which is written before the turn runs; the last one seen
    is the fallback for a usage record whose turn was not announced in this file.
    """
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    cwd = os.path.abspath(os.getcwd())

    seen: dict[str, Call] = {}
    for path in files:
        turn_model: dict[str, tuple[str, str]] = {}
        last_model = ("unknown", "")
        meta_cwd = ""
        thread_id = os.path.basename(path).removesuffix(".jsonl")
        sub_name = ""
        is_sub = False
        pending: list[tuple] = []

        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = rec.get("type")
                payload = rec.get("payload") or {}

                if kind == "session_meta":
                    meta_cwd = payload.get("cwd") or ""
                    thread_id = payload.get("id") or thread_id
                    sub_name = _subagent_name(payload.get("source"))
                    # A spawned thread carries its parent's session_id; a
                    # top-level thread's session_id is its own id.
                    is_sub = bool(sub_name) or (
                        bool(payload.get("session_id"))
                        and payload.get("session_id") != thread_id
                    )
                elif kind == "turn_context":
                    model = payload.get("model") or "unknown"
                    effort = payload.get("effort") or ""
                    if payload.get("turn_id"):
                        turn_model[payload["turn_id"]] = (model, effort)
                    last_model = (model, effort)
                    meta_cwd = payload.get("cwd") or meta_cwd
                elif kind == "token_usage_record":
                    usage = payload.get("usage") or {}
                    if not usage:
                        continue
                    pending.append((
                        payload.get("response_id") or f"{path}:{len(pending)}",
                        payload.get("turn_id") or "",
                        (rec.get("timestamp") or "")[:10],
                        rec.get("timestamp") or "",
                        usage,
                    ))

        if args.session and not thread_id.startswith(args.session):
            continue
        project = meta_cwd or root
        if not args.all and not args.root and os.path.abspath(project) != cwd:
            continue

        for rid, turn, stamp, ts, usage in pending:
            if args.today and stamp != today:
                continue
            if rid in seen:
                continue
            model, effort = turn_model.get(turn, last_model)
            total_in = usage.get("input_tokens", 0) or 0
            cached = usage.get("cached_input_tokens", 0) or 0
            seen[rid] = Call(
                "codex", thread_id, project, stamp, ts,
                model + (f" ({effort})" if effort else ""),
                # input_tokens is the whole prompt including the cached part;
                # billing the cached tokens at the full rate as well would
                # double-count them.
                max(total_in - cached, 0),
                usage.get("output_tokens", 0) or 0,
                usage.get("cache_write_input_tokens", 0) or 0,
                cached,
                is_subagent=is_sub,
                label=sub_name,
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
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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
    ap.add_argument("--budgets", action="store_true", help="print the installed plans' budget tables")
    args = ap.parse_args()

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
