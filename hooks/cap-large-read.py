#!/usr/bin/env python3
"""PreToolUse hook: refuse unbounded Read calls on large files.

The main session re-reads its whole context on every turn, so one 500K-character
Read is paid for again on every subsequent turn of the session. This hook does
not cap what can be read — it only insists that reading something large is an
explicit act: pass `limit`, and the read goes through untouched.
"""
import json
import os
import sys

MAX_LINES = int(os.environ.get("CLAUDE_READ_MAX_LINES", "4000"))
MAX_BYTES = int(os.environ.get("CLAUDE_READ_MAX_BYTES", "250000"))

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
    except Exception:
        allow()

    if payload.get("tool_name") != "Read":
        allow()

    tool_input = payload.get("tool_input") or {}
    if tool_input.get("limit"):          # an explicit range is always honoured
        allow()

    path = tool_input.get("file_path")
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
        f"  - Read with an explicit offset and limit (any limit is allowed through)\n"
        "  - send a subagent (Explore for code, log-reader for logs) and keep its summary"
    )


if __name__ == "__main__":
    main()
