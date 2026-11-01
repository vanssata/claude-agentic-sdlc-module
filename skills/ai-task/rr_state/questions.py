"""questions: the questions file — its regexes and constants, how it is parsed, rendered and written.

shell: question_lines, parse_questions, write_questions, answer_line, question_block, parse_prose, prose_id, parse_assignment, set_pending
core: QUESTIONS_HEADER, TASK_QUESTIONS_NOTE, QUESTIONS_SECTION, OTHER_OPTION, HEADING_RE, OPTION_RE, OTHER_RE, ANSWER_RE, META_RE, CONTEXT_RE, VIA_VALUES, TRAILER_RE, CHOICE_RE, CHOICE_TEXT_RE, OTHER_TEXT_RE, LETTER_RE, PROSE_CHOICE_RE, PROSE_TEXT_RE, OPTION_INPUT_RE, OPTION_KEY_RE, OPTION_HEAD_RE, in_task_md, split_task_md, with_preamble, parse_answer_body, is_pending, render_prose, render_md, render_questions, unquote
"""

import json
import os
import re

from rr_state import fs


# The questions are written by state.py and never by a model (R1). One regex
# per line (I2), so a hand edit that keeps the shape round-trips exactly. A
# task's questions live in task.md §Questions (R7, R8); a topic's in its own file.
QUESTIONS_HEADER = """# Questions — %s
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->
"""
TASK_QUESTIONS_NOTE = """<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->"""
QUESTIONS_SECTION = "## Questions"
OTHER_OPTION = "X. Other — answer as `X: <text>`"
HEADING_RE = re.compile(r"^## (Q|G)(\d+)\. (.+)$")
OPTION_RE = re.compile(r"^([A-W])\. (.+?)( \(recommended\))?$")
OTHER_RE = re.compile(r"^X\. Other")
ANSWER_RE = re.compile(r"^\[Answer\]:\s*(.*)$")
META_RE = re.compile(r"^asked: (\S+) · stage: (\S+)(?: · by: (.+))?$")
CONTEXT_RE = re.compile(r"^context: (.+)$")
# The trailer must be a suffix free text cannot produce: a closed `via`
# vocabulary, an exact timestamp, and a name that cannot span another em dash —
# otherwise `X: we chose Adyen — by the way it is cheaper` eats its own answer.
VIA_VALUES = "picker|prose|file|terminal|unattended|dialog"
TRAILER_RE = re.compile(
    r"\s+—\s+by ([^—]+?) via (%s) at (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$" % VIA_VALUES)
CHOICE_RE = re.compile(r"^[A-W]$")
CHOICE_TEXT_RE = re.compile(r"^([A-W])\s*[—:-]\s*(.+)$")
OTHER_TEXT_RE = re.compile(r"^X\s*:\s*(.+)$")
LETTER_RE = re.compile(r"^[A-Z]$")
PROSE_CHOICE_RE = re.compile(r"\b(\d+)\s*([A-W])\b")
PROSE_TEXT_RE = re.compile(r"\b(\d+)\s*:")
OPTION_INPUT_RE = re.compile(r"^([A-W])\s*[:.]\s*(.+)$")
OPTION_KEY_RE = re.compile(r"^[A-W]$")
OPTION_HEAD_RE = re.compile(r"^([A-Za-z0-9]{1,3})\s*[:.]\s")


def in_task_md(path):
    return os.path.basename(path) == "task.md"


def split_task_md(lines):
    """task.md as (before, section, after): `before` ends with the §Questions
    heading, `section` runs to the next `## ` heading that is not a question's.
    No heading: everything is `before` and the section is None."""
    try:
        start = lines.index(QUESTIONS_SECTION) + 1
    except ValueError:
        return lines, None, []
    end = start
    while end < len(lines) and not (lines[end].startswith("## ") and not HEADING_RE.match(lines[end])):
        end += 1
    return lines[:start], lines[start:end], lines[end:]


def question_lines(path):
    """The lines the questions live in. For task.md that is §Questions only; a
    task started before the fold may still hold its questions in questions.md
    beside it, which is read until the first write carries them into task.md."""
    lines = fs.read_lines(path)
    if not in_task_md(path):
        return lines or []
    section = split_task_md(lines or [])[1] or []
    if not any(HEADING_RE.match(line) for line in section):
        legacy = fs.read_lines(os.path.join(os.path.dirname(path), "questions.md"))
        if legacy and any(HEADING_RE.match(line) for line in legacy):
            first = next(i for i, line in enumerate(legacy) if HEADING_RE.match(line))
            return [""] + TASK_QUESTIONS_NOTE.split("\n") + [""] + legacy[first:]
    return section


