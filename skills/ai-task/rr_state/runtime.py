"""The runtime: which runtime (claude or codex) this process acts as, where each one is installed, and the agent markers in the environment.

shell: Runtime, installed_runtime, detect_runtime, runtime_home, own_runtime, other_runtime, installed, agent_markers
core: RUNTIMES, AGENT_MARKERS
"""

import dataclasses
import os

from rr_state import fs

RUNTIMES = ["claude", "codex"]


@dataclasses.dataclass(frozen=True)
class Runtime:
    """The runtime this process acts as and whether the command mutates state; built once by cli.main from the three resolutions, never changed (R4)."""
    name: str = "unknown"
    mutating: bool = False


def installed_runtime():
    """The runtime whose home this copy is installed in, or None for a checkout.
    Both skills call state.py from their own home ($AI_HOME), so this answers
    for every call a runtime makes."""
    here = fs.ENTRY
    for runtime in ("codex", "claude"):
        home = os.path.abspath(runtime_home(runtime)).rstrip(os.sep) + os.sep
        if here.startswith(home):
            return runtime
    return None


def detect_runtime(explicit, root):
    """--runtime > AI_RUNTIME > install location > CLAUDECODE > session.json >
    unknown (I10). session.json names whichever runtime was prompted last, so it
    comes after everything the process itself can tell: read first, it let one
    runtime's change pass as the other's while both were working. The install
    location outranks CLAUDECODE because an environment variable is inherited:
    codex started from a Claude Code shell carries CLAUDECODE=1 (seen live)."""
    for candidate in (explicit, os.environ.get("AI_RUNTIME"), installed_runtime(),
                      "claude" if os.environ.get("CLAUDECODE") else None,
                      fs.read_session(root).get("runtime")):
        if candidate in RUNTIMES:
            return candidate
    return "unknown"


def runtime_home(runtime):
    if runtime == "codex":
        return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def own_runtime(runtime="unknown"):
    """This process's runtime; an undetected one is read from where this file
    is installed, so a plain shell under ~/.codex still reads the Codex plan."""
    if runtime in RUNTIMES:
        return runtime
    return "codex" if "%s.codex%s" % (os.sep, os.sep) in fs.ENTRY else "claude"


def other_runtime(runtime=None, rt=Runtime()):
    return "codex" if (runtime or own_runtime(runtime=rt.name)) == "claude" else "claude"


def installed(runtime):
    return os.path.isfile(os.path.join(runtime_home(runtime), "skills", "ai-task", "state.py"))


# Set by the runtimes in every process they start, the `!` prefix's shell
# included. Duplicated on purpose from skills/project-update/adopt.py
# (AGENT_MARKERS): the two skills are installed independently and neither
# imports the other.
AGENT_MARKERS = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI",
                 "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION")


def agent_markers():
    return [name for name in AGENT_MARKERS if name in os.environ]
