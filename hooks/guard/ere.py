"""POSIX extended regular expressions, read the way glibc's regcomp and GNU grep
-E read them, translated to Python's re.

The shell guards matched with bash's [[ =~ ]] (glibc regexec) and with
`LC_ALL=C grep -E`. Every pattern a user config or the guards themselves hold is
one of those, so it is parsed here by the POSIX rules and emitted as an
equivalent Python pattern. What glibc rejects is rejected (EreError) and then
never matches, as an invalid pattern never matched in the shell.

Two modes:
  "b"  bytewise: the subject and the pattern are the latin-1 view of their
       bytes, one character per byte, [[:space:]] is ASCII. This is the C
       locale, and every `LC_ALL=C grep` / `local LC_ALL=C` of the shell.
  "u"  a UTF-8 locale: the subject and the pattern are decoded text,
       [[:space:]] is glibc's iswspace — ASCII and the 15 code points SH_BLANK
       names — and `.` or a negated bracket never matches an invalid byte.

Existence is the same under leftmost-longest and leftmost-first, so a boolean
search needs nothing more. Where the shell read BASH_REMATCH, the groups are
those of a greedy leftmost-first match; tests/test_guard_differential.py holds
them against bash. A backtracking engine is quadratic where glibc's DFA was
not, so two rewrites keep a long subject linear: a search drops each
alternative's leading min-0 item (it cannot decide whether a match exists),
and a literal every match must contain is looked for with str.find first. A
pattern that nests repetition — (a+)+, (a|aa)+, (a?){30}, the shapes on which
backtracking is exponential — is searched by a lazily built DFA instead
(_Dfa), linear like glibc's; a user's config can hold any of them.

Not modelled: collating elements beyond one character, equivalence classes
beyond the character itself, and the Unicode extent of [:upper:], [:lower:],
[:punct:], [:print:], [:graph:] in a UTF-8 locale (they are ASCII here).
"""
import re

RE_DUP_MAX = 0x7FFF
_INTERVAL = re.compile(r"(\d*)(,(\d*))?\}")

_ASCII_CLASSES = {
    "alpha": [(0x41, 0x5A), (0x61, 0x7A)],
    "digit": [(0x30, 0x39)],
    "alnum": [(0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A)],
    "upper": [(0x41, 0x5A)],
    "lower": [(0x61, 0x7A)],
    "space": [(0x09, 0x0D), (0x20, 0x20)],
    "blank": [(0x09, 0x09), (0x20, 0x20)],
    "punct": [(0x21, 0x2F), (0x3A, 0x40), (0x5B, 0x60), (0x7B, 0x7E)],
    "print": [(0x20, 0x7E)],
    "graph": [(0x21, 0x7E)],
    "cntrl": [(0x00, 0x1F), (0x7F, 0x7F)],
    "xdigit": [(0x30, 0x39), (0x41, 0x46), (0x61, 0x66)],
}
# glibc's iswspace / iswblank beyond ASCII (SH_BLANK in the path guard).
_U_SPACE = [(0x1680, 0x1680), (0x2000, 0x2006), (0x2008, 0x200A), (0x2028, 0x2029),
            (0x205F, 0x205F), (0x3000, 0x3000)]
_U_BLANK = [(0x1680, 0x1680), (0x2000, 0x2006), (0x2008, 0x200A), (0x205F, 0x205F),
            (0x3000, 0x3000)]
# Python spellings of the Unicode letter classes, used in a UTF-8 locale.
_U_EXTRA = {"alpha": r"[^\W\d_]", "alnum": r"[^\W_]"}
# An invalid byte of the subject, decoded with surrogateescape.
_INVALID = (0xDC80, 0xDCFF)


class EreError(ValueError):
    """The pattern is not a valid POSIX ERE; glibc's regcomp would fail."""


# The tree: ("alt", [seq...]), ("seq", [item...]), ("lit", ch), ("any",),
# ("set", negated, ranges, extras), ("group", n, alt), ("rep", node, lo, hi),
# ("bol",), ("eol",), ("raw", python-text), ("backref", n).

