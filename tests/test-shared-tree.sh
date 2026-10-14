#!/usr/bin/env bash
# The shared tree: ai/ holds the policies, agent contracts, workflows and
# templates every project reads from the plugin (T-2026-10-13-004). safety.md
# and security.md stay project-owned (Q5=A), and no .json is shared: risk-tiers
# and path-guard are project policy.
#
# Since the cut-over (0006) a shared file lives only here: the scaffold no
# longer carries it, and 0006 retires the project copies.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

cd "$PLUGIN_ROOT" || exit 1
TPL="skills/ai-init/templates/.ai"

SHARED="agents/context.md
agents/discovery.md
agents/implementer.md
agents/manager.md
agents/planner.md
agents/release.md
agents/reviewer.md
agents/risk.md
agents/security.md
agents/tester.md
policies/context-management.md
policies/database.md
policies/git.md
policies/model-routing.md
policies/production.md
policies/release.md
policies/review-economy.md
policies/tooling.md
templates/architecture-decision.md
templates/impact-report.md
templates/implementation-plan.md
templates/release-report.md
templates/review-report.md
templates/task-context.md
workflows/bugfix.md
workflows/feature.md
workflows/hotfix.md
workflows/investigation.md
workflows/refactoring.md"

echo "== the shared file set"
[ "$(printf '%s\n' "$SHARED" | wc -l)" -eq 29 ] && pass "the literal list names 29 files" || fail "the literal list is not 29 files"
actual=$(cd ai && find . -type f | sed 's|^\./||' | LC_ALL=C sort)
[ "$actual" = "$(printf '%s\n' "$SHARED" | LC_ALL=C sort)" ] && pass "ai/ holds exactly the 29 shared files" \
    || fail "ai/ differs from the shared list" "$(diff <(printf '%s\n' "$SHARED" | LC_ALL=C sort) <(printf '%s\n' "$actual"))"
for f in policies/safety.md policies/security.md; do
    [ ! -e "ai/$f" ] && pass "$f stays project-owned" || fail "$f must not be shared"
done
[ -z "$(find ai -name '*.json')" ] && pass "no .json is shared" || fail "a .json file is in ai/"

echo "== one home per file: the shared tree, not the scaffold"
both=""
while IFS= read -r f; do [ -e "$TPL/$f" ] && both="$both $f"; done <<< "$SHARED"
[ -z "$both" ] && pass "no shared path is also a scaffold template" || fail "a path is in both trees:" "$both"
for f in policies/safety.md policies/security.md; do
    [ -f "$TPL/$f" ] && pass "$f is still scaffolded" || fail "$f must stay in the scaffold"
