"""dialog_cmd: the consent and decision commands -- decision open/show/settle/fallback, the pick applied, and the read-only consent view.

core: SETTLE_EFFECT
shell: cmd_decision, decision_open, decision_settle, apply_choice, cmd_consent
"""
# pylint: disable=unused-argument  # uniform cli dispatch: cmd_consent takes rt like every command
import argparse
import json
import os
import sys

from rr_state import dialog, fs, labels, profile, questions_cmd, task
from rr_state import ledger as rr_ledger
from rr_state import runtime as rr_runtime

SETTLE_EFFECT = {"defer": "defer", "keep": "ack", "ack": "ack", "answer": "answered"}


def cmd_decision(args, root, rt=rr_runtime.Runtime()):
    """decision show|open|settle|fallback (R36.3, R36.14, R36.15)."""
    if args.action == "open":
        decision_open(args, root, rt=rt)
        return
    data = rr_ledger.read_decisions(root)
    if args.action == "show":
        # A session sees the decisions it opened (and those that name none):
        # the hooks' gate and Stop reminder hold only the opener to them.
        session = os.environ.get(dialog.SESSION_ENV.get(rr_runtime.own_runtime(runtime=rt.name), ""))
        chosen = [d for d in data["open"] if (not args.id or d["id"] == args.id) and (
            not session or (d.get("session") in (None, "", session) and d.get("runtime") in (None, "", rr_runtime.own_runtime(runtime=rt.name))))]
        if not chosen:
            fs.die("no open decision%s" % (" " + args.id if args.id else ""))
        if args.json:
            print(json.dumps(dialog.dialog_payload(chosen, rr_runtime.own_runtime(runtime=rt.name)), ensure_ascii=False))
        else:
            dialog.print_dialog(chosen, rt=rt)
        return
    decision = next((d for d in data["open"] if d["id"] == args.id), None)
    if decision is None:
        fs.die("no open decision %s (open: %s)" % (args.id or "(--id)",
                                                ", ".join(d["id"] for d in data["open"]) or "none"))
    if args.action == "fallback":
        if not args.why:
            fs.die("decision fallback needs --why \"<why the dialog cannot be used>\"")
        dialog.settle_decision(root, decision["id"], "fallback")
        print("%s falls back to the terminal (%s). The human runs, outside the agent:"
              % (decision["id"], fs.one_line(args.why, 200)))
        for option in decision["options"]:
            if option["kind"] == "command":
                print("  %s" % option["label"])
        return
    decision_settle(args, root, decision, rt=rt)


