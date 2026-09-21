# schema-v4

An overlay on a project built from today's templates: what a project at schema 4
looks like, with a task in flight at `implementation` that already carries the
WP4 keys (`diff`, `sensors`, `tests`, `risk_tier_lowered`) and none of schema
5's — no `handoff.pending_to`, `handoff.pending_since` or `cross_vendor_review`,
the ones migration 0005 adds.

It is `schema-v3` with migration 0004 applied, so the two fixtures describe one
task at two points of its life. A mutating command has to work on it before
migration 0005 runs (the defaults are filled in memory) and after it.

Copy it over the project with `cp -r schema-v4/.ai <project>/`.
