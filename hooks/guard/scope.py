"""Port of hooks/ai-scope-guard.sh: the task-scope guard, on Edit, Write,
MultiEdit, NotebookEdit and Codex's apply_patch.

During the implementation stage the approved plan names the files a step may
touch; an edit outside them is refused with SCOPE_CHANGE_REQUIRED. Inert unless
.ai/state/state.json (or, for one version, the legacy current.json) exists and
its stage is "implementation".

Bash semantics kept: a plan glob is matched as `[[ $rel == $pattern ]]` — "*"
crosses "/", extglob is on inside [[ ]] — and the deny lists the allowed globs
with an unquoted `printf '  - %s\\n' $ALLOWED`, so each is split on blanks and
expanded against the process's working directory, a word that matches nothing
staying as written.
"""
import os

from guard.common import (Deny, JqError, abs_path, b_bytes, bytes_b, chomp_all, find_ai_root,
                          herestring_lines, is_file, is_jq_string, jq_iter, jq_raw, jq_tostring,
                          load_json_file, read_lines, text_to_b)

_SPACES = set(" \t\n\x0b\x0c\r        "
              "      　")
_CLASSES = {
    "alpha": str.isalpha, "digit": lambda c: "0" <= c <= "9", "alnum": str.isalnum,
    "upper": str.isupper, "lower": str.islower, "space": lambda c: c in _SPACES,
    "blank": lambda c: c in " \t" or (c in _SPACES and c not in "\n\x0b\x0c\r  "),
    "punct": lambda c: c.isascii() and c.isprintable() and not c.isalnum() and c != " ",
    "print": str.isprintable, "graph": lambda c: c.isprintable() and c != " " and c not in _SPACES,
    "cntrl": lambda c: ord(c) < 0x20 or ord(c) == 0x7F, "xdigit": lambda c: c in "0123456789abcdefABCDEF",
    "word": lambda c: c.isalnum() or c == "_",
}


# ------------------------------------------------------------------ bash patterns

def _bracket(p, i):
    """Parse a bracket at p[i] == "[": (predicate, next index) or None when it
    does not close (the "[" is then an ordinary character)."""
    j = i + 1
    negate = j < len(p) and p[j] in "!^"
    if negate:
        j += 1
    items = []
    first = True
    while j < len(p):
        c = p[j]
        if c == "]" and not first:
            return _predicate(items, negate), j + 1
        first = False
        if c == "[" and j + 1 < len(p) and p[j + 1] == ":":
            end = p.find(":]", j + 2)
            if end >= 0:
                f = _CLASSES.get(p[j + 2:end])
                items.append(f if f else (lambda ch: False))
                j = end + 2
                continue
        if c == "\\" and j + 1 < len(p):
            j += 1
            c = p[j]
        lo = c
        j += 1
        if j + 1 < len(p) and p[j] == "-" and p[j + 1] != "]":
            hi = p[j + 1]
            if hi == "\\" and j + 2 < len(p):
                hi = p[j + 2]
                j += 1
            j += 2
            items.append(lambda ch, lo=lo, hi=hi: lo <= ch <= hi)
        else:
            items.append(lambda ch, lo=lo: ch == lo)
    return None


def _predicate(items, negate):
    return lambda ch: any(f(ch) for f in items) != negate


def _parse(p, extglob, i=0, stop=""):
    """Tokens of a pattern up to an unescaped character of `stop` at depth 0:
    ("lit", c), ("any",), ("star",), ("set", pred), ("ext", op, [alt tokens])."""
    toks = []
    while i < len(p):
        c = p[i]
        if c in stop:
            return toks, i
        if extglob and c in "?*+@!" and i + 1 < len(p) and p[i + 1] == "(":
            alts, j, ok = [], i + 2, False
            while j <= len(p):
                sub, j = _parse(p, extglob, j, "|)")
                alts.append(sub)
                if j < len(p) and p[j] == "|":
                    j += 1
                    continue
                ok = j < len(p) and p[j] == ")"
                break
            if ok:
                toks.append(("ext", c, alts))
                i = j + 1
                continue
        if c == "*":
            toks.append(("star",))
        elif c == "?":
            toks.append(("any",))
        elif c == "[":
            b = _bracket(p, i)
            if b:
                toks.append(("set", b[0]))
                i = b[1]
                continue
            toks.append(("lit", "["))
        elif c == "\\" and i + 1 < len(p):
            i += 1
            toks.append(("lit", p[i]))
        else:
            toks.append(("lit", c))
        i += 1
    return toks, i


