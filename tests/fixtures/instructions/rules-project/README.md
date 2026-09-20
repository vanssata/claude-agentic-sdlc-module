# rules-project

The `.ai/rules/` overlay `test-instruction-budget.sh` and `test-project-update.sh`
render: two rules, one of them path-scoped, and one directory shared by both so
a file that carries two blocks is exercised.

Only `.ai/rules/` is kept here. The project around it is scaffolded by the test,
so the fixture never has to be kept in step with a template it does not own.

Copy it over a scaffolded project with `cp -r rules-project/.ai <project>/`.
