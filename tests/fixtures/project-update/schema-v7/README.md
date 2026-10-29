A schema-7 project, as `tests/test_project_update.py::TestMigration0008` builds it:
today's `scaffold-ai.sh` output with these files laid over it.

- `.ai/VERSION` — 7, the schema before the rename (R35).

The test turns the rest back to schema 7 itself, so the fixture never goes
stale when a template changes: the managed block's markers and the router's
routes back to `claude-agentic`, and — for the in-flight variant — a task
started with today's `state.py`, which writes `current.json` (R34 moves the
file in a later task).
