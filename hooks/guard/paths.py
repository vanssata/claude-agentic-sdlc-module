"""Port of hooks/ai-path-guard.sh: the sensitive-path guard, on Read, Edit,
Write, MultiEdit, NotebookEdit and Bash (Codex: Bash and apply_patch).

Opt-in: it does nothing unless the project has a .ai/ directory — except the
`--confirm-delete` rule, which runs first and everywhere. Four jobs: keep
secrets and data dumps out of the context; keep the guards' configuration and
the task state out of an agent's edits; freeze the runtime's own configuration
while a task is in flight; treat a dependency's instruction files as data.

Every block of the shell guard is here, in its order, with its messages, its
caps and its clock. The shell's processes are done in-process with the same
answers: `realpath -m` (realpath_m), `find … -prune -o -print` (find_print),
the awk segmenter (shell_segments), each `grep` (Matcher.grep_q, loose_hits),
the redirection `sed`. What ran inside `$( )` and so could not change the
guard's own state still cannot: covers_protected asks whether a task is in
flight without remembering the answer, as its subshell forgot it.
"""
import os
import re
import stat

from guard.common import (Allow, Deny, abs_path, b_bytes, bytes_b, chomp_all, ere_escape,
                          env_b, exists, find_ai_root, herestring_lines, is_dir, is_file,
                          is_jq_string, jq_iter, jq_tostring, load_json_file, read_lines,
                          real_path, realpath_strict, strip1, text_to_b)

T = text_to_b

Q = "['\"]?"
END = "([[:space:]]|['\"]|$)"
VAR = "\\$\\{?[A-Za-z_][A-Za-z0-9_]*\\}?"

WHY_CONFIRM_DELETE = T(
    "\n\n--confirm-delete is a human confirming an irreversible deletion, and the name\n"
    "typed is the audit trail. A human runs the same command in a terminal\n"
    "outside Claude Code or Codex (not through the ! prefix: that shell is the\n"
    "agent's). An unattended run exports AI_UNATTENDED=1 in the launcher's environment, and the\n"
    "record then says via: unattended. See skills/project-update/SKILL.md.")
WHY_SENSITIVE = T(
    "\n\nProduction secrets and data dumps must not enter the model context.\n"
    "If this path is genuinely safe (a .dist/.example file, a fixture), add a regex to\n"
    "\"allow_patterns\" in .ai/policies/path-guard.json. See .ai/policies/security.md.")
WHY_PROTECTED = T(
    "\n\nThese files are the guard configuration and the task state. State is written by\n"
    "skills/ai-task/state.py, and during a schema migration by\n"
    "skills/project-update/update.py; policy files are edited by a human outside an\n"
    "agent run, so a change to them is reviewable. See .ai/policies/safety.md.")
WHY_TASK = T(
    "\n\nWhile a task is in flight the runtime's own configuration is frozen: settings,\n"
    "agent and skill definitions, commands, hooks, and the pipeline's policies and\n"
    "workflows. A run that edits the rules it is being judged by is how scope and\n"
    "review quietly get weaker. Finish or archive the task\n"
    "(skills/ai-task/state.py close), then change this through /project-update or by\n"
    "hand outside a run. See .ai/policies/safety.md.")
WHY_APPROVE = T(
    "\n\nApproval happens outside the agent. A human runs, in their own terminal:\n"
    "  python3 <plugin>/skills/ai-task/state.py --root . approve --by \"<name>\"\n"
    "or sets [Answer]: A on the gate question in .ai/reports/<task-id>/task.md\n"
    "and tells the session to run state.py questions --sync. An unattended run\n"
    "exports AI_UNATTENDED=1 in the launcher's environment, and the journal then\n"
    "records the approval as unattended for ever. See .ai/policies/safety.md.")
WHY_WORK_CAP = T(
    "This command names more paths than the guard can check within its timeout; split it into "
    "smaller commands, or pass the list through a file and xargs.")

TOKEN_END = "([[:space:]\"';&|)<>]|$)"

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
MODE_LIGHT = Q + "--mode" + Q + "(=|[[:space:]]+)" + Q + "light" + END
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
WHY_HUMAN = T(
    "\n\nThis command is the human's, whether or not the dialog is on. A human runs it in their\n"
    "own terminal, outside the agent session; an unattended run exports AI_UNATTENDED=1 in the\n"
    "launcher's environment. See .ai/policies/safety.md.")
WHY_PICK = T(
    "\n\nWith the dialog on, this command runs from an agent session only as the human's pick.\n"
    "The command that needs it opened a decision: 'state.py decision show' prints the dialog;\n"
    "send it and run the picked command verbatim, once. Otherwise the human runs it in their\n"
    "own terminal. See .ai/policies/safety.md.")
# R36.11: running the dialog's recorder by hand would forge the human's answer.
# dialog-gate.py in command position — the program itself, or the script a
# python runs — after a separator, a quote, exec/env/command/nohup/time/sudo
# and their words; naming it as an argument (grep, git diff, chmod) is not running it.
DIALOG_GATE_RE = ("(^|[|;&(`{'\"]|\\$\\()[[:space:]]*((exec|env|command|nohup|time|sudo)([[:space:]]+[^[:space:]|;&]+)*"
                  "[[:space:]]+)?(" + Q + "[^[:space:]'\"|;&]*python[0-9.]*" + Q
                  + "([[:space:]]+-[^[:space:]]+)*[[:space:]]+)?" + Q + "[^[:space:]'\"|;&]*dialog-gate\\.py" + Q
                  + "([[:space:]|;&)<>]|$)")
