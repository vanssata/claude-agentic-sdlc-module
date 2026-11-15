#!/usr/bin/env node
// The installer's arrow-key menu (spec interactive-setup-options R2, R7). Node 18+, stdlib only.
//
// bin/riskrails.js runs this file as a child, `spawnSync(process.execPath, [menu.js])` with
// stdio ['inherit', 'pipe', 'inherit'], and passes the menu in RISKRAILS_MENU_SPEC:
//   {"title": "plan", "why": "detected from …", "initial": 0,
//    "items": [{"value": "pro", "label": "pro", "note": "…"}, …]}
// The child owns the terminal while it runs: raw mode on stdin, the menu drawn on stderr.
//   Enter          erases the menu, prints `<title>: <value>` (and ` (<why>)` when the value is the
//                  initial one) on stderr, writes the value to stdout, exit 0
//   Ctrl-C/Esc/q   erases the menu, exit 130
//   no terminal    exit 3, nothing drawn: the parent falls back to its typed prompt
// Keys: ↑/k ↓/j (stop at the ends), Home/End, 1–9 jump to that row, Enter picks.
//
// A spec with any of the keys below is drawn as a wizard screen; without them it is the 4.2.0 menu.
//   step    {"n": 3, "names": ["runtimes", "plan", "context", …]}: the stepper line, step n of names
//   help    the help line, replacing the default
//   back    true: ←, h or Backspace exit 4, nothing drawn, nothing on stdout
//   multi   true: Space toggles a row, Enter confirms the set; stdout is the checked values in
//           item order joined by "," ("" when none is checked)
//   checked the values checked at the start (multi)
//   color   true: styles on stderr, when ansi.useColor allows it
// Items may carry "desc", shown under the list while the item is highlighted. → also confirms.
// Exit codes: 0 pick, 3 no terminal, 4 back, 130 abort.
'use strict';
const { useColor, paint } = require('./ansi');

const WIZARD_KEYS = ['help', 'multi', 'checked', 'step', 'back', 'color'];
const isWizard = (spec) => WIZARD_KEYS.some((k) => spec[k] !== undefined);

// The key, as readline's keypress event gives it, as one of the reducer's tokens (or null).
function token(key, wizard) {
  if (!key) return null;
  if (key.ctrl && key.name === 'c') return 'abort';
  if (key.ctrl || key.meta) return null;
  const name = key.name || key.sequence;
  if (name === 'up' || name === 'k') return 'up';
  if (name === 'down' || name === 'j') return 'down';
  if (name === 'home' || name === 'end') return name;
  if (name === 'return' || name === 'enter') return 'enter';
  if (name === 'escape' || name === 'q') return 'abort';
  if (wizard) {
    if (name === 'left' || name === 'h' || name === 'backspace') return 'back';
    if (name === 'right') return 'enter';
    if (name === 'space' || name === ' ') return 'space';
  }
  if (/^[1-9]$/.test(String(name))) return String(name);
  return null;
}

// The pure step: {index, count, done, checked?} and a token → the next state. done is null, 'pick',
// 'back' or 'abort'. checked, an array of booleans, is there only for a multi-select.
function reduce(state, tok) {
  const last = state.count - 1;
  switch (tok) {
    case 'up': return { ...state, index: Math.max(0, state.index - 1) };
    case 'down': return { ...state, index: Math.min(last, state.index + 1) };
    case 'home': return { ...state, index: 0 };
    case 'end': return { ...state, index: last };
    case 'enter': return { ...state, done: 'pick' };
    case 'abort': return { ...state, done: 'abort' };
    case 'back': return { ...state, done: 'back' };
    case 'space': return state.checked
      ? { ...state, checked: state.checked.map((c, i) => (i === state.index ? !c : c)) } : state;
    default: {
      const n = /^[1-9]$/.test(String(tok)) ? Number(tok) : 0;
      return n >= 1 && n <= state.count ? { ...state, index: n - 1 } : state;
    }
  }
}

// The menu's lines, each cut to the terminal's width: a wrapped line would break the redraw's count.
function lines(spec, index, columns) {
  const fit = (t) => (columns > 1 && [...t].length > columns - 1 ? [...t].slice(0, columns - 2).join('') + '…' : t);
  const head = `${spec.title}${spec.why ? ` (${spec.why})` : ''} — ↑/↓ to move, Enter to confirm, Esc to abort`;
  const width = Math.max(...spec.items.map((it) => String(it.label).length));
  return [fit(head), ...spec.items.map((it, i) => {
    const mark = i === index ? '❯' : ' ';
    const row = fit(`${mark} ${i + 1}. ${String(it.label).padEnd(width)}${it.note ? `  ${it.note}` : ''}`);
    return i === index ? `\x1b[7m${row}\x1b[0m` : row;
  })];
}

