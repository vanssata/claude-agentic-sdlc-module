#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Layout of the split of skills/project-update/update.py into skills/project-update/rr_update/
(small-oop-modules WP3: R2, R3, R4, R6, R6a, R10, R15, R16; the paper form in step s0, the
phase 2 form is exercised by the cut-over, step s3).

tests/fixtures/update/partition.json is the authority: which module owns which name, the layer
of each module, core or shell per name, the signature each function has today, the module
import edges, the names retired (find_block: callers use render_instructions.find_block, D3).
The call graph is read from update.py with `ast` in this file; no tool is needed.

Two phases, told by whether update.py still defines `main`:

  phase 1 (update.py holds the code; the module steps are copying it out) - the partition is
    checked against update.py: every top-level def, class and assigned name is in it exactly
    once (retired ones in no module), each signature and kind matches, the recorded edges are
    the call graph's, every edge goes to a lower layer and there is no cycle (R10, on paper),
    a core name touches no file, clock or subprocess and refers to no shell name (R16). Every
    module present under rr_update/ is then checked on its own, so the test passes with none
    and with any subset: its names are the partition's, each function keeps its signature,
    each constant without references keeps its value, it imports, holds no `global`, no
    `__file__` (paths.py holds exactly one, D1), imports only lower layers, takes no name out
    of a sibling with `from rr_update.<mod> import` (R6), and a module whose names are all
    core imports none of os, subprocess, time, fcntl.
  phase 2 (update.py is the entry, step s3) - TestCutOver: the entry under 100 lines with its
    docstring, `sys.dont_write_bytecode` before the first import of rr_update, which brings in
    cli only (R2, Q25), one home per name, the real import graph, no `import update` and no
    name taken from the entry in tests/ (R6; `__doc__` excepted), the forbidden constructs of
    R4, hooks isolation (R15), module sizes printed (600 lines advisory).
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
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
PACKAGE = os.path.join(ROOT, "skills", "project-update", "rr_update")
PARTITION = os.path.join(ROOT, "tests", "fixtures", "update", "partition.json")
IO_IMPORTS = {"os", "subprocess", "time", "fcntl"}
IO_ROOTS = {"subprocess", "time", "shutil", "tempfile", "sys", "importlib", "fcntl"}
PURE_PATH = {"join", "dirname", "basename", "normpath", "sep", "splitext", "split", "isabs",
             "relpath", "commonpath"}
PURE_OS = {"sep", "linesep", "pathsep", "curdir", "pardir", "fspath", "fsdecode", "fsencode"}
BARE_IO = {"open", "print", "input", "exec", "eval", "__import__"}
FORBIDDEN_NAMES = {"ABC", "abstractmethod", "Protocol", "staticmethod"}
# the one use of the entry R6 allows in tests/: test_project_update.py loads it for its docstring
ENTRY_ALLOWED = {"__doc__"}
# a call that runs the entry as a program (`done = subprocess.run([..., UPDATE, ...])`) does not load it
RUNNERS = {"run", "Popen", "call", "check_call", "check_output"}
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp,
          ast.GeneratorExp)


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def parse(path):
    return ast.parse(read_text(path), filename=path)


def entry_defines_main(path=UPDATE):
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in parse(path).body)


def read_partition(path=PARTITION):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def present_modules(package=PACKAGE):
    if not os.path.isdir(package):
        return []
    return sorted(n[:-3] for n in os.listdir(package) if n.endswith(".py") and n != "__init__.py")


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


def comprehension_targets(node):
    return {n for gen in node.generators for n in target_names(gen.target)}


def bound_in(node):
    """What a scope binds for the code inside it."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
        names.update(a.arg for a in (args.vararg, args.kwarg) if a)
        return names | (own_stores(node) if not isinstance(node, ast.Lambda) else set())
    return comprehension_targets(node)


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
    graph = {}
    for name, (_kind, node, _value) in defs.items():
        graph[name] = references(node, set(defs)) - {name}
    return graph


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
    """{module: {module it must import}} from a call graph; a name of no module (retired) is no edge."""
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


# --------------------------------------------------------------------------------------
# the modules under rr_update/


def imported_modules(tree):
    """The rr_update modules a module imports: `from rr_update import a, b`, `import rr_update.a`,
    `from rr_update.a import x`, `from . import a`, `from .a import x`."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = (node.module or "").split(".")
            if node.level and base == [""]:
                found.update(a.name for a in node.names)
            elif node.level and node.level == 1:
                found.add(base[0])
            elif base[0] == "rr_update":
                found.update([base[1]] if len(base) > 1 else [a.name for a in node.names])
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[1] for a in node.names
                         if a.name.startswith("rr_update.") and "." in a.name)
    return found


