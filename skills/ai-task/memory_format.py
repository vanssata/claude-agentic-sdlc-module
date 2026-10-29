"""The compact project record, format 1 — pure functions, no I/O.

Spec: docs/sdlc/specs/compact-project-memory.md §D2, §D3, §D8, §I1, §I2. The
pre-push validator, the compaction, both History backends and state.py import
this one copy, so the canonical form, the rid, the ranker and the matcher are
the same everywhere (R11).
"""
import fnmatch
import hashlib
import json
import math
import re
import unicodedata

FORMAT = 1
PKG = "riskrails-memory"
KEEP_VERSION = 1
KINDS = ("task", "weight", "override", "scope", "question", "approval", "verify", "review", "note",
         "handoff", "risk", "conflict", "redaction")
ACTORS = ("human", "agent", "hook", "migration", "unknown")
RUNTIMES = ("claude", "codex", "unknown")
LABELS = ("KNOWN FACT", "INFERENCE", "UNKNOWN", "RISK")
RISK_STATUS = ("open", "ticketed", "accepted", "fixed")
SEVERITIES = ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")
ENVELOPE = ("v", "rid", "task", "inst", "seq", "kind", "ts", "actor", "by", "runtime", "src")
REQUIRED = {
    "task": ("result", "goal", "workflow", "mode", "w", "axes", "started_at", "closed_at", "files", "steps",
             "stages", "changes", "code", "facts", "verify_runs", "counts", "people", "runtimes", "entries",
             "digest", "source", "schema", "version"),
    "weight": ("change", "w", "mode", "axes", "from", "to", "lines"),
    "override": ("what", "from", "to", "via", "why"),
    "scope": ("change", "added", "why"),
    "question": ("qid", "stage", "question", "context", "options", "recommended", "answer"),
    "approval": ("gate_id", "requested_at", "decision", "at", "via", "unattended", "tty", "note", "why",
                 "tree", "confirm", "operations"),
    "verify": ("n", "scope", "exit", "tree", "command", "duration_s", "expected_fail", "after_fix", "why",
               "excerpt", "log"),
    "review": ("pass", "tier", "focus", "verdict", "findings", "closed", "report"),
    "note": ("note_kind", "text", "why", "error"),
    "handoff": ("from", "to", "via", "reason"),
    "risk": ("rkey", "title", "where", "label", "what", "likelihood", "fix", "status", "status_why",
             "found_by", "text"),
    "conflict": ("key", "rids", "reason"),
    "redaction": ("target", "field", "why"),
}
AGENT_TEXT_MAX = 2000
LINE_MAX_BYTES = 65536
RECALL_LINE_MAX = 300
RECALL_MAX_BUDGET = 8000

# KEEP_RULES v1 (§D3): what each journal event becomes. "seal" and "summary"
# lines are summarised into the seal's arrays; "drop" lines are counted in
# counts.dropped; an event no rule names is kept as note/unknown-event.
KEEP_RULES = {1: {
    "task_started": "seal", "task_closed": "seal",
    "weight_set": "weight", "weight_raised": "weight", "tier_raised": "weight",
    "mode_set": "override", "human_set": "override",
    "plan_registered": "scope", "scope_change": "scope",
    "question_asked": "question", "question_answered": "question",
    "gate_requested": "approval", "gate_approved": "approval", "gate_rejected": "approval",
    "review_verdict": "review", "findings_closed": "review",
    "verify_run": "verify",
    "note": "note", "field_set": "note", "plan_drift": "note", "review_budget_refused": "note",
    "legacy": "note",
    "runtime_handoff": "handoff",
    "risk_recorded": "risk",
    "stage_started": "summary", "step_started": "summary", "step_done": "summary",
    "handoff_written": "drop", "schema_migrated": "drop", "model_fallback": "drop",
    "missed_reroute": "drop",
}}
DROP_PREFIXES = ("decision_", "consent_")

TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")      # state.py's, every id it accepts
LEGACY_ID_RE = re.compile(r"^T-\d{4}-\d{2}-\d{2}-\d{3}$")
NEW_ID_RE = re.compile(r"^T-\d{4}-\d{2}-\d{2}-\d{4}-(?=[a-z0-9-]{3,24}$)[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_RE = re.compile(r"^(?=.{3,24}$)[a-z0-9]+(?:-[a-z0-9]+)*$")
RID_RE = re.compile(r"^r1-[0-9a-f]{24}$")
AUTHOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
PACKAGE_RE = re.compile(r"^(?P<period>\d{4}(?:-\d{2}|-Q[1-4])?)\.(?P<author>[a-z0-9][a-z0-9-]{0,31})"
                        r"(?:\.(?P<batch>[0-9a-hjkmnp-tv-z]{4}))?\.jsonl$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
PERIODS = ("month", "quarter", "year")
GLOB_CHARS = "*?["

# A fixed table (§D2), Bulgarian first; NFKD and the [a-z0-9] filter handle the rest.
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a", "ь": "y", "ю": "yu",
    "я": "ya", "ё": "yo", "э": "e", "ы": "y", "і": "i", "ї": "yi", "є": "ye", "ґ": "g", "ў": "u",
    "ђ": "dj", "ј": "j", "љ": "lj", "њ": "nj", "ћ": "c", "џ": "dz", "ѓ": "gj", "ќ": "kj", "ѕ": "dz",
}

# The redaction set (R5, risk 11): applied to every log excerpt before it is kept.
REDACTIONS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b([a-z0-9_]*(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)[a-z0-9_]*)"
               r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
]


# ------------------------------------------------------------------ ids (§D2, R1)
def slug_of(goal):
    """Casefold, transliterate, keep [a-z0-9] words, whole words while they fit
    in 24 characters; 'task' when nothing is left."""
    text = "".join(TRANSLIT.get(ch, ch) for ch in (goal or "").casefold())
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", text)
    out = []
    for word in words:
        if len("-".join(out + [word])) > 24:
            break
        out.append(word)
    if not out and words:
        out = [words[0][:24]]
    slug = "-".join(out)
    if len(slug) < 3:
        slug = (slug + "-task") if slug else "task"
    return slug


def with_suffix(slug, n):
    """The local disambiguator, counted inside the 24 characters."""
    if n <= 1:
        return slug
    tail = "-%d" % n
    return slug[:24 - len(tail)].rstrip("-") + tail


def new_task_id(now, slug):
    """`now` is an aware UTC datetime; the id is T-YYYY-MM-DD-HHMM-<slug>."""
    if not SLUG_RE.match(slug or ""):
        raise ValueError("slug must be 3-24 characters of [a-z0-9] words joined by '-': %r" % slug)
    return "T-%s-%s" % (now.strftime("%Y-%m-%d-%H%M"), slug)


def is_task_id(task_id):
    return bool(task_id) and bool(TASK_ID_RE.match(task_id))


# ------------------------------------------------------------------ the journal rules
def classify(event, schema=None, version=KEEP_VERSION):
    """The KEEP_RULES class of one journal event type."""
    if event == "tier_set":
        # schema 7 writes a compat tier_set beside weight_set (state.py cmd_start).
        return "weight" if (schema or 0) < 7 else "summary"
    rule = KEEP_RULES[version].get(event)
    if rule:
        return rule
    if isinstance(event, str) and event.startswith(DROP_PREFIXES):
        return "drop"
    return "unknown"


