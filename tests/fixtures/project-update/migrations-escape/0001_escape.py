"""An operation outside the project, and content that is not bytes: both refused."""
VERSION = 1
TITLE = "write outside the project"
MOVES = []


def plan(ctx):
    ctx.create("../outside-the-project.md", b"this must never be written\n")
