"""What the plugin shipped and what a project declares: the schema error, the project's runtimes, the shipped-template history, the shared tree, the schema numbers.

shell: project_runtimes, History, shared_files, undeclared_shared, template_version, project_version
core: SchemaError
"""

import json
import os
import re

from rr_update import files
from rr_update import paths


class SchemaError(Exception):
    """The project's schema cannot be read or is newer than this plugin."""



def project_runtimes(root):
    """The runtimes a project declares, or the one this plugin copy serves."""
    out = []
    if os.path.exists(os.path.join(root, "CLAUDE.md")) or os.path.isdir(os.path.join(root, ".claude")):
        out.append("claude")
    if os.path.exists(os.path.join(root, "AGENTS.md")) or os.path.isdir(os.path.join(root, ".codex")):
        out.append("codex")
    if os.path.exists(os.path.join(root, "GEMINI.md")) or os.path.isdir(os.path.join(root, ".gemini")):
        out.append("gemini")
    if os.path.isdir(os.path.join(root, ".junie")):
        out.append("junie")
    if not out:
        out.append("codex" if "/.codex/" in paths.HERE + "/" else "claude")
    return out



class History:
    """index.json answers "was this ever shipped" from hashes alone; the blobs
    give the one-time split its base values."""

    def __init__(self, root):
        try:
            with open(os.path.join(root, "index.json"), encoding="utf-8") as fh:
                self.index = json.load(fh)
        except (OSError, ValueError, RecursionError):
            self.index = {}
        self.root = root

    def versions(self, key):
        """Every shipped version of a template, oldest first, as bytes."""
        out = []
        for h in self.index.get(key, []):
            try:
                out.append(files.read(os.path.join(self.root, "blobs", h)))
            except OSError:
                pass
        return out

    def hashes(self, key):
        """The sha of every version shipped under this key; a version whose blob is gone still counts."""
        return set(self.index.get(key, []))

    def shipped(self, key, data):
        """True when these bytes are a version the plugin shipped, also after a checkout turned its line endings into CRLF."""
        known = self.hashes(key)
        return files.sha(data) in known or files.sha(data.replace(b"\r\n", b"\n")) in known


def shared_files():
    """{".ai/<rel>": bytes} for every shared file the shared tree holds; empty when the tree is not installed."""
    out = {}
    for path in sorted(paths.SHARED_SET):
        full = os.path.join(paths.SHARED, path[len(".ai/"):])
        if os.path.isfile(full):
            out[path] = files.read(full)
    return out


def undeclared_shared():
    """Files in the shared tree outside the shared set, as .ai/ paths."""
    out = []
    for here, _dirs, names in os.walk(paths.SHARED):
        for name in names:
            rel = ".ai/" + os.path.relpath(os.path.join(here, name), paths.SHARED).replace(os.sep, "/")
            if rel not in paths.SHARED_SET:
                out.append(rel)
    return sorted(out)



def template_version():
    """The schema number this plugin ships (its .ai/VERSION template)."""
    return int(files.read(os.path.join(paths.TEMPLATES["ai-init"], paths.VERSION_FILE)).decode().strip())


def project_version(root):
    """The project's .ai/VERSION: 0 when there is none; SchemaError when it cannot
    be read, is not a number, or is newer than this plugin's."""
    path = os.path.join(root, paths.VERSION_FILE)
    try:
        raw = files.read(path) if os.path.lexists(path) else None
    except OSError as exc:  # a directory, a mode-000 file, a dangling link
        raise SchemaError("%s cannot be read: %s" % (paths.VERSION_FILE, exc)) from exc
    if raw is None:
        return 0
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""
    if not re.fullmatch(r"\d+", text):
        raise SchemaError("%s is not a schema number: %r" % (paths.VERSION_FILE, raw[:40]))
    ours = template_version()
    if int(text) > ours:
        raise SchemaError("%s says schema %s, this plugin ships schema %d — update the plugin "
                          "(riskrails/install.sh)" % (paths.VERSION_FILE, text, ours))
    return int(text)