def with_preamble(path, lines, name):
    """An existing but empty (or header-less) question store still gets the
    notice that tells a human not to edit the questions."""
    if in_task_md(path):
        if not any(line.startswith("<!-- Written by state.py") for line in lines):
            lines = [""] + TASK_QUESTIONS_NOTE.split("\n") + [line for line in lines
                                                              if line.strip() not in ("", "none")]
        return lines
    if not any(line.startswith("# Questions") for line in lines):
        lines = (QUESTIONS_HEADER % name).rstrip("\n").split("\n") + lines
    return lines


def parse_answer_body(question, body):
    """`LETTER`, `LETTER: text`, `X: text` or bare text, with the trailer this
    command writes parsed back off the end and ignored (I2)."""
    question["choice"] = question["text"] = None
    question["invalid"] = None
    trailer = TRAILER_RE.search(body)
    if trailer:
        question["answered_by"], question["via"], question["answered_at"] = trailer.groups()
        body = body[:trailer.start()]
    body = body.strip()
    if not body:
        return
    letters = [letter for letter, _ in question["options"]]
    if question["other"]:
        letters.append("X")
    other = OTHER_TEXT_RE.match(body)
    pair = CHOICE_TEXT_RE.match(body)
    if other:
        choice, text = "X", other.group(1).strip()
    elif pair:
        choice, text = pair.group(1), pair.group(2).strip()
    elif CHOICE_RE.match(body) or LETTER_RE.match(body):
        choice, text = body, None
    else:
        choice, text = ("X" if question["other"] else None), body
    if choice is not None and choice not in letters:
        question["invalid"] = choice
        return
    question["choice"], question["text"] = choice, text


def parse_questions(path):
    """One regex per line (I2). Returns the store's lines beside the questions, so
    a writer can replace an [Answer]: line and leave every other byte alone."""
    lines = question_lines(path)
    questions, current = [], None
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading:
            current = {
                "id": heading.group(1) + heading.group(2), "kind": heading.group(1),
                "number": int(heading.group(2)), "question": heading.group(3),
                "asked": None, "stage": None, "by": None, "context": None,
                "options": [], "recommend": None, "other": False,
                "answer_at": None, "choice": None, "text": None, "invalid": None,
                "answered_by": None, "via": None, "answered_at": None,
            }
            questions.append(current)
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
            current["answer_at"] = index
            parse_answer_body(current, answer.group(1))
            current = None                # the block ends at its answer line
            continue
        if OTHER_RE.match(line):
            current["other"] = True
            continue
        option = OPTION_RE.match(line)
        if option:
            current["options"].append((option.group(1), option.group(2)))
            if option.group(3):
                current["recommend"] = option.group(1)
    return lines, questions


def is_pending(question):
    return question["choice"] is None


def write_questions(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if in_task_md(path):
        # Only §Questions is replaced; the other sections stay as rendered.
        before, section, after = split_task_md(fs.read_lines(path) or [])
        lines = lines + ([""] if lines and lines[-1] else [])
        if section is not None:
            lines = before + lines + after
        else:
            lines = before + (["", QUESTIONS_SECTION] if before else [QUESTIONS_SECTION]) + lines
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp, path)


def answer_line(choice, text, by, via):
    text = fs.one_line(text)
    if TRAILER_RE.search(text):
        # An answer that ends in the trailer's exact shape would re-parse as
        # somebody else's; the em dash is the anchor, so it goes.
        text = text.replace("—", "-")
    by = fs.one_line(by).replace("—", "-")
    if choice and text:
        body = "%s: %s" % (choice, text)
    elif choice:
        body = choice
    else:
        body = text
    return "[Answer]: %s — by %s via %s at %s" % (body, by or "unknown", via, fs.now())


def question_block(question, stage, by):
    by = fs.one_line(by)
    block = ["", "## %s. %s" % (question["id"], fs.one_line(question["question"])),
             "asked: %s · stage: %s%s" % (fs.now(), stage, " · by: " + by if by else "")]
    if question.get("context"):
        block.append("context: %s" % fs.one_line(question["context"]))
    for letter, text in question["options"]:
        block.append("%s. %s%s" % (letter, fs.one_line(text),
                                   " (recommended)" if letter == question.get("recommend") else ""))
    block.append(OTHER_OPTION)
    block.append("[Answer]:")
    return block


