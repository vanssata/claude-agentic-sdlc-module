# Direct-mode diet — staged policy texts (task 2)

Task 2 of `docs/sdlc/specs/direct-mode-diet.md` (§Order of work). Every file
below is protected or frozen for an agent (§Constraints): `.ai/policies/*.json`
always, the rest while a task is in flight. The agent stages the exact text
here as two `git apply` patches; a human applies them with **no task in
flight** (`state.py get --quiet` says `no task in flight`) and commits.

Generated from the tree after diet task 1 (T-2026-10-22-001, uncommitted when
this was written) by reading each target file; nothing here has been applied.

## Two parts, and why

| Part | When | What |
|---|---|---|
| A | now, before diet task 3 | §1 items 1–5 (project examples, mirror, rules, C6, `CLAUDE.md`), §4c (threat model, acceptances), the provenance and scope-guard entries, the pylint line and one new `known-risks.md` entry |
| B | after diet task 4 is committed | the template side of §3b (`review_rounds_max`) and §5c (profile strings, `AGENTS.md:51`), project and shipped template |

Part B describes `state.py test-run --scope all`, `close` finishing steps and
`review_rounds_max`, which only exist once task 4 ships; applied earlier, the
policy would name calls that fail. If one commit matters more than the order,
apply A and B together after task 4 — B is written on top of A.

### Part A — files

- `.ai/policies/risk-tiers.json` — one `"this repository: …"` row appended to
  the `examples` of T2, T3 and T4 (D1). Nothing else moves; the `pipeline`
  floor stays.
- `.ai/policies/risk-tiers.md` — the D1 table under the tier table; header
  hash `sha256:7b96b55a33363347fee45eda6f0ad17956c251ed271c49b1e61c75bb7c8fa747` (the Part-A JSON).
- `.ai/policies/safety.md` — the guards' threat model, two sentences (§4c).
- `.ai/project/known-risks.md` — one rationale section above the first
  affected entry; `Status: accepted (2026-10-22, …)` on "`shell_segments` is
  quadratic…", "One amplifying symlink…", "`realpath`'s line count…", "The
  token pass strips quotes…", "Batched movers…" (its status said "accepted …;
  open"), and on the residuals of "The path guard is quadratic on long lines"
  and "`sh -c` spellings `segments_of` does not read". Three new entries:
  review provenance, the scope guard's reach, and the pylint exit 12 found by
  T-2026-10-22-001 (the lint sensor is red on every task until three
  pre-existing messages go — spec R2 does not hold without it).
- `.ai/rules/hooks.md`, `.ai/rules/skills.md` — new, three rules each. The
  next `/project-update` renders them into `hooks/CLAUDE.md` and
  `skills/CLAUDE.md` (`install.sh` copies `skills/*/` only, so the rendered
  file is not installed).
- `docs/sdlc/constitution.md` — C6.
- `CLAUDE.md` — one line under "Things Claude Code gets wrong".
- `CONTRIBUTING.md` — where pylint comes from.

### Part B — files

- `.ai/policies/risk-tiers.json` and
  `skills/ai-init/templates/.ai/policies/risk-tiers.json` —
  `"review_rounds_max": 2` after `remediation_rounds`; the `solo` profile
  strings `test`, `e2e`, `triage` reworded to the three-call path.
- `.ai/policies/risk-tiers.md` and its template — the tests paragraph names
  `test-run --scope all`, `close` and `review_rounds_max`; header hashes
  `sha256:6361c98f0c3dffe244a63793934cc7798fe0ad7409b884ef912acc3768d79ed4` (project) and `sha256:0719098eb5b7dc8e7a93cc0b0be5ba8349feae7adf0dfe4cdc7a87efe6ef9727` (template).
- `.ai/AGENTS.md:51` and `skills/ai-init/templates/.ai/AGENTS.md:51` — the
  row names `test-run --scope all` and `close` for direct mode.
- Template history: `python3 tools/build-template-history.py` after the patch,
  so `/project-update` recognises the new template versions
  (`tests/test-project-update.sh` fails without it); commit
  `skills/project-update/history/` with the rest.

Task 4 re-reads Part B against the code it ships and regenerates this file if
a call or flag moved.

## Applying

From the repository root, no task in flight:

```bash
F=docs/sdlc/plans/direct-mode-diet-policy-texts.md
part() { awk -v m="<!-- patch:$1 -->" '$0==m{f=1;next} f&&/^```diff$/{p=1;next} p&&/^```$/{exit} p' "$F"; }
part A | git apply --check && part A | git apply      # Part A
part B | git apply --check && part B | git apply && python3 tools/build-template-history.py   # Part B, after task 4
bash tests/run-all.sh                                 # then commit
```

`/ai-status` should then report the risk-tier mirror current.

Rollback: `git revert` of the commit.

## Part A — apply now