class _Parser:
    def __init__(self, pattern, mode):
        self.p = pattern
        self.n = len(pattern)
        self.i = 0
        self.mode = mode
        self.groups = 0
        self.closed = set()
        self.depth = 0
        self.backrefs = False

    def parse(self):
        node = self._alt()
        if self.i != self.n:
            raise EreError("trailing text")
        return node

    def _alt(self):
        seqs = [self._seq()]
        while self.i < self.n and self.p[self.i] == "|":
            self.i += 1
            seqs.append(self._seq())
        return ("alt", seqs)

    def _seq(self):
        items = []
        while self.i < self.n:
            c = self.p[self.i]
            if c == "|" or (c == ")" and self.depth > 0):
                break
            if c in "*+?{":
                if not items or items[-1][0] in ("bol", "eol"):
                    raise EreError("nothing to repeat")
                items[-1] = self._quantifier(items[-1])
                continue
            items.append(self._atom())
        return ("seq", items)

    def _quantifier(self, node):
        c = self.p[self.i]
        self.i += 1
        if c == "*":
            return ("rep", node, 0, None)
        if c == "+":
            return ("rep", node, 1, None)
        if c == "?":
            return ("rep", node, 0, 1)
        m = _INTERVAL.match(self.p, self.i)
        if not m or (m.group(1) == "" and m.group(2) is None):
            raise EreError("bad interval")
        lo = int(m.group(1)) if m.group(1) else 0
        if m.group(2) is None:
            hi = lo
        else:
            hi = int(m.group(3)) if m.group(3) else None
        if lo > RE_DUP_MAX or (hi is not None and (hi > RE_DUP_MAX or hi < lo)):
            raise EreError("bad interval")
        self.i = m.end()
        return ("rep", node, lo, hi)

    def _atom(self):
        c = self.p[self.i]
        if c == "(":
            self.i += 1
            self.groups += 1
            n = self.groups
            self.depth += 1
            inner = self._alt()
            self.depth -= 1
            if self.i >= self.n or self.p[self.i] != ")":
                raise EreError("unmatched (")
            self.i += 1
            self.closed.add(n)
            return ("group", n, inner)
        if c == "[":
            return self._bracket()
        if c == ".":
            self.i += 1
            return ("any",)
        if c == "^":
            self.i += 1
            return ("bol",)
        if c == "$":
            self.i += 1
            return ("eol",)
        if c == "\\":
            return self._escape()
        self.i += 1
        return ("lit", c)

    def _escape(self):
        if self.i + 1 >= self.n:
            raise EreError("trailing backslash")
        c = self.p[self.i + 1]
        self.i += 2
        word = "\\w" if self.mode == "u" else "[A-Za-z0-9_]"
        if c in "123456789":
            if int(c) not in self.closed:
                raise EreError("invalid back reference")
            self.backrefs = True
            return ("backref", int(c))
        if c == "<":
            return ("raw", r"\b(?=%s)" % word)
        if c == ">":
            return ("raw", r"\b(?<=%s)" % word)
        if c == "b":
            return ("raw", r"\b")
        if c == "B":
            return ("raw", r"\B")
        if c == "w":
            return ("set", False, [], [word])
        if c == "W":
            return ("set", True, [], [word])
        if c == "s":
            return ("set", False, self._class("space"), [])
        if c == "S":
            return ("set", True, self._class("space"), [])
        if c == "`":
            return ("raw", r"\A")
        if c == "'":
            return ("raw", r"\Z")
        return ("lit", c)

    def _class(self, name):
        if name not in _ASCII_CLASSES:
            raise EreError("unknown class")
        ranges = list(_ASCII_CLASSES[name])
        if self.mode == "u":
            if name == "space":
                ranges += _U_SPACE
            elif name == "blank":
                ranges += _U_BLANK
        return ranges

    def _bracket(self):
        self.i += 1
        negated = False
        if self.i < self.n and self.p[self.i] == "^":
            negated = True
            self.i += 1
        ranges, extras = [], []
        first = True
        while True:
            if self.i >= self.n:
                raise EreError("unmatched [")
            c = self.p[self.i]
            if c == "]" and not first:
                self.i += 1
                break
            first = False
            if c == "[" and self.i + 1 < self.n and self.p[self.i + 1] == ":":
                end = self.p.find(":]", self.i + 2)
                if end < 0:
                    raise EreError("unmatched [:")
                name = self.p[self.i + 2:end]
                ranges += self._class(name)
                if self.mode == "u" and name in _U_EXTRA:
                    extras.append(_U_EXTRA[name])
                self.i = end + 2
                continue
            lo = self._bracket_char()
            if (self.i + 1 < self.n and self.p[self.i] == "-" and self.p[self.i + 1] != "]"):
                self.i += 1
                hi = self._bracket_char()
                if hi < lo:
                    raise EreError("invalid range end")
                if self.i < self.n and self.p[self.i] == "-" and self.i + 1 < self.n \
                        and self.p[self.i + 1] != "]":
                    raise EreError("invalid range end")
                ranges.append((lo, hi))
            else:
                ranges.append((lo, lo))
        return ("set", negated, ranges, extras)

    def _bracket_char(self):
        """One bracket element that can end a range: a character, [.c.] or [=c=]."""
        c = self.p[self.i]
        if c == "[" and self.i + 1 < self.n and self.p[self.i + 1] in ".=":
            kind = self.p[self.i + 1]
            end = self.p.find(kind + "]", self.i + 2)
            if end < 0:
                raise EreError("unmatched [%s" % kind)
            sym = self.p[self.i + 2:end]
            if len(sym) != 1:
                raise EreError("invalid collating element")
            self.i = end + 2
            return ord(sym)
        self.i += 1
        return ord(c)


