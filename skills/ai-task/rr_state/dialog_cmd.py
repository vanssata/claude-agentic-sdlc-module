"""dialog_cmd: the consent and decision commands -- decision open/show/settle/fallback, the pick applied, and the read-only consent view.

core: SETTLE_EFFECT, SETUP_VALUES, SETUP_VALUE_MAX, SETUP_SPEC_MAX, setup_option_why, setup_decision_why, setup_spec_why
shell: cmd_decision, decision_open, read_setup_spec, setup_command_why, check_setup_labels, setup_open, decision_settle, apply_choice, cmd_consent
"""
# pylint: disable=unused-argument  # uniform cli dispatch: cmd_consent takes rt like every command
import argparse
import json
import os
import shlex
import sys

from rr_state import dialog, fs, labels, profile, questions_cmd, task
from rr_state import ledger as rr_ledger
from rr_state import runtime as rr_runtime

SETTLE_EFFECT = {"defer": "defer", "keep": "ack", "ack": "ack", "answer": "answered", "set": "set"}
# What `decision open --kind setup` accepts (R11): the questions /rr-setup asks, each with the words a choice may set
# (what the skill applies is what the human read: one of these words, or, for verify only, a command shown verbatim
# in its own label), the longest value, and the most characters of a spec it reads.
SETUP_VALUES = {"memory": ("off", "keep"), "runtime": ("auto", "claude", "codex", "both"),
                "survey": ("light", "full", "keep"), "verify": ("", "other", "keep", "edit")}
SETUP_VALUE_MAX = 200
SETUP_SPEC_MAX = 262144


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
    """The openers the model may call: --kind commit (git commit and git push) and --kind setup (the /rr-setup
    questions: choices that set a value, and this project's `memory enable`); nothing else."""
    if args.kind == "setup":
        setup_open(args, root, rt=rt)
        return
    if args.kind != "commit":
        fs.die("decision open takes --kind commit or --kind setup; every other decision is opened by the "
            "command that needs it (close, ask, the budgets, start --mode)")
    if args.spec is not None:
        fs.die("decision open --kind commit takes --command, not --spec", 2)
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


def read_setup_spec(path):
    """--spec FILE|- as JSON: a spec that cannot be read, is longer than SETUP_SPEC_MAX characters, is not JSON or
    nests deeper than the dialog's own cap is a bad spec (exit 2)."""
    try:
        if path == "-":
            text = sys.stdin.read(SETUP_SPEC_MAX + 1)
        else:
            with open(path, encoding="utf-8") as fh:
                text = fh.read(SETUP_SPEC_MAX + 1)
        if len(text) > SETUP_SPEC_MAX:
            fs.die("bad spec — more than %d characters" % SETUP_SPEC_MAX, 2)
        spec = dialog.json_loads_capped(text)
        # A lone surrogate ("\ud800") parses, yet no file can hold it: refused here, not after a first decision is written.
        json.dumps(spec, ensure_ascii=False).encode("utf-8")
        return spec
    except (OSError, ValueError, RecursionError) as exc:
        fs.die("bad spec — %s" % exc, 2)


def setup_option_why(option, key):
    """Why one option of the decision `key` is not {kind: choice, label, value[, description]} or {kind: command,
    label[, description]}, else None. A choice sets one of its key's words (SETUP_VALUES); a verify choice may also
    set a command, and check_setup_labels (exit 6) makes its label show it, like every rule of the labels."""
    if not isinstance(option, dict) or option.get("kind") not in ("choice", "command"):
        return "an option is an object whose kind is choice or command"
    need = {"kind", "label", "value"} if option["kind"] == "choice" else {"kind", "label"}
    if not need <= set(option) <= need | {"description"}:
        return "a %s option holds %s, and a description if it has one" % (option["kind"], ", ".join(sorted(need)))
    text, value = option.get("description", ""), option.get("value", "")
    if not isinstance(option["label"], str) or not isinstance(text, str) or len(text) > dialog.QUESTION_MAX:
        return "a label and a description are text, a description at most %d characters" % dialog.QUESTION_MAX
    if not isinstance(value, str) or len(value) > SETUP_VALUE_MAX or not value.isprintable():
        return "a choice value is at most %d printable characters (empty is allowed)" % SETUP_VALUE_MAX
    if option["kind"] == "choice" and key != "verify" and value not in SETUP_VALUES[key]:
        return "a %s choice sets one of: %s" % (key, ", ".join(SETUP_VALUES[key]))
    return None


def setup_decision_why(item):
    """Why one decision of a spec is not {key, header, question, options}, else None."""
    if not isinstance(item, dict) or set(item) != {"key", "header", "question", "options"}:
        return "a decision is an object holding exactly key, header, question and options"
    if not isinstance(item["key"], str) or item["key"] not in SETUP_VALUES:
        return "a decision key is one of %s" % ", ".join(SETUP_VALUES)
    if not all(isinstance(item[name], str) and item[name].strip() for name in ("header", "question")):
        return "a header and a question are text and not empty"
    if not isinstance(item["options"], list) or not 2 <= len(item["options"]) <= 4:
        return "a decision has 2 to 4 options"
    for number, option in enumerate(item["options"], 1):
        why = setup_option_why(option, item["key"])
        if why:
            return "option %d: %s" % (number, why)
    return None


