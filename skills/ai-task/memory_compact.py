"""Close-time and migration-time extraction of the compact record (spec §D3).

compact_task reads one task's sources through a reader — FsReader over the
working tree, GitTreeReader over a commit — and returns its entries and seal.
Deterministic: the same sources give the same rids. Every journal line is
accounted for exactly once (R3): as the src of an entry, summarised into the
seal, or counted as dropped; a line no rule knows is kept as a note.
"""
import collections
import json
import os
import re
from datetime import datetime, timezone

import memory_format as mf

Compaction = collections.namedtuple("Compaction", "entries seal coverage problems")

# The question grammar of state.py (HEADING_RE … TRAILER_RE), read-only here:
# the record must not import state.py, because the pre-push hook imports it.
HEADING_RE = re.compile(r"^## (Q|G)(\d+)\. (.+)$")
OPTION_RE = re.compile(r"^([A-W])\. (.+?)( \(recommended\))?$")
OTHER_RE = re.compile(r"^X\. Other")
ANSWER_RE = re.compile(r"^\[Answer\]:\s*(.*)$")
META_RE = re.compile(r"^asked: (\S+) · stage: (\S+)(?: · by: (.+))?$")
CONTEXT_RE = re.compile(r"^context: (.+)$")
TRAILER_RE = re.compile(r"\s+—\s+by ([^—]+?) via (picker|prose|file|terminal|unattended|dialog) at "
                        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$")
CHOICE_TEXT_RE = re.compile(r"^([A-W])\s*[—:-]\s*(.+)$")
OTHER_TEXT_RE = re.compile(r"^X\s*:\s*(.+)$")
PASS_RE = re.compile(r"^### Pass (\d+) — (\w+), (\w+)(?: \(focus (\w+)\))?(?: by (.+))?$")
FINDING_RE = re.compile(r"^\s*(?:[-*]\s+)?\[(BLOCKER|HIGH|MEDIUM|LOW|INFO)\]\s+([A-Z][0-9]+)\b[.:]?\s*(.*)$")
IN_SCOPE_RE = re.compile(r"^\s*in_scope:\s*(yes|no)\b", re.I)
WHERE_RE = re.compile(r"`([A-Za-z0-9_.~/-]*[/.][A-Za-z0-9_.~/-]*(?::\d+(?:[-,]\d+)*)?)`")
CHANGE_ROW_RE = re.compile(r"^\| (.+) \| (binary|\+(\d+) −(\d+)) \| (New|Edit|Delete) \|$")
FACTS_RE = re.compile(r"^facts: \(a\) (.+) · \(b\) (.+)$")
AMENDED_RE = re.compile(r"^amended (\S+): \+(.*?) — (.*)$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
FAIL_LINE_RE = re.compile(r"^(FAIL|ERROR):")
EVIDENCE_LIMIT_LINES = 12
EVIDENCE_FAIL_LINES = 10


class FsReader:
    """The working tree. `tracked` sources read only .ai/reports/<id>/, which
    is what every clone has; close sources also read the local raw store."""

    def __init__(self, root):
        self.root = root

    def read(self, rel):
        try:
            with open(os.path.join(self.root, rel), "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def listdir(self, rel):
        try:
            return sorted(os.listdir(os.path.join(self.root, rel)))
        except OSError:
            return []


def report_rel(task_id, name):
    return ".ai/reports/%s/%s" % (task_id, name)


def text_of(data):
    if data is None:
        return None
    return data.decode("utf-8", errors="replace")


# ------------------------------------------------------------------ task.md
def parse_questions_lines(lines, src_name):
    questions, current = {}, None
    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            qid = heading.group(1) + heading.group(2)
            current = {"id": qid, "question": heading.group(3), "asked": None, "stage": None, "by": None,
                       "context": None, "options": [], "recommend": None, "answered": False,
                       "choice": None, "text": None, "answered_by": None, "via": None, "answered_at": None,
                       "src": "%s#%s" % (src_name, qid)}
            questions[qid] = current
            continue
        if current is None:
            continue
        meta = META_RE.match(line)
        if meta:
            current["asked"], current["stage"], current["by"] = meta.groups()
            continue
        context = CONTEXT_RE.match(line)
        if context:
            current["context"] = context.group(1)
            continue
        answer = ANSWER_RE.match(line)
        if answer:
            parse_answer(current, answer.group(1))
            current = None
            continue
        if OTHER_RE.match(line):
            continue
        option = OPTION_RE.match(line)
        if option:
            current["options"].append({"key": option.group(1), "text": option.group(2)})
            if option.group(3):
                current["recommend"] = option.group(1)
    return questions


def parse_answer(question, body):
    trailer = TRAILER_RE.search(body)
    if trailer:
        question["answered_by"], question["via"], question["answered_at"] = trailer.groups()
        body = body[:trailer.start()]
    body = body.strip()
    if not body:
        return
    question["answered"] = True
    other, pair = OTHER_TEXT_RE.match(body), CHOICE_TEXT_RE.match(body)
    if other:
        question["choice"], question["text"] = "X", other.group(1).strip()
    elif pair:
        question["choice"], question["text"] = pair.group(1), pair.group(2).strip()
    elif re.match(r"^[A-Z]$", body):
        question["choice"] = body
    else:
        question["choice"], question["text"] = "X", body


def sections(lines):
    """{heading: [lines]} for the `## ` sections of task.md; a question's own
    `## Q1.` heading stays inside §Questions."""
    out, name, fence = {}, None, None
    for line in lines:
        run = re.match(r"^`{3,}", line)
        if run and (fence is None or run.group(0) == fence):
            # A review report quotes its own `## FINDINGS`: a fence is opaque.
            fence = run.group(0) if fence is None else None
        elif fence is None and line.startswith("## ") and not HEADING_RE.match(line):
            name = line[3:].strip()
            out[name] = []
            continue
        if name is not None:
            out[name].append(line)
    return out


def parse_task_md(text, questions_md=None):
    """What the record takes from task.md: questions, gates, review passes,
    the plan's files, the change table, the facts and the gate line."""
    lines = (text or "").split("\n")
    parts = sections(lines)
    out = {"goal": None, "weight_lines": None, "files": None, "questions": {}, "reviews": {},
           "changes": None, "facts": None, "confirm": None}
    if lines and lines[0].startswith("# ") and " — " in lines[0]:
        out["goal"] = lines[0].split(" — ", 1)[1]
    weight = parts.get("Weight")
    if weight and "```" in weight:
        start = weight.index("```")
        end = weight.index("```", start + 1) if "```" in weight[start + 1:] else len(weight)
        out["weight_lines"] = weight[start + 1:end]
    out["amended"] = []
    for line in parts.get("Plan", []):
        if line.startswith("files: "):
            body = line[len("files: "):]
            out["files"] = [] if body == "none" else [f for f in body.split(", ") if f]
        amended = AMENDED_RE.match(line)
        if amended:
            out["amended"].append({"ts": amended.group(1), "added": amended.group(2).split(", "),
                                   "why": amended.group(3)})
    out["questions"] = parse_questions_lines(parts.get("Questions", []), "task.md")
    if questions_md is not None:
        for qid, q in parse_questions_lines(questions_md.split("\n"), "questions.md").items():
            out["questions"].setdefault(qid, q)
    review = parts.get("Review", [])
    i = 0
    while i < len(review):
        head = PASS_RE.match(review[i])
        if not head:
            i += 1
            continue
        n, tier, verdict, focus, by = head.groups()
        body, j = [], i + 1
        while j < len(review) and not review[j].startswith("`"):
            if PASS_RE.match(review[j]):
                break
            j += 1
        if j < len(review) and review[j].startswith("`"):
            fence = re.match(r"^`+", review[j]).group(0)
            j += 1
            while j < len(review) and review[j] != fence:
                body.append(review[j])
                j += 1
        out["reviews"][int(n)] = {"tier": tier, "verdict": verdict, "focus": focus, "by": by,
                                  "text": "\n".join(body)}
        i = j + 1
    changes = []
    for line in parts.get("Changes", []):
        row = CHANGE_ROW_RE.match(line)
        if row:
            path = row.group(1).replace("\\|", "|")
            binary = row.group(2) == "binary"
            changes.append({"path": path, "status": {"New": "A", "Delete": "D"}.get(row.group(5), "M"),
                            "added": 0 if binary else int(row.group(3)),
                            "deleted": 0 if binary else int(row.group(4)), "binary": binary})
    if changes or any(line == "| File | Change | New/Edit/Delete |" for line in parts.get("Changes", [])):
        out["changes"] = changes
    for line in parts.get("Verdict", []):
        facts = FACTS_RE.match(line)
        if facts:
            parsed = {}
            for key, value in zip(("a", "b"), facts.groups()):
                if value != "not measured" and " — " in value:
                    state, detail = value.split(" — ", 1)
                    parsed[key] = [state == "green", detail]
            out["facts"] = parsed or None
        if line.startswith("confirm: "):
            value = line[len("confirm: "):]
            out["confirm"] = None if value == "none" else value
    return out


def parse_findings(text):
    """[{label, severity, where, text, in_scope}] from a FINDINGS block."""
    findings, current = [], None
    for line in (text or "").split("\n"):
        match = FINDING_RE.match(line)
        if match:
            severity, label, rest = match.groups()
            where = WHERE_RE.search(rest)
            current = {"label": label, "severity": severity, "where": where.group(1) if where else None,
                       "text": rest.strip(), "in_scope": None}
            findings.append(current)
            continue
        if current is None:
            continue
        scope = IN_SCOPE_RE.match(line)
        if scope:
            current["in_scope"] = scope.group(1).lower() == "yes"
            continue
        if not line.strip() or line.startswith("#") or re.match(r"^(VERDICT|verdict:)", line.strip()):
            current = None
            continue
        current["text"] += "\n" + line.strip()
    return findings


def excerpt(log_text, expected_fail, limit):
    """At most `limit` bytes: the last 12 non-empty lines, ANSI stripped, with
    up to 10 FAIL:/ERROR: lines first for an expected_fail run, redacted."""
    if not log_text or limit <= 0:
        return None
    lines = [ANSI_RE.sub("", line).rstrip() for line in log_text.replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if line.strip()]
    tail = lines[-EVIDENCE_LIMIT_LINES:]
    head = [line for line in lines if FAIL_LINE_RE.match(line)][:EVIDENCE_FAIL_LINES] if expected_fail else []
    picked = head + [line for line in tail if line not in head]
    text = mf.redact("\n".join(picked))
    data = text.encode("utf-8")
    if len(data) > limit:
        text = data[-limit:].decode("utf-8", errors="ignore")
    return text


# ------------------------------------------------------------------ the journal
def parse_journal(data):
    """[(line_no, event or None)] — None is a torn line."""
    out = []
    if not data:
        return out
    for number, raw in enumerate(data.split(b"\n"), 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.decode("utf-8"))
            out.append((number, event if isinstance(event, dict) else None))
        except (ValueError, UnicodeDecodeError):
            out.append((number, None))
    return out


def split_instances(events):
    """One list per task_started segment; lines before the first belong to
    instance 1 (a backfilled journal starts mid-task)."""
    instances = [[]]
    for number, event in events:
        if event and event.get("event") == "task_started" and any(e for _, e in instances[-1]
                                                                  if e and e.get("event") == "task_started"):
            instances.append([])
        instances[-1].append((number, event))
    return [inst for inst in instances if inst] or [[]]


def actor_of(event):
    actor = (event or {}).get("actor")
    return actor if actor in mf.ACTORS else "unknown"


def runtime_of(event):
    runtime = (event or {}).get("runtime")
    return runtime if runtime in mf.RUNTIMES else "unknown"


class Builder:
    """One instance's entries, in journal order; the seal comes last."""

    def __init__(self, task_id, inst):
        self.task_id, self.inst = task_id, inst
        self.entries = []

    def add(self, kind, ts, actor, by, runtime, src, fields, truncated=(), unrecorded=()):
        entry = {"v": mf.FORMAT, "task": self.task_id, "inst": self.inst, "kind": kind, "ts": ts,
                 "actor": actor, "by": by, "runtime": runtime, "src": list(src)}
        entry.update(fields)
        if truncated:
            entry["truncated"] = sorted(set(truncated))
        if unrecorded:
            entry["unrecorded"] = sorted(set(unrecorded))
        self.entries.append(entry)
        return entry


def capped(fields, names, truncated, prefix=""):
    for name in names:
        value, cut = mf.cap(fields.get(name))
        fields[name] = value
        if cut:
            truncated.append(prefix + name)


def ts_ok(ts, fallback="1970-01-01T00:00:00Z"):
    return ts if isinstance(ts, str) and mf.TS_RE.match(ts) else fallback


def compact_task(reader, task_id, sources="close", inst=None, excerpt_max=1024):
    """One instance's Compaction (the last one by default)."""
    found = compact_instances(reader, task_id, sources, excerpt_max)
    if not found:
        return Compaction([], None, {"lines": 0, "accounted": 0, "skipped": 0}, ["no sources for %s" % task_id])
    if inst is None:
        return found[-1]
    for c in found:
        if c.seal and c.seal["inst"] == inst:
            return c
    return Compaction([], None, {"lines": 0, "accounted": 0, "skipped": 0}, ["no instance %s" % inst])


def compact_instances(reader, task_id, sources="close", excerpt_max=1024):
    """Every instance of one task id, in order."""
    journal = reader.read(report_rel(task_id, "events.jsonl"))
    task_md_raw = reader.read(report_rel(task_id, "task.md"))
    questions_raw = reader.read(report_rel(task_id, "questions.md"))
    state_rel = (".ai/state/logs/%s/state.json" % task_id) if sources == "close" else report_rel(task_id, "state.json")
    state_raw = reader.read(state_rel)
    if state_raw is None and sources == "close":
        state_rel = report_rel(task_id, "state.json")
        state_raw = reader.read(state_rel)
    problems, state = [], None
    if state_raw is not None:
        try:
            state = json.loads(state_raw.decode("utf-8"))
            if not isinstance(state, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            problems.append("%s is not valid JSON — the task is not exported (known risk: a torn archive)"
                            % state_rel)
            state = None
    md = parse_task_md(text_of(task_md_raw), text_of(questions_raw))
    events = parse_journal(journal)
    if not events and state is None:
        if md["goal"] is None:
            return []
    ctx = {"reader": reader, "task_id": task_id, "sources": sources, "excerpt_max": excerpt_max,
           "state": state, "state_rel": os.path.basename(state_rel), "md": md}
    instances = split_instances(events) if events else [[]]
    out = []
    for number, lines in enumerate(instances, 1):
        last = number == len(instances)
        out.append(_compact_one(ctx, number, lines, last, list(problems)))
    return out


def _compact_one(ctx, inst, lines, last, problems):
    task_id, md = ctx["task_id"], ctx["md"]
    state = ctx["state"] if last else None
    b = Builder(task_id, inst)
    accounted, dropped, skipped = set(), collections.Counter(), 0
    seal_src, summary = [], {"steps": [], "stages": [], "verify_runs": [], "runtimes": set()}
    started = closed = None
    schema = None
    weights, questions, gates, reviews, verifies = [], {}, {}, [], []
    tier_last = None
    prev_stage = None
    open_gate = None
    for number, event in lines:
        if event is None:
            skipped += 1
            continue
        name = event.get("event")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        ts = ts_ok(event.get("ts"))
        src = "events.jsonl:%d" % number
        summary["runtimes"].add(runtime_of(event))
        stage = event.get("stage")
        if stage and stage != prev_stage:
            summary["stages"].append([stage, ts])
            prev_stage = stage
        if name == "task_started":
            schema = data.get("schema", schema)
        rule = mf.classify(name, schema)
        accounted.add(number)
        if rule == "seal":
            seal_src.append(src)
            if name == "task_started":
                started = (event, data)
            else:
                closed = (event, data)
        elif rule == "summary":
            if name in ("step_started", "step_done"):
                step = data.get("step_id")
                rows = [r for r in summary["steps"] if r[0] == step]
                if name == "step_started" and not rows:
                    summary["steps"].append([step, "started"])
                elif name == "step_done":
                    if rows:
                        rows[0][1] = "done"
                    else:
                        summary["steps"].append([step, "done"])
            elif name == "tier_set":
                tier_last = data.get("tier")
        elif rule == "drop":
            dropped[name] += 1
        elif rule == "weight":
            weights.append((number, event, data))
        elif rule == "override":
            unrecorded = []
            if cut_line(data) and name == "mode_set":
                # The 4 KB cap dropped the payload: the live state keeps the override.
                data = {k: (state or {}).get("mode_override", {}).get(k) for k in ("from", "to", "by", "why")} \
                    if (state or {}).get("mode_override") else {}
            if cut_line(data) or not data:
                unrecorded = ["from", "to", "why"]
            fields = {"what": "mode" if name == "mode_set" else data.get("field"), "from": data.get("from"),
                      "to": data.get("to") if name == "mode_set" else data.get("value"),
                      "via": data.get("via"), "why": data.get("why")}
            if data.get("pick"):
                fields["pick"] = data["pick"]
            b.add("override", ts, actor_of(event), data.get("by"), runtime_of(event), [src], fields,
                  unrecorded=unrecorded)
        elif rule == "scope":
            truncated, unrecorded = [], []
            if cut_line(data):
                data = amendment_at(state, md if last else {}, ts)
                unrecorded = [] if data else ["added", "why"]
            fields = {"change": "plan" if name == "plan_registered" else (data.get("kind") or "amend"),
                      "added": list(data.get("added") or data.get("files") or []), "why": data.get("why")}
            capped(fields, ("why",), truncated)
            if name == "plan_registered":
                fields["steps"] = data.get("steps")
            b.add("scope", ts, actor_of(event), data.get("by"), runtime_of(event), [src], fields, truncated,
                  unrecorded)
        elif rule == "question":
            qid = data.get("id") or id_from_detail(event, r"[QG]\d+") or ""
            if qid.startswith("G"):
                gates.setdefault(qid, []).append((number, event, data))
            else:
                questions.setdefault(qid, []).append((number, event, data))
        elif rule == "approval":
            gate_id = data.get("gate_id") or id_from_detail(event, r"G\d+") or open_gate or "G?"
            if name == "gate_requested":
                open_gate = gate_id
            gates.setdefault(gate_id, []).append((number, event, data))
        elif rule == "review":
            reviews.append((number, event, data))
        elif rule == "verify":
            summary["verify_runs"].append([data.get("n"), data.get("scope"), data.get("exit"), data.get("tree"),
                                           bool(data.get("expected_fail"))])
            verifies.append((number, event, data))     # evidence runs also become entries
        elif rule == "note":
            truncated = []
            if name == "note":
                fields = {"note_kind": data.get("kind"), "text": data.get("text"), "why": data.get("why"),
                          "error": data.get("error")}
                if fields["text"] is None and event.get("detail"):
                    # `event note --detail …` without --data, or a payload the 4 KB cap dropped:
                    # the detail (at most 500 characters) is all the journal kept.
                    fields["text"] = event["detail"]
                    if cut_line(data) or len(event["detail"]) >= DETAIL_MAX:
                        truncated.append("text")
            elif name == "field_set":
                fields = {"note_kind": "field", "text": event.get("detail"), "why": None, "error": None,
                          "field": data.get("field"), "raw": data}
            else:
                fields = {"note_kind": name, "text": event.get("detail"), "why": data.get("why"), "error": None,
                          "raw": data}
            capped(fields, ("text", "why", "error"), truncated)
            # A payload the cap dropped is said, never guessed (review M1, pass 2).
            unrecorded = [k for k in ("note_kind", "text", "why") if fields.get(k) is None] if cut_line(data) else []
            b.add("note", ts, actor_of(event), data.get("by"), runtime_of(event), [src], fields, truncated,
                  unrecorded)
        elif rule == "handoff":
            b.add("handoff", ts, actor_of(event), data.get("by"), runtime_of(event), [src],
                  {"from": data.get("from"), "to": data.get("to"), "via": data.get("via"),
                   "reason": data.get("reason")})
        elif rule == "risk":
            fields = {k: data.get(k) for k in ("rkey", "title", "where", "label", "what", "likelihood", "fix",
                                               "status", "status_why")}
            fields.update(found_by=task_id, text=data.get("text"))
            if data.get("supersedes"):
                fields["supersedes"] = data["supersedes"]
            if data.get("label_derived"):
                fields["label_derived"] = True
            b.add("risk", ts, actor_of(event), data.get("by"), runtime_of(event), [src], fields)
        else:
            b.add("note", ts, actor_of(event), data.get("by"), runtime_of(event), [src],
                  {"note_kind": "unknown-event", "text": event.get("detail"), "why": None, "error": None,
                   "raw": event})
    _weights(b, weights, md)
    _questions(b, questions, md if last else {"questions": {}})
    _gates(b, gates, md if last else {"questions": {}}, state, md.get("confirm") if last else None)
    _reviews(b, reviews, md if last else {"reviews": {}})
    _verifies(ctx, b, verifies, state)
    if not lines and state is not None:
        _history(b, state)
    b.entries.sort(key=_entry_order)
    for seq, entry in enumerate(b.entries):
        entry["seq"] = seq
    entries = relink_risks([mf.with_rid(e) for e in b.entries])
    seal = _seal(ctx, entries, inst, last, state, started, closed, seal_src, summary, dropped, skipped,
                 len(lines), schema, tier_last)
    coverage = {"lines": len(lines), "accounted": len(accounted), "skipped": skipped}
    if skipped:
        problems.append("%d torn journal line(s) — cleanup stays blocked for this task" % skipped)
    return Compaction(entries, seal, coverage, problems)


DETAIL_MAX = 500                          # state.py's cap on a journal line's detail


def relink_risks(entries):
    """A risk closed in the task that recorded it superseded the live rid
    (`memory risks` before close); the record points at the exported one."""
    out, last = [], {}
    for e in entries:
        if e.get("kind") == "risk":
            prev = last.get(e.get("rkey"))
            if e.get("supersedes") and prev and e["supersedes"] != prev:
                e = mf.with_rid(dict(e, supersedes=prev))
            last[e.get("rkey")] = e["rid"]
        out.append(e)
    return out


def cut_line(data):
    """A line over JOURNAL_MAX_BYTES keeps its existence and loses its payload."""
    return data == {"truncated": True}


def id_from_detail(event, pattern):
    """A question or gate id from the detail's head (`Q1 = A`, `G1: human_approval`)
    when the payload is gone; the id only, never the text."""
    match = re.match(r"^(%s)\b" % pattern, event.get("detail") or "")
    return match.group(1) if match else None


def epoch(ts):
    try:
        return datetime.strptime((ts or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def amendment_at(state, md, ts):
    """A scope change the cap cut, from the archived state's amendments (exact)
    or task.md's `amended` line (whitespace folded): the one recorded nearest
    the journal line, within two seconds (state.py stamps both in one call)."""
    when = epoch(ts)
    if when is None:
        return {}
    for source in ((state or {}).get("amendments") or [], md.get("amended") or []):
        near = [(abs(epoch(a.get("ts")) - when), i, a) for i, a in enumerate(source)
                if isinstance(a, dict) and epoch(a.get("ts")) is not None and abs(epoch(a.get("ts")) - when) <= 2]
        if near:
            amendment = min(near, key=lambda n: (n[0], n[1]))[2]
            return {"kind": "amend", "added": list(amendment.get("added") or []), "why": amendment.get("why")}
    return {}


def _entry_order(entry):
    first = entry["src"][0] if entry["src"] else ""
    match = re.match(r"^events\.jsonl:(\d+)$", first)
    return (0, int(match.group(1)), "") if match else (1, 0, first)


def _weights(b, weights, md):
    first = True
    for number, event, data in weights:
        name = event.get("event")
        if name == "weight_set":
            fields = {"change": "set", "w": data.get("w"), "mode": data.get("mode"), "axes": data.get("axes"),
                      "from": None, "to": None, "lines": md.get("weight_lines") if first else None}
            first = False
        elif name == "weight_raised":
            fields = {"change": "raised", "w": data.get("w"), "mode": data.get("mode"), "axes": data.get("axes"),
                      "from": data.get("from"), "to": data.get("to"), "lines": None}
        elif name == "tier_raised":
            fields = {"change": "tier_raised", "w": None, "mode": None, "axes": None, "from": data.get("from"),
                      "to": data.get("to"), "lines": None}
        else:
            fields = {"change": "legacy_tier", "w": data.get("w"), "mode": data.get("mode"), "axes": None,
                      "from": data.get("from"), "to": data.get("tier"), "lines": None}
        b.add("weight", ts_ok(event.get("ts")), actor_of(event), data.get("by"), runtime_of(event),
              ["events.jsonl:%d" % number], fields)


def _questions(b, questions, md):
    from_md = md.get("questions") or {}
    ids = list(questions) + [q for q in from_md if q.startswith("Q") and q not in questions]
    for qid in ids:
        lines = questions.get(qid, [])
        q = from_md.get(qid)
        asked = next(((n, e, d) for n, e, d in lines if e.get("event") == "question_asked"), None)
        answers = [(n, e, d) for n, e, d in lines if e.get("event") == "question_answered"]
        src = ["events.jsonl:%d" % n for n, _, _ in lines] + ([q["src"]] if q else [])
        unrecorded = []
        options = list(q["options"]) if q else None
        if options is None:
            keys = (asked[2].get("options") if asked else None) or []
            options = [{"key": k, "text": None} for k in keys]
            unrecorded.append("options")
        fields = {"qid": qid, "stage": (q or {}).get("stage") or (asked[1].get("stage") if asked else None),
                  "question": q["question"] if q else None, "context": (q or {}).get("context"),
                  "options": options,
                  "recommended": (asked[2].get("recommended") if asked else None) or (q or {}).get("recommend"),
                  "answer": None}
        if fields["question"] is None:
            unrecorded.append("question")
        if answers or (q and q.get("answered")):
            _, ev, data = answers[-1] if answers else (None, None, {})
            whole = bool(answers) and not data.get("truncated")
            text = data.get("text") if whole else None
            if text is None and q and q.get("answered"):
                text = q.get("text")
            fields["answer"] = {
                "choice": data.get("choice") if whole else (q or {}).get("choice"),
                "text": text, "by": data.get("by") or (q or {}).get("answered_by"),
                "via": data.get("via") or (q or {}).get("via"),
                "at": (q or {}).get("answered_at") or (ts_ok(ev.get("ts")) if ev else None),
                "actor": actor_of(ev) if ev else "unknown"}
        head = asked or (lines[0] if lines else None)
        ts = ts_ok(head[1].get("ts")) if head else ts_ok((q or {}).get("asked"))
        b.add("question", ts, actor_of(head[1]) if head else "unknown", (q or {}).get("by"),
              runtime_of(head[1]) if head else "unknown", src, fields, unrecorded=unrecorded)


def _gates(b, gates, md, state, confirm):
    from_md = md.get("questions") or {}
    gate_state = (state or {}).get("gate") or {}
    ids = list(gates) + [g for g in from_md if g.startswith("G") and g not in gates]
    for gid in ids:
        lines = gates.get(gid, [])
        q = from_md.get(gid)
        request = next(((n, e, d) for n, e, d in lines if e.get("event") == "gate_requested"), None)
        decided = [(n, e, d) for n, e, d in lines if e.get("event") in ("gate_approved", "gate_rejected")]
        answered = [(n, e, d) for n, e, d in lines if e.get("event") == "question_answered"]
        last = decided[-1] if decided else (answered[-1] if answered else None)
        decision = "pending"
        if decided:
            decision = "approved" if decided[-1][1].get("event") == "gate_approved" else "rejected"
        elif answered:
            decision = "approved" if answered[-1][2].get("choice") == "A" else "rejected"
        elif q and q.get("answered"):
            decision = "approved" if q.get("choice") == "A" else "rejected"
        data = last[2] if last else {}
        text = q.get("text") if q else None
        same = gate_state.get("gate_id") == gid
        fields = {"gate_id": gid,
                  "requested_at": (request[2].get("requested_at") if request else None) or (q or {}).get("asked"),
                  "decision": decision,
                  "at": (q or {}).get("answered_at") or (ts_ok(last[1].get("ts")) if last else None),
                  "via": data.get("via") or (q or {}).get("via"), "unattended": data.get("unattended"),
                  "tty": data.get("tty"), "note": text if decision == "approved" else None,
                  "why": (data.get("why") or text) if decision == "rejected" else None,
                  "tree": gate_state.get("tree") if same else None,
                  "confirm": (gate_state.get("confirm") if same else None) or (confirm if decision == "approved" else None),
                  "operations": list(gate_state.get("operations") or []) if same else []}
        if data.get("pick"):
            fields["pick"] = data["pick"]
        src = ["events.jsonl:%d" % n for n, _, _ in lines] + ([q["src"]] if q else [])
        head = last or request or (lines[0] if lines else None)
        unrecorded = [] if q else ["note"]
        if not same:
            unrecorded.append("tree")
        b.add("approval", ts_ok(head[1].get("ts")) if head else ts_ok((q or {}).get("asked")),
              actor_of(head[1]) if head else "unknown", data.get("by") or (q or {}).get("answered_by"),
              runtime_of(head[1]) if head else "unknown", src, fields, unrecorded=unrecorded)


def _reviews(b, reviews, md):
    passes = md.get("reviews") or {}
    entries = {}
    for number, event, data in reviews:
        if event.get("event") == "review_verdict":
            n = data.get("pass_n")
            text = (passes.get(n) or {}).get("text")
            findings = parse_findings(text)
            truncated = []
            for i, f in enumerate(findings):
                f["text"], cut = mf.cap(f["text"])
                if cut:
                    truncated.append("findings[%d].text" % i)
            fields = {"pass": n, "tier": data.get("tier"), "focus": data.get("focus"),
                      "verdict": data.get("verdict"), "findings": findings, "closed": [],
                      "report": "task.md#Review-pass-%s" % n}
            entries[n] = b.add("review", ts_ok(event.get("ts")), actor_of(event), (passes.get(n) or {}).get("by"),
                               runtime_of(event), ["events.jsonl:%d" % number] + (["task.md#Review-pass-%s" % n]
                                                                                   if text is not None else []),
                               fields, truncated, [] if text is not None else ["findings"])
        else:
            target = entries[max(entries)] if entries else None
            if target is None:
                b.add("note", ts_ok(event.get("ts")), actor_of(event), None, runtime_of(event),
                      ["events.jsonl:%d" % number],
                      {"note_kind": "findings_closed", "text": event.get("detail"), "why": None, "error": None,
                       "raw": data})
                continue
            target.setdefault("closed", []).append({"labels": list(data.get("labels") or []),
                                                    "by_run": data.get("run")})
            target.setdefault("src", []).append("events.jsonl:%d" % number)


def _verifies(ctx, b, verifies, state):
    runs = {r.get("n"): r for r in ((state or {}).get("verify") or {}).get("runs") or [] if isinstance(r, dict)}
    evidence = set()
    for number, _, data in verifies:
        if data.get("expected_fail"):
            evidence.add(number)
    for scope in ("suite", "e2e"):
        last = [number for number, _, data in verifies if data.get("scope") == scope]
        if last:
            evidence.add(last[-1])
    for number, event, data in verifies:
        if number not in evidence:
            continue
        run = runs.get(data.get("n")) or {}
        log = data.get("log")
        text = None
        if log and (ctx["sources"] == "close" or log.startswith(".ai/reports/")):
            text = text_of(ctx["reader"].read(log))
        fields = {"n": data.get("n"), "scope": data.get("scope"), "exit": data.get("exit"),
                  "tree": data.get("tree"), "command": run.get("command"), "duration_s": run.get("duration_s"),
                  "expected_fail": bool(data.get("expected_fail")), "after_fix": run.get("after_fix"),
                  "why": data.get("why"), "excerpt": excerpt(text, data.get("expected_fail"), ctx["excerpt_max"]),
                  "log": ("log:%s" % log) if log else None}
        truncated = []
        capped(fields, ("why", "after_fix"), truncated)
        b.add("verify", ts_ok(event.get("ts")), actor_of(event), None, runtime_of(event),
              ["events.jsonl:%d" % number], fields, truncated)


def _history(b, state):
    """A state-only legacy task (pre-WP2): its history[] as notes, by migration."""
    for i, item in enumerate(state.get("history") or []):
        if not isinstance(item, dict):
            continue
        fields = {"note_kind": "history:%s" % item.get("event"), "text": item.get("detail"), "why": None,
                  "error": None}
        truncated = []
        capped(fields, ("text",), truncated)
        b.add("note", ts_ok(item.get("at")), "migration", None, "unknown", ["state.json#history[%d]" % i], fields,
              truncated)


def _seal(ctx, entries, inst, last, state, started, closed, seal_src, summary, dropped, skipped, nlines,
          schema, tier_last):
    md = ctx["md"] if last else {}
    sdata = started[1] if started else {}
    cdata = closed[1] if closed else {}
    state = state or {}
    unrecorded, truncated = [], []
    goal = sdata.get("goal") or state.get("goal") or md.get("goal")
    goal, cut = mf.cap(goal)
    if cut:
        truncated.append("goal")
    weights = [e for e in entries if e["kind"] == "weight" and e.get("axes")]
    modes = [e for e in entries if e["kind"] == "override" and e.get("what") == "mode"]
    if closed:
        result = "abandoned" if cdata.get("abandoned") else "closed"
    elif not last:
        result = "restarted"
    else:
        result = state.get("result") or ("closed" if state.get("current_stage") == "done" else "open")
    if ctx["sources"] == "close" and state.get("files") is not None:
        files = list(state.get("files") or [])
    else:
        files = md.get("files")
    if files is None and isinstance(state.get("approved_plan"), dict):
        # A legacy state.json (tracked): the plan's steps name their files.
        plan_files = []
        for step in state["approved_plan"].get("steps") or []:
            for path in (step.get("allowed_files") or []) if isinstance(step, dict) else []:
                if isinstance(path, str) and path not in plan_files:
                    plan_files.append(path)
        files = plan_files or None
    if files is None:
        files = sorted({p for e in entries if e["kind"] == "scope" for p in e.get("added") or []})
        unrecorded.append("files")
    changes = state.get("changes") if ctx["sources"] == "close" and state.get("changes") is not None \
        else md.get("changes")
    if changes is None:
        changes = []
        unrecorded.append("changes")
    diff, facts_state = state.get("diff") or {}, state.get("facts") or {}
    if diff and (ctx["sources"] == "close" or diff.get("base_tree")):
        code = {"base_commit": diff.get("base_commit"), "base_tree": diff.get("base_tree"),
                "final_tree": facts_state.get("tree") or ((diff.get("task") or {}).get("tree")
                                                          if isinstance(diff.get("task"), dict) else None)}
    else:
        code = {"base_commit": None, "base_tree": None, "final_tree": None}
        unrecorded.append("code")
    if ctx["sources"] == "close" and facts_state.get("a"):
        facts = {k: list(facts_state[k]) for k in ("a", "b") if facts_state.get(k)}
    else:
        facts = md.get("facts")
    if facts is None:
        facts = {}
        unrecorded.append("facts")
    humans = set()
    for e in entries:
        if e["kind"] == "question" and e.get("answer") and (e["answer"].get("actor") == "human"
                                                            or e["answer"].get("via") in ("file", "terminal")):
            humans.add(e["answer"].get("by"))
        elif e["actor"] == "human" and e.get("by"):
            humans.add(e["by"])
        elif e["kind"] in ("approval",) and e.get("by") and e.get("decision") != "pending":
            humans.add(e["by"])
    humans.discard(None)
    rids = [e["rid"] for e in entries]
    unrecorded.append("people.started_by")
    when = (closed[0].get("ts") if closed else None) or (started[0].get("ts") if started else None) \
        or state.get("closed_at") or state.get("updated_at") or state.get("created_at") or state.get("created")
    seal = {"v": mf.FORMAT, "task": ctx["task_id"], "inst": inst, "seq": len(entries), "kind": "task",
            "ts": ts_ok(when),
            "actor": actor_of(closed[0]) if closed else ("migration" if not started else "agent"),
            "by": None, "runtime": runtime_of(closed[0]) if closed else "unknown",
            "src": seal_src + ([ctx["state_rel"]] if state else []) or ["task.md"],
            "result": result, "goal": goal,
            "workflow": sdata.get("workflow") or state.get("workflow"),
            "mode": cdata.get("mode") or (modes[-1].get("to") if modes else None) or sdata.get("mode")
            or state.get("mode"),
            "w": cdata.get("w") if cdata.get("w") is not None else (weights[-1].get("w") if weights else None),
            "axes": weights[-1].get("axes") if weights else None,
            "started_at": ts_ok(started[0].get("ts")) if started else (state.get("created_at") or state.get("created")),
            "closed_at": ts_ok(closed[0].get("ts")) if closed else state.get("closed_at"),
            "files": files, "steps": summary["steps"], "stages": summary["stages"], "changes": changes,
            "code": code, "facts": facts, "verify_runs": summary["verify_runs"],
            "counts": {"lines": nlines, "skipped": skipped, "dropped": dict(sorted(dropped.items()))},
            "people": {"started_by": None, "humans": sorted(humans)},
            "runtimes": sorted(summary["runtimes"] - {"unknown"}) or ["unknown"],
            "entries": len(entries), "digest": mf.seal_digest(rids),
            "source": "close" if ctx["sources"] == "close" else "migration",
            "schema": schema if schema is not None else state.get("schema"), "version": mf.KEEP_VERSION}
    if tier_last and (seal["schema"] or 0) < 7:
        seal["legacy_tier"] = tier_last
    elif state.get("risk_tier") and not started:
        seal["legacy_tier"] = state.get("risk_tier")
    if not when:
        unrecorded.append("ts")
    if truncated:
        seal["truncated"] = truncated
    seal["unrecorded"] = sorted(set(unrecorded))
    return mf.with_rid(seal)


# ------------------------------------------------------------------ known-risks.md (§D9, R24)
RISK_HEAD_RE = re.compile(r"^## (.+)$")
RISK_FIELD_RE = re.compile(r"^- \*\*([^*]+)\*\*:\s?(.*)$")
LABEL_IN_TEXT_RE = re.compile(r"\b(KNOWN FACT|INFERENCE|UNKNOWN)\b")
TASK_REF_RE = re.compile(r"\bT-[0-9A-Za-z][0-9A-Za-z._-]*[0-9A-Za-z]")


def rkey_of(title):
    """R-<slug(title)[:40]>-<sha256(title)[:4]> (§D9)."""
    import hashlib  # pylint: disable=import-outside-toplevel
    text = "".join(mf.TRANSLIT.get(c, c) for c in (title or "").casefold())
    words = re.findall(r"[a-z0-9]+", text)
    slug = "-".join(words)[:40].strip("-") or "risk"
    return "R-%s-%s" % (slug, hashlib.sha256((title or "").encode("utf-8")).hexdigest()[:4])


def risk_status(text):
    text = (text or "").strip().lower()
    for status in mf.RISK_STATUS:
        if text.startswith(status):
            return status
    if re.match(r"^(closed|done|resolved)", text):
        return "fixed"
    return "open"


def parse_known_risks(text):
    """(risks, leftovers): one risk per `## ` section outside an HTML comment,
    each with its exact text, so render_known_risks reproduces the file byte
    for byte (A12). leftovers are the lines before the first section."""
    raw = text or ""
    trailing_newline = raw.endswith("\n")
    lines = raw.split("\n")
    if trailing_newline:
        lines = lines[:-1]
    first, in_comment = len(lines), False
    for i, line in enumerate(lines):
        if not in_comment and RISK_HEAD_RE.match(line):
            first = i
            break
        if "<!--" in line and "-->" not in line.split("<!--", 1)[1]:
            in_comment = True
        elif "-->" in line:
            in_comment = False
    blocks, current = [], None
    for line in lines[first:]:
        if RISK_HEAD_RE.match(line):
            current = [line]
            blocks.append(current)
        else:
            current.append(line)
    risks = []
    for section in blocks:
        title = RISK_HEAD_RE.match(section[0]).group(1)
        fields = {}
        for line in section[1:]:
            match = RISK_FIELD_RE.match(line)
            if match and match.group(1) not in fields:
                fields[match.group(1)] = match.group(2)
        label, derived = fields.get("Label"), False
        if label not in mf.LABELS:
            found = LABEL_IN_TEXT_RE.search(fields.get("What could go wrong") or "")
            label, derived = (found.group(1) if found else "RISK"), True
        found_text = fields.get("Found") or fields.get("Found by")
        ref = TASK_REF_RE.search(found_text or "")
        where = fields.get("Where") or ""
        risks.append({"rkey": rkey_of(title), "title": title,
                      "where": [w.group(1) for w in re.finditer(r"`([^`]+)`", where)] or
                               ([where.strip()] if where.strip() else []),
                      "label": label, "label_derived": derived, "what": fields.get("What could go wrong"),
                      "likelihood": fields.get("How likely / how bad"),
                      "fix": fields.get("Suggested fix") or fields.get("Fix"),
                      "status": risk_status(fields.get("Status")), "status_why": fields.get("Status"),
                      "found_by": ref.group(0) if ref else found_text, "text": "\n".join(section)})
    return risks, {"lines": lines[:first], "trailing_newline": trailing_newline}


def render_known_risks(risks, leftovers):
    """The inverse of parse_known_risks, from each risk's stored text."""
    lines = list(leftovers["lines"])
    for risk in risks:
        lines += risk["text"].split("\n")
    return "\n".join(lines) + ("\n" if leftovers["trailing_newline"] else "")


def risk_section(title, where, label, what, likely, fix, status, found):
    """A new known-risks.md section: the file's template plus a Label line."""
    return ["## %s" % title, "", "- **Found**: %s" % found,
            "- **Where**: %s" % ", ".join("`%s`" % w for w in where),
            "- **What could go wrong**: %s" % (what or ""), "- **How likely / how bad**: %s" % (likely or ""),
            "- **Suggested fix**: %s" % (fix or ""), "- **Status**: %s" % status, "- **Label**: %s" % label]
