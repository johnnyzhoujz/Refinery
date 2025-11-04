"""
Tests for Langfuse file parser.

Tests parsing of Langfuse JSON exports to Trace objects, including:
- Observation type mapping
- Hierarchy building from parentObservationId
- ISO timestamp parsing
- Error handling
- Metadata extraction
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from refinery.integrations.langfuse_parser import (
    parse_langfuse_trace,
    _map_observation_type,
    _parse_iso_timestamp,
    _build_hierarchy,
)
from refinery.core.models import Trace, TraceRun, RunType


@pytest.fixture
def langfuse_fixture_path():
    """Path to Langfuse test fixture."""
    return Path(__file__).parent / "fixtures" / "langfuse_trace.json"


@pytest.fixture
def langfuse_data(langfuse_fixture_path):
    """Load Langfuse test fixture data."""
    with open(langfuse_fixture_path, "r") as f:
        return json.load(f)


def test_parse_langfuse_trace_basic(langfuse_data):
    """Test basic parsing of Langfuse trace."""
    trace = parse_langfuse_trace(langfuse_data)

    # Verify trace structure
    assert isinstance(trace, Trace)
    assert trace.trace_id == "trace-123"
    assert trace.project_name == "test-project"
    assert len(trace.runs) == 5  # All observations parsed

    # Verify metadata
    assert trace.metadata["format"] == "langfuse"
    assert trace.metadata["source"] == "file"


def test_observation_type_mapping():
    """Test mapping of Langfuse observation types to RunType."""
    assert _map_observation_type("GENERATION") == RunType.LLM
    assert _map_observation_type("SPAN") == RunType.CHAIN
    assert _map_observation_type("EVENT") == RunType.TOOL
    assert _map_observation_type("TOOL") == RunType.TOOL
    assert _map_observation_type("RETRIEVER") == RunType.RETRIEVER
    assert _map_observation_type("EMBEDDING") == RunType.EMBEDDING
    assert _map_observation_type("AGENT") == RunType.CHAIN
    assert _map_observation_type("CHAIN") == RunType.CHAIN
    assert _map_observation_type("EVALUATOR") == RunType.CHAIN
    assert _map_observation_type("GUARDRAIL") == RunType.CHAIN

    # Test unknown type defaults to CHAIN
    assert _map_observation_type("UNKNOWN_TYPE") == RunType.CHAIN


def test_hierarchy_building(langfuse_data):
    """Test hierarchy building from parentObservationId."""
    trace = parse_langfuse_trace(langfuse_data)

    # Find runs by ID
    runs_by_id = {run.id: run for run in trace.runs}

    # Root observations (no parent)
    obs_1 = runs_by_id["obs-1"]
    obs_2 = runs_by_id["obs-2"]
    obs_5 = runs_by_id["obs-5"]

    # Child observations
    obs_3 = runs_by_id["obs-3"]  # child of obs-2
    obs_4 = runs_by_id["obs-4"]  # child of obs-2

    # Verify root runs have simple dotted_order
    assert obs_1.dotted_order.count(".") == 0  # Root level
    assert obs_2.dotted_order.count(".") == 0  # Root level
    assert obs_5.dotted_order.count(".") == 0  # Root level

    # Verify child runs have nested dotted_order
    assert obs_3.dotted_order.count(".") == 1  # One level deep
    assert obs_4.dotted_order.count(".") == 1  # One level deep
    assert obs_3.parent_run_id == "obs-2"
    assert obs_4.parent_run_id == "obs-2"


def test_timestamp_parsing():
    """Test ISO 8601 timestamp parsing."""
    # Test with Z timezone
    ts1 = _parse_iso_timestamp("2025-01-15T10:00:00Z")
    assert isinstance(ts1, datetime)
    assert ts1.tzinfo == timezone.utc

    # Test with +00:00 timezone
    ts2 = _parse_iso_timestamp("2025-01-15T10:00:00+00:00")
    assert isinstance(ts2, datetime)
    assert ts2.tzinfo == timezone.utc

    # Test with None
    ts3 = _parse_iso_timestamp(None)
    assert ts3 is None


def test_error_extraction(langfuse_data):
    """Test error extraction from observations with ERROR level."""
    trace = parse_langfuse_trace(langfuse_data)

    # Find the failed event (obs-5)
    failed_run = next(run for run in trace.runs if run.id == "obs-5")

    assert failed_run.error == "Connection timeout"
    assert failed_run.name == "Failed Event"
    assert failed_run.run_type == RunType.TOOL  # EVENT maps to TOOL


def test_metadata_extraction(langfuse_data):
    """Test metadata extraction from observations."""
    trace = parse_langfuse_trace(langfuse_data)

    # Find observation with metadata (obs-4)
    nested_llm = next(run for run in trace.runs if run.id == "obs-4")

    assert nested_llm.metadata["model"] == "gpt-3.5-turbo"
    assert nested_llm.metadata["usage"]["promptTokens"] == 5
    assert nested_llm.metadata["usage"]["completionTokens"] == 3
    assert nested_llm.metadata["promptName"] == "test-prompt"
    assert nested_llm.metadata["promptVersion"] == 1


def test_inputs_outputs_extraction(langfuse_data):
    """Test extraction of inputs and outputs."""
    trace = parse_langfuse_trace(langfuse_data)

    # Find LLM call (obs-1)
    llm_run = next(run for run in trace.runs if run.id == "obs-1")

    assert "messages" in llm_run.inputs
    assert llm_run.inputs["messages"][0]["role"] == "system"
    assert llm_run.inputs["messages"][0]["content"] == "You are helpful"
    assert llm_run.outputs["content"] == "Hi there!"


def test_missing_required_fields():
    """Test handling of observations with missing required fields."""
    data = {
        "id": "trace-999",
        "projectId": "test",
        "observations": [
            {
                "id": "obs-valid",
                "name": "Valid",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
            },
            {
                # Missing 'name' field
                "id": "obs-invalid-1",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
            },
            {
                # Missing 'type' field
                "id": "obs-invalid-2",
                "name": "Invalid",
                "startTime": "2025-01-15T10:00:00Z",
            },
        ],
    }

    trace = parse_langfuse_trace(data)

    # Only valid observation should be parsed
    assert len(trace.runs) == 1
    assert trace.runs[0].id == "obs-valid"


def test_missing_trace_id():
    """Test error when trace ID is missing."""
    data = {
        "projectId": "test",
        "observations": [],
    }

    with pytest.raises(ValueError, match="missing required field: id"):
        parse_langfuse_trace(data)


def test_empty_observations():
    """Test parsing trace with no observations."""
    data = {
        "id": "trace-empty",
        "projectId": "test",
        "observations": [],
    }

    trace = parse_langfuse_trace(data)

    assert trace.trace_id == "trace-empty"
    assert len(trace.runs) == 0
    assert trace.project_name == "test"


def test_missing_optional_fields():
    """Test handling of observations with missing optional fields."""
    data = {
        "id": "trace-minimal",
        "projectId": "test",
        "observations": [
            {
                "id": "obs-minimal",
                "name": "Minimal",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
                # Missing: endTime, input, output, model, usage, metadata
            }
        ],
    }

    trace = parse_langfuse_trace(data)

    run = trace.runs[0]
    assert run.id == "obs-minimal"
    assert run.end_time is None
    assert run.inputs == {}
    assert run.outputs == {}
    assert run.error is None
    assert run.metadata["model"] is None
    assert run.metadata["usage"] == {}


def test_hierarchy_with_multiple_levels():
    """Test hierarchy building with multiple nesting levels."""
    data = {
        "id": "trace-nested",
        "projectId": "test",
        "observations": [
            {
                "id": "root",
                "name": "Root",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
            },
            {
                "id": "child1",
                "name": "Child 1",
                "type": "SPAN",
                "parentObservationId": "root",
                "startTime": "2025-01-15T10:00:01Z",
            },
            {
                "id": "grandchild1",
                "name": "Grandchild 1",
                "type": "SPAN",
                "parentObservationId": "child1",
                "startTime": "2025-01-15T10:00:02Z",
            },
            {
                "id": "child2",
                "name": "Child 2",
                "type": "SPAN",
                "parentObservationId": "root",
                "startTime": "2025-01-15T10:00:03Z",
            },
        ],
    }

    trace = parse_langfuse_trace(data)
    runs_by_id = {run.id: run for run in trace.runs}

    # Verify hierarchy levels
    root = runs_by_id["root"]
    child1 = runs_by_id["child1"]
    grandchild1 = runs_by_id["grandchild1"]
    child2 = runs_by_id["child2"]

    assert root.dotted_order.count(".") == 0  # Level 0
    assert child1.dotted_order.count(".") == 1  # Level 1
    assert grandchild1.dotted_order.count(".") == 2  # Level 2
    assert child2.dotted_order.count(".") == 1  # Level 1

    # Verify parent relationships
    assert root.parent_run_id is None
    assert child1.parent_run_id == "root"
    assert grandchild1.parent_run_id == "child1"
    assert child2.parent_run_id == "root"


def test_deterministic_sibling_ordering():
    """Test that sibling runs are ordered deterministically by start_time."""
    data = {
        "id": "trace-siblings",
        "projectId": "test",
        "observations": [
            {
                "id": "parent",
                "name": "Parent",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
            },
            {
                "id": "child-c",
                "name": "Child C",
                "type": "SPAN",
                "parentObservationId": "parent",
                "startTime": "2025-01-15T10:00:03Z",  # Latest
            },
            {
                "id": "child-a",
                "name": "Child A",
                "type": "SPAN",
                "parentObservationId": "parent",
                "startTime": "2025-01-15T10:00:01Z",  # Earliest
            },
            {
                "id": "child-b",
                "name": "Child B",
                "type": "SPAN",
                "parentObservationId": "parent",
                "startTime": "2025-01-15T10:00:02Z",  # Middle
            },
        ],
    }

    trace = parse_langfuse_trace(data)
    runs_by_id = {run.id: run for run in trace.runs}

    # Verify ordering by dotted_order
    child_a = runs_by_id["child-a"]
    child_b = runs_by_id["child-b"]
    child_c = runs_by_id["child-c"]

    # Children should be ordered by start_time (A < B < C)
    assert child_a.dotted_order < child_b.dotted_order < child_c.dotted_order


def test_trace_time_range():
    """Test that trace start_time and end_time reflect all observations."""
    data = {
        "id": "trace-times",
        "projectId": "test",
        "observations": [
            {
                "id": "early",
                "name": "Early",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:00Z",
                "endTime": "2025-01-15T10:00:02Z",
            },
            {
                "id": "late",
                "name": "Late",
                "type": "SPAN",
                "startTime": "2025-01-15T10:00:05Z",
                "endTime": "2025-01-15T10:00:10Z",
            },
        ],
    }

    trace = parse_langfuse_trace(data)

    # Trace should span from earliest start to latest end
    expected_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    expected_end = datetime(2025, 1, 15, 10, 0, 10, tzinfo=timezone.utc)

    assert trace.start_time == expected_start
    assert trace.end_time == expected_end
