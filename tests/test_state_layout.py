#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Layout of the split of skills/ai-task/state.py into skills/ai-task/rr_state/
(small-oop-modules R2, R3, R4, R6, R6a, R10, R15, R16; first form in step s0, full form in s8).

tests/fixtures/state/partition.json is the authority: which module owns which name, the
layer of each module, core or shell per name, the signature each function has today.
tools/state-partition.py reads state.py and that file, prints the module import graph and
exits 1 on a cycle, an upward edge, an unassigned or doubly assigned name.

Two phases, told by whether state.py still defines `main`:

  phase 1 (state.py holds the code; the module steps are copying it out) - every module
    present under rr_state/ is checked on its own, so the test passes with none and with
    any subset: its names are the partition's (retired names may be absent, the classes of
    R4 listed under "added" may be extra), each function keeps its signature (a parameter
    named in "params_added" may be new: the runtime values travel as parameters, R4), each
    constant without references keeps its value, the module imports, holds no `global`
    statement and no `__file__`, imports only lower layers (R10), and a module whose names
    are all core imports none of os, subprocess, time, fcntl (R16).
  phase 2 (state.py is the shim, step s8) - TestCutOver: the entry under 200 lines, the missing-
    package message, module sizes (advisory), the partition on every module, one home per name,
    no `global`, no `__file__`, the re-export list against the two greps of R6, the import
    graph from the real imports, the forbidden constructs of R4 and R6, hooks isolation (R15),
    R16 at full.

Both phases run the partition tool and assert exit 0.
"""
import ast
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
PACKAGE = os.path.join(ROOT, "skills", "ai-task", "rr_state")
PARTITION = os.path.join(ROOT, "tests", "fixtures", "state", "partition.json")
TOOL = os.path.join(ROOT, "tools", "state-partition.py")
IO_IMPORTS = {"os", "subprocess", "time", "fcntl"}


def load_tool():
    spec = importlib.util.spec_from_file_location("state_partition", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL_MODULE = load_tool()


def entry_defines_main(path=STATE):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)


def read_partition(path=PARTITION):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_tool(*args):
    return subprocess.run([sys.executable, "-I", "-B", TOOL] + list(args), capture_output=True,
                          text=True, check=False, timeout=120)


def present_modules(package=PACKAGE):
    if not os.path.isdir(package):
        return []
    return sorted(n[:-3] for n in os.listdir(package) if n.endswith(".py") and n != "__init__.py")


def param_tokens(signature, dropped):
    """The parameters of a signature string as comparable tokens, those named in `dropped` left out."""
    args = ast.parse("def f%s: pass" % signature).body[0].args
    plain = args.posonlyargs + args.args
    defaults = [None] * (len(plain) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(plain, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    tokens = ["%s=%s" % (a.arg, ast.unparse(d)) if d is not None else a.arg for a, d in pairs
              if a.arg not in dropped]
    tokens += ["*" + a.arg for a in (args.vararg,) if a] + ["**" + a.arg for a in (args.kwarg,) if a]
    return tokens


def module_names(tree):
    """{name: (kind, node, value)} of what a module defines at its top level."""
    found = {}
    for node in tree.body:
        for name, value in TOOL_MODULE.statement_names(node):
            kind = "function" if isinstance(node, ast.FunctionDef) else \
                "class" if isinstance(node, ast.ClassDef) else "const"
            found.setdefault(name, (kind, node, value))
    return found


def imported_modules(tree):
    """The rr_state modules a module imports: `from rr_state import a, b`, `import rr_state.a`,
    `from rr_state.a import x`, `from . import a`, `from .a import x`."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = (node.module or "").split(".")
            if node.level and base == [""]:
                found.update(a.name for a in node.names)
            elif node.level and node.level == 1:
                found.add(base[0])
            elif base[0] == "rr_state":
                found.update([base[1]] if len(base) > 1 else [a.name for a in node.names])
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[1] for a in node.names
                         if a.name.startswith("rr_state.") and "." in a.name)
    return found


