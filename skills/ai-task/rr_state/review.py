"""review: the `review` command -- one reviewer pass recorded, the verdict checked against the findings block, the findings closed by a green suite.

core: REVIEW_TIERS, FINDING_RE, OUT_OF_SCOPE_RE, open_findings, VERDICT_LINE_RE
shell: read_report, verdict_matches_findings, cmd_review, review_closes
"""
# pylint: disable=protected-access  # cmd_review calls fs._split_files, which partition.json assigns to fs
import os
import re
import shlex
import sys

from rr_state import dialog, fs, handoff, journal, task
from rr_state import labels as rr_labels
from rr_state import policy as rr_policy
from rr_state import report as rr_report
from rr_state import runtime as rr_runtime

REVIEW_TIERS = ["BALANCED", "STRONG"]
FINDING_RE = re.compile(r"\[(BLOCKER|HIGH|MEDIUM|LOW|INFO)\]\s+([A-Z][0-9]+)\b")
OUT_OF_SCOPE_RE = re.compile(r"in_scope:\s*no\b", re.I)


def read_report(source):
    if not source:
        return ""
    if source == "-":
        return sys.stdin.read()
    try:
        with open(source, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        fs.die("--report %s: %s" % (source, exc))
    return ""                             # unreachable: die() exits


def open_findings(text, severities=("BLOCKER", "HIGH")):
    """Labels of `severities` whose block does not say in_scope: no."""
    hits = list(FINDING_RE.finditer(text or ""))
    out = []
    for i, m in enumerate(hits):
        block = text[m.start():hits[i + 1].start() if i + 1 < len(hits) else len(text)]
        if m.group(1) in severities and not OUT_OF_SCOPE_RE.search(block):
            out.append(m.group(2))
    return out


# "VERDICT pass", "VERDICT: pass", "## VERDICT pass" and the shipped reviewer's
# "## VERDICT" section with its "verdict: pass" line (ai/agents/reviewer.md).
VERDICT_LINE_RE = re.compile(r"^(?:#+[ \t]*)?verdict[ \t]*:?[ \t]*(pass_with_findings|blockers_open|pass)\b",
                             re.M | re.I)


def verdict_matches_findings(verdict, text):
    """The verdict a reviewer's FINDINGS block allows: an in-scope BLOCKER is
    blockers_open, an in-scope HIGH is not a pass, and a VERDICT line in the
    block is the verdict. The block is the evidence; a verdict without it is a
    claim nobody can audit."""
    if not (text or "").strip() or "FINDINGS" not in text:
        fs.die("review needs the reviewer's FINDINGS block: --report - (stdin) or --report FILE")
    blockers, highs = (open_findings(text, (sev,)) for sev in ("BLOCKER", "HIGH"))
    said = VERDICT_LINE_RE.search(text)
    if said and said.group(1) != verdict:
        fs.die("--verdict %s, but the report's VERDICT line says %s" % (verdict, said.group(1)))
    if blockers and verdict != "blockers_open":
        fs.die("the report has an in-scope BLOCKER (%s): the verdict is blockers_open, not %s"
            % (", ".join(blockers), verdict))
    if highs and verdict == "pass":
        fs.die("the report has an in-scope HIGH (%s): the verdict is pass_with_findings or blockers_open"
            % ", ".join(highs))


def cmd_review(args, root, rt=rr_runtime.Runtime()):
    """One pass recorded; the pass past review_rounds_max is the human's (exit 6)."""
    state = task.load_v7(root, rt=rt)
    policy = rr_policy.weight_policy(root)
    review = state["review"]
    if args.closes:
        review_closes(root, state, fs._split_files(args.closes), rt=rt)
        return
    if not args.verdict or not args.tier:
        fs.die("review needs --verdict pass|pass_with_findings|blockers_open and --tier BALANCED|STRONG")
    rounds, budget_name = rr_policy.budget(policy, state, "review_rounds_max")
    by_human = None
    if review["passes"] >= rounds:
        if not args.by:
            report = ["--report", os.path.abspath(args.report)] if args.report and os.path.isfile(args.report) else []
            dialog.offer_decision(root, state, "human_set", "Review",
                           "%s\nREVIEW_BUDGET: %d review passes; weight.json allows %d%s. The next verdict is yours."
                           % (dialog.task_facts(root, state), review["passes"], rounds,
                              " (%s)" % budget_name if rr_policy.batch_on(state) else ""),
                           [{"kind": "choice", "effect": "keep", "label": "Keep it open — no verdict now"}] +
                           [{"kind": "command",
                             "label": rr_labels.state_label(root, ["review", "--verdict", verdict, "--tier", args.tier] +
                                                     report + ["--by", rr_labels.human_name(root)])}
                            for verdict in ("pass", "pass_with_findings", "blockers_open")], "review", rt=rt)
            fs.die("REVIEW_BUDGET — %d review passes; weight.json allows %d (%s). The next "
                "verdict is the human's, in their own terminal:\n  python3 %s --root %s review --verdict "
                "<verdict> --tier %s --by \"<name>\"" % (review["passes"], rounds, budget_name,
                                                         shlex.quote(fs.ENTRY),
                                                         shlex.quote(root), args.tier), 6)
        via, why = dialog.human_route(root, allow_dialog=True, rt=rt)
        if via is None:
            fs.die("APPROVAL_REFUSED — a verdict past the review budget is the human's, from their own "
                "terminal.\nRefused because %s." % why, 5)
        by_human = (args.by, via)
    wanted = rr_policy.mode_setting(policy, state["mode"], "reviewer", "BALANCED")
    if wanted in REVIEW_TIERS and REVIEW_TIERS.index(args.tier) < REVIEW_TIERS.index(wanted):
        fs.die("%s mode needs a %s review (weight.json modes.%s.reviewer); this one was %s"
            % (state["mode"], wanted, state["mode"], args.tier))
    text = read_report(args.report)
    if not by_human:
        verdict_matches_findings(args.verdict, text)
    labels = [m.group(2) for m in FINDING_RE.finditer(text)]
    status = rr_policy.VERDICT_STATUS[args.verdict]
    tree = fs.current_tree(root)
    review.update(status=status, passes=review["passes"] + (0 if by_human else 1), tier=args.tier,
                  findings=open_findings(text), tree=tree, ts=fs.now(),
                  runs_at=len(state["verify"]["runs"]))
    review["log"].append({"n": len(review["log"]) + 1, "tier": args.tier, "verdict": args.verdict,
                          "focus": args.focus, "text": text[:20000], "tree": tree, "ts": fs.now(),
                          "runtime": rt.name, "by": by_human[0] if by_human else None})
    state["stage"] = "review"
    if by_human:
        journal.emit(root, state, "human_set", "review %s by %s via %s" % (args.verdict, by_human[0], by_human[1]),
             dict({"field": "review", "value": status, "by": by_human[0], "via": by_human[1],
                   "unattended": by_human[1] == "unattended"}, **dialog.pick_data(dialog.DIALOG_PICK[0])),
             actor="human" if by_human[1] == "terminal" else "agent", rt=rt)
    journal.emit(root, state, "review_verdict", "%s on %s (pass %d)" % (args.verdict, args.tier, review["passes"]),
         {"verdict": args.verdict, "tier": args.tier, "pass_n": review["passes"], "labels": labels,
          "focus": args.focus}, rt=rt)
    state["next_action"] = rr_policy.review_next_action(state)
    handoff.write_handoff(root, state, "review", rt=rt)
    task.save(root, state)
    rr_report.write_task_md(root, state)
    print("review: %s (%s, pass %d of %d)%s" % (status, args.tier, review["passes"], rounds,
                                               " — open: %s" % ", ".join(review["findings"])
                                               if review["findings"] else ""))


def review_closes(root, state, labels, rt=rr_runtime.Runtime()):
    """passed_with_findings → passed once a green suite run after the verdict, on
    a tree the fix changed, is the tree now (§3a, without a second review)."""
    review = state["review"]
    if review["status"] != "passed_with_findings":
        fs.die("--closes is for a passed_with_findings review; this one is %s" % review["status"])
    unknown = [l for l in labels if l not in review["findings"]]
    if not labels or unknown:
        fs.die("--closes names open findings (%s); not open: %s"
            % (", ".join(review["findings"]) or "none", ", ".join(unknown) or "none given"))
    tree = fs.current_tree(root)
    runs = [r for r in state["verify"]["runs"][review.get("runs_at") or 0:]
            if rr_policy.full_suite(r) and r.get("exit") == 0]
    if not runs or runs[-1].get("tree") != tree or tree == review.get("tree"):
        fs.die("findings %s stay open: they close on a green 'state.py verify --scope suite|all --after-fix "
            "\"…\"' after the verdict, on a tree the fix changed, which is the tree now" % ", ".join(labels))
    review["findings"] = [l for l in review["findings"] if l not in labels]
    review["closed"] = list(review.get("closed") or []) + labels
    if not review["findings"]:
        review["status"] = "passed"
    journal.emit(root, state, "findings_closed", "%s closed by suite run %d on %s"
         % (", ".join(labels), runs[-1]["n"], tree[:9]),
         {"labels": labels, "run": runs[-1]["n"], "tree": tree}, rt=rt)
    task.save(root, state)
    rr_report.write_task_md(root, state)
    print("findings closed: %s; review %s" % (", ".join(labels), review["status"]))
