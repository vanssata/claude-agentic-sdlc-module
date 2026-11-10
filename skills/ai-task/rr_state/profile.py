"""profile: the plan profile, the live plan detection for both runtimes, the drift acknowledgement and the profile resolver.

core: js_number, js_str, js_truthy, jwt_plan_type, SAME_TIER, context_mode, installer_command, PLAN_PROFILES, DIRECT_MODE_CAP
shell: profile_file, read_profile, read_quota, preferred_runtime, advisory_line, advise, read_json_object, detect_claude, detect_codex, profile_detect, acknowledged, drift_ack_path, read_drift_ack, write_drift_ack, open_drift, load_resolver
"""
import base64
import decimal
import hashlib
import importlib.util
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone

from rr_state import dialog
from rr_state import fs
from rr_state import ledger
from rr_state import runtime as rr_runtime
from rr_state import task


def profile_file(home):
    """<home>/riskrails/profile.json."""
    return os.path.join(home, "riskrails", "profile.json")


def read_profile(runtime=None, rt=rr_runtime.Runtime()):
    """<home>/riskrails/profile.json, written by the installer; {} when absent,
    which turns every plan budget into a no-op."""
    try:
        with open(profile_file(rr_runtime.runtime_home(runtime or rr_runtime.own_runtime(runtime=rt.name))), encoding="utf-8") as fh:
            data = dialog.json_loads_capped(fh.read())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, RecursionError):
        return {}


def read_quota(runtime):
    """The weekly percentage runtime-gate last recorded, or None when unknown
    or stale — advice never rests on a reading older than a day."""
    try:
        with open(os.path.join(rr_runtime.runtime_home(runtime), "state", "runtime-gate.json"),
                  encoding="utf-8") as fh:
            quota = json.load(fh).get("quota") or {}
        seen, resets = float(quota.get("seen_at") or 0), float(quota.get("resets_at") or 0)
        now_s = datetime.now(timezone.utc).timestamp()
        if not seen or now_s - seen > 86400 or (resets and now_s > resets):
            return None
        pct = quota.get("weekly_pct")
        return float(pct) if pct is not None else None
    except (OSError, ValueError, AttributeError, TypeError, RecursionError):
        return None


def preferred_runtime(workflow, rt=rr_runtime.Runtime()):
    """(runtime, reason) when the plan's table or the quota rule names the
    other runtime and it is installed; None otherwise. Advice only (D3)."""
    me = rr_runtime.own_runtime(runtime=rt.name)
    other = rr_runtime.other_runtime(me, rt=rt)
    if not rr_runtime.installed(other):
        return None
    pref = read_profile(me, rt=rt).get("preferred_runtime") or {}
    named = (pref.get("by_workflow") or {}).get(workflow) or pref.get("default") or "same"
    if named == other:
        return other, "plan table: %s -> %s" % (workflow, other)
    limit = pref.get("quota_pct")
    mine, theirs = read_quota(me), read_quota(other)
    if limit is not None and mine is not None and mine >= float(limit) \
            and (theirs is None or theirs < float(limit)):
        return other, "quota %.0f%% >= %.0f%%" % (mine, float(limit))
    return None


def advisory_line(state, rt=rr_runtime.Runtime()):
    found = preferred_runtime(state.get("workflow"), rt=rt)
    return "preferred runtime: %s (%s)" % found if found else None


def advise(state, rt=rr_runtime.Runtime()):
    line = advisory_line(state, rt=rt)
    if line:
        print(line, file=sys.stderr)      # stdout carries the task id callers capture