VERBS_RE = ("(^|[^A-Za-z0-9_.-])(cp|mv|install|rsync|rm|rmdir|unlink|tee|truncate|shred|touch|ln|chmod|chown|"
            "dd|sed|perl|ruby)([^A-Za-z0-9_.-]|$)")
SEGMENT = "^[[:space:]]*"
MOVERS = SEGMENT + "(cp|mv|install|rsync|rm|rmdir|unlink)([[:space:]]|$)"
MOVER_VERBS = ("cp", "mv", "install", "rsync", "rm", "rmdir", "unlink")
REMOVE_VERBS = ("rm", "rmdir", "unlink")
MOVER_CHUNK = 32768
GLOBBY = set("][*?$`{}()\\~@!+")

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
# An interpreter one-liner is not parsed, its text is scanned: one that names a
# secret, or one that names a control file and looks like a write, is refused (H3).
INTERP_RE = "(^|[|;&[:space:]])(python3?|perl|ruby|node|php)([[:space:]]+-[^[:space:]]+)*[[:space:]]+-(c|e)([[:space:]]|$)"
CONTROL_TEXT_RE = "\\.ai/state/|\\.ai/reports/"
INPLACE_RE = ("(^|[|;&[:space:]])(perl|ruby)([[:space:]]+-([CEIMmr][[:space:]]*[^[:space:]]+|[^[:space:]]+))*"
              "[[:space:]]+-[acdfghlnpsStTuUvwWXy]*i")
EVAL_WORD_RE = "(^|[|;&[:space:]])eval([[:space:]]|$)"
SECRET_TEXT_RE = "\\.env|secrets?/|credentials?|id_rsa|\\.pem|\\.aws"
WRITE_CALL_RE = (
    "(^|[^A-Za-z0-9_])(write|writelines|write_text|write_bytes|write_file|writeFile|writeFileSync|appendFile|"
    "appendFileSync|createWriteStream|binwrite|syswrite|fwrite|fputs|file_put_contents|dump|unlink|unlinkSync|"
    "remove|removedirs|rename|renames|renameSync|rmdir|rmdirSync|rm|rmSync|rmtree|mkdir|mkdirSync|makedirs|"
    "mkdtemp|truncate|truncateSync|ftruncate|symlink|symlinkSync|symlink_to|hardlink_to|link|linkSync|link_to|"
    "touch|chmod|chown|utime|utimes|copyFile|copyFileSync|cp|cpSync|move|delete|system|exec|execSync|execFile|"
    "execFileSync|spawn|spawnSync|popen|passthru|shell_exec|proc_open|fork|eval|copy_into|move_into)"
    "([[:space:]]*\\(|[[:space:]]+['\"$])|(^|[^A-Za-z0-9_.])copy[[:space:]]*\\(")
WRITE_WORD_RE = ("subprocess|shutil|child_process|FileUtils|Open3|O_(WRONLY|RDWR|CREAT|APPEND|TRUNC)|os\\.replace|"
                 "inplace|`|\\$\\(|%x[^A-Za-z0-9_[:space:]]|(^|[^A-Za-z0-9_])qx[^A-Za-z0-9_[:space:]]")
FIRST_ARG = "([^,()'\"]|'[^']*'|\"[^\"]*\"|\\(([^()]|\\([^()]*\\))*\\))*"
WRITE_PATHREPL_RE = "\\.replace[[:space:]]*\\(" + FIRST_ARG + "\\)"
WRITE_PATHCOPY_RE = "\\.copy[[:space:]]*\\([[:space:]]*[^)[:space:]]"
WRITE_MODE_RE = ("((open[A-Za-z]*|new([[:space:]]+[A-Za-z_][A-Za-z0-9_:]*)?|FileIO)[[:space:]]*(\\(|[[:space:]])"
                 + FIRST_ARG + ",|mode[[:space:]]*=|open[A-Za-z]*[[:space:]]*\\()[[:space:]]*\\\\?['\"]"
                 "([rbtU]*[wax+][rbtU+]*\\\\?['\"]|>|\\+|-?\\|[^[:space:]|])")
WRITE_REDIR_RE = (">[>|]?[[:space:]]*['\"]?[^[:space:]'\"|;&<>]*\\.ai/(state|reports)/|"
                  "(^|[^A-Za-z0-9_.-])tee[[:space:]][^|;&]*\\.ai/(state|reports)/")

_SED1 = "[0-9]*[<>]{1,2}&[0-9]+"
_SED2 = "(&|[0-9]*)[<>]{1,2}[[:space:]]*[^[:space:]|;&<>]*"
_KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time", "exec",
             "command", "nohup", "builtin", "env", "sudo"}
_FLAGGED = {"time", "exec", "command", "env", "sudo"}
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
_SPECIAL_OUT = re.compile(r"""['$"#<(\n`)&;|\\]""")
_SPECIAL_D = re.compile(r'["$`\n\\]')
_SPECIAL_A = re.compile(r"['\n\\]")
_FIND_PRUNE_ROOTS = {".git", "vendor", "node_modules", "projects"}
_FIND_PRUNE_SCAN = {".git", "vendor", "node_modules", "bower_components", "third_party", "Pods",
                    "site-packages", ".venv", ".pnpm", ".yarn"}


class LoopError(OSError):
    """A path that does not resolve: realpath prints an error, not a line."""


