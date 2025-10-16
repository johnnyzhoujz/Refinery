# Refinery Architecture

This document explains Refinery's architecture, with a focus on the provider abstraction strategy and how it enables future multi-model support.

## Overview

Refinery is designed as **model-agnostic infrastructure** for AI agent debugging. While v0.1 launches with OpenAI-only support, the architecture is built to support multiple LLM providers in future releases.

This is a strategic positioning: **we're not an ecosystem play like AgentKit**. Our goal is to work across your entire AI stack.

## Provider Abstraction Strategy

Refinery uses **two LLM abstraction layers** by design, each serving different purposes:

### 1. LLMProvider (Simple Completions)

**Location**: `refinery/integrations/llm_provider.py`

**Purpose**: Generic text completions for simple, single-turn tasks

**Current Support**:
- OpenAI (GPT-4o, GPT-5)
- Anthropic Claude
- Google Gemini

**Use Cases**:
- Simple text transformations
- Utility functions (summarization, classification)
- Non-critical analysis steps
- Development and testing utilities

**Example**:
```python
from refinery.integrations.llm_provider import create_llm_provider

provider = create_llm_provider()
result = await provider.complete(
    prompt="Summarize this trace event",
    system_prompt="You are a helpful assistant",
    temperature=0.7
)
```

**Why This Layer Works Across Providers**:
- Simple request/response pattern
- All major providers support chat completions
- Easy to add new providers (minimal API differences)
- Fallback-friendly (can retry with different provider)

### 2. AnalysisProvider (Structured Analysis)

**Location**: `refinery/integrations/responses_client.py`

**Purpose**: Complex structured analysis requiring advanced features

**Current Support**:
- **OpenAI Responses API only** (v0.1)

**Use Cases**:
- 4-stage trace analysis pipeline
- Hypothesis generation with structured outputs
- Large context analysis (100K+ tokens)
- Background job polling for long-running tasks

**Why This Layer is OpenAI-Only (For Now)**:

The 4-stage analysis pipeline requires features that don't map to simple completion APIs:

1. **Large Context Windows**: Analysis of complex traces requires 100K+ token contexts
2. **File Search + Vector Store**: Upload trace data as searchable documents
3. **Background Job Polling**: Long-running analysis (GPT-5 reasoning effort can take minutes)
4. **Structured JSON Outputs**: Strict schema validation with retries
5. **Reasoning Effort Control**: GPT-5 specific feature for deep analysis

**Current Implementation**:
```python
from refinery.integrations.responses_client import ResponsesClient

client = ResponsesClient(api_key=openai_key)

# Create background job with file search
response, metadata = await client.create_background(
    body={
        "model": "gpt-5-preview",
        "reasoning_effort": "high",
        "input": [...],
        "file_search": [...],
        "output_schema": {...}
    },
    poll_interval=5.0,
    timeout=600.0
)
```

### Why Two Layers?

**Different Use Cases, Different Requirements**:

| Feature | Simple Completions | Structured Analysis |
|---------|-------------------|---------------------|
| **Context Size** | <32K tokens | 100K+ tokens |
| **Response Type** | Text | Structured JSON |
| **Execution** | Synchronous | Background jobs |
| **Vector Store** | Not needed | Required for trace search |
| **Provider Support** | OpenAI, Anthropic, Gemini | OpenAI only (v0.1) |

**Design Principle**: Use the right tool for the job
- Simple tasks → LLMProvider (provider-agnostic)
- Complex analysis → AnalysisProvider (OpenAI Responses API)

## Model Support Roadmap

### v0.1 (Current - OpenAI Launch)

**Rationale**: Prove core value with single provider, avoid multi-model complexity

✅ **OpenAI**:
- GPT-4o for general completions
- GPT-5 for advanced reasoning (trace analysis, hypothesis generation)
- Responses API for structured outputs + file search

**What Works**:
- Full 4-stage analysis pipeline
- Hypothesis generation with structured outputs
- Background job polling
- Large trace analysis (100K+ tokens)

**What Doesn't**:
- No Anthropic/Claude support
- No Google Gemini support (for analysis; LLMProvider supports Gemini)

### v0.2 (Planned - Multi-Model Support)

**Goal**: Add Anthropic Claude support for core analysis pipeline

**Challenges to Solve**:

1. **No Direct Responses API Equivalent**
   - Anthropic uses standard Messages API
   - Need to implement equivalent functionality

2. **Different Extended Context Approach**
   - Anthropic: 200K token context in single request
   - OpenAI: File search + vector store

3. **No Reasoning Effort Parameter**
   - GPT-5 has `reasoning_effort` control
   - Claude: Manual prompt engineering required

4. **Structured Outputs**
   - OpenAI: Native JSON schema support
   - Anthropic: Requires tool use or prompt engineering

**Implementation Plan**:

```python
# New abstraction layer (v0.2)
class AnalysisProviderBase:
    """Abstract base for analysis providers."""

    async def analyze_trace(
        self,
        trace: Dict,
        analysis_type: str,
        output_schema: Dict
    ) -> Dict:
        """Provider-agnostic analysis interface."""
        raise NotImplementedError

class OpenAIAnalysisProvider(AnalysisProviderBase):
    """OpenAI Responses API implementation."""
    # Current responses_client.py logic

class AnthropicAnalysisProvider(AnalysisProviderBase):
    """Anthropic Messages API implementation."""
    # New: Large context + tool use for structured outputs
```

