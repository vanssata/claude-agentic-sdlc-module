"""Packages mode: configuration, export at close, verification, the pre-push
validator's checks, the git hook, migration, cleanup, restore, redaction and
pack (spec compact-project-memory §D4–§D6, §D9–§D13, §I4–§I6).

Files mode (no .ai/policies/memory.json, or mode "files") never reaches the
writers here: no .ai/memory/, no .ai/local/memory/, no hook (R15). state.py
is the only caller of the writers; the path guard refuses an agent's direct
write to either directory (R19). Nothing here reads a package to grant or
refuse anything.
"""
import collections
import contextlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:                       # not POSIX: last writer wins within one clone (docs/local-memory.md)
    fcntl = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_compact as mc  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
from memory_compact import FsReader  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import

POLICY_REL = os.path.join(".ai", "policies", "memory.json")
MEMORY_REL = os.path.join(".ai", "memory")
LOCAL_REL = os.path.join(".ai", "local", "memory")
SCHEMA = 1
DEFAULTS = {"schema": 1, "mode": "files", "period": "quarter", "package_max_bytes": 1048576, "cleanup": False,
            "excerpt_max_bytes": 1024, "keep_rules": 1, "recall": {"budget_tokens": 1500, "max_items": 40}}
PENDING_MAX = 5
BATCH_CHARS = "0123456789abcdefghjkmnpqrstvwxyz"
HOOK_MARKER = "# riskrails-memory-pre-push 1"
VALIDATOR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hooks",
                                          "memory-pre-push.py"))
SELF = os.path.abspath(__file__)            # the fallback validator: this module, run as a script
FINDINGS_MAX = 40
ZERO_SHA = "0" * 40


