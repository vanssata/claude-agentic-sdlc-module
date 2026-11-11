"""The plan of one run: every rule, in the order D3 sets, collected into one Plan.

shell: build_plan
core: PHASE
"""

import os

from rr_update import blocks
from rr_update import cleanup
from rr_update import files as files_mod
from rr_update import hints
from rr_update import history as history_mod
from rr_update import paths
from rr_update import plan as plan_mod
from rr_update import rules
from rr_update import shared
from rr_update import weights


PHASE = {"split": 0, "delete": 2, "delete?": 2}


def build_plan(root, confirm_delete=None, confirm_via=None, confirm_cleanup=None, cleanup_via=None):
    """D3: split_once -> regenerate -> shared -> block per runtime -> rules -> local -> gitignore, cleanup, hints.
    The caller has run check_kept: nothing here reads a kept file for meaning."""
    plan = plan_mod.Plan(root)
    plan.confirm_cleanup = confirm_cleanup
    plan.cleanup_via = cleanup_via
    plan.confirm_delete = confirm_delete
    plan.confirm_via = confirm_via
    has_ai = os.path.isdir(os.path.join(root, ".ai"))
    has_sdlc = os.path.isdir(os.path.join(root, "docs", "sdlc"))
    if not (has_ai or has_sdlc):
        return None
    history = history_mod.History(paths.HISTORY)
    runtimes = history_mod.project_runtimes(root)
    plan.version_from = history_mod.project_version(root) if has_ai else None

    if has_sdlc:
        tpl = paths.TEMPLATES["project-init"]
        for src, target in paths.SDLC_CREATE:  # the project's own from then on
            if not plan.exists(target):
                plan.add("create", target, content=files_mod.read(os.path.join(tpl, src)).replace(
                    b"{{PROJECT}}", os.path.basename(root).encode()))
        for rt in runtimes:
            for src, target, kind in paths.RUNTIME_MAP[rt]:
                content = files_mod.read(os.path.join(tpl, src))
                if kind == "create":
                    if not plan.exists(target):
                        plan.add("create", target, content=content)
                else:
                    plan_mod.regenerate(plan, history, "project-init/" + src, target, content)
        hints.gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

    if has_ai:
        tpl = paths.TEMPLATES["ai-init"]
        weights.split_once(plan, history)
        files = []
        for dirpath, _, names in os.walk(os.path.join(tpl, ".ai")):
            for n in names:
                files.append(os.path.relpath(os.path.join(dirpath, n), tpl).replace(os.sep, "/"))
        for rel in sorted(files):
            if rel in paths.NOT_COPIED or rel in (paths.VERIFICATION_MD, paths.WEIGHT_PROJECT):
                continue
            content = files_mod.read(os.path.join(tpl, rel))
            if rel in paths.CREATE_ONLY or rel.startswith(paths.CREATE_ONLY_DIRS):
                if not plan.exists(rel):
                    plan.add("create", rel, content=content)
            else:
                plan_mod.regenerate(plan, history, "ai-init/" + rel, rel, content)
        weights.weight_md(plan, history)
        shared.shared_update(plan, history, runtimes)
        rules.rule_sources(plan)
        cleanup.local_cache(plan)
        cleanup.cleanup_update(plan)
        for rt in runtimes:
            blocks.block_update(plan, history, rt)
        rules.rules_update(plan, runtimes)
        cleanup.deletion_hint(plan)
        hints.gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))
        cleanup.tracked_ignored_hint(plan)
        hints.verification_hints(plan)
        hints.budget_hints(plan, runtimes)
        if plan.items and plan.exists(paths.STATE_FILE):
            plan.hints.append("%s: a task is in flight while files are regenerated — check that the files "
                              "its current step may touch still exist afterwards" % paths.STATE_FILE)
        # Last of the items: an apply that stops short leaves the version alone, and the next run plans the rest again.
        ours = history_mod.template_version()
        if plan.version_from != ours:
            plan.add("regenerate" if plan.exists(paths.VERSION_FILE) else "create", paths.VERSION_FILE,
                     "schema %d" % ours, content=b"%d\n" % ours)
    if has_sdlc:
        hints.constitution_hint(plan)
    plan.items.sort(key=lambda i: 3 if i["target"] == paths.VERSION_FILE else PHASE.get(i["action"], 1))
    return plan
