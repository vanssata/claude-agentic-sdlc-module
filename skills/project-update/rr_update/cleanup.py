"""The cleanup proposals: the local cache, the task journals, the [cleanup] rows and the hints about deletion and tracked ignored files.

shell: local_cache, task_journal, cleanup_update, deletion_hint, tracked_ignored_hint
core: TRACKED_IGNORED_SHOWN
"""

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from rr_update import files
from rr_update import paths


def local_cache(plan):
    """R18: .ai/local/plugin-update/ (the old merge's conflict copies) is removed; .ai/local/memory/ is never touched."""
    for here, _dirs, names in os.walk(os.path.join(plan.root, paths.LOCAL_CACHE)):
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(here, name), plan.root).replace(os.sep, "/")
            if not files.unsafe_path(plan.root, rel):
                why = "[local] the old merge's cache, not written any more"
                plan.gated("delete", rel, why, reason=why)


def task_journal(root, task_id):
    """(finished, abandoned, last event as a datetime) from the task's journal,
    or None when it holds no readable event. A task is finished when its journal
    has task_closed or gate_approved, or when logs/<id>/state.json records a
    result (so a torn task_closed line does not make a closed task look unclosed)."""
    closed = abandoned = False
    last = None
    try:
        with open(os.path.join(root, ".ai", "reports", task_id, "events.jsonl"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        try:
            ev = json.loads(line)
            when = datetime.strptime(ev["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, KeyError, TypeError, RecursionError):
            continue
        if last is None or when > last:
            last = when
        if ev.get("event") == "task_closed":
            closed = True
            data = ev.get("data")
            abandoned = (isinstance(data, dict) and data.get("abandoned") is True) or ev.get("detail") == "abandoned"
        elif ev.get("event") == "gate_approved":
            closed = True
    try:
        with open(os.path.join(root, ".ai", "state", "logs", task_id, "state.json"), encoding="utf-8") as fh:
            result = json.load(fh).get("result")
    except (OSError, ValueError, AttributeError, UnicodeDecodeError, RecursionError):
        result = None
    if isinstance(result, str) and result:
        closed = True
        abandoned = abandoned or result == "abandoned"
    return None if last is None else (closed, abandoned, last)


def cleanup_update(plan, now=None):
    """Old run logs and stale unclosed tasks, proposed for deletion and never
    deleted unasked (only with --confirm-cleanup). A closed task's `*.log` files
    go (its state.json stays); an abandoned task loses every file under
    .ai/reports/<id>/ and .ai/state/logs/<id>/ except that state.json; an unclosed
    one idle for STALE_DAYS loses every file in both. The task in flight is
    never touched. `now` is a datetime; RISKRAILS_NOW (ISO, Z) overrides it."""
    if now is None:
        try:
            now = datetime.strptime(paths.env("NOW") or files.utc_now(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            print("project-update: RISKRAILS_NOW %r is not a UTC time like 2026-01-31T12:00:00Z" % paths.env("NOW"),
                  file=sys.stderr)
            raise SystemExit(2) from None
    flight = None
    raw = plan.read(paths.STATE_FILE)
    if raw is not None:
        try:
            flight = json.loads(raw).get("task_id")
        except (ValueError, AttributeError, RecursionError):
            return  # unreadable: a task may be in flight, so no task is proposed as stale
    reports =os.path.join(plan.root, ".ai", "reports")
    logs = os.path.join(plan.root, ".ai", "state", "logs")

    def files_of(base, rel, only_logs=False, keep=()):
        out = []
        for here, _dirs, names in os.walk(os.path.join(base, rel)):
            for n in names:
                full = os.path.join(here, n)
                if os.path.isfile(full) and not os.path.islink(full) and (not only_logs or n.endswith(".log")) \
                        and n not in keep:
                    out.append(os.path.relpath(full, plan.root).replace(os.sep, "/"))
        return out

    for task_id in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        journal = task_journal(plan.root, task_id)
        if journal is None or task_id == flight:
            continue
        closed, abandoned, last = journal
        if abandoned:
            why, targets = "[cleanup] abandoned task %s" % task_id, \
                files_of(reports, task_id) + files_of(logs, task_id, keep=("state.json",))
        elif not closed and now - last > timedelta(days=paths.STALE_DAYS):
            why = "[cleanup] unclosed task %s, last event %s" % (task_id, last.strftime("%Y-%m-%d"))
            targets = files_of(reports, task_id) + files_of(logs, task_id)
        elif closed:
            why, targets = "[cleanup] log of closed task %s" % task_id, files_of(logs, task_id, only_logs=True)
        else:
            continue
        # .ai/reports/ is usually git-tracked; only .ai/state/ is git-ignored run state
        held = files.git_states(plan.root, ".ai/reports/" + task_id)
        skipped = set()
        for target in sorted(targets):
            unsafe = files.unsafe_path(plan.root, target)
            if unsafe:     # --apply would abort on it: say so instead of proposing it
                if unsafe not in skipped:
                    skipped.add(unsafe)
                    plan.hints.append("%s: not proposed for deletion, %s — remove it yourself if it should go"
                                      % (target, unsafe))
                continue
            note = why
            state = held(target) if target.startswith(".ai/reports/") else None
            if state == "tracked":
                note += "; tracked: git can restore a committed copy"
            elif state == "uncommitted":
                note += "; uncommitted: git holds no copy of it"
            elif state == "ignored":
                note += "; git-ignored: not recoverable through git"
            if state in ("tracked", "uncommitted"):
                plan.git_kept.add(target)
            if plan.confirm_cleanup:
                plan.add("delete", target, note, reason=why)
                plan.remove(target)
            else:
                plan.add("delete?", target, note, reason=why)


def deletion_hint(plan):
    """M4: git is the rollback of a deletion or an overwrite; it must hold .ai/ first.
    A [cleanup] deletion of git-ignored run state is not counted: git does not roll it back;
    one under .ai/reports/ that git tracks, or should, is."""
    if any(i["action"] in ("delete?", "delete", "regenerate?") and i["target"].startswith(".ai/")
           and (not (i.get("reason") or "").startswith("[cleanup]") or i["target"] in plan.git_kept)
           for i in plan.items) \
            and files.git_dirty_ai(plan.root):
        plan.hints.append("commit .ai/ first: git is this update's rollback "
                          "(`git status -- .ai` lists what it does not hold yet)")


TRACKED_IGNORED_SHOWN = 10  # per-file hints before tracked_ignored_hint counts the rest


def tracked_ignored_hint(plan):
    """A file under .ai/state that git tracks although an ignore rule lists it: the rule
    has no effect on it. Read-only: the human untracks it; nothing is planned.
    At most TRACKED_IGNORED_SHOWN files get their own hint; one more line counts the rest."""
    try:
        res = subprocess.run(["git", "-C", plan.root, "ls-files", "-z", "-ci", "--exclude-standard",
                              "--", ".ai/state"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return
    if res.returncode != 0:
        return
    # --literal-pathspecs: a * ? [ ] in a name is that name, not a pattern that matches its neighbours.
    all_cmd = "git ls-files -z -ci --exclude-standard -- .ai/state | xargs -0 -r git --literal-pathspecs rm --cached --"
    names = [os.fsdecode(raw) for raw in res.stdout.split(b"\0") if raw]
    for path in names[:TRACKED_IGNORED_SHOWN]:
        # A control character (or a byte that is not UTF-8, which fsdecode keeps as a lone
        # surrogate) in the name would forge a report line or break the copy-paste command:
        # show it escaped, and untrack by the NUL-safe listing.
        shown = "".join(c if c.isprintable() else repr(c)[1:-1] for c in path)
        if shown == path:
            plan.hints.append("%s: tracked by git but ignored by an ignore rule — the rule has no "
                              "effect on a tracked file, so every run leaves the tree dirty and "
                              "`git commit -a` sweeps it in; untrack it yourself, from the project root: "
                              "`git --literal-pathspecs rm --cached -- %s` and commit (the file stays on disk)"
                              % (shown, shlex.quote(path)))
        else:
            plan.hints.append("%s: tracked by git but ignored by an ignore rule — the rule has no "
                              "effect on a tracked file, so every run leaves the tree dirty and "
                              "`git commit -a` sweeps it in; this name cannot be typed safely, so "
                              "untrack it, from the project root, with `%s`, which untracks EVERY tracked, ignored file "
                              "under .ai/state, not only this one, and commit (the files stay on disk)"
                              % (shown, all_cmd))
    if len(names) > TRACKED_IGNORED_SHOWN:
        plan.hints.append(".ai/state: %d more file(s) tracked by git but ignored by an ignore rule, "
                          "not listed; untrack ALL tracked, ignored files under .ai/state "
                          "(the ones listed above too), from the project root, with `%s` and commit (the files stay on disk)"
                          % (len(names) - TRACKED_IGNORED_SHOWN, all_cmd))