def setup_spec_why(spec):
    """Why a parsed spec is not {"schema": 1, "decisions": [...]} with 1 to DECISIONS_MAX decisions, each key
    once, else None (R11)."""
    if not isinstance(spec, dict) or set(spec) != {"schema", "decisions"}:
        return "a spec is an object holding exactly schema and decisions"
    schema, decisions = spec["schema"], spec["decisions"]
    if not isinstance(schema, int) or isinstance(schema, bool) or schema != 1:
        return "schema is 1"
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= dialog.DECISIONS_MAX:
        return "decisions is a list of 1 to %d decisions" % dialog.DECISIONS_MAX
    for number, item in enumerate(decisions, 1):
        why = setup_decision_why(item)
        if why:
            return "decision %d: %s" % (number, why)
    keys = [item["key"] for item in decisions]
    return None if len(set(keys)) == len(keys) else "a decision key is used once"


def setup_command_why(root, label):
    """Why `label` is not exactly `python3 <this state.py> --root <this project> memory enable [options]`, else
    None. validate_label alone also passes another --root, a --runtime, interpreter flags, approve and git commit
    (R11, B1); the paths must be absolute, as the labels state_label writes."""
    why = labels.validate_label(label)
    if why:
        return why
    words = shlex.split(label)
    if len(words) >= 6 and words[0] == "python3" and words[2] == "--root" and words[4:6] == ["memory", "enable"] \
            and os.path.isabs(words[1]) and os.path.realpath(words[1]) == os.path.realpath(fs.ENTRY) \
            and os.path.isabs(words[3]) and os.path.realpath(words[3]) == os.path.realpath(root):
        return None
    return ("a setup command is exactly python3 <this state.py> --root <this project> memory enable "
            "[--author S] [--period P] [--index none|sqlite]")


def check_setup_labels(root, decisions):
    """Every label of the spec, before anything is written (exit 6): only the memory decision offers a command, and
    that is setup_command_why's; a choice never reads as a command, because the gate passes a Bash command equal
    to any pick and dialog_pick runs a pick that is a state.py label; and a verify choice that sets a command
    shows it, whole, as one `span` of its label, because the skill applies the value and the human reads the
    label (R11, B1)."""
    for item in decisions:
        options = item["options"]
        if len({option["label"] for option in options}) != len(options):
            fs.die("CONSENT_LABEL_INVALID — two options of the %s decision carry the same label" % item["key"], 6)
        for option in options:
            label = option["label"]
            if option["kind"] == "command":
                why = setup_command_why(root, label) if item["key"] == "memory" else \
                    "only the memory decision offers a command"
            elif not 0 < len(label) <= labels.LABEL_MAX or not label.isprintable():
                why = "a choice label is 1 to %d printable characters" % labels.LABEL_MAX
            elif label.startswith(("python3", "git", "npx")) or labels.label_argv(label) \
                    or labels.validate_label(label) is None:
                why = "a choice label never reads as a command"
            elif item["key"] == "verify" and option["value"] not in SETUP_VALUES["verify"] \
                    and option["value"] not in label.split("`")[1:-1:2]:
                why = "a verify command is shown verbatim in its label, inside backticks"
            else:
                why = None
            if why:
                fs.die("CONSENT_LABEL_INVALID — %s: %s" % (why, label[:120]), 6)


def setup_open(args, root, rt=rr_runtime.Runtime()):
    """decision open --kind setup --spec FILE|-: every check runs for every decision of the spec before the first
    write, then all are opened in the spec's order, or none (R11). The caller sends the one dialog."""
    if args.commands or args.spec is None:
        fs.die("decision open --kind setup takes --spec FILE|- and no --command", 2)
    spec = read_setup_spec(args.spec)
    why = setup_spec_why(spec)
    if why:
        fs.die("bad spec — %s" % why, 2)
    decisions = spec["decisions"]
    check_setup_labels(root, decisions)
    if not dialog.dialog_on(root, runtime=rt.name):
        fs.die("the dialog is off here (.ai/policies/dialog.json, the runtime's dialog tool, a session id): "
            "suggest the commands; the human runs them outside the agent")
    data = rr_ledger.read_decisions(root)
    questions = [item["question"].strip()[:dialog.QUESTION_MAX] for item in decisions]   # as open_decision stores them
    if len(set(questions)) != len(questions):
        fs.die("DECISION_DUPLICATE — two decisions of the spec carry one question text", 6)
    twin = next((d for d in data["open"] if d.get("question") in questions), None)
    if twin:
        fs.die("DECISION_DUPLICATE — %s is open with this very question; settle it, or 'state.py decision fallback "
            "--id %s --why …', before opening it again" % (twin.get("id"), twin.get("id")), 6)
    open_questions = sum(len(dialog.dialog_questions(d)) for d in data["open"])
    if open_questions + len(decisions) > dialog.DECISIONS_MAX:
        fs.die("DECISION_LIMIT — %d questions are open and the spec adds %d; one dialog call carries %d"
            % (open_questions, len(decisions), dialog.DECISIONS_MAX), 6)
    state = task.load(root, required=False, claim=False, rt=rt)
    state = state if state and task.is_v7(state) else None
    opened = []
    for item in decisions:
        options = [dict(o, effect="set") if o["kind"] == "choice" else o for o in item["options"]]
        decision, why = dialog.open_decision(root, state, "setup", item["header"], item["question"], options,
                                      "decision open --kind setup", rt=rt, setup_key=item["key"])
        if decision is None:
            for done in opened:               # a race since the checks above: none of this call stays open
                dialog.settle_decision(root, done["id"], "withdrawn")
            fs.die(why, 6)
        opened.append(decision)
    dialog.print_dialog(opened, rt=rt)


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
        if decision.get("kind") == "setup":
            print("SETUP_PICK %s=" % decision.get("setup_key"))
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
    if decision.get("kind") == "setup":
        print("SETUP_PICK %s=%s" % (decision.get("setup_key"), option.get("value", "")))


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