class MemoryError_(Exception):            # pylint: disable=invalid-name  # not the builtin MemoryError
    """A refusal with its exit code (§I4: 1 findings, 2 usage, 3 aborted, 5 human, 6 scope)."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def crash(point):
    """Fault injection (A9): AI_MEMORY_CRASH_AT=B2..B6 ends the process here."""
    if os.environ.get("AI_MEMORY_CRASH_AT") == point:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(70)                      # pylint: disable=protected-access  # a crash, not an exit


# ------------------------------------------------------------------ configuration (§D11, §I6)
def author_slug(name):
    slug = re.sub(r"[^a-z0-9-]+", "-", (name or "").casefold()).strip("-")[:32].strip("-")
    return slug if slug and mf.AUTHOR_RE.match(slug) else "unknown"


class MemoryConfig:
    """The project policy (.ai/policies/memory.json) and the developer's own
    choices (.ai/local/memory/config.json)."""

    def __init__(self, root, policy, local, present):
        self.root, self.policy, self.local, self.present = root, policy, local, present

    def __getattr__(self, name):
        if name in ("mode", "period", "package_max_bytes", "cleanup", "excerpt_max_bytes", "keep_rules"):
            return self.policy.get(name, DEFAULTS[name])
        raise AttributeError(name)

    @property
    def recall_budget(self):
        return int((self.policy.get("recall") or {}).get("budget_tokens", 1500))

    @property
    def recall_max_items(self):
        return int((self.policy.get("recall") or {}).get("max_items", 40))

    @property
    def author(self):
        return self.local.get("author") or author_slug(os.environ.get("USER") or os.environ.get("USERNAME"))

    @property
    def index(self):
        return self.local.get("index") or "none"

    @property
    def packages(self):
        return self.mode == "packages"


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_config(root):
    path = os.path.join(root, POLICY_REL)
    present = os.path.exists(path)
    policy = dict(DEFAULTS)
    if present:
        try:
            loaded = read_json(path)
        except (OSError, ValueError) as exc:
            raise MemoryError_("%s is not valid JSON (%s): fix it, or 'state.py memory disable'"
                               % (POLICY_REL, exc)) from exc
        if not isinstance(loaded, dict):
            raise MemoryError_("%s must be a JSON object" % POLICY_REL)
        schema = loaded.get("schema", 1)
        if isinstance(schema, int) and not isinstance(schema, bool) and schema > SCHEMA:
            raise MemoryError_("%s has schema %s; this state.py knows %d — update the plugin"
                               % (POLICY_REL, schema, SCHEMA))
        policy.update(loaded)
        check_policy(policy)
    local = {}
    with contextlib.suppress(OSError, ValueError):
        found = read_json(os.path.join(root, LOCAL_REL, "config.json"))
        if isinstance(found, dict):
            local = found
    where = os.path.join(LOCAL_REL, "config.json")
    if local.get("author") is not None and not (isinstance(local["author"], str)
                                                and mf.AUTHOR_RE.match(local["author"])):
        raise MemoryError_("%s: author %r is not a slug of [a-z0-9-]" % (where, local["author"]))
    if local.get("index", "none") not in ("none", "sqlite"):
        raise MemoryError_("%s: index takes none or sqlite" % where)
    return MemoryConfig(root, policy, local, present)


def check_policy(policy):
    """Every key of memory.json with its type (§I6): a wrong one is a refusal
    naming the key, never a traceback inside close."""
    def is_int(value, low):
        return isinstance(value, int) and not isinstance(value, bool) and value >= low
    problems = []
    if not is_int(policy.get("schema"), 1):
        problems.append("schema must be an integer (1)")
    if policy.get("mode") not in ("files", "packages"):
        problems.append('mode must be "files" or "packages"')
    if policy.get("period") not in mf.PERIODS:
        problems.append("period must be month, quarter or year")
    if not is_int(policy.get("package_max_bytes"), 1024):
        problems.append("package_max_bytes must be an integer of at least 1024")
    if not isinstance(policy.get("cleanup"), bool):
        problems.append("cleanup must be true or false")
    if not is_int(policy.get("excerpt_max_bytes"), 0):
        problems.append("excerpt_max_bytes must be an integer >= 0")
    if policy.get("keep_rules") != 1:
        problems.append("keep_rules must be 1")
    recall = policy.get("recall")
    if not (isinstance(recall, dict) and is_int(recall.get("budget_tokens", 1500), 1)
            and is_int(recall.get("max_items", 40), 1)):
        problems.append('recall must be {"budget_tokens": N, "max_items": N}')
    if problems:
        raise MemoryError_("%s: %s" % (POLICY_REL, "; ".join(problems)))


def mode_of(root):
    """'files' or 'packages' without raising: close must archive whatever happens."""
    try:
        return load_config(root).mode
    except MemoryError_:
        return "files"


# ------------------------------------------------------------------ small I/O
def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


@contextlib.contextmanager
def locked(root):
    """flock on .ai/local/memory/lock: two closes in one clone serialise here."""
    os.makedirs(os.path.join(root, LOCAL_REL), exist_ok=True)
    fd = os.open(os.path.join(root, LOCAL_REL, "lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def git(root, *args, stdin=None, binary=False):
    done = subprocess.run(["git", "-C", root, *args], input=stdin, capture_output=True, check=False,
                          text=not binary)
    return done.returncode, done.stdout, done.stderr


def current_branch(root):
    code, out, _ = git(root, "symbolic-ref", "--short", "-q", "HEAD")
    if code == 0 and out.strip():
        return out.strip()
    code, out, _ = git(root, "rev-parse", "--short=8", "HEAD")
    return "HEAD@%s" % (out.strip() if code == 0 and out.strip() else "unborn")


def memory_dir(root):
    return os.path.join(root, MEMORY_REL)


def local_path(root, *parts):
    return os.path.join(root, LOCAL_REL, *parts)


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


# ------------------------------------------------------------------ packages on disk
def load_packages(root):
    """{name: (header, entries, errors)} for every package in the working tree."""
    out = {}
    base = memory_dir(root)
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.endswith(".jsonl"):
            out[name] = mf.parse_package(read_bytes(os.path.join(base, name)) or b"", name)
    return out


def all_rids(packages):
    return {e["rid"] for _, entries, _ in packages.values() for e in entries}


def seals_by_key(packages):
    out = collections.defaultdict(list)
    for name, (_, entries, _) in packages.items():
        for e in entries:
            if e.get("kind") == "task":
                out[mf.key_of(e)].append((name, e))
    return out


def read_batches(root):
    with contextlib.suppress(OSError, ValueError):
        data = read_json(local_path(root, "batches.json"))
        if isinstance(data, dict) and isinstance(data.get("open"), dict):
            return data
    return {"schema": 1, "open": {}}


def write_batches(root, data):
    atomic_write(local_path(root, "batches.json"), json.dumps(data, sort_keys=True, indent=1) + "\n")


def new_batch_name(root, period, author):
    rng = random.SystemRandom()
    for _ in range(64):
        batch = "".join(rng.choice(BATCH_CHARS) for _ in range(4))
        name = mf.package_name(period, author, batch)
        if not os.path.exists(os.path.join(memory_dir(root), name)):
            return name
    raise MemoryError_("no free batch name for %s.%s" % (period, author), 3)


def open_batch(root, cfg, stamp=None):
    """The branch's open batch, reused while it is in the tree, the author's,
    of the current period and under package_max_bytes; else a new name.
    Called under the lock."""
    stamp = stamp or now()
    period = mf.period_of(stamp, cfg.period)
    branch = current_branch(root)
    books = read_batches(root)
    name = books["open"].get(branch)
    if name:
        parts = mf.parse_package_name(name)
        path = os.path.join(memory_dir(root), name)
        header = None
        data = read_bytes(path)
        if data:
            header, _, _ = mf.parse_package(data.split(b"\n", 1)[0] + b"\n", name)
        if parts and data and header and header.get("author") == cfg.author and parts["period"] == period \
                and parts["batch"] and len(data) < cfg.package_max_bytes:
            return name, branch, books
    name = new_batch_name(root, period, cfg.author)
    return name, branch, books


# ------------------------------------------------------------------ export (§D5)
def outbox_path(root, key):
    task, inst = key.rsplit("#", 1)
    return local_path(root, "outbox", "%s~%s.jsonl" % (task, inst))


def exportable(compactions):
    return [c for c in compactions if c.seal and c.seal["result"] in ("closed", "abandoned", "restarted")]


ExportResult = collections.namedtuple("ExportResult",
                                      "package added sealed coverage failures conflicts already added_by_key")


def compact_for_export(root, task_id, cfg):
    found = mc.compact_instances(FsReader(root), task_id, "close", cfg.excerpt_max_bytes)
    problems = [p for c in found for p in c.problems if "torn journal" not in p]
    if problems:
        raise MemoryError_(problems[0], 3)
    ready = exportable(found)
    if not ready:
        raise MemoryError_("%s has no closed instance to export" % task_id, 3)
    return ready


def write_outbox(root, compaction):
    key = mf.key_of(compaction.seal)
    lines = [mf.canonical(e) for e in compaction.entries + [compaction.seal]]
    atomic_write(outbox_path(root, key), b"\n".join(lines) + b"\n")
    return key


def read_outbox(root):
    base = local_path(root, "outbox")
    out = {}
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not name.endswith(".jsonl"):
            continue
        entries = []
        for raw in (read_bytes(os.path.join(base, name)) or b"").split(b"\n"):
            if raw.strip():
                with contextlib.suppress(ValueError, UnicodeDecodeError):
                    entries.append(json.loads(raw.decode("utf-8")))
        seals = [e for e in entries if e.get("kind") == "task"]
        if seals:
            out[mf.key_of(seals[-1])] = entries
    return out


def export(root, ids, cfg=None, stamp=None):
    """B2–B4 for every id (or the pending ones); returns ExportResult. A
    failure of one task keeps its outbox and is reported, never raised."""
    cfg = cfg or load_config(root)
    if not cfg.packages:
        raise MemoryError_("files mode: nothing is exported ('state.py memory enable' turns packages on)")
    failures, coverage, sealed, already, added_by_key = [], {}, [], [], {}
    if ids == "pending":
        ids = pending_ids(root, cfg)
    ids = list(ids)
    # A key with a seal in the tree is never sealed again from other sources: a
    # second compaction of changed local sources (a restarted id, a cleaned-up
    # directory) would add a degraded seal to an append-only record (R8, R9).
    # The same seal is a repair: the rids it lacks come back, nothing else (V4, V5).
    sealed_here = seals_by_key(load_packages(root))
    for task_id in ids:
        try:
            for compaction in compact_for_export(root, task_id, cfg):
                key = mf.key_of(compaction.seal)
                coverage[key] = compaction.coverage
                stored = {s["rid"] for _, s in sealed_here.get(key, [])}
                if stored and compaction.seal["rid"] not in stored:
                    already.append(key)
                    continue
                write_outbox(root, compaction)
        except MemoryError_ as exc:
            failures.append((task_id, str(exc)))
        except OSError as exc:
            failures.append((task_id, "the outbox could not be written (%s)" % exc))
    crash("B2")
    added, conflicts, name = 0, [], None
    try:
        with locked(root):
            outbox = read_outbox(root)    # under the lock: another close may have taken it
            packages = load_packages(root)
            have = all_rids(packages)
            seals = seals_by_key(packages)
            recorded = {e.get("key"): set(e.get("rids") or []) for _, entries, _ in packages.values()
                        for e in entries if e.get("kind") == "conflict"}
            new, keep = [], {}
            for key, entries in outbox.items():
                seal_rid = [e for e in entries if e.get("kind") == "task"][-1]["rid"]
                stored = {s["rid"] for _, s in seals.get(key, [])}
                missing = [e for e in entries if e["rid"] not in have]
                if (stored and seal_rid not in stored) or not missing:
                    # Sealed meanwhile from other sources, or nothing lacking (a re-run, B4).
                    os.remove(outbox_path(root, key))
                    if key not in already:
                        already.append(key)
                    continue
                new += missing
                added_by_key[key] = len(missing)
                keep[key] = entries
            for key in coverage:
                if key in seals and key not in keep and key not in already:
                    already.append(key)   # another close took this outbox and sealed it (review L3)
            for key, found in sorted(seals.items()):
                # Two seals that arrived by a merge (one id closed in two clones):
                # recorded side by side, never merged (R9).
                rids = sorted({s["rid"] for _, s in found} - {s.get("supersedes") for _, s in found})
                if len(rids) < 2 or key.rsplit("#", 1)[0] not in ids or set(rids) <= recorded.get(key, set()):
                    continue
                seal = found[-1][1]
                conflict = mf.with_rid({
                    "v": mf.FORMAT, "task": seal["task"], "inst": seal["inst"], "seq": seal["seq"] + 1,
                    "kind": "conflict", "ts": max(s["ts"] for _, s in found), "actor": "agent", "by": None,
                    "runtime": seal["runtime"], "src": ["export"], "key": key, "rids": rids,
                    "reason": "two different seals for one key — kept side by side, never merged"})
                if conflict["rid"] not in have:
                    new.append(conflict)
                conflicts.append(key)
            if not new:
                return ExportResult(None, 0, sealed, coverage, failures, conflicts, already, added_by_key)
            name, branch, books = open_batch(root, cfg, stamp)
            path = os.path.join(memory_dir(root), name)
            header, current, _ = packages.get(name, (None, [], []))
            parts = mf.parse_package_name(name)
            header = header or mf.package_header(parts["period"], cfg.author, parts["batch"], stamp or now())
            current = [mf.strip_private(e) for e in current]
            outbox = keep
            if new:
                data = mf.render_package(header, current + new)
                crash("B3")
                atomic_write(path, data)
                added = len(new)
                books["open"][branch] = name
                write_batches(root, books)
            crash("B4")
            check = load_packages(root)
            present = all_rids(check)
            for key, entries in outbox.items():
                seal = [e for e in entries if e.get("kind") == "task"][-1]
                if all(e["rid"] in present for e in entries):
                    os.remove(outbox_path(root, key))
                    sealed.append(key)
                else:
                    failures.append((seal["task"], "read-back found %d of %d entries" % (
                        sum(e["rid"] in present for e in entries), len(entries))))
    except OSError as exc:
        failures.append((",".join(sorted(coverage)) or "the outbox",
                         "%s (%s)" % (exc.strerror or exc, getattr(exc, "filename", ""))))
    if added and cfg.index == "sqlite":
        crash("B5")
        index_import(root, cfg)
    return ExportResult(name, added, sealed, coverage, failures, conflicts, already, added_by_key)


def record_lines(result):
    """What close and `memory export` print: each key newly sealed with what it
    added, each key that was already sealed, each conflict recorded (review L5)."""
    out = []
    for key in result.sealed:
        cov = result.coverage.get(key) or {}
        out.append("record: %s (+%d entries, %s sealed, coverage %s/%s lines)" % (
            os.path.join(MEMORY_REL, result.package or "-"), result.added_by_key.get(key, 0),
            key.rsplit("#", 1)[0], cov.get("accounted", "?"), cov.get("lines", "?")))
    for key in result.already:
        out.append("record: %s already sealed in %s — nothing added" % (key, MEMORY_REL))
    for key in result.conflicts:
        out.append("conflict: %s has two different seals — recorded side by side, never merged "
                   "('state.py memory show %s')" % (key, key.rsplit("#", 1)[0]))
    return out


def index_import(root, cfg):
    """B5: the index learns the new package; any failure marks it stale."""
    try:
        import memory_store  # pylint: disable=import-outside-toplevel
        memory_store.SqliteHistory(root, cfg).refresh()
    except Exception:  # pylint: disable=broad-except  # a stale index is rebuilt by the next read
        with contextlib.suppress(Exception):
            import memory_store  # pylint: disable=import-outside-toplevel
            memory_store.mark_stale(root)


def sealed_task_ids(packages):
    return {e.get("task") for _, entries, _ in packages.values() for e in entries if e.get("kind") == "task"}


def pending_ids(root, cfg=None):
    """Closed new-shape tasks (and anything in the outbox) without a seal:
    B1 left them closed but not exported. Legacy ids wait for the migration."""
    sealed = sealed_task_ids(load_packages(root))
    found = set(k.rsplit("#", 1)[0] for k in read_outbox(root))
    logs = os.path.join(root, ".ai", "state", "logs")
    for name in os.listdir(logs) if os.path.isdir(logs) else []:
        if not mf.NEW_ID_RE.match(name) or name in sealed:
            continue
        with contextlib.suppress(OSError, ValueError):
            state = read_json(os.path.join(logs, name, "state.json"))
            if state.get("result") in ("closed", "abandoned"):
                found.add(name)
    del cfg
    return sorted(found - sealed)


def after_close(root, task_id, out=print):
    """The one call close makes after archive_v7. Packages mode only; every
    failure is one printed line and close still exits 0 (B4)."""
    try:
        cfg = load_config(root)
    except MemoryError_ as exc:
        out("memory: %s — the task is closed in files mode" % exc)
        return None
    if not cfg.packages:
        return None
    try:
        pending = [t for t in pending_ids(root, cfg) if t != task_id][:PENDING_MAX]
        result = export(root, [task_id] + pending, cfg)
    except (MemoryError_, ValueError, OSError) as exc:
        out("memory: export of %s failed (%s) — the task is closed; 'state.py memory export %s' retries"
            % (task_id, exc, task_id))
        return None
    for failed, why in result.failures:
        out("memory: export of %s failed (%s) — the task is closed; 'state.py memory export %s' retries"
            % (failed, why, failed))
    for line in record_lines(result):
        out(line)
    if cfg.cleanup and any(k.rsplit("#", 1)[0] == task_id for k in result.sealed + result.already):
        crash("B6")
        try:
            done = cleanup_task(root, task_id, cfg)
            out("cleanup: %s" % done)
        except MemoryError_ as exc:
            out("cleanup: %s kept in .ai/reports/ (%s)" % (task_id, exc))
    return result


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
    for name, (_, _, errors) in sorted(packages.items()):
        if changed is not None and name not in changed:
            continue
        for line, what in errors:
            findings.append(Finding("V1", os.path.join(MEMORY_REL, name), line, what,
                                    "restore the line from git ('git checkout -- %s') or 'state.py memory verify'"
                                    % os.path.join(MEMORY_REL, name)))
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
                findings.append(Finding("V3", os.path.join(MEMORY_REL, unique[live[0]][0]), None,
                                        "%s has %d seals not chained by supersedes" % (key, len(live)),
                                        "'state.py memory export %s' records the two as a conflict" % task))
            elif not recorded:
                findings.append(Finding("V3", os.path.join(MEMORY_REL, unique[live[0]][0]), None,
                                        "legacy %s has %d seals and no conflict entry" % (key, len(live)),
                                        "'state.py memory export %s' records the conflict" % task))
        rids = {e["rid"] for _, e in items if e.get("kind") not in ("task", "conflict", "redaction")}
        if len(live) > 1:
            continue                      # a recorded conflict: which entries are whose is not knowable
        for rid in live:
            name, seal = unique[rid]
            own = sorted({redacted.get(r, r) for r in rids if _belongs(items, r, seal)})
            if len(own) != seal.get("entries") or mf.seal_digest(own) != seal.get("digest"):
                findings.append(Finding("V4", os.path.join(MEMORY_REL, name), seal.get("_line"),
                                        "%s: the seal names %s entries (%s), the package has %d" % (
                                            key, seal.get("entries"), (seal.get("digest") or "")[:19], len(own)),
                                        "'state.py memory export %s' re-exports it" % seal.get("task")))
    for name, size in sorted(sizes.items()):
        if size > 2 * max_bytes:
            findings.append(Finding("V8", os.path.join(MEMORY_REL, name), None,
                                    "%d bytes, over twice package_max_bytes (%d)" % (size, max_bytes),
                                    "a new batch opens on the next close; 'state.py memory pack' folds old ones"))
        elif size > max_bytes:
            findings.append(Finding("V8-warn", os.path.join(MEMORY_REL, name), None,
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
    seals = seals_by_key(packages)
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
    cfg = load_config(root)
    packages = load_packages(root)
    sizes = {n: os.path.getsize(os.path.join(memory_dir(root), n)) for n in packages}
    findings = check_packages(packages, cfg.package_max_bytes, sizes)
    reports = os.path.join(root, ".ai", "reports")
    paths = []
    for name in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        if ids and name not in ids:
            continue
        if os.path.exists(os.path.join(reports, name, "events.jsonl")):
            paths.append(".ai/reports/%s/events.jsonl" % name)
    findings += check_journals(lambda rel: read_bytes(os.path.join(root, rel)), paths, packages, False)
    if ids:
        findings = [f for f in findings if any(i in (f.path or "") or i in f.what for i in ids)]
    del scope
    return findings


def verify_fresh_clone(root):
    """§D6: a local clone of HEAD, rebuilt from packages alone, shows every
    sealed key as this clone does."""
    import memory_store  # pylint: disable=import-outside-toplevel
    findings = []
    here = memory_store.FileHistory(root, load_config(root))
    keys = sorted({mf.key_of(e) for _, entries, _ in load_packages(root).values() for e in entries
                   if e.get("kind") == "task"})
    with tempfile.TemporaryDirectory(prefix="ai-memory-clone-") as tmp:
        clone = os.path.join(tmp, "clone")
        code, _, err = git(root, "clone", "-q", "--no-hardlinks", root, clone)
        if code != 0:
            raise MemoryError_("git clone failed: %s" % err.strip(), 3)
        there = memory_store.FileHistory(clone, load_config(clone))
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


# ------------------------------------------------------------------ status, show
def hook_state(root):
    code, out, _ = git(root, "config", "--get", "core.hooksPath")
    if code == 0 and out.strip():
        return "hookspath"
    path = hooks_path(root)
    if not path:
        return "absent"
    hook = os.path.join(path, "pre-push")
    text = read_bytes(hook)
    if text is None:
        return "absent"
    if HOOK_MARKER.encode() in text:
        decoded = text.decode("utf-8", "replace")
        if not any(os.path.isfile(p) for p in shim_paths(decoded)):
            return "installed, validator missing — pushes are NOT checked ('state.py memory enable' rewrites it)"
        return "current" if decoded == shim_text() else "installed (stale)"
    return "foreign"


def status_lines(root):
    cfg = load_config(root)
    packages = load_packages(root)
    size = sum(os.path.getsize(os.path.join(memory_dir(root), n)) for n in packages)
    books = read_batches(root)
    branch = current_branch(root)
    pending = pending_ids(root, cfg) if cfg.packages else []
    legacy = unmigrated(root, packages)
    lines = ["mode: %s%s" % (cfg.mode, "" if cfg.present else " (no %s)" % POLICY_REL),
             "period: %s · author: %s · index: %s%s" % (cfg.period, cfg.author, cfg.index, fts_line(cfg)),
             "open batch: %s" % (books["open"].get(branch) or "none") + " (branch %s)" % branch,
             "packages: %d · %s bytes" % (len(packages), mf.fmt_n(size)),
             "closed, not exported: %s" % (", ".join(pending) if pending else "none"),
             "legacy, not migrated: %d%s" % (len(legacy), " — state.py memory migrate --report" if legacy else ""),
             "pre-push: %s" % hook_state(root), "cleanup: %s" % ("on" if cfg.cleanup else "off")]
    return lines


def fts_line(cfg):
    if cfg.index != "sqlite":
        return ""
    import memory_store  # pylint: disable=import-outside-toplevel
    if memory_store.fts5_available():
        return " · fts5: yes"
    import sqlite3  # pylint: disable=import-outside-toplevel
    return " · FTS5 unavailable in this SQLite %s: search scans; results identical, slower" % sqlite3.sqlite_version


def unmigrated(root, packages):
    sealed = sealed_task_ids(packages)
    reports = os.path.join(root, ".ai", "reports")
    out = []
    for name in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        path = os.path.join(reports, name, "events.jsonl")
        if mf.LEGACY_ID_RE.match(name) and name not in sealed and b'"task_closed"' in (read_bytes(path) or b""):
            out.append(name)
    return out


def show(root, task_id, fmt="md", rid=None):
    import memory_store  # pylint: disable=import-outside-toplevel
    cfg = load_config(root)
    history = memory_store.open_history(root, cfg)
    if rid:
        found = [e for e in history.all_entries() if e.get("rid") == rid]
        if not found:
            raise MemoryError_("no entry %s" % rid, 1)
        return [mf.canonical(found[0]).decode("utf-8")]
    if task_id == memory_store.current_task(root):
        found = mc.compact_instances(FsReader(root), task_id, "tracked", cfg.excerpt_max_bytes)
        entries = [e for c in found for e in c.entries]
        lines = ["# %s — in flight — live state ('state.py status' is the authority)" % task_id, ""]
        return lines + mf.render_task_md(entries)[1:] if fmt == "md" else \
            [mf.canonical(e).decode("utf-8") for e in entries]
    entries = history.entries(task_id)
    if not entries:
        raise MemoryError_("nothing recorded for %s" % task_id, 1)
    if fmt == "json":
        return [mf.canonical(e).decode("utf-8") for e in entries]
    out = []
    for inst in sorted({e.get("inst") for e in entries}):
        out += mf.render_task_md([e for e in entries if e.get("inst") == inst])
    return out


# ------------------------------------------------------------------ risks (§D9)
def risk_add_files(root, title, where, label, what, likely, fix, status, found):
    """Files mode: append the template section (plus Label) to known-risks.md."""
    import memory_compact  # pylint: disable=import-outside-toplevel,reimported
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = read_bytes(path)
    text = text.decode("utf-8") if text is not None else "# Known risks\n"
    risks, _ = memory_compact.parse_known_risks(text)
    rkey = memory_compact.rkey_of(title)
    if any(r["rkey"] == rkey for r in risks):
        raise MemoryError_("a risk titled %r is already recorded (%s)" % (title, rkey), 2)
    section = memory_compact.risk_section(title, where, label, what, likely, fix, status, found)
    body = text.rstrip("\n") + "\n\n" + "\n".join(section) + "\n"
    atomic_write(path, body)
    return rkey


def risk_close_files(root, rkey, status, why):
    import memory_compact  # pylint: disable=import-outside-toplevel,reimported
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = (read_bytes(path) or b"").decode("utf-8")
    risks, leftovers = memory_compact.parse_known_risks(text)
    hit = [r for r in risks if r["rkey"] == rkey]
    if not hit:
        raise MemoryError_("no risk %s in known-risks.md ('state.py memory risks --status all')" % rkey, 1)
    lines = hit[0]["text"].split("\n")
    for i, line in enumerate(lines):
        if line.startswith("- **Status**:"):
            lines[i] = "- **Status**: %s — %s" % (status, why)
            break
    else:
        lines.append("- **Status**: %s — %s" % (status, why))
    hit[0]["text"] = "\n".join(lines)
    atomic_write(path, memory_compact.render_known_risks(risks, leftovers))


def risk_data(title, where, label, what, likely, fix, status, why=None, supersedes=None, by=None):
    data = {"rkey": mc.rkey_of(title), "title": title, "where": where, "label": label, "what": what,
            "likelihood": likely, "fix": fix, "status": status, "status_why": why, "supersedes": supersedes}
    if by:
        data["by"] = by
    return data


def standalone_risk(root, cfg, data, runtime="unknown", by=None):
    """A risk with no task in flight: one entry, straight into the open batch."""
    entry = {"v": mf.FORMAT, "task": None, "inst": 1, "seq": 0, "kind": "risk", "ts": now(), "actor": "agent",
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
    with locked(root):
        name, branch, books = open_batch(root, cfg)
        packages = load_packages(root)
        have = all_rids(packages)
        header, current, _ = packages.get(name, (None, [], []))
        parts = mf.parse_package_name(name)
        header = header or mf.package_header(parts["period"], cfg.author, parts["batch"], now())
        new = [e for e in entries if e["rid"] not in have]
        if new:
            atomic_write(os.path.join(memory_dir(root), name),
                         mf.render_package(header, [mf.strip_private(e) for e in current] + new))
            books["open"][branch] = name
            write_batches(root, books)
    return name


# ------------------------------------------------------------------ git trees (§D10)
class GitTreeReader:
    """Blobs of one commit, through one `git cat-file --batch`."""

    def __init__(self, repo, sha):
        self.repo, self.sha = repo, sha
        self._cache = {}
        self._paths = None

    def paths(self):
        if self._paths is None:
            code, out, _ = git(self.repo, "ls-tree", "-r", "-z", "--name-only", self.sha, binary=True)
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
    code, out, _ = git(repo, "rev-parse", "--verify", "-q", name + "^{commit}")
    return out.strip() if code == 0 and out.strip() else None


def policy_at(repo, sha):
    code, out, _ = git(repo, "show", "%s:%s" % (sha, POLICY_REL.replace(os.sep, "/")))
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
        return [Finding("V1", POLICY_REL, None, "memory.json at %s is not valid JSON" % new[:9],
                        "fix the file, or 'state.py memory disable'")], {}
    max_bytes = int(policy.get("package_max_bytes", DEFAULTS["package_max_bytes"]))
    tree = GitTreeReader(repo, new)
    paths = tree.paths()
    pkg_paths = [p for p in paths if p.startswith(".ai/memory/") and p.endswith(".jsonl")]
    blobs = tree.read_many(pkg_paths)
    packages = {p.split("/", 2)[2]: mf.parse_package(blobs[p] or b"", p.split("/", 2)[2]) for p in pkg_paths}
    sizes = {p.split("/", 2)[2]: len(blobs[p] or b"") for p in pkg_paths}
    changed, added = None, []
    findings = []
    if old:
        code, out, _ = git(repo, "diff", "--name-status", "--no-renames", old, new, "--", ".ai")
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
        new_rids = all_rids(packages)
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
        outbox = local_path(repo, "outbox")
        if os.path.isdir(outbox) and any(n.endswith(".jsonl") for n in os.listdir(outbox)):
            findings.append(Finding("V9", os.path.join(LOCAL_REL, "outbox"), None, "an export is pending",
                                    "state.py memory export --pending, commit, push again"))
    stats = {"packages": len(packages), "tasks": len(journals), "ms": int((time.time() - started) * 1000)}
    return findings, stats


# ------------------------------------------------------------------ the git hook (R17, §D10)
def hooks_path(root):
    code, out, _ = git(root, "rev-parse", "--git-path", "hooks")
    if code != 0 or not out.strip():
        return None
    path = out.strip()
    return path if os.path.isabs(path) else os.path.join(root, path)


def shim_candidates(validator=None):
    """Where the shim looks for the validator, in order: the hook beside this
    module, the hook in either runtime home, then this module itself — a Codex
    install copies skills/ai-task/ but not every hook."""
    return [validator or VALIDATOR, "$HOME/.claude/hooks/memory-pre-push.py",
            "${CODEX_HOME:-$HOME/.codex}/hooks/memory-pre-push.py", SELF,
            "$HOME/.claude/skills/ai-task/memory_sync.py",
            "${CODEX_HOME:-$HOME/.codex}/skills/ai-task/memory_sync.py"]


def shim_text(validator=None):
    return ("#!/bin/sh\n%s — written by 'state.py memory enable'; 'state.py memory disable' removes it\n"
            "for v in %s; do\n"
            "  [ -f \"$v\" ] && exec python3 -I \"$v\" \"$@\"\n"
            "done\n"
            "echo \"riskrails memory: validator not found — this push is not checked\" >&2; exit 0\n"
            % (HOOK_MARKER, " ".join('"%s"' % c for c in shim_candidates(validator))))


def shim_paths(text):
    """The shim's candidates as paths on this machine."""
    match = re.search(r"^for v in (.+); do$", text, re.M)
    home = os.path.expanduser("~")
    codex = os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")
    return [c.replace("${CODEX_HOME:-$HOME/.codex}", codex).replace("$HOME", home)
            for c in re.findall(r'"([^"]+)"', match.group(1) if match else "")]


