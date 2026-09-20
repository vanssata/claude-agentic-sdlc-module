# schema-v3

An overlay on a project built from today's templates: what a project scaffolded
at schema 3 looks like, with a task in flight at `implementation` and no `diff`,
`sensors` or `tests` keys — the ones migration 0004 adds.

The state file here is the point of the fixture. It carries a plan with two
steps, one of them already done, so the migration has to add the per-step keys
as well as the top-level ones, and `state.py step-done` has to keep working
afterwards on a task whose base tree was never recorded.

Copy it over the project with `cp -r schema-v3/.ai <project>/`.
