"""A move the module did not declare in MOVES: ctx.move refuses it."""
VERSION = 1
TITLE = "move a file without declaring it"
MOVES = []


def plan(ctx):
    ctx.move(".ai/policies/git.md", ".ai/policies/vcs.md")
