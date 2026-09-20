"""0003: take the pipeline text out of the root instruction files.

Every root instruction file used to carry a `## SDLC workflow` section that
repeated, in prose, what the managed block now routes to. Two copies of the same
rule is one copy too many: the section is loaded into every session, it drifts
away from the block the moment either one is edited, and it is the part of the
file a human never wrote.

The section is removed only when the bytes in the project's file are bytes this
plugin shipped — matched against a version in the template history, never
against a pattern over the human's own prose. Anything else is a hint:

  * a section that was edited is the human's text now, and only they can merge it;
  * a managed block that was edited is never written over, here or anywhere else.

The file is the project's, not the plugin's, so `apply` keeps the original under
`.ai/reports/project-update-<date>/original/` before the rewrite.

Nothing here is a conflict and nothing is a deletion, so this migration never
holds `.ai/VERSION`: a project whose sections were all edited still reaches the
current schema, carrying two hints.
"""

VERSION = 3
TITLE = "move the pipeline text out of the instruction files (context diet)"
MOVES = []

HEADING = b"\n## SDLC workflow"
NEXT_SECTION = b"\n## "
NOTE = "SDLC workflow section removed (now in the managed block)"


def _section(blob):
    """The `## SDLC workflow` section of one shipped template, or None: from the
    newline before its heading to the newline before the next heading, so cutting
    it out of a file leaves the surrounding blank lines as they were."""
    start = blob.find(HEADING)
    if start < 0:
        return None
    end = blob.find(NEXT_SECTION, start + 1)
    return blob[start:] if end < 0 else blob[start:end]


def _shipped_section(text, shipped):
    """The one shipped section this file carries verbatim, or None."""
    for blob in shipped:
        section = _section(blob)
        if section and section in text:
            return section
    return None


def plan(ctx):
    for path in ctx.instruction_files():
        text = ctx.read(path)
        section = _shipped_section(text, ctx.shipped(path))
        if section:
            ctx.edit_text(path, lambda t, s=section: t.replace(s, b"", 1), NOTE)
        elif HEADING in text:
            ctx.hint("%s: the SDLC workflow section was edited, so it is yours to keep — "
                     "the managed block below it now says the same thing" % path)
        if ctx.block_status(path) == "edited":
            ctx.hint("%s: the managed block was edited here, so the plugin's stub cannot "
                     "replace it — move your lines below the block and run /project-update "
                     "again" % path)
