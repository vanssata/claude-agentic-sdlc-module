#!/usr/bin/env python3
"""Codex expert-model gate — kept so old registrations, statuslines and habits keep working.
runtime-gate.py beside it does the work; run as a hook or CLI this execs it with
argv and stdin intact, and imported it exposes the gate bound to the codex runtime."""
import importlib.util
import os
import sys

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runtime-gate.py")
if __name__ == "__main__":
    os.execv(sys.executable, [sys.executable, GATE, "--as", "codex-model-gate", *sys.argv[1:]])
_spec = importlib.util.spec_from_file_location("runtime_gate", GATE)
_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gate)
_gate.configure("codex")
globals().update({k: v for k, v in vars(_gate).items() if not k.startswith("__")})
