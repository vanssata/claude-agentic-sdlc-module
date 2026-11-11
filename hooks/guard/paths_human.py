"""The human-only gates: the --confirm-delete rule (confirm_delete) and the state.py commands an agent
may not run (approve, profile set, the --by forms, the dialog recorder), with their patterns
(dialog_consent).

R16: shell (they read the file system, the clock or a subprocess): dialog_consent; every other name here is core.
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import os
from guard.common import Deny, b_bytes, exists, herestring_lines
from guard.paths_base import END, Q, VAR, WHY_CONFIRM_DELETE


# The --confirm-delete rule, and --confirm-cleanup (the same human gate; any argparse prefix).
SEP = "(([^|;&]|[<>]&|&>)*[[:space:]])?" + Q
CONFIRM_DEL = "d(e(l(e(t(e)?)?)?)?)?"
CONFIRM_CLEAN = "c(l(e(a(n(u(p)?)?)?)?)?)?"
CONFIRM = ("--co(n(f(i(r(m(-(" + CONFIRM_DEL + "|" + CONFIRM_CLEAN + ")?)?)?)?)?)?)?"
           "(=|[[:space:]]|['\"]|$)")
APPLY = "--ap(p(l(y)?)?)?" + END
HEAD = "(^|[[:space:]'\"/|;&(`])(update\\.py|-[A-Za-z]*m[[:space:]]*" + Q + "update|" + VAR + ")" + Q + "[[:space:]]"
CONFIRM_RE = HEAD + SEP + CONFIRM + SEP + APPLY + "|" + HEAD + SEP + APPLY + SEP + CONFIRM

# The gate rules.
ARGS = "([[:space:]]+--r[a-z]*(=|[[:space:]]+)(\"[^\"]*\"|'[^']*'|[^[:space:]]+))*"
VERB = "([[:space:]]+--)?[[:space:]]+" + Q + "approve" + END
BOUND = "(^|[|;&([:space:]`])"
APPROVE_RE = (BOUND + "(python3?[[:space:]]+)?" + Q + "[^[:space:]'\"]*state\\.py" + Q + ARGS + VERB + "|"
              + BOUND + "(python3?[[:space:]]+)?" + Q + VAR + Q + ARGS + VERB)
# R36.11: the other human-only state.py commands — `profile set` (dialog on only)
# and the --by forms of verify, review and reject (dialog on or off) — run from an
# agent session only as the next live pick, like approve. `start --mode light --by`
# is denied with the dialog off only: `light` is the one --mode value that can
# never raise a mode; with the dialog on it reaches state.py, which opens the
# lowering decision (review H1, T-2026-10-28-010); any other `start --mode X --by`
# reaches state.py too (T-2026-10-30-0758 Q1, Q2).
PROFILE_SET_VERB = "([[:space:]]+--)?[[:space:]]+" + Q + "profile" + Q + "[[:space:]]+" + Q + "set" + END
PROFILE_SET_RE = (BOUND + "(python3?[[:space:]]+)?" + Q + "[^[:space:]'\"]*state\\.py" + Q + ARGS + PROFILE_SET_VERB
                  + "|" + BOUND + "(python3?[[:space:]]+)?" + Q + VAR + Q + ARGS + PROFILE_SET_VERB)
BY_TOK = Q + "--by?" + Q + "(=|[[:space:]]|$)"
MODE_LIGHT = Q + "--m(o(d(e)?)?)?" + Q + "(=|[[:space:]]+)" + Q + "light" + END
SKIP = "([^|;&`]*[[:space:]])?"
HUMAN_BY_VERB = ("([[:space:]]+--)?[[:space:]]+" + Q + "(verify|review|reject)" + END + SKIP + BY_TOK)
START_LIGHT_VERB = ("([[:space:]]+--)?[[:space:]]+" + Q + "start" + END + SKIP + "("
                    + MODE_LIGHT + SKIP + BY_TOK + "|" + BY_TOK + SKIP + MODE_LIGHT + ")")


def state_verb_re(verb):
    """The state.py command whose verb part is `verb`, as an ERE: by path or by a variable."""
    return (BOUND + "(python3?[[:space:]]+)?" + Q + "[^[:space:]'\"]*state\\.py" + Q + ARGS
            + "(" + verb + ")|" + BOUND + "(python3?[[:space:]]+)?" + Q + VAR + Q + ARGS + "(" + verb + ")")


HUMAN_BY_RE = state_verb_re(HUMAN_BY_VERB)
START_LIGHT_RE = state_verb_re(START_LIGHT_VERB)

# R36.11: running the dialog's recorder by hand would forge the human's answer.
# dialog-gate.py in command position — the program itself, or the script a
# python runs — after a separator, a quote, exec/env/command/nohup/time/sudo
# and their words; naming it as an argument (grep, git diff, chmod) is not running it.
DIALOG_GATE_RE = ("(^|[|;&(`{'\"]|\\$\\()[[:space:]]*((exec|env|command|nohup|time|sudo)([[:space:]]+[^[:space:]|;&]+)*"
                  "[[:space:]]+)?(" + Q + "[^[:space:]'\"|;&]*python[0-9.]*" + Q
                  + "([[:space:]]+-[^[:space:]]+)*[[:space:]]+)?" + Q + "[^[:space:]'\"|;&]*dialog-gate\\.py" + Q
                  + "([[:space:]|;&)<>]|$)")


# -------------------------------------------------------------- the check

def confirm_delete(self, cmd):
    if "--co" not in cmd:
        return
    joined = cmd.replace("\\\n", " ")
    for line in herestring_lines(joined):
        if self.loc.length(line) <= 16384:
            continue
        if "--ap" not in line:
            continue
        if "update" not in line and "$" not in line:
            continue
        raise Deny("Refusing a command line over 16384 characters that holds --co, --ap and update or a "
                   "variable: the --confirm-delete rule does not run its pattern on a line that long."
                   + WHY_CONFIRM_DELETE)
    if self.m.ere_match(CONFIRM_RE, joined, need=("--co", "--ap")):
        raise Deny("Refusing 'update.py --apply --confirm-delete' from an agent session." + WHY_CONFIRM_DELETE)


def dialog_consent(self, cmd):
    """(the dialog is on for this call, the command is the next live pick
    of this session) — R36.11's pass-through. state.py spends the pick
    after its own argv check (R36.10); the guard only lets it reach it."""
    if not self.root or not exists(self.root + "/.ai/policies/dialog.json"):
        return False, False
    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel
    from guard import dialog            # pylint: disable=import-outside-toplevel
    root = os.fsdecode(b_bytes(self.root))
    values = self.p.values
    raw = values[0] if len(values) == 1 and isinstance(values[0], dict) else None
    hook_file = os.path.join(os.fsdecode(b_bytes(self.ctx.hook_dir)), "ai-guard.py")
    try:
        if raw is None or not dialog.effective_switch(root, dialog.payload_runtime(raw, hook_file), raw):
            return False, False
        pick = dialog.next_live_pick(root, raw.get("session_id"), datetime.now(timezone.utc))
    except Exception:                   # pylint: disable=broad-exception-caught
        return True, False
    command = b_bytes(cmd).decode("utf-8", "replace").strip()
    return True, bool(pick and pick.get("label") == command)
