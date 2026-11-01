#!/usr/bin/env python3
"""Partition check for the split of skills/ai-task/state.py into skills/ai-task/rr_state/.

    python3 tools/state-partition.py [--write] [--why FROM:TO] [--partition FILE] [--source FILE]

Reads state.py with `ast`: every top-level name a module will have to own (functions,
classes, module-level constants), and who references whom. Reads
tests/fixtures/state/partition.json (module -> ordered names, layer per module, core or
shell per name), builds the module import graph and prints it with every cycle and every
upward edge (a module that imports from its own layer or a higher one).

Exit 1 on: a cycle, an upward edge, a name of state.py that is assigned to no module or to
two, a name of the partition that state.py does not define (`optional` names excepted), a
core name that reaches I/O (R16), a signature that no longer matches, derived fields that
are stale (run --write). Exit 0 otherwise. Exit 2 is usage.

--write   recompute the derived fields of the partition (signature, kind, refs, imports,
          stdlib, approx_lines, value_hash, inferred label) and keep what a person decides
          (the modules, their layers and members, the label of every name).
--why     list the name-level edges behind the module edge FROM:TO.

Phase 2: once state.py is the shim (it no longer defines `main`) the source holds no
names to scan; the partition is then checked by itself (its recorded import edges).
stdlib only. `__file__` inside a function body counts as a reference to `ENTRY`, so the
graph is the same before and after step s2 of the plan.
"""
import argparse
import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "skills", "ai-task", "state.py")
PARTITION = os.path.join(ROOT, "tests", "fixtures", "state", "partition.json")
VIRTUAL = "ENTRY"                      # `ENTRY = os.path.abspath(__file__)`, added by step s2
BARE_IO = {"open", "print", "input", "exec", "eval", "__import__"}
PURE_PATH = {"join", "dirname", "basename", "normpath", "sep", "splitext", "split", "isabs"}
PURE_OS = {"sep", "linesep", "pathsep", "curdir", "pardir", "fspath"}
CLOCK = {"now", "utcnow", "today"}
IO_MODULES = {"subprocess", "time", "fcntl", "sensors", "importlib", "sys", "shutil", "tempfile"}
IO_CALLS = {"json": {"dump", "load"}}
SCHEMA = 1
DERIVED_DEF = ("kind", "signature", "refs", "global_writes", "lazy", "value_hash", "inferred")
DERIVED_MODULE = ("imports", "stdlib", "lazy", "approx_lines")


# --------------------------------------------------------------------------------------
# reading state.py


