"""questions_cmd: the question file's commands -- ask, answer, the sync of hand edits, and the gate closed from its own answer line.

shell: cmd_ask, apply_answers, cmd_answer, sync_answers, cmd_questions, close_gate_from_file
"""
import contextlib
import json
import os
import shlex
import sys

from rr_state import dialog, fs, gate, handoff, journal, locks, task
from rr_state import questions as rr_questions
from rr_state import runtime as rr_runtime


def cmd_ask(args, root, rt=rr_runtime.Runtime()):
    if args.gate:
        # A gate the agent can author is a gate the agent can have signed: the
        # human would approve whichever G was pending last.
        fs.die("a gate is requested by 'state.py close' in full mode, not by ask")
    state = None if args.topic else task.load(root, rt=rt)
    path = fs.questions_path(root, state, args.topic)
    stage = "intent" if args.topic else state["current_stage"]
    asked = []
    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as fh:
                batch = json.load(fh)
        except (OSError, ValueError, RecursionError) as exc:
            fs.die("cannot read batch file %s (%s)" % (args.batch, exc))
        if not isinstance(batch, list) or not batch:
            fs.die("the batch file must contain a non-empty JSON array")
        for item in batch:
            if not isinstance(item, dict):
                fs.die("every batch item must be an object with question and options")
            options = item.get("options") or []
            if not all(isinstance(o, dict) and "key" in o and "text" in o for o in options):
                fs.die("every option needs a key and a text (%r)" % item.get("question"))
            asked.append({"question": item.get("question"),
                          "options": [(o["key"], o["text"]) for o in options],
                          "recommend": item.get("recommend"), "context": item.get("context")})
    else:
        if not args.question:
            fs.die("ask takes a question, or --batch FILE.json")
        options, letters = [], "ABCDEFGHIJKLMNOPQRSTUVW"
        for option in args.option:
            # Collapsed first: a key is only recognisable once the value is one
            # line, and one line is what the file will hold either way.
            option = fs.one_line(option)
            if len(options) >= len(letters):
                fs.die("a question takes at most %d options" % len(letters))
            head = rr_questions.OPTION_INPUT_RE.match(option)
            if head:
                options.append((head.group(1), head.group(2).strip()))
                continue
            labelled = rr_questions.OPTION_HEAD_RE.match(option)
            if labelled:
                # "1: one" or "aa: one" is a key the I2 grammar cannot parse, not
                # an option whose text happens to start that way.
                fs.die("an option key is one letter A–W, not %r" % labelled.group(1))
            options.append((letters[len(options)], option))
        asked.append({"question": args.question, "options": options,
                      "recommend": args.recommend, "context": args.context})
    for item in asked:
        if not item["question"]:
            fs.die("every question needs a question line")
        if len(item["options"]) < 2:
            fs.die("a question needs at least two options (%r has %d)"
                % (item["question"], len(item["options"])))
        keys = [key for key, _ in item["options"]]
        # An option the I2 grammar cannot parse would round-trip as no option at
        # all, and the answer to it would be recorded as free text (R1).
        for key in keys:
            if not rr_questions.OPTION_KEY_RE.match(key):
                fs.die("an option key is one letter A–W, not %r" % key)
        if len(set(keys)) != len(keys):
            fs.die("option keys must be distinct (%s)" % ", ".join(keys))
        for _, text in item["options"]:
            if text.endswith(" (recommended)"):
                fs.die("an option text cannot end with ' (recommended)' — use --recommend")
        if item["recommend"] and item["recommend"] not in keys:
            fs.die("--recommend %s is not one of the options (%s)"
                % (item["recommend"], ", ".join(keys)))

    new_ids = []
    with locks.question_lock(path):
        lines, existing = rr_questions.parse_questions(path)
        while lines and not lines[-1].strip():
            lines.pop()
        lines = rr_questions.with_preamble(path, lines, args.topic or state["task_id"])
        kind = "G" if args.gate else "Q"
        number = max([q["number"] for q in existing if q["kind"] == kind] or [0])
        for item in asked:
            number += 1
            item["id"] = "%s%d" % (kind, number)
            if args.gate:
                item["question"] = "%s (gate: %s)" % (item["question"], args.gate)
            new_ids.append(item["id"])
            lines.extend(rr_questions.question_block(item, stage, args.by))
        rr_questions.write_questions(path, lines)
        lines, questions = rr_questions.parse_questions(path)
    relative = os.path.relpath(path, root)
    if state is not None:
        for item in asked:
            journal.emit(root, state, "question_asked", "%s: %s" % (item["id"], item["question"]),
                 {"id": item["id"], "options": [letter for letter, _ in item["options"]],
                  "recommended": item["recommend"], "gate": args.gate}, rt=rt)
        rr_questions.set_pending(root, state, questions, path)
        handoff.write_handoff(root, state, "stage", rt=rt)
        task.save(root, state)
    print("%s asked → %s" % (" ".join(new_ids), relative))
    for line in rr_questions.render_prose([q for q in questions if rr_questions.is_pending(q)]):
        print(line)
    for item in asked if state is not None else []:
        # A question with at most three options fits the dialog beside "Not now";
        # a longer one stays on the file route (R36.3).
        if len(item["options"]) <= 3:
            dialog.offer_decision(root, state, "question", item["id"],
                           "%s%s" % (item["question"], "\ncontext: %s" % item["context"] if item.get("context") else ""),
                           [{"kind": "choice", "effect": "defer", "label": "Not now — leave it pending"}] +
                           [{"kind": "choice", "effect": "answer", "answer": key,
                             "label": "%s — %s" % (key, fs.one_line(text, 100)),
                             "description": "%s%s" % (fs.one_line(text, 300),
                                                      " (recommended)" if key == item.get("recommend") else "")}
                            for key, text in item["options"]], "ask", rt=rt, question_id=item["id"])
    if fs.ai_unattended():
        # The literal line an unattended launcher greps for (R5).
        print("WAITING_FOR_ANSWERS %s %s" % (relative, " ".join(new_ids)))


