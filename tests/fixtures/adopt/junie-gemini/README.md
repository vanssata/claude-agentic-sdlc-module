# Junie + Gemini CLI fixture

Source: https://junie.jetbrains.com/docs , https://github.com/JetBrains/junie-guidelines , https://geminicli.com/docs/cli/gemini-md
Checked: 2026-09-22

`.junie/guidelines.md` and `GEMINI.md` at the root, both small and **without** the managed block,
so both are foreign (plan step 4, rule a) and neither is a split candidate: no `split?` line.
A `GEMINI.md` or `.junie/guidelines.md` the plugin scaffolded carries the block and is not
detected at all (rule b); the test proves that with a fresh gemini and junie scaffold.

Corrections to spec I2: none.
