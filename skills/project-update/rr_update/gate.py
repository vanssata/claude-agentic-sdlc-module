"""The one gate: who is at the keyboard, the audit-trail name, and the refusal every gate prints.

shell: ai_unattended, human_gate, refuse
core: AGENT_MARKERS, PLACEHOLDER_NAME_RE, placeholder_name
"""

import os
import re

from rr_update import paths

# Set in the environment of a shell an agent runs: Claude Code's CLAUDECODE,
# and the names Codex gives its tool calls. Present counts, an empty value too.
AGENT_MARKERS = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI",
                 "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION")


def ai_unattended():
    """AI_UNATTENDED is set when it is non-empty and not 0, false or no (case
    and blanks ignored): one rule in every reader (risk 0587)."""
    return os.environ.get("AI_UNATTENDED", "").strip().lower() not in ("", "0", "false", "no")


def human_gate():
    """(passed, via, why) for --confirm-delete. A terminal outside any agent
    session is a human: via "terminal". Otherwise a launcher that declared the
    run unattended (AI_UNATTENDED) passes: via "unattended", as state.py's
    approve records it. Anything else is refused, and `why` says what was seen —
    a terminal alone is not enough, since an agent can open a pty (F3).

    Duplicated in spirit from skills/ai-task/state.py (human_present) on purpose:
    the two skills are installed independently and neither imports the other."""
    markers = [name for name in AGENT_MARKERS if name in os.environ]
    if os.isatty(0) and not markers:
        return True, "terminal", ""
    if ai_unattended():
        return True, "unattended", ""
    if markers:
        return False, None, ("this run is inside an agent session (%s %s set); run it in a terminal "
                             "outside Claude Code or Codex, not through the `!` prefix"
                             % (", ".join(markers), "is" if len(markers) == 1 else "are"))
    return False, None, "this run has no terminal"


# The name typed into --confirm-delete is the audit trail; the template's own
# "<your name>" copied verbatim names no one. The whole value, not a substring.
PLACEHOLDER_NAME_RE = re.compile(r"\A\s*(?:<[^>]*>|your\s+name)\s*\Z", re.IGNORECASE)


def placeholder_name(name):
    return bool(PLACEHOLDER_NAME_RE.match(name or ""))


def refuse(reason, how):
    """Print the refusal the way every gate does — the marker on the first
    stdout line, then what to do — and return exit code 5."""
    print("%s: %s" % (paths.REFUSED, reason))
    print("  %s" % how)
    return 5