def _matcher(toks, s, dotfile=False):
    """Whether tokens match all of s. With dotfile, a leading "." must be matched
    by a literal (pathname expansion's rule)."""
    memo = {}

    def m(ti, si):
        key = (ti, si)
        if key in memo:
            return memo[key]
        memo[key] = r = _m(ti, si)
        return r

    def whole(alt, sub):
        return _matcher(alt, sub)

    def _m(ti, si):
        if ti == len(toks):
            return si == len(s)
        t = toks[ti]
        kind = t[0]
        if dotfile and si == 0 and s.startswith(".") and kind != "lit":
            return False
        if kind == "lit":
            return si < len(s) and s[si] == t[1] and m(ti + 1, si + 1)
        if kind == "any":
            return si < len(s) and m(ti + 1, si + 1)
        if kind == "set":
            return si < len(s) and t[1](s[si]) and m(ti + 1, si + 1)
        if kind == "star":
            return any(m(ti + 1, k) for k in range(si, len(s) + 1))
        op, alts = t[1], t[2]
        for j in range(si, len(s) + 1):
            sub = s[si:j]
            if op == "!":
                ok = not any(whole(a, sub) for a in alts)
            elif op == "?":
                ok = sub == "" or any(whole(a, sub) for a in alts)
            elif op == "@":
                ok = any(whole(a, sub) for a in alts)
            else:
                ok = (op == "*" and sub == "") or _repeats(alts, sub)
            if ok and m(ti + 1, j):
                return True
        return False

    return m(0, 0)


def _repeats(alts, sub):
    """sub is one or more matches of the alternatives, end to end."""
    if sub == "":
        return False
    for k in range(1, len(sub) + 1):
        if any(_matcher(a, sub[:k]) for a in alts) and (k == len(sub) or _repeats(alts, sub[k:])):
            return True
    return False


class Glob:
    """Bash pattern matching and pathname expansion in the process locale."""

    def __init__(self, loc):
        self.loc = loc

    def _text(self, s):
        return b_bytes(s).decode("utf-8", "surrogateescape") if self.loc.utf8 else s

    def _bstr(self, u):
        return u.encode("utf-8", "surrogateescape").decode("latin-1") if self.loc.utf8 else u

    def match(self, subject, pattern):
        """[[ $subject == $pattern ]]."""
        toks, _ = _parse(self._text(pattern), True)
        return _matcher(toks, self._text(subject))

    def _os(self, t):
        return t.encode("utf-8", "surrogateescape") if self.loc.utf8 else b_bytes(t)

    def _from_os(self, raw):
        return raw.decode("utf-8", "surrogateescape") if self.loc.utf8 else bytes_b(raw)

    def expand(self, word):
        """Pathname expansion of one unquoted word: the sorted matches, or the
        word itself when it holds no pattern or matches nothing."""
        if not any(c in word for c in "*?["):
            return [word]
        parts = self._text(word).split("/")
        absolute = parts[0] == ""
        first = 1 if absolute else 0
        toks_of = [_parse(part, False)[0] for part in parts]
        if all(t[0] == "lit" for toks in toks_of for t in toks):
            return [word]

        def join(base, name, n):
            """The path so far plus one component, every slash kept as written."""
            if n == first:
                return ("/" if absolute else "") + name
            return base + "/" + name

        found = [""]
        for n in range(first, len(parts)):
            last = n == len(parts) - 1
            nxt = []
            for base in found:
                if parts[n] == "":          # a doubled or trailing slash
                    nxt.append(join(base, "", n))
                    continue
                toks = toks_of[n]
                if all(t[0] == "lit" for t in toks):
                    cand = join(base, "".join(t[1] for t in toks), n)
                    exists_as = os.path.lexists if last else os.path.isdir
                    if exists_as(self._os(cand)):
                        nxt.append(cand)
                    continue
                try:
                    names = os.listdir(self._os(join(base, "", n) or "."))
                except OSError:
                    continue
                for raw in names:
                    name = self._from_os(raw)
                    cand = join(base, name, n)
                    if _matcher(toks, name, dotfile=True) and (last or os.path.isdir(self._os(cand))):
                        nxt.append(cand)
            found = nxt
            if not found:
                return [word]
        return sorted((self._bstr(f) for f in found), key=self.loc.sort_key)


# ------------------------------------------------------------------ the state file

