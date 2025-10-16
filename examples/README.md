# Example Traces

This directory contains example LangSmith traces for testing and demonstrating Refinery's analysis capabilities.

## demo_trace.json

**Source**: Real production customer support agent trace
**Purpose**: Demonstrates clear failure pattern for testing Refinery's analysis pipeline

### Trace Details

- **Size**: 5 runs (chain with 4 child operations)
- **Failure type**: Intent classification error leading to inadequate response
- **Use case**: End-to-end testing of `--trace-file` workflow

**Failure pattern demonstrated:**
1. Customer submits billing/subscription query: "I need to cancel my subscription and get a refund for the last month"
2. Intent classifier misclassifies as "general_inquiry" (should be "billing_inquiry")
3. Knowledge base retrieval returns irrelevant general FAQ documents
4. Response generator produces generic response instead of billing-specific help
5. Validation step marks response as inadequate

This trace demonstrates how Refinery can:
- Identify the root cause (missing billing intent in classifier)
- Provide evidence from the trace (classification confidence 0.65, wrong intent)
- Generate actionable hypotheses (add billing intent with few-shot examples)
- Propose specific changes (prompt modifications with diffs)

### Sanitization Process

All PII and sensitive data removed before inclusion:

1. **Removed all PII**
   - Emails replaced with generic placeholders (`billing@example.com`)
   - Customer names replaced with `cust_demo_123`
   - User IDs anonymized

2. **Replaced API keys**
   - All keys replaced with `sk-xxx...` or `ls-xxx...` patterns
   - No real credentials included

3. **Generalized business logic**
   - Specific domain details abstracted to generic customer support scenario
   - Company-specific terminology replaced with industry-standard terms

4. **Preserved failure patterns**
   - Trace structure intact (run hierarchy, timing, error states)
   - Failure mechanics preserved (wrong classification, inadequate retrieval)
   - Analysis-relevant content maintained

### Verification Commands

Run these to verify no sensitive data leaked:

```bash
# Check for emails (should return no matches)
grep -E '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b' examples/demo_trace.json

# Check for API keys - OpenAI format (should return no matches)
grep -E 'sk-[a-zA-Z0-9]{32,}' examples/demo_trace.json

# Check for API keys - LangSmith format (should return no matches)
grep -E 'ls-[a-zA-Z0-9]{32,}' examples/demo_trace.json
```

**Expected output**: No matches found for all three commands

If any matches are found, the trace may contain unsanitized data. Please report this as a security issue.

## Usage Examples

### Basic Analysis

Analyze the demo trace with default settings:

```bash
refinery chat --trace-file examples/demo_trace.json
```

### Export Hypothesis Pack

Analyze and export results to a file:

```bash
# Export as YAML (default)
refinery chat --trace-file examples/demo_trace.json --out hypothesis.yaml

# Export as JSON
refinery chat --trace-file examples/demo_trace.json --out hypothesis.json --format json
```

### Debug Mode

See detailed analysis steps:

```bash
refinery --debug chat --trace-file examples/demo_trace.json
```

### With Custom Codebase Path

If you have the agent codebase and want context-aware analysis:

```bash
refinery chat --trace-file examples/demo_trace.json --codebase /path/to/agent/code
```

## Expected Analysis Output

When you analyze `demo_trace.json`, Refinery should identify:

**Root Cause**: Intent classifier lacks billing/subscription category

**Evidence**:
- User query contains clear billing keywords: "cancel", "subscription", "refund"
- Classifier output: "general_inquiry" with confidence 0.65 (below threshold 0.80)
- Expected classification: "billing_inquiry" or "account_issue"

**Hypotheses** (example):
1. Add billing_inquiry intent category with few-shot examples to classifier prompt
2. Add billing policy documents to knowledge base
3. Update orchestration to route billing queries to specialized handler

Each hypothesis should include:
- Confidence level (high/medium/low)
- Risk assessment
- Proposed changes with file paths and diffs
- Example before/after behavior

## Contributing Examples

If you want to contribute additional example traces:

1. **Sanitize thoroughly**: Remove ALL PII, API keys, and sensitive business logic
2. **Verify sanitization**: Run the verification commands above
3. **Document the failure pattern**: Explain what went wrong and what Refinery should detect
4. **Update this README**: Add documentation for your example trace
5. **Test the analysis**: Verify Refinery correctly identifies the issue

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details.

## Trace Format

All traces in this directory follow the LangSmith trace format:

```json
{
  "trace_id": "unique-trace-id",
  "session_id": "project-name",
  "project_name": "project-name",
  "runs": [
    {
      "id": "run-id",
      "name": "ComponentName",
      "run_type": "chain|llm|retriever|tool",
      "inputs": { ... },
      "outputs": { ... },
      "start_time": "ISO-8601 timestamp",
      "end_time": "ISO-8601 timestamp",
      "error": "error message or null",
      "parent_run_id": "parent-id or null",
      "trace_id": "trace-id",
      "dotted_order": "1.2.3",
      "session_id": "project-name"
    }
  ]
}
```

For full LangSmith trace schema documentation, see: https://docs.smith.langchain.com/

## Security Note

These example traces are sanitized and safe to share publicly. However:

- **Do NOT commit** your own production traces to version control
- **Always sanitize** traces before sharing them
- **Use `--trace-file`** workflow for maximum control over sensitive data
- See [SECURITY.md](../SECURITY.md) for data handling best practices

## Questions?

If you have questions about the example traces:
- Open a GitHub issue
- See the main [README.md](../README.md) for usage documentation
- Check [SECURITY.md](../SECURITY.md) for data privacy guidance
