"""Verification (§D6, §D10): the findings of the package and journal checks, verify and its fresh-clone form,
the git tree reader and the range check the pre-push validator runs."""
import collections
import json
import os
import re
import subprocess
import tempfile
import time

import memory_compact as mc
import memory_config as mcfg
import memory_format as mf
import memory_io as mio
import memory_packages as mpkg


# ------------------------------------------------------------------ verify (§D6)
Finding = collections.namedtuple("Finding", "check path line what fix")


def kept_lines(events, schema=None):
    """The journal lines V5 requires to be the src of an entry."""
    out = []
    for number, event in events:
        if not event:
            continue
        if event.get("event") == "task_started":
            schema = (event.get("data") or {}).get("schema", schema)
        rule = mf.classify(event.get("event"), schema)
        if rule not in ("seal", "summary", "drop", "verify"):
            out.append(number)
    return out


def check_packages(packages, max_bytes, sizes=None, changed=None, ref_name=None):
    """V1, V3, V4, V8 over one tree's packages."""
    findings = []
    sizes = sizes or {}
    for name, (_, kept, errors) in sorted(packages.items()):
        if changed is not None and name not in changed:
            continue
        over = {e["_line"]: e for e in kept if "_over" in e}
        for line, what in errors:
            fix = ("restore the line from git ('git checkout -- %s') or 'state.py memory verify'"
                   % os.path.join(mio.MEMORY_REL, name))
            if line in over and what.startswith("line is "):
                entry = over[line]
                sizes_of = {k: len(mf.canonical(v)) for k, v in entry.items()
                            if k not in mf.ENVELOPE and not k.startswith("_")}
                field = max(sizes_of, key=sizes_of.get, default="changes")
                fix = ("shorten it: 'state.py memory redact %s --field %s --why \"…\"' (the human's route)"
                       % (entry["rid"], field))
            findings.append(Finding("V1", os.path.join(mio.MEMORY_REL, name), line, what, fix))
    by_key = collections.defaultdict(list)
    conflicts = set()
    redacted = {}
    for name, (_, entries, _) in packages.items():
        for e in entries:
            by_key[mf.key_of(e)].append((name, e))
            if e.get("kind") == "conflict":
                conflicts.add((e.get("key"), tuple(e.get("rids") or [])))
            if e.get("kind") == "redaction" and e.get("replacement"):
                redacted[e["replacement"]] = e.get("target")
    for key, items in sorted(by_key.items()):
        seals = [(n, e) for n, e in items if e.get("kind") == "task"]
        unique = {e["rid"]: (n, e) for n, e in seals}
        chained = {e.get("supersedes") for _, e in unique.values() if e.get("supersedes")}
        live = [rid for rid in unique if rid not in chained]
        if len(live) > 1:
            task = key.rsplit("#", 1)[0]
            recorded = any(k == key and set(live) <= set(r) for k, r in conflicts)
            if mf.NEW_ID_RE.match(task) and not recorded:
                findings.append(Finding("V3", os.path.join(mio.MEMORY_REL, unique[live[0]][0]), None,
                                        "%s has %d seals not chained by supersedes" % (key, len(live)),
                                        "'state.py memory export %s' records the two as a conflict" % task))
            elif not recorded:
                findings.append(Finding("V3", os.path.join(mio.MEMORY_REL, unique[live[0]][0]), None,
                                        "legacy %s has %d seals and no conflict entry" % (key, len(live)),
                                        "'state.py memory export %s' records the conflict" % task))
        rids = {e["rid"] for _, e in items if e.get("kind") not in ("task", "conflict", "redaction")}
        if len(live) > 1:
            continue                      # a recorded conflict: which entries are whose is not knowable
        for rid in live:
            name, seal = unique[rid]
            own = sorted({redacted.get(r, r) for r in rids if _belongs(items, r, seal)})
            if len(own) != seal.get("entries") or mf.seal_digest(own) != seal.get("digest"):
                findings.append(Finding("V4", os.path.join(mio.MEMORY_REL, name), seal.get("_line"),
                                        "%s: the seal names %s entries (%s), the package has %d" % (
                                            key, seal.get("entries"), (seal.get("digest") or "")[:19], len(own)),
                                        "'state.py memory export %s' re-exports it" % seal.get("task")))
    for name, size in sorted(sizes.items()):
        if size > 2 * max_bytes:
            findings.append(Finding("V8", os.path.join(mio.MEMORY_REL, name), None,
                                    "%d bytes, over twice package_max_bytes (%d)" % (size, max_bytes),
                                    "a new batch opens on the next close; 'state.py memory pack' folds old ones"))
        elif size > max_bytes:
            findings.append(Finding("V8-warn", os.path.join(mio.MEMORY_REL, name), None,
                                    "%d bytes, over package_max_bytes (%d)" % (size, max_bytes),
                                    "nothing to do now; the next close opens a new batch"))
    del ref_name
    return findings


def _belongs(items, rid, seal):
    """Entries of a key that came before its seal (seq below the seal's)."""
    for _, e in items:
        if e["rid"] == rid:
            return (e.get("seq") or 0) < (seal.get("seq") or 0)
    return False