# ------------------------------------------------------------------ canonical form (§D3)
def canonical(obj):
    """The one serialisation: sorted keys, no spaces, UTF-8, no trailing LF."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def make_rid(entry):
    body = {k: v for k, v in entry.items() if k != "rid"}
    return "r1-" + hashlib.sha256(canonical(body)).hexdigest()[:24]


def with_rid(entry):
    entry = dict(entry)
    entry.pop("rid", None)
    entry["rid"] = make_rid(entry)
    return entry


def seal_digest(rids):
    return "sha256:" + hashlib.sha256("\n".join(sorted(rids)).encode("utf-8")).hexdigest()


def key_of(entry):
    return "%s#%s" % (entry.get("task"), entry.get("inst"))


def cap(text, limit=AGENT_TEXT_MAX):
    """(text, cut): agent text capped at 2 000 characters (§D3)."""
    if isinstance(text, str) and len(text) > limit:
        return text[:limit], True
    return text, False


def validate(entry):
    """Every problem with one entry, as short strings; [] when it is valid."""
    if not isinstance(entry, dict):
        return ["not an object"]
    errors = ["missing %s" % k for k in ENVELOPE if k not in entry]
    if errors:
        return errors
    kind = entry["kind"]
    if entry["v"] != FORMAT:
        errors.append("v is %r, not %d" % (entry["v"], FORMAT))
    if kind not in KINDS:
        return errors + ["unknown kind %r" % kind]
    if not isinstance(entry["rid"], str) or not RID_RE.match(entry["rid"]):
        errors.append("rid %r is not r1-<24 hex>" % entry["rid"])
    elif entry["rid"] != make_rid(entry):
        errors.append("rid is not the hash of the entry")
    if entry["task"] is None:
        if kind not in ("risk", "redaction", "conflict"):
            errors.append("task is null for kind %s" % kind)
    elif not isinstance(entry["task"], str) or not TASK_ID_RE.match(entry["task"]):
        errors.append("task %r is not a task id" % entry["task"])
    if not isinstance(entry["inst"], int) or isinstance(entry["inst"], bool) or entry["inst"] < 1:
        errors.append("inst must be an integer >= 1")
    if not isinstance(entry["seq"], int) or isinstance(entry["seq"], bool) or entry["seq"] < 0:
        errors.append("seq must be an integer >= 0")
    if not isinstance(entry["ts"], str) or not TS_RE.match(entry["ts"]):
        errors.append("ts %r is not ISO-8601 UTC" % entry["ts"])
    if entry["actor"] not in ACTORS:
        errors.append("actor %r" % entry["actor"])
    if entry["by"] is not None and not isinstance(entry["by"], str):
        errors.append("by must be a string or null")
    if entry["runtime"] not in RUNTIMES:
        errors.append("runtime %r" % entry["runtime"])
    if not isinstance(entry["src"], list) or not entry["src"] or \
            not all(isinstance(s, str) for s in entry["src"]):
        errors.append("src must be a non-empty list of strings")
    for opt in ("unrecorded", "truncated"):
        if opt in entry and not (isinstance(entry[opt], list) and all(isinstance(s, str) for s in entry[opt])):
            errors.append("%s must be a list of strings" % opt)
    if "supersedes" in entry and not (isinstance(entry["supersedes"], str) and RID_RE.match(entry["supersedes"])):
        errors.append("supersedes must be a rid")
    errors += ["%s: missing %s" % (kind, k) for k in REQUIRED[kind] if k not in entry]
    if kind == "risk" and "label" in entry and entry["label"] not in LABELS:
        errors.append("risk label %r" % entry["label"])
    if kind == "risk" and "status" in entry and entry["status"] not in RISK_STATUS:
        errors.append("risk status %r" % entry["status"])
    return errors


# ------------------------------------------------------------------ packages (§D4, §I2)
def package_name(period, author, batch=None):
    name = "%s.%s.%s.jsonl" % (period, author, batch) if batch else "%s.%s.jsonl" % (period, author)
    if not PACKAGE_RE.match(name):
        raise ValueError("not a package name: %r" % name)
    return name


def parse_package_name(name):
    """{period, author, batch} or None."""
    match = PACKAGE_RE.match(name or "")
    return match.groupdict() if match else None


def package_header(period, author, batch, created):
    return {"author": author, "batch": batch, "created": created, "format": FORMAT, "period": period,
            "pkg": PKG}


def render_package(header, entries):
    """Bytes of a package: the header, then the entries by key and seq."""
    lines = [canonical(header)] + [canonical(e) for e in sort_entries(entries)]
    return b"\n".join(lines) + b"\n"


def sort_entries(entries):
    return sorted(entries, key=lambda e: (str(e.get("task")), e.get("inst") or 0, e.get("seq") or 0,
                                          e.get("rid") or ""))


def parse_package(data, name=None):
    """(header, entries, errors): errors are (line, what) pairs; a line that
    fails is left out of entries, so a reader still sees the rest."""
    errors, entries, header = [], [], None
    if isinstance(data, str):
        data = data.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        errors.append((1, "starts with a UTF-8 BOM"))
        data = data[3:]
    if data and not data.endswith(b"\n"):
        errors.append((data.count(b"\n") + 1, "no LF after the last line"))
    raw_lines = data.split(b"\n")
    if raw_lines and raw_lines[-1] == b"":
        raw_lines.pop()
    for number, raw in enumerate(raw_lines, 1):
        if raw.endswith(b"\r"):
            errors.append((number, "CRLF line ending"))
            raw = raw[:-1]
        if len(raw) > LINE_MAX_BYTES:
            errors.append((number, "line is %d bytes, over %d" % (len(raw), LINE_MAX_BYTES)))
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append((number, "not JSON (%s)" % str(exc).split(":")[0]))
            continue
        if canonical(obj) != raw:
            errors.append((number, "not in canonical form (sorted keys, no spaces)"))
        if number == 1:
            header = obj
            if not isinstance(obj, dict) or obj.get("pkg") != PKG or obj.get("format") != FORMAT:
                errors.append((1, "header is not a %s format %d header" % (PKG, FORMAT)))
            elif name:
                parts = parse_package_name(name)
                if not parts:
                    errors.append((1, "file name is not <period>.<author>[.<batch>].jsonl"))
                elif (parts["period"], parts["author"], parts["batch"]) != \
                        (obj.get("period"), obj.get("author"), obj.get("batch")):
                    errors.append((1, "file name does not match its header"))
            continue
        problems = validate(obj)
        if problems:
            errors.append((number, "; ".join(problems)))
            continue
        obj["_line"] = number
        entries.append(obj)
    if header is None and not errors:
        errors.append((1, "empty package"))
    return header, entries, errors


def strip_private(entry):
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def period_of(ts, period):
    year, month = int(ts[0:4]), int(ts[5:7])
    if period == "month":
        return "%04d-%02d" % (year, month)
    if period == "quarter":
        return "%04d-Q%d" % (year, (month - 1) // 3 + 1)
    if period == "year":
        return "%04d" % year
    raise ValueError("period must be one of %s" % ", ".join(PERIODS))


def est_tokens(text):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return int(math.ceil(len(text) / 3.5))


def redact(text):
    if not text:
        return text
    for pattern in REDACTIONS:
        if pattern.groups >= 3:
            text = pattern.sub(lambda m: m.group(1) + m.group(2) + "[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


# ------------------------------------------------------------------ paths (§D8)
def strip_line(path):
    return re.sub(r":\d+(?:[-,]\d+)*$", "", (path or "").strip().strip("`"))


def path_matches(a, b):
    """Equality, fnmatch either way when either side has a glob, or a directory
    prefix either way."""
    a, b = strip_line(a), strip_line(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if any(c in a for c in GLOB_CHARS) and fnmatch.fnmatchcase(b, a):
        return True
    if any(c in b for c in GLOB_CHARS) and fnmatch.fnmatchcase(a, b):
        return True
    da, db = a.rstrip("/") + "/", b.rstrip("/") + "/"
    return b.startswith(da) or a.startswith(db)


def touches(paths, files):
    return any(path_matches(p, f) for p in paths for f in files)


def seal_paths(seal):
    if not seal:
        return []
    out = list(seal.get("files") or [])
    out += [c.get("path") for c in seal.get("changes") or [] if isinstance(c, dict) and c.get("path")]
    return sorted(set(p for p in out if isinstance(p, str)))


def where_list(value):
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    if isinstance(value, str) and value:
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def own_paths(entry):
    kind = entry.get("kind")
    if kind == "scope":
        return [p for p in entry.get("added") or [] if isinstance(p, str)]
    if kind == "risk":
        return where_list(entry.get("where"))
    if kind == "task":
        return seal_paths(entry)
    return []


# ------------------------------------------------------------------ recall (§D8, R10, R11)
def one_line(text, limit=RECALL_LINE_MAX):
    text = re.sub(r"\s+", " ", str(text if text is not None else "")).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def fmt_n(n):
    return "{:,}".format(n).replace(",", " ")


def day(ts):
    return (ts or "")[:10]


def is_human_by(by):
    return bool(by) and by not in ("agent", "hook", "unknown", "migration")


def candidate_items(entries, seals, superseded=frozenset(), all_risks=False):
    """(items, excluded): every recall item the entries give, unranked. A
    review gives one item per finding; a seal its task one-liner. Built from
    fields every source provides, so file and index backends agree (R11)."""
    items, excluded = [], 0
    closed_labels, last_pass, last_risk = {}, {}, {}
    for e in entries:
        if e.get("kind") == "review":
            for c in e.get("closed") or []:
                closed_labels.setdefault(key_of(e), set()).update(c.get("labels") or [])
            if isinstance(e.get("pass"), int):
                last_pass[key_of(e)] = max(last_pass.get(key_of(e), 0), e["pass"])
        elif e.get("kind") == "risk" and e.get("rid") not in superseded:
            have = last_risk.get(e.get("rkey"))
            if have is None or (e.get("ts") or "", e["rid"]) > (have.get("ts") or "", have["rid"]):
                last_risk[e.get("rkey")] = e
    for e in entries:
        kind, rid = e.get("kind"), e.get("rid")
        if rid in superseded:
            excluded += 1
            continue
        if kind == "risk" and last_risk.get(e.get("rkey")) is not e:
            excluded += 1                 # an older state of a risk recorded again later
            continue
        if kind == "review" and isinstance(e.get("pass"), int) and e["pass"] < last_pass.get(key_of(e), 0):
            excluded += 1                 # a later pass of the same task is the standing review
            continue
        seal = seals.get(key_of(e)) if e.get("task") else None
        inherited = seal_paths(seal)
        task, ts = e.get("task") or "-", e.get("ts") or ""
        base = {"rid": rid, "kind": kind, "task": e.get("task"), "ts": ts, "src": list(e.get("src") or [])}

        def add(tier, line, paths, order=0, base=base):  # pylint: disable=dangerous-default-value
            items.append(dict(base, tier=tier, order=order, line=one_line(line), paths=paths))
        if kind == "risk":
            status = e.get("status")
            if status == "fixed" and not all_risks:
                excluded += 1
                continue
            where = where_list(e.get("where"))
            tier = 0 if status == "open" else 6
            add(tier, "[risk %s %s] %s — %s (%s; found %s)" % (
                status, e.get("label"), where[0] if where else "-", e.get("title"), e.get("rkey"),
                e.get("found_by") or "-"), where)
        elif kind == "review":
            closed = closed_labels.get(key_of(e), set())
            for f in e.get("findings") or []:
                if f.get("label") in closed or f.get("severity") not in SEVERITIES:
                    continue
                where = where_list(f.get("where"))
                add(1, "[finding %s residual] %s — %s (%s %s, %s, %s)" % (
                    f.get("severity"), where[0] if where else "-", f.get("text"), task, f.get("label"),
                    e.get("tier"), day(ts)), where or inherited, SEVERITIES.index(f["severity"]))
        elif kind == "question":
            answer = e.get("answer") or {}
            if not answer:
                continue
            who = "human" if answer.get("actor") == "human" or is_human_by(answer.get("by")) else "agent"
            option = next((o.get("text") for o in e.get("options") or []
                           if o.get("key") == answer.get("choice")), None)
            add(2 if who == "human" else 3, '[answer %s] %s/%s — "%s" → %s%s by %s via %s, %s' % (
                who, task, e.get("qid"), e.get("question") or "?", answer.get("choice") or "-",
                ' "%s"' % option if option else (' "%s"' % answer["text"] if answer.get("text") else ""),
                answer.get("by") or "-", answer.get("via") or "-", day(answer.get("at") or ts)), inherited)
        elif kind == "override":
            add(2, "[override %s] %s — %s %s → %s by %s%s" % (
                e.get("actor"), task, e.get("what"), e.get("from"), e.get("to"), e.get("by") or "-",
                " — %s" % e["why"] if e.get("why") else ""), inherited)
        elif kind == "approval":
            if e.get("decision") == "pending":
                continue
            text = e.get("note") if e.get("decision") == "approved" else e.get("why")
            add(2, "[%s %s] %s/%s — by %s via %s, %s%s (historical — authorises nothing now)" % (
                "approval" if e.get("decision") == "approved" else "rejection", e.get("actor"), task,
                e.get("gate_id"), e.get("by") or "-", e.get("via") or "-", day(e.get("at") or ts),
                " — %s" % text if text else ""), inherited)
        elif kind == "note" and e.get("note_kind") in ("decision", "rejected", "failed"):
            add(3, "[%s %s] %s — %s%s" % (
                e.get("note_kind"), e.get("actor"), task, e.get("text") or e.get("error") or "-",
                " — because %s" % e["why"] if e.get("why") else ""), inherited)
        elif kind == "scope" and e.get("why"):
            added = [p for p in e.get("added") or [] if isinstance(p, str)]
            add(4, "[scope] %s — +%s — %s" % (task, ", ".join(added) or "-", e.get("why")), added or inherited)
        elif kind == "task":
            add(5, "[task] %s · %s · %s · %s — %s (%d files)" % (
                task, day(e.get("closed_at") or ts), e.get("mode") or "-", e.get("result") or "-",
                e.get("goal") or "-", len(seal_paths(e))), seal_paths(e))
    return items, excluded


def item_order(item):
    return (item["tier"], item["order"], desc_key(item["ts"]), item["rid"] or "", item["line"])


def desc_key(text):
    """A sort key that orders strings descending inside an ascending sort."""
    return tuple(-ord(c) for c in text or "") + (1,)


def recall_header(nfiles, shown, total, used, budget, source, excluded_task):
    parts = ["# Recall — %s files" % fmt_n(nfiles), "%s of %s items" % (fmt_n(shown), fmt_n(total)),
             "~%s/%s tokens" % (fmt_n(used), fmt_n(budget)),
             "packages %s + legacy %s" % (fmt_n(source.get("packages", 0)), fmt_n(source.get("legacy", 0))),
             "index %s%s" % (source.get("index", "none"), " (fallback: files)" if source.get("fallback") else "")]
    if excluded_task:
        parts.append("current task %s excluded" % excluded_task)
    return " · ".join(parts)


def more_line(more, files, offset):
    return '… %s more: state.py recall --files "%s" --offset %d' % (fmt_n(more), ",".join(files), offset)


def rank_recall(candidates, files, budget, max_items, offset=0, source=None, excluded_task=None):
    """(text, result): the one ranker every backend calls (R11). The output,
    header and continuation line included, stays within budget × 3.5 bytes
    unless the header alone does not fit."""
    source = source or {}
    budget = max(1, min(int(budget), RECALL_MAX_BUDGET))
    matched = sorted((c for c in candidates if touches(c["paths"], files)), key=item_order)
    total = len(matched)
    if not total:
        text = "# Recall — %s files · nothing recorded for these files" % fmt_n(len(files))
        if excluded_task:
            text += " · current task %s excluded" % excluded_task
        return text + "\n", {"items": [], "more": 0, "used": est_tokens(text + "\n"), "next": None}
    rest = matched[offset:]
    limit = budget * 3.5
    # The longest header any backend prints, so every backend packs the same items (R11).
    widest = dict(source, index="sqlite", fallback=True)
    reserve = len(recall_header(len(files), total, total, budget, budget, widest, excluded_task).encode()) + 1
    reserve += len(more_line(total, files, total).encode()) + 1
    chosen, size = [], reserve
    for item in rest:
        line = "- %s\n" % item["line"]
        if len(chosen) >= max_items or size + len(line.encode()) > limit:
            break
        chosen.append(item)
        size += len(line.encode())
    more = len(rest) - len(chosen)
    body = "".join("- %s\n" % i["line"] for i in chosen)
    tail = (more_line(more, files, offset + len(chosen)) + "\n") if more else ""
    # The items and the continuation line, not the header: the header names
    # the backend, and the count must not depend on it (R11).
    used = est_tokens(body + tail)
    header = recall_header(len(files), len(chosen), total, used, budget, source, excluded_task)
    nxt = ('state.py recall --files "%s" --offset %d' % (",".join(files), offset + len(chosen))) if more else None
    return header + "\n" + body + tail, {"items": chosen, "more": more, "used": used, "next": nxt}


# ------------------------------------------------------------------ search (§D8, R13)
SEARCH_SKIP = {"rid", "src", "digest", "v", "log", "tree", "base_tree", "base_commit", "final_tree",
               "supersedes", "_line", "_package"}


def tokenize(text):
    return re.findall(r"[^\W_]+", (text or "").casefold())


def search_text(entry):
    out = []

    def walk(value, key=None):
        if key in SEARCH_SKIP:
            return
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            for k in sorted(value):
                walk(value[k], k)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(entry)
    return " ".join(out)


def match_search(entry, tokens, filters, seal=None):
    """Every query token a prefix of one of the entry's tokens, and every filter."""
    filters = filters or {}
    if filters.get("kind") and entry.get("kind") != filters["kind"]:
        return False
    if filters.get("by"):
        names = {entry.get("by"), (entry.get("answer") or {}).get("by") if entry.get("kind") == "question" else None}
        if filters["by"] not in names:
            return False
    if filters.get("task") and entry.get("task") != filters["task"]:
        return False
    ts = entry.get("ts") or ""
    if filters.get("since") and ts[:len(filters["since"])] < filters["since"]:
        return False
    if filters.get("until") and ts[:len(filters["until"])] > filters["until"]:
        return False
    if filters.get("files"):
        paths = own_paths(entry) or seal_paths(seal)
        if entry.get("kind") == "review":
            paths = paths + [w for f in entry.get("findings") or [] for w in where_list(f.get("where"))]
        if not touches(paths, filters["files"]):
            return False
    if not tokens:
        return True
    have = tokenize(search_text(entry))
    return all(any(h.startswith(t) for h in have) for t in tokens)


