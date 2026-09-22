# Cursor fixture

Source: https://cursor.com/docs/context/rules , https://cursor.com/docs/context/mcp
Checked: 2026-09-22

Layout assumed:
- `.cursorrules` at the root (legacy, still loaded, no frontmatter) and `.cursor/rules/` are the signatures.
- `.cursor/rules/**/*.mdc`, frontmatter `description`, `globs` (one comma-separated string), `alwaysApply` (bool). Nested `.cursor/rules/` in subdirectories is supported by Cursor; `detect` is root-only, so a nested one is `unmapped` (R4) — the test plants `packages/x/.cursor/rules/a.mdc`.
- `.cursor/mcp.json` → `ignore`.

The fixture covers always (general.mdc), glob-scoped with a literal leading directory
(frontend/react.mdc → `.ai/rules/`), and description-only (testing.mdc → `.ai/policies/adopted/`).

Corrections to spec I2: none. Noted, out of scope: Cursor now also reads `AGENTS.md` (root and
nested); a root one is the codex instruction file, nested ones are not detected.
