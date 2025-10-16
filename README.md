# Refinery

[![CI](https://github.com/johnnyzhoujz/Refinery/actions/workflows/ci.yml/badge.svg)](https://github.com/johnnyzhoujz/Refinery/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> AI-powered trace analysis and prompt fixes for LangSmith

Refinery analyzes LangSmith agent traces to find root causes of failures and generates AI-powered prompt edits to fix them. Built on GPT-5 for teams who want faster iteration on AI agent failures.

## Quick Start (2 Minutes - No LangSmith Required)

Get started with a local trace file - no LangSmith API access needed:

### 1. Install

```bash
pip install refinery-cli
```

### 2. Set OpenAI Key

```bash
export OPENAI_API_KEY=sk-...
```

### 3. Analyze a Local Trace

```bash
refinery chat --trace-file examples/demo_trace.json --out hypothesis.yaml
```

That's it! Refinery will analyze the trace and export a structured Hypothesis Pack with:
- Root cause diagnosis with evidence
- Ranked hypotheses with confidence scores
- Proposed code/prompt changes with diffs
- Reproducibility metadata

## Alternative: Fetch from LangSmith

If you have LangSmith API access, you can fetch and analyze traces directly:

```bash
# Set both API keys
export LANGSMITH_API_KEY=ls-...
export OPENAI_API_KEY=sk-...

# Fetch and analyze a trace
refinery chat --trace-id abc123 --project my-project --out hypothesis.yaml
```

## What You Need

Decision tree for getting started:

**Do you have a LangSmith trace to analyze?**
- **Yes, I have a trace JSON file** → Use `--trace-file` (only OpenAI key required)
- **Yes, I know the trace ID** → Use `--trace-id` (LangSmith + OpenAI keys required)
- **No, I want to try the demo** → Use the included `examples/demo_trace.json`

**Do you have the required API keys?**
- **OpenAI API key with GPT-5 access** (required for all workflows)
- **LangSmith API key** (optional, only needed for `--trace-id` workflow)

Get keys:
- OpenAI: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (GPT-5 access required)
- LangSmith: [smith.langchain.com/settings](https://smith.langchain.com/settings) (optional)

## Prerequisites

**Required:**
- Python 3.8+
- OpenAI account with GPT-5 access ([request access](https://openai.com/))

**Optional (for live trace fetching):**
- LangSmith account with API key ([get one here](https://smith.langchain.com/))

## Installation

### From PyPI (Recommended)

```bash
pip install refinery-cli
```

### From Source (Development)

```bash
git clone https://github.com/your-org/refinery.git
cd refinery
pip install -e .
```

## Usage Examples

### Analyze Local Trace File

```bash
# Basic analysis
refinery chat --trace-file examples/demo_trace.json

# Export hypothesis pack
refinery chat --trace-file trace.json --out hypothesis.yaml

# Export as JSON instead of YAML
refinery chat --trace-file trace.json --out hypothesis.json --format json
```

### Fetch from LangSmith API

```bash
# Analyze a specific trace
refinery chat --trace-id abc123 --project my-project

# With hypothesis pack export
refinery chat --trace-id abc123 --project my-project --out hypothesis.yaml
```

### Using the Analyze Alias

```bash
# 'analyze' is an alias for 'chat'
refinery analyze --trace-file trace.json --out hypothesis.yaml
```

### Web UI Mode

```bash
refinery ui
```

This launches a Streamlit web interface at `http://localhost:8501` with:
- Trace ID input and project selection
- Real-time analysis progress
- Visual trace timeline
- Interactive hypothesis comparison
- Side-by-side diff viewer for proposed changes

### With Debug Output

```bash
refinery --debug chat --trace-file trace.json
# Shows detailed logs and intermediate steps
```

### Check Version

```bash
$ refinery --version
Refinery v0.1.0 (GPT-5, Python 3.11)
```

### Help

```bash
$ refinery --help
Usage: refinery [OPTIONS] COMMAND [ARGS]...

  Refinery - AI-powered prompt analysis for LangSmith traces.

Options:
  --debug / --no-debug  Enable debug mode
  --version             Show version and exit
  --help                Show this message and exit

Commands:
  analyze  Alias for 'chat' - analyze AI agent failures
  chat     Interactive chat mode for analyzing AI agent failures
  ui       Launch Streamlit UI
```

## What Refinery Analyzes

Refinery performs a 4-stage analysis of your LangSmith traces:

1. **Timeline Extraction**: Parses trace into chronological events
2. **Gap Analysis**: Identifies where expectations diverged from reality
3. **Root Cause Diagnosis**: Determines why the failure occurred
4. **Hypothesis Generation**: Proposes specific prompt edits to fix the issue

## Why Refinery?

### The Problem

AgentKit and LangGraph help you **observe what happened** - traces, metrics, dashboards.
But when your agent fails, you still need to manually:
- Guess why it failed
- Hypothesize fixes
- Test changes without knowing confidence
- Iterate without reproducibility

### Refinery's Approach: Provability, Not Just Observability

**AgentKit tells you:** "Your agent failed at step 3"

**Refinery tells you:** "It failed because [root cause] with 87% confidence. Here are 3 ranked hypotheses with diffs and risk assessments. Reproduce with seed 12345."

### Works With Your Traces

Refinery is model-agnostic infrastructure:
- Fetch traces from LangSmith API OR analyze exported JSON files
- No vendor lock-in: works with any LangSmith project
- Launches with OpenAI (GPT-4o, GPT-5) support
- Anthropic Claude planned (see roadmap)

**AgentKit** = OpenAI ecosystem
**Refinery** = Independent provability layer

### What You Get

1. **Scientific Diagnosis:** Root cause analysis with evidence and confidence scores
2. **Experiment-Ready Hypotheses:** Ranked fixes with diffs, not just suggestions
3. **Reproducibility:** Deterministic analysis with seeds and version control
4. **Stable Interchange Format:** Hypothesis Pack schema for downstream tools
5. **Future:** Statistical rigor (power analysis, sequential testing) in Refinery Cloud

**Think of it as:**
- AgentKit = Your observability layer
- Refinery = Your provability layer
- Refinery Cloud = Your experiment governance layer

## Output Structure

### Diagnosis

Every analysis produces a structured diagnosis:

- **Failure Type**: Logic error, prompt issue, data quality, etc.
- **Root Cause**: Specific issue identified
- **Confidence**: Low, medium, or high
- **Affected Components**: Which prompts/code need changes
- **Evidence**: Trace data supporting the diagnosis
- **Recommended Fixes**: Prioritized list of actions

### Hypotheses (Chat Mode)

When you generate hypotheses, you get:

- **Description**: What the fix does
- **Rationale**: Why this should work
- **Proposed Changes**: Specific file edits
- **Risks**: Potential side effects
- **Confidence**: How likely this is to work

## Troubleshooting

### "LangSmith API key invalid"

**Problem**: Cannot authenticate with LangSmith

**Solutions**:
1. Verify your API key at https://smith.langchain.com/settings
2. Check that `LANGSMITH_API_KEY` is set correctly in your environment
3. Ensure no extra spaces or quotes around the key
4. Verify your LangSmith project name exists

### "OpenAI API key invalid"

**Problem**: Cannot authenticate with OpenAI

**Solutions**:
1. Verify your API key at https://platform.openai.com/api-keys
2. Check that `OPENAI_API_KEY` is set correctly in your environment
3. **GPT-5 Access Required**: Confirm you have GPT-5 API access enabled
4. Check OpenAI service status: https://status.openai.com/

### "Trace not found"

**Problem**: Cannot locate the specified trace ID

**Solutions**:
1. Verify the trace ID is correct (copy from LangSmith URL)
2. Check that the project name matches exactly (case-sensitive)
3. Ensure you have access to the project in LangSmith
4. Confirm the trace exists: https://smith.langchain.com/

### "Must provide either --trace-id or --trace-file"

**Problem**: No trace source specified

**Solutions**:
1. Provide a local trace file: `refinery chat --trace-file trace.json`
2. Or provide a trace ID: `refinery chat --trace-id abc123 --project my-project`
3. Cannot provide both at the same time - choose one workflow

### "Rate limit exceeded"

**Problem**: Too many OpenAI API requests

**Solutions**:
1. Wait a few minutes before retrying
2. Check your OpenAI quota: https://platform.openai.com/usage
3. For large traces, GPT-5 may hit tokens-per-minute (TPM) limits
4. Refinery automatically retries with exponential backoff
5. Use `--debug` flag to see rate limit details

### "Module not found" or Import Errors

**Problem**: Python dependencies not installed

**Solutions**:
1. Reinstall dependencies: `pip install refinery-cli`
2. Use a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install refinery-cli
   ```
3. Verify Python version: `python --version` (needs 3.8+)

### Streamlit UI Won't Launch

**Problem**: `refinery ui` fails or shows errors

**Solutions**:
1. Verify Streamlit is installed: `pip install streamlit`
2. Check for port conflicts (default is 8501)
3. Try manual launch: `streamlit run refinery/ui/app.py`
4. Clear Streamlit cache: `streamlit cache clear`

### Analysis Takes Too Long

**Problem**: Trace analysis is slow or times out

**Solutions**:
1. Large traces (>100 runs) may take 5-10 minutes
2. Use `--debug` to see progress details
3. GPT-5 has higher latency than GPT-4 (this is normal)
4. Check your internet connection
5. Verify OpenAI API is not experiencing issues

## Limitations

- **GPT-5 Only**: Refinery currently requires GPT-5. Other models are not supported in v0.1
- **LangSmith Native**: Works with LangSmith traces. OpenTelemetry support may come in future releases
- **English Only**: Analysis works best with English prompts and traces

## License

**Refinery CLI tool** is MIT licensed open source software.

Future **Refinery Cloud** (statistical rigor layer for experiment governance) will be proprietary.

See [LICENSE](LICENSE) file for full details.

## Future Compatibility

Refinery is built for LangSmith, where most teams already have observability infrastructure. We're monitoring the emergence of **OpenTelemetry** as the 2025 standard for AI observability and may add support based on user demand.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/refinery/issues)
- **Questions**: Open a discussion or issue on GitHub
- **Bugs**: Please include trace ID (if shareable) and full error output

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

---

**Built with GPT-5** | [Documentation](https://github.com/your-org/refinery) | [Report Issues](https://github.com/your-org/refinery/issues)
