#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
install.sh: rendering must be complete and correct for every plan/fable
combination, and a real install into a scratch CLAUDE_DIR must be idempotent.
Stdlib only; the installer runs through install_harness.install().

The sections share scratch directories and sequential installs, in the shell
suite's order: test_NN_ names keep it.
"""
import datetime
import glob
import json
import os
import re
import stat
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, env_with, install, read, write  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-install-dry-run.sh"

RETIRED_24 = "ai-context ai-expert ai-implementer ai-indexer ai-planner ai-release ai-risk ai-security ai-tester".split()
STALE = "code-implementer qa-runner qa-fixer db-migrator doc-lookup log-inspector sylius-i18n-keys".split()


def run(*args, stdin=None, merge=True, **env):
    """The installer with the overrides in env (None removes a variable)."""
    return install(*args, env=env_with(**env), stdin=stdin, merge=merge)


def sed_range(text, start, end):
    """Lines of `sed -n '/start/,/end/p'`: the end is looked for from the line after the start."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    res, inside = [], False
    for line in lines:
        if not inside:
            if re.search(start, line):
                res.append(line)
                inside = True
        else:
            res.append(line)
            if re.search(end, line):
                inside = False
    return res


def snippet(out):
    return sed_range(out, r"^== settings snippet", r"^== agents")


def has_line(text, regex):
    return re.search(regex, text, re.M) is not None


def line_eq(text, line):
    return line in text.split("\n")


def rd(path):
    try:
        return read(path)
    except OSError:
        return ""


