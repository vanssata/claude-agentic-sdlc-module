# Large CLAUDE.md fixture

Source: this plugin's own scaffold (`hooks/project-scaffold.sh`, `skills/ai-init/scaffold-ai.sh --runtime claude`) and `instructions/runtimes.json` `_budgets.skeleton` (2048 B).
Checked: 2026-09-22

`fixture-CLAUDE.md` (47 lines, 2121 B of project notes) is appended to the scaffolded CLAUDE.md, which
already carries the managed block, so the whole file is well over the budget: a split candidate
(`split?`). `split-proposal.fixture.json` is the canned proposal (R19), relative to the appended
lines (see ../README.md). It moves the notes to `.ai/project/overview.md`,
`.ai/policies/adopted/conventions.md` (heading taken verbatim from the outline) and
`.ai/rules/payment.md` (`dirs: src/Payment`, which exists here), and drops the five lines that
repeat the managed block. `large-claude-md` and `large-agents-md` carry the same notes and the
same proposal, so R19's parity check compares their destination sets.

Deviation from the plan text: the canned proposal is `split-proposal.fixture.json`, not
`split-proposal.json`, because it is not an I5 document until the test shifts it and adds the sha.
