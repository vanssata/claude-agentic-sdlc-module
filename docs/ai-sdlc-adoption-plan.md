# Assessment: quality → speed → cost

Date: 2026-09-18. Scope: **the distributable `claude-agentic` plugin**, its Codex/Claude adapters, context, routing and lifecycle. The local machine is a sample installation used for verification, not the main target of optimisation. Method: `ai-audit`, `plugin-creator`, read-only checks and isolated tests. The only change made by the analysis is this document.

## Clarification: plugin architecture and the leading plan

The goal is that installing the plugin improves **accuracy, time to an accepted result and cost per task** in every supported project. Packaging on its own does not reduce tokens. The effect comes from precise triggers, a small standing context, loading instructions on demand, deterministic checks and removing duplicate installations. The plan below leads; the general CI findings further down are its dependencies and secondary context.

**Current state:** there is a `.codex-plugin/plugin.json` that declares `skills/`, but the real full installation is a global copy (`README.md:96`, `install.sh:369`). Hooks live in `codex/hooks.json` with absolute host dependencies (`:10`); there is no standard `hooks/hooks.json`. Skills look in `~/.claude` first and then in `~/.codex` (`skills/ai-task/SKILL.md:17`), which with two installations can pick a different copy of the package. A native plugin install and `install.sh` must therefore not be treated as equivalent without an integration test.

Proposed boundary: **one versioned package with the shared logic; separate runtime adapters; in the project — its facts, decisions and task state; in the host configuration — only the registration that is required and the user's own choices.** Do not assume that `agents/` or global settings are activated automatically by the manifest. The current official documentation keeps `.codex-plugin/plugin.json` as a compatibility format and describes bundled skills/hooks; the migration guide requires an explicit adaptation of Claude agents/settings. [Packaging](https://developers.openai.com/plugins/build/plugins), [Runtime adaptation](https://developers.openai.com/plugins/guides/submit-claude-plugin).

| Order | Work on the plugin | Evidence of success |
|---|---|---|
| 1 | One canonical package root and version; package-relative helpers. Changes to `skills/*/SKILL.md`, the hook adapters and `install.sh`; the legacy migration keeps local edits. | A clean native install, a legacy install and a dual-runtime install find the right version without foreign global copies. Update/disable/uninstall leave no unexpected active behaviour. |
| 2 | A short entry `ai-task` router; the details of the direct/full pipeline in separate reference files. Short global rules in `AGENTS.snippet.md`/`CLAUDE.snippet.md`; the mandatory constraints stay reachable and mechanically enforced. | Measurably fewer instructions loaded at T0–T2; the same scope/security gates at high risk; an activation eval with no missed mandatory checks. The 387 lines of the current skill do not mean that every skill is loaded in full on every task. |
| 3 | A deterministic doctor for version, dependencies, paths, routing drift, duplicate skills/hooks and missing registration. Use the existing state/profile scripts instead of having the model re-derive the facts. | An unambiguous short status and fixtures for broken/outdated installations; no external MCP process just to read JSON locally. |
| 4 | A shared model/risk contract from `profiles/`; runtime-specific rendering instead of Claude model names in the shared workflow. The profile governs which delegations are allowed, with no hidden change to the current session. | Named-trigger tests, correct effective model/effort and a benchmark of completed tasks. An unknown subscription must not silently choose a more expensive profile — the current fallback is Pro (`install.sh:640`). |
| 5 | Native package lifecycle tests plus the current 16 suites in CI; a shared usage parser and a bounded eval set. | Two supported runtimes, zero double hook invocations, schema coverage and a comparison by first-pass acceptance, defects, p50/p95 time and usage per accepted task. |

This is a development plan for the plugin, not a request for a new installation or for an automatic change to host settings. Removing legacy copies is acceptable only after a successful migration and a check of who owns them.

## Conclusion and selection criterion

The largest proven opportunity is more reliable verification of the plugin and removing the mismatches between rules, installation and reports. There is no measurement proving which model completes real tasks fastest and with the fewest fixes.

The priority is **quality, then speed, then cost**: first the acceptance tests and the absence of critical defects; among the variants that pass — time to an accepted result, retries included; after that — use of the limit and spend. We do not optimise only time to first response or price per token.

Keeping Sol/medium for ordinary implementation, Terra/low for wide reading and tests, Sol/high for review and Astra/high for the designated expert cases is a reasonable **starting hypothesis**, not a proven winner. Check it with 12–20 representative tasks and identical acceptance criteria before changing the routing permanently. If the cheaper variant fails on quality, it is dropped regardless of cost.