def realpath_m(path):
    """`realpath -m` of one absolute path: every link that exists resolved,
    what does not exist appended as written, `..` after resolution; a symlink
    loop raises LoopError."""
    seen = {}

    def join(base, rest):
        if rest.startswith(b"/"):
            base = b"/"
        for name in rest.split(b"/"):
            if name in (b"", b"."):
                continue
            if name == b"..":
                base = os.path.dirname(base) if base != b"/" else base
                continue
            new = base.rstrip(b"/") + b"/" + name
            try:
                is_link = stat.S_ISLNK(os.lstat(new).st_mode)
            except OSError:
                is_link = False
            if not is_link:
                base = new
                continue
            if new in seen:
                if seen[new] is None:
                    raise LoopError()
                base = seen[new]
                continue
            seen[new] = None
            try:
                target = os.readlink(new)
            except OSError as exc:
                raise LoopError() from exc
            base = join(base, target)
            seen[new] = base
        return base

    try:
        return bytes_b(join(b"/", b_bytes(path)))
    except RecursionError as exc:
        raise LoopError() from exc


def find_print(start, maxdepth, prune):
    """`find START -maxdepth N \\( -name A -o … \\) -prune -o -print`, in
    name order (not find's readdir order), links not followed, errors silent."""
    def walk(path, name, depth):
        if name in prune:
            return
        yield path
        if depth >= maxdepth:
            return
        try:
            with os.scandir(b_bytes(path)) as it:
                entries = list(it)
        except OSError:
            return
        # by name, not readdir order: which held file a refusal names must not depend
        # on the filesystem (ext4 here put .ai/policies first, the CI runner .ai/state)
        for e in sorted(entries, key=lambda e: e.name):
            try:
                is_d = e.is_dir(follow_symlinks=False)
            except OSError:
                is_d = False
            child = (path.rstrip("/") if path != "/" else "") + "/" + bytes_b(e.name)
            if is_d:
                yield from walk(child, bytes_b(e.name), depth + 1)
            elif bytes_b(e.name) not in prune:
                yield child
    base = start.rstrip("/").rsplit("/", 1)[-1] if start.rstrip("/") else "/"
    try:
        st = os.lstat(b_bytes(start))
    except OSError:
        return
    if stat.S_ISLNK(st.st_mode):
        if base not in prune:
            yield start                     # -P: a start that is a link is not entered
        return
    yield from walk(start, base, 0)


def shell_segments(cmd):
    """The awk segmenter of shell_segments, character for character: the
    simple commands of a shell line, verb first, one per output line."""
    src = cmd + "\n"
    n = len(src)
    out = []
    cur = []
    stk, qst = [], []
    q = ""
    nh = 0
    hd, hs = [], []
    i = 0

    def emit():
        s = "".join(cur)
        cur.clear()
        while True:
            s = s.lstrip(" \t")
            if s == "":
                return
            qq = ""
            k = 0
            ln = len(s)
            while k < ln:
                c = s[k]
                if qq:
                    if c == qq:
                        qq = ""
                elif c in "\"'":
                    qq = c
                elif c in " \t":
                    break
                k += 1
            w = s[:k]
            if w in _KEYWORDS:
                s = s[k:]
                if w in _FLAGGED:
                    while True:
                        s = s.lstrip(" \t")
                        if not s.startswith("-"):
                            break
                        j = 0
                        while j < len(s) and s[j] not in " \t":
                            j += 1
                        s = s[j:]
                continue
            if _ASSIGN.match(w):
                s = s[k:]
                continue
            break
        out.append(s)

    def cur_ends(chars):
        return bool(cur) and cur[-1][-1:] in chars and cur[-1][-1:] != ""

    while i < n:
        c = src[i]
        d = src[i + 1] if i + 1 < n else ""
        if q == "s":
            j = src.find("'", i)
            k = src.find("\n", i)
            if j < 0:
                j = n
            if 0 <= k < j:
                cur.append(src[i:k] + " ")
                i = k + 1
                continue
            cur.append(src[i:j + 1])
            i = j + 1
            if j < n:
                q = ""
            continue
        if q == "a":
            m = _SPECIAL_A.search(src, i)
            j = m.start() if m else n
            if j > i:
                cur.append(src[i:j])
                i = j
                continue
            if c == "\\":
                cur.append(c + d)
                i += 2
                continue
            if c == "'":
                q = ""
            cur.append(" " if c == "\n" else c)
            i += 1
            continue
        if c == "\\":
            if d == "\n":
                i += 2
                continue
            cur.append(c + d)
            i += 2
            continue
        if q == "d":
            m = _SPECIAL_D.search(src, i)
            j = m.start() if m else n
            if j > i:
                cur.append(src[i:j])
                i = j
                continue
            if c == '"':
                q = ""
                cur.append(c)
                i += 1
                continue
            if c == "$" and d == "(":
                stk.append("p")
                qst.append(q)
                q = ""
                emit()
                i += 2
                continue
            if c == "`":
                stk.append("b")
                qst.append(q)
                q = ""
                emit()
                i += 1
                continue
            if c == "$":
                cur.append(c)
                i += 1
                continue
            cur.append(" " if c == "\n" else c)
            i += 1
            continue
        # outside quotes
        m = _SPECIAL_OUT.search(src, i)
        j = m.start() if m else n
        if j > i:
            cur.append(src[i:j])
            i = j
            continue
        if c == "'":
            q = "s"
            cur.append(c)
            i += 1
            continue
        if c == "$" and d == "'":
            q = "a"
            cur.append(c + d)
            i += 2
            continue
        if c == '"':
            q = "d"
            cur.append(c)
            i += 1
            continue
        if c == "#" and (not cur or "".join(cur) == "" or cur_ends(" \t")):
            k = src.find("\n", i)
            i = k if k >= 0 else n
            continue
        if c == "<" and d == "<" and src[i + 2:i + 3] == "<":
            cur.append("<<<")
            i += 3
            continue
        if (c == "$" and d == "(" and src[i + 2:i + 3] == "(") or (c == "(" and d == "("):
            j = i + (3 if c == "$" else 2)
            depth = 2
            while j < n and depth > 0:
                e = src[j]
                if e == "(":
                    depth += 1
                elif e == ")":
                    depth -= 1
                j += 1
            cur.append(src[i:j])
            i = j
            continue
        if c == "<" and d == "<":
            j = i + 2
            strip = 0
            if src[j:j + 1] == "-":
                strip = 1
                j += 1
            while src[j:j + 1] in (" ", "\t") and j < n:
                j += 1
            w = []
            wq = ""
            while j < n:
                e = src[j]
                if wq:
                    if e == wq:
                        wq = ""
                    else:
                        w.append(e)
                    j += 1
                    continue
                if e in "'\"":
                    wq = e
                    j += 1
                    continue
                if e == "\\":
                    w.append(src[j + 1:j + 2])
                    j += 2
                    continue
                if e in " \t\n;&|<>()":
                    break
                w.append(e)
                j += 1
            word = "".join(w)
            if word:
                nh += 1
                hd.append(word)
                hs.append(strip)
            i = j
            continue
        if c == "\n":
            emit()
            i += 1
            for h in range(nh):
                while i < n:
                    e = src.find("\n", i)
                    line = src[i:e] if e >= 0 else src[i:]
                    i = e + 1 if e >= 0 else n
                    if hs[h]:
                        line = line.lstrip("\t")
                    if line == hd[h]:
                        break
            nh = 0
            hd, hs = [], []
            continue
        if c == "$" and d == "(":
            stk.append("p")
            qst.append(q)
            emit()
            i += 2
            continue
        if c == "$":
            cur.append(c)
            i += 1
            continue
        if c == "`":
            if stk and stk[-1] == "b":
                stk.pop()
                q = qst.pop()
            else:
                stk.append("b")
                qst.append(q)
            emit()
            i += 1
            continue
        if c == "(":
            stk.append("p")
            qst.append(q)
            emit()
            i += 1
            continue
        if c == ")":
            if stk and stk[-1] == "p":
                stk.pop()
                q = qst.pop()
            emit()
            i += 1
            continue
        if c == "&" and (cur_ends("<>") or d == ">"):
            cur.append(c)
            i += 1
            continue
        if c in ";|&":
            emit()
            i += 1
            continue
        cur.append(c)
        i += 1
    emit()
    return chomp_all("".join(s + "\n" for s in out))


