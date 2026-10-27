#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
profiles/*.json and scripts/resolve-profile.py: every plan carries the plugin's
own tables under `riskrails`, max20 is max plus budgets and nothing else,
and the budgets carry no fan-out and no direct-mode cap since redesign 2.4 —
what is left is the EXPERT rule and the token table.

The sections share the resolved profiles of the first one, in the shell suite's
order: test_NN_ names keep it. A shell message such as "$name resolves with
every key" is filled in with the case's values by lbl().
"""
import glob
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, read_json, write  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-profiles.sh"

RESOLVE = os.path.join(PLUGIN, "scripts", "resolve-profile.py")
PROFILES = os.path.join(PLUGIN, "profiles")
TIERS = ("FAST", "BALANCED", "STRONG", "EXPERT")
CODEX = ("codex-plus", "codex-pro")


def lbl(template, **values):
    """A shell message with its $variables filled in."""
    for key in sorted(values, key=len, reverse=True):
        template = template.replace("$" + key, str(values[key]))
    return template


def truthy(value):
    """jq truthiness: only null and false are false."""
    return value is not None and value is not False


def resolve(*args):
    proc = subprocess.run(["python3", RESOLVE, *args], capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def jq_str(value):
    """jq -r of a value inside a string interpolation."""
    return value if isinstance(value, str) else json.dumps(value)


class Profiles(ScratchCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agentic = {}

    @classmethod
    def resolved(cls, name, *extra, key=None):
        """`resolve-profile.py <name> <extra> --print agentic` parsed, cached under key (the shell's $TMP/<key>.json)."""
        key = key or name
        if key not in cls.agentic:
            rc, out, err = resolve(name, *extra, "--print", "agentic")
            cls.agentic[key] = json.loads(out) if rc == 0 else None
        return cls.agentic[key]

    def check(self, label, cond, detail=""):
        with self.subTest(label):
            self.assertTrue(cond, detail or label)

    def names(self):
        return [os.path.basename(f)[:-len(".json")] for f in sorted(glob.glob(os.path.join(PROFILES, "*.json")))]

    def test_01_R1_every_profile_has_riskrails_with_tiers_budgets_preferred_runtime(self):
        for name in self.names():
            rc, out, err = resolve(name, "--print", "agentic")
            if rc != 0:
                self.check(lbl("$name does not resolve", name=name), False, lbl("$name does not resolve", name=name) + "\n" + err[:200])
                continue
            doc = json.loads(out)
            self.agentic[name] = doc
            missing = ",".join(k for k in ("tiers", "budgets", "preferred_runtime", "plan", "label", "runtime") if k not in doc)
            self.check(lbl("$name resolves with every key", name=name), missing == "", lbl("$name misses: $missing", name=name, missing=missing))
            tiers = doc["tiers"]
            n = sum(1 for k in TIERS if isinstance(tiers.get(k), dict) and truthy(tiers[k].get("model")) and truthy(tiers[k].get("effort")))
            self.check(lbl("$name has the four tiers with model and effort", name=name), n == 4,
                       lbl("$name: $n of 4 tiers complete", name=name, n=n))

        max20 = read_json(os.path.join(PROFILES, "max20.json"))
        keys = ",".join(sorted(max20))
        self.check("max20.json holds only riskrails", keys == "riskrails", "max20.json top-level keys: " + keys)
        self.check("max20 inherits max", max20["riskrails"].get("inherits") == "max", "max20 should inherit max")

        settings20 = json.loads(resolve("max20", "--print", "settings")[1])
        settings = json.loads(resolve("max", "--print", "settings")[1])
        raw = read_json(os.path.join(PROFILES, "max.json"))
        raw.pop("riskrails", None)
        self.check("resolved(max20) minus riskrails equals max.json minus it", settings20 == settings and settings == raw,
                   "max20 settings differ from max")
        doc20, doc = self.resolved("max20"), self.resolved("max")
        self.check("max20: own plan and label, max's tiers",
                   doc20["plan"] == "max20" and doc20["label"] == "Max 20x" and doc20["tiers"] == doc["tiers"],
                   "max20 plan/label/tiers wrong")

    def test_02_resolver_overrides(self):
        doc = self.resolved("pro", "--plan", "team-pro", "--label", "Team Pro", key="team-pro")
        out = "%s|%s" % (jq_str(doc["plan"]), jq_str(doc["label"]))
        self.check("--plan/--label override", out == "team-pro|Team Pro", "--plan/--label: " + out)
        doc = json.loads(resolve("max", "--fable", "no", "--print", "agentic")[1])
        out = "%s|%s" % (jq_str(doc["fable"]), jq_str("architect_model_with_fable" in doc["tiers"]["EXPERT"]))
        self.check("--fable no drops the Fable architect", out == "false|false", "--fable no: " + out)
        doc = json.loads(resolve("max", "--fable", "yes", "--print", "agentic")[1])
        out = "%s|%s" % (jq_str(doc["fable"]), jq_str(doc["tiers"]["EXPERT"]["architect_model_with_fable"]))
        self.check("--fable yes keeps it", out == "true|fable[1m]", "--fable yes: " + out)
        self.check("pro has no Fable key", "architect_model_with_fable" not in self.resolved("pro")["tiers"]["EXPERT"],
                   "pro should not name Fable")
        rc = resolve("no-such-plan")[0]
        self.check("unknown profile exits 2", rc == 2, "unknown profile exit %s" % rc)
        write(self.path("loop-a.json"), '{"claude_agentic":{"inherits":"loop-b"}}')
        write(self.path("loop-b.json"), '{"claude_agentic":{"inherits":"loop-a"}}')
        for loop in ("loop-a", "loop-b"):
            write(self.path("src", "profiles", loop + ".json"), read_text(self.path(loop + ".json")))
        rc = resolve("loop-a", "--src", self.path("src"))[0]
        self.check("an inheritance cycle exits 2", rc == 2, "cycle exit %s" % rc)

    def test_03_R2_R29_budgets_carry_no_fan_out_and_no_direct_mode(self):
        self.resolved("pro", "--plan", "team-pro", key="team-pro")
        for name in ("pro", "team-pro", "max", "max20", "balanced-max", "codex-plus", "codex-pro", "codex-balanced-max"):
            doc = self.resolved(name, *(("--plan", "team-pro") if name == "team-pro" else ()))
            budgets = doc["budgets"] if doc else {}
            self.check(lbl("$name: budgets.fan_out and budgets.direct_mode are gone", name=name),
                       doc is not None and "fan_out" not in budgets and "direct_mode" not in budgets,
                       lbl("$name still carries fan_out or direct_mode", name=name) + "\n" + json.dumps(budgets))
            expert = budgets.get("expert") if doc else None
            ok = (isinstance(expert, dict) and isinstance(expert.get("without_asking"), bool)
                  and isinstance(expert.get("max_per_task"), (int, float)) and not isinstance(expert.get("max_per_task"), bool)
                  and expert["max_per_task"] >= 1)
            self.check(lbl("$name: the EXPERT rule stays", name=name), ok, lbl("$name: budgets.expert", name=name))
        offenders = [f for f in sorted(glob.glob(os.path.join(PROFILES, "*.json")))
                     if '"fan_out"' in read_text(f) or '"direct_mode"' in read_text(f)]
        self.check("no profile source names fan_out or direct_mode", not offenders,
                   "a profile source still names fan_out or direct_mode: %s" % offenders)
        for name in CODEX:
            doc = self.resolved(name)
            self.check(lbl("$name: codex runtime, no workflow preference", name=name),
                       doc["preferred_runtime"].get("by_workflow") == {} and doc.get("runtime") == "codex",
                       lbl("$name: runtime/by_workflow", name=name))
            profile = read_json(os.path.join(PROFILES, name + ".json"))
            got = {k: {"model": v.get("model"), "effort": v.get("effort")} for k, v in doc["tiers"].items()}
            want = {k: {"model": v.get("model"), "effort": v.get("effort")} for k, v in profile["tiers"].items()}
            self.check(lbl("$name: tiers read from the Codex profile", name=name), got == want,
                       lbl("$name: tiers differ from the top-level tiers", name=name))
        for name in ("pro", "max", "max20"):
            doc = self.resolved(name)
            self.check(lbl("$name: refactoring prefers codex", name=name),
                       doc["preferred_runtime"].get("by_workflow") == {"refactoring": "codex"} and doc.get("runtime") == "claude",
                       lbl("$name: runtime/by_workflow", name=name))

    def test_04_R16_each_agent_template_tier_is_its_tier_everywhere(self):
        for t in sorted(glob.glob(os.path.join(PLUGIN, "agents", "*.md.tmpl"))):
            n = os.path.basename(t)[:-len(".md.tmpl")]
            text = read_text(t)
            tier = "\n".join(re.findall(r"^model: \{\{([A-Z]*)_MODEL\}\}$", text, re.M))
            # architect carries a whole model line rendered per plan
            # (ARCHITECT_MODEL_LINE), not a tier placeholder.
            if not tier:
                continue
            self.check(lbl("$n names no model in its source", n=n), not re.search(r"^model: [a-z]", text, re.M),
                       lbl("$n names a model in its source", n=n))
            for p in CODEX:
                roles = read_json(os.path.join(PROFILES, p + ".json")).get("roles") or {}
                role = (roles.get(n) or {}).get("tier")
                role = "none" if role is None or role is False else role
                self.check(lbl("$n: $tier in the template and in $p", n=n, tier=tier, p=p), role == tier,
                           lbl("$n: template $tier, $p role $role", n=n, tier=tier, p=p, role=role))
            for p in ("pro", "max"):
                agents = ((self.resolved(p)["tiers"].get(tier) or {}).get("agents"))
                self.check(lbl("$n listed under $tier in $p", n=n, tier=tier, p=p), isinstance(agents, list) and n in agents,
                           lbl("$n not listed under $tier in $p's riskrails.tiers", n=n, tier=tier, p=p))
            effs = re.findall(r"^effort: (.*)$", text, re.M)
            eff = "\n".join(effs)
            self.check(lbl("$n: effort is its tier's placeholder or a literal", n=n),
                       eff in ("{{%s_EFFORT}}" % tier, "low", "medium", "high"),
                       lbl("$n: effort '$eff' is neither its tier's placeholder nor a literal", n=n, eff=eff))


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    unittest.main()
