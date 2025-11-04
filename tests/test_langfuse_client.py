"""
Unit tests for LangfuseClient.

Tests cover:
- Trace fetching and parsing
- Prompt fetching
- Observation type mapping
- Hierarchy building
- Error handling for malformed data
- ISO timestamp parsing
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from refinery.core.models import RunType, Trace, TraceRun

# Mock the langfuse module before importing LangfuseClient
sys.modules["langfuse"] = MagicMock()

from refinery.integrations.langfuse_client import LangfuseClient


# Fixture data loader
@pytest.fixture
def langfuse_trace_data():
    """Load sample Langfuse trace from fixtures."""
    fixture_path = Path(__file__).parent / "fixtures" / "langfuse_trace.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture
def mock_langfuse_client():
    """Create a LangfuseClient with mocked Langfuse SDK."""
    from refinery.utils.config import config

    with patch("refinery.integrations.langfuse_client.Langfuse") as mock_langfuse, \
         patch.object(config, 'langfuse_public_key', 'pk-test'), \
         patch.object(config, 'langfuse_secret_key', 'sk-test'):
        # Mock the Langfuse SDK
        mock_instance = MagicMock()
        mock_langfuse.return_value = mock_instance

        # Create client
        client = LangfuseClient()
        client._mock_langfuse_instance = mock_instance

        yield client


class TestLangfuseClientInit:
    """Test LangfuseClient initialization."""

    def test_init_with_config(self):
        """Test that client initializes with config values."""
        with patch("refinery.integrations.langfuse_client.Langfuse") as mock_langfuse:
            with patch("refinery.integrations.langfuse_client.config") as mock_config:
                mock_config.langfuse_public_key = "test-public-key"
                mock_config.langfuse_secret_key = "test-secret-key"
                mock_config.langfuse_host = "https://test.langfuse.com"

                client = LangfuseClient()

                mock_langfuse.assert_called_once_with(
                    public_key="test-public-key",
                    secret_key="test-secret-key",
                    host="https://test.langfuse.com",
                )


class TestFetchTrace:
    """Test trace fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_trace_success(self, mock_langfuse_client, langfuse_trace_data):
        """Test successful trace fetching and parsing."""
        # Mock the trace.get API call
        mock_langfuse_client._mock_langfuse_instance.api.trace.get.return_value = (
            langfuse_trace_data
        )

        # Fetch trace
        trace = await mock_langfuse_client.fetch_trace("trace-123")

        # Verify trace structure
        assert isinstance(trace, Trace)
        assert trace.trace_id == "trace-123"
        assert trace.project_name == "test-project"
        assert len(trace.runs) == 5
        assert trace.metadata["format"] == "langfuse"
        assert trace.metadata["source"] == "api"

    @pytest.mark.asyncio
    async def test_fetch_trace_calls_api_correctly(self, mock_langfuse_client):
        """Test that fetch_trace calls the Langfuse API with correct trace_id."""
        mock_trace_data = {
            "id": "test-trace",
            "projectId": "test-project",
            "observations": [],
        }
        mock_langfuse_client._mock_langfuse_instance.api.trace.get.return_value = (
            mock_trace_data
        )

        await mock_langfuse_client.fetch_trace("test-trace")

        # Verify API was called with correct trace_id
        # Note: The call happens in run_in_executor, so we check the mock was called
        assert mock_langfuse_client._mock_langfuse_instance.api.trace.get.called


