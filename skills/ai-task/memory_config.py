"""The configuration of packages mode: the policy file's schema and defaults, MemoryConfig, loading and
checking .ai/policies/memory.json, and the mode a project runs in."""
import contextlib
import os
import re

import memory_format as mf
import memory_io as mio


SCHEMA = 1
DEFAULTS = {"schema": 1, "mode": "files", "period": "quarter", "package_max_bytes": 1048576, "cleanup": False,
            "excerpt_max_bytes": 1024, "keep_rules": 1, "recall": {"budget_tokens": 1500, "max_items": 40}}


# ------------------------------------------------------------------ configuration (§D11, §I6)
def author_slug(name):
    slug = re.sub(r"[^a-z0-9-]+", "-", (name or "").casefold()).strip("-")[:32].strip("-")
    return slug if slug and mf.AUTHOR_RE.match(slug) else "unknown"


class MemoryConfig:
    """The project policy (.ai/policies/memory.json) and the developer's own
    choices (.ai/local/memory/config.json)."""

    def __init__(self, root, policy, local, present):
        self.root, self.policy, self.local, self.present = root, policy, local, present

    def __getattr__(self, name):
        if name in ("mode", "period", "package_max_bytes", "cleanup", "excerpt_max_bytes", "keep_rules"):
            return self.policy.get(name, DEFAULTS[name])
        raise AttributeError(name)

    @property
    def recall_budget(self):
        return int((self.policy.get("recall") or {}).get("budget_tokens", 1500))

    @property
    def recall_max_items(self):
        return int((self.policy.get("recall") or {}).get("max_items", 40))

    @property
    def author(self):
        return self.local.get("author") or author_slug(os.environ.get("USER") or os.environ.get("USERNAME"))

    @property
    def index(self):
        return self.local.get("index") or "none"

    @property
    def packages(self):
        return self.mode == "packages"


def load_config(root):
    path = os.path.join(root, mio.POLICY_REL)
    present = os.path.exists(path)
    policy = dict(DEFAULTS)
    if present:
        try:
            loaded = mio.read_json(path)
        except (OSError, ValueError) as exc:
            raise mio.MemoryError_("%s is not valid JSON (%s): fix it, or 'state.py memory disable'"
                               % (mio.POLICY_REL, exc)) from exc
        if not isinstance(loaded, dict):
            raise mio.MemoryError_("%s must be a JSON object" % mio.POLICY_REL)
        schema = loaded.get("schema", 1)
        if isinstance(schema, int) and not isinstance(schema, bool) and schema > SCHEMA:
            raise mio.MemoryError_("%s has schema %s; this state.py knows %d — update the plugin"
                               % (mio.POLICY_REL, schema, SCHEMA))
        policy.update(loaded)
        check_policy(policy)
    local = {}
    with contextlib.suppress(OSError, ValueError):
        found = mio.read_json(os.path.join(root, mio.LOCAL_REL, "config.json"))
        if isinstance(found, dict):
            local = found
    where = os.path.join(mio.LOCAL_REL, "config.json")
    if local.get("author") is not None and not (isinstance(local["author"], str)
                                                and mf.AUTHOR_RE.match(local["author"])):
        raise mio.MemoryError_("%s: author %r is not a slug of [a-z0-9-]" % (where, local["author"]))
    if local.get("index", "none") not in ("none", "sqlite"):
        raise mio.MemoryError_("%s: index takes none or sqlite" % where)
    return MemoryConfig(root, policy, local, present)


def check_policy(policy):
    """Every key of memory.json with its type (§I6): a wrong one is a refusal
    naming the key, never a traceback inside close."""
    def is_int(value, low):
        return isinstance(value, int) and not isinstance(value, bool) and value >= low
    problems = []
    if not is_int(policy.get("schema"), 1):
        problems.append("schema must be an integer (1)")
    if policy.get("mode") not in ("files", "packages"):
        problems.append('mode must be "files" or "packages"')
    if policy.get("period") not in mf.PERIODS:
        problems.append("period must be month, quarter or year")
    if not is_int(policy.get("package_max_bytes"), 1024):
        problems.append("package_max_bytes must be an integer of at least 1024")
    if not isinstance(policy.get("cleanup"), bool):
        problems.append("cleanup must be true or false")
    if not is_int(policy.get("excerpt_max_bytes"), 0):
        problems.append("excerpt_max_bytes must be an integer >= 0")
    if policy.get("keep_rules") != 1:
        problems.append("keep_rules must be 1")
    recall = policy.get("recall")
    if not (isinstance(recall, dict) and is_int(recall.get("budget_tokens", 1500), 1)
            and is_int(recall.get("max_items", 40), 1)):
        problems.append('recall must be {"budget_tokens": N, "max_items": N}')
    if problems:
        raise mio.MemoryError_("%s: %s" % (mio.POLICY_REL, "; ".join(problems)))


def mode_of(root):
    """'files' or 'packages' without raising: close must archive whatever happens."""
    try:
        return load_config(root).mode
    except mio.MemoryError_:
        return "files"
