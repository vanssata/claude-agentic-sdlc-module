#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Layout of the split of hooks/guard/paths.py into the entry paths.py and eight sibling modules paths_base, paths_fs,
paths_shell, paths_human, paths_interp, paths_classify, paths_movers and paths_bash, imported as guard.<name>
(small-oop-modules WP5: R2, R3, R4, R6a, R10, R15, R16; decisions D1 to D6 of
docs/sdlc/plans/small-oop-modules-wp5.md).

tests/fixtures/guard/partition.json is the authority: which module owns which top-level name and which PathGuard
method (a moved method is a function with `self` first, under its new name when D3 renames it), the layer of each
module, core or shell per name, the signature each function has today, a constant's value hash, the module import
edges, the entry's contract. The call graph is read from paths.py with `ast` in this file; no tool is needed.

Three phases, told by what is on disk (nothing to flip when a step lands):

  single (no paths_*.py exists, paths.py is whole) - the partition against paths.py: every top-level name and every
    PathGuard method is in it exactly once and vice versa, kinds, signatures and value hashes match, the recorded
    edges are the call graph's, every edge goes to a lower layer and there is no cycle (R10, on paper), a core name
    touches no file, clock or subprocess and refers to no shell name (R16), no `global`.
  copy (some paths_*.py exist, paths.py still defines all 36 methods) - the single checks, and each module present is
    checked on its own: exactly the partition's names, signatures, values, no `global`, no `__file__`, imports that
    match the recorded edges and go downward, nothing from rr_state, state or skills/ (R15); and `move_problems`
    on the paths.py on disk is empty (D6).
  final (paths.py defines only PathGuard and check) - everything in `layout_problems`: the entry under 200 lines and
    nothing else at its top level, no re-export (Q25); all eight modules present and each the partition's;
    PathGuard's body is the nine kept methods and one class-level binding per moved method, each to its home
    module's function (an unbound method would make the guard fail open); the real import graph (R10); three
    classes (R4); no `global`, no `__file__`; no import of rr_state, state or skills/ (R15); sizes printed (600
    lines advisory).

`python3 -I tests/test_guard_layout.py --moved-from <rev>` runs `move_problems` (D6) between the paths.py of <rev>
(`git show <rev>:hooks/guard/paths.py`) and the working tree: every moved node equals its source node, once D3's
renames are applied. It prints each problem and exits 1, or prints `move_problems: none` and exits 0.

`layout_problems` and `move_problems` take the tree to read, so TestSyntheticTree runs them on a small tree built in
a temporary directory and shows that each check can fail, before the real tree reaches the final phase.
"""
import ast
import copy
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTITION = os.path.join(ROOT, "tests", "fixtures", "guard", "partition.json")
GUARD_REL = os.path.join("hooks", "guard")
CLASS = "PathGuard"
IO_IMPORTS = {"os", "subprocess", "time", "fcntl", "shutil", "datetime"}
IO_ROOTS = {"subprocess", "time", "shutil", "tempfile", "sys", "importlib", "fcntl", "dialog"}
IO_COMMON = {"exists", "is_dir", "is_file", "real_path", "realpath_strict", "load_json_file", "env_b",
             "find_ai_root"}
PURE_PATH = {"join", "dirname", "basename", "normpath", "sep", "splitext", "split", "isabs",
             "relpath", "commonpath"}
PURE_OS = {"sep", "linesep", "pathsep", "curdir", "pardir", "fspath", "fsdecode", "fsencode"}
BARE_IO = {"open", "print", "input", "exec", "eval", "__import__"}
FORBIDDEN_NAMES = {"ABC", "abstractmethod", "Protocol", "staticmethod"}
FORBIDDEN_ROOTS = {"rr_state", "state"}
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
          ast.GeneratorExp)
TOP_LEVEL = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign)
ENTRY_LEVEL = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)
ADVISORY_LINES = 600


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse(path):
    return ast.parse(read_text(path), filename=path)


def read_partition(path=PARTITION):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def module_path(base, mod):
    return os.path.join(base, GUARD_REL, mod + ".py")


def entry_path(base, part):
    return module_path(base, part["entry"]["module"])


def new_modules(part):
    """The modules the split adds: every module of the partition but the entry."""
    return sorted(m for m in part["modules"] if m != part["entry"]["module"])


def present_modules(base, part):
    return [m for m in new_modules(part) if os.path.isfile(module_path(base, m))]


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


def duplicate_names(tree):
    """The names a module defines more than once at its top level."""
    seen, twice = set(), set()
    for node in tree.body:
        for name, _value in statement_names(node):
            (twice if name in seen else seen).add(name)
    return sorted(twice)


def class_node(tree, name=CLASS):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def class_methods(tree, name=CLASS):
    """{method name: FunctionDef} of a class, in the order they are written."""
    cls = class_node(tree, name)
    return {m.name: m for m in cls.body if isinstance(m, ast.FunctionDef)} if cls else {}


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
    """The names of `names` that a statement refers to, minus those a function-like scope inside it binds
    for itself (a parameter called `read` is not the module's `read`)."""
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


def is_self(node):
    return isinstance(node, ast.Name) and node.id == "self"


def self_attrs(node):
    """The `self.<name>` attributes a node reads or calls: [(line, name)]."""
    return [(n.lineno, n.attr) for n in ast.walk(node)
            if isinstance(n, ast.Attribute) and is_self(n.value) and isinstance(n.ctx, ast.Load)]


def reaches_io(node):
    """The first thing in a statement that touches a file, the clock, a process or the screen, or ''."""
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and (item.id in BARE_IO or item.id in IO_COMMON):
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
        if root.id == "self" and "clock" in chain:
            return "self." + ".".join(chain)
        if root.id == "os" and chain != ["path"] and chain[0] not in PURE_OS \
                and not (chain[0] == "path" and chain[1] in PURE_PATH):
            return "os." + ".".join(chain)
        if root.id == "datetime" and chain[0] in ("now", "utcnow", "today"):
            return "datetime." + chain[0]
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


def normalised(node, renames):
    """A copy of a source node with D3's map applied: a def's own name and every `self.<old>` attribute,
    and its docstrings cleaned of the indentation of the line they continue on (a dedented method keeps
    its words; the compare does not count the indentation)."""
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.body and isinstance(item.body[0], ast.Expr) \
                and isinstance(item.body[0].value, ast.Constant) and isinstance(item.body[0].value.value, str):
            item.body[0].value.value = inspect.cleandoc(item.body[0].value.value)
        if isinstance(item, ast.FunctionDef) and item.name in renames:
            item.name = renames[item.name]
        elif isinstance(item, ast.Attribute) and is_self(item.value) and item.attr in renames:
            item.attr = renames[item.attr]
    return node


# --------------------------------------------------------------------------------------
# the partition: homes, units, the graph


def owners_of(part):
    owner = {}
    for mod, spec in part["modules"].items():
        for name in spec["defs"]:
            owner.setdefault(name, []).append(mod)
    return owner


def moved_methods(part):
    """{old name: (new name, module)} of the methods that leave PathGuard as functions (D2)."""
    return {rec["old_name"]: (name, rec["module"]) for name, rec in part["defs"].items()
            if rec["kind"] == "method"}


def method_labels(part):
    labels = {old: part["defs"][new]["label"] for old, (new, _mod) in moved_methods(part).items()}
    labels.update({name: rec["label"] for name, rec in part["kept_methods"].items()})
    return labels


def layers_of(part):
    return {m: s["layer"] for m, s in part["modules"].items()}


def source_graph(tree, part):
    """{unit: set(units it refers to)} of the source: a top-level name, or a moved method under its new name.
    PathGuard is its kept methods plus the table: it refers to every moved method's name."""
    names = set(module_names(tree))
    methods = class_methods(tree)
    graph = {}
    for name, (_kind, node, _value) in module_names(tree).items():
        if name == CLASS:
            refs = {new for new, _mod in moved_methods(part).values()}
            for kept in part["kept_methods"]:
                refs |= references(methods[kept], names) if kept in methods else set()
            graph[name] = refs
        else:
            graph[name] = references(node, names) - {name}
    for old, (new, _mod) in moved_methods(part).items():
        if old in methods:
            graph[new] = references(methods[old], names) - {new}
    return graph


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
                problems.append("%s imports %s, which is not a module of the partition (R10)" % (mod, dep))
            elif layer[dep] >= layer[mod]:
                problems.append("upward edge: %s (layer %d) imports %s (layer %d) (R10)"
                                % (mod, layer[mod], dep, layer[dep]))
    colour = {}

    def visit(node, path):
        if colour.get(node) == 1:
            problems.append("cycle: %s (R10)" % " -> ".join(path[path.index(node):] + [node]))
        elif node not in colour:
            colour[node] = 1
            for dep in sorted(edges.get(node, ())):
                visit(dep, path + [node])
            colour[node] = 2
    for mod in sorted(edges):
        visit(mod, [])
    return problems


def label_units(tree, part):
    """[(name, label, node, top-level names it refers to, methods it calls through self)] of the source:
    every top-level name, every kept method and every moved method. PathGuard is its kept methods."""
    names = set(module_names(tree))
    methods = class_methods(tree)
    called = set(methods)
    units = []
    for name, (_kind, node, _value) in module_names(tree).items():
        rec = part["defs"].get(name)
        if rec is None or name == CLASS:
            continue
        units.append((name, rec["label"], node, references(node, names) - {name}, set()))
    for old, rec in list(part["kept_methods"].items()) + [(o, part["defs"][n]) for o, (n, _m)
                                                             in moved_methods(part).items()]:
        if old in methods:
            node = methods[old]
            units.append((CLASS + "." + old, rec["label"], node, references(node, names),
                          {a for _l, a in self_attrs(node) if a in called}))
    return units


def label_problems(part, units):
    """R16: a core name touches no file, clock or subprocess, refers to no shell name and calls no shell method."""
    problems = []
    shell_methods = {o for o, label in method_labels(part).items() if label == "shell"}
    for name, label, node, refs, calls in sorted(units, key=lambda u: u[0]):
        if label != "core":
            continue
        hit = reaches_io(node)
        if hit:
            problems.append("core name %s reaches I/O (%s) (R16)" % (name, hit))
        problems += ["core name %s refers to the shell name %s (R16)" % (name, ref)
                     for ref in sorted(refs) if part["defs"].get(ref, {}).get("label") == "shell"]
        problems += ["core name %s calls the shell method self.%s (R16)" % (name, ref)
                     for ref in sorted(calls & shell_methods)]
    return problems


def instance_attrs(trees):
    """The attributes PathGuard code stores on self, anywhere in the files."""
    found = set()
    for tree in trees:
        for func in guard_functions(tree):
            found.update(n.attr for n in ast.walk(func)
                         if isinstance(n, ast.Attribute) and is_self(n.value) and isinstance(n.ctx, ast.Store))
    return found


def guard_functions(tree):
    """The functions in which `self` is a PathGuard: a top-level function with `self` first, a PathGuard method."""
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.args.args and n.args.args[0].arg == "self"]
    return found + list(class_methods(tree).values())


