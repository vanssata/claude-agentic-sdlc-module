"""R36: the hooks' side of the command-choice dialog — the effective switch,
the consent ledger (.ai/state/consent.jsonl) and its reader, and the one
adapter that maps both runtimes' dialog tools to one shape.

state.py keeps its own small reader of the same ledger (spec design item 2);
tests/test_dialog_contract.py feeds both the same fixtures, so they cannot
drift. Nothing here imports state.py: hooks run under `python3 -I -S`, stdlib
only.

Off is today: with .ai/policies/dialog.json missing or not `enabled: true`,
no AI_UNATTENDED, the runtime's verified dialog tool, the main session and a
session id all required, effective_switch() is False and no caller writes or
decides anything (R36.1, R36.2). Readers fail open: a missing or unreadable
file reads as "nothing open, nothing picked".
"""
import contextlib
import json
import os
import re
import shlex
import time
from datetime import datetime, timedelta, timezone

LABEL_MAX = 400
WINDOW = (120, 30, 600)                     # window_seconds: default, lower and upper bound
STOP_BLOCKS_MAX = 2
LOCK_STALE_S = 2.0
LINE_MAX = 4096                             # one write; O_APPEND keeps a line whole up to this

DIALOG_TOOL = {"claude": "AskUserQuestion", "codex": "request_user_input"}
LEDGER_TYPES = {"offer", "pick", "use", "void", "decline", "settle"}
STOP_BLOCK = "stop_block"                   # the Stop loop breaker's count; no reader of consent reads it
LABEL_FORBIDDEN = (";", "&", "|", "\n", "\r", "`", "$(", "<", ">")
# state.py's own patterns, ASCII only: a label the hook accepts state.py accepts.
INTERPRETER_RE = re.compile(r"^python3?$")
INTERPRETER_FLAG_RE = re.compile(r"^-[IS]+$")
PUSH_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
NPX_PACKAGE_RE = re.compile(r"^riskrails@[0-9A-Za-z.+-]+$")
TS = "%Y-%m-%dT%H:%M:%SZ"

# hooks/guard/dialog.py -> the plugin root; the Stop reminder names its
# state.py. A label's state.py is checked by form only: on the plugin route the
# hooks run from the plugin cache while the skills run <home>'s state.py, and
# that state.py checks a pick's path against itself (R36.10).
PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PY = os.path.join(PLUGIN, "skills", "ai-task", "state.py")


def stamp(at):
    return at.strftime(TS)


def parse_ts(text):
    try:
        return datetime.strptime(text, TS).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def canonical(obj):
    """One spelling of a JSON value, for comparing what was offered with what came back."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# -- the switch ---------------------------------------------------------------

def dialog_policy(root):
    """.ai/policies/dialog.json when it says enabled: true, else None."""
    try:
        with open(os.path.join(root, ".ai", "policies", "dialog.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("enabled") is not True:
        return None

    def bounded(key, default, low, high):
        value = data.get(key, default)
        value = value if isinstance(value, int) and not isinstance(value, bool) else default
        return min(high, max(low, value))
    return {"window_seconds": bounded("window_seconds", *WINDOW),
            "stop_blocks_max": bounded("stop_blocks_max", STOP_BLOCKS_MAX, 0, STOP_BLOCKS_MAX)}


def runtime_home(runtime):
    if runtime == "codex":
        return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def dialog_tool(runtime):
    """The runtime's dialog tool when the installer verified it (profile.json
    dialog.tool, R36.19), else None: Codex stays off on an unverified version.
    Only an installer from 7b on writes dialog.tool, always under riskrails/."""
    try:
        with open(os.path.join(runtime_home(runtime), "riskrails", "profile.json"), encoding="utf-8") as fh:
            tool = (json.load(fh).get("dialog") or {}).get("tool")
    except (OSError, ValueError, AttributeError):
        return None
    return tool if runtime in DIALOG_TOOL and tool == DIALOG_TOOL[runtime] else None


def payload_runtime(payload, hook_file):
    """Codex's envelope carries turn_id, Claude's prompt_id (docs/dialog-spike.md);
    an envelope with neither is read from where the hook is installed."""
    if isinstance(payload, dict):
        if "turn_id" in payload or payload.get("tool_name") == DIALOG_TOOL["codex"]:
            return "codex"
        if "prompt_id" in payload or payload.get("tool_name") == DIALOG_TOOL["claude"]:
            return "claude"
    return "codex" if "%s.codex%s" % (os.sep, os.sep) in os.path.abspath(hook_file) else "claude"


def effective_switch(root, runtime, payload):
    """On only when the project says so, nobody declared the run unattended,
    the runtime's dialog tool is the verified one, this is the main session
    (no agent_id: a subagent cannot answer a dialog) and the payload has a
    session id to bind a pick to. Every other combination is today's route."""
    if not root or dialog_policy(root) is None:
        return False
    if os.environ.get("AI_UNATTENDED") or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return False
    if dialog_tool(runtime) is None or not isinstance(payload, dict):
        return False
    return not payload.get("agent_id") and bool(payload.get("session_id"))


