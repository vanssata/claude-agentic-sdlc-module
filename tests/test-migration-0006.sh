#!/usr/bin/env bash
# Migration 0006: a schema-5 project stops carrying the shared policies, agent
# contracts, workflows and templates. The router learns where they live first;
# unedited copies are deleted only behind --confirm-delete; edited ones become
# overrides; nothing is deleted through a symlink, outside the project, or
# while an installed home lacks the shared file it would fall back to; git is
# the rollback (T-2026-10-13-004, plan rev 2 Step 7).
set -uo pipefail
. "$(dirname "$0")/lib.sh"

UPDATE="$PLUGIN_ROOT/skills/project-update/update.py"
FIX="$PLUGIN_ROOT/tests/fixtures/project-update"
OLDS="$FIX/shared-old"
MIG="$PLUGIN_ROOT/skills/project-update/migrations/0006_shared_files.py"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# Pinned: no real home is ever inspected, and the shared tree is this checkout's.
export HOME="$W/home"; mkdir -p "$HOME"
unset CODEX_HOME AI_UNATTENDED CLAUDE_AGENTIC_MIGRATIONS
export CLAUDE_AGENTIC_SHARED="$PLUGIN_ROOT/ai"
G=(git -c user.name=tester -c user.email=tester@example.invalid -c commit.gpgsign=false)
SHARED=$(cd "$PLUGIN_ROOT/ai" && find . -type f | sed 's|^\./|.ai/|' | LC_ALL=C sort)
N=$(printf '%s\n' "$SHARED" | wc -l)
REPORT=".ai/reports/project-update-$(date -u +%Y-%m-%d)"

# v5_project DIR [RUNTIME]: a committed schema-5 project as the cut-over finds
# it — today's scaffold, every shared file as it was carried, three of them at
# their oldest shipped version, the schema-5 router and VERSION 5.
v5_project() {
    local d="$1" rt="${2:-claude}"; mkdir -p "$d"
    bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$d" --runtime "$rt" >/dev/null
    cp -r "$PLUGIN_ROOT/ai/." "$d/.ai/"
    for f in workflows/feature.md agents/manager.md policies/model-routing.md; do cp "$OLDS/$f" "$d/.ai/$f"; done
    cp "$OLDS/AGENTS.v5.md" "$d/.ai/AGENTS.md"
    cp -r "$FIX/schema-v5/.ai/." "$d/.ai/"
    git init -q "$d" && "${G[@]}" -C "$d" add -A && "${G[@]}" -C "$d" commit -qm "schema 5"
}
upd() { python3 "$UPDATE" "$@"; }
confirm() { AI_UNATTENDED=1 python3 "$UPDATE" "$1" --apply --confirm-delete tester; }
tree_sum() { (cd "$1" && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum); }
# tracked DIR: exec bit, sha and path of every file git holds — what the git
# route restores (git keeps the exec bit; the rest of a mode is the umask's).
tracked() { (cd "$1" && git ls-files -z | xargs -0 -I{} sh -c 'printf "%s %s %s\n" "$([ -x "$1" ] && echo x || echo -)" "$(sha256sum < "$1" | cut -c1-64)" "$1"' _ {}); }
present() { local d="$1" n=0 f; for f in $SHARED; do [ -f "$d/$f" ] && n=$((n + 1)); done; echo "$n"; }
sections() { grep -c '^## Shared files$' "$1/.ai/AGENTS.md"; }
# router_first OUT: the router's line comes before the first delete? line.
router_first() {
    local r d
    r=$(printf '%s\n' "$1" | grep -n '^  [a-z?]* *\.ai/AGENTS\.md ' | head -1 | cut -d: -f1)
    d=$(printf '%s\n' "$1" | grep -n '^  delete? ' | head -1 | cut -d: -f1)
    [ -n "$r" ] && { [ -z "$d" ] || [ "$r" -lt "$d" ]; }
}

echo "== the migration itself"
[ "$N" -eq 29 ] && pass "the shared tree holds 29 files" || fail "the shared tree holds $N files, expected 29"
grep -nE 'claude|codex' "$MIG" >/dev/null && fail "0006 names a runtime in lowercase (L1)" "$(grep -nE 'claude|codex' "$MIG")" \
    || pass "0006 names no runtime (L1)"
# A schema-5 project ends at the plugin's schema, which later migrations raise (0007).
CUR=$(python3 -c "import sys; sys.path.insert(0, '$PLUGIN_ROOT/skills/project-update'); import migrations; print(migrations.CURRENT)")
[ "$CUR" -ge 6 ] && pass "the registry reaches schema 6 or later ($CUR)" || fail "CURRENT is $CUR, below 6"
[ "$(cat "$PLUGIN_ROOT/skills/ai-init/templates/.ai/VERSION")" = "$CUR" ] && pass "a fresh scaffold starts at the plugin's schema" || fail "the VERSION template is not $CUR"

