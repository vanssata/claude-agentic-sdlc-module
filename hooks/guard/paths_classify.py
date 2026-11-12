"""Pattern loading and path classification: the sensitive and protected patterns, their anchors, and
classify and check_path, which decide what a path is.

R16: shell (they read the file system, the clock or a subprocess): load_patterns, setup_anchors, classify, check_path; every other name here is core.
phys_path, which classify calls through self, stays a PathGuard method in paths.py (it reads no self).
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
from guard.common import (Deny, abs_path, chomp_all, env_b, herestring_lines, is_dir, is_file,
                          is_jq_string, jq_iter, load_json_file, real_path, strip1)
from guard.paths_base import T, WHY_PROTECTED, WHY_SENSITIVE, WHY_TASK
from guard.paths_fs import anchor_list, cd_physical, lexnorm


TOKEN_END = "([[:space:]\"';&|)<>]|$)"


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
                             ("p", "protected_config_patterns"), ("k", "task_protected_patterns")):
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
