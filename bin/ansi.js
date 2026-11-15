// The installer's colour gate and the few styles the menu uses. Pure: the stream's isTTY and the
// environment come in as parameters. Colour goes to stderr only (spec ui-first-approvals R14).
'use strict';

// Colour only on a terminal, with NO_COLOR empty or unset and TERM not dumb.
const useColor = (isTTY, env) => isTTY === true && !env.NO_COLOR && env.TERM !== 'dumb';

const CODES = { bold: '1', dim: '2', inverse: '7' };
// text in the style when on is true, else unchanged.
const paint = (on, style, text) => (on ? `\x1b[${CODES[style]}m${text}\x1b[0m` : text);

module.exports = { useColor, paint };
