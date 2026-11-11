"""The shared tree: refusing to drop a copy whose fallback is missing, and the shared-copy rows of the plan.

shell: require_shared, shared_update
"""

import os

from rr_update import files
from rr_update import history as history_mod
from rr_update import paths as paths_mod


# ---------------------------------------------------------------- shared files, rules, caches
def require_shared(paths, runtimes):
    """Refuse, before anything is written, to drop a project copy whose shared fallback is missing:
    in this plugin's tree, or in another installed home of a runtime the project declares. A home
    this machine does not have is not checked."""
    undeclared = sorted(p for p in paths if p not in paths_mod.SHARED_SET)
    if undeclared:
        raise history_mod.SchemaError("not in the shared set, never deleted as a shared copy: %s" % ", ".join(undeclared))
    rels = sorted(p[len(".ai/"):] for p in paths)
    missing = [r for r in rels if not os.path.isfile(os.path.join(paths_mod.SHARED, r))]
    if missing:
        raise history_mod.SchemaError("the plugin's shared tree %s lacks %d file(s) a project copy would fall back to: %s — "
                          "reinstall the plugin (install.sh), then run this again" % (paths_mod.SHARED, len(missing), ", ".join(missing)))
    homes = {"claude": os.path.join(os.path.expanduser("~"), ".claude"),
             "codex": os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")}
    mine = os.path.realpath(paths_mod.PLUGIN_HOME)
    for runtime in runtimes:
        home = homes.get(runtime)
        if (not home or os.path.realpath(home) == mine
                or not os.path.isdir(os.path.join(home, "skills", "project-update"))):
            continue
        tree = os.path.join(home, "riskrails", "ai")
        missing = [r for r in rels if not os.path.isfile(os.path.join(tree, r))]
        if missing:
            raise history_mod.SchemaError("%s has this plugin installed for %s, but %d of the %d shared file(s) a project copy "
                              "would fall back to are missing from %s — run `install.sh --target %s` from this "
                              "build, then run this again" % (home, runtime, len(missing), len(rels), tree, runtime))


def shared_update(plan, history, runtimes):
    """R17: an unedited copy of a shared file is offered for deletion; an edited one is an
    override, kept, and named once (OQ8)."""
    edited, candidates = [], []
    extra = history_mod.undeclared_shared()
    if extra:
        plan.hints.append("the shared tree %s holds %d file(s) outside the shared set, ignored — reinstall the "
                          "plugin (install.sh) if you did not put them there: %s" % (paths_mod.SHARED, len(extra), ", ".join(extra)))
    for path in sorted(history_mod.shared_files()):
        data = plan.read(path)
        if data is None:
            continue
        why = files.unsafe_path(plan.root, path)
        if why:
            plan.hints.append("%s: %s, so this update never deletes it — check by hand whether it is still "
                              "needed" % (path, why))
        elif not history.shipped("ai-init/" + path, data):
            edited.append(path)
        else:
            candidates.append(path)
    if candidates:
        try:
            require_shared(candidates, runtimes)
        except history_mod.SchemaError as exc:
            plan.hints.append("%s — the copies stay until then" % exc)
            candidates = []
    for path in candidates:
        why = "[shared] identical to a shipped version"
        plan.gated("delete", path, why, reason=why)
    if edited:
        plan.hints.append("%d file(s) override the plugin's shared copy and no longer receive its changes: %s — "
                          "diff each against %s/<path>; `ai-path <path>` shows which applies; delete one when it "
                          "adds nothing" % (len(edited), ", ".join(edited), paths_mod.SHARED))
