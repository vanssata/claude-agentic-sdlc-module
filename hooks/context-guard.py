#!/usr/bin/env python3
"""Context guard: keep long sessions short, and keep what matters across compaction.

One script, three Claude Code events:

UserPromptSubmit
    Reads the session's current context size from the transcript (the last
    main-chain response's input + cache read + cache write). At or above the
    warn threshold it shows a one-line warning, once per 10k band, and tells the
    model to suggest /clear when the prompt starts a new topic. At or above the
    block threshold it holds the prompt back once: sending the same prompt again
    lets it through, so the guard can be overridden but not ignored.

    Both thresholds follow the one knob the profile already sets. Auto-compaction
    fires about 33k tokens under `autoCompactWindow` (measured over 133 automatic
    compactions: a 150 000 window compacts at 115–125k, 117k most often), and
    Claude Code caps that window at the model's own: 200k, or 1M for a [1m] model.
    The guard warns at 80% of that point and blocks at 120% of it, which is only
    reached when auto-compaction is off or did not run. An 800 000 window therefore
    means, on a 200k model, compaction near 167k and a warning from 133k; on a [1m]
    model, compaction near 767k, a warning from 613k and a block from 920k.

PreCompact
    Writes a deterministic snapshot of the session — files edited, the latest
    user instructions verbatim, the todo list, git branch and status, and the
    .ai/ task state — to the state directory. No model is involved, so nothing
    in it depends on what the summary chose to keep. It also prints what the
    summary must keep; Claude Code appends a PreCompact hook's stdout to the
    compaction instructions.

SessionStart
    Records the session's model, which UserPromptSubmit does not carry, and writes
    .ai/state/session.json — the sidecar that tells state.py which runtime is driving
    and when the human last took a turn. With a task in flight it injects the handoff
    and the pending questions, so a session that has just lost its context reads the
    task before it reads anything else. It also puts the snapshot back, and consumes
    it: the snapshot belongs to the compaction it was written for, and a startup or a
    /clear simply finds nothing to put back.

Both runtimes: the script derives which one it serves from its own location, and no
decision here depends on a payload key. The transcript-derived snapshot stays
Claude-only — it is built from a Claude transcript and the rollout format differs —
while handoff.md, the questions and session.json cross unchanged. Fails open: an
unreadable payload or transcript never blocks a prompt and never breaks a compaction.

Environment:
    AI_CONTEXT_WARN_TOKENS    warn threshold in tokens, instead of 80% (0 turns warnings off)
    AI_CONTEXT_BLOCK_TOKENS   block threshold in tokens, instead of 120% (0 turns blocking off)
    AI_CONTEXT_GUARD_STATE    state directory, default ~/.claude/state/context-guard
    AI_HOOK_RUNTIME           claude|codex, for tests: normally the script's own path decides
    AI_HANDOFF_NO_PROMPT      1 keeps the user's prompt out of .ai/state/session.json
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

CHUNK_BYTES = 1024 * 1024          # the transcript is read backwards in blocks of this size
SCAN_LIMIT = 64 * 1024 * 1024      # how far back to look for the last response
SNAPSHOT_MAX_CHARS = 12000         # ~3k tokens re-injected after a compaction
SNAPSHOT_FRESH_SECONDS = 3600
HANDOFF_INJECT_MAX_CHARS = 8000    # the cross-runtime block; Codex allows ~2.5k tokens
STATE_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "skills", "ai-task", "state.py")
PROMPTS_KEPT = 5
PROMPT_MAX_CHARS = 800
FILES_KEPT = 40
STATUS_LINES = 40
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

DEFAULT_WINDOW = 800000            # profiles/max.json; capped per model below
MODEL_WINDOW, MODEL_WINDOW_1M = 200000, 1000000
COMPACT_RESERVE = 33000            # auto-compaction fires this far under the window
WARN_PCT, BLOCK_PCT = 80, 120      # of the point where auto-compaction fires

COMPACT_INSTRUCTIONS = """\
Keep in the summary: every decision made and the reason for it; the options that
were rejected and why; exact file paths and function, class and command names;
what was tried and failed, with the error text; open questions and the next step;
and the user's latest instructions word for word. Leave out tool output that has
already been acted on."""


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def positive_int(value):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def user_settings():
    try:
        with open(os.path.join(config_dir(), "settings.json"), encoding="utf-8") as fh:
            settings = json.load(fh)
        return settings if isinstance(settings, dict) else {}
    except (OSError, ValueError):
        return {}


def session_model(session_id):
    """UserPromptSubmit carries no model, SessionStart may: on_session_start records it.
    Headless `claude -p` sends SessionStart without one (seen on 2.1.276), and a session
    that predates the record has none either; both fall back to the settings default."""
    try:
        with open(state_path(session_id, "model"), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return str(user_settings().get("model") or "")


def model_window(session_id, ctx):
    """Only the [1m] variants take more than 200k; a context already past 200k proves one."""
    if "[1m]" in session_model(session_id).lower() or (ctx or 0) > MODEL_WINDOW:
        return MODEL_WINDOW_1M
    return MODEL_WINDOW


def compact_window(session_id, ctx):
    """The window Claude Code compacts against: the env var wins over settings.json, and
    Claude Code caps either at the model's window (\"capped to … by model\" in /autocompact),
    so one 800k setting compacts a 1M session near 767k and a 200k session near 167k."""
    window = positive_int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"))
    if not window:
        window = positive_int(user_settings().get("autoCompactWindow"))
    window = window if window > COMPACT_RESERVE else DEFAULT_WINDOW
    return min(window, model_window(session_id, ctx))


def thresholds(session_id, ctx):
    fires_at = compact_window(session_id, ctx) - COMPACT_RESERVE

    def one(name, pct):
        raw = os.environ.get(name, "").strip()
        return positive_int(raw) if raw.lstrip("-").isdigit() else fires_at * pct // 100

    return one("AI_CONTEXT_WARN_TOKENS", WARN_PCT), one("AI_CONTEXT_BLOCK_TOKENS", BLOCK_PCT)


def state_dir():
    base = os.environ.get("AI_CONTEXT_GUARD_STATE")
    if not base:
        base = os.path.join(config_dir(), "state", "context-guard")
    os.makedirs(base, exist_ok=True)
    return base


def state_path(session_id, ext):
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "unknown"
    return os.path.join(state_dir(), f"{safe}.{ext}")


def emit(obj):
    print(json.dumps(obj))
    sys.exit(0)


# ------------------------------------------------------------ transcript reading

def lines_from_end(path):
    """Whole lines, last first. One line of pasted tool output can be megabytes long,
    so a fixed-size tail is not enough: read backwards until the caller stops asking."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        position = fh.tell()
        stop = max(0, position - SCAN_LIMIT)
        pieces = []                 # the end of a line whose start is further back
        while position > stop:
            step = min(CHUNK_BYTES, position - stop)
            position -= step
            fh.seek(position)
            parts = fh.read(step).split(b"\n")
            if len(parts) == 1:
                pieces.append(parts[0])
                continue
            yield parts[-1] + b"".join(reversed(pieces))
            yield from reversed(parts[1:-1])
            pieces = [parts[0]]
        if position == 0:           # otherwise what is left is a line cut in half
            yield b"".join(reversed(pieces))


