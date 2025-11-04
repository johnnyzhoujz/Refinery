"""
Tests for OTLP parsing utilities.

Tests the OTLP utility functions for parsing timestamps, flattening
attributes, and building hierarchical span structures.
"""

from datetime import datetime, timezone

import pytest

from refinery.core.models import RunType, TraceRun
from refinery.integrations.otlp_utils import (
    build_hierarchy,
    flatten_otlp_attributes,
    parse_otlp_timestamp,
)


class TestParseOtlpTimestamp:
    """Tests for parse_otlp_timestamp function."""

    def test_parse_timestamp_from_int(self):
        """Test parsing timestamp from integer."""
        # January 1, 2021, 00:00:00 UTC = 1609459200 seconds
        # In nanoseconds: 1609459200000000000
        timestamp_ns = 1609459200000000000
        result = parse_otlp_timestamp(timestamp_ns)

        assert isinstance(result, datetime)
        assert result == datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_from_string(self):
        """Test parsing timestamp from string."""
        timestamp_ns_str = "1609459200000000000"
        result = parse_otlp_timestamp(timestamp_ns_str)

        assert isinstance(result, datetime)
        assert result == datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_zero(self):
        """Test parsing timestamp of zero (epoch)."""
        result = parse_otlp_timestamp(0)

        assert result == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_parse_timestamp_very_large(self):
        """Test parsing very large timestamp (far future)."""
        # Year 2286 approximately
        timestamp_ns = 10000000000000000000
        result = parse_otlp_timestamp(timestamp_ns)

        assert isinstance(result, datetime)
        assert result.year > 2200
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_with_microseconds(self):
        """Test parsing timestamp with microsecond precision."""
        # 1609459200.123456000 seconds (round to microseconds)
        timestamp_ns = 1609459200123456000
        result = parse_otlp_timestamp(timestamp_ns)

        assert isinstance(result, datetime)
        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1
        # Python datetime only has microsecond precision
        assert result.microsecond == 123456

    def test_parse_timestamp_recent(self):
        """Test parsing a recent timestamp."""
        # October 20, 2024, 12:00:00 UTC
        timestamp_ns = 1729425600000000000
        result = parse_otlp_timestamp(timestamp_ns)

        assert result == datetime(2024, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


class TestFlattenOtlpAttributes:
    """Tests for flatten_otlp_attributes function."""

    def test_flatten_string_value(self):
        """Test flattening string attributes."""
        attributes = [
            {"key": "service.name", "value": {"stringValue": "my-service"}},
            {"key": "http.method", "value": {"stringValue": "GET"}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"service.name": "my-service", "http.method": "GET"}

    def test_flatten_int_value(self):
        """Test flattening integer attributes."""
        attributes = [
            {"key": "http.status_code", "value": {"intValue": 200}},
            {"key": "retry.count", "value": {"intValue": 3}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"http.status_code": 200, "retry.count": 3}

    def test_flatten_double_value(self):
        """Test flattening double/float attributes."""
        attributes = [
            {"key": "response.time", "value": {"doubleValue": 123.456}},
            {"key": "cpu.usage", "value": {"doubleValue": 0.75}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"response.time": 123.456, "cpu.usage": 0.75}

    def test_flatten_bool_value(self):
        """Test flattening boolean attributes."""
        attributes = [
            {"key": "is.success", "value": {"boolValue": True}},
            {"key": "is.cached", "value": {"boolValue": False}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"is.success": True, "is.cached": False}

    def test_flatten_mixed_value_types(self):
        """Test flattening attributes with mixed value types."""
        attributes = [
            {"key": "service.name", "value": {"stringValue": "my-service"}},
            {"key": "http.status_code", "value": {"intValue": 200}},
            {"key": "response.time", "value": {"doubleValue": 123.456}},
            {"key": "is.success", "value": {"boolValue": True}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {
            "service.name": "my-service",
            "http.status_code": 200,
            "response.time": 123.456,
            "is.success": True,
        }

    def test_flatten_empty_attributes(self):
        """Test flattening empty attribute list."""
        result = flatten_otlp_attributes([])
        assert result == {}

    def test_flatten_attribute_with_missing_value(self):
        """Test flattening attribute with missing value field."""
        attributes = [
            {"key": "missing.value"},
            {"key": "valid.value", "value": {"stringValue": "test"}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"missing.value": None, "valid.value": "test"}

    def test_flatten_attribute_with_empty_value_object(self):
        """Test flattening attribute with empty value object."""
        attributes = [
            {"key": "empty.value", "value": {}},
            {"key": "valid.value", "value": {"stringValue": "test"}},
        ]
        result = flatten_otlp_attributes(attributes)

        assert result == {"empty.value": None, "valid.value": "test"}


class TestBuildHierarchy:
    """Tests for build_hierarchy function."""

    def test_build_hierarchy_single_root(self):
        """Test building hierarchy with a single root span."""
        spans = [
            TraceRun(
                id="root",
                name="RootSpan",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            )
        ]

        result = build_hierarchy(spans)

        assert result == spans  # Same list returned
        assert spans[0].dotted_order == "0000"

    def test_build_hierarchy_parent_child(self):
        """Test building hierarchy with parent and child spans."""
        spans = [
            TraceRun(
                id="child",
                name="ChildSpan",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="root",
                name="RootSpan",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        # Find spans by ID
        root = next(s for s in spans if s.id == "root")
        child = next(s for s in spans if s.id == "child")

        assert root.dotted_order == "0000"
        assert child.dotted_order == "0000.0000"

    def test_build_hierarchy_multiple_children(self):
        """Test building hierarchy with multiple children."""
        spans = [
            TraceRun(
                id="root",
                name="RootSpan",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child1",
                name="Child1",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child2",
                name="Child2",
                run_type=RunType.TOOL,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 4, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        root = next(s for s in spans if s.id == "root")
        child1 = next(s for s in spans if s.id == "child1")
        child2 = next(s for s in spans if s.id == "child2")

        assert root.dotted_order == "0000"
        # Children sorted by start_time
        assert child1.dotted_order == "0000.0000"
        assert child2.dotted_order == "0000.0001"

    def test_build_hierarchy_deep_nesting(self):
        """Test building hierarchy with deeply nested spans."""
        spans = [
            TraceRun(
                id="root",
                name="Root",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 4, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child",
                name="Child",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="grandchild",
                name="Grandchild",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id="child",
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        root = next(s for s in spans if s.id == "root")
        child = next(s for s in spans if s.id == "child")
        grandchild = next(s for s in spans if s.id == "grandchild")

        assert root.dotted_order == "0000"
        assert child.dotted_order == "0000.0000"
        assert grandchild.dotted_order == "0000.0000.0000"

    def test_build_hierarchy_multiple_roots(self):
        """Test building hierarchy with multiple root spans."""
        spans = [
            TraceRun(
                id="root1",
                name="Root1",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="root2",
                name="Root2",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        root1 = next(s for s in spans if s.id == "root1")
        root2 = next(s for s in spans if s.id == "root2")

        # Roots sorted by start_time
        assert root1.dotted_order == "0000"
        assert root2.dotted_order == "0001"

    def test_build_hierarchy_complex_tree(self):
        """Test building hierarchy with a complex tree structure."""
        spans = [
            TraceRun(
                id="root",
                name="Root",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child1",
                name="Child1",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child2",
                name="Child2",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 6, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 9, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="grandchild1a",
                name="Grandchild1a",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id="child1",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="grandchild1b",
                name="Grandchild1b",
                run_type=RunType.TOOL,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 4, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                error=None,
                parent_run_id="child1",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="grandchild2",
                name="Grandchild2",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 7, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 8, tzinfo=timezone.utc),
                error=None,
                parent_run_id="child2",
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        # Verify the hierarchy
        span_by_id = {s.id: s for s in spans}

        assert span_by_id["root"].dotted_order == "0000"
        assert span_by_id["child1"].dotted_order == "0000.0000"
        assert span_by_id["child2"].dotted_order == "0000.0001"
        assert span_by_id["grandchild1a"].dotted_order == "0000.0000.0000"
        assert span_by_id["grandchild1b"].dotted_order == "0000.0000.0001"
        assert span_by_id["grandchild2"].dotted_order == "0000.0001.0000"

    def test_build_hierarchy_sorting_by_start_time(self):
        """Test that children are sorted by start_time for deterministic ordering."""
        spans = [
            TraceRun(
                id="root",
                name="Root",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="",
            ),
            # Add children in reverse chronological order to test sorting
            TraceRun(
                id="child3",
                name="Child3",
                run_type=RunType.TOOL,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 4, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child2",
                name="Child2",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
            TraceRun(
                id="child1",
                name="Child1",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                error=None,
                parent_run_id="root",
                trace_id="trace-1",
                dotted_order="",
            ),
        ]

        build_hierarchy(spans)

        span_by_id = {s.id: s for s in spans}

        # Despite being added in reverse order, they should be sorted by start_time
        assert span_by_id["child1"].dotted_order == "0000.0000"
        assert span_by_id["child2"].dotted_order == "0000.0001"
        assert span_by_id["child3"].dotted_order == "0000.0002"

    def test_build_hierarchy_empty_list(self):
        """Test building hierarchy with empty span list."""
        spans = []
        result = build_hierarchy(spans)

        assert result == []