echo "== R1: the shipped schema-5 router; dry run and the gate"
R1="$W/r1"; v5_project "$R1"
chmod 755 "$R1/.ai/templates/review-report.md"; "${G[@]}" -C "$R1" commit -qam "an exec bit to keep"
before=$(tree_sum "$R1")
out=$(upd "$R1" 2>&1); rc=$?
[ $rc -eq 0 ] && [ "$before" = "$(tree_sum "$R1")" ] && pass "the dry run exits 0 and writes nothing" || fail "dry run: rc=$rc or files changed" "$out"
grep -q "^  schema    5 -> $CUR " <<<"$out" && pass "the dry run names the schema step" || fail "no schema line" "$out"
[ "$(printf '%s\n' "$out" | grep -c '^  delete? ')" -eq 29 ] && pass "all 29 shipped copies are proposed, the oldest versions too" \
    || fail "expected 29 delete? lines" "$(printf '%s\n' "$out" | grep '^  delete? ')"
grep -q '^  update  *\.ai/AGENTS\.md  *\[0006\] unchanged since it was installed' <<<"$out" \
    && pass "the shipped router is replaced" || fail "the router is not replaced" "$out"
grep -qE 'policies/(safety|security)\.md' <<<"$out" && fail "safety.md or security.md is named" "$out" \
    || pass "safety.md and security.md are never named"
grep -q 'commit .ai/ first' <<<"$out" && fail "a clean .ai/ gets the commit-first hint" || pass "a committed .ai/ gets no commit-first hint"
out=$(upd "$R1" --check); rc=$?
[ $rc -eq 1 ] && grep -qE "^project is behind the installed plugin: schema 5 -> $CUR, "'(.*, )?29 deletion\(s\) a human must confirm, the schema stays at 5 until they are settled — run /project-update$' <<<"$out" \
    && pass "--check names the deletions and the held schema" || fail "--check: rc=$rc" "$out"
upd "$R1" --apply >/dev/null 2>&1
[ "$(cat "$R1/.ai/VERSION")" = 5 ] && [ "$(sections "$R1")" = 1 ] && [ "$(present "$R1")" = 29 ] \
    && pass "a plain --apply writes the router, deletes nothing and keeps VERSION 5" \
    || fail "plain apply: VERSION $(cat "$R1/.ai/VERSION"), sections $(sections "$R1"), present $(present "$R1")"
out=$(CLAUDECODE=1 python3 "$UPDATE" "$R1" --apply --confirm-delete tester </dev/null 2>&1); rc=$?
[ $rc -eq 5 ] && [ "$(present "$R1")" = 29 ] && pass "inside an agent session without a terminal --confirm-delete exits 5" \
    || fail "agent session: rc=$rc" "$out"
out=$(confirm "$R1" 2>&1); rc=$?
[ $rc -eq 0 ] && [ "$(present "$R1")" = 0 ] && pass "the confirmed run deletes all 29" || fail "confirmed: rc=$rc, $(present "$R1") left" "$out"
[ "$(cat "$R1/.ai/VERSION")" = "$CUR" ] && pass "and the schema reaches $CUR" || fail "VERSION is $(cat "$R1/.ai/VERSION")"
bad=""
for f in $SHARED; do
    "${G[@]}" -C "$R1" show "HEAD:$f" | cmp -s - "$R1/$REPORT/original/$f" || bad="$bad $f"
done
[ -z "$bad" ] && pass "every original is kept byte-identical" || fail "originals differ or are missing:" "$bad"
[ "$(stat -c %a "$R1/$REPORT/original/.ai/templates/review-report.md")" = 755 ] && pass "with its mode" || fail "the original lost its mode"
rec="$R1/$REPORT/migration.json"
[ "$(jq '.deletions | length' "$rec")" = 29 ] && [ "$(jq -r '[.deletions[].confirmed_by] | unique | join(",")' "$rec")" = tester ] \
    && [ "$(jq -r '[.deletions[].via] | unique | join(",")' "$rec")" = unattended ] && [ "$(jq -r .to "$rec")" = "$CUR" ] \
    && pass "migration.json records each deletion, who confirmed it and how" || fail "migration.json" "$(cat "$rec")"
out=$(upd "$R1" 2>&1)
grep -q '^0 automatic, 0 conflict' <<<"$out" && pass "a second run has nothing to do" || fail "second run" "$out"
upd "$R1" --check >/dev/null && pass "--check exits 0 at schema $CUR" || fail "--check should exit 0 at schema $CUR"

