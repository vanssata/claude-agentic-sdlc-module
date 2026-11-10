"""report: the text the state is rendered to — the two close facts, the status lines, the schema line, task.md and its writer.

core: md_cell
shell: two_facts, status_lines, schema_line, task_md_lines, write_task_md
"""
import contextlib
import os
import re
import sys

from rr_state import fs, journal, locks, questions, task
from rr_state import policy as rr_policy   # status_lines names a local `policy`, as state.py does

# weight.py and sensors.py sit beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None
try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None


def two_facts(root, state, tree):
    """R6: (a) a green suite on the tree as it is now; (b) the diff since the base
    tree inside the task's files. Each is (green, why)."""
    runs = [r for r in state["verify"]["runs"] if rr_policy.full_suite(r)]
    here = [r for r in runs if tree and r.get("tree") == tree]
    green = [r for r in here if r.get("exit") == 0]
    documents = None
    if not tree:
        a = (False, "the tree cannot be measured (not a git repository)")
    elif not runs:
        a = (False, "no whole-suite 'verify --scope suite|all' has run")
    elif not here:
        a = (False, "the tree changed after the last verify (run %d on %s, now %s)"
             % (runs[-1]["n"], (runs[-1].get("tree") or "?")[:9], tree[:9]))
        ok, why, documents = rr_policy.documents_cover(root, state, rr_policy.weight_policy(root), tree)
        if ok or why:
            a = (ok, why)
    elif not green:
        a = (False, "the suite is red on this tree (run %d, exit %s)" % (here[-1]["n"], here[-1].get("exit")))
    else:
        # R19: a red under Codex on a tree green under another runtime is waived,
        # in either order (Codex is best effort). Any other red stands until a
        # later green under its own runtime: a green elsewhere does not answer it.
        others = any(g.get("runtime") != "codex" for g in green)

        def answered(r):
            return (r.get("runtime") == "codex" and others) or any(
                g["n"] > r["n"] and g.get("runtime") == r.get("runtime") for g in green)
        unwaived = [r for r in here if r.get("exit") != 0 and not answered(r)]
        before = [g for g in green if unwaived and g["n"] < unwaived[-1]["n"]]
        if unwaived and before:
            a = (False, "the suite went red on this tree after run %d (run %d under %s)"
                 % (before[-1]["n"], unwaived[-1]["n"], unwaived[-1].get("runtime")))
        elif unwaived:
            a = (False, "the suite is red on this tree under %s (run %d); green under %s (run %d) does "
                        "not answer it" % (unwaived[-1].get("runtime"), unwaived[-1]["n"],
                                           green[-1].get("runtime"), green[-1]["n"]))
        else:
            a = (True, "suite green on %s (run %d)" % (tree[:9], green[-1]["n"]))
    diff = fs.safe_sensor(sensors.diff_files, root, state["diff"].get("base_tree"), tree)
    allowed = task.task_files(state)
    outside = [d["path"] for d in diff or [] if not sensors.scope_any(d["path"], allowed)]
    if diff is None:
        b = (False, "the diff since the base tree cannot be measured")
    elif outside:
        b = (False, "outside the task's files: %s" % ", ".join(outside[:5])
             + (" (+%d more)" % (len(outside) - 5) if len(outside) > 5 else ""))
    else:
        b = (True, "%d changed files, all in the task's files" % len(diff))
    return {"a": a, "b": b, "diff": diff or [], "outside": outside, "documents": documents}

