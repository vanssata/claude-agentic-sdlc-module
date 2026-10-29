#!/usr/bin/env python3
"""Set the managed routing keys in ~/.codex/config.toml, and nothing else.

``config.toml`` is the user's file: it holds MCP servers, marketplaces, project
trust levels, plugin state and their comments. There is no comment-preserving
TOML writer in the standard library, so this edits the text surgically rather
than round-tripping the document — a round-trip would silently reformat the file
and drop every comment in it.

Exactly five keys are managed:

    model                                  (top level)
    model_reasoning_effort                 (top level)
    agents.enabled
    agents.default_subagent_model
    agents.default_subagent_reasoning_effort
    agents.max_concurrent_threads_per_session

and, with ``--status-context yes``, ``tui.status_line``: ``model-with-reasoning``
and ``context-used`` are appended to a list the user set, when missing; the user's
items are never removed or reordered. An unset key (Codex's own default items) and
an empty list are left alone, with a note: writing ours would replace either.
``--status-context no`` (the default) leaves the list alone.

Safety contract: the file is parsed before and after the edit, and the write is
abandoned unless the *only* difference between the two parses is inside that
managed set. A prose key name inside a multi-line string cannot slip through
that check, because it would show up as an unexpected difference.

  merge-codex-config.py <config.toml> --profile <codex-plus.json|codex-pro.json> [--dry-run] [--no-backup]
                        [--status-context yes|no]
"""
import argparse
import json
import os
import re
import sys
import tomllib

MANAGED_TOP = ("model", "model_reasoning_effort")
MANAGED_AGENTS = (
    "enabled",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
    "max_concurrent_threads_per_session",
)
STATUS_ITEMS = ("model-with-reasoning", "context-used")  # Codex 0.165 [tui] status_line ids
TABLE_HEADER = re.compile(r"^\s*\[")


def die(message):
    print(f"merge-codex-config: {message}", file=sys.stderr)
    sys.exit(1)


