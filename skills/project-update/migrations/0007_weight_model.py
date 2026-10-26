"""0007: the weight table carries the risk-tier table's edits; a task in flight gets a mode.

The six-axis weight model in .ai/policies/weight.json is what the schema-7
surface of state.py reads. This migration gives every project one — the shipped
table, created when the project has none — and converts into it every value the
project added on top of the risk-tier tables it was installed with:

  tiers.T0-T2.examples -> examples.light, T3-T4 -> guarded, T5-T6 -> full
  path_scopes money/identity/customer data -> axes.domain.modules
  path_scopes auth/security -> the domain hint; pipeline -> the behaviour hint;
              dependencies -> the novelty hint
  path_scopes infra/k8s/deploy/production -> reversibility.irreversible when the
              glob names prod, else reversibility.needs_step
  path_scopes migrations/schema/config -> reversibility.needs_step
  a scope this table does not know, with min_tier T5 or T6 -> axes.domain.modules
  sensors.tests.* -> tests.* with max_suite_runs = min(old, 2), and
  review_rounds_max, remediation_rounds -> carried — each only when the project
              changed it and weight.json still holds the shipped value

Everything else (diff_budget, sensors, pipeline profiles, model tiers, the
escalation and downgrade rules) has no place in the weight table; its prose lives
in docs/weight.md.

risk-tiers.json and its mirror stay where they are, untouched: the old surface
reads them until it is removed, and the plugin still ships them, so moving or
deleting them here would only have the next run put them back (a template is
never shipped at a path a migration moved away). Their retirement belongs with
the template's.

A task in flight keeps running on the old surface: it gets a `mode` from its
tier and a `weight` that says it was migrated, never a schema-7 marker —
state.py decides by that marker.
"""
import json
from collections import OrderedDict

VERSION = 7
TITLE = "carry the risk-tier table's edits into weight.json, and give a task in flight a mode"
OLD = ".ai/policies/risk-tiers.json"
NEW = ".ai/policies/weight.json"
MOVES = []

TIER_MODE = {"T0": "light", "T1": "light", "T2": "light", "T3": "guarded", "T4": "guarded",
             "T5": "full", "T6": "full_irreversible"}
EXAMPLE_MODE = dict(TIER_MODE, T6="full")
DOMAIN = {"payments", "money", "tax", "invoice", "identity", "customer_data", "personal_data"}
INFRA = {"infra", "k8s", "deploy", "production"}
NEEDS_STEP = {"migrations", "schema", "config"}
HINTS = {"auth": "domain", "security": "domain", "pipeline": "behaviour", "dependencies": "novelty"}
DROPPED = {"tests", "docs", "source"}
TEST_KEYS = ("timeout_seconds", "env_retries", "log_max_bytes")


