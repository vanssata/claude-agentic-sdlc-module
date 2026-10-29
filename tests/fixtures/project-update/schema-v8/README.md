A schema-8 project, as `tests/test_project_update.py::TestMigration0009` builds it:
today's `scaffold-ai.sh` output with these files laid over it.

- `.ai/VERSION` — 8, the schema before the state file moves (R34).

The test starts a task in flight with today's `state.py`, then puts the state file
back under its schema-8 name `current.json`, so the fixture never goes stale when
state.py changes.