**Estimated Timeline**: 2-4 weeks (tracked in [GitHub issue #1](link))

### v0.3+ (Future - Additional Providers)

**Candidates**:
- Google Gemini (1.5/2.0 with extended context)
- Mistral Large
- Local models via Ollama (experimental)

**Depends On**:
- Provider extended context support (100K+ tokens)
- Structured output capabilities
- Community demand

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Refinery CLI                           │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ Trace      │  │ Chat       │  │ Hypothesis           │  │
│  │ Sources    │  │ Interface  │  │ Generation           │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
┌─────────▼──────────┐             ┌─────────▼──────────┐
│  LLMProvider       │             │ AnalysisProvider   │
│  (Simple Tasks)    │             │ (Core Pipeline)    │
├────────────────────┤             ├────────────────────┤
│ • OpenAI           │             │ • OpenAI (v0.1)    │
│ • Anthropic        │             │ • Anthropic (v0.2) │
│ • Gemini           │             │ • Gemini (v0.3+)   │
└────────────────────┘             └────────────────────┘
         │                                   │
         └───────────────┬───────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Provider SDKs      │
              ├─────────────────────┤
              │ • openai            │
              │ • anthropic         │
              │ • google-genai      │
              └─────────────────────┘
```

## Trace Source Abstraction

In addition to provider abstraction, Refinery abstracts trace sources:

**Location**: `refinery/integrations/trace_sources.py`

**Implementations**:
1. **LangSmithAPISource**: Fetch traces via LangSmith API
2. **LocalFileSource**: Parse local trace JSON files

**Interface**:
```python
class TraceSource:
    async def fetch(self) -> Dict:
        """Fetch trace data."""
        raise NotImplementedError
```

**Why This Matters**:
- User controls data flow (API vs local file)
- Security-conscious workflow (review before sending to LLM)
- No vendor lock-in (works with any LangSmith project)
- Future: Support other trace formats (OpenTelemetry)

## Key Design Principles

### 1. Model-Agnostic Design, OpenAI Implementation

**Philosophy**: Build abstractions as if multi-model support exists, but implement OpenAI first

**Benefits**:
- Easier to add providers later (interfaces already defined)
- No major refactor needed for v0.2 Anthropic support
- Clear separation of concerns

**Example**:
```python
# Good: Provider-agnostic interface
async def analyze_failure(trace, provider):
    diagnosis = await provider.analyze_trace(trace, "diagnosis")
    return diagnosis

# Bad: OpenAI-specific logic in business code
async def analyze_failure(trace):
    response = await openai.chat.completions.create(...)
    return response
```

### 2. Lazy Validation

**Philosophy**: Only validate API keys needed for the chosen workflow

**Benefits**:
- Users without LangSmith can still use --trace-file
- Clearer error messages (explains what's actually needed)
- Better user experience (don't fail fast on unused features)

**Implementation** (`refinery/cli.py`):
```python
if trace_id:
    # LangSmith API workflow: need both keys
    config.validate_langsmith()
    config.validate_openai()
elif trace_file:
    # Local file workflow: only need OpenAI
    config.validate_openai()
```

### 3. Structured Outputs with Validation

**Philosophy**: Strong typing and validation at the boundaries

**Tools**:
- Pydantic models for schemas
- JSON Schema validation
- Hypothesis Pack v1.0 format

**Why**:
- Enables downstream tooling (CI/CD, evaluation frameworks)
- Reproducibility (same input → same output format)
- Versioned interchange format (backwards compatibility)

## Testing Strategy

### Mocking for CI/CD

**Challenge**: Tests require API keys and incur costs

**Solution**: Mock at provider interface level

**Locations**:
- `tests/mocks/mock_llm_provider.py`: Mocked LLMProvider
- `tests/mocks/mock_responses_client.py`: Mocked ResponsesClient

**Benefits**:
- Tests run without API keys
- Fast test execution
- No token costs
- Deterministic outputs

**Trade-offs**:
- Integration tests still need real API calls (run manually)
- Mocks need updates when provider APIs change

## Configuration

**Location**: `refinery/utils/config.py`

**Supported Providers**:
```python
config.llm_provider = "openai"  # or "anthropic", "gemini"
config.openai_model = "gpt-5-preview"
config.anthropic_model = "claude-3-5-sonnet-20241022"
config.gemini_model = "gemini-2.0-flash"
```

**v0.1 Limitation**: Analysis pipeline hard-coded to OpenAI
**v0.2 Goal**: Configurable analysis provider

## Future Work

### Planned Enhancements

1. **AnalysisProvider Abstraction** (v0.2)
   - Abstract base class for analysis providers
   - OpenAI and Anthropic implementations
   - Config-driven provider selection

2. **Provider Fallback** (v0.3)
   - Automatic fallback to different provider on failure
   - Cost optimization (use cheaper provider first)

3. **Hybrid Analysis** (v0.3+)
   - Use different providers for different stages
   - Example: GPT-5 for diagnosis, Claude for hypothesis generation
   - Optimize for cost/quality trade-offs

4. **Local Model Support** (v0.4+)
   - Experimental support for Ollama
   - Privacy-focused deployment
   - Requires significant context compression

### Contributing New Providers

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on adding new providers.

**Key Requirements**:
1. Must support 100K+ token context (for trace analysis)
2. Must support structured JSON outputs (or equivalent)
3. Must handle long-running requests (background jobs or timeouts)

## Questions?

For architecture questions:
- Open a GitHub Discussion
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup
- Review existing provider implementations as examples

---

**Remember**: Refinery is infrastructure, not an ecosystem play. We support the tools you already use, not replace them.