done
mig=$(python3 -I -c 'import importlib.util, sys
spec = importlib.util.spec_from_file_location("m6", sys.argv[1]); m = importlib.util.module_from_spec(spec)
sys.path.insert(0, sys.argv[2]); spec.loader.exec_module(m)
print("\n".join(sorted(p[len(".ai/"):] for p in m.SHARED)))' \
    skills/project-update/migrations/0006_shared_files.py skills/project-update 2>&1)
[ "$mig" = "$(printf '%s\n' "$SHARED" | LC_ALL=C sort)" ] && pass "0006.SHARED equals the shared tree (M1)" \
    || fail "0006.SHARED differs from ai/" "$(diff <(printf '%s\n' "$SHARED" | LC_ALL=C sort) <(printf '%s\n' "$mig"))"

echo "== the resolver: scripts/ai-path"
RES="$PLUGIN_ROOT/scripts/ai-path"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/proj/.ai/policies" "$W/proj/src/deep" "$W/none" "$W/proj/.ai/workflows/feature.md"
printf 'override\n' > "$W/proj/.ai/policies/git.md"
resolve() { (cd "$1" && shift && "$RES" "$@"); }
out=$(resolve "$W/proj" policies/git.md); [ "$out" = "$W/proj/.ai/policies/git.md" ] && pass "a project file overrides the shared one" || fail "override" "$out"
out=$(resolve "$W/proj" .ai/policies/git.md); [ "$out" = "$W/proj/.ai/policies/git.md" ] && pass "a leading .ai/ is stripped" || fail "leading .ai/" "$out"
out=$(resolve "$W/proj" policies/tooling.md); [ "$out" = "$PLUGIN_ROOT/ai/policies/tooling.md" ] && pass "without a project copy the shared file is printed" || fail "fallback" "$out"
out=$(resolve "$W/proj/src/deep" policies/git.md); [ "$out" = "$W/proj/.ai/policies/git.md" ] && pass "from a subdirectory the project override is found" || fail "upward search" "$out"
out=$(resolve "$W/proj" workflows/feature.md); [ "$out" = "$PLUGIN_ROOT/ai/workflows/feature.md" ] && pass "a directory at the path is not an override" || fail "directory as override" "$out"
out=$(resolve "$W/none" --root "$W/proj" policies/git.md); [ "$out" = "$W/proj/.ai/policies/git.md" ] && pass "--root names the project" || fail "--root" "$out"
out=$(resolve "$W/proj" policies/nothing.md 2>/dev/null); rc=$?
[ $rc -eq 1 ] && [ -z "$out" ] && pass "a missing file exits 1, nothing on stdout" || fail "missing file: rc=$rc" "$out"
out=$(resolve "$W/none" policies/git.md 2>/dev/null); rc=$?
[ $rc -eq 1 ] && [ -z "$out" ] && pass "no project exits 1, nothing on stdout" || fail "no project: rc=$rc" "$out"
resolve "$W/proj" ../etc/passwd >/dev/null 2>&1; rc=$?; [ $rc -eq 2 ] && pass "a .. component exits 2" || fail "traversal: rc=$rc"
resolve "$W/proj" policies/../../x >/dev/null 2>&1; rc=$?; [ $rc -eq 2 ] && pass "an inner .. component exits 2" || fail "inner traversal: rc=$rc"
resolve "$W/proj" /etc/passwd >/dev/null 2>&1; rc=$?; [ $rc -eq 2 ] && pass "an absolute path exits 2" || fail "absolute: rc=$rc"

echo "== the resolver in the installed layout"
mkdir -p "$W/home/claude-agentic"; cp -r ai "$W/home/claude-agentic/ai"; cp "$RES" "$W/home/claude-agentic/ai-path"
out=$(cd "$W/proj" && "$W/home/claude-agentic/ai-path" policies/tooling.md 2>&1)
[ "$out" = "$W/home/claude-agentic/ai/policies/tooling.md" ] && pass "installed: the tree beside the script is used" || fail "installed layout" "$out"
out=$(cd "$W/proj" && CLAUDE_AGENTIC_SHARED="$PLUGIN_ROOT/ai" "$W/home/claude-agentic/ai-path" policies/tooling.md 2>&1)
[ "$out" = "$PLUGIN_ROOT/ai/policies/tooling.md" ] && pass "CLAUDE_AGENTIC_SHARED outranks the installed tree" || fail "env override" "$out"

echo "== --tree-hash"
h1=$("$W/home/claude-agentic/ai-path" --tree-hash); h2=$("$W/home/claude-agentic/ai-path" --tree-hash)
[ -n "$h1" ] && [ "$h1" = "$h2" ] && pass "the tree hash is stable" || fail "tree hash unstable" "$h1 / $h2"
[ "$h1" = "$("$RES" --tree-hash)" ] && pass "an equal tree has an equal hash" || fail "copy hashes differently"
printf 'x' >> "$W/home/claude-agentic/ai/policies/git.md"
[ "$h1" != "$("$W/home/claude-agentic/ai-path" --tree-hash)" ] && pass "a one-byte edit changes the hash" || fail "hash ignored a one-byte edit"

echo "== update.py helpers for the cut-over"
# Python prints "ok <what>" or "FAIL <what> | <detail>"; each line becomes one assertion.
helpers=$(HOME="$W/h" CODEX_HOME= CLAUDE_AGENTIC_SHARED="$PLUGIN_ROOT/ai" PLUGIN_ROOT="$PLUGIN_ROOT" W="$W" \
    python3 -I - <<'PY' 2>&1
import os, shutil, sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import update as U
from migrations import SchemaError
W = os.environ["W"]

def check(ok, what, detail=""):
    print(("ok %s" % what) if ok else ("FAIL %s | %s" % (what, detail)))

mod = types.SimpleNamespace(VERSION=6, MOVES=[])
def ctx(root, history=None):
    return U.MigrationContext(U.Plan(root), mod, 5, None, history or U.History(U.HISTORY))

proj = os.path.join(W, "uproj"); os.makedirs(os.path.join(proj, ".ai"))
open(os.path.join(proj, "AGENTS.md"), "w").close()  # declares codex
open(os.path.join(proj, "CLAUDE.md"), "w").close()  # and claude
c = ctx(proj)
P = ".ai/workflows/feature.md"
cur = c.template(P)
check(cur == open(os.path.join(os.environ["PLUGIN_ROOT"], "ai", "workflows", "feature.md"), "rb").read(),
      "template() returns the shipped bytes")
try:
    c.template(".ai/workflows/nothing.md"); check(False, "template() of an unknown path raises")
except SchemaError:
    check(True, "template() of an unknown path raises")

# Shared keys keep their hashes, not their blobs: the old bytes are a fixture.
old = open(os.path.join(os.environ["PLUGIN_ROOT"], "tests", "fixtures", "project-update", "shared-old",
                        "workflows", "feature.md"), "rb").read()
check(old != cur, "the fixture holds an older feature.md", "oldest equals current")
check(c.history.versions("ai-init/" + P) == [], "a shared key ships no blob")
check(c.is_shipped(P, cur), "the current bytes are shipped")
check(c.is_shipped(P, old), "an older shipped version is shipped")
check(not c.is_shipped(P, cur + b"x"), "an edited copy is not shipped")
check(c.is_shipped(P, cur.replace(b"\n", b"\r\n")), "a CRLF checkout of a shipped version is shipped")
check(not c.is_shipped(".ai/project/notes.md", cur), "a path the plugin never shipped is not shipped")

bare = os.path.join(W, "history-noblobs"); os.makedirs(bare)
shutil.copy(os.path.join(U.HISTORY, "index.json"), bare)
h = U.History(bare)
check(h.versions("ai-init/" + P) == [], "the bare history has no blobs")
check(U.sha(old) in h.hashes("ai-init/" + P), "hashes() answers from index.json alone")
check(ctx(proj, h).is_shipped(P, old), "is_shipped needs no blob")

files = U.shared_files()
check(len(files) == 29 and files.get(P) == cur, "shared_files() maps the 29 to .ai/<rel>", len(files))

paths = sorted(files)
def refused():
    try:
        ctx(proj).require_shared(paths); return None
    except SchemaError as exc:
        return str(exc)
check(refused() is None, "require_shared: no other home on this machine is not checked")
codex = os.path.join(W, "h", ".codex"); os.makedirs(os.path.join(codex, "skills", "project-update"))
msg = refused()
check(msg is not None and codex in msg and "--target codex" in msg,
      "require_shared: a codex home with the plugin but no tree refuses", msg)
tree = os.path.join(codex, "claude-agentic", "ai")
shutil.copytree(U.SHARED, tree)
os.remove(os.path.join(tree, "policies", "git.md")); os.remove(os.path.join(tree, "agents", "risk.md"))
msg = refused()
check(msg is not None and " 2 of the 29 " in msg, "require_shared: a partial tree refuses with the count", msg)
shutil.rmtree(tree); shutil.copytree(U.SHARED, tree)
check(refused() is None, "require_shared: a full tree in every installed home passes")
saved = U.SHARED
U.SHARED = os.path.join(W, "local-shared"); shutil.copytree(saved, U.SHARED)
os.remove(os.path.join(U.SHARED, "templates", "review-report.md"))
msg = refused()
check(msg is not None and "templates/review-report.md" in msg, "require_shared: the local tree names the missing file", msg)
U.SHARED = saved

outside = os.path.join(W, "outside"); os.makedirs(outside)
open(os.path.join(outside, "feature.md"), "w").close()
os.symlink(outside, os.path.join(proj, ".ai", "workflows"))
os.makedirs(os.path.join(proj, ".ai", "policies"))
open(os.path.join(proj, ".ai", "policies", "real.md"), "w").close()
os.symlink("real.md", os.path.join(proj, ".ai", "policies", "git.md"))
c = ctx(proj)
why = c.unsafe_target(P)
check(why is not None and "symlink" in why, "unsafe_target: a file under a symlinked directory", why)
why = c.unsafe_target(".ai/policies/git.md")
check(why is not None and "symlink" in why, "unsafe_target: a symlinked file", why)
check(c.unsafe_target(".ai/policies/real.md") is None, "unsafe_target: a regular file is safe")
note = c.override_note(".ai/policies/git.md")
check("no longer receives its changes" in note and os.path.join(U.SHARED, "policies", "git.md") in note,
      "override_note names the shared copy", note)

repo = os.path.join(W, "repo"); os.makedirs(os.path.join(repo, ".ai"))
check(not U.git_dirty_ai(repo), "git_dirty_ai: outside a work tree is False")
import subprocess
subprocess.run(["git", "init", "-q", repo], check=True)
check(not U.git_dirty_ai(repo), "git_dirty_ai: an empty .ai/ is clean")
open(os.path.join(repo, ".ai", "x.md"), "w").close()
check(U.git_dirty_ai(repo), "git_dirty_ai: an untracked .ai/ file is dirty")
PY
)
while IFS= read -r line; do
    case "$line" in
        "ok "*) pass "${line#ok }" ;;
        "FAIL "*) fail "${line#FAIL }" ;;
        *) [ -n "$line" ] && fail "helper check crashed" "$line" ;;
    esac
