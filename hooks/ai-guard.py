#!/usr/bin/env python3
"""RiskRails: the PreToolUse guards in one process.

Reads the hook payload from stdin and either exits 0 silently (allow) or prints
the deny object and exits 0, the contract of every guard. The checks are the
open-decision gate, then the three shell guards this replaces, in the order a
runtime ran them:

  decision  the gate while a dialog decision is open, on every tool
            (guard/decision.py): deny all but the dialog, the picked command
            and `state.py decision show|settle|fallback`
  git    git and deployment safety, on Bash (guard/git.py)
  paths  sensitive paths, control files, the runtime lock, dependency
         instruction files (guard/paths.py)
  scope  the task's approved scope, on file edits (guard/scope.py)

`--only <check>` runs one of them; that is what each hooks/ai-*-guard.sh shim
passes, so a registration made for the shell guards keeps its meaning. With no
flag all of them run and the first refusal wins.

Fail-open: anything unexpected — a payload that is not JSON, a missing file,
an exception — allows, with no output. A guard is defence-in-depth against an
agent's mistakes, not a security boundary, and must never make a tool unusable.
Two exceptions, both with the dialog on (R36): the git check's consent rule
denies a commit or push when the consent ledger cannot be read (R36.9), and
state.py's own approve refuses without a pick or a terminal (R36.10).
Run as `python3 -I -S`: no site packages, no environment-driven imports.
"""
import os
import sys

CHECKS = ("decision", "git", "paths", "scope")
# The tools each check reads; any other tool is allowed by its first line, so
# the module is not even imported for it. None: every tool.
TOOLS = {
    "decision": None,
    "git": ("Bash",),
    "paths": ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"),
    "scope": ("Edit", "Write", "MultiEdit", "NotebookEdit"),
}


def main(argv):
    only = None
    if len(argv) == 2 and argv[0] == "--only" and argv[1] in CHECKS:
        only = argv[1]
    elif argv:
        return 0
    try:
        hook_dir = os.path.dirname(os.path.abspath(__file__))
        if hook_dir not in sys.path:
            sys.path.insert(0, hook_dir)
        from guard import common            # pylint: disable=import-outside-toplevel
        try:
            raw = sys.stdin.buffer.read()
            loc = common.Locale()
            pwd = common.shell_pwd()
            payload = common.Payload(raw, pwd)
        except common.Allow:
            return 0
        ctx = Context(payload, loc, pwd, common.bytes_b(os.fsencode(hook_dir)))
        for name in (only,) if only else CHECKS:
            if TOOLS[name] is not None and payload.tool not in TOOLS[name]:
                continue
            # Each shell guard was its own process with its own SECONDS: the
            # first shell guard's clock started with the process, a later one's
            # now. The decision check, new, does not move that.
            ctx.clock = common.Clock(common.START if name == (only or "git") else None)
            try:
                module = __import__("guard." + name, fromlist=["check"])
                module.check(ctx)
            except common.Allow:
                continue
            except Exception as exc:        # pylint: disable=broad-exception-caught
                # The decision gate fails open on its own (R36.12): a missing or
                # broken module — a half-done install — must not end the run
                # before git, paths and scope.
                if name != "decision" or isinstance(exc, common.Deny):
                    # A git pick the gate spent on this call is gone even
                    # though a later rule refuses the command (review focus 1).
                    if isinstance(exc, common.Deny) and name != "decision" and ctx.consent:
                        from guard import dialog    # pylint: disable=import-outside-toplevel
                        exc.reason += common.text_to_b(dialog.used_note(ctx.consent))  # pylint: disable=no-member  # exc is a common.Deny by the isinstance above
                    raise
    except Exception as exc:                # pylint: disable=broad-exception-caught
        common = sys.modules.get("guard.common")
        if common is not None and isinstance(exc, common.Deny):
            try:
                sys.stdout.buffer.write(common.deny_json(getattr(exc, "reason", "")))
                sys.stdout.buffer.flush()
            except Exception:               # pylint: disable=broad-exception-caught
                pass
        return 0
    return 0


class Context:                              # pylint: disable=too-few-public-methods
    """What every check reads: the payload, the locale and its matcher, the
    hook directory, bash's $PWD, and the check's own clock."""

    def __init__(self, payload, loc, pwd, hook_dir):
        from guard import common            # pylint: disable=import-outside-toplevel
        self.payload = payload
        self.loc = loc
        self.matcher = common.Matcher(loc)
        self.pwd = pwd
        self.hook_dir = hook_dir
        self.clock = common.Clock()
        self.consent = None                 # the git pick the decision gate spent on this call


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
