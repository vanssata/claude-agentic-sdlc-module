#!/usr/bin/env python3
"""Benchmark of the project history (spec compact-project-memory R27, A5, Q5).

  tools/benchmark-memory.py [--tasks 100,1000,10000] [--seed N] [--journal-kb K]
                            [--layouts legacy,packages] [--json]

Seeded synthetic histories, measured apart: `legacy` is today's layout — one
.ai/reports/<id>/ per task with its journal (journal_kb each), read by
FileHistory as files mode does; `packages` is the record — quarterly package
files, read by FileHistory and by the SQLite index (build, then query).
Each row reports time cold and warm, files read, bytes returned and storage.
generate() is importable: the recall and index suites reuse its histories.
Read-only towards the repository: everything is written to a temp directory.
"""
import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import memory_store  # noqa: E402  pylint: disable=wrong-import-position

START = datetime(2025, 1, 6, 8, 0, tzinfo=timezone.utc)
WORDS = ("cache", "key", "locale", "guard", "path", "review", "budget", "verify", "approve", "journal", "index",
         "widget", "report", "close", "scope", "risk", "migration", "hook", "token", "render")
AUTHORS = ("ana", "boris")


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def file_pool(rng, size=200):
    return ["src/mod%02d/%s_%d.py" % (i % 40, rng.choice(WORDS), i) for i in range(size)]


def words(rng, n):
    return " ".join(rng.choice(WORDS) for _ in range(n))


def generate(n, seed=1, journal_kb=4):
    """n synthetic tasks, deterministic for (n, seed, journal_kb): a list of
    {task, when, author, files, goal, journal (bytes), entries (record)}."""
    rng = random.Random(seed)
    pool = file_pool(rng)
    tasks = []
    for i in range(n):
        when = START + timedelta(minutes=37 * i)
        task_id = mf.new_task_id(when, "bench-%d" % i)
        files = rng.sample(pool, rng.randint(1, 5))
        goal = "%s %s" % (words(rng, 4), i)
        author = AUTHORS[i % len(AUTHORS)]
        tasks.append({"task": task_id, "when": when, "author": author, "files": files, "goal": goal,
                      "entries": task_entries(rng, task_id, when, author, files, goal),
                      "journal": journal(rng, task_id, when, goal, journal_kb)})
    return tasks


def envelope(task, seq, kind, when, actor="agent", by=None, src=None):
    return {"v": mf.FORMAT, "task": task, "inst": 1, "seq": seq, "kind": kind, "ts": stamp(when), "actor": actor,
            "by": by, "runtime": "claude", "src": src or ["events.jsonl:%d" % (seq + 1)]}


def task_entries(rng, task, when, author, files, goal):
    out = []
    q = envelope(task, 0, "question", when + timedelta(minutes=1))
    q.update(qid="Q1", stage="build", question="Which %s?" % words(rng, 2), context=files[0],
             options=[{"key": "A", "text": words(rng, 3)}, {"key": "B", "text": words(rng, 3)}], recommended="A",
             answer={"choice": rng.choice("AB"), "text": None, "by": author, "via": "prose",
                     "at": stamp(when + timedelta(minutes=2)), "actor": "agent"})
    out.append(q)
    note = envelope(task, 1, "note", when + timedelta(minutes=3))
    note.update(note_kind=rng.choice(("decision", "rejected", "failed")), text=words(rng, 8), why=words(rng, 5),
                error=None)
    out.append(note)
    scope = envelope(task, 2, "scope", when + timedelta(minutes=4))
    scope.update(change="amend", added=[rng.choice(files)], why=words(rng, 6))
    out.append(scope)
    review = envelope(task, 3, "review", when + timedelta(minutes=5))
    findings = [{"label": "%s%d" % (sev[0], k + 1), "severity": sev, "where": "%s:%d" % (rng.choice(files), k + 1),
                 "text": words(rng, 7), "in_scope": True}
                for k, sev in enumerate(rng.sample(mf.SEVERITIES, rng.randint(0, 2)))]
    review.update(**{"pass": 1, "tier": "BALANCED", "focus": None, "verdict": "pass_with_findings",
                     "findings": findings, "closed": [], "report": "task.md#Review-pass-1"})
    out.append(review)
    if rng.random() < 0.05:
        risk = envelope(task, 4, "risk", when + timedelta(minutes=6))
        title = "Risk %s %s" % (words(rng, 3), task[-6:])
        risk.update(rkey="R-%s-%04x" % (mf.slug_of(title)[:20], rng.getrandbits(16)), title=title,
                    where=[rng.choice(files)], label="RISK", what=words(rng, 6), likelihood=None, fix=None,
                    status=rng.choice(("open", "open", "accepted")), status_why=None, found_by=task, text=None)
        out.append(risk)
    out = [mf.with_rid(e) for e in out]
    seal = envelope(task, len(out), "task", when + timedelta(minutes=9), src=["events.jsonl:1"])
    seal.update(result="closed", goal=goal, workflow="feature", mode=rng.choice(("light", "guarded", "full")),
                w=rng.randint(1, 9), axes=None, started_at=stamp(when), closed_at=stamp(when + timedelta(minutes=9)),
                files=files, steps=[], stages=[], changes=[], code={}, facts={}, verify_runs=[],
                counts={"lines": len(out) + 2, "skipped": 0, "dropped": {}}, people={"started_by": None,
                                                                                    "humans": [author]},
                runtimes=["claude"], entries=len(out), digest=mf.seal_digest([e["rid"] for e in out]),
                source="close", schema=7, version=mf.KEEP_VERSION)
    return out + [mf.with_rid(seal)]


