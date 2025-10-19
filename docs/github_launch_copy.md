# Refinery GitHub Launch Copy (Draft)

> Working draft of public-facing repo content. Edit as needed before publishing.

---

## Repo Description

```
Refinery: open source error analysis for AI agents. Analyze traces from any agent system and get ranked, reproducible fix hypotheses in minutes.
```

## Suggested Topics

```
ai-agents, observability, error-analysis, experimentation, provability, openai, mlops, python, agent-reliability, opentelemetry, langfuse, generic-traces, langsmith
```

---

## README.md (Draft)

```markdown
# Refinery
> Open source error analysis for AI agents – analyze failures, generate ranked fix hypotheses, and improve agent reliability through disciplined iteration.

Andrew Ng observed that "the single biggest predictor of how rapidly a team makes progress building an AI agent lay in their ability to drive a disciplined process for evals and error analysis." Yet most teams shortcut this process, attempting quick fixes rather than identifying root causes. Refinery makes rigorous error analysis practical: bring any trace from any agent system, and get a structured Hypothesis Pack with evidence, ranked fixes, confidence scores, and reproducibility metadata.

[![CI](https://github.com/YOUR-ORG/refinery-server/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-ORG/refinery-server/actions/workflows/ci.yml)
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
```

---

## SECURITY.md (Draft)

```markdown
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
```

---

## examples/README.md (Draft)

```markdown
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
```

---

## CHANGELOG.md (Draft)

```markdown
# Changelog

All notable changes to Refinery will be documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-19
### Added
- Four-stage analysis pipeline: Timeline → Gap → Diagnosis → Synthesis
- Multi-format trace support: OpenTelemetry, Langfuse, LangSmith exports, custom JSON
- Generic trace format auto-detection with raw JSON storage
- Local prompt/eval file loading via --prompts and --evals flags
- --expected-behavior flag for custom validation requirements
- Structured Hypothesis Pack schema v1.0 with YAML/JSON export
- Example field display in CLI and Streamlit UI (example_before/example_after)
- CLI alias `refinery analyze` mirroring `refinery chat`
- Schema validation via `refinery/schemas/hypothesis_pack_v1.py`
- Mocked LangSmith & LLM providers; pytest runs without secrets
- Minimal CI (ruff, black, pytest) with zero-secret configuration

### Fixed
- Schema validation mismatch between JSON schema and Pydantic models
- Added missing maxLength constraints (200/500/1000 chars)
- Added file_path pattern validation

### Changed
- LangSmith is now one of many integrations, not required
- Local trace analysis is the primary workflow

### Known Limitations
- Structured analysis uses OpenAI only (Claude/Gemini planned as open source)
- English-language prompts yield best results today

## [Unreleased]
### Planned for v0.2 (Open Source)
- Anthropic Claude support for structured analysis
- Langfuse API direct integration
- OpenTelemetry Collector integration
- Extended trace format parsers
```

---

## RELEASE.md (Draft)

```markdown
# Release Process

## Pre-release checklist
- [ ] `pytest` passes locally and in CI.
- [ ] Version bumped in `pyproject.toml`, `refinery/__init__.py`, `refinery/cli.py`.
- [ ] `CHANGELOG.md` updated with release date.
- [ ] README install instructions reflect new version/package name.
- [ ] Example traces validated (sanitization commands pass).
- [ ] Dist artifacts contain `examples/` and `schema/`.

## Steps
1. `git checkout -b release/vX.Y.Z`
2. Update versions & changelog; run `python -m build && twine check dist/*`
3. Smoke test in a clean venv.
4. `git add . && git commit -m "Release vX.Y.Z"`
5. `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
6. `git push origin release/vX.Y.Z && git push origin vX.Y.Z`
7. Create GitHub Release (paste changelog, upload artifacts).
8. `twine upload dist/*`
9. Verify: `pip install refinery-cli==X.Y.Z && refinery --version`.
10. Announce (X/Twitter, Hacker News, r/LangChain, LangChain Discord).

## Post-release
- Merge `release/vX.Y.Z` into `main`.
- Reopen `[Unreleased]` section in changelog.
- Create milestone for next version; seed roadmap issues.
```

---

## docs/ARCHITECTURE.md (Draft)

```markdown
# Refinery Architecture

## Two-layer provider strategy

Refinery deliberately separates simple completions from structured analysis.

### 1. `LLMProvider` – simple completions
- Location: `refinery/integrations/llm_provider.py`
- Purpose: lightweight text completions used across utilities.
- Providers today: OpenAI, Anthropic, Gemini.

### 2. `AnalysisProvider` – structured analysis
- Location: `refinery/integrations/responses_client.py` (v0.1).
- Purpose: long-context, tool-augmented workflows (timeline clustering, evidence retrieval, schema-constrained outputs, background job polling).
- Provider today: OpenAI Responses API (GPT-5).

### Why two layers?
The AI failure analyst pipeline requires:
- 100k+ token context and file search over trace artifacts.
- Structured JSON outputs that match the Hypothesis Pack schema.
- Reasoning effort controls and background job polling.
These demands map poorly to simple completion SDKs; separating layers keeps the codebase maintainable and ready for provider-specific capabilities.

## Roadmap: multi-provider analysis (v0.2)
Issue: `[v0.2] Implement multi-provider support for analysis pipeline` (to be opened at launch).

Planned steps:
1. Define `AnalysisProviderInterface`.
2. Refactor the OpenAI implementation into `OpenAIAnalysisProvider`.
3. Add `AnthropicAnalysisProvider` using Claude tool use & extended context.
4. Introduce provider factory driven by config (`REFINERY_ANALYSIS_PROVIDER`).
5. Expand golden tests to cover provider-specific outputs.

## Extending Refinery
When adding providers:
- Implement the interface without bypassing validation.
- Ensure Hypothesis Pack generation stays schema-compliant.
- Add integration tests with mocked responses.
- Document any provider-specific setup in README/SECURITY.

Refer to `CONTRIBUTING.md` (Week 1 deliverable) for coding standards.
```

---

## Next Steps

1. Replace `YOUR-ORG` in badge URLs with the actual GitHub org/repo.
2. Review tone, tighten copy, and align with final visual assets (GIF, screenshots).
3. When ready, copy each section into the corresponding repo file and commit alongside launch day assets.
```
