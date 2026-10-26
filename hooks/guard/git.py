"""Port of hooks/ai-git-guard.sh: git and deployment safety, on Bash calls.

GLOBAL: not gated on .ai/. It refuses rewriting shared history, pushing to a
protected branch, staging a secret, bypassing hooks and running a production
deploy, in any repository. Rules match the command with prose removed; the
secret-staging rule reads the command itself, because a path is an argument.
"""
import re

from guard.common import (Deny, b_bytes, bytes_b, chomp_all, herestring_lines,
                          is_file, is_jq_string, load_json_file, read_lines,
                          runtime_hook_config, strip1, strip_prose, text_to_b)

LIST_KEYS = ("protected_branches", "deploy_patterns", "sensitive_staging_patterns",
             "allow_force_push_repos", "allow_protected_push_repos")

WHY_HISTORY = ("\n\nRewriting or force-pushing shared history destroys other people's work and cannot\n"
               "be undone from here. If this really is needed, a human does it after agreeing with\n"
               "whoever else has the branch checked out.")
WHY_PROTECTED = ("\n\nProtected branches change through a reviewed pull request, not through a push\n"
                 "from an agent session. Open a PR, or ask the human to run this push themselves.")
WHY_DEPLOY = ("\n\nProduction deployments are a human action with a human on the hook for the\n"
              "rollback. The pipeline ends at the release report and human approval; see\n"
              "policies/release.md.")

SPACE = "[[:space:]]"
CHEAP_RE = ("(^|[|;&[:space:]])(git|gh|argocd|helm|kubectl|terraform|dep|deployer|cap|flyctl|fly|"
            "vercel|netlify)([[:space:]]|$)")
ADD_RE = "(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]|$)"
WILD1_RE = ("(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]+-[^[:space:]]+)*[[:space:]]+"
            "(\\.|-A|--all|\\*)([[:space:]]|$)")
WILD2_RE = "(^|[|;&[:space:]])git[[:space:]]+(add|stage)[[:space:]]+(-A|--all)([[:space:]]|$)"
PUSH_RE = "(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)"
FORCE_RE = "(^|[[:space:]])(-f|--force|--force-with-lease(=[^[:space:]]*)?|--force-if-includes)([[:space:]]|$)"
DELETE1_RE = "(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*(--delete|-d)([[:space:]]|$)"
DELETE2_RE = "(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|[:space:]]+[[:space:]]+:[^[:space:]]+"
FILTER_BRANCH_RE = "(^|[|;&[:space:]])git[[:space:]]+filter-branch([[:space:]]|$)"
FILTER_REPO_RE = "(^|[|;&[:space:]])git-?filter-repo([[:space:]]|$)"
MIRROR_RE = "(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*--mirror([[:space:]]|$)"
REFSPEC_RE = (".*git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([[:space:]]+--?[a-z-]+(=[^[:space:]]+)?)*"
              "[[:space:]]+[^-][^[:space:];&|]*[[:space:]]+([^[:space:];&|]+).*")
MERGE_RE = "(^|[|;&[:space:]])git[[:space:]]+merge([[:space:]]|$)"
GH_MERGE_RE = "(^|[|;&[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)"
RESET_RE = "(^|[|;&[:space:]])git[[:space:]]+reset[[:space:]]+[^;&|]*--hard"
NO_VERIFY_RE = "(^|[|;&[:space:]])git[[:space:]]+[^;&|]*(--no-verify|-n[[:space:]]+--)"
COMMIT_PUSH_RE = "(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?(commit|push)([[:space:]]|$)"

_WORD_SPLIT = re.compile("[ \t\n]+")


def load_lists(path):
    """load_lists: each key's string elements, each followed by a newline, over
    every document of the file; a document jq cannot index adds nothing."""
    lists = dict.fromkeys(LIST_KEYS, "")
    if not is_file(path):
        return lists
    loaded = load_json_file(path)
    if loaded is None:
        return lists
    values, _ = loaded
    for doc in values:
        if doc is not None and not isinstance(doc, dict):
            continue                        # `$doc[.]` fails: nothing for this document
        for key in LIST_KEYS:
            v = doc.get(key) if doc else None
            items = v if isinstance(v, list) else list(v.values()) if isinstance(v, dict) else []
            lists[key] += "".join(text_to_b(x) + "\n" for x in items if is_jq_string(x))
    return lists


def basename(p):
    if p == "":
        return ""
    s = p.rstrip("/")
    return "/" if s == "" else s.rsplit("/", 1)[-1]


def git_out(cwd, *args):
    """(stdout bstr, ok) of `git -C cwd …` with stderr discarded."""
    import subprocess                       # pylint: disable=import-outside-toplevel  # most calls never get here
    try:
        r = subprocess.run(["git", "-C", b_bytes(cwd), *args], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, check=False)
    except OSError:
        return "", False
    return bytes_b(r.stdout), r.returncode == 0


