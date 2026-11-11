"""The report of a run: one line per item, the hints and the summary.

shell: report
"""


def report(plan, applied):
    auto = [i for i in plan.items if i["action"] not in ("delete?", "regenerate?")]
    gated = [i for i in plan.items if i["action"] in ("delete?", "regenerate?")]
    head = "applied" if applied else "dry run, nothing written; --apply to write"
    print("project-update: %s (%s)" % (plan.root, head))
    if not plan.items:
        print("  up to date with the installed plugin")
    # a cleanup is one line per directory, however many files it holds
    rows, groups = [], {}
    for i in plan.items:
        if (i["reason"] or "").startswith("[cleanup]"):
            parts = i["target"].split("/")
            where = "/".join(parts[:4] if i["target"].startswith(".ai/state/logs/") else parts[:3])
            key = (where, i["action"], i["note"])
            if key in groups:
                groups[key]["count"] += 1
                continue
            row = dict(i, count=1)
            groups[key] = row
            row["target"] = where
            i = row
        rows.append(i)
    for (where, _action, _note), row in groups.items():
        row["target"] = "%s/ (%d file%s)" % (where, row["count"], "" if row["count"] == 1 else "s")
    width = max([len(i["target"]) for i in rows] + [10])
    for i in rows:
        note = i["note"]
        if i["action"] in ("delete?", "regenerate?"):
            if (i["reason"] or "").startswith("[cleanup]"):
                note += "; needs --apply --confirm-cleanup NAME"
                if i["target"].startswith(".ai/state/"):
                    note += " (git-ignored: not recoverable through git)"
            else:
                note += "; needs --apply --confirm-delete NAME"
        print("  %-9s %-*s  %s" % (i["action"], width, i["target"], note))
    for h in plan.hints:
        print("  hint      " + h)
    tail = ""
    # the summary names the flag each row names: [cleanup] rows settle with --confirm-cleanup only
    cleanups = [i for i in gated if (i["reason"] or "").startswith("[cleanup]")]
    if len(gated) > len(cleanups):
        tail += ", %d change(s) awaiting --confirm-delete" % (len(gated) - len(cleanups))
    if cleanups:
        tail += ", %d cleanup file(s) awaiting --confirm-cleanup" % len(cleanups)
    print("%d automatic%s" % (len(auto), tail))