def unbound_problems(part, trees, source=False):
    """R3: a `self.<name>(...)` call with no method behind it is an AttributeError at run time, and the
    guard fails open on one; a `self.<old>` left over from D3's renames is the same. `source` is paths.py
    before the split, where the old names are the methods."""
    known = set(part["kept_methods"]) | {new for new, _mod in moved_methods(part).values()}
    if source:
        known |= set(moved_methods(part))
    attrs = instance_attrs(trees.values())
    stale = set() if source else {old for old in part["renames"] if old not in known}
    problems = []
    for mod, tree in sorted(trees.items()):
        for func in guard_functions(tree):
            for node in ast.walk(func):
                if not (isinstance(node, ast.Attribute) and is_self(node.value)):
                    continue
                if node.attr in stale and node.attr not in attrs and isinstance(node.ctx, ast.Load):
                    problems.append("%s:%d self.%s was renamed %s (D3)" % (mod, node.lineno, node.attr,
                                                                       part["renames"][node.attr]))
    for mod, tree in sorted(trees.items()):
        calls = [n for f in guard_functions(tree) for n in ast.walk(f) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and is_self(n.func.value)]
        problems += ["%s:%d self.%s() is no method of PathGuard (an unbound method fails open) (R3)" % (
            mod, c.lineno, c.func.attr) for c in calls
            if c.func.attr not in known and c.func.attr not in attrs and c.func.attr not in part["renames"]]
    return problems


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
    """The modules of `mods` a tree imports as guard.<m>: `import guard.m`, `from guard.m import y`,
    `from guard import m`."""
    found = set()
    for _line, base, names, _is_from in imports_of(tree):
        parts = base.split(".")
        if parts[0] != "guard":
            continue
        if len(parts) > 1 and parts[1] in mods:
            found.add(parts[1])
        elif len(parts) == 1:
            found.update(n for n in names if n in mods)
    return found


