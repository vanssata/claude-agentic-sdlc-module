"""A MOVES pair the registry refuses: the destination is outside the project."""
VERSION = 1
TITLE = "declare a move out of the project"
MOVES = [(".ai/policies/git.md", "../stolen.md")]


def plan(ctx):
    ctx.move(*MOVES[0])