def chain_of(node):
    """(root, [attr, ...]) of `a.b.c`; the root is the innermost non-attribute node."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return node, parts[::-1]


def arg_names(args):
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    names += [a.arg for a in (args.vararg, args.kwarg) if a]
    return names


class Bindings(ast.NodeVisitor):
    """The names one function-like scope binds itself, and the ones it declares global."""

    def __init__(self, node):
        super().__init__()
        self.names = set()
        self.declared = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            self.names.update(arg_names(node.args))
            body = node.body if isinstance(node.body, list) else [node.body]
        elif isinstance(node, ast.comprehension):
            body = [node.target]
        else:
            body = []
        for stmt in body:
            self.visit(stmt)

    def visit_Name(self, node):                       # pylint: disable=invalid-name
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_FunctionDef(self, node):                # pylint: disable=invalid-name
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node):                     # pylint: disable=invalid-name,unused-argument
        return

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_Lambda

    def visit_Import(self, node):                     # pylint: disable=invalid-name
        for alias in node.names:
            self.names.add(alias.asname or alias.name.split(".")[0])

    visit_ImportFrom = visit_Import

    def visit_ExceptHandler(self, node):              # pylint: disable=invalid-name
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node):                     # pylint: disable=invalid-name
        self.declared.update(node.names)


class Scan(ast.NodeVisitor):
    """What one top-level name references: other top-level names, imports, I/O."""

    def __init__(self, tops, imports, own):
        super().__init__()
        self.tops, self.imports, self.own = tops, imports, own
        self.scopes = []
        self.refs, self.uses, self.io = set(), set(), set()
        self.global_writes, self.lazy = set(), set()

    def local(self, name):
        for names, declared in reversed(self.scopes):
            if name in declared:
                return False
            if name in names:
                return True
        return False

    def name(self, node, parts=()):
        ident = node.id
        if ident == "__file__":
            ident = VIRTUAL
        if self.local(ident):
            return
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            if self.scopes and ident in self.tops:
                self.global_writes.add(ident)
                self.refs.add(ident)
            return
        if ident in self.tops or ident == VIRTUAL:
            if ident != self.own:
                self.refs.add(ident)
        elif ident in self.imports:
            self.uses.add(ident)
            if self.impure(ident, list(parts)):
                self.io.add(".".join([ident] + list(parts)[:1]))
        elif ident in BARE_IO:
            self.io.add(ident)

    @staticmethod
    def impure(root, parts):
        head = parts[0] if parts else ""
        if root == "os":
            return not ((head == "path" and len(parts) > 1 and parts[1] in PURE_PATH) or head in PURE_OS)
        if root == "datetime":
            return head in CLOCK
        if root in IO_MODULES:
            return True
        return head in IO_CALLS.get(root, ())

    def visit_Name(self, node):                       # pylint: disable=invalid-name
        self.name(node)

    def visit_Attribute(self, node):                  # pylint: disable=invalid-name
        root, parts = chain_of(node)
        if isinstance(root, ast.Name):
            self.name(root, parts)
        else:
            self.visit(root)

    def function(self, node):
        for deco in getattr(node, "decorator_list", []):
            self.visit(deco)
        args = node.args
        for default in args.defaults + [d for d in args.kw_defaults if d]:
            self.visit(default)
        for arg in args.posonlyargs + args.args + args.kwonlyargs + [a for a in (args.vararg, args.kwarg) if a]:
            if arg.annotation:
                self.visit(arg.annotation)
        if getattr(node, "returns", None):
            self.visit(node.returns)
        bound = Bindings(node)
        self.scopes.append((bound.names, bound.declared))
        self.global_writes.update(bound.declared)
        body = node.body if isinstance(node.body, list) else [node.body]
        for stmt in body:
            self.visit(stmt)
        self.scopes.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = function

    def comprehension(self, node):
        names = set()
        for gen in node.generators:
            names.update(Bindings(gen).names)
        self.scopes.append((names, set()))
        self.generic_visit(node)
        self.scopes.pop()

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = comprehension

    def visit_Import(self, node):                     # pylint: disable=invalid-name
        for alias in node.names:
            self.lazy.add(alias.name if isinstance(node, ast.Import) else (node.module or alias.name))

    visit_ImportFrom = visit_Import


def statement_names(node):
    """Names a top-level statement binds, with the value expression of each when it has one."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [(node.name, None)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [(node.target.id, node.value)]
    if not isinstance(node, ast.Assign):
        return []
    found = []
    for target in node.targets:
        if isinstance(target, ast.Name):
            found.append((target.id, node.value))
        elif isinstance(target, ast.Tuple) and all(isinstance(e, ast.Name) for e in target.elts):
            same = isinstance(node.value, ast.Tuple) and len(node.value.elts) == len(target.elts)
            found += [(e.id, node.value.elts[i] if same else node.value) for i, e in enumerate(target.elts)]
    return found


def import_names(tree):
    """Top-level import bindings, the guarded ones (`try: import fcntl`) included."""
    found = set()
    for node in tree.body:
        for sub in ast.walk(node) if isinstance(node, ast.Try) else [node]:
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    found.add(alias.asname or alias.name.split(".")[0])
    return found


def signature_of(node):
    if isinstance(node, ast.ClassDef):
        return "(%s)" % ", ".join(ast.unparse(b) for b in node.bases)
    return "(%s)" % ast.unparse(node.args)


def hash_of(value):
    return hashlib.sha1(ast.dump(value).encode()).hexdigest()[:12]


