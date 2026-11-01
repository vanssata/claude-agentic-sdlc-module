"""dialog: the human decision dialog and the authority that tells a human from the agent -- decisions, consent labels, picks, the approval offer.

shell: human_route, human_turn, refuse_approval, DIALOG_PICK, dialog_policy, dialog_tool_verified, dialog_on, open_decision, print_dialog, offer_decision, settle_decision, settle_written, prune_decisions, mirror_ledger, sync_dialog, dialog_pick, valid_decisions, retire_approvals, task_facts, audit_pick, approve_command, offer_approval
core: DIALOG_TOOL, SESSION_ENV, DECISIONS_MAX, QUESTION_MAX, HEADER_MAX, JSON_DEPTH_MAX, json_loads_capped, dialog_questions, option_description, part_question, dialog_payload, MIRROR, pick_data
"""
import json
import os
import shlex
import sys

from rr_state import fs, journal, labels, locks
from rr_state import ledger as rr_ledger
from rr_state import policy as rr_policy
from rr_state import runtime as rr_runtime
from rr_state import task


def human_route(root=None, allow_dialog=False, rt=rr_runtime.Runtime()):
    """(via, why): "terminal" for a terminal outside any agent session,
    "unattended" for a launcher that declared the run unattended, else None and
    what was seen. A terminal alone is not enough — an agent can open a pty — so
    a terminal that carries an agent marker is the agent's. The same condition
    as adopt.human_gate().

    With allow_dialog, and only with the dialog on, a third route comes before
    the agent-marker refusal: "dialog", when a live pick of this session is this
    very command (dialog_pick, R36.10). The pick is spent here; DIALOG_PICK
    names it for the caller's journal line."""
    markers = rr_runtime.agent_markers()
    if os.isatty(0) and not markers:
        return "terminal", ""
    if fs.ai_unattended():
        return "unattended", ""
    if allow_dialog and root and dialog_pick(root, rt=rt):
        return "dialog", ""
    if markers:
        return None, ("this run is inside an agent session (%s %s set); run it in a terminal "
                      "outside Claude Code or Codex, not through the `!` prefix"
                      % (", ".join(markers), "is" if len(markers) == 1 else "are"))
    return None, "this run has no terminal"


def human_turn(root, state):
    """Did a human take a turn in this project since the gate was requested?

    The evidence is .ai/state/session.json, which only context-guard.py writes,
    on UserPromptSubmit. It is what makes the file route different from the
    agent filling in the answer itself: the agent cannot advance last_prompt_at
    without the human sending a prompt. Weaker than a TTY, and documented as
    such — but it is a turn the human took, at a moment they could see the plan.
    """
    session = fs.read_session(root)
    relative = os.path.relpath(fs.session_path(root), root)
    turn = session.get("last_prompt_at")
    requested = (state.get("human_approval") or {}).get("requested_at")
    if not isinstance(turn, str) or not turn:
        return False, "there is no %s, so no human turn can be seen" % relative
    if not requested or turn < requested:
        return False, ("the last prompt in %s (%s) is older than the approval request (%s)"
                       % (relative, turn, requested))
    opened_in = (state.get("human_approval") or {}).get("requested_session")
    if not opened_in:
        # The gate was opened without a session on record — the hook had never
        # run in this project (Codex before /hooks, or a task older than the
        # install). There is then nothing to bind the turn to, and any later
        # session's prompt would do. The terminal route is unaffected; this
        # route fails closed, because it is the weaker of the two.
        return False, ("no session was recorded when the gate was requested, so a prompt in %s "
                       "cannot be tied to it — approve from your own terminal instead" % relative)
    if session.get("last_prompt_session") != opened_in:
        # One file per project, last writer wins, so session.json's own two
        # fields always agree after any real second session. The turn has to
        # come from the session the plan was presented in.
        return False, ("the last prompt in %s came from another session (%s, not %s, "
                       "which is where the gate was requested)"
                       % (relative, session.get("last_prompt_session"), opened_in))
    return True, ""