def top_level_imports(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def import_problem(base, mod):
    """'' when `import rr_state.<mod>` works in a clean interpreter, else its last error line."""
    code = "import sys; sys.path.insert(0, %r); import rr_state.%s" % (base, mod)
    done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True,
                          check=False, timeout=60)
    if done.returncode == 0:
        return ""
    return (done.stderr.strip().splitlines() or ["exit %d" % done.returncode])[-1]


def module_problems(part, mod, path):
    """Everything wrong with one module file against the partition; [] when it is right."""
    if mod not in part["modules"]:
        return ["%s: not a module of the partition%s" % (
            mod, " (merged into %s)" % part["merged"][mod] if mod in part.get("merged", {}) else "")]
    spec = part["modules"][mod]
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    problems = []
    found = module_names(tree)
    wanted = set(spec["defs"]) - set(part.get("retired", []))
    allowed = set(spec["defs"]) | set(part.get("added", {}).get(mod, []))
    problems += ["%s: missing %s" % (mod, n) for n in sorted(wanted - set(found))]
    problems += ["%s: %s is not the partition's" % (mod, n) for n in sorted(set(found) - allowed)]
    dropped = set(part.get("params_added", []))
    memos = set(part.get("globals", {}))
    for name, (kind, node, value) in found.items():
        rec = part["defs"].get(name)
        if not rec or name not in spec["defs"]:
            continue
        if rec["kind"] != kind:
            problems.append("%s: %s is a %s, the partition says %s" % (mod, name, kind, rec["kind"]))
        elif kind == "function":
            sig = "(%s)" % ast.unparse(node.args)
            if param_tokens(sig, dropped) != param_tokens(rec["signature"], dropped):
                problems.append("%s: %s%s, the partition has %s%s" % (mod, name, sig, name, rec["signature"]))
        elif rec["value_hash"] and name not in memos and value is not None \
                and TOOL_MODULE.hash_of(value) != rec["value_hash"]:
            problems.append("%s: %s has another value than state.py's" % (mod, name))
    problems += ["%s: `global %s` (R4)" % (mod, ", ".join(n.names)) for n in ast.walk(tree)
                 if isinstance(n, ast.Global)]
    problems += ["%s: __file__ at line %d (R6a: use fs.ENTRY)" % (mod, n.lineno) for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and n.id == "__file__"]
    layer = {m: s["layer"] for m, s in part["modules"].items()}
    for dep in sorted(imported_modules(tree)):
        if dep not in layer:
            problems.append("%s: imports rr_state.%s, which is not a module of the partition" % (mod, dep))
        elif layer[dep] >= spec["layer"]:
            problems.append("%s (layer %d) imports %s (layer %d): not downward (R10)"
                            % (mod, spec["layer"], dep, layer[dep]))
    labels = {part["defs"][n]["label"] for n in spec["defs"] if n in part["defs"]}
    if labels == {"core"}:
        problems += ["%s: all names are core, yet it imports %s (R16)" % (mod, n)
                     for n in sorted(top_level_imports(tree) & IO_IMPORTS)]
    return problems


class TestPartitionFile(unittest.TestCase):
    """The authority itself, whatever the phase."""

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()

    def test_tool_exits_zero(self):
        done = run_tool()
        self.assertEqual(done.returncode, 0, done.stdout[-3000:] + done.stderr[-1000:])

    def test_every_name_has_one_home_and_a_label(self):
        owner = {}
        for mod, spec in self.part["modules"].items():
            for name in spec["defs"]:
                self.assertNotIn(name, owner, "%s is in %s and %s" % (name, owner.get(name), mod))
                owner[name] = mod
                self.assertIn(self.part["defs"][name]["label"], ("core", "shell"), name)
        self.assertEqual(set(owner), set(self.part["defs"]))

    def test_layers_are_numbers_and_merged_modules_are_gone(self):
        for mod, spec in self.part["modules"].items():
            self.assertIsInstance(spec["layer"], int, mod)
        for gone, into in self.part["merged"].items():
            self.assertNotIn(gone, self.part["modules"])
            self.assertIn(into, self.part["modules"])

    def test_recorded_imports_go_downward(self):
        layer = {m: s["layer"] for m, s in self.part["modules"].items()}
        for mod, spec in self.part["modules"].items():
            for dep in spec["imports"]:
                self.assertLess(layer[dep], layer[mod], "%s imports %s" % (mod, dep))

    def test_mutable_globals_are_listed_with_a_plan(self):
        """RUNTIME, MUTATING, LOCK_DEPTH, DIALOG_PICK: each is rebound by a `global` (R4 refuses it)."""
        self.assertEqual(sorted(self.part["globals"]), ["DIALOG_PICK", "LOCK_DEPTH", "MUTATING", "RUNTIME"])
        for name, rec in self.part["globals"].items():
            self.assertTrue(rec["plan"], name)
            self.assertTrue(rec["owner"], name)


