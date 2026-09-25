# Security policy

## Supported versions

Only the latest release gets security fixes. Upgrade before reporting an issue
against an older version.

| Version | Supported |
|---|---|
| 2.0.x | yes |
| < 2.0 | no |

## What counts as a vulnerability

claude-agentic installs hooks, guards and routing rules into Claude Code and
Codex. These are in scope:

- a guard (`ai-path-guard`, `ai-scope-guard`, `ai-git-guard`) letting through a case it is documented to block, for example reading
  a production secret, editing outside the approved step, force-pushing or
  deploying
- a way for a tool call from the agent to grant human approval or answer a gate
  question without a human
- the installer or `/project-update` overwriting, leaking or corrupting a user's
  configuration, credentials or unrelated files
- command injection or path traversal in any script, hook or skill this plugin
  ships
- anything that sends user data to a place the user did not configure

These are **not** vulnerabilities, because they are documented limits. See
[Known risks](README.md#known-risks):

- bypassing a guard on purpose through obfuscation. The guards are a tripwire,
  not a sandbox.
- behaviour under `AI_UNATTENDED=1`, which turns the human gates off by design
- Codex hooks that the user has not reviewed and trusted
- budgets and quotas being advisory

A report that shows one of these limits is wider than the Known risks entry
says is welcome.

## Reporting a vulnerability

**Do not open a public issue or pull request.**

Report it privately through GitHub:
[Report a vulnerability](https://github.com/vanssata/claude-agentic-sdlc-module/security/advisories/new).

Include:

- the version (`version` in `.codex-plugin/plugin.json`), the runtime (Claude
  Code or Codex) and the operating system
- the smallest input that reproduces it, for example the hook payload, the
  command or the file layout
- what happened and what you expected

## What to expect

- an acknowledgement within 7 days
- an assessment, and a planned fix or the reason it will not be fixed, within
  30 days
- credit in the release notes when the fix ships, unless you ask to stay
  anonymous

Please give us time to release a fix before you disclose the issue publicly.
