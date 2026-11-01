"""verify: the `verify` command -- run one scope's command to the end, record it, re-score; the e2e declarations and the moved-tree detail.

shell: moved_detail, run_v7, e2e_na_refusal, e2e_na, e2e_none, cmd_verify
core: E2E_NONE
"""
# pylint: disable=protected-access  # run_v7 calls fs._split_files, which partition.json assigns to fs
# pylint: disable=unused-argument  # uniform cli dispatch: cmd_verify takes rt like every command
import os
import shlex
import sys

from rr_state import dialog, fs, handoff, journal, labels, report, task
from rr_state import policy as rr_policy
from rr_state import runtime as rr_runtime

# sensors.py sits beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None


def moved_detail(root, before, after, limit=5):
    """Lines naming what changed between the two snapshots of a run that moved the tree,
    and saying so when the new paths are untracked (a suite that writes a cache or a
    coverage file moves the tree on every run). [] when the paths cannot be measured."""
    diff = fs.safe_sensor(sensors.diff_files, root, before, after)
    if not diff:
        return []
    paths = [d["path"] for d in diff]
    tracked = set()
    code, out = fs.safe_sensor(sensors.git, root, ["ls-files", "-z", "--"] + paths) or (1, "")
    if code == 0:
        tracked = set(f for f in out.split("\0") if f)
    new = [d["path"] for d in diff if d["status"] == "A" and d["path"] not in tracked]
    def esc(path):
        # A name from `git diff -z` is data: a newline or ESC in it would forge a verify line.
        return "".join(c if c.isprintable() else repr(c)[1:-1] for c in path)
    shown = ", ".join("%s (%s)" % (esc(d["path"]), "untracked" if d["path"] in new else
                                   {"A": "added", "D": "deleted", "T": "type changed"}.get(d["status"], "changed"))
                      for d in diff[:limit])
    more = " and %d more" % (len(diff) - limit) if len(diff) > limit else ""
    lines = ["changed during the run: %s%s" % (shown, more)]
    if new:
        lines.append("untracked files written by the suite move the tree on every run: add them to "
                     ".gitignore or stop the suite writing them")
    return lines


def run_v7(root, state, scope, args, tcfg, rt=rr_runtime.Runtime()):
    """One scope's command, to the end, logged under .ai/state/logs/; returns the run."""
    command = fs.safe_sensor(sensors.command_for, root, scope) or ""
    if not command:
        fs.die("no command for scope '%s' in .ai/policies/testing.md — write it down first" % scope)
    files = fs._split_files(args.files)
    if files:
        command = fs.safe_sensor(sensors.expand_files, command, files) or command
    runs = state["verify"]["runs"]
    n = len(runs) + 1
    fs.ensure_logs(root, state["task_id"])
    log = os.path.join(fs.logs_dir(root, state["task_id"]), "%s-%d.log" % (scope, n))
    before = fs.current_tree(root)
    result = fs.safe_sensor(sensors.run_command, root, command, log, tcfg.get("timeout_seconds", 1800),
                         tcfg.get("log_max_bytes", 2097152))
    if result is None:
        fs.die("sensors.py is not installed beside state.py — run the project's command yourself")
    after = fs.current_tree(root)
    # A tree that moved during the run was not the tree the run tested: the run
    # is kept in the record, but stands for no tree at all.
    run = {"n": n, "scope": scope, "exit": result["exit"], "tree": after if after == before else None,
           "tree_moved": after != before,
           "log": os.path.relpath(log, root), "ts": fs.now(), "expected_fail": args.expect == "fail",
           "runtime": rt.name, "command": command, "duration_s": result["duration_s"],
           "after_fix": args.after_fix or None, "files": files}
    runs.append(run)
    if scope == "suite":
        state["verify"]["suite_runs"] += 1
        state["verify"]["status"] = ("passing" if run["exit"] == 0 else
                                     "env_failure" if run["exit"] is None else "failing")
    elif scope == "e2e":
        state["verify"]["e2e"] = "passing" if run["exit"] == 0 else "failing"
        state["verify"]["e2e_tree"] = run["tree"]
    if run["tree_moved"]:
        print("tree moved during the run: run %d stands for no tree — run it again on a still tree" % n)
        for line in moved_detail(root, before, after):
            print(line)
    journal.emit(root, state, "verify_run", "%s run %d: exit %s" % (scope, n, run["exit"]),
         {k: run[k] for k in ("n", "scope", "exit", "tree", "log", "expected_fail")}, rt=rt)
    if rr_policy.full_suite(run) and run["exit"] is not None and run["tree"]:
        other = [r for r in runs[:-1] if rr_policy.full_suite(r) and r.get("tree") == run["tree"]
                 and r.get("runtime") != rt.name and (r.get("exit") == 0) != (run["exit"] == 0)
                 and r.get("exit") is not None]
        red, green = (run, other[-1]) if other and run["exit"] != 0 else \
            (other[-1], run) if other else (None, None)
        if red:
            # R19: the same tree green under one runtime and red under the other, in
            # either order, goes into task.md. A red under Codex is best effort and
            # never a gate; a red under any other runtime is the change's, and the
            # green elsewhere does not answer it (two_facts).
            state["findings"].append("%s: suite red under %s (run %d) and green under %s (run %d) on %s"
                                     % (fs.now(), red.get("runtime"), red["n"], green.get("runtime"),
                                        green["n"], run["tree"][:9]))
            if red.get("runtime") == "codex":
                print("finding: red under %s on a tree green under %s — recorded in task.md, close is not "
                      "blocked" % (red.get("runtime"), green.get("runtime")))
            else:
                print("red under %s on a tree green under %s — recorded in task.md; the red is the change's "
                      "and close is blocked until it is green under %s"
                      % (red.get("runtime"), green.get("runtime"), red.get("runtime")))
    print("%s run %d: exit %s in %ds" % (scope, n, run["exit"], run["duration_s"]))
    print("command: %s" % command)
    print("log: %s" % run["log"])
    if result.get("detail"):
        print(result["detail"])
    return run


