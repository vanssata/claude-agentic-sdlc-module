"""cli: the argument parser and the dispatch -- the one place that resolves the runtime and builds the Runtime every command receives.

shell: BLOCKING_COMMANDS, MUTATING_COMMANDS, DIALOG_SYNC_COMMANDS, memory_parsers, main
"""
import argparse
import os

from rr_state import close, dialog, dialog_cmd, fs, gate, gate_cmd, memory_cmd, policy, questions_cmd
from rr_state import report_cmd, review, start, steps, task, verify
from rr_state import runtime as rr_runtime

# A pending question stops a stage from moving; it never stops a command that
# records, reads or answers (R3). close --abandon is exempt: abandoning a task is
# how an unanswerable question is closed.
BLOCKING_COMMANDS = {"step-done", "approve", "close", "verify"}

# The commands that change the task. Only these take ownership of it: reading a
# task from the other runtime, or writing a note about it, is not a handoff.
MUTATING_COMMANDS = {"step-done", "ask", "answer", "close", "start", "verify", "review", "batch"}
# What prunes decision.json and mirrors consent.jsonl first (R36.14, R36.24):
# every command that changes something; status and consent stay read-only.
DIALOG_SYNC_COMMANDS = MUTATING_COMMANDS | {"approve", "reject", "decision"}


def memory_parsers(sub):
    p = sub.add_parser("recall", help="what the record holds about these files, within a token budget")
    p.add_argument("--files", default=""); p.add_argument("--budget", type=int)
    p.add_argument("--kinds", default=""); p.add_argument("--all-risks", dest="all_risks", action="store_true")
    p.add_argument("--offset", type=int, default=0); p.add_argument("--json", action="store_true")
    p.set_defaults(func=memory_cmd.cmd_recall)
    p = sub.add_parser("memory", help="the compact project record (docs/local-memory.md)")
    p.set_defaults(func=memory_cmd.cmd_memory)
    msub = p.add_subparsers(dest="memory_action", required=True)
    m = msub.add_parser("status"); m.add_argument("--json", action="store_true")
    m = msub.add_parser("enable"); m.add_argument("--author"); m.add_argument("--period", choices=["month", "quarter", "year"])
    m.add_argument("--index", choices=["none", "sqlite"])
    msub.add_parser("disable")
    m = msub.add_parser("export"); m.add_argument("ids", nargs="*"); m.add_argument("--pending", action="store_true")
    m = msub.add_parser("verify"); m.add_argument("ids", nargs="*"); m.add_argument("--all", action="store_true")
    m.add_argument("--range"); m.add_argument("--fresh-clone", dest="fresh_clone", action="store_true")
    m.add_argument("--json", action="store_true")
    m = msub.add_parser("show"); m.add_argument("id"); m.add_argument("--md", action="store_true")
    m.add_argument("--json", action="store_true"); m.add_argument("--entry")
    m = msub.add_parser("search"); m.add_argument("query", nargs="?", default="")
    for flag in ("--kind", "--by", "--file", "--task", "--since", "--until"):
        m.add_argument(flag)
    m.add_argument("--limit", type=int, default=20); m.add_argument("--offset", type=int, default=0)
    m.add_argument("--json", action="store_true")
    m = msub.add_parser("risk"); rsub = m.add_subparsers(dest="risk_action", required=True)
    r = rsub.add_parser("add"); r.add_argument("--title", required=True); r.add_argument("--where", default="")
    r.add_argument("--label", required=True); r.add_argument("--what", required=True)
    r.add_argument("--likely"); r.add_argument("--fix"); r.add_argument("--status", default="open")
    r = rsub.add_parser("close"); r.add_argument("rkey"); r.add_argument("--status", required=True)
    r.add_argument("--why", required=True)
    m = msub.add_parser("risks"); m.add_argument("--status", choices=["open", "ticketed", "accepted", "fixed", "all"],
                                                 default="open")
    m.add_argument("--md", action="store_true"); m.add_argument("--json", action="store_true")
    m = msub.add_parser("migrate"); g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true"); g.add_argument("--apply", action="store_true")
    g.add_argument("--move-logs", dest="move_logs", action="store_true")
    m.add_argument("--risks", action="store_true"); m.add_argument("--confirm-delete", dest="confirm_delete")
    msub.add_parser("rebuild")
    m = msub.add_parser("cleanup"); m.add_argument("ids", nargs="*"); m.add_argument("--all", action="store_true")
    m.add_argument("--confirm-delete", dest="confirm_delete")
    m = msub.add_parser("restore"); m.add_argument("ids", nargs="*"); m.add_argument("--all", action="store_true")
    m = msub.add_parser("pack"); m.add_argument("--period", required=True)
    m.add_argument("--confirm-delete", dest="confirm_delete")
    m = msub.add_parser("redact"); m.add_argument("rid"); m.add_argument("--field", required=True)
    m.add_argument("--why", required=True)