def read_source(path):
    """{name: record} in source order, or None when the file no longer defines `main`."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    tree = ast.parse(text)
    stmts = {}
    for node in tree.body:
        for name, value in statement_names(node):
            stmts.setdefault(name, (node, value))
    if "main" not in stmts:
        return None
    imports = import_names(tree)
    tops = set(stmts)
    mutable_names = {g for node, _ in stmts.values() for g in global_names(node)}
    found = {}
    for name, (node, value) in stmts.items():
        scan = Scan(tops, imports, name)
        defn = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        scan.visit(node if defn else value)
        rec = {"kind": "function" if isinstance(node, ast.FunctionDef) else
               "class" if isinstance(node, ast.ClassDef) else "const",
               "signature": signature_of(node) if defn else "",
               "refs": sorted(scan.refs), "global_writes": sorted(g for g in scan.global_writes if g in tops),
               "lazy": sorted(scan.lazy), "uses": sorted(scan.uses), "io": sorted(scan.io),
               "mutable": name in mutable_names, "value_hash": None, "line": node.lineno,
               "lines": node.end_lineno - node.lineno + 1,
               "stmt": node.lineno if not defn else None}
        if not defn and value is not None and not scan.refs and name != VIRTUAL:
            rec["value_hash"] = hash_of(value)
        found[name] = rec
    return found


def global_names(node):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    return [g for sub in ast.walk(node) if isinstance(sub, ast.Global) for g in sub.names]


def infer_labels(found):
    """core or shell by R16: shell when it does I/O, reads a clock or the environment, keeps
    process-wide state, or references a shell name; core otherwise. A constant that only
    lists functions (a dispatch table) does nothing by listing them."""
    shell = {n for n, r in found.items() if r["io"] or r["mutable"] or r["global_writes"]}
    changed = True
    while changed:
        changed = False
        for name, rec in found.items():
            if name not in shell and rec["kind"] != "const" and (set(rec["refs"]) & shell):
                shell.add(name)
                changed = True
    return {name: "shell" if name in shell else "core" for name in found}


# --------------------------------------------------------------------------------------
# the partition


def load_partition(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def owners(part):
    """{name: [module, ...]} from the modules' ordered lists."""
    own = {}
    for mod, spec in part["modules"].items():
        for name in spec["defs"]:
            own.setdefault(name, []).append(mod)
    return own


def module_edges(part, refs):
    """{(from, to): [(name, target), ...]} over the name-level references."""
    own = {n: m[0] for n, m in owners(part).items()}
    edges = {}
    for name, targets in refs.items():
        src = own.get(name)
        for target in targets:
            dst = own.get(target)
            if src and dst and src != dst:
                edges.setdefault((src, dst), []).append((name, target))
    return edges


def cycles_of(modules, edges):
    """Strongly connected components with more than one module (Tarjan)."""
    graph = {m: sorted(b for (a, b) in edges if a == m) for m in modules}
    index, low, stack, on, found, counter = {}, {}, [], set(), [], [0]

    def visit(node):
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on.add(node)
        for nxt in graph[node]:
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            comp = []
            while True:
                top = stack.pop()
                on.discard(top)
                comp.append(top)
                if top == node:
                    break
            if len(comp) > 1:
                found.append(sorted(comp))

    for node in modules:
        if node not in index:
            visit(node)
    return found


def derive(part, found):
    """The derived fields of every name and module, from the source."""
    own = {n: m[0] for n, m in owners(part).items()}
    inferred = infer_labels(found)
    defs, mods = {}, {}
    for mod, spec in part["modules"].items():
        imports, stdlib, lazy, lines = {}, set(), set(), 0
        for name in spec["defs"]:
            rec = found.get(name)
            if rec is None:
                continue
            lines += rec["lines"]
            stdlib.update(rec["uses"])
            lazy.update(rec["lazy"])
            for target in rec["refs"]:
                if own.get(target) not in (None, mod):
                    imports.setdefault(own[target], set()).add(target)
        mods[mod] = {"imports": {m: sorted(v) for m, v in sorted(imports.items(), key=lambda kv: (part["modules"][kv[0]]["layer"], kv[0]))},
                     "stdlib": sorted(stdlib), "lazy": sorted(lazy), "approx_lines": lines}
    for name, rec in found.items():
        defs[name] = {"kind": rec["kind"], "signature": rec["signature"], "refs": rec["refs"],
                      "global_writes": rec["global_writes"], "lazy": rec["lazy"],
                      "value_hash": rec["value_hash"], "inferred": inferred[name]}
    return defs, mods


