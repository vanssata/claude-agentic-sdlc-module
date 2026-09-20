# schema-v2

An overlay on a project built from the oldest shipped templates: what a project
scaffolded at schema 2 looks like — the journal and the handoff keys are already
there, and the root instruction files still carry the `## SDLC workflow` section
that migration 0003 takes out.

Only `.ai/VERSION` is kept here. Everything the migration reads — the shipped
section, the managed block, the router — comes from the templates the test
builds out of `history/`, so the fixture never has to be kept in step with a
template it does not own.

Copy it over the project with `cp -r schema-v2/.ai <project>/`.
