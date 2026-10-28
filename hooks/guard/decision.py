"""R36.12: the gate while a dialog decision is open — the first check of
hooks/ai-guard.py, on every tool (the Claude matcher is `*`).

7d1 ships only its fast path: with no .ai/state/decision.json the check costs
one stat per ancestor directory and allows. The gate itself — deny every tool
but the dialog tool, the next live pick and `state.py decision show|settle|
fallback` — lands in 7d2; until then an open decision allows too, so no
guard decision moves. It fails open: it is not the security boundary (R36.9
and R36.10 are).
"""
from guard.common import Allow, exists, find_ai_root


def check(ctx):
    # Its own failure is an Allow, never an exception: ai-guard.py ends the
    # run on one, and the git, paths and scope checks after this must still run.
    try:
        root = find_ai_root(ctx.payload.cwd, ctx.pwd)
        if root is None or not exists(root + "/.ai/state/decision.json"):
            raise Allow()
    except Exception:                       # pylint: disable=broad-exception-caught
        raise Allow() from None
    raise Allow()                           # 7d2: the gate reads the open decisions here
