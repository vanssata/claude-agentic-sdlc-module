"""0005: the state keys a task needs to move between runtimes on purpose.

Schema 4 already recorded which runtime owns a task and where it resumes, but
a move was only ever noticed after the fact, by the next command that ran
somewhere else. `state.py handoff --to` now hands a task over deliberately and
waits for the receiving side to pick it up; a T4+ review can be asked of the
other side. Both need a place in the state file.

One operation, adding keys only where they are absent, so a re-run records
nothing and a task at any stage keeps working. `state.py` fills the same
defaults in memory, so a task in flight works whether or not this has run; the
migration exists so the project reports itself behind until it has, and so
`schema_migrated` lands in the journal. Nothing is backfilled: a task that was
never handed over has nothing pending, and no review was ever asked of anyone.
"""

VERSION = 5
TITLE = "add the pending-handoff and cross-vendor-review keys a task in flight needs"
MOVES = []


def _add_defaults(state):
    """The schema-5 keys, added only where they are absent."""
    handoff = state.get("handoff")
    if not isinstance(handoff, dict):
        handoff = state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None,
                                      "reason": None}
    handoff.setdefault("pending_to", None)
    handoff.setdefault("pending_since", None)
    state.setdefault("cross_vendor_review", None)
    return state


def plan(ctx):
    ctx.patch_state(_add_defaults)
