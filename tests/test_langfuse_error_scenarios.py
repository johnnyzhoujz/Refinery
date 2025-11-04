"""
Langfuse-specific error scenario tests.

Tests realistic user mistakes and edge cases when working with Langfuse traces.
These test real errors users would encounter, not just toy examples.
"""

import pytest
import json
import asyncio
from pathlib import Path

from refinery.integrations.local_file_provider import LocalFileTraceProvider
from refinery.integrations.langfuse_parser import parse_langfuse_trace


class TestLangfuseFileFormatErrors:
    """Test handling of malformed or invalid Langfuse trace files."""

    def test_langfuse_trace_missing_id(self, tmp_path):
        """Test trace without ID field - common copy-paste error."""
        trace = {
            "observations": [
                {
                    "id": "obs-1",
                    "name": "Test",
                    "type": "SPAN",
                    "startTime": "2024-01-01T00:00:00Z",
                }
            ]
        }
        file_path = tmp_path / "bad_trace.json"
        file_path.write_text(json.dumps(trace))

        provider = LocalFileTraceProvider(str(file_path))

        with pytest.raises(ValueError, match="trace.*id|missing.*id"):
            asyncio.run(provider.fetch_trace())

    def test_langfuse_trace_missing_observations(self, tmp_path):
        """Test trace without observations field - export error."""
        trace = {"id": "trace-123", "name": "My Trace"}  # Missing observations
        file_path = tmp_path / "no_obs_trace.json"
        file_path.write_text(json.dumps(trace))

        provider = LocalFileTraceProvider(str(file_path))

        with pytest.raises((ValueError, KeyError), match="observations"):
            asyncio.run(provider.fetch_trace())

    def test_langfuse_observation_missing_type(self):
        """Test observation without type field - gets skipped."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Test Span",
                    # Missing 'type' field
                    "startTime": "2024-01-01T00:00:00Z",
                }
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should skip malformed observation
        assert len(trace.runs) == 0

    def test_langfuse_malformed_timestamp(self):
        """Test observation with invalid ISO timestamp."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Test",
                    "type": "SPAN",
                    "startTime": "not-a-timestamp",  # Invalid
                }
            ],
        }

        with pytest.raises(ValueError, match="timestamp|time|parse|invalid"):
            parse_langfuse_trace(trace_data)

    def test_langfuse_wrong_json_structure_looks_like_otlp(self, tmp_path):
        """Test when user provides OTLP file thinking it's Langfuse."""
        # OTLP structure
        otlp_trace = {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": "abc123",
                                    "spanId": "span-1",
                                    "name": "test",
                                    "startTimeUnixNano": "1609459200000000000",
                                    "endTimeUnixNano": "1609459205000000000",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        file_path = tmp_path / "otlp_misidentified.json"
        file_path.write_text(json.dumps(otlp_trace))

        provider = LocalFileTraceProvider(str(file_path))

        # Should detect this is OTLP format, not Langfuse
        trace = asyncio.run(provider.fetch_trace())
        assert trace.metadata.get("format") == "opentelemetry"


class TestLangfuseDataQualityErrors:
    """Test handling of low-quality or edge case Langfuse data."""

    def test_langfuse_all_observations_malformed(self):
        """Test when ALL observations are invalid - realistic data export bug."""
        trace_data = {
            "id": "trace-123",
            "observations": [
                {"id": "obs-1"},  # Missing required fields
                {"name": "Test"},  # Missing id
                {},  # Completely empty
                {"id": "obs-2", "name": "Test2"},  # Missing type and timestamps
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should succeed but with 0 runs
        assert trace.trace_id == "trace-123"
        assert len(trace.runs) == 0

    def test_langfuse_circular_parent_relationships(self):
        """Test circular parent references - data corruption."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Span 1",
                    "type": "SPAN",
                    "parentObservationId": "span-2",  # Points to span-2
                    "startTime": "2024-01-01T00:00:00Z",
                },
                {
                    "id": "span-2",
                    "name": "Span 2",
                    "type": "SPAN",
                    "parentObservationId": "span-1",  # Points back to span-1
                    "startTime": "2024-01-01T00:00:01Z",
                },
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should handle gracefully - both treated as roots
        assert len(trace.runs) == 2
        root_runs = [r for r in trace.runs if r.parent_run_id is None]
        assert len(root_runs) == 2  # Both should be roots

    def test_langfuse_parent_id_not_found(self):
        """Test observation references non-existent parent - broken export."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Orphan Span",
                    "type": "SPAN",
                    "parentObservationId": "nonexistent-parent",  # Doesn't exist
                    "startTime": "2024-01-01T00:00:00Z",
                }
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should treat as root observation
        assert len(trace.runs) == 1
        assert trace.runs[0].parent_run_id is None

    def test_langfuse_duplicate_observation_ids(self):
        """Test duplicate IDs - data export bug."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "duplicate-id",
                    "name": "First",
                    "type": "SPAN",
                    "startTime": "2024-01-01T00:00:00Z",
                },
                {
                    "id": "duplicate-id",  # Same ID!
                    "name": "Second",
                    "type": "SPAN",
                    "startTime": "2024-01-01T00:00:01Z",
                },
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should handle - likely uses first occurrence
        assert len(trace.runs) >= 1
        # Both might be included or second might override first
        assert len(trace.runs) <= 2


class TestLangfuseFileSystemErrors:
    """Test file system related errors."""

    def test_langfuse_file_with_spaces_in_path(self, tmp_path):
        """Test handling paths with spaces - common user mistake."""
        # Create directory with spaces
        dir_with_spaces = tmp_path / "My Documents"
        dir_with_spaces.mkdir()

        trace = {"id": "trace-123", "observations": []}
        file_path = dir_with_spaces / "langfuse trace.json"
        file_path.write_text(json.dumps(trace))

        # Should handle path with spaces correctly
        provider = LocalFileTraceProvider(str(file_path))
        result = asyncio.run(provider.fetch_trace())

        assert result.trace_id == "trace-123"

    def test_langfuse_file_wrong_extension_but_valid_json(self, tmp_path):
        """Test .txt file that's actually valid JSON - user confusion."""
        trace = {
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
        file_path = tmp_path / "trace.txt"  # Wrong extension
        file_path.write_text(json.dumps(trace))

        # Should still work - we parse by content, not extension
        provider = LocalFileTraceProvider(str(file_path))
        result = asyncio.run(provider.fetch_trace())

        assert len(result.runs) == 1

    def test_langfuse_very_large_trace(self, tmp_path):
        """Test trace with many observations - performance concern."""
        observations = []
        for i in range(1000):  # 1000 observations
            observations.append(
                {
                    "id": f"span-{i}",
                    "name": f"Span {i}",
                    "type": "SPAN",
                    "startTime": f"2024-01-01T{i//3600:02d}:{(i//60)%60:02d}:{i%60:02d}Z",
                }
            )

        trace = {"id": "large-trace", "observations": observations}
        file_path = tmp_path / "large_trace.json"
        file_path.write_text(json.dumps(trace))

        provider = LocalFileTraceProvider(str(file_path))

        # Should handle large traces
        import time

        start = time.time()
        result = asyncio.run(provider.fetch_trace())
        duration = time.time() - start

        assert len(result.runs) == 1000
        assert duration < 5.0  # Should complete in under 5 seconds


class TestLangfuseObservationTypeHandling:
    """Test handling of various observation types and edge cases."""

    def test_langfuse_unknown_observation_type(self):
        """Test observation with unknown type - future compatibility."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "span-1",
                    "name": "Unknown Type",
                    "type": "FUTURE_TYPE",  # Not in current mapping
                    "startTime": "2024-01-01T00:00:00Z",
                }
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should default to CHAIN or skip gracefully
        assert len(trace.runs) == 1
        # Should have some run_type assigned
        assert trace.runs[0].run_type is not None

    def test_langfuse_mixed_valid_and_invalid_observations(self):
        """Test trace with mix of valid and invalid observations."""
        trace_data = {
            "id": "trace-1",
            "observations": [
                {
                    "id": "valid-1",
                    "name": "Valid Span",
                    "type": "SPAN",
                    "startTime": "2024-01-01T00:00:00Z",
                },
                {"id": "invalid-1"},  # Missing required fields
                {
                    "id": "valid-2",
                    "name": "Valid Gen",
                    "type": "GENERATION",
                    "startTime": "2024-01-01T00:00:01Z",
                },
                {},  # Completely invalid
                {
                    "id": "valid-3",
                    "name": "Valid Event",
                    "type": "EVENT",
                    "startTime": "2024-01-01T00:00:02Z",
                },
            ],
        }

        trace = parse_langfuse_trace(trace_data)

        # Should parse all valid observations, skip invalid
        assert len(trace.runs) == 3
        assert trace.runs[0].id == "valid-1"
        assert trace.runs[1].id == "valid-2"
        assert trace.runs[2].id == "valid-3"
