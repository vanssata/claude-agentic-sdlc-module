"""0010: the command-choice dialog is on (R36.1).

`.ai/policies/dialog.json` is the project's switch for the dialog: the human
picks a commit, push or approval command in the runtime's dialog and the agent
runs that command, verbatim and once. This migration writes the switch, on, as
the scaffold does for a new project.

  * A project that already has the file keeps it, whatever it says: `create`
    does not overwrite, and a human's `"enabled": false` stays off.
  * A second run finds the file and does nothing, and prints nothing.
  * The task's state is not touched: a task in flight survives.
"""

VERSION = 10
TITLE = "the command-choice dialog switch"
SWITCH = ".ai/policies/dialog.json"
MOVES = []


def plan(ctx):
    if ctx.exists(SWITCH):
        return
    ctx.create(SWITCH, ctx.template(SWITCH))
    ctx.hint("%s is new and the command-choice dialog is on; set \"enabled\": false in it to turn the dialog off"
             % SWITCH)
    ctx.hint("docs/sdlc/constitution.md C5 still says no agent commits, merges or deploys: if you keep the dialog "
             "on, amend C5 to the new sentence (skills/project-init/templates/constitution.md, C5)")
    if ctx.state is not None:
        ctx.hint("a task is in flight: the dialog switch takes effect for it too; set \"enabled\": false in %s "
                 "to turn it off" % SWITCH)
