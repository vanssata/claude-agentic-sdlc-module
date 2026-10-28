#!/usr/bin/env node
// RiskRails installer (Claude Code and/or Codex). Node 18+, stdlib only.
//   npx riskrails [--target auto|claude|codex|both] [--plan pro|team-pro|team-max|max|max20|balanced-max]
//                 [--fable auto|yes|no] [--codex-plan plus|pro|balanced-max] [--dry-run]
//                 [--context default|economy] [--statusline-context yes|no]
//                 [--home DIR] [--codex-home DIR] [--yes] [--version]
// --target defaults to auto: each runtime is installed only if its executable is on PATH.
// --plan   Claude only: pro, team-pro (Team Standard seat), team-max (Team Premium seat), max
//          or max20 (Max 20x: max's settings, larger budgets). Defaults to auto-detect from
//          ~/.claude.json (organizationType, organizationRateLimitTier, the seat tiers for a
//          Team org). On a terminal the detected plan is proposed and Enter confirms it (a plan
//          recorded by an earlier install is the proposal); without one, or with --yes, the
//          detection is used and printed on stderr. --plan skips the question.
//          balanced-max is never detected, only chosen: a Max account where only the session
//          runs Opus 5.5 (200k window). It also selects the Codex balanced-max profile unless
//          --codex-plan is given.
// --fable  Claude only. auto = yes on max, max20 and team-max, no on pro and team-pro.
// --codex-plan  Codex only: plus, pro or balanced-max. Defaults to auto-detect from the ChatGPT
//          login in ~/.codex/auth.json (chatgpt_plan_type); assumes pro when it cannot tell.
// --context  default leaves each runtime its own context window and compaction, and
//          context-guard only warns. economy writes the plan's autoCompactWindow (800 000 on
//          Max, 300 000 on Pro) and the guard also holds a prompt back past 120% of it.
//          Without economy, an autoCompactWindow equal to the plan's is removed; any other
//          value is the user's and stays. Recorded in riskrails/profile.json as `context`.
// --statusline-context  yes (default) shows the model and the context use in the
//          statusline: a line before the user's own in Claude Code, `model-with-reasoning`
//          and `context-used` in Codex's [tui] status_line. no adds nothing and removes nothing.
// --home / --codex-home  the runtime homes (default ~/.claude and ~/.codex; the environment
//          variables CLAUDE_DIR and CODEX_DIR mean the same). Naming exactly one of them under
//          --target auto installs that runtime alone.
// --dry-run prints everything that would be written, per runtime, and writes nothing.
//
// This is the port of the install.sh that shipped up to 2.0.2: the same tree, the same
// messages, the same backups (backups/<date>/<path> under the runtime's home). JSON merges
// run here; the profile, the Codex agents, config.toml and the managed block are rendered
// by the Python scripts the package ships, each run as `python3 -I`. Idempotent: re-running
// updates in place and never duplicates a hook entry or a managed block.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const SRC = path.resolve(__dirname, '..');
const out = (s) => fs.writeSync(1, s + '\n');
const err = (s) => fs.writeSync(2, s + '\n');

function die(msg, code) { err(msg); process.exit(code); }

// ------------------------------------------------------------------ arguments
const env = process.env;
let CLAUDE_DIR_GIVEN = !!env.CLAUDE_DIR, CODEX_DIR_GIVEN = !!env.CODEX_DIR;
let CLAUDE_DIR = env.CLAUDE_DIR || path.join(os.homedir(), '.claude');
let CODEX_DIR = env.CODEX_DIR || path.join(os.homedir(), '.codex');
const HOME = env.HOME || os.homedir();
let PLAN = '', FABLE = 'auto', DRY = false, TARGET = 'auto', PLAN_GIVEN = false;
let CODEX_PLAN = '', CODEX_PLAN_GIVEN = false, YES = false;
let CONTEXT = 'default', STATUSLINE_CONTEXT = 'yes';

function version() {
  try { return JSON.parse(fs.readFileSync(path.join(SRC, 'package.json'), 'utf8')).version || 'unknown'; }
  catch (e) { return 'unknown'; }
}

function usage() {
  const text = fs.readFileSync(__filename, 'utf8').split('\n');
  const end = text.findIndex((l, i) => i > 0 && !l.startsWith('//'));
  out(text.slice(1, end).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'));
}

{
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    let a = argv[i], val = null;
    const eq = a.indexOf('=');
    if (a.startsWith('--') && eq > 0) { val = a.slice(eq + 1); a = a.slice(0, eq); }
    const take = () => {
      if (val !== null) return val;
      const v = argv[++i];
      if (v === undefined || v === '') die('riskrails: missing value for ' + a, 2);
      return v;
    };
    switch (a) {
      case '--target': TARGET = take(); break;
      case '--plan': PLAN = take(); PLAN_GIVEN = true; break;
      case '--fable': FABLE = take(); PLAN_GIVEN = true; break;
      case '--codex-plan': CODEX_PLAN = take(); CODEX_PLAN_GIVEN = true; break;
      case '--context': CONTEXT = take(); break;
      case '--statusline-context': STATUSLINE_CONTEXT = take(); break;
      case '--home': CLAUDE_DIR = path.resolve(take()); CLAUDE_DIR_GIVEN = true; break;
      case '--codex-home': CODEX_DIR = path.resolve(take()); CODEX_DIR_GIVEN = true; break;
      case '--dry-run': DRY = true; break;
      case '--yes': case '-y': YES = true; break;
      case '--version': case '-v': out(version()); process.exit(0); break;
      case '-h': case '--help': usage(); process.exit(0); break;
      default: die('unknown option: ' + argv[i], 2);
    }
  }
}
if (!['auto', 'claude', 'codex', 'both'].includes(TARGET)) {
  die(`--target must be auto|claude|codex|both (got '${TARGET}')`, 2);
}
if (!['default', 'economy'].includes(CONTEXT)) die(`--context must be default|economy (got '${CONTEXT}')`, 2);
if (!['yes', 'no'].includes(STATUSLINE_CONTEXT)) {
  die(`--statusline-context must be yes|no (got '${STATUSLINE_CONTEXT}')`, 2);
}
const major = Number(process.versions.node.split('.')[0]);
if (major < 18) die('riskrails needs Node 18 or newer (this is ' + process.versions.node + ')', 1);

function onPath(cmd) {
  for (const dir of (env.PATH || '').split(':')) {
    if (!dir) continue;
    const p = path.join(dir, cmd);
    try { fs.accessSync(p, fs.constants.X_OK); if (fs.statSync(p).isFile()) return true; } catch (e) { /* next */ }
  }
  return false;
}
if (!onPath('python3')) die('python3 is required', 1);

// ------------------------------------------------------------------ helpers
const exists = (p) => fs.existsSync(p);                       // follows symlinks, as [ -e ]
const isDir = (p) => { try { return fs.statSync(p).isDirectory(); } catch (e) { return false; } };
const isFile = (p) => { try { return fs.statSync(p).isFile(); } catch (e) { return false; } };
const isLink = (p) => { try { return fs.lstatSync(p).isSymbolicLink(); } catch (e) { return false; } };
const lexists = (p) => { try { fs.lstatSync(p); return true; } catch (e) { return false; } };
const read = (p) => fs.readFileSync(p, 'utf8');
const readJSON = (p) => JSON.parse(read(p));
const pretty = (v) => JSON.stringify(v, null, 2);
const mkdirp = (p) => fs.mkdirSync(p, { recursive: true });
const rmrf = (p) => fs.rmSync(p, { recursive: true, force: true });
const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const clone = (v) => JSON.parse(JSON.stringify(v));

// The order `ls` and a glob print in, the same on every machine: bytewise.
function lsSort(names) { return names.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)); }
const ls = (dir) => lsSort(fs.readdirSync(dir).filter((n) => !n.startsWith('.')));
// `<dir>/*<suffix>` as bash expands it: sorted, dot files excluded.
const glob = (dir, suffix) => (isDir(dir) ? ls(dir).filter((n) => n.endsWith(suffix)).map((n) => path.join(dir, n)) : []);

function sameFile(a, b) {                                      // cmp -s
  try { return fs.readFileSync(a).equals(fs.readFileSync(b)); } catch (e) { return false; }
}

const skipped = (name, skip) => (Array.isArray(skip) ? skip.includes(name) : name === skip);

// diff -rq [-x <name>...]: the same names, kinds and file contents, symlinks followed.
function sameTree(a, b, exclude) {
  let sa, sb;
  try { sa = fs.statSync(a); sb = fs.statSync(b); } catch (e) { return false; }
  if (sa.isDirectory() !== sb.isDirectory()) return false;
  if (!sa.isDirectory()) return sameFile(a, b);
  const names = (d) => fs.readdirSync(d).filter((n) => !skipped(n, exclude)).sort();
  const na = names(a), nb = names(b);
  if (na.length !== nb.length || na.some((n, i) => n !== nb[i])) return false;
  return na.every((n) => sameTree(path.join(a, n), path.join(b, n), exclude));
}

// cp -r: directories, files and symlinks as they are (a link keeps its own target).
function copyTree(src, dst, skip) {
  const st = fs.lstatSync(src);
  if (st.isSymbolicLink()) { fs.symlinkSync(fs.readlinkSync(src), dst); return; }
  if (!st.isDirectory()) { fs.copyFileSync(src, dst); return; }
  fs.mkdirSync(dst, { mode: st.mode & 0o7777 });
  for (const n of fs.readdirSync(src)) {
    if (skipped(n, skip)) continue;
    copyTree(path.join(src, n), path.join(dst, n), skip);
  }
}

function countFiles(dir) {                                     // find <dir> -type f | wc -l
  let n = 0;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) n += countFiles(path.join(dir, e.name));
    else if (e.isFile()) n += 1;
  }
  return n;
}

function chmodX(p) { fs.chmodSync(p, fs.statSync(p).mode | 0o111); }

// jq's `*`: objects merge key by key, recursively; anything else is replaced.
function deepMerge(a, b) {
  if (!isObj(a) || !isObj(b)) return clone(b);
  const r = clone(a);
  for (const [k, v] of Object.entries(b)) r[k] = isObj(r[k]) && isObj(v) ? deepMerge(r[k], v) : clone(v);
  return r;
}

// jq -S: keys sorted at every level, for a comparison that ignores key order.
function sortedJSON(v) {
  if (Array.isArray(v)) return '[' + v.map(sortedJSON).join(',') + ']';
  if (isObj(v)) return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + sortedJSON(v[k])).join(',') + '}';
  return JSON.stringify(v);
}

// Python's json.dump(..., indent=2): ensure_ascii escapes every non-ASCII character.
const asciiJSON = (v) => pretty(v).replace(/[\u0080-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));

const spaced = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');   // "{:,}" with spaces

function python(args, opts = {}) {
  const r = spawnSync('python3', ['-I', ...args], {
    env: opts.env || env, encoding: 'utf8',
    stdio: ['ignore', opts.capture === false ? 'inherit' : 'pipe', 'inherit'],
  });
  if (r.error) throw r.error;
  if (r.status !== 0 && !opts.allowFail) {
    if (r.stdout) fs.writeSync(1, r.stdout);
    die(`riskrails: python3 ${path.basename(args[0])} failed (exit ${r.status})`, r.status || 1);
  }
  return r.stdout || '';
}

const pad2 = (n) => String(n).padStart(2, '0');
const now = new Date();
const BACKUP_DATE = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
const utcStamp = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');