echo "== L5: the empty directories stay, and the shared copy applies"
[ -d "$R1/.ai/agents" ] && [ -z "$(ls -A "$R1/.ai/agents")" ] && pass "an empty .ai/agents/ remains" || fail ".ai/agents/ should remain, empty"
out=$(cd "$R1" && "$PLUGIN_ROOT/scripts/ai-path" agents/manager.md)
[ "$out" = "$PLUGIN_ROOT/ai/agents/manager.md" ] && pass "ai-path resolves to the shared copy" || fail "ai-path" "$out"

echo "== M6: a migrated project — a copy that comes back, an edited one"
cp "$PLUGIN_ROOT/ai/policies/git.md" "$R1/.ai/policies/git.md"
{ cat "$PLUGIN_ROOT/ai/policies/tooling.md"; printf 'our own rule\n'; } > "$R1/.ai/policies/tooling.md"
out=$(upd "$R1" 2>&1)
grep -qE '^  delete\?  *\.ai/policies/git\.md  *\[shared\] identical to a shipped version' <<<"$out" \
    && pass "a re-added shipped copy is offered for deletion again" || fail "no delete? [shared]" "$out"
[ "$(printf '%s\n' "$out" | grep -c 'override the plugin.s shared copy and no longer receive its changes: .ai/policies/tooling.md')" = 1 ] \
    && pass "an edited copy is named once, as an override" || fail "no aggregated override hint" "$out"
grep -q 'commit .ai/ first' <<<"$out" && pass "an uncommitted .ai/ gets the commit-first hint (M4)" || fail "no commit-first hint" "$out"
upd "$R1" --apply >/dev/null 2>&1
[ "$(cat "$R1/.ai/VERSION")" = "$CUR" ] && [ -f "$R1/.ai/policies/git.md" ] && pass "VERSION stays $CUR and nothing is deleted unconfirmed" \
    || fail "M6 plain apply changed VERSION or deleted"
confirm "$R1" >/dev/null 2>&1
[ ! -e "$R1/.ai/policies/git.md" ] && grep -q 'our own rule' "$R1/.ai/policies/tooling.md" \
    && pass "the confirmed run deletes the shipped copy and keeps the override" || fail "M6 confirmed run"

echo "== edited, CRLF and project-only files"
E="$W/edited"; v5_project "$E"
printf 'x' >> "$E/.ai/policies/git.md"
sed -i 's/$/\r/' "$E/.ai/workflows/bugfix.md"
printf 'ours\n' > "$E/.ai/workflows/custom.md"
mkdir -p "$E/.ai/policies/adopted"; printf 'adopted\n' > "$E/.ai/policies/adopted/x.md"
"${G[@]}" -C "$E" add -A && "${G[@]}" -C "$E" commit -qm edits
crlf=$(sha256sum < "$E/.ai/workflows/bugfix.md")
out=$(upd "$E" 2>&1)
grep -q 'hint      .ai/policies/git.md overrides the plugin.s shared copy' <<<"$out" \
    && pass "a one-byte edit is an override" || fail "no override hint for git.md" "$out"
[ "$(printf '%s\n' "$out" | grep -c '^  delete? ')" = 28 ] && pass "the other 28 are proposed, the CRLF copy among them" || fail "expected 28 delete?" "$out"
confirm "$E" >/dev/null 2>&1
[ -f "$E/.ai/policies/git.md" ] && [ ! -e "$E/.ai/workflows/bugfix.md" ] && pass "the edited copy stays; the CRLF copy is deleted (L4)" \
    || fail "edited/CRLF outcome wrong"
[ "$(sha256sum < "$E/$REPORT/original/.ai/workflows/bugfix.md")" = "$crlf" ] && pass "the CRLF original is kept byte-identical" \
    || fail "the CRLF original changed"
[ "$(cat "$E/.ai/workflows/custom.md")" = ours ] && [ "$(cat "$E/.ai/policies/adopted/x.md")" = adopted ] \
    && pass "a project-only workflow and an adopted policy are untouched" || fail "project-only files touched"
[ "$(cat "$E/.ai/VERSION")" = "$CUR" ] && pass "an override does not hold the schema" || fail "VERSION is $(cat "$E/.ai/VERSION")"
out=$(upd "$E" 2>&1)
grep -q '^0 automatic, 0 conflict' <<<"$out" && grep -q 'no longer receive its changes: .ai/policies/git.md' <<<"$out" \
    && pass "a second run changes nothing and names the override" || fail "second run on the edited project" "$out"

echo "== the router fixtures"
add_rows() {  # add_rows DIR: two rows the way --adopt writes them
    PLUGIN_ROOT="$PLUGIN_ROOT" python3 -I - "$1" <<'PY'
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "skills", "project-update"))
import adopt, update as U
plan = U.Plan(sys.argv[1])
assert adopt.add_router_rows(plan, ["| a tool the project adopted | `policies/adopted/x.md` |",
                                    "| the adopted specs | `docs/adopted/` |"]) == 2
