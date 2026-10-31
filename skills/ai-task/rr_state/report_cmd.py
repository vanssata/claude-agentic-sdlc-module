"""report_cmd: the commands that report -- the plan profile (read, detect, ack, set), the journal event line, the handoff and the status.

shell: cmd_profile, cmd_profile_detect, cmd_profile_ack, cmd_profile_set, cmd_event, cmd_handoff, cmd_status
"""
# pylint: disable=unused-argument  # uniform cli dispatch: every cmd_* takes rt
import contextlib
import json
import os
import sys

from rr_state import dialog, fs, handoff, journal, profile, report, task
from rr_state import runtime as rr_runtime


def cmd_profile(args, _root, rt=rr_runtime.Runtime()):
    if args.action == "detect":
        cmd_profile_detect(args, fs.find_root_quiet(args.root), rt=rt)
        return
    if args.action == "set":
        cmd_profile_set(args, rt=rt)
        return
    if args.action == "ack":
        cmd_profile_ack(args, rt=rt)
        return
    if args.plan:
        fs.die("unrecognized argument %r: profile takes detect, set or ack" % args.plan, 2)
    if args.open or args.detect_runtime:
        fs.die("--open and --runtime after profile belong to profile detect")
    runtime = rr_runtime.other_runtime(rt=rt) if args.other else rr_runtime.own_runtime(runtime=rt.name)
    prof = profile.read_profile(runtime, rt=rt)
    if not prof:
        fs.die("no plan profile for %s (%s/riskrails/profile.json); npx riskrails writes it"
            % (runtime, rr_runtime.runtime_home(runtime)))
    if args.tier:
        model = ((prof.get("tiers") or {}).get(args.tier) or {}).get("model")
        if not model:
            fs.die("the %s profile has no %s tier" % (runtime, args.tier))
        print(model)
        return
    value = prof
    if args.field:
        for part in args.field.split("."):
            if not isinstance(value, dict) or part not in value:
                fs.die("the %s profile has no %s" % (runtime, args.field))
            value = value[part]
    if args.json or isinstance(value, (dict, list)):
        print(json.dumps(value, indent=None if args.field else 2, ensure_ascii=False))
    else:
        print(value)


def cmd_profile_detect(args, root, rt=rr_runtime.Runtime()):
    """Read-only, exit 0 always (R36.16); `--open` also opens the plan_drift decision (R36.18)."""
    if args.field or args.tier or args.other or args.plan:
        fs.die("--field, --tier, --other and a plan belong to the profile reader or profile set, not to profile detect")
    found = profile.profile_detect(args.detect_runtime or rr_runtime.own_runtime(runtime=rt.name), rt=rt)
    if args.open:
        try:
            found["decision"] = profile.open_drift(root, found, rt=rt)
        except SystemExit:               # decision.json unreadable: stay read-only, exit 0 (R36.16)
            found["decision"] = None
    if args.json:
        print(json.dumps(found, ensure_ascii=False))
        return
    have = (found["installed"] or {}).get("plan") or "none"
    live = found["live"]
    print("plan: installed %s · account %s%s → %s" % (
        have, live["plan"] or "unknown", " (%s)" % live["from"] if live["from"] else "", found["status"]))
    if found["command"]:
        print("fix: %s" % found["command"])
    if found["ack"]:
        print("keep: %s" % found["ack"])
    if found["decision"]:
        print("decision: %s" % found["decision"])


def cmd_profile_ack(args, rt=rr_runtime.Runtime()):
    """32ee: the terminal route to "Keep" — with the dialog off no plan_drift decision
    opens, so this is the only way to silence a drift the human chose to stay on. The
    same drift-ack.json the decision's Keep writes; any plan_drift decision still open
    is settled as stale by the next `detect --open`."""
    if args.open or args.field or args.tier or args.other or args.json or args.plan:
        fs.die("profile ack takes --runtime only")
    runtime = args.detect_runtime or rr_runtime.own_runtime(runtime=rt.name)
    via, why = dialog.human_route(None, rt=rt)
    if not via:
        fs.die("profile ack is the human's: %s" % why, 5)
    found = profile.profile_detect(runtime, rt=rt)
    status = found["status"]
    if status == "same":
        print("no drift: nothing to acknowledge")
        return
    if status == "acknowledged":
        print("already acknowledged; nothing written")
        return
    if status != "drift":
        fs.die("nothing to acknowledge: plan %s" % status)
    kept = found["installed"]["plan"]
    profile.write_drift_ack(runtime, found["live"]["fingerprint"], kept, via)
    print("drift-ack.json: keep %s for this %s account (%s); delete %s to be asked again"
          % (kept, runtime, found["live"]["plan"], profile.drift_ack_path(runtime)))


