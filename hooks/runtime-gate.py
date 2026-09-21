#!/usr/bin/env python3
"""Runtime gate: one hook for both runtimes, replacing fable-gate.py and
codex-model-gate.py (which remain as shims that exec this file).

The most capable model of a plan can stop serving an account — a rate limit, a
used-up usage limit, a model the account cannot reach — and the runtime's own
fallback does not cover those: the agent ends with an error and the next launch
hits the same wall. The gate records the outage and, while the record lives,
sends launches of that model to the next tier down.

Claude Code (model: fable -> opus):
  StopFailure (rate_limit|model_not_found)  records that Fable is unavailable
  PostToolUse:Agent                         records a Fable agent that fell back (overload), briefly
  PreToolUse:Agent                          while a record is live, rewrites model fable -> opus
  statusline [--then <command>]             records it when the weekly limit is nearly used, then
                                            runs the user's own statusline command on the same input

Codex (EXPERT model -> STRONG model):
  SubagentStop (rate limit / model unavailable)  records that EXPERT is unusable
  PostToolUse:Agent (same signals in the result) records it too
  PreToolUse:Agent   while a record is live, rewrites an EXPERT launch to STRONG
                     (MODE=context: explains the outage without rewriting)

Budgets (from <home>/claude-agentic/profile.json; no profile, no budget):
  PreToolUse:Agent   an EXPERT launch without `expert.without_asking`, or past
                     `expert.max_per_task` for the task in flight, and a launch past
                     `fan_out.max_parallel_agents` (or past `max_parallel_on_strong`
                     for a STRONG/EXPERT agent) asks on Claude Code; Codex cannot
                     ask, so there — and under AI_UNATTENDED=1 or `claude -p`
                     (CLAUDE_CODE_SESSION_ATTENDED=0) — it allows and explains.
                     A launch that goes ahead counts at once, so one message
                     launching several agents meets the fan-out too
  SubagentStart / SubagentStop   keep the per-session count of running agents;
                     a start claims its launch; an entry older than AGENT_TTL
                     (1800 s), or a launch unclaimed for 60 s, no longer counts
A rewrite made while a task is in flight is journaled as `model_fallback`
through that project's state.py.

A record expires on its own. The gate never denies, always exits 0, and any
error inside it fails open: the call goes through unchanged.

  runtime-gate.py status | quota [--json] | clear | set <seconds> [reason]
                  | statusline [--then <cmd>]

Quota (advice only, it never refuses anything): Claude Code's comes from the
statusline payload, Codex's from the newest rollout's token_count event. Both
are stored in the state file; `quota --json` prints
{runtime, weekly_pct, five_hour_pct, resets_at, seen_at, source, stale}.

The runtime is the home the hook runs from (~/.codex/hooks -> Codex, anything
else -> Claude Code); the shims name theirs. State lives in
<home>/state/runtime-gate.json; a state file of the old gate is imported once.

Environment, new name before the old one of that runtime before the default:
AI_RUNTIME_GATE=off (CLAUDE_FABLE_GATE, CODEX_MODEL_GATE) disables every check;
AI_RUNTIME_GATE_STATE, _TTL, _NOT_FOUND_TTL, _OVERLOAD_TTL, _LAUNCH_WINDOW,
_WEEKLY_PCT, _FALLBACK, _EXPERT, _FALLBACK_EFFORT, _MODE, _AGENT_TTL tune it.
"""
import contextlib
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import fcntl
except ImportError:                             # not POSIX: no lock, as before
    fcntl = None

LEGACY = {"claude": ("fable-gate", "CLAUDE_FABLE_GATE"), "codex": ("codex-model-gate", "CODEX_MODEL_GATE")}

# Set by configure(); module-level so the shims (and the old suites through
# them) can read STATE and call mark() exactly as before.
RUNTIME = "claude"
HOME = STATE = LEGACY_STATE = QUOTA_STATE = ""
LIMIT_TTL = NOT_FOUND_TTL = OVERLOAD_TTL = LAUNCH_WINDOW = 0
WEEKLY_PCT = 0.0
EXPERT = FALLBACK = FALLBACK_EFFORT = MODE = ""
AGENT_TTL = 1800
RESPONSE = {}
TTL_BY_ERROR = {}


def setting(name, default, runtime=None, fits=None):
    """AI_RUNTIME_GATE_<RUNTIME>_<name>, AI_RUNTIME_GATE_<name>, then the
    runtime's old name, then the default. The shared name is read by both
    runtimes, so `fits` drops a value that belongs to the other one (a Codex
    model exported for Codex must not become a Claude Agent model)."""
    runtime = runtime or RUNTIME
    old = LEGACY[runtime][1]
    for key in (f"AI_RUNTIME_GATE_{runtime.upper()}_{name}", f"AI_RUNTIME_GATE_{name}", f"{old}_{name}"):
        value = os.environ.get(key)
        if value in (None, ""):
            continue
        if fits and key == f"AI_RUNTIME_GATE_{name}" and not fits(value):
            continue
        return value
    return default


def number_setting(name, default, kind=int):
    """A numeric setting; a value that does not parse keeps the default, so a
    typo such as AGENT_TTL=30m cannot crash the gate (or the statusline it wraps)."""
    try:
        return kind(setting(name, str(default)))
    except ValueError:
        return kind(default)