<!-- patch:A -->
```diff
diff --git a/.ai/policies/risk-tiers.json b/.ai/policies/risk-tiers.json
--- a/.ai/policies/risk-tiers.json
+++ b/.ai/policies/risk-tiers.json
@@ -214,7 +214,8 @@
       "examples": [
         "an isolated admin screen or form",
         "a new field on an existing form, a grid column or filter",
-        "a small isolated feature that changes no existing process"
+        "a small isolated feature that changes no existing process",
+        "this repository: a change that moves no guard decision and no state.py refusal — skill or agent text, usage-report, installer paths, performance work that keeps the guard golden byte-identical"
       ],
       "model_tier": "BALANCED",
       "stages_required": [
@@ -241,7 +242,8 @@
         "a new resource: entity, repository, form, grid, routes, menu, translations",
         "a non-critical API extension",
         "a new service with limited blast radius",
-        "anything that adds and presents data without changing an existing process"
+        "anything that adds and presents data without changing an existing process",
+        "this repository: a change that adds a decision or a refusal — a new deny, a new sensor, a new state.py check — or changes a deny's reason text, the guard golden re-recorded"
       ],
       "model_tier": "BALANCED",
       "stages_required": [
@@ -272,7 +274,8 @@
         "asynchronous processing",
         "an important integration",
         "a schema migration that adds to an existing table",
-        "configuration and dependencies"
+        "configuration and dependencies",
+        "this repository: a change that allows what was denied or weakens a refusal; one that changes the approval path (approve, questions --sync, AI_UNATTENDED, review_status transitions); one that changes how user projects are installed or migrated (install.sh, the project-update merge, tools/)"
       ],
       "model_tier": "STRONG",
       "stages_required": [
diff --git a/.ai/policies/risk-tiers.md b/.ai/policies/risk-tiers.md
--- a/.ai/policies/risk-tiers.md
+++ b/.ai/policies/risk-tiers.md
@@ -1,4 +1,4 @@
-<!-- generated from risk-tiers.json sha256:616a6da3c59073926c5ece428efa251fbe539d25a53bcf50be67522f44848368 -->
+<!-- generated from risk-tiers.json sha256:7b96b55a33363347fee45eda6f0ad17956c251ed271c49b1e61c75bb7c8fa747 -->
 <!-- If /ai-status reports this hash as stale, risk-tiers.json changed and this
      mirror did not. The JSON file is the source of truth; update this by hand. -->
 
@@ -23,6 +23,22 @@
 | **T4** | shared domain behaviour and processes: shared services, orders, workflows, async processing, an important integration, a schema migration that adds to a table, configuration and dependencies | no — the human reviews it in plan mode | yes | yes, on STRONG | when auth or personal data is touched | yes |
 | **T5** | payments, accounting, tax, fiscal, authentication, authorization, order state transitions, customer data, external financial systems | yes | yes | yes | yes | yes |
 | **T6** | migration strategy, infrastructure, Kubernetes, production deployment, data migration, destructive schema change, cross-system migration | yes | yes | yes | yes | yes |
+
+**In this repository** — the `examples` that start with "this repository:" in
+`risk-tiers.json`. They refine the rows above and win where they speak; "take
+the higher" decides between two generic rows, never over one of these. The
+plugin is a developer tool: a change to its hooks, skills or state machine is
+tiered by what it does to a user project's decisions, never by its being a
+process (constitution C6).
+
+| Tier | In this repository |
+|---|---|
+| **T2** | moves no guard decision and no `state.py` refusal: skill or agent text, `usage-report`, installer paths, performance work that keeps the guard golden byte-identical |
+| **T3** | **adds** a decision or a refusal — a new deny, a new sensor, a new `state.py` check — or changes a deny's reason text, golden re-recorded |
+| **T4** | **allows what was denied** or weakens a refusal; changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, `review_status` transitions); changes how user projects are installed or migrated (`install.sh`, the `project-update` merge, `tools/`) |
+
+The `pipeline` floor is unchanged: `.ai/policies/**`, `.ai/workflows/**`,
+`.claude/**`, `.codex/**`, `CLAUDE.md` and `AGENTS.md` stay T4 by scope.
 
 ## Which model works on it
 
diff --git a/.ai/policies/safety.md b/.ai/policies/safety.md
--- a/.ai/policies/safety.md
+++ b/.ai/policies/safety.md
@@ -43,6 +43,12 @@
 an agent that behaves correctly only because a hook is watching is not behaving
 correctly. The rules above hold whether or not a hook enforces them.
 
+**The guards' threat model.** The guards defend against an agent's mistakes — a
+careless `rm`, a write to a frozen policy during a task, a commit with a
+secret — not against an agent that constructs a command to exhaust them. A
+command built to time the guard out is visible in the transcript and in the
+journal, and the human gate at T4+ is the boundary for anything that matters.
+
 ## Evidence labels
 
 Anything an agent writes into `.ai/project/` carries one of four labels:
diff --git a/.ai/project/known-risks.md b/.ai/project/known-risks.md
--- a/.ai/project/known-risks.md
+++ b/.ai/project/known-risks.md
@@ -60,6 +60,26 @@
 - **Suggested fix**: deny or skip the ERE for a line over a fixed length that contains both `update` and `--co`.
 - **Status**: fixed (T-2026-10-15-003) — a line over 16384 characters that holds `--co`, `--ap` and either `update` or a `$` is denied before `CONFIRM_RE` runs (200 KB: ~80 ms). The first version required `update` only; the security review timed a 64 KB `$U --co …` line at 12.5 s past it, and the adversarial review found a false deny on a minified-CSS heredoc full of `--color` — both fixed in remediation R2 and pinned in `tests/test-ai-path-guard.sh`. Measured on the way: a 200 KB payload cannot be built with `jq --arg` (one exec argument is capped at 128 KB), which made an earlier test look green. Residuals: under 16384 characters `CONFIRM_RE` with a variable head takes up to ~0.8 s; a long heredoc that holds `--co`, `--ap` and a `$` is denied (err on the deny side); the rest of the guard is slow on any long line — see the next entry.
 
+## Guard threat model: constructed-input findings are accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)
+
+> The guards defend against an agent's mistakes — a careless `rm`, a write to
+> a frozen policy during a task, a commit with a secret — not against an agent
+> that constructs a command to exhaust them. A command built to time the guard
+> out is visible in the transcript and in the journal, and the human gate at
+> T4+ is the boundary for anything that matters. Findings that need such a
+> command are accepted here and do not open a task.
+
+This covers, below: the `sh -c`/`eval` residual of "The path guard is quadratic
+on long lines", the remaining spellings of "`sh -c` spellings `segments_of`
+does not read", "`shell_segments` is quadratic on one long segment", "One
+amplifying symlink keeps `realpath -m` past the hook timeout", "`realpath`'s
+line count can balance while its lines are misaligned", "Batched movers cost a
+few µs more per segment, near the clock" and "The token pass strips quotes one
+character at a time". Entries already fixed are not touched. What happens when
+a guard runs past the runtime's 10 s hook timeout (`settings.common.json:45`)
+is the runtime's rule, not the guard's; this acceptance does not claim the
+guard fails closed. The same threat model is in `.ai/policies/safety.md`.
+
 ## The path guard is quadratic on long lines
 
 - **Found**: 2026-10-15, by T-2026-10-15-003 (while testing the long-line `--confirm-delete` fix)
@@ -67,7 +87,7 @@
 - **What could go wrong**: a benign `echo <40 KB>` takes ~7.5 s in the hook, 10 KB ~0.5 s; 200 KB would take minutes. Past the 10 s hook timeout, if the runtime treats a timeout as non-blocking, a padded command naming a protected path runs (inferred, not observed).
 - **How likely / how bad**: deliberate padding, or a very long generated command; the deny side of every path rule is lost for that call.
 - **Suggested fix**: a single length cap at the top of the Bash branch (deny over N characters when the line names a protected or sensitive pattern's literal, allow otherwise), or find the quadratic loop and make it linear.
-- **Status**: fixed (T-2026-10-15-004) except the `sh -c`/`eval` re-segmentation — see "Padded `sh -c` segments still outrun the path guard" below. Causes, profiled: (1) `[[ =~ ]]` (glibc regexec, unanchored search restarting at every offset) on a long line; (2) a fork-heavy pass per token and per mover operand; (3) found during the fix: in a UTF-8 locale GNU grep re-verifies a line its DFA accepts with the same regexec (a 200 KB line that *matches* took > 20 s; in C, 12 ms), and bash's `${s%$'\n'}`, `${w#*=}` and `${w##*/}` cost 0.7 s, 9.5 s and 4.5 s on 140–200 KB. Fix: `ere_match` hands a subject over 4096 characters to `LC_ALL=C grep -aqE -f <(…)` through a here-string (`hooks/lib/ai-hook-common.sh`), so the approve, context-guard, VERBS, CONFIRM and fast-path rules and the git/scope guards are linear; `deny()` passes its reason to jq on stdin with a fixed deny as fallback (a reason over 128 KB used to fail exec and allow — older than this task, found by the STRONG review); the movers pass and the token loop pre-filter every operand/token in one bytewise grep (`loose_hits`: absolute, resolved and after-`=` paths), so an operand or a word that matches nothing costs no fork and prose that matches nothing is not counted; when `realpath -m` drops a line (a symlink loop) operands are resolved one at a time instead of falling back to the unresolved list; `covers_work` decides covers_protected's work in process; an operand or token over 4096 characters (no such path opens: ENAMETOOLONG) is denied when it holds a glob or expansion character or its absolute form matches a loose pattern, and is otherwise a stand-in that matches nothing; caps deny past 64 operands that need `classify`, 16 directory scans, 256 tokens that hit the pre-filter, or 6 s of hook time (`SECONDS`, checked before every counted unit and, in process, once per operand and per token in every loop of the hook's own shell — remediation R2, after the re-review timed 25000 plain `mv` sources at 14 s) — "…names more paths than the guard can check within its timeout…". Measured on this machine, before → after: `echo <40 KB>` 6.5 s → 0.07 s; `sh -c '<40 KB>'`, `sed -n 1p <40 KB>` 6.5 s → 0.07–0.3 s; 200 KB `echo` + `cat .env` → denied in 0.3 s; `rm -f` + 3000 names 350 s → 0.7 s; the same + `.ai/state/current.json` 291 s → denied in 0.7 s; `rm -f <200 KB>/… .ai/state/current.json` → denied in 0.65 s (HEAD: minutes); `cp <140 KB>.json x.json .ai/state/` → denied in 0.4 s (HEAD: allowed); 63 frozen operands + 16 directories of 50 frozen files + a policy file → denied in 6.4 s by the clock (HEAD 11.1 s); 300-word heredoc or commit message mentioning `.env.example` → allowed in 0.09 s. `mv` of 25000 sources + `.ai/state/current.json` → denied in 5.7 s. Adversarial review (STRONG): 1 BLOCKER, 4 HIGH, 2 MEDIUM, fixed in remediation R1; the scoped re-review closed six, found the uncounted-work BLOCKER (fixed in R2) and three LOWs (residuals below); all and pinned in the "padded line" section of `tests/test-ai-path-guard.sh`; `tests/test-guard-characterization.sh` stays byte-identical. Residuals: the 6 s clock and the caps assume one unit of work (a scan of ≤ 20000 entries, ≤ 50 classify) finishes within the remaining 4 s — a much slower host has less headroom; an ordinary `rm -rf` of more than 16 existing directories, or a command naming more than 256 guarded-looking paths, is now denied (deny side, split the command); a single operand or token over 4096 characters without glob characters is not checked as a path (it cannot open); a project policy whose joined patterns exceed 128 KB is fine now (patterns go through `-f`), but `[[ =~ ]]` below 4096 characters still compiles them per call; matching is bytewise over 4096 characters and in every `loose_hits` pre-filter (all mover operands and tokens, any length), so a single-character wildcard (`.`, a one-character bracket, a POSIX class) in a project pattern sees one byte of a multibyte character and can miss — the default patterns have none; prose that does look like guarded paths still counts against the token cap (a minified-JS heredoc with 400 `process.env` mentions is denied with the cap message, HEAD allowed it in 6.4 s); a token over 4096 characters holding `+ @ ! ~ { } $` or another glob/expansion character is denied on any line past the fast path (a long base64 or minified line beside a guarded mention) — all three deny side; under 4096 characters `[[ =~ ]]` still runs (≤ ~0.1 s). Observation, not fixed: the "directory that holds runtime configuration" deny prints `task ?` instead of the task id, because `covers_protected` runs in `$( )` and `task_in_flight`'s `AI_TASK_ID` is lost with the subshell; the characterization golden pins it.
+- **Status**: fixed (T-2026-10-15-004) except the `sh -c`/`eval` re-segmentation, whose residual is accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md) — see "Padded `sh -c` segments still outrun the path guard" below. Causes, profiled: (1) `[[ =~ ]]` (glibc regexec, unanchored search restarting at every offset) on a long line; (2) a fork-heavy pass per token and per mover operand; (3) found during the fix: in a UTF-8 locale GNU grep re-verifies a line its DFA accepts with the same regexec (a 200 KB line that *matches* took > 20 s; in C, 12 ms), and bash's `${s%$'\n'}`, `${w#*=}` and `${w##*/}` cost 0.7 s, 9.5 s and 4.5 s on 140–200 KB. Fix: `ere_match` hands a subject over 4096 characters to `LC_ALL=C grep -aqE -f <(…)` through a here-string (`hooks/lib/ai-hook-common.sh`), so the approve, context-guard, VERBS, CONFIRM and fast-path rules and the git/scope guards are linear; `deny()` passes its reason to jq on stdin with a fixed deny as fallback (a reason over 128 KB used to fail exec and allow — older than this task, found by the STRONG review); the movers pass and the token loop pre-filter every operand/token in one bytewise grep (`loose_hits`: absolute, resolved and after-`=` paths), so an operand or a word that matches nothing costs no fork and prose that matches nothing is not counted; when `realpath -m` drops a line (a symlink loop) operands are resolved one at a time instead of falling back to the unresolved list; `covers_work` decides covers_protected's work in process; an operand or token over 4096 characters (no such path opens: ENAMETOOLONG) is denied when it holds a glob or expansion character or its absolute form matches a loose pattern, and is otherwise a stand-in that matches nothing; caps deny past 64 operands that need `classify`, 16 directory scans, 256 tokens that hit the pre-filter, or 6 s of hook time (`SECONDS`, checked before every counted unit and, in process, once per operand and per token in every loop of the hook's own shell — remediation R2, after the re-review timed 25000 plain `mv` sources at 14 s) — "…names more paths than the guard can check within its timeout…". Measured on this machine, before → after: `echo <40 KB>` 6.5 s → 0.07 s; `sh -c '<40 KB>'`, `sed -n 1p <40 KB>` 6.5 s → 0.07–0.3 s; 200 KB `echo` + `cat .env` → denied in 0.3 s; `rm -f` + 3000 names 350 s → 0.7 s; the same + `.ai/state/current.json` 291 s → denied in 0.7 s; `rm -f <200 KB>/… .ai/state/current.json` → denied in 0.65 s (HEAD: minutes); `cp <140 KB>.json x.json .ai/state/` → denied in 0.4 s (HEAD: allowed); 63 frozen operands + 16 directories of 50 frozen files + a policy file → denied in 6.4 s by the clock (HEAD 11.1 s); 300-word heredoc or commit message mentioning `.env.example` → allowed in 0.09 s. `mv` of 25000 sources + `.ai/state/current.json` → denied in 5.7 s. Adversarial review (STRONG): 1 BLOCKER, 4 HIGH, 2 MEDIUM, fixed in remediation R1; the scoped re-review closed six, found the uncounted-work BLOCKER (fixed in R2) and three LOWs (residuals below); all and pinned in the "padded line" section of `tests/test-ai-path-guard.sh`; `tests/test-guard-characterization.sh` stays byte-identical. Residuals: the 6 s clock and the caps assume one unit of work (a scan of ≤ 20000 entries, ≤ 50 classify) finishes within the remaining 4 s — a much slower host has less headroom; an ordinary `rm -rf` of more than 16 existing directories, or a command naming more than 256 guarded-looking paths, is now denied (deny side, split the command); a single operand or token over 4096 characters without glob characters is not checked as a path (it cannot open); a project policy whose joined patterns exceed 128 KB is fine now (patterns go through `-f`), but `[[ =~ ]]` below 4096 characters still compiles them per call; matching is bytewise over 4096 characters and in every `loose_hits` pre-filter (all mover operands and tokens, any length), so a single-character wildcard (`.`, a one-character bracket, a POSIX class) in a project pattern sees one byte of a multibyte character and can miss — the default patterns have none; prose that does look like guarded paths still counts against the token cap (a minified-JS heredoc with 400 `process.env` mentions is denied with the cap message, HEAD allowed it in 6.4 s); a token over 4096 characters holding `+ @ ! ~ { } $` or another glob/expansion character is denied on any line past the fast path (a long base64 or minified line beside a guarded mention) — all three deny side; under 4096 characters `[[ =~ ]]` still runs (≤ ~0.1 s). Observation, not fixed: the "directory that holds runtime configuration" deny prints `task ?` instead of the task id, because `covers_protected` runs in `$( )` and `task_in_flight`'s `AI_TASK_ID` is lost with the subshell; the characterization golden pins it.
 
 ## tests/test-project-update.sh is red on the uncommitted tier-model v2 tree (found 2026-10-13, outside T1 task on test-runtime-gate.sh)
 - **Where**: `tests/test-project-update.sh:79,90,109,114` against `skills/ai-init/templates/.ai/policies/risk-tiers.json` as delivered after T-2026-10-13-002 closed (post-close JSON hand-over at 17:58, after its last suite run at 17:40).
@@ -142,7 +162,7 @@
 - **What could go wrong**: KNOWN FACT (review probe, HEAD and new alike) — each of these is allowed although the string it runs removes `.ai/state/current.json`: `bash --norc -c '…'`, `bash -o posix -c '…'`, `sh -c -- '…'`, `sh -c 2>/dev/null '…'`, `'sh' -c '…'`, and `set -- '/bin/sh,-c,…'; IFS=,; $1`, or the same split on a multibyte character that is no blank to glibc, such as U+2007 or U+00A0 (T-2026-10-20-002; `tests/test-ai-path-guard.sh` pins U+2007 as allowed).
 - **How likely / how bad**: a deliberately reworded command; the guard is a backstop, not a security boundary (file header), but each is a missed deny.
 - **Suggested fix**: accept long options and `-o <name>` before `-c`, `--` and a redirection between `-c` and the string, and a quoted command word; the `IFS` split is out of reach for a text match. Its own T4 hooks task; the characterization golden must stay identical.
-- **Status**: fixed in T-2026-10-20-003 for the option, redirection and command-word spellings; the rest stays open. KNOWN FACT — `SH_OPT` (`hooks/ai-path-guard.sh:433`) is the words bash takes before the `-c` cluster without making one the string, `SH_COPT` (`:434`) one it takes after it. Either side, a flag (`SH_FLAG`, `:431`): a short cluster, `-`, `+e`, not ending in `o`/`O`; `--`. Or an option that takes a word (`SH_ARG`, `:432`): a cluster that ends in `o`/`O` and its name (`-o posix`, `-eo pipefail`, `+O extglob`); a redirection (`>`, `>>`, `>&`, `<`, `<>`, `<&`, `&>`, `&>>`, an fd number before it) and its target, joined or apart. Before `-c` only, as bash rejects them after it (`bash -c --norc 'x'`: `--: invalid option`): a long option, `--rcfile`/`--init-file` and its file. A name, file or target (`SH_WORD`, `:430`) is one word of bare, quoted and backslashed pieces (`2>"$HOME"/x`, `2>/tmp/x\ y`); only a backslashed piece holds a blank: bare or in quotes (`SH_NB`, `:429`) a piece takes no ASCII blank and no byte `E1`–`E3` but `SH_MB` (`:428`), the characters of those lead bytes that are not in `SH_BLANK` (`…`, `あ`, `→`, U+1681 stay inside a target). So no word runs past the blank after a match start's `sh`, and a quoted target or name with a blank is not read (still open, below). No two alternatives fit one word: glibc reports the first that fits, and a bare `-o` had left `posix '…'` as the string. `SH_RE` (`:435`) takes any number of flags before `-c`, as HEAD did, and at most 8 options that take a word, at most 4 words after it, and a command word with a leading quote or backslash and a trailing quote; the string is still its last group. A flag holds no match start, so a run of them is read by at most the 9 starts whose options reach it. `segments_of` (`:463`) reads every `sh -c` in a segment, not only the leftmost: a match can begin at an argument (`find . -name 'sh' -exec sh -c '…'`, where `-exec` is a cluster with a `c`), and `sh_string` hands back the text after the matched command word for the next one; a further string that is not quoted is cut to its first `SH_WORD`, which stops at a quoted blank too (`rm" -f <S>"` reads `rm`), so `-exec sh -c rm\ -f\ <S>`, `rm" -f <S>"` and `"rm -f "<S>` stay allowed there, as on HEAD; each further string counts against the same 64 and 6 s clock, and at most 8 follow one segment, past either the hook denies (`WHY_WORK_CAP`). Before → after (`tests/test-ai-path-guard.sh`, T-2026-10-20-003 block and its review cases), each with `'rm -f .ai/state/current.json'`, allow → deny: `bash --norc -c`, `bash -o posix -c`, `bash +o posix -c`, `bash -O extglob -c`, `bash -eo pipefail -c`, `bash --rcfile /dev/null -c`, `sh -c --`, `sh -c -`, `sh -c -e`, `sh -c 2>/dev/null`, `sh -c 2> /dev/null`, `sh -c >/dev/null 2>&1`, `sh -c &>/dev/null`, `sh </dev/null -c`, `'sh' -c`, `"bash" -c`, `\sh -c`, `'/bin/sh' -c`, `bash -c -o posix`, `bash -c +O extglob`, `bash -c -eo pipefail`, `bash -c -e -o pipefail`, `bash -c 2>/dev/null -o posix`, `sh -c 2>"$HOME"/x`, `sh -c 2>/tmp/x\ y` (bash runs the string in all, checked), and, by probe, `find . -name sh -exec sh -c`, and `sh -c 'echo; bash -c "…"'` (a `sh -c` inside the string, read as a further match; HEAD allow, measured by the second review pass); also `bash -o posix -e ×9 -O extglob -c`, and `bash 2>/tmp/…あ→<U+1681>x -c` (deny on the first pass's tree too); deny, as on HEAD (the second review pass had found them allowed): `bash -e ×9 -c`, `bash -e ×20 -c`, `bash -e -u -x -v -e -u -x -v -e -c`, `sh -a -b -e -f -h -m -u -v -x -c`; deny, unchanged: `find . -name 'sh' -exec sh -c`, `find . -name sh 2>/dev/null -exec sh -c`, `find . -path '*/sh' -exec bash -c`, `sudo -u 'sh' -c x bash -c` (the first review pass had turned these to allow); allow, unchanged: eight of them with `'rm -f a.txt'`, `bash -e ×9 -c 'rm -f a.txt'`, `sh -c 'x' 2>/dev/null`, `sh -c echo -n hi`. Probe, 184 commands, HEAD 21faea3 against the first pass's tree: no deny → allow among them; the second review pass found 9 or more flags before `-c` deny → allow, closed above. The fourth review pass, 768 commands with a quoted-blank target or name, HEAD against this tree: no deny → allow; 630 of them deny on the second pass's tree and allow on this one, given up with the linear `SH_WORD`. Regex alone at 200 KB, first pass's tree: 6–28 ms on every ASCII padding the review tried (` sh >`, ` sh <`, ` >/sh`, ` sh -O`, ` sh &>`, ` sh -o`, ` bash 2>`, ` 2>/bin/sh`, ` sh --rcfile`, ` sh 2>`, ` -a`, ` -o x`, ` 2> x`, ` --x`, ` -c`, ` sh -c`, ` \x`), each ending in ` X sh -c 'rm y'`; unbounded, the first review pass took 13 s on ` sh 2>`. Not on a multibyte padding: the second review pass measured `U+3000 sh U+3000 -o U+3000 x` at 11.5 s for 280 KB (HEAD 9 ms), as a word ran across U+3000. Nor on a quoted one: the third review pass found that ` sh 2>\''` kept every start's target inside a quote to the end of the line — `\'` is escaped outside a quote, closes `'…'` and is literal in `"…"`, and the next `'` re-opens — regex alone 11.4 s at 198 KB (17.9 s at 286 KB with U+3000 blanks), the hook 10.3 s (manager probe, the second pass's tree); with no blank in a quoted piece, 11 ms and 0.75 s, and 9–24 ms up to 1.1 MB (fourth review pass: linear, and a structured fuzzer found nothing on this tree); `echo` + ` sh 2>\''` ×22000 + ` X sh -c x; rm -f <the state file>` deny, and the same with U+3000 blanks ×11000 and `rm -f a.txt` allow, are timed tests now. The hook at 140 KB, first pass's tree → this tree: `echo` + `U+3000 sh U+3000 -o U+3000 x` ×10000 + ` X sh -c x; rm -f <the state file>` deny 3.6 s → 0.50 s, `echo` + `U+3000 sh U+3000 2>x` ×13000 + ` X sh -c x; rm -f a.txt` allow, 4.8 s → 0.53 s; both timed tests now. The hook, padded (HEAD 21faea3 → this tree, one run each): `echo` + ` sh 2>` ×33333 + ` X sh -c x; rm -f <the state file>` deny 0.76 s → 0.72 s (first pass 14.4 s, now a timed test); the same with ` 2>/sh` 0.74 s → 0.72 s; `echo` + ` sh -c` ×33333 + ` x; rm -f a.txt` allow 1.2 s → deny 1.2 s, ×66666 allow 3.7 s → deny 3.8 s, `echo` + ` sh -c 'x'` ×20000 + `; rm -f a.txt` allow 0.77 s → deny 0.84 s (the 8-per-segment cap); `sh -c x; ` ×6000 + the state file deny 0.28 s → 0.39 s; `x;` ×100000 + `rm -f a.txt` allow 0.38 s → 0.35 s; `sh -c '<200 KB>'; rm -f a.txt` allow 1.3 s → 1.3 s; `sh -c '<400 KB>'; rm -f a.txt` allow 4.2 s → 4.2 s. `tests/test-guard-characterization.sh` byte-identical. Deny side, by design: the guard reads more than bash runs — in `bash -c -- -x '…'` bash runs `-x` and the guard reads `'…'`; a quoted `"sh -c '…'"` inside an `echo` or a `grep` pattern is read as a command (`echo "use 'bash' -c 'rm …' never"`, `grep -n "bash -o posix -c 'rm …'" docs/x.md`, `echo sh -c -- 'rm …'` now deny); a `sh -c` inside a quoted string is read too. Allowed, as bash fails on them: `bash -c -o '…'` (the string is the option name), `bash -c --norc '…'`, `bash -c --rcfile /dev/null '…'`. Still open: the `IFS` split (`IFS=,`, U+2007, U+00A0); a quoted option word (`sh '-c' '…'`, `sh "-c" '…'`); `-o` after the `c` in the cluster (`bash -co posix '…'`); a command word split by quotes (`s'h'`, `"ba"sh`); any indirection (`$x`, `"$@"`, `r\m`); `>|` beside `-c` (`sh -c >|/dev/null '…'`: `shell_segments` splits at the `|`); a redirection target or option name with a blank inside quotes (`bash 2>'/tmp/a b' -c`, `bash -c 2>"/tmp/a b"`, `bash -o 'pos ix' -c`; HEAD allow, the second pass's tree deny, given up for the linear regex; `tests/test-ai-path-guard.sh` pins the first as allowed), and a quoted piece holding an `E1`–`E3` byte that is not valid UTF-8; more than 8 options that take a word before `-c`, or more than 4 words after it (`bash -c -e -u -x -v -o pipefail '…'`). Deny side, open (second review pass, LOW): 10 or more `sh -c` in one segment are denied by the 8-per-segment cap with `WHY_WORK_CAP`'s wording (`find . -exec sh -c '…' _ {} \;` ×10, a `docker run … bash -c '…'` holding 10 shell words), HEAD allow.
+- **Status**: fixed in T-2026-10-20-003 for the option, redirection and command-word spellings; the rest is accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md). KNOWN FACT — `SH_OPT` (`hooks/ai-path-guard.sh:433`) is the words bash takes before the `-c` cluster without making one the string, `SH_COPT` (`:434`) one it takes after it. Either side, a flag (`SH_FLAG`, `:431`): a short cluster, `-`, `+e`, not ending in `o`/`O`; `--`. Or an option that takes a word (`SH_ARG`, `:432`): a cluster that ends in `o`/`O` and its name (`-o posix`, `-eo pipefail`, `+O extglob`); a redirection (`>`, `>>`, `>&`, `<`, `<>`, `<&`, `&>`, `&>>`, an fd number before it) and its target, joined or apart. Before `-c` only, as bash rejects them after it (`bash -c --norc 'x'`: `--: invalid option`): a long option, `--rcfile`/`--init-file` and its file. A name, file or target (`SH_WORD`, `:430`) is one word of bare, quoted and backslashed pieces (`2>"$HOME"/x`, `2>/tmp/x\ y`); only a backslashed piece holds a blank: bare or in quotes (`SH_NB`, `:429`) a piece takes no ASCII blank and no byte `E1`–`E3` but `SH_MB` (`:428`), the characters of those lead bytes that are not in `SH_BLANK` (`…`, `あ`, `→`, U+1681 stay inside a target). So no word runs past the blank after a match start's `sh`, and a quoted target or name with a blank is not read (still open, below). No two alternatives fit one word: glibc reports the first that fits, and a bare `-o` had left `posix '…'` as the string. `SH_RE` (`:435`) takes any number of flags before `-c`, as HEAD did, and at most 8 options that take a word, at most 4 words after it, and a command word with a leading quote or backslash and a trailing quote; the string is still its last group. A flag holds no match start, so a run of them is read by at most the 9 starts whose options reach it. `segments_of` (`:463`) reads every `sh -c` in a segment, not only the leftmost: a match can begin at an argument (`find . -name 'sh' -exec sh -c '…'`, where `-exec` is a cluster with a `c`), and `sh_string` hands back the text after the matched command word for the next one; a further string that is not quoted is cut to its first `SH_WORD`, which stops at a quoted blank too (`rm" -f <S>"` reads `rm`), so `-exec sh -c rm\ -f\ <S>`, `rm" -f <S>"` and `"rm -f "<S>` stay allowed there, as on HEAD; each further string counts against the same 64 and 6 s clock, and at most 8 follow one segment, past either the hook denies (`WHY_WORK_CAP`). Before → after (`tests/test-ai-path-guard.sh`, T-2026-10-20-003 block and its review cases), each with `'rm -f .ai/state/current.json'`, allow → deny: `bash --norc -c`, `bash -o posix -c`, `bash +o posix -c`, `bash -O extglob -c`, `bash -eo pipefail -c`, `bash --rcfile /dev/null -c`, `sh -c --`, `sh -c -`, `sh -c -e`, `sh -c 2>/dev/null`, `sh -c 2> /dev/null`, `sh -c >/dev/null 2>&1`, `sh -c &>/dev/null`, `sh </dev/null -c`, `'sh' -c`, `"bash" -c`, `\sh -c`, `'/bin/sh' -c`, `bash -c -o posix`, `bash -c +O extglob`, `bash -c -eo pipefail`, `bash -c -e -o pipefail`, `bash -c 2>/dev/null -o posix`, `sh -c 2>"$HOME"/x`, `sh -c 2>/tmp/x\ y` (bash runs the string in all, checked), and, by probe, `find . -name sh -exec sh -c`, and `sh -c 'echo; bash -c "…"'` (a `sh -c` inside the string, read as a further match; HEAD allow, measured by the second review pass); also `bash -o posix -e ×9 -O extglob -c`, and `bash 2>/tmp/…あ→<U+1681>x -c` (deny on the first pass's tree too); deny, as on HEAD (the second review pass had found them allowed): `bash -e ×9 -c`, `bash -e ×20 -c`, `bash -e -u -x -v -e -u -x -v -e -c`, `sh -a -b -e -f -h -m -u -v -x -c`; deny, unchanged: `find . -name 'sh' -exec sh -c`, `find . -name sh 2>/dev/null -exec sh -c`, `find . -path '*/sh' -exec bash -c`, `sudo -u 'sh' -c x bash -c` (the first review pass had turned these to allow); allow, unchanged: eight of them with `'rm -f a.txt'`, `bash -e ×9 -c 'rm -f a.txt'`, `sh -c 'x' 2>/dev/null`, `sh -c echo -n hi`. Probe, 184 commands, HEAD 21faea3 against the first pass's tree: no deny → allow among them; the second review pass found 9 or more flags before `-c` deny → allow, closed above. The fourth review pass, 768 commands with a quoted-blank target or name, HEAD against this tree: no deny → allow; 630 of them deny on the second pass's tree and allow on this one, given up with the linear `SH_WORD`. Regex alone at 200 KB, first pass's tree: 6–28 ms on every ASCII padding the review tried (` sh >`, ` sh <`, ` >/sh`, ` sh -O`, ` sh &>`, ` sh -o`, ` bash 2>`, ` 2>/bin/sh`, ` sh --rcfile`, ` sh 2>`, ` -a`, ` -o x`, ` 2> x`, ` --x`, ` -c`, ` sh -c`, ` \x`), each ending in ` X sh -c 'rm y'`; unbounded, the first review pass took 13 s on ` sh 2>`. Not on a multibyte padding: the second review pass measured `U+3000 sh U+3000 -o U+3000 x` at 11.5 s for 280 KB (HEAD 9 ms), as a word ran across U+3000. Nor on a quoted one: the third review pass found that ` sh 2>\''` kept every start's target inside a quote to the end of the line — `\'` is escaped outside a quote, closes `'…'` and is literal in `"…"`, and the next `'` re-opens — regex alone 11.4 s at 198 KB (17.9 s at 286 KB with U+3000 blanks), the hook 10.3 s (manager probe, the second pass's tree); with no blank in a quoted piece, 11 ms and 0.75 s, and 9–24 ms up to 1.1 MB (fourth review pass: linear, and a structured fuzzer found nothing on this tree); `echo` + ` sh 2>\''` ×22000 + ` X sh -c x; rm -f <the state file>` deny, and the same with U+3000 blanks ×11000 and `rm -f a.txt` allow, are timed tests now. The hook at 140 KB, first pass's tree → this tree: `echo` + `U+3000 sh U+3000 -o U+3000 x` ×10000 + ` X sh -c x; rm -f <the state file>` deny 3.6 s → 0.50 s, `echo` + `U+3000 sh U+3000 2>x` ×13000 + ` X sh -c x; rm -f a.txt` allow, 4.8 s → 0.53 s; both timed tests now. The hook, padded (HEAD 21faea3 → this tree, one run each): `echo` + ` sh 2>` ×33333 + ` X sh -c x; rm -f <the state file>` deny 0.76 s → 0.72 s (first pass 14.4 s, now a timed test); the same with ` 2>/sh` 0.74 s → 0.72 s; `echo` + ` sh -c` ×33333 + ` x; rm -f a.txt` allow 1.2 s → deny 1.2 s, ×66666 allow 3.7 s → deny 3.8 s, `echo` + ` sh -c 'x'` ×20000 + `; rm -f a.txt` allow 0.77 s → deny 0.84 s (the 8-per-segment cap); `sh -c x; ` ×6000 + the state file deny 0.28 s → 0.39 s; `x;` ×100000 + `rm -f a.txt` allow 0.38 s → 0.35 s; `sh -c '<200 KB>'; rm -f a.txt` allow 1.3 s → 1.3 s; `sh -c '<400 KB>'; rm -f a.txt` allow 4.2 s → 4.2 s. `tests/test-guard-characterization.sh` byte-identical. Deny side, by design: the guard reads more than bash runs — in `bash -c -- -x '…'` bash runs `-x` and the guard reads `'…'`; a quoted `"sh -c '…'"` inside an `echo` or a `grep` pattern is read as a command (`echo "use 'bash' -c 'rm …' never"`, `grep -n "bash -o posix -c 'rm …'" docs/x.md`, `echo sh -c -- 'rm …'` now deny); a `sh -c` inside a quoted string is read too. Allowed, as bash fails on them: `bash -c -o '…'` (the string is the option name), `bash -c --norc '…'`, `bash -c --rcfile /dev/null '…'`. Still open: the `IFS` split (`IFS=,`, U+2007, U+00A0); a quoted option word (`sh '-c' '…'`, `sh "-c" '…'`); `-o` after the `c` in the cluster (`bash -co posix '…'`); a command word split by quotes (`s'h'`, `"ba"sh`); any indirection (`$x`, `"$@"`, `r\m`); `>|` beside `-c` (`sh -c >|/dev/null '…'`: `shell_segments` splits at the `|`); a redirection target or option name with a blank inside quotes (`bash 2>'/tmp/a b' -c`, `bash -c 2>"/tmp/a b"`, `bash -o 'pos ix' -c`; HEAD allow, the second pass's tree deny, given up for the linear regex; `tests/test-ai-path-guard.sh` pins the first as allowed), and a quoted piece holding an `E1`–`E3` byte that is not valid UTF-8; more than 8 options that take a word before `-c`, or more than 4 words after it (`bash -c -e -u -x -v -o pipefail '…'`). Deny side, open (second review pass, LOW): 10 or more `sh -c` in one segment are denied by the 8-per-segment cap with `WHY_WORK_CAP`'s wording (`find . -exec sh -c '…' _ {} \;` ×10, a `docker run … bash -c '…'` holding 10 shell words), HEAD allow.
 
 ## Many mover segments on one line reach the path guard's 6 s clock (found 2026-10-20 while probing T-2026-10-20-001)
 - **Where**: `hooks/ai-path-guard.sh`, the movers pass (`:642-800`): one `realpath` fork, and for a loose hit more, per `cp`/`mv`/`install`/`rsync`/`rm`/`rmdir`/`unlink` segment. Older than T-2026-10-20-001 and not changed by it.
@@ -156,33 +176,59 @@
 - **What could go wrong**: KNOWN FACT (scratchpad probe, HEAD and after alike) — `rm` + N operands of 1 KB + ` a.txt`, one segment: N=250 allow 1.2 s, N=500 allow 3.4 s, N=1000 deny by the clock in 14.8 s; one segment of 3000 × 1 KB, or of 400 × 4 KB symlink-chain operands, is still running at 15 s. A trace of the N=500 line puts 2.5 s inside that one `awk` call. The clock is checked only after it returns, so the hook passes its 10 s timeout. Multi-segment lines are not affected: the cost grows with the length of one segment.
 - **How likely / how bad**: an unusually long single command (about 1 MB); deny side only if the runtime blocks on a timeout. INFERENCE (as for the other timeout entries): a timed-out hook does not block, so the command would run unchecked.
 - **Suggested fix**: find the quadratic step inside the `awk` program (string concatenation or `substr` per character over the whole segment) and make it linear, or cap the bytes `shell_segments` reads per segment and deny past it. Its own T4 hooks task; the characterization golden must stay identical.
-- **Status**: open
+- **Status**: accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)
 
 ## One amplifying symlink keeps `realpath -m` past the hook timeout (found 2026-10-22 by the STRONG re-review of T-2026-10-21-001)
 - **Where**: `hooks/ai-path-guard.sh`, every `realpath -m` fork: the movers pass (`mover_resolve`, `:743`, and its one-at-a-time fallback, `:749`) and `real_path`. Older than T-2026-10-21-001; the same on HEAD 2f7f9f7 and after it.
 - **What could go wrong**: KNOWN FACT (re-review probe, HEAD and after alike) — with `c -> .` and `d -> c/c/…(×2000)/.`, `realpath -m <dir>/d/d/…(×N)/x` alone takes 2.96 s at N=50, 6.25 s at N=100 and 13.33 s at N=200 (a 400-byte operand); through the guard, `rm <that>; rm <the state file>` takes 13.4 s on HEAD and 13.6 s after. It is one fork, so the 6 s clock cannot stop it. INFERENCE (as for the other timeout entries): a timed-out hook does not block, so the command would run unchecked.
 - **How likely / how bad**: deliberate, and it needs the symlinks created first by a command the guard allows (`ln -s`); the deny side of every path rule for that call.
 - **Suggested fix**: bound one `realpath` by the clock that is left (`timeout`, then deny with `WHY_WORK_CAP`), or resolve with a cap on symlink expansions. Its own T4 hooks task; the characterization golden must stay identical.
-- **Status**: open
+- **Status**: accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)
 
 ## `realpath`'s line count can balance while its lines are misaligned (found 2026-10-22 by the STRONG re-review of T-2026-10-21-001)
 - **Where**: `hooks/ai-path-guard.sh:743-744`, `mover_resolve`: the test that a chunk's `realpath` printed one line per candidate counts lines only. HEAD 2f7f9f7 has the same test per segment.
 - **What could go wrong**: INFERENCE from the code, not run — a symlink loop drops a line and a symlink whose target holds a newline adds one. In one chunk the two balance, and the `reals` between them belong to the wrong candidates, so a symlink to the state directory there is checked against a neighbour's real path. HEAD allowed this within one segment; the batches allow it across the segments of one chunk too.
 - **How likely / how bad**: deliberate, and it needs two crafted symlinks created first; a missed deny.
 - **Suggested fix**: `realpath -m -z` read NUL by NUL, so a newline in a target cannot add a record. Its own hooks task.
-- **Status**: open
+- **Status**: accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)
 
 ## Batched movers cost a few µs more per segment, near the clock (found 2026-10-22 by the fifth STRONG review of T-2026-10-21-001)
 - **Where**: `hooks/ai-path-guard.sh`, the movers pass: the batch bookkeeping (R1–R3, about 2 µs per mover segment over HEAD 2f7f9f7) and the pre-build estimate (`:897-904`, about 3.8 µs more), both run for a segment that makes no candidate too.
 - **What could go wrong**: KNOWN FACT (review probe, `x7.sh`, `x8.sh`) — `rm -f;` ×90000 (540 KB, no candidate): HEAD mean 4.65 s, 6/6 allow; R3 4.56 s, 6/6 allow; after 5.15 s, 1/6 denied by the clock with `WHY_WORK_CAP`. ×95000: HEAD 3/3 allow, R3 1/3 deny, after 2/3 deny.
 - **How likely / how bad**: a line of about half a megabyte of operandless mover segments; fails closed only, a false deny, never a missed one.
 - **Suggested fix**: run the estimate only when the segment has sources and the batch holds a segment; it narrows the gap, it does not close it (R3 had part of it).
-- **Status**: accepted by the human (Q4 = A in T-2026-10-21-001); open.
+- **Status**: accepted by the human (Q4 = A in T-2026-10-21-001) and under the guard threat model above (2026-10-22, docs/sdlc/specs/direct-mode-diet.md).
 
 ## The token pass strips quotes one character at a time (found 2026-10-22 while fixing T-2026-10-21-001)
 - **Where**: `hooks/ai-path-guard.sh:992-993`, inside the per-token pass's process substitution: the loops the movers pass had before T-2026-10-21-001. Older than that task and not changed by it.
 - **What could go wrong**: INFERENCE from the code and the movers pass's measurement (0.27 s per 4 KB operand of `""`), not measured here — a line of many quote-padded words spends that per word in the subshell; the reading loop checks the clock between tokens, so such a line is denied by the clock, not let through.
 - **How likely / how bad**: a crafted line; a false deny with `WHY_WORK_CAP`.
 - **Suggested fix**: the movers pass's one-step strip (`quote_tail`). Its own hooks task.
+- **Status**: accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)
+
+## Any session can write `review_status passed` without a review (found 2026-10-22 while writing docs/sdlc/specs/direct-mode-diet.md)
+
+- **Found**: 2026-10-22, the direct-mode-diet spec (non-goal "review provenance")
+- **Where**: `skills/ai-task/state.py:1386-1415` (`cmd_set`)
+- **What could go wrong**: KNOWN FACT — `set` refuses only `skipped_green` for `review_status`; `state.py set review_status passed` is accepted from any session, so the state cannot tell a verdict a reviewer returned from one the session typed. The diet adds no second route to `passed` (`remediate --closes` needs a report a review wrote) and leaves this as it is.
+- **How likely / how bad**: RISK — needs an agent to record a verdict nobody gave; the journal shows the write, not its source.
+- **Suggested fix**: its own design: the verdict carries the review run that produced it.
 - **Status**: open
 
+## One open step blocks every write outside it, scratchpad included (found 2026-10-22 while writing docs/sdlc/specs/direct-mode-diet.md)
+
+- **Found**: 2026-10-22, twice while writing the direct-mode-diet spec (non-goal "the scope guard's reach")
+- **Where**: `hooks/ai-scope-guard.sh:106-120`
+- **What could go wrong**: KNOWN FACT — while a step is current, every `Edit`/`Write` outside its `allowed_files` is refused with SCOPE_CHANGE_REQUIRED whatever the path, so a spec, a memory note or a scratchpad file waits until the step is done.
+- **How likely / how bad**: certain inside a task; costs a detour, never a wrong write.
+- **Suggested fix**: a later design that exempts paths outside the project root; it touches the invariant the guard exists for (C4).
+- **Status**: open
+
+## `lint_command` exits 12 on three pre-existing pylint messages, so the lint sensor is red on every task (found 2026-10-22 by T-2026-10-22-001)
+
+- **Found**: 2026-10-22, `state.py review-gate` in T-2026-10-22-001
+- **Where**: `.ai/reports/T-2026-10-22-001/lint.log` — `skills/ai-task/sensors.py:409` W0621, `skills/project-update/update.py:264` W1510, `tools/build-template-history.py:39` R1710
+- **What could go wrong**: KNOWN FACT — pylint rates the tree 10.00/10 and still exits 12 (its warning and refactor bits); the sensor reads that as red. The direct-mode-diet outcome (R2: lint green on a clean tree) does not hold until the three messages are gone, so every T2/T3 task keeps a BALANCED review the sensors would otherwise skip.
+- **How likely / how bad**: certain; one avoidable review per T2/T3 task.
+- **Suggested fix**: fix the three messages (none changes behaviour) — `sensors.py` inside diet task 4, the other two in a T1 task — or a human decides in `.pylintrc`.
+- **Status**: open
diff --git a/docs/sdlc/constitution.md b/docs/sdlc/constitution.md
--- a/docs/sdlc/constitution.md
+++ b/docs/sdlc/constitution.md
@@ -8,7 +8,7 @@
 C3. A refactoring changes no behaviour and is never mixed with a feature.
 C4. Every step names its files; scope grows only by amending the plan.
 C5. No agent commits, merges or deploys; a human approves outside the agent.
-C6. <!-- project principle — filled by /ai-init from the survey, confirmed by you -->
+C6. This plugin is a developer tool. A change to its hooks, skills or state machine is classified by what it does to a user project's decisions — allow where it denied, change approval, change install — never by its being a process.
 C7. <!-- project principle -->
 C8. <!-- project principle -->
 C9. <!-- project principle -->
diff --git a/CLAUDE.md b/CLAUDE.md
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -23,6 +23,7 @@
 <!-- Recurring mistakes and their corrections. Grow this list from code review. -->
 
 - A BLOCKER is closed only with a test that pins it; for a regex's running time, a `timed` case at the measured size that fails on the tree before the fix. Reviews of T-2026-10-20-003 found an untested blocker twice, and its BLOCKERs 2, 4 and 5 all came from edits to `SH_WORD`/`SH_RE` in `hooks/ai-path-guard.sh`, where the invariant is: no piece of a word crosses the blank after a match start's `sh`.
+- A change to this plugin's hooks, skills or `state.py` is not T4 for being "a process every call runs through": T-2026-10-21-001, a 51-line guard bugfix, ran as T4 and cost 25.4M tokens and three STRONG reviews. Tier it by what it does to a user project's decisions — the "this repository:" examples in `.ai/policies/risk-tiers.json`, constitution C6.
 
 <!-- claude-agentic:start -->
 ## AI agent workflow
diff --git a/CONTRIBUTING.md b/CONTRIBUTING.md
--- a/CONTRIBUTING.md
+++ b/CONTRIBUTING.md
@@ -37,6 +37,10 @@
 ```bash
 pylint $(git ls-files '*.py')
 ```
+
+pylint comes from the distribution package (`python3-pylint` on Debian and
+Ubuntu); no `pip` install is needed — `pylint` on `PATH` is what
+`lint_command` in `.ai/policies/testing.md` calls.
 
 Run the suite to the end and fix every failure before you push.
 
diff --git a/.ai/rules/hooks.md b/.ai/rules/hooks.md
new file mode 100644
--- /dev/null
+++ b/.ai/rules/hooks.md
@@ -0,0 +1,7 @@
+---
+dirs: [hooks]
+---
+# Hooks rules
+- Tier by what the change does to a user project's decisions, never by the hook being a process every call runs through (constitution C6).
+- T2: no guard decision moves, golden byte-identical. T3: adds a deny or changes a deny's text, golden re-recorded. T4: allows what was denied or weakens a refusal.
+- The guards defend against an agent's mistakes, not a constructed command: such a finding is accepted in `known-risks.md` under the threat model in `.ai/policies/safety.md`.
diff --git a/.ai/rules/skills.md b/.ai/rules/skills.md
new file mode 100644
--- /dev/null
+++ b/.ai/rules/skills.md
@@ -0,0 +1,7 @@
+---
+dirs: [skills]
+---
+# Skills rules
+- Tier by what the change does to a user project's decisions, never by the skill being a process (constitution C6).
+- T2: skill or agent text, `usage-report`, no `state.py` refusal moves. T3: adds a `state.py` check, a sensor or a refusal. T4: weakens a refusal, changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, `review_status` transitions) or changes install and migration (the `project-update` merge).
+- A change to a shipped template or to `ai/` runs `tools/build-template-history.py` in the same task, or `tests/test-project-update.sh` goes red.
```