def module_aliases(tree, mods):
    """{local name: module} of the sibling modules a tree imports at its top level as a module."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "guard" and node.level == 0:
            found.update({(a.asname or a.name): a.name for a in node.names if a.name in mods})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if alias.asname and parts[0] == "guard" and len(parts) == 2 and parts[1] in mods:
                    found[alias.asname] = parts[1]
    return found


def import_problems(mod, tree, mods):
    """R15, D4: nothing of the guard modules imports rr_state, state or anything under skills/, a
    sibling is imported as guard.<name>, and no import is relative."""
    problems = []
    for line, base, names, is_from in imports_of(tree):
        root = base.split(".")[0]
        if root in FORBIDDEN_ROOTS or root == "skills" or base.startswith("skills"):
            problems.append("%s:%d imports %s (R15)" % (mod, line, base))
        elif base.startswith("."):
            problems.append("%s:%d relative import of %s (D4)" % (mod, line, base or "."))
        elif root in mods:
            problems.append("%s:%d imports %s, as guard.%s (D4)" % (mod, line, base, root))
        elif is_from and root == "guard" and base == "guard" and any(n in FORBIDDEN_ROOTS for n in names):
            problems.append("%s:%d from guard import %s (R15)" % (mod, line, ", ".join(names)))
    return problems


def file_uses(tree):
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]


def shape_problems(mod, tree, allowed=TOP_LEVEL):
    """D6: a module holds imports, definitions and its docstring, and defines no name twice."""
    problems = []
    for idx, node in enumerate(tree.body):
        doc = idx == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
            and isinstance(node.value.value, str)
        if not doc and not isinstance(node, allowed):
            problems.append("%s:%d a top-level %s: only imports, definitions and the docstring (D6)"
                            % (mod, node.lineno, type(node).__name__))
    problems += ["%s defines %s twice (D6)" % (mod, n) for n in duplicate_names(tree)]
    if not ast.get_docstring(tree):
        problems.append("%s has no module docstring (R11)" % mod)
    return problems


def module_problems(part, mod, path):
    """Everything wrong with one new module file against the partition; [] when it is right."""
    if mod not in part["modules"] or mod == part["entry"]["module"]:
        return ["%s: not one of the new modules of the partition" % mod]
    spec = part["modules"][mod]
    tree = parse(path)
    problems = []
    found = module_names(tree)
    wanted = set(spec["defs"])
    problems += ["%s: missing %s" % (mod, n) for n in sorted(wanted - set(found))]
    problems += ["%s: %s is not the partition's" % (mod, n) for n in sorted(set(found) - wanted)]
    for name, (kind, node, value) in found.items():
        rec = part["defs"].get(name)
        if not rec or name not in wanted:
            continue
        want = "function" if rec["kind"] == "method" else rec["kind"]
        if want != kind:
            problems.append("%s: %s is a %s, the partition says %s" % (mod, name, kind, want))
        elif kind == "function":
            sig = signature_of(node)
            if param_tokens(sig) != param_tokens(rec["signature"]):
                problems.append("%s: %s%s, the partition has %s%s" % (mod, name, sig, name, rec["signature"]))
        elif kind == "const" and rec["value_hash"] and value is not None and hash_of(value) != rec["value_hash"]:
            problems.append("%s: %s has another value than paths.py's" % (mod, name))
    problems += shape_problems(mod, tree)
    problems += ["%s:%d `global %s` (R4)" % (mod, n.lineno, ", ".join(n.names)) for n in ast.walk(tree)
                 if isinstance(n, ast.Global)]
    problems += ["%s:%d __file__ (R6a: no guard module reads its own path)" % (mod, n) for n in file_uses(tree)]
    problems += import_problems(mod, tree, set(part["modules"]))
    layer = layers_of(part)
    real = sibling_imports(tree, set(layer))
    problems += graph_problems(layer, {mod: real})
    if mod in real:
        problems.append("%s imports itself (R10)" % mod)
    if real != set(spec["imports"]):
        problems.append("%s imports %s, the partition has %s (R10)" % (mod, sorted(real), spec["imports"]))
    labels = {part["defs"][n]["label"] for n in spec["defs"] if n in part["defs"]}
    if labels == {"core"}:
        taken = {b.split(".")[0] for _l, b, _n, _f in imports_of(tree)} & IO_IMPORTS
        taken |= {n for _l, b, names, _f in imports_of(tree) if b == "guard.common" for n in names} & IO_COMMON
        problems += ["%s: all names are core, yet it imports %s (R16)" % (mod, n) for n in sorted(taken)]
    return problems


def r4_problems(part, trees):
    """R4: only the partition's classes with their bases, no ABC, Protocol or staticmethod."""
    problems, classes = [], {}
    for mod, tree in sorted(trees.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes[node.name] = ", ".join(ast.unparse(b) for b in node.bases) or None
            if isinstance(node, ast.Name):
                used = {node.id}
            elif isinstance(node, ast.Attribute):
                used = {node.attr}
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                used = {a.name.split(".")[-1] for a in node.names}
            else:
                used = set()
            problems += ["%s:%d uses %s (R4)" % (mod, node.lineno, hit) for hit in sorted(used & FORBIDDEN_NAMES)]
    if classes != part["classes"]:
        problems.append("classes are %s, R4 allows %s" % (classes, part["classes"]))
    return problems


def table_problems(part, tree):
    """D2, R3: PathGuard's body is the kept methods and one binding per moved method, each to the home
    module's function of that name; none missing, none extra."""
    cls = class_node(tree)
    if cls is None:
        return ["%s has no class %s (R3)" % (part["entry"]["module"], CLASS)]
    aliases = module_aliases(tree, set(part["modules"]))
    moved = dict(moved_methods(part).values())
    problems, defs, binds = [], [], {}
    for idx, stmt in enumerate(cls.body):
        if isinstance(stmt, ast.FunctionDef):
            defs.append(stmt.name)
            rec = part["kept_methods"].get(stmt.name)
            if rec and param_tokens(signature_of(stmt)) != param_tokens(rec["signature"]):
                problems.append("method %s%s, the partition has %s%s (R3)" % (stmt.name, signature_of(stmt),
                                                                           stmt.name, rec["signature"]))
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            binds.setdefault(stmt.targets[0].id, []).append(stmt.value)
        elif not (idx == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)):
            problems.append("%s:%d %s holds a %s (R3)" % (part["entry"]["module"], stmt.lineno, CLASS,
                                                         type(stmt).__name__))
    problems += ["%s lost the method %s (R3)" % (CLASS, n) for n in sorted(set(part["kept_methods"]) - set(defs))]
    problems += ["%s has the method %s, which the partition moves or does not know (R3)" % (CLASS, n)
                 for n in sorted(set(defs) - set(part["kept_methods"]))]
    for name, mod in sorted(moved.items()):
        values = binds.get(name, [])
        if not values:
            problems.append("%s.%s is not bound to %s.%s: an unbound method fails open (R3)" % (CLASS, name, mod, name))
        elif len(values) > 1 or name in defs:
            problems.append("%s.%s is bound more than once (R3)" % (CLASS, name))
        else:
            value = values[0]
            ok = isinstance(value, ast.Attribute) and value.attr == name and isinstance(value.value, ast.Name)
            if not ok:
                problems.append("%s.%s is bound to %s, not to %s.%s (R3)" % (CLASS, name, ast.unparse(value), mod, name))
            elif value.value.id not in aliases:
                problems.append("%s.%s: %s is not imported as a module of guard (R3)" % (CLASS, name, value.value.id))
            elif aliases[value.value.id] != mod:
                problems.append("%s.%s is bound to %s.%s, its home is %s (R3)" % (CLASS, name, aliases[value.value.id],
                                                                                    name, mod))
    problems += ["%s binds %s, which is no moved method of the partition (R3)" % (CLASS, n)
                 for n in sorted(set(binds) - set(moved))]
    return problems


def entry_problems(part, path):
    """R2, D1, Q25: the entry is small, defines PathGuard and check only, re-exports nothing, binds the
    moved methods, and imports what the partition records."""
    spec = part["entry"]
    text = read_text(path)
    tree = ast.parse(text, filename=path)
    problems = []
    count = len(text.splitlines())
    if count >= spec["max_lines"]:
        problems.append("%s has %d lines, the limit is under %d (R2)" % (spec["module"], count, spec["max_lines"]))
    defined = set(module_names(tree))
    if defined != set(spec["names"]):
        problems.append("%s defines %s, D1 has %s (R2)" % (spec["module"], sorted(defined), sorted(spec["names"])))
    problems += ["%s:%d `__all__` re-exports (Q25)" % (spec["module"], n.lineno) for n in tree.body
                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)]
    problems += shape_problems(spec["module"], tree, ENTRY_LEVEL)
    doc = ast.get_docstring(tree, clean=False) or ""
    if hashlib.sha256(doc[:part["entry_docstring_chars"]].encode()).hexdigest() != part["entry_docstring_sha256"]:
        problems.append("%s lost the first %d characters of its docstring (R11)" % (spec["module"],
                                                                                   part["entry_docstring_chars"]))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "check" in funcs and param_tokens(signature_of(funcs["check"])) != ["ctx"]:
        problems.append("check%s, the hook calls check(ctx) (R1)" % signature_of(funcs["check"]))
    problems += table_problems(part, tree)
    problems += import_problems(spec["module"], tree, set(part["modules"]))
    problems += ["%s:%d __file__ (R6a)" % (spec["module"], n) for n in file_uses(tree)]
    problems += ["%s:%d `global %s` (R4)" % (spec["module"], n.lineno, ", ".join(n.names)) for n in ast.walk(tree)
                 if isinstance(n, ast.Global)]
    real = sibling_imports(tree, set(part["modules"]))
    if real != set(part["modules"][spec["module"]]["imports"]):
        problems.append("%s imports %s, the partition has %s (R10)" % (
            spec["module"], sorted(real), part["modules"][spec["module"]]["imports"]))
    return problems


def layout_problems(base, part, quiet=True):
    """The final-phase checks on the tree at `base` (hooks/guard/ beneath it); [] when right."""
    problems = []
    trees = {}
    for mod in new_modules(part):
        path = module_path(base, mod)
        if not os.path.isfile(path):
            problems.append("%s.py is missing (R3)" % mod)
            continue
        trees[mod] = parse(path)
        problems += module_problems(part, mod, path)
        count = line_count(path)
        if not quiet:
            print("%s.py: %d lines%s" % (mod, count, "  (over %d: note it in task.md)" % ADVISORY_LINES
                                         if count > ADVISORY_LINES else ""))
    entry = entry_path(base, part)
    problems += entry_problems(part, entry)
    entry_tree = parse(entry)
    trees[part["entry"]["module"]] = entry_tree
    if not quiet:
        print("%s.py: %d lines" % (part["entry"]["module"], line_count(entry)))
    layer = layers_of(part)
    real = {mod: sibling_imports(tree, set(layer)) for mod, tree in trees.items()}
    problems += graph_problems(layer, real)
    problems += ["%s imports the entry %s (R10)" % (m, part["entry"]["module"]) for m, deps in sorted(real.items())
                 if part["entry"]["module"] in deps and m != part["entry"]["module"]]
    problems += r4_problems(part, trees)
    problems += unbound_problems(part, trees)
    return problems