def _chr(cp):
    return re.escape(chr(cp))


def _emit_set(node, mode):
    _, negated, ranges, extras = node
    body = "".join(_chr(lo) if lo == hi else "%s-%s" % (_chr(lo), _chr(hi)) for lo, hi in ranges)
    if negated and not extras:
        if mode == "u":
            body += "%s-%s" % (_chr(_INVALID[0]), _chr(_INVALID[1]))
        return "[^%s]" % body if body else "(?s:.)"
    parts = (["[%s]" % body] if body else []) + list(extras)
    if not parts:
        alt = "(?!)"
    elif len(parts) == 1:
        alt = parts[0]
    else:
        alt = "(?:%s)" % "|".join(parts)
    if not negated:
        return alt
    anything = _emit_any(mode)
    return anything if alt == "(?!)" else "(?!%s)%s" % (alt, anything)


def _emit_any(mode):
    if mode == "u":
        return "[^%s-%s]" % (_chr(_INVALID[0]), _chr(_INVALID[1]))
    return "(?s:.)"


def _emit(node, mode):
    kind = node[0]
    if kind == "alt":
        return "|".join(_emit(s, mode) for s in node[1])
    if kind == "seq":
        return "".join(_emit(i, mode) for i in node[1])
    if kind == "lit":
        return re.escape(node[1])
    if kind == "any":
        return _emit_any(mode)
    if kind == "set":
        return _emit_set(node, mode)
    if kind == "group":
        return "(%s)" % _emit(node[2], mode)
    if kind == "rep":
        _, inner, lo, hi = node
        if (lo, hi) == (0, None):
            q = "*"
        elif (lo, hi) == (1, None):
            q = "+"
        elif (lo, hi) == (0, 1):
            q = "?"
        elif hi is None:
            q = "{%d,}" % lo
        elif lo == hi:
            q = "{%d}" % lo
        else:
            q = "{%d,%d}" % (lo, hi)
        return "(?:%s)%s" % (_emit(inner, mode), q)
    if kind == "bol":
        return r"\A"
    if kind == "eol":
        return r"\Z"
    if kind == "raw":
        return node[1]
    if kind == "backref":
        return "(?:\\%d)" % node[1]
    raise AssertionError(kind)


