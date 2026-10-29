#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
install.sh --target: auto-detection must install each runtime only where that
runtime exists, an explicit --target must override detection, and a host with
neither runtime must fail loudly instead of writing a half-configured tree.

PATH is reduced to /usr/bin:/bin plus a scratch bin/, so the developer's own
claude and codex executables (typically in ~/.local/bin) are invisible here.
The environment is the shell suite's `env -i`: HOME, PATH, CLAUDE_DIR, CODEX_DIR
and nothing else. The sections share one scratch tree in the shell suite's
order (the reinstall reuses the explicit-both homes): test_NN_ names keep it.
"""
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, install, read  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-dual-runtime-install.sh"

BASE_PATH = "/usr/bin:/bin"
CLAUDE_MARK = re.compile(r"^# Model routing \(.* plan\)$", re.M)
CODEX_MARK = re.compile(r"^# Model allocation by task", re.M)


def wrote(path):
    return os.path.isdir(path) and bool(os.listdir(path))


def has(path, pattern):
    try:
        return re.search(pattern, read(path)) is not None
    except OSError:
        return False


def contains(path, text):
    try:
        return text in read(path)
    except OSError:
        return False


def tree(root):
    """Relative directories and files of a tree, files with their bytes (diff -r)."""
    dirs, files = set(), {}
    for base, names, fnames in os.walk(root):
        for name in names:
            dirs.add(os.path.relpath(os.path.join(base, name), root))
        for name in fnames:
            full = os.path.join(base, name)
            with open(full, "rb") as fh:
                files[os.path.relpath(full, root)] = fh.read()
    return dirs, files


def same_tree(a, b):
    try:
        return tree(a) == tree(b)
    except OSError:
        return False


class DualRuntimeInstall(ScratchCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bin = os.path.join(cls.tmp, "bin")
        os.makedirs(cls.bin)

    def stub(self, *names):
        """Put fake runtimes on the scratch PATH."""
        for entry in os.listdir(self.bin):
            os.remove(os.path.join(self.bin, entry))
        for name in names:
            target = os.path.join(self.bin, name)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/sh\nexit 0\n")
            os.chmod(target, 0o755)

    def run_case(self, name, *args):
        """Fresh scratch homes, never created up front, so "the directory exists"
        cannot be mistaken for "the runtime is installed"."""
        os.makedirs(self.path(name), exist_ok=True)
        env = {"HOME": self.path(name, "home"), "PATH": self.bin + ":" + BASE_PATH,
               "CLAUDE_DIR": self.path(name, "claude"), "CODEX_DIR": self.path(name, "codex")}
        return install(*args, env=env)

    def check(self, label, cond, detail=""):
        with self.subTest(label):
            self.assertTrue(cond, detail or label)

    def test_01_only_claude_present(self):
        self.stub("claude")
        _, out = self.run_case("claude-only", "--target", "auto", "--plan", "max", "--fable", "yes")
        self.check("auto installed Claude", wrote(self.path("claude-only", "claude")), "Claude should have been installed\n" + out)
        self.check("Codex is left untouched", not wrote(self.path("claude-only", "codex")), "auto must not touch Codex when it is absent")
        self.check("the detected runtime is reported", re.search(r"detected runtime: claude$", out, re.M), "expected 'detected runtime: claude'\n" + out)

    def test_02_only_codex_present(self):
        self.stub("codex")
        _, out = self.run_case("codex-only", "--target", "auto")
        self.check("auto installed Codex", wrote(self.path("codex-only", "codex")), "Codex should have been installed\n" + out)
        self.check("Claude is left untouched", not wrote(self.path("codex-only", "claude")), "auto must not touch Claude when it is absent")
        self.check("no Claude plan is asked for", "Enter plan" not in out, "a Codex-only install must not ask for a Claude plan")

    def test_03_both_present(self):
        self.stub("claude", "codex")
        _, out = self.run_case("both", "--target", "auto", "--plan", "max", "--fable", "yes")
        self.check("auto installed Claude", wrote(self.path("both", "claude")), "Claude missing\n" + out)
        self.check("auto installed Codex", wrote(self.path("both", "codex")), "Codex missing\n" + out)
        self.check("the Claude summary is printed", "Done (Claude Code)" in out, "no Claude summary\n" + out)
        self.check("the Codex summary is printed", "Done (Codex)" in out, "no Codex summary\n" + out)

    def test_04_a_leftover_directory_is_not_an_installed_runtime(self):
        self.stub("claude")
        os.makedirs(self.path("dir-only", "codex"))
        _, out = self.run_case("dir-only", "--target", "auto", "--plan", "max", "--fable", "yes")
        self.check("auto installed Claude", wrote(self.path("dir-only", "claude")), "Claude should have been installed")
        self.check("the Codex directory is left untouched", not wrote(self.path("dir-only", "codex")),
                   "a codex directory without a codex executable must be left alone")
        self.check("no Codex plan is asked for", not re.search(r"codex plan|ChatGPT plan", out), "no Codex plan may be asked for or chosen")
        self.check("the skip is reported with its reason", "no codex on PATH — skipped" in out,
                   "expected the skip note\n" + "\n".join(out.splitlines()[:3]))
        self.check("the note names the override", "--target both" in out, "the note should suggest --target both")

        # A path with a space is one path, in the note as everywhere else.
        self.stub("claude")
        os.makedirs(self.path("dir only spaced", "codex"))
        _, out = self.run_case("dir only spaced", "--target", "auto", "--plan", "max", "--fable", "yes")
        self.check("the note keeps a path with spaces whole",
                   "codex: %s found but no codex on PATH" % self.path("dir only spaced", "codex") in out,
                   "the note split the path\n" + "\n".join(out.splitlines()[:3]))

        self.stub()
        os.makedirs(self.path("dirs-only", "claude"))
        os.makedirs(self.path("dirs-only", "codex"))
        rc, out = self.run_case("dirs-only", "--target", "auto")
        self.check("directories alone are no runtime: it stops and says so", rc != 0 and "No supported runtime" in out,
                   "expected 'No supported runtime'\n" + "\n".join(out.splitlines()[:3]))
        self.check("no plan is asked for", not re.search(r"Enter plan|codex plan|ChatGPT plan", out), "nothing may be asked for")

    def test_05_neither_present(self):
        self.stub()
        rc, out = self.run_case("neither", "--target", "auto")
        self.check("a host with no runtime exits non-zero", rc != 0, "expected a non-zero exit\n" + out)
        self.check("nothing is written", not wrote(self.path("neither", "claude")), "nothing may be written when no runtime is found")
        self.check("no Codex tree either", not wrote(self.path("neither", "codex")), "nothing may be written when no runtime is found")
        self.check("the error names the override", "--target claude" in out, "the error should suggest --target\n" + out)

    def test_06_an_explicit_target_overrides_detection(self):
        self.stub("codex")
        _, out = self.run_case("explicit-claude", "--target", "claude", "--plan", "max", "--fable", "yes")
        self.check("--target claude installs Claude with no claude executable", wrote(self.path("explicit-claude", "claude")),
                   "should install Claude\n" + out)
        self.check("--target claude leaves Codex alone", not wrote(self.path("explicit-claude", "codex")),
                   "--target claude must leave Codex alone even when Codex is present")

        self.stub("claude")
        _, out = self.run_case("explicit-codex", "--target", "codex")
        self.check("--target codex installs Codex with no codex executable", wrote(self.path("explicit-codex", "codex")),
                   "should install Codex\n" + out)
        self.check("--target codex leaves Claude alone", not wrote(self.path("explicit-codex", "claude")),
                   "--target codex must leave Claude alone")

        self.stub()
        _, out = self.run_case("explicit-both", "--target", "both", "--plan", "pro")
        self.check("--target both installs Claude without detection", wrote(self.path("explicit-both", "claude")),
                   "should install Claude\n" + out)
        self.check("--target both installs Codex without detection", wrote(self.path("explicit-both", "codex")),
                   "should install Codex\n" + out)

    def test_07_each_runtime_renders_its_own_routing(self):
        # Each runtime renders its own routing.md; one shared temp file meant the
        # second render (Codex) overwrote the first before Claude's was installed.
        cr = self.path("explicit-both", "claude", "riskrails", "routing.md")
        xr = self.path("explicit-both", "codex", "riskrails", "routing.md")
        self.check("Claude's routing.md is the Claude text", has(cr, CLAUDE_MARK) and not has(cr, CODEX_MARK),
                   "Claude's routing.md is not the Claude text")
        self.check("Codex's routing.md is the Codex text", has(xr, CODEX_MARK) and not has(xr, CLAUDE_MARK),
                   "Codex's routing.md is not the Codex text")

    def test_08_the_shared_tree_per_home(self):
        # The shared .ai/ tree (T-2026-10-13-004): each home gets its own copy and its
        # own resolver, and its routing.md names that home's tree, never the other's.
        for home in ("claude", "codex"):
            other = "codex" if home == "claude" else "claude"
            h = self.path("explicit-both", home)
            rr = os.path.join(h, "riskrails")
            routing = os.path.join(rr, "routing.md")
            self.check("$home: riskrails/ai equals ai/".replace("$home", home),
                       same_tree(os.path.join(PLUGIN, "ai"), os.path.join(rr, "ai")),
                       "%s: riskrails/ai differs from ai/" % home)
            ai_path = os.path.join(rr, "ai-path")
            self.check("$home: ai-path is executable".replace("$home", home),
                       os.path.isfile(ai_path) and os.access(ai_path, os.X_OK), "%s: ai-path is missing or not executable" % home)
            self.check("$home: routing.md names its own shared tree".replace("$home", home),
                       contains(routing, os.path.join(rr, "ai") + "/"), "%s: routing.md does not name %s/ai/" % (home, rr))
            self.check("$home: routing.md does not name the $other tree".replace("$home", home).replace("$other", other),
                       not contains(routing, self.path("explicit-both", other, "riskrails", "ai")),
                       "%s: routing.md names the %s tree" % (home, other))
            if os.path.exists(ai_path):
                proc = subprocess.run([ai_path, "--root", self.tmp, "policies/git.md"], cwd=self.tmp,
                                      capture_output=True, text=True, check=False)
                got = (proc.stdout + proc.stderr).rstrip("\n")
            else:
                got = "missing"
            self.check("$home: the installed resolver finds its own tree".replace("$home", home),
                       got == os.path.join(rr, "ai", "policies", "git.md"), "%s: installed resolver\n%s" % (home, got))
            self.check("$home: no temp tree left behind".replace("$home", home),
                       not any(re.match(r"^ai\.(new|old)$", n) for n in os.listdir(rr)), "%s: a temp tree was left behind" % home)

    def test_09_a_reinstall_backs_up_an_edited_tree(self):
        # A reinstall over a tree someone edited backs that tree up, then replaces it.
        c = self.path("explicit-both", "claude")
        with open(os.path.join(c, "riskrails", "ai", "policies", "git.md"), "a", encoding="utf-8") as fh:
            fh.write("local edit\n")
        self.stub()
        _, out = self.run_case("explicit-both", "--target", "both", "--plan", "pro")
        backup = os.path.join(c, "backups", time.strftime("%Y-%m-%d"), "riskrails", "ai", "policies", "git.md")
        self.check("reinstall backs up an edited shared tree", has(backup, re.compile(r"^local edit$", re.M)),
                   "no backup of the edited shared tree\n" + out)
        self.check("reinstall restores the shipped shared tree", same_tree(os.path.join(PLUGIN, "ai"), os.path.join(c, "riskrails", "ai")),
                   "reinstall left the edited tree")

    def test_10_an_unknown_target_is_rejected(self):
        self.stub("claude", "codex")
        rc, out = self.run_case("bad-target", "--target", "everything")
        self.check("--target everything is rejected", rc != 0, "unknown target should fail\n" + out)

    def test_11_dry_run_writes_nothing_for_either_runtime(self):
        self.stub("claude", "codex")
        _, out = self.run_case("dry", "--target", "both", "--plan", "max", "--fable", "yes", "--dry-run")
        self.check("the Claude tree is untouched", not wrote(self.path("dry", "claude")), "a dry run wrote to the Claude tree")
        self.check("the Codex tree is untouched", not wrote(self.path("dry", "codex")), "a dry run wrote to the Codex tree")
        self.check("the dry run has a Claude section", "== claude:" in out, "no Claude section\n" + out)
        self.check("the dry run has a Codex section", "== codex:" in out, "no Codex section\n" + out)
        self.check("every placeholder is rendered", "{{" not in out, "the dry run left an unrendered placeholder")


if __name__ == "__main__":
    unittest.main()
