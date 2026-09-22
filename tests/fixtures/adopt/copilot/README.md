# GitHub Copilot fixture

Source: https://docs.github.com/copilot/customizing-copilot , https://code.visualstudio.com/docs/agent-customization/prompt-files
Checked: 2026-09-22

Layout assumed:
- `.github/copilot-instructions.md` (plain Markdown, no frontmatter) and `.github/instructions/` are the signatures.
- `.github/instructions/*.instructions.md`, frontmatter `applyTo` (one comma-separated glob string), optional `description` and `excludeAgent` (`code-review` | `cloud-agent`).
- `.github/prompts/*.prompt.md` exists but is not a root: `.github/` is never a root, only the exact paths above.

Corrections to spec I2: the rule row's frontmatter map gains `"title": "description"`;
`excludeAgent` has no equivalent and is logged to `dropped.jsonl` like any rewritten key.
