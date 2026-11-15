#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The uninstall plan (spec ui-first-approvals R18): bin/uninstall.js plans from an inventory given
as data, and applies a plan only through the io it is handed. Node runs on data alone, with no
home. Stdlib only.
"""
import copy
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import INSTALLER  # noqa: E402  pylint: disable=wrong-import-position

UNINSTALL = os.path.join(os.path.dirname(INSTALLER[1]), "uninstall.js")
GATE = '"$HOME/.claude/hooks/runtime-gate.py" statusline'
BLOCK = "<!-- riskrails:start -->\nrules\n<!-- riskrails:end -->"
USER_HOOK = {"hooks": [{"type": "command", "command": "/home/me/bin/mine.sh"}]}
OUR_HOOK = {"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/ai-guard.py"}]}
SNIPPET = {"model": "opusplan", "env": {"A": "1", "B": "2"}, "hooks": {"PreToolUse": [OUR_HOOK]},
           "statusLine": {"type": "command", "command": GATE}}
FILES = ["agents/architect.md", "hooks/ai-guard.py", "skills/rr-build", "riskrails", "bin/claude-1m"]


def inventory(**over):
    """A seeded home: user hooks and keys beside ours, an edited key, a foreign settings key."""
    inv = {"files": list(FILES), "shippedHooks": ["ai-guard.py"], "earlierSettings": None,
           "settings": {"model": "opusplan", "env": {"A": "1", "B": "changed", "MINE": "x"}, "theme": "dark",
                        "hooks": {"PreToolUse": [USER_HOOK, OUR_HOOK], "Stop": [OUR_HOOK]},
                        "statusLine": {"type": "command", "command": GATE + " --line"}},
           "snippet": SNIPPET, "statusline": {"mode": "riskrails", "replaced": "my-line.sh"},
           "claudeMd": "mine\n\n" + BLOCK + "\n\nalso mine\n"}
    inv.update(over)
    return inv


def node(body, *args):
    """Run body with bin/uninstall.js as `u` and the arguments parsed as `a`; stdout parsed as JSON."""
    script = ("const u = require(%s); const a = process.argv.slice(1).map((x) => JSON.parse(x));\n%s"
              % (json.dumps(UNINSTALL), body))
    proc = subprocess.run([INSTALLER[0], "-e", script, *[json.dumps(x) for x in args]],
                          capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    return json.loads(proc.stdout)


def plan_of(inv):
    """planUninstall(inv)."""
    return node("process.stdout.write(JSON.stringify(u.planUninstall(a[0])));", inv)


def edit(plan, name):
    """The edited entry for a file."""
    return next(e for e in plan["edited"] if e["file"] == name)


class TestPlan(unittest.TestCase):
    """What is moved, edited and kept."""

    def test_moved_is_exactly_ours(self):
        """Only the shipped items are moved; nothing else, and nothing is deleted by the plan."""
        plan = plan_of(inventory())
        self.assertEqual(plan["moved"], FILES)
        self.assertEqual(set(plan), {"moved", "edited", "kept"})

    def test_settings_edit(self):
        """Our hook entries go, the user's stay; the statusLine is restored; equal keys go, edited keys stay."""
        doc = edit(plan_of(inventory()), "settings.json")["content"]
        self.assertEqual(doc["hooks"], {"PreToolUse": [USER_HOOK]})
        self.assertEqual(doc["statusLine"], {"type": "command", "command": "my-line.sh"})
        self.assertNotIn("model", doc)
        self.assertEqual(doc["env"], {"B": "changed", "MINE": "x"})
        self.assertEqual(doc["theme"], "dark")

    def test_differing_key_is_kept_and_printed(self):
        """A key that differs from the rendered snippet is listed under kept, with the fixed items."""
        kept = plan_of(inventory())["kept"]
        self.assertTrue(any("env.B" in k and "differs" in k for k in kept), kept)
        for word in ("config.toml", "plugin", ".ai/"):
            self.assertTrue(any(word in k for k in kept), (word, kept))

    def test_block_removed_and_user_text_kept(self):
        """The managed block goes from CLAUDE.md; the text around it stays."""
        text = edit(plan_of(inventory()), "CLAUDE.md")["content"]
        self.assertNotIn("riskrails", text)
        self.assertEqual(text, "mine\n\nalso mine\n")

    def test_foreign_statusline_untouched(self):
        """A statusLine that is not ours is neither edited nor restored."""
        inv = inventory()
        inv["settings"]["statusLine"] = {"type": "command", "command": "theirs.sh"}
        self.assertEqual(edit(plan_of(inv), "settings.json")["content"]["statusLine"],
                         {"type": "command", "command": "theirs.sh"})

    def test_wrapped_own_statusline_restored(self):
        """Without a saved record, the command our wrapper runs after --then is restored."""
        inv = inventory(statusline=None)
        inv["settings"]["statusLine"] = {"type": "command", "command": GATE + " --then 'echo it'\\''s'"}
        self.assertEqual(edit(plan_of(inv), "settings.json")["content"]["statusLine"]["command"], "echo it's")

    def test_our_statusline_without_a_saved_command_is_removed(self):
        """Nothing to restore: the statusLine goes."""
        doc = edit(plan_of(inventory(statusline=None)), "settings.json")["content"]
        self.assertNotIn("statusLine", doc)

    def test_user_data_never_moved_or_dropped(self):
        """A user-only home: nothing moved, nothing edited."""
        inv = inventory(files=[], snippet={}, claudeMd="mine\n",
                        settings={"theme": "dark", "hooks": {"Stop": [USER_HOOK]}})
        self.assertEqual(plan_of(inv), {"moved": [], "edited": [], "kept": []})

    def test_idempotent(self):
        """Planning the result of a plan is empty: files gone, edits applied."""
        plan = plan_of(inventory())
        after = inventory(files=[], settings=edit(plan, "settings.json")["content"],
                          claudeMd=edit(plan, "CLAUDE.md")["content"])
        self.assertEqual(plan_of(after), {"moved": [], "edited": [], "kept": []})

    def test_our_hook_entries_go_when_their_files_are_already_gone(self):
        """The hook names come from the shipped list: no hook file in the home, the entries of ours still go."""
        files = [f for f in FILES if not f.startswith("hooks/")]
        doc = edit(plan_of(inventory(files=files)), "settings.json")["content"]
        self.assertEqual(doc["hooks"], {"PreToolUse": [USER_HOOK]})

    def test_every_removed_key_is_listed_with_hook_entries_also_removed(self):
        """Hook entries and snippet-equal keys go together: each removed key is named by its dotted path."""
        entry = edit(plan_of(inventory(earlierSettings="/h/backups/2026-01-01/settings.json")), "settings.json")
        self.assertEqual(entry["removedKeys"], ["model", "env.A"])
        self.assertIn("/h/backups/2026-01-01/settings.json", entry["earlier"])
        self.assertIn("no settings backup", edit(plan_of(inventory()), "settings.json")["earlier"])

    def test_inventory_not_mutated(self):
        """The planner leaves its input as it found it."""
        inv = inventory()
        before = copy.deepcopy(inv)
        got = node("const i = a[0]; u.planUninstall(i); process.stdout.write(JSON.stringify(i));", inv)
        self.assertEqual(got, before)