def js_number(value):
    """Number.prototype.toString for a JSON number: shortest digits, exponent
    form below 1e-6 and from 1e21."""
    f = float(value)
    if f == 0:
        return "0"
    d = decimal.Decimal(repr(f))
    if 1e-6 <= abs(f) < 1e21:
        text = format(d, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    sign, digits, exp = d.normalize().as_tuple()
    mant = "".join(map(str, digits))
    power = exp + len(mant) - 1
    return "%s%s%s%se%s%d" % ("-" if sign else "", mant[0], "." if len(mant) > 1 else "", mant[1:],
                               "+" if power >= 0 else "-", abs(power))


def js_str(value):
    """String(value) as bin/riskrails.js wrote it, for the detection port; None
    is "" because every JS caller had already turned null into ''."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value) if abs(value) <= 2 ** 53 else js_number(value)
    if isinstance(value, float):
        return js_number(value)
    if isinstance(value, list):
        return ",".join(js_str(v) for v in value)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def js_truthy(value):
    return not (value is None or value is False or value == "" or
                (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0))


def read_json_object(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else {}


def detect_claude():
    """The port of detectClaudePlan (bin/riskrails.js before R36.16): ~/.claude.json's
    oauthAccount, the same regular expressions in the same order."""
    home = os.environ.get("HOME") or os.path.expanduser("~")
    account = read_json_object(os.path.join(home, ".claude.json")) or {}
    oauth = account.get("oauthAccount")
    o = oauth if isinstance(oauth, dict) else {}

    def s(value):
        return "" if value is False else js_str(value)
    org = s(o.get("organizationType")) or s(account.get("organizationType"))
    ratelimit = s(o.get("organizationRateLimitTier"))
    plan, why = None, ""
    if re.search(r"^claude_max|max", org):
        if "max_20x" in ratelimit:
            plan, why = "max20", "organizationRateLimitTier %s" % ratelimit
        else:
            plan, why = "max", "organizationType %s%s" % (org, ", " + ratelimit if ratelimit else "")
    elif re.search(r"pro", org):
        plan, why = "pro", "organizationType %s" % org
    elif re.search(r"team|enterprise", org):
        seat = " ".join(js_str(v) for v in (o.get("seatTier"), o.get("userRateLimitTier"),
                                             o.get("organizationRateLimitTier")) if v is not None and v != "")
        if re.search(r"premium|max", seat):
            plan, why = "team-max", "%s, seat '%s'" % (org, seat)
        elif re.search(r"standard|pro", seat):
            plan, why = "team-pro", "%s, seat '%s'" % (org, seat)
        else:
            why = "team"
    api = not isinstance(oauth, dict) and any(os.environ.get(k) for k in (
        "ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"))
    fields = {k: js_str(o.get(k)) for k in ("organizationType", "organizationRateLimitTier", "seatTier",
                                            "userRateLimitTier")}
    fields.update(accountOrganizationType=js_str(account.get("organizationType")), api=api)
    return {"plan": plan, "from": why or None, "org": org}, api, fields


def jwt_plan_type(token):
    """chatgpt_plan_type from a JWT's body, decoded as leniently as Node's
    Buffer.from(body, 'base64url'): characters outside the alphabet are skipped,
    decoding stops at '=', bad UTF-8 becomes U+FFFD. The value is returned as
    JSON gave it; the caller applies JS truthiness."""
    try:
        body = token.split(".")[1].split("=")[0].replace("+", "-").replace("/", "_")
        body = re.sub(r"[^A-Za-z0-9_-]", "", body)
        body = body[:len(body) - 1] if len(body) % 4 == 1 else body
        text = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode("utf-8", "replace")
        auth = json.loads(text).get("https://api.openai.com/auth") or {}
        value = auth.get("chatgpt_plan_type")
        return value if js_truthy(value) else ""
    except (IndexError, ValueError, AttributeError, TypeError, RecursionError):
        return ""


def detect_codex():
    """The port of codexDetectPlan and codexRender's mapping: chatgpt_plan_type from
    the JWT in <CODEX_HOME>/auth.json, then ~/.codex/auth.json."""
    home = os.environ.get("HOME") or os.path.expanduser("~")
    raw, first = "", None
    for path in (os.path.join(rr_runtime.runtime_home("codex"), "auth.json"), os.path.join(home, ".codex", "auth.json")):
        data = read_json_object(path)
        if data is None:
            continue
        first = data if first is None else first
        tokens = data.get("tokens") or {}
        tokens = tokens if isinstance(tokens, dict) else {}
        for key in ("id_token", "access_token"):
            value = tokens.get(key)
            found = jwt_plan_type(js_str(value) if js_truthy(value) else "")
            if js_truthy(found):
                raw = js_str(found).lower()
                break
        if raw:
            break
    plan, why = None, ""
    if raw in ("plus", "pro"):
        plan, why = raw, "chatgpt_plan_type"
    elif re.search(r"^(team|business|enterprise|edu)", raw):
        plan, why = "pro", "chatgpt_plan_type %s, uses the pro profile" % raw
    first = first or {}
    mode = first.get("auth_mode")
    api = (bool(first.get("OPENAI_API_KEY")) and not first.get("tokens")) or \
        (mode is not None and mode != "chatgpt")
    fields = {"chatgpt_plan_type": raw, "auth_mode": js_str(mode), "api": api}
    return {"plan": plan, "from": why or None, "raw": raw}, api, fields


# Pairs whose profiles differ only in profile.json (R36.17), so `profile set` fixes a
# drift; any other pair needs the installer. Codex plus and pro differ in tiers, session
# and agents, so every Codex change is the installer's.
SAME_TIER = {"claude": ({"max", "max20"}, {"pro", "team-pro"}, {"max", "team-max"}), "codex": ()}


def context_mode(prof):
    """The record's --context: "economy" or None (default, or a record from before it)."""
    context = (prof or {}).get("context")
    return "economy" if isinstance(context, dict) and context.get("mode") == "economy" else None


def installer_command(runtime, plan, version, context=None):
    return "npx riskrails%s --target %s %s %s%s --yes" % (
        "@%s" % version if version else "", runtime, "--plan" if runtime == "claude" else "--codex-plan", plan,
        " --context %s" % context if context else "")


def profile_detect(runtime, rt=rr_runtime.Runtime()):
    live, api, fields = detect_claude() if runtime == "claude" else detect_codex()
    live["fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()
    prof = read_profile(runtime, rt=rt)
    installed = {k: prof.get(k) for k in ("plan", "profile", "plugin_version")} if prof else None
    have = (installed or {}).get("plan")
    render = command = ack = None
    if api:
        status = "unsupported"
    elif not live["plan"]:
        status = "unknown"
    elif not installed:
        status = "no_profile"
    elif have == live["plan"] or (runtime == "claude" and have == "balanced-max" and live["plan"] in ("max", "max20")):
        status = "same"
    elif acknowledged(runtime, live["fingerprint"], have):
        status = "acknowledged"           # the human kept this very plan for this very account (R36.18)
    else:
        status = "drift"
        if any({have, live["plan"]} <= pair for pair in SAME_TIER[runtime]):
            render = "profile"
            command = "python3 %s profile set %s --runtime %s" % (
                shlex.quote(fs.ENTRY), live["plan"], runtime)
        else:
            render = "installer"
            command = installer_command(runtime, live["plan"], installed.get("plugin_version"),
                                        context_mode(prof))
        ack = "python3 %s profile ack --runtime %s" % (shlex.quote(fs.ENTRY), runtime)
    return {"runtime": runtime, "status": status, "installed": installed, "live": live,
            "render": render, "command": command, "ack": ack, "decision": None}


def acknowledged(runtime, fingerprint, installed_plan):
    """True when drift-ack.json holds this fingerprint AND the plan kept is the installed one."""
    entry = read_drift_ack(runtime).get(runtime)
    return isinstance(entry, dict) and entry.get("fingerprint") == fingerprint and \
        entry.get("kept") == installed_plan


def drift_ack_path(runtime):
    return os.path.join(rr_runtime.runtime_home(runtime), "riskrails", "drift-ack.json")


def read_drift_ack(runtime):
    """<home>/riskrails/drift-ack.json, or {}: per user, never per project (D2)."""
    return read_json_object(drift_ack_path(runtime)) or {}


def write_drift_ack(runtime, fingerprint, kept, via):
    """"Keep" on a plan_drift decision: the fingerprint, the plan kept and when. Plan
    fields hashed, never an email, an id or a token (R36.16). Atomic."""
    data = read_drift_ack(runtime)
    data = {"version": 1, "claude": data.get("claude"), "codex": data.get("codex")}
    data[runtime] = {"fingerprint": fingerprint, "kept": kept, "at": fs.now(), "via": via}
    path = drift_ack_path(runtime)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def open_drift(root, found, rt=rr_runtime.Runtime()):
    """`profile detect --open` (R36.18): on drift, with the dialog on, the plan_drift
    decision — option 1 keeps the installed plan (and writes drift-ack.json when
    settled), option 2 is the `command` detect prints. The id of the decision, an
    open one for the same fingerprint included; None when nothing was opened."""
    runtime = found["runtime"]
    if not root or runtime != rr_runtime.own_runtime(runtime=rt.name):
        return None
    fingerprint = found["live"]["fingerprint"]
    on = dialog.dialog_on(root, runtime=rt.name) if found["status"] == "drift" else None
    session = (on or {}).get("session")
    reuse = None
    for decision in ledger.read_decisions(root)["open"]:
        drift = decision.get("drift") or {}
        if decision.get("kind") != "plan_drift" or drift.get("runtime") != runtime:
            continue
        if on and reuse is None and drift.get("fingerprint") == fingerprint and \
                decision.get("session") == session:
            reuse = decision["id"]
        else:
            # resolved, acknowledged elsewhere, another account or another session's: stale
            dialog.settle_decision(root, decision["id"], "fallback")
    if not on:
        return None
    if reuse:
        return reuse
    kept = found["installed"]["plan"]
    live = found["live"]
    question = "This %s account is %s (%s); RiskRails is installed for %s.\nKeep %s, or run the command below?" % (
        runtime, live["plan"], live["from"] or "no detail", kept, kept)
    state = task.load(root, required=False, claim=False, rt=rt)
    state = state if state and task.is_v7(state) else None
    options = [{"kind": "choice", "effect": "ack", "label": "Keep %s — do not ask again for this account" % kept},
               {"kind": "command", "label": found["command"]}]
    decision, why = dialog.open_decision(root, state, "plan_drift", "Plan drift", question, options, "profile detect",
                                  drift={"runtime": runtime, "fingerprint": fingerprint, "kept": kept}, rt=rt)
    if decision is None:
        print("state.py: no dialog — %s" % why, file=sys.stderr)
        return None
    return decision["id"]


# plan -> (profile, label), as bin/riskrails.js maps --plan and --codex-plan; the
# installer and `profile set` must resolve a plan to the same profile.json.
PLAN_PROFILES = {
    "claude": {"pro": ("pro", "Pro"), "team-pro": ("pro", "Team Pro"), "team-max": ("max", "Team Max"),
               "max": ("max", "Max"), "max20": ("max20", "Max 20x"), "balanced-max": ("balanced-max", "BalancedMax")},
    "codex": {"plus": ("codex-plus", "Plus"), "pro": ("codex-pro", "Pro"),
              "balanced-max": ("codex-balanced-max", "BalancedMax")},
}


def load_resolver(runtime):
    """The installed scripts/resolve-profile.py beside its profiles/ (the installer copies
    both to <home>/riskrails/), else the plugin's, else this checkout's; None when none."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(fs.ENTRY)))
    for base in (os.path.join(rr_runtime.runtime_home(runtime), "riskrails"), os.environ.get("CLAUDE_PLUGIN_ROOT"), here):
        path = os.path.join(base, "scripts", "resolve-profile.py") if base else ""
        if path and os.path.isfile(path) and os.path.isdir(os.path.join(base, "profiles")):
            spec = importlib.util.spec_from_file_location("resolve_profile", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, base
    return None, None


DIRECT_MODE_CAP = "T4"
