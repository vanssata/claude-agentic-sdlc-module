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

A record expires on its own. The gate never denies, always exits 0, and any
error inside it fails open: the call goes through unchanged.

  runtime-gate.py status | clear | set <seconds> [reason] | statusline [--then <cmd>]

The runtime is the home the hook runs from (~/.codex/hooks -> Codex, anything
else -> Claude Code); the shims name theirs. State lives in
<home>/state/runtime-gate.json; a state file of the old gate is imported once.

Environment, new name before the old one of that runtime before the default:
AI_RUNTIME_GATE=off (CLAUDE_FABLE_GATE, CODEX_MODEL_GATE) disables every check;
AI_RUNTIME_GATE_STATE, _TTL, _NOT_FOUND_TTL, _OVERLOAD_TTL, _LAUNCH_WINDOW,
_WEEKLY_PCT, _FALLBACK, _EXPERT, _FALLBACK_EFFORT, _MODE tune it.
"""
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

LEGACY = {"claude": ("fable-gate", "CLAUDE_FABLE_GATE"), "codex": ("codex-model-gate", "CODEX_MODEL_GATE")}

# Set by configure(); module-level so the shims (and the old suites through
# them) can read STATE and call mark() exactly as before.
RUNTIME = "claude"
HOME = STATE = LEGACY_STATE = ""
LIMIT_TTL = NOT_FOUND_TTL = OVERLOAD_TTL = LAUNCH_WINDOW = 0
WEEKLY_PCT = 0.0
EXPERT = FALLBACK = FALLBACK_EFFORT = MODE = ""
TTL_BY_ERROR = {}


def setting(name, default, runtime=None):
    """AI_RUNTIME_GATE_<name>, then the runtime's old name, then the default."""
    old = LEGACY[runtime or RUNTIME][1]
    for key in (f"AI_RUNTIME_GATE_{name}", f"{old}_{name}"):
        value = os.environ.get(key)
        if value not in (None, ""):
            return value
    return default


def profile_tier(home, tier, field, default):
    """A field of the installed plan's tier table, else the default."""
    try:
        with open(os.path.join(home, "claude-agentic", "profile.json"), encoding="utf-8") as fh:
            value = json.load(fh)["tiers"][tier][field]
        return value if isinstance(value, str) and value else default
    except (OSError, ValueError, KeyError, TypeError):
        return default


def configure(runtime):
    """Bind every setting for one runtime."""
    # pylint: disable=global-statement
    global RUNTIME, HOME, STATE, LEGACY_STATE, LIMIT_TTL, NOT_FOUND_TTL, OVERLOAD_TTL
    global LAUNCH_WINDOW, WEEKLY_PCT, EXPERT, FALLBACK, FALLBACK_EFFORT, MODE, TTL_BY_ERROR
    RUNTIME = runtime
    if runtime == "codex":
        HOME = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    else:
        HOME = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    STATE = setting("STATE", "") or os.path.join(HOME, "state", "runtime-gate.json")
    LEGACY_STATE = os.path.join(HOME, "state", LEGACY[runtime][0] + ".json")
    LIMIT_TTL = int(setting("TTL", "3600"))
    NOT_FOUND_TTL = int(setting("NOT_FOUND_TTL", "21600"))
    OVERLOAD_TTL = int(setting("OVERLOAD_TTL", "900"))
    LAUNCH_WINDOW = int(setting("LAUNCH_WINDOW", "300"))
    WEEKLY_PCT = float(setting("WEEKLY_PCT", "90"))
    MODE = setting("MODE", "rewrite")
    if runtime == "codex":
        EXPERT = setting("EXPERT", profile_tier(HOME, "EXPERT", "model", "gpt-6-astra"))
        FALLBACK = setting("FALLBACK", profile_tier(HOME, "STRONG", "model", "gpt-5.6-sol"))
        FALLBACK_EFFORT = setting("FALLBACK_EFFORT", profile_tier(HOME, "STRONG", "effort", "high"))
    else:
        EXPERT = setting("EXPERT", "fable")
        FALLBACK = setting("FALLBACK", "opus")
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
def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except OSError:
        return import_legacy()
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


def save(data):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, STATE)


def active(now=None):
    """The live unavailability record, or None."""
    rec = load().get("unavailable")
    now = time.time() if now is None else now
    if isinstance(rec, dict) and float(rec.get("until", 0)) > now:
        return rec
    return None


def mark(until, reason, source):
    until = math.ceil(until)                     # round up: truncating would end the record up to a second early
    data = load()
    rec = data.get("unavailable")
    if isinstance(rec, dict) and float(rec.get("until", 0)) >= until:
        return                                  # a longer record already stands
    data["unavailable"] = {"until": until, "reason": reason, "source": source,
                           "set_at": int(time.time())}
    save(data)


def note_launch():
    data = load()                               # remembered for failure attribution
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
    print(json.dumps({
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
    }))


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
    week = ((payload.get("rate_limits") or {}).get("seven_day") or {})
    pct = week.get("used_percentage")
    if pct is None or float(pct) < WEEKLY_PCT:
        return
    until = reset_epoch(week.get("resets_at"))
    if not until or until <= time.time():
        until = time.time() + LIMIT_TTL
    mark(until, f"weekly limit {float(pct):.0f}% used", "statusline")


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
        out["hookSpecificOutput"]["permissionDecision"] = "allow"
        out["hookSpecificOutput"]["updatedInput"] = {
            **tool_input, "model": FALLBACK, "model_reasoning_effort": FALLBACK_EFFORT,
        }
    out["hookSpecificOutput"]["additionalContext"] = context
    print(json.dumps(out))


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


# ------------------------------------------------------------------ entry points
HANDLERS = {
    "claude": {"PreToolUse": claude_pre_tool_use, "PostToolUse": claude_post_tool_use,
               "StopFailure": claude_stop_failure},
    "codex": {"PreToolUse": codex_pre_tool_use, "PostToolUse": codex_post_tool_use,
              "SubagentStop": codex_subagent_stop},
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
    if cmd == "clear":
        data = load()
        data.pop("unavailable", None)
        save(data)
        print("cleared")
        return 0
    if cmd == "set" and len(argv) >= 2 and argv[1].isdigit():
        mark(time.time() + int(argv[1]), " ".join(argv[2:]) or "manual", "cli")
        return cli(["status"])
    print("usage: runtime-gate.py status | clear | set <seconds> [reason] | statusline [--then <cmd>] < json",
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
    except Exception:  # pylint: disable=broad-exception-caught
        pass                                    # fail open: never break an Agent call
    return 0


configure(detect_runtime())

if __name__ == "__main__":
    sys.exit(main())
