"""Port of hooks/lib/ai-hook-common.sh: the payload, the locale, the matching
helpers and the deny object every check shares.

Strings. A guard handles bytes — a path need not be UTF-8 — so every string here
is the latin-1 view of its bytes ("bstr": one character per byte). The JSON
payload's text is UTF-8 encoded on the way in, as jq printed it; a match that
bash ran in a UTF-8 locale decodes its operands for the match only.

The locale. bash ran [[ =~ ]] under the user's locale and the guards pinned
LC_ALL=C on some greps. Python coerces a C locale to UTF-8 at start-up (PEP 538,
540) and records it in sys.flags.utf8_mode, which is therefore how a C locale is
recognised; the coercion's LC_CTYPE is taken back out of the environment, so git
runs under the locale it was given. Collation is the user's, for `sort -u` and
for bash's pathname expansion.

Fail-open: every caller catches every exception and allows. The deny is an
exception (Deny) so that one process can run several checks and stop at the
first refusal, as the first guard to print a deny did.
"""
import json
import locale
import os
import re
import stat
import sys
import time

START = time.time()


class Deny(Exception):
    """The tool call is refused; .reason is a bstr."""

    def __init__(self, reason):
        super().__init__("deny")
        self.reason = reason


class Allow(Exception):
    """The check ends here and allows (the shell's `allow` / `exit 0`)."""


# ------------------------------------------------------------------ strings

def text_to_b(u):
    """JSON text -> bstr, as jq printed it: UTF-8, a lone surrogate as U+FFFD."""
    if any(0xD800 <= ord(c) <= 0xDFFF for c in u):
        u = "".join("�" if 0xD800 <= ord(c) <= 0xDFFF else c for c in u)
    return u.encode("utf-8").decode("latin-1")


def b_to_u(s):
    return s.encode("latin-1").decode("utf-8", "surrogateescape")


def b_bytes(s):
    return s.encode("latin-1")


def bytes_b(b):
    return b.decode("latin-1")


def chomp_all(s):
    """The string without trailing newlines, as $(...) returns it."""
    return s.rstrip("\n")


def strip1(s, suffix):
    """${s%suffix} for a literal suffix: at most one occurrence goes."""
    return s[:-len(suffix)] if suffix and s.endswith(suffix) else s


def read_lines(text):
    """The lines `while IFS= read -r line` reads from text that ends with a
    newline (a pipe, a here-string's own newline): an unterminated last line is
    not read."""
    return text.split("\n")[:-1]


def herestring_lines(s):
    """The lines read from `<<< "$s"`: the here-string adds the newline."""
    return s.split("\n")


# ------------------------------------------------------------------ locale and clock

class Locale:
    """What the shell's locale decided: UTF-8 matching, and collation."""

    def __init__(self):
        self.utf8 = False
        self.collate_c = True
        if sys.flags.utf8_mode:
            env = os.environ
            if "LC_ALL" not in env and env.get("LC_CTYPE") == "C.UTF-8":
                del env["LC_CTYPE"]         # PEP 538's coercion, not the user's
        else:
            try:
                locale.setlocale(locale.LC_CTYPE, "")
                codeset = locale.nl_langinfo(locale.CODESET).upper().replace("-", "")
                self.utf8 = codeset == "UTF8"
            except (locale.Error, ValueError, AttributeError):
                self.utf8 = False
        try:
            name = locale.setlocale(locale.LC_COLLATE, "")
        except locale.Error:
            name = "C"
        self.collate_c = name in ("C", "POSIX") or name.split(".")[0] in ("C", "POSIX")
        self._u = {}

    def u(self, s):
        """bstr -> text for a UTF-8 match, cached (patterns repeat)."""
        r = self._u.get(s)
        if r is None:
            r = b_to_u(s)
            if len(self._u) < 4096:
                self._u[s] = r
        return r

    def length(self, s):
        """${#s}: characters in a UTF-8 locale (an invalid byte counts one), bytes in C."""
        return len(b_to_u(s)) if self.utf8 and not s.isascii() else len(s)

    def sort_key(self, s):
        if self.collate_c:
            return s
        try:
            return locale.strxfrm(b_to_u(s))
        except (ValueError, OSError):
            return s