def check_journals(read, paths, packages, cleanup_on=False):
    """V5 (and V7 with cleanup) against the committed journals."""
    findings = []
    seals = mpkg.seals_by_key(packages)
    sealed_tasks = {k.rsplit("#", 1)[0] for k in seals}
    srcs = collections.defaultdict(set)
    for _, entries, _ in packages.values():
        for e in entries:
            for s in e.get("src") or []:
                srcs[mf.key_of(e)].add(s)
    journals = sorted(p for p in paths if re.match(r"^\.ai/reports/[^/]+/events\.jsonl$", p))
    for path in journals:
        task = path.split("/")[2]
        data = read(path) or b""
        if b'"task_closed"' not in data:
            continue
        if not (mf.NEW_ID_RE.match(task) or task in sealed_tasks):
            continue                       # an unmigrated legacy task: 'memory status' lists it
        events = mc.parse_journal(data)
        instances = mc.split_instances(events)
        for inst, lines in enumerate(instances, 1):
            key = "%s#%d" % (task, inst)
            closed = any(e and e.get("event") == "task_closed" for _, e in lines)
            if not closed and inst == len(instances):
                continue
            if key not in seals:
                findings.append(Finding("V5", path, None, "%s is closed but has no seal" % key,
                                        "state.py memory export %s" % task))
                continue
            missing = [n for n in kept_lines(lines) if "events.jsonl:%d" % n not in srcs[key]]
            if missing:
                findings.append(Finding("V5", path, missing[0], "%s: %d kept line(s) are no entry's src" % (
                    key, len(missing)), "state.py memory export %s" % task))
        if cleanup_on and task in sealed_tasks:
            findings.append(Finding("V7", "/".join(path.split("/")[:3]) + "/", None,
                                    "cleanup is on and %s is sealed" % task, "state.py memory cleanup %s" % task))
    return findings


def verify(root, scope="all", ids=None):
    """Findings for --all or ids over the working tree; [] is green."""
    cfg = mcfg.load_config(root)
    packages = mpkg.load_packages(root)
    sizes = {n: os.path.getsize(os.path.join(mio.memory_dir(root), n)) for n in packages}
    findings = check_packages(packages, cfg.package_max_bytes, sizes)
    reports = os.path.join(root, ".ai", "reports")
    paths = []
    for name in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        if ids and name not in ids:
            continue
        if os.path.exists(os.path.join(reports, name, "events.jsonl")):
            paths.append(".ai/reports/%s/events.jsonl" % name)
    findings += check_journals(lambda rel: mio.read_bytes(os.path.join(root, rel)), paths, packages, False)
    if ids:
        findings = [f for f in findings if any(i in (f.path or "") or i in f.what for i in ids)]
    del scope
    return findings


def verify_fresh_clone(root):
    """§D6: a local clone of HEAD, rebuilt from packages alone, shows every
    sealed key as this clone does."""
    import memory_store  # pylint: disable=import-outside-toplevel
    findings = []
    here = memory_store.FileHistory(root, mcfg.load_config(root))
    keys = sorted({mf.key_of(e) for _, entries, _ in mpkg.load_packages(root).values() for e in entries
                   if e.get("kind") == "task"})
    with tempfile.TemporaryDirectory(prefix="ai-memory-clone-") as tmp:
        clone = os.path.join(tmp, "clone")
        code, _, err = mio.git(root, "clone", "-q", "--no-hardlinks", root, clone)
        if code != 0:
            raise mio.MemoryError_("git clone failed: %s" % err.strip(), 3)
        there = memory_store.FileHistory(clone, mcfg.load_config(clone))
        for key in keys:
            a = "\n".join(mf.render_task_md(here.entries(key)))
            b = "\n".join(mf.render_task_md(there.entries(key)))
            if a != b:
                findings.append(Finding("fresh-clone", key, None, "renders differently in a fresh clone",
                                        "commit .ai/memory/ (the clone sees HEAD only)"))
    return findings


def format_finding(f, ref=None):
    where = f.path + (":%s" % f.line if f.line else "")
    return "%s%s: %s: %s — fix: %s" % ("%s: " % ref if ref else "", f.check, where, f.what, f.fix)


# ------------------------------------------------------------------ git trees (§D10)
class GitTreeReader:
    """Blobs of one commit, through one `git cat-file --batch`."""

    def __init__(self, repo, sha):
        self.repo, self.sha = repo, sha
        self._cache = {}
        self._paths = None

    def paths(self):
        if self._paths is None:
            code, out, _ = mio.git(self.repo, "ls-tree", "-r", "-z", "--name-only", self.sha, binary=True)
            self._paths = [p.decode("utf-8", "replace") for p in out.split(b"\0") if p] if code == 0 else []
        return self._paths

    def read_many(self, rels):
        wanted = [r for r in rels if r not in self._cache]
        if wanted:
            stdin = "".join("%s:%s\n" % (self.sha, r) for r in wanted).encode("utf-8")
            done = subprocess.run(["git", "-C", self.repo, "cat-file", "--batch"], input=stdin,
                                  capture_output=True, check=False)
            data, pos = done.stdout, 0
            for rel in wanted:
                end = data.find(b"\n", pos)
                head = data[pos:end].split(b" ")
                pos = end + 1
                if len(head) == 2 and head[1] == b"missing" or len(head) < 3:
                    self._cache[rel] = None
                    continue
                size = int(head[2])
                self._cache[rel] = data[pos:pos + size]
                pos += size + 1
        return {r: self._cache.get(r) for r in rels}

    def read(self, rel):
        return self.read_many([rel])[rel]

    def listdir(self, rel):
        prefix = rel.rstrip("/") + "/"
        return sorted({p[len(prefix):].split("/")[0] for p in self.paths() if p.startswith(prefix)})