open(os.path.join(sys.argv[1], ".ai", "AGENTS.md"), "wb").write(plan.items[-1]["content"])
PY
}
R2="$W/r2"; v5_project "$R2"; add_rows "$R2"
R3="$W/r3"; v5_project "$R3"
last=$(grep -n '^|' "$R3/.ai/AGENTS.md" | tail -1 | cut -d: -f1)
sed -i "${last}s/ |\$/ (our own wording) |/" "$R3/.ai/AGENTS.md"; add_rows "$R3"
R4="$W/r4"; v5_project "$R4"; sed -i 's/^## Doing X → read Y$/## Where to look/' "$R4/.ai/AGENTS.md"
R5="$W/r5"; v5_project "$R5"; rm "$R5/.ai/AGENTS.md"
for d in "$R2" "$R3" "$R4" "$R5"; do "${G[@]}" -C "$d" add -A && "${G[@]}" -C "$d" commit -qm router; done
for d in "$R2" "$R3" "$R4" "$R5"; do
    out=$(upd "$d" 2>&1)
    router_first "$out" && pass "$(basename "$d"): the router item precedes the first delete?" || fail "$(basename "$d"): router not first" "$out"
done
out=$(upd "$R5" 2>&1)
grep -q '^  create  *\.ai/AGENTS\.md  *\[0006\]' <<<"$out" && pass "r5: a missing router is created" || fail "r5: no create" "$out"
out=$(upd "$R2" 2>&1)
grep -q 'Shared files section added; your router edits kept' <<<"$out" && pass "r2: an adopted router gets the section inserted" \
    || fail "r2: no insertion" "$out"
for d in "$R2" "$R3" "$R4" "$R5"; do
    confirm "$d" >/dev/null 2>&1
    [ "$(sections "$d")" = 1 ] && [ "$(present "$d")" = 0 ] && [ "$(cat "$d/.ai/VERSION")" = "$CUR" ] \
        && pass "$(basename "$d"): after the confirmed run the section is there exactly once" \
        || fail "$(basename "$d"): sections $(sections "$d"), present $(present "$d"), VERSION $(cat "$d/.ai/VERSION")"
done
for d in "$R2" "$R3"; do
    grep -qF '| a tool the project adopted | `policies/adopted/x.md` |' "$d/.ai/AGENTS.md" \
        && grep -qF '| the adopted specs | `docs/adopted/` |' "$d/.ai/AGENTS.md" \
        && pass "$(basename "$d"): the adopt rows survive" || fail "$(basename "$d"): adopt rows lost"
    sec=$(grep -n '^## Shared files$' "$d/.ai/AGENTS.md" | cut -d: -f1); tbl=$(grep -n '^## Doing X → read Y$' "$d/.ai/AGENTS.md" | cut -d: -f1)
    [ -n "$sec" ] && [ -n "$tbl" ] && [ "$sec" -lt "$tbl" ] && pass "$(basename "$d"): the section sits before the routing table" \
        || fail "$(basename "$d"): section placement"
done
grep -q '(our own wording) |$' "$R3/.ai/AGENTS.md" && pass "r3: the edited last row survives" || fail "r3: the edited row was lost"
grep -q '^## Where to look$' "$R4/.ai/AGENTS.md" && [ "$(grep -n '^## Shared files$' "$R4/.ai/AGENTS.md" | cut -d: -f1)" -gt "$(grep -n '^## Keeping this directory true$' "$R4/.ai/AGENTS.md" | cut -d: -f1)" ] \
    && pass "r4: with the heading renamed the section is appended, the rename kept" || fail "r4: placement" "$(cat "$R4/.ai/AGENTS.md")"
out=$(upd "$R4" 2>&1)
[ "$(sections "$R4")" = 1 ] && ! grep -qE '^  (update|merge|conflict)  *\.ai/AGENTS\.md' <<<"$out" \
    && pass "r4: the next run neither doubles the section nor conflicts" || fail "r4: a later run rewrites or conflicts on the router" "$out"

echo "== R7: a router whose section a human moved is merged around the section"
# At schema 6, a human moved the section to the end. The rest of the router is
# merged without it, so the move is neither doubled nor a conflict.
R7="$W/r7"; v5_project "$R7"; confirm "$R7" >/dev/null 2>&1
python3 - "$R7/.ai/AGENTS.md" <<'PY'
import sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
s, e = t.index("\n## Shared files"), t.index("\n## Doing X → read Y")
open(p, "w", encoding="utf-8").write(t[:s] + t[e:] + t[s:e])
PY
"${G[@]}" -C "$R7" add -A && "${G[@]}" -C "$R7" commit -qm "section moved"
moved=$(sha256sum < "$R7/.ai/AGENTS.md")
out=$(upd "$R7" --apply 2>&1)
! grep -qE '^  (update|merge|conflict)  *\.ai/AGENTS\.md' <<<"$out" \
    && pass "r7: the moved section is neither doubled nor a conflict" || fail "r7: router rewritten or conflicting" "$out"
