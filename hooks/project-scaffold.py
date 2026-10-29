#!/usr/bin/env python3
"""Idempotent project scaffold: the shared SDLC folders plus the layout of every
agent runtime the project uses. Never overwrites an existing file.
  project-scaffold.py [project-dir] [--runtime auto|claude|codex|both]
(default: $PWD, auto)
hooks/project-scaffold.sh execs it; that script is also wired as a Claude Code
Setup hook (matcher "init"), and the hook JSON on stdin is read only to pick up
cwd when no argument is given.

docs/sdlc/** and .gitignore are shared and are created once. Only the
provider-specific layer — .claude/** with CLAUDE.md, .codex/** with AGENTS.md —
is duplicated, and only for the runtimes in scope.

A port of the shell script it replaced, kept to its bytes: the same files and
modes, the same listing in the same order, the same messages and exit codes
(tests/test_scaffold_differential.py runs the frozen shell beside it).
"""
import errno
import json
import os
import shutil
import stat
import sys

NAME = "project-scaffold"
HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIMES = ("claude", "codex", "gemini", "junie")


class Exit(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def env(name):
    """A variable as `${NAME:-…}` reads it: unset and empty are the same."""
    return os.environ.get(name) or None


def parse_args(argv):
    root, runtime = "", env("AI_RUNTIMES") or "auto"
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--runtime":
            if i + 1 >= len(argv) or argv[i + 1] == "":
                raise Exit(1, "%s: 2: missing value for --runtime" % NAME)
            runtime = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--runtime="):
            runtime = arg[len("--runtime="):]
        else:
            root = arg
        i += 1
    return root, runtime


def stdin_cwd():
    """The hook payload's cwd, as `python3 -c 'print(json.load(sys.stdin).get("cwd",""))'` printed it."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return ""
        return str(json.load(sys.stdin).get("cwd", "")).rstrip("\n")
    except Exception:  # pylint: disable=broad-except
        return ""


def logical_pwd():
    """bash's $PWD: the inherited one when it still names the working directory."""
    pwd = os.environ.get("PWD", "")
    try:
        if os.path.isabs(pwd) and os.path.samefile(pwd, "."):
            return pwd
    except OSError:
        pass
    return os.getcwd()


CD_USAGE = "cd: usage: cd [-L|[-P [-e]]] [-@] [dir]"


def cd_operand(root):
    """What `cd "$root"` goes to, and whether physically: `--` and an option cluster leave no operand, so $HOME."""
    if root == "-" or not root.startswith("-"):
        return root, False
    physical = False
    if root != "--":
        for ch in root[1:]:
            if ch not in "LPe":
                raise Exit(2, "%s: cd: -%s: invalid option\n%s" % (NAME, ch, CD_USAGE))
            if ch in "LP":
                physical = ch == "P"   # the last of -L and -P wins
    home = os.environ.get("HOME")
    if home is None:
        raise Exit(1, "%s: cd: HOME not set" % NAME)
    return home, physical


def fold(path):
    """bash's logical path: `.` and empty parts dropped, `..` pops a part only once
    what precedes it is a directory (None when it is not)."""
    lead = "//" if path.startswith("//") and not path.startswith("///") else "/"
    parts = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not os.path.isdir(lead + "/".join(parts)):
                return None
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return lead + "/".join(parts)


def logical_cd(root):
    """`cd "$root" && pwd`: the directory, symlinks kept, `..` folded."""
    target, physical = cd_operand(root)
    if target == "" and not physical:
        return logical_pwd()
    path = target if os.path.isabs(target) else os.path.join(logical_pwd(), target)
    found = os.path.realpath(path) if physical else fold(path)
    if target == "" or found is None or not os.path.isdir(found):
        # bash then chdirs to the path as given: the kernel's reason is the message.
        try:
            reason = errno.ENOENT if target == "" else (0 if stat.S_ISDIR(os.stat(path).st_mode) else errno.ENOTDIR)
        except OSError as e:
            reason = e.errno
        if not reason:
            return os.path.realpath(path)
        raise Exit(1, "%s: cd: %s: %s" % (NAME, target, os.strerror(reason)))
    if not os.access(found, os.X_OK):
        raise Exit(1, "%s: cd: %s: %s" % (NAME, target, os.strerror(errno.EACCES)))
    return found


def runtimes(runtime, root):
    """The runtimes in scope: what the project declares (auto), or the list given."""
    if runtime == "both":
        runtime = "claude,codex"
    if runtime == "auto":
        on = {
            "claude": os.path.exists(os.path.join(root, "CLAUDE.md")) or os.path.isdir(os.path.join(root, ".claude")),
            "codex": os.path.exists(os.path.join(root, "AGENTS.md")) or os.path.isdir(os.path.join(root, ".codex")),
            "gemini": os.path.exists(os.path.join(root, "GEMINI.md")) or os.path.isdir(os.path.join(root, ".gemini")),
            "junie": os.path.isdir(os.path.join(root, ".junie")),
        }
        if not any(on.values()):
            # Nothing declared: the runtime this copy of the plugin was installed for.
            on["codex" if "/.codex/" in HERE else "claude"] = True
        return {r for r in RUNTIMES if on[r]}
    # bash splits on IFS=, : a trailing comma ends the last field, it opens no new one.
    fields = runtime.split(",")
    if fields[-1] == "":
        fields.pop()
    for one in fields:
        if one not in RUNTIMES:
            raise Exit(2, "%s: --runtime must be auto|both or a comma list of claude,codex,gemini,junie (got '%s')"
                       % (NAME, one))
    return set(fields)


def umask():
    old = os.umask(0)
    os.umask(old)
    return old


def newline_lead(data):
    """`[ -s f ] && [ -n "$(tail -c1 f)" ] && echo`: a newline unless the file is empty
    or ends in one. `$(…)` drops a NUL last byte as it drops a newline, and says so."""
    if data[-1:] == b"\0":
        sys.stderr.write("%s: warning: command substitution: ignored null byte in input\n" % NAME)
    return b"\n" if data and data[-1:] not in (b"\n", b"\0") else b""


class Scaffold:
    def __init__(self, tpl, root):
        self.tpl, self.root, self.created = tpl, root, []
        name = "/" if root == "/" else os.path.basename(root)
        self.project = os.fsencode(name)

    def put(self, template, target, render=False):
        src, dst = os.path.join(self.tpl, template), os.path.join(self.root, target)
        if os.path.exists(dst):
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if render:
            with open(src, "rb") as fh:
                data = fh.read().replace(b"{{PROJECT}}", self.project)
            with open(dst, "wb") as fh:
                fh.write(data)
        else:
            # cp: the source's permission bits, less the umask.
            shutil.copyfile(src, dst)
            os.chmod(dst, os.stat(src).st_mode & 0o777 & ~umask())
        self.created.append(target)

    def keep(self, rel):
        d = os.path.join(self.root, rel)
        if os.path.exists(os.path.join(d, ".gitkeep")):
            return
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, ".gitkeep"), "wb").close()
        self.created.append(rel + "/.gitkeep")

    def append_once(self, path, marker, template, label):
        """Append a template unless the file already holds `marker`; a missing last newline is added first."""
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except FileNotFoundError:
            data = b""
        if marker in data:
            return
        lead = newline_lead(data)
        with open(os.path.join(self.tpl, template), "rb") as fh:
            chunk = fh.read()
        with open(path, "ab") as fh:
            fh.write(lead + chunk)
        self.created.append(label)


