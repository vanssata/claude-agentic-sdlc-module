# Questions — small-oop-modules
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Scope of the split: which files does this spec cover?
asked: 2026-10-30T23:06:50Z · stage: intent
context: Measured 2026-10-31: wc -l; the sections state.py already draws are the natural module seams
A. skills/ai-task/state.py only (5 256 lines, 239 functions, 0 classes)
B. every Python file over 1 000 lines in one spec and one plan — state.py, adopt.py (2 219), update.py (2 114), memory_sync.py (1 571), hooks/guard/paths.py (1 452), hooks/runtime-gate.py (1 214)
C. state.py as WP1 with its own plan and task; the other five as later work packages under the same spec, each with its own plan, task and golden, in the order of their size (recommended)
X. Other — answer as `X: <text>`
[Answer]: C — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z

## Q2. The entry point: what happens to the path every caller uses?
asked: 2026-10-30T23:06:50Z · stage: intent
context: grep -rln ai-task/state.py → 109 files; tests/test_ai_task_state.py:26-35 imports state from sys.path; hooks/memory-pre-push.py:19 inserts skills/ai-task on sys.path
A. skills/ai-task/state.py stays, as a thin CLI entry (argparse, dispatch, main) over a package skills/ai-task/rr_state/ — the 109 files that name the path, the test shim (import state; state.main()), bin/riskrails.js:368 and the installed copy are untouched (recommended)
B. a new package entry and the 109 references rewritten
X. Other — answer as `X: <text>`
[Answer]: A — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z

## Q3. Shape of the modules: how far does the OOP go?
asked: 2026-10-30T23:06:50Z · stage: intent
context: 70 module globals and 239 functions; sensors.py, weight.py and memory_*.py are already sibling modules imported by sys.path
A. one module per seam the file already draws (journal and questions, profile, gates, dialog, the schema-7 surface, batch, start/verify/review/close, compact record), with a class only where state is threaded through many functions — the task record, the journal, the resolved profile, the runtime context; no class per command (recommended)
B. a command class per subcommand and a full hierarchy
C. modules of functions only, no classes
X. Other — answer as `X: <text>`
[Answer]: A — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z

## Q4. Proof that no behaviour changes (C2, C3): what pins the refactoring?
asked: 2026-10-30T23:06:50Z · stage: intent
context: tests/test_guard_characterization.py is the precedent for the hooks port
A. characterization first — the existing suites plus a new CLI golden recorded on the tree before the split (every subcommand's --help, and a scripted task run's stdout, journal and task.md with timestamps normalised), byte-identical after; each WP green on verify --scope all and e2e before the next starts (recommended)
B. the existing suites only (214 state tests, e2e, pylint 10/10)
X. Other — answer as `X: <text>`
[Answer]: A — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z

## Q5. Order of work: where does this refactor sit against everything else on the roadmap?
asked: 2026-10-30T23:06:50Z · stage: intent
context: Developer instruction of 2026-10-31 (verbatim, Bulgarian): всички останали трябва да се блокират до окончателното завършване на този голям рефактор — изключение прави само текущия фикс на известните рискове
A. next after the risk burndown in flight (T-2026-10-30-2251-risk-burndown-b5 and the rest of its loop); every other row — ROADMAP §1 operating modes, §2 open rows, the multi-agent intent — is blocked until the last WP of this spec closes (recommended)
B. interleaved with the open rows as capacity allows
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose instruction of 2026-10-31, recorded by claude via prose at 2026-10-30T23:06:50Z

## Q6. An open risk or a bug met while splitting: what does the refactoring do with it?
asked: 2026-10-30T23:06:50Z · stage: intent
context: state.py recall --files skills/ai-task/state.py lists 158 items, 18 shown
A. records it in the register (state.py memory risk add) and moves on; a fix is its own bugfix task after the WP closes — a refactoring changes no behaviour (C3), and a bugfix starts with its failing test (C2) (recommended)
B. fixes it in place when it is small
X. Other — answer as `X: <text>`
[Answer]: A — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z

## Q7. bin/riskrails.js (1 442 lines, JavaScript, the installer): in or out?
asked: 2026-10-30T23:06:50Z · stage: intent
A. out — a different language and toolchain, and a change to how user projects are installed scores behaviour 2 (C6, weight.json examples), so it would drag every WP into full mode (recommended)
B. in, as the last WP
X. Other — answer as `X: <text>`
[Answer]: A — by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:51Z

