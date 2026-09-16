#!/usr/bin/env python3
"""Codex expert-model gate: send EXPERT subagents to the STRONG model while the
EXPERT model cannot serve this account.

Codex resolves a subagent's model from the spawn request, then the `[agents]`
default, then the parent — and a custom agent file's own `model` wins over all
of them. That is what makes `ai-expert` genuinely run on the EXPERT model, and
it is also why a rate limit on that model turns every EXPERT launch into the
same failure. This hook closes that gap:

  SubagentStop (rate limit / model unavailable)  records that EXPERT is unusable
  PostToolUse:Agent (same signals in the result) records it too
  PreToolUse:Agent   while a record is live, rewrites an EXPERT launch to STRONG

A record expires on its own, so the EXPERT model is tried again after the reset.

What this deliberately does *not* do: react to a wrong or low-confidence answer.
Only an explicit capacity or availability signal activates the gate — an agent
that reasons badly is not an agent that could not run.

  codex-model-gate.py status | clear | set <seconds> [reason]

Environment: CODEX_MODEL_GATE=off disables every check.
CODEX_MODEL_GATE_STATE, _TTL, _NOT_FOUND_TTL, _EXPERT, _FALLBACK,
_FALLBACK_EFFORT tune it. CODEX_MODEL_GATE_MODE=context makes the PreToolUse
handler explain the outage without rewriting the spawn arguments, for a Codex
build whose spawn tool rejects an explicit `model`.
"""
import datetime as dt
import json
import os
import re
import sys
import time

CODEX_HOME = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
STATE = os.environ.get("CODEX_MODEL_GATE_STATE") or os.path.join(CODEX_HOME, "state", "codex-model-gate.json")
LIMIT_TTL = int(os.environ.get("CODEX_MODEL_GATE_TTL", "3600"))
NOT_FOUND_TTL = int(os.environ.get("CODEX_MODEL_GATE_NOT_FOUND_TTL", "21600"))
EXPERT = os.environ.get("CODEX_MODEL_GATE_EXPERT", "gpt-6-astra")
FALLBACK = os.environ.get("CODEX_MODEL_GATE_FALLBACK", "gpt-5.6-sol")
FALLBACK_EFFORT = os.environ.get("CODEX_MODEL_GATE_FALLBACK_EFFORT", "high")
MODE = os.environ.get("CODEX_MODEL_GATE_MODE", "rewrite")

# Explicit capacity and availability signals only. Each one names a condition
# under which the model could not run at all; none of them describes an answer
# the model gave. `error`/`failed` alone is not enough on purpose.
SIGNALS = (
    (re.compile(r"rate[ _-]?limit|429\b|too many requests|usage limit reached|"
                r"quota (?:exceeded|exhausted)|insufficient_quota", re.I), "rate_limit", LIMIT_TTL),
    (re.compile(r"model[ _-]?not[ _-]?found|unknown model|unsupported model|"
                r"model_unavailable|model is (?:currently )?unavailable|"
                r"does not have access to (?:the )?model|no access to model", re.I),
     "model_unavailable", NOT_FOUND_TTL),
    (re.compile(r"\b(?:overloaded|capacity (?:exceeded|unavailable)|service unavailable|503)\b", re.I),
     "overloaded", LIMIT_TTL),
)

AGENT_TOOLS = {"agent", "spawn_agent", "task"}
AGENT_NAME_KEYS = ("agent_type", "subagent_type", "agent", "agent_name", "name", "type")


# ------------------------------------------------------------------ state
def load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = f"{STATE}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, STATE)


def active(now=None):
    rec = load().get("unavailable")
    now = time.time() if now is None else now
    if isinstance(rec, dict) and float(rec.get("until", 0)) > now:
        return rec
    return None


def mark(until, reason, source):
    data = load()
    rec = data.get("unavailable")
    if isinstance(rec, dict) and float(rec.get("until", 0)) >= until:
        return                                   # a longer record already stands
    data["unavailable"] = {"until": int(until), "reason": reason, "source": source,
                           "set_at": int(time.time())}
    save(data)


def hhmm(epoch):
    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ model resolution
def is_expert(model):
    return isinstance(model, str) and EXPERT.lower() in model.lower()


