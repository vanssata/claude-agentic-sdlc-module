"""0001: record the schema version.

A project scaffolded before schema versions existed has .ai/ without .ai/VERSION,
which is schema 0. This migration has no operations: the .ai/VERSION write that
closes every migration run is its whole effect.
"""
VERSION = 1
TITLE = "record the schema version in .ai/VERSION"
MOVES = []


def plan(ctx):  # pylint: disable=unused-argument  # no operations; update.py writes .ai/VERSION
    """Nothing to do."""