## Inventory and proven findings

| Area | State and evidence | Practical action |
|---|---|---|
| Project | Dual-runtime plugin: shared prompts, Codex render; `README.md:39`, `scripts/render-codex-agents.py:83`. The working tree was clean. | Keep the shared source and the regression tests. |
| Own instructions | No root `AGENTS.md`/`CLAUDE.md` or `.ai/`; there are templates and host-wide rules. `.claude/settings.json:1` is an empty configuration. | A short root `AGENTS.md` with the real verify command and the architecture; `.ai/` through the existing init if the plugin is to be developed through the pipeline. |
| Runtime layout | Host: both Codex and Claude; Codex has 16 TOML agents with explicit model/effort. The repo has no project-local `.codex/` layout; the distributable resources are in `codex/`, `agents/`, `skills/`. | Do not duplicate the whole host configuration inside the project. |
| CI | `pylint.yml:10` tests Python 3.8–3.10; `python-package-conda.yml:23` points to a missing `environment.yml`. Neither job runs the real shell runner. | A PR/push workflow with `bash tests/run-all.sh`, Bash syntax, Python parse and ShellCheck; remove or replace the inapplicable Conda template. |
| Python contract | `scripts/merge-codex-config.py:31` uses `tomllib`; `install.sh:71` only checks that Python is present. | A declared and verified minimum of Python 3.11 for this code; CI on the minimum and the current supported version. |
| Tests | `tests/run-all.sh:11` includes all 16 `test-*.sh` and carries on after a failed suite. There is no Makefile/package build entry point. | The runner is a sufficient base; the lack of a package manifest is not a defect in itself for a shell plugin. |
| Release | The SLSA workflow generates literally `artifact1` and `artifact2`, not a plugin archive: `.github/workflows/generator-generic-ossf-slsa3-publish.yml:33`. | Provenance for the actual release archive, or disable the template until there is a real packaging step. |
| Documentation | Intent/spec/ADR templates; a real `docs/sdlc/plans/dual-runtime-agentic-routing.md`; no `REVIEW.md`. `docs/agents.md:3` has an outdated agent count. | Generated inventories and short review rules. |
| Synchronisation | The repo's `skills/ai-task/SKILL.md:61` and `:97` include scoped tests/e2e; the installed Codex and Claude copies still carry the previous rules. `cap-large-read.py` also differs in Claude. | A read-only doctor with versions/hashes and a diff; update through the existing installer, keeping local edits. A different hash does not necessarily mean an error. |
| Model | `~/.codex/config.toml:1` is Astra/medium, `:3` is fast; `~/.codex/AGENTS.md:42` and `profiles/codex-plus.json:3` set Sol/medium. | An explicit choice of baseline and showing the effective settings for a new task; the text in AGENTS does not change the active model. |
| Claude context | `~/.claude/settings.json:119` allows 75,000 characters of Bash output and 80,000 of task output; compaction is at 150,000. | Short extracts and log-reader first; a trial output cap of 8–12 thousand characters, with the full log in a file and extraction on demand. Do not cut away diagnostic evidence. |
| Usage reports | Two skills with the same name: `~/.agents/skills/usage-report` and `~/.codex/skills/usage-report`. The old one reads the legacy `token_count`, the new one `token_usage_record`. | One canonical parser for both formats, deduplication and fixtures for replay/resume; explicit schema coverage. |

## Scores against the 12 plays

0 = missing; 1 = partial/ad hoc; 2 = defined, with no proven enforcement; 3 = enforced and measured. The score is for this repository, not automatically for every project that uses the plugin.

| Play | Score | Basis |
|---|---:|---|
| 1. Intent | 1 | `docs/sdlc/intent/TEMPLATE.md:1`, the skill exists, no real intent in the inventory. |
| 2. Spec/policies | 1 | `docs/sdlc/specs/TEMPLATE.md:1`; `.ai/` is not initialised here. |
| 3. Plan | 2 | `docs/sdlc/plans/dual-runtime-agentic-routing.md:1`; no verified merge gate. |
| 4. Project instructions | 1 | Host instructions exist; no root project file; `skills/project-init/templates/AGENTS.md:1` is only a template. |
| 5. Skills | 2 | `skills/ai-task/SKILL.md:57`; active skills, but confirmed install drift. |
| 6. Subagents | 2 | `profiles/codex-plus.json:13`, `scripts/render-codex-agents.py:83`; declarative routing, no quality/latency benchmark. |
| 7. Feedback loop | 2 | `tests/run-all.sh:1`; a real runner, not a CI gate. |
| 8. Continuous evals | 1 | Fixtures and tests exist, but `.github/workflows/pylint.yml:21` does not run them. |
| 9. PR review loop | 1 | `skills/ai-task/SKILL.md:128` defines review; no PR workflow/REVIEW.md in the inventory. |
| 10. Hooks | 2 | `codex/hooks.json:3`, `hooks/ai-git-guard.sh:73`; runtime trust not confirmed. |
| 11. CI/CD | 1 | `.github/workflows/generator-generic-ossf-slsa3-publish.yml:33`; sample artifacts, unverified rollback. |
| 12. Closing the loop | not verified | No incident/tracker process provided, and no evidence of feedback into intent. |