## Part B — apply after diet task 4 is committed

<!-- patch:B -->
```diff
diff --git a/.ai/policies/risk-tiers.json b/.ai/policies/risk-tiers.json
--- a/.ai/policies/risk-tiers.json
+++ b/.ai/policies/risk-tiers.json
@@ -59,9 +59,9 @@
         "T5": "ai-planner on STRONG, in plan mode",
         "T6": "ai-expert"
       },
-      "test": "three scopes. During a step: only the tests the plan named for that step (`step_test_command` scoped to its files), fixed inside the step before `state.py step-done` — never the full suite, never e2e. After the LAST step: `verify_command` once, to the end, no fail-fast flag, output through tail -40 or log-reader; every failure is collected and classified first, every NEW REGRESSION is fixed in ONE `state.py remediate` step and the command runs once more, at most two rounds. At the END of the task, after the full suite is green: `e2e_command` once, never per step, skipped at T0/T1 and when no e2e-covered flow can be reached (say which).",
-      "e2e": "once per task, at the end, after verify_command is green and before the adversarial review. T0/T1: none. T2+: required when the change can reach a flow the e2e suite covers, otherwise one line saying why it cannot. T5/T6: always, and its result goes in the release report. Record it with `state.py set e2e_status <passing|failing|not_applicable|not_run>`.",
-      "triage": "T0/T1: no state file. T2, T3 and T4: `state.py quick` records discovery, context, impact, risk and the one-step plan in a single call (at T4 after the human approved the plan). T5+: the stages run and are recorded one at a time.",
+      "test": "three scopes. During a step: only the tests the plan named for that step (`step_test_command` scoped to its files), fixed inside the step — never the full suite, never e2e. After the LAST step, in direct mode: `state.py test-run --scope all` once — `verify_command` to the end, no fail-fast flag, then `e2e_command` only when the suite is green; every failure is collected and classified first, every NEW REGRESSION is fixed in ONE `state.py remediate` step (it finishes the open step itself) and `test-run --scope all` runs once more, at most two rounds. e2e never runs per step; it is skipped at T0/T1 and, when no e2e-covered flow can be reached, `--e2e not-applicable \"<why>\"` says so. The sdlc pipeline runs `state.py step-done` per step, then `--scope suite` and `--scope e2e`.",
+      "e2e": "once per task, at the end, after verify_command is green and before the adversarial review — in direct mode the second half of `state.py test-run --scope all`. T0/T1: none. T2+: required when the change can reach a flow the e2e suite covers, otherwise `test-run --scope all --e2e not-applicable \"<why>\"` (or `state.py set e2e_status not_applicable`). T5/T6: always, and its result goes in the release report.",
+      "triage": "T0/T1: no state file. T2, T3 and T4: `state.py quick` records discovery, context, impact, risk and the one-step plan in a single call (at T4 after the human approved the plan), and `state.py close` ends it: it finishes the open step, runs the review gate, stops where a review or the human gate is owed, and archives. A green T2/T3 is three calls: `quick`, `test-run --scope all`, `close`. T5+: the stages run and are recorded one at a time.",
       "artifacts": {
         "T0": "none — the commit message",
         "T1": "none — the commit message",
@@ -618,6 +618,7 @@
     }
   },
   "remediation_rounds": 2,
