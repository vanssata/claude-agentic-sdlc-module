# Verification — this project's commands
<!-- Yours. Read by state.py verify and close, setup.py check, update.py hints; /rr-setup --update never rewrites it.
     Each line is `field: value`; a line left empty reads as "not written down yet", `none` says the project has none.
     What each command must do is in policies/testing.md (Verification). -->

verify_command:      # the full fast suite, e2e excluded, no fail-fast — e.g. make test | composer qa && vendor/bin/phpunit --exclude-group e2e
step_test_command:   # the same runner scoped to a path or filter, `{files}` replaced by the step's paths — e.g. vendor/bin/phpunit {files} | pytest {files}
e2e_command:         # the end-to-end suite, run once at the end of a task — e.g. make e2e | vendor/bin/behat | npx playwright test — `none` if the project has none
lint_command:        # e.g. vendor/bin/php-cs-fixer fix --dry-run | ruff check . | npm run lint — `none` if the project has none
typecheck_command:   # e.g. vendor/bin/phpstan analyse --no-progress | mypy . | npx tsc --noEmit — `none` if the project has none
single_test:         # how to run one test, for the failing-test-first step of a bugfix
doc_tests:           # the suites a documents-only edit runs after a green suite — e.g. tests/test_docs.py; `none` if the project has none
bite_codes:          # exit codes that mean "a test failed" (default 1) — e.g. 1,2 for pytest and phpunit, 101 for cargo
healthy_output:      # two or three lines of what a green run ends with

## Project specifics

<!-- How to run unit tests, integration tests, a single test. Where fixtures live. What the CI runs. Cite the config. -->
