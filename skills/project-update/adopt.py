"""Adopt a foreign AI-tool structure into claude-agentic's layout (`update.py --adopt`).

This module grows over WP6's plan steps; update.py keeps only flag parsing and the
calls into it, so new behaviour lives here.

Exit codes used by the adopt family (update.py returns them):
  4  unmapped, a failed check or an invalid proposal: a decision is needed
  5  refused: a gate that needs a human, a clean tree or a finished task did not hold
"""
import os
import subprocess

REFUSED = "ADOPT_REFUSED"


def human_present():
    """The same condition WP2's approval uses: a terminal, or a launcher that
    declared the run unattended. An agent has neither.

    Duplicated from skills/ai-task/state.py (human_present) on purpose: the two
    skills are installed independently and neither imports the other."""
    return os.isatty(0) or bool(os.environ.get("AI_UNATTENDED"))


def clean_tree(root):
    """The paths `git status` reports as changed or untracked under root, or
    None when root is not inside a git work tree. `-z` keeps paths with spaces
    or quotes intact; a rename entry carries its source as a second record,
    which is skipped."""
    try:
        proc = subprocess.run(["git", "-C", root, "status", "--porcelain", "-z", "--untracked-files=all"],
                              capture_output=True, check=False)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    records = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    paths, skip = [], False
    for rec in records:
        if skip:
            skip = False
            continue
        if len(rec) < 4:
            continue
        status, path = rec[:2], rec[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            skip = True
    return paths


def refuse(reason, how):
    """Print the refusal the way every adopt gate does — the marker on the first
    stdout line, then what to do — and return exit code 5."""
    print("%s: %s" % (REFUSED, reason))
    print("  %s" % how)
    return 5


def budget_offenders(root, files, caps, block_of):
    """R21: one line per root instruction file over budget — its managed block
    over `caps["project"]`, or the whole file over `caps["skeleton"]`. Files that
    do not exist are skipped; a file under both budgets prints nothing."""
    out = []
    for name in files:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block = block_of(text)
        size = len(text.encode("utf-8"))
        if block is not None and caps.get("project") and len(block.encode("utf-8")) > caps["project"]:
            out.append("%s block %d B over the project budget of %d B"
                       % (name, len(block.encode("utf-8")), caps["project"]))
        if caps.get("skeleton") and size > caps["skeleton"]:
            out.append("%s file %d B over the skeleton budget of %d B" % (name, size, caps["skeleton"]))
    return out
