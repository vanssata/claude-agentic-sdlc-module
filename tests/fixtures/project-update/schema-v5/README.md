# schema-v5

An overlay on a project built from today's templates: `.ai/VERSION` at 5, the
schema before migration 0006 moved the shared policies, agent contracts,
workflows and templates into the plugin. No task in flight.

`tests/test-migration-0006.sh` builds the rest of a schema-5 project around it:
today's scaffold, a copy of every file under `ai/` as the project carried it, the
oldest shipped versions from `shared-old/`, and the schema-5 router
`shared-old/AGENTS.v5.md`.

Copy it over the project with `cp -r schema-v5/.ai <project>/`.
