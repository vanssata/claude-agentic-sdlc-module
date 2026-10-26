A schema-6 project, as `tests/test_project_update.py::TestMigration0007` builds it:
today's `scaffold-ai.sh` output with these files laid over it.

- `.ai/VERSION` — 6, the schema before the weight model.
- `in-flight/.ai/state/current.json` — a T4 task on the old surface, mid-step,
  laid over the project for the in-flight variant.

The test adds the risk-tier edits itself (an example, extra path scopes, a
suite cap), on top of the shipped `risk-tiers.json`, so the fixture never goes
stale when that template changes.
