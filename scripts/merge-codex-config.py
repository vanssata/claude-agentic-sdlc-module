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

Safety contract: the file is parsed before and after the edit, and the write is
abandoned unless the *only* difference between the two parses is inside that
managed set. A prose key name inside a multi-line string cannot slip through
that check, because it would show up as an unexpected difference.

  merge-codex-config.py <config.toml> --profile <codex-plus.json|codex-pro.json> [--dry-run] [--no-backup]
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
TABLE_HEADER = re.compile(r"^\s*\[")


def die(message):
    print(f"merge-codex-config: {message}", file=sys.stderr)
    sys.exit(1)


def toml_value(value):
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
