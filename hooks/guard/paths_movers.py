"""The movers pass: cp, mv, rm, ln, sed -i, find -delete and their kin, resolved against the covered
roots, with MoverState, the per-call counters of that pass.

R16: shell (they read the file system, the clock or a subprocess): cover_init, realpath_m_arg, roots_under, covers_work, covers_protected, movers, mover_resolve, mover_check; every other name here is core.
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import re
from guard.common import (Deny, chomp_all, env_b, exists, herestring_lines, is_dir, read_lines,
                          real_path, strip1)
from guard.paths_fs import LoopError, find_print, realpath_m
from guard.paths_base import SEGMENT, WHY_PROTECTED, WHY_TASK


MOVERS = SEGMENT + "(cp|mv|install|rsync|rm|rmdir|unlink)([[:space:]]|$)"
MOVER_VERBS = ("cp", "mv", "install", "rsync", "rm", "rmdir", "unlink")
REMOVE_VERBS = ("rm", "rmdir", "unlink")
MOVER_CHUNK = 32768
GLOBBY = set("][*?$`{}()\\~@!+")

_SED1 = "[0-9]*[<>]{1,2}&[0-9]+"
_SED2 = "(&|[0-9]*)[<>]{1,2}[[:space:]]*[^[:space:]|;&<>]*"

_FIND_PRUNE_ROOTS = {".git", "vendor", "node_modules", "projects"}
_FIND_PRUNE_SCAN = {".git", "vendor", "node_modules", "bower_components", "third_party", "Pods",
                    "site-packages", ".venv", ".pnpm", ".yarn"}


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


def roots_under(self, c):
    for r in herestring_lines(self.cover_roots):
        if r and (c == "/" or r == c or r.startswith(c + "/")) and exists(r):
            yield r


def covers_work(self, real, lexical):
    c = strip1(real, "/") or "/"
    for _ in self.roots_under(c):
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
    roots = list(self.roots_under(c))
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
    sed1 = m.ere.compile_ere(self.loc_pat(_SED1), self.loc_mode(), capture=True).rx
    sed2 = m.ere.compile_ere(self.loc_pat(_SED2), self.loc_mode(), capture=True).rx
    kept = []
    for line in segs.split("\n"):
        t = self.loc_text(line)
        t = sed1.sub("", t) if sed1 else t
        t = sed2.sub("", t) if sed2 else t
        line = self.from_loc(t)
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


def loc_mode(self):
    return "u" if self.loc.utf8 else "b"


def loc_pat(self, p):
    return self.loc.u(p) if self.loc.utf8 else p


def loc_text(self, s):
    return self.loc.u(s) if self.loc.utf8 else s


def from_loc(self, t):
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


class MoverState:                           # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """One batch of the movers pass: candidates and the segments that own them."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.cands, self.covers, self.abss = [], [], []
        self.seg_first, self.seg_count, self.seg_verb = [], [], []
        self.reals, self.hits = {}, set()
        self.batch = 0
