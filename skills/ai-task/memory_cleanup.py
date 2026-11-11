"""Cleanup, restore, redaction (§D6, §D13) and pack (§D4, R7): the writers that remove, bring back, blank
or archive what a package holds."""
import json
import os
import re
import shutil

import memory_config as mcfg
import memory_format as mf
import memory_io as mio
import memory_packages as mpkg
import memory_verify as mver


# ------------------------------------------------------------------ cleanup, restore, redact (§D6, §D13)
def cleanup_ready(root, task_id, cfg, packages=None):
    """The R22 conditions for one task, or the first that fails."""
    packages = packages if packages is not None else mpkg.load_packages(root)
    seals = [(n, e) for n, (_, entries, _) in packages.items() for e in entries
             if e.get("kind") == "task" and e.get("task") == task_id]
    if not cfg.cleanup:
        return "cleanup is off in %s" % mio.POLICY_REL
    if not seals:
        return "no seal for %s in a package in the working tree" % task_id
    findings = mver.check_packages({n: packages[n] for n, _ in seals}, cfg.package_max_bytes)
    if findings:
        return "its package does not verify (%s)" % findings[0].what
    for _, seal in seals:
        if (seal.get("counts") or {}).get("skipped"):
            return "%s has %s torn journal line(s)" % (mf.key_of(seal), seal["counts"]["skipped"])
    journal = mio.read_bytes(os.path.join(root, ".ai", "reports", task_id, "events.jsonl"))
    if journal is not None:
        found = mver.check_journals(lambda rel: journal if rel.endswith("events.jsonl") else None,
                               [".ai/reports/%s/events.jsonl" % task_id], packages)
        found = [f for f in found if f.check == "V5"]
        if found:
            return "coverage is incomplete (%s)" % found[0].what
    return None


def cleanup_task(root, task_id, cfg):
    """B6: .ai/reports/<id> → .ai/state/logs/<id>/report; copy, verify,
    remove when the two are on different filesystems."""
    why = cleanup_ready(root, task_id, cfg)
    if why:
        raise mio.MemoryError_(why, 1)
    src = os.path.join(root, ".ai", "reports", task_id)
    dest = os.path.join(root, ".ai", "state", "logs", task_id, "report")
    if not os.path.isdir(src):
        return "%s already cleaned up" % task_id
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        raise mio.MemoryError_("%s exists: 'state.py memory restore %s' first" % (os.path.relpath(dest, root), task_id), 3)
    try:
        if os.environ.get("AI_MEMORY_FORCE_EXDEV"):
            raise OSError(18, "Invalid cross-device link (forced)")
        os.replace(src, dest)
    except OSError as exc:
        if exc.errno != 18:
            raise
        shutil.copytree(src, dest)
        if tree_digest(src) != tree_digest(dest):
            shutil.rmtree(dest, ignore_errors=True)
            raise mio.MemoryError_("the copy of %s does not match its source — nothing removed" % task_id, 3) \
                from exc
        shutil.rmtree(src)
    return "%s → %s" % (os.path.relpath(src, root), os.path.relpath(dest, root))


def tree_digest(path):
    import hashlib  # pylint: disable=import-outside-toplevel
    h = hashlib.sha256()
    for dirpath, dirs, names in os.walk(path):
        dirs.sort()
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            h.update(os.path.relpath(full, path).encode() + b"\0" + (mio.read_bytes(full) or b"") + b"\0")
    return h.hexdigest()


def cleanup(root, ids):
    cfg = mcfg.load_config(root)
    if not cfg.packages:
        raise mio.MemoryError_("files mode: cleanup needs packages mode", 2)
    if not cfg.cleanup:
        raise mio.MemoryError_("cleanup is off: set \"cleanup\": true in %s once 'memory verify --all' and "
                           "'--fresh-clone' are green (§D6)" % mio.POLICY_REL, 2)
    findings = [f for f in mver.verify(root) if not f.check.endswith("-warn")]
    if findings:
        raise mio.MemoryError_("'memory verify --all' is not green: %s" % mver.format_finding(findings[0]), 1)
    packages = mpkg.load_packages(root)
    if ids == "all":
        ids = sorted(mpkg.sealed_task_ids(packages) & set(os.listdir(os.path.join(root, ".ai", "reports"))))
    out = []
    for task_id in ids:
        try:
            out.append(cleanup_task(root, task_id, cfg))
        except mio.MemoryError_ as exc:
            out.append("%s kept: %s" % (task_id, exc))
    return out


