# Review — T-2026-10-25-001 (T4, STRONG, pass 1 of 2)

verdict: pass_with_findings → recorded as `blockers_open` (an in-scope HIGH, no BLOCKER)

| id | sev | in scope | finding | where |
|---|---|---|---|---|
| H1 | HIGH | yes | WRITE_MODE_RE's first-argument walk misses writes HEAD denied: a paren two levels deep in the first argument (`open(os.path.join(os.getcwd(), p), 'w')`, `str(Path.cwd() / p)`, `File.expand_path(File.join(Dir.pwd, p))`, `dirname(getcwd())`), `new IO::File(p, "w")` / `new SplFileObject(p, 'w')`, a comma inside a string in the first argument; WRITE_PATHREPL_RE's `[^,]*` misses `p.replace(os.path.join(a, b))`. Bites when the mode is the only indicator. | `hooks/ai-path-guard.sh:1345,1347` |
| M1 | MEDIUM | yes | known-risks entry understates the residual's extent and says the protected files keep their own patterns, false for interpreter one-liners. | `.ai/project/known-risks.md:195,197` |
| M2 | MEDIUM | yes | docs and hook comment say "after the first argument of open…, new or FileIO"; for `new Class(` and depth-2 parens it did not hold. | `docs/hooks.md:299-304`, `hooks/ai-path-guard.sh:1330-1334` |
| L1 | LOW | yes | INPLACE_RE's `[aclnpsuwW]` drops no-argument switches HEAD's `[a-z]` covered: `perl -gpi`, `-tpi`, `-dpi`, `ruby -vpi`. | `hooks/ai-path-guard.sh:1130` |
| L2 | LOW | yes | new false deny `copy.copy(x)` on a Path line; `.replace(')', '')` and `datetime.now().replace(microsecond=0)` still denied. | `hooks/ai-path-guard.sh:1345-1346` |
| I1 | INFO | yes | WRITE_CALL_RE has no `writeSync`/`writevSync`, `fprintf`, Ruby `puts`/`<<` on a handle; older than the diff. | `hooks/ai-path-guard.sh:1343` |

Examined and clean (reviewer): regex running time in process and through grep (worst 28 ms at 3997 chars, ≤21 ms at 200 KB), shell quoting of the embedded regexes, the INPLACE_RE loop (a superset of HEAD's), L4 spellings, the new test block's names and coverage.

## Remediation R1 (one batch)
H1, M1, M2, L1, L2 fixed; I1 recorded in known-risks, not fixed (outside the goal).

- H1: `FIRST_ARG` reads plain characters, quoted strings and parens three deep; `new Class(` accepted; PATHREPL uses the same walk. Pinned by 10 deny cases (9 failed before R1; the shell-escaped-quote case passed and stays).
- L1: in-place cluster `[acdfghlnpsStTuUvwWXy]*i`, separate-argument switches `[CEIMmr]`; pinned by `-gpi`, `-tpi`, `ruby -vpi`, `ruby -E utf-8 -i`.
- L2: `copy.copy(` taken out before PATHCOPY; `.replace(')', '')` allowed by the string walk; both pinned.
- M1/M2: known-risks entry restated (extent, and that the tripwire is the only check for one-liners); docs/hooks.md and the hook comment describe the walk.
- Running time: MODE and PATHREPL with 18 pads at 4 KB in process and 40 KB/200 KB through GNU grep 3.12: worst 15 ms. (The session shell's `grep` is a function that runs ugrep, which is quadratic on `new[[:space:]][^,]*,`; the hook resolves `/usr/bin/grep`.)
- Guard tests 637/0 (622/15 before R1). Suite run 2 exit 0 in 311 s; e2e run 2 exit 0. No BLOCKER, so no re-review; the green run closes the HIGH.
