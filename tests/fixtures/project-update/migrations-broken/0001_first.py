VERSION = 1
TITLE = "the registry these two files form has a gap at 0002"
MOVES = []


def plan(ctx):  # pylint: disable=unused-argument  # never runs: load() rejects this registry
    """Nothing: this file exists to make the registry invalid."""
