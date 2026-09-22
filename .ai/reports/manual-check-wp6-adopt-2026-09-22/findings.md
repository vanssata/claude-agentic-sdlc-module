# Manual check — WP6 `project-update --adopt` on real projects (2026-09-22)

Investigation, T1, direct mode. Nothing was fixed; every difference is recorded below as a finding.
Compared against `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp6-adopt.md` (the spec) and the
"Manual checks" section of `.ai/reports/T-2026-09-21-001/release.md`.

## Setup

- Plugin under test: the installed copy under `~/.claude`, byte-identical to this repository at
  `0bed018` for `adopt.py`, `update.py`, `adopt-map.json`, `scaffold-ai.sh` and `project-scaffold.sh`.
- Real projects, shallow clones into the session scratchpad (not fixtures):

| Project | Tool | Commit | Shape |
|---|---|---|---|
| `github.com/galax-io/gatling-picatinny` | Spec Kit (current, with extensions/presets/workflows) | `0228bb4` (2026-09-22) | 242 Spec Kit files, 14 features under `specs/`, `AGENTS.md` 8.7 KB, `CLAUDE.md` with a `SPECKIT` block |
| `github.com/pulumi/pulumi-hyperv` | Spec Kit (skills layout `.claude/skills/speckit-*`) | `60eaaa4` (2026-04-10) | no `specs/`, `.specify/` 18 files, `CLAUDE.md` 29 KB |
| `github.com/un-pany/v3-admin-vite` | Cursor | `c2c895d` (2026-07-11) | `.cursor/rules/*.mdc` ×5 (2 `alwaysApply: true`), `.cursor/mcp.json`, `AGENTS.md` 5 KB; cloned into a path with a space |

- Each clone was scaffolded as `/project-init` and `/ai-init` do (`project-scaffold.sh` and
  `scaffold-ai.sh`, `--runtime auto`) and committed before adopting. Decisions for unmapped files and
  the split proposals were written as the SKILL §8 flow prescribes (proposals by one BALANCED
  subagent, profile `max20`, fan-out 6). These are test decisions in a scratch clone, not a team's.
- `--cleanup --apply --confirm-delete` was **not** run by the agent. It is handed to the human below.

## What behaved as specified

