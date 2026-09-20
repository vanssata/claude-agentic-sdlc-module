"""A migration that moves a file the project has edited, and one it never had."""
VERSION = 2
TITLE = "rename the bugfix workflow"
MOVES = [(".ai/workflows/bugfix.md", ".ai/workflows/fix.md"),
         (".ai/workflows/never-existed.md", ".ai/workflows/still-not-there.md")]


def plan(ctx):
    for src, dst in MOVES:
        ctx.move(src, dst)
