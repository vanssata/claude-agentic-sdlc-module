"""The project rules: where they come from, how they render, the nested tree, and the rules rows of the plan.

shell: rule_sources, rendered_rules, nested_tree, unwalked_dir, _frozen_block, rules_update
"""

import os

import render_instructions  # next to the entry, whose directory the entry puts on sys.path

from rr_update import files
from rr_update import paths


def rule_sources(plan):
    """OQ1: a rule source is not kept. Each `.ai/rules/<slug>.md` is `delete?` behind the gate with its
    original copied; until it is confirmed the rule stays rendered."""
    rules = os.path.join(plan.root, paths.RULES_DIR)
    for name in sorted(os.listdir(rules)) if os.path.isdir(rules) else []:
        rel = "%s/%s" % (paths.RULES_DIR, name)
        if name.endswith(".md") and name != "README.md" and os.path.isfile(os.path.join(rules, name)) \
                and not files.unsafe_path(plan.root, rel):
            why = "[rules] rule sources are not kept by an update: the rendered blocks go with it"
            plan.gated("delete", rel, why, reason=why)


def rendered_rules(plan):
    """Every (file, slug) in the project that carries a rule block today, plus
    every path-scoped copy under .claude/rules/. Walked rather than remembered:
    a manifest would be one more file to keep true, and the markers already say
    who wrote them."""
    blocks, docs = [], []
    names = set(render_instructions.RULE_FILE.values())
    for dirpath, dirnames, filenames in os.walk(plan.root):
        dirnames[:] = sorted(d for d in dirnames if d not in paths.RULES_SKIP
                             and not os.path.lexists(os.path.join(dirpath, d, ".git")))
        rel_dir = os.path.relpath(dirpath, plan.root)
        for name in sorted(filenames):
            rel = name if rel_dir == "." else os.path.join(rel_dir, name)
            rel = rel.replace(os.sep, "/")
            if name in names:
                text = plan.read(rel)
                if text is None:
                    continue
                for slug in render_instructions.rule_slugs_in(text.decode("utf-8", "replace")):
                    blocks.append((rel, slug))
            elif rel.startswith(render_instructions.CLAUDE_RULES_DIR + "/") and name.endswith(".md"):
                text = plan.read(rel)
                if text is not None and render_instructions.RULE_GENERATED % name[:-3] in \
                        text.decode("utf-8", "replace"):
                    docs.append(rel)
    return blocks, docs


def nested_tree(root, rel_dir):
    """The first directory below the root on the way to `rel_dir`, `rel_dir`
    included, that holds a .git entry (a worktree, a nested repository, a
    submodule), or None. The same predicate rendered_rules() prunes on."""
    # "." and "" are the root itself (dirs: ["."] reaches here as ""), whose
    # own .git is not a nested tree.
    parts = [p for p in rel_dir.split("/") if p not in ("", ".")]
    for i in range(1, len(parts) + 1):
        candidate = "/".join(parts[:i])
        if os.path.lexists(os.path.join(root, candidate, ".git")):
            return candidate
    return None


def unwalked_dir(root, rel_dir):
    """Why the take-back walk (rendered_rules) never enters `rel_dir`, or None:
    a RULES_SKIP name on the way, or a symlinked directory on the way."""
    here = root
    for part in (p for p in rel_dir.split("/") if p not in ("", ".")):
        here = os.path.join(here, part)
        if part.casefold() in paths.RULES_SKIP_FOLDED:
            return "%s is under a directory the take-back never walks (%s)" % (rel_dir, part)
        if os.path.islink(here):
            return "%s is a symlink, which the take-back never follows" % os.path.relpath(here, root).replace(os.sep, "/")
    return None