def current_context(path):
    """Tokens in context at the last main-chain response, or None after a compaction."""
    for raw in lines_from_end(path):
        if b'"compact_boundary"' not in raw and b'"usage"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            return None             # the numbers before it describe the old context
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        total = sum(positive_int(usage.get(key)) for key in
                    ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        if total:                   # a synthetic error entry carries zeros: keep looking
            return total
    return None


REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
COMMAND = re.compile(r"<command-name>(.*?)</command-name>", re.S)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def prompt_text(message):
    content = message.get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = "\n".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = REMINDER.sub("", content).strip()
    # only a wrapper at the very start is a slash command: a prompt may quote these tags
    command = COMMAND.search(text) if text.startswith(("<command-name>", "<command-message>")) else None
    if command:                     # "/ai-task fix the export" is an instruction; a bare "/model" is not
        name, args = command.group(1).strip(), (COMMAND_ARGS.search(text) or [None, ""])[1].strip()
        return f"{name} {args}" if args else None
    # local command output, caveats, interruptions
    if not text or text.startswith("<") or text.startswith("[Request interrupted"):
        return None
    return text


def scan_session(path):
    files, prompts, todos = {}, [], None
    with open(path, "rb") as fh:
        for raw in fh:
            if b'"tool_use"' not in raw and b'"user"' not in raw:
                continue
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if entry.get("isSidechain"):
                continue
            message = entry.get("message") or {}
            if entry.get("type") == "user":
                if entry.get("isMeta") or entry.get("isCompactSummary"):
                    continue
                text = prompt_text(message)
                if text:
                    prompts.append(text)
            elif entry.get("type") == "assistant":
                for block in message.get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name, args = block.get("name"), block.get("input") or {}
                    if name in EDIT_TOOLS:
                        target = args.get("file_path") or args.get("notebook_path")
                        if target:
                            files.pop(target, None)
                            files[target] = name       # re-insert: most recent last
                    elif name == "TodoWrite" and isinstance(args.get("todos"), list):
                        todos = args["todos"]
    return files, prompts[-PROMPTS_KEPT:], todos


def run(cmd, cwd):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=3, check=False)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ------------------------------------------------------------- the .ai/ project