CLAUDE_MODEL = re.compile(r"^(fable|opus|sonnet|haiku|claude-)", re.I)


def claude_model(value):
    return bool(CLAUDE_MODEL.match(value))


def codex_model(value):
    return not claude_model(value)


def profile_tier(home, tier, field, default):
    """A field of the installed plan's tier table, else the default."""
    try:
        with open(os.path.join(home, "claude-agentic", "profile.json"), encoding="utf-8") as fh:
            value = json.load(fh)["tiers"][tier][field]
        return value if isinstance(value, str) and value else default
    except (OSError, ValueError, KeyError, TypeError):
        return default


def profile_fable(home):
    """profile.json's `fable`; True when there is no profile (an install from
    before WP5 wrapped the statusline only on a Fable install)."""
    try:
        with open(os.path.join(home, "claude-agentic", "profile.json"), encoding="utf-8") as fh:
            return bool(json.load(fh).get("fable", True))
    except (OSError, ValueError, AttributeError):
        return True


def configure(runtime):
    """Bind every setting for one runtime."""
    # pylint: disable=global-statement
    global RUNTIME, HOME, STATE, LEGACY_STATE, QUOTA_STATE, LIMIT_TTL, NOT_FOUND_TTL, OVERLOAD_TTL
    global LAUNCH_WINDOW, WEEKLY_PCT, EXPERT, FALLBACK, FALLBACK_EFFORT, MODE, TTL_BY_ERROR, AGENT_TTL
    RUNTIME = runtime
    if runtime == "codex":
        HOME = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    else:
        HOME = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    STATE = setting("STATE", "") or os.path.join(HOME, "state", "runtime-gate.json")
    # The quota ledger belongs in runtime-gate.json. A state file named by the
    # old variable only ever held the outage record, so the ledger does not
    # move into it: it stays at the default path beside it.
    QUOTA_STATE = STATE if os.environ.get("AI_RUNTIME_GATE_STATE") or \
        os.environ.get(f"AI_RUNTIME_GATE_{runtime.upper()}_STATE") or \
        not os.environ.get(f"{LEGACY[runtime][1]}_STATE") else os.path.join(HOME, "state", "runtime-gate.json")
    LEGACY_STATE = os.path.join(HOME, "state", LEGACY[runtime][0] + ".json")
    LIMIT_TTL = number_setting("TTL", 3600)
    NOT_FOUND_TTL = number_setting("NOT_FOUND_TTL", 21600)
    OVERLOAD_TTL = number_setting("OVERLOAD_TTL", 900)
    LAUNCH_WINDOW = number_setting("LAUNCH_WINDOW", 300)
    WEEKLY_PCT = number_setting("WEEKLY_PCT", 90, float)
    MODE = setting("MODE", "rewrite")
    AGENT_TTL = number_setting("AGENT_TTL", 1800)
    if runtime == "codex":
        EXPERT = setting("EXPERT", profile_tier(HOME, "EXPERT", "model", "gpt-6-astra"), fits=codex_model)
        FALLBACK = setting("FALLBACK", profile_tier(HOME, "STRONG", "model", "gpt-5.6-sol"), fits=codex_model)
        FALLBACK_EFFORT = setting("FALLBACK_EFFORT", profile_tier(HOME, "STRONG", "effort", "high"))
    else:
        EXPERT = setting("EXPERT", "fable", fits=claude_model)
        FALLBACK = setting("FALLBACK", "opus", fits=claude_model)
        FALLBACK_EFFORT = setting("FALLBACK_EFFORT", "")
    # StopFailure categories that mean "Fable cannot serve this account right now".
    # Authentication, billing and account errors are account-wide: Opus would fail too.
    TTL_BY_ERROR = {"rate_limit": LIMIT_TTL, "model_not_found": NOT_FOUND_TTL}


def detect_runtime():
    here = os.path.realpath(os.path.abspath(__file__))
    codex_home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    if here.startswith(os.path.realpath(codex_home) + os.sep) or f"{os.sep}.codex{os.sep}" in here:
        return "codex"
    return "claude"


