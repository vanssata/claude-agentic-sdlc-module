"""Modules of the sibling skills, loaded by path once per run, and the weight files they serve.

shell: _MODULES, sibling, weight_module, weight_overlay, shipped_weight
"""

import importlib.util
import os

from rr_update import paths


_MODULES = {}


def sibling(name, *parts):
    """A module of another skill, loaded by path once per run (skills are installed independently)."""
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location("riskrails_" + name, os.path.join(paths.SKILLS, *parts))
        _MODULES[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MODULES[name])
    return _MODULES[name]


def weight_module():
    """skills/ai-task/weight.py, the renderer behind `state.py weight --mirror`."""
    return sibling("weight", "ai-task", "weight.py")


def weight_overlay():
    """skills/ai-task/weight_overlay.py: the plugin's table with the project's laid over it."""
    return sibling("weight_overlay", "ai-task", "weight_overlay.py")


def shipped_weight():
    return os.path.join(paths.TEMPLATES["ai-init"], paths.WEIGHT_JSON)


