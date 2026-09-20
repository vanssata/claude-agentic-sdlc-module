"""An edit that returns str instead of bytes: refused in the dry run."""
VERSION = 1
TITLE = "return the wrong type"
MOVES = []


def plan(ctx):
    ctx.edit_text(".ai/policies/testing.md", lambda b: b.decode())
