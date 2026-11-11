"""What a regenerate must not overwrite: the old markers, the kept-file check, the old file shapes, the refusal text.

shell: check_kept, old_shapes, kept_refusal
core: tomllib, OLD_MARKERS
"""

import json
import os

try:
    import tomllib
except ImportError:  # Python before 3.11: .codex/config.toml is not checked
    tomllib = None

import render_instructions  # next to the entry, whose directory the entry puts on sys.path

from rr_update import files
from rr_update import paths
from rr_update import siblings


# Old shapes the update no longer converts: literal checks, nothing parsed (D4).
OLD_MARKERS = (b"<!-- claude-agentic:", b"<!-- Codex-agentic:")


def check_kept(root):
    """[(path, reason)] for every kept file its own reader cannot take and every old
    shape this version no longer converts. Reads only: the caller refuses on a
    non-empty answer before anything is written (R12)."""
    bad = []

    def raw_of(rel):
        path = os.path.join(root, rel)
        if not os.path.lexists(path):
            return None
        try:
            return files.read(path)
        except OSError as exc:
            bad.append((rel, "cannot be read: %s" % (exc.strerror or exc)))
            return None

    def json_object(rel, data):
        try:
            doc = json.loads(data.decode("utf-8"))
        except (ValueError, RecursionError) as exc:  # UnicodeDecodeError is a ValueError
            bad.append((rel, "is not valid JSON (%s)" % (type(exc).__name__ if isinstance(exc, RecursionError) else exc)))
            return None
        if not isinstance(doc, dict):
            bad.append((rel, "is not a JSON object"))
            return None
        return doc

    for rel in (paths.STATE_FILE, ".ai/policies/dialog.json", ".ai/policies/memory.json", ".claude/settings.json"):
        data = raw_of(rel)
        if data is not None:
            json_object(rel, data)
    data = raw_of(paths.WEIGHT_PROJECT)
    if data is not None:
        doc = json_object(paths.WEIGHT_PROJECT, data)
        if doc is not None and doc.get("version") != 1:
            bad.append((paths.WEIGHT_PROJECT, "has no \"version\": 1"))
        elif doc is not None:
            try:
                siblings.weight_overlay().load(siblings.shipped_weight(), os.path.join(root, paths.WEIGHT_PROJECT))
            except ValueError as exc:
                bad.append((paths.WEIGHT_PROJECT, str(exc).split(": ", 1)[-1]))
    data = raw_of(paths.VERIFICATION_MD)
    if data is not None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            bad.append((paths.VERIFICATION_MD, "is not UTF-8 text"))
    data = raw_of(".codex/config.toml")
    if data is not None and tomllib is not None:
        try:
            tomllib.loads(data.decode("utf-8"))
        except ValueError as exc:  # TOMLDecodeError and UnicodeDecodeError
            bad.append((".codex/config.toml", "is not valid TOML (%s)" % exc))
    # the old weight.json is read once, by the split, so it must parse then
    if not os.path.lexists(os.path.join(root, paths.WEIGHT_PROJECT)):
        data = raw_of(paths.WEIGHT_JSON)
        if data is not None:
            json_object(paths.WEIGHT_JSON, data)
    old_shapes(root, bad)
    return bad


def old_shapes(root, bad):
    """The four literal detectors of an older riskrails' files (D4)."""
    exists = lambda rel: os.path.lexists(os.path.join(root, rel))  # noqa: E731
    if exists(".ai/state/current.json") and not exists(paths.STATE_FILE):
        bad.append((".ai/state/current.json", "is the task state of a riskrails before 3.4b (there is no state.json)"))
    if exists(".ai/policies/risk-tiers.json") and not exists(paths.WEIGHT_JSON) and not exists(paths.WEIGHT_PROJECT):
        bad.append((".ai/policies/risk-tiers.json", "is the risk-tier policy of a riskrails before 2.2 (there is no weight table)"))
    names = set(render_instructions.RULE_FILE.values()) | {e[0] for e in paths.INSTRUCTION_FILE.values()}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in paths.RULES_SKIP
                             and not os.path.lexists(os.path.join(dirpath, d, ".git")))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            if name not in names and rel not in names:
                continue
            try:
                data = files.read(os.path.join(root, rel))
            except OSError:
                continue  # an unreadable instruction file is the plan's to report, not an old shape
            found = next((m for m in OLD_MARKERS if m in data), None)
            if found:
                bad.append((rel, "carries %s of a riskrails before 3.4b" % found.decode()))


def kept_refusal(bad):
    """I3, verbatim: one line per failing file, then the rest."""
    for rel, why in bad:
        print("KEPT_UNREADABLE: %s: %s" % (rel, why))
    print("project-update: nothing was deleted or written. This version regenerates its own files and no longer "
          "converts older ones.")
    print("Install riskrails@%s (npx riskrails@%s), run /rr-setup --update with it, then install this version "
          "and run /rr-setup --update again." % (paths.LAST_MIGRATING_VERSION, paths.LAST_MIGRATING_VERSION))
    return paths.EXIT_KEPT_UNREADABLE
