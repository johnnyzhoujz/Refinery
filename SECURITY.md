# Security Policy

## Reporting a vulnerability
- Email: security@refinery.ai
- Or open a private security advisory via GitHub

Please avoid filing public issues for security reports.

## Data handling

### Trace data
- Held in memory during analysis only
- Never persisted unless you pass `--out`
- Redacted from logs by default
- Sent to your chosen LLM provider via your API key

### API keys
- Read from environment variables (`OPENAI_API_KEY`, `LANGSMITH_API_KEY`, etc.)
- Never written to disk or logs
- Excluded from error messages
- Sent to your chosen LLM provider (OpenAI currently, more providers coming)

### Local storage
- Config: `~/.refinery/config` (no secrets).
- Cache: `~/.refinery/cache/` (TTL 15 minutes, metadata only).
- Purge: `rm -rf ~/.refinery/`.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | ✅ |
| < 0.1.0 | ❌ |

## Best practices

1. Inspect exported traces before analysis (`jq`, internal tooling).
2. Rotate API keys regularly.
3. Store credentials in environment managers, not code.
4. Export only the traces you need for debugging.