def agent_file_model(name):
    """The `model` pinned by a custom agent file, or None when there is none.
    Project agents win over personal ones, the way Codex layers config."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""):
        return None
    roots = [os.path.join(os.getcwd(), ".codex", "agents"), os.path.join(CODEX_HOME, "agents")]
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
    path = os.path.join(CODEX_HOME, "config.toml")
    try:
        with open(path, encoding="utf-8") as fh:
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
    pinned = agent_file_model(agent_name(tool_input))
    if pinned:
        return pinned
    return config_default_model()


def is_agent_event(payload):
    name = (payload.get("tool_name") or "").lower()
    return name in AGENT_TOOLS


# ------------------------------------------------------------------ signals
def classify(text):
    """(reason, ttl) for an explicit availability failure, or None."""
    if not text:
        return None
    for pattern, reason, ttl in SIGNALS:
        if pattern.search(text):
            return reason, ttl
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


# ------------------------------------------------------------------ hook events
def pre_tool_use(payload):
    tool_input = payload.get("tool_input")
    if not is_agent_event(payload) or not isinstance(tool_input, dict):
        return
    if not is_expert(launch_model(tool_input)):
        return

    rec = active()
    if rec is None:
        data = load()                            # remembered for SubagentStop attribution
        data["last_expert_launch"] = int(time.time())
        save(data)
        return

    name = agent_name(tool_input) or "the expert agent"
    why = f"{EXPERT} is unavailable ({rec.get('reason', 'unknown')}) until {hhmm(float(rec['until']))}"
    context = (
        f"codex-model-gate: {why}. {name} runs on {FALLBACK} instead, so its answer is "
        f"{FALLBACK}'s, not {EXPERT}'s. Say so when you report it. "
        "`codex-model-gate.py clear` re-enables the expert model early."
    )
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if MODE == "rewrite":
        out["hookSpecificOutput"]["permissionDecision"] = "allow"
        out["hookSpecificOutput"]["updatedInput"] = {
            **tool_input, "model": FALLBACK, "model_reasoning_effort": FALLBACK_EFFORT,
        }
    out["hookSpecificOutput"]["additionalContext"] = context
    print(json.dumps(out))


def post_tool_use(payload):
    tool_input = payload.get("tool_input")
    if not is_agent_event(payload) or not isinstance(tool_input, dict):
        return
    if not is_expert(launch_model(tool_input)):
        return
    hit = classify(texts(payload.get("tool_response")))
    if hit:
        mark(time.time() + hit[1], hit[0], "PostToolUse")


def subagent_stop(payload):
    text = texts(payload.get("last_assistant_message"), payload.get("error"),
                 payload.get("error_details"), payload.get("stopReason"))
    hit = classify(text)
    if not hit:
        return
    # Attribute the failure before acting on it: a rate limit reported by a Terra
    # agent says nothing about the expert model.
    agent_type = payload.get("agent_type")
    launched = load().get("last_expert_launch", 0)
    involved = (
        EXPERT.lower() in text.lower()
        or is_expert(payload.get("model"))
        or is_expert(agent_file_model(agent_type) or "")
        or time.time() - float(launched or 0) <= 300
    )
    if involved:
        mark(time.time() + hit[1], hit[0], "SubagentStop")


# ------------------------------------------------------------------ entry points
def cli(argv):
    cmd = argv[0]
    if cmd == "status":
        rec = active()
        if rec:
            print(f"active: {EXPERT} -> {FALLBACK} until {hhmm(float(rec['until']))} "
                  f"({rec.get('reason')}, from {rec.get('source')})")
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
    print("usage: codex-model-gate.py status | clear | set <seconds> [reason]", file=sys.stderr)
    return 2


HANDLERS = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use,
            "SubagentStop": subagent_stop}


def disabled():
    return os.environ.get("CODEX_MODEL_GATE", "on").lower() in ("off", "0", "false", "no")


def main():
    argv = sys.argv[1:]
    if argv:
        return cli(argv)
    if disabled():
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        handler = HANDLERS.get(payload.get("hook_event_name"))
        if handler:
            handler(payload)
    except Exception:
        pass                                     # fail open: never break a spawn
    return 0


if __name__ == "__main__":
    sys.exit(main())
