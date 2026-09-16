# How agents work in this repository

This directory is the contract between the people who own this codebase and any
AI agent that works in it. Read this file first; it tells you where everything
else is and what you are allowed to do.

## The rule that outranks the others

**Production behaviour is the source of truth.** This is an existing system with
real users. Code that looks wrong may be load-bearing. Document what you find;
change only what the task asked for.

Full rules: `policies/safety.md`. Read it before your first edit.

## What is where

| Directory | What it holds |
|---|---|
| `project/` | what this system *is* — architecture, modules, integrations, business rules, legacy, risks, glossary |
| `policies/` | what agents may and may not do — safety, production, coding, testing, security, database, git, release, context, model routing, risk tiers |
| `agents/` | the role each agent plays and what it must return |
| `workflows/` | the pipeline for a feature, a bugfix, a refactoring, a hotfix, an investigation |
| `templates/` | the shape of every artifact a task produces |
| `state/` | the current task's machine-readable state (not committed) |
| `reports/` | one directory per task: its context, plan, reviews and release report (committed) |

## The pipeline

```
REQUEST
  → DISCOVERY            what exists, where, who calls it
  → CONTEXT              the compressed, structured summary
  → IMPACT ANALYSIS      what this change reaches
  → RISK CLASSIFICATION  T0 … T5, from policies/risk-tiers.json
  → PLAN                 steps, each with the files it may touch
  → PLAN REVIEW          for T3 and above
  → IMPLEMENTATION       one approved step at a time
  → TEST
  → ADVERSARIAL REVIEW   assumes the implementation is wrong
  → SECURITY REVIEW      mandatory for T4 and T5
  → RELEASE REPORT
  → HUMAN APPROVAL
```

Stages are lightweight for a small change and heavy for a dangerous one. None of
them is skipped because the task "looks easy" — that judgement is exactly what
the risk classification exists to replace.

Run it with `/ai-task <what you want>`. Check where a task stands with
`/ai-status`.

## Evidence labels

Everything written into `project/` is labelled:

- **KNOWN FACT** — read from code, config, a migration or a test, with `file:line`.
- **INFERENCE** — a conclusion, with what it was drawn from.
- **UNKNOWN** — it matters, it could not be determined, and here is what would answer it.
- **RISK** — this looks dangerous, and here is what could go wrong.

An inference is never written as a fact. Where the documentation and the code
disagree, both are recorded, with the evidence, and a human decides which is the
bug.

## Scope

Each implementation step names the files it may touch. Anything else is refused
by a hook, and the answer is `SCOPE_CHANGE_REQUIRED`: stop, say what you need and
why, let the plan be amended. Silent scope growth is the failure mode this whole
system is built to prevent.

## Keeping this directory true

`project/` describes the system as it was last surveyed. When you discover that
it is wrong, fix it in the same task — a knowledge base nobody trusts is worse
than none. Re-run `/ai-init` after a large change to refresh it.
