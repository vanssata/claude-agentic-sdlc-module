"""The hints of a run: budget offenders and hints, the .gitignore rows, the constitution and verification hints.

shell: budget_offenders, gitignore_update, budget_hints, constitution_hint, verification_hints
"""

import contextlib
import io
import os
import re

import render_instructions  # next to the entry, whose directory the entry puts on sys.path

from rr_update import files as files_mod
from rr_update import paths


def budget_offenders(root, files, caps, block_of):
    """R21: one line per root instruction file over budget — its managed block
    over `caps["project"]`, or the whole file over `caps["skeleton"]`. Files that
    do not exist are skipped; a file under both budgets prints nothing."""
    out = []
    for name in files:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block = block_of(text)
        size = len(text.encode("utf-8"))
        if block is not None and caps.get("project") and len(block.encode("utf-8")) > caps["project"]:
            out.append("%s block %d B over the project budget of %d B"
                       % (name, len(block.encode("utf-8")), caps["project"]))
        if caps.get("skeleton") and size > caps["skeleton"]:
            out.append("%s file %d B over the skeleton budget of %d B" % (name, size, caps["skeleton"]))
    return out


def gitignore_update(plan, snippet_path):
    snippet = files_mod.read(snippet_path).decode().splitlines()
    current = plan.read(".gitignore") or b""
    have = set(current.decode().splitlines())
    missing = [l for l in snippet if l.strip() and not l.startswith("#") and l not in have]
    if not missing:
        return
    header = [l for l in snippet if l.startswith("#") and l not in have]
    add = "\n".join(header + missing) + "\n"
    sep = b"\n" if current and not current.endswith(b"\n") else b""
    new = current + sep + add.encode()
    # Replace an earlier .gitignore item from this run instead of stacking two.
    plan.items = [i for i in plan.items if i["target"] != ".gitignore"]
    plan.add("regenerate", ".gitignore", "entries appended: " + ", ".join(missing), content=new)


def budget_hints(plan, runtimes):
    """What the always-loaded block costs this project after this run.

    Downstream the budget is advisory (R4): the plugin measures its own block
    and says what it costs, but a project's own file is never refused. A block
    that is over budget and still the one the plugin installed is the plugin's
    to trim; an edited one is the project's."""
    try:
        cap = render_instructions.budgets(render_instructions.DEFAULT_SOURCE).get("project")
    except render_instructions.RenderError:
        return
    if not cap:
        return
    for rt in runtimes:
        name, block_tpl, _ = paths.INSTRUCTION_FILE[rt]
        text = plan.read(name)
        if text is None:
            continue
        block = render_instructions.block_of(text.decode("utf-8", "replace"))
        if block is None:
            continue
        size = len(block.encode("utf-8"))
        if size <= cap:
            continue
        shipped = files_mod.read(os.path.join(paths.TEMPLATES["ai-init"], block_tpl)).rstrip(b"\n")
        whose = ("the plugin ships it that size — report it"
                 if block.encode("utf-8").rstrip() == shipped
                 else "it was edited here, so the plugin will not rewrite it: trimming it is yours")
        plan.hints.append("%s: the managed block is %d B, budget %d B — %s"
                          % (name, size, cap, whose))


def constitution_hint(plan):
    """R10: the cap is hard for the shipped template and advisory for a project.
    The rule lives in render_instructions; this only relays what it says."""
    rel = "docs/sdlc/constitution.md"
    path = os.path.join(plan.root, rel)
    if not os.path.isfile(path):
        return
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        render_instructions.constitution(path, out=io.StringIO())
    for line in err.getvalue().splitlines():
        plan.hints.append(line.replace(path, rel))


def verification_hints(plan):
    """R10: update's empty-field hints read verification.md."""
    text = plan.read(paths.VERIFICATION_MD)
    if text is None:
        return
    for field, why in (
        ("verify_command", "the feedback loop needs it"),
        ("step_test_command", "a step runs only its own tests"),
        ("e2e_command", "e2e runs once at the end of a task; write 'none' if there is no suite"),
        ("lint_command", "a sensor reads it; read the project's config files for it, and write 'none' if there is none"),
        ("typecheck_command", "a sensor reads it; read the project's config files for it, and write 'none' if there is none"),
    ):
        if re.search(rb"(?m)^" + field.encode() + rb":[ \t]*(#.*)?$", text):
            plan.hints.append("%s: %s is empty — %s" % (paths.VERIFICATION_MD, field, why))
        elif not re.search(rb"(?m)^" + field.encode() + rb":", text):
            plan.hints.append("%s: %s is missing — %s" % (paths.VERIFICATION_MD, field, why))