def status_lines(root, state):
    """≤ 20 lines; read-only (the facts are measured, nothing is written)."""
    lines = ["root: %s" % root]
    if not state or not state.get("task_id"):
        return lines + ["task: none — no task in flight", schema_line(root)]
    events, _ = journal.read_journal(root, state["task_id"])
    last = events[-1] if events else {}
    pending = (state.get("questions") or {}).get("pending") or []
    if task.is_v7(state):
        # The cache lags a hand-filled [Answer]:; the file is the truth, as guard_pending reads it.
        with contextlib.suppress(OSError, ValueError, KeyError):
            _, asked = questions.parse_questions(fs.questions_path(root, state, None))
            gate_id = task.open_gate(state)
            pending = [q["id"] for q in asked if (q["kind"] != "G" and questions.is_pending(q)) or q["id"] == gate_id]
    lines.append("task: %s — %s" % (state["task_id"], fs.one_line(state.get("goal"), 140)))
    if not task.is_v7(state):
        lines += ["tier: %s · workflow %s · stage %s" % (state.get("risk_tier") or "?", state.get("workflow"),
                                                        state.get("current_stage")),
                  "next: %s" % (fs.one_line(state.get("next_action"), 160) or "?"),
                  "old surface (schema < 7): /status reads it directly"]
    else:
        w = state.get("weight") or {}
        policy = rr_policy.weight_policy(root)
        tree = fs.current_tree(root)
        facts = two_facts(root, state, tree)
        steps = state.get("steps") or []
        cur = next((s for s in steps if s.get("status") == "in_progress"), None)
        review, ver, gate = state["review"], state["verify"], state.get("gate") or {}
        override = state.get("mode_override") or {}
        lines += [
            "mode: %s · W %s · workflow %s%s" % (state["mode"], w.get("w"), state.get("workflow"),
                                                 " · override %s → %s by %s" % (override.get("from"),
                                                                               override.get("to"),
                                                                               override.get("by"))
                                                 if override else ""),
            "axes: %s" % " ".join("%s %s" % (a, (w.get("axes") or {}).get(a, "?")) for a in weight.AXES),
            "stage: %s · next: %s" % (state.get("stage"), fs.one_line(state.get("next_action"), 140)),
            ("steps: %d of %d done — current %s" % (len([s for s in steps if s["status"] == "done"]), len(steps),
                                                    cur["id"] if cur else "none")
             if steps else "steps: one scope"),
            "files: %d in scope — %s" % (len(task.task_files(state)), ", ".join(task.task_files(state)[:4])
                                         + (" (+%d more)" % (len(task.task_files(state)) - 4)
                                            if len(task.task_files(state)) > 4 else "")),
            "verify: suite %s · runs %d/%s · e2e %s" % (ver["status"], ver["suite_runs"],
                                                        rr_policy.budget(policy, state, "max_suite_runs")[0],
                                                        ver.get("e2e")),
            "facts: (a) %s — %s" % ("green" if facts["a"][0] else "RED", facts["a"][1]),
            "       (b) %s — %s" % ("green" if facts["b"][0] else "RED", facts["b"][1]),
            "review: %s (%d of %s) · tier %s%s" % (review["status"], review["passes"],
                                                   rr_policy.budget(policy, state, "review_rounds_max")[0],
                                                   review.get("tier") or "-",
                                                   " · open %s" % ", ".join(review["findings"])
                                                   if review["findings"] else ""),
            "gate: %s" % ("approved by %s%s" % (gate["approved_by"], " · confirm \"%s\"" % gate["confirm"]
                                                if gate.get("confirm") else "")
                          if gate.get("approved_by") else "requested %s, waiting for the human" % gate.get("gate_id")
                          if task.open_gate(state) else "not requested"
                          if state["mode"] in ("full", "full_irreversible") else "none in %s mode" % state["mode"]),
            "findings: %d recorded in task.md" % len(state.get("findings") or []),
        ]
        if rr_policy.batch_on(state):
            # Before the truncation point, so the 20-line cap never cuts it.
            lines.insert(3, "batch: on by %s · review %d/%d · suite %d/%d · ready %s" % (
                fs.one_line(state["batch"].get("by"), 40), review["passes"],
                rr_policy.budget(policy, state, "review_rounds_max")[0], ver["suite_runs"],
                rr_policy.budget(policy, state, "max_suite_runs")[0],
                ", ".join(s["id"] for s in task.ready_steps(state)) or "none"))
    lines += ["questions: %d pending%s" % (len(pending), " — %s" % ", ".join(map(str, pending[:4])) if pending else ""),
              schema_line(root),
              "last event: %s" % (" ".join(fs.one_line(last.get(k), 80) for k in ("ts", "event", "detail")
                                           if last.get(k)) or "none")]
    return lines[:20]

def schema_line(root):
    try:
        with open(os.path.join(root, ".ai", "VERSION"), encoding="utf-8") as fh:
            project = fh.read().strip() or "0"
    except OSError:
        project = "0"
    here = os.path.dirname(os.path.dirname(fs.ENTRY))
    try:
        with open(os.path.join(here, "ai-init", "templates", ".ai", "VERSION"), encoding="utf-8") as fh:
            plugin = fh.read().strip() or "?"
    except OSError:
        plugin = "?"
    behind = project.isdigit() and plugin.isdigit() and int(project) < int(plugin)
    return "schema: project %s · plugin %s%s" % (project, plugin, " — behind: run /rr-setup --update" if behind else "")

def md_cell(text):
    return fs.one_line(text, 200).replace("|", "\\|")

