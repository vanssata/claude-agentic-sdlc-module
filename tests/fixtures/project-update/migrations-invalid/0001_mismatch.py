"""VERSION does not equal the NNNN prefix: the registry is refused."""
VERSION = 2
TITLE = "the file name says 0001 and VERSION says 2"
MOVES = []


def plan(ctx):  # pylint: disable=unused-argument  # never runs: load() rejects this registry
    """Nothing: this file exists to make the registry invalid."""
