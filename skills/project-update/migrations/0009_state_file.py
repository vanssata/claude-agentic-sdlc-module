"""0009: the task's state file is `.ai/state/state.json`.

R34's contract half. 0008 shipped the expand half: the guards and state.py of
3.4b read `.ai/state/state.json` first and `current.json` otherwise, and write
the file where it is. This migration, run once such a version is installed,
moves a task in flight from `current.json` to `state.json`, and `state.py start`
opens every new task in `state.json`.

  * The move goes through MOVES like any other: no task in flight means no
    file, and nothing happens; a project that already holds `state.json` keeps
    it (a `current.json` beside it is a conflict for a human, not overwritten).
  * The file's bytes are not touched: every field of the task survives.
  * Reverting to 3.4b after the move still guards the task, because that
    version reads `state.json`.
"""

VERSION = 9
TITLE = "the task's state file is state.json"
STATE_LEGACY = ".ai/state/current.json"
STATE_NEW = ".ai/state/state.json"
MOVES = [(STATE_LEGACY, STATE_NEW)]


def plan(ctx):
    ctx.move(STATE_LEGACY, STATE_NEW)
