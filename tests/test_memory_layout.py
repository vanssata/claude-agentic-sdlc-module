#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Layout of the split of skills/ai-task/memory_sync.py into ten sibling modules memory_io, memory_config,
memory_packages, memory_verify, memory_hook, memory_risks, memory_cleanup, memory_migrate, memory_export and
memory_status, memory_sync.py staying the pre-push validator entry (small-oop-modules WP4: R2, R3, R4, R6, R6a,
R10, R15, R16; decisions D1, D2, D5, D6 of docs/sdlc/plans/small-oop-modules-wp4.md).

tests/fixtures/memory/partition.json is the authority: which module owns which name, the layer of each module,
core or shell per name, the signature each function has today, the module import edges, the entry's contract.
The call graph is read from memory_sync.py with `ast` in this file; no tool is needed.

Three phases, told by what is on disk (nothing to flip when a step lands):

  single (none of the ten modules exists, memory_sync.py is whole) - the partition against memory_sync.py:
    every top-level name is in it exactly once and vice versa (HERE, new in D2, aside), kinds, signatures and
    values match, the recorded edges are the call graph's, every edge goes to a lower layer and there is no
    cycle (R10, on paper), a core name touches no file, clock or subprocess and refers to no shell name (R16),
    no `global`.
  copy (some of the ten exist, memory_sync.py is still whole) - the single checks, and each module present is
    checked on its own: exactly the partition's names, signatures, values, no `global`, `__file__` only in
    memory_io, no `from memory_<x> import` / `from json import` / `from os import`, imports that match the
    recorded edges and go downward, `basename(memory_io.SELF) == "memory_sync.py"` (D2).
  final (memory_sync.py defines only the entry's four names) - everything in `layout_problems`: the entry under
    150 lines with D1's four defs, no re-export, its sys.path line before any sibling import; all ten modules
    present and each the partition's; the real import graph (R10); no `global`, one `__file__` in memory_io and
    one in the entry (R4, R6a); the forbidden constructs of R4; nothing under skills/ and tests/ imports
    memory_sync (R6; hooks/memory-pre-push.py is the one importer, D1); no import of hooks/ from the modules
    (R15); sizes printed (600 lines advisory).

`layout_problems` takes the tree to read, so TestSyntheticTree runs it on a small tree built in a temporary
directory and shows that each check can fail, before the real tree reaches the final phase.
"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTITION = os.path.join(ROOT, "tests", "fixtures", "memory", "partition.json")
SKILL_REL = os.path.join("skills", "ai-task")
THIS = os.path.basename(os.path.abspath(__file__))
IO_IMPORTS = {"os", "subprocess", "time", "fcntl"}
IO_ROOTS = {"subprocess", "time", "shutil", "tempfile", "sys", "importlib", "fcntl"}
PURE_PATH = {"join", "dirname", "basename", "normpath", "sep", "splitext", "split", "isabs",
             "relpath", "commonpath"}
PURE_OS = {"sep", "linesep", "pathsep", "curdir", "pardir", "fspath", "fsdecode", "fsencode"}
BARE_IO = {"open", "print", "input", "exec", "eval", "__import__"}
FORBIDDEN_NAMES = {"ABC", "abstractmethod", "Protocol", "staticmethod"}
IMPORTERS = {"sibling", "import_module", "__import__"}
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
          ast.GeneratorExp)
ADVISORY_LINES = 600


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse(path):
    return ast.parse(read_text(path), filename=path)


def read_partition(path=PARTITION):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def skill_dir(base):
    return os.path.join(base, SKILL_REL)


def entry_path(base, part):
    return os.path.join(skill_dir(base), part["entry"]["module"] + ".py")


def new_modules(part):
    """The modules the split adds: every module of the partition but the entry."""
    return sorted(m for m in part["modules"] if m != part["entry"]["module"])


def present_modules(base, part):
    return [m for m in new_modules(part) if os.path.isfile(os.path.join(skill_dir(base), m + ".py"))]


def line_count(path):
    return len(read_text(path).splitlines())


# --------------------------------------------------------------------------------------
# reading a module with ast: names, signatures, values, references


def canon(node):
    """A text of an ast value that is the same on every Python the suite runs on (ast.dump is not:
    3.13 leaves empty fields out)."""
    if isinstance(node, ast.AST):
        fields = [(k, getattr(node, k, None)) for k in node._fields]  # pylint: disable=protected-access
        return "%s(%s)" % (type(node).__name__, ",".join(
            "%s=%s" % (k, canon(v)) for k, v in fields if v is not None and v != []))
    if isinstance(node, list):
        return "[%s]" % ",".join(canon(v) for v in node)
    return repr(node)


def hash_of(value):
    return hashlib.sha1(canon(value).encode()).hexdigest()[:12]


def target_names(target):
    """The names an assignment target binds: `a`, `a, b`, not `a.b` or `a[b]`."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for item in target.elts for n in target_names(item)]
    if isinstance(target, ast.Starred):
        return target_names(target.value)
    return []


def statement_names(node):
    """[(name, value-node or None)] a top-level statement defines: a def, a class, an assignment
    (tuple targets included) and what a `try: import x / except: x = None` binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [(node.name, None)]
    if isinstance(node, ast.Assign):
        single = len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        return [(n, node.value if single else None) for t in node.targets for n in target_names(t)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [(node.target.id, node.value)]
    if isinstance(node, ast.Try):
        inner = list(node.body) + list(node.orelse) + list(node.finalbody) + \
            [s for h in node.handlers for s in h.body]
        found = []
        for stmt in inner:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                found += [((a.asname or a.name).split(".")[0], None) for a in stmt.names]
            else:
                found += statement_names(stmt)
        return found
    return []


def kind_of(node):
    return "function" if isinstance(node, ast.FunctionDef) else "class" if isinstance(node, ast.ClassDef) \
        else "const"


def module_names(tree):
    """{name: (kind, node, value)} of what a module defines at its top level."""
    found = {}
    for node in tree.body:
        for name, value in statement_names(node):
            found.setdefault(name, (kind_of(node), node, value))
    return found


def signature_of(node):
    return "(%s)" % ast.unparse(node.args) if isinstance(node, ast.FunctionDef) else ""


def own_stores(scope):
    """The names a function-like scope binds itself: not what its nested scopes bind."""
    names = set()
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, SCOPES):
            continue
        else:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
            stack.extend(ast.iter_child_nodes(node))
    return names