def derive_globals(part, found):
    """Module-level names some function rebinds with `global`: owner, writers, readers (R4)."""
    own = {n: m[0] for n, m in owners(part).items()}
    names = sorted({g for r in found.values() for g in r["global_writes"] if g in found})
    out = {}
    for name in names:
        writers = sorted(n for n, r in found.items() if name in r["global_writes"])
        readers = sorted(n for n, r in found.items() if name in r["refs"] and n not in writers)
        out[name] = {"owner": own.get(name), "writers": writers, "readers": readers}
    return out


def write_partition(path, part, found):
    """Refresh the derived fields; keep modules, members, groups and labels."""
    defs, mods = derive(part, found)
    old_globals = part.get("globals", {})
    part["globals"] = {k: dict(v, plan=old_globals.get(k, {}).get("plan", ""))
                       for k, v in derive_globals(part, found).items()}
    old = part.get("defs", {})
    new_defs = {}
    for mod_spec in part["modules"].values():
        for name in mod_spec["defs"]:
            if name in defs:
                rec = dict(defs[name])
                rec["label"] = old.get(name, {}).get("label", rec["inferred"])
            else:
                rec = dict(old.get(name, {"kind": "const", "signature": "", "refs": [], "global_writes": [],
                                          "lazy": [], "value_hash": None, "inferred": "shell", "label": "shell"}))
            new_defs[name] = rec
    for mod, spec in part["modules"].items():
        spec.update(mods[mod])
    part["defs"] = new_defs
    part["schema"] = SCHEMA
    dump_partition(path, part)


