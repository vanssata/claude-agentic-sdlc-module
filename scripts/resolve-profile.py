#!/usr/bin/env python3
"""Resolve a plan profile from ``profiles/`` into one object.

Every file in ``profiles/`` carries the plugin's own tables under one namespaced
key, ``claude_agentic`` — the model tiers, the per-plan budgets and the preferred
runtime. The rest of a Claude profile is a ``settings.json`` fragment, and the
rest of a Codex profile is read field by field by the Codex renderers; neither
ever sees ``claude_agentic``. This script is the single place that reads it, so
the installer, the gate and ``state.py profile`` all agree on what a plan means.

Resolution:

* ``claude_agentic.inherits`` names another profile (``max20`` inherits ``max``).
  The parent is resolved first and the child deep-merged over it: objects merge
  key by key, arrays and scalars are replaced. A file that holds only
  ``claude_agentic`` takes the parent's settings unchanged.
* A Codex profile keeps its top-level ``tiers``; ``claude_agentic.tiers`` is
  filled from them, with each tier's ``agents`` taken from ``roles`` (the roles
  that have their own ``source`` — variants are renderings, not agents).
* ``--plan`` and ``--label`` override ``plan``/``label`` (``team-pro`` resolves
  ``pro.json``, ``team-max`` resolves ``max.json``).
* ``--fable yes|no`` records ``fable`` and drops ``architect_model_with_fable``
  when Fable is off, so a reader never has to know the flag.

  resolve-profile.py <name|path> [--src DIR] [--plan P] [--label L]
                     [--fable yes|no] [--print full|settings|agentic]

``settings`` prints the profile without ``claude_agentic``; ``agentic`` prints
the resolved ``claude_agentic`` object; ``full`` (the default) prints both.
"""
import argparse
import copy
import json
import os
import sys

KEY = "claude_agentic"


def deep_merge(base, over):
    """Objects merge key by key; anything else in ``over`` replaces ``base``."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return copy.deepcopy(over)
    out = copy.deepcopy(base)
    for key, value in over.items():
        out[key] = deep_merge(out[key], value) if key in out else copy.deepcopy(value)
    return out


def profile_path(src, name):
    if name.endswith(".json") or os.sep in name:
        return name
    return os.path.join(src, "profiles", name + ".json")


def load(src, name, seen=()):
    path = profile_path(src, name)
    stem = os.path.basename(path)[: -len(".json")]
    if stem in seen:
        raise ValueError("inheritance cycle: " + " -> ".join(seen + (stem,)))
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    parent = (data.get(KEY) or {}).get("inherits")
    if not parent:
        return data
    return deep_merge(load(src, parent, seen + (stem,)), data)


def codex_tiers(data):
    tiers = copy.deepcopy(data.get("tiers") or {})
    for tier in tiers.values():
        tier.setdefault("agents", [])
    for role, spec in (data.get("roles") or {}).items():
        if spec.get("source") and spec.get("tier") in tiers:
            tiers[spec["tier"]]["agents"].append(role)
    return tiers


def resolve(src, name, plan=None, label=None, fable=None):
    data = load(src, name)
    agentic = data.get(KEY)
    if not isinstance(agentic, dict):
        raise ValueError(f"{profile_path(src, name)}: no {KEY} object")
    if "tiers" not in agentic and agentic.get("runtime") == "codex":
        agentic["tiers"] = codex_tiers(data)
    if plan:
        agentic["plan"] = plan
    if label:
        agentic["label"] = label
    if fable is not None:
        agentic["fable"] = fable
        if not fable:
            agentic.get("tiers", {}).get("EXPERT", {}).pop("architect_model_with_fable", None)
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("profile", help="profile name under profiles/ (max, max20, codex-pro …) or a path")
    ap.add_argument("--src", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="plugin root (default: this script's repository)")
    ap.add_argument("--plan")
    ap.add_argument("--label")
    ap.add_argument("--fable", choices=("yes", "no"))
    ap.add_argument("--print", dest="what", choices=("full", "settings", "agentic"), default="full")
    args = ap.parse_args(argv)

    fable = None if args.fable is None else args.fable == "yes"
    try:
        data = resolve(args.src, args.profile, args.plan, args.label, fable)
    except (OSError, ValueError) as exc:
        print(f"resolve-profile: {exc}", file=sys.stderr)
        return 2

    if args.what == "settings":
        data = {k: v for k, v in data.items() if k != KEY}
    elif args.what == "agentic":
        data = data[KEY]
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