def task_md_lines(root, state):
    """A pure function of the state and the journal: eight sections (§Interfaces).
    §Questions is "none" here; write_task_md keeps the section already on disk."""
    events, _ = journal.read_journal(root, state["task_id"])
    w = state.get("weight") or {}
    override = state.get("mode_override")
    out = ["# %s — %s" % (state["task_id"], fs.one_line(state.get("goal"))), "",
           "%s · %s · started %s · %s" % (state.get("workflow"), state.get("mode"), state.get("created"),
                                          state.get("owner_runtime") or "unknown"), "",
           "## Weight", "", "```"] + list(w.get("lines") or []) + ["```"]
    if override:
        out.append("override: %s → %s by %s at %s%s" % (override.get("from"), override.get("to"),
                                                        override.get("by"), override.get("ts"),
                                                        " — %s" % fs.one_line(override["why"])
                                                        if override.get("why") else ""))
    out += ["re-score %s" % fs.one_line(line, 300) for line in w.get("rescores") or []]
    if rr_policy.batch_on(state):
        batch = state["batch"]
        out.append("batch: on by %s at %s%s" % (fs.one_line(batch.get("by"), 80), batch.get("since"),
                                                " — %s" % fs.one_line(batch["why"]) if batch.get("why") else ""))
    out += ["", "## Plan", "", "files: %s" % (", ".join(state.get("files") or []) or "none"),
            "tests: %s" % (", ".join(state.get("tests") or []) or "none")]
    for step in state.get("steps") or []:
        out.append("- %s · %s · %s · %s%s" % (step["id"], ", ".join(step["files"]),
                                              ", ".join(step["tests"]) or "no tests", step["status"],
                                              " · after %s" % ", ".join(step["after"]) if step.get("after") else ""))
    out += ["amended %s: +%s — %s" % (a["ts"], ", ".join(a["added"]), fs.one_line(a["why"]))
            for a in state.get("amendments") or []]
    out += ["", questions.QUESTIONS_SECTION, "", "none"]
    out += ["", "## Verify", "", "| n | scope | exit | tree | log | expected_fail |", "|---|---|---|---|---|---|"]
    for r in state["verify"]["runs"]:
        out.append("| %s | %s | %s | %s | %s | %s |" % (r["n"], r["scope"], r.get("exit"),
                                                        (r.get("tree") or "-")[:9], md_cell(r.get("log")),
                                                        "yes" if r.get("expected_fail") else "no"))
    out.append("")
    out.append("suite %s · e2e %s%s · suite runs %d" % (
        state["verify"]["status"], state["verify"].get("e2e"),
        " (%s)" % fs.one_line(state["verify"]["e2e_why"]) if state["verify"].get("e2e_why") else "",
        state["verify"]["suite_runs"]))
    out += ["finding: %s" % fs.one_line(f, 300) for f in state.get("findings") or []]
    out += ["", "## Review", ""]
    for p in state["review"]["log"]:
        out += ["### Pass %d — %s, %s%s%s" % (p["n"], p["tier"], p["verdict"],
                                             " (focus %s)" % p["focus"] if p.get("focus") else "",
                                             " by %s" % p["by"] if p.get("by") else ""), ""]
        # A fence longer than any backtick run in the text, so a report quoting
        # code cannot close it early.
        fence = "`" * max([3] + [len(run) + 1 for run in re.findall(r"`+", p.get("text") or "")])
        out += ([fence] + p["text"].rstrip("\n").split("\n") + [fence]) if p.get("text", "").strip() \
            else ["no FINDINGS block"]
        out.append("")
    if not state["review"]["log"]:
        out += ["none yet", ""]
    if state["review"].get("closed"):
        out += ["closed by a green run: %s" % ", ".join(state["review"]["closed"]), ""]
    out += ["## Changes", ""]
    changes = state.get("changes")
    if changes is None:
        out.append("measured at close")
    else:
        kind = {"A": "New", "D": "Delete"}
        out += ["| File | Change | New/Edit/Delete |", "|---|---|---|"]
        out += ["| %s | %s | %s |" % (md_cell(c["path"]), "binary" if c.get("binary") else
                                      "+%d −%d" % (c["added"], c["deleted"]), kind.get(c["status"], "Edit"))
                for c in changes]
        out += ["", "+%d −%d lines, %d files" % (sum(c["added"] for c in changes),
                                                 sum(c["deleted"] for c in changes), len(changes))]
    gate, facts = state.get("gate") or {}, state.get("facts") or {}
    handoffs = len([e for e in events if e.get("event") == "handoff_written"])
    out += ["", "## Verdict", "",
            "close: %s" % (state.get("result") or "open — %s" % fs.one_line(state.get("next_action"))),
            "facts: (a) %s · (b) %s" % tuple(
                "%s — %s" % ("green" if facts[k][0] else "RED", facts[k][1]) if facts.get(k) else "not measured"
                for k in ("a", "b")),
            "gate: %s" % ("requested %s at %s; approved by %s at %s via %s" % (
                gate.get("gate_id"), gate.get("requested_at"), gate.get("approved_by") or "-",
                gate.get("approved_at") or "-", gate.get("via") or "-") if gate else "none"),
            "confirm: %s" % (gate.get("confirm") or "none"),
            "handoffs: %d · suite runs: %d · review passes: %d" % (handoffs, state["verify"]["suite_runs"],
                                                                   state["review"]["passes"])]
    return out

def write_task_md(root, state):
    """Rewritten whole and atomically after every change; best effort, because
    the state is the contract and task.md is rendered from it — except
    §Questions, which is read back from disk under the questions lock, so an
    [Answer]: line a human filled survives until `questions --sync` reads it."""
    path = fs.task_md_path(root, state)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with locks.question_lock(path):
            before, _, after = questions.split_task_md(task_md_lines(root, state))
            section = questions.question_lines(path)
            if not any(questions.HEADING_RE.match(line) for line in section):
                section = ["", "none"]
            text = "\n".join(before + section + ([""] if section[-1] else []) + after) + "\n"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
    except Exception as exc:  # pylint: disable=broad-exception-caught  # derived artefact: never fatal
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        print("state.py: task.md not written (%s)" % exc, file=sys.stderr)
