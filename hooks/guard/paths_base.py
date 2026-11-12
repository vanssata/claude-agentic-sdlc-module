"""The shared texts of the path guard: the text converter T, the regex fragments Q, END, VAR and
SEGMENT, and the deny messages (the WHY_* texts) that more than one rule module raises.

R16: every name here is core (no file, clock or subprocess access).
Moved from paths.py in WP5 (small-oop-modules), unchanged.
"""
from guard.common import text_to_b


T = text_to_b

Q = "['\"]?"
END = "([[:space:]]|['\"]|$)"
VAR = "\\$\\{?[A-Za-z_][A-Za-z0-9_]*\\}?"

WHY_CONFIRM_DELETE = T(
    "\n\n--confirm-delete is a human confirming an irreversible deletion, and the name\n"
    "typed is the audit trail. A human runs the same command in a terminal\n"
    "outside Claude Code or Codex (not through the ! prefix: that shell is the\n"
    "agent's). An unattended run exports AI_UNATTENDED=1 in the launcher's environment, and the\n"
    "record then says via: unattended. See skills/project-update/SKILL.md.")
WHY_SENSITIVE = T(
    "\n\nProduction secrets and data dumps must not enter the model context.\n"
    "If this path is genuinely safe (a .dist/.example file, a fixture), add a regex to\n"
    "\"allow_patterns\" in .ai/policies/path-guard.json. See .ai/policies/security.md.")
WHY_PROTECTED = T(
    "\n\nThese files are the guard configuration and the task state. State is written by\n"
    "skills/ai-task/state.py, and during a schema migration by\n"
    "skills/project-update/update.py; policy files are edited by a human outside an\n"
    "agent run, so a change to them is reviewable. See .ai/policies/safety.md.")
WHY_TASK = T(
    "\n\nWhile a task is in flight the runtime's own configuration is frozen: settings,\n"
    "agent and skill definitions, commands, hooks, and the pipeline's policies and\n"
    "workflows. A run that edits the rules it is being judged by is how scope and\n"
    "review quietly get weaker. Finish or archive the task\n"
    "(skills/ai-task/state.py close), then change this through /project-update or by\n"
    "hand outside a run. See .ai/policies/safety.md.")
WHY_APPROVE = T(
    "\n\nApproval happens outside the agent. A human runs, in their own terminal:\n"
    "  python3 <plugin>/skills/ai-task/state.py --root . approve --by \"<name>\"\n"
    "or sets [Answer]: A on the gate question in .ai/reports/<task-id>/task.md\n"
    "and tells the session to run state.py questions --sync. An unattended run\n"
    "exports AI_UNATTENDED=1 in the launcher's environment, and the journal then\n"
    "records the approval as unattended for ever. See .ai/policies/safety.md.")
WHY_WORK_CAP = T(
    "This command names more paths than the guard can check within its timeout; split it into "
    "smaller commands, or pass the list through a file and xargs.")

WHY_HUMAN = T(
    "\n\nThis command is the human's, whether or not the dialog is on. A human runs it in their\n"
    "own terminal, outside the agent session; an unattended run exports AI_UNATTENDED=1 in the\n"
    "launcher's environment. See .ai/policies/safety.md.")
WHY_PICK = T(
    "\n\nWith the dialog on, this command runs from an agent session only as the human's pick.\n"
    "The command that needs it opened a decision: 'state.py decision show' prints the dialog;\n"
    "send it and run the picked command verbatim, once. Otherwise the human runs it in their\n"
    "own terminal. See .ai/policies/safety.md.")

SEGMENT = "^[[:space:]]*"
