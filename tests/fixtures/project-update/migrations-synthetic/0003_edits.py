"""A policy edit, a text edit, a state patch and a proposed deletion."""
VERSION = 3
TITLE = "edit a policy, patch the task state, propose a deletion"
MOVES = []


def plan(ctx):
    ctx.edit_json(".ai/policies/risk-tiers.json", lambda o: {**o, "schema_probe": "0003"})
    # plan() runs again on every run until the schema advances, so an edit must
    # be idempotent: appending unconditionally would duplicate the line.
    ctx.edit_text(".ai/policies/testing.md", add_marker)
    ctx.edit_text(".ai/policies/testing.md", lambda b: b)  # a no-op returns its input
    ctx.patch_state(rename_step)
    ctx.delete(".ai/legacy-notes.md", "no template has shipped this since schema 0")


def rename_step(state):
    """The rename in 0002 takes a path the task in flight may touch with it."""
    for step in state.get("approved_plan", {}).get("steps", []):
        step["allowed_files"] = [".ai/workflows/fix.md" if f == ".ai/workflows/bugfix.md" else f
                                 for f in step.get("allowed_files", [])]
    return state


MARKER = b"# added by migration 0003\n"


def add_marker(text):
    return text if MARKER in text else text + b"\n" + MARKER
