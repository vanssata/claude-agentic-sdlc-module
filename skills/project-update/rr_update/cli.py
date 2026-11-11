"""Bring a project's RiskRails files up to date with the installed plugin.

shell: main
"""
# argparse's description is the first line of this docstring, which is the entry's first line.
import argparse
import os
import sys

import render_instructions  # next to the entry, whose directory the entry puts on sys.path
from rr_update import apply, build, gate, hints, history, kept, paths, report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--budget", action="store_true",
                    help="with --check: exit 1 when a root instruction file is over its byte budget")
    ap.add_argument("--confirm-delete", metavar="NAME",
                    help="a human confirms this run's gated rows (regenerate?, delete?), and is recorded in "
                         "the migration report; only with --apply")
    ap.add_argument("--confirm-cleanup", metavar="NAME",
                    help="a human confirms this run's [cleanup] deletions (run logs and stale task files, "
                         "git-ignored and not recoverable through git); only with --apply. "
                         "--confirm-delete does not settle them")
    args = ap.parse_args()
    confirm_via = cleanup_via = None
    for flag, name in (("--confirm-delete", args.confirm_delete), ("--confirm-cleanup", args.confirm_cleanup)):
        if name is None:
            continue
        if not args.apply:
            ap.error("%s only makes sense with --apply" % flag)
        if not name.strip():
            ap.error("%s needs the name of the human who confirmed the change" % flag)
        if gate.placeholder_name(name):
            ap.error("%s got the placeholder %r; type your own name, it is the audit trail"
                     % (flag, name.strip()))
        passed, via, why = gate.human_gate()
        if not passed:
            # Under an agent-session marker the AI_UNATTENDED route is the launcher's
            # to declare, not the agent's to type: the hint names it only otherwise.
            hint = "run the same command yourself in a terminal outside Claude Code or Codex"
            if "agent session" not in why:
                hint += ", or set AI_UNATTENDED=1 if a launcher runs it unattended on your behalf"
            return gate.refuse("%s is typed by a human, and %s" % (flag, why), hint)
        if flag == "--confirm-delete":
            confirm_via = via
        else:
            cleanup_via = via
    if args.budget and not args.check:
        ap.error("--budget only makes sense with --check")
    root = os.path.abspath(args.root)
    if args.check and args.budget:
        offenders = hints.budget_offenders(
            root, [paths.INSTRUCTION_FILE[rt][0] for rt in history.project_runtimes(root)],
            render_instructions.budgets(render_instructions.DEFAULT_SOURCE), render_instructions.block_of)
        for line in offenders:
            print(line)
        return 1 if offenders else 0
    for name, tpl in paths.TEMPLATES.items():
        if not os.path.isdir(tpl):
            print("project-update: %s templates not found at %s (run riskrails/install.sh)" % (name, tpl), file=sys.stderr)
            return 2
    if not (os.path.isdir(os.path.join(root, ".ai")) or os.path.isdir(os.path.join(root, "docs", "sdlc"))):
        print("project-update: %s has neither .ai/ nor docs/sdlc/ — run /rr-setup first" % root, file=sys.stderr)
        return 2
    try:
        if os.path.isdir(os.path.join(root, ".ai")):
            history.project_version(root)
        bad = kept.check_kept(root)
        if bad:
            return kept.kept_refusal(bad)
        plan = build.build_plan(root, confirm_delete=args.confirm_delete, confirm_via=confirm_via,
                          confirm_cleanup=args.confirm_cleanup, cleanup_via=cleanup_via)
    except history.SchemaError as exc:
        # --check is read by /rr-status, which reads stdout: it must see the reason.
        print("project-update: %s" % exc, file=sys.stdout if args.check else sys.stderr)
        return 2
    if args.check:
        pending = [i for i in plan.items if not i["action"].endswith("?")]
        waiting = [i for i in plan.items if i["action"].endswith("?") and not (i["reason"] or "").startswith("[cleanup]")]
        if pending:
            bits = ["%d file(s) to update" % len(pending)]
            if waiting:
                bits.append("%d change(s) a human must confirm" % len(waiting))
            print("project is behind the installed plugin: %s — run /rr-setup --update" % ", ".join(bits))
            return 1
        print("project matches the installed plugin"
              + (" (%d change(s) wait for --confirm-delete)" % len(waiting) if waiting else ""))
        return 0
    if args.apply:
        try:
            apply.apply(plan)
        except apply.Abort as exc:
            where = "%s %s" % (exc.item["action"], exc.item["target"]) if exc.item else "the update"
            print("project-update: aborted at %s: %s — nothing after it was written; "
                  "run the dry run again" % (where, exc.why), file=sys.stderr)
            return 3
    report.report(plan, args.apply)
    return 0
