# Review report — T-2026-10-25-006

## Pass 1 — STRONG `ai-reviewer` (opus), full review over `git diff`, T4 direct mode

### FINDINGS

- [MEDIUM] M1 Writer and take-back still disagree for `dirs:` spelled with `./` or `//` (`skills/project-update/update.py:80-83`, `:1049` vs `:992-995`; `render_instructions.py:345,398`) — in_scope: yes. `dirs: ["./lib"]`: the writer targets `./lib/CLAUDE.md`, the walk reports `lib/CLAUDE.md`, not in `managed`; four `--apply` runs alternate create/remove, `--check` exits 1 forever (blocks `--adopt` via `plain_pending`). Pre-existing (reproduces on HEAD). The new comment claimed both sides cover the same directories. Direction: record in known-risks, soften the comment.
- [LOW] L1 Symlinked directories: `os.walk` does not follow them, `write_file` does — `ext -> /tmp/outside`, `dirs: [ext]` writes `/tmp/outside/CLAUDE.md` and is never taken back. Pre-existing. Direction: record.
- [LOW] L2 The new hint is never shown on the adopt path: `adopt.py` `report()` (`:792-845`) does not print `plan.hints` (the `RenderError` hint is lost there too). Direction: record (adopt.py is outside this task's files).
- [LOW] L3 A block written into a nested tree by an earlier version stays; the hint says "not rendered there" while an old block is there. Direction: mention an existing block in the hint.
- [LOW] L4 Test gaps: no worktree-hint assertion, no codex (`AGENTS.md`) case, no `./`-spelled nested dir; `--check exits 0` passes pre-fix too. The reviewer ran these by hand: all correct. Not vacuous: 4 assertions fail on the unfixed tree.
- [INFO] I1 A submodule not checked out yet (empty dir, no `.git`) is written into; `git submodule update --init` then fails — in_scope: no.
- [INFO] I2 The RULES_SKIP entry's INFERENCE was reproduced on disk (`dirs: [vendor/x]` written, never taken back, `--check` 0) — relabel KNOWN FACT; `.git`/`.ai` are RULES_SKIP names too.

### VERDICT

verdict: pass — the change stayed inside the plan; M1 and L1 are pre-existing writer/walk mismatches the change neither causes nor fixes.

### Disposition (manager)

- M1: the `update.py:80-83` comment now names where the two sides still disagree.
- M1, L1, L2, L3, I1, I2: recorded in `.ai/project/known-risks.md` under "The rule writer still reaches directories the take-back never walks …", relabelled KNOWN FACT. Not fixed here: production behaviour, outside the plan.
- L4: accepted as coverage gaps; the reviewer's manual runs of the codex runtime and the spellings are the evidence.