+  "review_rounds_max": 2,
   "escalation_triggers": [
     "the STRONG tier could not resolve an ambiguity and said so",
     "two constraints in the architecture contradict each other",
diff --git a/.ai/policies/risk-tiers.md b/.ai/policies/risk-tiers.md
--- a/.ai/policies/risk-tiers.md
+++ b/.ai/policies/risk-tiers.md
@@ -1,4 +1,4 @@
-<!-- generated from risk-tiers.json sha256:7b96b55a33363347fee45eda6f0ad17956c251ed271c49b1e61c75bb7c8fa747 -->
+<!-- generated from risk-tiers.json sha256:6361c98f0c3dffe244a63793934cc7798fe0ad7409b884ef912acc3768d79ed4 -->
 <!-- If /ai-status reports this hash as stale, risk-tiers.json changed and this
      mirror did not. The JSON file is the source of truth; update this by hand. -->
 
@@ -111,9 +111,13 @@
 more. At most two rounds, then the human decides. **At the end of the task**,
 after the fast suite is green: `e2e_command`, once — never per step, skipped at
 T0/T1 and whenever the change cannot reach an e2e-covered flow, which is said
-in one line. Review findings are handled the same way as test failures: one
-batch, one scoped re-review only when a blocker was fixed. A bugfix still shows
-its failing test first.
+in one line. In direct mode the suite and e2e are one call, `state.py test-run
+--scope all`, and `state.py close` finishes the open step, runs the review gate
+and stops where a review or the human gate is owed: a green T2/T3 is `quick`,
+`test-run --scope all`, `close`. Review findings are handled the same way as
+test failures: one batch, one scoped re-review only when a blocker was fixed,
+and at most `review_rounds_max` (2) review passes per task — past them the human
+decides. A bugfix still shows its failing test first.
 
 In `solo` the session still delegates one `ai-discovery` when the area is
 unfamiliar or the plan depends on an `UNKNOWN`, `ai-risk` on STRONG when a T4+
diff --git a/.ai/AGENTS.md b/.ai/AGENTS.md
--- a/.ai/AGENTS.md
+++ b/.ai/AGENTS.md
@@ -48,7 +48,7 @@
 | a large file, logs, a tool or MCP server | `policies/context-management.md`, `policies/tooling.md` |
 | writing code under `<dir>/` | `policies/coding.md`; `rules/<slug>.md` for that directory |
 | tests | `policies/testing.md` — Verification: the three commands |
-| finishing a step, running the suite, asking whether the review can be skipped | `state.py step-done`, `state.py test-run`, `state.py review-gate` — the measurements are deterministic and the refusals name the way out |
+| running the suite, closing a task, asking whether the review can be skipped | direct mode: `state.py test-run --scope all`, then `state.py close` (it finishes the step and runs the review gate); the sdlc pipeline: `state.py step-done`, `test-run`, `review-gate` — the measurements are deterministic and the refusals name the way out |
 | schema, data, migrations | `policies/database.md`, `policies/production.md` |
 | auth, secrets, personal data, payments | `policies/security.md` |
 | git, release | `policies/git.md`, `policies/release.md` |
diff --git a/skills/ai-init/templates/.ai/policies/risk-tiers.json b/skills/ai-init/templates/.ai/policies/risk-tiers.json
--- a/skills/ai-init/templates/.ai/policies/risk-tiers.json
+++ b/skills/ai-init/templates/.ai/policies/risk-tiers.json
@@ -59,9 +59,9 @@
         "T5": "ai-planner on STRONG, in plan mode",
         "T6": "ai-expert"
       },
