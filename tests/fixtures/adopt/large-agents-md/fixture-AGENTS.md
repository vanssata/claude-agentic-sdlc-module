## Project notes

This service takes orders and payments for the shop backend.
Run `make test` before every push; CI runs the same target.

## Conventions

- PHP 8.3, strict_types in every file.
- One class per file; the file name is the class name.
- Services are final and injected through the constructor.
- No static calls into the container.
- Money is an integer number of cents, never a float.
- Dates are stored in UTC and converted only in templates.
- Every public method of a service has a test.
- Use the repository classes; no raw SQL outside src/Repository.
- Log with the channel of the module, never the default channel.
- Feature flags live in config/flags.yaml and are read through FlagReader.

## Payments

- Every change under src/Payment needs a test with a declined card.
- Amounts are validated before the gateway is called, never after.
- The gateway client is the only class that talks to the provider.
- Retries are idempotent: the idempotency key is the order id plus the attempt.
- Webhooks are verified by signature before the payload is read.
- Refunds go through RefundService, never through the gateway directly.
- A payment state changes only through PaymentStateMachine.
- Card data never reaches our logs; mask it in the formatter.
- Currency is taken from the order, never from the request.
- The sandbox key is used in tests; the live key only in production.

## Architecture

The HTTP layer is in src/Controller and only maps requests to commands.
Commands are handled in src/Handler; each handler owns one transaction.
Domain objects live in src/Domain and have no framework imports.
Integrations with other systems are in src/Integration, one directory each.
Background jobs are Messenger messages under src/Message.
Read models are built by projectors in src/Projection.
The admin panel is a separate bundle under src/Admin.
Configuration is environment-driven; see .env.dist for the keys.

## Reminders

- Production behaviour is the source of truth; do not fix what is outside the task.
- Verify before reporting done and show the output.
- No agent commits, merges or deploys.
