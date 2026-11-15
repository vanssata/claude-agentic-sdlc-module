#!/usr/bin/env node
// --uninstall as a plan (spec ui-first-approvals R18). Pure: planUninstall takes what a home holds as
// data and returns what to do; applyUninstall does it only through the injected `io`. Nothing is deleted.
'use strict';

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const START = '<!-- riskrails:start -->', END = '<!-- riskrails:end -->';
const GATE = '"$HOME/.claude/hooks/runtime-gate.py" statusline';

// Our hook entries out of hooks: a command naming hooks/<one of our files>. Returns the count removed.
function dropOurHooks(hooks, names) {
  const ours = (h) => isObj(h) && typeof h.command === 'string' && names.some((n) => h.command.includes(`/hooks/${n}`));
  let n = 0;
  for (const ev of Object.keys(hooks)) {
    if (!Array.isArray(hooks[ev])) continue;
    for (const g of hooks[ev]) {
      if (isObj(g) && Array.isArray(g.hooks)) { const k = g.hooks.length; g.hooks = g.hooks.filter((h) => !ours(h)); n += k - g.hooks.length; }
    }
    hooks[ev] = hooks[ev].filter((g) => !(isObj(g) && Array.isArray(g.hooks) && g.hooks.length === 0));
    if (hooks[ev].length === 0) delete hooks[ev];
  }
  return n;
}

// The snippet's keys out of doc where equal (their dotted paths go to `removed`); a key that differs goes to `differs`.
function dropSnippet(doc, snippet, path, differs, removed) {
  for (const k of Object.keys(snippet)) {
    if (!(k in doc)) continue;
    if (isObj(doc[k]) && isObj(snippet[k])) {
      dropSnippet(doc[k], snippet[k], `${path}${k}.`, differs, removed);
      if (Object.keys(doc[k]).length === 0) delete doc[k];
    } else if (same(doc[k], snippet[k])) { delete doc[k]; removed.push(path + k); }
    else differs.push(path + k);
  }
}

// The user's command our statusline wraps, or the one the record saved; '' when there is none.
function ownCommand(line, record) {
  if (record && typeof record.replaced === 'string' && record.replaced.trim()) return record.replaced;
  const m = /--then '((?:[^']|'\\'')*)'$/.exec(line.command);
  return m ? m[1].replace(/'\\''/g, "'") : '';
}

function planSettings(inv, ours) {
  const doc = JSON.parse(JSON.stringify(inv.settings));
  const notes = [];
  if (isObj(doc.hooks) && dropOurHooks(doc.hooks, ours)) notes.push('our hook entries removed');
  if (isObj(doc.hooks) && Object.keys(doc.hooks).length === 0) delete doc.hooks;
  const line = doc.statusLine;
  if (isObj(line) && typeof line.command === 'string' && line.command.startsWith(GATE)) {
    const own = ownCommand(line, inv.statusline);
    if (own) doc.statusLine = { type: 'command', command: own }; else delete doc.statusLine;
    notes.push(own ? 'statusLine restored to your own command' : 'our statusLine removed');
  }
  const { hooks, statusLine, ...rest } = inv.snippet || {};
  const differs = [], removed = [];
  dropSnippet(doc, rest, '', differs, removed);
  if (!same(doc, inv.settings) && notes.length === 0) notes.push('settings keys of the recorded plan removed');
  return { doc, notes, differs, removed };
}

function blockRemoved(text) {
  const i = text.indexOf(START), j = text.indexOf(END);
  if (i < 0 || j < i) return null;
  return (text.slice(0, i) + text.slice(j + END.length)).replace(/\n{3,}/g, '\n\n').replace(/^\n+/, '').replace(/\n+$/, '') + '\n';
}

// inventory: { files: [paths relative to the home that exist and that the installer ships: agents/x.md,
//   hooks/…, skills/x, riskrails, bin/claude-1m], settings: object|null, snippet: object (what the recorded
//   plan renders into settings.json), statusline: object|null (riskrails/statusline.json), claudeMd: string|null,
//   shippedHooks: [names of the hook files the installer ships, relative to hooks/, whether or not they exist],
//   earlierSettings: path of the oldest settings backup|null }.
// Returns { moved: [path], edited: [{ file, kind: 'json'|'text', content, notes: [string], removedKeys: [string],
//   earlier: string }], kept: [string] }.
function planUninstall(inv) {
  const moved = [...inv.files], edited = [], kept = [];
  if (isObj(inv.settings)) {
    const { doc, notes, differs, removed } = planSettings(inv, inv.shippedHooks);
    const earlier = inv.earlierSettings ? `an earlier value of yours, if you had one, is in ${inv.earlierSettings}`
      : 'no settings backup under backups/; a value of yours that the install replaced is not recoverable from here';
    if (!same(doc, inv.settings)) edited.push({ file: 'settings.json', kind: 'json', content: doc, notes, removedKeys: removed, earlier });
    for (const k of differs) kept.push(`settings.json: ${k} differs from what the recorded plan writes; left as it is`);
  }
  const text = typeof inv.claudeMd === 'string' ? blockRemoved(inv.claudeMd) : null;
  if (text !== null) edited.push({ file: 'CLAUDE.md', kind: 'text', content: text, notes: ['the managed block removed'] });
  if (moved.length === 0 && edited.length === 0) return { moved, edited, kept: [] };
  kept.push('Codex config.toml: values stay', 'the riskrails plugin: stays installed', "every project's .ai/: stays");
  return { moved, edited, kept };
}

// io: { move(rel) — to backups/<stamp>/<rel>, backup(rel) — a copy there, writeJSON(rel, obj),
//   writeText(rel, text), log(line) }. Nothing else is touched. The files are edited first, so a move that
//   fails leaves no setting pointing at a file of ours; the failure stops the run with what was done and what is left.
function applyUninstall(plan, io) {
  const edited = [];
  for (const e of plan.edited) {
    io.backup(e.file);
    if (e.kind === 'json') io.writeJSON(e.file, e.content); else io.writeText(e.file, e.content);
    edited.push(e.file);
    io.log(`edited: ${e.file} — ${e.notes.join(', ')}`);
    for (const k of e.removedKeys || []) io.log(`removed: ${e.file}: ${k}`);
    if ((e.removedKeys || []).length > 0) io.log(`earlier: ${e.earlier}`);
  }
  for (const [i, f] of plan.moved.entries()) {
    try { io.move(f); } catch (err) {
      throw new Error(`riskrails: could not move ${f} into backups/ (${err.message}); done: edited ${edited.join(', ') || 'nothing'}, ${i} of ${plan.moved.length} moved; `
        + `left: ${plan.moved.slice(i).join(', ')}; nothing was deleted. Move the rest by hand into backups/, or run --uninstall again once the cause is gone`);
    }
    io.log(`moved: ${f} -> backups/`);
  }
  for (const k of plan.kept) io.log(`kept: ${k}`);
}

module.exports = { planUninstall, applyUninstall };
