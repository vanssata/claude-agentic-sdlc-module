# T-2026-10-30-2251-risk-burndown-b5 — Risk burndown B5: interpreter tripwire residuals in hooks/guard/paths.py (php -r, Node writeSync/writevSync and PHP fprintf write calls, head anchored to a command position, perl -e then -i)

bugfix · full · started 2026-10-30T22:51:42Z · claude

## Weight

```
scope          2  hooks/guard/paths.py matches hot_paths hooks/**
behaviour      1  the control-file tripwire denies a few more interpreter one-liners that write .ai/state or repor
reversibility  0  git revert returns everything
domain         0  guard against an agent's mistakes, not a security boundary (safety.md threat model) (declared)
novelty        1  regex edits under the SH_WORD/SH_RE running-time invariant (CLAUDE.md), timed cases required (de
coverage       2  0 of 1 code files have a test
W 6 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-30T22:51:42Z — /loop risk burndown B5 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md); hooks task, raised to full for a STRONG review and the gate
batch: on by Ivan Kakurov at 2026-10-30T22:51:42Z — /loop risk burndown B5 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md); hooks task, raised to full for a STRONG review and the gate

## Plan

files: hooks/guard/paths.py, tests/test_ai_path_guard.py, tests/test_ere_unit.py, tests/test_guard_characterization.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/review-b5.md, docs/sdlc/intent/risk-aware-multi-agent-adlc.md, docs/sdlc/intent/small-oop-modules.questions.md, docs/sdlc/specs/small-oop-modules.md
tests: tests/test_ai_path_guard.py, tests/test_ere_unit.py, tests/test_guard_characterization.py
- s1 · hooks/guard/paths.py, tests/test_ai_path_guard.py, tests/test_ere_unit.py, tests/test_guard_characterization.py · tests/test_ai_path_guard.py, tests/test_ere_unit.py, tests/test_guard_characterization.py · done
amended 2026-10-30T23:11:11Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/review-b5.md — the STRONG review's verbatim report quotes perl -i spellings next to .ai/reports in markdown backticks; the path guard's tripwire refuses the heredoc that writes it, so it is written with the Write tool to this scratch file and passed to review --report
amended 2026-10-30T23:31:12Z: +docs/sdlc/intent/risk-aware-multi-agent-adlc.md, docs/sdlc/intent/small-oop-modules.questions.md, docs/sdlc/specs/small-oop-modules.md — committed by Ivan Kakurov in c403f0f during this task (spec and intent work from another session), on top of the task's base 3d692a4; NOT B5's work — listed only so close's diff-since-base measure covers them

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2251-risk-burndown-b5 for implementation? (gate: human_approval)
asked: 2026-10-30T23:31:12Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T23:31:34Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 09152f018 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/suite-1.log | no |
| 2 | e2e | 0 | 09152f018 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/e2e-2.log | no |
| 3 | suite | 0 | d9b91e69e | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/suite-3.log | no |
| 4 | e2e | 0 | d9b91e69e | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/e2e-4.log | no |
| 5 | suite | 0 | 5846854b3 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/suite-5.log | no |
| 6 | e2e | 0 | 5846854b3 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/e2e-6.log | no |
| 7 | suite | 0 | 5846854b3 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/suite-7.log | no |
| 8 | e2e | 0 | 5846854b3 | .ai/state/logs/T-2026-10-30-2251-risk-burndown-b5/e2e-8.log | no |

suite passing · e2e passing · suite runs 4

## Review

### Pass 1 — STRONG, pass

```
Review of T-2026-10-30-2251-risk-burndown-b5. Full mode, STRONG, all dimensions, limited to B5's hunks in `hooks/guard/paths.py` and `tests/test_ai_path_guard.py`.

There was no `review-ledger.md` or `sensors.json` for this task, so nothing was inherited. I used about 30 tool calls.