def bound_in(node):
    """What a scope binds for the code inside it."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
        names.update(a.arg for a in (args.vararg, args.kwarg) if a)
        return names | (own_stores(node) if not isinstance(node, ast.Lambda) else set())
    return {n for gen in node.generators for n in target_names(gen.target)}


def references(node, names):
    """The names of `names` that a top-level statement refers to, minus those a function-like scope
    inside it binds for itself (a parameter called `read` is not the module's `read`)."""
    found = set()

    def visit(item, shadow):
        if isinstance(item, SCOPES):
            shadow = shadow | bound_in(item)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
            if item.id in names and item.id not in shadow:
                found.add(item.id)
        for child in ast.iter_child_nodes(item):
            visit(child, shadow)
    visit(node, frozenset())
    return found


def call_graph(tree):
    """{name: set(top-level names it refers to)} of a file, a name's own name left out."""
    defs = module_names(tree)
    return {name: references(node, set(defs)) - {name} for name, (_kind, node, _value) in defs.items()}


def reaches_io(node):
    """The first thing in a statement that touches a file, the clock, a process or the screen, or ''."""
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and item.id in BARE_IO:
            return item.id
        if not isinstance(item, ast.Attribute):
            continue
        chain, root = [], item
        while isinstance(root, ast.Attribute):
            chain.append(root.attr)
            root = root.value
        chain.reverse()
        if not isinstance(root, ast.Name):
            continue
        if root.id in IO_ROOTS:
            return root.id
        if root.id == "os" and chain != ["path"] and chain[0] not in PURE_OS \
                and not (chain[0] == "path" and chain[1] in PURE_PATH):
            return "os." + ".".join(chain)
        if root.id == "datetime" and chain[0] in ("now", "utcnow", "today"):
            return "datetime." + chain[0]
        if root.id == "json" and chain[0] in ("dump", "load"):
            return "json." + chain[0]
    return ""


def param_tokens(signature):
    """The parameters of a signature string as comparable tokens."""
    args = ast.parse("def f%s: pass" % signature).body[0].args
    plain = args.posonlyargs + args.args
    defaults = [None] * (len(plain) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(plain, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    tokens = ["%s=%s" % (a.arg, ast.unparse(d)) if d is not None else a.arg for a, d in pairs]
    tokens += ["*" + a.arg for a in (args.vararg,) if a] + ["**" + a.arg for a in (args.kwarg,) if a]
    return tokens


# --------------------------------------------------------------------------------------
# the partition and the graph


def owners_of(part):
    owner = {}
    for mod, spec in part["modules"].items():
        for name in spec["defs"]:
            owner.setdefault(name, []).append(mod)
    return owner


def module_edges(part, graph):
    """{module: {module it must import}} from a call graph."""
    owner = owners_of(part)
    edges = {mod: set() for mod in part["modules"]}
    for name, refs in graph.items():
        if name not in owner:
            continue
        for ref in refs:
            if ref in owner and owner[ref][0] != owner[name][0]:
                edges[owner[name][0]].add(owner[ref][0])
    return edges


def graph_problems(layer, edges):
    """An upward or same-layer edge, an edge to an unknown module, a cycle: the list of them (R10)."""
    problems = []
    for mod, deps in sorted(edges.items()):
        for dep in sorted(deps):
            if dep not in layer:
                problems.append("%s imports %s, which is not a module of the partition" % (mod, dep))
            elif layer[dep] >= layer[mod]:
                problems.append("upward edge: %s (layer %d) imports %s (layer %d)"
                                % (mod, layer[mod], dep, layer[dep]))
    colour = {}

    def visit(node, path):
        if colour.get(node) == 1:
            problems.append("cycle: %s" % " -> ".join(path[path.index(node):] + [node]))
        elif node not in colour:
            colour[node] = 1
            for dep in sorted(edges.get(node, ())):
                visit(dep, path + [node])
            colour[node] = 2
    for mod in sorted(edges):
        visit(mod, [])
    return problems


def label_problems(part, graph, nodes):
    """R16: a core name touches no file, clock or subprocess and refers to no shell name."""
    problems = []
    for name, rec in sorted(part["defs"].items()):
        if rec["label"] != "core" or name not in nodes:
            continue
        hit = reaches_io(nodes[name])
        if hit:
            problems.append("core name %s reaches I/O (%s)" % (name, hit))
        problems += ["core name %s refers to the shell name %s" % (name, ref)
                     for ref in sorted(graph[name]) if part["defs"].get(ref, {}).get("label") == "shell"]
    return problems


def layers_of(part):
    return {m: s["layer"] for m, s in part["modules"].items()}


# --------------------------------------------------------------------------------------
# the real import lines of a module


def imports_of(tree):
    """[(line, dotted module, [names taken], is_from)] of every import statement of a tree."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, a.name, [], False) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.lineno, ("." * node.level) + (node.module or ""), [a.name for a in node.names], True))
    return found


def sibling_imports(tree, mods):
    """The modules of `mods` a tree imports, by `import m`, `import m as x` or `from m import y`."""
    return {m.split(".")[0] for _line, m, _names, _from in imports_of(tree) if m.split(".")[0] in mods}


def seam_problems(mod, tree):
    """D5, R6: a name taken out of a sibling, json or os at import escapes a patch on its attribute;
    the code reads `mio.crash` at call time so a suite's patch reaches it."""
    problems = []
    for line, base, names, is_from in imports_of(tree):
        if not is_from:
            continue
        if base.startswith("."):
            problems.append("%s:%d relative import" % (mod, line))
        elif base == "json" or base == "os" or base.startswith("os."):
            problems.append("%s:%d from %s import %s (D5: keep it a module attribute)" % (mod, line, base, ", ".join(names)))
        elif base.startswith("memory_"):
            problems.append("%s:%d from %s import %s (D5: `import %s`, call `%s.<name>`)" % (
                mod, line, base, ", ".join(names), base, base))
    return problems


def hooks_problems(mod, tree):
    """R15: nothing under the new modules imports anything of hooks/."""
    return ["%s:%d imports %s (R15)" % (mod, line, base) for line, base, _n, _f in imports_of(tree)
            if base.split(".")[0] in ("hooks", "guard") or base.startswith("memory-pre-push")
            or base.split(".")[0] == "memory_pre_push"]


def file_uses(tree):
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]


def self_problems(base, part):
    """D2: memory_io.SELF is the entry beside it, run as a script by every shim; VALIDATOR is the hook."""
    wanted = part["entry"]["module"] + ".py"
    code = ("import os, sys; sys.path.insert(0, %r); import memory_io; "
            "print(memory_io.SELF); print(memory_io.VALIDATOR)" % skill_dir(base))
    done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True,
                          check=False, timeout=60)
    if done.returncode != 0:
        return ["memory_io does not import: %s" % (done.stderr.strip().splitlines() or ["exit %d" % done.returncode])[-1]]
    found = done.stdout.splitlines()
    problems = []
    if os.path.basename(found[0]) != wanted:
        problems.append("basename(memory_io.SELF) is %s, not %s (D2: a shim would run a module with no main)"
                        % (os.path.basename(found[0]), wanted))
    elif os.path.dirname(os.path.realpath(found[0])) != os.path.realpath(skill_dir(base)):
        problems.append("memory_io.SELF %s is not beside memory_io.py" % found[0])
    if os.path.basename(found[1]) != "memory-pre-push.py":
        problems.append("basename(memory_io.VALIDATOR) is %s, not memory-pre-push.py" % os.path.basename(found[1]))
    return problems


def module_problems(part, mod, path):
    """Everything wrong with one module file against the partition; [] when it is right."""
    if mod not in part["modules"] or mod == part["entry"]["module"]:
        return ["%s: not one of the new modules of the partition" % mod]
    spec = part["modules"][mod]
    tree = ast.parse(read_text(path), filename=path)
    problems = []
    found = module_names(tree)
    wanted = set(spec["defs"])
    problems += ["%s: missing %s" % (mod, n) for n in sorted(wanted - set(found))]
    problems += ["%s: %s is not the partition's" % (mod, n) for n in sorted(set(found) - wanted)]
    for name, (kind, node, value) in found.items():
        rec = part["defs"].get(name)
        if not rec or name not in wanted:
            continue
        if rec["kind"] != kind:
            problems.append("%s: %s is a %s, the partition says %s" % (mod, name, kind, rec["kind"]))
        elif kind == "function":
            sig = signature_of(node)
            if param_tokens(sig) != param_tokens(rec["signature"]):
                problems.append("%s: %s%s, the partition has %s%s" % (mod, name, sig, name, rec["signature"]))
        elif rec["value_hash"] and value is not None and hash_of(value) != rec["value_hash"]:
            problems.append("%s: %s has another value than memory_sync.py's" % (mod, name))
    problems += ["%s:%d `global %s` (R4)" % (mod, n.lineno, ", ".join(n.names)) for n in ast.walk(tree)
                 if isinstance(n, ast.Global)]
    uses = file_uses(tree)
    if mod == "memory_io":
        if len(uses) != 1:
            problems.append("memory_io: %d uses of __file__, exactly one is HERE's (R6a, D2)" % len(uses))
    else:
        problems += ["%s:%d __file__ (R6a: only memory_io has one, as HERE)" % (mod, n) for n in uses]
    problems += seam_problems(mod, tree) + hooks_problems(mod, tree)
    layer = layers_of(part)
    real = sibling_imports(tree, set(part["modules"]))
    problems += graph_problems(layer, {mod: real})
    if mod in real:
        problems.append("%s imports itself" % mod)
    if real != set(spec["imports"]):
        problems.append("%s imports %s, the partition has %s" % (mod, sorted(real), spec["imports"]))
    labels = {part["defs"][n]["label"] for n in spec["defs"] if n in part["defs"]}
    if labels == {"core"}:
        io_names = {b.split(".")[0] for _l, b, _n, _f in imports_of(tree)} & IO_IMPORTS
        problems += ["%s: all names are core, yet it imports %s (R16)" % (mod, n) for n in sorted(io_names)]
    return problems


def r4_problems(part, trees):
    """R4: only the partition's classes and namedtuples, no ABC, Protocol or staticmethod."""
    problems, classes, tuples = [], set(), set()
    for mod, tree in sorted(trees.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
                problems += ["%s:%d class %s(%s): a base other than Exception" % (
                    mod, node.lineno, node.name, ast.unparse(b)) for b in node.bases if ast.unparse(b) != "Exception"]
            elif isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] == "namedtuple":
                tuples.add(node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else "?")
            if isinstance(node, ast.Name):
                used = {node.id}
            elif isinstance(node, ast.Attribute):
                used = {node.attr}
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                used = {a.name.split(".")[-1] for a in node.names}
            else:
                used = set()
            problems += ["%s:%d uses %s (R4)" % (mod, node.lineno, hit) for hit in sorted(used & FORBIDDEN_NAMES)]
    if classes != set(part["classes"]):
        problems.append("classes are %s, R4 allows %s" % (sorted(classes), sorted(part["classes"])))
    if tuples != set(part["namedtuples"]):
        problems.append("namedtuples are %s, R4 allows %s" % (sorted(tuples), sorted(part["namedtuples"])))
    return problems


def entry_problems(part, path):
    """R2, D1, Q25: the entry is small, defines D1's names, imports only memory_io and memory_verify among
    the siblings, re-exports nothing, and sets sys.path before its first sibling import."""
    spec = part["entry"]
    text = read_text(path)
    tree = ast.parse(text, filename=path)
    problems = []
    count = len(text.splitlines())
    if count >= spec["max_lines"]:
        problems.append("%s has %d lines, the limit is under %d (R2)" % (spec["module"], count, spec["max_lines"]))
    defined = set(module_names(tree))
    wanted = set(part["modules"][spec["module"]]["defs"])
    problems += ["%s defines %s, D1 has %s" % (spec["module"], sorted(defined - wanted), sorted(wanted))
                 for _ in [0] if defined != wanted]
    doc = ast.get_docstring(tree, clean=False) or ""
    if hashlib.sha256(doc[:part["entry_docstring_chars"]].encode()).hexdigest() != part["entry_docstring_sha256"]:
        problems.append("%s lost the first %d characters of its docstring" % (spec["module"], part["entry_docstring_chars"]))
    problems += ["%s:%d `__all__` re-exports (Q25)" % (spec["module"], n.lineno) for n in tree.body
                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)]
    problems += seam_problems(spec["module"], tree)
    problems += ["%s:%d imports %s, R2 allows %s" % (spec["module"], line, base, spec["may_import"])
                 for line, base, _n, _f in imports_of(tree)
                 if base.split(".")[0].startswith("memory_") and base.split(".")[0] not in spec["may_import"]]
    inserts = [n.lineno for n in tree.body if isinstance(n, ast.Expr) and ast.unparse(n.value) == spec["sys_path_line"]]
    firsts = [line for line, base, _n, _f in imports_of(tree) if base.split(".")[0].startswith("memory_")]
    if len(inserts) != 1:
        problems.append("%s: `%s` appears %d times, exactly once" % (spec["module"], spec["sys_path_line"], len(inserts)))
    elif firsts and min(firsts) < inserts[0]:
        problems.append("%s: a sibling is imported at line %d, before the sys.path line %d" % (
            spec["module"], min(firsts), inserts[0]))
    uses = file_uses(tree)
    if len(uses) != 1 or (inserts and uses != inserts):
        problems.append("%s: __file__ at lines %s, only the sys.path line's (R6a)" % (spec["module"], uses))
    return problems


