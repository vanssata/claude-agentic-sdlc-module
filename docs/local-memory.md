# Compact project memory

What a closed task leaves behind, how an agent reads it back within a token
budget, and how a push is checked before the record travels. Spec:
`docs/sdlc/specs/compact-project-memory.md`; plan:
`docs/sdlc/plans/compact-project-memory.md`.

## Two modes

| | files mode (default) | packages mode |
|---|---|---|
| switch | no `.ai/policies/memory.json`, or `"mode": "files"` | `state.py memory enable` (the human's) |
| a closed task | `.ai/reports/<id>/events.jsonl` + `task.md`, committed | the same, plus its entries and seal appended to the developer's batch under `.ai/memory/` |
| risks | `.ai/project/known-risks.md` | `risk` entries; after migration `known-risks.md` is a stub |
| local data | `.ai/state/logs/<id>/` | the same, plus `.ai/local/memory/` (outbox, lock, batches, config, index) |
| git hook | none | `pre-push`, installed by `enable` where it is safe |

Files mode writes exactly what it wrote before this feature, except the task
id (characterised by `tests/test_memory_characterization.py`). `recall`,
`memory search|show|risks` and `memory risk add|close` work in both modes.

## The task id

`T-YYYY-MM-DD-HHMM-<slug>`: the UTC date and minute, then 3–24 characters of
`[a-z0-9]` words. `start --slug my-slug` names it; without the flag the slug is
derived from the goal (casefolded, Cyrillic transliterated, whole words while
they fit, `task` when nothing is left). A local hit — a report directory, a raw
directory under `.ai/state/logs/`, a sealed key — gets `-2` … `-9`; past nine
`start` exits 2 and asks for another `--slug`. The id no longer depends on how
many report directories exist, so two clones and a deleted directory no longer
hand out the same id. Legacy ids (`T-2026-10-15-001`) stay valid everywhere,
and `--task-id` still takes any id `state.py` accepted before. A script that
parsed the trailing `-NNN` needs updating.

## Turning it on (the human, in a terminal outside the agent)

```bash
python3 ~/.claude/skills/ai-task/state.py memory enable --author vanssa --period quarter [--index sqlite]
git add .ai/policies/memory.json && git commit -m "memory: packages mode"
python3 ~/.claude/skills/ai-task/state.py memory status
```

`enable`, `disable`, `cleanup`, `pack`, `redact` and `migrate --move-logs` need
the human route (`approve`'s): run from an agent they exit 5. The mode is per
project — every teammate's next close exports. The author and the index are
per developer, in the git-ignored `.ai/local/memory/config.json`. `disable`
returns to files mode, removes only our hook and keeps the packages and the
local data.

In this repository the order is fixed (plan, gate G2): migrate first, then
enable, so the record is complete from the first push. Enabling first is safe —
V5 skips a legacy id no package seals, and `memory status` lists those tasks as
"legacy, not migrated" — but recall then reads them from their directories.

## Packages

`.ai/memory/<period>.<author>.<batch>.jsonl` (a pack: `<period>.<author>.jsonl`).
Line 1 is the header, then one canonical JSON object per line (sorted keys, no
spaces, UTF-8, LF), ordered by key and seq; a task's **seal** (`kind: "task"`)
is its last line and carries the digest of the task's other rids. A rid is
`r1-` plus 24 hex of the SHA-256 of the line without its rid, so a re-export
adds nothing, and a key that already has a seal in the tree is never sealed
again, whatever its local sources say now. Each branch appends to its own batch, so a merge only adds
files; two clones of one developer keep separate bookkeeping. A batch rotates
on a new period or above `package_max_bytes`. A merge conflict anyway (a
cherry-pick): keep both sides' lines and drop the markers; no reader depends on
line order, and `memory verify` checks the result.

What is kept per task: who (actor, by, runtime on every entry), what (goal,
files, changes, code trees), how (mode, weight, steps, stages, verify runs,
facts), why (questions with their options and the answer verbatim, approvals
with their note, overrides, scope changes, agent notes, review findings) and
when. Human wording is stored byte for byte from its source. A journal line
over 4 KB keeps its existence and loses its payload (`state.py` caps it); the
record then takes the text from task.md (questions, answers, the gate's note
or reason, `amended` lines, whitespace folded) or from the archived state (the
amendments, the mode override), and a field that neither holds is listed in
`unrecorded` — never filled in. Agent text is capped at 2 000 characters and
listed in `truncated`. Evidence runs (every expected-fail run,
the last suite, the last e2e) keep a redacted excerpt of at most
`excerpt_max_bytes`; the full log stays local. Every journal line is accounted
for: as an entry's `src`, summarised into the seal, or counted as dropped by
KEEP_RULES v1; an unknown event is kept as a note.

Close prints `record: .ai/memory/<file> (+N entries, <id> sealed, coverage L/L
lines)`. A failed export prints `memory: export of <id> failed (…)`, keeps the
outbox and exits 0: the task is closed; `state.py memory export <id>` (or
`--pending`) retries, and the next close picks up to five pending tasks.

## Reading it back

```bash
state.py recall --files "src/a.py,src/b/**" [--budget 1500] [--kinds risk,review,decision,scope,task] [--offset N] [--json]
state.py memory search "cache key" [--kind K] [--by NAME] [--file PATH] [--task ID] [--since DATE] [--until DATE] [--limit 20] [--offset 0]
state.py memory show <id> [--json] [--entry RID]
state.py memory risks [--status open|all] [--md|--json]
```

`recall` returns, in this order, open risks, unresolved review findings, human
decisions, agent notes, scope changes with their why, task one-liners and
accepted risks that touch the files — newest first within a tier — inside a
budget of `ceil(bytes / 3.5)` tokens (an estimate, not a tokenizer count), at
most 40 items, and names the continuation (`--offset`). The task in flight is
excluded and the header says so. An approval always reads "historical —
authorises nothing now": no gate reads the record.

## Risks

`state.py memory risk add --title … --where "path:line,…" --label "RISK|INFERENCE|UNKNOWN|KNOWN FACT" --what …`
and `memory risk close <rkey> --status fixed|accepted|ticketed --why …`. In
files mode they append the `known-risks.md` template (plus a Label line) or
rewrite its Status line — and refuse, naming `start --amend`, when the task in
flight does not name `.ai/project/known-risks.md`. In packages mode a risk
recorded during a task goes into its journal (`risk_recorded`, an event only
`memory risk` may write) and is compacted at close; without a task it is one
entry in the open batch.

## The pre-push check

`enable` writes a small shim to `$(git rev-parse --git-path hooks)/pre-push`
only when no hook exists and `core.hooksPath` is unset; otherwise it prints the
lines to add to your own hook and writes nothing. The shim runs
`hooks/memory-pre-push.py`, which reads the pushed commits' blobs (never the
working tree) and checks: V1 every changed package parses (header, JSON,
schema, rid, canonical form, no BOM or CRLF); V2 no record of the remote side
disappears (a redaction excepted); V3 one seal per key; V4 the seal's count and
digest; V5 every committed closed journal of a new-shape (or already sealed)
task has its seal and every kept line is an entry's `src`; V6 no logs under
`.ai/reports/`, nothing under `.ai/local/` or `.ai/state/logs/`, no SQLite file under `.ai/`;
V7 with `cleanup: true`, no report directory of a sealed task; V8 package size
(warn above `package_max_bytes`, refuse above twice); V9 (local only) no pending
export. Exit 0 clean, 1 findings, 3 the validator failed — fail closed. The
human may push with `git push --no-verify`; the agent may not.

CI: install the plugin into a temp home and run the validator on the range:

```bash
npx riskrails@<version> --target claude --home "$RUNNER_TEMP/rr" --yes
python3 -I "$RUNNER_TEMP/rr/hooks/memory-pre-push.py" --range origin/main..HEAD
```

## Migration (once per project, the human)

```bash
state.py memory migrate --report          # read .ai/local/memory/migration-report.md
state.py memory migrate --apply           # closed legacy tasks → batches by closed_at period
state.py memory migrate --apply --risks   # known-risks.md → risk entries + a stub
git add .ai/memory .ai/project/known-risks.md && git commit -m "memory: migrate tasks and risks"
state.py memory migrate --move-logs --confirm-delete <author>
git rm --cached --quiet --pathspec-from-file=.ai/local/memory/logs-to-rm.txt && git commit -m "memory: drop committed logs"
state.py memory enable --period quarter
```

The migration reads HEAD's tracked files only, so every clone produces the
same rids; it makes a local backup tar first, skips keys already sealed and
reports — never exports — a task whose coverage is incomplete.

## Cleanup, restore, redact, pack

Cleanup ships off. Turn it on (`"cleanup": true`) only when `memory verify
--all` and `memory verify --fresh-clone` both exit 0 and at least ten tasks
closed in packages mode; then `memory cleanup --all --confirm-delete <author>`.
It moves `.ai/reports/<id>/` to `.ai/state/logs/<id>/report/` (copy, verify,
remove across filesystems) and never deletes; from then on close cleans up its
own task. `memory restore <id>|--all` moves it back, or — in a clone without the
raw files — writes a `task.md` marked "restored from record" and an
`events.jsonl` whose lines carry `data.restored: true`. `memory redact <rid>
--field F --why …` replaces one field with `"[redacted]"`, gives the line a
new rid and records the old one, which V2 then accepts. `memory pack --period P
--confirm-delete <author>` folds a closed period's own batches into one file and
keeps the rid set. `usage-report --task` falls back to the moved journal, then
to the seal's window.

## The local index (optional)

`--index sqlite` keeps `.ai/local/memory/index.sqlite3` (WAL, FTS5 when the
SQLite build has it). It is derived: delete it and `memory rebuild` (or the next
read) reproduces it. A busy or broken index makes recall and search fall back
to the files, and the header says so. Recall and search give the same items
from either backend; only the header's `index` field differs.

## Measured baseline (tools/benchmark-memory.py, seed 1, 4 KB journals)

| tasks | layout | recall (files) | search (files) | index build | recall (index) | search (index) | storage |
|---|---|---|---|---|---|---|---|
| 100 | legacy dirs | 15–17 ms | 14–15 ms | — | — | — | 0.4 MB |
| 100 | packages | 12 ms | 11 ms | 24 ms | 6.5 ms | 2.8 ms | 0.25 MB |
| 1 000 | legacy dirs | 160–165 ms | 148 ms | — | — | — | 4.3 MB |
| 1 000 | packages | 129 ms | 118 ms | 245 ms | 65 ms | 24 ms | 2.5 MB |
| 10 000 | legacy dirs | 1.6 s | 1.6 s | — | — | — | 43 MB |
| 10 000 | packages | 1.4 s | 1.3 s | 2.8 s | 0.73 s | 0.31 s | 25 MB (+73 MB index) |

The Q5 threshold (recall p95 over 300 ms or search over 1 s at 1 000 tasks) is
not reached by the files; the index is shipped anyway, opt-in, by the
developer's decision of 2026-10-28. Recall output stays within budget × 3.5
bytes at every size.

## Limits

- Without `fcntl` (not POSIX) two closes in one clone are last-writer-wins on
  the batch; on POSIX they serialise on `.ai/local/memory/lock`.
- The same slug started in the same UTC minute in two clones gives one id;
  after the merge `memory verify` reports the two seals (V3), `memory export
  <id>` records them as a `conflict`, and `memory show` renders both. Nothing
  is merged or renamed silently. For a key with a recorded conflict V4 checks
  no digest, because which entries belong to which seal is not knowable from
  the lines alone.
- The dialog's `decision_*` and `consent_*` journal lines are dropped (KEEP_RULES
  v1, spec §D3); the pick id survives on the approval, answer or override it
  produced, and the dialog's own trace stays local.
- `migrate --apply [--risks]` and `restore` do not take the human route: they
  only add records or bring files back, and `--apply` keeps a backup tar of
  `.ai/reports/` and `known-risks.md` first. The one migration step that
  removes committed files, `--move-logs`, is the human's.
- The pre-push shim looks for the validator beside the module that wrote it, in
  `~/.claude/hooks/` and `$CODEX_HOME/hooks/`, then runs
  `skills/ai-task/memory_sync.py` itself (a Codex install copies that tree);
  when none is found it warns and lets the push through, and `memory status`
  says "validator missing".
- The FTS5 prefilter is used for ASCII query tokens only; other queries scan.
- Recall estimates tokens; it does not run a tokenizer.
