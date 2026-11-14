# External integrations

## Claude Code hook protocol

- **Direction**: the runtime calls us (stdin JSON → stdout JSON)
- **Code**: `hooks/hooks.json` (plugin), `settings.common.json` + `settings.gate.json` (npx install)
- **Failure behaviour**: KNOWN FACT: fail-open. `ai-guard.py` exits 0 with no output on bad JSON, a missing file or any non-Deny exception (`hooks/ai-guard.py:21-23,85-93`), and `dialog-gate.py` likewise (`:99-100`). A deny is JSON plus exit 0, never exit 2. Timeouts: ai-guard 15 s, cap-large-read 5 s. The git subprocess has no timeout of its own (`hooks/guard/git.py:103-107`).
- **Known issues**: RISK: a half-installed or syntax-broken `hooks/guard/*.py` silently disables the git, path and scope checks, with no signal to the user.

## Codex hook protocol

- **Code**: `codex/hooks.json` (npx), `hooks/codex-hooks.json` (plugin, `.codex-plugin/plugin.json:20`). The two differ on purpose (paths); `tests/test_install_routes.py:335` pins equality of the effective inventories.
- **Differences**: no Read cap, no Setup scaffold, no `auth_success`, no StopFailure gate; the dialog tool is `request_user_input`. Codex hooks must be trusted by the human via `/hooks`, otherwise they are listed and skipped (`codex/hooks.json:2`).
- **Config merge**: `scripts/merge-codex-config.py` writes `config.toml.bak` then replaces atomically (`:347-354`). RISK: a fixed `.bak` name, so a second run overwrites the first backup.
- **Known issues**: UNKNOWN: whether `memory-pre-push.py` reaches `~/.codex/hooks` (`bin/riskrails.js:1429` lists five fixed files without it; `memory_hook.py:46` looks there).

## Installer → the user's ~/.claude and ~/.codex

- **Code**: `bin/riskrails.js` (claude render/dry-run/apply `:478,811,1159`; codex `:1371,1431,1460`)
- **Idempotency**: `--dry-run` writes nothing. Backups go to `<home>/backups/<date>/` (`:843-866`). The statusline that was replaced is kept in `<home>/riskrails/statusline.json`. Retired shims move to the backups.
- **Known issues**: UNKNOWN: same-day backup collisions, and whether the plain `fs.writeFileSync` at `:361,417` can leave a half-written settings file if killed.

## git

- **Code**: `hooks/guard/git.py` (guard), `hooks/memory-pre-push.py` (pre-push; honours `core.hooksPath`, `memory_hook.py:14-33`)
- **Failure behaviour**: git absent → `OSError` caught → the check allows (INFERENCE from `git.py:107`). pre-push: an import failure exits 3 and names `--no-verify` as the bypass (fails closed). RISK: a half-updated plugin blocks pushes.

## npm and GitHub

- **Code**: `.github/workflows/npm-publish.yml` (push to main / tag `v*.*.*`; detect → verify → publish), `generator-generic-ossf-slsa3-publish.yml` (release / dispatch)
- **Credentials**: `secrets.NPM_TOKEN` as `NODE_AUTH_TOKEN` (`:170`); OIDC `id-token: write` (trusted publishing preferred, `:20-22`); `github.token` as `GH_TOKEN` in detect. Environment `npm` on publish (`:152`). Values never in the repo.
- **Idempotency**: an existing release for the tag skips republishing (`:69,129`).
- **Known issues**: the agent cannot push `release/*` (use `chore/release-X.Y.Z`); a publish from a dev machine is denied by the git guard.

## Transcripts (usage report, rr-status --cost)

- **Code**: `skills/usage-report/usage-report.py:43` (`$CLAUDE_CONFIG_DIR/projects`), Codex sessions via `CODEX_HOME`
- **Failure behaviour**: bad lines are skipped (`errors="replace"`, broad exception tolerance). UNKNOWN: whether a renamed usage field gives zero silently.

## Update notice (network)

- **Code**: `hooks/update_notice.py`, imported by `context-guard.py:743-755`. Registry URL can be overridden by `RISKRAILS_REGISTRY_URL` (`:128`). Disabled by `RISKRAILS_NO_UPDATE_CHECK` or `CI` (`:71`).
- **Data sent**: INFERENCE: a registry version lookup only. Not traced further.