// A line from the terminal, as `read -r -p`: the prompt on stderr.
function ask(prompt) {
  fs.writeSync(2, prompt);
  const buf = Buffer.alloc(1);
  const bytes = [];
  for (;;) {
    let n;
    try { n = fs.readSync(0, buf, 0, 1, null); } catch (e) { if (e.code === 'EAGAIN') continue; break; }
    if (n === 0 || buf[0] === 10) break;
    bytes.push(buf[0]);
  }
  return Buffer.from(bytes).toString('utf8');
}
const interactive = () => !YES && process.stdin.isTTY === true;

// ------------------------------------------------------------------ runtime detection
let DO_CLAUDE = false, DO_CODEX = false;
const skippedRuntime = (rt, dir) => err(`${rt}: ${dir} found but no ${rt} on PATH — skipped (--target ${rt} for it alone, --target both for both)`);
if (TARGET === 'claude') DO_CLAUDE = true;
else if (TARGET === 'codex') DO_CODEX = true;
else if (TARGET === 'both') { DO_CLAUDE = true; DO_CODEX = true; }
else if (CLAUDE_DIR_GIVEN && !CODEX_DIR_GIVEN) DO_CLAUDE = true;
else if (CODEX_DIR_GIVEN && !CLAUDE_DIR_GIVEN) DO_CODEX = true;
else {
  // The executable is the runtime; a directory alone is not. A plan flag still names it.
  if (onPath('claude') || PLAN_GIVEN) DO_CLAUDE = true;
  else if (isDir(CLAUDE_DIR)) skippedRuntime('claude', CLAUDE_DIR);
  if (onPath('codex') || CODEX_PLAN_GIVEN) DO_CODEX = true;
  else if (isDir(CODEX_DIR)) skippedRuntime('codex', CODEX_DIR);
}
if (!DO_CLAUDE && !DO_CODEX) {
  err(`No supported runtime found.

Looked for a \`claude\` or \`codex\` executable on PATH and found neither (an
existing ~/.claude or ~/.codex directory alone does not count). Install Claude
Code or Codex first, or name the runtime yourself:

  npx riskrails --target claude      # Claude Code only
  npx riskrails --target codex       # Codex only
  npx riskrails --target both        # both, whether or not they are detected`);
  process.exit(1);
}
if (TARGET === 'auto') out('detected runtime:' + (DO_CLAUDE ? ' claude' : '') + (DO_CODEX ? ' codex' : ''));

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'riskrails-'));
process.on('exit', () => rmrf(TMP));

// render <src> <dst> — substitute {{PLACEHOLDER}}s from `vars`.
function render(src, dst, vars) {
  const text = read(src).replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => (k in vars ? vars[k] : m));
  if (text.includes('{{')) die(`riskrails: unrendered placeholder in ${src}`, 1);
  fs.writeFileSync(dst, text);
}

// render_stub — the always-loaded managed block (or the routing file), from instructions/stub.md.
function renderStub(scope, runtime, dst, vars, kind = 'block') {
  const e = { ...env };
  for (const [k, v] of Object.entries(vars)) e['RENDER_' + k] = String(v);
  python([path.join(SRC, 'skills/project-update/render_instructions.py'), 'render', '--scope', scope,
    '--runtime', runtime, '--kind', kind, '--source', SRC, '--out', dst], { env: e });
}

// block_size — what the always-loaded block costs, and how much of the file is the user's own.
function blockSize(file, budget) {
  const text = read(file);
  const m = text.match(/<!-- (riskrails|claude-agentic|[Cc]odex-agentic):start -->[\s\S]*?<!-- \1:end -->/);
  const block = m ? Buffer.byteLength(m[0]) : 0;
  out(`${path.basename(file)}: managed block ${spaced(block)} B (budget ${spaced(budget)}), file ${spaced(Buffer.byteLength(text))} B — the rest is yours`);
}

function codexDocAdvisory(file) {
  const size = fs.statSync(file).size;
  if (size > 16384) out(`${path.basename(file)} is ${size} B; Codex reads at most 32 KiB of project docs — consider a project .ai/`);
}

// agentic_profile — the resolved riskrails tables plus who wrote them, for <home>/riskrails/profile.json.
let PLUGIN_VERSION = 'unknown';
try { PLUGIN_VERSION = readJSON(path.join(SRC, '.codex-plugin/plugin.json')).version || 'unknown'; } catch (e) { /* unknown */ }
function agenticProfile(runtime, profile, plan, label, fable) {
  const p = JSON.parse(python([path.join(SRC, 'scripts/resolve-profile.py'), profile, '--src', SRC, '--plan', plan,
    '--label', label, '--fable', fable, '--context', CONTEXT, '--print', 'agentic']));
  p.runtime = runtime; p.plugin_version = PLUGIN_VERSION; p.written_at = utcStamp();
  p.dialog = { tool: runtime === 'claude' ? 'AskUserQuestion' : codexDialogTool() };
  p.set_by = { via: 'installer', at: p.written_at };
  return p;
}

// The first Codex whose request_user_input fires PreToolUse and PostToolUse outside plan
// mode (spike 7.0, docs/dialog-spike.md; G1). An older, unknown or missing codex gets null:
// the dialog stays off for it (R36.19).
const CODEX_DIALOG_SINCE = [0, 165, 0];
function codexDialogTool() {
  const r = spawnSync('codex', ['--version'], { env, encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] });
  const m = !r.error && r.status === 0 && /(\d+)\.(\d+)\.(\d+)/.exec(r.stdout || '');
  if (!m) return null;
  const v = m.slice(1, 4).map(Number);
  const i = v.findIndex((n, k) => n !== CODEX_DIALOG_SINCE[k]);
  return i < 0 || v[i] > CODEX_DIALOG_SINCE[i] ? 'request_user_input' : null;
}

// write_profile — plugin state, replaced rather than backed up, and only when something
// other than written_at changed, so a second install leaves it alone.
function writeProfile(home, profile) {
  const dst = path.join(home, 'riskrails/profile.json');
  const strip = (v) => { const c = clone(v); delete c.written_at; if (isObj(c.set_by)) delete c.set_by.at; return sortedJSON(c); };
  try { if (isFile(dst) && strip(readJSON(dst)) === strip(profile)) return; } catch (e) { /* rewrite */ }
  mkdirp(path.join(home, 'riskrails'));
  fs.writeFileSync(dst, pretty(profile) + '\n');
  fs.chmodSync(dst, 0o644);
}

function prevPlan(home) {
  for (const name of ['riskrails', 'claude-agentic']) {   // before 3.4b it lived under claude-agentic/ (R35)
    try {
      const plan = readJSON(path.join(home, name, 'profile.json')).plan;
      return plan === null || plan === undefined || plan === false ? '' : String(plan);
    } catch (e) { /* next */ }
  }
  return '';
}

// ================================================================= Claude Code
const C = {};   // the Claude branch's rendered values

function prettyModel(m) {
  if (m === 'fable[1m]') return 'Fable 5.1 [1m]';
  if (m.startsWith('fable')) return 'Fable 5.1';
  if (m === 'opusplan') return 'Opus 5 in plan mode, Sonnet 5 when executing (opusplan)';
  if (m === 'claude-opus-5-5[1m]') return 'Opus 5.5 [1m]';
  if (m === 'opus[1m]') return 'Opus 5 [1m]';
  if (m.startsWith('claude-opus-5-5')) return 'Opus 5.5';
  if (m.startsWith('opus')) return 'Opus 5';
  if (m.startsWith('sonnet')) return 'Sonnet 5';
  if (m.startsWith('haiku')) return 'Haiku 4.5';
  return m;
}

// The plan is read by `state.py profile detect` (R36.16), the one copy of the detection;
// live.plan is the profile's plan, live.from why, live.org/live.raw the account's own value.
function detectPlan(runtime) {
  const out = python([path.join(SRC, 'skills/ai-task/state.py'), 'profile', 'detect', '--runtime', runtime, '--json'],
    { env: { ...env, HOME, CODEX_HOME: CODEX_DIR }, allowFail: true });
  try { const live = JSON.parse(out).live; if (isObj(live)) return live; } catch (e) { /* none */ }
  return {};
}

