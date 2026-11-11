#!/usr/bin/env python3
"""Bring a project's RiskRails files up to date with the installed plugin.

  update.py [project-dir] [--apply [--confirm-delete NAME] [--confirm-cleanup NAME]] [--check [--budget]]

Default is a dry run: print what would change, write nothing.
  --apply   write the changes
  --check   print one line and exit 1 when an update is pending
  --check --budget   print one line per root instruction file over its byte
            budget (block over `project`, file over `skeleton`) and exit 1
  --confirm-delete NAME   a human confirms this run's gated rows (`regenerate?`,
            `delete?`); refused (exit 5, CONFIRM_REFUSED) unless a terminal outside
            Claude Code or Codex (no agent-session marker) or AI_UNATTENDED
  --confirm-cleanup NAME  the same for the [cleanup] rows

Exit codes:
  0  done (or, with --check, the project is current)
  1  --check: an update is pending; --check --budget: a file is over budget
  2  usage error, missing templates, .ai/VERSION unreadable or newer than the plugin
  3  an apply aborted part-way; nothing after the failing item was written
  5  refused: --confirm-* without a human (CONFIRM_REFUSED on stdout line 1)
  6  a file this update keeps cannot be read (KEPT_UNREADABLE on stdout line 1); nothing written

This version regenerates its own files and converts nothing, except one split:
a project that still has the mixed files gets .ai/policies/verification.md (the
command lines of testing.md, verbatim) and .ai/policies/weight.project.json
(what its weight.json changed against the plugin's table) once, when they are absent.

What it does, per file:
  GENERATED  .ai/AGENTS.md, .ai/VERSION, .ai/policies/{path-guard.json, coding.md,
    safety.md, security.md, testing.md, weight.md}, .ai/rules/README.md,
    .ai/state/README.md, <runtime>/memory/README.md, the managed block of each
    instruction file: rewritten from the plugin. A copy that is a version the plugin
    once shipped is replaced (regenerate); an edited one waits for --confirm-delete
    (regenerate?) and its original is kept under .ai/reports/project-update-<date>/original/.
  KEPT  .ai/project, .ai/reports, .ai/memory, .ai/state, docs/sdlc, verification.md,
    weight.project.json, dialog.json, memory.json, .ai/local/memory, edited shared
    overrides, the text outside the managed blocks, .claude/settings.json,
    .codex/config.toml, .gitignore (entries appended): never rewritten.
  REMOVED  .ai/rules/<slug>.md, .ai/local/plugin-update/, the old weight.json after its
    split, an unedited copy of a shared file: delete?, gated, with a copy in original/.
  [cleanup] rows are unchanged: proposals only, settled with --confirm-cleanup.

A project uses the runtime(s) it declares: CLAUDE.md or .claude/ means Claude
Code, AGENTS.md or .codex/ means Codex, both means both. A project that declares
neither gets the runtime this copy of the plugin was installed for.
"""
import os
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ in an installed plugin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from rr_update import cli
except ImportError:
    sys.exit("rr_update/ is missing beside update.py: re-run `npx riskrails`")

if __name__ == "__main__":
    sys.exit(cli.main())
