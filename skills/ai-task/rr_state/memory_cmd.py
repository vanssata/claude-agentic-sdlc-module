"""memory_cmd: the `memory` and `recall` commands over the memory_store and memory_sync modules -- the actions, the human's route, the risk record.

shell: memory_modules, memory_config, memory_human, memory_confirm, cmd_recall, cmd_memory, memory_status, memory_enable, memory_disable, memory_export, memory_verify, memory_show, memory_search, risk_scope, memory_risk, memory_risks, memory_migrate, memory_rebuild, memory_cleanup, memory_restore, memory_pack, memory_redact
core: MEMORY_ACTIONS
"""
# pylint: disable=protected-access  # cmd_recall, memory_search and memory_risk call fs._split_files, which partition.json assigns to fs
# pylint: disable=unused-argument  # every action in MEMORY_ACTIONS is called with the same arguments, rt included; most never read it
import json
import os
import shlex
import sys

from rr_state import fs, journal, task
from rr_state import dialog as rr_dialog
from rr_state import runtime as rr_runtime

# sensors.py sits beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None


def memory_modules():
    """memory_sync and memory_store, imported only by the commands that use them."""
    try:
        import memory_store               # pylint: disable=import-outside-toplevel
        import memory_sync                # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        fs.die("the memory modules are not installed beside state.py (%s)" % exc, 2)
    return memory_sync, memory_store


def memory_config(sync, root):
    try:
        return sync.load_config(root)
    except sync.MemoryError_ as exc:
        fs.die(str(exc), exc.code)
    return None


def memory_human(root, what, allow_dialog=False, rt=rr_runtime.Runtime()):
    """R16: enable, disable, cleanup, pack, redact and move-logs take the human's route, as approve does. Only
    enable passes allow_dialog: a live pick of this session that is this very command is the human's answer."""
    via, why = rr_dialog.human_route(root, allow_dialog=allow_dialog, rt=rt)
    if via is None:
        fs.die("APPROVAL_REFUSED — 'memory %s' is the human's, from their own terminal:\n  python3 %s --root %s "
            "%s\nRefused because %s." % (what, shlex.quote(fs.ENTRY), shlex.quote(root),
                                         " ".join(shlex.quote(a) for a in sys.argv[sys.argv.index("memory"):]
                                                  if "memory" in sys.argv), why), 5)
    return via


def memory_confirm(cfg, name, what):
    if not name:
        fs.die("'memory %s' deletes or moves files: add --confirm-delete %s" % (what, cfg.author), 2)
    if name != cfg.author:
        fs.die("--confirm-delete names %r; this clone's author is %r (.ai/local/memory/config.json)"
            % (name, cfg.author), 2)


def cmd_recall(args, root, rt=rr_runtime.Runtime()):
    """R10: the open risks, residual findings, decisions, scope changes and task
    one-liners that touch these files, within the budget. Read-only."""
    sync, store = memory_modules()
    cfg = memory_config(sync, root)
    files = fs._split_files(args.files)
    if not files:
        fs.die("recall needs --files \"a,b,dir/**\"", 2)
    kinds = fs._split_files(args.kinds) or None
    history = store.open_history(root, cfg)
    budget = args.budget if args.budget is not None else cfg.recall_budget
    text, result = history.recall(files, budget, cfg.recall_max_items, kinds, args.all_risks, args.offset)
    if args.json:
        print(json.dumps({"schema": 1, "files": files, "budget": budget, "used": result["used"],
                          "items": [{k: i[k] for k in ("rid", "kind", "task", "ts", "line", "src")}
                                    for i in result["items"]],
                          "more": result["more"], "next": result["next"], "source": history.source()},
                         ensure_ascii=False, sort_keys=True))
        return
    sys.stdout.write(text)


def cmd_memory(args, root, rt=rr_runtime.Runtime()):
    sync, store = memory_modules()
    action = args.memory_action
    try:
        MEMORY_ACTIONS[action](args, root, sync, store, rt=rt)
    except sync.MemoryError_ as exc:
        fs.die(str(exc), exc.code)


def memory_status(args, root, sync, _store, rt=rr_runtime.Runtime()):
    lines = sync.status_lines(root)
    if args.json:
        print(json.dumps(dict(line.split(": ", 1) for line in lines), ensure_ascii=False, sort_keys=True))
        return
    print("\n".join(lines))


def memory_enable(args, root, sync, _store, rt=rr_runtime.Runtime()):
    if memory_human(root, "enable", allow_dialog=True, rt=rt) == "dialog":
        pick = rr_dialog.pick_data(rr_dialog.DIALOG_PICK[0])
        print("memory: via dialog (consent %s, decision %s)" % (pick["consent"], pick["decision"]))
    hook = sync.enable(root, args.author, args.period, args.index)
    print("memory: packages mode on (%s); every teammate's next close exports" % sync.POLICY_REL)
    print("pre-push: %s" % hook)
    if hook in ("foreign", "hookspath"):
        print("not written — %s. Add these lines to your own pre-push hook:\n%s" % (
            "core.hooksPath is set" if hook == "hookspath" else "a pre-push hook exists", sync.snippet_text()))
    print("\n".join(sync.status_lines(root)))