function claudeRender() {
  const PREV_PLAN = prevPlan(CLAUDE_DIR);
  if (!PLAN) {
    const live = detectPlan('claude');
    const org = live.org || '', detected = live.plan || '', from = live.from || '';
    if (interactive()) {
      const proposed = PREV_PLAN || detected;
      if (proposed) {
        const why = PREV_PLAN ? 'recorded by the previous install' : `detected from ${from}`;
        PLAN = ask(`plan: ${proposed} (${why}) — Enter to confirm, or type pro/team-pro/team-max/max/max20/balanced-max: `) || proposed;
      } else if (from === 'team') {
        PLAN = ask(`Team org detected (${org}) but not the seat. Enter plan [team-pro/team-max]: `);
      } else {
        PLAN = ask(`Could not detect plan (organizationType='${org}'). Enter plan [pro/team-pro/team-max/max/max20]: `);
      }
    } else if (detected) {
      PLAN = detected; err(`detected plan: ${PLAN} (${from})`);
    } else if (from === 'team') {
      PLAN = 'team-pro';
      err(`detected plan: team (${org}) — seat unknown, using team-pro (Pro's models and limits); pass --plan team-max for a Premium seat`);
    } else if (PREV_PLAN) {
      PLAN = PREV_PLAN; err(`plan: ${PLAN} (recorded by the previous install; organizationType='${org}')`);
    } else {
      die('Could not detect plan; pass --plan pro|team-pro|team-max|max|max20', 1);
    }
  }
  PLAN = { 'team-standard': 'team-pro', team_standard: 'team-pro', team: 'team-pro', 'team-premium': 'team-max',
    team_premium: 'team-max', team_pro: 'team-pro', team_max: 'team-max' }[PLAN] || PLAN;
  const plans = {
    pro: ['pro', 'pro', 'Pro'], 'team-pro': ['pro', 'pro', 'Team Pro'], 'team-max': ['max', 'max', 'Team Max'],
    max: ['max', 'max', 'Max'], max20: ['max', 'max20', 'Max 20x'], 'balanced-max': ['max', 'balanced-max', 'BalancedMax'],
  };
  if (['max-20x', 'max_20x'].includes(PLAN)) PLAN = 'max20';
  if (['balanced_max', 'balancedmax'].includes(PLAN)) PLAN = 'balanced-max';
  if (!plans[PLAN]) die(`--plan must be pro, team-pro, team-max, max, max20 or balanced-max (got '${PLAN}')`, 2);
  const [TIER, PROFILE_NAME, PLAN_LABEL] = plans[PLAN];
  if (FABLE === 'auto') FABLE = TIER === 'max' && PLAN !== 'balanced-max' ? 'yes' : 'no';
  else if (!['yes', 'no'].includes(FABLE)) die('--fable must be auto|yes|no', 2);
  if ((TIER === 'pro' || PLAN === 'balanced-max') && FABLE === 'yes') {
    err(`Fable is not available on the ${PLAN} plan; using --fable no`); FABLE = 'no';
  }

  // The profile's riskrails tables are the plugin's, not Claude Code's: the resolver
  // prints the settings half alone, so they never reach settings.json.
  // --context economy puts the plan's autoCompactWindow into that half; default leaves it out.
  const profile = JSON.parse(python([path.join(SRC, 'scripts/resolve-profile.py'), PROFILE_NAME, '--src', SRC,
    '--context', CONTEXT, '--print', 'settings']));
  if (TIER === 'max' && FABLE === 'no') {
    profile.availableModels = (profile.availableModels || []).filter((m) => !String(m).startsWith('fable'));
    if (isObj(profile.modelSettings)) delete profile.modelSettings['claude-fable-5-1'];
  }
  const claudeProfile = agenticProfile('claude', PROFILE_NAME, PLAN, PLAN_LABEL, FABLE);
  const tier = (t, f) => String(claudeProfile.tiers[t][f]);
  let snippet = deepMerge(readJSON(path.join(SRC, 'settings.common.json')), profile);

  const SESSION_MODEL = String(snippet.model);
  const fallbacks = Array.isArray(snippet.fallbackModel) ? snippet.fallbackModel : [snippet.fallbackModel];
  const FALLBACK = fallbacks.join(', then ');
  const EFFORT = String(snippet.effortLevel);
  // The plan's own window (riskrails.economy), written only with --context economy; in
  // default the runtime compacts against the model's window. Auto-compaction fires about
  // 33k under the window; context-guard.py derives its thresholds from the same point and
  // holds a prompt back only when a window is configured. Claude Code caps
  // autoCompactWindow at the model's own window, so print the number that matches the
  // session this install configures.
  const COMPACT = CONTEXT === 'economy' ? Number(snippet.autoCompactWindow) || 0 : 0;
  const MODEL_WINDOW = SESSION_MODEL.includes('[1m]') ? 1000000 : 200000;
  const fires = (window) => (COMPACT ? Math.min(COMPACT, window) : window) - 33000;
  const COMPACT_AT = fires(MODEL_WINDOW);
  const ONE_M_AT = fires(1000000);
  const COMPACT_NOTE = COMPACT ? `\`autoCompactWindow\` ${COMPACT}` : 'the runtime default, `--context economy` sets a window';
  const ONE_M_FABLE = FABLE === 'yes' ? ' and `claude-1m fable` for Fable 5.1 [1m]' : '';
  let ONE_M_RULE = COMPACT
    ? `One \`autoCompactWindow\` of ${COMPACT} serves every model: Claude Code caps it at the model's own window, so this session compacts near ${COMPACT_AT} and a \`[1m]\` one near ${ONE_M_AT}, whether it was started with \`claude-1m\` (\`~/.claude/bin/claude-1m\`) for \`opus[1m]\`${ONE_M_FABLE} or switched to with \`/model\`. \`claude-1m\` pins the model at launch and \`CLAUDE_1M_COMPACT_WINDOW\` lowers the window for that one process; it is no longer what grants the large window. When a task inside an ordinary session needs one large-context read, say so and, once the user agrees, run \`claude-1m -p '<brief>'\` from Bash — its own process, only the answer comes back.`
    : `Compaction is at the runtime default: each model compacts against its own window, so this session near ${COMPACT_AT} and a \`[1m]\` one near ${ONE_M_AT}, whether it was started with \`claude-1m\` (\`~/.claude/bin/claude-1m\`) for \`opus[1m]\`${ONE_M_FABLE} or switched to with \`/model\`. \`claude-1m\` pins the model at launch and \`CLAUDE_1M_COMPACT_WINDOW\` sets an earlier window for that one process. When a task inside an ordinary session needs one large-context read, say so and, once the user agrees, run \`claude-1m -p '<brief>'\` from Bash — its own process, only the answer comes back.`;
  if (MODEL_WINDOW > 200000) {
    ONE_M_RULE = COMPACT
      ? `\`autoCompactWindow\` ${COMPACT} applies uncapped to this 1M session, so it compacts near ${COMPACT_AT}; a 200k model picked with \`/model opus\` is capped at its own window and compacts near 167000. For a small task a 200k session is cheaper per turn — say so and let the user switch. \`claude-1m\` (\`~/.claude/bin/claude-1m\`) still pins the model at launch${ONE_M_FABLE}, and \`CLAUDE_1M_COMPACT_WINDOW\` lowers the window for that one process.`
      : `Compaction is at the runtime default, so this 1M session compacts near ${COMPACT_AT} and context-guard only warns; a 200k model picked with \`/model opus\` compacts near 167000. For a small task a 200k session is cheaper per turn — say so and let the user switch. \`claude-1m\` (\`~/.claude/bin/claude-1m\`) still pins the model at launch${ONE_M_FABLE}, and \`CLAUDE_1M_COMPACT_WINDOW\` sets an earlier window for that one process.`;
  }
  const READ_LINES = String(snippet.env.CLAUDE_READ_MAX_LINES);
  const READ_BYTES = String(snippet.env.CLAUDE_READ_MAX_BYTES);
  const SESSION_HUMAN = prettyModel(SESSION_MODEL);
  const FALLBACK_HUMAN = fallbacks.map((m) => prettyModel(String(m))).join(', then ');
  const WEEKLY = env.CLAUDE_FABLE_GATE_WEEKLY_PCT || '90';

  // Every agent pins its own `model:`; CLAUDE_CODE_SUBAGENT_MODEL is not set. architect,
  // the EXPERT-tier agent, pins opus on pro/team-pro, fable[1m] on max with Fable, and
  // inherits the session otherwise.
  let EXPERT_EFFORT, EXPERT_MODEL_LINE, ARCHITECT_MODEL_LINE, ARCHITECT_EFFORT, EXPERT_ROW, PLAN_SPECIFIC, EFFORT_RULE;
  if (TIER === 'pro') {
    EXPERT_EFFORT = 'high';
    EXPERT_MODEL_LINE = 'model: opus';
    ARCHITECT_MODEL_LINE = 'model: opus';
    ARCHITECT_EFFORT = 'high';
    EXPERT_ROW = '`opus` / `high`, pinned — on opusplan an inherited model is Sonnet outside plan mode';
    PLAN_SPECIFIC = '- Session model is `opusplan`: Opus 5 in plan mode, Sonnet 5 when executing. Use plan mode for T3+ and for a T2 that spans several modules — that is where Opus is paid for. Fable is off this plan; never request it. `xhigh`/`max` are unavailable. STRONG and EXPERT both pin `model: opus` explicitly.';
    EFFORT_RULE = 'Raise to `high` only for architecture, root-cause analysis and adversarial verification, and say that you are raising it.';
  } else {
    EXPERT_EFFORT = tier('EXPERT', 'effort');
    EXPERT_MODEL_LINE = 'model: opus';
    if (FABLE === 'yes') {
      ARCHITECT_MODEL_LINE = 'model: fable[1m]';
      ARCHITECT_EFFORT = 'xhigh';
      EXPERT_ROW = '`fable[1m]` / `xhigh`, pinned on `architect`';
      PLAN_SPECIFIC = `- Session model is ${SESSION_HUMAN} by default, compaction near ${COMPACT_AT} tokens (${COMPACT_NOTE}). A large context is not free: every turn re-reads it, so keep \`/clear\` between tasks. ${ONE_M_RULE} Fable 5.1 [1m] is pinned on \`architect\` (\`model: fable[1m]\`, \`xhigh\`) and is the session only when the user starts one with \`claude-1m fable\` — never pick it for a reader or a reviewer. \`max\` stays off.
- \`runtime-gate\` checks Fable at run time. \`fallbackModel\` covers an overload; after a rate-limit or model-not-found failure, and while the weekly limit is ${WEEKLY}% or more used, the gate sends every \`model: fable\` agent to Opus until the reset, and says so in the agent's context. If a Fable agent still returns such an error, re-run the same brief once with \`model: opus\` — an availability switch, not a downgrade. \`~/.claude/hooks/runtime-gate.py status\` shows the gate; \`clear\` re-enables Fable early.`;
    } else {
      ARCHITECT_MODEL_LINE = `# model: intentionally omitted — inherits the session model (${SESSION_HUMAN}, Fable disabled in this install)`;
      ARCHITECT_EFFORT = 'high';
      EXPERT_ROW = `the session model at \`${ARCHITECT_EFFORT}\` — \`architect\` inherits it`;
      PLAN_SPECIFIC = `- Session model is ${SESSION_HUMAN} by default, compaction near ${COMPACT_AT} tokens (${COMPACT_NOTE}). ${ONE_M_RULE} Fable is disabled in this install (\`--fable no\`). Do not request \`model: fable\` anywhere. \`xhigh\` and \`max\` stay off.`;
    }
    if (PLAN === 'balanced-max') {
      ARCHITECT_MODEL_LINE = '# model: intentionally omitted — inherits the session model (Opus 5.5; no Fable on BalancedMax)';
      PLAN_SPECIFIC = `- BalancedMax: only the session runs the strong model. Session model is Opus 5.5 with the 200k window and compaction near ${COMPACT_AT} tokens (${COMPACT_NOTE}); it plans and implements. Agents keep their cheap tiers — readers (\`Explore\`, \`log-reader\`) on \`${tier('FAST', 'model')}\` / \`${tier('FAST', 'effort')}\`, judgement (\`ai-discovery\`) on \`${tier('BALANCED', 'model')}\`, \`ai-reviewer\` on \`${tier('STRONG', 'model')}\`, and \`architect\` inherits the session. \`opus[1m]\` is a per-task choice, never the default. ${ONE_M_RULE} Fable is off on this plan; never request \`model: fable\`. \`xhigh\` and \`max\` stay off.`;
    }
    EFFORT_RULE = 'Raise to `high` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; readers stay at `low`.';
  }

  // runtime-gate runs on every plan; its Fable branch (StopFailure) only where Fable does.
  const GATE = TIER === 'max' && FABLE === 'yes' ? 'on' : 'off';
  const gate = readJSON(path.join(SRC, 'settings.gate.json'));
  if (GATE === 'off' && isObj(gate.hooks)) delete gate.hooks.StopFailure;
  snippet.hooks = snippet.hooks || {};
  for (const [k, v] of Object.entries(gate.hooks || {})) snippet.hooks[k] = (snippet.hooks[k] || []).concat(v);

  const vars = {
    PLAN: PLAN_LABEL, PLAN_LABEL, SESSION_MODEL: SESSION_HUMAN, FALLBACK_MODEL: FALLBACK_HUMAN,
    DEFAULT_EFFORT: EFFORT, COMPACT_WINDOW: spaced(COMPACT_AT),
    CONTEXT_WARN: `${Math.trunc(COMPACT_AT * 80 / 100000)}k`,
    CONTEXT_BLOCK: COMPACT
      ? `and from ${Math.trunc(COMPACT_AT * 120 / 100000)}k the prompt is held back once — sending it again goes through`
      : 'and the prompt is never held back (only `--context economy` sets a block threshold)',
    READ_LINES, PLAN_SPECIFIC_ROUTING: PLAN_SPECIFIC, EFFORT_RULE, EXPERT_EFFORT, EXPERT_MODEL_LINE, EXPERT_ROW,
    ARCHITECT_MODEL_LINE, ARCHITECT_EFFORT,
    FAST_MODEL: tier('FAST', 'model'), FAST_EFFORT: tier('FAST', 'effort'),
    BALANCED_MODEL: tier('BALANCED', 'model'), BALANCED_EFFORT: tier('BALANCED', 'effort'),
    STRONG_MODEL: tier('STRONG', 'model'), STRONG_EFFORT: tier('STRONG', 'effort'),
    AI_SHARED: path.join(CLAUDE_DIR, 'riskrails/ai'), AI_RESOLVER: path.join(CLAUDE_DIR, 'riskrails/ai-path'),
  };
  // Every agent source is a template: tiers from the resolved profile, EXPERT lines from above.
  mkdirp(path.join(TMP, 'agents'));
  for (const f of glob(path.join(SRC, 'agents'), '.md.tmpl')) render(f, path.join(TMP, 'agents', path.basename(f, '.tmpl')), vars);
  renderStub('global', 'claude', path.join(TMP, 'CLAUDE.block.md'), vars);
  renderStub('global', 'claude', path.join(TMP, 'claude-routing.md'), vars, 'routing');

  Object.assign(C, { TIER, PROFILE_NAME, PLAN_LABEL, GATE, snippet, claudeProfile, SESSION_MODEL, SESSION_HUMAN,
    FALLBACK, EFFORT, COMPACT, COMPACT_AT, MODEL_WINDOW, ONE_M_AT, READ_LINES, READ_BYTES, ARCHITECT_EFFORT, WEEKLY });
}