# --------------------------------------------------------------------------------------
# the copy check (D6): every moved node is its source node


def move_problems(source_text, base, part=None):
    """Compare the original paths.py (`source_text`) with each module present under `base`: every name homed
    there equals its source node once D3's renames are applied (a method compares as a top-level function),
    and a module defines nothing but its partition names. Once the entry is final its kept methods and
    `check` are compared too. Returns the list of problems."""
    part = part or PART
    tree = ast.parse(source_text)
    top = module_names(tree)
    methods = class_methods(tree)
    renames = part["renames"]
    problems = []
    for mod in present_modules(base, part):
        found = module_names(parse(module_path(base, mod)))
        spec = part["modules"][mod]
        for name in spec["defs"]:
            rec = part["defs"][name]
            src = methods.get(rec["old_name"]) if rec["kind"] == "method" else top.get(name, (0, None, 0))[1]
            if src is None:
                problems.append("%s: %s is not in the source (D6)" % (mod, name))
            elif name not in found:
                problems.append("%s: %s is missing (D6)" % (mod, name))
            elif canon(normalised(src, renames)) != canon(normalised(found[name][1], {})):
                problems.append("%s: %s differs from the source (D6)" % (mod, name))
        problems += ["%s: defines %s, not a name of its partition (D6)" % (mod, n)
                     for n in sorted(set(found) - set(spec["defs"]))]
    entry = entry_path(base, part)
    if os.path.isfile(entry) and entry_is_final(base, part):
        tree_e = parse(entry)
        kept = class_methods(tree_e)
        for name in part["kept_methods"]:
            if name not in methods:
                problems.append("%s: %s is not in the source (D6)" % (CLASS, name))
            elif name not in kept:
                problems.append("%s: %s is missing (D6)" % (CLASS, name))
            elif canon(normalised(methods[name], renames)) != canon(normalised(kept[name], {})):
                problems.append("%s.%s differs from the source (D6)" % (CLASS, name))
        funcs = {n.name: n for n in tree_e.body if isinstance(n, ast.FunctionDef)}
        if "check" in top and "check" not in funcs:
            problems.append("check is missing (D6)")
        elif "check" in top and canon(normalised(top["check"][1], {})) != canon(normalised(funcs["check"], {})):
            problems.append("check differs from the source (D6)")
    return problems


def moved_from(rev):
    """The command-line form: exit 1 on any problem, 0 on none, 2 when git cannot show the revision."""
    part = PART
    done = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (rev, part["source"])], capture_output=True,
                          encoding="utf-8", check=False)
    if done.returncode != 0:
        print("git show %s:%s failed: %s" % (rev, part["source"], done.stderr.strip()))
        return 2
    problems = move_problems(done.stdout, ROOT, part)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("move_problems: none")
    return 0


# --------------------------------------------------------------------------------------
# the single-phase checks, on the file that still holds the code


def home_problems(tree, part):
    """Every top-level name and every PathGuard method of the source has one home in the partition, and
    the partition names nothing the source lacks."""
    names = set(module_names(tree))
    methods = set(class_methods(tree))
    owner = owners_of(part)
    top = {n for n, rec in part["defs"].items() if rec["kind"] != "method"}
    moved = set(moved_methods(part))
    kept = set(part["kept_methods"])
    problems = ["%s is not in the partition" % n for n in sorted(names - top)]
    problems += ["%s is not in the source" % n for n in sorted(top - names)]
    problems += ["PathGuard.%s is not in the partition" % n for n in sorted(methods - moved - kept)]
    problems += ["PathGuard.%s is not in the source" % n for n in sorted((moved | kept) - methods)]
    problems += ["%s is homed in %s" % (n, homes) for n, homes in sorted(owner.items()) if len(homes) != 1]
    problems += ["%s is in no module's defs" % n for n in sorted(set(part["defs"]) - set(owner))]
    problems += ["%s: module of the record is not the module that lists it" % n for n, rec in sorted(part["defs"].items())
                 if n in owner and owner[n] != [rec["module"]]]
    problems += ["%s is both a moved method and a top-level name" % n
                 for n in sorted({new for new, _m in moved_methods(part).values()} & names)]
    return problems


def shape_of_source_problems(tree, part):
    """Kinds, signatures and value hashes against the source."""
    problems = []
    top = module_names(tree)
    methods = class_methods(tree)
    for name, (kind, node, value) in top.items():
        rec = part["defs"].get(name)
        if rec is None:
            continue
        if rec["kind"] != kind:
            problems.append("%s is a %s, the partition says %s" % (name, kind, rec["kind"]))
        elif kind == "function" and param_tokens(signature_of(node)) != param_tokens(rec["signature"]):
            problems.append("%s%s, the partition has %s" % (name, signature_of(node), rec["signature"]))
        elif kind == "const" and rec["value_hash"] and (value is None or hash_of(value) != rec["value_hash"]):
            problems.append("%s has another value than the partition's" % name)
    for old, (new, _mod) in moved_methods(part).items():
        if old in methods and param_tokens(signature_of(methods[old])) != param_tokens(part["defs"][new]["signature"]):
            problems.append("PathGuard.%s%s, the partition has %s" % (old, signature_of(methods[old]),
                                                                      part["defs"][new]["signature"]))
    for old, rec in part["kept_methods"].items():
        if old in methods and param_tokens(signature_of(methods[old])) != param_tokens(rec["signature"]):
            problems.append("PathGuard.%s%s, the partition has %s" % (old, signature_of(methods[old]), rec["signature"]))
    return problems


def whole_problems(base, part):
    """All the single-phase checks on paths.py under `base`, as [(check name, [problems])]."""
    tree = parse(entry_path(base, part))
    graph = source_graph(tree, part)
    derived = module_edges(part, graph)
    edge_problems = ["%s: derive the partition again: it imports %s, the call graph has %s" % (
        mod, spec["imports"], sorted(derived[mod])) for mod, spec in part["modules"].items()
        if sorted(derived[mod]) != sorted(spec["imports"])]
    doc = ast.get_docstring(tree, clean=False) or ""
    pin = [] if hashlib.sha256(doc[:part["entry_docstring_chars"]].encode()).hexdigest() == \
        part["entry_docstring_sha256"] else ["the docstring is not the one the partition pins"]
    return [
        ("homes", home_problems(tree, part)),
        ("shapes", shape_of_source_problems(tree, part)),
        ("edges", edge_problems),
        ("graph", graph_problems(layers_of(part), derived)),
        ("labels", label_problems(part, label_units(tree, part))),
        ("global", ["line %d" % n.lineno for n in ast.walk(tree) if isinstance(n, ast.Global)]),
        ("self calls", unbound_problems(part, {"source": tree}, source=True)),
        ("docstring", pin),
    ]


# --------------------------------------------------------------------------------------
# which phase the tree is in