def snippet_text(validator=None):
    validator = validator or VALIDATOR
    return ("# riskrails memory: add to your own pre-push hook (stdin can be read only once)\n"
            "rr_in=$(mktemp) && cat > \"$rr_in\"\n"
            "python3 -I \"%s\" \"$@\" < \"$rr_in\" || { rr=$?; rm -f \"$rr_in\"; exit $rr; }\n"
            "# … then your hook, reading \"$rr_in\" where it read stdin …\n"
            "rm -f \"$rr_in\"\n" % validator)


def install_hook(root):
    """installed | current | foreign | hookspath (R17)."""
    code, out, _ = git(root, "config", "--get", "core.hooksPath")
    if code == 0 and out.strip():
        return "hookspath"
    path = hooks_path(root)
    if not path:
        raise MemoryError_("not a git repository: no hooks path", 2)
    hook = os.path.join(path, "pre-push")
    text = read_bytes(hook)
    if text is not None and HOOK_MARKER.encode() not in text:
        return "foreign"
    if text is not None and text.decode("utf-8", "replace") == shim_text():
        return "current"
    os.makedirs(path, exist_ok=True)
    atomic_write(hook, shim_text())
    os.chmod(hook, 0o755)
    return "installed"


def remove_hook(root):
    path = hooks_path(root)
    hook = os.path.join(path, "pre-push") if path else None
    text = read_bytes(hook) if hook else None
    if text is not None and HOOK_MARKER.encode() in text:
        os.remove(hook)
        return "removed"
    return "foreign" if text is not None else "absent"


