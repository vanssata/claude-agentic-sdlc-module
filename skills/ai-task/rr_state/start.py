"""start: the `weight` and `start` commands -- the six axes and a mode from weight.json, and the task started under them with the scope guard armed.

shell: cmd_weight, parse_declares, cmd_start, start_amend
core: WORKFLOWS, arm_scope
"""
# pylint: disable=protected-access  # cmd_weight, cmd_start and start_amend call fs._split_files, which partition.json assigns to fs
# pylint: disable=unused-argument  # cmd_weight takes the same arguments as every command, rt included (uniform cli dispatch)
import contextlib
import json
import os
import re
import shlex
import sys

from rr_state import fs, journal, task, dialog, report, profile, handoff
from rr_state import policy as rr_policy
from rr_state import runtime as rr_runtime

# sensors.py and weight.py sit beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None
try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None

WORKFLOWS = ["feature", "bugfix", "refactoring", "hotfix", "investigation"]


def cmd_weight(args, root, rt=rr_runtime.Runtime()):
    """Six axes and a mode from weight.json. Read-only, and it needs no task:
    the weight is what decides how a task is run, so it comes before one."""
    if weight is None:
        fs.die("weight.py is missing beside state.py: reinstall the plugin")
    try:
        policy, path = weight.load_policy(root)
    except (OSError, ValueError) as exc:
        fs.die("cannot read the weight table: %s" % exc)
    if args.mirror:
        own = os.path.join(root, ".ai", "policies", "weight.json")
        if path != own:
            fs.die("%s has no .ai/policies/weight.json: the mirror is written beside the project's own table"
                % root)
        target = os.path.join(os.path.dirname(own), "weight.md")
        tmp = "%s.%d.tmp" % (target, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(weight.mirror(own))
            os.replace(tmp, target)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            fs.die("cannot write %s: %s" % (target, exc))
        print(target)
        return
    files = fs._split_files(args.files)
    if not files:
        fs.die("weight needs --files: the declared files are what it measures")
    declared = {}
    for item in args.declare:
        m = re.match(r"^(\w+)=(\d{1,3}):(.*\S.*)$", item, re.S)
        if not m:
            fs.die("--declare %r: write axis=n:\"evidence\" — a declaration without its evidence is not one"
                % item)
        declared[m.group(1)] = (int(m.group(2)), m.group(3).strip())
    try:
        result = rr_policy.weigh(root, files, declared, args.goal, policy)
    except ValueError as exc:
        fs.die(str(exc))
    except (TypeError, AttributeError) as exc:     # a table whose values have the wrong shape
        fs.die("%s is malformed: %s" % (path, exc))
    if args.json:
        out = dict(result.as_dict(), policy=path)
        if result.documents_only is not None:
            out["documents_only"] = result.documents_only
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(weight.render(result, long=args.long))


def arm_scope(state):
    """The legacy view the scope guard (hooks/guard/scope.py) reads (D2): stage implementation and one
    step holding every file of the task, for as long as the task is open."""
    state["current_stage"] = "implementation"
    state["approved_plan"] = {"ref": "inline", "current_step_id": "task", "steps": [{
        "step_id": "task", "description": state.get("goal"), "allowed_files": task.task_files(state),
        "forbidden_files": [], "forbidden_reason": "not part of this task",
        "required_tests": list(state.get("tests") or []), "status": "in_progress"}]}


def parse_declares(items):
    declared = {}
    for item in items or []:
        m = re.match(r"^(\w+)=(\d{1,3}):(.*\S.*)$", item, re.S)
        if not m:
            fs.die("--declare %r: write axis=n:\"evidence\" — a declaration without its evidence is not one"
                % item)
        declared[m.group(1)] = (int(m.group(2)), m.group(3).strip())
    return declared


def cmd_start(args, root, rt=rr_runtime.Runtime()):
    """The task, its weight and its mode in one call; the scope guard is armed."""
    if args.amend:
        start_amend(args, root, rt=rt)
        return
    missing = [flag for flag, value in (("--goal", args.goal), ("--workflow", args.workflow),
                                        ("--files", args.files)) if not value]
    if missing:
        fs.die("start needs %s (or --amend to widen the task in flight)" % ", ".join(missing))
    if args.workflow not in WORKFLOWS:
        fs.die("workflow must be one of: %s" % ", ".join(WORKFLOWS))
    existing = task.load(root, required=False, claim=False, rt=rt)
    if existing and existing.get("current_stage") != "done":
        fs.die("task %s is in flight: finish it with 'state.py close' (or 'close --abandon'), or widen it "
            "with 'state.py start --amend --files \"+a\" --why \"…\"'" % existing.get("task_id"))
    files, tests = fs._split_files(args.files), fs._split_files(args.tests)
    if not files:
        # An empty list would arm a scope guard that allows everything.
        fs.die("--files must name at least one file or glob the task may touch")
    if fs.current_tree(root) is None:
        fs.die("start needs a git repository: the two facts close decides by are measured on its tree")
    steps = task.parse_steps(args.steps, args.plan_file)
    policy = rr_policy.weight_policy(root)
    table = rr_policy.batch_policy(policy, strict=True)      # a malformed section is refused here, not at status
    if args.batch and args.no_batch:
        fs.die("--batch and --no-batch exclude each other")
    if args.batch and not args.by:
        fs.die("--batch needs --by \"<who asked for the batch loop>\": it is journaled with its author")
    batch = {"on": False, "by": None, "why": None, "since": None}
    if args.batch:
        batch = {"on": True, "by": args.by, "why": args.why or None, "since": fs.now()}
    elif not args.no_batch and table["default"]:
        batch = {"on": True, "by": "weight.json batch.default", "why": None, "since": fs.now()}
    # Shared files order steps only in a batch task, where steps run side by
    # side; a standard task's steps run one after another, as before.
    implied = task.order_shared_files(steps) if batch["on"] else []
    task.check_steps(steps, implied)
    concrete = [f for f in files if not any(c in f for c in "*?[")]
    try:
        result = rr_policy.weigh(root, concrete, parse_declares(args.declare), args.goal, policy,
                       [f for f in files if f not in concrete])
    except ValueError as exc:
        fs.die(str(exc))
    except (TypeError, AttributeError) as exc:
        fs.die("the weight table is malformed: %s" % exc)
    mode, override = result.mode, None
    if args.mode:
        if args.mode not in rr_policy.MODES:
            fs.die("--mode takes one of: %s" % ", ".join(rr_policy.MODES))
        if not args.by:
            fs.die("--mode needs --by \"<who>\": an override is journaled with its author")
        if args.mode == mode:
            args.mode = None              # the weight already says so: nothing to override
    via = None
    if args.mode:
        if rr_policy.MODES.index(args.mode) < rr_policy.MODES.index(mode):
            via, why = dialog.human_route(root, allow_dialog=True, rt=rt)
            if via is None:
                dialog.offer_decision(root, None, "human_set", "Mode",
                               "%s — W %s, the weight says %s.\nLower the mode from %s to %s (by %s)?"
                               % (fs.one_line(args.goal, 300), result.w, mode, mode, args.mode, args.by),
                               [{"kind": "choice", "effect": "keep", "label": "Keep mode %s" % mode},
                                {"kind": "command", "label": dialog.state_label(root, sys.argv[1:])}], "start --mode", rt=rt)
                fs.die("APPROVAL_REFUSED — lowering the mode from %s to %s is a human's decision. Run it in "
                    "your own terminal:\n  python3 %s --root %s start … --mode %s --by %s\nRefused because %s."
                    % (mode, args.mode, shlex.quote(fs.ENTRY), shlex.quote(root),
                       args.mode, shlex.quote(args.by), why), 5)
        override = {"from": mode, "to": args.mode, "by": args.by, "why": args.why, "ts": fs.now()}
        mode = args.mode
    if args.slug is not None:
        import memory_format              # pylint: disable=import-outside-toplevel
        if args.task_id:
            fs.die("--slug and --task-id both name the id: pass one", 2)
        if not memory_format.SLUG_RE.match(args.slug):
            fs.die("--slug takes 3-24 characters of [a-z0-9] words joined by '-', not %r" % args.slug, 2)
    task_id = task.valid_task_id(args.task_id) if args.task_id else task.next_task_id(root, args.goal, args.slug)
    base_tree = fs.current_tree(root)
    state = {
        "schema": task.SCHEMA, "task_id": task_id, "goal": args.goal, "workflow": args.workflow,
        "mode": mode, "weight": dict(result.as_dict(), lines=weight.render(result).split("\n"),
                                     tree=base_tree, computed_at=fs.now(), rescores=[], operations=[]),
        "mode_override": override, "stage": "build", "files": files, "tests": tests,
        "steps": steps, "amendments": [], "findings": [], "batch": batch,
        "diff": {"base_tree": base_tree, "base_commit": fs.safe_sensor(sensors.head_commit, root)},
        "gate": None, "owner_runtime": rt.name if rt.name in rr_runtime.RUNTIMES else None,
        "created": fs.now(), "created_at": fs.now(), "history": [],
    }
    if result.documents_only is not None:
        state["weight"]["documents_only"] = result.documents_only
    if os.path.exists(fs.ledger_path(root)):
        # The ledger is per project: a task mirrors only the lines after its start.
        state["dialog"] = {"ledger_pos": os.path.getsize(fs.ledger_path(root))}
    task.apply_defaults_v7(state)
    if steps:
        # The first step whose dependencies are done — steps[0] in a plan without `after`.
        next(iter(task.ready_steps(state)), steps[0]).update(status="in_progress", tree_before=base_tree)
    arm_scope(state)
    state["next_action"] = rr_policy.next_action_for(state)
    journal.emit(root, state, "task_started", fs.one_line(args.goal, 200),
         {"goal": args.goal, "workflow": args.workflow, "mode": mode, "schema": task.SCHEMA}, rt=rt)
    journal.emit(root, state, "weight_set", "W %d → %s" % (result.w, result.mode),
         {"w": result.w, "mode": result.mode, "axes": result.axes, "hints": result.hints,
          "unknown": result.unknown}, rt=rt)
    if override:
        journal.emit(root, state, "mode_set", "%s -> %s by %s" % (override["from"], mode, args.by),
             dict({"from": override["from"], "to": mode, "by": args.by, "why": args.why},
                  **(dict(via=via, **dialog.pick_data(dialog.DIALOG_PICK[0])) if via else {})),
             actor="human" if rr_policy.MODES.index(mode) < rr_policy.MODES.index(override["from"]) else "agent", rt=rt)
    journal.emit(root, state, "tier_set", "%s (mode %s, compat)" % (rr_policy.MODE_TIER[mode], mode),
         {"tier": rr_policy.MODE_TIER[mode], "mode": mode, "w": result.w}, rt=rt)
    if batch["on"]:
        journal.emit(root, state, "batch_set", "on by %s" % batch["by"],
             {"on": True, "by": batch["by"], "why": batch["why"], "via": None, "review_passes": 0, "suite_runs": 0}, rt=rt)
    handoff.set_resume_point(state, rt=rt)
    handoff.write_handoff(root, state, "start", rt=rt)
    task.save(root, state)
    report.write_task_md(root, state)
    print(weight.render(result))
    if override:
        print("mode: %s (override of %s by %s)" % (mode, override["from"], args.by))
    for later, earlier, shared in implied:
        print("ordered: %s after %s (shares %s)" % (later, earlier, shared))
    if batch["on"]:
        print("batch: on by %s · review %s passes · suite %s runs · %s at once on %s"
              % (batch["by"], table["review_rounds_max"], table["max_suite_runs"], table["parallel"], table["tier"]))
    advice = int((policy.get("rules") or {}).get("steps_advice_over", 8))
    if len(steps) > advice:
        print("advice: %d steps, over %d — fewer, larger steps cost fewer handoffs (not a gate)"
              % (len(steps), advice))
    print("%s started: %s · %d files in scope · %s"
          % (task_id, mode, len(task.task_files(state)), os.path.relpath(fs.task_md_path(root, state), root)))
    print("next: %s" % state["next_action"])
    profile.advise(state, rt=rt)


def start_amend(args, root, rt=rr_runtime.Runtime()):
    """R25: the task's files grow in place, journaled, never back to a plan."""
    state = task.load_v7(root, rt=rt)
    added = [f.lstrip("+").strip() for f in fs._split_files(args.files)]
    added = [f for f in added if f]
    if not added or not (args.why or "").strip():
        fs.die("--amend needs --files \"+a,+b\" and --why \"<why the task needs them>\"")
    new = [f for f in added if f not in state["files"]]
    if not new:
        print("scope unchanged: %s already in the task" % ", ".join(added))
        return
    state["files"] += new
    state["amendments"].append({"ts": fs.now(), "added": new, "why": args.why})
    arm_scope(state)
    journal.emit(root, state, "scope_change", "+%s — %s" % (", ".join(new), fs.one_line(args.why, 200)),
         {"added": new, "why": args.why}, rt=rt)
    task.save(root, state)
    report.write_task_md(root, state)
    print("scope amended: +%s (%d files in scope)" % (", ".join(new), len(task.task_files(state))))