// Only the statusline receives the account's rate_limits, so the gate's weekly check rides
// on it: on a Fable install the statusline command is wrapped as
//   "$HOME/.claude/hooks/runtime-gate.py" statusline --then '<your command>'
// (or set to the bare check when there was none), and unwrapped to exactly the original
// command on any other install. Written as Python's json.dump wrote it (ASCII, indent 2).
function shQuote(s) {                                            // shlex.quote
  if (!s) return "''";
  if (!/[^\w@%+=:,./-]/.test(s)) return s;
  return "'" + s.replace(/'/g, "'\"'\"'") + "'";
}

function shSplit(s) {                                            // shlex.split, POSIX mode
  const words = [];
  let cur = null, i = 0;
  while (i < s.length) {
    const c = s[i];
    if (/\s/.test(c)) { if (cur !== null) { words.push(cur); cur = null; } i++; continue; }
    cur = cur || '';
    if (c === "'") {
      const j = s.indexOf("'", i + 1);
      if (j < 0) throw new Error('No closing quotation');
      cur += s.slice(i + 1, j); i = j + 1;
    } else if (c === '"') {
      i++;
      for (;;) {
        if (i >= s.length) throw new Error('No closing quotation');
        if (s[i] === '"') { i++; break; }
        if (s[i] === '\\' && i + 1 < s.length && (s[i + 1] === '"' || s[i + 1] === '\\')) { cur += s[i + 1]; i += 2; continue; }
        cur += s[i++];
      }
    } else if (c === '\\') {
      if (i + 1 >= s.length) throw new Error('No escaped character');
      cur += s[i + 1]; i += 2;
    } else { cur += c; i++; }
  }
  if (cur !== null) words.push(cur);
  return words;
}

// The wrapper is `<PREFIX> [--context] [--then '<the user's command>']`; --context
// (--statusline-context yes) adds a line with the model and the context use.
function statuslineGate(file, gate, mode) {
  const PREFIX = '"$HOME/.claude/hooks/runtime-gate.py" statusline';
  const WANT = STATUSLINE_CONTEXT === 'yes' ? `${PREFIX} --context` : PREFIX;
  const OLD_PREFIX = '"$HOME/.claude/hooks/fable-gate.py" statusline';
  let settings = {};
  if (exists(file)) {
    try { settings = JSON.parse(read(file)); } catch (e) { return ['statusline: settings.json is not valid JSON; left alone']; }
  }
  const line = settings.statusLine;
  const cmd = isObj(line) ? (line.command === undefined ? '' : line.command) : '';
  let ours = typeof cmd === 'string' && cmd.startsWith(PREFIX);
  if (typeof cmd === 'string' && cmd.startsWith(OLD_PREFIX)) {
    line.command = PREFIX + cmd.slice(OLD_PREFIX.length);
    ours = true; gate = 'moved';
  }
  // What follows the prefix and an optional --context: the user's --then, byte for byte.
  const tail = () => line.command.slice(PREFIX.length).trim().replace(/^--context(\s+|$)/, '');
  const shown = STATUSLINE_CONTEXT === 'yes' ? ' with the model and the context use' : '';
  let action = null;
  if (gate === 'moved') {
    const rest = tail();
    line.command = rest ? `${WANT} ${rest}` : WANT;
    action = 'moved the fable-gate statusline wrapper to runtime-gate (your command is unchanged)';
  } else if (gate === 'on') {
    if (ours) {
      const rest = tail();
      const want = rest ? `${WANT} ${rest}` : WANT;
      if (want === cmd) return ['statusline: already records the quota'];
      line.command = want;
      action = STATUSLINE_CONTEXT === 'yes'
        ? 'added the model and the context use to the statusline wrapper (your command is unchanged)'
        : 'removed the model and context line from the statusline wrapper (your command is unchanged)';
    } else if (line === undefined || line === null) {
      settings.statusLine = { type: 'command', command: WANT };
      action = `added a statusline that records the quota (and the Fable weekly limit)${shown}`;
    } else if (isObj(line) && line.type === 'command' && typeof cmd === 'string' && cmd.trim()) {
      line.command = `${WANT} --then ${shQuote(cmd)}`;
      action = `wrapped your statusline command with the quota check${shown} (its output is unchanged)`;
    } else {
      return ['statusline: not a command statusline; the weekly-limit check is not wired'];
    }
  } else {
    if (!ours) return [];
    const rest = tail();
    if (rest.startsWith('--then')) {
      const parts = shSplit(rest);
      line.command = parts.length > 1 ? parts[1] : '';
      action = 'restored your original statusline command (runtime-gate off)';
    } else {
      delete settings.statusLine;
      action = 'removed the quota statusline (runtime-gate off)';
    }
  }
  if (mode === 'dry') return ['statusline: would have ' + action];
  fs.writeFileSync(file + '.tmp', asciiJSON(settings) + '\n');
  fs.renameSync(file + '.tmp', file);
  return ['statusline: ' + action];
}

const agentNames = (sep) => ls(path.join(SRC, 'agents')).filter((n) => n !== 'superseded')
  .map((n) => n.replace(/\.md(\.tmpl)?$/, '')).join(sep);

// The hook files claudeApply installs: hooks/*.sh and *.py but the Codex-only guards, lib/, guard/.
const claudeHookFiles = () => [...glob(path.join(SRC, 'hooks'), '.sh'), ...glob(path.join(SRC, 'hooks'), '.py'),
  ...glob(path.join(SRC, 'hooks/lib'), '.sh'), ...glob(path.join(SRC, 'hooks/guard'), '.py')]
  .filter((f) => !path.basename(f).startsWith('codex-'));
const skillsLine = (plugin) => out(`   skills:  ${ls(path.join(SRC, 'skills')).filter((n) => isDir(path.join(SRC, 'skills', n))).join(',')}${plugin ? ' (without SKILL.md: the plugin loads them)' : ''}`);

// Without --context economy, an autoCompactWindow equal to a shipped plan's economy window
// (800000 Max, 300000 Pro — the one an earlier install wrote, whichever plan it was for)
// goes; any other value is the user's own and stays. Returns the value to remove, or 0.
function ownCompactWindow(doc) {
  if (CONTEXT === 'economy' || !isObj(doc)) return 0;
  const shipped = glob(path.join(SRC, 'profiles'), '.json').map((f) => {
    try { return Number(((readJSON(f).riskrails || {}).economy || {}).autoCompactWindow) || 0; } catch (e) { return 0; }
  });
  return shipped.includes(doc.autoCompactWindow) ? doc.autoCompactWindow : 0;
}

function claudeDryRun() {
  out(`== claude: plan=${PLAN} (${C.PLAN_LABEL}, ${C.TIER} profile) fable=${FABLE} fable-gate=${C.GATE} runtime-gate=on (dry run, nothing written)`);
  out(`== claude: target directory ${CLAUDE_DIR}`);
  for (const l of statuslineGate(path.join(CLAUDE_DIR, 'settings.json'), 'on', 'dry')) out('== ' + l);
  out(`== settings snippet (merged into ${CLAUDE_DIR}/settings.json):`);
  out(pretty(C.snippet));
  let current = {};
  try { current = readJSON(path.join(CLAUDE_DIR, 'settings.json')); } catch (e) { /* nothing installed yet */ }
  if (ownCompactWindow(current)) out(`== would remove autoCompactWindow ${current.autoCompactWindow} (economy off)`);
  out('== agents/architect.md (rendered head):');
  out(read(path.join(TMP, 'agents/architect.md')).split('\n').slice(0, 10).join('\n'));
  out('== CLAUDE.md managed block:');
  fs.writeSync(1, read(path.join(TMP, 'CLAUDE.block.md')));
  out(`== routing.md (on demand): ${CLAUDE_DIR}/riskrails/routing.md`);
  fs.writeSync(1, read(path.join(TMP, 'claude-routing.md')));
  out(`== profile.json (plan tables): ${CLAUDE_DIR}/riskrails/profile.json`);
  out(pretty(C.claudeProfile));
  out('== would install:');
  out(`   agents:  ${agentNames(',')}`);
  out(`   hooks:   ${claudeHookFiles().map((f) => path.relative(path.join(SRC, 'hooks'), f)).join(',')},ai-path-guard-defaults.json,ai-git-guard-defaults.json`);
  if (C.TIER === 'max') out(`   bin:     claude-1m (opus[1m]${FABLE === 'yes' ? ' / fable[1m]' : ''}, pins the model at launch; compacts near ${C.ONE_M_AT})`);
  const plugin = claudePlugin(CLAUDE_DIR);
  skillsLine(plugin);
  out('   retire:  skills/status (now skills/rr-status), into backups/<date>/ if present');
  shimLine('settings.json');
  pluginLine(plugin, true);
  homeLine(CLAUDE_DIR);
  sharedLine();
  out('   config:  ai-git-guard.json (only if absent)');
  out('   routing: riskrails/routing.md');
  out('   profile: riskrails/profile.json');
  out('== would migrate: the claude-routing managed block, if present, into this one');
}

// Every backup goes to one dated directory, <root>/backups/<date>/<path>: a backup beside
// the file it saves would be loaded too. A second run on the same day replaces that copy.
function backupFile(dst, root, src = dst) {
  const rel = path.relative(root, dst);
  const bak = path.join(root, 'backups', BACKUP_DATE, rel);
  mkdirp(path.dirname(bak));
  rmrf(bak);
  // A file is copied through a symlink: a CLAUDE.md linked from dotfiles is saved as its content.
  if (isDir(src)) copyTree(src, bak); else fs.copyFileSync(fs.realpathSync(src), bak);
  out(`backup: ${rel} -> backups/${BACKUP_DATE}/${rel}`);
}

function retire(root, rel) {                       // move what nothing installs any more into backups/<date>/
  if (!exists(path.join(root, rel))) return;
  const dest = path.join(root, 'backups', BACKUP_DATE, rel);
  mkdirp(path.dirname(dest));
  rmrf(dest);
  fs.renameSync(path.join(root, rel), dest);
  out(`retired: ${rel} -> backups/${BACKUP_DATE}/${rel}`);
}

// move_home — R35: the install home was <root>/claude-agentic/ before 3.4b. It moves to
// <root>/riskrails/ and the old path becomes a symlink to it for one version. A real old
// home beside an existing new one (or a link there, dangling or not) is retired.
function moveHome(root) {
  const old = path.join(root, 'claude-agentic'), nw = path.join(root, 'riskrails');
  if (!isDir(old) || isLink(old)) return;
  if (lexists(nw)) retire(root, 'claude-agentic');
  else { fs.renameSync(old, nw); out('moved: claude-agentic/ -> riskrails/'); }
  fs.symlinkSync('riskrails', old);
  out('linked: claude-agentic -> riskrails (for one version)');
}

// sweep_bak — every *.bak an older installer left beside a live file moves into
// backups/<date>/, keeping its path. Only the directories and root files this installer writes.
function sweepBak(root, ...names) {
  const candidates = [];
  for (const d of ['agents', 'hooks', 'hooks/lib', 'riskrails', 'bin']) candidates.push(...glob(path.join(root, d), '.bak'));
  for (const n of names) candidates.push(path.join(root, n + '.bak'));
  for (const bak of candidates) {
    if (!isFile(bak) || !exists(bak.slice(0, -4))) continue;
    const rel = path.relative(root, bak);
    const dest = path.join(root, 'backups', BACKUP_DATE, rel);
    mkdirp(path.dirname(dest));
    fs.renameSync(bak, dest);
    out(`moved: ${rel} -> backups/${BACKUP_DATE}/${rel}`);
  }
}

