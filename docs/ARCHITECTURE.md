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
