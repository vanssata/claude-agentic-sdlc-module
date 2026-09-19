#!/usr/bin/env python3
"""Bring a project's claude-agentic files up to date with the installed plugin.

  update.py [project-dir] [--apply] [--check]

Default is a dry run: print what would change, write nothing.
  --apply   write the changes
  --check   print one line and exit 1 when an automatic update is pending

What it manages, and how:
  .ai/** (policies, workflows, agents, templates)   three-way update
  docs/sdlc/*/TEMPLATE.md                            three-way update
  .claude/memory/README.md, .codex/memory/README.md  three-way update, per runtime the project uses
  the managed block in CLAUDE.md and/or AGENTS.md    three-way update of the block only
  .gitignore                                         missing entries appended
  .ai/project/**, the instruction files themselves,
  .claude/settings.json, .codex/config.toml          created when missing, never updated

A project uses the runtime(s) it declares: CLAUDE.md or .claude/ means Claude
Code, AGENTS.md or .codex/ means Codex, both means both. A project that declares
neither gets the runtime this copy of the plugin was installed for, exactly as
the scaffolds do.

Three-way update: a file whose content is a version this plugin once shipped was
never edited, so it is replaced. An edited file is merged against the shipped
version closest to it (git merge-file for text, per key for JSON), keeping every
edit. A real conflict leaves the project file alone and puts the plugin's version
in a git-ignored local directory for a human or /project-update to merge.
"""
import argparse, difflib, hashlib, json, os, re, subprocess, sys, tempfile
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)
TEMPLATES = {
    "ai-init": os.environ.get("CLAUDE_AGENTIC_TEMPLATES", os.path.join(SKILLS, "ai-init", "templates")),
    "project-init": os.environ.get("CLAUDE_ROUTING_TEMPLATES", os.path.join(SKILLS, "project-init", "templates")),
}
HISTORY = os.environ.get("CLAUDE_AGENTIC_HISTORY", os.path.join(HERE, "history"))
START, END = "<!-- claude-agentic:start -->", "<!-- claude-agentic:end -->"
MISSING = object()
HASH_RE = re.compile(rb"sha256:[0-9a-f]{64}")

PROJECT_INIT_MAP = [  # template -> target, kind
    ("sdlc-README.md", "docs/sdlc/README.md", "update"),
    ("intent.md", "docs/sdlc/intent/TEMPLATE.md", "update"),
    ("spec.md", "docs/sdlc/specs/TEMPLATE.md", "update"),
    ("plan.md", "docs/sdlc/plans/TEMPLATE.md", "update"),
    ("adr.md", "docs/sdlc/adr/TEMPLATE.md", "update"),
]
RUNTIME_MAP = {  # the per-runtime layer of the project-init scaffold
    "claude": [("memory-README.md", ".claude/memory/README.md", "update"),
               ("project-settings.json", ".claude/settings.json", "create")],
    "codex":  [("memory-README.md", ".codex/memory/README.md", "update"),
               ("project-config.toml", ".codex/config.toml", "create")],
}
INSTRUCTION_FILE = {  # runtime -> (file, block template, minimal template)
    "claude": ("CLAUDE.md", "CLAUDE.block.md", "CLAUDE.minimal.md"),
    "codex":  ("AGENTS.md", "AGENTS.block.md", "AGENTS.minimal.md"),
}


def project_runtimes(root):
    """The runtimes a project declares, or the one this plugin copy serves."""
    out = []
    if os.path.exists(os.path.join(root, "CLAUDE.md")) or os.path.isdir(os.path.join(root, ".claude")):
        out.append("claude")
    if os.path.exists(os.path.join(root, "AGENTS.md")) or os.path.isdir(os.path.join(root, ".codex")):
        out.append("codex")
    if not out:
        out.append("codex" if "/.codex/" in HERE + "/" else "claude")
    return out


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


class History:
    def __init__(self, root):
        try:
            with open(os.path.join(root, "index.json"), encoding="utf-8") as fh:
                self.index = json.load(fh)
        except (OSError, ValueError):
            self.index = {}
        self.root = root

    def versions(self, key):
        """Every shipped version of a template, oldest first, as bytes."""
        out = []
        for h in self.index.get(key, []):
            try:
                out.append(read(os.path.join(self.root, "blobs", h)))
            except OSError:
                pass
        return out


# ---------------------------------------------------------------- merging
def closest(candidates, ours, score):
    best, best_score = None, -1.0
    for c in candidates:  # oldest first; ties keep the older one
        s = score(c, ours)
        if s > best_score:
            best, best_score = c, s
    return best