def journal(rng, task, when, goal, journal_kb):
    """A schema-7 journal of about journal_kb KB: the lines a real close leaves."""
    lines = [{"ts": stamp(when), "task": task, "event": "task_started", "actor": "agent", "runtime": "claude",
              "stage": "build", "detail": goal, "data": {"goal": goal, "workflow": "feature", "mode": "light",
                                                         "schema": 7}}]
    size = len(json.dumps(lines[0]))
    n = 1
    while size < journal_kb * 1024 - 300:
        n += 1
        kind = rng.choice(("handoff_written", "verify_run", "note", "step_done"))
        data = {"reason": "stage", "lines": 12} if kind == "handoff_written" else \
            {"n": n, "scope": "step", "exit": 0, "tree": None, "log": None, "expected_fail": False} \
            if kind == "verify_run" else {"kind": "decision", "text": words(rng, 12), "why": words(rng, 6)} \
            if kind == "note" else {"step_id": "s%d" % n}
        line = {"ts": stamp(when + timedelta(seconds=n)), "task": task, "event": kind, "actor": "agent",
                "runtime": "claude", "stage": "build", "detail": words(rng, 4), "data": data}
        lines.append(line)
        size += len(json.dumps(line)) + 1
    lines.append({"ts": stamp(when + timedelta(minutes=9)), "task": task, "event": "task_closed", "actor": "agent",
                  "runtime": "claude", "stage": "done", "detail": "", "data": {"abandoned": False, "mode": "light"}})
    return ("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n").encode("utf-8")


def write_packages(root, tasks, period="quarter"):
    """The tasks as package files, one per (period, author), like long-lived branches."""
    groups = {}
    for t in tasks:
        groups.setdefault((mf.period_of(stamp(t["when"]), period), t["author"]), []).extend(t["entries"])
    base = os.path.join(root, ".ai", "memory")
    os.makedirs(base, exist_ok=True)
    for (p, author), entries in sorted(groups.items()):
        header = mf.package_header(p, author, None, "2026-01-01T00:00:00Z")
        with open(os.path.join(base, mf.package_name(p, author)), "wb") as fh:
            fh.write(mf.render_package(header, entries))
    return len(groups)


def write_legacy(root, tasks):
    for t in tasks:
        d = os.path.join(root, ".ai", "reports", t["task"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "events.jsonl"), "wb") as fh:
            fh.write(t["journal"])
        with open(os.path.join(d, "task.md"), "w", encoding="utf-8") as fh:
            fh.write("# %s — %s\n\n## Plan\n\nfiles: %s\n" % (t["task"], t["goal"], ", ".join(t["files"])))


def storage(path):
    total = 0
    for dirpath, _, names in os.walk(path):
        total += sum(os.path.getsize(os.path.join(dirpath, n)) for n in names)
    return total


def timed(call):
    started = time.perf_counter()
    result = call()
    return (time.perf_counter() - started) * 1000.0, result


def measure(n, seed, journal_kb, layout):
    tasks = generate(n, seed, journal_kb)
    files = tasks[len(tasks) // 2]["files"][:2]
    query = " ".join(tasks[len(tasks) // 3]["goal"].split()[:2])
    root = tempfile.mkdtemp(prefix="ai-memory-bench-")
    try:
        os.makedirs(os.path.join(root, ".ai"))
        row = {"tasks": n, "layout": layout, "seed": seed, "journal_kb": journal_kb}
        if layout == "legacy":
            write_legacy(root, tasks)
            row["files_read"] = n * 2
        else:
            row["files_read"] = write_packages(root, tasks)
        row["storage_bytes"] = storage(os.path.join(root, ".ai"))
        for phase in ("cold", "warm"):
            ms, (text, _) = timed(lambda: memory_store.FileHistory(root).recall(files, 1500))
            row["file_recall_ms_%s" % phase] = round(ms, 1)
            ms, _ = timed(lambda: memory_store.FileHistory(root).search(query))
            row["file_search_ms_%s" % phase] = round(ms, 1)
        row["recall_bytes"] = len(text.encode("utf-8"))
        if layout == "packages":
            history = memory_store.SqliteHistory(root)
            ms, _ = timed(history.rebuild)
            row["index_build_ms"] = round(ms, 1)
            row["index_bytes"] = os.path.getsize(history.path)
            for phase in ("cold", "warm"):
                ms, _ = timed(lambda: memory_store.SqliteHistory(root).recall(files, 1500))
                row["index_recall_ms_%s" % phase] = round(ms, 1)
                ms, _ = timed(lambda: memory_store.SqliteHistory(root).search(query))
                row["index_search_ms_%s" % phase] = round(ms, 1)
            row["fts5"] = memory_store.fts5_available()
        return row
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tasks", default="100,1000,10000")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--journal-kb", dest="journal_kb", type=int, default=4)
    ap.add_argument("--layouts", default="legacy,packages")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows = [measure(int(n), args.seed, args.journal_kb, layout)
            for n in args.tasks.split(",") if n.strip() for layout in args.layouts.split(",") if layout.strip()]
    if args.json:
        print(json.dumps(rows, indent=1, sort_keys=True))
        return 0
    keys = ["tasks", "layout", "files_read", "storage_bytes", "recall_bytes", "file_recall_ms_cold",
            "file_recall_ms_warm", "file_search_ms_cold", "file_search_ms_warm", "index_build_ms",
            "index_recall_ms_warm", "index_search_ms_warm"]
    print(" ".join("%-20s" % k for k in keys))
    for row in rows:
        print(" ".join("%-20s" % row.get(k, "-") for k in keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
