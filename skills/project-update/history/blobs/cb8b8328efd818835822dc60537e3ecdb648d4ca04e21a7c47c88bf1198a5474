# Testing policy

Tests describe behaviour. Coverage percentage is a side effect, not a goal.

## Characterization first

Before changing behaviour that is not covered by a test — which is most legacy
behaviour — write a test that passes against the code **as it is today**. That
test is the definition of what must not break. Only then change the code.

```
characterization test → refactor → verify identical behaviour → feature change
```

Never do those in one step, and never in one commit.

## What to consider, by kind of change

| Change touches | Also test |
|---|---|
| a shared service | the existing callers, not only the new one |
| money, tax, fiscal | rounding, currency, negative and zero amounts, refunds |
| a state machine | every transition that is now reachable, and the ones that must stay unreachable |
| an async consumer | retry, double delivery, out-of-order delivery, poison message |
| an external integration | timeout, 500, malformed response, partial write |
| a write path | idempotency, concurrency, transaction boundaries |
| authorization | the negative case, for every role |
| a public API or event | the old shape still works |

## Reading a failure

Classify before fixing. The four answers are:

- **EXISTING TEST FAILURE** — it failed before this change too. Say so, do not
  fix it inside this task.
- **NEW REGRESSION** — this change broke it. Fix the code, not the test.
- **TEST ENVIRONMENT FAILURE** — database, fixtures, network, container. Say what
  is missing.
- **UNKNOWN** — you could not tell. Say what you tried.

**Never edit a test to make it pass when production behaviour changed
unexpectedly.** A test that suddenly disagrees with the code is evidence, and
deleting evidence is the worst available option.

## Verification

One command that proves the project is healthy, and what healthy looks like.
`/ai-task` runs it once, after the last implementation step and before
reporting a task done; during a step only the step's own single test runs, when
it is cheap. A bugfix additionally shows its new test failing first. Keep it to one
command — chain the pieces in a Makefile or composer script if there are several.

```
verify_command:      # e.g. make check   |   composer qa && vendor/bin/phpunit
healthy_output:      # two or three lines of what a green run ends with
runtime:             # roughly, so a hang is recognisable
single_test:         # how to run one test, for the bugfix loop
```

## Project specifics

<!-- The real commands: how to run unit tests, integration tests, a single test.
     Where fixtures live. What the CI runs. Cite the config. -->
