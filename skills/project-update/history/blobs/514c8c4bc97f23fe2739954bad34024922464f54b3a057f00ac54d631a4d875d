<!-- claude-agentic:start -->
## AI agent workflow

This repository has an agentic engineering setup under `.ai/`. Read
`.ai/AGENTS.md` before making any change.

- Production behaviour is the source of truth. Document problems you find outside
  the task; do not fix them.
- Work runs through `/ai-task <request>`: discovery, context, impact, risk tier,
  plan, implementation, test, review, security review, release report, human
  approval. `/ai-status` shows where a task stands.
- Each implementation step names the files it may touch. Editing anything else is
  refused; answer `SCOPE_CHANGE_REQUIRED` and let the plan be amended. One
  `apply_patch` is checked file by file, so a patch that reaches outside the step
  is refused whole.
- The risk tier in `.ai/policies/risk-tiers.json` decides who reviews the change
  and whether a human must approve it. Payments, tax, fiscal, auth and order
  state transitions are T4 by default.
- Delegate to the named agents rather than asking for "a subagent": `ai-discovery`
  and `Explore` to read, `ai-reviewer` and `ai-security` to review, `ai-expert`
  only on a T5 or irreversible decision. A spawn with no agent named runs on the
  default subagent model.
- If this repository also has a `CLAUDE.md`, it describes the same pipeline for
  Claude Code. `.ai/` holds the one set of policies and task state both obey.
- No agent commits, merges or deploys on its own initiative.
<!-- claude-agentic:end -->