class GitGuard:
    def __init__(self, ctx):
        self.ctx = ctx
        self.m = ctx.matcher
        self.cwd = ctx.payload.cwd
        self.cfg = self.dflt = None
        self.protected = ""
        self.branch = None

    def read_list(self, key):
        out = chomp_all(self.cfg[key])
        return out or chomp_all(self.dflt[key])

    def allowed_repo(self, key):
        out, ok = git_out(self.cwd, "rev-parse", "--show-toplevel")
        repo = basename(chomp_all(out if ok else self.cwd + "\n"))
        return any(name == repo for name in herestring_lines(strip1(self.cfg[key], "\n")))

    def current_branch(self):
        if self.branch is None:
            self.branch = chomp_all(git_out(self.cwd, "branch", "--show-current")[0])
        return self.branch

    def is_protected(self, branch):
        if not branch:
            return False
        return any(p and self.m.ere_match("^" + p + "$", branch) for p in herestring_lines(self.protected))

    def check(self):
        p, m = self.ctx.payload, self.m
        if p.tool != "Bash":
            return
        cmd = p.bash_command()
        if not cmd:
            return
        cmd_rules = strip_prose(cmd, self.ctx.loc)
        if not m.ere_match(CHEAP_RE, cmd_rules):
            return
        hook_dir = self.ctx.hook_dir
        defaults = hook_dir + "/ai-git-guard-defaults.json"
        config = runtime_hook_config("ai-git-guard.json", hook_dir) or defaults
        self.cfg = load_lists(config)
        self.dflt = self.cfg if config == defaults else load_lists(defaults)
        self.protected = self.read_list("protected_branches")
        deploys = self.read_list("deploy_patterns")
        sensitive = self.read_list("sensitive_staging_patterns")

        # 1. secrets in a commit
        if m.ere_match(ADD_RE, cmd):
            for token in _WORD_SPLIT.split(re.sub("[|;&()]", " ", cmd + "\n")):
                if token == "" or token.startswith("-") or token in ("git", "add", "stage", ".", "*"):
                    continue
                hit = m.matches_any(sensitive, token)
                if hit is not None:
                    raise Deny("Refusing to stage what looks like a secret: %s (matched: %s)\n\n"
                               "A credential committed once stays in the history even after it is deleted. Add\n"
                               "the path to .gitignore, or stage the files you meant one by one." % (token, hit))
            if m.ere_match(WILD1_RE, cmd) or m.ere_match(WILD2_RE, cmd):
                status = git_out(self.cwd, "status", "--porcelain", "--untracked-files=all")[0]
                for path in read_lines(status):
                    path = self._drop_status(path)
                    if " -> " in path:
                        path = path.rsplit(" -> ", 1)[1]
                    if not path:
                        continue
                    hit = m.matches_any(sensitive, path)
                    if hit is not None:
                        raise Deny("Refusing a wildcard 'git add': it would stage %s (matched: %s)\n\n"
                                   "Add that path to .gitignore first, or stage the files you meant "
                                   "explicitly." % (path, hit))

        # 2. force push
        if m.ere_match(PUSH_RE, cmd_rules) and m.ere_match(FORCE_RE, cmd_rules):
            if not self.allowed_repo("allow_force_push_repos"):
                raise Deny("Refusing a force push (--force and --force-with-lease alike)." + WHY_HISTORY)

        # 3. deleting a remote branch
        if m.ere_match(DELETE1_RE, cmd_rules) or m.ere_match(DELETE2_RE, cmd_rules):
            raise Deny("Refusing to delete a remote branch." + WHY_HISTORY)

        # 4. history rewriting
        if (m.ere_match(FILTER_BRANCH_RE, cmd_rules) or m.ere_match(FILTER_REPO_RE, cmd_rules)
                or m.ere_match(MIRROR_RE, cmd_rules)):
            raise Deny("Refusing to rewrite repository history (filter-branch / filter-repo / --mirror push)."
                       + WHY_HISTORY)

        # 5. protected branches
        if m.ere_match(PUSH_RE, cmd_rules):
            target = ""
            for line in herestring_lines(strip1(cmd_rules, "\n")):
                g = m.groups(REFSPEC_RE, line)
                if g is not None:
                    target = g[4]
                    break
            target = target.rsplit(":", 1)[-1]
            if target.startswith("refs/heads/"):
                target = target[len("refs/heads/"):]
            if target in ("HEAD", ""):
                target = self.current_branch()
            if self.is_protected(target) and not self.allowed_repo("allow_protected_push_repos"):
                raise Deny("Refusing to push directly to the protected branch '%s'.%s" % (target, WHY_PROTECTED))

        if m.ere_match(MERGE_RE, cmd_rules) and self.is_protected(self.current_branch()):
            raise Deny("Refusing to merge into '%s', which is a protected branch.%s"
                       % (self.current_branch(), WHY_PROTECTED))

        if m.ere_match(GH_MERGE_RE, cmd_rules):
            raise Deny("Refusing to merge a pull request. Merging is the reviewer's call, not the agent's."
                       + WHY_PROTECTED)

        if m.ere_match(RESET_RE, cmd_rules) and self.is_protected(self.current_branch()):
            raise Deny("Refusing 'git reset --hard' while '%s' is checked out.\n\n"
                       "A hard reset on a protected branch throws away commits and uncommitted work with\n"
                       "no way back. Check out a working branch first." % self.current_branch())

        # 6. bypassing hooks
        if m.ere_match(NO_VERIFY_RE, cmd_rules) and m.ere_match(COMMIT_PUSH_RE, cmd_rules):
            raise Deny("Refusing '--no-verify'.\n\n"
                       "The pre-commit and pre-push hooks are the project's own quality gate. If they\n"
                       "fail, the fix is the code, not the flag. If a hook is broken, say so and let a\n"
                       "human decide.")

        # 7. production deploys
        for pattern in herestring_lines(deploys):
            if pattern and m.ere_match(pattern, cmd_rules):
                raise Deny("Refusing to run a deployment or infrastructure-mutating command.\n\n"
                           "Matched pattern: %s%s" % (pattern, WHY_DEPLOY))

    def _drop_status(self, path):
        """`[ "${#path}" -lt 3 ] || path="${path:3}"`, counted in the locale's characters."""
        loc = self.ctx.loc
        if not loc.utf8:
            return path if len(path) < 3 else path[3:]
        u = b_bytes(path).decode("utf-8", "surrogateescape")
        return path if len(u) < 3 else u[3:].encode("utf-8", "surrogateescape").decode("latin-1")


def check(ctx):
    GitGuard(ctx).check()
