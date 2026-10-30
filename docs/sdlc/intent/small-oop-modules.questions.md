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