# ------------------------------------------------------------------ state
def load(path=None):
    try:
        with open(path or STATE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except OSError:
        return import_legacy() if path in (None, STATE) else {}
    except ValueError:
        return {}


def import_legacy():
    """First run after the rename: carry a live outage record over from the old
    gate's own state file, once. Only for the default location — a state file
    named through the environment is the caller's."""
    if STATE != os.path.join(HOME, "state", "runtime-gate.json"):
        return {}
    try:
        with open(LEGACY_STATE, encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        return {}
    data = {"imported_from": os.path.basename(LEGACY_STATE)}
    if isinstance(old, dict) and isinstance(old.get("unavailable"), dict):
        data["unavailable"] = old["unavailable"]
    try:
        save(data)
    except OSError:
        pass
    return data


def save(data, path=None):
    path = path or STATE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


@contextlib.contextmanager
def locked(path=None):
    """Hold an exclusive lock on <state>.lock for one load -> change -> save.
    save() alone is atomic, but parallel hooks (a fan-out's SubagentStart and
    SubagentStop next to a StopFailure) each loaded the old file and the last
    save won, dropping the others' writes. Not re-entrant: never nest it.
    Fails open: without a lock file the write goes ahead unlocked."""
    path = path or STATE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fh = open(f"{path}.lock", "a", encoding="utf-8")  # pylint: disable=consider-using-with
    except OSError:
        yield
        return
    try:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_EX)
        yield
    finally:
        fh.close()                              # closing releases the lock


def active(now=None):
    """The live unavailability record, or None."""
    rec = load().get("unavailable")
    now = time.time() if now is None else now
    if isinstance(rec, dict) and float(rec.get("until", 0)) > now:
        return rec
    return None


def mark(until, reason, source):
    until = math.ceil(until)                     # round up: truncating would end the record up to a second early
    with locked():
        data = load()
        rec = data.get("unavailable")
        if isinstance(rec, dict) and float(rec.get("until", 0)) >= until:
            return                              # a longer record already stands
        data["unavailable"] = {"until": until, "reason": reason, "source": source,
                               "set_at": int(time.time())}
        save(data)


def note_launch():
    with locked():
        data = load()                           # remembered for failure attribution
        data["last_expert_launch"] = int(time.time())
        save(data)


def last_launch():
    data = load()
    return max(float(data.get("last_expert_launch") or 0), float(data.get("last_fable_launch") or 0))


def hhmm(epoch):
    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def transcript_tail(path):
    """The last megabyte of a transcript as lines, newest last; [] when unreadable."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 1_000_000))
            return fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return []


# ================================================================== Claude Code
# Until this Claude Code version CLAUDE_CODE_SUBAGENT_MODEL overrode the call's own
# `model` and the frontmatter; since it, the variable is only the fallback after them.
ENV_FIRST_BEFORE = (2, 1, 251)


def is_fable(model):
    return isinstance(model, str) and "fable" in model.lower()


def frontmatter_model(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read(8192)
    except OSError:
        return None
    if not text.startswith("---"):
        return ""
    head = text.split("\n---", 1)[0]
    m = re.search(r"(?m)^model:\s*([^\s#]+)", head)
    return m.group(1) if m else ""


def claude_code_version(path):
    """The Claude Code version that wrote the transcript, as a tuple, or None.
    Hooks get no version field and no documented version variable; every
    transcript record carries the `version` of the Claude Code that wrote it."""
    for line in reversed(transcript_tail(path)):
        if '"version"' not in line:
            continue
        try:
            version = json.loads(line).get("version")
        except (ValueError, AttributeError):
            continue
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", version) if isinstance(version, str) else None
        if m:
            return tuple(int(part) for part in m.groups())
    return None


def definition_model(tool_input, cwd):
    """The `model:` of the agent's definition, project before user; "" when it
    has none or inherits."""
    name = tool_input.get("subagent_type") or "general-purpose"
    if re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        dirs = [os.environ.get("CLAUDE_PROJECT_DIR", ""), cwd]
        candidates = [os.path.join(d, ".claude", "agents", f"{name}.md") for d in dirs if d]
        candidates.append(os.path.join(HOME, "agents", f"{name}.md"))
        for path in candidates:
            model = frontmatter_model(path)
            if model is None:
                continue                        # no definition here, look further
            if model and model != "inherit":
                return model
            break
    return ""


def agent_model(tool_input, payload, guess=True):
    """The model an Agent call will run on, in Claude Code's order: the call's
    own `model`, then the definition's frontmatter (project before user), then
    CLAUDE_CODE_SUBAGENT_MODEL. Before Claude Code 2.1.251 the variable came
    first and overrode both; the version is read from the payload's transcript,
    and only when the variable and the rest disagree about Fable.

    With no readable version, rerouting guesses the current order: the old
    order would let a pinned Fable agent launch while Fable is unavailable and
    turn a Sonnet call into an Opus one, while a wrong guess of the current one
    costs nothing - an old Claude Code lets the variable override the rewritten
    `model` just as it overrode the original. Recording does not guess
    (`guess=False` answers ""): blaming Fable for an agent the variable sent
    elsewhere would close the gate on a healthy Fable."""
    env = os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL", "")
    own = tool_input.get("model") or definition_model(tool_input, payload.get("cwd") or "")
    if not env or not own:
        return env or own
    if is_fable(env) != is_fable(own):
        version = claude_code_version(payload.get("transcript_path"))
        if version is None and not guess:
            return ""
        if version is not None and version < ENV_FIRST_BEFORE:
            return env
    return own


def claude_pre_tool_use(payload):
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") != "Agent" or not isinstance(tool_input, dict):
        return
    if tool_input.get("subagent_type") == "fork":   # forks ignore `model`
        return
    if not is_fable(agent_model(tool_input, payload)):
        return

    rec = active()
    if rec is None:
        note_launch()
        return

    name = tool_input.get("subagent_type") or "general-purpose"
    why = f"Fable is unavailable ({rec.get('reason', 'unknown')}) until {hhmm(float(rec['until']))}"
    journal_fallback(payload, name, agent_model(tool_input, payload), FALLBACK, rec)
    respond({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"fable-gate: {why}; {name} runs on {FALLBACK}",
            "updatedInput": {**tool_input, "model": FALLBACK},
            "additionalContext": (
                f"fable-gate routed this {name} agent to {FALLBACK}: {why}. "
                f"Its answer is {FALLBACK}'s, not Fable's. "
                "`~/.claude/hooks/runtime-gate.py clear` re-enables Fable early."
            ),
        }
    })


def claude_post_tool_use(payload):
    tool_input = payload.get("tool_input")
    response = payload.get("tool_response")
    if payload.get("tool_name") != "Agent" or not isinstance(tool_input, dict) \
            or not isinstance(response, dict):
        return
    if not is_fable(agent_model(tool_input, payload, guess=False)):
        return
    resolved = response.get("resolvedModel") or ""
    used = [m for m in (response.get("modelsUsed") or []) if isinstance(m, str)]
    if (resolved and not is_fable(resolved)) or any(not is_fable(m) for m in used):
        mark(time.time() + OVERLOAD_TTL, "fell back from Fable", "PostToolUse")


def last_transcript_model(path):
    for line in reversed(transcript_tail(path)):
        try:
            model = (json.loads(line).get("message") or {}).get("model")
        except (ValueError, AttributeError):
            continue
        if isinstance(model, str) and model and not model.startswith("<"):
            return model
    return ""


def claude_stop_failure(payload):
    error = payload.get("error")
    if error not in TTL_BY_ERROR:
        return
    text = " ".join(str(payload.get(k) or "") for k in ("error_details", "last_assistant_message"))
    agent_type = payload.get("agent_type")
    fable_involved = (
        "fable" in text.lower()
        or is_fable(payload.get("model"))
        or (isinstance(agent_type, str)
            and is_fable(agent_model({"subagent_type": agent_type}, payload, guess=False)))
        or is_fable(last_transcript_model(payload.get("agent_transcript_path")
                                          or payload.get("transcript_path")))
        or time.time() - last_launch() <= LAUNCH_WINDOW
    )
    if fable_involved:
        mark(time.time() + TTL_BY_ERROR[error], error, "StopFailure")


def reset_epoch(value):
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        epoch = float(value)
        return epoch / 1000 if epoch > 1e12 else epoch
    if isinstance(value, str) and value:
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def statusline(payload):
    limits = payload.get("rate_limits") or {}
    week = limits.get("seven_day") or {}
    five = limits.get("five_hour") or {}
    pct = week.get("used_percentage")
    record_quota(pct, five.get("used_percentage"), reset_epoch(week.get("resets_at")), "statusline")
    if pct is None or float(pct) < WEEKLY_PCT or not profile_fable(HOME):
        return
    until = reset_epoch(week.get("resets_at"))
    if not until or until <= time.time():
        until = time.time() + LIMIT_TTL
    mark(until, f"weekly limit {float(pct):.0f}% used", "statusline")


# ================================================================== quota
QUOTA_STALE = 24 * 3600
ROLLOUT_EVERY = 60
ROLLOUT_TAIL = 64 * 1024


def number(value):
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def record_quota(weekly, five_hour, resets_at, source, seen_at=None):
    """Store what the runtime last said about the account's limits. A write
    happens only when a number moved or the record is a minute old, so a
    statusline that redraws every second does not rewrite the file each time."""
    weekly, five_hour = number(weekly), number(five_hour)
    if weekly is None and five_hour is None:
        return
    now = time.time()
    new = {"weekly_pct": weekly, "five_hour_pct": five_hour, "resets_at": int(resets_at or 0),
           "seen_at": int(seen_at or now), "source": source}
    old = load(QUOTA_STATE).get("quota")
    old = old if isinstance(old, dict) else {}
    same = all(old.get(k) == new[k] for k in ("weekly_pct", "five_hour_pct", "resets_at", "source"))
    if same and now - float(old.get("seen_at") or 0) < ROLLOUT_EVERY:
        return                                  # checked unlocked: a redraw that changes nothing takes no lock
    with locked(QUOTA_STATE):
        data = load(QUOTA_STATE)
        data["quota"] = new
        save(data, QUOTA_STATE)


def newest_rollout():
    """The newest rollout-*.jsonl in the three newest day directories."""
    root = os.path.join(HOME, "sessions")
    days = []
    for year in sorted(os.listdir(root), reverse=True) if os.path.isdir(root) else []:
        for month in sorted(os.listdir(os.path.join(root, year)), reverse=True):
            for day in sorted(os.listdir(os.path.join(root, year, month)), reverse=True):
                days.append(os.path.join(root, year, month, day))
                if len(days) == 3:
                    break
            if len(days) == 3:
                break
        if len(days) == 3:
            break
    files = [os.path.join(d, f) for d in days if os.path.isdir(d)
             for f in os.listdir(d) if f.startswith("rollout-") and f.endswith(".jsonl")]
    return max(files, key=os.path.getmtime) if files else None


def rollout_limits(path):
    """(weekly_pct, five_hour_pct, weekly resets_at, seen_at) from the last
    token_count event in the last 64 KB of a rollout, or None."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - ROLLOUT_TAIL))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if '"token_count"' not in line or '"rate_limits"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        limits = (event.get("payload") or {}).get("rate_limits") or {}
        weekly = five = None
        resets = 0
        for window in (limits.get("primary"), limits.get("secondary")):
            if not isinstance(window, dict):
                continue
            minutes = number(window.get("window_minutes")) or 0
            if minutes >= 7 * 24 * 60:
                weekly, resets = window.get("used_percent"), window.get("resets_at") or 0
            elif minutes:
                five = window.get("used_percent")
        if weekly is None and five is None:
            continue
        seen = reset_epoch(event.get("timestamp")) or os.path.getmtime(path)
        return weekly, five, reset_epoch(resets) or 0, seen
    return None


def refresh_codex_quota():
    """Read the newest rollout, at most once a minute."""
    with locked(QUOTA_STATE):
        data = load(QUOTA_STATE)
        if time.time() - float(data.get("quota_checked_at") or 0) < ROLLOUT_EVERY:
            return
        data["quota_checked_at"] = int(time.time())
        save(data, QUOTA_STATE)
    path = newest_rollout()
    found = rollout_limits(path) if path else None
    if found:
        record_quota(found[0], found[1], found[2], "rollout", seen_at=found[3])


def quota():
    if RUNTIME == "codex":
        refresh_codex_quota()
    q = load(QUOTA_STATE).get("quota")
    q = q if isinstance(q, dict) else {}
    now = time.time()
    seen = float(q.get("seen_at") or 0)
    resets = float(q.get("resets_at") or 0)
    return {
        "runtime": RUNTIME,
        "weekly_pct": q.get("weekly_pct"),
        "five_hour_pct": q.get("five_hour_pct"),
        "resets_at": int(resets),
        "seen_at": int(seen),
        "source": q.get("source"),
        "stale": not seen or now - seen > QUOTA_STALE or (resets and now > resets),
    }


# ================================================================== Codex
# Explicit capacity and availability signals only. Each one names a condition
# under which the model could not run at all; none of them describes an answer
# the model gave. `error`/`failed` alone is not enough on purpose.
SIGNALS = (
    (re.compile(r"rate[ _-]?limit|429\b|too many requests|usage limit reached|"
                r"quota (?:exceeded|exhausted)|insufficient_quota", re.I), "rate_limit", "TTL"),
    (re.compile(r"model[ _-]?not[ _-]?found|unknown model|unsupported model|"
                r"model_unavailable|model is (?:currently )?unavailable|"
                r"does not have access to (?:the )?model|no access to model", re.I),
     "model_unavailable", "NOT_FOUND_TTL"),
    (re.compile(r"\b(?:overloaded|capacity (?:exceeded|unavailable)|service unavailable|503)\b", re.I),
     "overloaded", "TTL"),
)

AGENT_TOOLS = {"agent", "spawn_agent", "task"}
AGENT_NAME_KEYS = ("agent_type", "subagent_type", "agent", "agent_name", "name", "type")


def is_expert(model):
    return isinstance(model, str) and EXPERT.lower() in model.lower()


def agent_file_model(name):
    """The `model` pinned by a custom agent file, or None when there is none.
    Project agents win over personal ones, the way Codex layers config."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""):
        return None
    roots = [os.path.join(os.getcwd(), ".codex", "agents"), os.path.join(HOME, "agents")]
    for root in roots:
        path = os.path.join(root, f"{name}.toml")
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read(16384)
        except OSError:
            continue
        match = re.search(r"(?m)^\s*model\s*=\s*[\"']([^\"']+)[\"']", text)
        if match:
            return match.group(1)
    return None


def config_default_model():
    try:
        with open(os.path.join(HOME, "config.toml"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    match = re.search(r"(?m)^\s*default_subagent_model\s*=\s*[\"']([^\"']+)[\"']", text)
    return match.group(1) if match else ""


def agent_name(tool_input):
    for key in AGENT_NAME_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def launch_model(tool_input):
    """The model an Agent spawn will use: its own `model`, else the named custom
    agent's pinned model, else the configured subagent default."""
    if isinstance(tool_input.get("model"), str) and tool_input["model"]:
        return tool_input["model"]
    return agent_file_model(agent_name(tool_input)) or config_default_model()


def is_agent_event(payload):
    return (payload.get("tool_name") or "").lower() in AGENT_TOOLS


def classify(text):
    """(reason, ttl) for an explicit availability failure, or None."""
    if not text:
        return None
    for pattern, reason, ttl in SIGNALS:
        if pattern.search(text):
            return reason, (NOT_FOUND_TTL if ttl == "NOT_FOUND_TTL" else LIMIT_TTL)
    return None


def texts(*values):
    out = []
    for value in values:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, (dict, list)):
            try:
                out.append(json.dumps(value))
            except (TypeError, ValueError):
                pass
    return " ".join(out)