MEMORY_SYNC_STRING = re.compile(r"(?<![\w.])(?:import memory_sync(?![\w])|from memory_sync import)")


def memory_sync_uses(path, tree):
    """What a file does to import memory_sync: an import statement, `import memory_sync` in a string,
    sibling(DIR, "memory_sync") and the like."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found += ["%s:%d %s" % (path, line, ("from " if is_from else "import ") + base)
                      for line, base, _n, is_from in [x for x in imports_of(node) if x[1].split(".")[0] == "memory_sync"]]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and MEMORY_SYNC_STRING.search(node.value):
            found.append("%s:%d `%s` in a string" % (path, node.lineno, MEMORY_SYNC_STRING.search(node.value).group(0)))
        elif isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] in IMPORTERS:
            found += ["%s:%d %s(... %r)" % (path, node.lineno, ast.unparse(node.func), a.value) for a in node.args
                      if isinstance(a, ast.Constant) and a.value == "memory_sync"]
    return found


def importer_problems(base, part):
    """R6: nothing under skills/ and tests/ imports the entry; hooks/ is the one importer (D1)."""
    problems = []
    own = os.path.abspath(entry_path(base, part))
    for top in ("skills", "tests"):
        for here, _dirs, files in os.walk(os.path.join(base, top)):
            for name in sorted(files):
                path = os.path.join(here, name)
                if not name.endswith(".py") or os.path.abspath(path) == own or (top == "tests" and name == THIS):
                    continue
                try:
                    tree = parse(path)
                except SyntaxError:
                    continue
                problems += memory_sync_uses(os.path.relpath(path, base), tree)
    return problems


def layout_problems(base, part, quiet=True):
    """The final-phase checks on the tree at `base` (skills/ai-task, tests, hooks beneath it); [] when right."""
    skill = skill_dir(base)
    problems = []
    trees = {}
    for mod in new_modules(part):
        path = os.path.join(skill, mod + ".py")
        if not os.path.isfile(path):
            problems.append("%s.py is missing" % mod)
            continue
        trees[mod] = parse(path)
        problems += module_problems(part, mod, path)
        count = line_count(path)
        if not quiet:
            print("%s.py: %d lines%s" % (mod, count, "  (over %d: note it in task.md)" % ADVISORY_LINES
                                         if count > ADVISORY_LINES else ""))
    entry = entry_path(base, part)
    problems += entry_problems(part, entry)
    if not quiet:
        print("%s.py: %d lines" % (part["entry"]["module"], line_count(entry)))
    layer = layers_of(part)
    real = {mod: sibling_imports(tree, set(layer)) for mod, tree in trees.items()}
    real[part["entry"]["module"]] = sibling_imports(parse(entry), set(layer))
    problems += graph_problems(layer, real)
    problems += ["%s imports the entry %s" % (m, part["entry"]["module"]) for m, deps in sorted(real.items())
                 if part["entry"]["module"] in deps and m != part["entry"]["module"]]
    problems += r4_problems(part, trees)
    problems += importer_problems(base, part)
    if "memory_io" in trees:
        problems += self_problems(base, part)
    return problems


# --------------------------------------------------------------------------------------
# which phase the tree is in


def entry_is_final(base, part):
    """True once memory_sync.py defines only the entry's names."""
    names = set(module_names(parse(entry_path(base, part))))
    return names <= set(part["modules"][part["entry"]["module"]]["defs"])


