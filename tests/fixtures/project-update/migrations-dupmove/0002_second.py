"""The destination 0001 already moves a file to: the registry refuses the pair."""
VERSION = 2
TITLE = "move another file to the same destination"
MOVES = [(".ai/policies/release.md", ".ai/policies/vcs.md")]


def plan(ctx):
    ctx.move(*MOVES[0])
