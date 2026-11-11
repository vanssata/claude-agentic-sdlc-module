"""The Bash rule of the path guard: the verb tables (readers, copiers, writers, removers, fetchers,
ln, dd) and check_bash, which walks the segments of one command and applies every other rule.

R16: shell (they read the file system, the clock or a subprocess): check_bash; every other name here is core.
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import re
from guard.common import (Allow, Deny, abs_path, chomp_all, ere_escape, exists, herestring_lines,
                          real_path, realpath_strict, strip1)
from guard.paths_base import (SEGMENT, T, WHY_APPROVE, WHY_HUMAN, WHY_PICK, WHY_PROTECTED,
                              WHY_SENSITIVE, WHY_TASK)
from guard.paths_shell import shell_segments
from guard.paths_human import (APPROVE_RE, DIALOG_GATE_RE, HUMAN_BY_RE, PROFILE_SET_RE,
                               START_LIGHT_RE)
from guard.paths_movers import GLOBBY


VERBS_RE = ("(^|[^A-Za-z0-9_.-])(cp|mv|install|rsync|rm|rmdir|unlink|tee|truncate|shred|touch|ln|chmod|chown|"
            "dd|sed|perl|ruby)([^A-Za-z0-9_.-]|$)")

READERS = ("(^|[|;&[:space:]])(cat|bat|less|more|head|tail|strings|xxd|od|hexdump|base64|nl|tac|rev)"
           "([[:space:]]+-[^[:space:]]+)*[[:space:]]+")
COPIERS = "(^|[|;&[:space:]])(cp|mv|rsync|scp|install|tar|zip|curl|wget)([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+"
WRITERS = SEGMENT + "(tee|truncate|shred|touch|ln)([[:space:]]+-[^[:space:]]+)*[[:space:]]+"
REMOVERS = SEGMENT + "(rm|rmdir|unlink)([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+"
MODES = SEGMENT + "(chmod|chown)([[:space:]]+-[^[:space:]]+)*[[:space:]]+[^-][^[:space:]]*[[:space:]]+"
DDWRITE = SEGMENT + "dd([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+"
INPLACE = SEGMENT + "(sed|perl|ruby)([[:space:]]+-[^[:space:]]*i[^[:space:]]*)([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+"
LN_RE = "(^|[|;&[:space:]])ln([[:space:]]+-[^[:space:]]+)*[[:space:]]"
LN_SRC_RE = ".*(^|[|;&[:space:]])ln([[:space:]]+-[^[:space:]]+)*[[:space:]]+([^[:space:];&|]+).*"
# Words that make a long command worth a full check; past LONG_CMD the guard
# refuses rather than run its patterns over the text (R22, D3).
LONG_CMD = 4096
# Whole words only, so --cov, --config and approve_invoice do not trip it.
LONG_TRIGGER_RE = ("(^|[^A-Za-z0-9_])approve([^A-Za-z0-9_]|$)|--by(=|[[:space:]]|$)|"
                   "--con?f?i?r?m?-?(d?e?l?e?t?e?|c?l?e?a?n?u?p?)(=|[[:space:]]|$)|state\\.py|update\\.py")
# Tools that write a file named on their command line without a redirect; the
# movers do not parse them, so any protected path they name is refused (H1).
FETCHERS = "(^|[|;&[:space:]])(scp|tar|zip|unzip|curl|wget)([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+"


def check_bash(self, unattended):           # pylint: disable=too-many-branches,too-many-statements
    m = self.m
    cmd = chomp_all(self.p.bash_command())
    if not cmd:
        raise Allow()
    cmd_joined = cmd.replace("\\\n", " ")
    length = self.loc.length
    if length(cmd) > LONG_CMD and (m.search_c(LONG_TRIGGER_RE, cmd) or m.matches_joined(cmd, self.loose)):
        raise Deny("Refusing a %d-character shell command that names a guarded path or a state.py or "
                   "update.py verb: write it to a file and run that, or split it." % length(cmd))
    if m.ere_match(DIALOG_GATE_RE, cmd_joined):
        raise Deny("Refusing to run hooks/dialog-gate.py from a shell: it records the human's answer to "
                   "the dialog, and only the runtime calls it, after the dialog tool. To answer a decision, "
                   "send the dialog ('state.py decision show'); a human settles one in their own terminal "
                   "('state.py decision settle --id D<n> --pick <n>'). See .ai/policies/safety.md.")
    on, picked = self.dialog_consent(cmd)
    if m.ere_match(APPROVE_RE, cmd_joined) and not unattended and self.task_in_flight() and not picked:
        raise Deny("Refusing 'state.py approve' from an agent session." + WHY_APPROVE)
    if on and not picked and not unattended and m.ere_match(PROFILE_SET_RE, cmd_joined):
        raise Deny("Refusing 'state.py profile set' from an agent session." + WHY_PICK)
    if not picked and not unattended and m.ere_match(HUMAN_BY_RE, cmd_joined):
        raise Deny(T("Refusing a verdict with 'state.py … --by' from an agent session.")
                   + (WHY_PICK if on else WHY_HUMAN))
    if not on and not picked and not unattended and m.ere_match(START_LIGHT_RE, cmd_joined):
        raise Deny(T("Refusing 'state.py start --mode light … --by' from an agent session: lowering the "
                     "mode is the human's.") + WHY_HUMAN)
    self.interpreter_text(cmd)

    # Top-level splitting only: the string a sh -c or an eval runs is not
    # re-parsed (R22, SQ13; the bypass is accepted in known-risks.md).
    segs = shell_segments(cmd) if m.ere_match(VERBS_RE, cmd) else ""
    self.movers(segs)

    if not (m.matches_joined(cmd, self.loose) or m.ere_match(LN_RE, cmd)):
        raise Allow()

    tokens = []
    words = [w for w in re.split("[ \t\n]+", re.sub("[|;&()<>]", " ", cmd + "\n")) if w]
    stripped = []
    for w in words:
        w = w.lstrip("\"'").rstrip("\"'")
        if w:
            stripped.append(w)
    for token in self.sort_u(stripped):
        self.work_clock()
        if not token or token.startswith("-"):
            continue
        tokens.append(token)
    short, abs_lines = [], []
    for token in tokens:
        self.work_clock()
        if length(token) > 4096:
            if any(c in GLOBBY for c in token):
                raise Deny("Refusing a shell command with a %d-character argument that holds a glob or "
                           "expansion character: the guard cannot check what it expands to." % length(token))
            after = token.split("=", 1)[1] if "=" in token else token
            if m.ere_match(self.loose_joined, abs_path(token, self.cwd) + "\n" + abs_path(after, self.cwd)):
                raise Deny("Refusing a shell command with a %d-character argument that matches a guarded "
                           "path pattern: no path that long names a file, and the guard does not check it."
                           % length(token))
            continue
        short.append(token)
        abs_lines.append(token if token.startswith("/") else strip1(self.cwd, "/") + "/" + token)
    exist = []
    for i in range(len(short)):
        self.work_clock()
        if exists(abs_lines[i]):
            exist.append(i)
    resolved = []
    if exist:
        for i in exist:
            r = realpath_strict(abs_lines[i])
            if r is not None:
                resolved.append(chomp_all(r))
        if len(resolved) != len(exist):
            resolved = []
            for i in exist:
                self.work_cap("token")
                resolved.append(real_path(short[i], self.cwd))
    real_lines = list(abs_lines)
    for j, i in enumerate(exist):
        real_lines[i] = resolved[j]
    lines = []
    for i, token in enumerate(short):
        eq = abs_lines[i]
        if "=/" in token:
            eq = token.split("=", 1)[1]
        elif "=" in token:
            eq = strip1(self.cwd, "/") + "/" + token.split("=", 1)[1]
        lines += [abs_lines[i], real_lines[i], eq]
    thits = {(n - 1) // 3 for n in self.loose_hits(lines)}
    self.work_clock()
    for token in [short[i] for i in range(len(short)) if i in thits]:
        self.work_cap("token")
        verdict = self.classify(abs_path(token, self.cwd)) or self.classify(real_path(token, self.cwd))
        if "=" in token and verdict is None:
            verdict = self.classify(abs_path(token.split("=", 1)[1], self.cwd))
        if verdict is None:
            continue
        kind, pattern = verdict
        esc = ere_escape(token)
        # Reading is refused for a secret only; a control file is read freely (R22),
        # unless it also matches a secret pattern (.ai/state/x.pem).
        secret = kind == "sensitive" or m.matches_any(self.deny_p, abs_path(token, self.cwd)) is not None
        if secret and (m.ere_match(READERS + "[\"']?" + esc, cmd)
                                    or m.ere_match(COPIERS + "[\"']?" + esc, cmd)
                                    or m.ere_match("<[[:space:]]*[\"']?" + esc, cmd)):
            raise Deny("Refusing a shell command that would expose a sensitive path: %s (matched: %s)%s"
                       % (token, pattern, WHY_SENSITIVE))
        how = ""
        if m.ere_match(">>?[[:space:]]*[\"']?" + esc, cmd):
            how = "redirect into"
        elif m.ere_match(FETCHERS + "[\"']?" + esc, cmd):
            how = "command that writes"
        for rx, what in ((WRITERS, "command that writes"), (MODES, "command that writes"),
                         (DDWRITE, "command that writes"), (INPLACE, "in-place edit of"),
                         (REMOVERS, "removal of")):
            if not how and m.ere_match(rx + "[\"']?" + esc, segs):
                how = what
        if how:
            if kind == "protected":
                raise Deny("Refusing a shell %s a RiskRails control file: %s%s" % (how, token, WHY_PROTECTED))
            if kind == "task" and self.task_in_flight():
                raise Deny("Refusing a shell %s runtime configuration while task %s is in flight: %s%s"
                           % (how, self.task_id, token, WHY_TASK))

    if m.ere_match(LN_RE, cmd):
        src = []
        for line in herestring_lines(strip1(cmd, "\n")):
            g = m.groups(LN_SRC_RE, line)
            if g is not None:
                src.append(g[3] + "\n")
        src = chomp_all("".join(src))
        if src and self.classify(abs_path(src, self.cwd)):
            raise Deny("Refusing to create a symlink to a sensitive path: %s%s" % (src, WHY_SENSITIVE))