-      "test": "three scopes. During a step: only the tests the plan named for that step (`step_test_command` scoped to its files), fixed inside the step before `state.py step-done` — never the full suite, never e2e. After the LAST step: `verify_command` once, to the end, no fail-fast flag, output through tail -40 or log-reader; every failure is collected and classified first, every NEW REGRESSION is fixed in ONE `state.py remediate` step and the command runs once more, at most two rounds. At the END of the task, after the full suite is green: `e2e_command` once, never per step, skipped at T0/T1 and when no e2e-covered flow can be reached (say which).",
-      "e2e": "once per task, at the end, after verify_command is green and before the adversarial review. T0/T1: none. T2+: required when the change can reach a flow the e2e suite covers, otherwise one line saying why it cannot. T5/T6: always, and its result goes in the release report. Record it with `state.py set e2e_status <passing|failing|not_applicable|not_run>`.",
-      "triage": "T0/T1: no state file. T2, T3 and T4: `state.py quick` records discovery, context, impact, risk and the one-step plan in a single call (at T4 after the human approved the plan). T5+: the stages run and are recorded one at a time.",
+      "test": "three scopes. During a step: only the tests the plan named for that step (`step_test_command` scoped to its files), fixed inside the step — never the full suite, never e2e. After the LAST step, in direct mode: `state.py test-run --scope all` once — `verify_command` to the end, no fail-fast flag, then `e2e_command` only when the suite is green; every failure is collected and classified first, every NEW REGRESSION is fixed in ONE `state.py remediate` step (it finishes the open step itself) and `test-run --scope all` runs once more, at most two rounds. e2e never runs per step; it is skipped at T0/T1 and, when no e2e-covered flow can be reached, `--e2e not-applicable \"<why>\"` says so. The sdlc pipeline runs `state.py step-done` per step, then `--scope suite` and `--scope e2e`.",
+      "e2e": "once per task, at the end, after verify_command is green and before the adversarial review — in direct mode the second half of `state.py test-run --scope all`. T0/T1: none. T2+: required when the change can reach a flow the e2e suite covers, otherwise `test-run --scope all --e2e not-applicable \"<why>\"` (or `state.py set e2e_status not_applicable`). T5/T6: always, and its result goes in the release report.",
+      "triage": "T0/T1: no state file. T2, T3 and T4: `state.py quick` records discovery, context, impact, risk and the one-step plan in a single call (at T4 after the human approved the plan), and `state.py close` ends it: it finishes the open step, runs the review gate, stops where a review or the human gate is owed, and archives. A green T2/T3 is three calls: `quick`, `test-run --scope all`, `close`. T5+: the stages run and are recorded one at a time.",
       "artifacts": {
         "T0": "none — the commit message",
         "T1": "none — the commit message",
@@ -615,6 +615,7 @@
     }
   },
   "remediation_rounds": 2,