def apply_answers(lines, by_id, assignments, args, relative):
    for qid, choice, text in assignments:
        question = by_id.get(qid)
        if question is None:
            fs.die("no question %s in %s (have: %s)" % (qid, relative, ", ".join(by_id) or "none"))
        if question["kind"] == "G":
            fs.die("%s is a gate: run 'state.py approve' in your terminal or fill its [Answer]: line" % qid)
        letters = [letter for letter, _ in question["options"]]
        if question["other"]:
            letters.append("X")
        if choice is None:
            choice = "X" if question["other"] else None
        if choice not in letters:
            fs.die("%s: invalid choice %r (options: %s)" % (qid, choice, ", ".join(letters)))
        lines[question["answer_at"]] = rr_questions.answer_line(choice, text, args.by, args.via)


def cmd_answer(args, root, rt=rr_runtime.Runtime()):
    state = None if args.topic else task.load(root, rt=rt)
    path = fs.questions_path(root, state, args.topic)
    with locks.question_lock(path):
        lines, questions = rr_questions.parse_questions(path)
        if not questions:
            fs.die("no questions in %s" % os.path.relpath(path, root))
        by_id = {q["id"]: q for q in questions}
        assignments = []
        if args.prose:
            assignments = rr_questions.parse_prose(args.prose, by_id)
        for token in args.assignment:
            assignments.append(rr_questions.parse_assignment(token))
        if not assignments:
            fs.die("answer takes Q1=B …, or --prose \"1B 2A 3: text\"")
        apply_answers(lines, by_id, assignments, args, os.path.relpath(path, root))
        rr_questions.write_questions(path, lines)
        lines, questions = rr_questions.parse_questions(path)
        by_id = {q["id"]: q for q in questions}
    if state is not None:
        for qid, _, _ in assignments:
            question = by_id[qid]
            # actor is derived from the route, never asserted by the caller:
            # `human` is reserved for the file route and the gate (I3).
            journal.emit(root, state, "question_answered", "%s = %s" % (qid, question["choice"]),
                 {"id": qid, "choice": question["choice"], "text": question["text"],
                  "via": args.via, "by": args.by}, actor="agent", rt=rt)
        rr_questions.set_pending(root, state, questions, path)
        handoff.write_handoff(root, state, "stage", rt=rt)
        task.save(root, state)
    pending = [q["id"] for q in questions if rr_questions.is_pending(q)]
    print("%s answered; %s" % (", ".join(qid for qid, _, _ in assignments),
                               ("still pending: " + ", ".join(pending)) if pending else "none pending"))


def sync_answers(root, state, path, lines, questions, args, rt=rr_runtime.Runtime()):
    """Pick up hand edits: a filled line with no trailer is a fresh answer, a
    line this command already wrote has one, so syncing twice changes nothing."""
    changed, gates = [], []
    for question in questions:
        if question["invalid"]:
            print("state.py: %s: invalid choice %r — it stays pending"
                  % (question["id"], question["invalid"]), file=sys.stderr)
            continue
        if question["kind"] == "G":
            # A gate is not answered, it is granted or rejected: a filled answer
            # on the open gate goes through the file route, and any other G block
            # is left exactly as it is rather than consumed.
            if (state is not None and question["id"] == task.open_gate(state)
                    and question["choice"] and not question["answered_by"] and not gates):
                if question["choice"] not in ("A", "B"):
                    # A gate has two answers. Free text — the likeliest thing a
                    # human writes into a question file — must not be read as a
                    # rejection with their own approving sentence as the reason.
                    print("state.py: %s is the approval gate: answer it A or B, not %r"
                          % (question["id"], question["text"] or question["choice"]),
                          file=sys.stderr)
                    continue
                gates.append(question)
            continue
        if question["choice"] is not None and not question["answered_by"]:
            lines[question["answer_at"]] = rr_questions.answer_line(
                question["choice"], question["text"], args.by, "file")
            changed.append(question)
    if not changed:
        return gates
    if state is not None:
        # Recording answers changes the task, so it takes ownership as ask does.
        task.claim_runtime(root, state, rt=rt)
    rr_questions.write_questions(path, lines)
    if state is not None:
        by_id = {q["id"]: q for q in rr_questions.parse_questions(path)[1]}
        for question in changed:
            if question["kind"] == "G":
                continue                          # the gate's file route is step 6's
            current = by_id[question["id"]]
            journal.emit(root, state, "question_answered", "%s = %s" % (current["id"], current["choice"]),
                 {"id": current["id"], "choice": current["choice"], "text": current["text"],
                  "via": "file", "by": args.by}, actor="human", rt=rt)
    return changed + gates


