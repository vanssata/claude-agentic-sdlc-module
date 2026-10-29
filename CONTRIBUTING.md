# Contributing to claude-agentic

Thanks for helping. This plugin decides what agents may do on other people's
machines and in their repositories, so a change is judged first by whether it
keeps that promise: **it should be harder for an agent to damage a project than
to make a small, well-defined change safely.**

## Before you start

- For anything bigger than a typo, open an issue first and say what you want to
  change and why. A guard, a risk tier or a model route that changes behaviour
  is easier to agree on before the code exists.
- Security problems do not go in a public issue. See [SECURITY.md](SECURITY.md).

## Setup

You need `bash`, `git`, `jq` and Python 3.11 or newer (the scripts import
`tomllib`). Nothing else is installed for development.

```bash
git clone https://github.com/vanssata/claude-agentic-sdlc-module.git
cd claude-agentic-sdlc-module
./install.sh --dry-run    # shows what an install would write, writes nothing
```

Install into your own runtime only when you want to try a change by hand, and
restart the runtime afterwards.

## Tests

Locally, run the parallel runner: one process per test file, the same test ids, the
same `Ran N tests` / `OK` tail, exit 1 on anything red (about a minute and a half).
CI runs the serial `unittest discover` below as the oracle, plus the end-to-end suite,
on every pull request:

```bash
python3 -I tests/run_suite.py
python3 -I -m unittest discover -s tests -p 'test_*.py'
AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py
```

```bash
pylint $(git ls-files '*.py')
```

pylint comes from the distribution package (`python3-pylint` on Debian and
Ubuntu); no `pip` install is needed — `pylint` on `PATH` is what
`lint_command` in `.ai/policies/testing.md` calls.

Run the suite to the end and fix every failure before you push.

- A new suite is a `tests/test_*.py` file; `unittest discover` picks it up.
- No test may read or write the real `~/.claude` or `~/.codex`. Build a scratch
  directory and point the code at it, the way the existing suites do.
- A guard change comes with fixtures that show the new rule catching what it
  should and letting ordinary work through.
- Never loosen an existing assertion to make a change pass. If the old
  behaviour was wrong, say so in the pull request.
- When the number of suites or assertions changes, update the count in the
  **Tests** section of the README.

## Making a change

- Keep one pull request to one concern. A refactoring and a behaviour change go
  in separate pull requests.
- Both runtimes share one `.ai/` tree. A change to the pipeline, the state file
  or a guard must keep working under Claude Code **and** Codex, and the
  end-to-end suite proves that.
- If you accept a risk instead of fixing it, add it to
  [Known risks](README.md#known-risks) in the same shape as the other entries
  (risk, why it stays, limits, what to do, source).
- A shared policy, agent contract, workflow or template lives once, in `ai/`;
  `install.sh` puts it at `<home>/claude-agentic/ai/` and projects read it from
  there. A project-owned one lives in `skills/ai-init/templates/.ai/`. Moving a
  file from one side to the other is a migration under
  `skills/project-update/migrations/`, never a plain move. After changing a
  project-owned template, run `tools/build-template-history.py` and commit the
  result; shared files keep only their hashes there.
- Update the documentation in `docs/` that describes what you changed.

## Commits and pull requests

- Commit subjects follow the style in `git log`: `feat:`, `fix:`, `docs:`,
  `test:`, `chore:`, with an optional scope, e.g. `fix(codex): …`.
- Describe what changed, why, and how you verified it: the commands you ran and
  their result.
- Every change lands on `main` through a reviewed pull request.

## Releases

A release bumps `version` in `.codex-plugin/plugin.json`, the version badge and
the **Version** line at the top of the README, and the version named in
**Known risks**, all in one commit. It is then tagged `vX.Y.Z`.

## License

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE).