def memory_disable(_args, root, sync, _store, rt=rr_runtime.Runtime()):
    memory_human(root, "disable", rt=rt)
    print("memory: files mode; packages and local data kept; pre-push: %s" % sync.disable(root))


def memory_export(args, root, sync, _store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    ids = "pending" if args.pending or not args.ids else [task.valid_task_id(t, "ID") for t in args.ids]
    result = sync.export(root, ids, cfg)
    for line in sync.record_lines(result):
        print(line)
    print("exported: +%d entries%s" % (result.added, "" if result.added else " — nothing pending"))
    for task_id, why in result.failures:
        print("memory: export of %s failed (%s)" % (task_id, why))
    if result.failures:
        sys.exit(1)


def memory_verify(args, root, sync, _store, rt=rr_runtime.Runtime()):
    stats = None
    if args.range:
        if ".." not in args.range:
            fs.die("--range takes OLD..NEW", 2)
        old, new = args.range.split("..", 1)
        findings, stats = sync.validate_range(root, sync.rev(root, old), sync.rev(root, new) or new, local=False)
        findings = findings or []
    elif args.fresh_clone:
        findings = sync.verify_fresh_clone(root)
    else:
        findings = sync.verify(root, "all", [task.valid_task_id(t, "ID") for t in args.ids] or None)
    failing = [f for f in findings if not f.check.endswith("-warn")]
    if args.json:
        print(json.dumps({"findings": [f._asdict() for f in findings], "ok": not failing, "stats": stats},
                         ensure_ascii=False, sort_keys=True))
    else:
        for f in findings:
            print(sync.format_finding(f))
        print("memory verify: %s" % ("ok" if not failing else "%d finding(s)" % len(failing)))
    if failing:
        sys.exit(1)


def memory_show(args, root, sync, _store, rt=rr_runtime.Runtime()):
    print("\n".join(sync.show(root, task.valid_task_id(args.id, "ID"), "json" if args.json else "md", args.entry)))


def memory_search(args, root, sync, store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    filters = {"kind": args.kind, "by": args.by, "task": args.task, "since": args.since, "until": args.until,
               "files": fs._split_files(args.file) or None}
    history = store.open_history(root, cfg)
    hits, total = history.search(args.query or "", filters, args.limit, args.offset)
    if args.json:
        print(json.dumps({"schema": 1, "query": args.query or "", "total": total, "offset": args.offset,
                          "items": [{"rid": e["rid"], "kind": e["kind"], "task": e.get("task"), "ts": e.get("ts"),
                                     "line": store.mf.search_line(e)} for e in hits],
                          "source": history.source()}, ensure_ascii=False, sort_keys=True))
        return
    print("# Search — \"%s\" · %d of %d matches · offset %d · index %s" % (
        args.query or "", len(hits), total, args.offset, history.source()["index"]))
    for e in hits:
        print("- %s" % store.mf.search_line(e))
    if args.offset + len(hits) < total:
        print("… %d more: --offset %d" % (total - args.offset - len(hits), args.offset + len(hits)))


def risk_scope(state):
    """C4 (§D9): with a task in flight, files mode edits known-risks.md only
    when the task names it."""
    rel = ".ai/project/known-risks.md"
    if state and not sensors.scope_any(rel, task.task_files(state)):
        fs.die("SCOPE_CHANGE_REQUIRED — 'memory risk' writes %s, which task %s does not name:\n"
            "  state.py start --amend --files \"+%s\" --why \"<the risk you record>\"" % (rel, state["task_id"], rel),
            6)


def memory_risk(args, root, sync, store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    state = task.in_flight(root, rt=rt)
    if args.risk_action == "add":
        where = fs._split_files(args.where)
        if args.label not in store.mf.LABELS:
            fs.die("--label takes one of: %s" % ", ".join(store.mf.LABELS), 2)
        if args.status not in store.mf.RISK_STATUS:
            fs.die("--status takes one of: %s" % ", ".join(store.mf.RISK_STATUS), 2)
        if not cfg.packages:
            risk_scope(state)
            found = "%s, by %s" % (fs.now()[:10], state["task_id"] if state else "no task")
            rkey = sync.risk_add_files(root, args.title, where, args.label, args.what, args.likely, args.fix,
                                       args.status, found)
            print("risk: %s added to .ai/project/known-risks.md" % rkey)
            return
        data = sync.risk_data(args.title, where, args.label, args.what, args.likely, args.fix, args.status)
    else:
        if args.status not in ("fixed", "accepted", "ticketed"):
            fs.die("--status takes fixed, accepted or ticketed", 2)
        if not cfg.packages:
            risk_scope(state)
            sync.risk_close_files(root, args.rkey, args.status, args.why)
            print("risk: %s is %s" % (args.rkey, args.status))
            return
        history = store.FileHistory(root, cfg)
        found = [e for e in history.risks("all") if e.get("rkey") == args.rkey]
        if not found:
            fs.die("no risk %s ('state.py memory risks --status all')" % args.rkey, 1)
        last = found[0]
        data = sync.risk_data(last["title"], last.get("where"), last.get("label"), last.get("what"),
                              last.get("likelihood"), last.get("fix"), args.status, args.why, last["rid"])
    if state:
        state = task.load(root, rt=rt)
        journal.emit(root, state, "risk_recorded", "%s: %s" % (data["rkey"], fs.one_line(data["title"], 200)), data, rt=rt)
        task.save(root, state)
        print("risk: %s recorded in %s's journal (exported at close)" % (data["rkey"], state["task_id"]))
        return
    entry = sync.standalone_risk(root, cfg, data, rt.name)
    print("risk: %s recorded (%s)" % (data["rkey"], entry["rid"]))


def memory_risks(args, root, sync, store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    risks = store.open_history(root, cfg).risks(args.status)
    if args.json:
        for e in risks:
            print(store.mf.canonical(e).decode("utf-8"))
        return
    if args.md:
        out = ["# Known risks", ""]
        for e in risks:
            out += (e["text"].split("\n") if e.get("text") else store.mc.risk_section(
                e.get("title"), store.mf.where_list(e.get("where")), e.get("label"), e.get("what"),
                e.get("likelihood"), e.get("fix"), "%s%s" % (e.get("status"), " — %s" % e["status_why"]
                                                             if e.get("status_why") else ""),
                e.get("found_by") or "-")) + [""]
        print("\n".join(out).rstrip("\n"))
        return
    print("# Risks — %s · %d" % (args.status, len(risks)))
    for e in risks:
        where = store.mf.where_list(e.get("where"))
        print("- [%s %s] %s — %s (%s)" % (e.get("status"), e.get("label"), where[0] if where else "-",
                                          e.get("title"), e.get("rkey")))


def memory_migrate(args, root, sync, _store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    if args.move_logs:
        memory_human(root, "migrate --move-logs", rt=rt)
        memory_confirm(cfg, args.confirm_delete, "migrate --move-logs")
        moved, command = sync.move_logs(root)
        print("moved %d committed log(s) into .ai/state/logs/<id>/legacy/; now, as its own commit (C3):\n  %s"
              % (len(moved), command))
        return
    if args.apply:
        print("\n".join(sync.migrate_apply(root, risks=args.risks)))
        return
    report = sync.migrate_report(root)
    print("report: %s (%d lines) — read it, then 'state.py memory migrate --apply'"
          % (os.path.join(sync.LOCAL_REL, "migration-report.md"), report.count("\n")))


def memory_rebuild(_args, root, sync, store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    print("index: rebuilt from %d sources (%s)" % (store.SqliteHistory(root, cfg).rebuild(), store.INDEX_REL))


def memory_cleanup(args, root, sync, _store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    memory_human(root, "cleanup", rt=rt)
    memory_confirm(cfg, args.confirm_delete, "cleanup")
    if not args.all and not args.ids:
        fs.die("memory cleanup takes IDs or --all", 2)
    print("\n".join(sync.cleanup(root, "all" if args.all else [task.valid_task_id(t, "ID") for t in args.ids])))


def memory_restore(args, root, sync, _store, rt=rr_runtime.Runtime()):
    if not args.all and not args.ids:
        fs.die("memory restore takes IDs or --all", 2)
    print("\n".join(sync.restore(root, "all" if args.all else [task.valid_task_id(t, "ID") for t in args.ids])))


def memory_pack(args, root, sync, _store, rt=rr_runtime.Runtime()):
    cfg = memory_config(sync, root)
    memory_human(root, "pack", rt=rt)
    memory_confirm(cfg, args.confirm_delete, "pack")
    target, removed, count = sync.pack(root, args.period)
    print("pack: %s (%d records; %d batch(es) removed)" % (os.path.join(sync.MEMORY_REL, target), count,
                                                          len(removed)))


def memory_redact(args, root, sync, _store, rt=rr_runtime.Runtime()):
    via = memory_human(root, "redact", rt=rt)
    rid, name = sync.redact(root, args.rid, args.field, args.why, by="%s via %s" % (os.environ.get("USER") or
                                                                                   "unknown", via))
    print("redacted: %s in %s (new rid %s)" % (args.field, os.path.join(sync.MEMORY_REL, name), rid))


MEMORY_ACTIONS = {"status": memory_status, "enable": memory_enable, "disable": memory_disable,
                  "export": memory_export, "verify": memory_verify, "show": memory_show, "search": memory_search,
                  "risk": memory_risk, "risks": memory_risks, "migrate": memory_migrate, "rebuild": memory_rebuild,
                  "cleanup": memory_cleanup, "restore": memory_restore, "pack": memory_pack,
                  "redact": memory_redact}