def refuse_approval(root, state, gate_id, by, why):
    # Quoted: this project's own path has a space in it, and the command the
    # refusal prints is the only route a human without the flag has.
    fs.die("APPROVAL_REFUSED — approval happens outside the agent. Run in your own terminal:\n"
        "  python3 %s --root %s approve --by %s\n"
        "or set [Answer]: A on %s in %s and tell the session to sync. An unattended run exports "
        "AI_UNATTENDED=1 in the launcher's environment; the journal then records the approval as "
        "unattended.\nRefused because %s."
        % (shlex.quote(fs.ENTRY), shlex.quote(root), shlex.quote(by), gate_id,
           os.path.relpath(fs.questions_path(root, state, None), root), why), 5)


# ---------------------------------------------- the dialog (R36, step 7c)
#
# A guarded command or a decision, offered in the runtime's own dialog. state.py
# is the only writer of decision.json and prepares every question; the recorder
# hook (7d1) appends the human's picks to consent.jsonl from the harness's
# tool_response, and state.py appends `use` and `settle`. With the switch off —
# no .ai/policies/dialog.json, every project until 7f ships the template — none
# of this runs and every command prints and refuses as before (R36.2).

DIALOG_TOOL = {"claude": "AskUserQuestion", "codex": "request_user_input"}
# The runtime's session id as the Bash tool's environment carries it. Both
# mappings are verified by the 2026-10-31 spike (docs/dialog-spike.md, "Session
# ids and the Stop block"): the variable equals the hook payload's session_id.
# It must equal hooks/guard/dialog.py SESSION_ENV; tests/test_dialog_contract.py
# checks that and feeds both sides the same switch fixtures.
SESSION_ENV = {"claude": "CLAUDE_CODE_SESSION_ID", "codex": "CODEX_THREAD_ID"}
DECISIONS_MAX = 4                         # questions one dialog call carries (R36.3)
QUESTION_MAX, HEADER_MAX = 1200, 12

# The pick human_route() consumed in this process, held in a one-slot list changed in place:
# `global` is refused under rr_state/ (R4).
DIALOG_PICK = [None]

JSON_DEPTH_MAX = 64                       # one nesting cap for both switches, not the stack's


def json_loads_capped(text):
    """json.loads(text), except that a text nested deeper than JSON_DEPTH_MAX is
    malformed (ValueError). The parser's own limit moves with the stack depth, so
    the hook and state.py could disagree; this scan does not recurse."""
    depth, in_str, esc = 0, False, False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > JSON_DEPTH_MAX:
                raise ValueError("JSON nested deeper than %d" % JSON_DEPTH_MAX)
        elif ch in "]}":
            depth -= 1
    return json.loads(text)


def dialog_policy(root):
    """.ai/policies/dialog.json when it says enabled: true, else None (R36.1)."""
    try:
        with open(os.path.join(root, ".ai", "policies", "dialog.json"), encoding="utf-8") as fh:
            data = json_loads_capped(fh.read())
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("enabled") is not True:
        return None
    window = data.get("window_seconds", 120)
    window = window if isinstance(window, int) and not isinstance(window, bool) else 120
    return {"window_seconds": min(600, max(30, window)),
            "background_sessions": data.get("background_sessions") is True}


def dialog_tool_verified(runtime):
    """profile.json dialog.tool read from <home>/riskrails/profile.json only, as the
    hooks' dialog_tool() does: an installer from 7b on writes dialog.tool, always
    there, so the pre-3.4b claude-agentic/ fallback of read_profile() is not
    consulted. A missing, unreadable, malformed, too deeply nested or non-object
    file is no tool."""
    try:
        with open(os.path.join(rr_runtime.runtime_home(runtime), "riskrails", "profile.json"), encoding="utf-8") as fh:
            data = json_loads_capped(fh.read())
        return (data.get("dialog") or {}).get("tool")
    except (OSError, ValueError, AttributeError, RecursionError):
        return None