def cmd_questions(args, root, rt=rr_runtime.Runtime()):
    state = None if args.topic else task.load(root, rt=rt)
    path = fs.questions_path(root, state, args.topic)
    granted, touched = None, []
    with locks.question_lock(path) if args.sync else contextlib.nullcontext():
        lines, questions = rr_questions.parse_questions(path)
        if args.sync:
            touched = sync_answers(root, state, path, lines, questions, args, rt=rt)
        if state is not None and touched:
            # Persisted before the gate is evaluated, because a refusal there
            # exits 5 and never returns: the answers this sync already wrote
            # into the file must be in the state and the history too.
            # Only a sync that changed something writes at all — questions.pending
            # is a cache, and guard_pending re-parses the file anyway, so a read
            # (which /rr-status and the session-start hook both perform) never
            # races a command that is mid-write.
            _, questions = rr_questions.parse_questions(path)
            rr_questions.set_pending(root, state, questions, path)
            task.save(root, state)
        for question in [q for q in touched if q["kind"] == "G"]:
            granted = close_gate_from_file(root, state, question, args.by, rt=rt)
        if touched:
            _, questions = rr_questions.parse_questions(path)
            if state is not None:
                rr_questions.set_pending(root, state, questions, path)
                task.save(root, state)
    if granted is not None:
        print("gate %s by %s via the file" % ("approved" if granted else "rejected", args.by))
    shown = [q for q in questions if rr_questions.is_pending(q)] if args.pending else questions
    for line in rr_questions.render_questions(shown, args.format):
        print(line)


def close_gate_from_file(root, state, question, by, rt=rr_runtime.Runtime()):
    """R13: an [Answer]: filled into the gate's own question grants or rejects,
    but only behind a human turn in the session the plan was presented in — or
    AI_UNATTENDED, which says there is nobody to take one.

    The whole decision happens inside the questions lock and on a state re-read,
    because the human may be typing `reject` in their terminal in exactly these
    seconds: deciding before the lock and applying after it would overwrite them.
    """
    gate_id = question["id"]
    unattended = fs.ai_unattended()
    with locks.question_lock(fs.questions_path(root, state, None)):
        fresh = task.load(root, claim=False, rt=rt)
        if task.open_gate(fresh) != gate_id:
            # Somebody closed it between the parse and here: their outcome wins.
            return None
        state.clear()
        state.update(fresh)
        seen, why = (True, "") if unattended else dialog.human_turn(root, state)
        if not seen:
            fs.die("APPROVAL_REFUSED — %s. Fill the answer, tell the session, and sync again, or run "
                "in your own terminal:\n  python3 %s --root %s approve --by %s"
                % (why, shlex.quote(fs.ENTRY), shlex.quote(root),
                   shlex.quote(by)), 5)
        approved = question["choice"] == "A"
        session = fs.read_session(root)
        task.claim_runtime(root, state, rt=rt)
        state["human_approval"].update({
            "required": True, "granted": approved,
            "granted_by": by if approved else None,
            "granted_at": fs.now() if approved else None,
            "requested_at": None, "gate_id": None, "requested_session": None,
            "via": "file" if approved else None, "unattended": approved and unattended,
        })
        if approved:
            state["human_approval"]["rejected_at"] = None
        if approved:
            journal.record(state, "human_approval", "granted by %s via file" % by)
        else:
            state["next_action"] = "address the rejection: %s" % fs.one_line(question["text"])
            state["human_approval"]["rejected_at"] = fs.now()
            journal.record(state, "gate_rejected", "%s: %s" % (by, question["text"] or "no reason given"))
        handoff.write_handoff(root, state, "stage", rt=rt)
        task.save(root, state)                 # durable first: the answer line is derived
        # The evidence, recorded beside the outcome: this is the weakest of the
        # three routes, and an audit has to be able to see what it rested on.
        evidence = {"session": session.get("last_prompt_session"),
                    "at": session.get("last_prompt_at"), "unattended": unattended}
        journal.append_journal(root, state["task_id"], journal.journal_line(
            state["task_id"], "gate_approved" if approved else "gate_rejected",
            "human" if not unattended else "agent",
            state.get("current_stage"), "%s by %s via file" % (gate_id, by),
            {"by": by, "gate_id": gate_id, "via": "file", "unattended": unattended,
             "tty": False, "evidence": evidence}
            if approved else {"by": by, "gate_id": gate_id, "why": question["text"],
                              "via": "file", "evidence": evidence}, runtime=rt.name))
        gate.close_gate(root, state, gate_id, question["choice"], question["text"], by, "file")
        task.save(root, state)
    return approved
