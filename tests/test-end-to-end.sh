#!/usr/bin/env bash
# The end-to-end suite, now tests/test_end_to_end.py; this wrapper stays until 3.H.
exec env AI_E2E=1 python3 -I -m unittest discover -s "$(dirname "$0")" -p test_end_to_end.py