def text_ratio(a, b):
    return difflib.SequenceMatcher(None, a.splitlines(), b.splitlines(), autojunk=False).ratio()


def merge_text(ours, base, theirs):
    with tempfile.TemporaryDirectory() as d:
        paths = [os.path.join(d, n) for n in ("ours", "base", "theirs")]
        for p, c in zip(paths, (ours, base, theirs)):
            with open(p, "wb") as fh:
                fh.write(c)
        r = subprocess.run(["git", "merge-file", "-p", "--quiet", *paths], capture_output=True, check=False)
    return r.stdout if r.returncode == 0 else None


def flatten(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out.update(flatten(v, prefix + ("." if prefix else "") + str(k)))
        return out or {prefix: {}}
    return {prefix: value}


def json_score(base, ours):
    fb, fo = flatten(base), flatten(ours)
    return sum(1 for k, v in fo.items() if k in fb and fb[k] == v)


def merge_json(base, ours, theirs, path, conflicts):
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict) and (base is MISSING or isinstance(base, dict)):
        b = base if isinstance(base, dict) else {}
        out = OrderedDict()
        for k in list(ours) + [k for k in theirs if k not in ours]:
            v = merge_json(b.get(k, MISSING), ours.get(k, MISSING), theirs.get(k, MISSING), path + [k], conflicts)
            if v is not MISSING:
                out[k] = v
        return out
    conflicts.append(".".join(map(str, path)) or "(root)")
    return ours


def dump_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def leaf_changes(before, after):
    """Changed leaf paths; a whole new or removed subtree is reported once, at its top."""
    fb, fa = flatten(before), flatten(after)

    def top(key, other):
        parts = key.split(".")
        for n in range(1, len(parts) + 1):
            prefix = ".".join(parts[:n])
            if not any(k == prefix or k.startswith(prefix + ".") for k in other):
                return prefix
        return key

    out = set()
    for k in set(fb) | set(fa):
        if k not in fb:
            out.add("+ " + top(k, fb))
        elif k not in fa:
            out.add("- " + top(k, fa))
        elif fb[k] != fa[k]:
            out.add("~ " + k)
    return sorted(out, key=lambda c: c[2:])


# ---------------------------------------------------------------- planning
class Plan:
    def __init__(self, root):
        self.root = root
        self.items = []   # dicts: action, target, note, content, conflict_copy, policy
        self.hints = []
        self.final = {}   # target -> bytes after this run (for cross-file fixes)
        self.removed = set()  # targets this run takes away

    # The project as this run leaves it: planned content first, then the disk.
    # File readers in the planning path go through these, not the disk.
    def exists(self, target):
        if target in self.final:
            return True
        return target not in self.removed and os.path.exists(os.path.join(self.root, target))

    def read(self, target):
        if target in self.final:
            return self.final[target]
        return read(os.path.join(self.root, target)) if self.exists(target) else None

    def remove(self, target):
        self.final.pop(target, None)
        self.removed.add(target)

    def add(self, action, target, note="", content=None, conflict_copy=None, policy=None):
        self.items.append(dict(action=action, target=target, note=note, content=content,
                               conflict_copy=conflict_copy, policy=policy))
        if content is not None:
            self.final[target] = content

    @property
    def local_dir(self):
        base = ".ai/local/plugin-update" if os.path.isdir(os.path.join(self.root, ".ai")) \
            else ".claude/memory/local/plugin-update"
        return base


def three_way(plan, history, key, target, theirs):
    ours = plan.read(target)
    if ours is None:
        plan.add("create", target, content=theirs)
        return
    is_mirror = target.endswith(".ai/policies/risk-tiers.md")
    norm = (lambda b: HASH_RE.sub(b"sha256:" + b"0" * 64, b)) if is_mirror else (lambda b: b)
    if norm(ours) == norm(theirs):
        return
    versions = [v for v in history.versions(key) if norm(v) != norm(theirs)]
    if any(norm(v) == norm(ours) for v in versions):
        policy = None
        if target.endswith(".json") and "/policies/" in "/" + target:
            try:
                policy = leaf_changes(json.loads(ours, object_pairs_hook=OrderedDict),
                                      json.loads(theirs, object_pairs_hook=OrderedDict))
            except ValueError:
                policy = None
        plan.add("update", target, "unchanged since it was installed",
                 content=fix_mirror(plan, target, theirs, ours), policy=policy)
        return

    if target.endswith(".json"):
        try:
            o = json.loads(ours, object_pairs_hook=OrderedDict)
            t = json.loads(theirs, object_pairs_hook=OrderedDict)
            bases = [json.loads(v, object_pairs_hook=OrderedDict) for v in versions]
        except ValueError:
            plan.add("conflict", target, "not valid JSON; not merged", conflict_copy=theirs)
            return
        base = closest(bases, o, json_score) if bases else MISSING
        conflicts = []
        merged = merge_json(base, o, t, [], conflicts)
        policy = leaf_changes(o, merged) if "/policies/" in "/" + target else None
        if merged == o and not conflicts:
            return
        if merged != o:
            plan.add("merge", target, "your edits kept", content=dump_json(merged), policy=policy)
        if conflicts:
            plan.add("conflict", target, "kept your value for: " + ", ".join(conflicts), conflict_copy=theirs)
        return

    base = closest(versions, norm(ours), lambda b, o: text_ratio(norm(b), o)) if versions else None
    merged = merge_text(norm(ours), norm(base), norm(theirs)) if base is not None else None
    if merged is None:
        plan.add("conflict", target, "edited here and changed in the plugin", conflict_copy=theirs)
    elif merged != norm(ours):
        plan.add("merge", target, "your edits kept", content=fix_mirror(plan, target, merged, ours))


