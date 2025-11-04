"""
Unit tests for OTLP trace parser.

Tests parsing of OpenTelemetry traces from various backends including
Grafana Tempo, Honeycomb, and other OTLP-compliant systems.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from refinery.core.models import RunType, Trace
from refinery.integrations.otlp_parser import (
    _extract_error,
    _extract_inputs,
    _extract_outputs,
    _extract_service_name,
    _infer_run_type,
    _parse_span,
    parse_otlp_trace,
)
from refinery.integrations.otlp_utils import (
    build_hierarchy,
    flatten_otlp_attributes,
    parse_otlp_timestamp,
)


@pytest.fixture
def fixtures_dir():
    """Get path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tempo_trace_data(fixtures_dir):
    """Load Tempo OTLP trace fixture."""
    with open(fixtures_dir / "otlp_trace_tempo.json") as f:
        return json.load(f)


@pytest.fixture
def honeycomb_trace_data(fixtures_dir):
    """Load Honeycomb OTLP trace fixture."""
    with open(fixtures_dir / "otlp_trace_honeycomb.json") as f:
        return json.load(f)


class TestOTLPUtils:
    """Test OTLP utility functions."""

    def test_parse_otlp_timestamp_string(self):
        """Test parsing OTLP timestamp from string."""
        # 2025-01-15 08:00:00 UTC in nanoseconds
        timestamp = "1736935200000000000"
        result = parse_otlp_timestamp(timestamp)

        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_otlp_timestamp_int(self):
        """Test parsing OTLP timestamp from integer."""
        timestamp = 1736935200000000000
        result = parse_otlp_timestamp(timestamp)

        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_flatten_otlp_attributes_string_value(self):
        """Test flattening OTLP attributes with stringValue."""
        attributes = [
            {"key": "service.name", "value": {"stringValue": "my-service"}},
            {"key": "service.version", "value": {"stringValue": "1.0.0"}},
        ]

        result = flatten_otlp_attributes(attributes)

        assert result == {
            "service.name": "my-service",
            "service.version": "1.0.0",
        }

    def test_flatten_otlp_attributes_multiple_types(self):
        """Test flattening OTLP attributes with various value types."""
        attributes = [
            {"key": "name", "value": {"stringValue": "test"}},
            {"key": "count", "value": {"intValue": 42}},
            {"key": "ratio", "value": {"doubleValue": 3.14}},
            {"key": "enabled", "value": {"boolValue": True}},
        ]

        result = flatten_otlp_attributes(attributes)

        assert result == {
            "name": "test",
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
        }

    def test_flatten_otlp_attributes_empty(self):
        """Test flattening empty attributes list."""
        result = flatten_otlp_attributes([])
        assert result == {}

    def test_build_hierarchy_single_root(self):
        """Test building hierarchy with single root span."""
        from refinery.core.models import TraceRun

        spans = [
            TraceRun(
                id="root",
                name="root",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            )
        ]

        result = build_hierarchy(spans)

        assert len(result) == 1
        assert result[0].dotted_order == "0000"

    def test_build_hierarchy_nested_spans(self):
        """Test building hierarchy with nested parent-child spans."""
        from refinery.core.models import TraceRun

        spans = [
            TraceRun(
                id="root",
                name="root",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child1",
                name="child1",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child2",
                name="child2",
                run_type=RunType.TOOL,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 1, 0, 0, 6, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 1, 0, 0, 9, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="grandchild",
                name="grandchild",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                end_time=datetime(2025, 1, 1, 0, 0, 4, tzinfo=timezone.utc),
                error=None,
                parent_run_id="child1",
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        result = build_hierarchy(spans)

        # Verify dotted_order assignments
        assert spans[0].dotted_order == "0000"  # root
        assert spans[1].dotted_order == "0000.0000"  # child1 (first child by time)
        assert spans[2].dotted_order == "0000.0001"  # child2 (second child by time)
        assert spans[3].dotted_order == "0000.0000.0000"  # grandchild


class TestOTLPParser:
    """Test OTLP parser functions."""

    def test_extract_service_name_found(self):
        """Test extracting service name from resource attributes."""
        data = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "my-awesome-service"},
                            }
                        ]
                    }
                }
            ]
        }

        result = _extract_service_name(data)
        assert result == "my-awesome-service"

    def test_extract_service_name_not_found(self):
        """Test extracting service name when not present."""
        data = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "other.attribute", "value": {"stringValue": "value"}}
                        ]
                    }
                }
            ]
        }

        result = _extract_service_name(data)
        assert result == "unknown"

    def test_extract_service_name_empty_resources(self):
        """Test extracting service name with empty resourceSpans."""
        data = {"resourceSpans": []}

        result = _extract_service_name(data)
        assert result == "unknown"

    def test_infer_run_type_llm(self):
        """Test inferring LLM run type from gen_ai attributes."""
        span = {"kind": "SPAN_KIND_INTERNAL"}
        attributes = {
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": "claude-3",
        }

        result = _infer_run_type(span, attributes)
        assert result == RunType.LLM

    def test_infer_run_type_tool(self):
        """Test inferring TOOL run type from SPAN_KIND_CLIENT."""
        span = {"kind": "SPAN_KIND_CLIENT"}
        attributes = {"tool.name": "calculator"}

        result = _infer_run_type(span, attributes)
        assert result == RunType.TOOL

    def test_infer_run_type_chain_default(self):
        """Test inferring CHAIN run type as default."""
        span = {"kind": "SPAN_KIND_INTERNAL"}
        attributes = {"some.attribute": "value"}

        result = _infer_run_type(span, attributes)
        assert result == RunType.CHAIN

    def test_extract_inputs_with_messages(self):
        """Test extracting inputs from gen_ai.input.messages."""
        span = {}
        attributes = {
            "gen_ai.input.messages": '[{"role": "user", "content": "Hello"}]'
        }

        result = _extract_inputs(span, attributes)
        assert "messages" in result
        assert result["messages"] == '[{"role": "user", "content": "Hello"}]'

    def test_extract_inputs_with_prompt_fallback(self):
        """Test extracting inputs from gen_ai.prompt.* fallback."""
        span = {}
        attributes = {
            "gen_ai.prompt.0.role": "user",
            "gen_ai.prompt.0.content": "Hello",
        }

        result = _extract_inputs(span, attributes)
        assert "prompts" in result
        assert result["prompts"]["gen_ai.prompt.0.role"] == "user"
        assert result["prompts"]["gen_ai.prompt.0.content"] == "Hello"

    def test_extract_inputs_empty(self):
        """Test extracting inputs when none present."""
        span = {}
        attributes = {"other.attribute": "value"}

        result = _extract_inputs(span, attributes)
        assert result == {}

    def test_extract_outputs_with_messages(self):
        """Test extracting outputs from gen_ai.output.messages."""
        span = {}
        attributes = {
            "gen_ai.output.messages": '[{"role": "assistant", "content": "Hi!"}]'
        }

        result = _extract_outputs(span, attributes)
        assert "messages" in result
        assert result["messages"] == '[{"role": "assistant", "content": "Hi!"}]'

    def test_extract_outputs_with_completion_fallback(self):
        """Test extracting outputs from gen_ai.completion.* fallback."""
        span = {}
        attributes = {
            "gen_ai.completion.0.role": "assistant",
            "gen_ai.completion.0.content": "Response here",
        }

        result = _extract_outputs(span, attributes)
        assert "completions" in result
        assert result["completions"]["gen_ai.completion.0.role"] == "assistant"
        assert result["completions"]["gen_ai.completion.0.content"] == "Response here"

    def test_extract_outputs_empty(self):
        """Test extracting outputs when none present."""
        span = {}
        attributes = {"other.attribute": "value"}

        result = _extract_outputs(span, attributes)
        assert result == {}

    def test_extract_error_from_status_code_string(self):
        """Test extracting error from status code (string format)."""
        span = {
            "status": {
                "code": "STATUS_CODE_ERROR",
                "message": "Something went wrong",
            }
        }

        result = _extract_error(span)
        assert result == "Something went wrong"

    def test_extract_error_from_status_code_int(self):
        """Test extracting error from status code (integer format)."""
        span = {"status": {"code": 2, "message": "Error occurred"}}

        result = _extract_error(span)
        assert result == "Error occurred"

    def test_extract_error_from_exception_event(self):
        """Test extracting error from exception event."""
        span = {
            "events": [
                {
                    "name": "exception",
                    "attributes": [
                        {
                            "key": "exception.message",
                            "value": {"stringValue": "Timeout error"},
                        }
                    ],
                }
            ]
        }

        result = _extract_error(span)
        assert result == "Timeout error"

    def test_extract_error_none(self):
        """Test extracting error when none present."""
        span = {"status": {"code": "STATUS_CODE_OK"}}

        result = _extract_error(span)
        assert result is None

    def test_parse_span_complete(self):
        """Test parsing a complete OTLP span."""
        span = {
            "spanId": "span-123",
            "name": "test.span",
            "kind": "SPAN_KIND_INTERNAL",
            "startTimeUnixNano": "1736935200000000000",
            "endTimeUnixNano": "1736935205000000000",
            "traceId": "trace-456",
            "parentSpanId": "parent-789",
            "attributes": [
                {"key": "gen_ai.system", "value": {"stringValue": "anthropic"}},
                {"key": "test.attribute", "value": {"intValue": 42}},
            ],
            "status": {"code": "STATUS_CODE_OK"},
        }

        result = _parse_span(span)

        assert result.id == "span-123"
        assert result.name == "test.span"
        assert result.run_type == RunType.LLM  # gen_ai.system present
        assert result.parent_run_id == "parent-789"
        assert result.trace_id == "trace-456"
        assert result.error is None
        assert result.dotted_order == ""  # Set by build_hierarchy
        assert result.metadata["gen_ai.system"] == "anthropic"
        assert result.metadata["test.attribute"] == 42