class Clock:
    """bash's SECONDS: whole seconds of wall clock since the shell started."""

    def __init__(self, start=None):
        self.start = int(time.time() if start is None else start)

    def seconds(self):
        return int(time.time()) - self.start


# ------------------------------------------------------------------ jq, the part the guards use

class JNum(str):
    """A JSON number, kept as written: jq prints a literal it did not compute
    as it was given."""


class JqError(Exception):
    """A jq filter error on one input: nothing more for that input."""


def _constant(name):
    if name == "NaN":
        return None
    return JNum("1.7976931348623157e+308" if name == "Infinity" else "-1.7976931348623157e+308")


_DECODER = json.JSONDecoder(parse_float=JNum, parse_int=JNum, parse_constant=_constant)
_WS = " \t\n\r"


def parse_stream(text):
    """(values, ok): every JSON value of a jq input stream, and False when a
    parse error ended it (the values before the error are kept)."""
    values, i, n = [], 0, len(text)
    while True:
        while i < n and text[i] in _WS:
            i += 1
        if i >= n:
            return values, True
        try:
            value, i = _DECODER.raw_decode(text, i)
        except (ValueError, RecursionError):
            return values, False
        values.append(value)


def jq_index(value, key):
    """`.key` on one value."""
    if isinstance(value, dict):
        return value.get(key)
    if value is None:
        return None
    raise JqError(key)


def jq_try_path(value, *keys):
    """`.a.b?`: the value, or _EMPTY when indexing failed."""
    try:
        for key in keys:
            value = jq_index(value, key)
    except JqError:
        return _EMPTY
    return value


_EMPTY = object()


def is_jq_string(value):
    return type(value) is str          # pylint: disable=unidiomatic-typecheck  # JNum is a str too


def jq_iter(value):
    """`.[]?`."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    return []


def jq_escape(u):
    out = ['"']
    for c in u:
        o = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif c == "\b":
            out.append("\\b")
        elif c == "\f":
            out.append("\\f")
        elif o < 0x20 or o == 0x7F:
            out.append("\\u%04x" % o)
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def jq_dump(value, pretty=False, level=0):
    """jq's JSON text of a value: -c (compact) or the default 2-space indent."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, JNum):
        return str(value)
    if isinstance(value, str):
        return jq_escape(value)
    if isinstance(value, list):
        items = [jq_dump(v, pretty, level + 1) for v in value]
        open_, close = "[", "]"
    else:
        items = ["%s:%s%s" % (jq_escape(k), " " if pretty else "", jq_dump(v, pretty, level + 1))
                 for k, v in value.items()]
        open_, close = "{", "}"
    if not items:
        return open_ + close
    if not pretty:
        return open_ + ",".join(items) + close
    pad = "  " * (level + 1)
    return open_ + "\n" + ",\n".join(pad + i for i in items) + "\n" + "  " * level + close


def jq_raw(value):
    """One value as `jq -r` prints it, without the newline (unicode text)."""
    return value if is_jq_string(value) else jq_dump(value, pretty=True)


def jq_tostring(value):
    """`tostring` / string interpolation."""
    return value if is_jq_string(value) else jq_dump(value)


def jq_field_r(values, *keys):
    """`jq -r '.a.b // empty'` over a stream: (bstr output, ok). A value whose
    filter fails prints nothing and jq goes on to the next; the exit status is
    the last value's."""
    out, ok = [], True
    for value in values:
        try:
            for key in keys:
                value = jq_index(value, key)
            ok = True
        except JqError:
            ok = False
            continue
        if value is None or value is False:
            continue
        out.append(jq_raw(value) + "\n")
    return text_to_b("".join(out)), ok


