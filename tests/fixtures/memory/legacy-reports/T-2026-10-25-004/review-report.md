# Review — T-2026-10-25-004 (T3, solo direct)

## Pass 1 — ai-reviewer, BALANCED (sonnet), bounded

Sensors red before the review: lint (pre-existing, files outside the diff) and duplicates (template ↔ its history blob, by design). Manager probe: review-ledger.md.

### FINDINGS

- [HIGH] H1 A declared directory scores "new", so it never reaches a hard axis — weight.py:166/134/216. `--files src/Payment/` → domain 1 UNKNOWN, W 2 → light; `src/Payment/Foo.php` → domain 2 → full. No test covers a directory. in_scope: yes
- [MEDIUM] M1 The common-word bound (25% of a tree ≥ 20 files) also downgrades real hubs (`state.py` scores 1 here) and cannot tell a hub from a word; the unknown flag is hidden when another file scores 2 — weight.py:145-148. in_scope: yes
- [MEDIUM] M2 Coverage matches an ident as a substring of any basename under the test globs, fixtures included; a short ident (`db`, `app`) is falsely covered — weight.py:200-202. in_scope: yes
- [LOW] L1 Paths outside the root (`/etc/x`, `../x`, a symlink to outside) are accepted and read by the keyword scan — weight.py:216. in_scope: yes
- [LOW] L2 `tree_files` walk fallback and the keyword reads have no deadline; only the grep is bounded — weight.py:80-90, 173. in_scope: yes
- [LOW] L3 Tracebacks: `--declare scope=<5000 digits>`, `--mirror` onto a directory or a read-only dir (tmp left behind), a malformed table — state.py cmd_weight, weight.py:129, 246-247. in_scope: yes
- [LOW] L4 `a.py` and `./a.py` are counted twice (dedupe before relpath) — weight.py:216-217. in_scope: yes
- [INFO] I1 `irreversible_content` shipped but unread — deliberate (2.2a re-score). in_scope: yes

### VERDICT

pass_with_findings — H1 contradicts the hard-axis guarantee for directory input; the rest are heuristics and error handling.

### Remediation R1

Closed by suite run 2 (green): H1 (directory refused), L1 (outside-root and symlink-out refused), L3 (no traceback on a huge declaration, a failed mirror write — tmp removed — or a wrong-shaped table), L4 (dedupe after normalising). Tests: `test_directory_is_refused`, `test_outside_the_root_is_refused`, `test_two_forms_of_one_file_count_once`, `test_odd_input_is_refused_without_a_traceback`.

Deferred, open: M1 (common-word bound vs hubs), M2 (coverage substring match), L2 (walk/read deadline) — heuristic changes, candidates for 2.2a when `weight` starts deciding modes.
