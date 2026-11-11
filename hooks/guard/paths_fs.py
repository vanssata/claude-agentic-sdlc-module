"""The path guard's stand-ins for the shell's file tools: realpath -m (realpath_m), find -prune -o
-print (find_print), the lexical clean-up (lexnorm), cd -P (cd_physical) and the anchored-pattern list
(anchor_list), with the LoopError they raise.

R16: shell (they read the file system, the clock or a subprocess): realpath_m, find_print, cd_physical; every other name here is core.
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
import os
import stat
from guard.common import b_bytes, bytes_b, herestring_lines, is_dir


class LoopError(OSError):
    """A path that does not resolve: realpath prints an error, not a line."""


def realpath_m(path):
    """`realpath -m` of one absolute path: every link that exists resolved,
    what does not exist appended as written, `..` after resolution; a symlink
    loop raises LoopError."""
    seen = {}

    def join(base, rest):
        if rest.startswith(b"/"):
            base = b"/"
        for name in rest.split(b"/"):
            if name in (b"", b"."):
                continue
            if name == b"..":
                base = os.path.dirname(base) if base != b"/" else base
                continue
            new = base.rstrip(b"/") + b"/" + name
            try:
                is_link = stat.S_ISLNK(os.lstat(new).st_mode)
            except OSError:
                is_link = False
            if not is_link:
                base = new
                continue
            if new in seen:
                if seen[new] is None:
                    raise LoopError()
                base = seen[new]
                continue
            seen[new] = None
            try:
                target = os.readlink(new)
            except OSError as exc:
                raise LoopError() from exc
            base = join(base, target)
            seen[new] = base
        return base

    try:
        return bytes_b(join(b"/", b_bytes(path)))
    except RecursionError as exc:
        raise LoopError() from exc


def find_print(start, maxdepth, prune):
    """`find START -maxdepth N \\( -name A -o … \\) -prune -o -print`, in
    name order (not find's readdir order), links not followed, errors silent."""
    def walk(path, name, depth):
        if name in prune:
            return
        yield path
        if depth >= maxdepth:
            return
        try:
            with os.scandir(b_bytes(path)) as it:
                entries = list(it)
        except OSError:
            return
        # by name, not readdir order: which held file a refusal names must not depend
        # on the filesystem (ext4 here put .ai/policies first, the CI runner .ai/state)
        for e in sorted(entries, key=lambda e: e.name):
            try:
                is_d = e.is_dir(follow_symlinks=False)
            except OSError:
                is_d = False
            child = (path.rstrip("/") if path != "/" else "") + "/" + bytes_b(e.name)
            if is_d:
                yield from walk(child, bytes_b(e.name), depth + 1)
            elif bytes_b(e.name) not in prune:
                yield child
    base = start.rstrip("/").rsplit("/", 1)[-1] if start.rstrip("/") else "/"
    try:
        st = os.lstat(b_bytes(start))
    except OSError:
        return
    if stat.S_ISLNK(st.st_mode):
        if base not in prune:
            yield start                     # -P: a start that is a link is not entered
        return
    yield from walk(start, base, 0)


def lexnorm(path):
    """lexnorm: //, /./ and /../ resolved by text, no trailing slash."""
    out = []
    rest = path[1:] if path.startswith("/") else path
    for seg in (rest + "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
        else:
            out.append(seg)
    return "/" + "/".join(out) if out else "/"


def cd_physical(d):
    """$PWD after `cd -P -- "$d"`, or None when cd fails."""
    try:
        if not (is_dir(d) and os.access(b_bytes(d), os.X_OK)):
            return None
        return bytes_b(os.path.realpath(b_bytes(d)))
    except (OSError, ValueError):
        return None


def anchor_list(patterns):
    """[(anchored regex, pattern as written, matched against the absolute path)]."""
    out = []
    for p in herestring_lines(patterns):
        if not p:
            continue
        if p.startswith("(^|/)"):
            out.append(("^" + p[5:], p, False))
        elif p.startswith("^"):
            out.append((p, p, True))
        elif p.startswith("/"):
            out.append(("^" + p[1:], p, False))
        else:
            out.append(("(^|/)(" + p + ")", p, False))
    return out
