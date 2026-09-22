# AI-DLC fixture (v1 layout)

Source: https://github.com/awslabs/aidlc-workflows at tag `v1.0.1` (README.md, docs/GENERATED_DOCS_REFERENCE.md)
Checked: 2026-09-22

Scope decision (2026-09-22, human): **v1 only.** `main` (v2.x, "Harness") moved to
`aidlc/spaces/<space>/memory/*.md` and `<record>/<phase>/<stage>/*.md`; that layout is not
detected (no `aidlc-docs/`) and is out of scope for WP6.

Layout assumed (v1.0.1):
- `aidlc-docs/` is the signature: `aidlc-state.md`, `audit.md`, `inception/{plans,requirements,user-stories,application-design,reverse-engineering}/`, `construction/{plans,build-and-test,<unit>/{functional-design,nfr-requirements,nfr-design,infrastructure-design,code}}/`, `operations/` (placeholder).
- Rules, per agent: Amazon Q `.amazonq/rules/aws-aidlc-rules/` + `.amazonq/aws-aidlc-rule-details/`; Kiro `.kiro/steering/aws-aidlc-rules/` + `.kiro/aws-aidlc-rule-details/`; Cursor `.cursor/rules/ai-dlc-workflow.mdc`; Claude `CLAUDE.md`; Copilot `.github/copilot-instructions.md`; Codex `AGENTS.md`.

Corrections to spec I2:
- Removed `.aidlc/rules/` (no such path in v1) and narrowed `.amazonq/rules/**` to `.amazonq/rules/aws-aidlc-rules/`.
- The AI-DLC rules are its methodology, not project knowledge, and they reference `aws-aidlc-rule-details/` by path: copying them into `.ai/policies/adopted/` would add a second process next to ours and leave dangling references after cleanup. They are `ignore` (kept in place, never deleted) instead of `copy`. **This changes the spec's transform for these rows; flagged for the human.**
- `aidlc-state.md` is `drop` (the tracker; `.ai/state/` replaces it); `audit.md` is `ignore` (history stays where it is).
- `{rel}` (spec: the path under the root, `/` → `-`) is taken without the `.md` extension, which the row's `dest` adds back: `aidlc-docs/inception/requirements/requirements.md` → `docs/sdlc/intent/aidlc-inception-requirements-requirements.md`.
