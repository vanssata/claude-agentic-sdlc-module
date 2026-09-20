# schema-v0

An overlay on a project built from the oldest shipped templates: what a project
scaffolded before `.ai/VERSION` existed looks like. The build already leaves out
`ai-init/.ai/VERSION`, so the tree is schema 0; this overlay adds the files such
a project carries that no template ships — a hand-written knowledge base.

The task in flight that the migration test needs is created by `state.py`, not
kept here: the task state is written by that script alone, and `ai-path-guard`
refuses any other writer, fixtures included.

Copy it over the project with `cp -r schema-v0/.ai <project>/`.