class PathGuard:                            # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, ctx):
        self.ctx = ctx
        self.m = ctx.matcher
        self.loc = ctx.loc
        self.p = ctx.payload
        self.cwd = ctx.payload.cwd
        self.home = env_b("HOME")
        self.task_active = None
        self.task_id = "?"
        self.work = {"classify": 0, "scan": 0, "token": 0}
        self.caps = {"classify": 64, "scan": 16, "token": 256}
        self.cover_done = False
        self.cover_joined = ""
        self.cover_roots = ""
        self.root = ""
        self.deny_p = self.allow_p = self.prot_p = self.task_p = ""
        self.interesting = self.loose = self.loose_joined = ""
        self.roots, self.prefixes, self.renamed = [], [], []
        self.anch = {"PROT": [], "TASK": []}

    # -------------------------------------------------------------- clock and caps

    def clock_ok(self):
        return self.ctx.clock.seconds() < 6

    def work_cap(self, kind):
        self.work[kind] += 1
        if not (self.work[kind] <= self.caps[kind] and self.clock_ok()):
            raise Deny(WHY_WORK_CAP)

    def work_clock(self):
        if not self.clock_ok():
            raise Deny(WHY_WORK_CAP)

    # -------------------------------------------------------------- the task

    def _state_file(self):
        """R34: state.json, or the legacy current.json for one version."""
        new = self.root + "/.ai/state/state.json"
        return new if is_file(new) else self.root + "/.ai/state/current.json"

    def _task_line(self):
        loaded = load_json_file(self._state_file())
        out = []
        if loaded is not None:
            for doc in loaded[0]:
                if doc is not None and not isinstance(doc, dict):
                    continue
                stage = doc.get("current_stage") if doc else None
                task = doc.get("task_id") if doc else None
                stage = "" if stage is None or stage is False else stage
                task = "?" if task is None or task is False else task
                out.append(jq_tostring(stage) + "\t" + jq_tostring(task) + "\n")
        return chomp_all(T("".join(out)))

    def task_in_flight(self, remember=True):
        """task_in_flight. With remember=False it is asked from a subshell: an
        answer the guard already had is used, a new one is not kept."""
        if self.task_active is None:
            active, task_id = "no", self.task_id
            if is_file(self._state_file()):
                line = self._task_line()
                if line.split("\t", 1)[0] != "done":
                    active = "yes"
                if line:
                    task_id = line.split("\t", 1)[1] if "\t" in line else line
            if not remember:
                return active == "yes"
            self.task_active, self.task_id = active, task_id
        return self.task_active == "yes"

    # -------------------------------------------------------------- patterns

    def load_patterns(self):
        files = [f for f in (self.ctx.hook_dir + "/ai-path-guard-defaults.json",
                             self.root + "/.ai/policies/path-guard.json") if is_file(f)]
        tagged = []
        for f in files:
            loaded = load_json_file(f)
            if loaded is None:
                continue
            for doc in loaded[0]:
                if doc is not None and not isinstance(doc, dict):
                    continue
                for tag, key in (("d", "deny_patterns"), ("a", "allow_patterns"),
                                 ("p", "protected_config_patterns"), ("k", "task_protected_patterns"),
                                 # A project's list from before 3.4 keeps its read and write deny.
                                 ("d", "dependency_instruction_patterns")):
                    v = doc.get(key) if doc else None
                    for item in jq_iter(v if v is not None and v is not False else []):
                        if is_jq_string(item) and item != "":
                            tagged.extend((tag, T(piece)) for piece in item.split("\n"))
        key = self.loc.sort_key
        seen, lists = set(), {"d": "", "a": "", "p": "", "k": ""}
        for tag, pat in sorted(tagged, key=lambda t: (key(t[0]), key(t[1]))):
            k = (key(tag), key(pat))
            if k in seen:
                continue
            seen.add(k)
            lists[tag] += pat + "\n"
        self.deny_p = chomp_all(lists["d"])
        self.allow_p = chomp_all(lists["a"])
        self.prot_p = chomp_all(lists["p"])
        self.task_p = chomp_all(lists["k"])

    def build_loose(self):
        interesting, loose_all = [], []
        for pattern in herestring_lines(self.deny_p + "\n" + self.prot_p + "\n" + self.task_p):
            if not pattern:
                continue
            interesting.append(pattern + "\n")
            loose = pattern[5:] if pattern.startswith("(^|/)") else pattern
            loose = loose[1:] if loose.startswith("^") else loose
            loose = strip1(loose, "$")
            loose_all.append(loose.replace("$", TOKEN_END) + "\n")
        self.interesting = chomp_all("".join(interesting))
        self.loose = chomp_all("".join(loose_all))
        self.loose_joined = self.loose.replace("\n", "|")

    # -------------------------------------------------------------- anchoring

    def setup_anchors(self):
        self.roots, self.prefixes, self.renamed = [], [], []

        def anchor_root(d, prefix):
            if not d.startswith("/"):
                return
            norm = lexnorm(d)
            self.roots.append(norm)
            self.prefixes.append(prefix)
            self.renamed.append(bool(prefix) and norm.rsplit("/", 1)[-1] + "/" != prefix)

        anchor_root(self.root, "")
        anc = self.root.rsplit("/", 1)[0] if "/" in self.root else ""
        while anc:
            if is_dir(anc + "/.ai"):
                anchor_root(anc, "")
            anc = anc.rsplit("/", 1)[0] if "/" in anc else ""
        if self.root != "/" and is_dir("/.ai"):
            anchor_root("/", "")
        if self.home:
            anchor_root(self.home + "/.claude", ".claude/")
            anchor_root(self.home + "/.codex", ".codex/")
        ccd, cxh = env_b("CLAUDE_CONFIG_DIR"), env_b("CODEX_HOME")
        if ccd:
            anchor_root(ccd, ".claude/")
        if cxh:
            anchor_root(cxh, ".codex/")
        self.anch = {"PROT": anchor_list(self.prot_p), "TASK": anchor_list(self.task_p)}

    def anchor_rels(self, path, roots, rels):
        np = lexnorm(path)
        tail = "/" if path.endswith("/") or path.endswith("/.") else ""
        for i, r in enumerate(roots):
            if r == "/":
                rel = np[1:] if np.startswith("/") else np
            elif np == r:
                rel = ""
            elif np.startswith(r + "/"):
                rel = np[len(r) + 1:]
            else:
                continue
            rel = self.prefixes[i] + rel if rel else strip1(self.prefixes[i], "/")
            if rel:
                rels.append(rel + tail)

    def anchored_hit(self, kind, path, rels):
        for rx, orig, absolute in self.anch[kind]:
            if absolute:
                if self.m.ere_match(rx, path):
                    return orig
                continue
            for r in rels:
                if self.m.ere_match(rx, r):
                    return orig
        return None

    def unanchored_hit(self, kind, path):
        for _, orig, _ in self.anch[kind]:
            if self.m.ere_match(orig, path):
                return orig
        return None

    def phys_path(self, p):
        tail = "/" if p.endswith("/") or p.endswith("/.") else ""
        d = lexnorm(p)
        rest = ""
        while d != "/" and not is_dir(d):
            rest = "/" + d.rsplit("/", 1)[-1] + rest
            d = d.rsplit("/", 1)[0] or "/"
        pwd = cd_physical(d)
        if pwd is None:
            return None
        return (strip1(pwd, "/") + rest + tail) or "/"

    # -------------------------------------------------------------- classify

    def classify(self, p):
        """(kind, pattern) or None: protected, task or sensitive."""
        m = self.m
        subject = p
        for i, r in enumerate(self.roots):
            if self.renamed[i] and p.startswith(r + "/"):
                subject += "\n" + self.prefixes[i] + p[len(r) + 1:]
        if not m.matches_joined(subject, self.interesting):
            return None
        if m.matches_any(self.allow_p, p) is not None:
            return None
        anchored = not (any(c in p for c in "$`~*?{[") or self.loc.length(p) > 4096)
        task_hit = None
        if not anchored:
            hit = self.unanchored_hit("PROT", p)
            if hit is not None:
                return ("protected", hit)
            if self.task_p:
                task_hit = self.unanchored_hit("TASK", p)
        else:
            rels = []
            self.anchor_rels(p, self.roots, rels)
            hit = self.anchored_hit("PROT", p, rels)
            if hit is not None:
                return ("protected", hit)
            task_hit = self.anchored_hit("TASK", p, rels)
            if task_hit is None and (self.unanchored_hit("PROT", p) is not None
                                     or self.unanchored_hit("TASK", p) is not None):
                resolved = self.phys_path(p)
                if resolved is not None:
                    phys_roots = [cd_physical(r) or r for r in self.roots]
                    rels = []
                    self.anchor_rels(resolved, self.roots, rels)
                    self.anchor_rels(resolved, phys_roots, rels)
                    hit = self.anchored_hit("PROT", resolved, rels)
                    if hit is not None:
                        return ("protected", hit)
                    task_hit = self.anchored_hit("TASK", resolved, rels)
        if task_hit is not None:
            return ("task", task_hit)
        hit = m.matches_any(self.deny_p, p)
        if hit is not None:
            return ("sensitive", hit)
        return None

    def check_path(self, literal, verb):
        a = abs_path(literal, self.cwd)
        real = real_path(literal, self.cwd)
        for cand in [a] if real == a else [a, real]:
            v = self.classify(cand)
            if v is None:
                continue
            kind, pattern = v
            if verb == "read" and kind != "sensitive":
                hit = self.m.matches_any(self.deny_p, cand)
                if hit is not None:
                    raise Deny("Refusing to read a sensitive path: %s (matched: %s)%s"
                               % (literal, hit, WHY_SENSITIVE))
            if kind == "protected":
                if verb == "read":
                    continue
                raise Deny("Refusing to %s a RiskRails control file: %s (matched: %s)%s"
                           % (verb, literal, pattern, WHY_PROTECTED))
            if kind == "task":
                if verb == "read" or not self.task_in_flight():
                    continue
                raise Deny("Refusing to %s runtime configuration while task %s is in flight: %s (matched: %s)%s"
                           % (verb, self.task_id, literal, pattern, WHY_TASK))
            raise Deny("Refusing to %s a sensitive path: %s (matched: %s)%s"
                       % (verb, literal, pattern, WHY_SENSITIVE))

    # -------------------------------------------------------------- covers

    def cover_init(self):
        if self.cover_done:
            return
        self.cover_done = True
        parts = []
        for p in read_lines(self.prot_p + "\n" + self.task_p + "\n"):
            if not p:
                continue
            p = p[5:] if p.startswith("(^|/)") else p
            p = p[1:] if p.startswith("^") else p
            parts.append(p + "\n")
        self.cover_joined = chomp_all("".join(parts)).replace("\n", "|")
        home = self.home
        roots = []
        for r in (self.root + "/.ai", self.root + "/.claude", self.root + "/.codex",
                  env_b("CLAUDE_CONFIG_DIR") or home + "/.claude", env_b("CODEX_HOME") or home + "/.codex"):
            got = self.realpath_m_arg(r)
            if got is not None:
                roots.append(got)
        self.cover_roots = chomp_all("".join(r + "\n" for r in self.sort_u(roots)))

    def realpath_m_arg(self, p):
        """One argument of `realpath -m`, as the line it prints, or None."""
        if p == "":
            return None
        full = p if p.startswith("/") else self.ctx.pwd.rstrip("/") + "/" + p
        try:
            return realpath_m(full)
        except LoopError:
            return None

    def sort_u(self, items):
        key = self.loc.sort_key
        out, seen = [], set()
        for item in sorted(items, key=key):
            k = key(item)
            if k not in seen:
                seen.add(k)
                out.append(item)
        return out

    def _roots_under(self, c):
        for r in herestring_lines(self.cover_roots):
            if r and (c == "/" or r == c or r.startswith(c + "/")) and exists(r):
                yield r

    def covers_work(self, real, lexical):
        c = strip1(real, "/") or "/"
        for _ in self._roots_under(c):
            self.work_cap("scan")
            return True
        if is_dir(c):
            self.work_cap("scan")
            return True
        return bool(lexical)

    def covers_protected(self, real):
        c = strip1(real, "/") or "/"
        for line in (c, c + "/"):
            if not self.m.ere_match(self.loose_joined, line):
                continue
            v = self.classify(line)
            if v and (v[0] == "protected" or (v[0] == "task" and self.task_in_flight(remember=False))):
                return strip1(line, "/")
        roots = list(self._roots_under(c))
        scan = [c] if is_dir(c) else []
        if not roots and not scan:
            return None

        def stream():
            for r in roots:
                yield from find_print(r, 3, _FIND_PRUNE_ROOTS)
            count = 0
            for s in scan:
                for path in find_print(s, 6, _FIND_PRUNE_SCAN):
                    if count >= 20000:
                        return
                    count += 1
                    yield path

        pats = self.cover_joined.split("\n")
        valid = all(self.m.ere.valid(pt) for pt in pats)
        picked = 0
        if not valid:
            return None
        for path in stream():
            for line in (path, path + "/"):
                if not any(self.m.search_c(pt, line) for pt in pats):
                    continue
                picked += 1
                if picked > 50:
                    return None
                v = self.classify(line)
                if v and (v[0] == "protected" or (v[0] == "task" and self.task_in_flight(remember=False))):
                    return strip1(line, "/")
        return None

    def loose_hits(self, lines):
        """1-based numbers of the lines that match the loose patterns, bytewise."""
        pats = self.loose_joined.split("\n")
        if not all(self.m.ere.valid(pt) for pt in pats):
            return []
        return [n for n, line in enumerate(lines, 1) if any(self.m.search_c(pt, line) for pt in pats)]

    # -------------------------------------------------------------- the movers pass

    def movers(self, segs):
        m = self.m
        if not (segs and m.ere_match(MOVERS, segs)):
            return
        self.cover_init()
        sed1 = m.ere.compile_ere(self._loc_pat(_SED1), self._mode(), capture=True).rx
        sed2 = m.ere.compile_ere(self._loc_pat(_SED2), self._mode(), capture=True).rx
        kept = []
        for line in segs.split("\n"):
            t = self._loc_text(line)
            t = sed1.sub("", t) if sed1 else t
            t = sed2.sub("", t) if sed2 else t
            line = self._from_loc(t)
            if m.search_c(MOVERS, line):
                kept.append(line)
        segments = chomp_all("".join(k + "\n" for k in kept))
        st = MoverState()
        cwd_slash = strip1(self.cwd, "/") + "/"
        length = self.loc.length
        mover_base = max(length(self.cwd), length(self.home)) + 2
        pending = ""
        for seg in herestring_lines(segments):
            self.work_clock()
            if not st.batch + length(seg) < MOVER_CHUNK:
                self.mover_check(st)
            st.batch += length(seg) + 1
            operands = [w for w in re.split("[ \t]+", seg) if w]
            if len(operands) <= 1:
                continue
            verb = operands[0]
            if verb not in MOVER_VERBS:
                continue
            dest, sources, opts_done, want_dest = "", [], False, False
            stop = False
            for w in operands[1:]:
                self.work_clock()
                if length(w) > 4096:
                    if any(c in GLOBBY for c in w):
                        pending = ("Refusing a shell %s with a %d-character operand that holds a glob or "
                                   "expansion character: the guard cannot check what it expands to."
                                   % (verb, length(w)))
                        stop = True
                        break
                    if not opts_done and not want_dest:
                        if w.startswith("--target-directory="):
                            dest = "LONG-OPERAND"
                            continue
                        if w.startswith("-"):
                            continue
                    w = "LONG-OPERAND"
                if want_dest:
                    want_dest = False
                    dest = w
                    continue
                if not opts_done:
                    if w == "--":
                        opts_done = True
                        continue
                    if w in ("-t", "--target-directory"):
                        if verb not in REMOVE_VERBS:
                            want_dest = True
                        continue
                    if w.startswith("--target-directory="):
                        dest = w.split("=", 1)[1]
                        continue
                    if w.startswith("-"):
                        continue
                w = w.lstrip("\"'").rstrip("\"'")
                if w:
                    sources.append(w)
            if stop:
                break
            dl = 0
            if verb not in REMOVE_VERBS:
                dl = length(dest)
                if not dest and sources:
                    dl = length(sources[-1])
            if st.seg_first and not (st.batch + (2 * len(sources) + 1) * (mover_base + dl) + 2 * length(seg)
                                     < MOVER_CHUNK):
                self.mover_check(st)
            first = len(st.cands)
            if verb in REMOVE_VERBS:
                for src in sources:
                    st.cands.append(src)
                    st.covers.append("yes")
            else:
                if not dest:
                    if len(sources) <= 1:
                        continue
                    dest = sources.pop()
                dest = dest.lstrip("\"'").rstrip("\"'")
                if not dest:
                    continue
                into = ""
                for src in sources:
                    if verb in ("rsync", "cp") and (src.endswith("/") or src.endswith("/.")):
                        into = "yes"
                st.cands.append(dest)
                st.covers.append(into)
                for src in sources:
                    src = strip1(strip1(src, "/"), "/.")
                    st.cands.append(strip1(dest, "/") + "/" + src.rsplit("/", 1)[-1])
                    st.covers.append("yes")
                    if verb == "mv":
                        st.cands.append(src)
                        st.covers.append("yes")
            if len(st.cands) <= first:
                continue
            for k in range(first, len(st.cands)):
                self.work_clock()
                cand = st.cands[k]
                if cand in ("~", "$HOME", "${HOME}"):
                    cand = self.home
                elif cand.startswith("~/"):
                    cand = self.home + "/" + cand[2:]
                elif cand.startswith("$HOME/"):
                    cand = self.home + "/" + cand[6:]
                elif cand.startswith("${HOME}/"):
                    cand = self.home + "/" + cand[8:]
                if not cand.startswith("/"):
                    cand = cwd_slash + cand
                st.abss.append(cand)
                st.batch += length(cand) + 1
            st.seg_first.append(first)
            st.seg_count.append(len(st.cands) - first)
            st.seg_verb.append(verb)
        self.mover_check(st)
        if pending:
            raise Deny(pending)

    def _mode(self):
        return "u" if self.loc.utf8 else "b"

    def _loc_pat(self, p):
        return self.loc.u(p) if self.loc.utf8 else p

    def _loc_text(self, s):
        return self.loc.u(s) if self.loc.utf8 else s

    def _from_loc(self, t):
        return t.encode("utf-8", "surrogateescape").decode("latin-1") if self.loc.utf8 else t

    def mover_resolve(self, st, first, end, one_at_a_time=False):
        length = self.loc.length
        size, cuts = 0, []
        for k in range(first, end):
            self.work_clock()
            if not size < MOVER_CHUNK:
                cuts.append(k)
                size = 0
            size += length(st.abss[k]) + 1
        cuts.append(end)
        at, got = first, []
        for k in cuts:
            self.work_clock()
            args = st.abss[at:k]
            had = len(got)
            for a in args:
                r = self.realpath_m_arg(a)
                if r is not None:
                    got.append(r)
            if len(got) - had != len(args):
                if not one_at_a_time:
                    return False
                got = []
                for n in range(first, end):
                    self.work_cap("classify")
                    r = self.realpath_m_arg(st.abss[n])
                    got.append(r if r else st.abss[n])
                break
            at = k
        for n in range(first, end):
            st.reals[n] = got[n - first]
        at = first
        for k in cuts:
            self.work_clock()
            lines = []
            for n in range(at, k):
                norm = strip1(st.reals[n], "/") or "/"
                lines += [st.abss[n] + " " + st.reals[n], norm, norm + "/"]
            for r in self.loose_hits(lines):
                st.hits.add(3 * at + r)
            at = k
        return True

    def mover_check(self, st):
        per_seg = False
        st.reals, st.hits = {}, set()
        if st.abss and not self.mover_resolve(st, 0, len(st.abss)):
            per_seg = True
        for s, first in enumerate(st.seg_first):
            last = first + st.seg_count[s]
            verb = st.seg_verb[s]
            if per_seg:
                self.mover_resolve(st, first, last, one_at_a_time=True)
            self.work_clock()
            for i in range(first, last):
                self.work_clock()
                a, real, cand = st.abss[i], st.reals[i], st.cands[i]
                how = "copy or move into"
                if verb in REMOVE_VERBS:
                    how = "removal of"
                elif verb == "mv" and i > first and a != strip1(st.abss[first], "/") + "/" + a.rsplit("/", 1)[-1]:
                    how = "move of"
                verdict = None
                lexical = (3 * i + 2) in st.hits or (3 * i + 3) in st.hits
                if (3 * i + 1) in st.hits or (st.covers[i] == "yes" and lexical):
                    self.work_cap("classify")
                if (3 * i + 1) in st.hits:
                    verdict = (self.classify(a) or self.classify(real)
                               or self.classify(real_path(a, self.cwd)))
                kind = verdict[0] if verdict else ""
                if kind == "protected":
                    raise Deny("Refusing a shell %s a RiskRails control file: %s%s" % (how, cand, WHY_PROTECTED))
                if kind == "task" and self.task_in_flight():
                    raise Deny("Refusing a shell %s runtime configuration while task %s is in flight: %s%s"
                               % (how, self.task_id, cand, WHY_TASK))
                if st.covers[i] != "yes":
                    continue
                if not self.covers_work(real, lexical):
                    continue
                found = self.covers_protected(real)
                if found is None:
                    continue
                verdict = self.classify(found) or self.classify(found + "/")
                held = "" if found == strip1(real, "/") else " (holds %s)" % found
                if verdict and verdict[0] == "protected":
                    raise Deny("Refusing a shell %s a directory that holds a RiskRails control file: %s%s%s"
                               % (how, cand, held, WHY_PROTECTED))
                raise Deny("Refusing a shell %s a directory that holds runtime configuration while task %s is "
                           "in flight: %s%s%s" % (how, self.task_id, cand, held, WHY_TASK))
        st.reset()

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

    def check(self):
        p = self.p
        if p.tool not in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"):
            return
        unattended = bool(env_b("AI_UNATTENDED"))
        if p.tool == "Bash" and not unattended:
            self.confirm_delete(p.bash_command())
        root = find_ai_root(p.cwd, self.ctx.pwd)
        if root is None:
            return
        self.root = root
        self.load_patterns()
        if not (self.deny_p + self.prot_p + self.task_p):
            return
        self.build_loose()
        self.setup_anchors()
        if p.tool == "Read":
            for f in p.target_paths():
                if f:
                    self.check_path(f, "read")
            return
        if p.tool != "Bash":
            for f in p.target_paths():
                if f:
                    self.check_path(f, "write")
            return
        self.check_bash(unattended)

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

    def interpreter_text(self, cmd):
        """The text of an interpreter one-liner or an eval, scanned whole (H3)."""
        m = self.m
        is_eval = m.ere_match(EVAL_WORD_RE, cmd)
        is_interp = m.ere_match(INTERP_RE, cmd)
        if (is_eval or is_interp) and m.ere_match(SECRET_TEXT_RE, cmd):
            raise Deny("Refusing an interpreter one-liner that references a sensitive path." + WHY_SENSITIVE)
        if m.ere_match(CONTROL_TEXT_RE, cmd):
            if is_eval or m.ere_match(INPLACE_RE, cmd):
                raise Deny("Refusing an interpreter one-liner that writes the task's own control files." + WHY_APPROVE)
            if is_interp:
                scan = cmd.replace("stdout.write", " ").replace("stderr.write", " ")
                pscan = cmd.replace("copy.copy(", " ")
                if (m.ere_match(WRITE_CALL_RE, scan) or m.ere_match(WRITE_WORD_RE, cmd)
                        or (m.ere_match("Path", cmd)
                            and (m.ere_match(WRITE_PATHREPL_RE, cmd) or m.ere_match(WRITE_PATHCOPY_RE, pscan)))
                        or (m.ere_match("open|new|FileIO", cmd) and m.ere_match(WRITE_MODE_RE, cmd))
                        or m.ere_match(WRITE_REDIR_RE, cmd)):
                    raise Deny("Refusing an interpreter one-liner that writes the task's own control files."
                               + WHY_APPROVE)

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


