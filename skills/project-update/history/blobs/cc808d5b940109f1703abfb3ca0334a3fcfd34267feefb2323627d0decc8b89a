# Security policy

A security review is mandatory for T4 and T5, and is requested for any change
that touches authentication, authorization or personal data.

## Review checklist

- **Authentication** — who can reach this, and how is that established?
- **Authorization** — is the check on the server, on every path, including the
  API and the message consumer? Is the negative case tested?
- **Secrets** — nothing hardcoded, nothing logged, nothing in a fixture.
- **Personal data** — what is stored, where does it flow, what is logged?
- **Payment and financial data** — card data must not be stored or logged at all.
- **Webhooks** — signature verified, timestamp checked, replay rejected.
- **Input validation** — every external input, including message payloads and
  webhook bodies, is validated before use.
- **Injection** — SQL, LDAP, template, command. Parameterised queries only.
- **SSRF** — any URL that comes from user input, including a redirect target.
- **IDOR** — an identifier taken from the request that selects someone's record.
- **Deserialization** — never unserialize untrusted input.
- **File access** — path traversal, upload type and size, where uploads are served from.
- **Command execution** — argument escaping, or better, no shell at all.
- **Dependencies** — a new dependency is a decision; state why it is needed.
- **Data exposure** — API responses, error messages, debug output.
- **Audit logging** — who did what to which record, for anything money-related.

## Findings

Every finding has a severity and a location:

| Severity | Meaning |
|---|---|
| **BLOCKER** | do not merge |
| **HIGH** | fix before release |
| **MEDIUM** | fix soon, ticket it |
| **LOW** | worth improving |
| **INFO** | observation, no action needed |

## AI context safety

Production data must not be sent to a model unnecessarily. `ai-path-guard`
enforces a deny list mechanically; it is defence-in-depth against an ordinary
mistake, not a security boundary.

Denied by default: `.env` and its environment-specific variants, `secrets/`,
`credentials/`, `.ssh/`, private keys and certificates, cloud credential files,
database dumps and customer exports, production logs.

Allowed: `.env.example` and its siblings, fixtures, migrations.

Project-specific additions go in `.ai/policies/path-guard.json`. When a deny is
wrong, widen the allow list in that file — do not work around the guard.