def e2e_na_refusal(root, state):
    """Why e2e cannot be declared not applicable now, or None. The last e2e run
    decides, on whatever tree it ran: a red flow is fixed and run again, never
    declared away by an edit and a declaration; a run that could not finish
    (exit None) is run again."""
    runs = [r for r in state["verify"]["runs"] if r.get("scope") == "e2e"]
    if not runs or runs[-1].get("exit") == 0:
        return None
    last, tree = runs[-1], fs.current_tree(root)
    if last.get("exit") is None:
        return ("e2e run %d did not finish: run it again with 'verify --scope e2e' — an environment "
                "failure is not a reason to declare e2e not applicable" % last["n"])
    where = "on this tree" if tree and last.get("tree") == tree else \
        "on %s, and no e2e run since has passed" % (last.get("tree") or "a moving tree")[:9]
    return ("e2e run %d is red %s: a failing flow is fixed and 'verify --scope e2e' run again, not "
            "declared not applicable" % (last["n"], where))


def e2e_na(root, state, why, rt=rr_runtime.Runtime()):
    refusal = e2e_na_refusal(root, state)
    if refusal:
        fs.die(refusal)
    tree = fs.current_tree(root)
    state["verify"]["e2e_tree"] = tree
    state["verify"]["e2e"] = "not_applicable"
    state["verify"]["e2e_why"] = why
    journal.emit(root, state, "verify_run", "e2e not applicable: %s" % fs.one_line(why, 200),
         {"scope": "e2e", "exit": None, "not_applicable": True, "why": why}, rt=rt)
    print("e2e: not applicable — %s" % fs.one_line(why, 200))


E2E_NONE = "e2e_command: none in .ai/policies/testing.md"


def e2e_none(root):
    return (fs.safe_sensor(sensors.command_for, root, "e2e") or "").strip() == "none"


