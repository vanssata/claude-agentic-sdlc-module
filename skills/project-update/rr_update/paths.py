"""Where things are: the skill's directories, the environment's overrides, and the literal path tables the update reads.

shell: env, HERE, SKILLS, TEMPLATES, HISTORY, PLUGIN_HOME, SHARED
core: LAST_MIGRATING_VERSION, EXIT_KEPT_UNREADABLE, REFUSED, VERSION_FILE, ROUTER_FILE, STALE_DAYS, STATE_FILE, TESTING_MD, VERIFICATION_MD, WEIGHT_JSON, WEIGHT_MD, WEIGHT_PROJECT, LOCAL_CACHE, GENERATED, CREATE_ONLY, CREATE_ONLY_DIRS, NOT_COPIED, KEPT, is_kept, SHARED_SET, RULES_DIR, RULES_SKIP, RULES_SKIP_FOLDED, RUNTIME_MAP, SDLC_CREATE, INSTRUCTION_FILE
"""

import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the skill directory, one above this package
SKILLS = os.path.dirname(HERE)
LAST_MIGRATING_VERSION = "3.1.0"  # the last riskrails that converts older trees; I3 names it
EXIT_KEPT_UNREADABLE = 6
REFUSED = "CONFIRM_REFUSED"


def env(name, default=None):
    """RISKRAILS_<name>."""
    return os.environ.get("RISKRAILS_" + name, default)



TEMPLATES = {
    "ai-init": env("TEMPLATES", os.path.join(SKILLS, "ai-init", "templates")),
    "project-init": os.environ.get("CLAUDE_ROUTING_TEMPLATES", os.path.join(SKILLS, "project-init", "templates")),
}
HISTORY = env("HISTORY", os.path.join(HERE, "history"))
# The shared tree every project reads unless it keeps its own copy: installed
# beside the skills as riskrails/ai, or ai/ at the root of a checkout.
PLUGIN_HOME = os.path.dirname(SKILLS)
SHARED = env("SHARED") or next(
    (p for p in (os.path.join(PLUGIN_HOME, "riskrails", "ai"), os.path.join(PLUGIN_HOME, "ai"))
     if os.path.isdir(p)), os.path.join(PLUGIN_HOME, "riskrails", "ai"))
VERSION_FILE = ".ai/VERSION"
ROUTER_FILE = ".ai/AGENTS.md"
STALE_DAYS = 7  # an unclosed task whose last event is older is proposed for cleanup
STATE_FILE = ".ai/state/state.json"
TESTING_MD = ".ai/policies/testing.md"
VERIFICATION_MD = ".ai/policies/verification.md"
WEIGHT_JSON, WEIGHT_MD = ".ai/policies/weight.json", ".ai/policies/weight.md"
WEIGHT_PROJECT = ".ai/policies/weight.project.json"
LOCAL_CACHE = ".ai/local/plugin-update"

# D2. GENERATED targets copied from a template as they are. weight.md is rendered,
# .ai/VERSION is written last, the managed blocks and the runtimes' memory READMEs
# come from the maps below.
GENERATED = (ROUTER_FILE, ".ai/policies/path-guard.json", ".ai/policies/coding.md", ".ai/policies/safety.md",
             ".ai/policies/security.md", TESTING_MD, ".ai/rules/README.md", ".ai/state/README.md")
# Template files created when missing and never touched again: the project's own from then on.
CREATE_ONLY = (VERIFICATION_MD, WEIGHT_PROJECT, ".ai/reports/.gitkeep")
CREATE_ONLY_DIRS = (".ai/project/",)
# Template files that are not copied: written last, the plugin's own table, the human's switch.
NOT_COPIED = (VERSION_FILE, WEIGHT_JSON, WEIGHT_MD, ".ai/policies/dialog.json")
KEPT = (".ai/project/", ".ai/reports/", ".ai/memory/", ".ai/state/", "docs/sdlc/", ".ai/local/memory/",
        WEIGHT_PROJECT, VERIFICATION_MD, ".ai/policies/dialog.json", ".ai/policies/memory.json",
        ".claude/settings.json", ".codex/config.toml", ".gitignore")


def is_kept(path):
    """True for a path update.py never rewrites. A GENERATED path under a KEPT
    directory (.ai/state/README.md) is generated: the two sets are disjoint."""
    if path in GENERATED:
        return False
    return any(path == k or (k.endswith("/") and path.startswith(k)) for k in KEPT)


# The shared set, literally: the plugin's tree must equal it (tested). A project
# copy identical to a shipped version is offered for deletion; an edited one is an override.
SHARED_SET = frozenset((
    ".ai/policies/production.md", ".ai/policies/database.md", ".ai/policies/git.md", ".ai/policies/release.md",
    ".ai/policies/context-management.md", ".ai/policies/tooling.md", ".ai/policies/model-routing.md",
    ".ai/policies/review-economy.md",
    ".ai/agents/context.md", ".ai/agents/discovery.md", ".ai/agents/implementer.md",
    ".ai/agents/planner.md", ".ai/agents/release.md", ".ai/agents/reviewer.md", ".ai/agents/risk.md",
    ".ai/agents/security.md", ".ai/agents/tester.md",
    ".ai/templates/task-context.md", ".ai/templates/impact-report.md", ".ai/templates/review-report.md",
    ".ai/templates/release-report.md", ".ai/templates/architecture-decision.md",
    ".ai/templates/implementation-plan.md",
    ".ai/using-riskrails.md", ".ai/workflows.md",
))
RULES_DIR = ".ai/rules"
# Directories a stale rule block is never hunted in: a dependency's instruction
# file is not ours (the path guard refuses it too), and .git is not text.
# A child holding a .git entry (worktree, nested repository, submodule) is pruned
# too, by the take-back walk (rendered_rules) and by the writer (nested_tree). The
# writer also skips a RULES_SKIP name or a symlinked directory (unwalked_dir), so it
# never writes where the take-back never walks.
RULES_SKIP = {".git", ".ai", "vendor", "node_modules", "bower_components",
              "third_party", "Pods", "site-packages", ".venv", ".pnpm", ".yarn"}
# Compared case-insensitively: on a case-insensitive filesystem `Vendor/` is `vendor/`.
RULES_SKIP_FOLDED = frozenset(n.casefold() for n in RULES_SKIP)

RUNTIME_MAP = {  # the per-runtime layer of the project-init scaffold: template, target, kind
    "claude": [("memory-README.md", ".claude/memory/README.md", "regenerate"),
               ("project-settings.json", ".claude/settings.json", "create")],
    "codex":  [("memory-README.md", ".codex/memory/README.md", "regenerate"),
               ("project-config.toml", ".codex/config.toml", "create")],
    "gemini": [("memory-README.md", ".gemini/memory/README.md", "regenerate")],
    "junie":  [("memory-README.md", ".junie/memory/README.md", "regenerate")],
}
SDLC_CREATE = (("sdlc-README.md", "docs/sdlc/README.md"), ("constitution.md", "docs/sdlc/constitution.md"))
INSTRUCTION_FILE = {  # runtime -> (file, block template, minimal template)
    "claude": ("CLAUDE.md", "CLAUDE.block.md", "CLAUDE.minimal.md"),
    "codex":  ("AGENTS.md", "AGENTS.block.md", "AGENTS.minimal.md"),
    "gemini": ("GEMINI.md", "GEMINI.block.md", "GEMINI.minimal.md"),
    "junie":  (".junie/guidelines.md", "junie-guidelines.block.md",
               "junie-guidelines.minimal.md"),
}

