# Review report — T-2026-10-20-001

Reviewer: `ai-reviewer`, STRONG tier (model `opus`), one pass over `git diff`, read-only.
Verdict: **pass**. No BLOCKER, no HIGH. Probes in the task scratchpad (`mine.sh`,
`cases-a.sh` … `cases-g.sh`), each run against the working tree and against the
HEAD guard.

## Findings

| sev | where | finding | disposition |
|---|---|---|---|
| MEDIUM | `.ai/project/known-risks.md` residual 2; filter `hooks/ai-path-guard.sh:417` | The residual "the shell splits words on ASCII blanks only" is false: `set -- '/bin/sh　-c　rm -f ST'; IFS='　'; $1` (U+3000) was denied at HEAD and is allowed now, and bash runs it. The bytewise filter misses blanks that bash's `[[ =~ ]]` matches in the inherited UTF-8 locale. The `IFS=,` sibling was already allowed at HEAD. | R1: record corrected (allow-side residual, named and measured). No code change: restoring that deny is a design change outside the approved plan — for the human. |
| LOW | `hooks/ai-path-guard.sh:403`, caller `:605` | The 64-candidate cap counts prose that mentions `sh -c`: 70 × `echo "use bash -c …"` + `rm -f a.txt` went allow → deny; the refusal text (`WHY_WORK_CAP`) speaks of paths. | R1: recorded in the deny-side residual. The cap of 64 is the approved plan's. |
| LOW | `.ai/project/known-risks.md` residual 3 | One inner unit can start just before 6 s: 400 KB → deny at 6.4 s, 800 KB → 7.8–8.3 s (HEAD > 15 s). | R1: residual restated with the measurements and a pointer to "quadratic on long lines". |
| INFO | `segments_of` `sh_re` | `bash --norc -c`, `bash -o posix -c`, `sh -c --`, `sh -c 2>/dev/null '…'`, `'sh' -c`, `IFS=,` splitting are not read — HEAD and new alike. | R1: new open entry in known-risks. |
| INFO | `:417`, `:633` | A grep that errors yields no candidates (allow), as `ere_match` already does; no realistic trigger. | noted |
| INFO | `.ai/reports/T-2026-10-15-004/` | 5 extra lines in `events.jsonl` and an untracked `state.json` — present in `git status` at the start of this session, before this task; not this diff. | noted |

## Examined and clean

Movers filter is a superset of what the loop acts on (11 cases, same decision HEAD
and new); `return 3` leaves `segments_of` with no partial output; `SECONDS`
carries into `$( )`; ordinary lines cost the same (55–56 ms); the 12 deny-side
`sh -c`/`eval` variants the ledger marked unverified deny in HEAD and new; the
known-risks line numbers are right; the tests only add.
