"""The plan one run builds and the decisions about one file: lost lines, patterns, the note on an edited copy, the regenerate rule.

shell: Plan, regenerate
core: lost_lines, patterns_of, edited_note
"""

import json
import os
from datetime import datetime, timezone

from rr_update import files


# ---------------------------------------------------------------- planning
class Plan:
    def __init__(self, root):
        self.root = root
        self.items = []   # dicts: action, target, note, content, reason, keep, expect
        self.hints = []
        self.confirm_delete = None  # the human who confirmed this run's gated rows
        self.confirm_via = None  # why that gate passed: "terminal" or "unattended"
        self.confirm_cleanup = None  # the human who confirmed this run's [cleanup] deletions
        self.cleanup_via = None
        self.version_from = None  # the .ai/VERSION this run started from
        self.final = {}   # target -> bytes after this run (for cross-file fixes)
        self.removed = set()  # targets this run takes away
        self.seen = {}    # target -> sha of what was on disk when it was first read,
        #                   or None when nothing was there: apply's precondition
        self.git_kept = set()  # [cleanup] targets git holds or should hold: a hint and an original/ copy
        self.report_dir = ".ai/reports/project-update-%s" % datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # The project as this run leaves it: planned content first, then the disk.
    # File readers in the planning path go through these, not the disk.
    def exists(self, target):
        if target in self.final:
            return True
        return target not in self.removed and os.path.exists(os.path.join(self.root, target))

    def read(self, target):
        if target in self.final:
            return self.final[target]
        if not self.exists(target):
            return None
        data = files.read(os.path.join(self.root, target))
        self.seen.setdefault(target, files.sha(data))  # what apply must find there
        return data

    def remove(self, target):
        self.final.pop(target, None)
        self.removed.add(target)

    def before(self, target):
        """The sha of the target as this run first read it, None when it was
        absent. Recorded by the read that planned the change, so the precondition
        and the planning input are the same bytes."""
        if target not in self.seen:
            path = os.path.join(self.root, target)
            self.seen[target] = files.sha(files.read(path)) if os.path.isfile(path) and not os.path.islink(path) else None
        return self.seen[target]

    def add(self, action, target, note="", content=None, reason=None, keep=False):
        self.items.append(dict(action=action, target=target, note=note, content=content,
                               reason=reason, keep=keep, expect=self.before(target)))
        if content is not None:
            self.final[target] = content
            self.removed.discard(target)  # planned content wins over an earlier removal

    def original_of(self, target):
        return "%s/original/%s" % (self.report_dir, target)

    def gated(self, action, target, note, content=None, reason=None):
        """A change that waits for a human: `regenerate?` / `delete?` until
        --apply --confirm-delete NAME, then `regenerate` / `delete` with the original kept
        under original/ (R7)."""
        if self.confirm_delete:
            self.add(action, target, note, content=content, reason=reason, keep=True)
            if action == "delete":
                self.remove(target)
        else:
            self.add(action + "?", target, note, reason=reason)


# ---------------------------------------------------------------- regenerate
def lost_lines(ours, theirs):
    """The lines of the project's copy that the plugin's version does not have."""
    kept = set(theirs.decode("utf-8", "replace").splitlines())
    return [line.strip() for line in ours.decode("utf-8", "replace").splitlines()
            if line.strip() and line not in kept]


def patterns_of(data):
    """The count of non-empty deny and allow patterns in a path-guard.json, or None when it is not one."""
    try:
        doc = json.loads(data)
        return sum(1 for key in ("deny_patterns", "allow_patterns") for p in doc.get(key) or []
                   if isinstance(p, str) and p.strip())
    except (ValueError, AttributeError, TypeError, RecursionError):
        return None


def edited_note(plan, target, ours, theirs):
    """What a gated regenerate would lose, and where the original goes (R6)."""
    lost = lost_lines(ours, theirs)
    shown = "; ".join("`%s`" % (line[:48] + ("…" if len(line) > 48 else "")) for line in lost[:3])
    note = "edited here: %d line(s) of yours are not in the plugin's version%s" % (len(lost), " (" + shown + ")" if shown else "")
    if target.endswith("path-guard.json"):
        count = patterns_of(ours)
        note += "; drops %s deny/allow pattern(s)" % ("an unreadable number of" if count is None else count)
    return "%s; original kept at %s" % (note, plan.original_of(target))


def regenerate(plan, history, key, target, theirs):
    """D5: absent -> create; equal -> nothing; a version the plugin once shipped -> regenerate;
    anything else is the human's edit -> regenerate? behind the gate."""
    ours = plan.read(target)
    if ours is None:
        plan.add("create", target, content=theirs)
    elif ours == theirs:
        return
    elif history.shipped(key, ours):
        plan.add("regenerate", target, "unchanged since it was installed", content=theirs)
    else:
        plan.gated("regenerate", target, edited_note(plan, target, ours, theirs), content=theirs)
