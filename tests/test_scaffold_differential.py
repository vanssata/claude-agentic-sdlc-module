#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The frozen shell scaffolds beside the port: same arguments, same tree, same bytes.

tests/fixtures/scaffold-port/ holds project-scaffold.sh and scaffold-ai.sh as
they were when the port was made. Each case runs a sequence of invocations
through the frozen scripts and through the live ones, each installed into a
throwaway plugin tree (under .claude/ or .codex/, which `auto` reads), over a
project of the same name. After every invocation the two records — exit code,
stdout, stderr and every file and directory of the project with its mode and
bytes — must be identical, with the temporary paths replaced by placeholders.

Two messages come from bash itself, not from the script: a missing --runtime
value and a project directory that does not exist. bash prefixes them with the
script's path and line, which a port cannot keep; those cases compare the exit
code, the tree and the message text without the prefix.

Every case runs under C, C.UTF-8 and en_US.UTF-8 where the system has them:
`find | sort` orders the "created" listing by the locale's collation.
"""
import concurrent.futures
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
FROZEN = os.path.join(TESTS, "fixtures", "scaffold-port")
AI_TPL = os.path.join(REPO, "skills", "ai-init", "templates")
PROJECT_TPL = os.path.join(REPO, "skills", "project-init", "templates")
ENV_KEYS = ("AI_RUNTIMES", "AI_PROJECT_TEMPLATES", "CLAUDE_ROUTING_TEMPLATES", "CLAUDE_AGENTIC_TEMPLATES")

# The scripts, as installed: (path in the plugin tree, frozen source, live sources).
SCRIPTS = {
    "project": ("hooks/project-scaffold.sh", "project-scaffold.sh",
                ("hooks/project-scaffold.sh", "hooks/project-scaffold.py")),
    "ai": ("skills/ai-init/scaffold-ai.sh", "scaffold-ai.sh",
           ("skills/ai-init/scaffold-ai.sh", "skills/rr-setup/scaffold_ai.py")),
}


def locales():
    try:
        have = subprocess.run(["locale", "-a"], capture_output=True, text=True, check=False).stdout.split()
    except OSError:
        have = []
    norm = {h.lower().replace("-", ""): h for h in have}
    out = ["C"]
    for want in ("c.utf8", "en_us.utf8"):
        if want in norm:
            out.append(norm[want])
    return out


def plugin_tree(base, home, variant):
    """A plugin installed under base/<home>/: the scripts and the two template dirs."""
    root = os.path.join(base, home)
    for rel, frozen, live in SCRIPTS.values():
        if variant == "shell":
            pairs = [(os.path.join(FROZEN, frozen), rel)]
        else:
            pairs = [(os.path.join(REPO, src), src) for src in live if os.path.exists(os.path.join(REPO, src))]
        for src, dst in pairs:
            dst = os.path.join(root, dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
    os.makedirs(os.path.join(root, "skills", "project-init"), exist_ok=True)
    os.symlink(AI_TPL, os.path.join(root, "skills", "ai-init", "templates"))
    os.symlink(PROJECT_TPL, os.path.join(root, "skills", "project-init", "templates"))
    return root


def snapshot(root):
    out = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs) + sorted(files):
            p = os.path.join(d, name)
            st = os.lstat(p)
            rel = os.path.relpath(p, root)
            if stat.S_ISREG(st.st_mode):
                with open(p, "rb") as fh:
                    out.append((rel, oct(st.st_mode), fh.read()))
            else:
                out.append((rel, oct(st.st_mode), os.readlink(p) if stat.S_ISLNK(st.st_mode) else None))
    return out


# The prefix of a message bash raises itself: "<script>: line <n>: " from the
# shell, the script's own name from the port.
BASH_PREFIX = re.compile(rb"^(?:.*?: line \d+|project-scaffold|scaffold-ai): ", re.M)


class Case:
    """A setup over the project dir, then invocations: (args, stdin, env, cwd) where cwd is
    False for the project dir, True for its parent, LINK for a symlink to it beside it.
    <ROOT> in args, stdin and env values is the project dir; an env value None unsets it."""

    def __init__(self, label, script, runs, setup=None, loose=False, name="proj", home=".claude", umask=None):
        self.label, self.script, self.runs = label, script, runs
        self.setup, self.loose, self.name, self.home = setup, loose, name, home
        self.umask = umask


def write(rel, data, mode=None):
    def go(root):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        if mode is not None:
            os.chmod(p, mode)
    return go


def mkdir(rel):
    return lambda root: os.makedirs(os.path.join(root, rel), exist_ok=True)


def chain(*fns):
    def go(root):
        for fn in fns:
            fn(root)
    return go


def legacy_agents(name):
    with open(os.path.join(AI_TPL, "AGENTS.block.md"), "rb") as fh:
        block = fh.read()
    block = re.sub(rb"claude-agentic:(start|end)", name.encode() + rb":\1", block)
    return write("AGENTS.md", b"# mine\n\nkeep this.\n\n" + block)


R = "<ROOT>"   # replaced by the project dir in args, stdin and env values
LINK = "link"
# Cases run again under C.UTF-8 and en_US.UTF-8: those that list many created files or carry UTF-8.
COLLATED = re.compile(r"fresh|both|UTF-8|existing files|without VERSION")


def cases():
    out = []
    for script in ("project", "ai"):
        def c(label, runs, **kw):
            out.append(Case("%s: %s" % (script, label), script, runs, **kw))
        twice = lambda args, **kw: [(args, b"", kw.get("env", {}), False)] * 2
        c("fresh, then rerun", twice([R]))
        c("fresh from a Codex install", twice([R]), home=".codex")
        for rt in ("both", "codex", "claude", "claude,gemini", "junie", "gemini,junie,codex,claude",
                   "claude,", ",claude", ",", "nope", "claude,,codex", "auto"):
            c("--runtime %s" % rt, twice([R, "--runtime", rt]))
        c("--runtime=codex", twice(["--runtime=codex", R]))
        c("--runtime given twice, last wins", twice([R, "--runtime", "nope", "--runtime", "codex"]))
        c("AI_RUNTIMES=codex", twice([R], env={"AI_RUNTIMES": "codex"}))
        c("AI_RUNTIMES overridden by --runtime", twice([R, "--runtime", "claude"], env={"AI_RUNTIMES": "x"}))
        c("--runtime without a value", [([R, "--runtime"], b"", {}, False)], loose=True)
        c("--runtime with an empty value", [([R, "--runtime", ""], b"", {}, False)], loose=True)
        c("a project dir that does not exist", [([R + "/missing"], b"", {}, False)], loose=True)
        c("two positional dirs, the last wins", twice(["/nonexistent-first", R]))
        c("auto: AGENTS.md declares Codex", twice([R]), setup=write("AGENTS.md", b"# existing\n"))
        c("auto: .codex/ declares Codex", twice([R]), setup=mkdir(".codex"))
        c("auto: GEMINI.md and .junie/", twice([R]), setup=chain(write("GEMINI.md", b"g"), mkdir(".junie")))
        c("auto: .gemini/ and .claude/", twice([R]), setup=chain(mkdir(".gemini"), mkdir(".claude")))
        c("existing .gitignore without a trailing newline", twice([R]),
          setup=write(".gitignore", b"vendor/\nnode_modules/"))
        c("empty .gitignore", twice([R]), setup=write(".gitignore", b""))
        c(".gitignore that already carries both markers", twice([R]),
          setup=write(".gitignore", b".claude/settings.local.json\n.ai/state/*.json\n"))
        c("existing CLAUDE.md without a trailing newline", twice([R]), setup=write("CLAUDE.md", b"# mine\nmake test"))
        c("empty CLAUDE.md", twice([R]), setup=write("CLAUDE.md", b""))
        c("existing files are never overwritten", twice([R, "--runtime", "both"]),
          setup=chain(write("docs/sdlc/README.md", b"mine"), write(".ai/policies/safety.md", b"mine"),
                      write(".claude/plans/.gitkeep", b"kept"), write(".codex/config.toml", b"x")))
        c(".ai/ without VERSION", twice([R]), setup=write(".ai/project/overview.md", b"# mine\n"))
        c("stdin hook JSON names the cwd", [([], b'{"cwd": "<ROOT>"}', {}, True)] * 2)
        c("stdin garbage falls back to $PWD", [([], b"not json", {}, False)] * 2)
        c("stdin JSON without cwd falls back to $PWD", [([], b'{"x": 1}', {}, False)] * 2)
        c("a relative project dir through a symlink", [(["link"], b"", {}, True)] * 2,
          setup=lambda root: os.symlink(os.path.basename(root), os.path.join(os.path.dirname(root), "link")))
        # bash's `cd` folds `..` only past a directory, and reads a leading dash as options.
        c("a `..` past a missing directory", [([R + "/missing/.."], b"", {}, False)], loose=True)
        c("a `..` past a regular file", [([R + "/f/.."], b"", {}, False)], loose=True, setup=write("f", b""))
        c("a `..` past a dangling symlink", [([R + "/dang/.."], b"", {}, False)], loose=True,
          setup=lambda root: os.symlink("nowhere", os.path.join(root, "dang")))
        c("a `..` past a directory and a `.`", twice([R + "/d/./.."]), setup=mkdir("d"))
        c("a `..` past a symlinked directory", twice([R + "/ld/.."]),
          setup=chain(mkdir("d"), lambda root: os.symlink("d", os.path.join(root, "ld"))))
        for opt in ("-x", "-Lx", "--x", "-@", "--runtimex"):
            c("an invalid cd option %s" % opt, [([opt], b"", {}, False)], loose=True, setup=mkdir(opt))
        home = {"HOME": R + "/h"}
        for opt in ("--", "-L", "-P", "-LP", "-PL", "-eP"):
            c("%s goes to a symlinked $HOME" % opt, twice([opt], env=home),
              setup=chain(mkdir("hd"), lambda root: os.symlink("hd", os.path.join(root, "h"))))
            c("%s with an empty $HOME" % opt, [([opt], b"", {"HOME": ""}, False)] * 2, loose=True)
        c("-- with $HOME unset", [(["--"], b"", {"HOME": None}, False)], loose=True)
        c("-- with a missing $HOME", [(["--"], b"", {"HOME": R + "/nope"}, False)], loose=True)
        c("an existing .gitignore ending in a NUL", twice([R]), loose=True, setup=write(".gitignore", b"vendor/\0"))
        c("an existing CLAUDE.md ending in a NUL", twice([R]), loose=True, setup=write("CLAUDE.md", b"# mine\0"))
        c("stdin cwd with a trailing newline", [([], b'{"cwd": "<ROOT>\\n\\n"}', {}, True)] * 2)
        c("`.` from a symlinked $PWD", [(["."], b"", {}, LINK)] * 2,
          setup=lambda root: os.symlink(os.path.basename(root), os.path.join(os.path.dirname(root), LINK)))
        c("a project name with sed metacharacters", twice([R, "--runtime", "both"]), name="a&b\\c|d")
        c("a project name with spaces and UTF-8", twice([R, "--runtime", "gemini,junie"]), name="мой проект")
        for loc in ("Codex-agentic", "codex-agentic", "claude-agentic"):
            c("a %s block in AGENTS.md" % loc, twice([R, "--runtime", "codex"]), setup=legacy_agents(loc))
    out.append(Case("project: templates not found", "project", [([R], b"", {"AI_PROJECT_TEMPLATES": "/nope"}, False)]))
    out.append(Case("project: CLAUDE_ROUTING_TEMPLATES not found", "project",
                    [([R], b"", {"CLAUDE_ROUTING_TEMPLATES": "/nope"}, False)]))
    out.append(Case("project: AI_PROJECT_TEMPLATES before CLAUDE_ROUTING_TEMPLATES", "project",
                    [([R], b"", {"AI_PROJECT_TEMPLATES": "/nope", "CLAUDE_ROUTING_TEMPLATES": PROJECT_TPL}, False),
                     ([R], b"", {"AI_PROJECT_TEMPLATES": PROJECT_TPL, "CLAUDE_ROUTING_TEMPLATES": "/nope"}, False)]))
    # The snippet is read only to append it: a scaffolded .gitignore needs none.
    no_snippet = {"AI_PROJECT_TEMPLATES": R + "/../tpl", "CLAUDE_AGENTIC_TEMPLATES": R + "/../tpl"}
    for script, tpl, marker in (("project", PROJECT_TPL, b".claude/settings.local.json\n"),
                                ("ai", AI_TPL, b".ai/state/*.json\n")):
        def strip_snippet(root, tpl=tpl, marker=marker):
            dst = os.path.join(os.path.dirname(root), "tpl")
            shutil.copytree(tpl, dst)
            os.remove(os.path.join(dst, "gitignore.snippet"))
            write(".gitignore", marker)(root)
        out.append(Case("%s: templates without gitignore.snippet, .gitignore scaffolded" % script, script,
                        [([R], b"", no_snippet, False)] * 2, setup=strip_snippet))
    out.append(Case("ai: templates not found", "ai", [([R], b"", {"CLAUDE_AGENTIC_TEMPLATES": "/nope"}, False)]))
    return out


def exec_templates(base):
    """Template copies where a cp-copied and a sed-rendered file are executable."""
    proj = os.path.join(base, "ptpl")
    ai = os.path.join(base, "atpl")
    shutil.copytree(PROJECT_TPL, proj)
    shutil.copytree(AI_TPL, ai)
    for p in (os.path.join(proj, "sdlc-README.md"), os.path.join(proj, "CLAUDE.md"),
              os.path.join(ai, ".ai", "AGENTS.md"), os.path.join(ai, "CLAUDE.minimal.md")):
        os.chmod(p, 0o755)
    return {"AI_PROJECT_TEMPLATES": proj, "CLAUDE_AGENTIC_TEMPLATES": ai}


class ScaffoldDifferentialTest(unittest.TestCase):

    def run_variant(self, base, variant, case, loc, extra_env):
        plugin = plugin_tree(os.path.join(base, "plugin"), case.home, variant)
        parent = os.path.join(base, "work")
        root = os.path.join(parent, case.name)
        os.makedirs(root)
        if case.setup:
            case.setup(root)
        script = os.path.join(plugin, SCRIPTS[case.script][0])
        records = []
        for args, stdin, env, in_parent in case.runs:
            e = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
            e.update(extra_env)
            for k, v in env.items():
                if v is None:
                    e.pop(k, None)
                else:
                    e[k] = v.replace(R, root)
            e["LC_ALL"] = loc
            cwd = os.path.join(parent, LINK) if in_parent == LINK else parent if in_parent else root
            e["PWD"] = cwd
            argv = ["bash", script] + [a.replace(R, root) for a in args]
            if case.umask is not None:
                argv = ["sh", "-c", 'umask %s; exec "$@"' % case.umask, "sh"] + argv
            p = subprocess.run(argv, input=stdin.replace(R.encode(), os.fsencode(root)), capture_output=True,
                               cwd=cwd, env=e, check=False, timeout=60)
            subst = lambda b: (b.replace(os.fsencode(root), b"<ROOT>").replace(os.fsencode(parent), b"<WORK>")
                               .replace(os.fsencode(plugin), b"<PLUGIN>"))
            err = subst(p.stderr)
            if case.loose:
                err = BASH_PREFIX.sub(b"", err)
            records.append((p.returncode, subst(p.stdout), err, snapshot(parent)))
        return records

    def records(self, case, loc, exec_tpl=False):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            env_a = exec_templates(a) if exec_tpl else {}
            env_b = exec_templates(b) if exec_tpl else {}
            return self.run_variant(a, "shell", case, loc, env_a), self.run_variant(b, "port", case, loc, env_b)

    def compare(self, case, loc, shell, port):
        for i, (s, p) in enumerate(zip(shell, port)):
            for what, x, y in zip(("exit", "stdout", "stderr", "tree"), s, p):
                self.assertEqual(x, y, "%s [%s] run %d: %s differs" % (case.label, loc, i + 1, what))

    def test_frozen_and_live_agree(self):
        """Every case under C; the cases whose listing collation can reorder under the other locales."""
        jobs = []
        for loc in locales():
            jobs += [(case, loc) for case in cases() if loc == "C" or COLLATED.search(case.label)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            done = list(pool.map(lambda job: self.records(*job), jobs))
        for (case, loc), (shell, port) in zip(jobs, done):
            with self.subTest(case=case.label, locale=loc):
                self.compare(case, loc, shell, port)

    def test_template_modes_are_kept(self):
        """cp keeps an executable template's mode less the umask; a {{PROJECT}} rendering does not."""
        for script in ("project", "ai"):
            for mask in (None, "027", "077"):
                case = Case("%s: executable templates, umask %s" % (script, mask), script,
                            [(["<ROOT>", "--runtime", "both"], b"", {}, False)], umask=mask)
                with self.subTest(case=case.label):
                    self.compare(case, "C", *self.records(case, "C", exec_tpl=True))

    def test_frozen_copies_are_the_shell_scaffold(self):
        """The fixtures are scripts, not shims: the port is compared with the real thing."""
        for _, frozen, _ in SCRIPTS.values():
            with open(os.path.join(FROZEN, frozen), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("put()" if frozen == "project-scaffold.sh" else "instruction_file()", text)
            self.assertNotIn("exec python3", text)


if __name__ == "__main__":
    unittest.main()