| Spec | Observed |
|---|---|
| R1 detection | `detect` line per tool with counts on all three; `.claude/skills/speckit-*` found |
| R2 dry run writes nothing | `git status` empty after every dry run and `--diff` |
| R4 unmapped → exit 4 | gatling 98 unmapped, pulumi 5 → `ADOPT_INCOMPLETE`, exit 4 |
| R5 refusals, exit 5 | no `.ai/` ✓, project behind the plugin ✓, dirty tree ✓, task in flight (created with `state.py init`) ✓. "Not a git work tree" not exercised |
| R6 originals | cursor: 6 files in `original/`, byte-identical to `HEAD`; pulumi 215 422 B |
| R7/R8 split | proposal accepted on both; `--split fallback` planned on cursor and gatling |
| R10 no-line-lost | PASS on cursor and pulumi; an independent line-set check (not the tool's normaliser) found 0 lines missing on cursor |
| R12/R13 cleanup gates | refuses before the adopt is committed ✓; dry run recomputes both checks ✓; lists exactly the `cleanup: true` sources (cursor 5, pulumi 27) ✓; `--confirm-delete` with stdin from `/dev/null` → exit 5 ✓ |
| R14 coexist | apply writes router rows and the record only; `--cleanup` → exit 5 `coexist keeps the foreign files` ✓ |
| R15 idempotent | second `--adopt` after commit: `0 automatic` ✓ (cursor and coexist) |
| R16 regeneration | edited `.cursor/rules/ts.mdc` after the adopt: `--adopt --check` exit 1 with the file named, plain dry run `hint`, cleanup exit 5 on the sha ✓ |
| R23 secret hint | 6 hints in gatling `specs/007-secret-masking…`, `file:line` only, no value ✓ |

## Findings

Severity is this check's judgement of impact on a real adoption; "spec gap" means the code follows
the spec and the spec does not cover the case.

### F1 — HIGH — Migrating a real Spec Kit `specs/` tree cannot pass no-dangling (spec gap + fixture gap)

Spec Kit's own templates put the feature path into every generated artifact, e.g.
`specs/001-transactions-reliability/plan.md:5` "**Input**: Feature specification from
`specs/001-transactions-reliability/spec.md`" and `tasks.md:7` "Design documents from `specs/…/`".
gatling has 71 such lines in `specs/*/*.md`. The `copy` transform keeps them verbatim in
`docs/sdlc/{specs,plans}/`, which is hard scope (I8), so `check no-dangling FAIL` lists 20+ of the
migrated documents themselves, plus `CLAUDE.md:4` (Spec Kit's `<!-- SPECKIT START -->` block) and
the fallback-split `AGENTS.md`. `--apply` exits 4, nothing written.
There is no remedy inside the flow: `decisions.json` settles only unmapped files, a proposal only
splits instruction files, and SKILL §8 step 6 forbids editing a destination. The only way through
is to rewrite ~71 source lines by hand and commit first. The fixture's `specs/001-user-auth/*.md`
contain no path reference at all, so `tests/test-project-adopt.sh` never meets this, although the
release report says the fixtures were verified against real formats.

### F2 — HIGH — Spec Kit's constitution "Sync Impact Report" dangles (spec gap)

`/speckit.constitution` prepends an HTML comment listing `.specify/templates/*.md`
(pulumi `.specify/memory/constitution.md:14-18`). `append-section` copies it into
`docs/sdlc/constitution.md` → `no-dangling FAIL: docs/sdlc/constitution.md:32 -> .specify/`,
apply exit 4. Same missing remedy as F1; to continue the check the lines were deleted from the
source and committed, after which pulumi passed. (gatling's constitution has no such comment.)

### F3 — HIGH — The cleanup human gate is `isatty(0)` only, and a pty satisfies it

There is no interactive prompt: `human_present()` is `os.isatty(0) or AI_UNATTENDED`
(`skills/project-update/adopt.py:24-30`). A plain tool call has `isatty(0) == False`, but
`script -qec "<cmd>" /dev/null` gives the same tool call `isatty(0) == True` (demonstrated with a
harmless `print(os.isatty(0))`; the deletion itself was not run). No hook matches
`--confirm-delete` (`grep` over `hooks/` finds nothing), so only the SKILL text stops an agent. Such
a run would be recorded as `tty: true, unattended: false` — indistinguishable from a human. The
residual risk accepted in release.md covers `AI_UNATTENDED=1`, which is audited; this path is not.
The release report's manual check speaks of "the human-gate prompt"; there is none to observe.

### F4 — MEDIUM — The dry run exits 0 on a failed check, a conflict or a missing proposal (spec I1)

I1 lists "a missing or invalid proposal, a failed check, a `conflict` on a destination" under exit 4.
Observed exit 0 with no `ADOPT_INCOMPLETE` first line:
- cursor, raw: `split?` awaiting a proposal and `check no-dangling FAIL: AGENTS.md:142 -> .cursor/`;
- gatling with decisions: `no-dangling FAIL` on 20+ files;
- cursor after regeneration: `1 conflict(s)` and `no-line-lost FAIL`.
The summary line reads `8 automatic, 0 conflict(s)` next to a FAIL. Unmapped files *do* give exit 4
in the dry run, so the behaviour is inconsistent. SKILL §8 step 5 then asks "apply?" on a plan that
`--apply` refuses with exit 4.

### F5 — MEDIUM — `alwaysApply: true` Cursor rules are no longer always applied (spec gap)

`index.mdc` and `project.mdc` are labelled `rule: always` and land in
`.ai/policies/adopted/cursor-{index,project}.md`, exactly like an on-demand rule without globs
(`adopt.py:295-303`: `always` only changes the label and keeps the rule out of `.ai/rules/`). Nothing
loads them always. For v3-admin-vite this drops, for instance, "always answer in Simplified Chinese"
from every session. I2 does not say where an always rule goes. Related: glob-only rules
(`globs: *.ts,*.tsx`, `*.vue`) keep `paths:` in `.ai/policies/adopted/`, where nothing reads it
(as I2 says, but inert).

### F6 — MEDIUM — Router rows carry no trigger (spec I9 as written)

The rows added are `| an adopted Cursor file | policies/adopted/ |`,
`| an adopted Codex file | policies/adopted/ |`, `| an adopted Claude file | policies/adopted/ |`.
The `## Doing X → read Y` table then has no X that would make an agent open them. Content that was
always loaded before the adopt ends up behind these rows: v3-admin-vite's `AGENTS.md` principles, and
pulumi's `CLAUDE.md` "Important Restrictions" and "Code Style Guidelines" (CLAUDE.md goes from
29 273 B to 1 109 B). The Cursor `description:` becomes a heading in the file, not the row text.

### F7 — MEDIUM — Coexist writes one router row per file (spec I9: per tool and directory)

gatling `--mode coexist`: `+138 row(s)`; `.ai/AGENTS.md` grows from 3 521 B to 22 475 B (×6.4), and
it is the file read first on every task. Every row ends "(kept in place; its globs are not applied
by this runtime)", including specs and constitution files that have no globs. Migrate with
`decisions.json` copies added `+33 row(s)`, one per decision destination directory.

### F8 — MEDIUM — `adopt-map.json` is behind the current Spec Kit layout; decisions are per file

Unmapped on real projects: `.specify/{extensions,presets,workflows,integrations}/**`,
`.specify/{init-options,integration,feature}.json`, `.specify/extensions.yml`, and the standard
`specs/*/checklists/requirements.md` (from `/speckit.checklist`) besides `contracts/` (unmapped on
purpose per the fixture README) and project-specific `harness/`, `evidence/`. gatling: 98 files,
pulumi: 5. `decisions.json` takes no glob, so a human settles 98 entries one by one.
Also `.specify/integrations/speckit.manifest.json` is dropped by the `*/**/speckit*` row with the
reason "Spec Kit agent commands…", while `claude.manifest.json` next to it is unmapped — the match is
a filename coincidence.

### F9 — LOW — After a regeneration the suggested next step dead-ends

Cleanup refuses with "run /project-update --adopt --apply again, then --cleanup". That apply exits 4:
`conflict … the destination exists and differs`, and there is no update path for an adopted file.
Its `no-line-lost FAIL` names 10 lines of `ts.mdc` as lost that are present in the existing
destination (the conflicted item is left out of the planned tree), which misleads.

### F10 — LOW — `--adopt --check` in coexist offers a cleanup that R14 forbids

It prints `adopted 2026-09-22: speckit — up to date; 242 file(s) await cleanup`, while `--cleanup`
exits 5 in coexist. The record itself says `cleanup.offered: false`.

### F11 — LOW — No-dangling warnings are counted and never named

`PASS (1 warning(s) outside the new structure)` in the dry run, apply and `report.md`; no path is
shown anywhere, so the human cannot judge it.

### F12 — LOW — An abandoned task's report directory blocks adopt

After `state.py done --abandon` and `archive`, `.ai/reports/T-…/` is untracked and R5 refuses the
tree as dirty (the exclusions are only `adopt-*`, `.ai/state/`, `.ai/local/`). Defensible; worth a
line in the refusal text.

### F13 — LOW — `--confirm-delete` accepts an unfilled placeholder as the confirmer

The human's terminal run on the cursor clone (13:17:59Z) passed `--confirm-delete "<your name>"`
verbatim, copied from the template (the same form SKILL §8 prints). The deletion went through and
`adopt.json.cleanup.confirmed_by` and `report.md` now read `<your name>`: the audit trail names no
one. Nothing rejects an empty-looking or `<…>` value. Otherwise the run matched R13 exactly: both
checks recomputed, the 5 rules deleted and nothing else, `tty: true, unattended: false`, `at`
written, originals kept, `--adopt --check` → `up to date`, a re-adopt → `0 automatic`,
`.cursor/mcp.json` (ignored) left in place. Also: `report.md:46` still says "Run
`/project-update --adopt --cleanup` to review" above the new `## Cleanup` section that records the
deletion.

The pulumi cleanup (13:18:22Z, also with `<your name>`) matched R13 the same way: 27 deleted,
`tty: true, unattended: false`, `original/` holds 29 files, `--adopt --check` → `up to date`, a
re-adopt → `0 automatic`. `.specify/` is gone, but the nine directories
`.claude/skills/speckit-*/` stay behind on disk, empty. Git does not see them, but a runtime that
scans `.claude/skills/` does.

### Outside WP6 (observed on the way, not part of the spec)

- **O1** A fresh `--runtime auto` scaffold of gatling (has both `AGENTS.md` and `CLAUDE.md`) is at
  once "behind the installed plugin": `update.py` wants `.claude/memory/local/` and
  `.codex/memory/local/` in `.gitignore`, which `project-scaffold.sh` did not add. Adopt refuses
  until a plain `--apply`.
- **O2** The path guard refused `python3 -c '…json.dump(…)' .ai/reports/adopt-*/decisions.json`
  with the approval-gate message, while a `python3 - <<EOF` heredoc writing the same kind of file
  passed. `decisions.json` is a file SKILL §8 tells the session to write.

## The release report's manual checks

| Check (release.md) | Status |
|---|---|
| `--adopt` on a real Spec Kit or Cursor project | Done: F1–F12 |
| `--adopt --cleanup` by a human in a terminal | Done by the human on cursor and pulumi, as specified except F13 (placeholder name, empty skill dirs). See F3 on what the gate checks |
| CI pylint on 3.11/3.12/3.13 | `pylint.yml` matrix is 3.11–3.13; success on `0bed018` (and on `6b14d52`) |
| `bash tests/run-all.sh` green on `7a193b2` exactly | Not done in this task |
| `/ai-status` shows `(deleted unattended)` | Not done: it needs a cleanup under `AI_UNATTENDED=1`, which the agent must not set |

## Commands for the human (the cleanup in a terminal)

The scratch clones are in the session scratchpad; both are committed and clean, and the cleanup dry
run passes on both.

```bash
python3 "/home/vanssa/.claude/skills/project-update/update.py" "/tmp/claude-1000/-home-vanssa-Downloads-Claude-Plugin-claude-native-claude-agentic/31f9d717-46d8-4cdc-bad7-2822c93457d6/scratchpad/real/cursor v3-admin-vite" --adopt --cleanup --apply --confirm-delete "<your name>"
```

```bash
python3 "/home/vanssa/.claude/skills/project-update/update.py" "/tmp/claude-1000/-home-vanssa-Downloads-Claude-Plugin-claude-native-claude-agentic/31f9d717-46d8-4cdc-bad7-2822c93457d6/scratchpad/real/speckit-pulumi-hyperv" --adopt --cleanup --apply --confirm-delete "<your name>"
```

Expected per the spec: 5 and 27 deletions; `adopt.json.cleanup` with `confirmed_by`, `at`,
`tty: true`, `unattended: false` written before the first removal; originals remain under
`.ai/reports/adopt-2026-09-22/original/`; then `--adopt --check` and `/ai-status` there.