def codex_pre_tool_use(payload):
    tool_input = payload.get("tool_input")
    if not is_agent_event(payload) or not isinstance(tool_input, dict):
        return
    try:
        refresh_codex_quota()
    except (OSError, ValueError):
        pass
    if not is_expert(launch_model(tool_input)):
        return

    rec = active()
    if rec is None:
        note_launch()
        return

    name = agent_name(tool_input) or "the expert agent"
    why = f"{EXPERT} is unavailable ({rec.get('reason', 'unknown')}) until {hhmm(float(rec['until']))}"
    context = (
        f"codex-model-gate: {why}. {name} runs on {FALLBACK} instead, so its answer is "
        f"{FALLBACK}'s, not {EXPERT}'s. Say so when you report it. "
        "`runtime-gate.py clear` re-enables the expert model early."
    )
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if MODE == "rewrite":
        journal_fallback(payload, name, launch_model(tool_input), FALLBACK, rec)
        out["hookSpecificOutput"]["permissionDecision"] = "allow"
        out["hookSpecificOutput"]["updatedInput"] = {
            **tool_input, "model": FALLBACK, "model_reasoning_effort": FALLBACK_EFFORT,
        }
    out["hookSpecificOutput"]["additionalContext"] = context
    respond(out)


def codex_post_tool_use(payload):
    tool_input = payload.get("tool_input")
    if not is_agent_event(payload) or not isinstance(tool_input, dict):
        return
    if not is_expert(launch_model(tool_input)):
        return
    hit = classify(texts(payload.get("tool_response")))
    if hit:
        mark(time.time() + hit[1], hit[0], "PostToolUse")


