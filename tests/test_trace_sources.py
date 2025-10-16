"""
Tests for trace source abstraction (LocalFileSource and LangSmithAPISource).
"""

import json
from pathlib import Path

import pytest

from refinery.core.models import Trace
from refinery.integrations.trace_sources import LocalFileSource, TraceSource


def test_local_file_source_implements_interface():
    """Verify LocalFileSource implements TraceSource interface."""
    assert issubclass(LocalFileSource, TraceSource)


def test_local_file_source_file_not_found():
    """Test LocalFileSource raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        LocalFileSource("/nonexistent/path/trace.json")


@pytest.mark.asyncio
async def test_local_file_source_parses_demo_trace():
    """Test LocalFileSource successfully parses examples/demo_trace.json."""
    # Get path to demo trace
    demo_trace_path = Path(__file__).parent.parent / "examples" / "demo_trace.json"

    # Create source
    source = LocalFileSource(str(demo_trace_path))

    # Fetch trace
    trace = await source.fetch_trace()

    # Verify trace structure
    assert isinstance(trace, Trace)
    assert trace.trace_id == "demo-trace-001"
    assert trace.project_name == "demo-project"
    assert len(trace.runs) == 5

    # Verify failed runs are detected
    failed_runs = trace.get_failed_runs()
    assert len(failed_runs) == 1
    assert failed_runs[0].id == "run-005"
    assert "Validation failed" in failed_runs[0].error


@pytest.mark.asyncio
async def test_local_file_source_validates_schema():
    """Test LocalFileSource validates required fields."""
    import tempfile

    # Create invalid trace file (missing required fields)
    invalid_data = {"some_field": "value"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(invalid_data, f)
        temp_path = f.name

    try:
        source = LocalFileSource(temp_path)
        with pytest.raises(ValueError, match="missing required field"):
            await source.fetch_trace()
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_local_file_source_invalid_json():
    """Test LocalFileSource handles invalid JSON gracefully."""
    import tempfile

    # Create file with invalid JSON
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid json content")
        temp_path = f.name

    try:
        source = LocalFileSource(temp_path)
        with pytest.raises(ValueError, match="Invalid JSON"):
            await source.fetch_trace()
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_local_file_source_metadata():
    """Test LocalFileSource adds correct metadata to trace."""
    demo_trace_path = Path(__file__).parent.parent / "examples" / "demo_trace.json"
    source = LocalFileSource(str(demo_trace_path))

    trace = await source.fetch_trace()

    # Verify source metadata
    assert trace.metadata["source"] == "local_file"
    assert "file_path" in trace.metadata
    assert trace.metadata["total_runs"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
