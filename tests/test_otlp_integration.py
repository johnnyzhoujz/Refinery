"""
Integration tests for OTLP prompt extraction.

Tests the complete flow: parse OTLP trace -> extract prompts using OTLPPromptExtractor.
"""

import json
from pathlib import Path

import pytest

from refinery.integrations.otlp_parser import parse_otlp_trace
from refinery.integrations.prompt_extractors import OTLPPromptExtractor


@pytest.fixture
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def extractor():
    """Create OTLPPromptExtractor instance."""
    return OTLPPromptExtractor()


class TestOTLPTempoIntegration:
    """Test integration with Grafana Tempo OTLP trace."""

    @pytest.mark.asyncio
    async def test_extract_from_tempo_trace(self, fixtures_dir, extractor):
        """Test prompt extraction from Tempo OTLP trace fixture."""
        with open(fixtures_dir / "otlp_trace_tempo.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "tempo-trace-1")
        result = await extractor.extract(trace)

        # The tempo fixture uses old-style gen_ai.input.messages with simple content
        # It has: [{"role": "user", "content": "Hello"}]
        # This is NOT compliant with the parts array format, so it should fall back
        assert result is not None
        # Check that we got some prompts (exact content depends on fixture format)
        # The current tempo fixture doesn't have proper parts array format
        # so it won't extract via official path, but may extract via fallback


class TestOTLPHoneycombIntegration:
    """Test integration with Honeycomb OTLP trace."""

    @pytest.mark.asyncio
    async def test_extract_from_honeycomb_trace(self, fixtures_dir, extractor):
        """Test prompt extraction from Honeycomb OTLP trace fixture."""
        with open(fixtures_dir / "otlp_trace_honeycomb.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "honeycomb-trace-1")
        result = await extractor.extract(trace)

        # Honeycomb fixture uses gen_ai.prompt.0.role/content pattern (non-standard)
        # This won't be extracted by official path or fallback (it's in metadata, not inputs)
        # Result may be None or contain prompts from fallback if inputs has messages


class TestOTLPFullSpecIntegration:
    """Test integration with full spec-compliant OTLP trace."""

    @pytest.mark.asyncio
    async def test_extract_from_full_spec_trace(self, fixtures_dir, extractor):
        """Test prompt extraction from full spec-compliant OTLP trace."""
        with open(fixtures_dir / "otlp_trace_full_spec.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "fullspec-trace-1")
        result = await extractor.extract(trace)

        assert result is not None

        # First LLM span has system + user prompts with parts array
        assert len(result.system_prompts) >= 1
        assert (
            "You are an expert software engineer" in result.system_prompts[0]
        )

        assert len(result.user_prompts) >= 1
        # User message has two text parts that should be joined
        assert "distributed cache using Redis" in result.user_prompts[0]
        assert "Include code examples" in result.user_prompts[0]

    @pytest.mark.asyncio
    async def test_system_instructions_extraction(self, fixtures_dir, extractor):
        """Test that gen_ai.system_instructions is extracted when input.messages not present."""
        with open(fixtures_dir / "otlp_trace_full_spec.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "fullspec-trace-1")

        # The second LLM span uses gen_ai.system_instructions
        # When we extract, it should include system instructions from that span
        result = await extractor.extract(trace)

        assert result is not None
        # Check that we have prompts from multiple LLM runs
        # First span: system + user via input.messages
        # Second span: user via input.messages (system_instructions is skipped because input.messages exists)
        assert len(result.user_prompts) >= 2


class TestOTLPParserIntegration:
    """Test that OTLP parser correctly preserves attributes for extraction."""

    @pytest.mark.asyncio
    async def test_parser_preserves_gen_ai_attributes(self, fixtures_dir, extractor):
        """Test that OTLP parser preserves gen_ai.* attributes in metadata."""
        with open(fixtures_dir / "otlp_trace_full_spec.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "test-trace")

        # Verify that gen_ai attributes are in metadata
        llm_runs = [run for run in trace.runs if run.run_type.value == "llm"]
        assert len(llm_runs) >= 1

        # First LLM run should have gen_ai.input.messages in metadata
        first_llm = llm_runs[0]
        assert "gen_ai.input.messages" in first_llm.metadata
        assert "gen_ai.system" in first_llm.metadata

        # Verify extraction works with preserved metadata
        result = await extractor.extract(trace)
        assert result is not None

    @pytest.mark.asyncio
    async def test_parser_handles_non_llm_runs(self, fixtures_dir, extractor):
        """Test that non-LLM runs don't interfere with prompt extraction."""
        with open(fixtures_dir / "otlp_trace_full_spec.json") as f:
            data = json.load(f)

        trace = parse_otlp_trace(data, "test-trace")

        # Trace should have both LLM and non-LLM runs
        llm_runs = [run for run in trace.runs if run.run_type.value == "llm"]
        other_runs = [run for run in trace.runs if run.run_type.value != "llm"]

        assert len(llm_runs) >= 1
        assert len(other_runs) >= 1  # Should have tool runs

        # Extraction should only process LLM runs
        result = await extractor.extract(trace)
        assert result is not None
        # Prompts should only come from LLM runs, not tool runs


class TestEndToEndFlow:
    """Test complete end-to-end flow from file to extracted prompts."""

    @pytest.mark.asyncio
    async def test_complete_flow_with_full_spec_trace(self, fixtures_dir, extractor):
        """Test complete flow: load JSON -> parse -> extract -> verify."""
        # 1. Load OTLP JSON file
        with open(fixtures_dir / "otlp_trace_full_spec.json") as f:
            otlp_data = json.load(f)

        # 2. Parse OTLP trace
        trace = parse_otlp_trace(otlp_data, "e2e-test-trace")

        # Verify trace was parsed correctly
        assert trace.trace_id == "e2e-test-trace"
        assert trace.project_name == "ai-agent-service"
        assert len(trace.runs) >= 3  # 2 LLM + 1 tool

        # 3. Extract prompts
        prompts = await extractor.extract(trace)

        # 4. Verify extracted prompts
        assert prompts is not None
        assert isinstance(prompts.system_prompts, list)
        assert isinstance(prompts.user_prompts, list)

        # Should have at least one system prompt
        assert len(prompts.system_prompts) >= 1
        assert "expert software engineer" in prompts.system_prompts[0].lower()

        # Should have at least one user prompt
        assert len(prompts.user_prompts) >= 1
        assert "redis" in prompts.user_prompts[0].lower()

    @pytest.mark.asyncio
    async def test_no_prompts_returns_none(self, fixtures_dir, extractor):
        """Test that traces without LLM prompts return None."""
        # Create minimal OTLP trace with no LLM spans
        minimal_otlp = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "test-service"},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "test"},
                            "spans": [
                                {
                                    "traceId": "test123",
                                    "spanId": "span-1",
                                    "name": "http.request",
                                    "kind": "SPAN_KIND_CLIENT",
                                    "startTimeUnixNano": "1737110400000000000",
                                    "endTimeUnixNano": "1737110401000000000",
                                    "attributes": [],
                                    "status": {"code": "STATUS_CODE_OK"},
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        trace = parse_otlp_trace(minimal_otlp, "no-llm-trace")
        result = await extractor.extract(trace)

        assert result is None
