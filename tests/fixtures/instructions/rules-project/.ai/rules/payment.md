---
dirs: [src/Payment, tests/Payment]      # required: where the rules apply
paths: ["src/Payment/**"]               # optional: also a path-scoped rules file
---
# Payment rules
- Amounts are integer minor units; never a float.
- A refund never writes to the order; it emits an event.