def hook_runtime():
    """Which runtime this copy serves. The same file is installed into
    ~/.claude/hooks/ and ~/.codex/hooks/, so its own location is the answer —
    no payload key is consulted, here or anywhere else (R7). AI_HOOK_RUNTIME is
    a test override, and it comes first so a fixture can force either side."""
    override = os.environ.get("AI_HOOK_RUNTIME")
    if override in ("claude", "codex"):
        return override
    return "codex" if f"{os.sep}.codex{os.sep}" in os.path.abspath(__file__) else "claude"


def ai_root(cwd):
    """The project the session is in, or None. cwd falls back to the process's
    own, which is where the hook starts anyway."""
    directory = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(directory, ".ai")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def task_in_flight(root):
    return bool(root) and os.path.exists(os.path.join(root, ".ai", "state", "current.json"))


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_session(root, updates):
    """.ai/state/session.json (I5): the sidecar this hook owns. current.json has
    two writers by contract and the hook is not one of them. Atomic, and silent
    about its own failures — a session that cannot be recorded must still start."""
    path = os.path.join(root, ".ai", "state", "session.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    data.update(updates)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def state_py(root, *args):
    """state.py is the only thing that renders a handoff or reads the questions.
    Three seconds inside a fifteen-second hook, and an empty string on anything
    at all going wrong: the guard fails open."""
    if not os.path.exists(STATE_PY):
        return ""
    return run([sys.executable or "python3", STATE_PY, "--root", root,
                "--runtime", hook_runtime(), *args], root)


def handoff_block(root, reason):
    return state_py(root, "handoff", "--print", "--reason", reason)


def task_frame(root, reason):
    """What a session that has just lost its context needs before anything else.
    Capped, with the questions collapsed to one line when the budget is tight —
    the Codex additionalContext limit is about 2 500 tokens."""
    handoff = handoff_block(root, reason)
    if not handoff:
        return ""
    parts = ["# Task in flight — read this before anything else "
             "(written by state.py handoff, not by a model)", handoff]
    pending = [line for line in handoff.splitlines() if line.startswith("Pending questions: ")]
    if pending and not pending[0].endswith(": none"):
        ids = pending[0].split(": ", 1)[1].split(" — ")[0]
        count = len(ids.split(", "))
        prose = state_py(root, "questions", "--pending")
        parts.append(f"## Pending questions ({count}) — answer with `state.py answer …` "
                     "or fill the file")
        parts.append(prose or ids)
    parts.append("Resume with: /ai-task --resume")
    text = "\n".join(parts)
    if len(text) > HANDOFF_INJECT_MAX_CHARS and len(parts) > 3:
        parts[-2:-1] = [ids]                  # the questions collapse to their ids
        text = "\n".join(parts)
    return text[:HANDOFF_INJECT_MAX_CHARS]


def build_snapshot(payload, handoff=""):
    transcript, cwd = payload.get("transcript_path"), payload.get("cwd") or os.getcwd()
    files, prompts, todos = scan_session(transcript)
    parts = ["# Session state before compaction (written by context-guard, not by the summary)",
             "Trust this over the summary where they differ."]

    if prompts:
        parts.append("\n## Latest user instructions, verbatim (oldest first)")
        for text in prompts:
            cut = text if len(text) <= PROMPT_MAX_CHARS else text[:PROMPT_MAX_CHARS] + " […]"
            parts.append("- " + cut.replace("\n", "\n  "))

    if files:
        parts.append("\n## Files edited in this session (most recent last)")
        for target in list(files)[-FILES_KEPT:]:
            shown = os.path.relpath(target, cwd) if target.startswith(cwd.rstrip("/") + "/") else target
            parts.append(f"- {shown}")

    if todos:
        parts.append("\n## Todo list")
        for item in todos:
            parts.append(f"- [{item.get('status', '?')}] {item.get('content', '')}")

    branch = run(["git", "branch", "--show-current"], cwd)
    status = run(["git", "status", "--short"], cwd)
    if branch or status:
        parts.append("\n## Git")
        if branch:
            parts.append(f"branch: {branch}")
        if status:
            lines = status.splitlines()
            parts.extend(lines[:STATUS_LINES])
            if len(lines) > STATUS_LINES:
                parts.append(f"… {len(lines) - STATUS_LINES} more")

    if handoff:
        # handoff.md, verbatim, in place of a JSON dump: one owner per fact, and
        # this one is rendered by state.py from the state, the journal,
        # questions.md and session.json.
        parts.append("\n" + handoff)

    text = "\n".join(parts)
    if len(text) > SNAPSHOT_MAX_CHARS:
        text = text[:SNAPSHOT_MAX_CHARS] + "\n[…snapshot truncated]"
    return text


# ------------------------------------------------------------------- the events

def on_prompt(payload):
    transcript = payload.get("transcript_path")
    session = payload.get("session_id") or "unknown"
    root = ai_root(payload.get("cwd"))
    if task_in_flight(root):
        # The evidence that a human took a turn — what the gate's file route
        # (R13) reads back. Recorded before any early exit below.
        update = {"runtime": hook_runtime(), "session_id": session, "last_prompt_at": stamp()}
        if not os.environ.get("AI_HANDOFF_NO_PROMPT"):
            update["last_prompt"] = (payload.get("prompt") or "")[:PROMPT_MAX_CHARS]
        write_session(root, update)
    ctx = current_context(transcript) if transcript else None
    marker = state_path(session, "json")
    try:
        with open(marker, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}

    def save():
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    warn, block = thresholds(session, ctx)
    if ctx is None or (not warn or ctx < warn) and (not block or ctx < block):
        if state:
            os.remove(marker)       # back under the threshold, e.g. after a compaction
        sys.exit(0)

    k = round(ctx / 1000)
    if block and ctx >= block:
        digest = hashlib.sha256((payload.get("prompt") or "").encode()).hexdigest()
        if state.get("blocked") != digest:
            state["blocked"] = digest
            save()
            emit({"decision": "block", "reason": (
                f"Context is {k}k tokens, past the {block // 1000}k limit: every turn re-reads all of it. "
                "Run /compact (or /clear if this is a new task) and send the prompt again. "
                "To go ahead anyway, send the same prompt once more.")})
        state.pop("blocked")
        save()
        sys.exit(0)             # the same prompt a second time: the user has decided

    band = ctx // 10000
    if band <= state.get("band", -1):
        sys.exit(0)
    state["band"] = band
    save()
    emit({
        "systemMessage": f"Context is {k}k tokens (warning from {warn // 1000}k). "
                         "/compact keeps the thread, /clear starts a new task.",
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"context-guard: the session context is {k}k tokens. If this prompt starts a "
                "different task from the one so far, say so in one line and suggest /clear "
                "before doing the work. Otherwise continue and do not mention it."),
        },
    })