def rr_update_import(node):
    """True for an `import rr_update...` or `from rr_update... import ...` statement."""
    if isinstance(node, ast.ImportFrom):
        return not node.level and (node.module or "").split(".")[0] == "rr_update"
    return isinstance(node, ast.Import) and any(a.name.split(".")[0] == "rr_update" for a in node.names)


def top_level_imports(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def import_problem(base, mod):
    """'' when `import rr_update.<mod>` works in a clean interpreter, else its last error line."""
    code = "import sys; sys.path.insert(0, %r); import rr_update.%s" % (base, mod)
    done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True,
                          check=False, timeout=60)
    if done.returncode == 0:
        return ""
    return (done.stderr.strip().splitlines() or ["exit %d" % done.returncode])[-1]


def seam_problems(mod, tree):
    """R6: a name taken out of a sibling, json or os at import escapes a patch on its attribute, and
    the code reads `paths.SHARED` at call time so a suite's assignment reaches it."""
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = node.module or ""
        if node.level:
            problems.append("%s:%d relative import" % (mod, node.lineno))
        elif base in ("json", "os") or base.startswith("os."):
            problems.append("%s:%d from %s import ... (R6: keep it a module attribute)" % (mod, node.lineno, base))
        elif base.startswith("rr_update."):
            problems.append("%s:%d from %s import %s (R6: use `from rr_update import %s`)" % (
                mod, node.lineno, base, ", ".join(a.name for a in node.names), base.split(".")[1]))
    return problems


def module_problems(part, mod, path):
    """Everything wrong with one module file against the partition; [] when it is right."""
    if mod not in part["modules"]:
        return ["%s: not a module of the partition" % mod]
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
            problems.append("%s: %s has another value than update.py's" % (mod, name))
    problems += ["%s: `global %s` (R4)" % (mod, ", ".join(n.names)) for n in ast.walk(tree)
                 if isinstance(n, ast.Global)]
    uses = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]
    if mod == "paths":
        if len(uses) != 1:
            problems.append("paths: %d uses of __file__, exactly one is HERE's (R6a, D1)" % len(uses))
    else:
        problems += ["%s: __file__ at line %d (R6a: only paths.py has one, as paths.HERE)" % (mod, n) for n in uses]
    problems += seam_problems(mod, tree)
    layer = {m: s["layer"] for m, s in part["modules"].items()}
    for dep in sorted(imported_modules(tree)):
        if dep not in layer:
            problems.append("%s: imports rr_update.%s, which is not a module of the partition" % (mod, dep))
        elif layer[dep] >= spec["layer"]:
            problems.append("%s (layer %d) imports %s (layer %d): not downward (R10)"
                            % (mod, spec["layer"], dep, layer[dep]))
    labels = {part["defs"][n]["label"] for n in spec["defs"] if n in part["defs"]}
    if labels == {"core"}:
        problems += ["%s: all names are core, yet it imports %s (R16)" % (mod, n)
                     for n in sorted(top_level_imports(tree) & IO_IMPORTS)]
    return problems


# --------------------------------------------------------------------------------------
# what tests/ may still take from the entry (R6)


def entry_uses_in(source):
    """What a test file still takes from the entry: an `import update` / `from update import` (a string
    snippet included) and `<module>.<name>` on a module the file loads from the UPDATE path, minus
    `__doc__`."""
    found = set(re.findall(r"(?<![\w.])(import update(?![\w])(?: as \w+)?|from update import)", source))
    tree = ast.parse(source)
    specs, modules = set(), set()
    for _ in range(3):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call) \
                    or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            call, target = node.value, node.targets[0].id
            func = ast.unparse(call.func).split(".")[-1]
            args = {n.id for a in call.args for n in ast.walk(a) if isinstance(n, ast.Name)}
            if func == "spec_from_file_location" and "UPDATE" in args:
                specs.add(target)
            elif func == "module_from_spec" and args & specs:
                modules.add(target)
            elif "UPDATE" in args and func not in RUNNERS:
                modules.add(target)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules \
                and node.attr not in ENTRY_ALLOWED:
            found.add("%s.%s" % (node.value.id, node.attr))
    return found