def main():
    # description: the first line of state.py's docstring, which argparse printed as __doc__ before the split
    parser = argparse.ArgumentParser(
        description="Task state for /ai-task — the small, machine-readable record of one task.")
    parser.add_argument("--root", default=".", help="project directory (default: search upwards for .ai/)")
    parser.add_argument("--runtime", choices=rr_runtime.RUNTIMES,
                        help="overrides AI_RUNTIME and detection for this call")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("step-done"); p.add_argument("step_id")
    p.add_argument("--force", action="store_true",
                   help="accepted for older callers; it forces nothing")
    p.set_defaults(func=steps.cmd_step_done_v7)

    who = os.environ.get("USER") or "unknown"
    p = sub.add_parser("ask"); p.add_argument("question", nargs="?")
    p.add_argument("--option", action="append", default=[]); p.add_argument("--recommend")
    p.add_argument("--context", default=""); p.add_argument("--gate")
    p.add_argument("--batch"); p.add_argument("--topic"); p.add_argument("--by", default="")
    p.set_defaults(func=questions_cmd.cmd_ask)

    p = sub.add_parser("answer"); p.add_argument("assignment", nargs="*")
    p.add_argument("--prose"); p.add_argument("--by", default=who)
    # `file` is not offered: it is what --sync writes, and it is the one route
    # that is recorded as a human's.
    p.add_argument("--via", choices=["picker", "prose"], default="prose")
    p.add_argument("--topic"); p.set_defaults(func=questions_cmd.cmd_answer)

    p = sub.add_parser("questions"); p.add_argument("--pending", action="store_true")
    p.add_argument("--sync", action="store_true"); p.add_argument("--topic")
    p.add_argument("--by", default=who)
    p.add_argument("--format", choices=["md", "prose", "json"], default="prose")
    p.set_defaults(func=questions_cmd.cmd_questions)

    p = sub.add_parser("handoff")
    p.add_argument("--print", dest="print_it", action="store_true")
    p.add_argument("--reason", choices=["stage", "precompact", "manual", "session-start"],
                   default="manual")
    p.add_argument("--to", choices=rr_runtime.RUNTIMES)
    p.add_argument("--for", dest="for_", choices=["continue", "review"], default="continue")
    p.add_argument("--why", default="")
    p.set_defaults(func=report_cmd.cmd_handoff)

    p = sub.add_parser("profile"); p.add_argument("action", nargs="?", choices=["detect", "set", "ack"])
    p.add_argument("plan", nargs="?")
    p.add_argument("--field")
    p.add_argument("--runtime", dest="detect_runtime", choices=rr_runtime.RUNTIMES)
    p.add_argument("--open", action="store_true")
    p.add_argument("--tier", choices=["FAST", "BALANCED", "STRONG", "EXPERT"])
    p.add_argument("--other", action="store_true"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=report_cmd.cmd_profile)

    p = sub.add_parser("weight"); p.add_argument("--files", default="")
    p.add_argument("--goal", default=""); p.add_argument("--declare", action="append", default=[])
    out = p.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true"); out.add_argument("--long", action="store_true")
    out.add_argument("--mirror", action="store_true"); p.set_defaults(func=start.cmd_weight)

    p = sub.add_parser("event"); p.add_argument("type"); p.add_argument("--detail", default="")
    p.add_argument("--data"); p.set_defaults(func=report_cmd.cmd_event)

    p = sub.add_parser("approve"); p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--confirm", default="", help="the operation a full_irreversible task performs")
    p.set_defaults(func=gate_cmd.cmd_approve_v7)

    p = sub.add_parser("reject"); p.add_argument("--by", required=True)
    p.add_argument("--why", required=True); p.set_defaults(func=gate_cmd.cmd_reject)

    p = sub.add_parser("close")
    p.add_argument("--abandon", action="store_true", help="archive without the checks")
    p.set_defaults(func=close.cmd_close_v7)

    p = sub.add_parser("start"); p.add_argument("--goal", default="")
    p.add_argument("--workflow", default=""); p.add_argument("--files", default="")
    p.add_argument("--tests", default=""); p.add_argument("--declare", action="append", default=[])
    p.add_argument("--mode"); p.add_argument("--by", default=""); p.add_argument("--why", default="")
    p.add_argument("--steps", default=""); p.add_argument("--plan-file", dest="plan_file")
    p.add_argument("--task-id", help="an id of your own; a legacy T-YYYY-MM-DD-NNN id is still accepted")
    p.add_argument("--slug", help="3-24 characters of [a-z0-9] words joined by '-': the id becomes "
                                  "T-YYYY-MM-DD-HHMM-<slug> (UTC). Default: derived from --goal")
    p.add_argument("--amend", action="store_true")
    p.add_argument("--batch", action="store_true", help="the batch loop of /rr-build-all (needs --by)")
    p.add_argument("--no-batch", dest="no_batch", action="store_true", help="opt out of weight.json batch.default")
    p.set_defaults(func=start.cmd_start)

    p = sub.add_parser("steps"); p.add_argument("--ready", action="store_true")
    p.add_argument("--json", action="store_true"); p.set_defaults(func=steps.cmd_steps)

    p = sub.add_parser("batch"); p.add_argument("action", choices=["on", "off"])
    p.add_argument("--by", default=""); p.add_argument("--why", default="")
    p.set_defaults(func=steps.cmd_batch)

    p = sub.add_parser("verify")
    p.add_argument("--scope", required=True, choices=["step", "suite", "e2e", "all"])
    p.add_argument("--files", default=""); p.add_argument("--expect", choices=["fail"])
    p.add_argument("--e2e", nargs=2, metavar=("not-applicable", "WHY"))
    p.add_argument("--after-fix", dest="after_fix", default="")
    p.add_argument("--by", default=""); p.set_defaults(func=verify.cmd_verify)

    p = sub.add_parser("review"); p.add_argument("--verdict", choices=sorted(policy.VERDICT_STATUS))
    p.add_argument("--tier", choices=review.REVIEW_TIERS); p.add_argument("--focus", choices=["security"])
    p.add_argument("--report", default=""); p.add_argument("--closes", default="")
    p.add_argument("--by", default=""); p.set_defaults(func=review.cmd_review)

    p = sub.add_parser("status"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=report_cmd.cmd_status)

    p = sub.add_parser("decision"); p.add_argument("action", choices=["show", "open", "settle", "fallback"])
    p.add_argument("--id"); p.add_argument("--kind"); p.add_argument("--command", dest="commands", action="append", default=[])
    p.add_argument("--pick", type=int); p.add_argument("--why", default="")
    p.add_argument("--json", action="store_true"); p.set_defaults(func=dialog_cmd.cmd_decision)

    p = sub.add_parser("consent"); p.add_argument("action", nargs="?", choices=["audit"])
    p.add_argument("--json", action="store_true"); p.set_defaults(func=dialog_cmd.cmd_consent)

    memory_parsers(sub)

    args = parser.parse_args()
    if getattr(args, "topic", None):
        # Topic mode never touches .ai/: it must work where there is none (I11).
        args.func(args, fs.find_docs_root(args.root), rt=rr_runtime.Runtime())
        return
    if args.command == "profile":
        # Read-only and task-free: it answers where there is no .ai/ at all.
        name = args.runtime or os.environ.get("AI_RUNTIME") or \
            ("claude" if os.environ.get("CLAUDECODE") else "unknown")
        args.func(args, None, rt=rr_runtime.Runtime(name=name))
        return
    root = fs.find_root(args.root)
    rt = rr_runtime.Runtime(name=rr_runtime.detect_runtime(args.runtime, root),
                            mutating=args.command in MUTATING_COMMANDS)
    task.route_surface(root, args, rt=rt)
    if args.command in BLOCKING_COMMANDS and not getattr(args, "abandon", False):
        gate.guard_pending(root, args.command, rt=rt)
    # After the guard: an exit-4 refusal leaves every file as it was.
    if args.command in DIALOG_SYNC_COMMANDS:
        dialog.sync_dialog(root, rt=rt)
    args.func(args, root, rt=rt)