**How I tested:** I ran the real hook (`ai-guard.py --only paths`) twice per command, once from HEAD (`git archive` into the scratchpad) and once from the working tree, on about 120 commands. The rows marked `**` in the probe output are where the two trees decide differently. Probe files:
- `/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/b5probe/probe.py`
- command lists `c1.txt` to `c5.txt` in that same `b5probe/` folder
- the HEAD copy in `/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/b5head/hooks/`

## FINDINGS

- [MEDIUM] M1 Adding `'` and `"` to the anchor of INPLACE_RE makes a quoted mention of "perl -i" count as an in-place edit. Searches like these used to be allowed and are now denied (`hooks/guard/paths.py:163`)  in_scope: yes
  - `grep -rn "perl -i" .ai/reports/`
  - `grep -rn 'perl -pi' .ai/reports/`
  - `rg "ruby -i" .ai/reports/T-1/notes.md`
  - `git log -S "perl -i" -- .ai/reports/`
  - `echo "perl -pi -e s/x/y/ was refused"; cat .ai/reports/T-1/notes.md`

  why it matters: the comment the change adds says "grep perl -i names it, does not run it". That now holds only for the unquoted form, and the quoted form is how people actually write a grep pattern. `interpreter_text` gets `cmd` without `strip_prose`, so commit messages and heredoc lines that start with a quoted `perl -i` are caught too. The refusal says "an interpreter one-liner that writes the task's own control files", which is wrong for a grep. This repository's agents grep `.ai/reports` for exactly these spellings when they work these risks. Test 18c pins only the unquoted `grep perl -i`, so nothing catches this.

  suggested direction: only treat a quote as a command position when a shell is running the quoted text (`sh|bash -c '…`, `eval "`), and add the quoted grep/rg cases as allow tests.

- [MEDIUM] M2 Anchoring to a fixed list of wrappers turns earlier denies into silent allows (misses) for wrappers and positions not on the list (`hooks/guard/paths.py:163-165`)  in_scope: yes
  - Wrappers that were denied at HEAD and are allowed now:
    - `parallel perl -pi -e 's/a/b/' ::: .ai/reports/T-1/notes.md`
    - `ionice perl -pi …`
    - `doas perl -pi …`
    - `chrt 5 perl -pi …`
    - `unbuffer perl -pi …`
    - `watch perl -pi …`
    - by the same mechanism, presumably `flock`, `strace`, `chronic`, `caffeinate`
  - Positions: `case x in x) perl -pi -e … .ai/reports/T-1/notes.md;; esac`. `)` is not in the anchor set.

  why it matters: the risk text says the tripwire is the only check on an interpreter one-liner's writes, including `.ai/state/current.json`. A miss is an unguarded write; a false deny costs one Read call. The change trades the cheaper error for the dearer one on these spellings, and no test pins it. Under `hooks/CLAUDE.md` this is "allows what was denied", which is behaviour 2.

  suggested direction: on an unlisted wrapper word, fall back to "any blank before perl" (the old behaviour), and anchor only where the program is plainly an argument (after grep/rg/echo/git). Add `)` to the anchor set, or add allow and deny tests for the residual list and record it as a risk.

- [LOW] L1 The Weight record says behaviour 1 ("denies a few more interpreter one-liners"). The change also allows what was denied: the intended `grep perl -i …`, the 18d case `env a a a a; … grep perl -i`, and the M2 list (`.ai/reports/T-2026-10-30-2251-risk-burndown-b5/task.md` §Weight)  in_scope: yes

  why it matters: `hooks/CLAUDE.md` requires `--declare behaviour=2:"<effect>"` for that direction. The full-mode override already brings the STRONG review and the gate, so the outcome is the same, but the record misstates what the change does.

  suggested direction: declare behaviour=2 with the effect named.