def codex_subagent_stop(payload):
    text = texts(payload.get("last_assistant_message"), payload.get("error"),
                 payload.get("error_details"), payload.get("stopReason"))
    hit = classify(text)
    if not hit:
        return
    # Attribute the failure before acting on it: a rate limit reported by a Terra
    # agent says nothing about the expert model.
    agent_type = payload.get("agent_type")
    involved = (
        EXPERT.lower() in text.lower()
        or is_expert(payload.get("model"))
        or is_expert(agent_file_model(agent_type) or "")
        or time.time() - last_launch() <= LAUNCH_WINDOW
    )
    if involved:
        mark(time.time() + hit[1], hit[0], "SubagentStop")


# ================================================================== budgets
TIERS = ("EXPERT", "STRONG", "BALANCED", "FAST")


def respond(out):
    """Merge one handler's hookSpecificOutput into the single answer main()
    prints: `ask` outranks `allow`, reasons and context accumulate."""
    new = out.get("hookSpecificOutput") or {}
    cur = RESPONSE.setdefault("hookSpecificOutput", {"hookEventName": new.get("hookEventName", "PreToolUse")})
    decision = new.get("permissionDecision")
    if decision and (cur.get("permissionDecision") != "ask"):
        cur["permissionDecision"] = decision
    for key, sep in (("permissionDecisionReason", "; "), ("additionalContext", " ")):
        if new.get(key):
            cur[key] = f"{cur[key]}{sep}{new[key]}" if cur.get(key) else new[key]
    if "updatedInput" in new:
        cur["updatedInput"] = new["updatedInput"]