def toml_value(value):
    if isinstance(value, list):
        return "[%s]" % ", ".join(toml_value(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def key_line(lines, start, end, key):
    """Index of the assignment for `key` between [start, end), or None."""
    pattern = re.compile(r"^\s*(?:%s|\"%s\"|'%s')\s*=" % (re.escape(key), re.escape(key), re.escape(key)))
    for i in range(start, end):
        if pattern.match(lines[i]):
            return i
    return None


def top_level_end(lines):
    for i, line in enumerate(lines):
        if TABLE_HEADER.match(line):
            return i
    return len(lines)


def table_span(lines, name):
    """(header index, end index) of [name], or None. Sub-tables are not it."""
    header = re.compile(r"^\s*\[\s*(?:%s|\"%s\")\s*\]\s*$" % (re.escape(name), re.escape(name)))
    for i, line in enumerate(lines):
        if header.match(line):
            for j in range(i + 1, len(lines)):
                if TABLE_HEADER.match(lines[j]):
                    return i, j
            return i, len(lines)
    return None


def set_in_span(lines, start, end, key, value, changes):
    """Replace or insert `key = value` inside [start, end). Returns the new end."""
    rendered = "%s = %s" % (key, toml_value(value))
    at = key_line(lines, start, end, key)
    if at is not None:
        if lines[at].strip() != rendered:
            changes.append("set %s (was: %s)" % (rendered, lines[at].strip()))
            lines[at] = rendered
        return end
    # Insert after the last non-blank line of the span, so a trailing blank line
    # separating this table from the next one stays where it is.
    insert = end
    while insert > start and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, rendered)
    changes.append("added %s" % rendered)
    return end + 1


def value_end(lines, at):
    """One past the last line of the value assigned on line `at` (an array may span lines)."""
    chunk = lines[at].split("=", 1)[1]
    for j in range(at, len(lines)):
        if j > at:
            chunk += "\n" + lines[j]
        try:
            tomllib.loads("v = " + chunk)
            return j + 1
        except tomllib.TOMLDecodeError:
            continue
    return None


def status_items(lines, before, changes, notes):
    """Append STATUS_ITEMS to the user's [tui] status_line where missing; the user's
    items keep their order. Returns the wanted list, or None when nothing is to change,
    the key is unset or empty, or it lives somewhere this edit does not reach."""
    current = before.get("tui.status_line")
    if current is None or current == []:
        # Unset is Codex's own default set, and [] a deliberate empty line: writing
        # our two items would replace either.
        notes.append("left [tui] status_line alone (%s; add %s to show them)"
                     % ("not set: Codex's default items" if current is None else "empty on purpose",
                        " and ".join(STATUS_ITEMS)))
        return None
    if not isinstance(current, list):
        return None
    missing = [item for item in STATUS_ITEMS if item not in current]
    if not missing:
        return None
    value = current + missing
    rendered = "status_line = %s" % toml_value(value)
    span = table_span(lines, "tui")
    at = key_line(lines, span[0] + 1, span[1], "status_line") if span else None
    if at is None:
        notes.append("left [tui] status_line alone (not a status_line key in a [tui] table)")
        return None
    end = value_end(lines, at)
    if end is None:
        return None
    was = " ".join(line.strip() for line in lines[at:end])
    kept = append_items(lines[at:end], missing)
    try:
        ok = kept is not None and tomllib.loads("\n".join(kept))["status_line"] == value
    except (tomllib.TOMLDecodeError, KeyError):
        ok = False
    # The user's own lines and comments stay; one rendered line only when they cannot.
    lines[at:end] = kept if ok else [rendered]
    changes.append("set [tui] %s (was: %s)" % (rendered, was))
    return value


def array_marks(block):
    """(line, col) of the closing ] of the array assigned on block[0], and of the last
    character before it outside strings, comments and blanks; None for an array this
    scan does not read (nested, or a multi-line string)."""
    row, col = 0, block[0].index("=") + 1
    depth, last, quote = 0, None, None
    while row < len(block):
        line = block[row]
        while col < len(line):
            ch = line[col]
            if quote:
                if quote == '"' and ch == "\\":
                    col += 2
                    continue
                if ch == quote:
                    quote = None
                    last = (row, col)
            elif ch in "\"'":
                if line.startswith(ch * 3, col):
                    return None
                quote = ch
            elif ch == "#":
                break
            elif ch == "[":
                depth += 1
                if depth > 1:
                    return None
                last = (row, col)
            elif ch == "]":
                return (row, col), last
            elif not ch.isspace():
                last = (row, col)
            col += 1
        if quote:
            return None
        row, col = row + 1, 0
    return None


def append_items(block, items):
    """The lines of `block` (one `status_line = [...]` assignment) with `items` added
    before its closing ], comments and layout kept; None when the scan cannot place them."""
    marks = array_marks(block)
    if marks is None or marks[1] is None:
        return None
    (row, col), (lrow, lcol) = marks
    out = list(block)
    comma = block[lrow][lcol] not in ",["
    if block[row][:col].strip():
        # ] shares its line with an item: `["a"]  # c` → `["a", "x", "y"]  # c`.
        joined = ", ".join(toml_value(item) for item in items)
        lead = ", " if comma else ("" if block[lrow][lcol] == "[" else " ")
        out[row] = out[row][:col] + lead + joined + out[row][col:]
    else:
        # ] on its own line: one `"item",` line each, at the last item's indentation.
        indent = re.match(r"\s*", block[lrow]).group(0) if lrow > 0 else re.match(r"\s*", block[row]).group(0) + "  "
        out[row:row] = ["%s%s," % (indent, toml_value(item)) for item in items]
        if comma:
            out[lrow] = out[lrow][:lcol + 1] + "," + out[lrow][lcol + 1:]
    return out


def flatten(data, prefix=""):
    out = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--status-context", choices=("yes", "no"), default="no")
    args = parser.parse_args()

    try:
        with open(args.profile, encoding="utf-8") as fh:
            profile = json.load(fh)
    except (OSError, ValueError) as exc:
        die(f"cannot read {args.profile}: {exc}")

    session = profile["session"]
    agents = profile["agents"]
    wanted = {
        "model": session["model"],
        "model_reasoning_effort": session["model_reasoning_effort"],
    }
    wanted.update({"agents.%s" % k: agents[k] for k in MANAGED_AGENTS if k in agents})

    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as fh:
            original = fh.read()
    else:
        original = ""
    try:
        before = flatten(tomllib.loads(original))
    except tomllib.TOMLDecodeError as exc:
        die(f"{args.config} is not valid TOML ({exc}); left alone")

    lines = original.split("\n")
    trailing_newline = original.endswith("\n") or original == ""
    if trailing_newline and lines and lines[-1] == "":
        lines.pop()
    changes = []

    end = top_level_end(lines)
    # New top-level keys go after any leading comment block and before the first
    # table header: below a header TOML would read them as that table's members.
    insert = 0
    while insert < end and (not lines[insert].strip() or lines[insert].lstrip().startswith("#")):
        insert += 1
    for key in MANAGED_TOP:
        at = key_line(lines, 0, end, key)
        rendered = "%s = %s" % (key, toml_value(wanted[key]))
        if at is not None:
            if lines[at].strip() != rendered:
                changes.append("set %s (was: %s)" % (rendered, lines[at].strip()))
                lines[at] = rendered
        else:
            lines.insert(insert, rendered)
            changes.append("added %s" % rendered)
            insert += 1
            end += 1

    span = table_span(lines, "agents")
    if span is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[agents]")
        changes.append("added [agents]")
        start, stop = len(lines) - 1, len(lines)
    else:
        start, stop = span[0], span[1]
    for key in MANAGED_AGENTS:
        if "agents.%s" % key not in wanted:
            continue
        stop = set_in_span(lines, start + 1, stop, key, wanted["agents.%s" % key], changes)

    notes = []
    if args.status_context == "yes":
        status = status_items(lines, before, changes, notes)
        if status is not None:
            wanted["tui.status_line"] = status

    text = "\n".join(lines)
    if trailing_newline or text:
        text = text.rstrip("\n") + "\n"

    try:
        after = flatten(tomllib.loads(text))
    except tomllib.TOMLDecodeError as exc:
        die(f"the edited config would not parse ({exc}); {args.config} left alone")

    unexpected = sorted(
        key for key in set(before) | set(after)
        if before.get(key, object()) != after.get(key, object()) and key not in wanted
    )
    if unexpected:
        die("refusing to write: the edit would also change %s" % ", ".join(unexpected))
    for key, value in wanted.items():
        if after.get(key) != value:
            die(f"refusing to write: {key} did not end up as {value!r}")

    for note in notes:
        print("codex config: %s" % note)
    if not changes:
        print("codex config: already set (model=%s, effort=%s)" % (wanted["model"], wanted["model_reasoning_effort"]))
        return 0
    if args.dry_run:
        for change in changes:
            print("codex config: would have %s" % change)
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(args.config)) or ".", exist_ok=True)
    if original and not args.no_backup:
        with open(args.config + ".bak", "w", encoding="utf-8") as fh:
            fh.write(original)
        print("backup: config.toml -> config.toml.bak")
    tmp = "%s.%d.tmp" % (args.config, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, args.config)
    for change in changes:
        print("codex config: %s" % change)
    return 0


if __name__ == "__main__":
    sys.exit(main())