def search_line(entry, seal=None):
    kind = entry.get("kind")
    text = ""
    if kind == "task":
        text = "%s · %s — %s" % (entry.get("mode"), entry.get("result"), entry.get("goal"))
    elif kind == "question":
        answer = entry.get("answer") or {}
        text = '%s "%s" → %s' % (entry.get("qid"), entry.get("question"), answer.get("choice") or "pending")
    elif kind == "note":
        text = "%s: %s" % (entry.get("note_kind"), entry.get("text") or entry.get("error"))
    elif kind == "risk":
        text = "%s %s %s — %s" % (entry.get("rkey"), entry.get("status"), entry.get("label"), entry.get("title"))
    elif kind == "review":
        text = "pass %s %s %s · %d findings" % (entry.get("pass"), entry.get("tier"), entry.get("verdict"),
                                                len(entry.get("findings") or []))
    elif kind == "approval":
        text = "%s %s by %s — %s" % (entry.get("gate_id"), entry.get("decision"), entry.get("by"),
                                     entry.get("note") or entry.get("why") or "")
    elif kind == "scope":
        text = "%s +%s — %s" % (entry.get("change"), ", ".join(entry.get("added") or []), entry.get("why"))
    elif kind == "override":
        text = "%s %s → %s — %s" % (entry.get("what"), entry.get("from"), entry.get("to"), entry.get("why"))
    elif kind == "verify":
        text = "run %s %s exit %s" % (entry.get("n"), entry.get("scope"), entry.get("exit"))
    elif kind == "weight":
        text = "%s W %s → %s" % (entry.get("change"), entry.get("w"), entry.get("mode"))
    else:
        text = search_text(entry)
    del seal
    return one_line("%s %s %s %s — %s" % (day(entry.get("ts")), kind, entry.get("task") or "-",
                                          entry.get("rid"), text))


