# Review — T-2026-10-25-007 (T4, STRONG ai-reviewer, pass 1 over the uncommitted diff against 9d0c43a)

## FINDINGS

- [LOW] L1 The dedupe is not pinned by the test — normalisation alone passes every assertion (`skills/project-update/render_instructions.py:356`, `tests/test-project-update.sh:600-601`, `:610-611`). in_scope: yes
  - Mutation run by the reviewer: real tree 12/12; normpath without dedupe 12/12; dedupe without normpath 7 fail (`--apply` exits 3, `--check` exits 1, `./`/`//` targets planned).
  - Why normpath suffices: `Plan.read()` returns this run's planned content (`update.py:694-701`), so a second item for the same `(target, slug)` splices to `current == new` and plans nothing (`update.py:1076-1081`); `managed` is a set. The dedupe's only visible effect is not printing a nested-tree hint twice for `dirs: [sub, ./sub]`.
  - The code comment and the known-risks record presented the dedupe as part of the fix; it is not.
  - Direction: drop the dedupe, or keep it and say that normpath alone closes the alternation.
- [LOW] L2 The known-risks entry was only partly updated (`.ai/project/known-risks.md`, "The rule writer still reaches directories the take-back never walks"). in_scope: yes
  - The heading still listed "`./` spellings"; "How likely / how bad" still said "the `./` spelling keeps `--check` red"; "Suggested fix" still opened with "normalise `dirs:` in `parse_rule()`".
  - "Where" cited `render_instructions.py:345-351` (now `:346-352`); the closed bullet's `:345`/`:398` are HEAD's line numbers.
- [INFO] I1 `dirs: ["/"]` (or `"///"`) is accepted and renders into the root `CLAUDE.md`: `rstrip("/") or "."` runs before the absolute-path check (`render_instructions.py:346`). Same on HEAD 9d0c43a; writer and walk agree on the target. in_scope: no (no fixture or session writes `/`).

## EXAMINED AND CLEAN

- Refusal: the raw check still runs first; normpath cannot produce a leading `/` or a `..` part the input did not have. Probed: `./../x` refused; `lib/.../x`, `lib/ `, `" ./lib"` unchanged; `.//`→`.`, `lib/x/./.`→`lib/x`, `./.claude/rules`→`.claude/rules`.
- Callers: only `update.py` `rules_update()` (`:1036-1046`) via `load_rules` and adopt's `planned`; the render_instructions CLI, `state.py` and hooks do not reach rules. `adopt.py:1970-1984`, `:2068-2070` write the raw spelling into frontmatter; parse_rule normalises at render.
- Old data: a block at `./lib/CLAUDE.md` is the same file as `lib/CLAUDE.md`; after upgrade the next run no-ops or updates.
- Ordering: `dict.fromkeys` keeps first-seen order; plan output unchanged.
- Comments `update.py:82-83` and `:1014-1015` accurate.
- Test: the `(\./|//)` assertion catches a spelled target and cannot false-match `.ai/`/`.claude/`; removing normpath fails 7 assertions, as recorded.
- Scope: inside the plan; nothing touches the out-of-scope items.

## VERDICT

verdict: pass

## Manager's disposition

- L1: dedupe kept (the approved plan asked for it); the comment (`render_instructions.py:353-356`) and the known-risks record now say normpath alone closes the alternation and the abort, and that the dedupe only saves planning the same file twice, unpinned.
- L2: heading, "Where", the pre-fix line references, "How likely / how bad" and "Suggested fix" corrected; the entry stays `open` for `RULES_SKIP` names, symlinks, adopt `report()`, old nested-tree blocks and un-checked-out submodules.
- I1: not recorded in known-risks as a separate entry; pre-existing, writer and walk agree, so no stale block results. Left for the human to decide whether it is worth an entry.
- Both LOW fixes are comment/record text only; the suite and e2e were re-run once on the final tree.
