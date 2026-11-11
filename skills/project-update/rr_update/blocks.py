"""The managed block of one instruction file.

shell: block_update
"""

import os

import render_instructions  # next to the entry, whose directory the entry puts on sys.path

from rr_update import files
from rr_update import paths
from rr_update import plan as plan_mod


def block_update(plan, history, runtime):
    """R15, D5: the managed block of one instruction file. Rewritten between its markers; no block
    -> appended; no file -> a minimal one with the block. Text outside the markers is never touched."""
    name, block_tpl, minimal_tpl = paths.INSTRUCTION_FILE[runtime]
    tpl = files.read(os.path.join(paths.TEMPLATES["ai-init"], block_tpl))
    text = plan.read(name)
    if text is None:
        created = files.read(os.path.join(paths.TEMPLATES["ai-init"], minimal_tpl)).replace(
            b"{{PROJECT}}", os.path.basename(plan.root).encode())
        plan.add("create", name, "with the managed block", content=created.rstrip(b"\n") + b"\n\n" + tpl)
        return
    found = render_instructions.find_block(text)
    if found is None:
        plan.add("regenerate", name, "managed block appended", content=text.rstrip(b"\n") + b"\n\n" + tpl)
        return
    s, e = found[0], found[1]
    ours = text[s:e] + b"\n"
    if ours == tpl:
        return
    content = text[:s] + tpl.rstrip(b"\n") + text[e:]
    if history.shipped("ai-init/" + block_tpl, ours):
        plan.add("regenerate", name, "managed block replaced (unchanged since it was installed)", content=content)
    else:
        plan.gated("regenerate", name, "managed block " + plan_mod.edited_note(plan, name, ours, tpl), content=content)