def load_json_file(path):
    """(values, ok) of a JSON file read as jq reads one, or None when absent."""
    try:
        with open(b_bytes(path), "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return parse_stream(data.decode("utf-8", "replace"))


# ------------------------------------------------------------------ the deny object

DENY_HEAD = '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":'


def deny_json(reason):
    """The deny line `jq -Rsc` printed for a bstr reason, as bytes."""
    text = b_bytes(reason).decode("utf-8", "replace")
    return (DENY_HEAD + jq_escape(text) + "}}\n").encode("utf-8")


# ------------------------------------------------------------------ the payload

class Payload:
    """read_payload's variables. Raises Allow where the shell exited 0."""

    def __init__(self, raw, pwd):
        data = raw.replace(b"\0", b"").rstrip(b"\n")     # AI_PAYLOAD=$(cat)
        if not data:
            raise Allow()
        self.values, ok = parse_stream(data.decode("utf-8", "replace"))
        if not ok:
            raise Allow()                   # `jq -rn '[inputs] …' || exit 0`
        self.command = ""
        self.command_ok = False
        v = self.values[0] if len(self.values) == 1 else None
        if isinstance(v, dict) and all(_plain(v.get(k)) for k in ("tool_name", "cwd", "hook_event_name")):
            self.tool_raw = chomp_all(_sh(v.get("tool_name")))
            self.cwd = chomp_all(_sh(v.get("cwd")))
            self.event = chomp_all(_sh(v.get("hook_event_name")))
            ti = v.get("tool_input")
            if ti is None or ti is False:
                self.command_ok = True
            elif isinstance(ti, dict) and _plain(ti.get("command")):
                self.command = chomp_all(_sh(ti.get("command")))
                self.command_ok = True
            # R36 (7d1): what binds a dialog pick to its session; empty when absent.
            for name in ("session_id", "transcript_path", "tool_use_id"):
                setattr(self, name, chomp_all(_sh(v.get(name))))
        else:
            for name in ("session_id", "transcript_path", "tool_use_id"):
                setattr(self, name, chomp_all(jq_field_r(self.values, name)[0]))
            out, ok = jq_field_r(self.values, "tool_name")
            if not ok:
                raise Allow()
            self.tool_raw = chomp_all(out)
            self.cwd = chomp_all(jq_field_r(self.values, "cwd")[0])
            self.event = chomp_all(jq_field_r(self.values, "hook_event_name")[0])
        if not self.cwd:
            self.cwd = pwd
        self.tool = {"apply_patch": "Edit", "shell": "Bash", "exec_command": "Bash",
                     "local_shell": "Bash"}.get(self.tool_raw, self.tool_raw)

    def field(self, *keys):
        """payload_field: `jq -r '.a.b // empty'`, as $( ) returns it."""
        return chomp_all(jq_field_r(self.values, *keys)[0])

    def bash_command(self):
        if self.tool != "Bash":
            return ""
        if self.command_ok:
            return self.command
        return self.field("tool_input", "command")

    def patch_paths(self):
        """The paths of a Codex patch's headers, as the sed of patch_paths printed them."""
        out = []
        text = jq_field_r(self.values, "tool_input", "command")[0]
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            if line.startswith("*** "):
                for verb in ("Add File: ", "Update File: ", "Delete File: "):
                    if line.startswith("*** " + verb):
                        line = line[4 + len(verb):]
                        out.append(line)
                        break
            if line.startswith("*** Move to: "):
                out.append(line[13:])
        return out

    def target_paths(self):
        """Every file path the call refers to, one entry per line read."""
        lines = []
        for v in self.values:
            found = [jq_try_path(v, "tool_input", k) for k in ("file_path", "notebook_path", "path")]
            edits = jq_try_path(v, "tool_input", "edits")
            if edits is _EMPTY or edits is None or edits is False:
                edits = []
            for e in jq_iter(edits):
                found.append(jq_try_path(e, "file_path"))
            for f in found:
                if is_jq_string(f) and f != "":
                    lines.extend(text_to_b(f).split("\n"))
        if self.tool_raw == "apply_patch":
            for p in self.patch_paths():
                lines.extend(p.split("\n"))
        return lines


def _plain(v):
    return v is None or v is False or is_jq_string(v)


def _sh(v):
    return text_to_b(v) if is_jq_string(v) else ""


def read_stdin_payload():
    return sys.stdin.buffer.read()


# ------------------------------------------------------------------ the filesystem, as the shell saw it

def exists(p):
    try:
        os.stat(b_bytes(p))
        return True
    except (OSError, ValueError):
        return False


def is_dir(p):
    try:
        return stat.S_ISDIR(os.stat(b_bytes(p)).st_mode)
    except (OSError, ValueError):
        return False


def is_file(p):
    try:
        return stat.S_ISREG(os.stat(b_bytes(p)).st_mode)
    except (OSError, ValueError):
        return False


def shell_pwd():
    """$PWD as bash starts with it: the inherited PWD when it names the current
    directory, else getcwd()."""
    pwd = os.environb.get(b"PWD")
    try:
        if pwd and pwd.startswith(b"/"):
            a, b = os.stat(pwd), os.stat(b".")
            if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
                return bytes_b(pwd)
        return bytes_b(os.getcwdb())
    except OSError:
        return bytes_b(pwd or b"")


def lexical(path):
    """The components of an absolute path with //, /./ and /../ resolved by text."""
    out = []
    for seg in path.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
        else:
            out.append(seg)
    return "/" + "/".join(out)


def logical_cd(d, pwd):
    """`cd "$d" && pwd` without moving: bash's logical directory, or None."""
    full = d if d.startswith("/") else strip1(pwd, "/") + "/" + d
    canon = lexical(full)
    try:
        st = os.stat(b_bytes(canon))
        if stat.S_ISDIR(st.st_mode) and os.access(b_bytes(canon), os.X_OK):
            return canon
    except (OSError, ValueError):
        pass
    try:                                    # bash's fallback: chdir as given, getcwd
        if is_dir(full) and os.access(b_bytes(full), os.X_OK):
            return bytes_b(os.path.realpath(b_bytes(full)))
    except (OSError, ValueError):
        pass
    return None


def find_ai_root(d, pwd):
    """Nearest ancestor of d holding a .ai/ directory, or None."""
    if not d:
        return None
    d = logical_cd(d, pwd)
    if d is None:
        return None
    while d and d != "/":
        if is_dir(d + "/.ai"):
            return d
        d = d.rsplit("/", 1)[0] or "/"
    return "/" if is_dir("/.ai") else None


def abs_path(p, cwd):
    """abs_path, as $(abs_path …) returns it."""
    return chomp_all(p if p.startswith("/") else strip1(cwd, "/") + "/" + p)


def realpath_strict(p):
    """`realpath "$p"` of an existing path, or None when it fails."""
    try:
        r = os.path.realpath(b_bytes(p), strict=True)
    except (OSError, ValueError, RuntimeError):
        return None
    return bytes_b(r)


def real_path(p, cwd):
    """real_path: the resolved path when it exists, else the absolute one."""
    a = abs_path(p, cwd)
    if exists(a):
        r = realpath_strict(a)
        return chomp_all(r) if r is not None else a
    return a


def runtime_hook_config(name, hook_dir):
    """The live config next to the guard, else in a runtime home — the home
    the guard runs from first (a plugin cache lies under it), then Claude's."""
    home = env_b("HOME")
    claude = env_b("CLAUDE_CONFIG_DIR") or home + "/.claude"
    codex = env_b("CODEX_HOME") or home + "/.codex"
    homes = [claude, codex]
    here, cx = realpath_strict(hook_dir) if hook_dir else None, realpath_strict(codex)
    if here and cx and here.startswith(cx + "/"):
        homes.reverse()
    for d in (hook_dir,) + tuple(h + "/hooks" for h in homes):
        if d and is_file(d + "/" + name):
            return d + "/" + name
    return None


def env_b(name, default=""):
    v = os.environb.get(name.encode())
    return bytes_b(v) if v is not None else default


# ------------------------------------------------------------------ matching

class Matcher:
    """ere_match and its callers, under one locale."""

    def __init__(self, loc):
        self.loc = loc
        from guard import ere          # pylint: disable=import-outside-toplevel
        self.ere = ere

    def search(self, pattern, subject):
        """[[ $subject =~ $pattern ]] on one line, in the process locale."""
        if self.loc.utf8:
            return self.ere.search(self.loc.u(pattern), self.loc.u(subject), "u")
        return self.ere.search(pattern, subject, "b")

    def search_c(self, pattern, subject):
        """The same under LC_ALL=C."""
        return self.ere.search(pattern, subject, "b")

    def groups(self, pattern, subject, bytewise=False):
        """BASH_REMATCH after [[ $subject =~ $pattern ]], or None."""
        if self.loc.utf8 and not bytewise:
            g = self.ere.match_groups(self.loc.u(pattern), self.loc.u(subject), "u")
            return None if g is None else [s.encode("utf-8", "surrogateescape").decode("latin-1") for s in g]
        return self.ere.match_groups(pattern, subject, "b")

    def grep_q(self, pattern, lines):
        """`LC_ALL=C grep -aqE -f <(printf '%s\\n' "$pattern")` over lines."""
        pats = pattern.split("\n")
        if not all(self.ere.valid(p) for p in pats):
            return False
        return any(self.ere.search(p, line, "b") for line in lines for p in pats)

    def ere_match(self, pattern, subject, need=()):
        """ere_match. `need`: substrings a line must all hold for the pattern
        to match there — a prefilter that skips a line, never a rule."""
        if subject == "":
            return False
        if self.loc.length(subject) > 4096:
            lines = strip1(subject, "\n").split("\n")
            if need:
                lines = [ln for ln in lines if all(n in ln for n in need)]
            return bool(lines) and self.grep_q(pattern, lines)
        lines = [subject] if "\n" not in subject else strip1(subject, "\n").split("\n")
        return any(self.search(pattern, line) for line in lines
                   if not need or all(n in line for n in need))

    def matches_any(self, patterns, subject):
        """The first pattern of a newline-separated list that matches, or None."""
        for pattern in herestring_lines(patterns):
            if pattern and self.ere_match(pattern, subject):
                return pattern
        return None

    def matches_joined(self, subject, patterns):
        joined = strip1(patterns, "\n").replace("\n", "|")
        return bool(joined) and self.ere_match(joined, subject)


_HEREDOC_RE = re.compile(r"<<-?\s*[\"\x27]?([A-Za-z_][A-Za-z0-9_]*)[\"\x27]?")
_MSG_QUOTED_RE = re.compile(r"(-m|--message)(=|\s+)([\"\x27])(?:(?!\3).)*\3", re.S)
_MSG_SUBST_RE = re.compile(r"(-m|--message)(=|\s+)\$\((?:[^()]|\([^()]*\))*\)", re.S)


def strip_prose(cmd, loc):
    """The command without heredoc bodies and commit-message arguments, as the
    shell's `python3 -c` printed it and $( ) kept it. That interpreter read
    stdin strictly in a UTF-8 locale: text it could not decode printed nothing."""
    if "<<" not in cmd and "-m" not in cmd:
        return cmd
    try:
        text = cmd.encode("latin-1").decode("utf-8", "strict" if loc.utf8 else "surrogateescape")
    except UnicodeDecodeError:
        return ""
    for m in list(_HEREDOC_RE.finditer(text)):
        marker = m.group(1)
        end = re.search(r"^\s*" + re.escape(marker) + r"\s*$", text[m.end():], re.M)
        if end:
            text = text[: m.end()] + text[m.end() + end.end():]
    text = _MSG_QUOTED_RE.sub(r"\1 MSG", text)
    text = _MSG_SUBST_RE.sub(r"\1 MSG", text)
    return chomp_all(text.encode("utf-8", "surrogateescape").decode("latin-1"))


def ere_escape(s):
    """ere_escape, quirk included: the shell's `case` listed '\\\\' in single
    quotes — two characters, which one character never equals — so a lone
    backslash stays unescaped, and in the ERE it then escapes what follows."""
    return "".join("\\" + c if c in "[].*^$(){}?+|" else c for c in s)
