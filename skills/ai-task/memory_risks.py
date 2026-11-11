"""Risks in the record (§D9): the files-mode and packages-mode writers of a risk entry and the journal
append they share."""
import os

import memory_compact as mc
import memory_format as mf
import memory_io as mio
import memory_packages as mpkg


# ------------------------------------------------------------------ risks (§D9)
def risk_add_files(root, title, where, label, what, likely, fix, status, found):
    """Files mode: append the template section (plus Label) to known-risks.md."""
    import memory_compact  # pylint: disable=import-outside-toplevel,reimported
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = mio.read_bytes(path)
    text = text.decode("utf-8") if text is not None else "# Known risks\n"
    risks, _ = memory_compact.parse_known_risks(text)
    rkey = memory_compact.rkey_of(title)
    if any(r["rkey"] == rkey for r in risks):
        raise mio.MemoryError_("a risk titled %r is already recorded (%s)" % (title, rkey), 2)
    section = memory_compact.risk_section(title, where, label, what, likely, fix, status, found)
    body = text.rstrip("\n") + "\n\n" + "\n".join(section) + "\n"
    mio.atomic_write(path, body)
    return rkey


def risk_close_files(root, rkey, status, why):
    import memory_compact  # pylint: disable=import-outside-toplevel,reimported
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = (mio.read_bytes(path) or b"").decode("utf-8")
    risks, leftovers = memory_compact.parse_known_risks(text)
    hit = [r for r in risks if r["rkey"] == rkey]
    if not hit:
        raise mio.MemoryError_("no risk %s in known-risks.md ('state.py memory risks --status all')" % rkey, 1)
    lines = hit[0]["text"].split("\n")
    for i, line in enumerate(lines):
        if line.startswith("- **Status**:"):
            lines[i] = "- **Status**: %s — %s" % (status, why)
            break
    else:
        lines.append("- **Status**: %s — %s" % (status, why))
    hit[0]["text"] = "\n".join(lines)
    mio.atomic_write(path, memory_compact.render_known_risks(risks, leftovers))


def risk_data(title, where, label, what, likely, fix, status, why=None, supersedes=None, by=None):
    data = {"rkey": mc.rkey_of(title), "title": title, "where": where, "label": label, "what": what,
            "likelihood": likely, "fix": fix, "status": status, "status_why": why, "supersedes": supersedes}
    if by:
        data["by"] = by
    return data


def standalone_risk(root, cfg, data, runtime="unknown", by=None):
    """A risk with no task in flight: one entry, straight into the open batch."""
    entry = {"v": mf.FORMAT, "task": None, "inst": 1, "seq": 0, "kind": "risk", "ts": mio.now(), "actor": "agent",
             "by": by, "runtime": runtime if runtime in mf.RUNTIMES else "unknown", "src": ["state.py memory risk"]}
    entry.update({k: data.get(k) for k in ("rkey", "title", "where", "label", "what", "likelihood", "fix",
                                           "status", "status_why")})
    entry.update(found_by=None, text=None)
    if data.get("supersedes"):
        entry["supersedes"] = data["supersedes"]
    entry = mf.with_rid(entry)
    append_entries(root, cfg, [entry])
    return entry


def append_entries(root, cfg, entries):
    """Entries outside a close (a standalone risk, a redaction) into the open batch."""
    with mio.locked(root):
        name, branch, books = mpkg.open_batch(root, cfg)
        packages = mpkg.load_packages(root)
        have = mpkg.all_rids(packages)
        header, current, _ = packages.get(name, (None, [], []))
        parts = mf.parse_package_name(name)
        header = header or mf.package_header(parts["period"], cfg.author, parts["batch"], mio.now())
        new = [e for e in entries if e["rid"] not in have]
        if new:
            mio.atomic_write(os.path.join(mio.memory_dir(root), name),
                         mf.render_package(header, [mf.strip_private(e) for e in current] + new))
            books["open"][branch] = name
            mpkg.write_batches(root, books)
    return name
