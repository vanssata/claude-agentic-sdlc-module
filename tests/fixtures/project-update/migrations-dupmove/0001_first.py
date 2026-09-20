"""Two migrations that move different files onto one destination: refused."""
VERSION = 1
TITLE = "move a file to the shared destination"
MOVES = [(".ai/policies/git.md", ".ai/policies/vcs.md")]


def plan(ctx):
    ctx.move(*MOVES[0])
