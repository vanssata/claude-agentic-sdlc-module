"""The History interface over a project's record (spec §D7, §D8).

FileHistory reads the packages under .ai/memory/, every legacy
.ai/reports/<id>/ whose key no package seals (compacted in tracked mode),
and the sections of .ai/project/known-risks.md. SqliteHistory (the optional
local index) answers the same calls from .ai/local/memory/index.sqlite3.
Both hand their entries to the one ranker and the one matcher in
memory_format, so recall and search are byte-identical across backends (R11).
"""
import json
import os
import re

import memory_compact as mc
import memory_format as mf

STATE_NAMES = ("state.json", "current.json")


def current_task(root):
    """The task in flight, from the live state, or None."""
    for name in STATE_NAMES:
        try:
            with open(os.path.join(root, ".ai", "state", name), encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(state, dict) and state.get("current_stage") != "done" and state.get("task_id"):
            return state["task_id"]
    return None


def risk_entries_from_md(text, src_name="known-risks.md"):
    """known-risks.md sections as risk entries without a task (files mode)."""
    risks, _ = mc.parse_known_risks(text)
    out = []
    for i, risk in enumerate(risks):
        found = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", risk["text"])
        entry = {"v": mf.FORMAT, "task": None, "inst": 1, "seq": i, "kind": "risk",
                 "ts": "%sT00:00:00Z" % found.group(1) if found else "1970-01-01T00:00:00Z",
                 "actor": "unknown", "by": None, "runtime": "unknown", "src": ["%s#%s" % (src_name, risk["rkey"])]}
        entry.update({k: risk[k] for k in ("rkey", "title", "where", "label", "what", "likelihood", "fix",
                                           "status", "status_why", "found_by", "text")})
        if risk["label_derived"]:
            entry["label_derived"] = True
        out.append(mf.with_rid(entry))
    return out


class History:
    """The interface: tasks, entries, raw_journal, task_window, recall,
    search, risks. Subclasses provide load()."""

    def __init__(self, root, cfg=None):
        self.root = root
        self.cfg = cfg
        self._loaded = None

    # ---------------------------------------------------------- loading
    def load(self):                       # pragma: no cover - abstract
        raise NotImplementedError

    def data(self):
        if self._loaded is None:
            self._loaded = self.load()
        return self._loaded

    def all_entries(self):
        return self.data()["entries"]

    def seals(self):
        """{key: seal}; for a conflicting key, the newest seal."""
        out = {}
        for e in self.all_entries():
            if e.get("kind") == "task":
                key = mf.key_of(e)
                if key not in out or (e.get("ts") or "", e["rid"]) > (out[key].get("ts") or "", out[key]["rid"]):
                    out[key] = e
        return out

    def superseded(self):
        return {e["supersedes"] for e in self.all_entries() if e.get("supersedes")}

    # ---------------------------------------------------------- the calls
    def tasks(self):
        return sorted(self.seals().values(), key=lambda s: (s.get("closed_at") or s.get("ts") or "", s["rid"]))

    def entries(self, key):
        """A key is `<task>#<inst>` or a bare task id (every instance)."""
        if "#" in key:
            return mf.sort_entries([e for e in self.all_entries() if mf.key_of(e) == key])
        return mf.sort_entries([e for e in self.all_entries() if e.get("task") == key])

    def conflicts(self):
        by_key = {}
        for e in self.all_entries():
            if e.get("kind") == "task":
                by_key.setdefault(mf.key_of(e), set()).add(e["rid"])
        chained = self.superseded()
        return {k: sorted(v) for k, v in by_key.items() if len(v - chained) > 1}

    def raw_journal(self, task_id):
        for rel in (".ai/reports/%s/events.jsonl" % task_id, ".ai/state/logs/%s/report/events.jsonl" % task_id):
            try:
                with open(os.path.join(self.root, rel), "rb") as fh:
                    return fh.read()
            except OSError:
                continue
        return None

    def task_window(self, task_id):
        """(started_at, closed_at) of the task's last instance, from its seal."""
        found = [s for s in self.seals().values() if s.get("task") == task_id]
        if not found:
            return None
        seal = max(found, key=lambda s: s.get("inst") or 0)
        return seal.get("started_at"), seal.get("closed_at")

    def risks(self, status="open"):
        latest = {}
        dead = self.superseded()
        for e in self.all_entries():
            if e.get("kind") != "risk" or e["rid"] in dead:
                continue
            have = latest.get(e.get("rkey"))
            if have is None or (e.get("ts") or "", e["rid"]) > (have.get("ts") or "", have["rid"]):
                latest[e.get("rkey")] = e
        out = sorted(latest.values(), key=lambda e: (mf.desc_key(e.get("ts") or ""), e["rid"]))
        return out if status == "all" else [e for e in out if e.get("status") == status]

    def source(self):
        d = self.data()
        return {"packages": d["packages"], "legacy": d["legacy"], "index": d.get("index") or self.index_name(),
                "fts5": False, "fallback": d.get("fallback", False)}

    def index_name(self):
        return "none"

    def recall(self, files, budget=1500, max_items=40, kinds=None, all_risks=False, offset=0, exclude=None):
        exclude = exclude if exclude is not None else current_task(self.root)
        entries = [e for e in self.all_entries() if not (exclude and e.get("task") == exclude)]
        items, _ = mf.candidate_items(entries, self.seals(), self.superseded(), all_risks)
        if kinds:
            wanted = set(kinds)
            items = [i for i in items if KIND_GROUP.get(i["kind"]) in wanted]
        return mf.rank_recall(items, files, budget, max_items, offset, self.source(), exclude)

    def search(self, query, filters=None, limit=20, offset=0):
        tokens = mf.tokenize(query)
        seals = self.seals()
        hits = [e for e in self.candidates(tokens, filters)
                if mf.match_search(e, tokens, filters, seals.get(mf.key_of(e)))]
        hits.sort(key=mf.search_order)
        return hits[offset:offset + limit], len(hits)

    def candidates(self, tokens, filters):
        del tokens, filters
        return self.all_entries()


KIND_GROUP = {"risk": "risk", "review": "review", "question": "decision", "override": "decision",
              "approval": "decision", "note": "decision", "scope": "scope", "task": "task"}


class FileHistory(History):
    """Packages, legacy report directories and known-risks.md, read each call."""

    def load(self):
        return load_files(self.root, self.cfg)


def package_files(root):
    base = os.path.join(root, ".ai", "memory")
    try:
        return sorted(n for n in os.listdir(base) if n.endswith(".jsonl"))
    except OSError:
        return []


def load_files(root, cfg=None):
    """Everything FileHistory reads, plus the problems it met on the way."""
    entries, errors, sealed = [], [], set()
    names = package_files(root)
    for name in names:
        try:
            with open(os.path.join(root, ".ai", "memory", name), "rb") as fh:
                data = fh.read()
        except OSError as exc:
            errors.append((name, 0, str(exc)))
            continue
        _, found, problems = mf.parse_package(data, name)
        errors += [(name, line, what) for line, what in problems]
        for e in found:
            e = mf.strip_private(e)
            entries.append(e)
            if e.get("kind") == "task":
                sealed.add(e.get("task"))
    rids = set()
    unique = []
    for e in entries:
        if e["rid"] not in rids:
            rids.add(e["rid"])
            unique.append(e)
    entries = unique
    legacy = legacy_entries(root, sealed, cfg)
    entries += legacy["entries"]
    md_risks = []
    text = read_text(os.path.join(root, ".ai", "project", "known-risks.md"))
    if text:
        md_risks = risk_entries_from_md(text)
        entries += [e for e in md_risks if e["rid"] not in rids]
    entries += live_risks(root)
    return {"entries": entries, "errors": errors, "packages": len(names), "legacy": legacy["count"],
            "legacy_keys": legacy["keys"], "known_risks": len(md_risks)}


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def legacy_entries(root, sealed, cfg=None):
    """Closed report directories no package seals, compacted from their
    tracked files only, so every clone sees the same rids."""
    reports = os.path.join(root, ".ai", "reports")
    reader = mc.FsReader(root)
    out, keys, count = [], [], 0
    excerpt_max = getattr(cfg, "excerpt_max_bytes", 1024) if cfg is not None else 1024
    in_flight = current_task(root)
    del reports
    for name in legacy_names(root):
        if name in sealed or name == in_flight:
            continue
        found = legacy_dir_entries(reader, name, excerpt_max)
        if not found:
            continue
        count += 1
        out += found
        keys += sorted({mf.key_of(e) for e in found if e.get("kind") == "task"})
    return {"entries": out, "keys": keys, "count": count}


def legacy_names(root):
    reports = os.path.join(root, ".ai", "reports")
    return [n for n in (sorted(os.listdir(reports)) if os.path.isdir(reports) else [])
            if n.startswith("T-") and mf.is_task_id(n)]


def legacy_dir_entries(reader, name, excerpt_max=1024):
    """One closed report directory, compacted from its tracked files; [] when
    its last instance is still open."""
    found = mc.compact_instances(reader, name, "tracked", excerpt_max)
    closed = [c for c in found if c.seal and c.seal["result"] in ("closed", "abandoned", "restarted")]
    if not closed or found[-1].seal["result"] == "open":
        return []
    return [e for c in closed for e in c.entries + [c.seal]]


def live_risks(root):
    """risk_recorded lines of the task in flight: `memory risks` shows them
    before close compacts them (§D9)."""
    task = current_task(root)
    if not task:
        return []
    data = mc.FsReader(root).read(".ai/reports/%s/events.jsonl" % task)
    out = []
    for number, event in mc.parse_journal(data):
        if not event or event.get("event") != "risk_recorded":
            continue
        d = event.get("data") or {}
        entry = {"v": mf.FORMAT, "task": task, "inst": 1, "seq": number, "kind": "risk",
                 "ts": mc.ts_ok(event.get("ts")), "actor": mc.actor_of(event), "by": d.get("by"),
                 "runtime": mc.runtime_of(event), "src": ["events.jsonl:%d" % number]}
        entry.update({k: d.get(k) for k in ("rkey", "title", "where", "label", "what", "likelihood", "fix",
                                            "status", "status_why")})
        entry.update(found_by=task, text=d.get("text"))
        if d.get("supersedes"):
            entry["supersedes"] = d["supersedes"]
        out.append(mf.with_rid(entry))
    return out


def open_history(root, cfg=None):
    """The index when the developer chose it and it answers; FileHistory otherwise."""
    if cfg is not None and getattr(cfg, "index", "none") == "sqlite":
        try:
            history = SqliteHistory(root, cfg)
            history.data()
            return history
        except Exception as exc:  # pylint: disable=broad-except  # any index failure falls back
            history = FileHistory(root, cfg)
            history.data()["fallback"] = True
            history.data()["index"] = "sqlite"
            history.data()["fallback_why"] = str(exc)
            return history
    return FileHistory(root, cfg)


# ------------------------------------------------------------------ the local index (§D7, §I3, M10)
INDEX_REL = os.path.join(".ai", "local", "memory", "index.sqlite3")
USER_VERSION = 1
DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS packages(path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, sha256 TEXT,
                                    author TEXT, period TEXT, entries INTEGER);
CREATE TABLE IF NOT EXISTS tasks(key TEXT PRIMARY KEY, task_id TEXT NOT NULL, inst INTEGER NOT NULL,
                                 started_at TEXT, closed_at TEXT, result TEXT, mode TEXT, w INTEGER,
                                 workflow TEXT, goal TEXT, seal_rid TEXT, source TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS tasks_closed ON tasks(closed_at);
CREATE TABLE IF NOT EXISTS entries(rid TEXT PRIMARY KEY, key TEXT, seq INTEGER, kind TEXT NOT NULL,
                                   ts TEXT NOT NULL, actor TEXT, by TEXT, runtime TEXT, status TEXT,
                                   superseded INTEGER NOT NULL DEFAULT 0, text TEXT NOT NULL, json TEXT NOT NULL,
                                   package TEXT, line INTEGER, origin TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS entries_key ON entries(key, seq);
CREATE INDEX IF NOT EXISTS entries_kind_ts ON entries(kind, ts);
CREATE INDEX IF NOT EXISTS entries_by_ts ON entries(by, ts);
CREATE INDEX IF NOT EXISTS entries_package ON entries(package);
CREATE TABLE IF NOT EXISTS entry_files(rid TEXT NOT NULL REFERENCES entries(rid) ON DELETE CASCADE,
                                       path TEXT NOT NULL, own INTEGER NOT NULL, PRIMARY KEY(rid, path));
CREATE INDEX IF NOT EXISTS entry_files_path ON entry_files(path);
CREATE TABLE IF NOT EXISTS conflicts(key TEXT, rid_a TEXT, rid_b TEXT, reason TEXT,
                                     PRIMARY KEY(key, rid_a, rid_b));
"""
FTS_DDL = ("CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(text, content='entries', "
           "content_rowid='rowid', tokenize='unicode61 remove_diacritics 0')")
LEGACY_FILES = ("events.jsonl", "task.md", "questions.md", "state.json")


def fts5_available():
    """FTS5, detected on :memory:; AI_MEMORY_NO_FTS=1 turns it off for tests."""
    if os.environ.get("AI_MEMORY_NO_FTS"):
        return False
    import sqlite3  # pylint: disable=import-outside-toplevel
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        con.close()
        return True
    except sqlite3.Error:
        return False


def mark_stale(root):
    """B5 failed: the next read refreshes the index or falls back to files."""
    import sqlite3  # pylint: disable=import-outside-toplevel
    path = os.path.join(root, INDEX_REL)
    if os.path.exists(path):
        con = sqlite3.connect(path, timeout=1)
        try:
            con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('stale', '1')")
            con.commit()
        finally:
            con.close()


def source_signature(root, rels):
    """(size, mtime_ns) of the files one source reads, as one string."""
    parts = []
    for rel in rels:
        try:
            st = os.stat(os.path.join(root, rel))
            parts.append("%s:%d:%d" % (rel, st.st_size, st.st_mtime_ns))
        except OSError:
            parts.append("%s:-" % rel)
    return "|".join(parts)


class SqliteHistory(History):
    """The derived index, refreshed from the sources on every open and never
    the only copy of anything. Any error is the caller's cue to fall back."""

    def __init__(self, root, cfg=None):
        super().__init__(root, cfg)
        self.path = os.path.join(root, INDEX_REL)
        self.fts = fts5_available()

    def index_name(self):
        return "sqlite"

    def source(self):
        out = super().source()
        out["fts5"] = self.fts
        return out

    def connect(self):
        import sqlite3  # pylint: disable=import-outside-toplevel
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        busy = int(os.environ.get("AI_MEMORY_BUSY_MS", "5000"))
        con = sqlite3.connect(self.path, timeout=busy / 1000.0, isolation_level=None)
        con.execute("PRAGMA busy_timeout=%d" % busy)
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, USER_VERSION):
            con.close()                   # a newer or older layout: rebuild from the sources
            os.remove(self.path)
            return self.connect()
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        if version == 0:
            con.executescript(DDL)
            con.execute("PRAGMA user_version=%d" % USER_VERSION)
        has_fts = bool(con.execute("SELECT 1 FROM sqlite_master WHERE name='entries_fts'").fetchone())
        if self.fts and not has_fts:
            con.execute(FTS_DDL)
            con.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        return con

    def rebuild(self):
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.path + suffix):
                os.remove(self.path + suffix)
        return self.refresh()

    def sources(self):
        """{source key: (origin, signature, name)} for everything FileHistory reads."""
        out = {}
        for name in package_files(self.root):
            out["memory/" + name] = ("package", source_signature(self.root, [os.path.join(".ai", "memory", name)]),
                                     name)
        for name in legacy_names(self.root):
            rels = [os.path.join(".ai", "reports", name, f) for f in LEGACY_FILES]
            out["legacy/" + name] = ("legacy", source_signature(self.root, rels), name)
        rel = os.path.join(".ai", "project", "known-risks.md")
        if os.path.exists(os.path.join(self.root, rel)):
            out["risks/known-risks.md"] = ("risks", source_signature(self.root, [rel]), rel)
        return out

    def load_source(self, origin, name):
        if origin == "package":
            with open(os.path.join(self.root, ".ai", "memory", name), "rb") as fh:
                _, entries, _ = mf.parse_package(fh.read(), name)
            return [mf.strip_private(e) for e in entries]
        if origin == "legacy":
            excerpt_max = getattr(self.cfg, "excerpt_max_bytes", 1024) if self.cfg is not None else 1024
            return legacy_dir_entries(mc.FsReader(self.root), name, excerpt_max)
        return risk_entries_from_md(read_text(os.path.join(self.root, name)) or "")

    def refresh(self):
        """Import what changed since the last call, in one BEGIN IMMEDIATE. A
        source that disappeared rebuilds: its rids may be another's too."""
        con = self.connect()
        try:
            known = {row[0]: row[1] for row in con.execute("SELECT path, sha256 FROM packages")}
            current = self.sources()
            if set(known) - set(current):
                con.close()
                return self.rebuild()
            changed = [k for k in sorted(current) if known.get(k) != current[k][1]]
            if not changed:
                return 0
            con.execute("BEGIN IMMEDIATE")
            for key in changed:
                self._import(con, key, *current[key])
            con.execute("INSERT OR REPLACE INTO meta VALUES('stale', '0')")
            con.execute("INSERT OR REPLACE INTO meta VALUES('fts5', ?)", ("1" if self.fts else "0",))
            con.execute("INSERT OR REPLACE INTO meta VALUES('keep_rules', ?)", (str(mf.KEEP_VERSION),))
            con.execute("COMMIT")
            return len(changed)
        finally:
            con.close()

    def _import(self, con, key, origin, signature, name):
        if self.fts:
            con.execute("INSERT INTO entries_fts(entries_fts, rowid, text) SELECT 'delete', rowid, text "
                        "FROM entries WHERE package=?", (key,))
        con.execute("DELETE FROM entries WHERE package=?", (key,))
        entries = self.load_source(origin, name)
        for line, e in enumerate(entries, 1):
            cur = con.execute(
                "INSERT OR IGNORE INTO entries(rid, key, seq, kind, ts, actor, by, runtime, status, text, json, "
                "package, line, origin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (e["rid"], mf.key_of(e), e.get("seq"), e.get("kind"), e.get("ts") or "", e.get("actor"),
                 e.get("by"), e.get("runtime"), e.get("status") or e.get("decision") or e.get("result"),
                 mf.search_text(e), mf.canonical(e).decode("utf-8"), key, line, origin))
            if not cur.rowcount:
                continue
            if self.fts:
                con.execute("INSERT INTO entries_fts(rowid, text) SELECT rowid, text FROM entries WHERE rid=?",
                            (e["rid"],))
            for path in mf.own_paths(e):
                con.execute("INSERT OR IGNORE INTO entry_files(rid, path, own) VALUES(?,?,1)", (e["rid"], path))
            if e.get("kind") == "task":
                con.execute("INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (mf.key_of(e), e.get("task"), e.get("inst"), e.get("started_at"), e.get("closed_at"),
                             e.get("result"), e.get("mode"), e.get("w"), e.get("workflow"), e.get("goal"),
                             e["rid"], origin))
        parts = mf.parse_package_name(name) if origin == "package" else None
        con.execute("INSERT OR REPLACE INTO packages VALUES(?,?,?,?,?,?,?)",
                    (key, 0, 0, signature, (parts or {}).get("author"), (parts or {}).get("period"), len(entries)))

    def load(self):
        self.refresh()
        con = self.connect()
        try:
            rows = con.execute("SELECT origin, json FROM entries").fetchall()
            n_packages = con.execute("SELECT COUNT(*) FROM packages WHERE path LIKE 'memory/%'").fetchone()[0]
        finally:
            con.close()
        by_origin = {"package": [], "legacy": [], "risks": []}
        for origin, text in rows:
            by_origin[origin].append(json.loads(text))
        sealed = {e.get("task") for e in by_origin["package"] if e.get("kind") == "task"}
        in_flight = current_task(self.root)
        legacy = [e for e in by_origin["legacy"] if e.get("task") not in sealed and e.get("task") != in_flight]
        rids = {e["rid"] for e in by_origin["package"]}
        entries = by_origin["package"] + legacy + [e for e in by_origin["risks"] if e["rid"] not in rids]
        entries += live_risks(self.root)
        return {"entries": entries, "errors": [], "packages": n_packages,
                "legacy": len({e.get("task") for e in legacy}),
                "legacy_keys": sorted({mf.key_of(e) for e in legacy if e.get("kind") == "task"}),
                "known_risks": len(by_origin["risks"])}

    def candidates(self, tokens, filters):
        """FTS5 only narrows, on ASCII prefix tokens; the Python matcher decides."""
        del filters
        if not self.fts or not tokens or not all(re.match(r"^[a-z0-9]+$", t) for t in tokens):
            return self.all_entries()
        con = self.connect()
        try:
            rids = {r[0] for r in con.execute(
                "SELECT e.rid FROM entries_fts JOIN entries e ON e.rowid = entries_fts.rowid "
                "WHERE entries_fts MATCH ?", (" AND ".join('"%s"*' % t for t in tokens),))}
        finally:
            con.close()
        live = {e["rid"] for e in live_risks(self.root)}
        return [e for e in self.all_entries() if e["rid"] in rids or e["rid"] in live]