def profile():
    try:
        with open(os.path.join(HOME, "claude-agentic", "profile.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def model_tier(model, tiers):
    """The tier a model belongs to on this runtime, or None."""
    if not isinstance(model, str) or not model:
        return None
    if RUNTIME == "claude":
        low = model.lower()
        for word, tier in (("fable", "EXPERT"), ("opus", "STRONG"), ("sonnet", "BALANCED"), ("haiku", "FAST")):
            if word in low:
                return tier
        return None
    for tier in TIERS:
        if (tiers.get(tier) or {}).get("model") == model:
            return tier
    return None


def launch_tier(tool_input, payload, tiers):
    """An explicit model on the call wins; then the agent's name in the tier
    lists; then the model its definition pins."""
    own = tool_input.get("model")
    if own:
        return model_tier(own, tiers)
    name = (tool_input.get("subagent_type") if RUNTIME == "claude" else agent_name(tool_input)) or ""
    for tier in TIERS:
        if name in ((tiers.get(tier) or {}).get("agents") or []):
            return tier
    pinned = agent_model(tool_input, payload) if RUNTIME == "claude" else launch_model(tool_input)
    return model_tier(pinned, tiers)


def project_task(cwd):
    """(project root, task id) of the task in flight at or above cwd, or (None, None)."""
    here = os.path.abspath(cwd) if isinstance(cwd, str) and cwd else None
    while here:
        path = os.path.join(here, ".ai", "state", "current.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    task = json.load(fh).get("task_id")
            except (OSError, ValueError, AttributeError):
                return None, None
            return (here, task) if task else (None, None)
        parent = os.path.dirname(here)
        here = None if parent == here else parent
    return None, None


def state_script():
    for path in (os.path.join(HOME, "skills", "ai-task", "state.py"),
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "skills", "ai-task", "state.py")):
        if os.path.isfile(path):
            return path
    return None


FALLBACK_REASONS = (("weekly", "weekly_limit"), ("fell back", "overloaded"), ("overload", "overloaded"),
                    ("not_found", "model_not_found"), ("unavailable", "model_not_found"),
                    ("rate", "rate_limit"))


def journal_fallback(payload, agent, from_model, to_model, rec):
    """One model_fallback line in the task's journal (WP2 vocabulary, actor
    hook). No task, no line; any failure is swallowed."""
    try:
        root, _task = project_task(payload.get("cwd"))
        script = state_script()
        if not root or not script:
            return
        raw = str(rec.get("reason") or "")
        reason = next((r for key, r in FALLBACK_REASONS if key in raw.lower()), raw or "rate_limit")
        data = {"agent": agent, "from": from_model or EXPERT, "to": to_model, "reason": reason}
        subprocess.run([sys.executable, script, "--root", root, "event", "model_fallback",
                        "--data", json.dumps(data)],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=3, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass


def running(data, session, now):
    """Live entries of one session, expired ones dropped."""
    agents = (data.get("running_agents") or {}).get(session) or []
    return [a for a in agents if isinstance(a, dict) and now - float(a.get("started_at") or 0) < AGENT_TTL]


PENDING_TTL = 60


def pending(data, session, now):
    """Launches PreToolUse let through that no SubagentStart has claimed yet.
    One message that launches five agents runs five PreToolUse hooks before
    the first SubagentStart, so without these each saw the same empty count.
    A launch the user declined leaves one behind for at most PENDING_TTL."""
    entries = (data.get("pending_launches") or {}).get(session) or []
    return [p for p in entries if isinstance(p, dict) and now - float(p.get("at") or 0) < PENDING_TTL]


def put_session(data, key, session, entries):
    table = data.get(key) if isinstance(data.get(key), dict) else {}
    table[session] = entries
    data[key] = {k: v for k, v in table.items() if v}


def subagent_start(payload):
    tiers = profile().get("tiers") or {}
    name = payload.get("agent_type") or payload.get("subagent_type") or ""
    tier = launch_tier({"subagent_type": name, "agent_type": name}, payload, tiers) if name else None
    now = time.time()
    session = str(payload.get("session_id") or "unknown")
    with locked():
        data = load()
        live = running(data, session, now)
        live.append({"agent_id": str(payload.get("agent_id") or ""), "tier": tier, "started_at": int(now)})
        put_session(data, "running_agents", session, live)
        waiting = pending(data, session, now)
        if waiting:                             # the start claims its launch: same tier first, else the oldest
            waiting.pop(next((i for i, p in enumerate(waiting) if p.get("tier") == tier), 0))
        put_session(data, "pending_launches", session, waiting)
        save(data)


def subagent_stop(payload):
    session = str(payload.get("session_id") or "unknown")
    agent_id = str(payload.get("agent_id") or "")
    with locked():
        data = load()
        table = data.get("running_agents")
        if not isinstance(table, dict) or session not in table:
            return
        live = running(data, session, time.time())
        for i, entry in enumerate(live):
            if not agent_id or entry.get("agent_id") == agent_id:
                del live[i]                     # one stop removes one entry
                break
        table[session] = live
        data["running_agents"] = {k: v for k, v in table.items() if v}
        save(data)


def unattended():
    """Nobody can answer an ask: AI_UNATTENDED=1, or Claude Code's own
    CLAUDE_CODE_SESSION_ATTENDED=0 (set by `claude -p` and the SDK). Unset —
    an older Claude Code — still asks."""
    return os.environ.get("AI_UNATTENDED") == "1" or os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0"


def will_ask():
    return RUNTIME == "claude" and not unattended()


def ask_or_explain(reason):
    """Ask on Claude Code; Codex cannot ask and an unattended run has nobody
    to answer, so there the launch goes through with the reason in context."""
    if will_ask():
        respond({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                        "permissionDecisionReason": f"runtime-gate: {reason}"}})
    else:
        respond({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                 f"runtime-gate: {reason}. It runs anyway ({'unattended' if RUNTIME == 'claude' else 'Codex cannot ask'}); "
                 "say so when you report it."}})


def budget_pre_tool_use(payload):
    tool_input = payload.get("tool_input")
    agent_call = payload.get("tool_name") == "Agent" if RUNTIME == "claude" else is_agent_event(payload)
    if not agent_call or not isinstance(tool_input, dict) or tool_input.get("subagent_type") == "fork":
        return
    prof = profile()
    budgets = prof.get("budgets")
    if not isinstance(budgets, dict):
        return                                  # no plan tables: no budget
    tier = launch_tier(tool_input, payload, prof.get("tiers") or {})
    plan = prof.get("label") or prof.get("plan") or "this plan"
    reasons = []

    task = project_task(payload.get("cwd"))[1] if tier == "EXPERT" else None
    session = str(payload.get("session_id") or "unknown")
    now = time.time()
    with locked():                              # one read and one write: parallel launches see each other
        data = load()
        used = 0
        if task:
            counts = data.get("expert_launches") if isinstance(data.get("expert_launches"), dict) else {}
            used = int(counts.get(task, 0))
            counts[task] = used + 1
            data["expert_launches"] = counts
        waiting = pending(data, session, now)
        live = running(data, session, now) + waiting

        if tier == "EXPERT":
            expert = budgets.get("expert") or {}
            limit = int(expert.get("max_per_task") or 0)
            if not expert.get("without_asking"):
                reasons.append(f"EXPERT agents run only when asked on {plan}")
            elif task and limit and used >= limit:
                reasons.append(f"task {task} already launched {used} EXPERT agent(s), the {plan} budget is {limit}")
        fan = budgets.get("fan_out") or {}
        most = int(fan.get("max_parallel_agents") or 0)
        if most and len(live) >= most:
            reasons.append(f"{len(live)} agent(s) already running, the {plan} fan-out is {most}"
                           + (" and serial" if fan.get("serial") else ""))
        strong = [a for a in live if a.get("tier") in ("STRONG", "EXPERT")]
        most_strong = int(fan.get("max_parallel_on_strong") or 0)
        if tier in ("STRONG", "EXPERT") and most_strong and len(strong) >= most_strong:
            reasons.append(f"{len(strong)} STRONG/EXPERT agent(s) already running, the {plan} limit is {most_strong}")

        # A launch that goes ahead now counts at once; one that asks does not —
        # declined, it would hold a slot for PENDING_TTL; approved, its
        # SubagentStart counts it.
        if not (reasons and will_ask()):
            waiting.append({"tier": tier, "at": int(now)})
        put_session(data, "pending_launches", session, waiting)
        save(data)
    if reasons:
        ask_or_explain("; ".join(reasons))


def pre_tool_use(payload):
    """The reroute first, then the budgets; each fails open on its own."""
    for step in (claude_pre_tool_use if RUNTIME == "claude" else codex_pre_tool_use, budget_pre_tool_use):
        try:
            step(payload)
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def codex_stop(payload):
    for step in (codex_subagent_stop, subagent_stop):
        try:
            step(payload)
        except Exception:  # pylint: disable=broad-exception-caught
            pass


# ------------------------------------------------------------------ entry points
HANDLERS = {
    "claude": {"PreToolUse": pre_tool_use, "PostToolUse": claude_post_tool_use,
               "StopFailure": claude_stop_failure,
               "SubagentStart": subagent_start, "SubagentStop": subagent_stop},
    "codex": {"PreToolUse": pre_tool_use, "PostToolUse": codex_post_tool_use,
              "SubagentStart": subagent_start, "SubagentStop": codex_stop},
}


def cli(argv):
    cmd = argv[0]
    if cmd == "status":
        rec = active()
        label = "Fable" if RUNTIME == "claude" else EXPERT
        if rec:
            print(f"active: {label} -> {FALLBACK} until {hhmm(float(rec['until']))} "
                  f"({rec.get('reason')}, from {rec.get('source')})")
        elif RUNTIME == "claude":
            print("inactive: model: fable agents run on Fable")
        else:
            print(f"inactive: EXPERT agents run on {EXPERT}")
        return 0
    if cmd == "quota":
        q = quota()
        if "--json" in argv[1:]:
            print(json.dumps(q))
        elif q["seen_at"]:
            def pct(v):
                return "?" if v is None else f"{v:.0f}%"
            print(f"quota ({RUNTIME}, from {q['source']}): weekly {pct(q['weekly_pct'])}, "
                  f"5-hour {pct(q['five_hour_pct'])}, seen {hhmm(q['seen_at'])}"
                  + (f", resets {hhmm(q['resets_at'])}" if q["resets_at"] else "")
                  + (" — stale" if q["stale"] else ""))
        else:
            print(f"quota ({RUNTIME}): unknown — no statusline or rollout seen yet")
        return 0
    if cmd == "clear":
        with locked():
            data = load()
            for key in ("unavailable", "running_agents", "pending_launches"):
                data.pop(key, None)             # the count too, as docs/hooks.md promises
            save(data)
        print("cleared")
        return 0
    if cmd == "set" and len(argv) >= 2 and argv[1].isdigit():
        mark(time.time() + int(argv[1]), " ".join(argv[2:]) or "manual", "cli")
        return cli(["status"])
    print("usage: runtime-gate.py status | quota [--json] | clear | set <seconds> [reason] | statusline [--then <cmd>] < json",
          file=sys.stderr)
    return 2


def disabled():
    for key in ("AI_RUNTIME_GATE", LEGACY[RUNTIME][1]):
        value = os.environ.get(key)
        if value:
            return value.lower() in ("off", "0", "false", "no")
    return False


def statusline_main(argv):
    """`statusline [--then <command>]`: check the weekly limit, then hand the same
    input to the user's own statusline command and pass its output and exit code
    through. The check never gets in the way of the statusline."""
    data = sys.stdin.buffer.read()
    if not disabled() and RUNTIME == "claude":
        try:
            payload = json.loads(data.decode("utf-8", "replace"))
            if isinstance(payload, dict):
                statusline(payload)
        except Exception:  # pylint: disable=broad-exception-caught  # fail open: a bad payload never breaks the statusline
            pass
    if len(argv) >= 3 and argv[1] == "--then" and argv[2].strip():
        shell = shutil.which("bash") or "/bin/sh"
        sys.stdout.flush()
        return subprocess.run([shell, "-c", argv[2]], input=data, check=False).returncode
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    runtime = None
    if argv[:1] == ["--as"] and len(argv) >= 2:     # set by the shims only
        runtime = {name: rt for rt, (name, _) in LEGACY.items()}.get(argv[1])
        argv = argv[2:]
    configure(runtime or detect_runtime())
    if argv and argv[0] == "statusline":
        return statusline_main(argv)
    if argv:
        return cli(argv)
    if disabled():
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        handler = HANDLERS[RUNTIME].get(payload.get("hook_event_name"))
        if handler:
            handler(payload)
        if RESPONSE:
            print(json.dumps(RESPONSE))
    except Exception:  # pylint: disable=broad-exception-caught
        pass                                    # fail open: never break an Agent call
    return 0


configure(detect_runtime())

if __name__ == "__main__":
    sys.exit(main())