## Plan in three phases

The dates are indicative windows, not an estimate of six weeks of continuous work. The owner roles are responsibilities; when working alone they can all be one person. The team/process context has not been confirmed.

| Phase | Concrete change and dependencies | Ownership, control and measurement |
|---|---|---|
| 1, weeks 1–2: foundation | `AGENTS.md`, `install.sh`, `README.md`, `.github/workflows/verify.yml`; fix the Python minimum and the inapplicable workflows. A read-only `scripts/doctor.py` for profile/install/hook drift. Plays 4/7/10 → 2–3. No prior dependency. | Engineer; a human approves the diff; all 16 suites on PR and push, the status as a merge requirement after checking the GitHub settings. Leading: share of PRs with the runner actually executed; lagging: escaped install/guard regressions. Source: CI/PR data. |
| 2, weeks 3–4: measurement | `skills/usage-report/usage-report.py`, `prices.json`, `tests/test-codex-usage-report.sh`; coverage of both schema formats, replay dedup, clear prices. `tests/evals/` and `docs/benchmarks/` for 12–20 real scenarios; `profiles/codex-plus.json` changes only on the results. Plays 6/8 → 3. Dependency: phase 1. | Tech lead/maintainer; identical criteria and a bounded benchmark budget. Leading: schema/scenario coverage; lagging: first-pass acceptance, review defects, p50/p95 time to an accepted result and usage per accepted task. Source: eval JSON. |
| 3, weeks 5–6: review/release | `REVIEW.md`, a PR review workflow and a fixed SLSA packaging workflow; `docs/sdlc/adr/` for the benchmark decision and incident feedback into intent/spec. Plays 9/11/12 → 2, then 3 with real evidence. Dependencies: evals + subagents before review; review + hooks before release; release + intent before feedback. | Maintainer/platform; human release approval, the review result visible in the PR, a sandboxed rollback rehearsal. Leading: PR/release coverage; lagging: repeated defects, rollback time and release failures. Source: PR/CI/incident records. |

## Guardrails

| Finding | Minimal measure |
|---|---|
| Without `.ai/` the path/scope guards do not act here (`hooks/ai-path-guard.sh:7`, `hooks/ai-scope-guard.sh:12`). | Initialise the plugin's own development if the pipeline is going to be used; do not present templates as active protection. |
| In `~/.codex/config.toml:113` I found trust entries for another project's hooks file, but not for the current global hooks. This does not prove the effective runtime state. | Check `/hooks` for every runtime in use, and safe deny fixtures. According to [OpenAI Hooks](https://developers.openai.com/codex/hooks), unreviewed/changed non-managed hooks are skipped. |
| Tests can be edited; a local hook does not replace an independent review/CI. | Review of weakened assertions and immutable base fixtures in CI; no blanket ban on legitimate new tests. |
| No proven protection at branch/server level. | Check the required checks and protections through GitHub once API access is restored. |

No credential files or secret values were read; a full secret-exposure audit is missing. This analysis alone gives no grounds to claim a compromise or a working end-to-end protection.

## Verification and open questions

`bash tests/run-all.sh`: **PASS**, all 16 suites, exit 0, about 33 seconds. Bash syntax (`bash -n`) and an AST parse of the Python files are also PASS. The first attempt was cut off by the 30-second tool timeout and is not counted as a result; the full run that followed completed successfully. The test runner agent used an isolated environment; no installation into the real host settings was performed. ShellCheck was not run because it is not installed. Passing fixtures do not prove effective hook trust in desktop or the quality of the models.

Not verified: team/owner, tracker, staging, server-side branch protection (the GitHub API connection failed), effective hook trust in desktop, release rollback, network/model latency, models on an identical benchmark and current validated API prices. None of these is assumed to be an established fact.