[ "$(sha256sum < "$R7/.ai/AGENTS.md")" = "$moved" ] && [ "$(sections "$R7")" = 1 ] \
    && pass "r7: the human's router is kept, with one section" || fail "r7: the router was rewritten" "$(grep -n '^## ' "$R7/.ai/AGENTS.md")"

echo "== R8: a router with its own non-negotiable, or an edited last line, stays quiet after 0006"
for kind in appended edited; do
    d="$W/r8-$kind"; v5_project "$d"
    python3 - "$d/.ai/AGENTS.md" "$kind" <<'PY'
import sys
p, kind = sys.argv[1], sys.argv[2]
t = open(p, encoding="utf-8").read()
i = t.index("\n\n## Doing X → read Y")
t = t[:i] + "\n- our own non-negotiable" + t[i:] if kind == "appended" else t[:i] + " (ours)" + t[i:]
open(p, "w", encoding="utf-8").write(t)
PY
    "${G[@]}" -C "$d" add -A && "${G[@]}" -C "$d" commit -qm "$kind"
    confirm "$d" >/dev/null 2>&1
    [ "$(sections "$d")" = 1 ] && [ "$(cat "$d/.ai/VERSION")" = "$CUR" ] && pass "r8-$kind: migrated, one section" \
        || fail "r8-$kind: sections $(sections "$d"), VERSION $(cat "$d/.ai/VERSION")"
    "${G[@]}" -C "$d" add -A && "${G[@]}" -C "$d" commit -qm migrated
    for run in 1 2; do
        out=$(upd "$d" --apply 2>&1)
        ! grep -qE '^  (update|merge|conflict)  *\.ai/AGENTS\.md' <<<"$out" \
            && pass "r8-$kind: run $run after the migration leaves the router alone" || fail "r8-$kind: run $run touches the router" "$out"
    done
done

echo "== R10: a router edited on an older version receives the plugin's later changes"
# The blob is a router the plugin shipped before the schema-5 one; the human
# added a note to it. The confirmed 0006 run inserts the section and merges
# the plugin's later router changes in the same pass; nothing stays stale.
R10="$W/r10"; v5_project "$R10"
python3 - "$PLUGIN_ROOT/skills/project-update/history/blobs/21319ce04158178b1d66ee8514e32c43bb1b4cd9cee11a456a9a863a5998c6ce" "$R10" <<'PY'
import sys
blob, d = sys.argv[1], sys.argv[2]
open(d + "/.ai/AGENTS.md", "wb").write(open(blob, "rb").read() + b"\n## our routing note\nalways ask us first\n")
PY
"${G[@]}" -C "$R10" add -A && "${G[@]}" -C "$R10" commit -qm "older router, edited"
confirm "$R10" >/dev/null 2>&1
"${G[@]}" -C "$R10" add -A && "${G[@]}" -C "$R10" commit -qm migrated
python3 - "$R10" "$PLUGIN_ROOT/skills/ai-init/templates/.ai/AGENTS.md" <<'PY' && pass "r10: one section, the note kept, every other line as the plugin ships it" || fail "r10: merged router"
import re, sys
strip = lambda t: re.sub(r"(?ms)^## Shared files$.*?(?=^## )", "", t)
ours = open(sys.argv[1] + "/.ai/AGENTS.md").read()
assert ours.count("\n## Shared files\n") == 1
assert "always ask us first" in ours
assert strip(ours).replace("\n## our routing note\nalways ask us first\n", "") == strip(open(sys.argv[2]).read())
PY
out=$(upd "$R10" 2>&1)
! grep -qE '^  (update|merge|conflict)  *\.ai/AGENTS\.md' <<<"$out" && pass "r10: and the run after that is quiet" || fail "r10: not settled" "$out"