class TestApply(unittest.TestCase):
    """applyUninstall touches only io."""

    def test_calls_only_io(self):
        """Every effect is an io call; moves first, then backup and write per edited file, then the kept lines."""
        plan = plan_of(inventory())
        calls = node("""const calls = [];
const io = { move: (f) => calls.push(['move', f]), backup: (f) => calls.push(['backup', f]),
  writeJSON: (f, o) => calls.push(['writeJSON', f]), writeText: (f, t) => calls.push(['writeText', f, t]),
  log: (l) => calls.push(['log', l]) };
u.applyUninstall(a[0], io);
process.stdout.write(JSON.stringify(calls));""", plan)
        verbs = [c[0] for c in calls]
        self.assertEqual([c[1] for c in calls if c[0] == "move"], FILES)
        self.assertLess(verbs.index("backup"), verbs.index("writeJSON"))
        self.assertIn(["writeText", "CLAUDE.md", "mine\n\nalso mine\n"], calls)
        self.assertEqual(verbs.count("backup"), 2)
        self.assertTrue(any(c[0] == "log" and "env.B" in c[1] for c in calls))

    def test_edits_come_before_the_first_move_and_each_edit_after_its_backup(self):
        """No setting may point at a moved file: every backup and write precedes the first move."""
        calls = self.run_apply(inventory(), "")
        verbs = [c[0] for c in calls]
        self.assertLess(max(i for i, v in enumerate(verbs) if v in ("backup", "writeJSON", "writeText")), verbs.index("move"))
        self.assertLess(verbs.index("backup"), verbs.index("writeJSON"))
        removed = [c[1] for c in calls if c[0] == "log" and c[1].startswith("removed:")]
        self.assertEqual(removed, ["removed: settings.json: model", "removed: settings.json: env.A"])
        self.assertTrue(any(c[0] == "log" and c[1].startswith("earlier:") for c in calls))

    def test_a_failed_move_stops_with_what_was_done_and_what_is_left(self):
        """The second move throws: the error names the path, the cause, the edits done, the count, the rest, the way out."""
        calls = self.run_apply(inventory(), "if (calls.filter((c) => c[0] === 'move').length === 2) throw new Error('EXDEV: cross-device link');")
        self.assertEqual(calls[-1][0], "error")
        self.assertEqual([c[0] for c in calls if c[0] == "move"], ["move", "move"])
        self.assertIn("writeJSON", [c[0] for c in calls])
        msg = calls[-1][1]
        for part in ("could not move hooks/ai-guard.py", "EXDEV: cross-device link", "edited settings.json, CLAUDE.md",
                     "1 of 5 moved", "left: hooks/ai-guard.py, skills/rr-build, riskrails, bin/claude-1m",
                     "nothing was deleted", "run --uninstall again"):
            self.assertIn(part, msg)

    @staticmethod
    def run_apply(inv, move_body):
        """applyUninstall(plan_of(inv)) with a recording io whose move runs move_body first; the calls, an error last."""
        return node("""const calls = [];
const io = { move: (f) => { calls.push(['move', f]); %s }, backup: (f) => calls.push(['backup', f]),
  writeJSON: (f) => calls.push(['writeJSON', f]), writeText: (f) => calls.push(['writeText', f]),
  log: (l) => calls.push(['log', l]) };
try { u.applyUninstall(a[0], io); } catch (e) { calls.push(['error', e.message]); }
process.stdout.write(JSON.stringify(calls));""" % move_body, plan_of(inv))

    def test_fails_without_io_helper(self):
        """No fs of its own: with an io lacking move, it throws instead of touching a file."""
        proc = subprocess.run([INSTALLER[0], "-e",
                               "require(%s).applyUninstall({moved:['x'],edited:[],kept:[]}, {log(){}})" % json.dumps(UNINSTALL)],
                              capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("io.move is not a function", proc.stderr)


if __name__ == "__main__":
    unittest.main()
