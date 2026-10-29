"""`state.py profile detect` (R36.16): the port of the installer's plan detection.

The cases live in tests/fixtures/profile/: the installer's own detection cases
(tests/test_install_dry_run.py, tests/test_codex_install.py) verbatim, plus the
statuses the installer never needed — unknown, unsupported, no_profile, same and
drift. Every home is a scratch directory; nothing reads the real ~/.claude.json.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "profile")
# Variables that change what detect sees or which runtime it believes it is.
SCRUB = ("CLAUDECODE", "AI_RUNTIME", "AI_UNATTENDED", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI",
         "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "ANTHROPIC_API_KEY",
         "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "OPENAI_API_KEY")


def cases(runtime):
    with open(os.path.join(FIXTURES, "%s-cases.json" % runtime), encoding="utf-8") as fh:
        return json.load(fh)["cases"]


def b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def jwt(plan_type):
    return ".".join([b64({"alg": "none"}), b64({"https://api.openai.com/auth": {"chatgpt_plan_type": plan_type}}), "sig"])


def with_jwts(value):
    if isinstance(value, dict):
        return {k: with_jwts(v) for k, v in value.items()}
    if isinstance(value, str) and value.startswith("<jwt:") and value.endswith(">"):
        return jwt(value[5:-1])
    return value


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


class Home:
    """A scratch HOME with ~/.claude and ~/.codex, written from one case."""

    def __init__(self, runtime, case):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.home = self.tmp.name
        self.claude = os.path.join(self.home, ".claude")
        self.codex = os.path.join(self.home, ".codex")
        os.makedirs(self.claude)
        os.makedirs(self.codex)
        if runtime == "claude" and case.get("account") is not None:
            write(os.path.join(self.home, ".claude.json"), case["account"])
        if runtime == "codex" and case.get("auth") is not None:
            write(os.path.join(self.codex, "auth.json"), with_jwts(case["auth"]))
        if case.get("installed") is not None:
            write(os.path.join(self.claude if runtime == "claude" else self.codex, "riskrails", "profile.json"),
                  dict(case["installed"], runtime=runtime))
        self.env = {k: v for k, v in os.environ.items() if k not in SCRUB}
        self.env.update(HOME=self.home, CLAUDE_CONFIG_DIR=self.claude, CODEX_HOME=self.codex)
        self.env.update(case.get("env") or {})

    def run(self, *args, stdin=None):
        return subprocess.run(["python3", "-I", STATE] + list(args), env=self.env, cwd=self.home, stdin=stdin,
                              capture_output=True, text=True, check=False)

    def close(self):
        self.tmp.cleanup()


class ProfileDetect(unittest.TestCase):

    def detect(self, runtime, case, *extra):
        home = Home(runtime, case)
        self.addCleanup(home.close)
        done = home.run("profile", "detect", "--runtime", runtime, *extra)
        self.assertEqual(done.returncode, 0, "detect exits 0 always: %s" % done.stderr)
        return done

    def check_cases(self, runtime):
        for case in cases(runtime):
            with self.subTest(case["name"]):
                out = json.loads(self.detect(runtime, case, "--json").stdout)
                want = case["expect"]
                self.assertEqual(out["runtime"], runtime)
                self.assertEqual(out["status"], want["status"])
                self.assertEqual(out["live"]["plan"], want["plan"])
                for key in ("from", "org", "raw"):
                    if key in want:
                        self.assertEqual(out["live"][key], want[key], key)
                if "render" in want:
                    self.assertEqual(out["render"], want["render"])
                if "command_has" in want:
                    self.assertIn(want["command_has"], out["command"] or "")
                if want["status"] != "drift":
                    self.assertIsNone(out["command"], "only drift proposes a command")
                self.assertIsNone(out["decision"], "detect without --open opens no decision")
                self.assertTrue(out["live"]["fingerprint"].startswith("sha256:"))
                installed = case.get("installed")
                self.assertEqual((out["installed"] or {}).get("plan"), installed and installed["plan"])

    def test_claude_cases(self):
        self.check_cases("claude")

    def test_codex_cases(self):
        self.check_cases("codex")

    def test_fingerprint_is_plan_fields_only(self):
        base = {"oauthAccount": {"organizationType": "claude_max", "organizationRateLimitTier": "default_claude_max_20x"}}
        other = {"oauthAccount": dict(base["oauthAccount"], emailAddress="someone@example.com",
                                      accountUuid="0000-1111", displayName="Someone"), "userID": "abc"}
        one = json.loads(self.detect("claude", {"account": base}, "--json").stdout)
        two = self.detect("claude", {"account": other}, "--json").stdout
        self.assertEqual(one["live"]["fingerprint"], json.loads(two)["live"]["fingerprint"],
                         "an email, an id or a name does not move the fingerprint")
        for secret in ("someone@example.com", "0000-1111", "Someone", "abc"):
            self.assertNotIn(secret, two, "detect prints no account identity")
        moved = {"oauthAccount": dict(base["oauthAccount"], organizationRateLimitTier="default_claude_max_5x")}
        three = json.loads(self.detect("claude", {"account": moved}, "--json").stdout)
        self.assertNotEqual(one["live"]["fingerprint"], three["live"]["fingerprint"], "a plan field moves it")

    def test_no_token_is_printed(self):
        case = {"auth": {"auth_mode": "chatgpt", "tokens": {"id_token": "<jwt:plus>", "refresh_token": "rt-secret"}}}
        out = self.detect("codex", case, "--json").stdout
        self.assertNotIn("rt-secret", out)
        self.assertNotIn(jwt("plus"), out)

    def test_codex_claims_as_js_read_them(self):
        """Review T-2026-10-28-002 L1, L2: JS truthiness and String() on the claim, and
        Node's lenient base64url (skipped stray characters, U+FFFD for bad UTF-8)."""
        def token(claim_bytes):
            return ".".join([b64({"alg": "none"}),
                             base64.urlsafe_b64encode(claim_bytes).decode().rstrip("="), "sig"])

        def claim(plan_type):
            return json.dumps({"https://api.openai.com/auth": {"chatgpt_plan_type": plan_type}}).encode()

        def live(tokens):
            out = self.detect("codex", {"auth": {"auth_mode": "chatgpt", "tokens": tokens}}, "--json").stdout
            return json.loads(out)["live"]
        self.assertEqual((live({"id_token": token(claim(["pro"]))})["plan"]), "pro", "['pro'] is 'pro' to String()")
        got = live({"id_token": token(claim([])), "access_token": jwt("pro")})
        self.assertEqual((got["plan"], got["raw"]), (None, ""), "[] is truthy in JS: the search stops at it")
        got = live({"id_token": token(claim({}))})
        self.assertEqual((got["plan"], got["raw"]), (None, "[object object]"))
        good = token(claim("plus"))
        head, body, sig = good.split(".")
        for name, bent in (("a stray *", body[:5] + "*" + body[5:]), ("a newline", body[:5] + "\n" + body[5:])):
            with self.subTest(name):
                self.assertEqual(live({"id_token": ".".join([head, bent, sig])})["plan"], "plus")
        bad_utf8 = b'{"x":"\xff","https://api.openai.com/auth":{"chatgpt_plan_type":"plus"}}'
        self.assertEqual(live({"id_token": token(bad_utf8)})["plan"], "plus", "bad UTF-8 decodes as U+FFFD")

    def test_reader_flags_are_refused(self):
        """Review T-2026-10-28-002 L3: detect answers for --runtime only."""
        home = Home("claude", {"account": {"oauthAccount": {"organizationType": "claude_max"}}})
        self.addCleanup(home.close)
        for flags in (["--other"], ["--field", "plan"], ["--tier", "FAST"]):
            with self.subTest(flags[0]):
                done = home.run("profile", "detect", "--runtime", "claude", *flags)
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("belong to the profile reader", done.stderr)

    def test_plain_text(self):
        case = {"account": {"oauthAccount": {"organizationType": "claude_max",
                                             "organizationRateLimitTier": "default_claude_max_20x"}},
                "installed": {"plan": "max", "plugin_version": "3.1.0"}}
        out = self.detect("claude", case).stdout
        self.assertIn("plan: installed max · account max20 (organizationRateLimitTier default_claude_max_20x) → drift",
                      out)
        self.assertIn("fix: ", out)

    MAX20 = {"oauthAccount": {"organizationType": "claude_max",
                              "organizationRateLimitTier": "default_claude_max_20x"}}

    def opening(self, account, switch=True, **env):
        """A Home whose project (Home/project) has .ai/ and, with switch, dialog.json on."""
        home = Home("claude", {"account": account, "installed": {"plan": "max", "plugin_version": "3.1.0",
                                                                    "dialog": {"tool": "AskUserQuestion"}},
                               "env": dict({"CLAUDE_CODE_SESSION_ID": "s1"}, **env)})
        self.addCleanup(home.close)
        home.project = os.path.join(home.home, "project")
        os.makedirs(os.path.join(home.project, ".ai", "state"))
        if switch:
            write(os.path.join(home.project, ".ai", "policies", "dialog.json"), {"version": 1, "enabled": True})
        return home

    def open_decisions(self, home):
        try:
            with open(os.path.join(home.project, ".ai", "state", "decision.json"), encoding="utf-8") as fh:
                return json.load(fh)["open"]
        except OSError:
            return []

    def detect_open(self, home, *extra):
        done = home.run("--root", home.project, "profile", "detect", "--runtime", "claude", "--open", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done

    def test_open_writes_decision(self):
        home = self.opening(self.MAX20)
        out = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((out["status"], out["decision"]), ("drift", "D1"))
        (decision,) = self.open_decisions(home)
        self.assertEqual((decision["id"], decision["kind"], decision["runtime"]), ("D1", "plan_drift", "claude"))
        keep, switch = decision["options"]
        self.assertEqual((keep["kind"], keep["effect"]), ("choice", "ack"))
        self.assertTrue(keep["label"].startswith("Keep max"), keep["label"])
        self.assertEqual((switch["kind"], switch["label"]), ("command", out["command"]))
        self.assertIn("profile set max20 --runtime claude", switch["label"])
        again = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((again["decision"], len(self.open_decisions(home))), ("D1", 1), "one open decision per drift")
        self.assertIn("decision: D1", self.detect_open(home).stdout)
        # Keep: the human's terminal settles option 1 and the fingerprint is written, with no account field.
        home.env["AI_UNATTENDED"] = "1"
        done = home.run("--root", home.project, "decision", "settle", "--id", "D1", "--pick", "1",
                        stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(os.path.join(home.claude, "riskrails", "drift-ack.json"), encoding="utf-8") as fh:
            ack = json.load(fh)
        self.assertEqual(ack["version"], 1)
        self.assertIsNone(ack["codex"])
        self.assertEqual((ack["claude"]["kept"], ack["claude"]["via"]), ("max", "unattended"))
        self.assertEqual(ack["claude"]["fingerprint"], out["live"]["fingerprint"])
        self.assertNotIn("claude_max", json.dumps(ack))
        del home.env["AI_UNATTENDED"]
        after = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((after["status"], after["decision"]), ("acknowledged", None))
        self.assertEqual(self.open_decisions(home), [])

    def test_open_with_dialog_off_opens_nothing(self):
        for name, home in (("switch off", self.opening(self.MAX20, switch=False)),
                           ("run declared unattended", self.opening(self.MAX20, AI_UNATTENDED="1"))):
            with self.subTest(name):
                out = json.loads(self.detect_open(home, "--json").stdout)
                self.assertEqual((out["status"], out["decision"]), ("drift", None))
                self.assertEqual(self.open_decisions(home), [])
        home = Home("claude", {"account": self.MAX20, "installed": {"plan": "max", "plugin_version": "3.1.0"}})
        self.addCleanup(home.close)
        out = json.loads(home.run("profile", "detect", "--runtime", "claude", "--open", "--json").stdout)
        self.assertEqual((out["status"], out["decision"]), ("drift", None), "no .ai/: nothing to open")

    def test_same_opens_nothing(self):
        home = self.opening({"oauthAccount": {"organizationType": "claude_max"}})
        out = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((out["status"], out["decision"]), ("same", None))
        self.assertEqual(self.open_decisions(home), [])
        self.assertFalse(os.path.exists(os.path.join(home.project, ".ai", "state", "decision.json")))

    def test_open_is_per_session(self):
        home = self.opening(self.MAX20)
        self.detect_open(home, "--json")
        home.env["CLAUDE_CODE_SESSION_ID"] = "s2"
        out = json.loads(self.detect_open(home, "--json").stdout)
        (decision,) = self.open_decisions(home)
        self.assertEqual((out["decision"], decision["id"], decision["session"]), (decision["id"], out["decision"], "s2"))
        self.assertNotEqual(out["decision"], "D1", "the first session's decision is not reused")

    def test_resolved_drift_removes_the_decision(self):
        home = self.opening(self.MAX20)
        self.detect_open(home, "--json")
        write(os.path.join(home.home, ".claude.json"), {"oauthAccount": {"organizationType": "claude_max"}})
        out = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((out["status"], out["decision"]), ("same", None))
        self.assertEqual(self.open_decisions(home), [])

    def test_ack_needs_the_plan_kept(self):
        home = self.opening(self.MAX20)
        fingerprint = json.loads(self.detect_open(home, "--json").stdout)["live"]["fingerprint"]
        ack = os.path.join(home.claude, "riskrails", "drift-ack.json")
        write(ack, {"version": 1, "claude": {"fingerprint": fingerprint, "kept": "max"}, "codex": None})
        self.assertEqual(json.loads(self.detect_open(home, "--json").stdout)["status"], "acknowledged")
        prof = os.path.join(home.claude, "riskrails", "profile.json")
        write(prof, {"plan": "pro", "runtime": "claude", "plugin_version": "3.1.0",
                     "dialog": {"tool": "AskUserQuestion"}})
        self.assertEqual(json.loads(self.detect_open(home, "--json").stdout)["status"], "drift")

    def test_ack_entry_not_an_object_is_ignored(self):
        home = self.opening(self.MAX20)
        write(os.path.join(home.claude, "riskrails", "drift-ack.json"), {"version": 1, "claude": "x"})
        done = home.run("profile", "detect", "--runtime", "claude", "--json")
        self.assertEqual((done.returncode, json.loads(done.stdout)["status"]), (0, "drift"), done.stderr)

    def test_open_with_unreadable_decision_file_stays_read_only(self):
        home = self.opening(self.MAX20)
        path = os.path.join(home.project, ".ai", "state", "decision.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        out = json.loads(self.detect_open(home, "--json").stdout)
        self.assertEqual((out["status"], out["decision"]), ("drift", None))

    def test_detect_without_open_writes_nothing(self):
        home = self.opening(self.MAX20)
        done = home.run("--root", home.project, "profile", "detect", "--runtime", "claude", "--json")
        self.assertIsNone(json.loads(done.stdout)["decision"])
        self.assertEqual(self.open_decisions(home), [])

    def test_needs_no_ai_dir_and_profile_reader_unchanged(self):
        case = {"installed": {"plan": "max20", "tiers": {"FAST": {"model": "claude-haiku-5-5"}}}}
        home = Home("claude", case)
        self.addCleanup(home.close)
        self.assertFalse(os.path.exists(os.path.join(home.home, ".ai")))
        done = home.run("--runtime", "claude", "profile", "--field", "plan")
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "max20"), done.stderr)
        done = home.run("--runtime", "claude", "profile", "--tier", "FAST")
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "claude-haiku-5-5"), done.stderr)


