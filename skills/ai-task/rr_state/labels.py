"""labels: the consent labels a decision may offer as commands -- the one-simple-command rule, the state.py command a label runs, and the absolute command the agent and the human share.

shell: validate_label, human_name, state_label
core: LABEL_MAX, LABEL_FORBIDDEN, INTERPRETER_RE, PUSH_REF_RE, INTERPRETER_FLAG_RE, NPX_PACKAGE_RE, label_argv, subcommand, state_label_ok, subcommand_prefix
"""

import os
import re
import shlex

from rr_state import fs

LABEL_MAX = 400
LABEL_FORBIDDEN = (";", "&", "|", "\n", "\r", "`", "$(", "<", ">")
INTERPRETER_RE = re.compile(r"^python3?$")   # a bare name: a path could be any program
PUSH_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")  # no '+' (a force push), no ':' (a refspec), no option
INTERPRETER_FLAG_RE = re.compile(r"^-[IS]+$")
NPX_PACKAGE_RE = re.compile(r"^riskrails@[0-9A-Za-z.+-]+$")


def label_argv(label):
    """(script, argv) when a label runs a state.py, else None."""
    try:
        tokens = shlex.split(label)
    except ValueError:
        return None
    if not tokens or not INTERPRETER_RE.match(tokens[0]):
        return None
    i = 1
    while i < len(tokens) and INTERPRETER_FLAG_RE.match(tokens[i]):
        i += 1
    if i >= len(tokens) or os.path.basename(tokens[i]) != "state.py":
        return None
    return tokens[i], tokens[i + 1:]


def subcommand(argv):
    """argv without the global options: what the command is."""
    rest = list(argv)
    while rest[:1] in (["--root"], ["--runtime"]) and len(rest) >= 2:
        rest = rest[2:]
    return rest


def state_label_ok(argv):
    """approve | reject | profile set | verify --by | review --by | start --mode … --by."""
    rest = subcommand(argv)
    if rest[:1] in (["approve"], ["reject"]) or rest[:2] == ["profile", "set"]:
        return True
    if rest[:1] in (["verify"], ["review"]):
        return "--by" in rest
    return rest[:1] == ["start"] and "--mode" in rest and "--by" in rest


def validate_label(label):
    """None when `label` may be offered as a command (R36.4), else why not."""
    if not isinstance(label, str) or not label or label != label.strip():
        return "a label is a non-empty string without surrounding blanks"
    if len(label) > LABEL_MAX or not label.isprintable():
        return "a label is at most %d printable characters" % LABEL_MAX
    bad = [c for c in LABEL_FORBIDDEN if c in label]
    if bad:
        return "a label is one simple command (it contains %s)" % " ".join(repr(c) for c in bad)
    try:
        tokens = shlex.split(label)
    except ValueError as exc:
        return "a label must split as a shell command (%s)" % exc
    if tokens[:2] == ["git", "commit"]:
        return None
    if tokens[:2] == ["git", "push"]:
        return None if len(tokens) == 4 and all(PUSH_REF_RE.match(t) and not t.startswith("-")
                                                for t in tokens[2:]) else \
            "a push label is exactly 'git push <remote> <branch>', no '+', ':' or option"
    if tokens[:1] == ["npx"] and len(tokens) >= 3 and NPX_PACKAGE_RE.match(tokens[1]) and tokens[-1] == "--yes":
        return None
    script = label_argv(label)
    if script and os.path.realpath(script[0]) == os.path.realpath(fs.ENTRY) \
            and state_label_ok(script[1]):
        return None
    return ("a label starts with git commit, git push <remote> <branch>, state.py approve|reject|"
            "profile set|verify --by|review --by|start --mode --by, or npx riskrails@<v> … --yes")


def human_name(root):
    """Who the labels name as --by: the repository's git user, else $USER."""
    return fs.one_line(fs.run_text(root, ["git", "config", "user.name"]) or os.environ.get("USER") or "human", 80)


def state_label(root, argv):
    """The command that runs this state.py with argv: absolute, quoted, with
    --root, so the human's pick and the agent's call are one string."""
    if "--root" not in subcommand_prefix(argv):
        argv = ["--root", root] + list(argv)
    return "python3 %s %s" % (shlex.quote(fs.ENTRY), shlex.join(argv))


def subcommand_prefix(argv):
    """The global options in front of the subcommand."""
    return list(argv)[:len(argv) - len(subcommand(argv))]