def decision_open(args, root, rt=rr_runtime.Runtime()):
    """The one opener the model may call: commit and push, nothing else."""
    if args.kind != "commit":
        fs.die("decision open takes --kind commit; every other decision is opened by the command that "
            "needs it (close, ask, the budgets, start --mode)")
    if not args.commands:
        fs.die("decision open --kind commit needs --command \"git commit …\" [--command \"git push <remote> <branch>\"]")
    for command in args.commands:
        why = labels.validate_label(command)
        if why or command.split()[:2] not in (["git", "commit"], ["git", "push"]):
            fs.die("CONSENT_LABEL_INVALID — %s: %s" % (why or "a commit decision offers git commit and git push only",
                                                     command[:120]), 6)
    if not dialog.dialog_on(root, runtime=rt.name):
        fs.die("the dialog is off here (.ai/policies/dialog.json, the runtime's dialog tool, a session id): "
            "suggest the commands; the human runs them outside the agent")
    state = task.load(root, required=False, claim=False, rt=rt)
    state = state if state and task.is_v7(state) else None
    head = dialog.task_facts(root, state) + "\n" if state else ""
    question = "%sbranch %s · %s\nRun these, in this order?\n%s" % (
        head, fs.run_text(root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "?",
        fs.run_text(root, ["git", "diff", "--shortstat", "HEAD"]) or "no uncommitted change",
        "\n".join("  %s" % c for c in args.commands))
    options = [{"kind": "choice", "effect": "defer", "label": "Not now — commit nothing"}] + \
        [{"kind": "command", "label": c} for c in args.commands]
    decision, why = dialog.open_decision(root, state, "commit", "Commit", question, options, "decision open",
                                  multi=len(args.commands) > 1, rt=rt)
    if decision is None:
        fs.die(why, 6)
    dialog.print_dialog([decision], rt=rt)


def decision_settle(args, root, decision, rt=rr_runtime.Runtime()):
    """(b) apply what the recorder wrote — a choice pick or a decline; (c) a
    human in a terminal picks an option by number (R36.14)."""
    if args.pick is not None:
        via, why = dialog.human_route(rt=rt)
        if via is None:
            fs.die("APPROVAL_REFUSED — 'decision settle --pick' is the human's, from their own terminal.\n"
                "Refused because %s." % why, 5)
        option = next((o for o in decision["options"] if o["n"] == args.pick), None)
        if option is None:
            fs.die("%s has no option %d" % (decision["id"], args.pick))
        if option["kind"] == "command":
            fs.die("option %d is a command: run it in this terminal instead —\n  %s" % (args.pick, option["label"]))
        apply_choice(root, decision, option, None, labels.human_name(root), via, rt=rt)
        return
    # The human's last answer decides: a decline after a pick wins, and only the
    # latest round's choice counts.
    ledger = rr_ledger.read_ledger(root)
    mine = [e for e in ledger if e.get("decision") == decision["id"] and e["type"] in ("pick", "decline")]
    choices = {o["n"]: o for o in decision["options"] if o["kind"] == "choice"}
    picked = [e for e in rr_ledger.latest_rounds(ledger).get(decision["id"], []) if e.get("option") in choices]
    if picked and mine[-1]["type"] == "pick":
        apply_choice(root, decision, choices[picked[-1]["option"]], picked[-1].get("id"), labels.human_name(root),
                     "dialog", rt=rt)
        return
    if mine and mine[-1]["type"] == "decline":
        dialog.settle_decision(root, decision["id"], "declined")
        print("%s settled: declined in the dialog (%s); nothing runs"
              % (decision["id"], mine[-1].get("why") or "no answer"))
        return
    live = [p for p in rr_ledger.live_picks(ledger, (dialog.dialog_on(root, runtime=rt.name) or {}).get("session"))
            if p.get("decision") == decision["id"]]
    if live:
        fs.die("%s has a live pick: run it verbatim —\n  %s" % (decision["id"], live[0].get("label")))
    fs.die("nothing is recorded for %s: send the dialog ('state.py decision show'), or "
        "'state.py decision fallback --id %s --why …'" % (decision["id"], decision["id"]))


def apply_choice(root, decision, option, pick_id, by, via, rt=rr_runtime.Runtime()):
    effect = SETTLE_EFFECT.get(option.get("effect"), "defer")
    drift = decision.get("drift") or {}
    if decision.get("kind") == "plan_drift" and effect == "ack" and drift.get("fingerprint"):
        profile.write_drift_ack(drift.get("runtime") or rr_runtime.own_runtime(runtime=rt.name), drift["fingerprint"], drift.get("kept"), via)
    if effect == "answered":
        questions_cmd.cmd_answer(argparse.Namespace(topic=None, prose=None, by=by, via=via,
                                      assignment=["%s=%s" % (decision.get("question_id"), option["answer"])]),
                   root, rt=rt)
    dialog.settle_decision(root, decision["id"], effect, pick_id)
    print("%s settled: %s (%s)" % (decision["id"], option["label"], effect))


def cmd_consent(args, root, rt=rr_runtime.Runtime()):
    """Read-only: the live picks and the ledger tail; `audit` checks each pick's
    tool_use_id against its transcript (R36.24)."""
    ledger = rr_ledger.read_ledger(root)
    if args.action == "audit":
        rows = [{"id": p.get("id"), "decision": p.get("decision"), "result": dialog.audit_pick(p)}
                for p in ledger if p["type"] == "pick"]
        if args.json:
            print(json.dumps(rows, ensure_ascii=False))
        else:
            for row in rows:
                print("%s %s %s" % (row["id"], row["decision"], row["result"]))
            print("%d picks: %s" % (len(rows), ", ".join("%d %s" % (sum(r["result"] == k for r in rows), k)
                                                       for k in ("ok", "mismatch", "unverifiable"))))
        if any(r["result"] == "mismatch" for r in rows):
            sys.exit(1)
        return
    switch = dialog.dialog_on(root, runtime=rt.name)
    live = rr_ledger.live_picks(ledger, (switch or {}).get("session"))
    if args.json:
        print(json.dumps({"dialog": bool(switch), "live": live, "tail": ledger[-10:]}, ensure_ascii=False))
        return
    print("dialog: %s · live picks: %d" % ("on" if switch else "off", len(live)))
    for pick in live:
        print("  %s %s until %s: %s" % (pick.get("id"), pick.get("decision"), pick.get("expires_at"),
                                        pick.get("label")))
    for entry in ledger[-10:]:
        print("  %s %s %s" % (entry.get("at"), entry["type"], entry.get("id") or entry.get("decision") or ""))
