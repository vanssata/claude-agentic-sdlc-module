"""task: the task record — its schema, defaults, load and save, the task id, the steps and their order, and the old-surface routing.

core: TASK_COMMANDS, apply_defaults, TASK_ID_RE, open_gate, SCHEMA, is_v7, apply_defaults_v7, task_files, _overlap, order_shared_files, ready_steps, old_surface_refusal
shell: load, claim_runtime, save, sealed_task_ids, next_task_id, valid_task_id, load_v7, parse_steps, check_steps, abandon_old, route_surface, in_flight
"""
# pylint: disable=protected-access  # parse_steps calls fs._split_files, which partition.json assigns to fs
import contextlib
import json
import os
import re
from datetime import datetime, timezone

from rr_state import fs
from rr_state import journal
from rr_state import runtime as rr_runtime

try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None


# The commands that work on the task in flight; a task the old surface started
# refuses them all but close --abandon (route_surface).
TASK_COMMANDS = {"step-done", "ask", "answer", "questions", "approve", "reject", "close", "verify",
                 "review", "steps", "batch"}


def apply_defaults(state):
    """Schema 2 keys (I6) in memory, so a v1 state answers every command before
    migration 0002 has run; save() then persists them. A reader that opens
    the state file directly — update.py does — sees the file, not these."""
    if is_v7(state):
        return apply_defaults_v7(state)
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    # A hand-edited or half-migrated file may hold null where v1 held an object.
    # load() promises to be loud about a file it cannot read and silent about one
    # it can, so the defaults are total rather than assuming the v1 shape.
    if not isinstance(state.get("questions"), dict):
        state["questions"] = {"file": ".ai/reports/%s/task.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": True, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("gate_id", None), ("requested_session", None),
                         ("rejected_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    # Schema 4 (WP4 I2): a task that started before the gates existed has no
    # tree to measure from, and one cannot be invented afterwards.
    if not isinstance(state.get("diff"), dict):
        state["diff"] = {}
    state["diff"].setdefault("base_commit", None)
    state["diff"].setdefault("base_tree", None)
    # Schema 5 (WP5 I4): a task handed to the other runtime, and a review asked of it.
    state["handoff"].setdefault("pending_to", None)
    state["handoff"].setdefault("pending_since", None)
    state.setdefault("cross_vendor_review", None)
    return state


def load(root, required=True, claim=None, rt=rr_runtime.Runtime()):
    path = fs.state_path(root)
    if not os.path.exists(path):
        if required:
            fs.die("no task in flight (%s does not exist). Start one with state.py start." % path)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            state = apply_defaults(json.load(fh))
    except (OSError, ValueError, RecursionError) as exc:
        # Loud on purpose: a corrupt state file must never be silently replaced,
        # because ai-scope-guard's boundaries are derived from it.
        fs.die("%s is unreadable (%s). Inspect it by hand; do not delete it blindly." % (path, exc))
    # Ownership is taken before the command's own events, so the journal and
    # history both show the handoff ahead of the work it covers.
    if rt.mutating if claim is None else claim:
        claim_runtime(root, state, rt=rt)
    return state


def claim_runtime(root, state, rt=rr_runtime.Runtime()):
    """Called from load() for the commands in MUTATING_COMMANDS, so ownership is
    taken once rather than in fifteen call sites. A task that changes runtime says
    so in the journal; WP5 is what will move a task on purpose."""
    pending = (state.get("handoff") or {}).get("pending_to")
    if pending in rr_runtime.RUNTIMES:
        if rt.name != pending:
            back = ("state.py handoff --to %s" % rt.name if rt.name in rr_runtime.RUNTIMES else
                    "state.py --runtime %s handoff --to %s (this shell is neither runtime; "
                    "name the one taking it)" % ((rr_runtime.other_runtime(pending, rt=rt),) * 2))
            fs.die("RUNTIME_HANDOFF_PENDING: task %s was handed to %s at %s. Resume it there "
                "(/rr-build), or take it back here with: %s"
                % (state.get("task_id"), pending, state["handoff"].get("pending_since"), back), 7)
        # The receiving runtime's first change: the handoff is complete. The
        # move itself was journaled when it was made, so there is no second event.
        state["handoff"]["pending_to"] = None
        state["handoff"]["pending_since"] = None
    previous = state.get("owner_runtime")
    if rt.name not in rr_runtime.RUNTIMES or previous == rt.name:
        return
    if previous in rr_runtime.RUNTIMES:
        journal.emit(root, state, "runtime_handoff", "%s -> %s" % (previous, rt.name),
             {"from": previous, "to": rt.name, "via": "resume"}, rt=rt)
    state["owner_runtime"] = rt.name


def save(root, state):
    state["updated_at"] = fs.now()
    path = fs.state_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        fs.die("cannot write %s (%s) — the state is the contract, so nothing was recorded" % (path, exc))


def sealed_task_ids(root):
    """The task ids a package under .ai/memory/ seals; empty in files mode."""
    found = set()
    base = os.path.join(root, ".ai", "memory")
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        try:
            with open(os.path.join(base, name), "rb") as fh:
                for raw in fh:
                    if b'"kind":"task"' not in raw:
                        continue
                    with contextlib.suppress(ValueError, UnicodeDecodeError, AttributeError, RecursionError):
                        found.add(json.loads(raw.decode("utf-8")).get("task"))
        except OSError:
            continue
    return found


def next_task_id(root, goal="", slug=None, at=None):
    """R1: T-YYYY-MM-DD-HHMM-<slug>, from the clock and the goal alone. A count
    of the day's report directories gave two clones the same id and handed a
    deleted directory's id to the next task. A local hit — a report directory,
    the raw store under .ai/state/logs/, a sealed key — gets -2 … -9."""
    import memory_format                  # pylint: disable=import-outside-toplevel
    stamp = at or datetime.now(timezone.utc)
    base = slug or memory_format.slug_of(goal)
    sealed = sealed_task_ids(root)
    for n in range(1, 10):
        task_id = memory_format.new_task_id(stamp, memory_format.with_suffix(base, n))
        if not (os.path.exists(os.path.join(root, ".ai", "reports", task_id))
                or os.path.exists(os.path.join(root, ".ai", "state", "logs", task_id)) or task_id in sealed):
            return task_id
    fs.die("%s and -2 … -9 are all taken this minute: start again with another --slug \"<3-24 characters>\""
        % memory_format.new_task_id(stamp, base), 2)
    return None


TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def valid_task_id(task_id, flag="--task-id"):
    """A task id is a directory name under .ai/reports/, and everything the
    journal and the questions file are worth rests on it staying one. A '/' or
    a '..' in it puts both outside the project — and outside the path guard's
    `.ai/reports/<id>/` patterns, which is how a writable task.md, and
    with it a self-granted gate, would come back."""
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id) or ".." in task_id:
        fs.die("%s takes a directory name — letters, digits, '.', '_' and '-', "
            "no path separators — not %r" % (flag, task_id))
    return task_id


def open_gate(state):
    """The one signal that a gate is open, and the one thing that names it.

    R11 words this as "a gate_requested event exists", and the first draft read
    the journal for one. It must not: events.jsonl is append-only, unprotected,
    and keyed on a caller-supplied task id, so a single hand-written line — or
    an `init --task-id` that reuses an old id — satisfied the precondition. The
    state is the contract and the path guard protects it; `stage human_approval`
    is the only writer, and approve/reject consume what it wrote.
    """
    approval = state.get("human_approval") or {}
    if approval.get("requested_at") and approval.get("gate_id"):
        return approval["gate_id"]
    return None


SCHEMA = 7


def is_v7(state):
    return isinstance(state, dict) and state.get("schema") == SCHEMA


def apply_defaults_v7(state):
    """The keys every shared helper reads (questions, handoff, the gate) and the
    schema-7 ones; none of the old surface's own keys, so a schema-7 file holds
    only what its commands use."""
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    state.setdefault("cross_vendor_review", None)
    if not isinstance(state.get("questions"), dict):
        state["questions"] = {"file": ".ai/reports/%s/task.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    state["handoff"].setdefault("pending_to", None)
    state["handoff"].setdefault("pending_since", None)
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": False, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("gate_id", None), ("requested_session", None),
                         ("rejected_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    for key, default in (("files", []), ("tests", []), ("steps", []), ("amendments", []),
                         ("findings", []), ("diff", {}), ("gate", None), ("mode_override", None)):
        if not isinstance(state.get(key), type(default)) and not (default is None and key in state):
            state[key] = default
    for step in state["steps"]:
        if not isinstance(step.get("after"), list):
            step["after"] = []                # a step from before the batch loop depends on nothing
    if not isinstance(state.get("batch"), dict):
        state["batch"] = {"on": False, "by": None, "why": None, "since": None}
    if not isinstance(state.get("verify"), dict):
        state["verify"] = {}
    for key, default in (("status", "not_run"), ("e2e", "not_run"), ("suite_runs", 0), ("runs", [])):
        state["verify"].setdefault(key, default)
    if not isinstance(state.get("review"), dict):
        state["review"] = {}
    for key, default in (("status", "not_started"), ("passes", 0), ("tier", None),
                         ("findings", []), ("tree", None), ("log", []), ("closed", [])):
        state["review"].setdefault(key, default)
    return state


def load_v7(root, rt=rr_runtime.Runtime()):
    state = load(root, rt=rt)
    if not is_v7(state):
        fs.die(old_surface_refusal(state))
    return state


def task_files(state):
    """Every file and glob the task may touch: its files, its tests, every step's."""
    out = list(state.get("files") or []) + list(state.get("tests") or [])
    for step in state.get("steps") or []:
        out += list(step.get("files") or []) + list(step.get("tests") or [])
    return list(dict.fromkeys(out))


def parse_steps(text, plan_file):
    """--steps "id:a,b:t;id2:c" or --plan-file F.json ([{id, files, tests, after}]);
    `after` (plan-file only) names the steps this one waits for (R2)."""
    raw = []
    if plan_file:
        try:
            with open(plan_file, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError, RecursionError) as exc:
            fs.die("--plan-file %s: %s" % (plan_file, exc))
        if not isinstance(raw, list) or not all(isinstance(s, dict) for s in raw):
            fs.die("--plan-file holds a JSON list of {\"id\", \"files\", \"tests\", \"after\"}")
        for s in raw:
            after = s.get("after") or []
            if not isinstance(after, list) or not all(isinstance(a, str) and a.strip() for a in after):
                fs.die("step %s: \"after\" is a JSON list of step ids" % (s.get("id") or "?"))
        raw = [(str(s.get("id") or ""), ",".join(s.get("files") or []), ",".join(s.get("tests") or []),
                [fs.one_line(a, 40) for a in s.get("after") or []]) for s in raw]
    for chunk in [c for c in (text or "").split(";") if c.strip()]:
        parts = chunk.split(":")
        raw.append((parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else "", []))
    steps = []
    for step_id, files, tests, after in raw:
        step_id = fs.one_line(step_id, 40)
        if not step_id or not fs._split_files(files):
            fs.die("a step is id:files[:tests], with at least one file: %r" % ":".join((step_id, files, tests)))
        if step_id in [s["id"] for s in steps]:
            fs.die("step id %s appears twice" % step_id)
        steps.append({"id": step_id, "files": fs._split_files(files), "tests": fs._split_files(tests),
                      "after": list(dict.fromkeys(after)), "status": "pending", "tree_before": None,
                      "tree_after": None})
    return steps


def _overlap(a, b):
    """One path or pattern covers the other: equal once normalised, or one
    matches the other as a glob — so `src/*.py` and `./src/a.py` count as shared."""
    a, b = os.path.normpath(a), os.path.normpath(b)
    return a == b or bool(weight and (weight.match(a, [b]) or weight.match(b, [a])))


def order_shared_files(steps):
    """Two steps that name one file or pattern — among their files or their
    tests — never run side by side: the later one is put after the earlier (R2).
    Returns the implied edges as (later, earlier, what they share)."""
    implied = []
    for n, later in enumerate(steps):
        for earlier in steps[:n]:
            shared = [f for f in later["files"] + later["tests"]
                      if any(_overlap(f, g) for g in earlier["files"] + earlier["tests"])]
            if shared and earlier["id"] not in later["after"]:
                later["after"].append(earlier["id"])
                implied.append((later["id"], earlier["id"], ", ".join(dict.fromkeys(shared))))
    return implied


def check_steps(steps, implied=()):
    """Every `after` names another, existing step, and the steps form no cycle (R2).
    A cycle closed by an implied edge (order_shared_files) names that edge."""
    ids = [s["id"] for s in steps]
    for step in steps:
        for dep in step["after"]:
            if dep == step["id"]:
                fs.die("step %s lists itself in after" % step["id"])
            if dep not in ids:
                fs.die("step %s is after %s, which is not a step (have: %s)" % (step["id"], dep, ", ".join(ids)))
    by_id = {s["id"]: s for s in steps}
    seen = {}                                 # id -> "visiting" | "done"

    def visit(step_id, trail):
        if seen.get(step_id) == "done":
            return
        if seen.get(step_id) == "visiting":
            loop = trail + [step_id]
            hints = ["%s after %s is implied: they share %s" % edge for edge in implied
                     if edge[0] in loop and edge[1] in loop]
            fs.die("the steps' after form a cycle: %s%s" % (
                " -> ".join(loop), " (%s — list the dependent row after the one it needs)" % "; ".join(hints)
                if hints else ""))
        seen[step_id] = "visiting"
        for dep in by_id[step_id]["after"]:
            visit(dep, trail + [step_id])
        seen[step_id] = "done"

    for step in steps:
        visit(step["id"], [])


def ready_steps(state):
    """The steps not yet done whose `after` are all done, in plan order: the next
    wave of /rr-build-all, and the step step-done starts next."""
    steps = state.get("steps") or []
    done = {s["id"] for s in steps if s.get("status") == "done"}
    return [s for s in steps if s.get("status") != "done" and all(d in done for d in s.get("after") or [])]


def old_surface_refusal(state):
    return ("task %s runs on the old surface (schema %s), whose commands were removed in redesign 2.6: "
            "finish it with the plugin version that started it, or drop it with 'state.py close --abandon'"
            % (state.get("task_id"), state.get("schema") or "<7"))


def abandon_old(_args, root, rt=rr_runtime.Runtime()):
    """close --abandon for a task the old surface started: the record moves to
    .ai/state/logs/<task>/state.json as it is, and nothing else is measured."""
    state = load(root, rt=rt)
    state["result"] = "abandoned"
    state["closed_at"] = fs.now()
    journal.emit(root, state, "task_closed", "abandoned", {"abandoned": True, "surface": "old"}, rt=rt)
    fs.ensure_logs(root, state["task_id"])
    target = os.path.join(fs.logs_dir(root, state["task_id"]), "state.json")
    state["updated_at"] = fs.now()
    tmp = "%s.%d.tmp" % (target, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, target)
    with contextlib.suppress(OSError):
        os.remove(fs.handoff_path(root))
    fs.remove_state(root)
    print("%s abandoned (old surface)" % state["task_id"])
    print("state: %s" % os.path.relpath(target, root))


def route_surface(root, args, rt=rr_runtime.Runtime()):
    """A task the old surface started (schema < 7) is read (status, handoff,
    questions without --sync) or dropped (close --abandon); every command that
    works on it refuses."""
    if args.command not in TASK_COMMANDS:
        return
    state = load(root, required=False, claim=False, rt=rt)
    if state is None or is_v7(state) or (args.command == "questions" and not args.sync):
        return
    if args.command == "close" and args.abandon:
        args.func = abandon_old
        return
    fs.die(old_surface_refusal(state))


def in_flight(root, rt=rr_runtime.Runtime()):
    state = load(root, required=False, claim=False, rt=rt)
    return state if state and state.get("current_stage") != "done" and state.get("task_id") else None
