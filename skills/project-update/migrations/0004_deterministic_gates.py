"""0004: the state keys the deterministic gates measure into.

Schema 3 recorded what a task decided; it recorded nothing about what the task
actually changed. `state.py step-done` now measures the step's diff between two
tree objects, re-scores the tier from it, and the review gate reads a sensor
report — all of which need somewhere to live in the state file.

One operation, and it adds keys only where they are absent, so a re-run records
nothing and a task at any stage keeps working. Nothing is backfilled and
nothing is invented: a task that started before this schema has no base tree,
and there is no honest way to reconstruct one after the fact. Its measurements
read `unavailable`, which keeps every review its tier asks for — the safe
reading, and the true one.

The policy side of this change (the diff budget, the path scopes, the sensor
set in `risk-tiers.json`) arrives through the normal template walk, which
merges a JSON policy per key and re-hashes a mirror that was in step. A
migration that rewrote the same file would ask the human to confirm the same
change twice.
"""

VERSION = 4
TITLE = "add the diff, sensor and test-run keys a task in flight needs"
MOVES = []


def _add_defaults(state):
    """The schema-4 keys, added only where they are absent."""
    task_id = state.get("task_id") or ""
    diff = state.setdefault("diff", {})
    diff.setdefault("base_commit", None)
    diff.setdefault("base_tree", None)
    diff.setdefault("task", {"files": 0, "added": 0, "deleted": 0, "lines": 0,
                             "excluded_lines": 0, "unbudgeted_lines": 0, "tree": None,
                             "measured_at": None, "status": "not_measured"})
    diff.setdefault("rescored_tier", None)
    diff.setdefault("rescore_reasons", [])
    diff.setdefault("over_budget", False)
    state.setdefault("sensors", {"file": ".ai/reports/%s/sensors.json" % task_id,
                                 "tree": None, "verdict": None, "checked_at": None})
    state.setdefault("tests", {"runs": [], "suite_runs": 0})
    state.setdefault("risk_tier_lowered", {"by": None, "at": None, "from": None})
    for step in ((state.get("approved_plan") or {}).get("steps") or []):
        if not isinstance(step, dict):
            continue
        # A step's kind is what the must-bite check reads: a remediation step
        # proves nothing on its own, and the R-prefix is how they were named
        # before there was a field to say so.
        step.setdefault("kind", "remediation"
                        if str(step.get("step_id", "")).startswith("R") else "implementation")
        step.setdefault("tree_before", None)
        step.setdefault("diff", None)
    return state


def plan(ctx):
    ctx.patch_state(_add_defaults)
