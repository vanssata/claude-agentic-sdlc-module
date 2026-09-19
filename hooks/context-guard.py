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
    compactions: a 150 000 window compacts at 115–125k, 117k most often). The
    guard warns at 80% of that point and blocks at 120% of it, which is only
    reached when auto-compaction is off or did not run. A 133 000 window therefore means
    compaction near 100k, a warning from 80k and a block from 120k.

PreCompact
    Writes a deterministic snapshot of the session — files edited, the latest
    user instructions verbatim, the todo list, git branch and status, and the
    .ai/ task state — to the state directory. No model is involved, so nothing
    in it depends on what the summary chose to keep. It also prints what the
    summary must keep; Claude Code appends a PreCompact hook's stdout to the
    compaction instructions.

SessionStart (source "compact")
    Puts that snapshot back into the context right after the summary. On
    startup, resume and /clear it does nothing: those are meant to start clean.

Claude only; Codex has no compaction events. Fails open: an unreadable payload
or transcript never blocks a prompt and never breaks a compaction.

Environment:
    AI_CONTEXT_WARN_TOKENS    warn threshold in tokens, instead of 80% (0 turns warnings off)
    AI_CONTEXT_BLOCK_TOKENS   block threshold in tokens, instead of 120% (0 turns blocking off)
    AI_CONTEXT_GUARD_STATE    state directory, default ~/.claude/state/context-guard
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
PROMPTS_KEPT = 5
PROMPT_MAX_CHARS = 800
FILES_KEPT = 40
STATUS_LINES = 40
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

DEFAULT_WINDOW = 133000            # profiles/max.json
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


def compact_window():
    """The window Claude Code compacts against: the env var wins over settings.json."""
    window = positive_int(os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"))
    if not window:
        try:
            with open(os.path.join(config_dir(), "settings.json"), encoding="utf-8") as fh:
                window = positive_int(json.load(fh).get("autoCompactWindow"))
        except (OSError, ValueError, AttributeError):
            window = 0
    return window if window > COMPACT_RESERVE else DEFAULT_WINDOW


def thresholds():
    fires_at = compact_window() - COMPACT_RESERVE
    found = []
    for name, pct in (("AI_CONTEXT_WARN_TOKENS", WARN_PCT), ("AI_CONTEXT_BLOCK_TOKENS", BLOCK_PCT)):
        raw = os.environ.get(name, "").strip()
        found.append(positive_int(raw) if raw.lstrip("-").isdigit() else fires_at * pct // 100)
    return found


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


def build_snapshot(payload):
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

    task_state = os.path.join(cwd, ".ai", "state", "current.json")
    try:
        with open(task_state, encoding="utf-8") as fh:
            task = json.dumps(json.load(fh), ensure_ascii=False)
        parts.append("\n## .ai/state/current.json")
        parts.append(task[:2000] + (" […]" if len(task) > 2000 else ""))
    except (OSError, ValueError):
        pass

    text = "\n".join(parts)
    if len(text) > SNAPSHOT_MAX_CHARS:
        text = text[:SNAPSHOT_MAX_CHARS] + "\n[…snapshot truncated]"
    return text


# ------------------------------------------------------------------- the events

def on_prompt(payload):
    transcript = payload.get("transcript_path")
    session = payload.get("session_id") or "unknown"
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

    warn, block = thresholds()
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
    if payload.get("transcript_path"):
        with open(state_path(payload.get("session_id") or "unknown", "md"), "w", encoding="utf-8") as fh:
            fh.write(build_snapshot(payload))
    sys.exit(0)


def on_session_start(payload):
    if payload.get("source") != "compact":
        sys.exit(0)
    snapshot_file = state_path(payload.get("session_id") or "unknown", "md")
    try:
        if time.time() - os.path.getmtime(snapshot_file) > SNAPSHOT_FRESH_SECONDS:
            raise OSError("stale")
        with open(snapshot_file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        if not payload.get("transcript_path"):
            sys.exit(0)
        text = build_snapshot(payload)   # PreCompact did not run; the transcript still has it all
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})


def main():
    try:
        payload = json.load(sys.stdin)
        handler = {"UserPromptSubmit": on_prompt, "PreCompact": on_precompact,
                   "SessionStart": on_session_start}.get(payload.get("hook_event_name"))
        if handler:
            handler(payload)
    except SystemExit:
        raise
    except Exception:  # pylint: disable=broad-exception-caught  # fail open: the guard never blocks work by crashing
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
