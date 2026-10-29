"""0008: the plugin is RiskRails.

A refactoring (R35); every decision the guards take stays the same.

  * The state file does not move here. R34 is expand/contract: this version's
    guards and state.py read `.ai/state/state.json` first and `current.json`
    otherwise, and write the file where it is; a later migration moves it, once
    a version that reads both names has shipped, so reverting the move still
    leaves every task guarded.
  * The markers of the managed block (`<!-- claude-agentic:start -->` / `:end`)
    and of each rule block (`claude-agentic:rule:<slug>:start` / `:end`) in the
    project's root instruction files take the name `riskrails`. Only the word
    inside a marker changes: the text around the block, and the spacing inside
    the marker, are left byte for byte as they are. Rule blocks in other
    directories are renamed by the renderer the next time it splices them.
  * `.ai/AGENTS.md` routes to `<home>/riskrails/ai` and `<home>/riskrails/ai-path`
    instead of `<home>/claude-agentic/...`; the installer leaves a symlink at the
    old home for one version.
"""
import re

VERSION = 8
TITLE = "rename the plugin's markers and routes to RiskRails"
MOVES = []

ROUTER = ".ai/AGENTS.md"
MARKER = re.compile(
    rb"(<!--\s*)claude-agentic(:(?:start|end|rule:[a-z0-9][a-z0-9-]*:(?:start|end))\s*-->)")
ROUTE = re.compile(rb"(?<=/)claude-agentic(?=/ai(?:-path)?\b)")


def rename_markers(data):
    return MARKER.sub(rb"\1riskrails\2", data)


def rename_routes(data):
    return ROUTE.sub(b"riskrails", data)


def plan(ctx):
    for path in ctx.instruction_files():
        ctx.edit_text(path, rename_markers, "claude-agentic markers renamed to riskrails")
    ctx.edit_text(ROUTER, rename_routes, "routes to the riskrails home")
