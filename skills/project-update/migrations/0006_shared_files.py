"""0006: the shared policies, agent contracts, workflows and templates are read
from the plugin, not from a copy in every project.

Twenty-nine files under `.ai/` were the same in every project that never edited
them, and each one was merged on every update. They now ship once, in the
plugin's shared tree, and a project reads them from there; a file at the same
path under `.ai/` still wins, as an override. The project keeps what is its own:
`project/`, `rules/`, `state/`, `reports/`, `VERSION`, and the policies
risk-tiers.json, risk-tiers.md, path-guard.json, testing.md, coding.md,
safety.md and security.md. Those two stay project-owned, so an instruction file
that names `.ai/policies/safety.md` keeps pointing at a file that exists.

The router goes first: before any copy is proposed for deletion, `.ai/AGENTS.md`
says where the shared files now live. `apply` stops at the first item that
fails, so no deletion lands while the router is unwritten.

  * no router: the shipped one is created;
  * a router that already names the shared tree: nothing;
  * a router the plugin shipped, unedited: replaced by the current one;
  * an edited router: the section is inserted before the heading that follows
    it in the shipped router, or appended when that heading was renamed. The
    human's lines are kept as they are.

Then each shared copy the project has:

  * reached through a symlink, or resolving outside the project: a hint, never
    deleted;
  * edited: a hint that it is now an override and no longer receives changes;
  * byte-identical to a version the plugin shipped (CRLF counts): proposed for
    deletion, once every installed home has the shared file it falls back to.

A deletion waits for --apply --confirm-delete NAME, and `.ai/VERSION` stays
where it was until it is settled. The original of every deleted file is kept
under `.ai/reports/project-update-<date>/original/`; git is the rollback.
"""
import re

from migrations import SchemaError

VERSION = 6
TITLE = "read the shared policies, agent contracts, workflows and templates from the plugin"
MOVES = []

ROUTER = ".ai/AGENTS.md"
HEADING = b"\n## Shared files"
NEXT_SECTION = b"\n## "
HAS_SECTION = re.compile(rb"(?m)^## Shared files[ \t]*\r?$")

# The shared set, literally: the plugin's tree must equal it (tested). A file
# that projects once held a copy of is added by a new migration, which plans
# that copy's deletion; one no project ever held needs only its name here.
SHARED = (
    ".ai/policies/production.md",
    ".ai/policies/database.md",
    ".ai/policies/git.md",
    ".ai/policies/release.md",
    ".ai/policies/context-management.md",
    ".ai/policies/tooling.md",
    ".ai/policies/model-routing.md",
    ".ai/policies/review-economy.md",
    ".ai/agents/context.md",
    ".ai/agents/discovery.md",
    ".ai/agents/implementer.md",
    ".ai/agents/manager.md",
    ".ai/agents/planner.md",
    ".ai/agents/release.md",
    ".ai/agents/reviewer.md",
    ".ai/agents/risk.md",
    ".ai/agents/security.md",
    ".ai/agents/tester.md",
    ".ai/workflows/feature.md",
    ".ai/workflows/bugfix.md",
    ".ai/workflows/hotfix.md",
    ".ai/workflows/investigation.md",
    ".ai/workflows/refactoring.md",
    ".ai/templates/task-context.md",
    ".ai/templates/impact-report.md",
    ".ai/templates/review-report.md",
    ".ai/templates/release-report.md",
    ".ai/templates/architecture-decision.md",
    ".ai/templates/implementation-plan.md",
    # Added after 0006 shipped (redesign 2.3), so declared_shared() knows them.
    # They were never copied into a project, so a schema < 6 project has
    # neither and plan() skips both.
    ".ai/using-riskrails.md",
    ".ai/workflows.md",
)
REASON = "identical to a version the plugin shipped; its shared copy applies"


def _section(blob):
    """The `## Shared files` section of the shipped router and the line that
    follows it: from the newline before its heading to the newline before the
    next heading, so inserting it leaves the blank lines as they were."""
    start = blob.find(HEADING)
    if start < 0:
        return None, None
    end = blob.find(NEXT_SECTION, start + 1)
    if end < 0:
        return blob[start:], None
    anchor_end = blob.find(b"\n", end + 1)
    return blob[start:end], blob[end:] if anchor_end < 0 else blob[end:anchor_end]


def _add_section(text, section, anchor):
    """The router with the section in it, its own lines untouched."""
    crlf = b"\r\n" in text
    if anchor:
        at = text.find(anchor + (b"\r\n" if crlf else b"\n"))
        if at < 0 and text.endswith(anchor):
            at = len(text) - len(anchor)
        if at >= 0:
            if crlf:  # inserted after the \r of the line before the anchor
                section = section.replace(b"\n", b"\r\n")[1:] + b"\r"
            return text[:at] + section + text[at:]
    eol = b"\r\n" if crlf else b"\n"
    return text.rstrip(b"\r\n") + eol + section.rstrip(b"\n").replace(b"\n", eol) + eol


def _router(ctx):
    shipped = ctx.template(ROUTER)
    text = ctx.read(ROUTER)
    if text is None:
        ctx.create(ROUTER, shipped)
    elif HAS_SECTION.search(text):
        return
    elif ctx.is_shipped(ROUTER, text):
        ctx.edit_text(ROUTER, lambda _t: shipped, "unchanged since it was installed; now names the shared files")
    else:
        section, anchor = _section(shipped)
        if section is None:
            raise SchemaError("%04d: the shipped router has no Shared files section" % VERSION)
        ctx.edit_text(ROUTER, lambda t: _add_section(t, section, anchor),
                      "Shared files section added; your router edits kept")


def plan(ctx):
    _router(ctx)
    candidates = []
    for path in SHARED:
        if not ctx.exists(path):
            continue
        why = ctx.unsafe_target(path)
        if why:
            ctx.hint("%s: %s, so this update never deletes it — check by hand whether it is "
                     "still needed" % (path, why))
        elif not ctx.is_shipped(path, ctx.read(path)):
            ctx.hint(ctx.override_note(path))
        else:
            candidates.append(path)
    if candidates:
        ctx.require_shared(candidates)
    for path in candidates:
        ctx.delete(path, REASON)