def cmd_verify(args, root, rt=rr_runtime.Runtime()):
    """Run, record, re-score up; exit 0 green, 1 red, 6 SUITE_BUDGET (R20)."""
    state = task.load_v7(root, rt=rt)
    policy = rr_policy.weight_policy(root)
    tcfg = policy.get("tests") or {}
    scope = args.scope
    if args.expect and (scope != "step" or not args.files):
        fs.die("--expect fail is for one test shown failing before the fix: --scope step --files <test>")
    if args.e2e and (scope not in ("all", "e2e") or args.e2e[0] != "not-applicable"
                     or not args.e2e[1].strip()):
        fs.die('--e2e takes: not-applicable "<why the change cannot reach an e2e flow>", with --scope all or e2e')
    if scope == "all" and args.files:
        fs.die("--files narrows one scope; --scope all runs the whole suite and e2e")
    if args.e2e and e2e_na_refusal(root, state):
        fs.die(e2e_na_refusal(root, state))         # before the suite runs, not after (N3)
    max_runs, budget_name = rr_policy.budget(policy, state, "max_suite_runs")
    if scope in ("suite", "all") and state["verify"]["suite_runs"] >= max_runs:
        if not args.by:
            dialog.offer_decision(root, state, "human_set", "Budget",
                           "%s\nSUITE_BUDGET: %d suite runs; weight.json allows %d%s. Run it once more?"
                           % (dialog.task_facts(root, state), state["verify"]["suite_runs"], max_runs,
                              " (%s)" % budget_name if rr_policy.batch_on(state) else ""),
                           [{"kind": "choice", "effect": "keep", "label": "Keep the budget — stop here"},
                            {"kind": "command",
                             "label": labels.state_label(root, sys.argv[1:] + ["--by", labels.human_name(root)])}], "verify", rt=rt)
            fs.die("SUITE_BUDGET — %d suite runs; weight.json allows %d (%s). Running it "
                "again is not the next move: the human decides. In their own terminal:\n  python3 %s "
                "--root %s verify --scope %s --by \"<name>\""
                % (state["verify"]["suite_runs"], max_runs, budget_name, shlex.quote(fs.ENTRY),
                   shlex.quote(root), scope), 6)
        via, why = dialog.human_route(root, allow_dialog=True, rt=rt)
        if via is None:
            fs.die("APPROVAL_REFUSED — a run past the suite budget is the human's, from their own terminal."
                "\nRefused because %s." % why, 5)
        journal.emit(root, state, "human_set", "suite run %d past the budget by %s via %s"
             % (state["verify"]["suite_runs"] + 1, args.by, via),
             dict({"field": "suite_runs", "value": state["verify"]["suite_runs"] + 1, "by": args.by,
                   "via": via, "unattended": via == "unattended"}, **dialog.pick_data(dialog.DIALOG_PICK[0])),
             actor="human" if via == "terminal" else "agent", rt=rt)
    green_before = rr_policy.suite_green(state)
    state["stage"] = "verify"
    code = 0
    if scope == "e2e" and args.e2e:
        e2e_na(root, state, args.e2e[1], rt=rt)
    elif scope == "e2e" and e2e_none(root):
        e2e_na(root, state, E2E_NONE, rt=rt)            # `none` is a declaration, not a command (N1)
    else:
        run = run_v7(root, state, "suite" if scope == "all" else scope, args, tcfg, rt=rt)
        code = run["exit"]
        if args.expect == "fail":
            # exit 1 is a failing test; the runner's own usage error (2) is not, unless
            # testing.md's bite_codes names it (pytest 1,2 — 2 is a collection error)
            run["bites"] = code in (fs.safe_sensor(sensors.bite_codes, root) or (1,))
            print("expected fail: %s" % ("the test fails without the fix — it bites" if run["bites"]
                                         else "the test passes without the fix — it does not bite yet"))
            code = 0 if run["bites"] else 1
        elif scope == "all" and code == 0:
            if args.e2e:
                e2e_na(root, state, args.e2e[1], rt=rt)
            elif not rr_policy.mode_setting(policy, state["mode"], "e2e", False):
                state["verify"]["e2e"] = "not_required"
                print("e2e: not required in %s mode" % state["mode"])
            elif e2e_none(root):
                e2e_na(root, state, E2E_NONE, rt=rt)
            else:
                code = run_v7(root, state, "e2e", args, tcfg, rt=rt)["exit"]
        elif scope == "all":
            print("e2e: not run — the suite is red")
    rr_policy.rescore_v7(root, state, policy, "verify", rt=rt)
    if not green_before and rr_policy.suite_green(state):
        handoff.write_handoff(root, state, "verify", rt=rt)
    task.save(root, state)
    report.write_task_md(root, state)
    if scope in ("suite", "all"):
        print("suite runs used: %d of %d" % (state["verify"]["suite_runs"], max_runs))
    sys.exit(0 if code == 0 else 1)