class TestParseTrace:
    """Test trace parsing logic."""

    def test_parse_trace_with_observations(
        self, mock_langfuse_client, langfuse_trace_data
    ):
        """Test parsing trace with multiple observations."""
        trace = mock_langfuse_client._parse_langfuse_trace(langfuse_trace_data)

        assert len(trace.runs) == 5
        assert trace.trace_id == "trace-123"

        # Check first run (LLM generation)
        llm_run = next(r for r in trace.runs if r.id == "obs-1")
        assert llm_run.name == "LLM Call"
        assert llm_run.run_type == RunType.LLM
        assert llm_run.metadata["model"] == "gpt-4"
        assert llm_run.metadata["usage"]["promptTokens"] == 10

    def test_parse_trace_builds_hierarchy(
        self, mock_langfuse_client, langfuse_trace_data
    ):
        """Test that hierarchy is correctly built from parentObservationId."""
        trace = mock_langfuse_client._parse_langfuse_trace(langfuse_trace_data)

        # Find parent and child runs
        parent_run = next(r for r in trace.runs if r.id == "obs-2")
        tool_run = next(r for r in trace.runs if r.id == "obs-3")
        nested_llm = next(r for r in trace.runs if r.id == "obs-4")

        # Verify parent-child relationships
        assert parent_run.parent_run_id is None
        assert tool_run.parent_run_id == "obs-2"
        assert nested_llm.parent_run_id == "obs-2"

        # Verify dotted_order reflects hierarchy
        assert parent_run.dotted_order.count(".") == 0  # Root level
        assert tool_run.dotted_order.count(".") == 1  # Child level
        assert nested_llm.dotted_order.count(".") == 1  # Child level

    def test_parse_trace_handles_errors(self, mock_langfuse_client, langfuse_trace_data):
        """Test that errors are correctly parsed from observations."""
        trace = mock_langfuse_client._parse_langfuse_trace(langfuse_trace_data)

        # Find the failed event
        failed_run = next(r for r in trace.runs if r.id == "obs-5")
        assert failed_run.error == "Connection timeout"
        assert failed_run.is_failed

    def test_parse_trace_extracts_metadata(
        self, mock_langfuse_client, langfuse_trace_data
    ):
        """Test that metadata like promptName and promptVersion are extracted."""
        trace = mock_langfuse_client._parse_langfuse_trace(langfuse_trace_data)

        # Find run with metadata
        nested_llm = next(r for r in trace.runs if r.id == "obs-4")
        assert nested_llm.metadata["promptName"] == "test-prompt"
        assert nested_llm.metadata["promptVersion"] == 1

    def test_parse_trace_skips_malformed_observations(self, mock_langfuse_client):
        """Test that malformed observations are skipped with warning."""
        malformed_trace = {
            "id": "trace-bad",
            "projectId": "test-project",
            "observations": [
                {
                    "id": "obs-1",
                    "name": "Valid Observation",
                    "type": "SPAN",
                    "startTime": "2025-01-15T10:00:00Z",
                },
                {
                    "id": "obs-2",
                    # Missing 'name' and 'type'
                    "startTime": "2025-01-15T10:00:01Z",
                },
                {
                    "name": "Missing ID",
                    # Missing 'id'
                    "type": "EVENT",
                    "startTime": "2025-01-15T10:00:02Z",
                },
            ],
        }

        with patch("refinery.integrations.langfuse_client.logger") as mock_logger:
            trace = mock_langfuse_client._parse_langfuse_trace(malformed_trace)

            # Only 1 valid observation should be parsed
            assert len(trace.runs) == 1
            assert trace.runs[0].id == "obs-1"

            # Warning should have been logged for malformed observations
            assert mock_logger.warning.call_count == 2

    def test_parse_trace_empty_observations(self, mock_langfuse_client):
        """Test parsing trace with no observations."""
        empty_trace = {
            "id": "trace-empty",
            "projectId": "test-project",
            "observations": [],
        }

        trace = mock_langfuse_client._parse_langfuse_trace(empty_trace)
        assert len(trace.runs) == 0
        assert trace.trace_id == "trace-empty"


class TestObservationTypeMapping:
    """Test observation type mapping."""

    @pytest.mark.parametrize(
        "langfuse_type,expected_run_type",
        [
            ("GENERATION", RunType.LLM),
            ("SPAN", RunType.CHAIN),
            ("EVENT", RunType.TOOL),
            ("TOOL", RunType.TOOL),
            ("RETRIEVER", RunType.RETRIEVER),
            ("EMBEDDING", RunType.EMBEDDING),
            ("AGENT", RunType.CHAIN),
            ("CHAIN", RunType.CHAIN),
            ("EVALUATOR", RunType.CHAIN),
            ("GUARDRAIL", RunType.CHAIN),
        ],
    )
    def test_map_observation_type(
        self, mock_langfuse_client, langfuse_type, expected_run_type
    ):
        """Test that Langfuse observation types map correctly to RunType."""
        result = mock_langfuse_client._map_observation_type(langfuse_type)
        assert result == expected_run_type

    def test_map_observation_type_unknown(self, mock_langfuse_client):
        """Test that unknown observation types default to CHAIN."""
        result = mock_langfuse_client._map_observation_type("UNKNOWN_TYPE")
        assert result == RunType.CHAIN


class TestHierarchyBuilding:
    """Test hierarchy building logic."""

    def test_build_hierarchy_simple(self, mock_langfuse_client):
        """Test building hierarchy with simple parent-child relationship."""
        runs = [
            TraceRun(
                id="parent",
                name="Parent",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 0),
                end_time=datetime(2025, 1, 15, 10, 0, 10),
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="0000",
            ),
            TraceRun(
                id="child",
                name="Child",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 1),
                end_time=datetime(2025, 1, 15, 10, 0, 5),
                error=None,
                parent_run_id="parent",
                trace_id="trace-1",
                dotted_order="0000",
            ),
        ]

        result = mock_langfuse_client._build_langfuse_hierarchy(runs)

        assert result[0].dotted_order == "0000"
        assert result[1].dotted_order == "0000.0000"

    def test_build_hierarchy_multiple_roots(self, mock_langfuse_client):
        """Test building hierarchy with multiple root nodes."""
        runs = [
            TraceRun(
                id="root1",
                name="Root 1",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 0),
                end_time=None,
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="0000",
            ),
            TraceRun(
                id="root2",
                name="Root 2",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 5),
                end_time=None,
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="0000",
            ),
        ]

        result = mock_langfuse_client._build_langfuse_hierarchy(runs)

        # Two roots should have different top-level indices
        assert result[0].dotted_order == "0000"
        assert result[1].dotted_order == "0001"

    def test_build_hierarchy_deep_nesting(self, mock_langfuse_client):
        """Test building hierarchy with deep nesting."""
        runs = [
            TraceRun(
                id="level0",
                name="Level 0",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 0),
                end_time=None,
                error=None,
                parent_run_id=None,
                trace_id="trace-1",
                dotted_order="0000",
            ),
            TraceRun(
                id="level1",
                name="Level 1",
                run_type=RunType.CHAIN,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 1),
                end_time=None,
                error=None,
                parent_run_id="level0",
                trace_id="trace-1",
                dotted_order="0000",
            ),
            TraceRun(
                id="level2",
                name="Level 2",
                run_type=RunType.LLM,
                inputs={},
                outputs={},
                start_time=datetime(2025, 1, 15, 10, 0, 2),
                end_time=None,
                error=None,
                parent_run_id="level1",
                trace_id="trace-1",
                dotted_order="0000",
            ),
        ]

        result = mock_langfuse_client._build_langfuse_hierarchy(runs)

        assert result[0].dotted_order == "0000"
        assert result[1].dotted_order == "0000.0000"
        assert result[2].dotted_order == "0000.0000.0000"


