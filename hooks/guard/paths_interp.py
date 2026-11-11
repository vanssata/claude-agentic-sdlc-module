"""Interpreter one-liners and in-place edits: the patterns that scan the text of python -c, perl -e and
the like for a secret or a control-file write, the text-tool words that merely name them, and the two
rules inplace_edit and interpreter_text.

R16: every name here is core (no file, clock or subprocess access).
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import re
from guard.common import Deny
from guard.paths_base import WHY_APPROVE, WHY_SENSITIVE
from guard.paths_shell import shell_segments


# An interpreter one-liner is not parsed, its text is scanned: one that names a
# secret, or one that names a control file and looks like a write, is refused (H3).
INTERP_RE = ("(^|[|;&[:space:]])(python3?|perl|ruby|node|php)([[:space:]]+-[^[:space:]]+)*[[:space:]]+-(c|e)([[:space:]]|$)|"
             "(^|[|;&[:space:]])php([[:space:]]+-[^[:space:]]+)*[[:space:]]+-r([[:space:]]|$)")
CONTROL_TEXT_RE = "\\.ai/state/|\\.ai/reports/"
# perl or ruby with -i, behind any blank, separator, ( ` { or quote, so every wrapper and
# position is caught; Guard.inplace_edit carves out the segments of a text tool (grep, echo,
# git log ...) that merely name it. An -e/-E/-ne code argument may be one quoted word.
INPLACE_RE = ("(^|[|;&(`{'\"[:space:]])"
              "(perl|ruby)([[:space:]]+-([CEIMmr][[:space:]]*[^[:space:]]+|[a-zA-Z]*[eE][[:space:]]+('[^']*'|\"[^\"]*\")|"
              "[^[:space:]]+))*[[:space:]]+-[acdfghlnpsStTuUvwWXy]*i")
_TEXT_TOOLS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "echo", "printf"}
_GIT_TEXT = {"log", "grep", "commit", "show", "diff", "tag", "notes"}
_STD_WRITE = re.compile(r"(writeSync|writevSync)\([ \t]*(1|2|process\.std(out|err)\.fd)[ \t]*,|"
                        r"v?fprintf\([ \t]*STD(OUT|ERR)[ \t]*,")

_SHELL_SINKS = {"sh", "bash", "zsh", "dash", "ksh", "ssh", "source", ".", "eval"}
_XARGS_ARG = {"-I", "-n", "-P", "-L", "-s", "-E", "-d", "-a"}
_GIT_RUNS = ("GIT_", "PAGER", "EDITOR", "VISUAL", "SSH_COMMAND")
_GIT_CFG = re.compile(r"[A-Za-z0-9_.-]+=[A-Za-z0-9_./:-]*$")


def _tool_word(w):
    """The bare word, /bin/<w> or /usr/bin/<w>; any other path is a program of its own."""
    if w.startswith("/bin/"):
        return w[5:]
    if w.startswith("/usr/bin/"):
        return w[9:]
    return w


def shell_sink(seg):
    """A segment that runs its input or its arguments as shell text."""
    words = seg.split()
    if not words:
        return False
    w = _tool_word(words[0])
    if w in _SHELL_SINKS:
        return True
    return w == "xargs" and any(_tool_word(x) in _SHELL_SINKS for x in words[1:])


def _plain_text_tool(words, i, git_runs):
    if i >= len(words):
        return False
    w = _tool_word(words[i])
    if w in _TEXT_TOOLS:
        return True
    if w != "git" or git_runs:
        return False
    if any(x.startswith(("-O", "--open-files-in-pager", "--config-env")) for x in words[i + 1:]):
        return False
    k = i + 1
    while k < len(words):
        x = words[k]
        if x in ("-C", "-c"):
            if x == "-c" and (k + 1 >= len(words) or not _GIT_CFG.match(words[k + 1])):
                return False
            k += 2
        elif x.startswith("-"):
            k += 1
        else:
            return x in _GIT_TEXT
    return False


def text_tool_segment(seg, git_runs=False):
    """A segment whose command word is a text tool: a program named in it is an argument.
    xargs and find -exec are looked through; git_runs is set when the line may hand git a
    command to run (a stripped GIT_PAGER=... assignment)."""
    words = seg.split()
    if not words:
        return False
    w = _tool_word(words[0])
    if w == "xargs":
        i = 1
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in _XARGS_ARG else 1
        return _plain_text_tool(words, i, git_runs)
    if w == "find":
        found = False
        for k, x in enumerate(words):
            if x in ("-exec", "-execdir", "-ok", "-okdir"):
                if not _plain_text_tool(words, k + 1, git_runs):
                    return False
                found = True
        return found
    return _plain_text_tool(words, 0, git_runs)


EVAL_WORD_RE = "(^|[|;&[:space:]])eval([[:space:]]|$)"
SECRET_TEXT_RE = "\\.env|secrets?/|credentials?|id_rsa|\\.pem|\\.aws"
WRITE_CALL_RE = (
    "(^|[^A-Za-z0-9_])(write|writelines|write_text|write_bytes|write_file|writeFile|writeFileSync|appendFile|"
    "appendFileSync|createWriteStream|binwrite|syswrite|fwrite|fputs|fprintf|vfprintf|writeSync|writevSync|file_put_contents|dump|unlink|unlinkSync|"
    "remove|removedirs|rename|renames|renameSync|rmdir|rmdirSync|rm|rmSync|rmtree|mkdir|mkdirSync|makedirs|"
    "mkdtemp|truncate|truncateSync|ftruncate|symlink|symlinkSync|symlink_to|hardlink_to|link|linkSync|link_to|"
    "touch|chmod|chown|utime|utimes|copyFile|copyFileSync|cp|cpSync|move|delete|system|exec|execSync|execFile|"
    "execFileSync|spawn|spawnSync|popen|passthru|shell_exec|proc_open|fork|eval|copy_into|move_into)"
    "([[:space:]]*\\(|[[:space:]]+['\"$])|(^|[^A-Za-z0-9_.])copy[[:space:]]*\\(")
WRITE_WORD_RE = ("subprocess|shutil|child_process|FileUtils|Open3|O_(WRONLY|RDWR|CREAT|APPEND|TRUNC)|os\\.replace|"
                 "inplace|`|\\$\\(|%x[^A-Za-z0-9_[:space:]]|(^|[^A-Za-z0-9_])qx[^A-Za-z0-9_[:space:]]")
FIRST_ARG = "([^,()'\"]|'[^']*'|\"[^\"]*\"|\\(([^()]|\\([^()]*\\))*\\))*"
WRITE_PATHREPL_RE = "\\.replace[[:space:]]*\\(" + FIRST_ARG + "\\)"
WRITE_PATHCOPY_RE = "\\.copy[[:space:]]*\\([[:space:]]*[^)[:space:]]"
WRITE_MODE_RE = ("((open[A-Za-z]*|new([[:space:]]+[A-Za-z_][A-Za-z0-9_:]*)?|FileIO)[[:space:]]*(\\(|[[:space:]])"
                 + FIRST_ARG + ",|mode[[:space:]]*=|open[A-Za-z]*[[:space:]]*\\()[[:space:]]*\\\\?['\"]"
                 "([rbtU]*[wax+][rbtU+]*\\\\?['\"]|>|\\+|-?\\|[^[:space:]|])")
WRITE_REDIR_RE = (">[>|]?[[:space:]]*['\"]?[^[:space:]'\"|;&<>]*\\.ai/(state|reports)/|"
                  "(^|[^A-Za-z0-9_.-])tee[[:space:]][^|;&]*\\.ai/(state|reports)/")


def inplace_edit(self, cmd):
    """perl or ruby -i as a command: INPLACE_RE on the line less the segments of a text tool."""
    m = self.m
    if not m.ere_match(INPLACE_RE, cmd):
        return False
    if "<<" in cmd:                     # a heredoc body is read by whoever reads it
        return True
    segs = shell_segments(cmd).split("\n")
    if "|" in cmd and any(shell_sink(sg) for sg in segs):
        return True                     # a text tool's output may run as shell text
    git_runs = any(t in cmd for t in _GIT_RUNS)
    if git_runs and any(_tool_word(sg.split(None, 1)[0]) == "git" for sg in segs if sg.strip()):
        return True                     # the assignment that runs a command is not in the segment
    keep = [sg for sg in segs if not text_tool_segment(sg, git_runs)]
    return m.ere_match(INPLACE_RE, "\n".join(keep))


def interpreter_text(self, cmd):
    """The text of an interpreter one-liner or an eval, scanned whole (H3)."""
    m = self.m
    is_eval = m.ere_match(EVAL_WORD_RE, cmd)
    is_interp = m.ere_match(INTERP_RE, cmd)
    if (is_eval or is_interp) and m.ere_match(SECRET_TEXT_RE, cmd):
        raise Deny("Refusing an interpreter one-liner that references a sensitive path." + WHY_SENSITIVE)
    if m.ere_match(CONTROL_TEXT_RE, cmd):
        if is_eval or self.inplace_edit(cmd):
            raise Deny("Refusing an interpreter one-liner that writes the task's own control files." + WHY_APPROVE)
        if is_interp:
            scan = _STD_WRITE.sub(" ", cmd.replace("stdout.write", " ").replace("stderr.write", " "))
            pscan = cmd.replace("copy.copy(", " ")
            if (m.ere_match(WRITE_CALL_RE, scan) or m.ere_match(WRITE_WORD_RE, cmd)
                    or (m.ere_match("Path", cmd)
                        and (m.ere_match(WRITE_PATHREPL_RE, cmd) or m.ere_match(WRITE_PATHCOPY_RE, pscan)))
                    or (m.ere_match("open|new|FileIO", cmd) and m.ere_match(WRITE_MODE_RE, cmd))
                    or m.ere_match(WRITE_REDIR_RE, cmd)):
                raise Deny("Refusing an interpreter one-liner that writes the task's own control files."
                           + WHY_APPROVE)
