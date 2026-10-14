"""A migration that moves a file the project has edited, and one it never had."""
VERSION = 2
TITLE = "rename the coding policy"
MOVES = [(".ai/policies/coding.md", ".ai/policies/code-style.md"),
         (".ai/workflows/never-existed.md", ".ai/workflows/still-not-there.md")]


def plan(ctx):
    for src, dst in MOVES:
        ctx.move(src, dst)
