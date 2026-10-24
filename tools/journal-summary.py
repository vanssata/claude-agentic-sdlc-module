#!/usr/bin/env python3
"""Read-only summary of .ai/reports/<task>/ journals and state snapshots.

usage: tools/journal-summary.py <project-root> [--timeline TASK ...]

Read-only: prints report directories, the state snapshot fields and the journal
event counts per task; with --timeline, the dated stage transitions of the named
tasks. Used for docs/redesign-analysis-2026-10-24.md.
"""
import collections
import datetime
import glob
import json
import os
import sys


def parse_ts(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_events(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    root = sys.argv[1]
    timeline = sys.argv[3:] if len(sys.argv) > 3 and sys.argv[2] == "--timeline" else []
    reports = sorted(glob.glob(os.path.join(root, ".ai", "reports", "T-*")))
    print("report dirs:", len(reports))
    for report in reports:
        files = sorted(os.listdir(report))
        print("==", os.path.basename(report), " ".join(files))
        snapshot = os.path.join(report, "state.json")
        if os.path.exists(snapshot):
            with open(snapshot, encoding="utf-8") as handle:
                state = json.load(handle)
            plan = state.get("approved_plan") or {}
            print("   tier=%s workflow=%s stage=%s created=%s updated=%s steps=%d review=%s test=%s e2e=%s security=%s"
                  % (state.get("risk_tier"), state.get("workflow"), state.get("current_stage"),
                     (state.get("created_at") or "")[:16], (state.get("updated_at") or "")[:16],
                     len(plan.get("steps") or []), state.get("review_status"), state.get("test_status"),
                     state.get("e2e_status"), state.get("security_status")))
            print("   goal:", (state.get("goal") or "")[:160])
        journal = os.path.join(report, "events.jsonl")
        if os.path.exists(journal):
            events = load_events(journal)
            stamps = [e["ts"] for e in events if e.get("ts")]
            minutes = round((parse_ts(stamps[-1]) - parse_ts(stamps[0])).total_seconds() / 60) if len(stamps) > 1 else 0
            tiers = [e.get("data", {}).get("tier") for e in events if e.get("event") == "tier_set"]
            print("   journal: %d events, %d min, tiers %s" % (len(events), minutes, tiers))
            print("   ", dict(collections.Counter(e.get("event") for e in events)))
            if os.path.basename(report) in timeline:
                prev = None
                for e in events:
                    if e.get("event") in ("handoff_written", "note"):
                        continue
                    stamp = parse_ts(e["ts"])
                    delta = "" if prev is None else "+%dm" % ((stamp - prev).total_seconds() / 60)
                    print("      %-6s %-16s %s" % (delta, e.get("event"), (e.get("detail") or "")[:110]))
                    prev = stamp


if __name__ == "__main__":
    main()