def write_policy(root, policy):
    atomic_write(os.path.join(root, POLICY_REL), json.dumps(policy, indent=2, ensure_ascii=False) + "\n")


def enable(root, author=None, period=None, index=None):
    cfg = load_config(root)
    policy = dict(DEFAULTS)
    policy.update(cfg.policy if cfg.present else {})
    policy["mode"] = "packages"
    if period:
        if period not in mf.PERIODS:
            raise MemoryError_("--period takes one of %s" % ", ".join(mf.PERIODS))
        policy["period"] = period
    write_policy(root, policy)
    local = dict(cfg.local)
    local["schema"] = 1
    local["author"] = author_slug(author) if author else cfg.author
    if index:
        if index not in ("none", "sqlite"):
            raise MemoryError_("--index takes none or sqlite")
        local["index"] = index
    local.setdefault("index", "none")
    atomic_write(local_path(root, "config.json"), json.dumps(local, sort_keys=True) + "\n")
    return install_hook(root)


def disable(root):
    cfg = load_config(root)
    policy = dict(cfg.policy)
    policy["mode"] = "files"
    write_policy(root, policy)
    return remove_hook(root)


# ------------------------------------------------------------------ migration (§D12, R25)
def migration_plan(root):
    """What --report shows and --apply does, from HEAD's tracked files only."""
    head = rev(root, "HEAD")
    if not head:
        raise MemoryError_("migration reads HEAD: commit first", 2)
    tree = GitTreeReader(root, head)
    packages = load_packages(root)
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
    lines = ["# Migration report — %s" % now(), "", "HEAD %s; tracked files only, so every clone gives the same "
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
    text = (read_bytes(os.path.join(root, ".ai", "project", "known-risks.md")) or b"").decode("utf-8")
    risks, leftovers = mc.parse_known_risks(text)
    titles = collections.Counter(r["title"] for r in risks)
    lines += ["", "## known-risks.md", "", "- sections parsed: %d" % len(risks),
              "- lines outside a section: %d" % len(leftovers["lines"]),
              "- label derived (no Label line): %d" % sum(1 for r in risks if r["label_derived"]),
              "- renders byte for byte: %s" % ("yes" if mc.render_known_risks(risks, leftovers) == text else "NO"),
              "- duplicate titles: %s" % (", ".join(t for t, n in titles.items() if n > 1) or "none")]
    report = "\n".join(lines) + "\n"
    atomic_write(local_path(root, "migration-report.md"), report)
    return report


def backup(root):
    path = local_path(root, "backup-%s.tar" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tarfile.open(path, "w") as tar:
        for rel in (".ai/reports", ".ai/project/known-risks.md"):
            if os.path.exists(os.path.join(root, rel)):
                tar.add(os.path.join(root, rel), arcname=rel)
    return path


def migrate_apply(root, risks=False):
    """Closed legacy tasks into batches by their closed_at period; then, with
    risks, known-risks.md into risk entries and a stub."""
    cfg = load_config(root)
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
    with locked(root):
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
                name = new_batch_name(root, period, cfg.author)
                parts = mf.parse_package_name(name)
                entries = [e for c in batch for e in c.entries + [c.seal]]
                atomic_write(os.path.join(memory_dir(root), name),
                             mf.render_package(mf.package_header(period, cfg.author, parts["batch"], now()),
                                               entries))
                written += len(batch)
                out.append("package: %s (%d tasks, %d entries)" % (os.path.join(MEMORY_REL, name), len(batch),
                                                                   len(entries)))
    findings = check_packages(load_packages(root), cfg.package_max_bytes)
    out.append("migrated %d task instance(s); %d already sealed; %d incomplete (reported, not exported)"
               % (written, len(skipped), len(incomplete)))
    out += ["incomplete: %s coverage %s/%s %s" % (k, cov["accounted"], cov["lines"], "; ".join(p))
            for k, cov, p in incomplete]
    out += [format_finding(f) for f in findings]
    return out


STUB = """# Known risks

<!-- The risks live in the record since {date}: `state.py memory risks --md` renders
     them, `state.py memory risk add|close` records them (spec compact-project-memory
     §D9, OQ4). A section written here is still read, as before the migration. -->
"""


def migrate_risks(root, cfg):
    path = os.path.join(root, ".ai", "project", "known-risks.md")
    text = (read_bytes(path) or b"").decode("utf-8")
    import memory_store  # pylint: disable=import-outside-toplevel
    entries = memory_store.risk_entries_from_md(text)
    risks, leftovers = mc.parse_known_risks(text)
    rendered = mc.render_known_risks([{"text": e["text"]} for e in entries], leftovers)
    if rendered != text:
        raise MemoryError_("known-risks.md does not render byte for byte from its entries — nothing changed", 3)
    entries = [dict(e, actor="migration", src=["known-risks.md#%s" % e["rkey"]]) for e in entries]
    entries = [mf.with_rid(e) for e in entries]
    name = append_entries(root, cfg, entries)
    atomic_write(path, STUB.format(date=now()[:10]))
    del risks
    return ["risks: %d entries into %s; known-risks.md is a stub" % (len(entries), os.path.join(MEMORY_REL, name))]


def move_logs(root):
    head = rev(root, "HEAD")
    tree = GitTreeReader(root, head) if head else None
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
    listing = local_path(root, "logs-to-rm.txt")
    atomic_write(listing, "".join("%s\n" % p for p in moved))
    return moved, "git rm --cached --quiet --pathspec-from-file=%s" % os.path.relpath(listing, root)


# ------------------------------------------------------------------ cleanup, restore, redact (§D6, §D13)
def cleanup_ready(root, task_id, cfg, packages=None):
    """The R22 conditions for one task, or the first that fails."""
    packages = packages if packages is not None else load_packages(root)
    seals = [(n, e) for n, (_, entries, _) in packages.items() for e in entries
             if e.get("kind") == "task" and e.get("task") == task_id]
    if not cfg.cleanup:
        return "cleanup is off in %s" % POLICY_REL
    if not seals:
        return "no seal for %s in a package in the working tree" % task_id
    findings = check_packages({n: packages[n] for n, _ in seals}, cfg.package_max_bytes)
    if findings:
        return "its package does not verify (%s)" % findings[0].what
    for _, seal in seals:
        if (seal.get("counts") or {}).get("skipped"):
            return "%s has %s torn journal line(s)" % (mf.key_of(seal), seal["counts"]["skipped"])
    journal = read_bytes(os.path.join(root, ".ai", "reports", task_id, "events.jsonl"))
    if journal is not None:
        found = check_journals(lambda rel: journal if rel.endswith("events.jsonl") else None,
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
        raise MemoryError_(why, 1)
    src = os.path.join(root, ".ai", "reports", task_id)
    dest = os.path.join(root, ".ai", "state", "logs", task_id, "report")
    if not os.path.isdir(src):
        return "%s already cleaned up" % task_id
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        raise MemoryError_("%s exists: 'state.py memory restore %s' first" % (os.path.relpath(dest, root), task_id), 3)
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
            raise MemoryError_("the copy of %s does not match its source — nothing removed" % task_id, 3) \
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
            h.update(os.path.relpath(full, path).encode() + b"\0" + (read_bytes(full) or b"") + b"\0")
    return h.hexdigest()


def cleanup(root, ids):
    cfg = load_config(root)
    if not cfg.packages:
        raise MemoryError_("files mode: cleanup needs packages mode", 2)
    if not cfg.cleanup:
        raise MemoryError_("cleanup is off: set \"cleanup\": true in %s once 'memory verify --all' and "
                           "'--fresh-clone' are green (§D6)" % POLICY_REL, 2)
    findings = [f for f in verify(root) if not f.check.endswith("-warn")]
    if findings:
        raise MemoryError_("'memory verify --all' is not green: %s" % format_finding(findings[0]), 1)
    packages = load_packages(root)
    if ids == "all":
        ids = sorted(sealed_task_ids(packages) & set(os.listdir(os.path.join(root, ".ai", "reports"))))
    out = []
    for task_id in ids:
        try:
            out.append(cleanup_task(root, task_id, cfg))
        except MemoryError_ as exc:
            out.append("%s kept: %s" % (task_id, exc))
    return out


def restore(root, ids):
    import memory_store  # pylint: disable=import-outside-toplevel
    logs = os.path.join(root, ".ai", "state", "logs")
    if ids == "all":
        ids = sorted(n for n in os.listdir(logs) if os.path.isdir(os.path.join(logs, n, "report"))) \
            if os.path.isdir(logs) else []
        history = memory_store.FileHistory(root, load_config(root))
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
        history = history or memory_store.FileHistory(root, load_config(root))
        entries = history.entries(task_id)
        if not entries:
            out.append("%s: nothing recorded" % task_id)
            continue
        os.makedirs(dest)
        md = ["<!-- restored from record %s — a reconstruction, not the original task.md -->" % now()]
        md += mf.render_task_md(entries)
        atomic_write(os.path.join(dest, "task.md"), "\n".join(md) + "\n")
        lines = []
        for e in entries:
            data = {k: v for k, v in e.items() if k not in mf.ENVELOPE}
            data["restored"] = True
            data["rid"] = e["rid"]
            lines.append(json.dumps({"ts": e["ts"], "task": task_id, "event": "restored_%s" % e["kind"],
                                     "actor": e["actor"], "runtime": e["runtime"], "stage": "",
                                     "detail": "restored from record", "data": data}, ensure_ascii=False))
        atomic_write(os.path.join(dest, "events.jsonl"), "\n".join(lines) + "\n")
        out.append("%s restored from record (task.md marked, events.jsonl with data.restored)" % task_id)
    return out


def redact(root, rid, field, why, by=None):
    """The one exception to append-only (R8): the field becomes "[redacted]",
    the line gets a new rid, a redaction entry names the old one."""
    cfg = load_config(root)
    with locked(root):
        packages = load_packages(root)
        for name, (header, entries, _) in packages.items():
            hit = [e for e in entries if e["rid"] == rid]
            if not hit:
                continue
            entry = mf.strip_private(hit[0])
            if field in mf.ENVELOPE or field not in entry:
                raise MemoryError_("%s has no redactable field %r" % (rid, field), 2)
            new = dict(entry, **{field: "[redacted]"})
            new = mf.with_rid(new)
            note = mf.with_rid({"v": mf.FORMAT, "task": entry.get("task"), "inst": entry.get("inst") or 1,
                                "seq": entry.get("seq") or 0, "kind": "redaction", "ts": now(), "actor": "human",
                                "by": by, "runtime": "unknown", "src": ["state.py memory redact"],
                                "target": rid, "field": field, "why": why, "replacement": new["rid"]})
            rest = [mf.strip_private(e) for e in entries if e["rid"] != rid]
            atomic_write(os.path.join(memory_dir(root), name), mf.render_package(header, rest + [new, note]))
            del cfg
            return new["rid"], name
    raise MemoryError_("no entry %s in .ai/memory/" % rid, 1)


# ------------------------------------------------------------------ pack (§D4, R7)
def pack(root, period):
    cfg = load_config(root)
    if not re.match(r"^\d{4}(?:-\d{2}|-Q[1-4])?$", period or ""):
        raise MemoryError_("--period takes YYYY-MM, YYYY-Qn or YYYY", 2)
    grain = "quarter" if "-Q" in period else ("month" if "-" in period else "year")
    current = mf.period_of(now(), grain)
    if period >= current:
        raise MemoryError_("period %s has not ended (now %s)" % (period, current), 2)
    with locked(root):
        packages = load_packages(root)
        mine = [n for n in packages if (mf.parse_package_name(n) or {}).get("period") == period
                and (mf.parse_package_name(n) or {}).get("author") == cfg.author]
        if not mine:
            raise MemoryError_("no package of %s for %s" % (cfg.author, period), 1)
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
        header = mf.package_header(period, cfg.author, None, now())
        data = b"\n".join([mf.canonical(header)] + [mf.canonical(e) for e in ordered]) + b"\n"
        atomic_write(os.path.join(memory_dir(root), target), data)
        _, check, errors = mf.parse_package(data, target)
        if errors or {e["rid"] for e in check} != before:
            raise MemoryError_("the pack does not hold the batches' rid set — batches kept", 3)
        removed = [n for n in mine if n != target]
        for name in removed:
            os.remove(os.path.join(memory_dir(root), name))
        books = read_batches(root)
        books["open"] = {b: n for b, n in books["open"].items() if n not in removed}
        write_batches(root, books)
    return target, removed, len(before)


# ------------------------------------------------------------------ the pre-push entry (§I5)
def _git_out(repo, *args):
    code, out, _ = git(repo, *args)
    return code, out.strip()


def base_for_new_branch(repo, remote, lsha):
    """The merge-base with <remote>/HEAD, else with the nearest <remote>/* ref."""
    code, base = _git_out(repo, "merge-base", lsha, "refs/remotes/%s/HEAD" % remote)
    if code == 0 and base:
        return base
    code, refs = _git_out(repo, "for-each-ref", "--format=%(refname)", "refs/remotes/%s/" % remote)
    best, best_time = None, -1
    for ref in refs.splitlines() if code == 0 else []:
        code, base = _git_out(repo, "merge-base", lsha, ref)
        if code != 0 or not base:
            continue
        code, stamp = _git_out(repo, "show", "-s", "--format=%ct", base)
        if code == 0 and stamp.isdigit() and int(stamp) > best_time:
            best, best_time = base, int(stamp)
    return best


def pre_push(argv, stdin):
    """The validator: the hook form (<remote> <url>, refs on stdin), --range or
    --tree; prints findings to stderr and returns 0 or 1."""
    repo = os.getcwd()
    if "--repo" in argv:
        i = argv.index("--repo")
        repo = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    jobs, local = [], False
    if argv[:1] == ["--range"] and len(argv) == 2 and ".." in argv[1]:
        old, new = argv[1].split("..", 1)
        new_sha = rev(repo, new)
        if not new_sha:
            raise MemoryError_("%s is not a commit" % new, 3)
        jobs.append((argv[1], rev(repo, old), new_sha))
    elif argv[:1] == ["--tree"] and len(argv) == 2:
        sha = rev(repo, argv[1])
        if not sha:
            raise MemoryError_("%s is not a commit" % argv[1], 3)
        jobs.append((argv[1], None, sha))
    else:
        local = True
        remote = argv[0] if argv else "origin"
        for line in stdin.read().splitlines():
            parts = line.split()
            if len(parts) != 4:
                continue
            lref, lsha, _, rsha = parts
            if lsha == ZERO_SHA or lref.startswith("refs/tags/"):
                continue                  # a deletion or a tag: nothing of ours travels
            known = rsha != ZERO_SHA and _git_out(repo, "cat-file", "-e", rsha + "^{commit}")[0] == 0
            jobs.append((lref, rsha if known else base_for_new_branch(repo, remote, lsha), lsha))
    failing, shown, packages, tasks, ms = [], 0, 0, 0, 0
    for ref, old, new in jobs:
        findings, stats = validate_range(repo, old, new, local=local)
        if findings is None:
            continue                      # files mode at T: not ours to check
        for f in findings[:FINDINGS_MAX]:
            print("memory-pre-push: %s" % format_finding(f, ref), file=sys.stderr)
        if len(findings) > FINDINGS_MAX:
            print("… %d more — state.py memory verify --range %s..%s" % (
                len(findings) - FINDINGS_MAX, (old or new)[:12], new[:12]), file=sys.stderr)
        failing += [f for f in findings if not f.check.endswith("-warn")]
        shown += len(findings)
        packages += stats.get("packages", 0)
        tasks += stats.get("tasks", 0)
        ms += stats.get("ms", 0)
    if shown:
        print("checked %d packages, %d tasks in %d ms" % (packages, tasks, ms), file=sys.stderr)
    return 1 if failing else 0


def pre_push_cli(argv):
    """Exit 0, 1, or 3 when the validator itself fails — closed, with the way out."""
    try:
        return pre_push(argv, sys.stdin)
    except Exception as exc:  # pylint: disable=broad-except  # fail closed
        print("memory-pre-push: validator error: %s — run 'state.py memory verify --all'; a human may push "
              "with 'git push --no-verify'" % exc, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(pre_push_cli(sys.argv[1:]))
