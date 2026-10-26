# Fixtures for `skills/rr-setup/setup.py`

`new-shop-like/` is a project carrying its own toolbox the way new-shop does: `.claude/{skills,rules,agents,hooks,commands}`,
`bin/*.sh`, a `Makefile` and `composer.json`. It is stored encoded exactly like `tests/fixtures/adopt/`
(`dot-<name>` → `.<name>`, `fixture-CLAUDE.md` → `CLAUDE.md`; `README.md` and `fixture.json` are not copied),
so the path guard and the runtimes never see a real `.claude/` or `CLAUDE.md` here.

Source: the shape of new-shop's toolbox (directory kinds and file kinds only, no content), 2026-10-26.