done <<< "$helpers"

echo "== adopt rows land in the routing table of a scaffolded router"
mkdir -p "$W/scaf" && bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$W/scaf" >/dev/null 2>&1
rows=$(PLUGIN_ROOT="$PLUGIN_ROOT" W="$W" python3 -I - <<'PY' 2>&1
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import adopt, update as U
plan = U.Plan(os.path.join(os.environ["W"], "scaf"))
row = "| a tool the project adopted | `policies/adopted/x.md` |"
print(adopt.add_router_rows(plan, [row]))
lines = plan.items[-1]["content"].decode().split("\n") if plan.items else []
i = lines.index(row) if row in lines else -1
print(i > 0 and lines[i - 1].startswith("|") and "## Shared files" in lines and lines.index("## Shared files") < i)
PY
)
[ "$rows" = "$(printf '1\nTrue')" ] && pass "add_router_rows appends after the routing table, below the Shared files section" \
    || fail "add_router_rows on the new router" "$rows"

echo "== consumers name the rule"
for a in ai-context ai-discovery ai-expert ai-implementer ai-planner ai-release ai-reviewer ai-risk ai-security ai-tester; do
    [ "$(grep -c '{{AI_SHARED}}/<path>' "agents/$a.md.tmpl")" -eq 1 ] && pass "agents/$a.md.tmpl states the rule once" || fail "agents/$a.md.tmpl should state the shared-path rule once"
done
grep -qF '"$AI_HOME/claude-agentic/ai-path" <path>' skills/ai-task/SKILL.md && pass "ai-task names the resolver" || fail "ai-task SKILL.md should name the resolver"
grep -q '^### ADVERSARIAL REVIEW' skills/ai-task/SKILL.md && pass "ai-task keeps ADVERSARIAL REVIEW" || fail "ADVERSARIAL REVIEW is gone from ai-task"

summary "shared-tree"
