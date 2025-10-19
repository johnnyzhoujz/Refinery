# Example Traces

Use these traces to try Refinery without LangSmith API access.

## demo_trace.json

- **Source:** Sanitized production trace used during Refinery internal testing.
- **Purpose:** Demonstrates a reproducible agent failure pattern (timeout on step 3).

### Sanitization process
1. Removed emails, names, and IDs via regex
2. Replaced all keys with `sk-xxx...`
3. Generalized domain-specific details while preserving failure semantics
4. Validated structure (supports multiple trace formats)

### Verification commands

```bash
# Emails
grep -E '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b' demo_trace.json

# API keys
grep -E 'sk-[a-zA-Z0-9]{32,}' demo_trace.json

# PII keywords
grep -iE '(ssn|social.security|credit.card|password)' demo_trace.json
```

### Quick run

```bash
refinery chat --trace-file examples/demo_trace.json --out hypothesis.yaml
```

Expect a hypothesis pack with one critical finding and a ranked fix in ~2–3 minutes.