// The seven agents the 2026-09-02 install shipped, and the nine redesign 2.4 removed (with
// the Codex -strong/-balanced twins). Moved, not deleted: one mv out of backups/ restores one.
const STALE_AGENTS = ['code-implementer', 'qa-runner', 'qa-fixer', 'db-migrator', 'doc-lookup', 'log-inspector',
  'sylius-i18n-keys', 'ai-context', 'ai-expert', 'ai-implementer', 'ai-indexer', 'ai-planner', 'ai-release',
  'ai-risk', 'ai-security', 'ai-tester'];
const STALE_CODEX_TWINS = ['ai-reviewer-balanced', 'ai-risk-strong', 'ai-planner-strong', 'ai-expert-strong'];
function retireStaleAgents(root, ext) {
  for (const n of STALE_AGENTS) retire(root, `agents/${n}.${ext}`);
  if (ext === 'toml') for (const n of STALE_CODEX_TWINS) retire(root, `agents/${n}.${ext}`);
}

function installFile(src, dst, root = CLAUDE_DIR) {  // back up on a real change, then copy
  if (exists(dst) && !sameFile(src, dst)) backupFile(dst, root);
  fs.copyFileSync(src, dst);
  out(`installed: ${path.relative(root, dst)}`);
}

// install_skills — a backup must not land inside skills/ (both runtimes load every directory
// there as a skill), so backups go to backups/<date>/skills/. With the plugin active each
// skill goes in without its SKILL.md: the plugin loads the skill, and the skills still find
// their scripts (state.py, ai-path, ...) through $AI_HOME/skills/ as on the npx route.
function installSkills(root, plugin) {
  const backups = path.join(root, 'backups', BACKUP_DATE, 'skills');
  // /status became /rr-status (redesign 2.3); a leftover would load as a second status command.
  retire(root, 'skills/status');
  for (const name of ls(path.join(SRC, 'skills')).filter((n) => isDir(path.join(SRC, 'skills', n)))) {
    const d = path.join(SRC, 'skills', name), dst = path.join(root, 'skills', name);
    // A developer who ran the scripts in place leaves __pycache__ behind; it is not copied.
    const skip = plugin ? ['__pycache__', 'SKILL.md'] : '__pycache__';
    // The SKILL.md an earlier npx install left goes into the backup with its folder.
    if (isDir(dst) && (!sameTree(d, dst, skip) || (plugin && exists(path.join(dst, 'SKILL.md'))))) backupFile(dst, root);
    rmrf(dst);
    copyTree(d, dst, skip);
    out(`installed: skills/${name}${plugin ? ' (without SKILL.md)' : ''}`);
  }
  // Backups a previous installer left inside skills/, where they loaded as duplicate skills.
  for (const stale of glob(path.join(root, 'skills'), '.bak')) {
    if (!isDir(stale)) continue;
    mkdirp(backups);
    const base = path.basename(stale).slice(0, -4);
    rmrf(path.join(backups, base + '-old'));
    fs.renameSync(stale, path.join(backups, base + '-old'));
    out(`moved: skills/${path.basename(stale)} -> backups/${BACKUP_DATE}/skills/ (it was loading as a duplicate skill)`);
  }
  for (const f of ['skills/ai-init/scaffold-ai.sh', 'skills/ai-task/state.py', 'skills/ai-task/sensors.py',
    'skills/project-update/update.py', 'skills/rr-status/status.py']) chmodX(path.join(root, f));
}

// install_shared — the .ai/ files every project shares, at <root>/riskrails/ai, and the
// resolver beside them. The new tree is copied next to the old one and renamed into place,
// so there is no moment without a tree; a tree that differs from ai/ is backed up first.
function installShared(root) {
  const home = path.join(root, 'riskrails');
  mkdirp(home);
  rmrf(path.join(home, 'ai.new')); rmrf(path.join(home, 'ai.old'));
  copyTree(path.join(SRC, 'ai'), path.join(home, 'ai.new'));
  if (isDir(path.join(home, 'ai'))) {
    if (!sameTree(path.join(SRC, 'ai'), path.join(home, 'ai'))) backupFile(path.join(home, 'ai'), root);
    fs.renameSync(path.join(home, 'ai'), path.join(home, 'ai.old'));
  }
  fs.renameSync(path.join(home, 'ai.new'), path.join(home, 'ai'));
  rmrf(path.join(home, 'ai.old'));
  out(`installed: riskrails/ai (${countFiles(path.join(home, 'ai'))} files)`);
  installFile(path.join(SRC, 'scripts/ai-path'), path.join(home, 'ai-path'), root);
  chmodX(path.join(home, 'ai-path'));
  // `state.py profile set` resolves a plan through these, wherever the plugin cache is (R36.17).
  mkdirp(path.join(home, 'profiles')); mkdirp(path.join(home, 'scripts'));
  for (const f of glob(path.join(SRC, 'profiles'), '.json')) installFile(f, path.join(home, 'profiles', path.basename(f)), root);
  installFile(path.join(SRC, 'scripts/resolve-profile.py'), path.join(home, 'scripts/resolve-profile.py'), root);
}

function homeLine(root) {
  const old = path.join(root, 'claude-agentic');
  if (isDir(old) && !isLink(old)) out('   home:    claude-agentic/ -> riskrails/, the old path a symlink for one version');
}
const sharedLine = () => out(`   shared:  riskrails/ai (${countFiles(path.join(SRC, 'ai'))} files), riskrails/ai-path`);