def dialog_on(root, runtime="unknown"):
    """The effective switch, state.py's copy of the hooks' switch_state() (7d1):
    the project says on, nobody declared the run unattended, the runtime's dialog
    tool is the one the installer verified (read from riskrails/profile.json
    only, never the old claude-agentic/ file), and the session has an id to bind
    a pick to. The hooks also compare the payload's session id with the
    environment's, which this copy never sees: a differing payload id is "closed"
    there while this returns a dict, and the hook refuses the call, so the dict is
    not acted on. A payload id with no environment id is "on" there and None here:
    no pick can be bound, so the commit is denied.

    None covers both of the hooks' "off" and "closed": no session id in the
    environment means a pick cannot be bound, so it fails closed to the
    terminal route (every approval and commit command prints for the human's
    terminal). A dict is the hooks' "on"."""
    if not root:
        return None
    policy = dialog_policy(root)
    if not policy or fs.ai_unattended():
        return None
    # the runtime's unattended marker (a background job, `claude -p`, the SDK)
    # turns the dialog off unless the project opts in, as the hooks' unattended();
    # the opt-in never covers an SDK entrypoint (sdk-*: `claude -p`, an SDK host — risk ffae)
    background = policy["background_sessions"] and \
        not os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk-")
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0" and not background:
        return None
    runtime = rr_runtime.own_runtime(runtime=runtime)
    tool = dialog_tool_verified(runtime)
    session = os.environ.get(SESSION_ENV.get(runtime, ""))
    if runtime not in DIALOG_TOOL or tool != DIALOG_TOOL[runtime] or not session:
        return None
    return dict(policy, runtime=runtime, tool=tool, session=session)


def dialog_questions(decision):
    """One decision as dialog questions: a command list is one multi-select,
    unless a label holds ", " — a joined answer would be ambiguous — and then
    one single-select per command, each with the safe option first (R36.4)."""
    options = decision["options"]
    commands = [o for o in options if o["kind"] == "command"]
    if decision.get("multi_select") and any(", " in o["label"] for o in commands):
        safe = [o for o in options if o["kind"] == "choice"][:1]
        return [(safe + [o], False) for o in commands]
    return [(options, bool(decision.get("multi_select")))]


def open_decision(root, state, kind, header, question, options, opened_by, multi=False, rt=rr_runtime.Runtime(), **extra):
    """Write one decision; return (it, "") or (None, why) (R36.3, R36.4)."""
    data = rr_ledger.read_decisions(root)
    questions = sum(len(dialog_questions(d)) for d in data["open"])
    if questions + len(dialog_questions({"options": options, "multi_select": multi})) > DECISIONS_MAX:
        return None, "DECISION_LIMIT — %d questions are open; one dialog call carries %d" % (
            questions, DECISIONS_MAX)
    if not 2 <= len(options) <= 4:
        return None, "a decision has 2 to 4 options"
    for option in options:
        why = labels.validate_label(option["label"]) if option["kind"] == "command" else (
            None if 0 < len(option["label"]) <= labels.LABEL_MAX and option["label"].isprintable()
            else "a choice label is 1 to %d printable characters" % labels.LABEL_MAX)
        if why:
            return None, "CONSENT_LABEL_INVALID — %s: %s" % (why, option["label"][:120])
    if len({o["label"] for o in options}) != len(options):
        return None, "CONSENT_LABEL_INVALID — two options carry the same label"
    # Two open decisions with one question text can never be answered in the
    # dialog: the recorder reads both as ambiguous (risks afd2, 712d).
    shown = (question or "").strip()[:QUESTION_MAX]
    session = (dialog_on(root, runtime=rt.name) or {}).get("session")
    twin = next((d for d in data["open"] if d.get("question") == shown), None)
    if twin:
        tid = twin.get("id")
        if twin.get("session") != session:
            # decision show lists only this session's decisions (risk e3ae).
            return None, ("DECISION_DUPLICATE — %s is open with this very question from another session; "
                          "it cannot be sent from here: 'state.py decision fallback --id %s --why …' "
                          "before opening it again" % (tid, tid))
        return None, ("DECISION_DUPLICATE — %s is open with this very question; send it ('state.py decision show') "
                      "and run the pick, or 'state.py decision fallback --id %s --why …', before opening it again"
                      % (tid, tid))
    decision = dict({
        "id": rr_ledger.next_decision_id(data, rr_ledger.read_ledger(root)), "kind": kind, "task": (state or {}).get("task_id"),
        "runtime": rr_runtime.own_runtime(runtime=rt.name), "session": session,
        "tree": fs.current_tree(root), "opened_at": fs.now(), "opened_by": opened_by,
        "header": fs.one_line(header, HEADER_MAX), "multi_select": bool(multi),
        "question": (question or "").strip()[:QUESTION_MAX],
        "options": [dict(option, n=n) for n, option in enumerate(options, 1)],
    }, **extra)
    data["open"].append(decision)
    rr_ledger.write_decisions(root, data)
    if state and state.get("task_id"):
        journal.append_journal(root, state["task_id"], journal.journal_line(
            state["task_id"], "decision_opened", "agent", state.get("current_stage"),
            "%s %s by %s" % (decision["id"], kind, opened_by),
            {"decision": decision["id"], "kind": kind, "options": len(options)}, runtime=rt.name))
    return decision, ""