# --------------------------------------------------------------------------------------


class TestPartitionFile(unittest.TestCase):
    """The authority itself, whatever the phase."""

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()

    def test_every_name_has_one_home_or_is_retired_and_has_a_label(self):
        owner = owners_of(self.part)
        for name, homes in owner.items():
            self.assertEqual(len(homes), 1, "%s is in %s" % (name, homes))
        for name, rec in self.part["defs"].items():
            self.assertIn(rec["label"], ("core", "shell"), name)
            self.assertIn(rec["kind"], ("function", "class", "const"), name)
            self.assertEqual(name in owner, name not in self.part["retired"], name)
        self.assertEqual(set(owner) | set(self.part["retired"]), set(self.part["defs"]))

    def test_find_block_is_retired_not_moved(self):
        """D3: callers use render_instructions.find_block; nothing is re-exported."""
        self.assertIn("find_block", self.part["retired"])
        self.assertNotIn("find_block", owners_of(self.part))

    def test_the_modules_are_the_plans_and_layers_are_numbers(self):
        self.assertEqual(sorted(self.part["modules"]), sorted(
            "paths files history gate siblings kept plan weights blocks shared rules cleanup hints build apply "
            "report cli".split()))
        for mod, spec in self.part["modules"].items():
            self.assertIsInstance(spec["layer"], int, mod)
        self.assertEqual(max(s["layer"] for s in self.part["modules"].values()),
                         self.part["modules"]["cli"]["layer"])

    def test_the_two_homes_decided_in_the_plan(self):
        """D1: HERE lives in paths; the memo of D5 lives in siblings."""
        self.assertIn("HERE", self.part["modules"]["paths"]["defs"])
        self.assertIn("_MODULES", self.part["modules"]["siblings"]["defs"])

    def test_recorded_imports_go_downward_and_acyclic(self):
        layer = {m: s["layer"] for m, s in self.part["modules"].items()}
        edges = {m: set(s["imports"]) for m, s in self.part["modules"].items()}
        self.assertEqual(graph_problems(layer, edges), [])

    def test_the_entry_docstring_is_pinned(self):
        self.assertRegex(self.part["entry_docstring_sha256"], r"^[0-9a-f]{64}$")


@unittest.skipUnless(entry_defines_main(), "update.py is the entry: the partition stands alone")
class TestPartitionAgainstUpdatePy(unittest.TestCase):
    """Phase 1: the partition against the file that holds the code, the graph on paper."""

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()
        cls.tree = parse(UPDATE)
        cls.names = module_names(cls.tree)
        cls.graph = call_graph(cls.tree)

    def test_every_name_of_update_py_is_assigned_once(self):
        self.assertEqual(sorted(set(self.names) - set(self.part["defs"])), [], "unassigned")
        self.assertEqual(sorted(set(self.part["defs"]) - set(self.names)), [], "not in update.py")

    def test_kinds_signatures_and_values_are_update_pys(self):
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
            self.assertEqual(sorted(derived[mod]), sorted(spec["imports"]), "%s: run the generator again" % mod)

    def test_the_import_graph_on_paper_is_acyclic_and_downward(self):
        """R10: found before any module is written, not after a move."""
        layer = {m: s["layer"] for m, s in self.part["modules"].items()}
        problems = graph_problems(layer, module_edges(self.part, self.graph))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_core_names_touch_nothing(self):
        nodes = {name: node for name, (_kind, node, _value) in self.names.items()}
        problems = label_problems(self.part, self.graph, nodes)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_entry_docstring_is_pinned_to_the_file(self):
        doc = ast.get_docstring(self.tree, clean=False)
        self.assertEqual(hashlib.sha256(doc.encode()).hexdigest(), self.part["entry_docstring_sha256"])


@unittest.skipUnless(entry_defines_main(), "update.py is the entry: the full form is step s3's")
class TestModulesPresent(unittest.TestCase):
    """Phase 1: each module the steps have written so far, on its own (none is fine)."""

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()

    def test_each_present_module_is_the_partitions(self):
        problems = []
        for mod in present_modules():
            problems += module_problems(self.part, mod, os.path.join(PACKAGE, mod + ".py"))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_each_present_module_imports(self):
        base = os.path.dirname(PACKAGE)
        problems = ["%s: %s" % (m, e) for m in present_modules() for e in [import_problem(base, m)] if e]
        self.assertEqual(problems, [], "\n".join(problems))

    def test_package_has_an_init_when_it_has_modules(self):
        if present_modules():
            self.assertTrue(os.path.exists(os.path.join(PACKAGE, "__init__.py")), "rr_update/__init__.py")

    def test_sizes_are_reported(self):
        """Advisory: over 600 lines is noted in the task report, never a failure."""
        for mod in present_modules():
            count = line_count(os.path.join(PACKAGE, mod + ".py"))
            print("rr_update/%s.py: %d lines%s" % (mod, count, "  (over 600: note it in task.md)" if count > 600 else ""))


