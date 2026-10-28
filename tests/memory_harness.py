"""Scratch projects for the compact-memory suites (tests/test_memory_*.py,
tests/test_task_id.py): a git repository with .ai/, a testing.md whose
commands read flag files outside the tree, and helpers that run state.py the
way an agent and a human do. Not a test module: discover skips it."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_TASK = os.path.join(ROOT, "skills", "ai-task")
STATE = os.path.join(AI_TASK, "state.py")
HOOK = os.path.join(ROOT, "hooks", "memory-pre-push.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "memory")
sys.path.insert(0, AI_TASK)

AGENT_MARKERS = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI", "CODEX_SANDBOX",
                 "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION")
ZERO = ["--declare", "behaviour=0:synthetic", "--declare", "domain=0:synthetic",
        "--declare", "novelty=0:synthetic"]
CLEAN = "FINDINGS\nnone\n"
FINDINGS = ("FINDINGS\n- [HIGH] H1 `src/widget.py:1` the cache key ignores the locale\nin_scope: yes\n"
            "- [LOW] L1 `src/widget.py:2` naming\nVERDICT pass_with_findings\n")
GIT_ID = ["-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]


def git(cwd, *args, check=True, env=None, stdin=None):
    done = subprocess.run(["git", *GIT_ID, *args], cwd=cwd, capture_output=True, text=True, check=False,
                          env=env, input=stdin)
    if check and done.returncode != 0:
        raise AssertionError("git %s: %s%s" % (" ".join(args), done.stdout, done.stderr))
    return done


def clean_env(extra=None, runtime="claude", human=False):
    env = {k: v for k, v in os.environ.items()
           if k not in AGENT_MARKERS and k not in ("AI_UNATTENDED", "AI_RUNTIME", "AI_HANDOFF_NO_PROMPT",
                                                    "AI_MEMORY_CRASH_AT", "AI_MEMORY_NO_FTS", "GIT_DIR",
                                                    "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    if runtime:
        env["AI_RUNTIME"] = runtime
    if human:
        env["AI_UNATTENDED"] = "1"
    env.update(extra or {})
    return env


class Project:
    """A scratch project: .ai/policies/testing.md, src/widget.py, its test, one commit."""

    def __init__(self, name="p", tmp=None, files=None, clone_of=None):
        self.own_tmp = tmp is None
        self.tmp = tmp or tempfile.mkdtemp(prefix="ai-memory-")
        self.root = os.path.join(self.tmp, name)
        self.flags = os.path.join(self.tmp, "flags-" + name)
        os.makedirs(self.flags, exist_ok=True)
        if clone_of:
            subprocess.run(["git", "clone", "-q", clone_of, self.root], check=True, capture_output=True)
            return
        os.makedirs(os.path.join(self.root, ".ai", "policies"))
        red = os.path.join(self.flags, "red")
        self.write(".ai/policies/testing.md",
                   "verify_command: sh -c 'test ! -e %s' {files}\nstep_test_command: sh -c 'test ! -e %s' "
                   "{files}\ne2e_command: test ! -e %s\n" % (red, os.path.join(self.flags, "stepred"),
                                                             os.path.join(self.flags, "e2ered")))
        self.write(".gitignore", ".ai/state/\n.ai/local/\n")
        base = {"src/widget.py": "x = 1\n", "tests/test_widget.py": "assert True\n"}
        base.update(files or {})
        for rel, text in base.items():
            self.write(rel, text)
        git(self.root, "init", "-q", "-b", "main")
        self.commit("init")

    def close(self):
        if self.own_tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)

    # -------------------------------------------------------------- files
    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text, mode="w"):
        path = self.path(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
            fh.write(text)

    def read(self, rel, binary=False):
        with open(self.path(rel), "rb" if binary else "r", encoding=None if binary else "utf-8") as fh:
            return fh.read()

    def exists(self, rel):
        return os.path.exists(self.path(rel))

    def flag(self, name, on=True):
        path = os.path.join(self.flags, name)
        if on:
            open(path, "w", encoding="utf-8").close()  # pylint: disable=consider-using-with
        elif os.path.exists(path):
            os.remove(path)

    def files_under(self, rel):
        base = self.path(rel)
        out = []
        for dirpath, _, names in os.walk(base):
            out += [os.path.relpath(os.path.join(dirpath, n), self.root) for n in names]
        return sorted(out)

    def tree_listing(self):
        """Every file in the working tree but .git, sorted."""
        out = []
        for dirpath, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d != ".git"]
            out += [os.path.relpath(os.path.join(dirpath, n), self.root) for n in names]
        return sorted(out)

    def memory_json(self, **overrides):
        policy = {"schema": 1, "mode": "packages", "period": "quarter", "package_max_bytes": 1048576,
                  "cleanup": False, "excerpt_max_bytes": 1024, "keep_rules": 1,
                  "recall": {"budget_tokens": 1500, "max_items": 40}}
        policy.update(overrides)
        self.write(".ai/policies/memory.json", json.dumps(policy, indent=2) + "\n")
        return policy

    def local_config(self, author="tester", index="none"):
        self.write(".ai/local/memory/config.json", json.dumps({"schema": 1, "author": author, "index": index}) + "\n")

    # -------------------------------------------------------------- git
    def git(self, *args, **kwargs):
        return git(self.root, *args, **kwargs)

    def commit(self, message="work"):
        self.git("add", "-A")
        self.git("commit", "-qm", message, "--allow-empty")
        return self.git("rev-parse", "HEAD").stdout.strip()

    # -------------------------------------------------------------- state.py
    def run(self, *args, human=False, runtime="claude", env=None, stdin=""):
        return subprocess.run([sys.executable, "-I", STATE, "--root", self.root] + list(args),
                              input=stdin, capture_output=True, text=True, check=False,
                              env=clean_env(env, runtime=runtime, human=human))

    def ok(self, *args, **kwargs):
        done = self.run(*args, **kwargs)
        assert done.returncode == 0, (args, done.returncode, done.stdout, done.stderr)
        return done

    def start(self, goal="tweak the widget", *extra,  # pylint: disable=keyword-arg-before-vararg
              files="src/widget.py,.ai/project/known-risks.md"):
        out = self.ok("start", "--goal", goal, "--workflow", "feature", "--files", files,
                      "--tests", "tests/test_widget.py", *ZERO, *extra).stdout
        return [line.split()[0] for line in out.splitlines() if " started: " in line][0]

    def state(self):
        with open(self.path(".ai/state/current.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def task_id(self):
        return self.state()["task_id"]

    def light_task(self, goal="tweak the widget", change="x = 2\n", env=None, extra=()):
        """start → edit → verify → close in light mode; returns (task_id, close stdout)."""
        task = self.start(goal, *extra)
        self.write("src/widget.py", change)
        self.ok("verify", "--scope", "all", env=env)
        return task, self.ok("close", env=env).stdout

    def rich_task(self, goal="a decided change", answer_text=None, env=None):
        """A full-mode task with a question, a review with findings, a scope
        change, a note and the human's approval; returns (task_id, close stdout)."""
        task = self.start(goal, "--mode", "full", "--by", "tester")
        self.ok("ask", "Which cache key?", "--option", "A: by locale", "--option", "B: by user",
                "--recommend", "A", "--context", "src/widget.py:1")
        if answer_text:
            self.ok("answer", "Q1=X:%s" % answer_text, "--by", "vanssa")
        else:
            self.ok("answer", "Q1=A", "--by", "vanssa")
        self.ok("start", "--amend", "--files", "+docs/widget.md", "--why", "the answer needs a doc line")
        self.ok("event", "note", "--data", json.dumps({"kind": "decision", "text": "keep the old key",
                                                        "why": "callers depend on it"}))
        self.write("src/widget.py", "x = 3\n")
        self.write("docs/widget.md", "widget\n")
        self.ok("verify", "--scope", "all", env=env)
        self.ok("review", "--verdict", "pass_with_findings", "--tier", "STRONG", "--report", "-",
                stdin=FINDINGS)
        self.ok("close", env=env)
        self.ok("approve", "--by", "vanssa", "--note", "looks right", human=True)
        return task, self.ok("close", env=env).stdout


def hook_run(repo, *args, stdin="", env=None):
    return subprocess.run([sys.executable, "-I", HOOK, *args], cwd=repo, input=stdin, capture_output=True,
                          text=True, check=False, env=clean_env(env))