def option_description(option):
    if option.get("description"):
        return option["description"]
    return "the session runs exactly this, once" if option["kind"] == "command" else "nothing runs"


def part_question(question, i, n):
    """The question text of part i of n: a split decision's parts must differ,
    Claude keys tool_response.answers by text; cut so the whole fits QUESTION_MAX."""
    if n < 2:
        return question
    suffix = " (%d of %d)" % (i, n)
    return (question or "")[:QUESTION_MAX - len(suffix)] + suffix


def dialog_payload(decisions, runtime):
    """The dialog tool's input for these decisions, in file order: AskUserQuestion
    for Claude, request_user_input for Codex (keyed by a question id)."""
    questions = []
    for decision in decisions:
        parts = dialog_questions(decision)
        for i, (options, multi) in enumerate(parts, 1):
            item = {"question": part_question(decision["question"], i, len(parts)), "header": decision["header"],
                    "options": [{"label": o["label"], "description": option_description(o)} for o in options]}
            if runtime == "codex":
                item = dict({"id": "%s%s" % (decision["id"].lower(), "_%d" % i if len(parts) > 1 else "")},
                            **item)
            else:
                item["multiSelect"] = multi
            questions.append(item)
    return {"questions": questions[:DECISIONS_MAX]}


def print_dialog(decisions, rt=rr_runtime.Runtime()):
    """DIALOG_PENDING and the JSON the agent sends to the dialog tool."""
    runtime = rr_runtime.own_runtime(runtime=rt.name)
    print("DIALOG_PENDING %s — call %s with exactly this JSON, then run the picked command verbatim "
          "or 'state.py decision settle --id %s':"
          % (" ".join(d["id"] for d in decisions), DIALOG_TOOL.get(runtime, "AskUserQuestion"),
             decisions[0]["id"]))
    print(json.dumps(dialog_payload(decisions, runtime), ensure_ascii=False))


def offer_decision(root, state, kind, header, question, options, opened_by, rt=rr_runtime.Runtime(), **extra):
    """An opener's whole dialog branch: with the switch on, open and print the
    decision and return it; off, or refused, return None and the caller prints
    today's terminal text (R36.2)."""
    if not dialog_on(root, runtime=rt.name):
        return None
    decision, why = open_decision(root, state, kind, header, question, options, opened_by, rt=rt, **extra)
    if decision is None:
        print("state.py: no dialog — %s" % why, file=sys.stderr)
        return None
    print_dialog([decision], rt=rt)
    return decision


def settle_decision(root, decision_id, effect, pick=None):
    """Write the settle line and drop the decision from decision.json."""
    with locks.ledger_lock(root):
        rr_ledger.ledger_append(root, {"type": "settle", "decision": decision_id, "pick": pick, "effect": effect})
    data = rr_ledger.read_decisions(root)
    data["open"] = [d for d in data["open"] if d.get("id") != decision_id]
    rr_ledger.write_decisions(root, data)


def settle_written(root, entry):
    """True when the settle line is in the ledger; a decision leaves decision.json
    only with its line (43ae-I4)."""
    try:
        with locks.ledger_lock(root):
            rr_ledger.ledger_append(root, entry)
    except OSError:
        return False
    return True