def fix_mirror(plan, target, content, ours):
    """risk-tiers.md carries the sha256 of risk-tiers.json. Carry the project's sync
    state forward: a mirror that matched its JSON before this run points at the JSON
    this run leaves behind; a mirror that was already stale, or a JSON left with a
    conflict, keeps its old hash so /ai-status keeps warning."""
    if not target.endswith(".ai/policies/risk-tiers.md"):
        return content
    old = HASH_RE.search(ours)
    # The disk, not the plan: the question is whether the mirror matched the JSON
    # the project had before this run.
    json_target = target[:-3] + ".json"
    json_path = os.path.join(plan.root, json_target)
    before = read(json_path) if os.path.exists(json_path) else None
    in_sync = old is not None and before is not None and old.group(0) == b"sha256:" + sha(before).encode()
    conflicted = any(i["action"] == "conflict" and i["target"] == json_target for i in plan.items)
    after = plan.final.get(json_target, before)
    if in_sync and not conflicted and after is not None:
        return HASH_RE.sub(b"sha256:" + sha(after).encode(), content, count=1)
    return HASH_RE.sub(old.group(0), content, count=1) if old else content


def block_update(plan, history, runtime):
    name, block_tpl, minimal_tpl = INSTRUCTION_FILE[runtime]
    tpl = read(os.path.join(TEMPLATES["ai-init"], block_tpl))
    text = plan.read(name)
    if text is None:
        created = read(os.path.join(TEMPLATES["ai-init"], minimal_tpl)).replace(
            b"{{PROJECT}}", os.path.basename(plan.root).encode())
        plan.add("create", name, "with the managed block", content=created.rstrip(b"\n") + b"\n\n" + tpl)
        return
    s, e = text.find(START.encode()), text.find(END.encode())
    if s < 0 or e < 0:
        plan.add("update", name, "managed block appended",
                 content=text.rstrip(b"\n") + b"\n\n" + tpl)
        return
    e += len(END)
    ours = text[s:e] + b"\n"
    if ours == tpl:
        return
    versions = [v for v in history.versions("ai-init/" + block_tpl) if v != tpl]
    if ours in versions:
        new_block = tpl
        note = "managed block replaced (unchanged since it was installed)"
    else:
        base = closest(versions, ours, text_ratio) if versions else None
        new_block = merge_text(ours, base, tpl) if base is not None else None
        note = "managed block merged, your edits kept"
    if new_block is None:
        plan.add("conflict", name, "the managed block was edited here and changed in the plugin",
                 conflict_copy=tpl)
        return
    plan.add("update", name, note, content=text[:s] + new_block.rstrip(b"\n") + text[e:])


def gitignore_update(plan, snippet_path):
    snippet = read(snippet_path).decode().splitlines()
    current = plan.read(".gitignore") or b""
    have = set(current.decode().splitlines())
    missing = [l for l in snippet if l.strip() and not l.startswith("#") and l not in have]
    if not missing:
        return
    header = [l for l in snippet if l.startswith("#") and l not in have]
    add = "\n".join(header + missing) + "\n"
    sep = b"\n" if current and not current.endswith(b"\n") else b""
    new = current + sep + add.encode()
    # Replace an earlier .gitignore item from this run instead of stacking two.
    plan.items = [i for i in plan.items if i["target"] != ".gitignore"]
    plan.add("update", ".gitignore", "entries appended: " + ", ".join(missing), content=new)