def _required(node):
    """A set of strings one of which every match contains, or None."""
    kind = node[0]
    if kind == "alt":
        sets = [_required(s) for s in node[1]]
        if any(s is None for s in sets):
            return None
        out = set().union(*sets)
        return out if "" not in out else None
    if kind == "group":
        return _required(node[2])
    if kind == "rep":
        return _required(node[1]) if node[2] >= 1 else None
    if kind == "lit":
        return {node[1]}
    if kind != "seq":
        return None
    best, run = None, ""

    def better(cand, cur):
        if not cand or "" in cand:
            return cur
        if cur is None or min(map(len, cand)) > min(map(len, cur)):
            return cand
        return cur

    for item in node[1]:
        if item[0] == "lit":
            run += item[1]
            continue
        best = better({run} if run else None, best)
        run = ""
        if item[0] in ("group", "alt") or (item[0] == "rep" and item[2] >= 1):
            best = better(_required(item), best)
    return better({run} if run else None, best)


def _strip_leading(tree):
    """Each alternative without its leading min-0 items: the same answer to
    "is there a match", which is all a boolean search asks."""
    seqs = []
    for seq in tree[1]:
        items = list(seq[1])
        while items and items[0][0] == "rep" and items[0][2] == 0:
            items.pop(0)
        seqs.append(("seq", items))
    return ("alt", seqs)


def _starts_with_dotstar(tree):
    return all(seq[1] and seq[1][0][0] == "rep" and seq[1][0][1][0] == "any"
               and seq[1][0][2] == 0 and seq[1][0][3] is None for seq in tree[1])


def _nested(node, inside=False):
    """Whether a repetition holds a repetition or an alternation: the shapes
    ((a+)+, (a|aa)+, (a?){30}) on which backtracking is exponential."""
    kind = node[0]
    if kind == "rep":
        if inside:
            return True
        return _nested(node[1], node[3] is None or node[3] > 1)
    if kind == "alt":
        if inside and len(node[1]) > 1:
            return True
        return any(_nested(s, inside) for s in node[1])
    if kind == "seq":
        return any(_nested(i, inside) for i in node[1])
    if kind == "group":
        return _nested(node[2], inside)
    return False


def _dfa_ok(node):
    """The DFA takes characters, ^, $, groups and bounded repetition only."""
    kind = node[0]
    if kind in ("raw", "backref"):
        return False
    if kind == "rep":
        return node[2] <= 256 and (node[3] is None or node[3] <= 256) and _dfa_ok(node[1])
    if kind in ("alt", "seq"):
        return all(_dfa_ok(i) for i in node[1])
    if kind == "group":
        return _dfa_ok(node[2])
    return True


class _Dfa:
    """Is there a match anywhere: a Thompson NFA run as a lazily built DFA,
    linear in the subject whatever the pattern, as glibc's matcher is. `^`
    holds only at position 0, `$` only at the end; no groups are reported."""

    def __init__(self, tree, mode):
        self.mode = mode
        self.kind, self.arg, self.nxt = [], [], []
        self.accept = self._add("match", None, None)
        self.start = self._build(tree, self.accept)
        self.ids, self.sets, self.trans, self.end_ok = {}, [], {}, {}
        self.start0 = self._intern(self._closure([self.start], True))
        self.start_n = self._closure([self.start], False)
        if len(self.kind) > 20000:
            raise OverflowError("pattern too large")

    def _add(self, kind, arg, nxt):
        self.kind.append(kind)
        self.arg.append(arg)
        self.nxt.append(nxt)
        return len(self.kind) - 1

    def _build(self, node, nxt):
        kind = node[0]
        if kind == "alt":
            return self._add("split", [self._build(s, nxt) for s in node[1]], None)
        if kind == "seq":
            for item in reversed(node[1]):
                nxt = self._build(item, nxt)
            return nxt
        if kind == "group":
            return self._build(node[2], nxt)
        if kind in ("bol", "eol"):
            return self._add(kind, None, nxt)
        if kind == "rep":
            inner, lo, hi = node[1], node[2], node[3]
            if hi is None:
                tail = self._add("split", None, None)
                self.arg[tail] = [self._build(inner, tail), nxt]
            else:
                tail = nxt
                for _ in range(hi - lo):
                    tail = self._add("split", [self._build(inner, tail), nxt], None)
            for _ in range(lo):
                tail = self._build(inner, tail)
            return tail
        if kind == "lit":
            c = node[1]
            return self._add("char", lambda ch, c=c: ch == c, nxt)
        flags = re.ASCII if self.mode == "b" else 0
        one = re.compile(_emit_any(self.mode) if kind == "any" else _emit_set(node, self.mode), flags)
        return self._add("char", lambda ch, one=one: one.match(ch) is not None, nxt)

    def _closure(self, states, at_start, at_end=False):
        out, stack, seen = set(), list(states), set()
        while stack:
            s = stack.pop()
            if s in seen:
                continue
            seen.add(s)
            k = self.kind[s]
            if k == "split":
                stack.extend(self.arg[s])
            elif k == "bol":
                if at_start:
                    stack.append(self.nxt[s])
            elif k == "eol" and at_end:
                stack.append(self.nxt[s])
            else:
                out.add(s)
        return frozenset(out)

    def _intern(self, states):
        i = self.ids.get(states)
        if i is None:
            i = self.ids[states] = len(self.sets)
            self.sets.append(states)
        return i

    def _step(self, cur, ch):
        moved = [self.nxt[s] for s in self.sets[cur] if self.kind[s] == "char" and self.arg[s](ch)]
        return self._intern(self._closure(moved, False) | self.start_n)

    def _accepts_at_end(self, cur):
        ok = self.end_ok.get(cur)
        if ok is None:
            eols = [s for s in self.sets[cur] if self.kind[s] == "eol"]
            ok = self.end_ok[cur] = self.accept in self._closure(eols, False, at_end=True)
        return ok

    def search(self, subject):
        if self.accept in self.sets[self.start0]:
            return True
        if not subject:
            eols = [s for s in self.sets[self.start0] if self.kind[s] == "eol"]
            return self.accept in self._closure(eols, True, at_end=True)
        trans, cur, accept = self.trans, self.start0, self.accept
        for ch in subject:
            nxt = trans.get((cur, ch))
            if nxt is None:
                nxt = trans[(cur, ch)] = self._step(cur, ch)
            cur = nxt
            if accept in self.sets[cur]:
                return True
        return self._accepts_at_end(cur)


