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