@unittest.skipIf(entry_defines_main(), "update.py still defines main: phase 1 above applies")
class TestCutOver(unittest.TestCase):
    """Phase 2: update.py is the entry. Entry size and contents (R2), one home per name (R3), the real
    import graph (R10), no `global`, one `__file__` (R4, R6a), the forbidden constructs (R4), the
    suites' use of the entry (R6), hooks isolation (R15), sizes (advisory)."""

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()
        cls.trees = {m: parse(os.path.join(PACKAGE, m + ".py")) for m in present_modules()}
        cls.entry_text = read_text(UPDATE)
        cls.entry = ast.parse(cls.entry_text)

    # -- R2: the entry
    def test_the_entry_is_under_100_lines_and_defines_nothing(self):
        count = len(self.entry_text.splitlines())
        print("update.py: %d lines" % count)
        self.assertLess(count, 100)
        self.assertEqual([n.name for n in self.entry.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))], [])
        self.assertTrue(os.access(UPDATE, os.X_OK), "update.py lost its executable bit")

    def test_the_entry_keeps_its_docstring(self):
        doc = ast.get_docstring(self.entry, clean=False)
        self.assertEqual(hashlib.sha256(doc.encode()).hexdigest(), self.part["entry_docstring_sha256"])

    def test_the_entry_stops_bytecode_before_it_imports_the_package(self):
        """D4: a package imported first writes rr_update/__pycache__ into an install."""
        flag = [n.lineno for n in self.entry.body if isinstance(n, ast.Assign)
                and ast.unparse(n.targets[0]) == "sys.dont_write_bytecode"]
        self.assertEqual(len(flag), 1, "sys.dont_write_bytecode is set once")
        firsts = [n.lineno for n in ast.walk(self.entry) if rr_update_import(n)]
        self.assertTrue(firsts, "the entry imports rr_update")
        self.assertLess(flag[0], min(firsts))

    def test_the_entry_imports_nothing_but_cli_from_the_package(self):
        """R2, Q25: no re-exports."""
        found = []
        for node in ast.walk(self.entry):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "rr_update":
                found += [(node.module, a.name) for a in node.names]
            elif isinstance(node, ast.Import):
                found += [(a.name, "") for a in node.names if a.name.split(".")[0] == "rr_update"]
        allowed = [[("rr_update", "cli")], [("rr_update.cli", "main")], [("rr_update.cli", "")]]
        self.assertIn(sorted(found), allowed, "the entry imports %s" % found)

    def test_a_missing_package_exits_with_one_line(self):
        skill = os.path.dirname(PACKAGE)
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "project-update")
            shutil.copytree(skill, copy, ignore=shutil.ignore_patterns("__pycache__"))
            os.rename(os.path.join(copy, "rr_update"), os.path.join(copy, "rr_update_away"))
            done = subprocess.run([sys.executable, "-I", "-B", os.path.join(copy, "update.py"), "--help"],
                                  capture_output=True, text=True, check=False, timeout=60, cwd=tmp)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertEqual(done.stdout, "")
        self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
        self.assertIn("npx riskrails", done.stderr)

    # -- R3: sizes (advisory) and the partition
    def test_sizes_are_reported(self):
        for mod in sorted(self.trees):
            count = line_count(os.path.join(PACKAGE, mod + ".py"))
            print("rr_update/%s.py: %d lines%s" % (mod, count, "  (over 600: note it in task.md)" if count > 600 else ""))

    def test_each_module_is_the_partitions(self):
        problems = []
        for mod in sorted(self.trees):
            problems += module_problems(self.part, mod, os.path.join(PACKAGE, mod + ".py"))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_each_module_imports(self):
        base = os.path.dirname(PACKAGE)
        problems = ["%s: %s" % (m, e) for m in sorted(self.trees) for e in [import_problem(base, m)] if e]
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_name_has_exactly_one_home(self):
        homes = {}
        for mod, tree in self.trees.items():
            for name in module_names(tree):
                homes.setdefault(name, []).append(mod)
        want = owners_of(self.part)
        problems = ["%s is retired but defined in %s" % (n, homes[n]) for n in sorted(self.part["retired"]) if n in homes]
        problems += ["%s lives in %s, the partition says %s" % (n, homes.get(n, []), want[n])
                     for n in sorted(want) if homes.get(n, []) != want[n]]
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertEqual(sorted(set(self.trees) - set(self.part["modules"])), [])
        self.assertEqual(sorted(set(self.part["modules"]) - set(self.trees)), [], "a module of the partition is missing")

    # -- R4, R6a
    def test_no_global_statement_and_the_one_file(self):
        problems = []
        for mod, tree in self.trees.items():
            problems += ["%s:%d global %s" % (mod, n.lineno, ", ".join(n.names)) for n in ast.walk(tree)
                         if isinstance(n, ast.Global)]
            uses = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "__file__"]
            if len(uses) != (1 if mod == "paths" else 0):
                problems.append("%s: __file__ at %s" % (mod, uses))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_forbidden_constructs_of_r4(self):
        problems, classes = [], set()
        for mod, tree in self.trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.add(node.name)
                    problems += ["%s:%d class %s(%s): a base other than Exception" % (
                        mod, node.lineno, node.name, ast.unparse(b)) for b in node.bases if ast.unparse(b) != "Exception"]
                if isinstance(node, ast.Name):
                    used = {node.id}
                elif isinstance(node, ast.Attribute):
                    used = {node.attr}
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    used = {a.name.split(".")[-1] for a in node.names}
                else:
                    used = set()
                problems += ["%s:%d uses %s" % (mod, node.lineno, hit) for hit in sorted(used & FORBIDDEN_NAMES)]
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertEqual(sorted(classes), sorted(n for n, r in self.part["defs"].items() if r["kind"] == "class"))

    # -- R6: tests/ import the owners
    def test_the_suites_take_nothing_from_the_entry(self):
        problems = []
        here = os.path.basename(__file__)
        for name in sorted(os.listdir(os.path.join(ROOT, "tests"))):
            if name.endswith(".py") and name != here:
                problems += ["tests/%s: %s" % (name, hit)
                             for hit in sorted(entry_uses_in(read_text(os.path.join(ROOT, "tests", name))))]
        self.assertEqual(problems, [], "\n".join(problems))

    # -- R10
    def test_the_import_graph_from_the_real_imports_is_acyclic_and_downward(self):
        layer = {m: s["layer"] for m, s in self.part["modules"].items()}
        graph = {mod: imported_modules(tree) for mod, tree in self.trees.items()}
        problems = graph_problems(layer, graph)
        problems += ["%s imports the entry or cli" % m for m, tree in sorted(self.trees.items())
                     if "update" in top_level_imports(tree) or "cli" in graph[m]]
        self.assertEqual(problems, [], "\n".join(problems))

    # -- R15
    @staticmethod
    def imports_of(tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield node.lineno, alias.name
            elif isinstance(node, ast.ImportFrom) and not node.level:
                yield node.lineno, node.module or ""

    def test_no_import_crosses_between_hooks_and_rr_update(self):
        problems = []
        for here, _dirs, files in os.walk(os.path.join(ROOT, "hooks")):
            for name in sorted(files):
                if name.endswith(".py"):
                    path = os.path.join(here, name)
                    problems += ["%s:%d imports %s" % (os.path.relpath(path, ROOT), line, mod)
                                 for line, mod in self.imports_of(parse(path)) if mod.split(".")[0] in ("rr_update", "update")]
        for mod, tree in self.trees.items():
            problems += ["rr_update/%s.py:%d imports %s" % (mod, line, target)
                         for line, target in self.imports_of(tree) if target.split(".")[0] in ("hooks", "guard")]
        self.assertEqual(problems, [], "\n".join(problems))

    # -- R16
    def test_a_module_of_core_names_imports_no_io(self):
        problems = []
        for mod, spec in self.part["modules"].items():
            if mod in self.trees and {self.part["defs"][n]["label"] for n in spec["defs"]} == {"core"}:
                problems += ["%s imports %s" % (mod, n) for n in sorted(top_level_imports(self.trees[mod]) & IO_IMPORTS)]
        self.assertEqual(problems, [], "\n".join(problems))


class TestAnalysis(unittest.TestCase):
    """The reading of a source on small synthetic ones: it sees what it must and passes what it may."""

    SOURCE = ("import os\n"
              "try:\n    import tomllib\nexcept ImportError:\n    tomllib = None\n"
              "LIMIT = 5\nA, B = (1, 2)\n\n"
              "def read(path):\n    with open(path) as fh:\n        return fh.read()\n\n"
              "def pure(x, read=LIMIT):\n    return [read for read in x]\n\n"
              "def user(path):\n    return read(path) + LIMIT\n\n"
              "class Holder:\n    def read(self, p):\n        return read(p)\n")

    def test_the_names_of_a_file(self):
        names = module_names(ast.parse(self.SOURCE))
        self.assertEqual(sorted(names), ["A", "B", "Holder", "LIMIT", "pure", "read", "tomllib", "user"])
        self.assertEqual(names["Holder"][0], "class")
        self.assertEqual(names["tomllib"][0], "const")
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
        self.assertEqual(hit("os.walk(a)"), "os.walk")
        self.assertEqual(hit("subprocess.run(a)"), "subprocess")
        self.assertEqual(hit("datetime.now(tz)"), "datetime.now")
        self.assertEqual(hit("datetime.strptime(a, b)"), "")
        self.assertEqual(hit("json.dumps(a)"), "")
        self.assertEqual(hit("json.load(f)"), "json.load")
        self.assertEqual(hit("print(a)"), "print")

    def test_the_graph_check_flags_an_upward_edge_a_same_layer_edge_and_a_cycle(self):
        layer = {"low": 0, "mid": 1, "top": 2}
        self.assertEqual(graph_problems(layer, {"low": set(), "mid": {"low"}, "top": {"low", "mid"}}), [])
        self.assertTrue(any("upward edge: low" in p for p in graph_problems(layer, {"low": {"mid"}, "mid": set()})))
        self.assertTrue(any("upward edge" in p for p in graph_problems(layer, {"mid": {"mid"}})))
        cyc = graph_problems({"a": 0, "b": 0}, {"a": {"b"}, "b": {"a"}})
        self.assertTrue(any(p.startswith("cycle: ") for p in cyc), cyc)
        self.assertTrue(any("not a module" in p for p in graph_problems(layer, {"low": {"nowhere"}})))

    def test_the_label_check_flags_a_core_name_that_reaches_io_or_a_shell_name(self):
        tree = ast.parse(self.SOURCE)
        nodes = {n: node for n, (_k, node, _v) in module_names(tree).items()}
        part = {"defs": {n: {"label": "shell" if n in ("read", "user", "Holder") else "core"} for n in nodes}}
        self.assertEqual(label_problems(part, call_graph(tree), nodes), [])
        part["defs"]["read"]["label"] = "core"
        part["defs"]["user"]["label"] = "core"
        found = label_problems(part, call_graph(tree), nodes)
        self.assertIn("core name read reaches I/O (open)", found)
        part["defs"]["read"]["label"] = "shell"
        self.assertIn("core name user refers to the shell name read", label_problems(part, call_graph(tree), nodes))

    def test_the_value_hash_tells_values_apart_and_names_not(self):
        def value(code):
            return ast.parse(code, mode="eval").body
        self.assertEqual(hash_of(value("re.compile(r'^a$', re.I)")), hash_of(value('re.compile(r"^a$", re.I)')))
        self.assertNotEqual(hash_of(value("5")), hash_of(value("6")))
        self.assertNotEqual(hash_of(value("(1, 2)")), hash_of(value("[1, 2]")))


class TestModuleChecks(unittest.TestCase):
    """module_problems on small synthetic modules: it flags what it must and passes what it may."""

    PART = {
        "modules": {"paths": {"layer": 0, "defs": ["LIMIT", "helper", "HERE"]},
                    "high": {"layer": 1, "defs": ["use"]}},
        "defs": {
            "LIMIT": {"kind": "const", "signature": "", "label": "core", "value_hash": hash_of(ast.parse("5").body[0].value)},
            "HERE": {"kind": "const", "signature": "", "label": "shell", "value_hash": None},
            "helper": {"kind": "function", "signature": "(a, b=1)", "label": "core", "value_hash": None},
            "use": {"kind": "function", "signature": "(root)", "label": "shell", "value_hash": None},
        },
    }
    GOOD = "HERE = __file__\nLIMIT = 5\n\ndef helper(a, b=1):\n    return a\n"

    def check(self, mod, source, part=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, mod + ".py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(source)
            return module_problems(part or self.PART, mod, path)

    def test_a_right_module_passes(self):
        self.assertEqual(self.check("paths", self.GOOD), [])

    def test_a_missing_and_an_extra_name(self):
        found = self.check("paths", "HERE = __file__\nLIMIT = 5\nOTHER = 1\n")
        self.assertIn("paths: missing helper", found)
        self.assertIn("paths: OTHER is not the partition's", found)

    def test_a_changed_signature_and_value(self):
        found = self.check("paths", "HERE = __file__\nLIMIT = 6\n\ndef helper(a):\n    pass\n")
        self.assertTrue(any("helper" in p and "partition has" in p for p in found), found)
        self.assertIn("paths: LIMIT has another value than update.py's", found)

    def test_global_is_refused(self):
        found = self.check("paths", self.GOOD + "\ndef other():\n    global LIMIT\n")
        self.assertTrue(any("`global LIMIT`" in p for p in found), found)

    def test_file_is_for_paths_alone_and_exactly_once(self):
        self.assertTrue(any("exactly one" in p for p in self.check("paths", self.GOOD.replace("__file__", "None"))))
        self.assertTrue(any("exactly one" in p for p in self.check("paths", self.GOOD + "THERE = __file__\n")))
        found = self.check("high", "def use(root):\n    return __file__\n")
        self.assertTrue(any("only paths.py has one" in p for p in found), found)

    def test_an_upward_or_unknown_import_is_refused(self):
        up = self.check("paths", "from rr_update import high\n" + self.GOOD)
        self.assertTrue(any("not downward" in p for p in up), up)
        down = self.check("high", "from rr_update import paths\n\ndef use(root):\n    return paths.LIMIT\n")
        self.assertEqual(down, [])
        unknown = self.check("high", "import rr_update.nowhere\n\ndef use(root):\n    pass\n")
        self.assertTrue(any("not a module of the partition" in p for p in unknown), unknown)

    def test_a_name_taken_out_of_a_sibling_is_refused(self):
        """R6: `from rr_update.paths import LIMIT` would copy the value a suite assigns later."""
        found = self.check("high", "from rr_update.paths import LIMIT\n\ndef use(root):\n    return LIMIT\n")
        self.assertTrue(any("R6" in p and "from rr_update.paths import LIMIT" in p for p in found), found)
        self.assertTrue(any("R6" in p for p in self.check("high", "from os import replace\n\ndef use(root):\n    pass\n")))

    def test_an_unknown_module_is_refused(self):
        self.assertEqual(self.check("gone", "X = 1\n"), ["gone: not a module of the partition"])

    def test_an_all_core_module_may_not_import_io(self):
        part = json.loads(json.dumps(self.PART))
        part["defs"]["HERE"]["label"] = "core"
        found = self.check("paths", "import os\n" + self.GOOD, part)
        self.assertEqual([p for p in found if "R16" in p], ["paths: all names are core, yet it imports os (R16)"])


class TestEntryUses(unittest.TestCase):
    """R6: what tests/ may still take from the entry."""

    def test_the_check_sees_a_leftover(self):
        self.assertEqual(entry_uses_in("import update\n"), {"import update"})
        self.assertEqual(entry_uses_in("cmd = 'import update as U; U.sha'"), {"import update as U"})
        self.assertEqual(entry_uses_in("from update import sha\n"), {"from update import"})
        self.assertEqual(entry_uses_in("import update_notice\nimport updater\n"), set())

    def test_a_module_loaded_from_the_entry_path_may_give_its_doc_and_nothing_else(self):
        loaded = "U = load('x', UPDATE)\nU.find_block(data)\nU.__doc__\n"
        self.assertEqual(entry_uses_in(loaded), {"U.find_block"})
        doc = ("spec = importlib.util.spec_from_file_location('update_doc', UPDATE)\n"
               "doc = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(doc)\ndoc.__doc__\n")
        self.assertEqual(entry_uses_in(doc), set())
        self.assertEqual(entry_uses_in(doc + "doc.main()\n"), {"doc.main"})
        self.assertEqual(entry_uses_in("W = load('w', WEIGHT)\nW.x\n"), set())


if __name__ == "__main__":
    unittest.main()
