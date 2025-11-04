"""
Additional error scenario tests identified during validation.

Tests handling of corrupted/invalid data, edge cases, and error conditions.
"""

import pytest
import json
from pathlib import Path
import asyncio

from refinery.integrations.local_file_provider import LocalFileTraceProvider
from refinery.integrations.langfuse_parser import parse_langfuse_trace
from refinery.integrations.otlp_parser import parse_otlp_trace


class TestMalformedData:
    """Test handling of corrupted/invalid data."""

    def test_malformed_json(self, tmp_path):
        """Test handling of corrupted JSON files."""
        bad_json = tmp_path / "bad_trace.json"
        bad_json.write_text('{"trace": "incomplete...')

        provider = LocalFileTraceProvider(str(bad_json))

        with pytest.raises(ValueError, match="Invalid JSON"):
            asyncio.run(provider.fetch_trace())

    def test_langfuse_circular_hierarchy(self):
        """Test handling of circular parent-child relationships in Langfuse traces."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Span 1",
                    "type": "SPAN",
                    "parentObservationId": "span-2",
                    "startTime": "2024-01-01T00:00:00Z",
                },
                {
                    "id": "span-2",
                    "name": "Span 2",
                    "type": "SPAN",
                    "parentObservationId": "span-1",
                    "startTime": "2024-01-01T00:00:01Z",
                },
            ],
        }

        # Should not crash - hierarchy building should handle this gracefully
        trace = parse_langfuse_trace(trace_data)
        assert len(trace.runs) == 2
        # Both will be treated as roots since they reference each other

    def test_langfuse_missing_required_fields(self):
        """Test handling of traces with missing required fields."""
        incomplete_trace = {
            "id": "trace-1",
            "observations": [
                {"id": "span-1"}  # Missing type, name, timestamps
            ],
        }

        # Should skip malformed observation, return trace with 0 runs
        trace = parse_langfuse_trace(incomplete_trace)
        assert len(trace.runs) == 0

    def test_langfuse_all_observations_malformed(self):
        """Test handling when ALL observations are malformed."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {"id": "span-1"},  # Missing required fields
                {"id": "span-2"},  # Missing required fields
                {},  # Completely empty
            ],
        }

        # Should return trace with empty runs list
        trace = parse_langfuse_trace(trace_data)
        assert len(trace.runs) == 0
        assert trace.trace_id == "trace-1"

    def test_otlp_missing_required_fields(self):
        """Test OTLP parser with missing required span fields."""
        incomplete_otlp = {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": "span-1",
                                    "name": "test",
                                    # Missing startTimeUnixNano and endTimeUnixNano
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        with pytest.raises((KeyError, ValueError)):
            parse_otlp_trace(incomplete_otlp, "test-trace")

    def test_otlp_empty_resourcespans(self):
        """Test OTLP parser with empty resourceSpans array."""
        empty_otlp = {"resourceSpans": []}

        with pytest.raises(ValueError, match="No spans found"):
            parse_otlp_trace(empty_otlp, "test-trace")

    def test_otlp_no_resourcespans_key(self):
        """Test OTLP parser with missing resourceSpans key."""
        invalid_otlp = {"data": "some other structure"}

        with pytest.raises(ValueError, match="No spans found"):
            parse_otlp_trace(invalid_otlp, "test-trace")


class TestFilePermissions:
    """Test file system error handling."""

    def test_nonexistent_file(self):
        """Test handling of missing files."""
        with pytest.raises(FileNotFoundError, match="Trace file not found"):
            LocalFileTraceProvider("/nonexistent/path.json")

    def test_directory_instead_of_file(self, tmp_path):
        """Test handling when directory provided instead of file."""
        # Create directory
        dir_path = tmp_path / "dir"
        dir_path.mkdir()

        with pytest.raises(FileNotFoundError):
            provider = LocalFileTraceProvider(str(dir_path))

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        provider = LocalFileTraceProvider(str(empty_file))

        with pytest.raises(ValueError, match="Invalid JSON"):
            asyncio.run(provider.fetch_trace())

    def test_non_json_file(self, tmp_path):
        """Test handling of non-JSON file."""
        text_file = tmp_path / "text.json"
        text_file.write_text("This is plain text, not JSON")

        provider = LocalFileTraceProvider(str(text_file))

        with pytest.raises(ValueError, match="Invalid JSON"):
            asyncio.run(provider.fetch_trace())


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_langfuse_very_deep_hierarchy(self):
        """Test handling of very deep nesting (100 levels)."""
        observations = []
        for i in range(100):
            obs = {
                "id": f"span-{i}",
                "name": f"Span {i}",
                "type": "SPAN",
                "startTime": f"2024-01-01T{i//60:02d}:{i%60:02d}:00Z",
            }
            if i > 0:
                obs["parentObservationId"] = f"span-{i-1}"
            observations.append(obs)

        trace_data = {"id": "trace-deep", "observations": observations}

        trace = parse_langfuse_trace(trace_data)
        assert len(trace.runs) == 100
        # Check dotted_order shows proper nesting
        deepest = [r for r in trace.runs if r.id == "span-99"][0]
        assert deepest.dotted_order.count(".") == 99  # 99 levels deep

    def test_langfuse_many_siblings(self):
        """Test handling of many sibling nodes (100 children of same parent)."""
        observations = [
            {
                "id": "root",
                "name": "Root",
                "type": "SPAN",
                "startTime": "2024-01-01T00:00:00Z",
            }
        ]

        for i in range(100):
            observations.append(
                {
                    "id": f"child-{i}",
                    "name": f"Child {i}",
                    "type": "SPAN",
                    "parentObservationId": "root",
                    "startTime": f"2024-01-01T00:00:{i//60:02d}:{i%60:02d}Z",
                }
            )

        trace_data = {"id": "trace-wide", "observations": observations}

        trace = parse_langfuse_trace(trace_data)
        assert len(trace.runs) == 101
        # All children should have dotted_order like 0000.0000, 0000.0001, etc.
        children = [r for r in trace.runs if r.parent_run_id == "root"]
        assert len(children) == 100

    def test_otlp_trace_with_no_gen_ai_attributes(self):
        """Test OTLP trace without any gen_ai.* attributes (just regular spans)."""
        trace_data = {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": "span-1",
                                    "name": "http.request",
                                    "startTimeUnixNano": "1609459200000000000",
                                    "endTimeUnixNano": "1609459205000000000",
                                    "kind": "SPAN_KIND_CLIENT",
                                    "attributes": [
                                        {
                                            "key": "http.method",
                                            "value": {"stringValue": "POST"},
                                        }
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        trace = parse_otlp_trace(trace_data, "test-trace")
        assert len(trace.runs) == 1
        assert trace.runs[0].run_type.value == "tool"  # SPAN_KIND_CLIENT → TOOL

    def test_format_detection_ambiguous_file(self, tmp_path):
        """Test format detection with file that has both langfuse and otlp markers (invalid)."""
        # This shouldn't happen in practice, but test priority
        ambiguous_file = tmp_path / "ambiguous.json"
        ambiguous_file.write_text(
            json.dumps(
                {
                    "id": "trace-1",
                    "observations": [],  # Langfuse marker
                    "resourceSpans": [],  # OTLP marker
                }
            )
        )

        provider = LocalFileTraceProvider(str(ambiguous_file))
        trace = asyncio.run(provider.fetch_trace())

        # Should prioritize Langfuse format (checked first)
        assert trace.metadata["format"] == "langfuse"

    def test_langfuse_invalid_timestamp_format(self):
        """Test handling of invalid ISO timestamp formats."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Span 1",
                    "type": "SPAN",
                    "startTime": "not-a-timestamp",  # Invalid format
                }
            ],
        }

        with pytest.raises(ValueError):
            parse_langfuse_trace(trace_data)

    @pytest.mark.asyncio
    async def test_trace_caching_persists_across_calls(self, tmp_path):
        """Test that trace caching works and returns same object."""
        trace_file = tmp_path / "test_trace.json"
        trace_file.write_text(
            json.dumps(
                {
                    "id": "trace-123",
                    "observations": [
                        {
                            "id": "span-1",
                            "name": "Test",
                            "type": "SPAN",
                            "startTime": "2024-01-01T00:00:00Z",
                        }
                    ],
                }
            )
        )

        provider = LocalFileTraceProvider(str(trace_file))

        # First fetch
        trace1 = await provider.fetch_trace()
        # Second fetch
        trace2 = await provider.fetch_trace()

        # Should be same object (cached)
        assert trace1 is trace2

    def test_unknown_observation_type(self):
        """Test handling of unknown Langfuse observation type."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Unknown Type",
                    "type": "UNKNOWN_TYPE",  # Not in mapping
                    "startTime": "2024-01-01T00:00:00Z",
                }
            ],
        }

        trace = parse_langfuse_trace(trace_data)
        assert len(trace.runs) == 1
        # Should default to CHAIN for unknown types
        assert trace.runs[0].run_type.value == "chain"