def search_order(entry):
    return (desc_key(entry.get("ts") or ""), entry.get("rid") or "")


# ------------------------------------------------------------------ show (§D8)
def render_task_md(entries):
    """One key's entries as Markdown lines: the `memory show` view and the
    task.md a restore writes. A pure function of the entries."""
    entries = sort_entries(entries)
    seals = [e for e in entries if e.get("kind") == "task"]
    seal = seals[-1] if seals else {}
    task = seal.get("task") or (entries[0].get("task") if entries else "?")
    out = ["# %s — %s" % (task, one_line(seal.get("goal") or "-", 10000)), ""]
    if seal:
        counts = seal.get("counts") or {}
        out += ["%s · %s · W %s · %s · %s → %s · %s" % (
            seal.get("workflow"), seal.get("mode"), seal.get("w"), seal.get("result"), seal.get("started_at"),
            seal.get("closed_at"), ", ".join(seal.get("runtimes") or []) or "unknown"),
            "source: %s · format %d · keep rules %s · %s journal lines, %s skipped · %d entries · %s" % (
                seal.get("source"), FORMAT, seal.get("version"), counts.get("lines"), counts.get("skipped"),
                seal.get("entries") or 0, seal.get("digest")), ""]
        facts = seal.get("facts") or {}
        if facts:
            out += ["facts: (a) %s · (b) %s" % tuple(_fact(facts.get(k)) for k in ("a", "b")), ""]
        files = seal.get("changes") or []
        out += ["## Files", ""]
        if files:
            out += ["- %s (%s, %s)" % (c.get("path"), "binary" if c.get("binary") else "+%s −%s" % (
                c.get("added"), c.get("deleted")), c.get("status")) for c in files]
        else:
            out += ["- %s" % f for f in seal.get("files") or []] or ["none recorded"]
        out.append("")
    if len(seals) > 1:
        out += ["## Conflict", ""] + ["- version %s: %s (%s)" % (chr(97 + i), s.get("rid"), s.get("digest"))
                                      for i, s in enumerate(seals)] + [""]
    sections = [("question", "Questions"), ("approval", "Approvals"), ("override", "Overrides"),
                ("scope", "Scope"), ("weight", "Weight"), ("verify", "Verify"), ("review", "Review"),
                ("note", "Notes"), ("handoff", "Handoffs"), ("risk", "Risks"), ("conflict", "Conflicts"),
                ("redaction", "Redactions")]
    for kind, title in sections:
        group = [e for e in entries if e.get("kind") == kind]
        if not group:
            continue
        out += ["## %s" % title, ""]
        for e in group:
            out += _render_entry(e)
        out.append("")
    return out


