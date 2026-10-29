# Hook performance — the hot path

The guard runs on **every** tool call of every session, in every mode. Its cost
is paid on every `Edit`, `Read` and `Bash`, so it is measured, budgeted and
proved behaviour-preserving.

## The rule that comes first

A guard is judged by its decisions, not by its speed. The characterization
suite records every decision the guard makes — exit code and the full deny
text — for 1 341 payloads under `tests/fixtures/guard-characterization/`
(`golden.txt`), and `tests/test_guard_characterization.py` compares the guard
against that record byte for byte. A performance change, a port, a refactoring
of the engine runs with the golden untouched; if a record moves, the change
moved a decision and is not a performance change. A deliberate rule change
re-records with `tools/golden-diff.py --record` and reads the diff record by
record (`changed / added / removed`); `tools/golden-diff.py` with no argument
compares the working golden against HEAD and exits 1 if anything moved.
`hooks/CLAUDE.md` says how such a change is weighed: behaviour 0 when the
golden is byte-identical, 1 when a deny is added or its text changes, 2 when
something that was denied is allowed.

## The budget

One process per tool call: `python3 -I -S hooks/ai-guard.py`, which imports
the check modules lazily and only for the tools that need them (`git` on
`Bash`; `paths` on reads, writes and `Bash`; `scope` on writes; `decision` on
everything while a decision file exists). The budget is a test, not a
document: `TestTimed` in `tests/test_guard_characterization.py` runs each case
five times and requires the median under its budget, scaled by
`AI_TIMED_FACTOR` on a slow machine.

| Case | Budget |
|---|---|
| `Bash`, a 1 KB command that touches nothing guarded | 40 ms |
| `Edit` inside the step | 25 ms |
| `Write` inside the step | 25 ms |
| `Read` of an ordinary file | 25 ms |
| `Bash`, the 20 KB `sh -c` fixture (`sh-c-20k.txt`) | 100 ms |

Each case must exit 0 with empty output. `verify_command` runs the timed class
serially, outside the parallel pool (`--serial
test_guard_characterization.TestTimed`), so the numbers are not skewed by the
other suites. The dialog gate's fast path has its own timed test,
`tests/test_dialog_gate.py::TestGateFastPath`: with no decision file the
`decision` check is one `stat`, so the `*` matcher costs nothing measurable
when nothing is pending.

## What the hot path does

For a payload that touches nothing guarded the path check is one in-process
regex pass over the path (or the command text) against a loose pattern built
from every list; only a hit opens the full classification — anchoring under
the project roots, the resolved path, `sh -c` and `eval` segmentation,
interpreter one-liners, the human-only verbs. The git check has the same
shape: a cheap prefilter on the command's first words (`git`, `gh`, `argocd`,
`helm`, `kubectl`, …) keeps every other command off the path. The scope check
reads `.ai/state/state.json` only during an implementation step.

## What is deliberately not done

- No daemon, no cache across calls: a hook that keeps state is a hook that
  can be wrong after a `git checkout`.
- No shell helpers: the engine is pure Python so the process count is one.
- No early exit that skips a list: the fast path proves *nothing matched*,
  it never guesses.

## How to measure

```bash
python3 -I -m unittest discover -s tests -p test_guard_characterization.py -k TestTimed
AI_TIMED_FACTOR=2 python3 -I tests/run_suite.py tests/test_guard_characterization.py   # a slow machine
time printf '%s' "$PAYLOAD" | python3 -I -S hooks/ai-guard.py                          # one call by hand
```

`$PAYLOAD` is any fixture under `tests/fixtures/*-guard/`. There is no
separate bench script: the timed class is the measurement and the regression
gate in one.

## Where the remaining cost is

Interpreter start-up. `-S` keeps `site` out, the modules are imported lazily,
and the fixtures are small, so the floor is Python itself — about the same as
the 25 ms budget on a developer machine. A payload over 4 KB that names a
guarded path is refused outright rather than scanned, which is both the
cheaper and the safer answer.