echo "== R9: an edited CRLF router gets the section before the table, in CRLF"
R9="$W/r9"; v5_project "$R9"
python3 - "$R9/.ai/AGENTS.md" <<'PY'
import sys
p = sys.argv[1]; t = open(p, "rb").read()
i = t.index("\n\n## Doing X → read Y".encode())
open(p, "wb").write((t[:i] + b"\n- ours" + t[i:]).replace(b"\n", b"\r\n"))
PY
"${G[@]}" -C "$R9" add -A && "${G[@]}" -C "$R9" commit -qm crlf
confirm "$R9" >/dev/null 2>&1
python3 - "$R9/.ai/AGENTS.md" <<'PY' && pass "r9: section before the table, line endings all CRLF" || fail "r9: placement or mixed endings" "$(head -c 400 "$R9/.ai/AGENTS.md" | od -c | head -5)"
import sys
t = open(sys.argv[1], "rb").read()
assert t.count(b"\r\n") == t.count(b"\n"), "mixed endings"
assert t.count(b"## Shared files\r\n") == 1
assert t.index(b"## Shared files") < t.index("## Doing X → read Y".encode())
PY

echo "== undeclared files in the shared tree are never deletion candidates"
X="$W/extra-tree"; cp -r "$PLUGIN_ROOT/ai" "$X"
cp "$PLUGIN_ROOT/skills/ai-init/templates/.ai/policies/security.md" "$X/policies/security.md"
cp "$PLUGIN_ROOT/skills/ai-init/templates/.ai/VERSION" "$X/VERSION"
XP="$W/extra"; v5_project "$XP"; confirm "$XP" >/dev/null 2>&1
"${G[@]}" -C "$XP" add -A && "${G[@]}" -C "$XP" commit -qm migrated
out=$(CLAUDE_AGENTIC_SHARED="$X" python3 "$UPDATE" "$XP" 2>&1)
! grep -qE '^  delete\?  *\.ai/(VERSION|policies/security\.md)' <<<"$out" \
    && pass "a planted policies/security.md or VERSION is not offered for deletion" || fail "project-owned file offered for deletion" "$out"
grep -q 'outside the shared set, ignored' <<<"$out" && pass "the extra files are named in a hint" || fail "no undeclared-file hint" "$out"
[ "$(python3 -c "import sys; sys.path.insert(0, '$PLUGIN_ROOT/skills/project-update'); import update; print(len(update.declared_shared()))")" = 29 ] \
    && pass "the declared shared set is 0006's 29" || fail "declared_shared() is not 29"

echo "== R6: a symlinked router stops the confirmed run before any deletion"
R6="$W/r6"; v5_project "$R6"
mv "$R6/.ai/AGENTS.md" "$R6/.ai/router-real.md" && ln -s router-real.md "$R6/.ai/AGENTS.md"
"${G[@]}" -C "$R6" add -A && "${G[@]}" -C "$R6" commit -qm symlink
out=$(confirm "$R6" 2>&1); rc=$?
[ $rc -eq 3 ] && grep -q 'aborted at update .ai/AGENTS.md' <<<"$out" && pass "exit 3 at the router item" || fail "r6: rc=$rc" "$out"
[ "$(present "$R6")" = 29 ] && [ "$(cat "$R6/.ai/VERSION")" = 5 ] && pass "every shared copy is still there, VERSION 5" \
    || fail "r6: $(present "$R6") present, VERSION $(cat "$R6/.ai/VERSION")"

echo "== Q5: a Gemini project keeps safety.md and security.md"
GM="$W/gemini"; v5_project "$GM" gemini
out=$(upd "$GM" 2>&1)
grep -qE 'policies/(safety|security)\.md' <<<"$out" && fail "gemini: safety/security named" "$out" || pass "gemini: neither is named"
confirm "$GM" >/dev/null 2>&1
[ -f "$GM/.ai/policies/safety.md" ] && [ -f "$GM/.ai/policies/security.md" ] && [ "$(present "$GM")" = 0 ] \
    && pass "gemini: both remain after the confirmed run, the shared copies are gone" || fail "gemini: outcome wrong"

echo "== M2: no deletion while a fallback is missing"
M2="$W/m2"; v5_project "$M2"; before=$(tree_sum "$M2")
out=$(CLAUDE_AGENTIC_SHARED=/nonexistent python3 "$UPDATE" "$M2" 2>&1); rc=$?
[ $rc -eq 2 ] && [ "$before" = "$(tree_sum "$M2")" ] && pass "no shared tree: exit 2, nothing written" || fail "no tree: rc=$rc" "$out"
out=$(AI_UNATTENDED=1 CLAUDE_AGENTIC_SHARED=/nonexistent python3 "$UPDATE" "$M2" --apply --confirm-delete tester 2>&1); rc=$?
[ $rc -eq 2 ] && [ "$before" = "$(tree_sum "$M2")" ] && pass "and the confirmed run writes nothing either" || fail "no tree, confirmed: rc=$rc" "$out"
cp -r "$PLUGIN_ROOT/ai" "$W/partial"; rm "$W/partial/policies/git.md"
out=$(CLAUDE_AGENTIC_SHARED="$W/partial" python3 "$UPDATE" "$M2" 2>&1); rc=$?
[ $rc -eq 2 ] && grep -q 'policies/git.md' <<<"$out" && pass "a local tree missing one file exits 2 and names it" || fail "partial: rc=$rc" "$out"
MC="$W/m2codex"; v5_project "$MC" codex
mkdir -p "$W/h2/.codex/skills/project-update"
out=$(HOME="$W/h2" python3 "$UPDATE" "$MC" 2>&1); rc=$?
[ $rc -eq 2 ] && grep -qF "$W/h2/.codex" <<<"$out" && pass "a declared home with the plugin but no tree exits 2 and names the home" \
    || fail "codex home: rc=$rc" "$out"