def _frozen_block(plan, target, slug):
    """True when `target` is a readable regular file inside the project, holding a
    block for `slug`, at a place the take-back walk (rendered_rules) never enters: a
    RULES_SKIP name or a nested git tree on its real path. A symlink that leads inside
    the walked part of the project is removed by the same run; one that leads outside
    the project, a directory, a FIFO or an unreadable file is not read at all."""
    full = os.path.join(plan.root, target)
    try:
        real = os.path.realpath(full)
        base = os.path.realpath(plan.root)
        if os.path.commonpath([real, base]) != base or not os.path.isfile(real):
            return False
        rel_dir = os.path.relpath(os.path.dirname(real), base).replace(os.sep, "/")
        parts = [p for p in rel_dir.split("/") if p not in ("", ".")]
        if not (any(p in paths.RULES_SKIP for p in parts) or nested_tree(base, rel_dir) is not None):
            return False
        held = plan.read(target)
    except (OSError, ValueError):
        return False
    return held is not None and slug in render_instructions.rule_slugs_in(held.decode("utf-8", "replace"))


def rules_update(plan, runtimes):
    """Render `.ai/rules/<slug>.md` into the instruction file of every directory
    it names, and take back what a rule no longer asks for. The text around a
    block belongs to the project and is never read for meaning, only preserved.
    A rule whose source this run deletes is no longer rendered."""
    rules_path = os.path.join(plan.root, paths.RULES_DIR)
    if not os.path.isdir(rules_path):
        return
    try:
        rules = [r for r in render_instructions.load_rules(rules_path)
                 if "%s/%s.md" % (paths.RULES_DIR, r.slug) not in plan.removed]
    except render_instructions.RenderError as exc:
        plan.hints.append("%s — that rule is not rendered; the rest are" % exc)
        return
    wanted = render_instructions.rule_targets(rules, runtimes)
    managed = {(i["target"], i["slug"]) for i in wanted if i["kind"] == "block"}
    kept_docs = {i["target"] for i in wanted if i["kind"] == "doc"}

    for item in wanted:
        source = "%s/%s.md" % (paths.RULES_DIR, item["slug"])
        target, content = item["target"], item["content"]
        tree = nested_tree(plan.root, os.path.dirname(target)) if item["kind"] == "block" else None
        if tree is not None:
            # Not this project's file, and the take-back never walks there: a
            # block written there could never be taken back again.
            plan.hints.append("%s: %s is a nested git tree (worktree, repository or submodule)"
                              " — rule %s is not rendered there" % (target, tree, item["slug"]))
            continue
        skip = unwalked_dir(plan.root, os.path.dirname(target)) if item["kind"] == "block" else None
        if skip is not None:
            hint = "%s: %s — rule %s is not rendered there" % (target, skip, item["slug"])
            if _frozen_block(plan, target, item["slug"]):
                hint += ("; an earlier rendering of it is still there, the take-back never walks there:"
                         " remove that block by hand")
            plan.hints.append(hint)
            continue
        current = plan.read(target)
        if item["kind"] == "doc":
            new = content.encode()
            if current is None:
                plan.add("create", target, "rendered from " + source, content=new)
            elif current != new:
                plan.add("regenerate", target, "rendered from " + source, content=new)
            continue
        text = "" if current is None else current.decode("utf-8")
        new = render_instructions.splice_rule(text, item["slug"], content).encode()
        if current is None:
            plan.add("create", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)
        elif current != new:
            plan.add("regenerate", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)

    blocks, docs = rendered_rules(plan)
    for target, slug in blocks:
        if (target, slug) in managed:
            continue
        text = plan.read(target).decode("utf-8")
        # The block is ours; the file is not. Take the block, leave the file.
        plan.add("regenerate", target, "rule block %s removed (%s/%s.md no longer renders here)"
                 % (slug, paths.RULES_DIR, slug),
                 content=render_instructions.strip_rule(text, slug).encode())
    for target in docs:
        if target in kept_docs:
            continue
        # The whole file is a rendered copy, so taking it away is a deletion, and
        # a deletion waits for a human exactly as a migration's does.
        slug = os.path.basename(target)[:-3]
        why = "[rules] %s" % ("%s/%s.md no longer sets paths:" % (paths.RULES_DIR, slug)
                              if slug in {r.slug for r in rules}
                              else "source %s/%s.md is gone" % (paths.RULES_DIR, slug))
        if plan.confirm_delete:
            plan.add("delete", target, why, reason=why)
            plan.remove(target)
        else:
            plan.add("delete?", target, why, reason=why)