def dump_partition(path, part):
    """One line per module and per name: reviewable in a diff."""
    lines = ["{"]
    keys = [k for k in part if k not in ("modules", "defs", "globals")]
    for key in keys:
        lines.append(" %s: %s," % (json.dumps(key), json.dumps(part[key], ensure_ascii=False)))
    for key in ("modules", "globals", "defs"):
        lines.append(" %s: {" % json.dumps(key))
        items = list(part.get(key, {}).items())
        for i, (name, rec) in enumerate(items):
            lines.append("  %s: %s%s" % (json.dumps(name), json.dumps(rec, ensure_ascii=False),
                                         "," if i < len(items) - 1 else ""))
        lines.append(" }%s" % ("," if key != "defs" else ""))
    lines.append("}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------------------
# the checks


def check_membership(part, found, problems):
    own = owners(part)
    optional = set(part.get("optional", []))
    for name in found:
        mods = own.get(name, [])
        if not mods:
            problems.append("unassigned: %s (state.py:%d)" % (name, found[name]["line"]))
        elif len(mods) > 1:
            problems.append("doubly assigned: %s -> %s" % (name, ", ".join(mods)))
    for name, mods in own.items():
        if len(mods) > 1 and name not in found:
            problems.append("doubly assigned: %s -> %s" % (name, ", ".join(mods)))
        if name not in found and name not in optional:
            problems.append("in the partition but not in state.py: %s" % name)
    for name in part.get("defs", {}):
        if name not in own:
            problems.append("labelled but owned by no module: %s" % name)
    for mod, spec in part["modules"].items():
        for name in spec["defs"]:
            label = part.get("defs", {}).get(name, {}).get("label")
            if label not in ("core", "shell"):
                problems.append("no core/shell label: %s (%s)" % (name, mod))


def check_statements(part, found, notes):
    """A tuple assignment split over two modules is a rewrite of one statement: say so."""
    own = {n: m[0] for n, m in owners(part).items()}
    by_stmt = {}
    for name, rec in found.items():
        if rec["stmt"] is not None:
            by_stmt.setdefault(rec["stmt"], []).append(name)
    for names in by_stmt.values():
        homes = {own.get(n) for n in names}
        if len(names) > 1 and len(homes) > 1:
            notes.append("statement split over modules: %s -> %s"
                         % (", ".join(names), ", ".join(sorted(h for h in homes if h))))


def check_labels(part, found, problems):
    inferred = infer_labels(found)
    for name, rec in part.get("defs", {}).items():
        if rec.get("label") == "core" and inferred.get(name) == "shell":
            why = found[name]["io"] or found[name]["global_writes"] or \
                [r for r in found[name]["refs"] if inferred.get(r) == "shell"]
            problems.append("core name reaches I/O or process state (R16): %s (%s)"
                            % (name, ", ".join(sorted(map(str, why))[:4])))


def check_signatures(part, found, problems):
    for name, rec in part.get("defs", {}).items():
        if name in found and rec.get("signature") != found[name]["signature"]:
            problems.append("signature changed: %s %s -> %s" % (name, rec.get("signature"), found[name]["signature"]))


def check_stale(part, found, problems):
    defs, mods = derive(part, found)
    for name, rec in derive_globals(part, found).items():
        old = part.get("globals", {}).get(name, {})
        if any(old.get(k) != rec[k] for k in rec):
            problems.append("stale global record of %s: run --write" % name)
    for mod, spec in part["modules"].items():
        for key in ("imports", "stdlib", "lazy"):
            if spec.get(key) != mods[mod][key]:
                problems.append("stale %s of module %s: run --write" % (key, mod))
    for name, rec in defs.items():
        old = part.get("defs", {}).get(name)
        if old and any(old.get(k) != rec[k] for k in ("kind", "refs", "global_writes", "lazy", "value_hash", "inferred")):
            problems.append("stale record of %s: run --write" % name)


def check_graph(part, edges, problems, report):
    layer = {m: s["layer"] for m, s in part["modules"].items()}
    for comp in cycles_of(list(part["modules"]), edges):
        problems.append("cycle: %s" % " <-> ".join(comp))
    for (src, dst), why in sorted(edges.items(), key=lambda kv: (layer[kv[0][0]], kv[0])):
        if layer[dst] >= layer[src]:
            kind = "upward" if layer[dst] > layer[src] else "same-layer"
            names = ", ".join("%s->%s" % w for w in why[:3])
            problems.append("%s edge: %s (layer %d) imports %s (layer %d): %s%s"
                            % (kind, src, layer[src], dst, layer[dst], names, " ..." if len(why) > 3 else ""))
    report.append("module import graph (%d modules, %d edges):" % (len(part["modules"]), len(edges)))
    for mod, spec in part["modules"].items():
        lower = ", ".join("%s(%d)" % (m, len(v)) for m, v in spec.get("imports", {}).items()) or "-"
        report.append("  L%d %-14s %3d names %5d lines  imports: %s"
                      % (spec["layer"], mod, len(spec["defs"]), spec.get("approx_lines", 0), lower))


def refs_from_partition(part):
    return {n: rec.get("refs", []) for n, rec in part.get("defs", {}).items()}


def explain(edges, pair):
    src, _, dst = pair.partition(":")
    for name, target in edges.get((src, dst), []):
        print("%s -> %s" % (name, target))
    if (src, dst) not in edges:
        print("no edge %s -> %s" % (src, dst))


def main(argv=None):
    ap = argparse.ArgumentParser(description="check the partition of skills/ai-task/state.py")
    ap.add_argument("--write", action="store_true", help="refresh the derived fields of the partition")
    ap.add_argument("--why", metavar="FROM:TO", help="list the name-level edges behind a module edge")
    ap.add_argument("--partition", default=PARTITION)
    ap.add_argument("--source", default=SOURCE)
    args = ap.parse_args(argv)
    try:
        part = load_partition(args.partition)
        found = read_source(args.source)
    except (OSError, ValueError, SyntaxError) as err:
        print("state-partition: %s" % err, file=sys.stderr)
        return 2
    problems, notes, report = [], [], []
    if found is None:
        report.append("phase 2: %s no longer defines main; the partition is checked by itself" % args.source)
        refs = refs_from_partition(part)
    else:
        if args.write:
            write_partition(args.partition, part, found)
            part = load_partition(args.partition)
        refs = {n: r["refs"] for n, r in found.items()}
        check_membership(part, found, problems)
        check_statements(part, found, notes)
        check_signatures(part, found, problems)
        check_labels(part, found, problems)
        check_stale(part, found, problems)
    edges = module_edges(part, refs)
    check_graph(part, edges, problems, report)
    if args.why:
        explain(edges, args.why)
    print("\n".join(report))
    for note in notes:
        print("note: " + note)
    for problem in problems:
        print("PROBLEM: " + problem)
    print("%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