def build_plan(root):
    history = History(HISTORY)
    plan = Plan(root)
    has_ai = os.path.isdir(os.path.join(root, ".ai"))
    has_sdlc = os.path.isdir(os.path.join(root, "docs", "sdlc"))
    if not (has_ai or has_sdlc):
        return None

    runtimes = project_runtimes(root)
    if has_sdlc:
        tpl = TEMPLATES["project-init"]
        entries = list(PROJECT_INIT_MAP)
        for rt in runtimes:
            entries += RUNTIME_MAP[rt]
        for src, target, kind in entries:
            content = read(os.path.join(tpl, src))
            if kind == "create":
                if not plan.exists(target):
                    plan.add("create", target, content=content.replace(
                        b"{{PROJECT}}", os.path.basename(root).encode()))
            else:
                three_way(plan, history, "project-init/" + src, target, content)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

    if has_ai:
        tpl = TEMPLATES["ai-init"]
        files = []
        for dirpath, _, names in os.walk(os.path.join(tpl, ".ai")):
            for n in names:
                files.append(os.path.relpath(os.path.join(dirpath, n), tpl))
        # JSON before markdown, so the risk-tier mirror can point at the merged JSON.
        for rel in sorted(files, key=lambda r: (not r.endswith(".json"), r)):
            content = read(os.path.join(tpl, rel))
            if rel.startswith(".ai/project/") or rel.startswith(".ai/reports/"):
                if not plan.exists(rel):
                    plan.add("create", rel, content=content)
                continue
            three_way(plan, history, "ai-init/" + rel, rel, content)
        for rt in runtimes:
            block_update(plan, history, rt)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

        testing = plan.read(".ai/policies/testing.md")
        if testing is not None:
            for field, why in (
                ("verify_command", "the feedback loop needs it"),
                ("step_test_command", "a step runs only its own tests"),
                ("e2e_command", "e2e runs once at the end of a task; write 'none' if there is no suite"),
            ):
                if re.search(rb"(?m)^" + field.encode() + rb":[ \t]*(#.*)?$", testing):
                    plan.hints.append(".ai/policies/testing.md: %s is empty — %s" % (field, why))
                elif not re.search(rb"(?m)^" + field.encode() + rb":", testing):
                    plan.hints.append(".ai/policies/testing.md: %s is missing — %s" % (field, why))
    return plan


# ---------------------------------------------------------------- output
def apply(plan):
    for item in plan.items:
        if item["content"] is not None:
            path = os.path.join(plan.root, item["target"])
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(item["content"])
        if item["conflict_copy"] is not None:
            copy = os.path.join(plan.root, plan.local_dir, item["target"])
            os.makedirs(os.path.dirname(copy), exist_ok=True)
            with open(copy, "wb") as fh:
                fh.write(item["conflict_copy"])


def report(plan, applied):
    auto = [i for i in plan.items if i["action"] != "conflict"]
    conflicts = [i for i in plan.items if i["action"] == "conflict"]
    head = "applied" if applied else "dry run, nothing written; --apply to write"
    print("project-update: %s (%s)" % (plan.root, head))
    if not plan.items:
        print("  up to date with the installed plugin")
    width = max([len(i["target"]) for i in plan.items] + [10])
    for i in plan.items:
        note = i["note"]
        if i["action"] == "conflict":
            note += "; plugin version %s %s/%s" % ("at" if applied else "will be at", plan.local_dir, i["target"])
        print("  %-9s %-*s  %s" % (i["action"], width, i["target"], note))
        for change in i["policy"] or []:
            print("  %-9s %-*s    %s" % ("policy", width, "", change))
    for h in plan.hints:
        print("  hint      " + h)
    print("%d automatic, %d conflict(s)%s" % (len(auto), len(conflicts),
          ", %d policy change(s) to confirm" % sum(len(i["policy"] or []) for i in auto) if any(i["policy"] for i in auto) else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    for name, tpl in TEMPLATES.items():
        if not os.path.isdir(tpl):
            print("project-update: %s templates not found at %s (run claude-agentic/install.sh)" % (name, tpl), file=sys.stderr)
            return 2
    plan = build_plan(root)
    if plan is None:
        print("project-update: %s has neither .ai/ nor docs/sdlc/ — run /ai-init or /project-init first" % root,
              file=sys.stderr)
        return 2
    pending = [i for i in plan.items if i["action"] != "conflict"]
    if args.check:
        conflicts = len(plan.items) - len(pending)
        if pending:
            print("project is behind the installed plugin: %d file(s) to update%s — run /project-update"
                  % (len(pending), ", %d need a manual merge" % conflicts if conflicts else ""))
            return 1
        print("project matches the installed plugin" + (" (%d file(s) differ by hand-merge choice)" % conflicts if conflicts else ""))
        return 0
    if args.apply:
        apply(plan)
    report(plan, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
