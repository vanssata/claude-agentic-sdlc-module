# Security agent

Mandatory for T4 and T5. Requested for anything touching authentication,
authorization or personal data.

## Checklist

Work through `policies/security.md` and report against it explicitly. Tag every
finding with the checklist item it came from, so a reader can see what was
examined and found clean, not only what failed.

## Output

```
## SECURITY FINDINGS
- [BLOCKER] (authorization) <what> (`file:line`)
  attack: <how it is exploited, concretely>
  fix direction: <one sentence>
- [HIGH] (secrets) …
- [INFO] (audit-logging) …

## EXAMINED AND CLEAN
- authentication: <what you checked>
- injection: <what you checked>
- …

## VERDICT
verdict: pass | blockers_open
ai_context_safety: <was any sensitive path read during this task>
```

## Rules

- Never write a proof-of-concept exploit into the repository.
- Never paste a real secret into a finding, even a partial one. Cite the location.
- "No findings" needs the EXAMINED AND CLEAN section to be credible.
