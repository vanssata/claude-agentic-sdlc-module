#!/usr/bin/env python3
"""PreToolUse hook: refuse unbounded Read calls on large files.

The main session re-reads its whole context on every turn, so one 500K-character
Read is paid for again on every subsequent turn of the session. This hook does
not cap what can be read — it only insists that reading something large is an
explicit act: pass a `limit` within the budget, and the read goes through
untouched. A `limit` larger than the budget is refused like an unbounded read:
the point is the size that lands in the context, not the presence of the
argument.

Claude Code only. It matches a tool named `Read` that takes a `file_path` and an
optional `limit`. Codex has no equivalent on the hook path: its file reads go
through the shell, where there is no `limit` argument to ask for and no file
path to size up before the command runs, so the installer does not register this
hook for Codex. The limits are read from AI_READ_MAX_LINES / AI_READ_MAX_BYTES,
with the original CLAUDE_READ_MAX_* names still honoured.
"""
import json
import os
import sys


def limit_from_env(neutral, legacy, default):
    for name in (neutral, legacy):
        value = os.environ.get(name)
        if value:
            try:
                return int(value)
            except ValueError:
                pass
    return default


MAX_LINES = limit_from_env("AI_READ_MAX_LINES", "CLAUDE_READ_MAX_LINES", 4000)
MAX_BYTES = limit_from_env("AI_READ_MAX_BYTES", "CLAUDE_READ_MAX_BYTES", 250000)

# Read handles these as media, not text — line and byte counts say nothing useful.
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".pdf", ".ipynb"}


def allow():
    sys.exit(0)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:  # pylint: disable=broad-exception-caught  # fail open: unreadable payload never blocks a Read
        allow()

    if payload.get("tool_name") != "Read":
        allow()

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path")
    limit = tool_input.get("limit")
    if limit:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            allow()
        if limit <= MAX_LINES:           # an explicit, bounded range is honoured
            allow()
        deny(
            f"limit={limit} is larger than the {MAX_LINES}-line budget, so this read costs "
            "the same as an unbounded one — and the context is re-read on every turn.\n"
            "Do one of these instead:\n"
            f"  - grep -n 'pattern' {path}  then Read only the ranges that matched\n"
            f"  - Read with a limit of {MAX_LINES} or less\n"
            "  - send a FAST reader (Explore for code, log-reader for logs) and keep only "
            "the excerpt it returns"
        )

    if not path or os.path.splitext(path)[1].lower() in BINARY:
        allow()

    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            lines = sum(1 for _ in fh)
    except OSError:
        allow()

    if size <= MAX_BYTES and lines <= MAX_LINES:
        allow()

    deny(
        f"{os.path.basename(path)} is {lines} lines / {size // 1000}KB. Reading it whole "
        f"costs roughly {size // 4000}K tokens on this turn and on every turn after it, "
        "because the context is re-read each time.\n"
        "Do one of these instead:\n"
        f"  - grep -n 'pattern' {path}  then Read only the ranges that matched\n"
        f"  - Read with an explicit offset and a limit of {MAX_LINES} or less\n"
        "  - send a FAST reader on the cheapest model (Explore for code, log-reader for "
        "logs and test output) and keep only the excerpt it returns — the ranges with "
        "file:line, never the file"
    )


if __name__ == "__main__":
    main()