// managed_block — replace the one managed block, or append it; migrates the predecessor
// plugin's block and an unmarked legacy section on the way. Backs up a non-empty target first.
function managedBlock(target, blockFile, label) {
  if (!exists(target)) fs.writeFileSync(target, '');
  if (fs.statSync(target).size > 0) backupFile(target, path.dirname(target));
  const block = read(blockFile).replace(/^\n+|\n+$/g, '');
  let text = read(target);
  const start = '<!-- riskrails:start -->', end = '<!-- riskrails:end -->';
  const notes = [];
  const routing = text.match(/<!-- claude-routing:start -->[\s\S]*?<!-- claude-routing:end -->\n?/);
  if (routing) {
    text = text.slice(0, routing.index) + text.slice(routing.index + routing[0].length);
    notes.push('migrated the claude-routing block');
  }
  const legacy = text.match(/^# Model allocation by task and scope[\s\S]*?(?=^# |(?![\s\S]))/m);
  if (legacy && !text.slice(0, legacy.index).includes(start)) {
    text = text.slice(0, legacy.index) + text.slice(legacy.index + legacy[0].length);
    notes.push("migrated an unmarked 'Model allocation' section");
  }
  // A legacy claude-agentic (before 3.4b) or Codex-agentic pair is the managed block under its
  // old name: rename it, never append beside it.
  if (!text.includes(start) && !text.includes(end)) {
    const pair = text.match(/<!-- (claude-agentic|[Cc]odex-agentic):start -->[\s\S]*?<!-- \1:end -->/);
    if (pair) {
      const name = pair[1];
      text = text.slice(0, pair.index)
        + pair[0].replace(`<!-- ${name}:start -->`, start).replace(`<!-- ${name}:end -->`, end)
        + text.slice(pair.index + pair[0].length);
      notes.push(`renamed the legacy ${name} markers`);
    }
  }
  let nw, action;
  if (text.includes(start) && text.includes(end)) {
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    nw = text.replace(new RegExp(esc(start) + '[\\s\\S]*?' + esc(end), 'g'), () => block);
    action = 'updated';
  } else {
    const sep = text.trim() ? '\n\n' : '';
    nw = text.replace(/\n+$/, '') + sep + block + '\n';
    action = 'appended';
  }
  nw = nw.replace(/\n{4,}/g, '\n\n\n');
  fs.writeFileSync(target, nw);
  out(`${label}: ${action}${notes.length ? ' + ' + notes.join(' + ') : ''}`);
}

// The three shell guards 3.5 retired: ai-guard.py runs all of them in one process. Their
// entries are removed from an existing install and the files moved into backups/<date>/.
const SHIM_RE = /\/hooks\/ai-(git|path|scope)-guard\.sh(?=["'\s]|$)/;
const SHIMS = ['ai-git-guard.sh', 'ai-path-guard.sh', 'ai-scope-guard.sh'];
const retireShims = (root) => { for (const n of SHIMS) retire(root, `hooks/${n}`); };
const shimLine = (file) => out(`   retire:  ${SHIMS.map((n) => 'hooks/' + n).join(', ')} and their ${file} entries (ai-guard.py runs all three), into backups/<date>/ if present`);

// Hook entries: the commands a group runs, as jq's `.hooks // [] | map(.command)`.
const commands = (group) => (Array.isArray(group && group.hooks) ? group.hooks : []).map((h) => (isObj(h) && 'command' in h ? h.command : null));
const sameList = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Drop the hooks whose command matches `re` from every group; a group or an event list left
// empty by that goes, the user's own hooks stay.
function dropHooks(doc, re) {
  if (!isObj(doc.hooks)) return doc;
  for (const [ev, groups] of Object.entries(doc.hooks)) {
    if (!Array.isArray(groups)) continue;
    doc.hooks[ev] = groups.flatMap((g) => {
      if (!isObj(g) || !Array.isArray(g.hooks) || g.hooks.length === 0) return [g];
      g.hooks = g.hooks.filter((h) => !re.test(isObj(h) && typeof h.command === 'string' ? h.command : ''));
      return g.hooks.length ? [g] : [];
    });
    if (doc.hooks[ev].length === 0) delete doc.hooks[ev];
  }
  return doc;
}

// Append each new group under its event unless an existing group there already runs one of
// its commands; with `replace`, an existing group that runs exactly a new group's commands is
// replaced by it (so a widened matcher or a raised timeout reaches an old install).
function mergeHooks(doc, newHooks, replace) {
  const before = clone(doc.hooks || {});
  doc.hooks = isObj(doc.hooks) ? doc.hooks : {};
  for (const [ev, entries] of Object.entries(newHooks || {})) {
    const known = (before[ev] || []).flatMap(commands);
    let groups = doc.hooks[ev] || [];
    if (replace) groups = groups.map((old) => entries.find((e) => sameList(commands(e), commands(old))) || old);
    const added = entries.filter((e) => !commands(e).some((c) => known.some((k) => k === c)));
    doc.hooks[ev] = groups.concat(clone(added));
  }
  return doc;
}

// The plugin route (R17): an active riskrails plugin carries the skills (their SKILL.md) and
// the hooks its hooks file names. npx then registers none of those hooks and installs no
// SKILL.md, so no skill loads twice and no hook runs twice; the skills' scripts, agents, the
// profile, the managed block, the shared tree and the settings stay npx's (the plugin format
// cannot carry them). Active is what the runtime itself records, never a cache folder alone:
// a cache outlives a disabled, project-scope or uninstalled plugin.
//
// Claude: plugins/installed_plugins.json has riskrails@<m> installed at scope user, and
// settings.json has enabledPlugins["riskrails@<m>"] true; the folder is its installPath.
function claudePlugin(home) {
  let reg, settings;
  try { reg = readJSON(path.join(home, 'plugins', 'installed_plugins.json')); } catch (e) { return null; }
  try { settings = readJSON(path.join(home, 'settings.json')); } catch (e) { settings = null; }
  const enabled = isObj(settings) && isObj(settings.enabledPlugins) ? settings.enabledPlugins : {};
  const plugins = isObj(reg) && isObj(reg.plugins) ? reg.plugins : {};
  for (const key of lsSort(Object.keys(plugins))) {
    const m = key.match(/^riskrails@(.+)$/);
    if (!m || enabled[key] !== true || !Array.isArray(plugins[key])) continue;
    const e = plugins[key].find((x) => isObj(x) && x.scope === 'user' && typeof x.installPath === 'string' && isDir(x.installPath));
    if (e) return { dir: e.installPath, marketplace: m[1], version: typeof e.version === 'string' ? e.version : path.basename(e.installPath) };
  }
  return null;
}

// 3.10.0 after 3.9.0: numeric parts compare as numbers, the rest as text.
function compareVersions(a, b) {
  const pa = a.split(/[.+-]/), pb = b.split(/[.+-]/);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] === undefined ? '' : pa[i], y = pb[i] === undefined ? '' : pb[i];
    const c = /^\d+$/.test(x) && /^\d+$/.test(y) ? Number(x) - Number(y) : x < y ? -1 : x > y ? 1 : 0;
    if (c) return c;
  }
  return 0;
}

// Codex: config.toml has a [plugins."riskrails@<m>"] table with enabled = true; the folder is
// the numerically latest version under plugins/cache/<m>/riskrails/.
function codexPlugin(home) {
  let toml;
  try { toml = read(path.join(home, 'config.toml')); } catch (e) { return null; }
  const table = /^[ \t]*\[plugins\."riskrails@([^"]+)"\][ \t]*(?:#.*)?$([\s\S]*?)(?=^[ \t]*\[|(?![\s\S]))/gm;
  for (const t of toml.matchAll(table)) {
    if (!/^[ \t]*enabled[ \t]*=[ \t]*true[ \t]*(?:#.*)?$/m.test(t[2])) continue;
    const p = path.join(home, 'plugins', 'cache', t[1], 'riskrails');
    const vers = isDir(p) ? ls(p).filter((v) => isDir(path.join(p, v))).sort(compareVersions) : [];
    if (vers.length) return { dir: path.join(p, vers[vers.length - 1]), marketplace: t[1], version: vers[vers.length - 1] };
  }
  return null;
}

// event -> the hook scripts the plugin registers on it.
function pluginHookKeys(plugin, file) {
  const keys = {};
  if (!plugin) return keys;
  let doc;
  try { doc = readJSON(path.join(plugin.dir, 'hooks', file)); } catch (e) { return keys; }
  for (const [ev, groups] of Object.entries(isObj(doc.hooks) ? doc.hooks : {})) {
    for (const g of Array.isArray(groups) ? groups : []) {
      for (const c of commands(g)) {
        const m = typeof c === 'string' && c.match(/\/hooks\/([\w.-]+)/);
        if (m) (keys[ev] = keys[ev] || new Set()).add(m[1]);
      }
    }
  }
  return keys;
}
const homeScript = (c) => { const m = typeof c === 'string' && c.match(/\$HOME\/\.(?:claude|codex)\/hooks\/([\w.-]+)/); return m ? m[1] : null; };
const pluginRuns = (keys, ev, c) => !!keys[ev] && keys[ev].has(homeScript(c));

// The groups of `newHooks` the plugin does not already run.
function withoutPluginHooks(newHooks, keys) {
  const r = {};
  for (const [ev, groups] of Object.entries(newHooks || {})) {
    const left = groups.filter((g) => !commands(g).every((c) => pluginRuns(keys, ev, c)));
    if (left.length) r[ev] = left;
  }
  return r;
}

// An earlier npx install's own entries for what the plugin now runs.
function dropPluginDuplicates(doc, keys) {
  if (!isObj(doc.hooks)) return 0;
  let n = 0;
  for (const ev of Object.keys(keys)) {
    if (!Array.isArray(doc.hooks[ev])) continue;
    doc.hooks[ev] = doc.hooks[ev].flatMap((g) => {
      if (!isObj(g) || !Array.isArray(g.hooks)) return [g];
      const before = g.hooks.length;
      g.hooks = g.hooks.filter((h) => !(isObj(h) && pluginRuns(keys, ev, h.command)));
      n += before - g.hooks.length;
      return g.hooks.length || before === 0 ? [g] : [];
    });
    if (doc.hooks[ev].length === 0) delete doc.hooks[ev];
  }
  return n;
}

function pluginLine(plugin, dry) {
  if (!plugin) return;
  const line = `riskrails ${plugin.version} (${plugin.marketplace}) loads the skills and runs the hooks; npx installs the skills without SKILL.md and registers none of the plugin's hooks`;
  out(dry ? '   plugin:  ' + line : 'plugin: ' + line);
}

function anyCommand(doc, events, re) {
  if (!isObj(doc.hooks)) return 0;
  let n = 0;
  for (const ev of events || Object.keys(doc.hooks)) {
    for (const g of Array.isArray(doc.hooks[ev]) ? doc.hooks[ev] : []) {
      if (isObj(g) && (Array.isArray(g.hooks) ? g.hooks : []).some((h) => re.test(isObj(h) && typeof h.command === 'string' ? h.command : ''))) n++;
    }
  }
  return n;
}

// The settings.json / hooks.json npx merges into: an object whose hooks, if any, map each
// event to a list of groups. Anything else exits 5 before either runtime is touched, as
// install.sh's jq did: a scripted install must not report success with no guard registered.
function homeJSONProblem(file) {
  if (!exists(file)) return '';
  let doc;
  try { doc = JSON.parse(read(file)); } catch (e) { return 'is not valid JSON'; }
  if (!isObj(doc)) return 'is not a JSON object';
  if (!('hooks' in doc)) return '';
  if (!isObj(doc.hooks)) return "has a 'hooks' that is not an object";
  for (const [ev, groups] of Object.entries(doc.hooks)) {
    if (!Array.isArray(groups)) return `has hooks.${ev} that is not a list`;
    if (groups.some((g) => !isObj(g) || ('hooks' in g && !Array.isArray(g.hooks)))) return `has an entry in hooks.${ev} that is not a hook group`;
  }
  return '';
}
function checkHomeJSON(files) {
  const bad = files.map((f) => [f, homeJSONProblem(f)]).filter(([, p]) => p);
  if (!bad.length) return;
  for (const [f, p] of bad) err(`riskrails: ${f} ${p}; fix it and run again`);
  die('riskrails: nothing was changed', 5);
}
const loadJSONFile = (file) => JSON.parse(read(file));
const writeJSONFile = (file, doc) => { fs.writeFileSync(file + '.tmp', pretty(doc) + '\n'); fs.renameSync(file + '.tmp', file); };

function claudeApply() {
  moveHome(CLAUDE_DIR);
  for (const d of ['agents', 'hooks/lib', 'hooks/guard', 'skills']) mkdirp(path.join(CLAUDE_DIR, d));
  sweepBak(CLAUDE_DIR, 'settings.json', 'CLAUDE.md');

  // ---------------------------------------------------------------- 1. agents
  for (const f of glob(path.join(TMP, 'agents'), '.md')) installFile(f, path.join(CLAUDE_DIR, 'agents', path.basename(f)));
  retireStaleAgents(CLAUDE_DIR, 'md');
  // `reviewer` is superseded by `ai-reviewer`. Retired only when byte-identical to the copy
  // claude-routing shipped — an edited one is the user's, and stays.
  const stale = path.join(CLAUDE_DIR, 'agents/reviewer.md');
  if (exists(stale)) {
    if (sameFile(path.join(SRC, 'agents/superseded/reviewer.md'), stale)) {
      fs.renameSync(stale, stale + '.superseded');
      out('retired: agents/reviewer.md -> reviewer.md.superseded (ai-reviewer replaces it)');
    } else {
      out('kept: agents/reviewer.md — you have edited it. ai-reviewer supersedes it; delete it when you are ready.');
    }
  }

  // ---------------------------------------------------------------- 2. hooks
  // hooks/guard/ is the package hooks/ai-guard.py imports.
  for (const f of claudeHookFiles()) {
    const sub = path.basename(path.dirname(f));
    const dst = sub === 'lib' || sub === 'guard' ? path.join(CLAUDE_DIR, 'hooks', sub, path.basename(f)) : path.join(CLAUDE_DIR, 'hooks', path.basename(f));
    installFile(f, dst);
    chmodX(dst);
  }
  installFile(path.join(SRC, 'hooks/ai-path-guard-defaults.json'), path.join(CLAUDE_DIR, 'hooks/ai-path-guard-defaults.json'));
  installFile(path.join(SRC, 'hooks/ai-git-guard-defaults.json'), path.join(CLAUDE_DIR, 'hooks/ai-git-guard-defaults.json'));
  // The git guard's live config is user-owned: seed it once, never overwrite it.
  seedGitGuard(CLAUDE_DIR);

  // ---------------------------------------------------------------- 2b. opus[1m] launcher
  // Max only. Linked into ~/.local/bin on a real install; a scratch home never writes outside itself.
  if (C.TIER === 'max') {
    mkdirp(path.join(CLAUDE_DIR, 'bin'));
    installFile(path.join(SRC, 'bin/claude-1m'), path.join(CLAUDE_DIR, 'bin/claude-1m'));
    chmodX(path.join(CLAUDE_DIR, 'bin/claude-1m'));
    const link = path.join(HOME, '.local/bin/claude-1m');
    if (CLAUDE_DIR === path.join(HOME, '.claude') && isDir(path.join(HOME, '.local/bin'))) {
      if (!exists(link) || isLink(link)) {
        rmrf(link);
        fs.symlinkSync(path.join(CLAUDE_DIR, 'bin/claude-1m'), link);
        out(`linked: ~/.local/bin/claude-1m -> ${CLAUDE_DIR}/bin/claude-1m`);
      } else {
        out(`kept: ~/.local/bin/claude-1m is not a link to this install; run ${CLAUDE_DIR}/bin/claude-1m directly`);
      }
    }
  }

  // ---------------------------------------------------------------- 3. skills
  const plugin = claudePlugin(CLAUDE_DIR);
  installShared(CLAUDE_DIR);
  pluginLine(plugin, false);
  installSkills(CLAUDE_DIR, plugin);

  // ---------------------------------------------------------------- 4. settings.json
  const SETTINGS = path.join(CLAUDE_DIR, 'settings.json');
  if (isFile(SETTINGS)) backupFile(SETTINGS, CLAUDE_DIR); else fs.writeFileSync(SETTINGS, '{}\n');
  let doc = loadJSONFile(SETTINGS);
  {
    // Every gate entry already there (fable-gate from before WP5, runtime-gate from an earlier
    // run) is removed first and the snippet's own merged below: two would count every agent twice.
    const beforeGate = anyCommand(doc, null, /fable-gate/);
    const hadStopFailure = anyCommand(doc, ['StopFailure'], /fable-gate|runtime-gate/);
    const hadShims = anyCommand(doc, null, SHIM_RE);
    dropHooks(doc, /\/hooks\/(fable-gate|runtime-gate)\.py/);
    dropHooks(doc, SHIM_RE);
    if (beforeGate) out('replaced: fable-gate hooks with runtime-gate');
    if (hadShims) out('replaced: the ai-git/path/scope-guard.sh hooks with ai-guard.py');
    if (C.GATE === 'off' && hadStopFailure) out('removed: runtime-gate StopFailure (no Fable on this install)');
    // `*` replaces arrays wholesale (wanted for availableModels/fallbackModel), so everything
    // but .hooks merges first. CLAUDE_CODE_SUBAGENT_MODEL=sonnet from older installs goes.
    const snippet = clone(C.snippet);
    const keys = pluginHookKeys(plugin, 'hooks.json');
    const newHooks = withoutPluginHooks(snippet.hooks || {}, keys);
    delete snippet.hooks;
    if (dropPluginDuplicates(doc, keys)) out('removed: the hook entries the riskrails plugin now runs');
    if (isObj(doc.env) && doc.env.CLAUDE_CODE_SUBAGENT_MODEL === 'sonnet') delete doc.env.CLAUDE_CODE_SUBAGENT_MODEL;
    doc = mergeHooks(deepMerge(doc, snippet), newHooks, true);
    const own = ownCompactWindow(doc);
    if (own) {
      delete doc.autoCompactWindow;
      out(`removed: autoCompactWindow ${own} (economy off)`);
    }
    writeJSONFile(SETTINGS, doc);
  }
  out('merged: settings.json');
  for (const l of statuslineGate(SETTINGS, 'on', 'apply')) out(l);
  // The fable-gate.py shim's last users were the entries and the statusline rewritten above.
  retire(CLAUDE_DIR, 'hooks/fable-gate.py');
  retireShims(CLAUDE_DIR);

  // ---------------------------------------------------------------- 5. CLAUDE.md block
  const GLOBAL_MD = path.join(CLAUDE_DIR, 'CLAUDE.md');
  managedBlock(GLOBAL_MD, path.join(TMP, 'CLAUDE.block.md'), 'CLAUDE.md');
  mkdirp(path.join(CLAUDE_DIR, 'riskrails'));
  installFile(path.join(TMP, 'claude-routing.md'), path.join(CLAUDE_DIR, 'riskrails/routing.md'));
  writeProfile(CLAUDE_DIR, C.claudeProfile);
  blockSize(GLOBAL_MD, 2560);

  // ---------------------------------------------------------------- 6. audits
  const missing = [], unpinned = [];
  for (const f of glob(path.join(CLAUDE_DIR, 'agents'), '.md')) {
    const text = read(f);
    if (!/^effort:/m.test(text)) missing.push(path.basename(f));
    if (path.basename(f) === 'architect.md') continue;       // may inherit the session on purpose
    if (!/^model:/m.test(text)) unpinned.push(path.basename(f));
  }
  if (missing.length) {
    out('');
    out("WARNING: these agents declare no 'effort:' and inherit the session effort:");
    for (const m of missing) out(`  - ${m}`);
    out("Add 'effort: low' for readers and runners, 'effort: medium' for mechanical work.");
  }
  if (unpinned.length) {
    out('');
    out("WARNING: these agents declare no 'model:' and inherit the session model:");
    for (const m of unpinned) out(`  - ${m}`);
    out("Pin 'model: haiku|sonnet|opus|fable' to the tier the role needs.");
  }
  let override = '';
  try { const v = readJSON(SETTINGS).env.CLAUDE_CODE_SUBAGENT_MODEL; override = v === null || v === undefined || v === false ? '' : String(v); } catch (e) { /* none */ }
  if (override) {
    out('');
    out(`WARNING: CLAUDE_CODE_SUBAGENT_MODEL=${override} is set. Since Claude Code 2.1.251 it only`);
    out("applies to an agent whose call and definition name no model. Before 2.1.251 (the JetBrains ACP");
    out("adapter bundles 2.1.219) it outranks every agent's 'model:' and the call's own model, so the");
    out('FAST/BALANCED/STRONG tiers all run on that one model. Unset it.');
  }
  const outside = read(GLOBAL_MD).replace(/<!-- riskrails:start -->[\s\S]*?<!-- riskrails:end -->/g, '');
  if (/claude-routing:start|# Model routing|# Model allocation by task/.test(outside)) {
    out('');
    out(`WARNING: ${GLOBAL_MD} still has routing rules outside the managed block.`);
    out('They are superseded by the block above — remove them by hand.');
  }
}

function seedGitGuard(root) {
  const live = path.join(root, 'hooks/ai-git-guard.json');
  if (!exists(live)) {
    fs.copyFileSync(path.join(SRC, 'hooks/ai-git-guard-defaults.json'), live);
    out('installed: hooks/ai-git-guard.json (edit this one; it is never overwritten)');
  } else {
    out('kept: hooks/ai-git-guard.json (your edits are preserved)');
  }
}

function claudeSummary() {
  const expert = C.TIER === 'pro' ? 'opus, pinned' : FABLE === 'yes' ? 'fable[1m], pinned' : 'the session model';
  const lines = [
    '',
    'Done (Claude Code).',
    `  target          ${CLAUDE_DIR}`,
    `  plan            ${PLAN}  (${C.PLAN_LABEL}, ${C.PROFILE_NAME} profile, fable=${FABLE})`,
    `  plan tables     ${CLAUDE_DIR}/riskrails/profile.json`,
    `  session model   ${C.SESSION_MODEL} (${C.SESSION_HUMAN}), effort ${C.EFFORT}`,
    `  fallback        ${C.FALLBACK}`,
    `  EXPERT tier     architect on ${expert} at effort ${C.ARCHITECT_EFFORT}`,
    ...(C.COMPACT ? [
      `  compaction      near ${C.COMPACT_AT} tokens on this ${Math.trunc(C.MODEL_WINDOW / 1000)}k session (autoCompactWindow ${C.COMPACT},`,
      "                  capped at the model's window, --context economy); context-guard warns from",
      `                  ${Math.trunc(C.COMPACT_AT * 80 / 100)} and holds a prompt back once from ${Math.trunc(C.COMPACT_AT * 120 / 100)}`,
    ] : [
      `  compaction      the runtime default: near ${C.COMPACT_AT} tokens on this ${Math.trunc(C.MODEL_WINDOW / 1000)}k session;`,
      `                  context-guard warns from ${Math.trunc(C.COMPACT_AT * 80 / 100)} and never holds a prompt back (economy only)`,
    ]),
    C.TIER === 'max'
      ? `  large context   claude-1m${FABLE === 'yes' ? ' [opus|fable]' : ''} starts one session on opus[1m]${FABLE === 'yes' ? ' or fable[1m] (Fable 5.1)' : ''} that compacts near ${C.ONE_M_AT}\n                  (${C.COMPACT ? 'the same autoCompactWindow, uncapped on a 1M model' : 'the runtime default'})`
      : '',
    `  read guard      an unbounded Read is refused above ${C.READ_LINES} lines / ${C.READ_BYTES} bytes`,
    `  agents          ${agentNames(' ')}`,
    '  hooks           cap-large-read, project-scaffold (Setup:init), ai-guard (git checks global;',
    '                  path and scope checks where .ai/ exists),',
    '                  context-guard (UserPromptSubmit, PreCompact, SessionStart:compact)',
    '  runtime gate    on — budgets from riskrails/profile.json, running agents, quota through the statusline',
    `  fable branch    ${C.GATE} ${C.GATE === 'on' ? `(Fable agents go to Opus while Fable is rate-limited, unreachable,\n                  or the weekly limit is ${C.WEEKLY}% used — checked through the statusline)` : '(no Fable on this install)'}`,
    `  skills          ${ls(path.join(SRC, 'skills')).join(' ')}`,
    '',
    'Restart Claude Code, then:',
    '  /config        model and effort match the profile',
    `  /hooks         lists cap-large-read, ai-guard, project-scaffold and context-guard, plus runtime-gate on PreToolUse, PostToolUse, SubagentStart, SubagentStop${C.GATE === 'on' ? ' and StopFailure' : ''}`,
    '  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report',
    '  /ai-init       in a project, to survey it and build .ai/',
    '  /project-update in a project that already has .ai/ or docs/sdlc/, to pull in these rules',
  ];
  out(lines.join('\n'));
}

// ======================================================================= Codex
// Two ChatGPT plans, two profiles. The plan is read from the ChatGPT login: the JWT in
// ~/.codex/auth.json carries chatgpt_plan_type.
const X = {};   // the Codex branch's rendered values

function codexRender() {
  const prev = prevPlan(CODEX_DIR);
  // BalancedMax is one routing idea on both runtimes: --plan balanced-max selects the Codex
  // balanced-max profile too, unless --codex-plan says otherwise.
  if (!CODEX_PLAN && PLAN === 'balanced-max') CODEX_PLAN = 'balanced-max';
  if (!CODEX_PLAN) {
    const live = detectPlan('codex');
    const detected = live.raw || '', det = live.plan || '', why = live.from || '';
    if (interactive()) {
      const proposed = prev || det;
      if (proposed) {
        const w = prev ? 'recorded by the previous install' : `detected from ${why}`;
        CODEX_PLAN = ask(`codex plan: ${proposed} (${w}) — Enter to confirm, or type plus/pro/balanced-max: `) || proposed;
      } else {
        CODEX_PLAN = ask(`Could not detect the ChatGPT plan (chatgpt_plan_type='${detected}'). Enter plan [plus/pro]: `);
      }
    } else if (det) {
      CODEX_PLAN = det; err(`detected codex plan: ${CODEX_PLAN} (${why})`);
    } else if (prev) {
      CODEX_PLAN = prev; err(`codex plan: ${CODEX_PLAN} (recorded by the previous install)`);
    } else {
      CODEX_PLAN = 'pro';
      err('could not detect the ChatGPT plan; using the pro profile — pass --codex-plan plus on Plus');
    }
  }
  if (['balanced_max', 'balancedmax'].includes(CODEX_PLAN)) CODEX_PLAN = 'balanced-max';
  const label = { plus: 'Plus', pro: 'Pro', 'balanced-max': 'BalancedMax' }[CODEX_PLAN];
  if (!label) die(`--codex-plan must be plus, pro or balanced-max (got '${CODEX_PLAN}')`, 2);
  const profileFile = path.join(SRC, `profiles/codex-${CODEX_PLAN}.json`);
  const codexProfile = agenticProfile('codex', `codex-${CODEX_PLAN}`, CODEX_PLAN, label, 'no');
  const P = readJSON(profileFile);
  const s = (v) => (v === null || v === undefined ? 'null' : String(v));
  const codexLabel = (m) => s((P.labels && P.labels[m] !== undefined && P.labels[m] !== null && P.labels[m] !== false) ? P.labels[m] : m);
  const t = (k, f) => s(P.tiers[k][f]);
  // The profile's plan rule names the EXPERT model by placeholder; render() makes one pass.
  const planRule = (P.plan_rule === null || P.plan_rule === undefined ? '' : String(P.plan_rule)).split('{{EXPERT_MODEL}}').join(codexLabel(P.tiers.EXPERT.model));

  python([path.join(SRC, 'scripts/render-codex-agents.py'), '--src', SRC, '--out', path.join(TMP, 'codex-agents'),
    '--profile', profileFile, '--ai-shared', path.join(CODEX_DIR, 'riskrails/ai')]);

  let readLines = 'null';
  try { readLines = s(readJSON(path.join(SRC, 'settings.common.json')).env.CLAUDE_READ_MAX_LINES); } catch (e) { /* null */ }
  const vars = {
    CODEX_PLAN: label, CODEX_PLAN_RULE: planRule,
    SESSION_MODEL: codexLabel(P.session.model), SESSION_MODEL_ID: s(P.session.model),
    SESSION_EFFORT: s(P.session.model_reasoning_effort), SUBAGENT_EFFORT: s(P.agents.default_subagent_reasoning_effort),
    FAST_EFFORT: t('FAST', 'effort'), BALANCED_EFFORT: t('BALANCED', 'effort'), STRONG_EFFORT: t('STRONG', 'effort'),
    FAST_MODEL: codexLabel(P.tiers.FAST.model), FAST_MODEL_ID: t('FAST', 'model'),
    BALANCED_MODEL: codexLabel(P.tiers.BALANCED.model), BALANCED_MODEL_ID: t('BALANCED', 'model'),
    STRONG_MODEL: codexLabel(P.tiers.STRONG.model), STRONG_MODEL_ID: t('STRONG', 'model'),
    EXPERT_MODEL: codexLabel(P.tiers.EXPERT.model), EXPERT_MODEL_ID: t('EXPERT', 'model'),
    EXPERT_EFFORT: t('EXPERT', 'effort'), MAX_THREADS: s(P.agents.max_concurrent_threads_per_session),
    PLAN_LABEL: `ChatGPT ${label}`, READ_LINES: readLines,
    AI_SHARED: path.join(CODEX_DIR, 'riskrails/ai'), AI_RESOLVER: path.join(CODEX_DIR, 'riskrails/ai-path'),
  };
  renderStub('global', 'codex', path.join(TMP, 'AGENTS.block.md'), vars);
  renderStub('global', 'codex', path.join(TMP, 'codex-routing.md'), vars, 'routing');
  Object.assign(X, { label, profileFile, codexProfile, P, s, t });
}

// The guard scripts Codex can use. cap-large-read.py is absent: Codex has no hookable Read
// tool. context-guard.py serves both runtimes: it reads its own location to know which;
// dialog-gate.py reads the payload's envelope (R36.19).
const codexHookFiles = () => ['ai-guard.py', 'runtime-gate.py', 'context-guard.py', 'dialog-gate.py'].map((n) => path.join(SRC, 'hooks', n));

function codexDryRun() {
  out(`== codex: plan=${CODEX_PLAN} (${X.label}) session ${X.s(X.P.session.model)} at ${X.s(X.P.session.model_reasoning_effort)} (dry run, nothing written)`);
  out(`== codex: target directory ${CODEX_DIR}`);
  const merged = python([path.join(SRC, 'scripts/merge-codex-config.py'), path.join(CODEX_DIR, 'config.toml'),
    '--profile', X.profileFile, '--status-context', STATUSLINE_CONTEXT, '--dry-run'], { allowFail: true });
  for (const l of merged.replace(/\n$/, '').split('\n')) if (merged) out('== ' + l);
  out('== AGENTS.md managed block:');
  fs.writeSync(1, read(path.join(TMP, 'AGENTS.block.md')));
  out(`== routing.md (on demand): ${CODEX_DIR}/riskrails/routing.md`);
  fs.writeSync(1, read(path.join(TMP, 'codex-routing.md')));
  out(`== profile.json (plan tables): ${CODEX_DIR}/riskrails/profile.json`);
  out(pretty(X.codexProfile));
  out('== would install:');
  out(`   agents:  ${ls(path.join(TMP, 'codex-agents')).map((n) => n.replace(/\.toml$/, '')).join(',')}`);
  out(`   hooks:   ${codexHookFiles().map((f) => path.basename(f)).join(',')}`);
  const plugin = codexPlugin(CODEX_DIR);
  skillsLine(plugin);
  out('   retire:  skills/status (now skills/rr-status), into backups/<date>/ if present');
  shimLine('hooks.json');
  pluginLine(plugin, true);
  homeLine(CODEX_DIR);
  sharedLine();
  out('   config:  ai-git-guard.json (only if absent)');
  out('   routing: riskrails/routing.md');
  out('   profile: riskrails/profile.json');
  out(`== hooks.json entries (merged into ${CODEX_DIR}/hooks.json):`);
  out(pretty(readJSON(path.join(SRC, 'codex/hooks.json'))));
  out('== reminder: Codex lists a non-managed hook until you review it in /hooks');
}

function codexApply() {
  moveHome(CODEX_DIR);
  for (const d of ['agents', 'hooks/lib', 'hooks/guard', 'skills']) mkdirp(path.join(CODEX_DIR, d));
  sweepBak(CODEX_DIR, 'hooks.json', 'config.toml', 'AGENTS.md');

  // -------------------------------------------------------------- 1. agents
  for (const f of glob(path.join(TMP, 'codex-agents'), '.toml')) installFile(f, path.join(CODEX_DIR, 'agents', path.basename(f)), CODEX_DIR);
  retireStaleAgents(CODEX_DIR, 'toml');

  // -------------------------------------------------------------- 2. hooks
  for (const f of codexHookFiles()) {
    const dst = path.join(CODEX_DIR, 'hooks', path.basename(f));
    installFile(f, dst, CODEX_DIR);
    chmodX(dst);
  }
  for (const f of glob(path.join(SRC, 'hooks/guard'), '.py')) installFile(f, path.join(CODEX_DIR, 'hooks/guard', path.basename(f)), CODEX_DIR);
  installFile(path.join(SRC, 'hooks/lib/ai-hook-common.sh'), path.join(CODEX_DIR, 'hooks/lib/ai-hook-common.sh'), CODEX_DIR);
  installFile(path.join(SRC, 'hooks/ai-path-guard-defaults.json'), path.join(CODEX_DIR, 'hooks/ai-path-guard-defaults.json'), CODEX_DIR);
  installFile(path.join(SRC, 'hooks/ai-git-guard-defaults.json'), path.join(CODEX_DIR, 'hooks/ai-git-guard-defaults.json'), CODEX_DIR);
  seedGitGuard(CODEX_DIR);

  // -------------------------------------------------------------- 3. skills
  const plugin = codexPlugin(CODEX_DIR);
  installShared(CODEX_DIR);
  pluginLine(plugin, false);
  installSkills(CODEX_DIR, plugin);

  // -------------------------------------------------------------- 4. hooks.json
  // codex-model-gate entries from before WP5 and runtime-gate ones from an earlier run go
  // first, so the merge adds exactly one gate per event. Codex runs only hooks the user has
  // reviewed (config.toml keeps a trusted_hash per entry): a changed entry is skipped until
  // it is reviewed once in /hooks. A group whose commands are exactly a new group's is
  // replaced by it, as on Claude, so a reinstall carries a widened matcher (R36 7d2); an
  // unchanged group is written back as it was and keeps its trust.
  const HOOKS = path.join(CODEX_DIR, 'hooks.json');
  if (isFile(HOOKS)) backupFile(HOOKS, CODEX_DIR); else fs.writeFileSync(HOOKS, '{}\n');
  let hadShim = false, hadGuardShims = false;
  const doc = loadJSONFile(HOOKS);
  {
    hadShim = anyCommand(doc, null, /\/hooks\/codex-model-gate\.py/) > 0;
    hadGuardShims = anyCommand(doc, null, SHIM_RE) > 0;
    dropHooks(doc, /\/hooks\/(codex-model-gate|runtime-gate)\.py/);
    dropHooks(doc, SHIM_RE);
    const keys = pluginHookKeys(plugin, 'codex-hooks.json');
    if (dropPluginDuplicates(doc, keys)) out('removed: the hook entries the riskrails plugin now runs');
    const fresh = withoutPluginHooks(readJSON(path.join(SRC, 'codex/hooks.json')).hooks, keys);
    const changed = Object.entries(fresh).some(([ev, entries]) => ((isObj(doc.hooks) && doc.hooks[ev]) || []).some(
      (old) => entries.some((e) => sameList(commands(e), commands(old)) && !sameList(e, old))));
    writeJSONFile(HOOKS, mergeHooks(doc, fresh, true));
    if (changed) out('changed: riskrails hook entries in hooks.json — review them once in /hooks, or Codex skips them');
  }
  out('merged: hooks.json');
  if (hadShim) out('replaced: codex-model-gate.py hooks with runtime-gate.py — review the changed gate entries once in /hooks, or Codex skips them');
  if (hadGuardShims) out('replaced: the ai-git/path/scope-guard.sh hooks with ai-guard.py — review the new guard entry once in /hooks, or Codex skips it');
  retire(CODEX_DIR, 'hooks/codex-model-gate.py');
  retireShims(CODEX_DIR);

  // -------------------------------------------------------------- 5. config.toml
  // Backed up only when the merge changed it: a second install the same day must not replace
  // the user's original with ours.
  const config = path.join(CODEX_DIR, 'config.toml'), before = path.join(TMP, 'config.toml.before');
  rmrf(before);
  if (exists(config) && fs.statSync(config).size > 0) fs.copyFileSync(fs.realpathSync(config), before);
  python([path.join(SRC, 'scripts/merge-codex-config.py'), config, '--profile', X.profileFile,
    '--status-context', STATUSLINE_CONTEXT, '--no-backup'], { capture: false });
  if (exists(before) && fs.statSync(before).size > 0 && !sameFile(before, config)) backupFile(config, CODEX_DIR, before);

  // -------------------------------------------------------------- 6. AGENTS.md
  managedBlock(path.join(CODEX_DIR, 'AGENTS.md'), path.join(TMP, 'AGENTS.block.md'), 'AGENTS.md');
  mkdirp(path.join(CODEX_DIR, 'riskrails'));
  installFile(path.join(TMP, 'codex-routing.md'), path.join(CODEX_DIR, 'riskrails/routing.md'), CODEX_DIR);
  writeProfile(CODEX_DIR, X.codexProfile);
  blockSize(path.join(CODEX_DIR, 'AGENTS.md'), 2560);
  codexDocAdvisory(path.join(CODEX_DIR, 'AGENTS.md'));
}

function codexSummary() {
  const { P, s, t } = X;
  out([
    '',
    'Done (Codex).',
    `  target          ${CODEX_DIR}`,
    `  plan            ${CODEX_PLAN}  (${X.label})`,
    `  session model   ${s(P.session.model)} at effort ${s(P.session.model_reasoning_effort)}`,
    `  subagent default ${s(P.agents.default_subagent_model)} at ${s(P.agents.default_subagent_reasoning_effort)}, at most ${s(P.agents.max_concurrent_threads_per_session)} threads at once`,
    `  FAST tier       ${t('FAST', 'model')} at ${t('FAST', 'effort')} (Explore, log-reader)`,
    `  BALANCED tier   ${t('BALANCED', 'model')} at ${t('BALANCED', 'effort')} (ai-discovery at low)`,
    `  STRONG tier     ${t('STRONG', 'model')} at ${t('STRONG', 'effort')} (ai-reviewer, architect)`,
    `  EXPERT tier     ${t('EXPERT', 'model')} at ${t('EXPERT', 'effort')} (no agent pins it)`,
    `  runtime gate    sends EXPERT work to ${t('STRONG', 'model')} while ${t('EXPERT', 'model')} is rate-limited or`,
    "                  unavailable, explains an EXPERT launch past the plan's budget, reads the quota",
    "                  from the session rollouts; 'runtime-gate.py status' / 'quota' show it",
    `  agents          ${ls(path.join(TMP, 'codex-agents')).map((n) => n.replace(/\.toml$/, '')).join(' ')}`,
    '  hooks           ai-guard (git checks global; path and scope checks where .ai/ exists),',
    '                  runtime-gate, context-guard. No cap-large-read: Codex has no hookable Read tool.',
    `  skills          ${ls(path.join(SRC, 'skills')).join(' ')}`,
    '',
    'Restart Codex, then:',
    '  /hooks         review and trust the guard, gate and context hooks — until you do, Codex skips them',
    '  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report',
    '  /ai-init       in a project, to survey it and build .ai/',
    '',
    `Your previous default model was replaced. backups/${BACKUP_DATE}/config.toml holds the old one.`,
  ].join('\n'));
}

// ======================================================================= run
if (DO_CLAUDE) claudeRender();
if (DO_CODEX) codexRender();
if (DRY) {
  if (DO_CLAUDE) claudeDryRun();
  if (DO_CODEX) codexDryRun();
  process.exit(0);
}
checkHomeJSON([...(DO_CLAUDE ? [path.join(CLAUDE_DIR, 'settings.json')] : []), ...(DO_CODEX ? [path.join(CODEX_DIR, 'hooks.json')] : [])]);
if (DO_CLAUDE) claudeApply();
if (DO_CODEX) codexApply();
if (DO_CLAUDE) claudeSummary();
if (DO_CODEX) codexSummary();
process.exit(0);
