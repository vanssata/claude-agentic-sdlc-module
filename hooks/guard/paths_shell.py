"""The awk segmenter of the retired shell guard: shell_segments cuts a command into its segments,
words and redirections, with the keyword, flag and redirection tables it reads.

R16: every name here is core (no file, clock or subprocess access).
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import re
from guard.common import chomp_all


_KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time", "exec",
             "command", "nohup", "builtin", "env", "sudo"}
_FLAGGED = {"time", "exec", "command", "env", "sudo"}
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
_SPECIAL_OUT = re.compile(r"""['$"#<(\n`)&;|\\]""")
_SPECIAL_D = re.compile(r'["$`\n\\]')
_SPECIAL_A = re.compile(r"['\n\\]")


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
