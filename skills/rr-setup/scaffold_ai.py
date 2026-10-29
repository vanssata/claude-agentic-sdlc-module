#!/usr/bin/env python3
"""Idempotent .ai/ scaffold for RiskRails.
  scaffold_ai.py [project-dir] [--runtime auto|claude|codex|both]   (default: $PWD, auto)
skills/ai-init/scaffold-ai.sh execs it; the templates stay in skills/ai-init/.

Never overwrites an existing file. Run it as often as you like: it creates what
is missing, reports what it created, and leaves everything else alone. That
matters because .ai/ is meant to be edited by humans after /rr-setup fills it.

There is exactly one `.ai/` tree however many agent runtimes the project uses:
the policies, weight table and task state are shared. Only the instruction file
that points at it differs — CLAUDE.md for Claude Code, AGENTS.md for Codex.

A port of the shell script it replaced, kept to its bytes: the same files and
modes, the same listing in the same order, the same messages and exit codes
(tests/test_scaffold_differential.py runs the frozen shell beside it).
"""
import errno
import json
import locale
import os
import re
import shutil
import stat
import sys

NAME = "scaffold-ai"
# The directory the shell script ran from: templates and the runtime it was installed for.
HERE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai-init"))
RUNTIMES = ("claude", "codex", "gemini", "junie")
BLOCK = re.compile(rb"<!-- (riskrails|claude-agentic|[Cc]odex-agentic):start -->")


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


def template_files(top):
    """`find "$top" -type f | sort`: regular files, no symlink followed, in the locale's collation."""
    if os.path.islink(top) or not os.path.isdir(top):
        return []
    found = []
    for d, _, files in os.walk(top):
        found += [os.path.join(d, f) for f in files if not os.path.islink(os.path.join(d, f))
                  and os.path.isfile(os.path.join(d, f))]
    try:
        locale.setlocale(locale.LC_COLLATE, "")
        # sort: strcoll first, the bytes when it ties.
        return sorted(found, key=lambda p: (locale.strxfrm(p), os.fsencode(p)))
    except (locale.Error, ValueError, UnicodeError):
        return sorted(found, key=os.fsencode)


def newline_lead(data):
    """`[ -s f ] && [ -n "$(tail -c1 f)" ] && echo`: a newline unless the file is empty
    or ends in one. `$(…)` drops a NUL last byte as it drops a newline, and says so."""
    if data[-1:] == b"\0":
        sys.stderr.write("%s: warning: command substitution: ignored null byte in input\n" % NAME)
    return b"\n" if data and data[-1:] not in (b"\n", b"\0") else b""


def append_block(path, chunk):
    """`{ [ -s f ] && [ -n "$(tail -c1 f)" ] && echo; echo; cat chunk; } >> f`."""
    with open(path, "rb") as fh:
        data = fh.read()
    lead = newline_lead(data)
    with open(path, "ab") as fh:
        fh.write(lead + b"\n" + chunk)


def main(argv):
    root, runtime = parse_args(argv)
    if not root:
        root = stdin_cwd()
    root = logical_cd(root or logical_pwd())
    project = os.fsencode("/" if root == "/" else os.path.basename(root))
    tpl = env("RISKRAILS_TEMPLATES") or env("CLAUDE_AGENTIC_TEMPLATES") or os.path.join(HERE, "templates")
    if not os.path.isdir(os.path.join(tpl, ".ai")):
        raise Exit(1, "%s: templates not found at %s (run riskrails/install.sh)" % (NAME, tpl))
    on = runtimes(runtime, root)
    created = []

    # A project that already has .ai/ carries a schema version this scaffold must not
    # invent: writing .ai/VERSION here would tell /project-update that every migration
    # has already run. Only a fresh tree starts at the shipped schema.
    had_ai = os.path.isdir(os.path.join(root, ".ai"))

    # Copy the .ai/ tree, file by file, skipping anything that already exists.
    top = os.path.join(tpl, ".ai")
    mask = umask()
    for src in template_files(top):
        rel = ".ai/" + os.path.relpath(src, top)
        dst = os.path.join(root, rel)
        if os.path.exists(dst) or (rel == ".ai/VERSION" and had_ai):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # cp: the source's permission bits, less the umask.
        shutil.copyfile(src, dst)
        os.chmod(dst, os.stat(src).st_mode & 0o777 & ~mask)
        created.append(rel)

    # .gitignore: append once, detected by the first real entry.
    gi = os.path.join(root, ".gitignore")
    try:
        with open(gi, "rb") as fh:
            current = fh.read()
    except FileNotFoundError:
        current = b""
    if b".ai/state/*.json" not in current:
        lead = newline_lead(current)
        with open(os.path.join(tpl, "gitignore.snippet"), "rb") as fh:
            snippet = fh.read()
        with open(gi, "ab") as fh:
            fh.write(lead + snippet)
        created.append(".gitignore (appended)")

    # The instruction file: create a minimal one if absent, then append the managed
    # block once. An existing file is never replaced — only appended to. A legacy
    # Codex-agentic pair is the block under its old name: nothing is appended beside
    # it; /project-update renames it.
    def instruction_file(name, minimal, block):
        md = os.path.join(root, name)
        os.makedirs(os.path.dirname(md), exist_ok=True)
        if not os.path.exists(md):
            with open(os.path.join(tpl, minimal), "rb") as fh:
                data = fh.read().replace(b"{{PROJECT}}", project)
            with open(md, "wb") as fh:
                fh.write(data)
            created.append(name)
        with open(md, "rb") as fh:
            has_block = BLOCK.search(fh.read())
        if not has_block:
            with open(os.path.join(tpl, block), "rb") as fh:
                append_block(md, fh.read())
            created.append(name + " (agent workflow block appended)")

    if "claude" in on:
        instruction_file("CLAUDE.md", "CLAUDE.minimal.md", "CLAUDE.block.md")
    if "codex" in on:
        instruction_file("AGENTS.md", "AGENTS.minimal.md", "AGENTS.block.md")
    if "gemini" in on:
        instruction_file("GEMINI.md", "GEMINI.minimal.md", "GEMINI.block.md")
    if "junie" in on:
        instruction_file(".junie/guidelines.md", "junie-guidelines.minimal.md", "junie-guidelines.block.md")

    out = sys.stdout.buffer
    if not created:
        out.write(os.fsencode("%s: nothing to do in %s (already scaffolded)\n" % (NAME, root)))
    else:
        out.write(os.fsencode("%s: created in %s:\n" % (NAME, root)))
        for item in created:
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
