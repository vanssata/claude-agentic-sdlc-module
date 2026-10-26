#!/usr/bin/env python3
"""claude-agentic: the PreToolUse guards in one process.

Reads the hook payload from stdin and either exits 0 silently (allow) or prints
the deny object and exits 0, the contract of every guard. The checks are the
three shell guards this replaces, in the order a runtime ran them:

  git    git and deployment safety, on Bash (guard/git.py)
  paths  sensitive paths, control files, the runtime lock, dependency
         instruction files (guard/paths.py)
  scope  the task's approved scope, on file edits (guard/scope.py)

`--only <check>` runs one of them; that is what each hooks/ai-*-guard.sh shim
passes, so a registration made for the shell guards keeps its meaning. With no
flag all three run and the first refusal wins.

Fail-open: anything unexpected — a payload that is not JSON, a missing file,
an exception — allows, with no output. A guard is defence-in-depth against an
agent's mistakes, not a security boundary, and must never make a tool unusable.
Run as `python3 -I -S`: no site packages, no environment-driven imports.
"""
import os
import sys

CHECKS = ("git", "paths", "scope")
# The tools each check reads; any other tool is allowed by its first line, so
# the module is not even imported for it.
TOOLS = {
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
            if payload.tool not in TOOLS[name]:
                continue
            module = __import__("guard." + name, fromlist=["check"])
            # Each shell guard was its own process with its own SECONDS: the
            # first check's clock started with the process, a later one's now.
            ctx.clock = common.Clock(common.START if name == ((only,) if only else CHECKS)[0] else None)
            try:
                module.check(ctx)
            except common.Allow:
                continue
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