def entry_is_final(base, part):
    """True once paths.py defines only the entry's names."""
    names = set(module_names(parse(entry_path(base, part))))
    return names <= set(part["entry"]["names"])


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

    def test_every_name_has_one_home_a_kind_and_a_label(self):
        owner = owners_of(self.part)
        for name, homes in owner.items():
            self.assertEqual(len(homes), 1, "%s is in %s" % (name, homes))
        every = dict(self.part["defs"], **{"PathGuard." + n: r for n, r in self.part["kept_methods"].items()})
        for name, rec in every.items():
            self.assertIn(rec["label"], ("core", "shell"), name)
            self.assertIn(rec["kind"], ("function", "class", "const", "method"), name)
        self.assertEqual(set(owner), set(self.part["defs"]))

    def test_the_modules_are_the_plans_and_layers_are_numbers(self):
        self.assertEqual(new_modules(self.part), sorted(
            "paths_base paths_fs paths_shell paths_human paths_interp paths_classify paths_movers "
            "paths_bash".split()))
        self.assertEqual(self.part["entry"]["module"], "paths")
        self.assertEqual(self.part["source"], "hooks/guard/paths.py")
        self.assertRegex(self.part["source_sha256"], r"^[0-9a-f]{64}$")
        for mod, spec in self.part["modules"].items():
            self.assertIsInstance(spec["layer"], int, mod)
        layers = layers_of(self.part)
        self.assertEqual([layers[m] for m in ("paths_base", "paths_fs", "paths_shell")], [0, 0, 0])
        self.assertEqual([layers[m] for m in ("paths_human", "paths_interp", "paths_classify", "paths_movers")],
                         [1, 1, 1, 1])
        self.assertEqual((layers["paths_bash"], layers["paths"]), (2, 3))

    def test_the_entry_is_d1(self):
        """D1, R2: PathGuard and check, nine kept methods, under 200 lines. phys_path stays a method: it reads
        no `self`, and as a function with `self` first it is W0613 (unused-argument), which R7 does not allow."""
        spec = self.part["entry"]
        self.assertEqual(sorted(spec["names"]), ["PathGuard", "check"])
        self.assertEqual(spec["max_lines"], 200)
        self.assertEqual(sorted(self.part["modules"]["paths"]["defs"]), sorted(spec["names"]))
        self.assertEqual(sorted(self.part["kept_methods"]), sorted(
            "__init__ clock_ok work_cap work_clock _state_file _task_line task_in_flight phys_path check".split()))

    def test_the_methods_are_all_accounted_for(self):
        """36 methods: nine stay, 27 move as functions under D2 and D3."""
        moved = moved_methods(self.part)
        self.assertEqual(len(moved), 27)
        self.assertEqual(len(moved) + len(self.part["kept_methods"]), 36)
        self.assertEqual({o: n for o, (n, _m) in moved.items() if o != n}, self.part["renames"])
        self.assertEqual(self.part["renames"], {"_mode": "loc_mode", "_loc_pat": "loc_pat", "_loc_text": "loc_text",
                                                "_from_loc": "from_loc", "_roots_under": "roots_under"})
        for new, rec in self.part["defs"].items():
            if rec["kind"] == "method":
                self.assertEqual(rec["method_of"], "PathGuard", new)
                self.assertTrue(rec["signature"].startswith("(self"), new)

    def test_the_classes_are_the_ones_r4_allows(self):
        self.assertEqual(self.part["classes"], {"LoopError": "OSError", "PathGuard": None, "MoverState": None})
        for name in self.part["classes"]:
            self.assertEqual(self.part["defs"][name]["kind"], "class", name)

    def test_recorded_imports_go_downward_and_acyclic(self):
        edges = {m: set(s["imports"]) for m, s in self.part["modules"].items()}
        self.assertEqual(graph_problems(layers_of(self.part), edges), [])

    def test_the_docstring_prefix_is_pinned(self):
        self.assertRegex(self.part["entry_docstring_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(self.part["entry_docstring_chars"], 100)


@unittest.skipIf(PHASE == "final", "paths.py is the entry: the partition stands alone")
class TestPartitionAgainstWhole(unittest.TestCase):
    """Phases single and copy: the partition against the file that still holds the code, on paper."""

    @classmethod
    def setUpClass(cls):
        cls.checks = dict(whole_problems(ROOT, PART))

    def only(self, name):
        self.assertEqual(self.checks[name], [], "\n".join(self.checks[name]))

    def test_every_name_and_method_of_paths_is_assigned_once(self):
        self.only("homes")

    def test_kinds_signatures_and_values_are_pathss(self):
        self.only("shapes")

    def test_the_recorded_edges_are_the_call_graphs(self):
        self.only("edges")

    def test_the_import_graph_on_paper_is_acyclic_and_downward(self):
        """R10: found before any module is written, not after a move."""
        self.only("graph")

    def test_core_names_touch_nothing(self):
        self.only("labels")

    def test_no_global_in_the_file(self):
        self.only("global")

    def test_every_self_call_has_a_method_in_the_partition(self):
        self.only("self calls")

    def test_the_docstring_is_pinned_to_the_file(self):
        self.only("docstring")


@unittest.skipIf(PHASE == "final", "paths.py is the entry: the full form below applies")
class TestModulesPresent(unittest.TestCase):
    """Phases single and copy: each module the steps have written so far, on its own (none is fine)."""

    def test_each_present_module_is_the_partitions(self):
        problems = []
        for mod in present_modules(ROOT, PART):
            problems += module_problems(PART, mod, module_path(ROOT, mod))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_each_moved_node_is_its_source_node(self):
        """D6, in the copy phase: the paths.py on disk is the source."""
        if not present_modules(ROOT, PART):
            self.skipTest("no module written yet")
        problems = move_problems(read_text(entry_path(ROOT, PART)), ROOT)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_sizes_are_reported(self):
        """Advisory: over 600 lines is noted in the task report, never a failure."""
        for mod in present_modules(ROOT, PART):
            count = line_count(module_path(ROOT, mod))
            print("%s.py: %d lines%s" % (mod, count, "  (over %d: note it in task.md)" % ADVISORY_LINES
                                         if count > ADVISORY_LINES else ""))


@unittest.skipUnless(PHASE == "final", "paths.py still defines the code: phases single and copy above apply")
class TestCutOver(unittest.TestCase):
    """Phase final: paths.py is the entry. One call to `layout_problems` on the real tree; the
    pieces are separate tests so a failure names its requirement."""

    @classmethod
    def setUpClass(cls):
        cls.problems = layout_problems(ROOT, PART, quiet=False)

    def only(self, *needles):
        found = [p for p in self.problems if any(n in p for n in needles)]
        self.assertEqual(found, [], "\n".join(found))

    def test_the_entry_is_small_and_defines_pathguard_and_check(self):
        self.only("(R2)", "(Q25)", "(R11)", "(R1)")

    def test_all_eight_modules_are_there_and_each_is_the_partitions(self):
        self.only(".py is missing", ": missing ", " is not the partition's", "partition has", "partition says",
                  "another value", "(D6)")

    def test_the_method_table_binds_every_moved_method(self):
        self.only("(R3)", "(D3)")

    def test_the_import_graph_from_the_real_imports_is_acyclic_and_downward(self):
        self.only("(R10)")

    def test_no_global_and_no_file(self):
        self.only("`global", "__file__")

    def test_the_imports_are_the_packages_style_and_stay_in_hooks(self):
        self.only("(D4)", "(R15)")

    def test_the_forbidden_constructs_of_r4(self):
        self.only("(R4)")

    def test_labels(self):
        self.only("(R16)")

    def test_nothing_else_is_wrong(self):
        self.assertEqual(self.problems, [], "\n".join(self.problems))


# --------------------------------------------------------------------------------------
# the checks themselves, on small synthetic trees


class TestAnalysis(unittest.TestCase):
    """The reading of a source on small synthetic ones: it sees what it must and passes what it may."""

    SOURCE = ("import os\n"
              "LIMIT = 5\nA, B = (1, 2)\n\n"
              "def read(path):\n    with open(path) as fh:\n        return fh.read()\n\n"
              "def pure(x, read=LIMIT):\n    return [read for read in x]\n\n"
              "def user(path):\n    return read(path) + LIMIT\n\n"
              "class Holder:\n    def read(self, p):\n        return read(p)\n")

    def test_the_names_of_a_file(self):
        names = module_names(ast.parse(self.SOURCE))
        self.assertEqual(sorted(names), ["A", "B", "Holder", "LIMIT", "pure", "read", "user"])
        self.assertEqual(names["Holder"][0], "class")
        self.assertEqual(signature_of(names["pure"][1]), "(x, read=LIMIT)")
        self.assertEqual(duplicate_names(ast.parse("A = 1\nA = 2\ndef f(): pass\n")), ["A"])

    def test_a_reference_is_a_reference_only_when_nothing_shadows_it(self):
        tree = ast.parse(self.SOURCE)
        names = set(module_names(tree))
        top = module_names(tree)
        self.assertEqual(references(top["user"][1], names), {"read", "LIMIT"})
        self.assertEqual(references(top["pure"][1], names), {"LIMIT"}, "the parameter and the comprehension variable are `read`'s own")
        self.assertEqual(references(top["Holder"][1], names), {"read"}, "a method called read is not the module's read")

    def test_io_is_what_touches_a_file_a_clock_or_a_process(self):
        def hit(code):
            return reaches_io(ast.parse(code))
        self.assertEqual(hit("open(p)"), "open")
        self.assertEqual(hit("os.path.join(a, b)"), "")
        self.assertEqual(hit("os.path.isfile(a)"), "os.path.isfile")
        self.assertEqual(hit("subprocess.run(a)"), "subprocess")
        self.assertEqual(hit("datetime.now(tz)"), "datetime.now")
        self.assertEqual(hit("is_file(a)"), "is_file")
        self.assertEqual(hit("self.ctx.clock.seconds()"), "self.ctx.clock.seconds")
        self.assertEqual(hit("self.m.grep_q(a, b)"), "")
        self.assertEqual(hit("os.fsdecode(b_bytes(a))"), "")

    def test_the_graph_check_flags_an_upward_edge_a_same_layer_edge_and_a_cycle(self):
        layer = {"low": 0, "mid": 1, "top": 2}
        self.assertEqual(graph_problems(layer, {"low": set(), "mid": {"low"}, "top": {"low", "mid"}}), [])
        self.assertTrue(any("upward edge: low" in p for p in graph_problems(layer, {"low": {"mid"}, "mid": set()})))
        self.assertTrue(any("upward edge" in p for p in graph_problems(layer, {"mid": {"mid"}})))
        cyc = graph_problems({"a": 0, "b": 0}, {"a": {"b"}, "b": {"a"}})
        self.assertTrue(any(p.startswith("cycle: ") for p in cyc), cyc)

    def test_the_real_imports_of_a_tree(self):
        tree = ast.parse("import os\nimport guard.paths_fs\nfrom guard.paths_base import T\nfrom guard import paths_shell as ps, common\n"
                         "from guard.common import Deny\n")
        mods = {"paths_fs", "paths_base", "paths_shell", "paths_bash"}
        self.assertEqual(sibling_imports(tree, mods), {"paths_fs", "paths_base", "paths_shell"})
        self.assertEqual(module_aliases(tree, mods), {"ps": "paths_shell"})
        self.assertEqual(import_problems("m", tree, mods), [])
        bad = ast.parse("import rr_state\nfrom skills.ai_task import x\nfrom . import y\nimport paths_base\nimport state\n")
        self.assertEqual(len(import_problems("m", bad, mods)), 5)

    def test_d3s_renames_apply_to_a_def_and_to_self_attributes_only(self):
        node = ast.parse("def f(self):\n    return self._mode() + other._mode()\n").body[0]
        out = normalised(node, {"_mode": "loc_mode", "f": "g"})
        self.assertEqual(ast.unparse(out), "def g(self):\n    return self.loc_mode() + other._mode()")
        self.assertEqual(node.name, "f", "the source node is not changed")

    def test_a_dedented_method_keeps_its_docstring_for_the_compare(self):
        method = ast.parse("class C:\n    def f(self):\n        \"\"\"One\n        two.\"\"\"\n        return 1\n").body[0].body[0]
        moved = ast.parse("def f(self):\n    \"\"\"One\n    two.\"\"\"\n    return 1\n").body[0]
        other = ast.parse("def f(self):\n    \"\"\"One\n    three.\"\"\"\n    return 1\n").body[0]
        self.assertEqual(canon(normalised(method, {})), canon(normalised(moved, {})))
        self.assertNotEqual(canon(normalised(method, {})), canon(normalised(other, {})))

    def test_the_methods_a_class_has_and_the_functions_where_self_is_a_guard(self):
        tree = ast.parse("class PathGuard:\n    def a(self): pass\n    b = a\n\n"
                         "def c(self): pass\ndef d(x): pass\nclass Other:\n    def e(self): pass\n")
        self.assertEqual(list(class_methods(tree)), ["a"])
        self.assertEqual([f.name for f in guard_functions(tree)], ["c", "a"])


SYNTH_SOURCE = (
    '"""The guard. Nothing else."""\n'
    "from guard.common import exists, text_to_b\n\n"
    "T = text_to_b\n"
    "LIMIT = 5\n\n\n"
    "class LoopError(OSError):\n    pass\n\n\n"
    "def lexnorm(path):\n    return path\n\n\n"
    "class PathGuard:\n"
    "    def __init__(self, ctx):\n        self.ctx = ctx\n\n"
    "    def check(self):\n        return self.classify(self.ctx)\n\n"
    "    def classify(self, p):\n        return self._mode() + T(p)\n\n"
    "    def _mode(self):\n        return LIMIT\n\n"
    "    def probe(self, p):\n        return exists(p)\n\n\n"
    "class MoverState:\n    def __init__(self):\n        self.n = 0\n        self.reset()\n\n"
    "    def reset(self):\n        self.n = 0\n\n\n"
    "def check(ctx):\n    PathGuard(ctx).check()\n")
SYNTH_FILES = {
    "hooks/guard/paths_base.py": (
        '"""Base: core, moved from paths.py unchanged."""\n'
        "from guard.common import text_to_b\n\n"
        "T = text_to_b\n"
        "LIMIT = 5\n"),
    "hooks/guard/paths_fs.py": (
        '"""Fs: core, moved from paths.py unchanged."""\n\n\n'
        "class LoopError(OSError):\n    pass\n\n\n"
        "def lexnorm(path):\n    return path\n\n\n"
        "class MoverState:\n    def __init__(self):\n        self.n = 0\n        self.reset()\n\n"
        "    def reset(self):\n        self.n = 0\n"),
    "hooks/guard/paths_classify.py": (
        '"""Classify: shell, moved from paths.py unchanged."""\n'
        "from guard.common import exists\n"
        "from guard.paths_base import LIMIT, T\n\n\n"
        "def classify(self, p):\n    return self.loc_mode() + T(p)\n\n\n"
        "def loc_mode(self):\n    return LIMIT\n\n\n"
        "def probe(self, p):\n    return exists(p)\n"),
    "hooks/guard/paths.py": (
        '"""The guard. Nothing else."""\n'
        "from guard import paths_classify\n\n\n"
        "class PathGuard:\n"
        "    def __init__(self, ctx):\n        self.ctx = ctx\n\n"
        "    def check(self):\n        return self.classify(self.ctx)\n\n"
        "    classify = paths_classify.classify\n"
        "    loc_mode = paths_classify.loc_mode\n"
        "    probe = paths_classify.probe\n\n\n"
        "def check(ctx):\n    PathGuard(ctx).check()\n"),
}


def synthetic_partition():
    def rec(kind, label, signature="", value=None, **more):
        return dict({"kind": kind, "label": label, "signature": signature, "value_hash": value}, **more)

    def value(code):
        return hash_of(ast.parse(code, mode="eval").body)

    def mod(name, **more):
        return dict({"module": name}, **more)
    defs = {
        "T": mod("paths_base", **rec("const", "core", value=value("text_to_b"))),
        "LIMIT": mod("paths_base", **rec("const", "core", value=value("5"))),
        "LoopError": mod("paths_fs", **rec("class", "core")),
        "lexnorm": mod("paths_fs", **rec("function", "core", "(path)")),
        "MoverState": mod("paths_fs", **rec("class", "core")),
        "classify": mod("paths_classify", **rec("method", "core", "(self, p)", method_of="PathGuard", old_name="classify")),
        "loc_mode": mod("paths_classify", **rec("method", "core", "(self)", method_of="PathGuard", old_name="_mode")),
        "probe": mod("paths_classify", **rec("method", "shell", "(self, p)", method_of="PathGuard", old_name="probe")),
        "PathGuard": mod("paths", **rec("class", "shell")),
        "check": mod("paths", **rec("function", "shell", "(ctx)")),
    }
    return {
        "schema": 1,
        "source": "hooks/guard/paths.py",
        "source_sha256": hashlib.sha256(SYNTH_SOURCE.encode()).hexdigest(),
        "entry_docstring_sha256": hashlib.sha256("The guard. Nothing else.".encode()).hexdigest(),
        "entry_docstring_chars": len("The guard. Nothing else."),
        "entry": {"module": "paths", "max_lines": 30, "names": ["PathGuard", "check"]},
        "classes": {"LoopError": "OSError", "PathGuard": None, "MoverState": None},
        "renames": {"_mode": "loc_mode"},
        "modules": {
            "paths_base": {"layer": 0, "imports": [], "defs": ["T", "LIMIT"]},
            "paths_fs": {"layer": 0, "imports": [], "defs": ["LoopError", "lexnorm", "MoverState"]},
            "paths_classify": {"layer": 1, "imports": ["paths_base"], "defs": ["classify", "loc_mode", "probe"]},
            "paths": {"layer": 2, "imports": ["paths_classify"], "defs": ["PathGuard", "check"]},
        },
        "kept_methods": {"__init__": rec("method", "core", "(self, ctx)", module="paths"),
                         "check": rec("method", "core", "(self)", module="paths")},
        "defs": defs,
    }


SYNTHETIC = synthetic_partition()


class SyntheticCase(unittest.TestCase):
    """A tree built in a temporary directory, edited by one replacement at a time."""

    def tree(self, edits=None, extra=None):
        tmp_name = tempfile.mkdtemp(prefix="guard-layout-")
        self.addCleanup(shutil.rmtree, tmp_name, ignore_errors=True)
        files = dict(SYNTH_FILES)
        for rel, edit in (edits or {}).items():
            for old, new in (edit if isinstance(edit, list) else [edit]):
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

    def moved(self, edits=None):
        return move_problems(SYNTH_SOURCE, self.tree(edits), SYNTHETIC)


class TestSyntheticTree(SyntheticCase):
    """The checks on the modules, the graph and the copy check: a good tree passes, and each rule fails on one
    edit of it. They show the checks work before the real tree reaches the final phase."""

    def test_a_good_tree_passes(self):
        tree = self.tree()
        self.assertEqual(layout_problems(tree, SYNTHETIC), [])
        self.assertEqual(move_problems(SYNTH_SOURCE, tree, SYNTHETIC), [])
        self.assertEqual(phase_of(tree, SYNTHETIC), "final")

    def test_the_phase_is_told_from_the_disk(self):
        whole = {"hooks/guard/paths.py": SYNTH_SOURCE}
        tree = self.tree(extra=whole)
        self.assertEqual(phase_of(tree, SYNTHETIC), "copy")
        for mod in new_modules(SYNTHETIC):
            os.remove(module_path(tree, mod))
        self.assertEqual(phase_of(tree, SYNTHETIC), "single")

    def test_the_single_phase_checks_pass_on_the_whole_source_and_fail_on_a_wrong_partition(self):
        tree = self.tree(extra={"hooks/guard/paths.py": SYNTH_SOURCE})
        self.assertEqual([(n, p) for n, p in whole_problems(tree, SYNTHETIC) if p], [])
        wrong = json.loads(json.dumps(SYNTHETIC))
        wrong["modules"]["paths_classify"]["defs"].remove("probe")
        wrong["modules"]["paths_classify"]["imports"] = ["paths_base", "paths_fs"]
        wrong["defs"]["T"]["value_hash"] = "0" * 12
        wrong["defs"]["lexnorm"]["signature"] = "(path, more)"
        wrong["defs"]["probe"]["label"] = "core"
        bad = dict(whole_problems(tree, wrong))
        for name in ("homes", "shapes", "edges", "labels"):
            self.assertTrue(bad[name], name)
        self.assertIn("core name PathGuard.probe reaches I/O (exists) (R16)", bad["labels"])

    def test_the_single_phase_sees_a_global_a_stray_self_call_and_an_upward_edge(self):
        text = SYNTH_SOURCE.replace("return LIMIT\n", "global X\n        return self.nope() + LIMIT\n", 1)
        tree = self.tree(extra={"hooks/guard/paths.py": text})
        bad = dict(whole_problems(tree, SYNTHETIC))
        self.assertTrue(bad["global"])
        self.assertTrue(any("self.nope() is no method" in p for p in bad["self calls"]))
        up = json.loads(json.dumps(SYNTHETIC))
        up["modules"]["paths_base"]["layer"] = 5
        self.assertTrue(dict(whole_problems(tree, up))["graph"])

    def test_a_changed_body_is_found(self):
        got = self.moved({"hooks/guard/paths_classify.py": ("return self.loc_mode() + T(p)", "return self.loc_mode() - T(p)")})
        self.assertEqual(got, ["paths_classify: classify differs from the source (D6)"])
        got = self.moved({"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 6")})
        self.assertEqual(got, ["paths_base: LIMIT differs from the source (D6)"])
        got = self.moved({"hooks/guard/paths_fs.py": ("def lexnorm(path):\n    return path", "def lexnorm(path):\n    return path or ''")})
        self.assertEqual(got, ["paths_fs: lexnorm differs from the source (D6)"])

    def test_a_renamed_use_left_as_it_was_is_found(self):
        self.found("self._mode was renamed loc_mode (D3)", {"hooks/guard/paths_classify.py": ("self.loc_mode()", "self._mode()")})
        got = self.moved({"hooks/guard/paths_classify.py": ("self.loc_mode()", "self._mode()")})
        self.assertEqual(got, ["paths_classify: classify differs from the source (D6)"])

    def test_a_missing_extra_or_duplicate_name_is_found(self):
        self.found("paths_classify: missing probe", {"hooks/guard/paths_classify.py": ("def probe", "def probe_")})
        self.found("paths_base: extra is not the partition's", {"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 5\nextra = 1")})
        self.found("paths_base defines LIMIT twice", {"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 5\nLIMIT = 5")})
        got = self.moved({"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 5\nextra = 1")})
        self.assertEqual(got, ["paths_base: defines extra, not a name of its partition (D6)"])
        got = self.moved({"hooks/guard/paths_classify.py": ("def probe", "def probe_")})
        self.assertIn("paths_classify: probe is missing (D6)", got)
        tree = self.tree()
        os.remove(module_path(tree, "paths_base"))
        self.assertIn("paths_base.py is missing (R3)", layout_problems(tree, SYNTHETIC))
        self.found("a top-level Expr", {"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 5\nprint(LIMIT)")})
        self.found("has no module docstring", {"hooks/guard/paths_base.py": ('"""Base: core, moved from paths.py unchanged."""\n', "")})

    def test_a_changed_signature_is_found(self):
        self.found("partition has lexnorm(path)", {"hooks/guard/paths_fs.py": ("def lexnorm(path)", "def lexnorm(path, more)")})
        self.found("partition has probe(self, p)", {"hooks/guard/paths_classify.py": ("def probe(self, p)", "def probe(p)")})
        self.found("another value than paths.py's", {"hooks/guard/paths_base.py": ("LIMIT = 5", "LIMIT = 6")})

    def test_an_upward_edge_and_a_cycle_are_found(self):
        edit = {"hooks/guard/paths_base.py": ("from guard.common import text_to_b\n",
                                              "from guard.common import text_to_b\nfrom guard.paths_classify import probe\n")}
        self.found("upward edge: paths_base (layer 0) imports paths_classify (layer 1)", edit)
        self.found("cycle:", edit)
        self.found("paths_base imports ['paths_classify'], the partition has []", edit)

    def test_an_import_of_the_entry_is_found(self):
        self.found("paths_classify imports the entry paths", {"hooks/guard/paths_classify.py": (
            "from guard.paths_base import", "from guard.paths import PathGuard\nfrom guard.paths_base import")})

    def test_an_import_missing_from_the_edges_is_found(self):
        self.found("paths_classify imports [], the partition has ['paths_base']", {"hooks/guard/paths_classify.py": (
            "from guard.paths_base import LIMIT, T\n", "T = LIMIT = 1\n")})

    def test_an_extra_class_and_a_forbidden_construct_are_found(self):
        self.found("class", {"hooks/guard/paths_fs.py": ("def lexnorm", "class Extra:\n    pass\n\n\ndef lexnorm")})
        self.found("classes are", {"hooks/guard/paths_fs.py": ("class LoopError(OSError)", "class LoopError(Exception)")})
        self.found("uses staticmethod (R4)", {"hooks/guard/paths_fs.py": ("def lexnorm", "x = staticmethod\n\n\ndef lexnorm")})
        self.found("uses ABC (R4)", {"hooks/guard/paths_fs.py": ("def lexnorm", "from abc import ABC\n\n\ndef lexnorm")})

    def test_a_global_and_file_are_found(self):
        self.found("`global X` (R4)", {"hooks/guard/paths_classify.py": ("return LIMIT", "global X\n    return LIMIT")})
        self.found("__file__ (R6a", {"hooks/guard/paths_fs.py": ("return path", "return __file__")})
        self.found("paths:", {"hooks/guard/paths.py": ("def check(ctx):\n    PathGuard(ctx).check()", "def check(ctx):\n    global X\n    PathGuard(ctx).check()")})

    def test_hook_isolation_is_found(self):
        self.found("imports rr_state (R15)", {"hooks/guard/paths_base.py": ("LIMIT = 5", "import rr_state\nLIMIT = 5")})
        self.found("imports state (R15)", {"hooks/guard/paths_fs.py": ('"""Fs: core, moved from paths.py unchanged."""\n',
                                                                      '"""Fs: core, moved from paths.py unchanged."""\nimport state\n')})
        self.found("imports skills.ai_task.x (R15)", {"hooks/guard/paths_classify.py": (
            "from guard.common import exists\n", "from guard.common import exists\nimport skills.ai_task.x\n")})

    def test_a_core_module_that_reaches_for_io_is_found(self):
        self.found("paths_base: all names are core, yet it imports os (R16)", {"hooks/guard/paths_base.py": (
            "from guard.common import text_to_b\n", "import os\nfrom guard.common import text_to_b\n")})
        self.found("yet it imports exists (R16)", {"hooks/guard/paths_base.py": (
            "from guard.common import text_to_b\n", "from guard.common import exists, text_to_b\n")})