# -- labels -------------------------------------------------------------------

def validate_label(label):
    """None when `label` may stand for a command (R36.4), else why not; the
    rule of state.py's validate_label, checked again when a pick is recorded."""
    if not isinstance(label, str) or not label or label != label.strip():
        return "a label is a non-empty string without surrounding blanks"
    if len(label) > LABEL_MAX or not label.isprintable():
        return "a label is at most %d printable characters" % LABEL_MAX
    if any(c in label for c in LABEL_FORBIDDEN):
        return "a label is one simple command"
    try:
        tokens = shlex.split(label)
    except ValueError:
        return "a label must split as a shell command"
    if tokens[:2] == ["git", "commit"]:
        return None
    if tokens[:2] == ["git", "push"]:
        refs_ok = len(tokens) == 4 and all(PUSH_REF_RE.match(t) and not t.startswith("-") for t in tokens[2:])
        return None if refs_ok else "a push label is exactly 'git push <remote> <branch>'"
    if tokens[:1] == ["npx"] and len(tokens) >= 3 and NPX_PACKAGE_RE.match(tokens[1]) and tokens[-1] == "--yes":
        return None
    if state_label_ok(tokens):
        return None
    return "a label starts with git commit, git push, a human-only state.py command or npx riskrails@<v>"


def state_label_ok(tokens):
    """python3 [-I|-S…] <…/state.py> approve|reject|profile set|verify --by|
    review --by|start --mode … --by."""
    if not tokens or not INTERPRETER_RE.match(tokens[0]):
        return False
    i = 1
    while i < len(tokens) and INTERPRETER_FLAG_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens) or os.path.basename(tokens[i]) != "state.py":
        return False
    rest = tokens[i + 1:]
    while rest[:1] in (["--root"], ["--runtime"]) and len(rest) >= 2:
        rest = rest[2:]
    if rest[:1] in (["approve"], ["reject"]) or rest[:2] == ["profile", "set"]:
        return True
    if rest[:1] in (["verify"], ["review"]):
        return "--by" in rest
    return rest[:1] == ["start"] and "--mode" in rest and "--by" in rest


# -- decisions ----------------------------------------------------------------