def cmd_profile_set(args, rt=rr_runtime.Runtime()):
    """R36.17: the human route only. A same-tier plan rewrites profile.json alone;
    one whose settings or tiers differ is the installer's (exit 6)."""
    if args.open or args.field or args.tier or args.other or args.json:
        fs.die("profile set takes a plan and --runtime only")
    runtime = args.detect_runtime or rr_runtime.own_runtime(runtime=rt.name)
    plans = profile.PLAN_PROFILES.get(runtime) or {}
    if args.plan not in plans:
        fs.die("profile set needs a %s plan: %s (got %r)" % (runtime, ", ".join(plans), args.plan or ""))
    via, why = dialog.human_route(fs.find_root_quiet(args.root), allow_dialog=True, rt=rt)
    if not via:
        fs.die("profile set is the human's: %s" % why, 5)
    prof = profile.read_profile(runtime, rt=rt)
    if not prof:
        fs.die("no plan profile for %s (%s/riskrails/profile.json); npx riskrails writes it"
            % (runtime, rr_runtime.runtime_home(runtime)))
    have = prof.get("plan")
    if have == args.plan:
        print("profile.json: already %s (%s); nothing written" % (have, runtime))
        return
    refusal = "PROFILE_NEEDS_INSTALLER — %s → %s also changes %s: %s" % (
        have, args.plan, "settings.json and the agents" if runtime == "claude" else "config.toml and the agents",
        profile.installer_command(runtime, args.plan, prof.get("plugin_version"), profile.context_mode(prof)))
    if have not in plans or not any({have, args.plan} <= pair for pair in profile.SAME_TIER[runtime]):
        fs.die(refusal, 6)
    resolver, src = profile.load_resolver(runtime)
    if resolver is None:
        fs.die("no resolve-profile.py under %s/riskrails/scripts or the plugin; npx riskrails installs it"
            % rr_runtime.runtime_home(runtime))
    fable = bool(prof.get("fable"))
    # Only an economy record passes context: a resolver installed before --context
    # has no such parameter, and only a later one writes an economy record.
    extra = {"context": "economy"} if profile.context_mode(prof) else {}
    try:
        old = resolver.resolve(src, plans[have][0], have, plans[have][1], fable, **extra)
        new = resolver.resolve(src, plans[args.plan][0], args.plan, plans[args.plan][1], fable, **extra)
    except (OSError, ValueError) as exc:
        fs.die("cannot resolve the %s profile: %s" % (args.plan, exc))
    key = resolver.KEY

    def rendered(data):
        return ({k: v for k, v in data.items() if k != key}, data[key].get("tiers"))
    if rendered(old) != rendered(new):
        fs.die(refusal, 6)
    out = dict(new[key], runtime=runtime, written_at=fs.now(), set_by={"via": via, "at": fs.now()})
    for kept in ("plugin_version", "dialog"):
        if kept in prof:
            out[kept] = prof[kept]
    target = os.path.join(rr_runtime.runtime_home(runtime), "riskrails", "profile.json")
    tmp = "%s.%d.tmp" % (target, os.getpid())
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, target)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        fs.die("cannot write %s: %s" % (target, exc))
    print("profile.json: %s → %s (%s); settings and agents unchanged; the managed block and routing.md "
          "keep the label '%s' until the next npx riskrails" % (have, args.plan, runtime, plans[have][1]))


def cmd_event(args, root, rt=rr_runtime.Runtime()):
    """For hooks and for WP5's model fallback: one journal line, no state write.
    The state file keeps its two writers; this command is not one of them."""
    if args.type not in journal.EVENT_TYPES:
        fs.die("unknown event type '%s' (have: %s)" % (args.type, ", ".join(journal.EVENT_TYPES)))
    if args.type in journal.FORGEABLE_EVENTS:
        # The journal is the compensating control for every route the gate
        # cannot block, so the actor it audits may not author its lines. These
        # types are emitted by the state transition that earns them, and by
        # nothing else: an agent that took the unattended route could otherwise
        # append a second, honest-looking gate_approved next to it.
        fs.die("'%s' is emitted by the state transition that earns it, not by 'event'. "
            "A journal the agent can write is not an audit trail." % args.type, 5)
    data = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except (ValueError, RecursionError) as exc:
            fs.die("--data must be a JSON object (%s)" % exc)
        if not isinstance(data, dict):
            fs.die("--data must be a JSON object")
    state = task.load(root, rt=rt)
    journal.append_journal(root, state["task_id"], journal.journal_line(
        state["task_id"], args.type, "agent" if args.type == "note" else "hook",
        state.get("current_stage"), args.detail, data, runtime=rt.name))
    print("%s recorded" % args.type)


def cmd_handoff(args, root, rt=rr_runtime.Runtime()):
    if args.to:
        handoff.handoff_to(args, root, rt=rt)
        return
    state = task.load(root, rt=rt)
    lines = handoff.write_handoff(root, state, args.reason, rt=rt)
    if lines is None:
        print("state.py: could not write %s" % os.path.relpath(fs.handoff_path(root), root),
              file=sys.stderr)
        # --print still answers from the render the caller asked for.
        lines = handoff.handoff_lines(root, state, args.reason, rt=rt)
    if args.print_it:
        for line in lines:
            print(line)
    else:
        print(os.path.relpath(fs.handoff_path(root), root))


def cmd_status(args, root, rt=rr_runtime.Runtime()):
    state = task.load(root, required=False, claim=False, rt=rt)
    if args.json:
        out = {"root": root, "task_id": (state or {}).get("task_id"), "schema": (state or {}).get("schema")}
        if task.is_v7(state):
            tree = fs.current_tree(root)
            facts = report.two_facts(root, state, tree)
            out.update({k: state.get(k) for k in ("goal", "workflow", "mode", "stage", "next_action",
                                                  "files", "tests", "steps", "verify", "review", "gate",
                                                  "mode_override", "findings")})
            out["weight"] = {k: (state.get("weight") or {}).get(k) for k in ("w", "axes", "hints", "unknown",
                                                                            "operations")}
            out["facts"] = {"a": list(facts["a"]), "b": list(facts["b"]), "tree": tree}
            out["questions_pending"] = len((state.get("questions") or {}).get("pending") or [])
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print("\n".join(report.status_lines(root, state)))
