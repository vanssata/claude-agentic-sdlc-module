"""Migration (§D12, R25): the plan and report of a move from files to packages, its backup and apply, the
risks stub and the move of agent logs."""
import collections
import os
import shutil
import tarfile
from datetime import datetime, timezone

import memory_compact as mc
import memory_config as mcfg
import memory_format as mf
import memory_io as mio
import memory_packages as mpkg
import memory_risks as mrisks
import memory_verify as mver


# ------------------------------------------------------------------ migration (§D12, R25)
def migration_plan(root):
    """What --report shows and --apply does, from HEAD's tracked files only."""
    head = mver.rev(root, "HEAD")
    if not head:
        raise mio.MemoryError_("migration reads HEAD: commit first", 2)
    tree = mver.GitTreeReader(root, head)
    packages = mpkg.load_packages(root)
    sealed = {mf.key_of(e) for _, entries, _ in packages.values() for e in entries if e.get("kind") == "task"}
    tasks = sorted({p.split("/")[2] for p in tree.paths() if p.startswith(".ai/reports/T-")})
    plan = []
    for task in tasks:
        found = mc.compact_instances(tree, task, "tracked")
        journal = tree.read(".ai/reports/%s/events.jsonl" % task)
        names = {e.get("task") for _, e in mc.parse_journal(journal) if e} if journal else set()
        logs = [(p, len(tree.read(p) or b"")) for p in tree.paths()
                if p.startswith(".ai/reports/%s/" % task) and p.endswith(".log")]
        plan.append({"task": task, "compactions": found, "journal": journal is not None,
                     "names": sorted(n for n in names if n), "logs": logs,
                     "sealed": [mf.key_of(c.seal) for c in found if c.seal and mf.key_of(c.seal) in sealed]})
    return head, plan


def migrate_report(root):
    head, plan = migration_plan(root)
    kinds, dropped = collections.Counter(), collections.Counter()
    lines = ["# Migration report — %s" % mio.now(), "", "HEAD %s; tracked files only, so every clone gives the same "
             "rids." % head[:12], "", "## Tasks", "",
             "| task | instances | journal | name in journal | coverage | result | sealed already |",
             "|---|---|---|---|---|---|---|"]
    total_logs = []
    for item in plan:
        found = item["compactions"]
        for c in found:
            if c.seal:
                for e in c.entries:
                    kinds[e["kind"]] += 1
                dropped.update(c.seal["counts"]["dropped"])
        cov = ", ".join("%s/%s" % (c.coverage["accounted"], c.coverage["lines"]) for c in found) or "-"
        names = ", ".join(item["names"]) or "-"
        mismatch = " ≠ dir" if item["names"] and item["names"] != [item["task"]] else ""
        lines.append("| %s | %d | %s | %s%s | %s | %s | %s |" % (
            item["task"], len(found), "yes" if item["journal"] else "no (state-only)", names, mismatch, cov,
            ", ".join(c.seal["result"] for c in found if c.seal) or "no sources",
            ", ".join(item["sealed"]) or "-"))
        total_logs += item["logs"]
    lines += ["", "## Kept per kind", ""] + ["- %s: %d" % (k, n) for k, n in sorted(kinds.items())]
    lines += ["", "## Dropped per event (KEEP_RULES v1)", ""] + ["- %s: %d" % (k, n) for k, n in sorted(dropped.items())]
    lines += ["", "## Committed logs (%d, %s bytes)" % (len(total_logs), mf.fmt_n(sum(s for _, s in total_logs))), ""]
    lines += ["- %s (%s bytes)" % (p, mf.fmt_n(s)) for p, s in total_logs]
    text = (mio.read_bytes(os.path.join(root, ".ai", "project", "known-risks.md")) or b"").decode("utf-8")
    risks, leftovers = mc.parse_known_risks(text)
    titles = collections.Counter(r["title"] for r in risks)
    lines += ["", "## known-risks.md", "", "- sections parsed: %d" % len(risks),
              "- lines outside a section: %d" % len(leftovers["lines"]),
              "- label derived (no Label line): %d" % sum(1 for r in risks if r["label_derived"]),
              "- renders byte for byte: %s" % ("yes" if mc.render_known_risks(risks, leftovers) == text else "NO"),
              "- duplicate titles: %s" % (", ".join(t for t, n in titles.items() if n > 1) or "none")]
    report = "\n".join(lines) + "\n"
    mio.atomic_write(mio.local_path(root, "migration-report.md"), report)
    return report