def prune_decisions(root):
    """On every run: a decision with a settle line, or whose latest round's
    command picks are all used, leaves decision.json (R36.14); with the
    project's dialog switch off, every open one falls back (R36.15)."""
    try:
        with open(fs.decision_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
        keep = list(data["open"])
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return                            # loud in the decision commands, not in every command
    ledger = rr_ledger.read_ledger(root)
    settled = {e.get("decision") for e in ledger if e["type"] == "settle"}
    used = {e.get("id") for e in ledger if e["type"] == "use"}
    rounds = rr_ledger.latest_rounds(ledger)
    off = dialog_policy(root) is None
    for decision in list(keep):
        commands = {o.get("n") for o in decision.get("options") or [] if o.get("kind") == "command"}
        picks = [e for e in rounds.get(decision.get("id"), []) if e.get("option") in commands]
        if decision.get("id") in settled:
            keep.remove(decision)
        elif off:
            if settle_written(root, {"type": "settle", "decision": decision["id"], "pick": None,
                                     "effect": "fallback"}):
                keep.remove(decision)
        elif picks and all(p.get("id") in used for p in picks):
            parsed = labels.label_argv(picks[-1].get("label") or "")
            effect = "declined" if parsed and labels.subcommand(parsed[1])[:1] == ["reject"] else "approved"
            if settle_written(root, {"type": "settle", "decision": decision["id"], "pick": picks[-1].get("id"),
                                     "effect": effect}):
                keep.remove(decision)
    if len(keep) != len(data["open"]):
        data["open"] = keep
        rr_ledger.write_decisions(root, data)


MIRROR = {"pick": "consent_recorded", "use": "consent_used", "void": "consent_voided",
          "decline": "decision_declined"}


def mirror_ledger(root, rt=rr_runtime.Runtime()):
    """New ledger lines into the journal of the task in flight (R36.24); the
    byte cursor is the state's, so each line is mirrored once."""
    state = task.load(root, required=False, claim=False, rt=rt)
    path = fs.ledger_path(root)
    if state is None or not task.is_v7(state) or not os.path.exists(path):
        return
    dialog = state.setdefault("dialog", {})
    position = dialog.get("ledger_pos", 0)
    try:
        with open(path, "rb") as fh:
            fh.seek(position)
            chunk = fh.read()
    except OSError:
        return
    end = chunk.rfind(b"\n") + 1
    if not end:
        return
    for raw in chunk[:end].decode("utf-8", "replace").splitlines():
        try:
            entry = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        if not isinstance(entry, dict) or entry.get("type") not in rr_ledger.LEDGER_TYPES or entry["type"] == "offer":
            continue
        event = MIRROR.get(entry["type"]) or ("decision_fallback" if entry.get("effect") == "fallback"
                                              else "decision_settled")
        data = {k: entry[k] for k in ("id", "ids", "decision", "option", "order", "by", "why", "pick",
                                      "effect", "tool_use_id", "session") if k in entry}
        journal.append_journal(root, state["task_id"], journal.journal_line(
            state["task_id"], event, "hook", state.get("current_stage"),
            fs.one_line(entry.get("label") or entry.get("id") or entry.get("decision"), 200), data, runtime=rt.name))
    dialog["ledger_pos"] = position + end
    task.save(root, state)


def sync_dialog(root, rt=rr_runtime.Runtime()):
    """Prune, then mirror: what every state-changing run does first."""
    if os.path.exists(fs.decision_path(root)):
        prune_decisions(root)
    if os.path.exists(fs.ledger_path(root)):
        mirror_ledger(root, rt=rt)


def dialog_pick(root, rt=rr_runtime.Runtime()):
    """The dialog branch of human_route() (R36.10): a live pick of this session
    whose label runs this very state.py with exactly this argv. Its `use` is
    appended before the caller acts, so the pick is spent even when the command
    then fails; when it was the decision's last pick, the decision settles.

    A pick counts only for a decision that is still open, and an approval's
    only while the gate and the tree it was offered for are the ones in force:
    an approve label is the same string for every gate of a project, so a pick
    left over from a rejected or superseded gate must not sign the next one."""
    switch = dialog_on(root, runtime=rt.name)
    if not switch:
        return None
    here, argv = os.path.realpath(fs.ENTRY), sys.argv[1:]
    current = valid_decisions(root, rt=rt)
    try:
        with locks.ledger_lock(root):
            for pick in rr_ledger.live_picks(rr_ledger.read_ledger(root), switch["session"]):
                parsed = labels.label_argv(pick.get("label") or "")
                if parsed and os.path.realpath(parsed[0]) == here and parsed[1] == argv \
                        and pick.get("decision") in current:
                    rr_ledger.ledger_append(root, {"type": "use", "id": pick["id"],
                                         "by": "state.py %s" % " ".join(labels.subcommand(argv)[:1])})
                    DIALOG_PICK[0] = pick
                    break
    except OSError:
        return None                       # no ledger, no lock: no consent (fails closed)
    if DIALOG_PICK[0]:
        prune_decisions(root)
    return DIALOG_PICK[0]


def valid_decisions(root, rt=rr_runtime.Runtime()):
    """The ids of the open decisions a pick may still count for: every open
    one, except an approval whose gate or tree is no longer the one in force."""
    try:
        with open(fs.decision_path(root), encoding="utf-8") as fh:
            decisions = [d for d in json.load(fh)["open"] if isinstance(d, dict)]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return set()
    state = task.load(root, required=False, claim=False, rt=rt) if any(d.get("kind") == "approval" for d in decisions) else None
    tree = fs.current_tree(root) if state else None
    return {d.get("id") for d in decisions
            if d.get("kind") != "approval" or (state and d.get("task") == state.get("task_id")
                                               and d.get("gate_id") and d.get("gate_id") == task.open_gate(state)
                                               and d.get("tree") == tree)}


def retire_approvals(root, task_id, effect):
    """Settle the task's open approval decisions: the gate they were offered for
    was granted, rejected or asked again (H1)."""
    if not os.path.exists(fs.decision_path(root)):
        return
    for decision in rr_ledger.read_decisions(root)["open"]:
        if decision.get("kind") == "approval" and decision.get("task") == task_id:
            settle_decision(root, decision["id"], effect)


def pick_data(pick):
    """What a grant through the dialog adds to its journal line (R36.10)."""
    return {"consent": pick.get("id"), "decision": pick.get("decision"),
            "tool_use_id": pick.get("tool_use_id")} if pick else {}


def task_facts(root, state):
    """The self-contained head of a decision's question: the modal hides the
    output above it (R36.3)."""
    review, weight_ = state.get("review") or {}, state.get("weight") or {}
    findings = [f.get("label") for f in state.get("findings") or [] if f.get("status") == "open"]
    reversibility = (weight_.get("axes") or {}).get("reversibility", 0)
    rollback = "git revert" if not reversibility else "git revert is not enough — reversibility %s: %s" % (
        reversibility, fs.one_line((weight_.get("evidence") or {}).get("reversibility"), 160))
    return ("%s — %s\nmode %s · W %s · tree %s\nverify: %s · review: %s%s\nrollback: %s"
            % (state.get("task_id"), fs.one_line(state.get("goal"), 200), state.get("mode"),
               weight_.get("w"), (fs.current_tree(root) or "?")[:9],
               "green" if rr_policy.suite_green(state) else "not green", review.get("status") or "none",
               " (open: %s)" % ", ".join(findings) if findings else "", rollback))


def audit_pick(pick):
    """ok: the transcript holds the pick's tool_use_id; mismatch: it does not —
    a line no dialog produced; unverifiable: no transcript to read."""
    path, tool_use = pick.get("transcript"), pick.get("tool_use_id")
    if not path or not tool_use or not os.path.isfile(path):
        return "unverifiable"
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "ok" if any(tool_use in line for line in fh) else "mismatch"
    except OSError:
        return "unverifiable"


def approve_command(root, state):
    ops = state["weight"].get("operations") or []
    confirm = (" --confirm \"<what it does, naming %s>\"" % (" and ".join(ops) or "the operation")
               if state["mode"] == "full_irreversible" else "")
    return "python3 %s --root %s approve --by \"<name>\"%s" % (
        shlex.quote(fs.ENTRY), shlex.quote(root), confirm)


def offer_approval(root, state, facts, rt=rr_runtime.Runtime()):
    """close's dialog branch (R36.3): Not now, approve, reject — full mode only;
    full_irreversible keeps the terminal command (R36.10)."""
    name = labels.human_name(root)
    retire_approvals(root, state["task_id"], "superseded")
    return offer_decision(
        root, state, "approval", "Approve",
        "%s\nfacts: (a) %s · (b) %s\nApprove this tree for %s?"
        % (task_facts(root, state), facts["a"][1], facts["b"][1], state["task_id"]),
        [{"kind": "choice", "effect": "defer", "label": "Not now — leave the gate open"},
         {"kind": "command", "label": labels.state_label(root, ["approve", "--by", name])},
         {"kind": "command", "label": labels.state_label(root, ["reject", "--by", name, "--why", "rejected in the dialog"])}],
        "close", gate_id=state["human_approval"]["gate_id"], rt=rt)
