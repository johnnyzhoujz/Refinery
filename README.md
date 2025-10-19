# Refinery
> Open source error analysis for AI agents – analyze failures, generate ranked fix hypotheses, and improve agent reliability through disciplined iteration.

Andrew Ng observed that "the single biggest predictor of how rapidly a team makes progress building an AI agent lay in their ability to drive a disciplined process for evals and error analysis." Yet most teams shortcut this process, attempting quick fixes rather than identifying root causes. Refinery makes rigorous error analysis practical: bring any trace from any agent system, and get a structured Hypothesis Pack with evidence, ranked fixes, confidence scores, and reproducibility metadata.

[![CI](https://github.com/johnnyzhoujz/Refinery/actions/workflows/ci.yml/badge.svg)](https://github.com/johnnyzhoujz/Refinery/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick Start

### 1. Analyze a local trace (no integrations needed)

```bash
pip install refinery-cli
export OPENAI_API_KEY=sk-your-key

# Basic analysis
refinery chat --trace-file examples/demo_trace.json --out hypothesis.yaml

# With prompts and evals
refinery chat \
  --trace-file trace.json \
  --prompts './prompts/*.txt' \
  --evals './tests/*.py' \
  --expected-behavior "Agent should call tools before answering" \
  --out hypothesis.yaml
```

Supported trace formats:
- OpenTelemetry GenAI conventions
- Langfuse observations
- LangSmith exports
- Custom JSON (auto-detected)

### 2. Fetch live traces via LangSmith integration (optional)

```bash
export OPENAI_API_KEY=sk-your-key
export LANGSMITH_API_KEY=ls-your-key

refinery chat --trace-id abc123 --project my-project --out hypothesis.yaml
```

You'll receive a validated Hypothesis Pack containing findings, ranked hypotheses with diffs, confidence scores, and reproducibility metadata.

---

## Why Refinery?

### The Problem: Reliable AI agents require disciplined error analysis

Building reliable AI agents isn't just about stacking the latest techniques. As Andrew Ng puts it: "To improve your agentic AI system, don't just stack up the latest buzzy techniques that just went viral on social media. Instead, use error analysis to figure out where it's falling short, and focus on that."

The challenge: error analysis is time-consuming, and existing tools lock you into specific platforms.

### Refinery's Solution: Open source, platform-agnostic error analysis

**AgentKit** does error analysis but only works if you use their agent framework.

**Refinery** is open source and works with ANY agent system:
- ✅ Not locked to any agent framework
- ✅ Not locked to any LLM provider (OpenAI today, Claude/Gemini coming)
- ✅ Not locked to any observability platform (LangSmith, Langfuse, OpenTelemetry, custom)
- ✅ Bring your own traces, prompts, and evals

**What Refinery does today (open source):**
Analyzes failures and generates ranked hypotheses for potential fixes with confidence scores and evidence.

**What Refinery will do in the future (not open source):**
Provide an experiment lab environment to validate whether proposed fixes actually improve your agent system.

---

## What you get

1. **Evidence-backed findings** – Canonicalized failure patterns with root cause analysis
2. **Ranked fix hypotheses** – Proposed changes with diffs, confidence scores, and risk assessment
3. **Before/after examples** – Concrete demonstrations of current vs expected behavior
4. **Reproducibility metadata** – Model params, seeds, and methodology for validation
5. **Portable Hypothesis Pack** – Schema-validated YAML/JSON interchange format

---

## Feature Highlights

**Multi-source trace analysis:**
- Local files: OpenTelemetry, Langfuse, LangSmith exports, custom JSON
- LangSmith API: Live trace fetching with --trace-id (optional)
- Auto-detection of trace format (generic vs LangSmith)

**Flexible input:**
- Bring your own prompts: --prompts flag with glob patterns
- Bring your own evals: --evals flag for test files
- Custom requirements: --expected-behavior for specific validation criteria

**Recent additions (v0.1.0):**
- Generic trace format support with raw JSON passthrough
- Schema validation fixes (maxLength constraints)
- Example field display in CLI and Streamlit UI
- File loading utilities for local prompt/eval analysis

**Developer experience:**
- Structured exports: --out PATH --format yaml|json
- CLI alias: `refinery analyze` mirrors `refinery chat`
- Mocked providers for testing – pytest runs without API keys
- Minimal CI pipeline (ruff, black, pytest) runs without secrets
- Hypothesis Pack schema validation (Pydantic)

---

## Usage

```bash
# Analyze local trace with prompts and evals
refinery chat \
  --trace-file trace.json \
  --prompts './prompts/*.md' \
  --evals './tests/*.py' \
  --expected-behavior "Agent must call check_policy tool before answering" \
  --out hypothesis.yaml

# Analyze exported LangSmith trace
refinery chat --trace-file langsmith_export.json --out hypothesis.yaml

# Fetch live from LangSmith
refinery analyze --trace-id abc123 --project my-project --out hypothesis.json --format json
```

The CLI validates output against the schema before writing files. Hypothesis IDs are normalized (`hyp-001`, …) for easy tracking.

---

## Hypothesis Pack schema

Refinery ships a versioned schema with Pydantic validation to prevent regressions.

```python
from refinery.schemas.hypothesis_pack_v1 import HypothesisPack

pack = HypothesisPack.from_path("hypothesis.yaml")
print(pack.findings[0].description)
```

- Schema file: `schema/hypothesis-pack-v1.yaml`
- Python model: `refinery/schemas/hypothesis_pack_v1.py`
- Golden tests: `tests/test_hypothesis_pack_schema.py`

Schema semver: `v1.x` = backwards-compatible additions, `v2.x` = breaking changes. Schema version is independent from package version; check `metadata.schema_version`.

---

## Supported Integrations

### Trace Sources (Current)
- **Local files** - OpenTelemetry, Langfuse, LangSmith exports, custom JSON
- **LangSmith API** - Live trace fetching (requires LANGSMITH_API_KEY)

### Trace Sources (Planned - Open Source)
- **Langfuse API** - Direct integration for live trace fetching
- **OpenTelemetry Collector** - Direct OTLP ingestion
- **Custom APIs** - Plugin system for your observability platform

### LLM Providers (Current)
- **OpenAI** - GPT-5 with Responses API for structured analysis

### LLM Providers (Planned - Open Source)
- **Anthropic Claude** - Extended context and tool use
- **Google Gemini** - Multi-modal analysis capabilities

Refinery is designed to be integration-agnostic. We started with LangSmith and OpenAI, but the architecture supports any trace format and LLM provider. Direct integrations will be added as open source contributions.

---

## Contributing

We welcome contributions! Refinery is built to be integration-agnostic, so adding new trace sources and LLM providers is encouraged.

**High-value contributions:**
- Direct integrations: Langfuse API, OpenTelemetry collectors, other observability platforms
- LLM provider support: Anthropic Claude, Google Gemini, local models
- Schema enhancements: New hypothesis types, validation rules
- Documentation: Tutorials, integration guides, examples

See `CONTRIBUTING.md` (coming Week 1) for style, testing, and provider guidelines. We label starter issues as `good first issue`; CI runs without secrets.

---

## License

MIT-licensed open source software.

**Future lab environment:** In the future, Refinery will provide an experiment orchestration lab to validate proposed fixes. This will be a separate proprietary product, not part of the open source CLI.

See `LICENSE` for details.