def main(argv):
    root, runtime = parse_args(argv)
    if not root:
        root = stdin_cwd()
    root = logical_cd(root or logical_pwd())
    tpl = env("AI_PROJECT_TEMPLATES") or env("CLAUDE_ROUTING_TEMPLATES") \
        or os.path.join(HERE, "..", "skills", "project-init", "templates")
    if not os.path.isdir(tpl):
        raise Exit(1, "%s: templates not found at %s (run riskrails/install.sh)" % (NAME, tpl))
    on = runtimes(runtime, root)
    s = Scaffold(tpl, root)

    # shared SDLC
    s.put("sdlc-README.md", "docs/sdlc/README.md")
    s.put("intent.md", "docs/sdlc/intent/TEMPLATE.md")
    s.put("spec.md", "docs/sdlc/specs/TEMPLATE.md")
    s.put("plan.md", "docs/sdlc/plans/TEMPLATE.md")
    s.put("adr.md", "docs/sdlc/adr/TEMPLATE.md")
    s.put("constitution.md", "docs/sdlc/constitution.md", render=True)

    # per runtime
    if "claude" in on:
        s.put("project-settings.json", ".claude/settings.json")
        s.put("memory-README.md", ".claude/memory/README.md")
        s.keep(".claude/plans")
        s.keep(".claude/agents")
        s.keep(".claude/skills")
        s.put("CLAUDE.md", "CLAUDE.md", render=True)
    if "codex" in on:
        s.put("project-config.toml", ".codex/config.toml", render=True)
        s.put("memory-README.md", ".codex/memory/README.md")
        s.keep(".codex/plans")
        s.keep(".codex/agents")
        s.keep(".codex/skills")
        s.put("AGENTS.md", "AGENTS.md", render=True)
    if "gemini" in on:
        s.put("memory-README.md", ".gemini/memory/README.md")
        s.put("GEMINI.md", "GEMINI.md", render=True)
    if "junie" in on:
        s.put("memory-README.md", ".junie/memory/README.md")
        s.put("junie-guidelines.md", ".junie/guidelines.md", render=True)

    # .gitignore: append the snippet only if its first real entry is absent
    s.append_once(os.path.join(root, ".gitignore"), b".claude/settings.local.json", "gitignore.snippet",
                  ".gitignore (appended)")

    out = sys.stdout.buffer
    if not s.created:
        out.write(os.fsencode("%s: nothing to do in %s (already scaffolded)\n" % (NAME, root)))
    else:
        out.write(os.fsencode("%s: created in %s:\n" % (NAME, root)))
        for item in s.created:
            out.write(os.fsencode("  %s\n" % item))
    out.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exit as e:
        sys.stderr.buffer.write(os.fsencode(str(e) + "\n"))
        sys.exit(e.code)
    except OSError as e:
        sys.stderr.write("%s: %s\n" % (NAME, e))
        sys.exit(1)
