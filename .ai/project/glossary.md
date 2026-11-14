# Glossary

| Term | Means here | In code |
|---|---|---|
| weight (W) | sum of six axes 0–2 scored from files, goal and declared axes | `skills/ai-task/weight.py:206` |
| mode | light / guarded / full / full_irreversible; sets the review tier, e2e and the human gate | `weight.py:239-247`, `rr_state/close.py:21-52` |
| behaviour 0/1/2 | the behaviour axis for hooks/skills changes: 0 no decision moves, 1 adds a deny/refusal, 2 allows what was denied or changes approval/install | CLAUDE.md, constitution C6 |
| tier (FAST/BALANCED/STRONG/EXPERT) | model ladder rung, not a model name | `profiles/*.json`, `rr_state/profile.py` |
| T0…T5 | old risk tiers, replaced by weight and mode | `docs/weight.md`, `MODE_TIER` |
| the two facts | (a) a green whole-suite verify on the current tree; (b) every changed file inside the task's files | `rr_state/report.py`, `close.py:78` |
| gate | the human approval a full-mode close waits for | `rr_state/gate.py`, `gate_cmd.py` |
| decision / pick / dialog | an AskUserQuestion offer recorded in the ledger; the picked command may run once, verbatim | `rr_state/dialog.py`, `hooks/guard/dialog.py`, `hooks/dialog-gate.py` |
| consent ledger | `.ai/state/consent.jsonl`, append-only offers/picks/uses | `rr_state/ledger.py`, `locks.py:58-84` |
| scope guard | refuses edits outside the step's files | `hooks/guard/scope.py` |
| golden | byte-compared record of guard decisions | `tests/fixtures/guard-characterization/golden.txt` |
| record / project memory | `.ai/memory/` packages written at close | `skills/ai-task/memory_*.py` |
| handoff | resume point `.ai/state/handoff.md` | `rr_state/handoff.py` |
| `AI_UNATTENDED` | marks a run with no human, which relaxes the terminal checks | `rr_state/fs.py:79` and four other copies |
| documents rule | a change whose files are all documents or all tests measures behaviour, domain and novelty as 0 | `weight.project.json` `documents`, `rr_state/policy.py` |
