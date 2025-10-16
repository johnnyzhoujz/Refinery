# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Refinery, please report it responsibly:

**Email**: security@refinery.ai

Alternatively, you can create a private security advisory on GitHub:
- Go to the Security tab in the repository
- Click "Report a vulnerability"
- Provide details about the issue

We take all security reports seriously and will respond within 48 hours.

## Data Handling

### Trace Data

Refinery handles trace data with the following security measures:

- **In-Memory Only**: Trace data is stored only in memory during analysis
- **No Automatic Persistence**: Data is NOT persisted to disk without your explicit `--out` flag
- **Log Redaction**: Trace contents are redacted from logs by default
- **Temporary Processing**: All trace data is cleared from memory after analysis completes

**Example of secure usage:**
```bash
# Trace data stays in memory only
refinery chat --trace-file trace.json

# Trace data is exported only when you specify --out
refinery chat --trace-file trace.json --out hypothesis.yaml
```

### API Keys

API keys are handled securely:

- **Environment Variables Only**: Keys are read from environment variables (`OPENAI_API_KEY`, `LANGSMITH_API_KEY`)
- **Never Logged**: API keys are never written to log files or console output
- **Not Included in Error Reports**: Error messages never contain API key values
- **No Disk Storage**: Keys are not persisted to configuration files

**Safe key management:**
```bash
# Set keys in environment (preferred)
export OPENAI_API_KEY=sk-...
export LANGSMITH_API_KEY=ls-...

# Keys are never logged or displayed
refinery chat --trace-file trace.json
```

### Local Storage

Refinery may create local cache and configuration directories:

**Configuration**: `~/.refinery/config`
- Stores non-sensitive settings (model preferences, formatting options)
- Does NOT store API keys or credentials

**Cache**: `~/.refinery/cache/`
- Time-to-live (TTL): 15 minutes
- Contains analysis intermediate results (for performance optimization)
- Automatically cleared after TTL expires

**To purge all local storage:**
```bash
rm -rf ~/.refinery/
```

### Network Communications

- **HTTPS Only**: All API communications use HTTPS encryption
- **No Third-Party Analytics**: Refinery does not send usage data to third-party services
- **Direct Provider Communication**: Talks directly to OpenAI and LangSmith APIs
- **No Proxies**: Does not route traffic through intermediary servers

## Data Privacy Best Practices

When using Refinery with production traces:

### 1. Sanitize Traces Before Sharing

If you need to share traces for debugging:

```bash
# Export trace from LangSmith
langsmith export trace-id > trace.json

# Review and sanitize before sharing
# Remove: emails, names, API keys, customer IDs, sensitive business logic
cat trace.json | jq '.runs[].inputs' | grep -E "email|api|key"

# Share sanitized version
```

### 2. Use Local File Workflow for Sensitive Data

For maximum control over data flow:

```bash
# Download trace locally
langsmith export trace-id > trace.json

# Review contents
cat trace.json | less

# Analyze locally (OpenAI API only sees what's in the file)
refinery chat --trace-file trace.json
```

### 3. Avoid Committing Traces to Version Control

Add to your `.gitignore`:
```
# Trace files
*.trace.json
*_trace.json
examples/demo_trace.json  # Except sanitized examples
```

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

Older versions may not receive security patches. Please upgrade to the latest version.

## Security Audit Status

- **Last Audit**: Not yet audited (v0.1.0 initial release)
- **Planned Audit**: Q1 2026 for v0.2.0 release

## Responsible Disclosure

We follow responsible disclosure principles:

1. **Private Reporting**: Report vulnerabilities privately first
2. **48-Hour Response**: We respond within 48 hours
3. **Fix Timeline**: We aim to fix critical issues within 7 days
4. **Public Disclosure**: We coordinate public disclosure with the reporter
5. **Credit**: We credit security researchers (unless they prefer anonymity)

## Security Features Roadmap

Planned security enhancements:

- [ ] **Trace PII Detection**: Automatic detection and warning for PII in traces
- [ ] **Key Rotation Support**: Easy API key rotation without service interruption
- [ ] **Audit Logging**: Optional audit log for all API calls made by Refinery
- [ ] **SOC 2 Compliance**: For Refinery Cloud (future proprietary service)

## Questions?

If you have questions about Refinery's security practices:

- Open a GitHub issue (for non-sensitive questions)
- Email security@refinery.ai (for sensitive inquiries)

Thank you for helping keep Refinery and its users secure!