def jload(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def jv(obj, *keys):
    """jq's .a.b[0]: None where a step is missing."""
    for key in keys:
        try:
            obj = obj[key]
        except (KeyError, IndexError, TypeError):
            return None
    return obj


def jr(value):
    """jq -r of a value."""
    return value if isinstance(value, str) else json.dumps(value)


def cmds(settings, event):
    """[.hooks[event][]?.hooks[]?.command]"""
    out = []
    for entry in jv(settings, "hooks", event) or []:
        for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
            out.append(hook.get("command"))
    return out


def count_ctx(settings, event):
    return len([c for c in cmds(settings, event) if isinstance(c, str) and re.search("context-guard", c)])


def agent_frontmatter(path):
    """The shell's awk: name, model ('-' when none) and effort of an agent's frontmatter."""
    model = effort = ""
    with open(path, encoding="utf-8") as fh:
        for nr, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if nr > 1 and line == "---":
                break
            fields = line.split()
            if line.startswith("model:"):
                model = fields[1] if len(fields) > 1 else ""
            if line.startswith("effort:"):
                effort = fields[1] if len(fields) > 1 else ""
    return "%s %s %s" % (os.path.basename(path)[:-3], model or "-", effort)


def is_x(path):
    return os.access(path, os.X_OK)


class InstallDryRun(ScratchCase):

    def ok(self, label, cond, detail="", subs=None):
        text = label
        for key, value in (subs or {}).items():
            text = text.replace(key, value)
        with self.subTest(text):
            self.assertTrue(cond, detail or text)

    def none(self):
        return self.path("none")

    def home_t(self):
        os.makedirs(self.path("home-team"), exist_ok=True)
        return self.path("home-team")

    def dry(self, *args, merge=True, **env):
        env.setdefault("CLAUDE_DIR", self.none())
        return run(*args, "--dry-run", merge=merge, **env)

    # == dry run renders for every plan
    def test_01_dry_run_renders_for_every_plan(self):
        for plan, fable, effort, model in [("max", "yes", "xhigh", "fable[1m]"),
                                           ("max", "no", "high", "Opus 5.5 [1m] by default"),
                                           ("pro", "no", "high", "Opus 5"),
                                           ("team-max", "yes", "xhigh", "fable[1m]"),
                                           ("team-max", "no", "high", "Opus 5.5 [1m] by default"),
                                           ("team-pro", "no", "high", "Opus 5")]:
            rc, out = self.dry("--target", "claude", "--plan", plan, "--fable", fable)
            subs = {"$1": plan, "$2": fable, "$effort": effort, "$model": model}
            self.ok("--plan $1 --fable $2 exits 0", rc == 0, out, subs)
            self.ok("--plan $1 --fable $2 renders every placeholder", "{{" not in out, out, subs)
            self.ok("--plan $1 --fable $2 renders architect effort $effort", "effort: " + effort in out, out, subs)
            self.ok("--plan $1 --fable $2 names $model", model in out, out, subs)
            self.ok("--plan $1 --fable $2 writes nothing", "nothing written" in out, out, subs)
        rc, out = self.dry("--plan", "max", "--fable", "no")
        self.ok("--fable no drops fable from the settings", '"fable' not in "\n".join(snippet(out)), out)

    # == dry run: the shared tree
    def test_02_dry_run_the_shared_tree(self):
        for target in ("claude", "codex"):
            subs = {"$target": target}
            rc, out = self.dry("--target", target, "--plan", "max", "--codex-plan", "plus",
                               HOME=self.path("h-" + target), CODEX_DIR=self.path("none-x"))
            n = len([ln for ln in out.split("\n") if ln == "   shared:  riskrails/ai (31 files), riskrails/ai-path"])
            self.ok("$target: the would-install list names the shared tree once", n == 1, "shared line count %d\n%s" % (n, out), subs)
            skills = "\n".join(re.findall(r"^   skills:  (.*)$", out, re.M))
            missing = [s for s in "rr-setup rr-spec rr-plan rr-build rr-review rr-ship rr-status".split()
                       if not re.search(r"(^|,)%s(,|$)" % s, skills, re.M)]
            self.ok("$target: the would-install list names the seven rr- skills and no bare status",
                    not missing and not re.search(r"(^|,)status(,|$)", skills, re.M),
                    "missing:%s - %s" % (missing, skills), subs)
            self.ok("$target: the dry run names the retire of skills/status",
                    has_line(out, r"^   retire:  skills/status \(now skills/rr-status\)"), out, subs)
            span = "\n".join(sed_range(out, r"^== (CLAUDE|AGENTS)\.md managed block:", r"^== profile\.json"))
            self.ok("$target: the shared line is outside the block/routing span", not has_line(span, r"^   shared:"), span, subs)
            self.ok("$target: routing.md renders the shared-files line", "riskrails/ai-path <path>" in span, span, subs)
            self.ok("$target: every placeholder is rendered", "{{" not in out, out, subs)

    # == pro: opusplan session, EXPERT tier pinned to opus
    def test_03_pro_opusplan_session(self):
        rc, out = self.dry("--plan", "pro")
        self.ok("pro sets the session model to opusplan", '"model": "opusplan"' in out, out)
        self.ok("pro names opusplan in the CLAUDE.md block", "Opus 5 in plan mode" in out, out)
        self.ok("pro pins model: opus on architect, the EXPERT agent", has_line(out, r"^model: opus"), out)
        self.ok("the block routes every change through /rr-build", "/rr-build <request>" in out, out)
        rc, out = self.dry("--plan", "max", "--fable", "yes")
        self.ok("max+fable pins fable[1m] on architect", line_eq(out, "model: fable[1m]"), out)
        self.ok("max renders the EXPERT tier at xhigh", line_eq(out, "effort: xhigh"), out)

    # == team-pro and team-max share the pro and max profiles
    def test_04_team_profiles(self):
        rc, out = self.dry("--plan", "team-pro")
        self.ok("team-pro uses the pro profile", "plan=team-pro (Team Pro, pro profile)" in out, out)
        self.ok("team-pro sets the session model to opusplan", '"model": "opusplan"' in out, out)
        self.ok("team-pro pins model: opus on the EXPERT agents", has_line(out, r"^model: opus"), out)
        self.ok("team-pro is named in the CLAUDE.md block", "Model routing (Team Pro plan)" in out, out)
        rc, out = self.dry("--plan", "team-pro", "--fable", "yes")
        self.ok("team-pro forces --fable no", "fable=no" in out, out)
        rc, out = self.dry("--plan", "team-max")
        self.ok("team-max uses the max profile with Fable and the gate",
                "plan=team-max (Team Max, max profile) fable=yes fable-gate=on" in out, out)
        self.ok("team-max pins fable[1m] on architect", has_line(out, r"^model: fable\[1m\]"), out)
        self.ok("team-max is named in the CLAUDE.md block", "Model routing (Team Max plan)" in out, out)
        rc, out = self.dry("--plan", "team-premium")
        self.ok("team-premium is an alias of team-max", "plan=team-max" in out, out)
        rc, out = self.dry("--plan", "team-standard")
        self.ok("team-standard is an alias of team-pro", "plan=team-pro" in out, out)

    # == plan detection reads the seat of a Team org
    def test_05_plan_detection_reads_the_seat(self):
        home = self.home_t()
        claude_json = os.path.join(home, ".claude.json")

        def detect(account):
            write(claude_json, account)
            return self.dry(HOME=home)[1]

        out = detect('{"oauthAccount":{"organizationType":"claude_team"}}')
        self.ok("claude_team with no seat falls back to team-pro", "plan=team-pro" in out, out)
        self.ok("the fallback says how to pick team-max", "--plan team-max" in out, out)
        out = detect('{"oauthAccount":{"organizationType":"claude_team","seatTier":"standard"}}')
        self.ok("a standard seat is detected as team-pro", "detected plan: team-pro" in out, out)
        out = detect('{"oauthAccount":{"organizationType":"claude_team","seatTier":"premium"}}')
        self.ok("a premium seat is detected as team-max", "detected plan: team-max" in out, out)
        out = detect('{"oauthAccount":{"organizationType":"claude_team","organizationRateLimitTier":"default_claude_max_5x"}}')
        self.ok("a max rate-limit tier is detected as team-max", "detected plan: team-max" in out, out)
        out = detect('{"oauthAccount":{"organizationType":"claude_max"}}')
        self.ok("claude_max is still detected as max", "plan=max (Max" in out, out)

    # == balanced-max: only the session is strong
    def test_06_balanced_max(self):
        rc, outb = self.dry("--target", "both", "--plan", "balanced-max", CODEX_DIR=self.path("nonecx"))
        self.ok("--plan balanced-max: BalancedMax on the max profile, Fable off",
                "plan=balanced-max (BalancedMax, max profile) fable=no" in outb, outb)
        self.ok("balanced-max pins the session to Opus 5.5", '"model": "claude-opus-5-5"' in outb, outb)
        self.ok("balanced-max offers no Fable", "fable[1m]" not in outb, outb)
        self.ok("balanced-max renders no xhigh", not line_eq(outb, "effort: xhigh"), outb)
        self.ok("--plan balanced-max selects the Codex balanced-max profile", "== codex: plan=balanced-max" in outb, outb)
        self.ok("Codex readers run on Luna", "| FAST | `gpt-5.6-luna`" in outb, outb)
        rc, o = self.dry("--target", "claude", "--plan", "balanced-max", "--fable", "yes")
        self.ok("--fable yes is refused on balanced-max", "fable=no" in o, o)

    # == max20: Max 20x, detected from organizationRateLimitTier (R3)
    def test_07_max20(self):
        home = self.home_t()
        claude_json = os.path.join(home, ".claude.json")
        rc, out20 = self.dry("--target", "claude", "--plan", "max20")
        rc, outmax = self.dry("--target", "claude", "--plan", "max")
        self.ok("--plan max20 is Max 20x on the max profile", "plan=max20 (Max 20x, max profile) fable=yes" in out20, out20)
        self.ok("max20's settings snippet equals max's",
                "\n".join(snippet(out20)).rstrip("\n") == "\n".join(snippet(outmax)).rstrip("\n"), "max20 snippet differs from max")
        for plan in ("pro", "team-pro", "team-max", "max", "max20"):
            subs = {"$plan": plan}
            rc, o = self.dry("--target", "claude", "--plan", plan)
            try:
                snip = json.loads("\n".join(snippet(o)[1:-1]))
                leaked = "riskrails" in snip
            except ValueError:
                leaked = True
            self.ok("$plan: riskrails never reaches settings.json", not leaked, "riskrails leaked into the snippet", subs)
            self.ok("$plan: --dry-run lists profile.json",
                    has_line(o, "^" + re.escape("== profile.json (plan tables): %s/riskrails/profile.json" % self.none())),
                    "profile.json not listed", subs)
        try:
            prof = json.loads("\n".join(sed_range(out20, r"^== profile.json", r"^== would install")[1:-1]))
            good = (prof.get("plan") == "max20" and prof.get("label") == "Max 20x" and prof.get("runtime") == "claude"
                    and prof.get("fable") is True and jv(prof, "budgets", "expert", "max_per_task") == 2
                    and "fan_out" not in prof["budgets"] and len(prof["plugin_version"]) > 0 and len(prof["written_at"]) > 0)
        except (ValueError, KeyError, TypeError):
            good = False
        self.ok("max20 profile.json carries plan, runtime, fable and the max20 budgets", good, "max20 profile.json content")
        write(claude_json, '{"oauthAccount":{"organizationType":"claude_max","organizationRateLimitTier":"default_claude_max_20x"}}')
        rc, out = self.dry(HOME=home)
        self.ok("default_claude_max_20x is detected as max20", "plan=max20 (Max 20x" in out, out)
        rc, o, err = self.dry(HOME=home, merge=False)
        self.ok("without a terminal the detection is printed on stderr",
                "detected plan: max20 (organizationRateLimitTier default_claude_max_20x)" in err, err)
        write(claude_json, '{"oauthAccount":{"organizationType":"claude_max","organizationRateLimitTier":"default_claude_max_5x"}}')
        rc, out = self.dry(HOME=home)
        self.ok("default_claude_max_5x stays max", "plan=max (Max" in out, out)
        # An install from before 3.4b recorded its plan under claude-agentic/ (R35).
        prev = self.path("prev")
        write(os.path.join(prev, "claude-agentic", "profile.json"), '{"plan":"max20"}')
        write(claude_json, "{}")
        rc, out = self.dry(HOME=home, CLAUDE_DIR=prev)
        self.ok("an undetectable account falls back to the plan the last install recorded", "plan=max20" in out, out)

    # == R16/R18: every installed agent's model and effort, per plan
    def test_08_agent_model_and_effort_per_plan(self):
        # The four tier agents are the same on every plan; only architect differs.
        # A change here is a model or effort change, which R18 forbids.
        common = ["ai-discovery sonnet low", "ai-reviewer opus high", "Explore haiku low", "log-reader haiku low"]
        for plan, fable, architect in [("pro", "no", "architect opus high"),
                                       ("team-pro", "no", "architect opus high"),
                                       ("max", "yes", "architect fable[1m] xhigh"),
                                       ("max", "no", "architect - high"),
                                       ("team-max", "yes", "architect fable[1m] xhigh"),
                                       ("team-max", "no", "architect - high"),
                                       ("max20", "yes", "architect fable[1m] xhigh")]:
            subs = {"$1": plan, "$2": fable}
            d = self.path("fm-%s-%s" % (plan, fable))
            os.makedirs(d, exist_ok=True)
            run("--target", "claude", "--plan", plan, "--fable", fable, CLAUDE_DIR=d)
            got = sorted(agent_frontmatter(f) for f in glob.glob(os.path.join(d, "agents", "*.md")))
            want = sorted(common + [architect])
            self.ok("--plan $1 --fable $2: all 5 agents keep their model and effort", got == want,
                    "agent frontmatter changed: want %s got %s" % (want, got), subs)
            prof = jload(os.path.join(d, "riskrails", "profile.json"))
            bad = []
            for tmpl in sorted(glob.glob(os.path.join(PLUGIN, "agents", "*.md.tmpl"))):
                m = re.search(r"^model: \{\{([A-Z]*)_MODEL\}\}$", read(tmpl), re.M)
                if not m or not m.group(1):
                    continue
                name = os.path.basename(tmpl)[:-len(".md.tmpl")]
                want_m = jr(jv(prof, "tiers", m.group(1), "model"))
                if "model: " + want_m not in rd(os.path.join(d, "agents", name + ".md")).split("\n"):
                    bad.append(name)
            self.ok("--plan $1: each installed model is the profile's tiers[<tier>].model", not bad,
                    "model differs from its tier: %s" % bad, subs)
            left = [f for f in glob.glob(os.path.join(d, "agents", "**"), recursive=True)
                    if os.path.isfile(f) and "{{" in read(f)]
            self.ok("--plan $1: no placeholder left in any agent", not left,
                    "an installed agent has an unrendered placeholder: %s" % left, subs)

    # == dry run writes nothing at all
    def test_09_dry_run_writes_nothing(self):
        probe = self.path("probe")
        os.makedirs(probe, exist_ok=True)
        run("--plan", "max", "--dry-run", CLAUDE_DIR=probe)
        self.ok("the target directory is untouched", not os.listdir(probe), "dry run created files: %s" % os.listdir(probe))

    # == bad arguments are rejected
    def test_10_bad_arguments_are_rejected(self):
        probe = self.path("probe")
        os.makedirs(probe, exist_ok=True)
        rc, out = run("--plan", "enterprise", "--dry-run", CLAUDE_DIR=probe)
        self.ok("an unknown plan is rejected", rc != 0, out)
        rc, out = run("--plan", "max", "--fable", "maybe", "--dry-run", CLAUDE_DIR=probe)
        self.ok("an unknown --fable value is rejected", rc != 0, out)

    # == real install into a scratch CLAUDE_DIR
    def test_11_real_install(self):
        d = self.path("claude")
        os.makedirs(d, exist_ok=True)
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("install exits 0", rc == 0, out)
        prof = jload(os.path.join(d, "riskrails", "profile.json"))
        self.ok("profile.json written for the Claude install (R4)",
                prof.get("plan") == "max" and prof.get("runtime") == "claude" and prof.get("fable") is True,
                "profile.json missing or wrong")
        try:
            mode = stat.S_IMODE(os.stat(os.path.join(d, "riskrails", "profile.json")).st_mode)
        except OSError:
            mode = None
        self.ok("profile.json is mode 0644", mode == 0o644, "profile.json mode")
        self.ok("settings.json has no riskrails", "riskrails" not in jload(os.path.join(d, "settings.json")),
                "riskrails leaked into settings.json")
        for f in ["agents/ai-discovery.md", "agents/ai-reviewer.md", "agents/architect.md", "agents/Explore.md",
                  "agents/log-reader.md", "hooks/lib/ai-hook-common.sh",
                  "hooks/cap-large-read.py", "hooks/project-scaffold.sh", "hooks/ai-git-guard.json",
                  "skills/ai-init/SKILL.md", "skills/ai-init/scaffold-ai.sh", "skills/ai-task/state.py",
                  "skills/ai-audit/SKILL.md", "skills/ai-status/SKILL.md", "skills/project-init/SKILL.md",
                  "skills/rr-status/SKILL.md", "skills/rr-status/status.py",
                  "skills/sdlc-intent/SKILL.md", "skills/sdlc-spec/SKILL.md", "skills/sdlc-plan/SKILL.md",
                  "skills/ai-init/templates/.ai/AGENTS.md", "skills/project-init/templates/intent.md",
                  "skills/project-update/SKILL.md", "skills/project-update/update.py", "skills/project-update/history/index.json",
                  "skills/project-update/migrations/__init__.py", "skills/project-update/migrations/0001_schema_version.py",
                  "skills/usage-report/SKILL.md", "skills/usage-report/usage-report.py",
                  "hooks/context-guard.py", "riskrails/routing.md", "riskrails/ai-path",
                  "riskrails/ai/policies/git.md", "riskrails/ai/workflows/feature.md",
                  "skills/project-update/render_instructions.py",
                  "hooks/ai-guard.py", "hooks/guard/__init__.py", "hooks/guard/common.py", "hooks/guard/ere.py",
                  "hooks/guard/git.py", "hooks/guard/paths.py", "hooks/guard/scope.py"]:
            self.ok("$f installed", os.path.exists(os.path.join(d, f)), f + " missing", {"$f": f})
        self.ok("hooks are executable", is_x(os.path.join(d, "hooks", "ai-guard.py")), "hooks should be executable")
        # The installed hooks/ai-guard.py and its guard/ package must run, not only
        # be there: the command settings.json registers, as Claude Code runs it.
        guard = ["python3", "-I", "-S", os.path.join(d, "hooks", "ai-guard.py")]

        def payload(command):
            body = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/",
                               "tool_input": {"command": command}}, separators=(",", ":"))
            try:
                proc = subprocess.run(guard, input=body, capture_output=True, text=True, env=env_with(), check=False)
                return proc.stdout
            except OSError as exc:
                return "ERROR %s" % exc

        self.ok("the installed git guard runs the port and denies a force push",
                '"permissionDecision":"deny"' in payload("git push --force"),
                "the installed git guard did not deny a force push")
        self.ok("the installed git guard allows ls", payload("ls").strip("\n") == "", "the installed git guard should allow ls")
        self.ok("rr-status/status.py is executable", is_x(os.path.join(d, "skills", "rr-status", "status.py")),
                "rr-status/status.py should be executable")
        self.ok("skills/status is not installed (redesign 2.3)", not os.path.exists(os.path.join(d, "skills", "status")),
                "skills/status installed")
        for f in ("hooks/fable-gate.py", "hooks/codex-model-gate.py"):
            self.ok("$f is not installed (redesign 1.3)", not os.path.exists(os.path.join(d, f)), f + " installed", {"$f": f})
        self.ok("ai-path is executable", is_x(os.path.join(d, "riskrails", "ai-path")), "ai-path should be executable")
        routing = rd(os.path.join(d, "riskrails", "routing.md"))
        self.ok("routing.md names the installed shared tree", d + "/riskrails/ai/" in routing, "routing.md should name %s/riskrails/ai/" % d)
        self.ok("routing.md names the resolver", d + "/riskrails/ai-path <path>" in routing, "routing.md should name the resolver")
        for a in ("ai-discovery", "ai-reviewer"):
            self.ok("$a names the installed shared tree", d + "/riskrails/ai/<path>" in rd(os.path.join(d, "agents", a + ".md")),
                    "%s should name %s/riskrails/ai/<path>" % (a, d), {"$a": a})
        self.ok("scaffold-ai.sh is executable", is_x(os.path.join(d, "skills", "ai-init", "scaffold-ai.sh")), "scaffold should be executable")
        got = " ".join(sorted(f[:-3] for f in os.listdir(os.path.join(d, "agents")) if f.endswith(".md")))
        self.ok("exactly the five agents are installed (redesign 2.4)", got == "Explore ai-discovery ai-reviewer architect log-reader", got)
        arch = rd(os.path.join(d, "agents", "architect.md"))
        self.ok("architect alone is pinned to fable[1m] on max+fable", has_line(arch, r"^model: fable\[1m\]"), "architect should pin fable[1m]")
        self.ok("architect runs at xhigh on Fable", "effort: xhigh" in arch, "architect effort wrong")

    # == real pro install
    def test_12_real_pro_install(self):
        dirp = self.path("claude-pro")
        os.makedirs(dirp, exist_ok=True)
        rc, out = run("--plan", "pro", CLAUDE_DIR=dirp)
        self.ok("pro install exits 0", rc == 0, out)
        arch = rd(os.path.join(dirp, "agents", "architect.md"))
        self.ok("pro: architect pins opus", has_line(arch, r"^model: opus"), "pro: architect should pin opus")
        self.ok("pro: architect runs at high", has_line(arch, r"^effort: high"), "pro: expert effort wrong")
        self.ok("pro: no opus[1m] launcher", not os.path.exists(os.path.join(dirp, "bin", "claude-1m")),
                "pro has no opus[1m]; the launcher must not be installed")
        st = jload(os.path.join(dirp, "settings.json"))
        self.ok("pro: settings.json model is opusplan", jr(jv(st, "model")) == "opusplan", "pro: model not opusplan")
        self.ok("pro: fallback is sonnet", jr(jv(st, "fallbackModel", 0)) == "sonnet", "pro: fallback wrong")
        self.ok("pro: default effort is medium", jr(jv(st, "effortLevel")) == "medium", "pro: effort wrong")
        arch_max = rd(os.path.join(self.path("claude"), "agents", "architect.md"))
        self.ok("max: architect is not pinned to opus", not line_eq(arch_max, "model: opus"), "max: architect must not pin opus")

    # == settings.json
    def test_13_settings_json(self):
        d = self.path("claude")
        sp = os.path.join(d, "settings.json")
        st = jload(sp)
        n = len(cmds(st, "PreToolUse"))
        self.ok("three PreToolUse hooks registered (cap-large-read, ai-guard, runtime-gate)", n == 3, "expected 3 PreToolUse commands, got %d" % n)
        setup_cmd = jv(st, "hooks", "Setup", 0, "hooks", 0, "command")
        self.ok("the Setup:init scaffold hook is registered",
                isinstance(setup_cmd, str) and re.search("project-scaffold", setup_cmd) is not None, "Setup hook missing")
        self.ok("the max session model is pinned to Opus 5.5 [1m], not Fable", jr(jv(st, "model")) == "claude-opus-5-5[1m]", "model not set")
        self.ok("the default effort is medium", jr(jv(st, "effortLevel")) == "medium", "effort not set")
        self.ok("fable[1m] stays available for architect", "fable[1m]" in (jv(st, "availableModels") or []),
                "fable should remain in availableModels")
        dirn = self.path("claude-nofable")
        os.makedirs(dirn, exist_ok=True)
        run("--plan", "max", "--fable", "no", CLAUDE_DIR=dirn)
        self.ok("with --fable no, architect inherits the Opus session",
                not has_line(rd(os.path.join(dirn, "agents", "architect.md")), r"^model:"),
                "with --fable no, architect must inherit the session")
        self.ok("with --fable no, fable is not offered",
                "fable[1m]" not in (jv(jload(os.path.join(dirn, "settings.json")), "availableModels") or []),
                "fable should be removed with --fable no")
        self.ok("by default no compaction window is written: the runtime compacts on its own",
                jv(st, "autoCompactWindow") is None, "autoCompactWindow written without --context economy")
        self.ok("context-guard is executable", is_x(os.path.join(d, "hooks", "context-guard.py")), "context-guard should be executable")
        for ev in ("UserPromptSubmit", "PreCompact", "SessionStart"):
            self.ok("context-guard is registered under $ev", count_ctx(st, ev) == 1,
                    "context-guard is not registered under " + ev, {"$ev": ev})
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        st = jload(sp)
        self.ok("a second install does not register context-guard twice", count_ctx(st, "UserPromptSubmit") == 1,
                "context-guard registered twice")
        routing = rd(os.path.join(d, "riskrails", "routing.md"))
        block = rd(os.path.join(d, "CLAUDE.md"))
        self.ok("routing.md names where the 1M session compacts on its own", "Compaction near 967 000 tokens" in routing,
                "routing.md should say compaction fires near 967 000")
        self.ok("routing.md says the guard warns and never blocks by default",
                "warning from 773k tokens, and the prompt is never held back" in routing, "the guard thresholds are not rendered")
        self.ok("routing.md says compaction is at the runtime default", "runtime default" in routing,
                "routing.md does not name the runtime default")
        self.ok("the block carries what a compaction must keep", "On compaction keep" in block,
                "the compaction rule is missing from the block")
        self.ok("every placeholder is rendered", "{{" not in block, "an unrendered placeholder is left in CLAUDE.md")
        launcher = os.path.join(d, "bin", "claude-1m")
        self.ok("max installs the opus[1m] launcher", is_x(launcher), "bin/claude-1m missing or not executable")
        fake = self.path("fake-claude")
        write(fake, '#!/usr/bin/env bash\necho "window=$CLAUDE_CODE_AUTO_COMPACT_WINDOW args=$*"\n')
        os.chmod(fake, 0o755)

        def launch(*args, window=None):
            proc = subprocess.run([launcher, *args], capture_output=True, text=True,
                                  env=env_with(CLAUDE_BIN=fake, CLAUDE_1M_COMPACT_WINDOW=window,
                                               CLAUDE_CODE_AUTO_COMPACT_WINDOW=None), check=False)
            return proc.returncode, proc.stdout.rstrip("\n")

        rc, out1m = launch("-p", "hi")
        self.ok("claude-1m runs opus[1m] and exports no compaction window", out1m == "window= args=--model opus[1m] -p hi",
                "claude-1m launched the wrong session " + out1m)
        rc, out1m = launch(window="500000")
        self.ok("CLAUDE_1M_COMPACT_WINDOW sets the 1m window", out1m == "window=500000 args=--model opus[1m]",
                "the window override was ignored " + out1m)
        rc, out1m = launch("fable", "-p", "hi")
        self.ok("claude-1m fable runs fable[1m], no window either", out1m == "window= args=--model fable[1m] -p hi",
                "claude-1m fable launched the wrong session " + out1m)
        rc, out1m = launch("opus")
        self.ok("claude-1m opus is the default spelled out", out1m == "window= args=--model opus[1m]",
                "claude-1m opus launched the wrong session " + out1m)
        self.ok("routing.md offers Fable 5.1 [1m] as a session through claude-1m fable", "claude-1m fable" in routing,
                "routing.md does not mention claude-1m fable")
        rc, _ = launch(window="lots")
        self.ok("a non-numeric window is refused", rc != 0, "a non-numeric window must be refused")
        rc, out1m = launch(window="")
        self.ok("an empty window is no window", out1m == "window= args=--model opus[1m]", "empty window: " + out1m)
        self.ok("the launcher writes no settings window", jv(jload(sp), "autoCompactWindow") is None, "settings window changed")

        # --context economy restores the plan's window and the guard's block.
        rc, log = run("--plan", "max", "--fable", "yes", "--context", "economy", CLAUDE_DIR=d)
        routing = rd(os.path.join(d, "riskrails", "routing.md"))
        self.ok("economy: the compaction window is 800k on max; uncapped on the 1M session, so it fires near 767k",
                rc == 0 and jr(jv(jload(sp), "autoCompactWindow")) == "800000", "economy did not write the window")
        self.ok("economy: routing.md names compaction near 767 000", "Compaction near 767 000 tokens" in routing,
                "routing.md should say compaction fires near 767 000")
        self.ok("economy: routing.md names the guard's thresholds",
                "warning from 613k tokens, and from 920k the prompt is held back once" in routing,
                "the guard thresholds are not rendered")
        self.ok("economy: profile.json records the mode and the window",
                jv(jload(os.path.join(d, "riskrails", "profile.json")), "context") == {"mode": "economy", "window": 800000},
                "profile.json context wrong")
        rc, log = run("--plan", "max", "--fable", "yes", "--context", "economy", "--dry-run", CLAUDE_DIR=d)
        self.ok("economy over economy: nothing to remove", "would remove autoCompactWindow" not in log, log[-300:])

        # Back to default: the window an install wrote goes, a user's own stays.
        rc, log = run("--plan", "max", "--fable", "yes", "--dry-run", CLAUDE_DIR=d)
        self.ok("default --dry-run names the window it would remove",
                "would remove autoCompactWindow 800000 (economy off)" in log, log[-300:])
        self.ok("--dry-run removes nothing", jr(jv(jload(sp), "autoCompactWindow")) == "800000", "dry run wrote settings")
        rc, log = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("default removes the plan's own 800000", "removed: autoCompactWindow 800000 (economy off)" in log
                and jv(jload(sp), "autoCompactWindow") is None, log[-300:])
        self.ok("default: profile.json records no window",
                jv(jload(os.path.join(d, "riskrails", "profile.json")), "context") == {"mode": "default", "window": None},
                "profile.json context wrong")
        doc = jload(sp)
        doc["autoCompactWindow"] = 500000
        write(sp, json.dumps(doc))
        rc, log = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("a window the user set (500000) is kept", "removed: autoCompactWindow" not in log
                and jv(jload(sp), "autoCompactWindow") == 500000, log[-300:])
        # Review M2: another plan's shipped window (Pro's 300000) is the installer's too.
        doc["autoCompactWindow"] = 300000
        write(sp, json.dumps(doc))
        rc, log = run("--plan", "max", "--fable", "yes", "--dry-run", CLAUDE_DIR=d)
        self.ok("default --dry-run on max names Pro's 300000 too",
                "would remove autoCompactWindow 300000 (economy off)" in log, log[-300:])
        rc, log = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("a Pro window left by a Pro install goes on a default Max install",
                "removed: autoCompactWindow 300000 (economy off)" in log and jv(jload(sp), "autoCompactWindow") is None,
                log[-300:])
        st = jload(sp)
        self.ok("routing.md says opus[1m] starts with claude-1m", "claude-1m" in routing, "routing.md does not mention claude-1m")
        self.ok("Opus runs at medium", jr(jv(st, "modelSettings", "claude-opus-5", "effortLevel")) == "medium", "opus effort not medium")

        def override(settings):
            value = jv(settings, "env", "CLAUDE_CODE_SUBAGENT_MODEL")
            return jr(value if value not in (None, False) else "unset")

        self.ok("CLAUDE_CODE_SUBAGENT_MODEL is not set, so each agent's own model: applies", override(st) == "unset",
                "CLAUDE_CODE_SUBAGENT_MODEL would override every agent tier")

        def edit(fn):
            doc = jload(sp)
            fn(doc)
            write(sp, json.dumps(doc, indent=2) + "\n")

        edit(lambda s: s.setdefault("env", {}).__setitem__("CLAUDE_CODE_SUBAGENT_MODEL", "sonnet"))
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        st = jload(sp)
        self.ok("a reinstall removes the stale sonnet override", override(st) == "unset",
                "the stale sonnet override survived a reinstall")
        self.ok("the rest of env survives the cleanup", jr(jv(st, "env", "CLAUDE_READ_MAX_LINES")) == "4000",
                "the cleanup dropped other env keys")
        edit(lambda s: s.setdefault("env", {}).__setitem__("CLAUDE_CODE_SUBAGENT_MODEL", "opus"))
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("a user-chosen override is kept", jr(jv(jload(sp), "env", "CLAUDE_CODE_SUBAGENT_MODEL")) == "opus",
                "a user-chosen override was removed")
        self.ok("the installer warns about a user-set override", "CLAUDE_CODE_SUBAGENT_MODEL=opus is set" in out,
                "no warning for a user-set override")
        self.ok("the warning says the override flattens the tiers only before Claude Code 2.1.251", "Before 2.1.251" in out,
                "the warning does not name the 2.1.251 boundary")
        edit(lambda s: s.get("env", {}).pop("CLAUDE_CODE_SUBAGENT_MODEL", None))
        self.ok("the CLAUDE.md block is written", "riskrails:start" in rd(os.path.join(d, "CLAUDE.md")), "block missing")

    # == backups never land inside skills/
    def test_14_backups_never_land_in_skills(self):
        d = self.path("claude")
        write(os.path.join(d, "skills", "ai-init", "EXTRA.md"), "stale\n")
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        bak = glob.glob(os.path.join(d, "skills", "*.bak"))
        self.ok("no *.bak directory is left in skills/ (they would load as duplicate skills)", not bak,
                "a backup was left in skills/: %s" % bak)
        self.ok("the backup went to backups/<date>/skills/ instead",
                os.path.isdir(os.path.join(d, "backups", datetime.date.today().isoformat(), "skills", "ai-init")),
                "backup not found in backups/<date>/skills/")
        os.makedirs(os.path.join(d, "skills", "legacy.bak"), exist_ok=True)
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("a backup left by an older installer is moved out", not os.path.isdir(os.path.join(d, "skills", "legacy.bak")),
                "stale .bak skill not cleaned up")

    # == an older install: its *.bak files, the stale agents and the shim move to backups/<date>/
    def test_15_an_older_install(self):
        d = self.path("claude")
        day = datetime.date.today().isoformat()
        for a in STALE + RETIRED_24:
            write(os.path.join(d, "agents", a + ".md"), "---\nname: %s\n---\nold\n" % a)
        write(os.path.join(d, "agents", "x.md"), "mine\n")
        write(os.path.join(d, "agents", "x.md.bak"), "old mine\n")
        write(os.path.join(d, "agents", "gone.md.bak"), "orphan\n")
        write(os.path.join(d, "hooks", "ai-guard.py.bak"), "old\n")
        write(os.path.join(d, "hooks", "lib", "ai-hook-common.sh.bak"), "old\n")
        write(os.path.join(d, "riskrails", "routing.md.bak"), "old\n")
        write(os.path.join(d, "settings.json.bak"), "{}\n")
        write(os.path.join(d, "CLAUDE.md.bak"), "old\n")
        write(os.path.join(d, "hooks", "fable-gate.py"), "#!/usr/bin/env python3\n")
        write(os.path.join(d, "bin", "claude-1m.bak"), "old\n")
        write(os.path.join(d, "skills", "status", "SKILL.md"), "---\nname: status\n---\nold\n")
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        bk = os.path.join(d, "backups", day)
        self.ok("an installed skills/status is retired into backups/<date>/skills/",
                not os.path.exists(os.path.join(d, "skills", "status")) and os.path.isfile(os.path.join(bk, "skills", "status", "SKILL.md"))
                and ("retired: skills/status -> backups/%s/skills/status" % day) in out, "skills/status not retired\n" + out)
        self.ok("bin/claude-1m.bak is swept too",
                not os.path.exists(os.path.join(d, "bin", "claude-1m.bak")) and os.path.isfile(os.path.join(bk, "bin", "claude-1m.bak")),
                "bin/*.bak not swept\n" + out)
        for a in STALE + RETIRED_24:
            self.ok("agents/$a.md is retired into backups/<date>/agents/",
                    not os.path.exists(os.path.join(d, "agents", a + ".md")) and os.path.isfile(os.path.join(bk, "agents", a + ".md"))
                    and ("retired: agents/%s.md -> backups/%s/agents/%s.md" % (a, day, a)) in out,
                    "agents/%s.md not retired\n%s" % (a, out), {"$a": a})
        xbak = os.path.join(bk, "agents", "x.md.bak")
        self.ok("a seeded x.md.bak beside a live x.md moves to backups/<date>/agents/x.md.bak",
                os.path.isfile(os.path.join(d, "agents", "x.md")) and os.path.isfile(xbak) and rd(xbak).rstrip("\n") == "old mine"
                and not os.path.exists(os.path.join(d, "agents", "x.md.bak")), "x.md.bak not swept\n" + out)
        self.ok("and the move is printed", ("moved: agents/x.md.bak -> backups/%s/agents/x.md.bak" % day) in out, "sweep not reported\n" + out)
        self.ok("a .bak with no live file beside it is left alone", os.path.isfile(os.path.join(d, "agents", "gone.md.bak")), "orphan .bak moved")
        self.ok("an installed fable-gate.py shim is retired too",
                not os.path.exists(os.path.join(d, "hooks", "fable-gate.py")) and os.path.isfile(os.path.join(bk, "hooks", "fable-gate.py")),
                "shim not retired\n" + out)
        left = []
        for pattern in ("*.bak", "agents/*.bak", "hooks/*.bak", "hooks/lib/*.bak", "riskrails/*.bak", "bin/*.bak"):
            for f in glob.glob(os.path.join(d, pattern)):
                if os.path.isfile(f) and os.path.exists(f[:-len(".bak")]):
                    left.append(os.path.relpath(f, d))
        self.ok("no *.bak is left beside a live file", not left, "*.bak left beside a live file: %s" % left)

        def baks():
            found = []
            for dirpath, dirnames, filenames in os.walk(d):
                rel = os.path.relpath(dirpath, d)
                if rel == ".":
                    dirnames[:] = [n for n in dirnames if n != "backups"]
                for name in dirnames + filenames:
                    if name.endswith(".bak"):
                        found.append("./" + os.path.normpath(os.path.join(rel, name)))
            return found

        self.ok("an install writes no *.bak anywhere outside backups/",
                [b for b in baks() if b != "./agents/gone.md.bak"] == [], "*.bak written: %s" % baks())
        self.ok("settings.json and CLAUDE.md are backed up into backups/<date>/",
                os.path.isfile(os.path.join(bk, "settings.json")) and os.path.isfile(os.path.join(bk, "CLAUDE.md")),
                "root backups missing: %s" % (os.listdir(bk) if os.path.isdir(bk) else bk))
        for f in (os.path.join(d, "agents", "x.md"), os.path.join(d, "agents", "gone.md.bak")):
            if os.path.exists(f):
                os.remove(f)

    # == re-install is idempotent
    def test_16_reinstall_is_idempotent(self):
        d = self.path("claude")
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        st = jload(os.path.join(d, "settings.json"))
        n = len(cmds(st, "PreToolUse"))
        self.ok("hook entries are not duplicated on re-install", n == 3, "hooks duplicated: %d" % n)
        self.ok("the Setup hook is not duplicated either", len(cmds(st, "Setup")) == 1, "Setup hook duplicated")
        b = len([ln for ln in rd(os.path.join(d, "CLAUDE.md")).split("\n") if "riskrails:start" in ln])
        self.ok("the CLAUDE.md block is not duplicated", b == 1, "block duplicated: %d copies" % b)

    # == a user edit to the git guard config survives a re-install
    def test_17_user_edit_to_git_guard_config_survives(self):
        d = self.path("claude")
        cfg = os.path.join(d, "hooks", "ai-git-guard.json")
        doc = jload(cfg)
        doc["protected_branches"] = doc.get("protected_branches", []) + ["develop"]
        write(cfg, json.dumps(doc, indent=2) + "\n")
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d)
        self.ok("a local edit to ai-git-guard.json is preserved", "develop" in (jv(jload(cfg), "protected_branches") or []),
                "the user's git guard config was overwritten")

    # == coexistence with a hook the plugin does not own
    def test_18_coexistence_with_a_foreign_hook(self):
        d2 = self.path("claude2")
        vendor = '"$HOME/.claude/hooks/vendor-write-guard.sh"'
        write(os.path.join(d2, "settings.json"), json.dumps(
            {"permissions": {"allow": ["Bash(ls:*)"]},
             "hooks": {"PreToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": vendor}]}]}}))
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d2)
        st = jload(os.path.join(d2, "settings.json"))
        pre = cmds(st, "PreToolUse")
        self.ok("a third-party hook survives the merge", vendor in pre, "the user's own hook was clobbered")
        self.ok("our three PreToolUse hooks are appended alongside it", len(pre) == 4, "expected 4 hook commands total")
        self.ok("unrelated settings keys are preserved", "Bash(ls:*)" in (jv(st, "permissions", "allow") or []),
                "unrelated settings were lost")

    # == migration off the predecessor plugin's block
    def test_19_migration_off_the_predecessor_block(self):
        d3 = self.path("claude3")
        write(os.path.join(d3, "CLAUDE.md"),
              "<!-- claude-routing:start -->\nrouting rules\n<!-- claude-routing:end -->\n\n# My own notes\n")
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d3)
        text = rd(os.path.join(d3, "CLAUDE.md"))
        self.ok("the migration is reported", "migrated the claude-routing block" in out, "migration should be reported\n" + out)
        self.ok("exactly one managed block remains", len([ln for ln in text.split("\n") if "riskrails:start" in ln]) == 1, "expected one block")
        self.ok("the claude-routing block is migrated away", "claude-routing:start" not in text,
                "the predecessor block should have been migrated away")
        self.ok("its superseded content is removed", "routing rules" not in text, "the old block's content should be gone")
        self.ok("the user's own content is kept", "# My own notes" in text, "user content must survive migration")

    # == R35: an install home from before 3.4b moves to riskrails/, the old path a symlink
    def test_20_r35_old_install_home_moves(self):
        d4 = self.path("claude4")
        os.makedirs(os.path.join(d4, "claude-agentic", "ai"), exist_ok=True)
        write(os.path.join(d4, "claude-agentic", "profile.json"), '{"plan":"max"}')
        write(os.path.join(d4, "claude-agentic", "notes.txt"), "mine\n")
        write(os.path.join(d4, "CLAUDE.md"),
              "<!-- claude-agentic:start -->\nold block\n<!-- claude-agentic:end -->\n\n# My own notes\n")
        rc, out = run("--plan", "max", "--fable", "yes", "--dry-run", CLAUDE_DIR=d4)
        self.ok("the dry run names the move", has_line(out, r"^   home:    claude-agentic/ -> riskrails/"), "dry run should name the move\n" + out)
        old = os.path.join(d4, "claude-agentic")
        self.ok("and moves nothing", os.path.isdir(old) and not os.path.islink(old), "dry run moved the home")
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d4)
        self.ok("the old home is a relative symlink to riskrails",
                os.path.islink(old) and os.readlink(old) == "riskrails", "old home is not a symlink\n" + out)
        self.ok("what the old home held moved with it",
                line_eq(rd(os.path.join(d4, "riskrails", "notes.txt")), "mine"), "old home content lost")
        self.ok("the old path still reaches routing.md", os.path.isfile(os.path.join(old, "routing.md")), "old path broken")
        text = rd(os.path.join(d4, "CLAUDE.md"))
        self.ok("the legacy global block is renamed, not doubled",
                len([ln for ln in text.split("\n") if "riskrails:start" in ln]) == 1 and "claude-agentic:start" not in text,
                "global block markers\n" + text)
        self.ok("the user's own text stays", "# My own notes" in text, "user text lost")
        rc, out = run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d4)
        self.ok("a reinstall leaves the symlink alone", not has_line(out, r"^(moved:|linked:)"), "a reinstall moved again\n" + out)
        d5 = self.path("claude5")
        os.makedirs(os.path.join(d5, "claude-agentic"), exist_ok=True)
        os.makedirs(os.path.join(d5, "riskrails"), exist_ok=True)
        write(os.path.join(d5, "claude-agentic", "notes.txt"), "stale\n")
        run("--plan", "max", "--fable", "yes", CLAUDE_DIR=d5)
        kept = os.path.join(d5, "backups", datetime.date.today().isoformat(), "claude-agentic", "notes.txt")
        self.ok("an old home beside a new one is retired into backups/, then linked",
                os.path.islink(os.path.join(d5, "claude-agentic")) and os.path.exists(kept) and line_eq(rd(kept), "stale"),
                "old home beside new one")

    def test_21_npx_surface(self):
        """R16: the flags npx adds, and install.sh reduced to the npx line."""
        with open(os.path.join(PLUGIN, "package.json"), encoding="utf-8") as fh:
            version = json.load(fh)["version"]
        rc, out = install("--version")
        self.ok("--version prints the package version", (rc, out.strip()) == (0, version), out)
        d6 = self.path("home-flag")
        rc, out = install("--home", d6, "--plan", "pro", env=env_with(HOME=self.path("h-flag")))
        self.ok("--home alone under auto installs Claude Code there",
                rc == 0 and os.path.isfile(os.path.join(d6, "settings.json"))
                and not os.path.exists(os.path.join(self.path("h-flag"), ".codex")), out)
        rc, out = install("--target", "nothing")
        self.ok("an unknown --target exits 2", rc == 2 and "--target must be" in out, out)
        proc = subprocess.run(["bash", os.path.join(PLUGIN, "install.sh"), "--target", "claude"],
                              capture_output=True, text=True, env=env_with(CLAUDE_DIR=self.path("wrapped")),
                              stdin=subprocess.DEVNULL, check=False)
        self.ok("install.sh prints the npx line and exits 2",
                proc.returncode == 2 and "npx riskrails@%s --target claude" % version in proc.stderr
                and not os.path.exists(self.path("wrapped")), proc.stdout + proc.stderr)


    def test_22_the_shell_guard_entries_of_an_older_install_are_replaced(self):
        """3.5: the three ai-*-guard.sh entries and files give way to one ai-guard.py entry."""
        d7 = self.path("claude-shims")
        old = [{"matcher": m, "hooks": [{"type": "command", "command": '"$HOME/.claude/hooks/ai-%s-guard.sh"' % g,
                                         "timeout": 10}]}
               for g, m in (("git", "Bash"), ("path", "Read|Edit|Write|MultiEdit|NotebookEdit|Bash"),
                            ("scope", "Edit|Write|MultiEdit|NotebookEdit"))]
        write(os.path.join(d7, "settings.json"), json.dumps({"hooks": {"PreToolUse": old}}))
        for g in ("git", "path", "scope"):
            write(os.path.join(d7, "hooks", "ai-%s-guard.sh" % g), "#!/bin/sh\n")
        rc, out = run("--plan", "pro", CLAUDE_DIR=d7)
        groups = jload(os.path.join(d7, "settings.json"))["hooks"]["PreToolUse"]
        cmds = [h["command"] for g in groups for h in g["hooks"]]
        self.ok("no shell guard entry is left", not [c for c in cmds if "-guard.sh" in c], json.dumps(cmds))
        self.ok("exactly one ai-guard.py entry", len([c for c in cmds if "ai-guard.py" in c]) == 1, json.dumps(cmds))
        self.ok("the install says what it replaced", "replaced: the ai-git/path/scope-guard.sh hooks with ai-guard.py" in out, out)
        day = datetime.date.today().isoformat()
        self.ok("the shim files are retired into backups/", all(
            not os.path.lexists(os.path.join(d7, "hooks", "ai-%s-guard.sh" % g))
            and os.path.isfile(os.path.join(d7, "backups", day, "hooks", "ai-%s-guard.sh" % g))
            for g in ("git", "path", "scope")), out)
        rc, out = run("--plan", "pro", CLAUDE_DIR=d7)
        self.ok("a reinstall replaces nothing more", "replaced:" not in out and "retired:" not in out, out)

    # == R36.20: no dialog timeout on any plan
    def test_23_no_ask_timeout(self):
        for plan, fable in (("pro", "no"), ("team-pro", "no"), ("team-max", "yes"), ("max", "yes"), ("max", "no"),
                            ("max20", "yes"), ("balanced-max", "no")):
            rc, out = self.dry("--target", "claude", "--plan", plan, "--fable", fable)
            subs = {"$1": plan, "$2": fable}
            self.ok("--plan $1 --fable $2 renders no askUserQuestionTimeout",
                    rc == 0 and "askUserQuestionTimeout" not in out, out, subs)
        d = self.path("claude")
        if os.path.exists(os.path.join(d, "settings.json")):
            self.ok("the installed settings.json has no askUserQuestionTimeout",
                    "askUserQuestionTimeout" not in read(os.path.join(d, "settings.json")))


if __name__ == "__main__":
    unittest.main()