## Q8. The risk-aware multi-agent intent that triggered this spec: what is written now?
asked: 2026-10-30T23:06:51Z · stage: intent
context: Developer: това трябва да е опционален модул, който да се добави след като се завърши разделянето на малки ООП модули … може би само го запиши като следваща задача
A. an intent file only — docs/sdlc/intent/risk-aware-multi-agent-adlc.md with the capability assessment, the gap list and the reduced scope, status blocked by this spec; its spec and plan are written after the last WP closes, against the split code (recommended)
B. its spec now, alongside this one
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose instruction of 2026-10-31, recorded by claude via prose at 2026-10-30T23:06:51Z

## Q9. Classes: which of the spec's six survive the external review of 2026-10-31?
asked: 2026-10-31T17:17:31Z · stage: intent · by: claude
context: review: a rich TaskState may complicate serialisation and compatibility; OOP only for a resource or transaction holder, a transition with invariants, a dependency seam, a value object. load returns the plain dict (state.py:377, :423); ledger_lock holds consent.lock by O_EXCL (state.py:2513)
A. three — Runtime and Profile as frozen dataclasses (value objects), Ledger as the one resource-holding class (lock, append, read, mirror); the task record stays the dict load/save return today, the JSON being the contract hooks, tests and both runtimes read; journal and questions file stay functions over a path (recommended)
B. the six of the 2026-10-31 spec — TaskState, Journal, Runtime, Profile, Ledger, QuestionsFile
C. none — functions and dicts only
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q10. Hook isolation: may rr_state and hooks/guard share code?
asked: 2026-10-31T17:17:32Z · stage: intent · by: claude
context: hooks run as python3 -I -S, stdlib only (hooks/ai-guard.py:27, hooks/dialog-gate.py:17); hooks/guard/dialog.py:21-27 imports only the stdlib; review: merging them into one architecture can break the security boundary
A. no — nothing under hooks/ imports skills/ai-task/rr_state and nothing under rr_state imports hooks/guard; the duplication between hooks/guard/dialog.py and rr_state/dialog.py is intentional and stays; the layout test fails on either import; WP5 and WP6 split inside hooks/ only (recommended)
B. one shared package under skills/ that the hooks import too
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q11. Forbidden constructs: what does the layout test refuse under rr_state/?
asked: 2026-10-31T17:17:32Z · stage: intent · by: claude
context: review: S is the useful SOLID letter here; D and I only at I/O boundaries; O on proven need; L irrelevant without inheritance
A. no inheritance and no Abstract/ABC base, no dependency-injection container, no interface or Protocol with one implementation, no repository or service class per JSON operation, no class that is only a namespace of static methods — the layout test greps for ABC, abstractmethod, Protocol, staticmethod and any class base other than a dataclass or Exception, and fails (recommended)
B. allow them where a reviewer argues for one
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q12. Core and shell: where do pure functions, I/O and the seams live?
asked: 2026-10-31T17:17:42Z · stage: intent · by: claude
context: sensors.py is the precedent (state.py:84 'measurement only; it never writes this file'); the suites patch state_mod.json.dump and state_mod.os as module attributes
A. functional core, imperative shell — parse, render and decide functions take data and return data (policy, questions parsing and rendering, weight, step ordering, the two facts); I/O sits in fs, locks, journal, task load/save, ledger and the command modules; the clock and command-runner seams stay module-level functions (fs.now, fs.now_ms, fs.run_text, sensors.git) a test patches as module attributes — no Clock or Runner object, no injected parameter (recommended)
B. inject a clock and a runner object through every command
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q13. Granularity: the spec's nine-layer ladder or the review's eight files?
asked: 2026-10-31T17:17:42Z · stage: intent · by: claude
context: review: 'only moving functions into many files gives navigation, not design'; the ladder came from the import graph (independent check B2); the review's lifecycle.py alone would hold start, steps, verify, review and close, about 2 000 lines
A. the ladder stays the partition, read as eight responsibility groups — store (fs, locks, task), journal, questions, decisions (ledger, gate, dialog, authority), lifecycle (start, steps, verify, review, close), profile and runtime, reporting (report, handoff), cli; a module exists for one cohesive responsibility, never to satisfy the 600-line layout test, and two modules of one group merge when the import graph allows (recommended)
B. the review's eight files — state_store, journal, questions, decisions, lifecycle, profile, cli, entry
C. one module per section comment of today's file, no layers
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q14. Timing: when does WP1 start against T-2026-10-31-1650-dialog-background?
asked: 2026-10-31T17:17:42Z · stage: intent · by: claude
context: review: must not be mixed with the current task on state.py and dialog.py; C3; handoff 2026-10-31T17:13 shows that task at its approval gate, files hooks/guard/dialog.py and skills/ai-task/state.py
A. the golden is recorded and the WP1 task started only after that task and every other task editing state.py or hooks/guard/dialog.py has closed; the golden is re-recorded if any such task lands between the recording and the first move (recommended)
B. start WP1 now on a branch and rebase later
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the external review of 2026-10-31 (over 70 % confident, developer's rule of 2026-10-31) via prose at 2026-10-31T17:17:46Z

## Q15. Does the split still block every other roadmap row (Q5), after the two reviews of 2026-10-31?
asked: 2026-10-31T17:41:16Z · stage: intent · by: claude
context: session and Codex Astra (gpt-6-astra) both: the split lowers context for later changes but not approvals, artefacts or tokens per task; policy simplifications and urgent fixes need no new package. Q5 was the developer's instruction and only the developer changes it
A. the split blocks only work that edits state.py internals or the extracted interfaces; the policy tasks of the Optimisation section (classification, activity scope, review rule, spec budget, measurement) and urgent fixes run as separate tasks, never mixed with a WP (recommended)
B. Q5 stands — everything waits for WP6
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov, reply 'Only state.py work' in the app, recorded by claude via picker at 2026-10-31T17:46:24Z

## Q16. The 600-line limit of R3: a failing check or an advisory measure?
asked: 2026-10-31T17:41:16Z · stage: intent · by: claude
context: Astra: 'remove arbitrary architecture quotas; make 600 lines advisory, let actual invariants justify classes'; session: a module exists for a responsibility, never to satisfy the limit (Q13)
A. advisory — the layout test prints module sizes and fails only on an import cycle, an upward edge, a global statement, a forbidden construct or a hooks/rr_state crossing; a module over 600 lines is noted in the task report with the reason (recommended)
B. a failing check at 600 lines
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31 (over 70 % confident, developer's rule) via prose at 2026-10-31T17:41:29Z

## Q17. Classes: a quota of three, or a rule?
asked: 2026-10-31T17:41:16Z · stage: intent · by: claude
context: Q9 named three; Astra reads a fixed count as a quota
A. a rule — a class needs a named resource it holds or an invariant it keeps, written in its docstring; Runtime, Profile and Ledger are the three that pass it today, and a fourth needs the same sentence, not a spec change (recommended)
B. exactly three, by name
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31 (over 70 % confident, developer's rule) via prose at 2026-10-31T17:41:29Z

## Q18. The optimisation proposals outside the split: where are they recorded and in what order?
asked: 2026-10-31T17:41:28Z · stage: intent · by: claude
context: merged from the session's six and Codex Astra's seven (2026-10-31); Astra: classification first, then activity scope, then review strength; the Codex freeze after those; the spec budget as defaults with justified exceptions; the state-file merge only after an ownership audit
A. in this spec's Optimisation section as separate tasks, none inside a WP, in the order: task classification (no keyword hints, light trial at W<=3), activity scope for documents (named paths per activity, no blanket docs/sdlc/** allow), review strength by named risk (reason mandatory; STRONG for domain, irreversibility or an approval-boundary change), spec budget as defaults, runtime and cost measurement per task, state ownership audit before any merge (recommended)
B. a separate spec for the optimisations
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31 (over 70 % confident, developer's rule) via prose at 2026-10-31T17:41:29Z

## Q19. WP6 (hooks/runtime-gate.py, Codex trust on a changed hook entry): keep it in the order, or make it conditional?
asked: 2026-10-31T17:41:29Z · stage: intent · by: claude
context: both reviews: freeze new Codex-facing capability until usage is measured; transcripts show no Codex sessions, which is not proof of none (Astra); FC5 already doubts WP6 is splittable
A. WP6 stays last and becomes conditional — planned only after the measurement task shows Codex in use, or when a Codex-side bug forces a change to the file; WP1–WP5 are unaffected (recommended)
B. WP6 stays unconditional
X. Other — answer as `X: <text>`
[Answer]: A — by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31 (over 70 % confident, developer's rule) via prose at 2026-10-31T17:41:29Z
