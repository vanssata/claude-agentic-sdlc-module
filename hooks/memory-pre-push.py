#!/usr/bin/env python3
"""riskrails memory pre-push validator (spec compact-project-memory §D10, §I5).

  memory-pre-push.py <remote> <url>  < "<lref> <lsha> <rref> <rsha>"…   git hook
  memory-pre-push.py --range OLD..NEW [--repo DIR]                       CI or server
  memory-pre-push.py --tree REV [--repo DIR]                             structure only

Checks the pushed commits' blobs, never the working tree. stderr carries one
line per finding; exit 0 clean, 1 findings (the push stops), 3 the validator
itself failed (fail closed). It writes no file, uses no network and imports
no state.py. A git hook, not a runtime hook: no tool call ever runs it. The
logic is memory_sync.pre_push, which the shim also runs directly where an
install copied skills/ai-task/ but not this file.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "ai-task"))

if __name__ == "__main__":
    try:
        import memory_sync  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        print("memory-pre-push: validator error: %s — run 'state.py memory verify --all'; a human may push "
              "with 'git push --no-verify'" % exc, file=sys.stderr)
        sys.exit(3)
    sys.exit(memory_sync.pre_push_cli(sys.argv[1:]))
