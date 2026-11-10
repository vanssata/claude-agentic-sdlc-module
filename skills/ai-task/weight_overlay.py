"""The weight table a project sees: the plugin's shipped table with the project's
weight.project.json laid over it (R9). weight.py's `load_policy` calls `load`.

Objects merge recursively, any other value (a list too) replaces. A file that is not
a JSON object, or a result without the axes and modes tables, raises ValueError
naming the file; nothing falls back to a default.
"""
import json
import os


def _table(path):
    """One JSON object from `path`; ValueError naming the file when it is not one."""
    try:
        with open(path, encoding="utf-8") as fh:
            table = json.load(fh)
        if isinstance(table, dict):
            return table
        raise ValueError("not a JSON object")
    except ValueError as exc:
        raise ValueError("%s: %s" % (path, exc)) from exc


def _overlay(base, top):
    """`top` laid over `base`: dicts merge, any other value (a list too) replaces."""
    for key, value in top.items():
        base[key] = _overlay(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return base


def load(shipped, own):
    """The table at `shipped`, with `own` laid over it when that file exists."""
    policy = _table(shipped)
    if os.path.isfile(own):
        _overlay(policy, _table(own))
    if not all(isinstance(policy.get(k), dict) for k in ("axes", "modes")):
        raise ValueError("%s has no axes or modes table" % own)
    return policy
