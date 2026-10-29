#!/usr/bin/env python3
"""Update notice: tell the user at session start when npm has a newer `riskrails`.

Imported by context-guard.py (SessionStart) and run as a script for the refresh:

    update_notice.py --refresh <cache path>

The hook itself never touches the network. It reads <home>/riskrails/update-check.json
({"checked_at": epoch, "latest": "x.y.z"}); when that file is missing or older than a
day it starts the refresh as a detached child and answers from the cache as it is, so
the first session after an install says nothing and a later one does. The child asks
the registry (3 s timeout) and writes the cache atomically; any error is silent, and a
failed fetch only moves checked_at, so the next try waits a day.

Environment:
    RISKRAILS_NO_UPDATE_CHECK   non-empty turns the check off (no read, no spawn)
    CI                          non-empty turns it off as well
    RISKRAILS_REGISTRY_URL      instead of https://registry.npmjs.org/riskrails/latest (file:// works)
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

REGISTRY_URL = "https://registry.npmjs.org/riskrails/latest"
MAX_AGE = 24 * 3600
TIMEOUT = 3
COMMAND = "npx -y riskrails@latest --yes"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")   # no prerelease, no build metadata


def parse(version):
    """(major, minor, patch) of a plain X.Y.Z, else None."""
    match = VERSION_RE.match(version.strip()) if isinstance(version, str) else None
    return tuple(int(n) for n in match.groups()) if match else None


def installed_version(runtime, plugin_root, home=None):
    """The installed release: profile.json's plugin_version (written by the installer into
    <home>/riskrails/), else the plugin manifest beside the hooks (plugin-cache layout).
    Only a plain X.Y.Z counts; anything else is None."""
    manifest = ".codex-plugin" if runtime == "codex" else ".claude-plugin"
    sources = [(os.path.join(plugin_root, manifest, "plugin.json"), "version")]
    if home:
        sources.insert(0, (os.path.join(home, "riskrails", "profile.json"), "plugin_version"))
    for path, key in sources:
        try:
            with open(path, encoding="utf-8") as fh:
                version = json.load(fh).get(key)
        except (OSError, ValueError, AttributeError):
            continue
        if parse(version):
            return version
    return None


def read_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def disabled():
    return bool(os.environ.get("RISKRAILS_NO_UPDATE_CHECK") or os.environ.get("CI"))


def spawn_refresh(path):
    try:
        subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "--refresh", path],  # pylint: disable=consider-using-with
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def notice(runtime, home, plugin_root, now):
    """(systemMessage, additionalContext) when the cache knows a newer release, else ("", "")."""
    if disabled():
        return "", ""
    riskrails = os.path.join(home, "riskrails")
    path = os.path.join(riskrails, "update-check.json")
    cache = read_cache(path)
    checked = cache.get("checked_at")
    fresh = isinstance(checked, (int, float)) and 0 <= now - checked < MAX_AGE
    if not fresh and os.path.isdir(riskrails):
        spawn_refresh(path)
    installed, latest = installed_version(runtime, plugin_root, home), cache.get("latest")
    have, new = parse(installed), parse(latest)
    if not have or not new or new <= have:
        return "", ""
    message = (f"RiskRails {latest} is available (installed {installed}). Update: {COMMAND} "
               f"— inside Claude Code or Codex CLI: ! {COMMAND} — then /rr-setup --update in each project.")
    context = (f"RiskRails {latest} is available on npm; {installed} is installed. The user updates it "
               f"with `{COMMAND}` in a terminal, or `! {COMMAND}` inside Claude Code or Codex CLI, "
               "then `/rr-setup --update` in each project. Mention this once to the user if it is "
               "relevant; never run the update yourself — installing is the user's act.")
    return message, context


def refresh(path):
    """Ask the registry and write the cache; on failure only move checked_at."""
    latest = None
    try:
        url = os.environ.get("RISKRAILS_REGISTRY_URL") or REGISTRY_URL
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:  # nosec: the registry, or a test's file URL
            version = json.loads(resp.read().decode("utf-8")).get("version")
        if parse(version):
            latest = version
    except (OSError, ValueError, AttributeError):
        pass
    if latest is None:
        previous = read_cache(path).get("latest")
        latest = previous if isinstance(previous, str) else None
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"checked_at": int(time.time()), "latest": latest}, fh)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--refresh" and not disabled():
        refresh(sys.argv[2])
    sys.exit(0)