// The wizard screen: the stepper, a blank line, the title, the rows, a blank line, the highlighted
// option's description and the help line. Cut to the terminal's width like lines().
function wizardLines(spec, state, columns, color) {
  const fit = (t) => (columns > 1 && [...t].length > columns - 1 ? [...t].slice(0, columns - 2).join('') + '…' : t);
  const out = [];
  if (spec.step) {
    const names = spec.step.names.map((nm, i) => (i + 1 === spec.step.n ? paint(color, 'bold', `[${nm}]`) : nm));
    out.push(fit(` step ${spec.step.n} of ${spec.step.names.length} · ${names.join(' › ')}`), '');
  }
  out.push(fit(`  ${paint(color, 'bold', spec.title)}${spec.why ? ` (${spec.why})` : ''}`));
  const width = Math.max(...spec.items.map((it) => String(it.label).length));
  spec.items.forEach((it, i) => {
    const box = state.checked ? `[${state.checked[i] ? 'x' : ' '}] ` : '';
    const row = fit(`  ${i === state.index ? '❯' : ' '} ${box}${i + 1}. ${String(it.label).padEnd(width)}${it.note ? `  ${it.note}` : ''}`);
    out.push(i === state.index ? paint(color, 'inverse', row) : row);
  });
  const desc = spec.items[state.index].desc;
  const keys = spec.help || `↑/↓ move   ${spec.multi ? 'Space toggle   ' : ''}${spec.back ? '← back   ' : ''}Enter next   Esc cancel`;
  out.push('', ...(desc ? [fit(`  ${paint(color, 'dim', desc)}`)] : []), fit(`  ${paint(color, 'dim', keys)}`));
  return out;
}

function main() {
  let spec;
  try { spec = JSON.parse(process.env.RISKRAILS_MENU_SPEC || ''); } catch (e) { process.exit(3); }
  if (!spec || !Array.isArray(spec.items) || spec.items.length === 0) process.exit(3);
  const stdin = process.stdin;
  if (!stdin.isTTY || !process.stderr.isTTY) process.exit(3);
  try { stdin.setRawMode(true); } catch (e) { process.exit(3); }

  const write = (s) => process.stderr.write(s);
  let drawn = 0;
  const erase = () => { if (drawn) write(`\x1b[${drawn}A\r\x1b[J`); drawn = 0; };
  const wizard = isWizard(spec);
  const color = spec.color === true && useColor(process.stderr.isTTY, process.env);
  const draw = () => {
    erase();
    const shown = wizard ? wizardLines(spec, state, process.stderr.columns || 0, color)
      : lines(spec, state.index, process.stderr.columns || 0);
    write(shown.join('\n') + '\n');
    drawn = shown.length;
  };
  const restore = () => {
    try { stdin.setRawMode(false); } catch (e) { /* already gone */ }
    stdin.pause();
    write('\x1b[?25h');
  };
  const finish = (code, value) => {
    erase();
    restore();
    if (code === 0) {
      const why = !spec.multi && state.index === initial && spec.why ? ` (${spec.why})` : '';
      write(`${spec.title}: ${spec.multi ? value.split(',').join(', ') : value}${why}\n`);
      process.stdout.write(value, () => process.exit(0));
    } else {
      process.exit(code);
    }
  };
  for (const sig of ['SIGTERM', 'SIGHUP', 'SIGINT']) process.on(sig, () => finish(130));

  const initial = Number.isInteger(spec.initial) && spec.initial >= 0 && spec.initial < spec.items.length
    ? spec.initial : 0;
  let state = { index: initial, count: spec.items.length, done: null };
  if (spec.multi) {
    const on = new Set((Array.isArray(spec.checked) ? spec.checked : []).map(String));
    state.checked = spec.items.map((it) => on.has(String(it.value)));
  }
  // A lone Esc: emitKeypressEvents without a readline interface has no escape timeout and would
  // wait for the rest of a sequence. An arrow key arrives as one chunk (ESC [ B), never as ESC alone.
  stdin.on('data', (chunk) => { if (chunk.length === 1 && chunk[0] === 0x1b) finish(130); });
  require('readline').emitKeypressEvents(stdin);
  write('\x1b[?25l');
  draw();
  stdin.on('keypress', (_str, key) => {
    const tok = token(key, wizard);
    if (tok === null || (tok === 'back' && !spec.back)) return;
    const next = reduce(state, tok);
    if (next.done === 'pick') {
      state = next;
      const set = spec.items.filter((_it, i) => state.checked && state.checked[i]).map((it) => String(it.value));
      finish(0, state.checked ? set.join(',') : String(spec.items[state.index].value));
      return;
    }
    if (next.done === 'abort') { finish(130); return; }
    if (next.done === 'back') { finish(4); return; }
    if (next.index !== state.index || next.checked !== state.checked) { state = next; draw(); }
  });
  stdin.resume();
}

module.exports = { reduce, token, lines, wizardLines };
if (require.main === module) main();
