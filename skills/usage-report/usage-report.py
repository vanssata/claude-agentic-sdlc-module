#!/usr/bin/env python3
"""Claude Code usage report — tokens, cost, time. Works from any project.

Zero model cost: run this instead of asking a model to re-derive the parsing
logic from the transcripts. Answers "what did this session cost", "how much did
today cost", "which model burned the tokens".

Usage:
    usage-report.py              # current project (derived from cwd)
    usage-report.py --all        # every project on this machine
    usage-report.py --today      # current UTC day
    usage-report.py --session ab # session id prefix
    usage-report.py --root DIR   # explicit transcript dir
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
from collections import defaultdict

PROJECTS_ROOT = os.path.expanduser("~/.claude/projects")


def project_root_for(path: str) -> str:
    """Transcript dir for a project path, using Claude Code's mangling
    (every non-alphanumeric character -> '-')."""
    mangled = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))
    return os.path.join(PROJECTS_ROOT, mangled)


# $/MTok (input, output) as of 2026-07. Update when pricing changes.
PRICES = {
    "fable": (10.0, 50.0),
    "opus": (5.0, 25.0),
    "sonnet": (2.0, 10.0),
    "haiku": (1.0, 5.0),
}
CW_MULT = 2.0   # cache write ~2x input (1h TTL)
CR_MULT = 0.1   # cache read ~0.1x input


def family(model: str) -> str:
    m = (model or "").lower()
    for key in PRICES:
        if key in m:
            return key
    return "opus"


def cost_of(model: str, inp: int, out: int, cw: int, cr: int) -> float:
    pin, pout = PRICES[family(model)]
    return (
        inp * pin + cw * pin * CW_MULT + cr * pin * CR_MULT + out * pout
    ) / 1_000_000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", action="store_true", help="restrict to the current UTC day")
    ap.add_argument("--session", metavar="PREFIX", help="restrict to one session id prefix")
    ap.add_argument("--all", action="store_true", help="scan every project, not just the current one")
    ap.add_argument("--root", help="explicit transcript directory (overrides --all and cwd)")
    args = ap.parse_args()

    if args.root:
        root = args.root
    elif args.all:
        root = PROJECTS_ROOT
    else:
        root = project_root_for(os.getcwd())
        if not os.path.isdir(root):
            print(f"no transcripts for this project ({root}); use --all or --root")
            return 1

    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    if not files:
        print(f"no transcripts under {root}")
        return 1

    today = dt.datetime.now(dt.timezone.utc).date().isoformat()

    per_model: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    per_day: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    per_session: dict[str, list] = defaultdict(lambda: [None, None, 0.0])
    per_project: dict[str, float] = defaultdict(float)
    total = subagents = 0.0

    # One API response is written as several transcript lines — one per content
    # block (thinking, text, tool_use) — each repeating the same message id and
    # usage. Count each response once, keeping the line with the final (largest)
    # output_tokens, or every response is billed two or three times over.
    calls: dict[str, tuple] = {}
    for path in files:
        session = os.path.basename(path).removesuffix(".jsonl")
        if args.session and not session.startswith(args.session):
            continue
        project = os.path.relpath(path, PROJECTS_ROOT).split(os.sep)[0] \
            if path.startswith(PROJECTS_ROOT) else root
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

    for session, project, stamp, ts, model, usage in calls.values():
        inp = usage.get("input_tokens", 0) or 0
        out = usage.get("output_tokens", 0) or 0
        cw = usage.get("cache_creation_input_tokens", 0) or 0
        cr = usage.get("cache_read_input_tokens", 0) or 0

        acc = per_model[model]
        acc[0] += inp
        acc[1] += out
        acc[2] += cw
        acc[3] += cr

        c = cost_of(model, inp, out, cw, cr)
        total += c
        if session.startswith("agent-"):
            subagents += c
        per_day[stamp][0] += c
        per_day[stamp][1] += 1
        per_project[project] += c

        s = per_session[session]
        if s[0] is None or ts < s[0]:
            s[0] = ts
        if s[1] is None or ts > s[1]:
            s[1] = ts
        s[2] += c

    if total == 0.0:
        print("no usage records matched")
        return 0

    print(f"{'MODEL':<34}{'IN':>12}{'OUT':>12}{'CACHE W':>14}{'CACHE R':>14}{'COST':>10}")
    for model, (inp, out, cw, cr) in sorted(
        per_model.items(), key=lambda kv: -cost_of(kv[0], *kv[1])
    ):
        print(
            f"{model:<34}{inp:>12,}{out:>12,}{cw:>14,}{cr:>14,}"
            f"{cost_of(model, inp, out, cw, cr):>10.2f}"
        )

    if args.all and len(per_project) > 1:
        print(f"\n{'PROJECT':<50}{'COST':>10}")
        for proj, c in sorted(per_project.items(), key=lambda kv: -kv[1]):
            print(f"{proj[:48]:<50}{c:>10.2f}")

    print(f"\n{'DAY':<14}{'CALLS':>8}{'COST':>10}")
    for day in sorted(per_day):
        c, n = per_day[day]
        print(f"{day:<14}{n:>8}{c:>10.2f}")

    print(f"\n{'SESSION':<38}{'FIRST':<22}{'COST':>10}")
    for session, (first, _last, c) in sorted(per_session.items(), key=lambda kv: -kv[1][2]):
        if c == 0.0:
            continue
        print(f"{session[:36]:<38}{(first or '')[:19]:<22}{c:>10.2f}")

    print(f"\nSUBAGENTS  ${subagents:,.2f} ({subagents / total:.0%} of total)")
    print(f"TOTAL  ${total:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