def restore(root, ids):
    import memory_store  # pylint: disable=import-outside-toplevel
    logs = os.path.join(root, ".ai", "state", "logs")
    if ids == "all":
        ids = sorted(n for n in os.listdir(logs) if os.path.isdir(os.path.join(logs, n, "report"))) \
            if os.path.isdir(logs) else []
        history = memory_store.FileHistory(root, mcfg.load_config(root))
        ids = sorted(set(ids) | {s.get("task") for s in history.seals().values()
                                 if not os.path.isdir(os.path.join(root, ".ai", "reports", s.get("task") or "-"))
                                 and mf.NEW_ID_RE.match(s.get("task") or "")})
    out = []
    history = None
    for task_id in ids:
        dest = os.path.join(root, ".ai", "reports", task_id)
        raw = os.path.join(logs, task_id, "report")
        if os.path.isdir(dest):
            out.append("%s is in .ai/reports/ already" % task_id)
            continue
        if os.path.isdir(raw):
            os.replace(raw, dest)
            out.append("%s restored from %s" % (task_id, os.path.relpath(raw, root)))
            continue
        history = history or memory_store.FileHistory(root, mcfg.load_config(root))
        entries = history.entries(task_id)
        if not entries:
            out.append("%s: nothing recorded" % task_id)
            continue
        os.makedirs(dest)
        md = ["<!-- restored from record %s — a reconstruction, not the original task.md -->" % mio.now()]
        md += mf.render_task_md(entries)
        mio.atomic_write(os.path.join(dest, "task.md"), "\n".join(md) + "\n")
        lines = []
        for e in entries:
            data = {k: v for k, v in e.items() if k not in mf.ENVELOPE}
            data["restored"] = True
            data["rid"] = e["rid"]
            lines.append(json.dumps({"ts": e["ts"], "task": task_id, "event": "restored_%s" % e["kind"],
                                     "actor": e["actor"], "runtime": e["runtime"], "stage": "",
                                     "detail": "restored from record", "data": data}, ensure_ascii=False))
        mio.atomic_write(os.path.join(dest, "events.jsonl"), "\n".join(lines) + "\n")
        out.append("%s restored from record (task.md marked, events.jsonl with data.restored)" % task_id)
    return out


def redact(root, rid, field, why, by=None):
    """The one exception to append-only (R8): the field becomes "[redacted]",
    the line gets a new rid, a redaction entry names the old one."""
    cfg = mcfg.load_config(root)
    with mio.locked(root):
        packages = mpkg.load_packages(root)
        for name, (header, entries, _) in packages.items():
            hit = [e for e in entries if e["rid"] == rid]
            if not hit:
                continue
            entry = mf.strip_private(hit[0])
            if field in mf.ENVELOPE or field not in entry:
                raise mio.MemoryError_("%s has no redactable field %r" % (rid, field), 2)
            new = dict(entry, **{field: "[redacted]"})
            new = mf.with_rid(new)
            note = mf.with_rid({"v": mf.FORMAT, "task": entry.get("task"), "inst": entry.get("inst") or 1,
                                "seq": entry.get("seq") or 0, "kind": "redaction", "ts": mio.now(), "actor": "human",
                                "by": by, "runtime": "unknown", "src": ["state.py memory redact"],
                                "target": rid, "field": field, "why": why, "replacement": new["rid"]})
            rest = [mf.strip_private(e) for e in entries if e["rid"] != rid]
            mio.atomic_write(os.path.join(mio.memory_dir(root), name), mf.render_package(header, rest + [new, note]))
            del cfg
            return new["rid"], name
    raise mio.MemoryError_("no entry %s in .ai/memory/" % rid, 1)


# ------------------------------------------------------------------ pack (§D4, R7)
def pack(root, period):
    cfg = mcfg.load_config(root)
    if not re.match(r"^\d{4}(?:-\d{2}|-Q[1-4])?$", period or ""):
        raise mio.MemoryError_("--period takes YYYY-MM, YYYY-Qn or YYYY", 2)
    grain = "quarter" if "-Q" in period else ("month" if "-" in period else "year")
    current = mf.period_of(mio.now(), grain)
    if period >= current:
        raise mio.MemoryError_("period %s has not ended (now %s)" % (period, current), 2)
    with mio.locked(root):
        packages = mpkg.load_packages(root)
        mine = [n for n in packages if (mf.parse_package_name(n) or {}).get("period") == period
                and (mf.parse_package_name(n) or {}).get("author") == cfg.author]
        if not mine:
            raise mio.MemoryError_("no package of %s for %s" % (cfg.author, period), 1)
        target = mf.package_name(period, cfg.author)
        before = set()
        entries = {}
        for name in mine:
            for e in packages[name][1]:
                before.add(e["rid"])
                entries[e["rid"]] = mf.strip_private(e)
        seals = {mf.key_of(e): e for e in entries.values() if e.get("kind") == "task"}

        def order(e):
            seal = seals.get(mf.key_of(e)) or {}
            return (seal.get("closed_at") or e.get("ts") or "", mf.key_of(e), e.get("seq") or 0, e["rid"])
        ordered = sorted(entries.values(), key=order)
        header = mf.package_header(period, cfg.author, None, mio.now())
        data = b"\n".join([mf.canonical(header)] + [mf.canonical(e) for e in ordered]) + b"\n"
        mio.atomic_write(os.path.join(mio.memory_dir(root), target), data)
        _, check, errors = mf.parse_package(data, target)
        if errors or {e["rid"] for e in check} != before:
            raise mio.MemoryError_("the pack does not hold the batches' rid set — batches kept", 3)
        removed = [n for n in mine if n != target]
        for name in removed:
            os.remove(os.path.join(mio.memory_dir(root), name))
        books = mpkg.read_batches(root)
        books["open"] = {b: n for b, n in books["open"].items() if n not in removed}
        mpkg.write_batches(root, books)
    return target, removed, len(before)