def rev(repo, name):
    code, out, _ = mio.git(repo, "rev-parse", "--verify", "-q", name + "^{commit}")
    return out.strip() if code == 0 and out.strip() else None


def policy_at(repo, sha):
    code, out, _ = mio.git(repo, "show", "%s:%s" % (sha, mio.POLICY_REL.replace(os.sep, "/")))
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        return {"mode": "invalid"}
    return data if isinstance(data, dict) else {"mode": "invalid"}


def validate_range(repo, old, new, local=False):
    """(findings, stats) for the commits O..T (§D10). O may be None: then only
    the structure of T is checked."""
    started = time.time()
    policy = policy_at(repo, new)
    if policy is None or policy.get("mode", "files") == "files":
        return None, {}
    if policy.get("mode") == "invalid":
        return [Finding("V1", mio.POLICY_REL, None, "memory.json at %s is not valid JSON" % new[:9],
                        "fix the file, or 'state.py memory disable'")], {}
    max_bytes = int(policy.get("package_max_bytes", mcfg.DEFAULTS["package_max_bytes"]))
    tree = GitTreeReader(repo, new)
    paths = tree.paths()
    pkg_paths = [p for p in paths if p.startswith(".ai/memory/") and p.endswith(".jsonl")]
    blobs = tree.read_many(pkg_paths)
    packages = {p.split("/", 2)[2]: mf.parse_package(blobs[p] or b"", p.split("/", 2)[2]) for p in pkg_paths}
    sizes = {p.split("/", 2)[2]: len(blobs[p] or b"") for p in pkg_paths}
    changed, added = None, []
    findings = []
    if old:
        code, out, _ = mio.git(repo, "diff", "--name-status", "--no-renames", old, new, "--", ".ai")
        rows = [line.split("\t") for line in out.splitlines() if "\t" in line] if code == 0 else []
        changed = {r[1].split("/", 2)[2] for r in rows if r[1].startswith(".ai/memory/")}
        added = [r[1] for r in rows if r[0].startswith("A")]
        before = GitTreeReader(repo, old)
        old_pkgs = [p for p in before.paths() if p.startswith(".ai/memory/") and p.endswith(".jsonl")]
        old_blobs = before.read_many(old_pkgs)
        old_rids = set()
        for p in old_pkgs:
            _, entries, _ = mf.parse_package(old_blobs[p] or b"")
            old_rids |= {e["rid"] for e in entries}
        new_rids = mpkg.all_rids(packages)
        redacted = {e.get("target") for _, entries, _ in packages.values() for e in entries
                    if e.get("kind") == "redaction"}
        lost = sorted(old_rids - new_rids - redacted)
        if lost:
            findings.append(Finding("V2", ".ai/memory/", None, "%d record(s) of %s are gone (%s…)" % (
                len(lost), old[:9], lost[0]), "git checkout %s -- .ai/memory/ and merge the lines back" % old[:9]))
    findings = check_packages(packages, max_bytes, sizes, changed) + findings
    journals = [p for p in paths if re.match(r"^\.ai/reports/[^/]+/events\.jsonl$", p)]
    journal_blobs = tree.read_many(journals)   # one cat-file --batch for every journal (§D10)
    findings += check_journals(journal_blobs.get, journals, packages, bool(policy.get("cleanup")))
    for path in added:
        if path.startswith(".ai/reports/") and path.endswith(".log"):
            findings.append(Finding("V6", path, None, "a log is committed under .ai/reports/",
                                    "git rm --cached %s (logs live in .ai/state/logs/)" % path))
    for path in paths:
        # The index lives under .ai/local/; a project's own SQLite file elsewhere is not ours.
        if path.startswith(".ai/local/") or path.startswith(".ai/state/logs/") or \
                (path.startswith(".ai/") and ".sqlite3" in path):
            findings.append(Finding("V6", path, None, "local data is committed",
                                    "git rm --cached %s (.ai/local/ and .ai/state/logs/ stay local)" % path))
    if local:
        outbox = mio.local_path(repo, "outbox")
        if os.path.isdir(outbox) and any(n.endswith(".jsonl") for n in os.listdir(outbox)):
            findings.append(Finding("V9", os.path.join(mio.LOCAL_REL, "outbox"), None, "an export is pending",
                                    "state.py memory export --pending, commit, push again"))
    stats = {"packages": len(packages), "tasks": len(journals), "ms": int((time.time() - started) * 1000)}
    return findings, stats