def read_decisions(root):
    """The open decisions of .ai/state/decision.json, in file order; [] when
    there is none or it cannot be read (only state.py writes it)."""
    try:
        with open(os.path.join(root, ".ai", "state", "decision.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError):
        return []
    opened = data.get("open") if isinstance(data, dict) else None
    return [d for d in opened if isinstance(d, dict) and d.get("id")] if isinstance(opened, list) else []


def decision_parts(decision):
    """state.py's dialog_questions: a command list is one multi-select unless a
    label holds ", " (a joined answer would be ambiguous); then one
    single-select per command, the safe choice first. [(options, multi)]."""
    options = [o for o in decision.get("options") or [] if isinstance(o, dict)]
    commands = [o for o in options if o.get("kind") == "command"]
    if decision.get("multi_select") and any(", " in str(o.get("label")) for o in commands):
        safe = [o for o in options if o.get("kind") == "choice"][:1]
        return [(safe + [o], False) for o in commands]
    return [(options, bool(decision.get("multi_select")))]


def offered(decisions, runtime):
    """What a dialog call for these decisions carries, question by question:
    (decision, options, the question as sent) — state.py's dialog_payload."""
    out = []
    for decision in decisions:
        parts = decision_parts(decision)
        for i, (options, multi) in enumerate(parts, 1):
            item = {"question": decision.get("question"), "header": decision.get("header"),
                    "options": [{"label": o.get("label"), "description": o.get("description") or (
                        "the session runs exactly this, once" if o.get("kind") == "command" else "nothing runs")}
                                for o in options]}
            if runtime == "codex":
                item = dict({"id": "%s%s" % (str(decision["id"]).lower(), "_%d" % i if len(parts) > 1 else "")},
                            **item)
            else:
                item["multiSelect"] = multi
            out.append((decision, options, item))
    return out


def question_key(question, runtime):
    """What identifies a question across the call: its text, header, labels
    with the descriptions the human read and, on Codex, its id. multiSelect is
    the model's to echo."""
    if not isinstance(question, dict):
        return None
    labels = [[o.get("label"), o.get("description")] if isinstance(o, dict) else None
              for o in question.get("options") or []]
    key = [question.get("question"), question.get("header"), labels]
    return canonical(key + [question.get("id")] if runtime == "codex" else key)


# -- the adapter --------------------------------------------------------------

def response_questions(runtime, payload):
    """The questions the dialog showed, in order."""
    source = payload.get("tool_response") if runtime == "claude" else None
    questions = source.get("questions") if isinstance(source, dict) else None
    if not isinstance(questions, list):
        tool_input = payload.get("tool_input")
        questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    return [q if isinstance(q, dict) else {} for q in questions] if isinstance(questions, list) else []


def adapt_response(runtime, payload):
    """The human's answers, one list of items per question shown, from
    tool_response — the harness's record, never the model's text (R36.6).

    Claude: answers keyed by question text, a multi-select's labels joined
    with ", "; two questions with one text cannot be told apart, so both read
    as unanswerable. Codex: tool_response is a JSON string,
    answers[<id>].answers is a list; "None of the above" and "user_note: …"
    are items like any other, and match no label."""
    questions = response_questions(runtime, payload)
    if runtime == "codex":
        try:
            answers = json.loads(payload.get("tool_response") or "").get("answers")
        except (ValueError, TypeError, AttributeError):
            answers = None
        out = []
        for q in questions:
            entry = answers.get(q.get("id")) if isinstance(answers, dict) else None
            items = entry.get("answers") if isinstance(entry, dict) else None
            out.append([i for i in items if isinstance(i, str)] if isinstance(items, list) else [])
        return out
    response = payload.get("tool_response")
    answers = response.get("answers") if isinstance(response, dict) else None
    texts = [q.get("question") for q in questions]
    out = []
    for q in questions:
        answer = answers.get(q.get("question")) if isinstance(answers, dict) else None
        if not isinstance(answer, str) or not answer or texts.count(q.get("question")) > 1:
            out.append([""] if texts.count(q.get("question")) > 1 else [])
        else:
            out.append(answer.split(", ") if q.get("multiSelect") else [answer])
    return out


# -- the ledger ---------------------------------------------------------------

def ledger_path(root):
    return os.path.join(root, ".ai", "state", "consent.jsonl")


@contextlib.contextmanager
def ledger_lock(root):
    """consent.lock by O_EXCL, portable where flock is not; a lock older than
    LOCK_STALE_S belongs to a writer that died and is taken over (R36.6)."""
    path = os.path.join(root, ".ai", "state", "consent.lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    deadline = time.time() + 2 * LOCK_STALE_S
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.stat(path).st_mtime > LOCK_STALE_S:
                    os.remove(path)
                    continue
            if time.time() > deadline:
                raise OSError("consent.lock is held and cannot be taken over") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


def ledger_append(root, line):
    """One line, one write, O_APPEND; called under ledger_lock. A line over
    LINE_MAX bytes is refused whole (OSError) rather than torn."""
    write_line(root, encode_line(line))


def encode_line(line):
    line = dict({"v": 1}, **line)
    line.setdefault("at", stamp(datetime.now(timezone.utc)))
    data = (json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > LINE_MAX:
        raise OSError("a consent line is over %d bytes" % LINE_MAX)
    return data


def write_line(root, data):
    fd = os.open(ledger_path(root), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, data) != len(data):
            raise OSError("short write to consent.jsonl")
    finally:
        os.close(fd)


def read_ledger(root, path=None, types=LEDGER_TYPES):
    """Every well-formed line of the given types, in order; a torn or foreign
    line is skipped, so a damaged ledger shows fewer picks, never more."""
    entries = []
    try:
        with open(path or ledger_path(root), encoding="utf-8") as fh:
            for raw in fh:
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("v") == 1 and entry.get("type") in types:
                    entries.append(entry)
    except OSError:
        return []
    return entries


def ledger_index(ledger):
    """(used {id: at}, voided ids, settled decisions, {decision: (call, picks of
    its latest dialog call)}) — what live_picks and pending read."""
    used, voided, settled, rounds = {}, set(), set(), {}
    for entry in ledger:
        kind = entry.get("type")
        if kind == "use":
            used[entry.get("id")] = parse_ts(entry.get("at"))
        elif kind == "void":
            voided.update(entry.get("ids") or [])
        elif kind == "settle":
            settled.add(entry.get("decision"))
        elif kind == "pick" and isinstance(entry.get("order"), int) and not isinstance(entry.get("order"), bool):
            call, chain = rounds.get(entry.get("decision"), (None, []))
            if chain and call == entry.get("tool_use_id"):
                chain.append(entry)
            else:
                rounds[entry.get("decision")] = (entry.get("tool_use_id"), [entry])
    return used, voided, settled, rounds


def live_picks(ledger, session, at):
    """The picks a command may consume at `at` (R36.7): of each decision's
    latest dialog call (one tool_use_id), unused, not voided, the decision not
    settled, same session, inside the window — and only the first unused one
    in its order. A later pick's window restarts when the one before is used."""
    used, voided, settled, rounds = ledger_index(ledger)
    live = []
    for decision, (_, chain) in rounds.items():
        if decision in settled:
            continue
        previous_use = None
        for pick in sorted(chain, key=lambda p: p["order"]):
            if pick.get("id") in used:
                previous_use = used[pick.get("id")]
                continue
            picked, expires = parse_ts(pick.get("at")), parse_ts(pick.get("expires_at"))
            if pick.get("id") in voided or pick.get("session") != session or not picked or not expires:
                break
            if previous_use and previous_use > picked:
                expires = previous_use + (expires - picked)
            if at <= expires:
                live.append(pick)
            break
    return live


def bound(decisions, runtime, session):
    """The decisions of this runtime and session: the one that opened a
    decision answers it (state.py records both; a decision with neither is
    everyone's, as before 7d2)."""
    return [d for d in decisions if d.get("runtime") in (None, "", runtime) and d.get("session") in (None, "", session)]


def pending(decisions, ledger):
    """The decisions still waiting (state.py's prune_decisions): not settled,
    and not every command pick of their latest dialog call used."""
    used, _, settled, rounds = ledger_index(ledger)
    out = []
    for decision in decisions:
        commands = {o.get("n") for o in decision.get("options") or [] if isinstance(o, dict) and o.get("kind") == "command"}
        picks = [p for p in rounds.get(decision.get("id"), (None, []))[1] if p.get("option") in commands]
        if decision.get("id") in settled or (picks and all(p.get("id") in used for p in picks)):
            continue
        out.append(decision)
    return out


def unused_picks(ledger, decision_ids, session):
    """The ids of this session's picks of the latest dialog call not yet used
    or voided, for every decision named: what a mismatch voids (R36.8)."""
    used, voided, _, rounds = ledger_index(ledger)
    return [p.get("id") for d in decision_ids for p in rounds.get(d, (None, []))[1]
            if p.get("session") == session and p.get("id") not in used and p.get("id") not in voided]


def unanswered_offer(ledger, session, tool_use_id, decision_ids):
    """This session's last offer when it named an open decision and no pick or
    decline of its call followed, seen from a later tool call: the recorder
    did not run (R36.15)."""
    offers = [e for e in ledger if e.get("type") == "offer" and e.get("session") == session]
    if not offers or not offers[-1].get("tool_use_id") or offers[-1].get("tool_use_id") == tool_use_id:
        return None
    call = offers[-1]["tool_use_id"]
    if any(e.get("type") in ("pick", "decline") and e.get("tool_use_id") == call for e in ledger):
        return None
    names = [d for d in offers[-1].get("decisions") or [] if d in decision_ids]
    return dict(offers[-1], decisions=names) if names else None


# git in command position — after a separator, NAME=value words and exec-like
# prefixes, with its global options — running commit or push as its subcommand.
# `git stash push`, `git grep commit`, `echo git commit` are not that.
GIT_CONSENT_RE = re.compile(
    r"(?:^|[|;&(\n]|\$\()\s*(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*|env|command|exec|nohup|time|sudo)\s+)*"
    r"git(?:\s+(?:-[Cc]\s+\S+|--?[A-Za-z][\w-]*(?:=\S+)?))*\s+(commit|push)(?=$|[\s|;&)])([^|;&\n)]*)")
HUMAN_VERB_RE = re.compile(r"(^|\s)(approve|reject)(\s|$)|(^|\s)profile\s+set(\s|$)|"
                           r"(^|\s)(verify|review|start)(\s.*)?\s--by(\s|=|$)")
DECISION_VERBS = ("show", "settle", "fallback")


def needs_consent(command):
    """A git commit or push that would change something: what the consent rule
    (R36.9) asks a pick for. Help and a push's dry run change nothing."""
    for match in GIT_CONSENT_RE.finditer(command):
        rest = match.group(2).split()
        if "--help" in rest or "-h" in rest:
            continue
        if match.group(1) == "push" and ("--dry-run" in rest or "-n" in rest):
            continue
        return True
    return False


def guarded(command):
    """git commit/push or a human-only state.py command: what a mismatch with
    the next live pick voids the picks for (R36.8)."""
    return bool(needs_consent(command)
                or (("state.py" in command or "STATE" in command) and HUMAN_VERB_RE.search(command)))


def decision_command(command):
    """`[python3 [-I…]] <…/state.py | $STATE> [--root X] decision show|settle|
    fallback …` as one simple command: the third thing the gate lets through."""
    if any(c in command for c in LABEL_FORBIDDEN):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    i = 0
    if tokens and INTERPRETER_RE.match(tokens[0]):
        i = 1
        while i < len(tokens) and INTERPRETER_FLAG_RE.match(tokens[i]):
            i += 1
    if i >= len(tokens) or not (os.path.basename(tokens[i]) == "state.py" or tokens[i] in ("$STATE", "${STATE}")):
        return False
    rest = tokens[i + 1:]
    while rest and ((rest[0] in ("--root", "--runtime") and len(rest) >= 2) or rest[0].startswith("--root=")):
        rest = rest[1:] if rest[0].startswith("--root=") else rest[2:]
    return len(rest) >= 2 and rest[0] == "decision" and rest[1] in DECISION_VERBS


def is_git_label(label):
    return (label or "").split()[:1] == ["git"]


def used_note(pick):
    """What a deny after the gate spent a git pick adds (review focus 1)."""
    return ("\n\nThe pick %s was used by this call and is spent; the command did not run. To ask the human "
            "again, open a new decision: state.py decision open --kind commit --command \"<command>\"."
            % pick.get("id"))


def next_live_pick(root, session_id, now):
    """The one pick a command may match now, or None: the live pick picked
    first (R36.7, 'only the next live pick in order')."""
    live = live_picks(read_ledger(root), session_id, now) if session_id else []
    if not live:
        return None
    return min(live, key=lambda p: (p.get("at") or "", p["order"]))


# -- the recorder (PostToolUse on the dialog tool) ----------------------------

def record(root, runtime, payload, now=None):
    """Turn one dialog call's answers into ledger lines (R36.6) and return them.

    Only questions equal to an open decision's count; a free dialog consents to
    nothing. Per decision: every answer item must be an offered label, else a
    `decline` (no answer, other text, an ambiguous join, a label that fails the
    rule) whose text is not stored. Commands picked become one `pick` each, in
    offered order; a decision answered only with a choice gets one `pick` of it.
    The caller has checked effective_switch()."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    policy = dialog_policy(root)
    decisions = read_decisions(root)
    if policy is None or not decisions or payload.get("tool_name") != DIALOG_TOOL.get(runtime):
        return []
    # A runtime's payload always carries both (7.0): without the call's id the
    # round cannot be told from another, and without the transcript `consent
    # audit` cannot check it.
    if not payload.get("tool_use_id") or not payload.get("transcript_path"):
        return []
    by_key = {question_key(item, runtime): (decision, options) for decision, options, item in
              offered(decisions, runtime)}
    answered = {}                             # decision id -> [decision, [(options, items)]]
    for question, items in zip(response_questions(runtime, payload), adapt_response(runtime, payload)):
        hit = by_key.get(question_key(question, runtime))
        if hit:
            answered.setdefault(hit[0]["id"], [hit[0], []])[1].append((hit[1], items))
    if not answered:
        return []
    common = {"session": payload.get("session_id"), "tool_use_id": payload["tool_use_id"]}
    lines = [dict({"type": "offer", "decisions": sorted(answered)}, **common)]
    for decision, parts in answered.values():
        picked, why = choose(decision, parts)
        if why:
            lines.append(dict({"type": "decline", "decision": decision["id"], "why": why}, **common))
            continue
        for order, option in enumerate(picked, 1):
            lines.append(dict({"type": "pick", "decision": decision["id"], "option": option.get("n"),
                               "order": order, "label": option.get("label")}, **common,
                              transcript=payload["transcript_path"], runtime=runtime,
                              at=stamp(now), expires_at=stamp(now + timedelta(seconds=policy["window_seconds"]))))
    written = []
    with ledger_lock(root):
        next_id = 1 + max([int(e["id"][1:]) for e in read_ledger(root) if e.get("type") == "pick" and
                           isinstance(e.get("id"), str) and e["id"][1:].isdigit()] or [0])
        for line in lines:
            if line["type"] == "pick":
                line = dict({"id": "C%d" % next_id}, **line)
                next_id += 1
            written.append(dict(line, at=line.get("at") or stamp(now)))
        # The round lands whole or not at all: every line is sized before the first write.
        for data in [encode_line(line) for line in written]:
            write_line(root, data)
    return [dict({"v": 1}, **line) for line in written]


def choose(decision, parts):
    """(options picked, None) or (None, why it is a decline)."""
    commands, choices = [], []
    for options, items in parts:
        if not items or items == [""]:
            return None, "ambiguous" if items == [""] else "no answer"
        labels = {o.get("label"): o for o in options}
        if any(item not in labels for item in items) or len(set(items)) != len(items):
            return None, "other text"
        for item in items:
            (commands if labels[item].get("kind") == "command" else choices).append(labels[item])
    split = len(decision_parts(decision)) > 1
    if commands and choices and not split:
        return None, "ambiguous"
    if commands:
        if any(validate_label(o.get("label")) for o in commands):
            return None, "label"
        return sorted({id(o): o for o in commands}.values(), key=lambda o: o.get("n") or 0), None
    return choices[:1], None


# -- Stop ---------------------------------------------------------------------

def dialog_payload(decisions, runtime):
    """The JSON the agent sends to the dialog tool, as state.py prints it."""
    return {"questions": [item for _, _, item in offered(decisions, runtime)][:4]}
