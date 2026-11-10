#!/usr/bin/env python3
"""Task state for /rr-build — the small, machine-readable record of one task.

Why a file and not the conversation: a conversation is expensive to re-read and
impossible for a hook to consult. This file is what ai-scope-guard enforces
against, what /rr-status reports, and what lets a task survive a /clear or a
crash. It holds facts, never transcripts.

Everything is stdlib. Writes are atomic (temp file + os.replace), so a hook that
reads the file while a stage is being recorded never sees half a document.

Every state change is also appended to .ai/reports/<task-id>/events.jsonl, the
append-only journal /rr-status and /rr-status --cost read at zero model cost. The
journal is best effort by contract: a line that cannot be written never fails
the command that emitted it, and nothing here depends on it being lossless.
history[] keeps its exact shape and its original event names beside it.

Usage:
  state.py start  --goal G --workflow W --files a,b [--tests t] [--declare axis=n:"why"]...
                  [--mode M --by WHO [--why TEXT]] [--steps "id:a,b:t;..." | --plan-file F.json]
                  [--batch --by WHO | --no-batch]  the batch loop of /rr-build-all (weight.json batch.*);
                                         a plan-file step may name "after": ["s1", ...]
  state.py start  --amend --files "+c,+d" --why TEXT     widen the task in place (R25)
  state.py verify --scope step|suite|e2e|all [--files a,b] [--expect fail]
                  [--e2e not-applicable WHY] [--after-fix WHAT] [--by WHO]
  state.py review --verdict pass|pass_with_findings|blockers_open --tier BALANCED|STRONG
                  --report -|FILE [--focus security] [--by WHO]  |  review --closes "H1,M2"
  state.py close  [--abandon]            two facts, the mode table, the gate, the archive
  state.py step-done <id>                a multi-step guarded or full task
  state.py steps  [--ready] [--json]     the steps, their status and after; --ready prints the next wave
  state.py batch  on|off --by WHO [--why TEXT]   off: the standard loop and budgets from here (anyone);
                                         on: lowers the rigor — the human's, in their own terminal
  state.py status [--json]               what /rr-status prints
  state.py ask    "<question>" --option "A: text" [--option ...] [--recommend A] [--topic S]
  state.py ask    --batch FILE.json [--topic SLUG]
  state.py answer Q1=B [Q2=X:"text"] [--by NAME] [--via picker|prose] | --prose "1B 2A 3: text"
  state.py questions [--pending] [--sync] [--format md|prose|json] [--topic SLUG]
                                         --sync records the [Answer]: lines a human filled in
                                         task.md §Questions, the gate's file route among them
  state.py handoff [--print] [--reason stage|precompact|manual|session-start]
  state.py handoff --to claude|codex [--for continue|review] [--why TEXT]
                                         move the task to the other runtime: it must resume there
                                         (exit 7 RUNTIME_HANDOFF_PENDING from anywhere else)
  state.py profile [--field a.b.c] [--tier FAST|BALANCED|STRONG|EXPERT] [--other] [--json]
                                         the installed plan's tables (read-only, no task needed)
  state.py weight --files a,b [--goal G] [--declare axis=n:"why"]... [--json|--long]
  state.py weight --mirror               six axes and a mode, read-only (no task needed);
                                         --mirror writes .ai/policies/weight.md from weight.json
  state.py event  <type> [--detail TEXT] [--data JSON]   # for hooks; type must be in EVENT_TYPES
  state.py approve --by NAME [--confirm "<what it does>"] [--note TEXT]
                                         outside the agent: a TTY, or AI_UNATTENDED;
                                         full_irreversible: the confirm names every operation
  state.py reject  --by NAME --why TEXT

A task the old surface started (schema < 7; its commands were removed in
redesign 2.6) answers status, handoff and questions, and close --abandon drops
it; every other command refuses it.
"""

# pylint: disable=wrong-import-position
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from rr_state import fs
except ImportError:
    sys.exit("rr_state/ is missing beside state.py: re-run `npx riskrails`")
fs.ENTRY = os.path.abspath(__file__)    # R6a: the one path the package prints and compares
from rr_state.cli import main

if __name__ == "__main__":
    main()