class _Found:                               # pylint: disable=too-few-public-methods
    """A truthy stand-in for a match object, from the DFA."""


class Compiled:
    """One pattern in one mode. `rx` is None when the pattern is invalid."""
    __slots__ = ("rx", "required", "anchored", "dfa")

    def __init__(self, pattern, mode, capture):
        self.rx = None
        self.required = None
        self.anchored = False
        self.dfa = None
        if mode == "u" and any(0xDC80 <= ord(c) <= 0xDCFF for c in pattern):
            return                          # invalid UTF-8 in the pattern: regcomp fails
        try:
            parser = _Parser(pattern, mode)
            tree = parser.parse()
            self.required = _required(tree)
            if not capture and not parser.backrefs:
                tree = _strip_leading(tree)
            elif capture:
                self.anchored = _starts_with_dotstar(tree)
            flags = re.ASCII if mode == "b" else 0
            self.rx = re.compile(_emit(tree, mode), flags)
            if not capture and _nested(tree) and _dfa_ok(tree):
                self.dfa = _Dfa(tree, mode)
        except (EreError, re.error, RecursionError, OverflowError):
            self.rx = None

    def search(self, subject):
        if self.rx is None:
            return None
        if self.required is not None and not any(r in subject for r in self.required):
            return None
        if self.dfa is not None:
            return _Found() if self.dfa.search(subject) else None
        return self.rx.match(subject) if self.anchored else self.rx.search(subject)


_CACHE = {}


def compile_ere(pattern, mode, capture=False):
    key = (pattern, mode, capture)
    c = _CACHE.get(key)
    if c is None:
        c = _CACHE[key] = Compiled(pattern, mode, capture)
    return c


def valid(pattern, mode="b"):
    return compile_ere(pattern, mode).rx is not None


def search(pattern, subject, mode):
    """Whether the ERE matches somewhere in subject (one line, no splitting)."""
    return compile_ere(pattern, mode).search(subject) is not None


def match_groups(pattern, subject, mode):
    """BASH_REMATCH: the match and its groups ("" for a group that took no
    part), or None when the pattern does not match."""
    m = compile_ere(pattern, mode, capture=True).search(subject)
    if m is None:
        return None
    return [m.group(0)] + [g if g is not None else "" for g in m.groups()]
