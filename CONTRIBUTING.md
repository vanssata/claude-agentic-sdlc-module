# Contributing to RiskRails

Thanks for helping. This plugin decides what agents may do on other people's
machines and in their repositories, so a change is judged first by whether it
keeps that promise: **it should be harder for an agent to damage a project than
to make a small, well-defined change safely.**

## Before you start

- For anything bigger than a typo, open an issue first and say what you want to
  change and why. A guard rule, a weight axis or a model route that changes
  behaviour is easier to agree on before the code exists.
- Security problems do not go in a public issue. See [SECURITY.md](SECURITY.md).

## Setup

You need `git`, Node 18 or newer and Python 3.11 or newer (the scripts import
`tomllib`; CI runs 3.11 to 3.13). The guards emulate the part of `jq` they
once called and need no external tool; CI still checks that `bash`, `jq`,
`patch` and `diff` exist, because the update suites and one fixture use them.

```bash
git clone https://github.com/vanssata/claude-agentic-sdlc-module.git
cd claude-agentic-sdlc-module
node bin/riskrails.js --dry-run     # shows what an install would write, writes nothing
```

Install into your own runtime only when you want to try a change by hand
(`node bin/riskrails.js`), and restart the runtime afterwards.

This repository runs its own pipeline: read `.ai/AGENTS.md`, and run a change
through `/rr-build <request>` — it weighs the change, arms the scope guard and
runs the verification. `CLAUDE.md` holds the lessons earlier reviews taught.

## Tests

Locally, run the parallel runner: one process per test file, the same test ids
as `unittest discover`, the same `Ran N tests` / `OK` tail, exit 1 on anything
red, the two timed classes serial. CI runs the serial `unittest discover` as
the oracle, plus the end-to-end suite, on every pull request:

```bash
python3 -I tests/run_suite.py --serial test_guard_characterization.TestTimed --serial test_dialog_gate.TestGateFastPath
python3 -I -m unittest discover -s tests -p 'test_*.py'
AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py
pylint $(git ls-files '*.py')
```

The first line is `verify_command` in `.ai/policies/testing.md`, which
`state.py verify --scope all` runs. pylint comes from the distribution package
(`python3-pylint` on Debian and Ubuntu); `pylint` on `PATH` is what
`lint_command` calls.

Run the suite to the end and fix every failure before you push.

- A new suite is a `tests/test_*.py` file; discovery picks it up. A suite that
  reads repository documents is added to `doc_tests` in `testing.md`.
- No test may read or write the real `~/.claude` or `~/.codex`. Build a scratch
  directory and point the code at it, the way the existing suites do
  (`tests/install_harness.py`, `tests/guard_harness.py`).
- **A guard change is proved by the golden.** `tests/test_guard_characterization.py`
  compares the guard against 1 341 recorded decisions byte for byte. A change
  that moves no decision leaves the golden untouched; a deliberate rule change
  re-records it with `tools/golden-diff.py --record` and the diff is read
  record by record in the pull request. New rules come with fixtures under
  `tests/fixtures/*-guard/` that show the rule catching what it should and
  letting ordinary work through. `hooks/CLAUDE.md` says how the change is
  weighed.
- A bugfix shows its test failing first (`state.py verify --scope step --files
  <test> --expect fail`), then passing.
- Never loosen an existing assertion to make a change pass. If the old
  behaviour was wrong, say so in the pull request.

## Making a change

- Keep one pull request to one concern. A refactoring and a behaviour change go
  in separate pull requests.
- Both runtimes share one `.ai/` tree. A change to the pipeline, the state file
  or a hook must keep working under Claude Code **and** Codex; the end-to-end
  suite drives one task through both.
- If you accept a risk instead of fixing it, record it with `state.py memory
  risk add` and, when it concerns a user, add it to
  [docs/known-risks.md](docs/known-risks.md) in the same shape as the other
  entries (risk, why it stays, limits, what to do, source).
- A shared policy, agent contract, workflow or template lives once, in `ai/`;
  the installer puts it at `<home>/riskrails/ai/` and projects read it from
  there. A project-owned one lives in `skills/ai-init/templates/.ai/`. Moving a
  file from one side to the other is a migration under
  `skills/project-update/migrations/`, never a plain move. After changing a
  project-owned template, run `tools/build-template-history.py` and commit the
  result; shared files keep only their hashes there. After editing a
  `weight.json` template, run `state.py --root skills/ai-init/templates weight
  --mirror`.
- The instruction block has one source, `instructions/stub.md`; the rendered
  templates are build artefacts and `render_instructions.py build --check`
  fails on drift. Shared prompts name tiers, never models.
- Update the documentation in `docs/` that describes what you changed.

## Commits and pull requests

- Commit subjects follow the style in `git log`: the task id and what it did,
  or `feat:`, `fix:`, `docs:`, `test:`, `chore:` with an optional scope.
- Describe what changed, why, and how you verified it: the commands you ran
  and their result.
- Every change lands on `main` through a reviewed pull request. No agent
  commits, pushes or merges; the pipeline ends at `/rr-ship`.

## Releases

A release bumps `version` in `package.json`, `.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json`, the badge and the version line at the top of the
README, and the version named in `docs/known-risks.md`, all in one commit. It
is then tagged `vX.Y.Z` and published to npm from CI with provenance; `npm
publish` from a developer machine is refused by the git guard on purpose.

## License

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE).
