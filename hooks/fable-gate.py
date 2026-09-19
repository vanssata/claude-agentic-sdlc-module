#!/usr/bin/env python3
"""Fable gate: send Fable subagents to Opus while Fable is unavailable.

`fallbackModel` already moves a subagent off an *overloaded* model. It does not
act on a rate limit, a used-up usage limit, or a model the account cannot reach —
those end the agent with an error, and the next `model: fable` agent hits the
same wall. This hook closes that gap:

  StopFailure (rate_limit|model_not_found)  records that Fable is unavailable
  PostToolUse:Agent                         records a Fable agent that fell back (overload), briefly
  PreToolUse:Agent                          while a record is live, rewrites model fable -> opus
  statusline [--then <command>]             records it when the weekly limit is nearly used, then
                                            runs the user's own statusline command on the same input

Hooks never see the account's rate limits; the statusline does, which is why the
installer wraps the statusline command with this script on a Fable install.

A record expires on its own, so Fable is tried again after the reset. The gate
never blocks an agent or breaks the statusline, and any error inside it fails
open: the call goes through unchanged.

  fable-gate.py status | clear | set <seconds> [reason]

Environment: CLAUDE_FABLE_GATE=off disables every check (the wrapped statusline
still runs); CLAUDE_FABLE_GATE_STATE, _TTL, _NOT_FOUND_TTL, _OVERLOAD_TTL,
_LAUNCH_WINDOW, _WEEKLY_PCT, _FALLBACK tune it.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time

CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
STATE = os.environ.get("CLAUDE_FABLE_GATE_STATE") or os.path.join(CONFIG_DIR, "state", "fable-gate.json")
LIMIT_TTL = int(os.environ.get("CLAUDE_FABLE_GATE_TTL", "3600"))
NOT_FOUND_TTL = int(os.environ.get("CLAUDE_FABLE_GATE_NOT_FOUND_TTL", "21600"))
OVERLOAD_TTL = int(os.environ.get("CLAUDE_FABLE_GATE_OVERLOAD_TTL", "900"))
LAUNCH_WINDOW = int(os.environ.get("CLAUDE_FABLE_GATE_LAUNCH_WINDOW", "300"))
WEEKLY_PCT = float(os.environ.get("CLAUDE_FABLE_GATE_WEEKLY_PCT", "90"))
FALLBACK = os.environ.get("CLAUDE_FABLE_GATE_FALLBACK", "opus")

# StopFailure categories that mean "Fable cannot serve this account right now".
# Authentication, billing and account errors are account-wide: Opus would fail too.
TTL_BY_ERROR = {"rate_limit": LIMIT_TTL, "model_not_found": NOT_FOUND_TTL}

# Until this Claude Code version CLAUDE_CODE_SUBAGENT_MODEL overrode the call's own
# `model` and the frontmatter; since it, the variable is only the fallback after them.
ENV_FIRST_BEFORE = (2, 1, 251)


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
    """The live unavailability record, or None."""
    rec = load().get("unavailable")
    now = time.time() if now is None else now
    if isinstance(rec, dict) and float(rec.get("until", 0)) > now:
        return rec
    return None


def mark(until, reason, source):
    data = load()
    rec = data.get("unavailable")
    if isinstance(rec, dict) and float(rec.get("until", 0)) >= until:
        return                                  # a longer record already stands
    data["unavailable"] = {"until": int(until), "reason": reason, "source": source,
                           "set_at": int(time.time())}
    save(data)


def hhmm(epoch):
    return dt.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ model resolution
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


def transcript_tail(path):
    """The last megabyte of a transcript as lines, newest last; [] when unreadable."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 1_000_000))
            return fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError):
        return []


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
        candidates.append(os.path.join(CONFIG_DIR, "agents", f"{name}.md"))
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


# ------------------------------------------------------------------ hook events
def pre_tool_use(payload):
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") != "Agent" or not isinstance(tool_input, dict):
        return
    if tool_input.get("subagent_type") == "fork":   # forks ignore `model`
        return
    if not is_fable(agent_model(tool_input, payload)):
        return

    rec = active()
    if rec is None:
        data = load()                           # remembered for StopFailure attribution
        data["last_fable_launch"] = int(time.time())
        save(data)
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
                "`~/.claude/hooks/fable-gate.py clear` re-enables Fable early."
            ),
        }
    }))


def post_tool_use(payload):
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


def stop_failure(payload):
    error = payload.get("error")
    if error not in TTL_BY_ERROR:
        return
    text = " ".join(str(payload.get(k) or "") for k in ("error_details", "last_assistant_message"))
    agent_type = payload.get("agent_type")
    launched = load().get("last_fable_launch", 0)
    fable_involved = (
        "fable" in text.lower()
        or is_fable(payload.get("model"))
        or (isinstance(agent_type, str)
            and is_fable(agent_model({"subagent_type": agent_type}, payload, guess=False)))
        or is_fable(last_transcript_model(payload.get("agent_transcript_path")
                                          or payload.get("transcript_path")))
        or time.time() - float(launched) <= LAUNCH_WINDOW
    )
    if fable_involved:
        mark(time.time() + TTL_BY_ERROR[error], error, "StopFailure")


# ------------------------------------------------------------------ statusline
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


# ------------------------------------------------------------------ entry points
def cli(argv):
    cmd = argv[0]
    if cmd == "status":
        rec = active()
        if rec:
            print(f"active: Fable -> {FALLBACK} until {hhmm(float(rec['until']))} "
                  f"({rec.get('reason')}, from {rec.get('source')})")
        else:
            print("inactive: model: fable agents run on Fable")
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
    print("usage: fable-gate.py status | clear | set <seconds> [reason] | statusline < json",
          file=sys.stderr)
    return 2


HANDLERS = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use, "StopFailure": stop_failure}


def disabled():
    return os.environ.get("CLAUDE_FABLE_GATE", "on").lower() in ("off", "0", "false", "no")


def statusline_main(argv):
    """`statusline [--then <command>]`: check the weekly limit, then hand the same
    input to the user's own statusline command and pass its output and exit code
    through. The check never gets in the way of the statusline."""
    data = sys.stdin.buffer.read()
    if not disabled():
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


def main():
    argv = sys.argv[1:]
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
        handler = HANDLERS.get(payload.get("hook_event_name"))
        if handler:
            handler(payload)
    except Exception:  # pylint: disable=broad-exception-caught
        pass                                    # fail open: never break an Agent call
    return 0


if __name__ == "__main__":
    sys.exit(main())