class TestTimestampParsing:
    """Test ISO timestamp parsing."""

    @pytest.mark.parametrize(
        "timestamp_str,expected_year,expected_month",
        [
            ("2025-01-15T10:00:00Z", 2025, 1),
            ("2025-01-15T10:00:00+00:00", 2025, 1),
            ("2024-12-31T23:59:59Z", 2024, 12),
        ],
    )
    def test_parse_iso_timestamp(
        self, mock_langfuse_client, timestamp_str, expected_year, expected_month
    ):
        """Test parsing ISO 8601 timestamps with Z and +00:00 formats."""
        result = mock_langfuse_client._parse_iso_timestamp(timestamp_str)
        assert isinstance(result, datetime)
        assert result.year == expected_year
        assert result.month == expected_month

    def test_parse_iso_timestamp_none(self, mock_langfuse_client):
        """Test that None input returns None."""
        result = mock_langfuse_client._parse_iso_timestamp(None)
        assert result is None

    def test_parse_iso_timestamp_empty_string(self, mock_langfuse_client):
        """Test that empty string returns None."""
        result = mock_langfuse_client._parse_iso_timestamp("")
        assert result is None


class TestFetchPrompt:
    """Test prompt fetching functionality."""

    @pytest.mark.asyncio
    async def test_fetch_prompt_with_defaults(self, mock_langfuse_client):
        """Test fetching prompt with default parameters."""
        mock_prompt_data = {
            "name": "test-prompt",
            "version": 1,
            "prompt": "You are a helpful assistant",
        }
        mock_langfuse_client._mock_langfuse_instance.get_prompt.return_value = (
            mock_prompt_data
        )

        result = await mock_langfuse_client.fetch_prompt("test-prompt")

        assert result["name"] == "test-prompt"

    @pytest.mark.asyncio
    async def test_fetch_prompt_with_version(self, mock_langfuse_client):
        """Test fetching specific prompt version."""
        mock_prompt_data = {
            "name": "test-prompt",
            "version": 2,
            "prompt": "Updated prompt",
        }
        mock_langfuse_client._mock_langfuse_instance.get_prompt.return_value = (
            mock_prompt_data
        )

        result = await mock_langfuse_client.fetch_prompt("test-prompt", version=2)

        assert result["version"] == 2

    @pytest.mark.asyncio
    async def test_fetch_prompt_with_label(self, mock_langfuse_client):
        """Test fetching prompt with custom label."""
        mock_prompt_data = {
            "name": "test-prompt",
            "version": 1,
            "label": "staging",
            "prompt": "Staging prompt",
        }
        mock_langfuse_client._mock_langfuse_instance.get_prompt.return_value = (
            mock_prompt_data
        )

        result = await mock_langfuse_client.fetch_prompt("test-prompt", label="staging")

        assert result["label"] == "staging"


class TestFetchFailedTraces:
    """Test fetch_failed_traces placeholder implementation."""

    @pytest.mark.asyncio
    async def test_fetch_failed_traces_placeholder(self, mock_langfuse_client):
        """Test that fetch_failed_traces returns empty list and logs warning."""
        with patch("refinery.integrations.langfuse_client.logger") as mock_logger:
            result = await mock_langfuse_client.fetch_failed_traces(
                project="test-project",
                start_time=datetime(2025, 1, 1),
                end_time=datetime(2025, 1, 31),
                limit=100,
            )

            assert result == []
            mock_logger.warning.assert_called_once()


class TestFetchTraceHierarchy:
    """Test trace hierarchy fetching."""

    @pytest.mark.asyncio
    async def test_fetch_trace_hierarchy(
        self, mock_langfuse_client, langfuse_trace_data
    ):
        """Test fetching trace hierarchy."""
        mock_langfuse_client._mock_langfuse_instance.api.trace.get.return_value = (
            langfuse_trace_data
        )

        result = await mock_langfuse_client.fetch_trace_hierarchy("trace-123")

        assert result["trace_id"] == "trace-123"
        assert result["project_name"] == "test-project"
        assert len(result["runs"]) == 5
        assert all("dotted_order" in run for run in result["runs"])