class MoverState:                           # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """One batch of the movers pass: candidates and the segments that own them."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.cands, self.covers, self.abss = [], [], []
        self.seg_first, self.seg_count, self.seg_verb = [], [], []
        self.reals, self.hits = {}, set()
        self.batch = 0


def lexnorm(path):
    """lexnorm: //, /./ and /../ resolved by text, no trailing slash."""
    out = []
    rest = path[1:] if path.startswith("/") else path
    for seg in (rest + "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
        else:
            out.append(seg)
    return "/" + "/".join(out) if out else "/"


def cd_physical(d):
    """$PWD after `cd -P -- "$d"`, or None when cd fails."""
    try:
        if not (is_dir(d) and os.access(b_bytes(d), os.X_OK)):
            return None
        return bytes_b(os.path.realpath(b_bytes(d)))
    except (OSError, ValueError):
        return None


def anchor_list(patterns):
    """[(anchored regex, pattern as written, matched against the absolute path)]."""
    out = []
    for p in herestring_lines(patterns):
        if not p:
            continue
        if p.startswith("(^|/)"):
            out.append(("^" + p[5:], p, False))
        elif p.startswith("^"):
            out.append((p, p, True))
        elif p.startswith("/"):
            out.append(("^" + p[1:], p, False))
        else:
            out.append(("(^|/)(" + p + ")", p, False))
    return out


def check(ctx):
    PathGuard(ctx).check()