def _loads(raw):
    try:
        doc = json.loads(raw, object_pairs_hook=OrderedDict)
    except (TypeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _shipped(ctx):
    """What every shipped risk-tiers.json said — per tier, per scope, and each
    scalar a run carries — and the shipped weight table: only a value the
    project changed on top of these is carried."""
    examples, scopes, scalars = {}, {}, {}
    for raw in ctx.shipped(OLD):
        doc = _loads(raw) or {}
        for key, value in _scalars(doc).items():
            scalars.setdefault(key, []).append(value)
        for tier, entry in (doc.get("tiers") or {}).items():
            if isinstance(entry, dict):
                examples.setdefault(tier, set()).update(e for e in entry.get("examples") or [] if isinstance(e, str))
        for scope in doc.get("path_scopes") or []:
            if isinstance(scope, dict):
                scopes.setdefault(scope.get("scope"), set()).update(
                    p for p in scope.get("paths") or [] if isinstance(p, str))
    return examples, scopes, scalars, _loads(ctx.template(NEW)) or {}


def _scalars(old):
    """{"tests.<key>" | "review_rounds_max" | "remediation_rounds": value} of an old table."""
    out = {}
    tests = (old.get("sensors") or {}).get("tests") if isinstance(old.get("sensors"), dict) else None
    for key in TEST_KEYS + ("max_suite_runs",):
        if isinstance(tests, dict) and key in tests:
            out["tests." + key] = tests[key]
    for key in ("review_rounds_max", "remediation_rounds"):
        if isinstance(old.get(key), int):
            out[key] = old[key]
    return out


def _get(doc, dotted):
    for part in dotted.split("."):
        doc = doc.get(part) if isinstance(doc, dict) else None
    return doc


def _add(items, values):
    for value in values:
        if value not in items:
            items.append(value)


def _hint(doc, axis, paths, note):
    hint = next((h for h in doc.setdefault("hints", []) if isinstance(h, dict) and h.get("axis") == axis), None)
    if hint is None:
        doc["hints"].append(OrderedDict([("paths", list(paths)), ("axis", axis), ("note", note)]))
    else:
        _add(hint.setdefault("paths", []), paths)


def convert(old, base, shipped):
    """The weight table `base` plus what the old table `old` added on top of the
    `shipped` (examples, scopes, scalars, weight template) it was installed
    with. A scalar is carried only when the old table changed it and `base`
    still holds the shipped weight value — a project's own weight.json edit
    wins. `base` is not changed, and converting twice adds nothing new."""
    shipped_examples, shipped_scopes, shipped_scalars, template = shipped
    new = json.loads(json.dumps(base), object_pairs_hook=OrderedDict)
    axes = new.setdefault("axes", OrderedDict())
    for tier, entry in (old.get("tiers") or {}).items():
        if tier in EXAMPLE_MODE and isinstance(entry, dict):
            extra = [e for e in entry.get("examples") or []
                     if isinstance(e, str) and e not in shipped_examples.get(tier, set())]
            if extra:
                _add(new.setdefault("examples", OrderedDict()).setdefault(EXAMPLE_MODE[tier], []), extra)
    for scope in old.get("path_scopes") or []:
        if not isinstance(scope, dict):
            continue
        name = scope.get("scope")
        paths = [p for p in scope.get("paths") or []
                 if isinstance(p, str) and p not in shipped_scopes.get(name, set())]
        if not paths or name in DROPPED:
            continue
        if name in DOMAIN or (name not in HINTS and name not in INFRA | NEEDS_STEP
                              and scope.get("min_tier") in ("T5", "T6")):
            _add(axes.setdefault("domain", OrderedDict()).setdefault("modules", []), paths)
        elif name in HINTS:
            _hint(new, HINTS[name], paths, "%s (from risk-tiers.json)" % name)
        elif name in INFRA | NEEDS_STEP:
            rev = axes.setdefault("reversibility", OrderedDict())
            two = [p for p in paths if name in INFRA and "prod" in p]
            _add(rev.setdefault("irreversible", []), two)
            _add(rev.setdefault("needs_step", []), [p for p in paths if p not in two])
    for key, value in _scalars(old).items():
        if value in shipped_scalars.get(key, []) or _get(base, key) != _get(template, key):
            continue
        if key == "tests.max_suite_runs" and isinstance(value, int):
            value = min(value, 2)
        if key.startswith("tests."):
            new.setdefault("tests", OrderedDict())[key[len("tests."):]] = value
        else:
            new[key] = value
    return new


def _mode(state):
    """The task in flight: a mode from its tier, a weight nobody measured. The
    schema-7 marker is never added: the task finishes on the surface it began on."""
    if state.get("schema") == VERSION:
        return state
    tier = state.get("risk_tier")
    if tier in TIER_MODE:
        state.setdefault("mode", TIER_MODE[tier])
    state.setdefault("weight", {"w": None, "axes": {}, "unknown": ["migrated"]})
    return state


def plan(ctx):
    old = ctx.read_json(OLD)
    shipped = _shipped(ctx)
    before = ctx.read(NEW)
    if before is None:
        template = ctx.template(NEW)
        doc = convert(old, _loads(template), shipped) if old is not None else None
        if doc is None or doc == _loads(template):
            ctx.create(NEW, template)
        else:
            ctx.create(NEW, (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode())
    elif old is not None:
        ctx.edit_json(NEW, lambda new: convert(old, new, shipped))
    after = ctx.read(NEW)
    if old is not None and _loads(after) != _loads(before or ctx.template(NEW)):
        ctx.hint("%s now carries this project's risk-tier edits: run `state.py weight --mirror` to "
                 "regenerate weight.md beside it" % NEW)
    ctx.patch_state(_mode)