RESOLVER = os.path.join(ROOT, "scripts", "resolve-profile.py")


def resolved(name, plan, label, fable, context="default"):
    out = subprocess.run(["python3", "-I", RESOLVER, name, "--plan", plan, "--label", label, "--fable", fable,
                          "--context", context, "--print", "agentic"], capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out)


def installed_max(context="default", **extra):
    """profile.json as the installer writes it for --plan max --fable yes [--context economy]."""
    prof = resolved("max", "max", "Max", "yes", context)
    prof.update(plugin_version="3.1.0", written_at="2026-10-01T00:00:00Z", dialog={"tool": "AskUserQuestion"},
                set_by={"via": "installer", "at": "2026-10-01T00:00:00Z"})
    prof.update(extra)
    return prof


class ProfileSet(unittest.TestCase):
    """`state.py profile set <plan>` (R36.17): the human route only; same tier rewrites
    profile.json, anything else is the installer's."""

    def home(self, installed=None, **env):
        home = Home("claude", {"installed": installed, "env": env})
        self.addCleanup(home.close)
        return home

    def profile(self, home):
        with open(os.path.join(home.claude, "riskrails", "profile.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_set_same_tier(self):
        home = self.home(installed_max(), AI_UNATTENDED="1")
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("profile.json: max → max20 (claude)", done.stdout)
        self.assertIn("keep the label 'Max'", done.stdout)
        prof = self.profile(home)
        want = resolved("max20", "max20", "Max 20x", "yes")
        self.assertEqual((prof["plan"], prof["label"], prof["budgets"], prof["tiers"], prof["fable"]),
                         (want["plan"], want["label"], want["budgets"], want["tiers"], True))
        self.assertEqual((prof["runtime"], prof["plugin_version"], prof["dialog"]),
                         ("claude", "3.1.0", {"tool": "AskUserQuestion"}))
        self.assertEqual(prof["set_by"]["via"], "unattended")
        self.assertNotEqual(prof["written_at"], "2026-10-01T00:00:00Z")

    def test_set_on_a_terminal_stamps_terminal(self):
        home = self.home(installed_max(plan="pro", label="Pro", fable=False))
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        try:
            done = home.run("profile", "set", "team-pro", "--runtime", "claude", stdin=slave)
        finally:
            os.close(slave)
        self.assertEqual(done.returncode, 0, done.stderr)
        prof = self.profile(home)
        self.assertEqual((prof["plan"], prof["label"], prof["set_by"]["via"]), ("team-pro", "Team Pro", "terminal"))

    def test_set_cross_tier_refuses(self):
        home = self.home(installed_max(), AI_UNATTENDED="1")
        before = self.profile(home)
        done = home.run("profile", "set", "pro", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 6, done.stderr)
        self.assertIn("PROFILE_NEEDS_INSTALLER", done.stderr)
        self.assertIn("npx riskrails@3.1.0 --target claude --plan pro --yes", done.stderr)
        self.assertEqual(self.profile(home), before)

    def test_set_same_tier_keeps_economy(self):
        """Review T-2026-10-28-006 L4: a same-tier set keeps the record's --context economy."""
        home = self.home(installed_max("economy"), AI_UNATTENDED="1")
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        prof = self.profile(home)
        self.assertEqual((prof["plan"], prof["context"]), ("max20", {"mode": "economy", "window": 800000}))

    def test_set_cross_tier_refuses_keeps_economy(self):
        """Review T-2026-10-28-006 L4: the installer command keeps --context economy."""
        home = self.home(installed_max("economy"), AI_UNATTENDED="1")
        done = home.run("profile", "set", "pro", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 6, done.stderr)
        self.assertIn("npx riskrails@3.1.0 --target claude --plan pro --context economy --yes", done.stderr)

    def test_detect_drift_keeps_economy(self):
        """Review T-2026-10-28-006 L4: detect's installer fix keeps --context economy."""
        home = Home("claude", {"account": {"oauthAccount": {"organizationType": "claude_pro"}},
                               "installed": installed_max("economy")})
        self.addCleanup(home.close)
        done = home.run("profile", "detect", "--runtime", "claude", "--json")
        out = json.loads(done.stdout)
        self.assertEqual((out["status"], out["render"]), ("drift", "installer"), done.stderr)
        self.assertEqual(out["command"], "npx riskrails@3.1.0 --target claude --plan pro --context economy --yes")

    def test_context_not_an_object_reads_as_default(self):
        """Review T-2026-10-28-007 L1: a hand-edited non-object `context` is a default record, not a traceback."""
        for bent in ("economy", ["economy"]):
            with self.subTest(repr(bent)):
                prof = installed_max()
                prof["context"] = bent
                home = self.home(prof, AI_UNATTENDED="1")
                done = home.run("profile", "set", "pro", "--runtime", "claude", stdin=subprocess.DEVNULL)
                self.assertEqual(done.returncode, 6, done.stderr)
                self.assertIn("npx riskrails@3.1.0 --target claude --plan pro --yes", done.stderr)

    def test_codex_plus_pro_needs_the_installer(self):
        prof = resolved("codex-plus", "plus", "Plus", "no")
        prof.update(plugin_version="3.1.0")
        home = Home("codex", {"installed": prof, "env": {"AI_UNATTENDED": "1"}})
        self.addCleanup(home.close)
        done = home.run("profile", "set", "pro", "--runtime", "codex", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 6, done.stderr)
        self.assertIn("npx riskrails@3.1.0 --target codex --codex-plan pro --yes", done.stderr)

    def test_set_via_dialog(self):
        """R36.10: inside the agent, profile set runs on the human's pick — this
        exact command, once — and stamps set_by.via = dialog."""
        home = self.home(installed_max(), CLAUDECODE="1", CLAUDE_CODE_SESSION_ID="s1",
                         CLAUDE_CODE_SESSION_ATTENDED="1")
        project = os.path.join(home.home, "project")
        write(os.path.join(project, ".ai", "policies", "dialog.json"), {"version": 1, "enabled": True})
        # The open decision the pick answers (7e's plan_drift; a pick of no open decision counts for nothing).
        write(os.path.join(project, ".ai", "state", "decision.json"),
              {"version": 1, "open": [{"id": "D1", "kind": "plan_drift", "options": [
                  {"n": 1, "kind": "choice", "label": "Keep max"}, {"n": 2, "kind": "command", "label": "x"}]}]})
        label = "python3 %s --root %s profile set max20 --runtime claude" % (STATE, project)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        later = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 120))
        os.makedirs(os.path.join(project, ".ai", "state"), exist_ok=True)
        with open(os.path.join(project, ".ai", "state", "consent.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"v": 1, "type": "pick", "id": "C1", "decision": "D1", "option": 2, "order": 1,
                                 "label": label, "session": "s1", "tool_use_id": "toolu_1", "at": stamp,
                                 "expires_at": later}) + "\n")
        argv = ["--root", project, "profile", "set", "max20", "--runtime", "claude"]
        other = home.run("--root", project, "profile", "set", "team-max", "--runtime", "claude",
                         stdin=subprocess.DEVNULL)
        self.assertEqual(other.returncode, 5, "a different argv is not the pick")
        done = home.run(*argv, stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        prof = self.profile(home)
        self.assertEqual((prof["plan"], prof["set_by"]["via"]), ("max20", "dialog"))
        again = home.run(*argv, stdin=subprocess.DEVNULL)
        self.assertEqual(again.returncode, 5, "a pick is used once")

    def test_set_refused_in_agent(self):
        home = self.home(installed_max(), CLAUDECODE="1")
        before = self.profile(home)
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 5, done.stderr)
        self.assertIn("CLAUDECODE", done.stderr)
        self.assertEqual(self.profile(home), before)

    def test_same_plan_writes_nothing(self):
        home = self.home(installed_max(), AI_UNATTENDED="1")
        before = self.profile(home)
        done = home.run("profile", "set", "max", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("already max", done.stdout)
        self.assertEqual(self.profile(home), before)

    def test_no_profile_and_unknown_plan_are_refused(self):
        home = self.home(None, AI_UNATTENDED="1")
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("npx riskrails writes it", done.stderr)
        done = home.run("profile", "set", "ultra", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("ultra", done.stderr)
        done = home.run("profile", "set", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 1, done.stderr)

    def test_the_installed_resolver_wins(self):
        """<home>/riskrails/scripts/resolve-profile.py and its profiles/ are read before the checkout's."""
        home = self.home(installed_max(), AI_UNATTENDED="1")
        dst = os.path.join(home.claude, "riskrails")
        shutil.copytree(os.path.join(ROOT, "profiles"), os.path.join(dst, "profiles"))
        os.makedirs(os.path.join(dst, "scripts"))
        shutil.copy(RESOLVER, os.path.join(dst, "scripts"))
        with open(os.path.join(dst, "profiles", "max20.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        data["riskrails"]["budgets"]["expert"]["max_per_task"] = 7
        write(os.path.join(dst, "profiles", "max20.json"), data)
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.profile(home)["budgets"]["expert"]["max_per_task"], 7)

    def test_a_profile_that_changes_tiers_is_the_installers(self):
        """The same-tier table is a claim; set checks it on the profiles it resolves."""
        home = self.home(installed_max(), AI_UNATTENDED="1")
        dst = os.path.join(home.claude, "riskrails")
        shutil.copytree(os.path.join(ROOT, "profiles"), os.path.join(dst, "profiles"))
        os.makedirs(os.path.join(dst, "scripts"))
        shutil.copy(RESOLVER, os.path.join(dst, "scripts"))
        with open(os.path.join(dst, "profiles", "max20.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        data["riskrails"]["tiers"] = {"FAST": {"model": "claude-sonnet-5-5"}}
        write(os.path.join(dst, "profiles", "max20.json"), data)
        before = self.profile(home)
        done = home.run("profile", "set", "max20", "--runtime", "claude", stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 6, done.stderr)
        self.assertIn("PROFILE_NEEDS_INSTALLER", done.stderr)
        self.assertEqual(self.profile(home), before)


if __name__ == "__main__":
    unittest.main()