out=$(HOME="$W/h3" python3 "$UPDATE" "$MC" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "with no such home on this machine it proceeds" || fail "no home: rc=$rc" "$out"

echo "== M9: never through a symlink, never outside the project"
M9="$W/m9"; v5_project "$M9"
mv "$M9/.ai/workflows" "$W/outside-workflows" && ln -s "$W/outside-workflows" "$M9/.ai/workflows"
cp "$M9/.ai/policies/git.md" "$M9/.ai/project/git-real.md" && rm "$M9/.ai/policies/git.md" && ln -s ../project/git-real.md "$M9/.ai/policies/git.md"
"${G[@]}" -C "$M9" add -A && "${G[@]}" -C "$M9" commit -qm links
out=$(upd "$M9" 2>&1)
[ "$(printf '%s\n' "$out" | grep -c 'hint      .ai/workflows/.* is a symlink, so this update never deletes it')" = 5 ] \
    && pass "a symlinked directory: a hint per file, no deletion" || fail "no symlink hints for workflows" "$out"
grep -q 'hint      .ai/policies/git.md: .ai/policies/git.md is a symlink' <<<"$out" && pass "a symlinked file: a hint" \
    || fail "no symlink hint for git.md" "$out"
grep -qE '^  delete\?  *\.ai/(workflows/|policies/git\.md)' <<<"$out" && fail "a symlinked path is proposed for deletion" "$out" \
    || pass "neither is proposed for deletion"
confirm "$M9" >/dev/null 2>&1
[ "$(ls "$W/outside-workflows" | wc -l)" = 5 ] && [ -L "$M9/.ai/policies/git.md" ] && [ -f "$M9/.ai/project/git-real.md" ] \
    && pass "after the confirmed run the outside files and the link are intact" || fail "M9: something was deleted"

echo "== M3: the hash sweep — every shared version stays on record without its blob; real bytes are deleted, a flipped byte never is"
sweep=$(PLUGIN_ROOT="$PLUGIN_ROOT" W="$W" OLDS="$OLDS" python3 -I - <<'PY' 2>&1
import hashlib, json, os, subprocess, sys
sys.dont_write_bytecode = True
root = os.environ["PLUGIN_ROOT"]
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import update as U
hist = U.HISTORY
index = json.load(open(os.path.join(hist, "index.json")))
history = U.History(hist)
shared = sorted(U.shared_files())
today = {p: open(os.path.join(root, "ai", p[len(".ai/"):]), "rb").read() for p in shared}
shared_keys = {"ai-init/" + p for p in shared}
owned = {h for k, v in index.items() if k not in shared_keys for h in v}
total, unrecorded, blobbed = 0, [], []
for p in shared:
    key = "ai-init/" + p
    known = history.hashes(key)
    total += len(known)
    if not known or known != set(index.get(key, [])) or hashlib.sha256(today[p]).hexdigest() not in known:
        unrecorded.append(p)
    # A shared version keeps its hash and loses its blob, unless a project-owned
    # key ships the same bytes.
    blobbed += ["%s %s" % (p, h[:12]) for h in known - owned if os.path.exists(os.path.join(hist, "blobs", h))]
for p in unrecorded:
    print("FAIL no hash on record (or not today's) for: " + p)
for b in blobbed:
    print("FAIL a blob only a shared key references is still shipped: " + b)

# The byte-level path: the old versions kept as fixtures in shared-old/, then
# today's shared tree, each through build_plan as a project carries them.
proj = os.path.join(os.environ["W"], "sweep")
os.makedirs(proj)
subprocess.run(["bash", os.path.join(root, "skills", "ai-init", "scaffold-ai.sh"), proj, "--runtime", "claude"],
               check=True, stdout=subprocess.DEVNULL)
open(os.path.join(proj, ".ai", "VERSION"), "w").write("5\n")
old = dict(today)
for p in shared:
    f = os.path.join(os.environ["OLDS"], p[len(".ai/"):])
    if os.path.isfile(f):
        old[p] = open(f, "rb").read()

def put(p, data):
    os.makedirs(os.path.dirname(os.path.join(proj, p)), exist_ok=True)
    open(os.path.join(proj, p), "wb").write(data)

bad, flipped_bad = [], []
for r, carried in enumerate((old, today)):
    for p in shared:
        put(p, carried[p])
    plan = U.build_plan(proj)
    dels = {i["target"] for i in plan.items if i["action"] == "delete?"}
    bad += ["%s r%d" % (p, r) for p in shared if p not in dels]
    for p in shared:
        put(p, carried[p][:-1] + bytes([carried[p][-1] ^ 1]))
    plan = U.build_plan(proj)
    dels = {i["target"] for i in plan.items if i["action"] == "delete?"}
    over = "\n".join(plan.hints)
    flipped_bad += ["%s r%d" % (p, r) for p in shared if p in dels or "%s overrides" % p not in over]
print("hash sweep: %d keys, %d versions; %d not on record; %d with a blob; bytes: 2 rounds, %d old fixtures; "
      "%d not deleted; flipped: %d not an override"
      % (len(shared), total, len(unrecorded), len(blobbed), sum(old[p] != today[p] for p in shared),
         len(bad), len(flipped_bad)))
for b in bad:
    print("FAIL shipped version not proposed for deletion: " + b)
for b in flipped_bad:
    print("FAIL flipped version not an override: " + b)
PY
)
printf '%s\n' "$sweep" | grep '^hash sweep:' | sed 's/^/  /'
if [ -n "${M3_LOG:-}" ]; then printf '%s\n' "$sweep" > "$M3_LOG"; fi
grep -qE '^hash sweep: 29 keys, [0-9]+ versions; 0 not on record; 0 with a blob; bytes: 2 rounds, 3 old fixtures; 0 not deleted; flipped: 0 not an override$' <<<"$sweep" \
    && ! grep -q '^FAIL\|Traceback' <<<"$sweep" \
    && pass "every shared version is on record by hash alone; real bytes are deleted; one flipped byte makes it an override" \
    || fail "hash sweep" "$(printf '%s\n' "$sweep" | head -20)"

echo "== rollback rehearsal: git first"
RB="$W/rb"; v5_project "$RB"
chmod 755 "$RB/.ai/agents/risk.md"; "${G[@]}" -C "$RB" commit -qam "an exec bit"
snap=$(tracked "$RB")
first=$(upd "$RB" 2>&1 | grep '^  delete? ' | LC_ALL=C sort)
confirm "$RB" >/dev/null 2>&1
mkdir -p "$W/reg5"; cp "$PLUGIN_ROOT/skills/project-update/migrations/000"[1-5]_*.py "$W/reg5/"
CLAUDE_AGENTIC_MIGRATIONS="$W/reg5" python3 "$UPDATE" "$RB" --check >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && pass "a 0001-0005 plugin refuses the migrated project (exit 2)" || fail "old registry on schema $CUR: rc=$rc"
"${G[@]}" -C "$RB" checkout -q HEAD -- .ai
[ "$snap" = "$(tracked "$RB")" ] && pass "git checkout restores every file byte- and exec-bit-identical, router included" \
    || fail "the git route did not restore the tree" "$(diff <(printf '%s\n' "$snap") <(tracked "$RB") | head -5)"
[ "$(cat "$RB/.ai/VERSION")" = 5 ] && pass "and VERSION 5" || fail "VERSION is $(cat "$RB/.ai/VERSION") after the restore"
CLAUDE_AGENTIC_MIGRATIONS="$W/reg5" python3 "$UPDATE" "$RB" --check >/dev/null 2>&1; rc=$?
{ [ $rc -eq 0 ] || [ $rc -eq 1 ]; } && pass "the 0001-0005 plugin reads the restored project (exit $rc)" || fail "old registry on the restored tree: rc=$rc"
again=$(upd "$RB" 2>&1 | grep '^  delete? ' | LC_ALL=C sort)
[ -n "$first" ] && [ "$first" = "$again" ] && pass "the new plugin re-plans the same delete? list" || fail "re-plan differs"
confirm "$RB" >/dev/null 2>&1
for d in "$RB"/.ai/reports/project-update-*/; do
    jq -r '.deletions[].path' "$d/migration.json" | while IFS= read -r p; do cp -p "$d/original/$p" "$RB/$p"; done
done
[ "$(present "$RB")" = 29 ] && "${G[@]}" -C "$RB" diff --quiet -- $(cd "$RB" && printf '%s ' $SHARED) \
    && pass "the jq fallback restores every deletion" || fail "the jq fallback did not restore the copies"
[ "$(sections "$RB")" = 1 ] && [ "$(cat "$RB/.ai/VERSION")" = "$CUR" ] \
    && pass "but leaves the router new and VERSION $CUR — its limit: git is the rollback" || fail "jq fallback: router or VERSION"

summary "migration 0006"