def _step_lines(doc):
    """The lines one document of the state file prints through the guard's jq
    filter (unicode text, each without its newline)."""
    stage = jq_index_safe(doc, "current_stage")
    if stage is None or stage is False:
        stage = ""
    if not (is_jq_string(stage) and stage == "implementation"):
        return []
    plan = jq_index_safe(doc, "approved_plan")
    sid = jq_index_safe(plan, "current_step_id")
    if sid is None or sid is False:
        sid = ""
    sid = jq_tostring(sid)
    if sid == "":
        return []
    steps_v = jq_index_safe(plan, "steps")
    steps = []
    for step in jq_iter(steps_v):
        step_id = jq_index_safe(step, "step_id")
        if is_jq_string(step_id) and step_id == sid:
            steps.append(step)
    if not steps:
        return []
    task = jq_index_safe(doc, "task_id")
    out = ["i\t" + sid, "t\t" + jq_tostring("?" if task is None or task is False else task)]
    for tag, key in (("a", "allowed_files"), ("f", "forbidden_files")):
        for step in steps:
            lst = jq_index_safe(step, key)
            if lst is None or lst is False:
                lst = []
            for item in jq_iter(lst):
                if is_jq_string(item) and item != "":
                    out.extend("%s\t%s" % (tag, piece) for piece in item.split("\n"))
    out.append("r")
    for step in steps:
        reason = jq_index_safe(step, "forbidden_reason")
        out.append(jq_raw("not part of this step" if reason is None or reason is False else reason))
    return out


def jq_index_safe(value, key):
    if isinstance(value, dict):
        return value.get(key)
    if value is None:
        return None
    raise JqError(key)


def read_state(path):
    """(step id, task id, allowed, forbidden, reason) as the guard read them."""
    loaded = load_json_file(path)
    text = []
    if loaded is not None:
        for doc in loaded[0]:
            try:
                text.extend(_step_lines(doc))
            except JqError:
                continue
    step_id = task_id = allowed = forbidden = reason = ""
    in_reason = False
    for line in read_lines("".join(text_to_b(t) + "\n" for t in text)):
        if in_reason:
            reason += line + "\n"
        elif line.startswith("i\t"):
            step_id = line[2:]
        elif line.startswith("t\t"):
            task_id = line[2:]
        elif line.startswith("a\t"):
            allowed += line[2:] + "\n"
        elif line.startswith("f\t"):
            forbidden += line[2:] + "\n"
        elif line == "r":
            in_reason = True
    return step_id, task_id, chomp_all(allowed), chomp_all(forbidden), chomp_all(reason)


# ------------------------------------------------------------------ the check

def check(ctx):
    p = ctx.payload
    if p.tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return
    root = find_ai_root(p.cwd, ctx.pwd)
    if root is None:
        return
    state = root + "/.ai/state/state.json"
    if not is_file(state):
        state = root + "/.ai/state/current.json"
    if not is_file(state):
        return
    step_id, task_id, allowed, forbidden, reason = read_state(state)
    if not step_id:
        return
    glob = Glob(ctx.loc)

    def match_glob(subject, patterns):
        for pattern in herestring_lines(patterns):
            if not glob_strip_spaces(pattern, ctx.loc):
                continue
            if glob.match(subject, pattern) or glob.match(subject, pattern.rstrip("/") + "/*"):
                return pattern
        return None

    for f in p.target_paths():
        if not f:
            continue
        a = abs_path(f, p.cwd)
        rel = a[len(root) + 1:] if a.startswith(root + "/") else a
        if forbidden:
            hit = match_glob(rel, forbidden)
            if hit is not None:
                raise Deny("%s is explicitly forbidden for step %s of task %s (matched: %s).\n"
                           "Reason recorded in the plan: %s\n\n"
                           "Do not edit it. If the step genuinely cannot be completed without this file, stop\n"
                           "and report SCOPE_CHANGE_REQUIRED so the plan is amended and re-approved."
                           % (rel, step_id, task_id, hit, reason))
        if allowed and match_glob(rel, allowed) is None:
            words = [w for w in allowed.replace("\t", " ").replace("\n", " ").split(" ") if w]
            listed = []
            for w in words:
                listed.extend(glob.expand(w))
            lines = chomp_all("".join("  - %s\n" % w for w in (listed or [""])))
            raise Deny(text_to_b("SCOPE_CHANGE_REQUIRED \u2014 ") + "%s is outside the approved scope of step %s (task %s).\n\n"
                       "Allowed for this step:\n%s\n\n"
                       "Stop implementing, report SCOPE_CHANGE_REQUIRED with the reason this file is\n"
                       "needed, and let the planner amend the step. Widening scope silently is what this\n"
                       "guard exists to prevent. See .ai/policies/safety.md."
                       % (rel, step_id, task_id, lines))


def glob_strip_spaces(pattern, loc):
    """${pattern//[[:space:]]/}: the pattern without its blanks."""
    if loc.utf8:
        u = b_bytes(pattern).decode("utf-8", "surrogateescape")
        return "".join(c for c in u if c not in _SPACES)
    return "".join(c for c in pattern if c not in " \t\n\x0b\x0c\r")

