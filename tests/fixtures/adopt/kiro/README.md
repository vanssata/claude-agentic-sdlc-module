# Kiro fixture

Source: https://kiro.dev/docs/steering/ , https://kiro.dev/docs/specs/ , https://kiro.dev/docs/hooks/
Checked: 2026-09-22

Layout assumed:
- `.kiro/` is the signature.
- `.kiro/steering/*.md`, frontmatter `inclusion: always | fileMatch | manual | auto`; `fileMatchPattern` (a glob string or a list) with `fileMatch`.
- `.kiro/specs/<name>/{requirements.md, design.md, tasks.md}`.
- `.kiro/settings/mcp.json`.
- `.kiro/hooks/<id>.json`, plain JSON (the older `*.kiro.hook` format is gone). Not stored here: the test plants one to prove R4 (`unmapped`, exit 4).

The fixture covers `always` (product.md), no frontmatter (tech.md), `fileMatch` (api-standards.md)
and `manual` (release-checklist.md).

Corrections to spec I2:
- A steering file without frontmatter is included always (Kiro's default): the row's frontmatter map gains `"always_when_absent": true`. Unverified against a sentence in the docs; the fixture's tech.md pins the behaviour we chose.
- `manual` and `auto` have no `paths` and are not `always`: they become `.ai/policies/adopted/kiro-<slug>.md` with a router row (the `dest: auto` rule), which is what an on-demand file is here.
- AI-DLC installed for Kiro puts its methodology under `.kiro/steering/aws-aidlc-rules/` and `.kiro/aws-aidlc-rule-details/`; two `ignore` rows keep those out of the steering row (see the aidlc README).