def phase_of(base, part):
    if entry_is_final(base, part):
        return "final"
    return "copy" if present_modules(base, part) else "single"


PART = read_partition()
PHASE = phase_of(ROOT, PART)


# --------------------------------------------------------------------------------------


class TestPartitionFile(unittest.TestCase):
    """The authority itself, whatever the phase."""

    @classmethod
    def setUpClass(cls):
        cls.part = PART

    def test_every_name_has_one_home_and_a_label(self):
        owner = owners_of(self.part)
        for name, homes in owner.items():
            self.assertEqual(len(homes), 1, "%s is in %s" % (name, homes))
        for name, rec in self.part["defs"].items():
            self.assertIn(rec["label"], ("core", "shell"), name)
            self.assertIn(rec["kind"], ("function", "class", "const"), name)
        self.assertEqual(set(owner), set(self.part["defs"]))

    def test_the_modules_are_the_plans_and_layers_are_numbers(self):
        self.assertEqual(new_modules(self.part), sorted(
            "memory_io memory_config memory_packages memory_verify memory_hook memory_risks memory_cleanup "
            "memory_migrate memory_export memory_status".split()))
        for mod, spec in self.part["modules"].items():
            self.assertIsInstance(spec["layer"], int, mod)
        self.assertEqual(max(layers_of(self.part).values()), self.part["modules"]["memory_sync"]["layer"])
        self.assertEqual(self.part["entry"]["module"], "memory_sync")

    def test_the_entry_is_d1s_four_defs_and_may_import_two_siblings(self):
        """D1 and R2: the entry defines the pre-push section only; memory_io and memory_verify are all it needs."""
        spec = self.part["modules"]["memory_sync"]
        self.assertEqual(sorted(spec["defs"]), ["_git_out", "base_for_new_branch", "pre_push", "pre_push_cli"])
        self.assertEqual(spec["imports"], sorted(self.part["entry"]["may_import"]))
        self.assertEqual(spec["imports"], ["memory_io", "memory_verify"])

    def test_the_homes_decided_in_the_plan(self):
        """D2: HERE, VALIDATOR and SELF in memory_io; D6: the fcntl fallback with `locked`."""
        io_defs = self.part["modules"]["memory_io"]["defs"]
        for name in ("HERE", "VALIDATOR", "SELF", "fcntl", "locked", "MemoryError_"):
            self.assertIn(name, io_defs)
        self.assertIn("new", self.part["defs"]["HERE"])
        self.assertEqual([n for n, r in self.part["defs"].items() if "new" in r], ["HERE"])

    def test_classes_and_namedtuples_are_the_ones_r4_allows(self):
        self.assertEqual(sorted(self.part["classes"]), ["GitTreeReader", "MemoryConfig", "MemoryError_"])
        self.assertEqual(sorted(self.part["namedtuples"]), ["ExportResult", "Finding"])
        for name in self.part["classes"]:
            self.assertEqual(self.part["defs"][name]["kind"], "class", name)
        for name in self.part["namedtuples"]:
            self.assertEqual(self.part["defs"][name]["kind"], "const", name)

    def test_recorded_imports_go_downward_and_acyclic(self):
        edges = {m: set(s["imports"]) for m, s in self.part["modules"].items()}
        self.assertEqual(graph_problems(layers_of(self.part), edges), [])

    def test_the_docstring_prefix_is_pinned(self):
        self.assertRegex(self.part["entry_docstring_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(self.part["entry_docstring_chars"], 100)


@unittest.skipIf(PHASE == "final", "memory_sync.py is the entry: the partition stands alone")
class TestPartitionAgainstWhole(unittest.TestCase):
    """Phases single and copy: the partition against the file that still holds the code, on paper."""

    @classmethod
    def setUpClass(cls):
        cls.part = PART
        cls.tree = parse(entry_path(ROOT, PART))
        cls.names = module_names(cls.tree)
        cls.graph = call_graph(cls.tree)
        cls.old = {n: r for n, r in PART["defs"].items() if "new" not in r}

    def test_every_name_of_memory_sync_is_assigned_once(self):
        self.assertEqual(sorted(set(self.names) - set(self.part["defs"])), [], "unassigned")
        self.assertEqual(sorted(set(self.old) - set(self.names)), [], "not in memory_sync.py")

    def test_kinds_signatures_and_values_are_memory_syncs(self):
        problems = []
        for name, (kind, node, value) in self.names.items():
            rec = self.part["defs"][name]
            if rec["kind"] != kind:
                problems.append("%s is a %s, the partition says %s" % (name, kind, rec["kind"]))
            elif kind == "function" and signature_of(node) != rec["signature"]:
                problems.append("%s%s, the partition has %s" % (name, signature_of(node), rec["signature"]))
            elif kind == "const" and rec["value_hash"] and (value is None or hash_of(value) != rec["value_hash"]):
                problems.append("%s has another value than the partition's" % name)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_recorded_edges_are_the_call_graphs(self):
        derived = module_edges(self.part, self.graph)
        for mod, spec in self.part["modules"].items():
            self.assertEqual(sorted(derived[mod]), sorted(spec["imports"]), "%s: derive the partition again" % mod)

    def test_the_import_graph_on_paper_is_acyclic_and_downward(self):
        """R10: found before any module is written, not after a move."""
        problems = graph_problems(layers_of(self.part), module_edges(self.part, self.graph))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_core_names_touch_nothing(self):
        nodes = {name: node for name, (_kind, node, _value) in self.names.items()}
        problems = label_problems(self.part, self.graph, nodes)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_no_global_in_the_file(self):
        self.assertEqual([n.lineno for n in ast.walk(self.tree) if isinstance(n, ast.Global)], [])

    def test_the_docstring_is_pinned_to_the_file(self):
        doc = ast.get_docstring(self.tree, clean=False)
        digest = hashlib.sha256(doc[:self.part["entry_docstring_chars"]].encode()).hexdigest()
        self.assertEqual(digest, self.part["entry_docstring_sha256"])

    def test_the_entrys_references_stay_within_r2(self):
        """R2: pre_push, pre_push_cli, base_for_new_branch and _git_out need memory_io and memory_verify only."""
        derived = module_edges(self.part, self.graph)["memory_sync"]
        self.assertEqual(sorted(derived), sorted(self.part["entry"]["may_import"]))

    def test_the_classes_and_namedtuples_are_the_ones_in_the_file(self):
        classes = sorted(n for n, (k, _node, _v) in self.names.items() if k == "class")
        tuples = sorted(n for n, (_k, _node, v) in self.names.items()
                        if isinstance(v, ast.Call) and ast.unparse(v.func).split(".")[-1] == "namedtuple")
        self.assertEqual(classes, sorted(self.part["classes"]))
        self.assertEqual(tuples, sorted(self.part["namedtuples"]))


@unittest.skipIf(PHASE == "final", "memory_sync.py is the entry: the full form below applies")
class TestModulesPresent(unittest.TestCase):
    """Phases single and copy: each module the steps have written so far, on its own (none is fine)."""

    def test_each_present_module_is_the_partitions(self):
        problems = []
        for mod in present_modules(ROOT, PART):
            problems += module_problems(PART, mod, os.path.join(skill_dir(ROOT), mod + ".py"))
        if "memory_io" in present_modules(ROOT, PART):
            problems += self_problems(ROOT, PART)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_no_new_module_is_imported_by_memory_sync_yet_or_imports_it(self):
        """The copy phase leaves memory_sync.py untouched; nothing of the new modules imports it."""
        problems = []
        for mod in present_modules(ROOT, PART):
            tree = parse(os.path.join(skill_dir(ROOT), mod + ".py"))
            problems += ["%s imports memory_sync" % mod for _ in [0] if "memory_sync" in sibling_imports(tree, {"memory_sync"})]
        self.assertEqual(problems, [])

    def test_sizes_are_reported(self):
        """Advisory: over 600 lines is noted in the task report, never a failure."""
        for mod in present_modules(ROOT, PART):
            count = line_count(os.path.join(skill_dir(ROOT), mod + ".py"))
            print("%s.py: %d lines%s" % (mod, count, "  (over %d: note it in task.md)" % ADVISORY_LINES
                                         if count > ADVISORY_LINES else ""))


@unittest.skipUnless(PHASE == "final", "memory_sync.py still defines the code: phases single and copy above apply")
class TestCutOver(unittest.TestCase):
    """Phase final: memory_sync.py is the entry. One call to `layout_problems` on the real tree; the
    pieces are separate tests so a failure names its requirement."""

    @classmethod
    def setUpClass(cls):
        cls.problems = layout_problems(ROOT, PART, quiet=False)

    def only(self, *needles):
        found = [p for p in self.problems if any(n in p for n in needles)]
        self.assertEqual(found, [], "\n".join(found))

    def test_the_entry_is_small_and_defines_d1s_four(self):
        self.only("memory_sync has", "memory_sync defines", "docstring", "sys.path", "`__all__`", "R2")

    def test_all_ten_modules_are_there_and_each_is_the_partitions(self):
        self.only(".py is missing", ": missing ", " is not the partition's", "partition has", "partition says",
                  "another value")

    def test_the_import_graph_from_the_real_imports_is_acyclic_and_downward(self):
        self.only("upward edge", "cycle:", "imports itself", "imports the entry", "which is not a module")

    def test_no_global_and_the_one_file(self):
        self.only("`global", "__file__")

    def test_the_seams_stay_attributes(self):
        self.only("D5", "relative import")

    def test_the_forbidden_constructs_of_r4(self):
        self.only("R4")

    def test_nothing_imports_the_entry_but_the_hook(self):
        self.only("memory_sync", "`import memory_sync`")

    def test_hooks_isolation(self):
        self.only("R15")

    def test_the_shim_path_is_the_entry(self):
        self.only("SELF", "VALIDATOR", "memory_io does not import")

    def test_nothing_else_is_wrong(self):
        self.assertEqual(self.problems, [], "\n".join(self.problems))


# --------------------------------------------------------------------------------------
# the checks themselves, on small synthetic trees


class TestAnalysis(unittest.TestCase):
    """The reading of a source on small synthetic ones: it sees what it must and passes what it may."""

    SOURCE = ("import os\n"
              "try:\n    import fcntl\nexcept ImportError:\n    fcntl = None\n"
              "LIMIT = 5\nA, B = (1, 2)\n\n"
              "def read(path):\n    with open(path) as fh:\n        return fh.read()\n\n"
              "def pure(x, read=LIMIT):\n    return [read for read in x]\n\n"
              "def user(path):\n    return read(path) + LIMIT\n\n"
              "class Holder:\n    def read(self, p):\n        return read(p)\n")

    def test_the_names_of_a_file(self):
        names = module_names(ast.parse(self.SOURCE))
        self.assertEqual(sorted(names), ["A", "B", "Holder", "LIMIT", "fcntl", "pure", "read", "user"])
        self.assertEqual(names["Holder"][0], "class")
        self.assertEqual(names["fcntl"][0], "const")
        self.assertEqual(signature_of(names["pure"][1]), "(x, read=LIMIT)")

    def test_a_reference_is_a_reference_only_when_nothing_shadows_it(self):
        graph = call_graph(ast.parse(self.SOURCE))
        self.assertEqual(graph["user"], {"read", "LIMIT"})
        self.assertEqual(graph["pure"], {"LIMIT"}, "the parameter and the comprehension variable are `read`'s own")
        self.assertEqual(graph["Holder"], {"read"}, "a method called read is not the module's read")

    def test_io_is_what_touches_a_file_a_clock_or_a_process(self):
        def hit(code):
            return reaches_io(ast.parse(code))
        self.assertEqual(hit("open(p)"), "open")
        self.assertEqual(hit("os.path.join(a, b)"), "")
        self.assertEqual(hit("os.path.isfile(a)"), "os.path.isfile")
        self.assertEqual(hit("subprocess.run(a)"), "subprocess")
        self.assertEqual(hit("datetime.now(tz)"), "datetime.now")
        self.assertEqual(hit("json.dumps(a)"), "")
        self.assertEqual(hit("print(a)"), "print")

    def test_the_graph_check_flags_an_upward_edge_a_same_layer_edge_and_a_cycle(self):
        layer = {"low": 0, "mid": 1, "top": 2}
        self.assertEqual(graph_problems(layer, {"low": set(), "mid": {"low"}, "top": {"low", "mid"}}), [])
        self.assertTrue(any("upward edge: low" in p for p in graph_problems(layer, {"low": {"mid"}, "mid": set()})))
        self.assertTrue(any("upward edge" in p for p in graph_problems(layer, {"mid": {"mid"}})))
        cyc = graph_problems({"a": 0, "b": 0}, {"a": {"b"}, "b": {"a"}})
        self.assertTrue(any(p.startswith("cycle: ") for p in cyc), cyc)

    def test_the_label_check_flags_a_core_name_that_reaches_io_or_a_shell_name(self):
        tree = ast.parse(self.SOURCE)
        nodes = {n: node for n, (_k, node, _v) in module_names(tree).items()}
        part = {"defs": {n: {"label": "shell" if n in ("read", "user", "Holder") else "core"} for n in nodes}}
        self.assertEqual(label_problems(part, call_graph(tree), nodes), [])
        part["defs"]["read"]["label"] = "core"
        part["defs"]["user"]["label"] = "core"
        self.assertIn("core name read reaches I/O (open)", label_problems(part, call_graph(tree), nodes))
        part["defs"]["read"]["label"] = "shell"
        self.assertIn("core name user refers to the shell name read", label_problems(part, call_graph(tree), nodes))

    def test_the_real_imports_of_a_tree(self):
        tree = ast.parse("import os\nimport memory_io as mio\nfrom memory_verify import rev\nimport json\n")
        self.assertEqual(sibling_imports(tree, {"memory_io", "memory_verify", "memory_status"}),
                         {"memory_io", "memory_verify"})
        self.assertEqual(len(seam_problems("m", tree)), 1)
        bad = ast.parse("from json import dumps\nfrom os import replace\nfrom os.path import join\nfrom . import x\n")
        self.assertEqual(len(seam_problems("m", bad)), 4)
        self.assertEqual(len(hooks_problems("m", ast.parse("import hooks.x\nfrom guard import y\nimport os\n"))), 2)

    def test_the_importers_of_the_entry_are_found(self):
        def uses(code):
            return memory_sync_uses("f.py", ast.parse(code))
        self.assertEqual(len(uses("import memory_sync as ms\n")), 1)
        self.assertEqual(len(uses("from memory_sync import pre_push\n")), 1)
        self.assertEqual(len(uses("m = sibling(AI_TASK, 'memory_sync')\n")), 1)
        self.assertEqual(len(uses("cmd = 'import memory_sync; memory_sync.x'\n")), 1)
        self.assertEqual(uses("import memory_syncing\nx = 'memory_sync.py'\nimport memory_io\n"), [])


GOOD_FILES = {
    "skills/ai-task/memory_io.py": (
        "import os\n\n"
        "HERE = os.path.dirname(os.path.abspath(__file__))\n"
        "VALIDATOR = os.path.normpath(os.path.join(HERE, '..', '..', 'hooks', 'memory-pre-push.py'))\n"
        "SELF = os.path.join(HERE, 'memory_sync.py')\n\n\n"
        "class MemoryError_(Exception):\n    pass\n\n\n"
        "def git(repo):\n    return repo\n"),
    "skills/ai-task/memory_verify.py": (
        "import collections\n"
        "import memory_io as mio\n\n"
        "Finding = collections.namedtuple('Finding', 'check path')\n\n\n"
        "def rev(repo):\n    return mio.git(repo)\n"),
    "skills/ai-task/memory_sync.py": (
        '"""The validator. Nothing else."""\n'
        "import os\n"
        "import sys\n\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "import memory_io as mio  # noqa: E402\n"
        "import memory_verify as mv  # noqa: E402\n\n\n"
        "def pre_push_cli(argv):\n    return mv.rev(argv) or mio.git(argv)\n\n\n"
        "if __name__ == '__main__':\n    sys.exit(pre_push_cli(sys.argv[1:]))\n"),
    "tests/test_something.py": "import memory_verify\nimport unittest\n",
    "hooks/memory-pre-push.py": "import memory_sync\n",
}
SYNTHETIC = {
    "schema": 1,
    "entry_docstring_sha256": hashlib.sha256("The validator. Nothing else.".encode()).hexdigest(),
    "entry_docstring_chars": len("The validator. Nothing else."),
    "entry": {"module": "memory_sync", "max_lines": 30, "may_import": ["memory_io", "memory_verify"],
              "sys_path_line": "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))"},
    "classes": ["MemoryError_"],
    "namedtuples": ["Finding"],
    "modules": {
        "memory_io": {"layer": 0, "imports": [], "defs": ["HERE", "VALIDATOR", "SELF", "MemoryError_", "git"]},
        "memory_verify": {"layer": 2, "imports": ["memory_io"], "defs": ["Finding", "rev"]},
        "memory_sync": {"layer": 6, "imports": ["memory_io", "memory_verify"], "defs": ["pre_push_cli"]},
    },
    "defs": {
        "HERE": {"kind": "const", "signature": "", "label": "shell", "value_hash": None},
        "VALIDATOR": {"kind": "const", "signature": "", "label": "shell", "value_hash": None},
        "SELF": {"kind": "const", "signature": "", "label": "shell", "value_hash": None},
        "MemoryError_": {"kind": "class", "signature": "", "label": "core", "value_hash": None},
        "git": {"kind": "function", "signature": "(repo)", "label": "core", "value_hash": None},
        "Finding": {"kind": "const", "signature": "",
                    "label": "core", "value_hash": hash_of(ast.parse("collections.namedtuple('Finding', 'check path')",
                                                                    mode="eval").body)},
        "rev": {"kind": "function", "signature": "(repo)", "label": "shell", "value_hash": None},
        "pre_push_cli": {"kind": "function", "signature": "(argv)", "label": "shell", "value_hash": None},
    },
}


class TestSyntheticTree(unittest.TestCase):
    """The final-phase checks on a tree built in a temporary directory: a good one passes, and each rule
    fails on one edit of it. They show the checks work before the real tree reaches the final phase."""

    def tree(self, edits=None, extra=None):
        tmp_name = tempfile.mkdtemp(prefix="memory-layout-")
        self.addCleanup(shutil.rmtree, tmp_name, ignore_errors=True)
        files = dict(GOOD_FILES)
        for rel, (old, new) in (edits or {}).items():
            self.assertIn(old, files[rel], "the edit of %s no longer applies" % rel)
            files[rel] = files[rel].replace(old, new, 1)
        files.update(extra or {})
        for rel, text in files.items():
            path = os.path.join(tmp_name, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        return tmp_name

    def found(self, needle, edits=None, extra=None):
        problems = layout_problems(self.tree(edits, extra), SYNTHETIC)
        self.assertTrue(any(needle in p for p in problems), "%r not in %s" % (needle, problems))

    def test_a_good_tree_passes(self):
        self.assertEqual(layout_problems(self.tree(), SYNTHETIC), [])
        self.assertEqual(phase_of(self.tree(), SYNTHETIC), "final")

    def test_the_phase_is_told_from_the_disk(self):
        whole = {"skills/ai-task/memory_sync.py": "def load_config():\n    pass\n\n\ndef pre_push_cli(argv):\n    pass\n"}
        tree = self.tree(extra=whole)
        self.assertEqual(phase_of(tree, SYNTHETIC), "copy")
        os.remove(os.path.join(tree, "skills/ai-task/memory_io.py"))
        os.remove(os.path.join(tree, "skills/ai-task/memory_verify.py"))
        self.assertEqual(phase_of(tree, SYNTHETIC), "single")

    def test_an_upward_edge_is_found(self):
        self.found("upward edge: memory_io (layer 0) imports memory_verify",
                   {"skills/ai-task/memory_io.py": ("import os\n", "import os\nimport memory_verify\n")})

    def test_a_cycle_is_found(self):
        self.found("cycle:", {"skills/ai-task/memory_io.py": ("import os\n", "import os\nimport memory_verify\n")})

    def test_a_module_importing_the_entry_is_found(self):
        self.found("imports the entry", {"skills/ai-task/memory_verify.py": ("import memory_io as mio\n",
                                                                           "import memory_io as mio\nimport memory_sync\n")})

    def test_from_memory_x_import_is_found(self):
        self.found("from memory_io import git", {"skills/ai-task/memory_verify.py": (
            "import memory_io as mio\n", "import memory_io as mio\nfrom memory_io import git\n")})

    def test_from_json_and_from_os_import_are_found(self):
        self.found("from json import dumps", {"skills/ai-task/memory_verify.py": ("import collections\n",
                                                                                "import collections\nfrom json import dumps\n")})
        self.found("from os import replace", {"skills/ai-task/memory_io.py": ("import os\n", "import os\nfrom os import replace\n")})

    def test_file_outside_memory_io_is_found(self):
        self.found("__file__ (R6a", {"skills/ai-task/memory_verify.py": ("return mio.git(repo)", "return __file__")})
        self.found("2 uses of __file__", {"skills/ai-task/memory_io.py": ("SELF = ", "OTHER = __file__\nSELF = ")})

    def test_a_wrong_self_is_found(self):
        self.found("basename(memory_io.SELF) is memory_io.py", {"skills/ai-task/memory_io.py": (
            "SELF = os.path.join(HERE, 'memory_sync.py')", "SELF = os.path.abspath(__file__)")})
        self.found("memory_io.SELF", {"skills/ai-task/memory_io.py": (
            "SELF = os.path.join(HERE, 'memory_sync.py')", "SELF = os.path.join(HERE, '..', 'memory_sync.py')")})

    def test_a_global_is_found(self):
        self.found("`global X`", {"skills/ai-task/memory_verify.py": ("return mio.git(repo)", "global X\n    return mio.git(repo)")})

    def test_a_forbidden_construct_is_found(self):
        self.found("class Other(object)", {"skills/ai-task/memory_verify.py": ("def rev", "class Other(object):\n    pass\n\n\ndef rev")})
        self.found("uses staticmethod", {"skills/ai-task/memory_verify.py": ("def rev", "x = staticmethod\n\n\ndef rev")})
        self.found("namedtuples are", {"skills/ai-task/memory_verify.py": ("def rev", "Other = collections.namedtuple('Other', 'a')\n\n\ndef rev")})

    def test_a_missing_or_extra_name_is_found(self):
        self.found("memory_verify: missing rev", {"skills/ai-task/memory_verify.py": ("def rev", "def rev_")})
        self.found("memory_io: extra is not the partition's", {"skills/ai-task/memory_io.py": ("def git", "extra = 1\n\n\ndef git")})
        tree = self.tree()
        os.remove(os.path.join(tree, "skills/ai-task/memory_verify.py"))
        self.assertIn("memory_verify.py is missing", layout_problems(tree, SYNTHETIC))

    def test_a_changed_signature_is_found(self):
        self.found("partition has git(repo)", {"skills/ai-task/memory_io.py": ("def git(repo)", "def git(repo, more)")})

    def test_the_entry_contract_is_found(self):
        self.found("memory_sync defines", {"skills/ai-task/memory_sync.py": ("def pre_push_cli", "def extra():\n    pass\n\n\ndef pre_push_cli")})
        self.found("R2 allows", {"skills/ai-task/memory_sync.py": ("import memory_verify as mv", "import memory_verify as mv\nimport memory_status")})
        self.found("lines, the limit is under 30", {"skills/ai-task/memory_sync.py": ("def pre_push_cli", "\n" * 30 + "def pre_push_cli")})
        self.found("before the sys.path line", {"skills/ai-task/memory_sync.py": (
            "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\nimport memory_io as mio  # noqa: E402\n",
            "import memory_io as mio  # noqa: E402\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n")})
        self.found("`__all__` re-exports", {"skills/ai-task/memory_sync.py": ("def pre_push_cli", "__all__ = ['rev']\n\n\ndef pre_push_cli")})
        self.found("lost the first", {"skills/ai-task/memory_sync.py": ('"""The validator. Nothing else."""', '"""Another."""')})
        self.found("__file__ at lines", {"skills/ai-task/memory_sync.py": ("def pre_push_cli", "HERE = __file__\n\n\ndef pre_push_cli")})

    def test_an_importer_of_the_entry_in_skills_or_tests_is_found(self):
        self.found("tests/test_other.py:1 import memory_sync", extra={"tests/test_other.py": "import memory_sync as ms\n"})
        self.found("skills/ai-task/rr_state/close.py:1 from memory_sync", extra={"skills/ai-task/rr_state/close.py": "from memory_sync import x\n"})
        self.found("tests/test_other.py", extra={"tests/test_other.py": "X = sibling(D, 'memory_sync')\n"})

    def test_the_hook_may_import_the_entry_and_the_layout_test_may_name_it(self):
        problems = layout_problems(self.tree(extra={"tests/" + THIS: "import memory_sync\n"}), SYNTHETIC)
        self.assertEqual(problems, [])

    def test_a_hook_import_from_a_module_is_found(self):
        self.found("R15", {"skills/ai-task/memory_verify.py": ("import collections\n", "import collections\nimport hooks.x\n")})


if __name__ == "__main__":
    unittest.main()