def render_prose(questions):
    """The rendering every runtime can show. The number is the question's own id
    number, so the same reply means the same thing whenever it is given."""
    out = []
    for question in questions:
        answered = "" if is_pending(question) else "  — answered: %s" % question["choice"]
        out.append("%s. %s  [%s]%s"
                   % (question["number"], question["question"], question["id"], answered))
        if question["context"]:
            out.append("   context: %s" % question["context"])
        for letter, text in question["options"]:
            out.append("   %s. %s%s" % (letter, text,
                                        " (recommended)" if letter == question["recommend"] else ""))
        if question["other"]:
            out.append("   X. Other — answer as `X: <text>`")
    pending = [q for q in questions if is_pending(q)]
    if pending:
        out.append("Reply `%s`, a free-text answer last, or run: state.py answer %s"
                   % (" ".join("%s<letter>" % q["number"] for q in pending),
                      " ".join("%s=<letter>" % q["id"] for q in pending)))
    return out


def render_md(questions):
    out = []
    for question in questions:
        if is_pending(question):
            out.append("- **%s** — _unanswered_ (%s)" % (question["question"], question["id"]))
            continue
        chosen = dict(question["options"]).get(question["choice"], question["text"] or "Other")
        detail = "%s — %s" % (chosen, question["text"]) if question["text"] and question["choice"] != "X" else chosen
        out.append("- **%s** — %s *(%s, %s)*" % (
            question["question"], detail, question["id"],
            "by %s via %s at %s" % (question["answered_by"], question["via"], question["answered_at"])
            if question["answered_by"] else "answered"))
    return out


def render_questions(questions, fmt):
    if fmt == "json":
        shown = []
        for question in questions:
            item = {k: v for k, v in question.items() if k != "answer_at"}
            item["options"] = [{"key": k, "text": t} for k, t in question["options"]]
            item["pending"] = is_pending(question)
            shown.append(item)
        return [json.dumps(shown, ensure_ascii=False, indent=2)]
    if fmt == "md":
        return render_md(questions)
    return render_prose(questions)


def parse_prose(text, by_id):
    """`3B` is a choice for Q3, `3: …` is free text for Q3.

    The number is the question's own id number, not its position in a rendering
    — a rendering the human saw yesterday must not answer a different question
    today. Free text runs to the end of the reply, because a sentence may
    legitimately contain `2B` or `step 2:` and half an answer is worse than a
    refusal; so a free-text answer comes last.
    """
    assignments = []
    start = PROSE_TEXT_RE.search(text)
    head = text[:start.start()] if start else text
    for token in PROSE_CHOICE_RE.finditer(head):
        assignments.append((prose_id(int(token.group(1)), by_id), token.group(2), None))
    if start:
        assignments.append((prose_id(int(start.group(1)), by_id), "X",
                            text[start.end():].strip()))
    if not assignments:
        fs.die("no answers found in %r — reply like `1B 2A 3: free text`" % text)
    return assignments


def prose_id(number, by_id):
    qid = "Q%d" % number
    if qid not in by_id:
        fs.die("prose answer %d has no question (have: %s)"
            % (number, ", ".join(i for i in by_id if i.startswith("Q")) or "none"))
    return qid


def unquote(text):
    """I1 writes the free-text form as X:"free text"; the quotes belong to the
    body and are stripped only as a matching pair."""
    text = text.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_assignment(token):
    """Q1=B, Q2=X:free text, Q3=B: because."""
    if "=" not in token:
        fs.die("answer takes Q1=B, not %r" % token)
    qid, value = token.split("=", 1)
    value = value.strip()
    other = OTHER_TEXT_RE.match(value)
    if other:
        return (qid.strip(), "X", unquote(other.group(1)))
    pair = CHOICE_TEXT_RE.match(value)
    if pair:
        return (qid.strip(), pair.group(1), unquote(pair.group(2)))
    # A bare letter is a choice even when it is not one of the options, so a
    # typo is refused rather than silently recorded as free text.
    if LETTER_RE.match(value):
        return (qid.strip(), value, None)
    return (qid.strip(), None, unquote(value))


def set_pending(root, state, questions, path):
    """questions.pending is a cache; the file is the truth (spec alternative 4)."""
    state["questions"] = {
        "file": os.path.relpath(path, root),
        "pending": [q["id"] for q in questions if is_pending(q)],
    }