def _fact(fact):
    if isinstance(fact, list) and len(fact) == 2:
        return "%s — %s" % ("green" if fact[0] else "RED", fact[1])
    return "not measured"


def _render_entry(e):
    kind, ref = e.get("kind"), "(%s, %s)" % (e.get("rid"), ", ".join(e.get("src") or []))
    if kind == "question":
        out = ["- %s (%s): %s %s" % (e.get("qid"), e.get("stage"), e.get("question"), ref)]
        out += ["  - %s. %s%s" % (o.get("key"), o.get("text"), " (recommended)"
                                  if o.get("key") == e.get("recommended") else "") for o in e.get("options") or []]
        if e.get("context"):
            out.append("  - context: %s" % e["context"])
        a = e.get("answer")
        out.append("  - answer: %s" % ("%s%s — by %s via %s at %s (%s)" % (
            a.get("choice"), ": %s" % a["text"] if a.get("text") else "", a.get("by"), a.get("via"), a.get("at"),
            a.get("actor")) if a else "pending"))
        return out
    if kind == "approval":
        return ["- %s %s by %s via %s at %s%s%s (historical — authorises nothing now) %s" % (
            e.get("gate_id"), e.get("decision"), e.get("by"), e.get("via"), e.get("at"),
            " — note: %s" % e["note"] if e.get("note") else "", " — why: %s" % e["why"] if e.get("why") else "",
            ref)]
    if kind == "override":
        return ["- %s %s → %s by %s via %s%s %s" % (e.get("what"), e.get("from"), e.get("to"), e.get("by"),
                                                    e.get("via"), " — %s" % e["why"] if e.get("why") else "", ref)]
    if kind == "scope":
        return ["- %s +%s%s %s" % (e.get("change"), ", ".join(e.get("added") or []),
                                   " — %s" % e["why"] if e.get("why") else "", ref)]
    if kind == "weight":
        return ["- %s W %s → %s%s %s" % (e.get("change"), e.get("w"), e.get("mode"),
                                         " (%s → %s)" % (e.get("from"), e.get("to")) if e.get("from") or e.get("to")
                                         else "", ref)]
    if kind == "verify":
        out = ["- run %s %s exit %s%s%s %s" % (e.get("n"), e.get("scope"), e.get("exit"),
                                               " expected_fail" if e.get("expected_fail") else "",
                                               " — %s" % e["why"] if e.get("why") else "", ref)]
        if e.get("excerpt"):
            out += ["    " + line for line in e["excerpt"].split("\n")]
        return out
    if kind == "review":
        out = ["- pass %s %s %s%s %s" % (e.get("pass"), e.get("tier"), e.get("verdict"),
                                         " (focus %s)" % e["focus"] if e.get("focus") else "", ref)]
        out += ["  - [%s] %s %s — %s" % (f.get("severity"), f.get("label"), f.get("where") or "-", f.get("text"))
                for f in e.get("findings") or []]
        out += ["  - closed: %s by run %s" % (", ".join(c.get("labels") or []), c.get("by_run"))
                for c in e.get("closed") or []]
        return out
    if kind == "note":
        return ["- %s: %s%s%s %s" % (e.get("note_kind"), e.get("text"), " — why: %s" % e["why"] if e.get("why")
                                     else "", " — error: %s" % e["error"] if e.get("error") else "", ref)]
    if kind == "handoff":
        return ["- %s → %s via %s %s" % (e.get("from"), e.get("to"), e.get("via"), ref)]
    if kind == "risk":
        return ["- %s %s [%s] %s — %s %s" % (e.get("rkey"), e.get("status"), e.get("label"), e.get("title"),
                                             e.get("what"), ref)]
    return ["- %s %s" % (json.dumps({k: v for k, v in e.items() if k not in ENVELOPE}, ensure_ascii=False,
                                    sort_keys=True), ref)]