- [LOW] L2 `writeSync`, `writevSync`, `fprintf` and `vfprintf` count as writes even when the target is stdout or stderr. A read that prints a control file is now denied (`hooks/guard/paths.py:173`)  in_scope: yes
  - `node -e "const fs=require('fs'); fs.writeSync(1, fs.readFileSync('.ai/state/current.json'))"`
  - `node -e "require('fs').writeSync(process.stdout.fd, …readFileSync('.ai/reports/T-1/notes.md'))"`
  - `php -r 'fprintf(STDOUT, "%s", file_get_contents(".ai/state/current.json"));'`

  All three were allowed at HEAD. Test 18c pins the same shape as a desired deny: `fprintf(STDERR, 'x')` and `vfprintf(STDERR, …)`, labelled "a handle write". STDERR is not the file, so those vectors pin a false deny instead of the miss the risk describes (a handle from `fopen` or `openSync` with the mode out of sight).

  why it matters: it costs one Read call (the risk's own estimate), and the test makes the false deny look intended.

  suggested direction: use a real file handle in the deny vectors (`$f=fopen($argv[1],$m); fprintf($f,…)`, `fs.writeSync(fs.openSync(p, m), …)`). Exclude fd 1 and 2, `process.stdout.fd`, `STDOUT` and `STDERR` the way `stdout.write` and `stderr.write` already are.

- [INFO] I1 Pre-existing, not introduced by B5: INTERP_RE recognises only a separate `-c` or `-e` (now also php `-r`). None of these count as interpreter one-liners, so their writes are never scanned, and every one is allowed on both trees with a write to `.ai/state/current.json` (paths check only)  in_scope: yes
  - `perl -ne`, `perl -le`, `perl -pe`, `perl -E`
  - `ruby -ne`
  - `node -p`, `node --eval`
  - `python3 -Ic`
  - `php -d k=v -r`: the value word does not start with `-`
  - `php -R`, `php -B`, `php -E`

  B5 itself teaches INPLACE_RE that `-ne` and `-E` carry code (`[a-zA-Z]*[eE]`), which makes the gap in INTERP_RE an internal inconsistency (`hooks/guard/paths.py:157-158`).

  why it matters: inside the boundary this is a set of HIGH-class misses on ordinary spellings. They belong in a new risk entry, not in this change.

- [INFO] I2 After a listed wrapper, the argument loop takes any words, so `sudo grep perl -i …`, `time grep perl -i …` and `env LC_ALL=C grep perl -i …` are still denied. The fix for "names it, does not run it" holds only with no wrapper  in_scope: yes

- [INFO] I3 Running time and tests  in_scope: yes
  - INPLACE_RE and INTERP_RE both contain nested repetition, so `ere.Compiled` searches them with `_Dfa` (NFA of 173 and 71 states), which is linear by construction. Test 18d therefore measures the DFA plus process start, not the pattern's shape. A pathological shape would fail it only if `_dfa_ok` rejected the pattern (a bounded repeat over 256, or a backreference).
  - The only consumer is Python `hooks/guard/ere.py`; `tests/fixtures/guard-port/ai-path-guard.sh` is frozen. The session's `/usr/bin/grep -E` probe timed a different engine from the one that runs in production, so the bash-ERE parity question does not apply.
  - On 21 adversarial inputs of 4 to 5 KB, in process with a fresh compile, every search took 0.6 ms or less and built at most 14 DFA states. Inputs included `sudo a…`, `if …`, `A=b …`, 4 KB of `'`, `(`, `$(`, mixed separators, `then perl`, `-e '-i' -e`, `-ee 'x'`, `find -exec…`, `-M x…`, `php -n…/-r…`, `fprintf` followed by 4 KB of blanks, and `writeSyn…`.

- [INFO] I4 Spellings missed on both trees, which B5's `-e` loop does not reach  in_scope: yes
  - The quoted-code alternative misses `-e 'a'\''b c'`, `-e $'a b'`, `-e "a \" b"`, `-e's/a b/c/'` (no blank) and `-0777ne '…'` (digits are outside `[a-zA-Z]*`), each followed by `-i`.
  - The head misses `\perl`, `"perl"`, `/usr/bin/perl` and `perl5.36`.
  - Neither change is a regression; they belong with the risk register.

## EXAMINED AND CLEAN
- **Diff scope:** `git diff HEAD` on the two files contains only B5 hunks, inside the plan's file list (it touches 2 of the 4 permitted files). No refactoring and no unrelated edits.
- **Anchoring, still denied on the new tree:**
  - `;perl`, `&&perl`, `||perl`, `ls|perl`, `ls &perl`, `&&<TAB>perl`, a newline before perl
  - `{ perl…; }`, `f() { perl…; }`, `! perl`, `for/while/until … do perl`, `(perl …)`
  - `sudo -u x`, `env -i`, `time -p`, `command -p`, `nice -n 5`, `timeout -s KILL 5`, `xargs -0 -I{}`, `find -exec`, `nohup sudo`, `sudo env`
  - `FOO=1`, `FOO="a b"`, `FOO='a b'`
  - `cat f | perl -pi`, `perl -i.bak`, `-0777 -pi`, `-Mstrict -pi`, `ruby -pi`
- **Newly denied, correctly:** `x=$(perl -pi …)`, `` x=`perl -pi …` ``, `echo "$(perl -pi …)"`, `bash -c "perl -pi …"`, and `-i` after quoted code (`-pe '…' -i`, `-e "…" -i`, `-l -pe … -i`, two `-e` arguments then `-i`, `-pe '' -i.orig`).
- **Reads still allowed:** `echo x | perl -ne 'print if /a/' …`, `perl -ne 'print -i' …`, `perl -ne 'print if / -i/' …`, `perl -e 'print 1' f -i` (the `-i` comes after the file).
- **php -r:** allowed on reads (`php -r 'echo 1;' f`, `php -n -r` with file_get_contents of argv). `ruby -r json -e … f` and `perl -r -e …` are not affected.
- **Length limit:** the 18d inputs are 3033 to 4092 characters, all at or under `LONG_CMD` = 4096, so their denies come from the tripwire and not the length rule. The probe showed every 18d deny case except `env a… perl -pi` being allowed at HEAD.
- **Tests run:** 18c and 18d pass on the tree (`python3 -m unittest …test_18c… …test_18d…`, 2 tests, OK). `suite-1.log` shows 1099 tests OK (5 skipped); `e2e-2.log` shows 5 OK.
- **Characterization golden:** unchanged (the suite passed). No serialized data or contract changed, and a revert is clean.
- not reached (budget): the UTF-8 versus C-locale split of the new anchor on non-ASCII blanks before `perl`, and the full `test_guard_differential` corpus.

## VERDICT

verdict: pass
(No BLOCKER or HIGH in scope. M1, M2, L1 and L2 are open findings worth fixing in the next batch; I1 goes to the risk register.)
scope_assessment: The change stayed within the approved plan: two of the four permitted files, only the three regexes and two new tests. M2 and L1 are side effects of that work, not scope creep. The record understates the behaviour change (it also allows previously denied commands, which is behaviour 2).
```

### Pass 2 — STRONG, pass_with_findings

```
Re-review (STRONG) of T-2026-10-30-2251-risk-burndown-b5, fix batch. M1, M2 and L2 close. The fix introduced one HIGH: some writes that HEAD denies are now allowed. I ran the real `ai-guard.py --only paths` on the HEAD copy and on the working tree using the existing harness. Case files c6–c11 are in `/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/b5probe/`. That folder also has `probe_all.py`, the same harness running every guard, and `timeit.py`. There is no review-ledger.md or sensors.json, so nothing was inherited. Numbering continues from §Review pass 1. I used about 22 tool calls.

## FINDINGS

- [HIGH] H1 `inplace_edit` runs its second match on the output of `shell_segments`. That output drops heredoc bodies and treats echo/printf as plain text even when their output is piped into a shell. Writes HEAD denies are now allowed (`hooks/guard/paths.py:1255-1261`, together with `text_tool_segment` at about :172)  in_scope: yes
  - Allowed on the tree, denied at HEAD, with `--only paths`:
    - `bash <<EOF\nperl -pi -e s/a/b/ .ai/reports/T-1/notes.md\nEOF`
    - `sh -s <<EOF …`
    - `ssh localhost <<EOF …`
    - `cat <<'EOF' | sh\nperl -pi …\nEOF`
    - `echo perl -pi -e s/a/b/ <ctl> | sh` (also `| bash`)
    - `printf '%s\n' perl -pi … | bash`
    - `echo … | xargs -I{} sh -c {}`
  - With every guard running (`probe_all.py`), `bash <<EOF\nperl -pi -e s/a/b/ .ai/state/current.json\nEOF` and `echo perl -pi -e s/a/b/ .ai/state/current.json | sh` are still allowed on the tree and denied at HEAD.
  - why it matters: this tripwire is the only check on an interpreter writing `.ai/state/current.json`, and a heredoc to bash is an ordinary multi-line spelling, not a contrived one. The intent was to stop counting a perl that a text tool only names, but the fix also skips every heredoc body, whoever reads it. This is "allows what was denied" (behaviour 2), and no 18e case pins it. HEAD already let quoted forms through (`echo "perl -pi …" | sh`), so a determined agent had a way around before. The new misses are the unquoted and heredoc spellings a cooperative agent writes by accident.
  - suggested direction: run the second match on the raw command with only the text-tool segments' own spans blanked, so heredoc bodies stay in, and never carve out a text-tool segment whose output goes to sh, bash, zsh, ssh, `xargs … sh` or `source`. Add deny cases for `bash <<EOF`, `cat <<EOF | sh` and `echo … | sh` to 18e.

- [MEDIUM] M3 What is left of M1: the `'`, `"`, `(` and `{` anchors still deny a quoted mention under any command not on the text-tool list (`hooks/guard/paths.py:163-166`, `text_tool_segment`)  in_scope: yes
  - Allowed at HEAD, denied on the tree:
    - `find .ai/reports/ -name '*.md' | xargs grep -l "perl -i"`
    - `find … -exec grep -l "perl -i" {} +`
    - `git -C . grep -n "perl -i" -- .ai/reports/` (`-C <dir>` makes `rest[0]` the directory)
    - `git -c a=b log 'perl -i'`
    - `gh pr create --body "… \"perl -i\" …"`
    - `python3 s.py --what "(perl -i)" .ai/reports/…`
  - why it matters: these are the commands agents use while working this risk: risk-register adds, PR bodies, and grep through xargs or find. The refusal wrongly says "writes the task's own control files". I2's wrapper residue (`sudo grep perl -i`) also goes the opposite way here: `sudo` and `time` grep are now allowed.
  - suggested direction: skip the wrapper word in `text_tool_segment` (`xargs`, `-exec`, `git -C/-c <arg>`), or apply the quote anchor only after a shell-running word (`sh|bash -c`, `eval`, `$(`, a backtick), as M1's direction said. Add allow tests for these spellings.

- [LOW] L3 B5's `php … -r` alternative in INTERP_RE extends a known false deny to php (`hooks/guard/paths.py:157-158`)  in_scope: yes
  - Allowed at HEAD, denied on the tree:
    - `cat > /tmp/out.md <<'EOF'\n- php -r 'echo 1;' is a one-liner; see \`x\`\n- .ai/reports/…\nEOF`
    - `python3 s.py … --what "php -d k=v -r x; php -r 'x' and \`y\`"`
  - Mechanism: `interpreter_text` scans the raw command, heredoc bodies and quoted arguments included. Any ` php -r ` followed by a blank sets `is_interp`, and WRITE_WORD_RE then matches any backtick or `$(`. Markdown code spans are full of backticks.
  - The same shape with ` perl -e '…' ` is denied on both trees, so it is not new. Only the php spelling is new.
  - why it matters: it costs one rewrite, and it fires on notes written about this very risk.
  - suggested direction: apply `strip_prose` before the `is_interp` write scan, or record it alongside I1 in the risk register.

- [LOW] L4 `text_tool_segment` keeps only the part after the last `/` (`rsplit("/")`), so `./grep perl -pi -e 's/a/b/' .ai/reports/T-1/notes.md` (a script named grep that runs perl -pi) is allowed on the tree and denied at HEAD (`hooks/guard/paths.py` `text_tool_segment`)  in_scope: yes
  - why it matters: it needs a script written first, and running a written script already gets past the tripwire at HEAD, so there is little new reach. It is still an unneeded hole.
  - suggested direction: match the bare word, or `/usr/bin/` and `/bin/` only.

- [INFO] I5 Git text tools whose environment or options run a command  in_scope: yes
  - Affected spellings:
    - `GIT_PAGER='perl -pi -e … <ctl>' git log`
    - `GIT_EDITOR='perl -pi …' git commit`
    - `GIT_EXTERNAL_DIFF=… git diff`
    - `env GIT_PAGER=… git log`
    - `X='perl -pi …' git --config-env=core.pager=X log`
    - `git grep -O'perl -pi -e s/a/b/' x -- .ai/reports/`. `-O` runs the pager on the matched files.
  - Status: HEAD allows these too (a quote comes before perl). B5 before this fix denied them, and the carve-out allowed them again.
  - Not a regression against HEAD. It belongs in the risk register, or the carve-out should refuse a segment that had an assignment stripped (`_ASSIGN`) or that carries `-O`/`--open-files-in-pager`/`--config-env`.
  - `git -c core.pager='perl -pi …' log` is now denied, an improvement over HEAD.

- [INFO] I6 The live false denies you asked about are HEAD behaviour, because this session's hook is HEAD's code  in_scope: yes
  - `~/.claude/settings.json:39` runs `$HOME/.claude/hooks/ai-guard.py`. Its `guard/paths.py` is byte-identical to the HEAD copy and differs from the working tree. So "refused both before and after the fix" was HEAD refusing both times. Neither B5 nor the fix ever ran live.
  - Heredoc case: the markdown body you described is allowed on both trees in the probe. It has the spans `` `grep -rn "perl -i" .ai/reports/` `` and `` `echo "perl -pi -e s/x/y/ was refused"; cat …` ``.
    - A body line with a blank before an unquoted `perl … -i` (`- plain grep -rn perl -i in .ai/reports/`) is denied at HEAD and allowed on the tree, because heredoc bodies are now dropped. That is the benign side of H1.
    - A body containing ` perl -e '…' ` plus a backtick is denied on both trees. That is the I1/L3 mechanism, and HEAD has it too.
    - The live refusal therefore came from one of those two pre-existing mechanisms, not from a B5 regression.
  - State.py case: the exact `--what` string you quoted is allowed on both trees. Neither INTERP_RE alternative matches `php -r)` or `php -d k=v -r`, and INPLACE_RE finds no `-…i`.
    - The live deny must come from the elided title or text.
    - A blank-anchored `perl -i`/`perl -pi -e` anywhere in it is denied on both trees.
    - A quoted `"perl -i"` or `(perl -i)` is denied only on the tree (M3).
    - A ` php -r '…' ` plus a backtick is denied only on the tree (L3).
    - Whichever it was, it ran on HEAD's code, so it is pre-existing.
  - My own live tool calls were refused twice by the HEAD guard while I wrote probe files: a heredoc carrying `perl -pi -e`, a control path and `$(`, and one carrying `node -e … writeSync(fd` with a control path. That is the same pre-existing `is_interp` + backtick/`$(` mechanism.

## EXAMINED AND CLEAN
- M1 closes. All five named spellings are allowed on the tree: `grep -rn "perl -i"`, `grep -rn 'perl -pi'`, `rg "ruby -i"`, `git log -S "perl -i"`, and `echo "perl -pi …"; cat`. The residue is M3.
- M2 closes. These are denied on both trees: `parallel`, `ionice`, `doas`, `chrt 5`, `unbuffer`, `watch`, `flock /tmp/l`, `strace`, and `case x in x) perl -pi …;; esac`.
- L2 closes. Allowed:
  - `writeSync(1|2, …)`, `writeSync(process.stdout.fd, …)`, `writevSync(process.stderr.fd, …)`
  - `fprintf(STDOUT, …)`, `vfprintf(STDERR, …)`

  Still denied:
  - `writeSync(10, …)`; the fd alternation does not accept a prefix of a longer number
  - `writeSync(fd, …)` next to a stdout write
  - `fprintf($f, …)` next to `fprintf(STDOUT, …)`
  - `writeSync(fs.openSync(p,'w'), …)`
  - `$f=fopen(…,"w"); fprintf($f, …)`

  The 18c deny vectors now use real handles, as L2 suggested.
- A real write cannot hide in a text-tool segment through command substitution or a pipe into perl. Each of these leaves perl in its own segment, and each is denied on the tree:
  - `echo x | perl -pi`, `grep x f && perl -pi`, `rg x; perl -i`
  - `grep x f |& perl`, `echo x & perl`, `echo x; exec perl`, `coproc perl`
  - `git commit -m "$(perl -pi …)"`, `printf '%s' "$(perl -pi …)"`, `` echo `perl -pi …` ``
  - `echo x > >(perl -pi …)`, `grep x <(perl -pi …)`
  - a perl after a comment line

  Of these, the four substitution forms (`git commit -m "$(…)"`, `printf '%s' "$(…)"`, `` echo `…` ``, `>(…)`, `<(…)`) were allowed at HEAD. `xargs perl` is denied, and `xargs grep perl -i` is still denied (I2). An alias cannot shadow a git builtin, and `git -c <k=v> <verb>` is not carved out.
- Running time is linear, not quadratic: one `shell_segments` pass, `split(None, 8)` per segment, and two `ere_match` calls. Process time on 4 KB inputs was 23–47 ms on both trees:
  - 220 segments of `grep 'perl -i' x;`
  - 290 pipes
  - 300 nested `$(`
  - 190 backtick spans
  - 300 heredocs
  - 150 `git -c` segments
  - 300 newline-separated echos
- 18e discrimination:
  - Its allow list was allowed at HEAD and denied by B5 before the fix, so it pins the fix against B5, not against HEAD.
  - The wrapper deny list pins HEAD's behaviour, which guards against M2 coming back.
  - `` echo `perl…` `` and `echo "$(perl…)"` are new denies and pin the anchors.
  - The 200-segment timed deny would fail if the carve-out removed too much.
  - Nothing in 18e pins the H1 shapes (heredoc, or a text tool piped into a shell) or M3's xargs, find, git -C and gh spellings.
- not reached (budget): the L1 Weight record, the test suite (18c/d/e were not run by me), and the full `test_guard_differential` corpus.

## VERDICT
verdict: pass_with_findings
scope_assessment: The fix stays in `hooks/guard/paths.py` and `tests/test_ai_path_guard.py` and changes only the tripwire. It closes M1, M2 and L2. Its carve-out works on `shell_segments` output, which drops heredoc bodies and ignores where a text tool's output goes. That turns HEAD denies into allows (H1, behaviour 2) and leaves part of M1 open (M3). H1 needs a pinning test before close.
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/sdlc/intent/risk-aware-multi-agent-adlc.md | +227 −0 | New |
| docs/sdlc/intent/small-oop-modules.questions.md | +68 −0 | New |
| docs/sdlc/specs/small-oop-modules.md | +450 −0 | New |
| hooks/guard/paths.py | +107 −6 | Edit |
| tests/test_ai_path_guard.py | +172 −0 | Edit |

+1024 −6 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on 5846854b3 (run 7) · (b) green — 5 changed files, all in the task's files
gate: requested G1 at 2026-10-30T23:31:12Z; approved by Ivan Kakurov at 2026-10-30T23:31:34Z via dialog
confirm: none
handoffs: 10 · suite runs: 4 · review passes: 2
