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
'use strict';

// The key, as readline's keypress event gives it, as one of the reducer's tokens (or null).
function token(key) {
  if (!key) return null;
  if (key.ctrl && key.name === 'c') return 'abort';
  if (key.ctrl || key.meta) return null;
  const name = key.name || key.sequence;
  if (name === 'up' || name === 'k') return 'up';
  if (name === 'down' || name === 'j') return 'down';
  if (name === 'home' || name === 'end') return name;
  if (name === 'return' || name === 'enter') return 'enter';
  if (name === 'escape' || name === 'q') return 'abort';
  if (/^[1-9]$/.test(String(name))) return String(name);
  return null;
}

// The pure step: {index, count, done} and a token → the next state. done is null, 'pick' or 'abort'.
function reduce(state, tok) {
  const last = state.count - 1;
  switch (tok) {
    case 'up': return { ...state, index: Math.max(0, state.index - 1) };
    case 'down': return { ...state, index: Math.min(last, state.index + 1) };
    case 'home': return { ...state, index: 0 };
    case 'end': return { ...state, index: last };
    case 'enter': return { ...state, done: 'pick' };
    case 'abort': return { ...state, done: 'abort' };
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
  const draw = (index) => {
    erase();
    const shown = lines(spec, index, process.stderr.columns || 0);
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
      const why = state.index === initial && spec.why ? ` (${spec.why})` : '';
      write(`${spec.title}: ${value}${why}\n`);
      process.stdout.write(value, () => process.exit(0));
    } else {
      process.exit(code);
    }
  };
  for (const sig of ['SIGTERM', 'SIGHUP', 'SIGINT']) process.on(sig, () => finish(130));

  const initial = Number.isInteger(spec.initial) && spec.initial >= 0 && spec.initial < spec.items.length
    ? spec.initial : 0;
  let state = { index: initial, count: spec.items.length, done: null };
  // A lone Esc: emitKeypressEvents without a readline interface has no escape timeout and would
  // wait for the rest of a sequence. An arrow key arrives as one chunk (ESC [ B), never as ESC alone.
  stdin.on('data', (chunk) => { if (chunk.length === 1 && chunk[0] === 0x1b) finish(130); });
  require('readline').emitKeypressEvents(stdin);
  write('\x1b[?25l');
  draw(state.index);
  stdin.on('keypress', (_str, key) => {
    const tok = token(key);
    if (tok === null) return;
    const next = reduce(state, tok);
    if (next.done === 'pick') { state = next; finish(0, String(spec.items[state.index].value)); return; }
    if (next.done === 'abort') { finish(130); return; }
    if (next.index !== state.index) { state = next; draw(state.index); }
  });
  stdin.resume();
}

module.exports = { reduce, token, lines };
if (require.main === module) main();