class TestParseOTLPTrace:
    """Test complete OTLP trace parsing."""

    def test_parse_tempo_trace(self, tempo_trace_data):
        """Test parsing Grafana Tempo OTLP trace."""
        trace = parse_otlp_trace(tempo_trace_data, "abc123")

        # Verify trace metadata
        assert isinstance(trace, Trace)
        assert trace.trace_id == "abc123"
        assert trace.project_name == "test-service"
        assert trace.metadata["format"] == "opentelemetry"
        assert trace.metadata["source"] == "file"

        # Verify spans parsed
        assert len(trace.runs) == 3
        assert all(run.trace_id == "abc123" for run in trace.runs)

        # Verify run types
        run_types = {run.name: run.run_type for run in trace.runs}
        assert run_types["llm.call"] == RunType.LLM
        assert run_types["tool.call"] == RunType.TOOL
        assert run_types["chain.orchestrator"] == RunType.CHAIN

        # Verify hierarchy (dotted_order assigned)
        root_run = next(run for run in trace.runs if run.name == "llm.call")
        assert root_run.dotted_order == "0000"
        assert root_run.parent_run_id is None

        child_runs = [run for run in trace.runs if run.parent_run_id == "span-1"]
        assert len(child_runs) == 2
        assert all(run.dotted_order.startswith("0000.") for run in child_runs)

    def test_parse_honeycomb_trace(self, honeycomb_trace_data):
        """Test parsing Honeycomb OTLP trace."""
        trace = parse_otlp_trace(honeycomb_trace_data, "def456")

        # Verify trace metadata
        assert isinstance(trace, Trace)
        assert trace.trace_id == "def456"
        assert trace.project_name == "honeycomb-demo-service"
        assert trace.metadata["format"] == "opentelemetry"

        # Verify spans parsed
        assert len(trace.runs) == 4

        # Verify error extraction from exception event
        error_run = next(
            run for run in trace.runs if run.name == "database.query"
        )
        assert error_run.error == "Connection timeout: database unreachable"
        assert error_run.run_type == RunType.TOOL  # SPAN_KIND_CLIENT

        # Verify LLM run with vendor-specific prompt attributes
        llm_run = next(run for run in trace.runs if run.name == "llm.generate")
        assert llm_run.run_type == RunType.LLM
        assert "gen_ai.system" in llm_run.metadata
        assert llm_run.metadata["gen_ai.system"] == "openai"

        # Check fallback input/output extraction
        if llm_run.inputs:
            # Should have prompts from gen_ai.prompt.* attributes
            assert "prompts" in llm_run.inputs or "messages" in llm_run.inputs
        if llm_run.outputs:
            # Should have completions from gen_ai.completion.* attributes
            assert "completions" in llm_run.outputs or "messages" in llm_run.outputs

    def test_parse_trace_with_no_spans_raises_error(self):
        """Test parsing trace with no spans raises ValueError."""
        data = {"resourceSpans": []}

        with pytest.raises(ValueError, match="No spans found"):
            parse_otlp_trace(data, "empty-trace")

    def test_parse_trace_calculates_times(self, tempo_trace_data):
        """Test trace start and end times are calculated correctly."""
        trace = parse_otlp_trace(tempo_trace_data, "abc123")

        # Verify start_time is minimum of all run start times
        assert trace.start_time == min(run.start_time for run in trace.runs)

        # Verify end_time is maximum of all run end times
        assert trace.end_time == max(
            run.end_time for run in trace.runs if run.end_time
        )

    def test_parse_trace_hierarchy_parent_child(self, tempo_trace_data):
        """Test hierarchy building assigns correct parent-child relationships."""
        trace = parse_otlp_trace(tempo_trace_data, "abc123")

        # Find parent and children
        parent = next(run for run in trace.runs if run.name == "llm.call")
        children = [run for run in trace.runs if run.parent_run_id == parent.id]

        assert len(children) == 2
        for child in children:
            assert child.dotted_order.startswith(parent.dotted_order + ".")

    def test_parse_trace_preserves_all_attributes(self, honeycomb_trace_data):
        """Test all OTLP attributes are preserved in metadata."""
        trace = parse_otlp_trace(honeycomb_trace_data, "def456")

        # Check that various attribute types are preserved
        llm_run = next(run for run in trace.runs if run.name == "llm.generate")

        # String value
        assert "gen_ai.system" in llm_run.metadata
        assert isinstance(llm_run.metadata["gen_ai.system"], str)

        # Double value
        assert "gen_ai.request.temperature" in llm_run.metadata
        assert isinstance(llm_run.metadata["gen_ai.request.temperature"], float)

        # Int value
        assert "gen_ai.request.max_tokens" in llm_run.metadata
        assert isinstance(llm_run.metadata["gen_ai.request.max_tokens"], int)

        # Bool value
        retry_run = next(run for run in trace.runs if run.name == "retry.attempt")
        assert "retry.success" in retry_run.metadata
        assert isinstance(retry_run.metadata["retry.success"], bool)

    def test_parse_trace_multiple_backends_compatibility(
        self, tempo_trace_data, honeycomb_trace_data
    ):
        """Test parser handles traces from different OTLP backends."""
        # Parse traces from different backends
        tempo_trace = parse_otlp_trace(tempo_trace_data, "tempo-123")
        honeycomb_trace = parse_otlp_trace(honeycomb_trace_data, "honeycomb-456")

        # Both should be valid Trace objects
        assert isinstance(tempo_trace, Trace)
        assert isinstance(honeycomb_trace, Trace)

        # Both should have runs with proper hierarchy
        assert all(run.dotted_order for run in tempo_trace.runs)
        assert all(run.dotted_order for run in honeycomb_trace.runs)

        # Both should extract service names
        assert tempo_trace.project_name == "test-service"
        assert honeycomb_trace.project_name == "honeycomb-demo-service"
