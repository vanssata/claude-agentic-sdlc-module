#!/usr/bin/env node
// The installer's wizard, as data (spec ui-first-approvals R15-R17). Pure: no terminal, clock or
// filesystem. bin/riskrails.js draws the steps with bin/menu.js and prints what these return.
'use strict';

const CLAUDE_PLANS = [['pro', 'Pro'], ['team-pro', 'Team Standard seat'], ['team-max', 'Team Premium seat'],
  ['max', 'Max'], ['max20', "Max 20x: max's settings, larger budgets"],
  ['balanced-max', 'Max account, only the session runs Opus 5.5 (200k window)']];
const CODEX_PLANS = [['plus', 'ChatGPT Plus'], ['pro', 'ChatGPT Pro'], ['balanced-max', 'only the session runs the strong model']];
const FABLE_PLANS = ['max', 'max20', 'team-max'];

const items = (rows, checked) => rows.map(([value, note]) => ({ value, label: value, note,
  ...(checked ? { checked: checked.includes(value) } : {}) }));
const initial = (rows, value) => Math.max(0, rows.findIndex(([v]) => v === value));

// The steps for what is detected: { claude, codex (booleans: the runtimes selected), plan, codexPlan }.
// Each is a menu spec { id, title, items:[{value,label,note}], initial, multi? } plus step/of/trail
// for the stepper line. After the runtimes step the caller asks again with the picked runtimes.
function steps(detected) {
  const { claude, codex, plan, codexPlan } = detected;
  const list = [{ id: 'runtimes', title: 'runtimes', multi: true, initial: 0,
    items: items([['claude', 'Claude Code: agents, hooks, skills, settings'], ['codex', 'Codex: agents, hooks, config.toml']],
      [claude && 'claude', codex && 'codex'].filter(Boolean)) }];
  if (claude) list.push({ id: 'plan', title: 'plan', initial: initial(CLAUDE_PLANS, plan), items: items(CLAUDE_PLANS) });
  if (claude && FABLE_PLANS.includes(plan)) {
    list.push({ id: 'fable', title: 'fable', initial: 0,
      items: items([['yes', 'Fable 5.1 pinned on architect, the runtime gate on'], ['no', 'no Fable anywhere in this install']]) });
  }
  list.push({ id: 'context', title: 'context', initial: 0, items: items([['default', "each runtime's own context window and compaction"],
    ['economy', "the plan's autoCompactWindow; a prompt past 120% is held back"]]) });
  if (claude) {
    list.push({ id: 'statusline', title: 'statusline', initial: 0, items: items([
      ['riskrails', "the plugin's statusline over your own command (kept, --statusline own brings it back)"],
      ['own', 'your own statusline command, behind the quota check']]) });
  }
  if (codex) list.push({ id: 'codex plan', title: 'codex plan', initial: initial(CODEX_PLANS, codexPlan), items: items(CODEX_PLANS) });
  list.push({ id: 'review', title: 'review', initial: 0, items: items([['install', 'write the files now'],
    ['back', 'change an answer'], ['cancel', 'exit; nothing is written']]) });
  const trail = list.map((s) => s.id);
  return list.map((s, i) => ({ ...s, step: i + 1, of: list.length, trail }));
}

// The flags that repeat the choices: { target, plan, fable, statusline, codexPlan, context, version }.
// A choice left undefined is not passed. Returns { argv, text }; text is argv as one line.
function flags(choices) {
  const { target, plan, fable, statusline, codexPlan, context, version } = choices;
  const claude = target !== 'codex', codex = target !== 'claude';
  const argv = ['npx', `riskrails@${version}`, '--target', target];
  if (claude && plan) argv.push('--plan', plan);
  if (claude && fable) argv.push('--fable', fable);
  if (claude && statusline) argv.push('--statusline', statusline);
  if (codex && codexPlan) argv.push('--codex-plan', codexPlan);
  argv.push('--context', context || 'default', '--yes');
  return { argv, text: argv.join(' ') };
}

// The review screen's lines, above the Install / Back / Cancel menu.
function reviewLines(dryRunText, command) {
  return ['Review — nothing is written until you pick Install', '', ...dryRunText.replace(/\n+$/, '').split('\n'), '',
    `same as: ${command}`];
}

// The final box: result = { command, next }; next defaults to the setup of a project.
function finalBox(result) {
  const body = ['riskrails is installed', `next: ${result.next || '/rr-setup in a project, to survey it and build .ai/'}`,
    `same as: ${result.command}`];
  const width = Math.max(...body.map((l) => [...l].length));
  const bar = '─'.repeat(width + 2);
  return [`┌${bar}┐`, ...body.map((l) => `│ ${l}${' '.repeat(width - [...l].length)} │`), `└${bar}┘`];
}

module.exports = { steps, flags, reviewLines, finalBox };
