"""A migration that adds a file, twice, to prove the second call is a no-op."""
VERSION = 1
TITLE = "add a note to the knowledge base"
MOVES = []


def plan(ctx):
    ctx.create(".ai/project/schema-note.md", b"added by migration 0001\n")
    ctx.create(".ai/project/schema-note.md", b"a second call must change nothing\n")
