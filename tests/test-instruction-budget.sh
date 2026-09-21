#!/usr/bin/env bash
# The instruction stubs: one source, no drift, and — from the diet onwards —
# a size every always-loaded file has to stay under.
#
# Today this suite proves only that the committed templates are what
# instructions/stub.md renders. The budget assertions and the phrase checklist
# arrive with the diet itself.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

RENDER="$PLUGIN_ROOT/skills/project-update/render_instructions.py"

echo "== one source: the committed templates are rendered, not written"
out=$(python3 "$RENDER" build --check 2>&1); rc=$?
if [ $rc -eq 0 ]; then
    pass "build --check: no template drifted from instructions/stub.md"
else
    fail "build --check: a template drifted from instructions/stub.md" "$out"
fi

# A template that is edited by hand must be caught, or the check proves nothing.
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
cp -r "$PLUGIN_ROOT/skills/ai-init/templates" "$TMP/templates"
cp -r "$PLUGIN_ROOT/skills/project-init/templates" "$TMP/project-init"
printf '\n- an edit nobody put in the stub\n' >> "$TMP/templates/CLAUDE.block.md"
out=$(python3 "$RENDER" build --check --templates "$TMP/templates" \
                              --project-init "$TMP/project-init" 2>&1); rc=$?
if [ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'CLAUDE.block.md'; then
    pass "build --check: a hand-edited template is drift"
else
    fail "build --check: a hand-edited template is drift" "exit $rc: $out"
fi

# and build writes it back
python3 "$RENDER" build --templates "$TMP/templates" --project-init "$TMP/project-init" >/dev/null 2>&1
if cmp -s "$TMP/templates/CLAUDE.block.md" "$PLUGIN_ROOT/skills/ai-init/templates/CLAUDE.block.md"; then
    pass "build: the edit is rendered away"
else
    fail "build: the edit is rendered away"
fi

echo "== every scope and runtime the stub declares renders"
for pair in "project claude block" "project codex block" \
            "project gemini block" "project junie block" \
            "skeleton claude skeleton" "skeleton codex skeleton" \
            "skeleton gemini skeleton" "skeleton junie skeleton" \
            "skeleton-sdlc claude skeleton" "skeleton-sdlc codex skeleton" \
            "skeleton-sdlc gemini skeleton" "skeleton-sdlc junie skeleton"; do
    set -- $pair
    if out=$(python3 "$RENDER" render --scope "$1" --runtime "$2" --kind "$3" 2>&1); then
        pass "render --scope $1 --runtime $2: $(printf '%s' "$out" | wc -c) B"
    else
        fail "render --scope $1 --runtime $2" "$out"
    fi
done

echo "== {{PROJECT}} survives the render: the scaffold fills it in, not the renderer"
if python3 "$RENDER" render --scope skeleton --runtime claude --kind skeleton \
   | grep -qF '{{PROJECT}}'; then
    pass "skeleton keeps {{PROJECT}}"
else
    fail "skeleton keeps {{PROJECT}}"
fi

echo "== an unknown placeholder is an error, not a silent gap"
out=$(RENDER_PLAN= python3 "$RENDER" render --scope global --runtime claude --kind block 2>&1); rc=$?
if [ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'unresolved placeholder'; then
    pass "an unresolved {{X}} exits 1 with its line"
else
    fail "an unresolved {{X}} exits 1 with its line" "exit $rc: $out"
fi

echo "== measure reports the managed block, not the whole file"
TF="$TMP/CLAUDE.md"
{ printf '# mine\n\nkeep this.\n\n'; cat "$PLUGIN_ROOT/skills/ai-init/templates/CLAUDE.block.md"; } > "$TF"
want=$(python3 "$RENDER" measure "$PLUGIN_ROOT/skills/ai-init/templates/CLAUDE.block.md" | awk '{print $(NF-1)}')
got=$(python3 "$RENDER" measure "$TF" | awk '{print $(NF-1)}')
if [ "$got" = "$want" ] && [ "$(python3 "$RENDER" measure "$TF" | awk '{print $(NF-2)}')" = block ]; then
    pass "measure: the block ($want B) out of a larger file"
else
    fail "measure: the block out of a larger file" "want $want, got $got"
fi
if [ "$(python3 "$RENDER" measure "$TF" --whole | awk '{print $(NF-2)}')" = file ]; then
    pass "measure --whole: the file"
else
    fail "measure --whole: the file"
fi
if python3 "$RENDER" measure "$TF" --budget 100 >/dev/null 2>&1; then
    fail "measure --budget: over budget exits 1"
else
    pass "measure --budget: over budget exits 1"
fi

echo "== the project block stays under 2048 B in every runtime"
for runtime in claude codex gemini junie; do
    python3 "$RENDER" render --scope project --runtime "$runtime" --kind block \
            --out "$TMP/$runtime.block.md"
    if python3 "$RENDER" measure "$TMP/$runtime.block.md" --budget 2048 >/dev/null; then
        pass "project block ($runtime) $(wc -c < "$TMP/$runtime.block.md") B <= 2048"
    else
        fail "over budget: the $runtime project block is $(wc -c < "$TMP/$runtime.block.md") B, budget 2048 B (project)" \
             "trim instructions/stub.md or move the rule to routing.md / a policy"
    fi
done

echo "== a freshly scaffolded instruction file stays under 2048 B — in a path with a space"
SPACE="$TMP/with space"; mkdir -p "$SPACE/proj"
( cd "$SPACE/proj" && git init -q . )
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$SPACE/proj" \
     --runtime claude,codex,gemini,junie >/dev/null
for f in CLAUDE.md AGENTS.md GEMINI.md .junie/guidelines.md; do
    if [ ! -f "$SPACE/proj/$f" ]; then fail "$f scaffolded"; continue; fi
    size=$(wc -c < "$SPACE/proj/$f")
    if [ "$size" -le 2048 ]; then
        pass "a fresh $f is $size B <= 2048"
    else
        fail "over budget: $f is $size B, budget 2048 B (project)" \
             "trim instructions/stub.md or move the rule to routing.md / a policy"
    fi
done

echo "== the stub alone is enough to work safely (R5)"
STUB=$(python3 "$RENDER" render --scope global --runtime claude --kind block \
       --var PLAN_LABEL=Max --var READ_LINES=4000)
for phrase in '/ai-task <request>' '.ai/AGENTS.md' 'SCOPE_CHANGE_REQUIRED' '/ai-init' \
              'human approval' 'source of truth' 'one batch' 'routing.md'; do
    if printf '%s' "$STUB" | grep -qF -- "$phrase"; then
        pass "the stub says \"$phrase\""
    else
        fail "the stub no longer says \"$phrase\"" "it is what makes the stub safe alone"
    fi
done

echo "== the stub names tiers, never models (R6)"
if grep -Eiqw 'haiku|sonnet|opus|fable|terra|sol|astra' "$PLUGIN_ROOT/instructions/stub.md" \
   || grep -Eiq 'gpt-[0-9]' "$PLUGIN_ROOT/instructions/stub.md"; then
    fail "a model name reached instructions/stub.md" \
         "$(grep -Einw 'haiku|sonnet|opus|fable|terra|sol|astra' "$PLUGIN_ROOT/instructions/stub.md" | head -3)"
else
    pass "no model name in instructions/stub.md"
fi

echo "== the constitution ships prefilled and inside its cap"
CONST="$SPACE/proj/docs/sdlc/constitution.md"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$SPACE/proj" --runtime claude >/dev/null 2>&1 || true
if [ -f "$CONST" ]; then
    python3 "$RENDER" constitution "$CONST" >/dev/null \
        && pass "the scaffolded constitution is within 15 principles and 4096 B" \
        || fail "the scaffolded constitution is over its cap"
    grep -q '^C5\.' "$CONST" && pass "C1-C5 ship prefilled" || fail "C1-C5 missing"
else
    python3 "$RENDER" constitution "$PLUGIN_ROOT/skills/project-init/templates/constitution.md" >/dev/null \
        && pass "the constitution template is within 15 principles and 4096 B" \
        || fail "the constitution template is over its cap"
fi
for f in skills/sdlc-spec/SKILL.md skills/sdlc-plan/SKILL.md agents/ai-planner.md.tmpl; do
    grep -q 'docs/sdlc/constitution.md' "$PLUGIN_ROOT/$f" \
        && pass "$f reads the constitution" || fail "$f does not read the constitution"
done

echo "== the router points at files that exist, and routes rather than explains (R7)"
ROUTER="$SPACE/proj/.ai/AGENTS.md"
if [ -f "$ROUTER" ]; then
    missing=""
    while read -r ref; do
        case "$ref" in
            */*) ;;
            *) continue;;
        esac
        probe="${ref%%/<*}"
        case "$ref" in
            *"<"*) probe=$(printf '%s' "$ref" | sed 's|<[a-z-]*>|*|g');;
            *) probe="$ref";;
        esac
        # shellcheck disable=SC2086
        if ! compgen -G "$SPACE/proj/.ai/$probe" >/dev/null \
           && ! compgen -G "$SPACE/proj/$probe" >/dev/null; then
            missing="$missing $ref"
        fi
    done < <(grep -o '`[a-zA-Z0-9_./<>-]*`' "$ROUTER" | tr -d '`' | grep -E '\.(md|json)$' | sort -u)
    if [ -z "$missing" ]; then
        pass "every path the router names exists in a scaffolded project"
    else
        fail "the router points at files that do not exist" "$missing"
    fi
    if grep -q 'ADVERSARIAL REVIEW' "$ROUTER"; then
        fail "the stage diagram is still in the router" "it belongs in skills/ai-task/SKILL.md"
    else
        pass "the router routes; the stage diagram lives in the /ai-task skill"
    fi
    size=$(wc -c < "$ROUTER")
    [ "$size" -le 4096 ] && pass "the router is $size B <= 4096 (advisory)" \
        || fail "the router is $size B, advisory cap 4096 B"
else
    fail "the router was not scaffolded"
fi
grep -q 'ADVERSARIAL REVIEW' "$PLUGIN_ROOT/skills/ai-task/SKILL.md" \
    && pass "the stage diagram is in the /ai-task skill" || fail "the stage diagram was lost"

echo "== .ai/rules/ renders into the directories it names, and only there (R9)"
RP="$SPACE/rules"; mkdir -p "$RP"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$RP" --runtime both >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$RP" --runtime both >/dev/null
cp -r "$PLUGIN_ROOT/tests/fixtures/instructions/rules-project/.ai" "$RP/"
mkdir -p "$RP/src/Payment" "$RP/tests/Payment"
printf '# Payment\n\nmy own note\n' > "$RP/src/Payment/CLAUDE.md"
python3 "$PLUGIN_ROOT/skills/project-update/update.py" "$RP" --apply >/dev/null 2>&1 \
    || fail "the rules round trip could not be applied"
for f in src/Payment/CLAUDE.md src/Payment/AGENTS.md tests/Payment/CLAUDE.md \
         tests/Payment/AGENTS.md .claude/rules/payment.md; do
    [ -f "$RP/$f" ] && pass "$f was rendered" || fail "$f was not rendered"
done
grep -q 'claude-agentic:rule:payment:start' "$RP/src/Payment/CLAUDE.md" \
    && grep -q 'claude-agentic:rule:imports:start' "$RP/src/Payment/CLAUDE.md" \
    && pass "one file carries both rules that name its directory" \
    || fail "a directory named by two rules should carry both blocks"
grep -q 'my own note' "$RP/src/Payment/CLAUDE.md" \
    && pass "the text outside the markers survives the render" \
    || fail "the render ate the project's own text"
head -1 "$RP/.claude/rules/payment.md" | grep -qx -- '---' \
    && pass "the path-scoped copy opens with its frontmatter, as Claude Code reads it" \
    || fail ".claude/rules/payment.md must start with --- or its paths: is not read"
grep -q 'generated from .ai/rules/payment.md' "$RP/.claude/rules/payment.md" \
    && pass "and says which file to edit instead" || fail "the generated copy does not name its source"
[ -f "$RP/tests/Payment/.claude" ] && fail "a rule wrote outside the directories it names"
out=$(python3 "$PLUGIN_ROOT/skills/project-update/update.py" "$RP" 2>&1)
printf '%s' "$out" | grep -q '^0 automatic' \
    && pass "re-rendering is a no-op: the round trip is idempotent" \
    || fail "the second render is not a no-op" "$(printf '%s' "$out" | grep -E '^  (create|update|delete)')"
rm "$RP/.ai/rules/imports.md"
out=$(python3 "$PLUGIN_ROOT/skills/project-update/update.py" "$RP" 2>&1)
printf '%s' "$out" | grep -q 'rule block imports removed' \
    && pass "a removed source takes its rendered blocks with it" \
    || fail "a removed rule left its blocks behind" "$out"

echo "== a real install: the global block stays under 2560 B and routing.md is written"
install_case() {  # install_case <label> <target> <args...>
    local label="$1" target="$2"; shift 2
    local dir="$SPACE/$label"
    mkdir -p "$dir"
    local out rc
    if [ "$target" = claude ]; then
        out=$(CLAUDE_DIR="$dir" bash "$PLUGIN_ROOT/install.sh" --target claude "$@" 2>&1); rc=$?
        file="$dir/CLAUDE.md"
    else
        out=$(CODEX_DIR="$dir" CLAUDE_DIR="$dir/claude" bash "$PLUGIN_ROOT/install.sh" --target codex "$@" 2>&1); rc=$?
        file="$dir/AGENTS.md"
    fi
    if [ $rc -ne 0 ]; then fail "install $label" "$(printf '%s' "$out" | tail -3)"; return; fi
    local size
    size=$(python3 "$RENDER" measure "$file" | awk '{print $(NF-1)}')
    if [ "$size" -le 2560 ]; then
        pass "$label: global block $size B <= 2560"
    else
        fail "over budget: $(basename "$file") block is $size B, budget 2560 B (global)" \
             "trim instructions/stub.md or move the rule to routing.md / a policy"
    fi
    [ -f "$dir/claude-agentic/routing.md" ] \
        && pass "$label: routing.md installed" || fail "$label: routing.md missing"
    printf '%s' "$out" | grep -q 'managed block .* B (budget' \
        && pass "$label: the size line is printed" || fail "$label: no size line" "$(printf '%s' "$out" | tail -3)"
}
install_case max-fable   claude --plan max --fable yes
install_case max-plain   claude --plan max --fable no
install_case pro         claude --plan pro
install_case team-max    claude --plan team-max --fable yes
install_case team-pro    claude --plan team-pro
install_case codex-plus  codex  --codex-plan plus
install_case codex-pro   codex  --codex-plan pro

echo "== a user's own 20 KiB of text is measured, never touched"
USERDIR="$SPACE/userfile"; mkdir -p "$USERDIR"
python3 -c "open('$USERDIR/CLAUDE.md','w').write('# mine\n\n' + ('a line the user wrote.\n' * 950))"
before=$(python3 -c "print(open('$USERDIR/CLAUDE.md').read()[:-1].count(chr(10)))")
out=$(CLAUDE_DIR="$USERDIR" bash "$PLUGIN_ROOT/install.sh" --target claude --plan max --fable yes 2>&1); rc=$?
[ $rc -eq 0 ] && pass "a 20 KiB user file does not fail the install" || fail "install exited $rc" "$(printf '%s' "$out" | tail -3)"
printf '%s' "$out" | grep -q 'the rest is yours' \
    && pass "the size line names the user's share" || fail "no size line for the large file"
python3 - "$USERDIR/CLAUDE.md" <<'PY' && pass "every line the user wrote survives byte-identical" || fail "the user's text was changed"
import sys
text = open(sys.argv[1], encoding="utf-8").read()
start = text.find("<!-- claude-agentic:start -->")
outside = text[:start] if start >= 0 else text
sys.exit(0 if outside.count("a line the user wrote.\n") == 950 else 1)
PY

# Codex reads at most 32 KiB of project documents, and the plugin owns only the
# block. Half of that is where saying something is still useful; below it, a
# line about a limit nobody is near is noise.
echo "== Codex is told once when the whole file gets close to its 32 KiB limit"
CXBIG="$SPACE/codex-big"; mkdir -p "$CXBIG"
python3 -c "open('$CXBIG/AGENTS.md','w').write('# mine\n\n' + ('a line the user wrote.\n' * 950))"
out=$(CODEX_DIR="$CXBIG" CLAUDE_DIR="$CXBIG/claude" bash "$PLUGIN_ROOT/install.sh" \
        --target codex --codex-plan pro 2>&1)
printf '%s' "$out" | grep -q 'Codex reads at most 32 KiB' \
    && pass "a 20 KiB AGENTS.md gets the advisory" \
    || fail "no advisory for a 20 KiB AGENTS.md" "$(printf '%s' "$out" | tail -3)"
CXSMALL="$SPACE/codex-small"; mkdir -p "$CXSMALL"
out=$(CODEX_DIR="$CXSMALL" CLAUDE_DIR="$CXSMALL/claude" bash "$PLUGIN_ROOT/install.sh" \
        --target codex --codex-plan pro 2>&1)
printf '%s' "$out" | grep -q 'Codex reads at most 32 KiB' \
    && fail "a fresh AGENTS.md got the advisory" "the limit is nowhere near" \
    || pass "a fresh AGENTS.md is left alone about the limit"

# Downstream the budget is advisory: /project-update measures, names the byte
# count and says whose the file is to trim. It never rewrites an edited block.
echo "== /project-update hints at an over-budget block and an oversized constitution"
HINT="$SPACE/hints"; cp -r "$SPACE/proj" "$HINT"
python3 - "$HINT/CLAUDE.md" <<'PY2'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
end = text.find("<!-- claude-agentic:end -->")
extra = "- a rule this project added inside the markers.\n" * 60
open(path, "w", encoding="utf-8").write(text[:end] + extra + text[end:])
PY2
mkdir -p "$HINT/docs/sdlc"
python3 -c "
open('$HINT/docs/sdlc/constitution.md','w').write(
    '# Constitution\n\n' + ''.join('C%d. a principle this project does not negotiate.\n' % n
                                     for n in range(1, 21)))"
out=$(python3 "$PLUGIN_ROOT/skills/project-update/update.py" "$HINT" 2>&1)
printf '%s' "$out" | grep -q 'CLAUDE.md: the managed block is .* B, budget 2048 B' \
    && pass "the over-budget block is named with its byte count" \
    || fail "no budget hint for an over-budget block" "$(printf '%s' "$out" | tail -5)"
printf '%s' "$out" | grep -q 'trimming it is yours' \
    && pass "the hint says an edited block is the project's to trim" \
    || fail "the budget hint does not say whose the block is" "$(printf '%s' "$out" | tail -5)"
printf '%s' "$out" | grep -q 'docs/sdlc/constitution.md: 20 principles, at most 15' \
    && pass "the constitution cap is advisory here, and named" \
    || fail "no constitution hint" "$(printf '%s' "$out" | tail -5)"
printf '%s' "$out" | grep -q '^  update .*CLAUDE.md' \
    && fail "the plugin planned a write over an edited block" "$(printf '%s' "$out" | tail -5)" \
    || pass "an edited block is still never rewritten"

summary "instruction budget"