+  "review_rounds_max": 2,
   "escalation_triggers": [
     "the STRONG tier could not resolve an ambiguity and said so",
     "two constraints in the architecture contradict each other",
diff --git a/skills/ai-init/templates/.ai/policies/risk-tiers.md b/skills/ai-init/templates/.ai/policies/risk-tiers.md
--- a/skills/ai-init/templates/.ai/policies/risk-tiers.md
+++ b/skills/ai-init/templates/.ai/policies/risk-tiers.md
@@ -1,4 +1,4 @@
-<!-- generated from risk-tiers.json sha256:616a6da3c59073926c5ece428efa251fbe539d25a53bcf50be67522f44848368 -->
+<!-- generated from risk-tiers.json sha256:0719098eb5b7dc8e7a93cc0b0be5ba8349feae7adf0dfe4cdc7a87efe6ef9727 -->
 <!-- If /ai-status reports this hash as stale, risk-tiers.json changed and this
      mirror did not. The JSON file is the source of truth; update this by hand. -->
 
@@ -95,9 +95,13 @@
 more. At most two rounds, then the human decides. **At the end of the task**,
 after the fast suite is green: `e2e_command`, once — never per step, skipped at
 T0/T1 and whenever the change cannot reach an e2e-covered flow, which is said
-in one line. Review findings are handled the same way as test failures: one
-batch, one scoped re-review only when a blocker was fixed. A bugfix still shows
-its failing test first.
+in one line. In direct mode the suite and e2e are one call, `state.py test-run
+--scope all`, and `state.py close` finishes the open step, runs the review gate
+and stops where a review or the human gate is owed: a green T2/T3 is `quick`,
+`test-run --scope all`, `close`. Review findings are handled the same way as
+test failures: one batch, one scoped re-review only when a blocker was fixed,
+and at most `review_rounds_max` (2) review passes per task — past them the human
+decides. A bugfix still shows its failing test first.
 
 In `solo` the session still delegates one `ai-discovery` when the area is
 unfamiliar or the plan depends on an `UNKNOWN`, `ai-risk` on STRONG when a T4+
diff --git a/skills/ai-init/templates/.ai/AGENTS.md b/skills/ai-init/templates/.ai/AGENTS.md
--- a/skills/ai-init/templates/.ai/AGENTS.md
+++ b/skills/ai-init/templates/.ai/AGENTS.md
@@ -48,7 +48,7 @@
 | a large file, logs, a tool or MCP server | `policies/context-management.md`, `policies/tooling.md` |
 | writing code under `<dir>/` | `policies/coding.md`; `rules/<slug>.md` for that directory |
 | tests | `policies/testing.md` — Verification: the three commands |
-| finishing a step, running the suite, asking whether the review can be skipped | `state.py step-done`, `state.py test-run`, `state.py review-gate` — the measurements are deterministic and the refusals name the way out |
+| running the suite, closing a task, asking whether the review can be skipped | direct mode: `state.py test-run --scope all`, then `state.py close` (it finishes the step and runs the review gate); the sdlc pipeline: `state.py step-done`, `test-run`, `review-gate` — the measurements are deterministic and the refusals name the way out |
 | schema, data, migrations | `policies/database.md`, `policies/production.md` |
 | auth, secrets, personal data, payments | `policies/security.md` |
 | git, release | `policies/git.md`, `policies/release.md` |
```
