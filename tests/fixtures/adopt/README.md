# Fixtures for `update.py --adopt`

One directory per foreign structure. Each has a `README.md` (the format assumption, its source and
the date it was checked) and a `fixture.json` that tells `run_fixture` in
`tests/test-project-adopt.sh` how to build the project:

```json
{"runtime": "claude", "instruction_append": {"CLAUDE.md": "fixture-CLAUDE.md"}}
```

## Stored encoded, materialised at test time

The path guard (`hooks/ai-path-guard-defaults.json`) refuses writes to `.cursorrules`,
`.cursor/rules/`, `.claude/commands/`, `.github/copilot-instructions.md`, `.junie/`, `.ai/**` and
similar paths anywhere in the tree, and Claude Code or Codex would load a fixture's `CLAUDE.md` or
`AGENTS.md` while working next to it. So nothing here is stored under its real name:

| Stored as | Materialised as |
|---|---|
| a path component `dot-<name>` | `.<name>` (`dot-cursor/rules/a.mdc` → `.cursor/rules/a.mdc`) |
| `fixture-CLAUDE.md`, `fixture-AGENTS.md`, `fixture-GEMINI.md` | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` |
| `README.md`, `fixture.json`, `split-proposal.fixture.json` | not copied |

`run_fixture` copies the fixture to `$TMP` (once under a path with a space, once without),
renames as above, scaffolds `.ai/` and the instruction files with `hooks/project-scaffold.sh` and
`skills/ai-init/scaffold-ai.sh --runtime <runtime>`, then `git init`, sets `user.email` and
`user.name`, and commits — so every fixture is current and clean for R5 and never goes stale.

A fixture instruction file named in `instruction_append` is **appended** to the scaffolded file,
which already carries the managed block; any other `fixture-*.md` replaces the file (it is foreign:
no managed block).

## `split-proposal.fixture.json`

The canned split proposal (R19) cannot hold absolute line numbers or the source sha, because both
depend on the scaffolded file. Its ranges are relative to the appended text (line 1 = its first
line) and it carries no `source_sha`. The test turns it into a real I5 `split-proposal.json`: every
range is shifted by the scaffolded file's line count, `keep` gains the scaffold's own lines above
the block, and `source_sha` is computed from the file on disk.

## Planted by the tests, not stored

The `API_KEY=` line (R23), `.kiro/hooks/*` (R4), a nested `packages/x/.cursor/rules/` (R4),
`specs/<dir>/contracts/` (R4, I6), `src/lib/speckit_x.py` (R18), the >1 MiB and NUL files (R6).

## Content

Written for this repository from each tool's documented layout. No upstream sample text is
copied; the files reproduce only the shape (paths, frontmatter keys, headings).
