# Changelog

All notable changes to Refinery will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v0.2

- Anthropic Claude support
- Google Gemini support
- Enhanced trace sanitization tools
- Improved error recovery and retry logic
- Performance optimizations for large traces

## [0.1.0] - 2025-10-16

### Added

**Core Features:**
- 4-stage analysis pipeline: Timeline Extraction → Gap Analysis → Root Cause Diagnosis → Hypothesis Generation
- `--trace-file` support for analyzing local LangSmith JSON files without API access
- `--trace-id` support for fetching and analyzing traces from LangSmith API
- Hypothesis Pack schema v1.0 with structured YAML/JSON export
- Interactive chat mode with real-time progress tracking
- `analyze` command alias for `chat` (convenience)
- Web UI via Streamlit (`refinery ui`)

**Model Support:**
- OpenAI GPT-4o support for trace analysis
- OpenAI GPT-5 support with reasoning effort optimization
- Configurable model selection and parameters

**Developer Experience:**
- CLI with comprehensive error messages and help text
- Debug mode (`--debug`) for detailed logging
- Lazy configuration validation (only validates required keys for chosen workflow)
- Example trace file (`examples/demo_trace.json`) for quick testing

**Infrastructure:**
- CI/CD pipeline with automated linting and testing
- Mocked testing infrastructure (no API keys required for tests)
- Comprehensive documentation (README, SECURITY, examples)
- MIT license for open source use

**Output Formats:**
- YAML export (default) for human readability
- JSON export for programmatic parsing
- Structured Hypothesis Pack schema with versioning

### Known Limitations

- **OpenAI models only**: Anthropic Claude and Google Gemini support planned for v0.2
- **LangSmith trace format only**: OpenTelemetry support may come in future releases
- **English language**: Analysis works best with English prompts and traces
- **GPT-5 access required**: No GPT-4o fallback in v0.1 (by design - GPT-5 required for optimal analysis)

### Technical Details

**Dependencies:**
- Python 3.8+ required
- OpenAI SDK 1.0+
- LangSmith SDK 0.1+
- Streamlit 1.49+ for web UI
- Pydantic 2.0+ for structured outputs

**Architecture:**
- Provider abstraction layer for future multi-model support
- Trace source abstraction (API vs local file)
- Modular analysis stages for maintainability
- Structured schema with Pydantic validation

## Schema Versioning Policy

This project uses semantic versioning for the Hypothesis Pack schema:

- **v1.x**: Backwards compatible additions (new optional fields, new enum values with defaults)
- **v2.x**: Breaking changes (removed/renamed fields, changed types, required fields without defaults)

**Schema version is tracked independently from package version:**
- Package version: `refinery-cli==0.1.0` (software release)
- Schema version: `hypothesis_pack.version: "1.0.0"` (output format)

### Compatibility Matrix

| Refinery Version | Supported Schema Versions |
|-----------------|---------------------------|
| 0.1.x           | v1.0.0                   |
| 0.2.x (planned) | v1.0.0, v1.1.0           |

## Migration Guides

When upgrading between major versions, see the migration guides:

- [Migrating from v0.1 to v0.2](docs/migrations/v0.1-to-v0.2.md) (coming soon)

## Deprecation Policy

We follow a deprecation policy to maintain backwards compatibility:

1. **Deprecation Notice**: Features are marked as deprecated at least one minor version before removal
2. **Migration Path**: We provide migration guides and alternative approaches
3. **Removal**: Deprecated features are removed in the next major version

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to Refinery, including:
- Development setup
- Testing guidelines
- Pull request process
- Code style requirements

## Links

- [Homepage](https://github.com/your-org/refinery)
- [Documentation](https://github.com/your-org/refinery#readme)
- [Issue Tracker](https://github.com/your-org/refinery/issues)
- [PyPI Package](https://pypi.org/project/refinery-cli/)
