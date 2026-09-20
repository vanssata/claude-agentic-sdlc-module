VERSION = 3
TITLE = "0002 is missing, so the registry is invalid"
MOVES = []


def plan(ctx):  # pylint: disable=unused-argument  # never runs: load() rejects this registry
    """Nothing: this file exists to make the registry invalid."""
