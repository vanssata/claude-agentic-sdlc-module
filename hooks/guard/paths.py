"""Port of hooks/ai-path-guard.sh: the sensitive-path guard, on Read, Edit,
Write, MultiEdit, NotebookEdit and Bash (Codex: Bash and apply_patch).

Opt-in: it does nothing unless the project has a .ai/ directory — except the
`--confirm-delete` rule, which runs first and everywhere. Four jobs: keep
secrets and data dumps out of the context; keep the guards' configuration and
the task state out of an agent's edits; freeze the runtime's own configuration
while a task is in flight; treat a dependency's instruction files as data.

Every block of the shell guard is here, in its order, with its messages, its
caps and its clock. The shell's processes are done in-process with the same
answers: `realpath -m` (realpath_m), `find … -prune -o -print` (find_print),
the awk segmenter (shell_segments), each `grep` (Matcher.grep_q, loose_hits),
the redirection `sed`. What ran inside `$( )` and so could not change the
guard's own state still cannot: covers_protected asks whether a task is in
flight without remembering the answer, as its subshell forgot it.
The rule groups live in the sibling modules paths_base, paths_fs, paths_shell, paths_human, paths_interp,
paths_classify, paths_movers and paths_bash, imported as guard.<name>; this file binds their methods.
"""
from guard import paths_bash, paths_classify, paths_human, paths_interp, paths_movers
from guard.common import (Deny, chomp_all, env_b, find_ai_root, is_dir, is_file, jq_tostring,
                          load_json_file, strip1)
from guard.paths_base import T, WHY_WORK_CAP
from guard.paths_fs import cd_physical, lexnorm


class PathGuard:                            # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """The state of one tool call: the work counters against their caps and the clock, and the task
    memo. Its methods live in the rule modules and are bound below."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.m = ctx.matcher
        self.loc = ctx.loc
        self.p = ctx.payload
        self.cwd = ctx.payload.cwd
        self.home = env_b("HOME")
        self.task_active = None
        self.task_id = "?"
        self.work = {"classify": 0, "scan": 0, "token": 0}
        self.caps = {"classify": 64, "scan": 16, "token": 256}
        self.cover_done = False
        self.cover_joined = ""
        self.cover_roots = ""
        self.root = ""
        self.deny_p = self.allow_p = self.prot_p = self.task_p = ""
        self.interesting = self.loose = self.loose_joined = ""
        self.roots, self.prefixes, self.renamed = [], [], []
        self.anch = {"PROT": [], "TASK": []}

    # -------------------------------------------------------------- clock and caps

    def clock_ok(self):
        return self.ctx.clock.seconds() < 6

    def work_cap(self, kind):
        self.work[kind] += 1
        if not (self.work[kind] <= self.caps[kind] and self.clock_ok()):
            raise Deny(WHY_WORK_CAP)

    def work_clock(self):
        if not self.clock_ok():
            raise Deny(WHY_WORK_CAP)

    # -------------------------------------------------------------- the task

    def _state_file(self):
        """The task's state file."""
        return self.root + "/.ai/state/state.json"

    def _task_line(self):
        loaded = load_json_file(self._state_file())
        out = []
        if loaded is not None:
            for doc in loaded[0]:
                if doc is not None and not isinstance(doc, dict):
                    continue
                stage = doc.get("current_stage") if doc else None
                task = doc.get("task_id") if doc else None
                stage = "" if stage is None or stage is False else stage
                task = "?" if task is None or task is False else task
                out.append(jq_tostring(stage) + "\t" + jq_tostring(task) + "\n")
        return chomp_all(T("".join(out)))

    def task_in_flight(self, remember=True):
        """task_in_flight. With remember=False it is asked from a subshell: an
        answer the guard already had is used, a new one is not kept."""
        if self.task_active is None:
            active, task_id = "no", self.task_id
            if is_file(self._state_file()):
                line = self._task_line()
                if line.split("\t", 1)[0] != "done":
                    active = "yes"
                if line:
                    task_id = line.split("\t", 1)[1] if "\t" in line else line
            if not remember:
                return active == "yes"
            self.task_active, self.task_id = active, task_id
        return self.task_active == "yes"

    def phys_path(self, p):
        tail = "/" if p.endswith("/") or p.endswith("/.") else ""
        d = lexnorm(p)
        rest = ""
        while d != "/" and not is_dir(d):
            rest = "/" + d.rsplit("/", 1)[-1] + rest
            d = d.rsplit("/", 1)[0] or "/"
        pwd = cd_physical(d)
        if pwd is None:
            return None
        return (strip1(pwd, "/") + rest + tail) or "/"

    # -------------------------------------------------------------- the check

    def check(self):
        p = self.p
        if p.tool not in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"):
            return
        # AI_UNATTENDED is set when non-empty and not 0, false or no: one rule (risk 0587)
        unattended = env_b("AI_UNATTENDED").strip().lower() not in ("", "0", "false", "no")
        if p.tool == "Bash" and not unattended:
            self.confirm_delete(p.bash_command())
        root = find_ai_root(p.cwd, self.ctx.pwd)
        if root is None:
            return
        self.root = root
        self.load_patterns()
        if not (self.deny_p + self.prot_p + self.task_p):
            return
        self.build_loose()
        self.setup_anchors()
        if p.tool == "Read":
            for f in p.target_paths():
                if f:
                    self.check_path(f, "read")
            return
        if p.tool != "Bash":
            for f in p.target_paths():
                if f:
                    self.check_path(f, "write")
            return
        self.check_bash(unattended)

    # -------------------------------------------------------------- the method table: moved methods, bound here

    # pattern loading, anchors and classification (paths_classify)
    load_patterns = paths_classify.load_patterns
    build_loose = paths_classify.build_loose
    setup_anchors = paths_classify.setup_anchors
    anchor_rels = paths_classify.anchor_rels
    anchored_hit = paths_classify.anchored_hit
    unanchored_hit = paths_classify.unanchored_hit
    classify = paths_classify.classify
    check_path = paths_classify.check_path

    # the movers pass and its location helpers (paths_movers)
    cover_init = paths_movers.cover_init
    realpath_m_arg = paths_movers.realpath_m_arg
    sort_u = paths_movers.sort_u
    roots_under = paths_movers.roots_under
    covers_work = paths_movers.covers_work
    covers_protected = paths_movers.covers_protected
    loose_hits = paths_movers.loose_hits
    movers = paths_movers.movers
    loc_mode = paths_movers.loc_mode
    loc_pat = paths_movers.loc_pat
    loc_text = paths_movers.loc_text
    from_loc = paths_movers.from_loc
    mover_resolve = paths_movers.mover_resolve
    mover_check = paths_movers.mover_check

    # the --confirm-delete rule and the dialog consent (paths_human)
    confirm_delete = paths_human.confirm_delete
    dialog_consent = paths_human.dialog_consent

    # interpreter one-liners and in-place edits (paths_interp)
    inplace_edit = paths_interp.inplace_edit
    interpreter_text = paths_interp.interpreter_text

    # the Bash rule (paths_bash)
    check_bash = paths_bash.check_bash


def check(ctx):
    PathGuard(ctx).check()