class TestSyntheticEntry(SyntheticCase):
    """The entry's contract and the method table: each rule fails on one edit of a good tree."""

    def test_a_missing_import_is_found(self):
        self.found("paths_classify is not imported as a module of guard",
                   {"hooks/guard/paths.py": ("from guard import paths_classify\n", "")})
        self.found("is not imported as a module of guard",
                   {"hooks/guard/paths.py": ("from guard import paths_classify\n", "from guard import paths_fs\n")})

    def test_a_method_left_out_of_the_table_is_found(self):
        self.found("PathGuard.loc_mode is not bound to paths_classify.loc_mode: an unbound method fails open",
                   {"hooks/guard/paths.py": ("    loc_mode = paths_classify.loc_mode\n", "")})

    def test_a_call_with_no_method_behind_it_is_found(self):
        self.found("self.nope() is no method of PathGuard", {"hooks/guard/paths_classify.py": (
            "return exists(p)", "return self.nope(p)")})

    def test_a_wrong_binding_is_found(self):
        both = [("from guard import paths_classify\n", "from guard import paths_classify, paths_fs\n"),
                ("probe = paths_classify.probe", "probe = paths_fs.probe")]
        self.found("is bound to paths_fs.probe, its home is paths_classify", {"hooks/guard/paths.py": both})
        self.found("is bound to other, not to paths_classify.probe", {"hooks/guard/paths.py": (
            "probe = paths_classify.probe", "probe = other")})
        self.found("binds nothing, which is no moved method", {"hooks/guard/paths.py": (
            "    probe = paths_classify.probe\n", "    probe = paths_classify.probe\n    nothing = 1\n")})
        self.found("is bound more than once", {"hooks/guard/paths.py": (
            "    probe = paths_classify.probe\n", "    probe = paths_classify.probe\n    probe = paths_classify.probe\n")})

    def test_a_kept_method_lost_or_an_extra_method_is_found(self):
        self.found("lost the method check", {"hooks/guard/paths.py": ("    def check(self):\n        return self.classify(self.ctx)\n\n", "")})
        self.found("has the method extra, which the partition moves or does not know", {"hooks/guard/paths.py": (
            "    classify = ", "    def extra(self):\n        pass\n\n    classify = ")})
        self.found("holds a Expr", {"hooks/guard/paths.py": ("    classify = ", "    print()\n    classify = ")})

    def test_the_entry_contract_is_found(self):
        self.found("paths defines", {"hooks/guard/paths.py": ("def check(ctx)", "def extra():\n    pass\n\n\ndef check(ctx)")})
        self.found("a top-level Assign", {"hooks/guard/paths.py": ("def check(ctx)", "T = 1\n\n\ndef check(ctx)")})
        self.found("lines, the limit is under 30", {"hooks/guard/paths.py": ("def check(ctx)", "\n" * 30 + "def check(ctx)")})
        self.found("`__all__` re-exports (Q25)", {"hooks/guard/paths.py": ("def check(ctx)", "__all__ = ['PathGuard']\n\n\ndef check(ctx)")})
        self.found("lost the first", {"hooks/guard/paths.py": ('"""The guard. Nothing else."""', '"""Another."""')})
        self.found("check(a, b), the hook calls check(ctx)", {"hooks/guard/paths.py": ("def check(ctx)", "def check(a, b)")})
        self.found("paths imports ['paths_classify', 'paths_fs'], the partition has ['paths_classify']", {
            "hooks/guard/paths.py": ("from guard import paths_classify\n", "from guard import paths_classify, paths_fs\n")})

    def test_the_entry_may_keep_a_longer_docstring(self):
        edit = {"hooks/guard/paths.py": ('"""The guard. Nothing else."""', '"""The guard. Nothing else. The rules: paths_*."""')}
        self.assertEqual(layout_problems(self.tree(edit), SYNTHETIC), [])

    def test_a_kept_method_that_drifts_is_found_by_the_copy_check(self):
        edit = {"hooks/guard/paths.py": ("return self.classify(self.ctx)", "return self.classify(None)")}
        self.assertEqual(self.moved(edit), ["PathGuard.check differs from the source (D6)"])
        edit = {"hooks/guard/paths.py": ("PathGuard(ctx).check()", "PathGuard(ctx).check() or 1")}
        self.assertEqual(self.moved(edit), ["check differs from the source (D6)"])


if __name__ == "__main__":
    if "--moved-from" in sys.argv:
        ARGS = sys.argv[sys.argv.index("--moved-from") + 1:]
        if len(ARGS) != 1:
            print("usage: python3 -I tests/test_guard_layout.py --moved-from <rev>")
            sys.exit(2)
        sys.exit(moved_from(ARGS[0]))
    unittest.main()