def on_precompact(payload):
    print(COMPACT_INSTRUCTIONS)     # exit 0: stdout is appended to the compaction instructions
    root = ai_root(payload.get("cwd"))
    handoff = handoff_block(root, "precompact") if task_in_flight(root) else ""
    if payload.get("transcript_path"):
        with open(state_path(payload.get("session_id") or "unknown", "md"), "w", encoding="utf-8") as fh:
            fh.write(build_snapshot(payload, handoff))
    sys.exit(0)


def take_snapshot(session):
    """The transcript-derived supplement PreCompact left behind, if it is fresh.

    Claude only — it is built from a Claude transcript — and consumed when it is
    read, so it goes back into the session it belongs to and into no other. That
    is what lets this hook run on every source without asking the payload which
    one it is (R7): a startup or a /clear simply finds nothing to put back."""
    if hook_runtime() != "claude":
        return ""
    path = state_path(session, "md")
    try:
        if time.time() - os.path.getmtime(path) > SNAPSHOT_FRESH_SECONDS:
            raise OSError("stale")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    try:
        os.remove(path)
    except OSError:
        pass
    return text


def on_session_start(payload):
    session = payload.get("session_id") or "unknown"
    model = payload.get("model")
    if isinstance(model, str) and model:
        with open(state_path(session, "model"), "w", encoding="utf-8") as fh:
            fh.write(model)

    root = ai_root(payload.get("cwd"))
    frame = ""
    if root:
        write_session(root, {"runtime": hook_runtime(), "session_id": session,
                             "source": payload.get("source") or "unknown",
                             "started_at": stamp()})
        frame = task_frame(root, "session-start") if task_in_flight(root) else ""

    text = "\n\n".join(part for part in (frame, take_snapshot(session)) if part)
    if not text:
        sys.exit(0)
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})


def main():
    try:
        payload = json.load(sys.stdin)
        handler = {"UserPromptSubmit": on_prompt, "PreCompact": on_precompact,
                   "SessionStart": on_session_start}.get(payload.get("hook_event_name"))
        if handler:
            handler(payload)
    except Exception:  # pylint: disable=broad-exception-caught  # fail open: the guard never blocks work by crashing
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
