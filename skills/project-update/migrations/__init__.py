"""Schema migrations for /project-update.

A project's schema is the integer in .ai/VERSION (missing = 0). Each migration is
one module NNNN_slug.py in this directory, numbered contiguously from 0001:

  VERSION = 1                      # equals the NNNN prefix
  TITLE = "one line"               # shown in the dry run
  MOVES = [("src", "dst"), ...]    # project-relative, static; the only moves plan() may make
  def plan(ctx): ...               # records operations on update.py's MigrationContext

update.py runs every migration with version < VERSION <= CURRENT before the
three-way merge. There is no down(): moves and deletions keep the original under
.ai/reports/project-update-<date>/original/.

CLAUDE_AGENTIC_MIGRATIONS points the registry at another directory (tests).
"""
import importlib.util, os, posixpath, re, sys

DIR = os.environ.get("CLAUDE_AGENTIC_MIGRATIONS", os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"(\d{4})_[a-z0-9_]+\.py")

# History keys of templates the plugin stopped shipping without a move: a project
# may still carry them, and they must not count as orphans.
RETIRED = []


class SchemaError(Exception):
    pass


def _files():
    try:
        names = sorted(os.listdir(DIR))
    except OSError as exc:
        raise SchemaError("migrations directory unreadable: %s" % exc) from exc
    return [n for n in names if n.endswith(".py") and n != "__init__.py"]


def _path_error(path):
    """Why a MOVES path is unusable, or None. Paths are project-relative and
    normalised, so template_key() and the plan's targets see one spelling."""
    if not isinstance(path, str) or not path:
        return "not a path"
    if path in (".", "..") or path.startswith(("/", "../")) or path.endswith("/") \
            or posixpath.normpath(path) != path:
        return "not a normalised project-relative file path"
    return None


def _check(mod, name, num, vacated):
    """Validate one loaded module; vacated holds the MOVES sources of earlier migrations."""
    sources = set()
    version = getattr(mod, "VERSION", None)
    if type(version) is not int or version != num:  # pylint: disable=unidiomatic-typecheck  # True == 1
        raise SchemaError("%s: VERSION is %r, the file name says %d" % (name, version, num))
    title = getattr(mod, "TITLE", None)
    if not isinstance(title, str) or not title.strip() or "\n" in title or "\r" in title:
        raise SchemaError("%s: TITLE must be one non-empty line" % name)
    moves = getattr(mod, "MOVES", None)
    if not isinstance(moves, list):
        raise SchemaError("%s: MOVES must be a list of (src, dst) path pairs" % name)
    for pair in moves:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise SchemaError("%s: MOVES must be a list of (src, dst) path pairs" % name)
        src, dst = pair
        for path in (src, dst):
            why = _path_error(path)
            if why:
                raise SchemaError("%s: MOVES path %r is %s" % (name, path, why))
        if src == dst:
            raise SchemaError("%s: MOVES pair %r moves a file onto itself" % (name, src))
        if src in vacated or src in sources:
            raise SchemaError("%s: MOVES source %r was already moved away" % (name, src))
        sources.add(src)
    # A path once moved away is never a destination again, in this migration or a
    # later one: its history key would then name two templates, and rename chains
    # could loop.
    for src, dst in moves:
        if dst in vacated or dst in sources:
            raise SchemaError("%s: MOVES destination %r is a path that was moved away" % (name, dst))
    if not callable(getattr(mod, "plan", None)):
        raise SchemaError("%s: no plan(ctx) function" % name)


def _current():
    nums = [int(m.group(1)) for m in map(NAME_RE.fullmatch, _files() if os.path.isdir(DIR) else []) if m]
    return max(nums, default=0)


CURRENT = _current()
_loaded = None


def load():
    """Every migration module, oldest first. Raises SchemaError on a misnamed file,
    a gap, a duplicate, a VERSION that differs from its prefix, a missing field,
    or an unusable MOVES pair. Call it before trusting CURRENT, which is read from
    the file names alone."""
    global _loaded  # pylint: disable=global-statement  # loaded once per run
    if _loaded is not None:
        return _loaded
    by_num = {}
    for name in _files():
        m = NAME_RE.fullmatch(name)
        if not m:
            raise SchemaError("%s: not a migration name (NNNN_slug.py)" % name)
        num = int(m.group(1))
        if num < 1:
            raise SchemaError("%s: migrations are numbered from 0001" % name)
        if num in by_num:
            raise SchemaError("%s: duplicate migration %04d" % (name, num))
        spec = importlib.util.spec_from_file_location("claude_agentic_migration_%04d" % num, os.path.join(DIR, name))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # dataclasses and pickle look the module up by name
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:  # pylint: disable=broad-exception-caught  # any import failure is a broken registry
            del sys.modules[spec.name]
            raise SchemaError("%s: cannot be loaded: %s: %s" % (name, type(exc).__name__, exc)) from exc
        by_num[num] = (name, mod)
    nums = sorted(by_num)
    if nums != list(range(1, len(nums) + 1)):
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        raise SchemaError("migrations are not contiguous from 0001: missing %s" % ", ".join("%04d" % n for n in missing))
    vacated = set()
    for n in nums:  # in order, so "moved away earlier" means earlier
        name, mod = by_num[n]
        _check(mod, name, n, vacated)
        vacated.update(src for src, _ in mod.MOVES)
    _loaded = [by_num[n][1] for n in nums]
    return _loaded


def template_key(target, mapped=None):
    """The history key of the template shipped at a project path, or None.
    mapped: {project target: "project-init/<template>"} for templates that land
    outside .ai/. The caller builds it from update.py's PROJECT_INIT_MAP and the
    RUNTIME_MAP entries of every runtime, not only the project's, so a rename
    resolves the same way for Claude, Codex and dual-runtime projects."""
    if target.startswith(".ai/"):
        return "ai-init/" + target
    return (mapped or {}).get(target)


def renames(mapped=None):
    """{new history key: [old history keys, oldest migration first]} from every
    migration's MOVES. A move between paths without history adds nothing. Chains
    (A -> B, then B -> C) appear hop by hop. load() rules out cycles between paths;
    two paths can share a history key (the per-runtime memory README), so a cycle
    between keys is refused here too, and the map is always acyclic."""
    out = {}
    for mod in load():
        for src, dst in mod.MOVES:
            old, new = template_key(src, mapped), template_key(dst, mapped)
            if old and new and old != new and old not in out.setdefault(new, []):
                out[new].append(old)

    def walk(key, seen):
        for old in out.get(key, []):
            if old in seen:
                raise SchemaError("MOVES make the history of %s a cycle through %s" % (key, old))
            walk(old, seen | {old})
    for key in out:
        walk(key, {key})
    return out
