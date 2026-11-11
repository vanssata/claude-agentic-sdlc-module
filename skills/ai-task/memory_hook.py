"""The git hook (R17, §D10): the installed shim and where it points, the policy file, and the enable and
disable commands that write and remove them."""
import json
import os
import re

import memory_config as mcfg
import memory_format as mf
import memory_io as mio


# ------------------------------------------------------------------ status, show
def hook_state(root):
    code, out, _ = mio.git(root, "config", "--get", "core.hooksPath")
    if code == 0 and out.strip():
        return "hookspath"
    path = hooks_path(root)
    if not path:
        return "absent"
    hook = os.path.join(path, "pre-push")
    text = mio.read_bytes(hook)
    if text is None:
        return "absent"
    if mio.HOOK_MARKER.encode() in text:
        decoded = text.decode("utf-8", "replace")
        if not any(os.path.isfile(p) for p in shim_paths(decoded)):
            return "installed, validator missing — pushes are NOT checked ('state.py memory enable' rewrites it)"
        return "current" if decoded == shim_text() else "installed (stale)"
    return "foreign"


# ------------------------------------------------------------------ the git hook (R17, §D10)
def hooks_path(root):
    code, out, _ = mio.git(root, "rev-parse", "--git-path", "hooks")
    if code != 0 or not out.strip():
        return None
    path = out.strip()
    return path if os.path.isabs(path) else os.path.join(root, path)


def shim_candidates(validator=None):
    """Where the shim looks for the validator, in order: the hook beside this
    module, the hook in either runtime home, then this module itself — a Codex
    install copies skills/ai-task/ but not every hook."""
    return [validator or mio.VALIDATOR, "$HOME/.claude/hooks/memory-pre-push.py",
            "${CODEX_HOME:-$HOME/.codex}/hooks/memory-pre-push.py", mio.SELF,
            "$HOME/.claude/skills/ai-task/memory_sync.py",
            "${CODEX_HOME:-$HOME/.codex}/skills/ai-task/memory_sync.py"]


def shim_text(validator=None):
    return ("#!/bin/sh\n%s — written by 'state.py memory enable'; 'state.py memory disable' removes it\n"
            "for v in %s; do\n"
            "  [ -f \"$v\" ] && exec python3 -I \"$v\" \"$@\"\n"
            "done\n"
            "echo \"riskrails memory: validator not found — this push is not checked\" >&2; exit 0\n"
            % (mio.HOOK_MARKER, " ".join('"%s"' % c for c in shim_candidates(validator))))


def shim_paths(text):
    """The shim's candidates as paths on this machine."""
    match = re.search(r"^for v in (.+); do$", text, re.M)
    home = os.path.expanduser("~")
    codex = os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")
    return [c.replace("${CODEX_HOME:-$HOME/.codex}", codex).replace("$HOME", home)
            for c in re.findall(r'"([^"]+)"', match.group(1) if match else "")]


def snippet_text(validator=None):
    validator = validator or mio.VALIDATOR
    return ("# riskrails memory: add to your own pre-push hook (stdin can be read only once)\n"
            "rr_in=$(mktemp) && cat > \"$rr_in\"\n"
            "python3 -I \"%s\" \"$@\" < \"$rr_in\" || { rr=$?; rm -f \"$rr_in\"; exit $rr; }\n"
            "# … then your hook, reading \"$rr_in\" where it read stdin …\n"
            "rm -f \"$rr_in\"\n" % validator)


def install_hook(root):
    """installed | current | foreign | hookspath (R17)."""
    code, out, _ = mio.git(root, "config", "--get", "core.hooksPath")
    if code == 0 and out.strip():
        return "hookspath"
    path = hooks_path(root)
    if not path:
        raise mio.MemoryError_("not a git repository: no hooks path", 2)
    hook = os.path.join(path, "pre-push")
    text = mio.read_bytes(hook)
    if text is not None and mio.HOOK_MARKER.encode() not in text:
        return "foreign"
    if text is not None and text.decode("utf-8", "replace") == shim_text():
        return "current"
    os.makedirs(path, exist_ok=True)
    mio.atomic_write(hook, shim_text())
    os.chmod(hook, 0o755)
    return "installed"


def remove_hook(root):
    path = hooks_path(root)
    hook = os.path.join(path, "pre-push") if path else None
    text = mio.read_bytes(hook) if hook else None
    if text is not None and mio.HOOK_MARKER.encode() in text:
        os.remove(hook)
        return "removed"
    return "foreign" if text is not None else "absent"


def write_policy(root, policy):
    mio.atomic_write(os.path.join(root, mio.POLICY_REL), json.dumps(policy, indent=2, ensure_ascii=False) + "\n")


def enable(root, author=None, period=None, index=None):
    cfg = mcfg.load_config(root)
    policy = dict(mcfg.DEFAULTS)
    policy.update(cfg.policy if cfg.present else {})
    policy["mode"] = "packages"
    if period:
        if period not in mf.PERIODS:
            raise mio.MemoryError_("--period takes one of %s" % ", ".join(mf.PERIODS))
        policy["period"] = period
    write_policy(root, policy)
    local = dict(cfg.local)
    local["schema"] = 1
    local["author"] = mcfg.author_slug(author) if author else cfg.author
    if index:
        if index not in ("none", "sqlite"):
            raise mio.MemoryError_("--index takes none or sqlite")
        local["index"] = index
    local.setdefault("index", "none")
    mio.atomic_write(mio.local_path(root, "config.json"), json.dumps(local, sort_keys=True) + "\n")
    return install_hook(root)


def disable(root):
    cfg = mcfg.load_config(root)
    policy = dict(cfg.policy)
    policy["mode"] = "files"
    write_policy(root, policy)
    return remove_hook(root)
