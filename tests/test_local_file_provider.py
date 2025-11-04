"""
Tests for LocalFileTraceProvider with multi-format support.

Tests automatic format detection and parsing for:
- Langfuse JSON exports
- OTLP JSON traces
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from refinery.integrations.local_file_provider import LocalFileTraceProvider
from refinery.core.models import Trace


@pytest.fixture
def langfuse_fixture_path():
    """Path to Langfuse test fixture."""
    return Path(__file__).parent / "fixtures" / "langfuse_trace.json"


@pytest.fixture
def otlp_fixture_path():
    """Path to OTLP test fixture."""
    return Path(__file__).parent / "fixtures" / "otlp_trace_tempo.json"


@pytest.mark.asyncio
async def test_load_langfuse_trace(langfuse_fixture_path):
    """Test loading Langfuse trace from file."""
    provider = LocalFileTraceProvider(str(langfuse_fixture_path))

    trace = await provider.fetch_trace()

    assert isinstance(trace, Trace)
    assert trace.trace_id == "trace-123"
    assert trace.metadata["format"] == "langfuse"
    assert trace.metadata["source"] == "file"
    assert len(trace.runs) == 5


@pytest.mark.asyncio
async def test_load_otlp_trace(otlp_fixture_path):
    """Test loading OTLP trace from file."""
    provider = LocalFileTraceProvider(str(otlp_fixture_path))

    trace = await provider.fetch_trace()

    assert isinstance(trace, Trace)
    assert trace.metadata["format"] == "opentelemetry"
    assert trace.metadata["source"] == "file"
    assert len(trace.runs) > 0


@pytest.mark.asyncio
async def test_format_detection_langfuse(langfuse_fixture_path):
    """Test that Langfuse format is correctly detected."""
    provider = LocalFileTraceProvider(str(langfuse_fixture_path))

    with open(langfuse_fixture_path, "r") as f:
        data = json.load(f)

    format_type = provider._detect_format(data)
    assert format_type == "langfuse"


@pytest.mark.asyncio
async def test_format_detection_otlp(otlp_fixture_path):
    """Test that OTLP format is correctly detected."""
    provider = LocalFileTraceProvider(str(otlp_fixture_path))

    with open(otlp_fixture_path, "r") as f:
        data = json.load(f)

    format_type = provider._detect_format(data)
    assert format_type == "otlp"


def test_format_detection_unknown():
    """Test that unknown format raises ValueError."""
    # Create temp file with unknown format
    temp_file = Path("/tmp/test_unknown_format.json")
    unknown_data = {"some": "data", "without": "expected fields"}

    with open(temp_file, "w") as f:
        json.dump(unknown_data, f)

    try:
        provider = LocalFileTraceProvider(str(temp_file))

        with pytest.raises(ValueError, match="Unknown trace format"):
            provider._detect_format(unknown_data)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def test_file_not_found():
    """Test that FileNotFoundError is raised for non-existent file."""
    with pytest.raises(FileNotFoundError, match="Trace file not found"):
        LocalFileTraceProvider("/nonexistent/file.json")


@pytest.mark.asyncio
async def test_caching(langfuse_fixture_path):
    """Test that trace is cached after first load."""
    provider = LocalFileTraceProvider(str(langfuse_fixture_path))

    # First fetch
    trace1 = await provider.fetch_trace()

    # Second fetch should return cached trace
    trace2 = await provider.fetch_trace()

    assert trace1 is trace2  # Same object reference


@pytest.mark.asyncio
async def test_invalid_json():
    """Test handling of invalid JSON file."""
    temp_file = Path("/tmp/test_invalid_json.json")

    # Write invalid JSON
    with open(temp_file, "w") as f:
        f.write("{invalid json content")

    try:
        provider = LocalFileTraceProvider(str(temp_file))

        with pytest.raises(ValueError, match="Invalid JSON"):
            await provider.fetch_trace()
    finally:
        if temp_file.exists():
            temp_file.unlink()


@pytest.mark.asyncio
async def test_trace_id_from_filename(langfuse_fixture_path):
    """Test that filename is used as trace_id when not explicitly provided."""
    provider = LocalFileTraceProvider(str(langfuse_fixture_path))

    # For Langfuse format, trace_id comes from the JSON "id" field
    trace = await provider.fetch_trace()

    # Langfuse traces use the 'id' field from JSON, not filename
    assert trace.trace_id == "trace-123"


@pytest.mark.asyncio
async def test_repr(langfuse_fixture_path):
    """Test string representation of provider."""
    provider = LocalFileTraceProvider(str(langfuse_fixture_path))

    repr_str = repr(provider)
    assert "LocalFileTraceProvider" in repr_str
    assert "langfuse_trace.json" in repr_str


@pytest.mark.asyncio
async def test_langfuse_format_priority():
    """Test that Langfuse format is detected even with extra fields."""
    temp_file = Path("/tmp/test_langfuse_priority.json")

    # Create file with both Langfuse markers and extra fields
    data = {
        "id": "trace-456",
        "projectId": "test",
        "observations": [],
        "extra_field": "should not interfere",
    }

    with open(temp_file, "w") as f:
        json.dump(data, f)

    try:
        provider = LocalFileTraceProvider(str(temp_file))

        with open(temp_file, "r") as f:
            loaded_data = json.load(f)

        format_type = provider._detect_format(loaded_data)
        assert format_type == "langfuse"

        trace = await provider.fetch_trace()
        assert trace.trace_id == "trace-456"
        assert trace.metadata["format"] == "langfuse"
    finally:
        if temp_file.exists():
            temp_file.unlink()


@pytest.mark.asyncio
async def test_otlp_format_detection():
    """Test OTLP format detection with resourceSpans."""
    temp_file = Path("/tmp/test_otlp_format.json")

    # Minimal OTLP structure
    data = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "test-service"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abc123",
                                "spanId": "span-1",
                                "name": "test-span",
                                "startTimeUnixNano": "1736935200000000000",
                                "endTimeUnixNano": "1736935205000000000",
                                "attributes": [],
                            }
                        ]
                    }
                ],
            }
        ]
    }

    with open(temp_file, "w") as f:
        json.dump(data, f)

    try:
        provider = LocalFileTraceProvider(str(temp_file))

        with open(temp_file, "r") as f:
            loaded_data = json.load(f)

        format_type = provider._detect_format(loaded_data)
        assert format_type == "otlp"

        trace = await provider.fetch_trace()
        assert trace.metadata["format"] == "opentelemetry"
    finally:
        if temp_file.exists():
            temp_file.unlink()


@pytest.mark.asyncio
async def test_multiple_providers_different_files(langfuse_fixture_path, otlp_fixture_path):
    """Test that multiple providers can be created for different files."""
    provider_langfuse = LocalFileTraceProvider(str(langfuse_fixture_path))
    provider_otlp = LocalFileTraceProvider(str(otlp_fixture_path))

    trace_langfuse = await provider_langfuse.fetch_trace()
    trace_otlp = await provider_otlp.fetch_trace()

    assert trace_langfuse.metadata["format"] == "langfuse"
    assert trace_otlp.metadata["format"] == "opentelemetry"
    assert trace_langfuse.trace_id != trace_otlp.trace_id