@unittest.skipUnless(entry_defines_main(), "state.py is the shim: the full form is step s8's")
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
        problems = []
        base = os.path.dirname(PACKAGE)
        for mod in present_modules():
            error = import_problem(base, mod)
            if error:
                problems.append("%s: %s" % (mod, error))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_package_has_an_init_when_it_has_modules(self):
        if present_modules():
            self.assertTrue(os.path.exists(os.path.join(PACKAGE, "__init__.py")), "rr_state/__init__.py")

    def test_sizes_are_reported(self):
        """Advisory (Q16): over 600 lines is noted in the task report, never a failure."""
        for mod in present_modules():
            with open(os.path.join(PACKAGE, mod + ".py"), encoding="utf-8") as handle:
                count = len(handle.read().splitlines())
            print("rr_state/%s.py: %d lines%s" % (mod, count, "  (over 600: note it in task.md)" if count > 600 else ""))


@unittest.skipIf(entry_defines_main(), "state.py still defines main: phase 1 above applies")
class TestCutOver(unittest.TestCase):
    """Phase 2: state.py is the shim. Entry size (R2), the missing-package message, sizes (Q16),
    no `global` and no `__file__` (R4, R6a), the re-export list (R6), the import graph from the
    real imports (R10), the forbidden constructs (R4, R6), hooks isolation (R15), R16 at full,
    exactly one home per name (R3)."""

    FORBIDDEN_NAMES = {"ABC", "abstractmethod", "Protocol", "staticmethod"}
    CLASSES = {"Runtime", "Ledger", "Profile"}
    SHIM_ABSENT = {"json", "os", "__file__", "RUNTIME"}      # R6: imported by the entry, or retired (Q24)
    # reached through a variable, which neither grep of R6 sees: test_dialog_contract.py runs
    # `module.json_loads_capped` for module in (dialog, state_mod)
    INDIRECT = {"json_loads_capped"}

    @classmethod
    def setUpClass(cls):
        cls.part = read_partition()
        cls.trees = {}
        for mod in present_modules():
            path = os.path.join(PACKAGE, mod + ".py")
            with open(path, encoding="utf-8") as handle:
                cls.trees[mod] = ast.parse(handle.read(), filename=path)
        with open(STATE, encoding="utf-8") as handle:
            cls.entry_text = handle.read()
        cls.entry = ast.parse(cls.entry_text)

    # -- R2: the entry
    def test_the_entry_is_under_200_lines_and_defines_nothing(self):
        count = len(self.entry_text.splitlines())
        print("state.py: %d lines" % count)
        self.assertLess(count, 200)
        self.assertEqual([n.name for n in self.entry.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))], [])

    def test_the_entry_keeps_its_path_insert_first_and_is_executable(self):
        inserts = [n for n in self.entry.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                   and ast.unparse(n.value.func) == "sys.path.insert"]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(ast.unparse(inserts[0].value),
                         "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))")
        before = [n for n in self.entry.body
                  if n.lineno < inserts[0].lineno and isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([ast.unparse(n) for n in before], ["import json", "import os", "import sys"])
        self.assertTrue(os.access(STATE, os.X_OK), "state.py lost its executable bit")

    def test_a_missing_package_exits_with_one_line(self):
        skill = os.path.dirname(PACKAGE)
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "ai-task")
            shutil.copytree(skill, copy, ignore=shutil.ignore_patterns("__pycache__"))
            os.rename(os.path.join(copy, "rr_state"), os.path.join(copy, "rr_state_away"))
            done = subprocess.run([sys.executable, "-I", "-B", os.path.join(copy, "state.py"), "status"],
                                  capture_output=True, text=True, check=False, timeout=60, cwd=tmp)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "rr_state/ is missing beside state.py: re-run `npx riskrails`\n")

    # -- R3: sizes (advisory) and the partition
    def test_sizes_are_reported(self):
        """Advisory (Q16): over 600 lines is noted in the task report, never a failure."""
        for mod in sorted(self.trees):
            with open(os.path.join(PACKAGE, mod + ".py"), encoding="utf-8") as handle:
                count = len(handle.read().splitlines())
            print("rr_state/%s.py: %d lines%s" % (mod, count, "  (over 600: note it in task.md)" if count > 600 else ""))

    def test_each_module_is_the_partitions(self):
        problems = []
        for mod in sorted(self.trees):
            problems += module_problems(self.part, mod, os.path.join(PACKAGE, mod + ".py"))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_each_module_imports(self):
        base = os.path.dirname(PACKAGE)
        problems = ["%s: %s" % (m, e) for m in sorted(self.trees) for e in [import_problem(base, m)] if e]
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_name_of_the_golden_file_has_exactly_one_home(self):
        homes = {}
        for mod, tree in self.trees.items():
            for name in module_names(tree):
                homes.setdefault(name, []).append(mod)
        retired = set(self.part["retired"])
        problems = []
        for name in sorted(self.part["defs"]):
            if name in retired:
                if name in homes:
                    problems.append("%s is retired but defined in %s" % (name, homes[name]))
            elif len(homes.get(name, [])) != 1:
                problems.append("%s has homes %s" % (name, homes.get(name, [])))
            else:
                want = [m for m, s in self.part["modules"].items() if name in s["defs"]]
                if homes[name] != want:
                    problems.append("%s lives in %s, the partition says %s" % (name, homes[name], want))
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertEqual(sorted(set(self.trees) - set(self.part["modules"])), [])

    # -- R4, R6a
    def test_no_global_statement_and_no_file_under_rr_state(self):
        problems = []
        for mod, tree in self.trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    problems.append("%s:%d global %s" % (mod, node.lineno, ", ".join(node.names)))
                if isinstance(node, ast.Name) and node.id == "__file__":
                    problems.append("%s:%d __file__" % (mod, node.lineno))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_forbidden_constructs_of_r4(self):
        problems = []
        classes = set()
        for mod, tree in self.trees.items():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.add(node.name)
                    if not ast.get_docstring(node):
                        problems.append("%s:%d class %s has no docstring naming its resource or invariant"
                                        % (mod, node.lineno, node.name))
                    for base in node.bases:
                        if ast.unparse(base) != "Exception":
                            problems.append("%s:%d class %s(%s): a base other than Exception"
                                            % (mod, node.lineno, node.name, ast.unparse(base)))
                    if node.name == "Runtime" and not any("dataclass" in ast.unparse(d) for d in node.decorator_list):
                        problems.append("%s:%d Runtime is not a dataclass" % (mod, node.lineno))
                if isinstance(node, ast.Name):
                    used = {node.id}
                elif isinstance(node, ast.Attribute):
                    used = {node.attr}
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    used = {a.name.split(".")[-1] for a in node.names}
                else:
                    used = set()
                problems += ["%s:%d uses %s" % (mod, node.lineno, hit) for hit in sorted(used & self.FORBIDDEN_NAMES)]
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertTrue({"Runtime"} <= classes <= self.CLASSES, "classes under rr_state/: %s" % sorted(classes))

    def test_no_from_import_of_a_seam_under_rr_state(self):
        """R6: the suites patch json.dump and os.replace as attributes; a name bound at import escapes them."""
        problems = []
        for mod, tree in self.trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                base = node.module or ""
                if node.level:
                    problems.append("%s:%d relative import" % (mod, node.lineno))
                elif base in ("json", "os") or base.startswith("os."):
                    problems.append("%s:%d from %s import ..." % (mod, node.lineno, base))
                elif base.startswith("rr_state."):
                    problems.append("%s:%d from %s import %s (use `from rr_state import %s`)" % (
                        mod, node.lineno, base, ", ".join(a.name for a in node.names), base.split(".")[1]))
        self.assertEqual(problems, [], "\n".join(problems))

    # -- R6: the re-export list
    def expected_reexports(self):
        found = set()
        for name in sorted(os.listdir(os.path.join(ROOT, "tests"))):
            if not name.endswith(".py") or name == os.path.basename(__file__):
                continue
            with open(os.path.join(ROOT, "tests", name), encoding="utf-8") as handle:
                text = handle.read()
            # R6's two greps; the name class takes digits too, or `archive_v7` would read `archive_v`
            found.update(re.findall(r"state_mod\.([A-Za-z_][A-Za-z_0-9]*)", text))
            found.update(re.findall(r'patch\.object\(state_mod, "([A-Za-z_][A-Za-z_0-9]*)"', text))
        return (found - self.SHIM_ABSENT) | self.INDIRECT | {"main"}

    def test_the_reexports_are_the_two_greps_of_r6(self):
        imported = {}
        for node in self.entry.body:
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("rr_state."):
                for alias in node.names:
                    self.assertNotIn(alias.name, imported, "re-exported twice")
                    imported[alias.name] = node.module.split(".")[1]
        self.assertEqual(sorted(set(imported) ^ self.expected_reexports()), [], "re-export list differs from the greps")
        homes = {n: m for m, s in self.part["modules"].items() for n in s["defs"]}
        self.assertEqual({n: m for n, m in imported.items() if homes.get(n) != m}, {},
                         "a name imported from a module that is not its home")

    def test_the_reexports_are_the_objects_of_their_homes(self):
        sys.path.insert(0, os.path.dirname(PACKAGE))
        try:
            state = importlib.import_module("state")
            for node in self.entry.body:
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("rr_state."):
                    home = importlib.import_module(node.module)
                    for alias in node.names:
                        self.assertIs(getattr(state, alias.name), getattr(home, alias.name), alias.name)
            self.assertIs(state.json, json)
            self.assertIs(state.os, os)
            self.assertEqual(os.path.abspath(state.__file__), STATE)
            self.assertEqual(importlib.import_module("rr_state.fs").ENTRY, STATE)
        finally:
            sys.path.remove(os.path.dirname(PACKAGE))

    # -- R10
    def test_the_import_graph_from_the_real_imports_is_acyclic_and_downward(self):
        layer = {m: s["layer"] for m, s in self.part["modules"].items()}
        graph = {mod: imported_modules(tree) for mod, tree in self.trees.items()}
        problems = ["%s (layer %d) imports %s (layer %s)" % (m, layer[m], d, layer.get(d))
                    for m, deps in sorted(graph.items()) for d in sorted(deps)
                    if d not in layer or layer[d] >= layer[m]]
        problems += ["%s imports the entry or cli" % m for m, tree in sorted(self.trees.items())
                     if "state" in top_level_imports(tree) or "cli" in graph[m]]
        colour = {}

        def visit(node, path):
            if colour.get(node) == 1:
                problems.append("cycle: %s" % " -> ".join(path + [node]))
            elif node not in colour:
                colour[node] = 1
                for dep in sorted(graph.get(node, ())):
                    visit(dep, path + [node])
                colour[node] = 2
        for mod in sorted(graph):
            visit(mod, [])
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

    def test_no_import_crosses_between_hooks_and_rr_state(self):
        problems = []
        for here, _dirs, files in os.walk(os.path.join(ROOT, "hooks")):
            for name in sorted(files):
                if name.endswith(".py"):
                    path = os.path.join(here, name)
                    with open(path, encoding="utf-8") as handle:
                        tree = ast.parse(handle.read(), filename=path)
                    problems += ["%s:%d imports %s" % (os.path.relpath(path, ROOT), line, mod)
                                 for line, mod in self.imports_of(tree) if mod.split(".")[0] in ("rr_state", "state")]
        for mod, tree in self.trees.items():
            problems += ["rr_state/%s.py:%d imports %s" % (mod, line, target)
                         for line, target in self.imports_of(tree) if target.split(".")[0] in ("hooks", "guard")]
        self.assertEqual(problems, [], "\n".join(problems))

    # -- R16
    def test_a_module_of_core_names_imports_no_io(self):
        problems = []
        for mod, spec in self.part["modules"].items():
            if mod in self.trees and {self.part["defs"][n]["label"] for n in spec["defs"]} == {"core"}:
                problems += ["%s imports %s" % (mod, n) for n in sorted(top_level_imports(self.trees[mod]) & IO_IMPORTS)]
        self.assertEqual(problems, [], "\n".join(problems))


