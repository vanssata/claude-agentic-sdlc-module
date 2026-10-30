"""0011: the old tier policy is retired (register #20, #50, #58, #62).

`.ai/policies/risk-tiers.json` and its generated mirror `risk-tiers.md` were
replaced by `.ai/policies/weight.json` (migration 0007 converted the project's
edits) and nothing in the plugin reads them any more. The plugin stops shipping
both, and this migration proposes deleting the project's copies.

  * Each file the project has is proposed for deletion: a `delete?` item that
    waits for --apply --confirm-delete NAME, with the original kept under
    `.ai/reports/project-update-<date>/original/`. Git is the rollback.
  * A copy the project edited is proposed too, and the reason says it was
    edited: the human decides, and may keep the file by never confirming (the
    schema then stays at 10) or by copying what they need into weight.json first.
  * A project without the files gets nothing, and so does a second run.
  * The templates are retired in `migrations.RETIRED`, so the template walk never
    re-creates a deleted file.
"""

VERSION = 11
TITLE = "retire risk-tiers.json and risk-tiers.md (weight.json replaced them)"
MOVES = []

PATHS = (".ai/policies/risk-tiers.json", ".ai/policies/risk-tiers.md")
REASON = "replaced by .ai/policies/weight.json; nothing reads it any more"
EDITED = REASON + " — your project edited this copy, check weight.json holds what you need"


def plan(ctx):
    for path in PATHS:
        if not ctx.exists(path):
            continue
        why = ctx.unsafe_target(path)
        if why:
            ctx.hint("%s: %s, so this update never deletes it — remove it by hand once weight.json holds "
                     "what you need" % (path, why))
            continue
        ctx.delete(path, REASON if ctx.is_shipped(path, ctx.read(path)) else EDITED)