def backup(root):
    path = mio.local_path(root, "backup-%s.tar" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tarfile.open(path, "w") as tar:
        for rel in (".ai/reports", ".ai/project/known-risks.md"):
            if os.path.exists(os.path.join(root, rel)):
                tar.add(os.path.join(root, rel), arcname=rel)
    return path


def migrate_apply(root, risks=False):
    """Closed legacy tasks into batches by their closed_at period; then, with
    risks, known-risks.md into risk entries and a stub."""
    cfg = mcfg.load_config(root)
    saved = backup(root)
    out = ["backup: %s" % os.path.relpath(saved, root)]
    if risks:
        return out + migrate_risks(root, cfg)
    _, plan = migration_plan(root)
    groups = collections.defaultdict(list)
    skipped, incomplete = [], []
    for item in plan:
        for c in item["compactions"]:
            if not c.seal or c.seal["result"] not in ("closed", "abandoned", "restarted"):
                continue
            key = mf.key_of(c.seal)
            if key in item["sealed"]:
                skipped.append(key)
                continue
            if c.coverage["accounted"] != c.coverage["lines"] or c.coverage["skipped"] or c.problems:
                incomplete.append((key, c.coverage, c.problems))
                continue
            when = c.seal.get("closed_at") or c.seal.get("started_at") or c.seal["ts"]
            groups[mf.period_of(when, cfg.period)].append(c)
    written = 0
    with mio.locked(root):
        for period in sorted(groups):
            # Whole tasks per batch, a new batch before package_max_bytes (V8).
            batches, size = [[]], 0
            for c in groups[period]:
                task_bytes = sum(len(mf.canonical(e)) + 1 for e in c.entries + [c.seal])
                if batches[-1] and size + task_bytes > cfg.package_max_bytes:
                    batches.append([])
                    size = 0
                batches[-1].append(c)
                size += task_bytes
            for batch in batches:
                name = mpkg.new_batch_name(root, period, cfg.author)
                parts = mf.parse_package_name(name)
                entries = [e for c in batch for e in c.entries + [c.seal]]
                mio.atomic_write(os.path.join(mio.memory_dir(root), name),
                             mf.render_package(mf.package_header(period, cfg.author, parts["batch"], mio.now()),
                                               entries))
                written += len(batch)
                out.append("package: %s (%d tasks, %d entries)" % (os.path.join(mio.MEMORY_REL, name), len(batch),
                                                                   len(entries)))
    findings = mver.check_packages(mpkg.load_packages(root), cfg.package_max_bytes)
    out.append("migrated %d task instance(s); %d already sealed; %d incomplete (reported, not exported)"
               % (written, len(skipped), len(incomplete)))
    out += ["incomplete: %s coverage %s/%s %s" % (k, cov["accounted"], cov["lines"], "; ".join(p))
            for k, cov, p in incomplete]
    out += [mver.format_finding(f) for f in findings]
    return out


STUB = """# Known risks

<!-- The risks live in the record since {date}: `state.py memory risks --md` renders
     them, `state.py memory risk add|close` records them (spec compact-project-memory
     §D9, OQ4). A section written here is still read, as before the migration. -->
"""


def migrate_risks(root, cfg):
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = (mio.read_bytes(path) or b"").decode("utf-8")
    import memory_store  # pylint: disable=import-outside-toplevel
    entries = memory_store.risk_entries_from_md(text)
    risks, leftovers = mc.parse_known_risks(text)
    rendered = mc.render_known_risks([{"text": e["text"]} for e in entries], leftovers)
    if rendered != text:
        raise mio.MemoryError_("known-risks.md does not render byte for byte from its entries — nothing changed", 3)
    entries = [dict(e, actor="migration", src=["known-risks.md#%s" % e["rkey"]]) for e in entries]
    entries = [mf.with_rid(e) for e in entries]
    name = mrisks.append_entries(root, cfg, entries)
    mio.atomic_write(path, STUB.format(date=mio.now()[:10]))
    del risks
    return ["risks: %d entries into %s; known-risks.md is a stub" % (len(entries), os.path.join(mio.MEMORY_REL, name))]


def move_logs(root):
    head = mver.rev(root, "HEAD")
    tree = mver.GitTreeReader(root, head) if head else None
    logs = [p for p in (tree.paths() if tree else []) if p.startswith(".ai/reports/") and p.endswith(".log")]
    moved = []
    for rel in logs:
        task = rel.split("/")[2]
        src = os.path.join(root, rel)
        if not os.path.exists(src):
            continue
        dest = os.path.join(root, ".ai", "state", "logs", task, "legacy", os.path.basename(rel))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        moved.append(rel)
    listing = mio.local_path(root, "logs-to-rm.txt")
    mio.atomic_write(listing, "".join("%s\n" % p for p in moved))
    return moved, "git rm --cached --quiet --pathspec-from-file=%s" % os.path.relpath(listing, root)