class TestModuleChecks(unittest.TestCase):
    """module_problems on small synthetic modules: it flags what it must and passes what it may."""

    PART = {
        "modules": {"low": {"layer": 0, "defs": ["LIMIT", "helper", "RUNTIME_X"]},
                    "high": {"layer": 1, "defs": ["use"]}},
        "merged": {"gone": "low"},
        "retired": ["RUNTIME_X"],
        "added": {"low": ["Holder"]},
        "params_added": ["rt"],
        "globals": {},
        "defs": {
            "LIMIT": {"kind": "const", "signature": "", "label": "core",
                      "value_hash": TOOL_MODULE.hash_of(ast.parse("5").body[0].value)},
            "helper": {"kind": "function", "signature": "(a, b=1)", "label": "core", "value_hash": None},
            "RUNTIME_X": {"kind": "const", "signature": "", "label": "shell", "value_hash": None},
            "use": {"kind": "function", "signature": "(root)", "label": "shell", "value_hash": None},
        },
    }

    def check(self, mod, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, mod + ".py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(source)
            return module_problems(self.PART, mod, path)

    def test_a_right_module_passes(self):
        self.assertEqual(self.check("low", "LIMIT = 5\n\ndef helper(a, b=1, rt=None):\n    return a\n\nclass Holder:\n    pass\n"), [])

    def test_a_missing_and_an_extra_name(self):
        found = self.check("low", "LIMIT = 5\nOTHER = 1\n")
        self.assertIn("low: missing helper", found)
        self.assertIn("low: OTHER is not the partition's", found)

    def test_a_changed_signature_and_value(self):
        found = self.check("low", "LIMIT = 6\n\ndef helper(a):\n    pass\n")
        self.assertTrue(any("helper" in p and "partition has" in p for p in found), found)
        self.assertIn("low: LIMIT has another value than state.py's", found)

    def test_global_and_file_are_refused(self):
        found = self.check("low", "LIMIT = 5\n\ndef helper(a, b=1):\n    global LIMIT\n    return __file__\n")
        self.assertTrue(any("`global LIMIT`" in p for p in found), found)
        self.assertTrue(any("__file__" in p for p in found), found)

    def test_an_upward_or_unknown_import_is_refused(self):
        up = self.check("low", "from rr_state import high\nLIMIT = 5\n\ndef helper(a, b=1):\n    pass\n")
        self.assertTrue(any("not downward" in p for p in up), up)
        down = self.check("high", "from rr_state import low\n\ndef use(root):\n    return low.LIMIT\n")
        self.assertEqual(down, [])
        unknown = self.check("high", "import rr_state.nowhere\n\ndef use(root):\n    pass\n")
        self.assertTrue(any("not a module of the partition" in p for p in unknown), unknown)

    def test_a_merged_or_unknown_module_is_refused(self):
        self.assertIn("gone: not a module of the partition (merged into low)", self.check("gone", "X = 1\n"))

    def test_an_all_core_module_may_not_import_io(self):
        part = json.loads(json.dumps(self.PART))
        part["defs"]["RUNTIME_X"]["label"] = "core"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "low.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("import os\nLIMIT = 5\n\ndef helper(a, b=1):\n    return os.sep\n")
            found = module_problems(part, "low", path)
        self.assertEqual([p for p in found if "R16" in p], ["low: all names are core, yet it imports os (R16)"])


class TestValueHash(unittest.TestCase):
    """value_hash is one value on every Python the suite runs on: ast.dump's text changed in 3.13
    (empty fields left out), so a hash of it recorded on 3.14 never matched on the release 3.12."""

    def test_the_hash_is_pinned_across_pythons(self):
        value = ast.parse('re.compile(r"^[a-z0-9][a-z0-9-]*$", re.I)', mode="eval").body
        self.assertEqual(TOOL_MODULE.hash_of(value), "cdcb648a4bcb")


class TestPartitionTool(unittest.TestCase):
    """The tool's exits on small synthetic sources: 0 on a clean graph, 1 on each fault."""

    SOURCE = ("import os\n\n"
              "def leaf():\n    return 1\n\n"
              "def mid():\n    return leaf()\n\n"
              "def reader():\n    return os.getcwd()\n\n"
              "def main():\n    return mid(), reader()\n")

    def part(self, **modules):
        layers = {"low": 0, "mid": 1, "top": 2}
        return {"schema": 1, "optional": [],
                "modules": {m: {"layer": layers[m], "defs": names} for m, names in modules.items()},
                "defs": {n: {"label": "core" if n in ("leaf", "mid") else "shell"}
                         for names in modules.values() for n in names}}

    def run_case(self, source, part, expect):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = os.path.join(tmp, "state.py"), os.path.join(tmp, "partition.json")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write(source)
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(part, handle)
            run_tool("--source", src, "--partition", out, "--write")
            done = run_tool("--source", src, "--partition", out)
        self.assertEqual(done.returncode, expect, done.stdout + done.stderr)
        return done.stdout

    def test_a_clean_partition_exits_zero_and_is_stable(self):
        self.run_case(self.SOURCE, self.part(low=["leaf"], mid=["mid", "reader"], top=["main"]), 0)

    def test_an_unassigned_name_exits_one(self):
        out = self.run_case(self.SOURCE, self.part(low=["leaf"], mid=["mid"], top=["main"]), 1)
        self.assertIn("unassigned: reader", out)

    def test_a_doubly_assigned_name_exits_one(self):
        out = self.run_case(self.SOURCE, self.part(low=["leaf", "mid"], mid=["mid", "reader"], top=["main"]), 1)
        self.assertIn("doubly assigned: mid", out)

    def test_an_upward_edge_exits_one(self):
        part = self.part(low=["mid"], mid=["leaf", "reader"], top=["main"])
        out = self.run_case(self.SOURCE, part, 1)
        self.assertIn("upward edge: low (layer 0) imports mid (layer 1)", out)

    def test_a_cycle_exits_one(self):
        source = "def a():\n    return b()\n\ndef b():\n    return a()\n\ndef main():\n    return a()\n"
        part = {"schema": 1, "optional": [],
                "modules": {"low": {"layer": 0, "defs": ["a"]}, "mid": {"layer": 1, "defs": ["b"]},
                            "top": {"layer": 2, "defs": ["main"]}},
                "defs": {n: {"label": "core"} for n in "ab"} | {"main": {"label": "core"}}}
        out = self.run_case(source, part, 1)
        self.assertIn("cycle: low <-> mid", out)

    def test_a_core_name_that_reaches_io_exits_one(self):
        part = self.part(low=["leaf"], mid=["mid", "reader"], top=["main"])
        part["defs"]["reader"]["label"] = "core"
        out = self.run_case(self.SOURCE, part, 1)
        self.assertIn("core name reaches I/O or process state (R16): reader", out)

    def test_once_the_source_is_the_shim_the_partition_stands_alone(self):
        out = self.run_case("def other():\n    return 1\n", self.part(low=["leaf"], mid=["mid", "reader"], top=["main"]), 0)
        self.assertIn("phase 2", out)


if __name__ == "__main__":
    unittest.main()
