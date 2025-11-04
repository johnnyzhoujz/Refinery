"""
CLI smoke tests for Langfuse workflows.

Tests real user workflows with the Refinery CLI to ensure
end-to-end functionality works as expected.
"""

import pytest
import json
import os
import yaml
from pathlib import Path
from datetime import datetime, timezone
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock, MagicMock

from refinery.cli import main
from refinery.core.models import (
    Trace, TraceRun, RunType, CompleteAnalysis, Diagnosis,
    TraceAnalysis, GapAnalysis, Hypothesis, FailureType, Confidence
)


# Mock helper functions
def create_mock_trace():
    """Create a mock Trace object for testing."""
    return Trace(
        trace_id="test-trace-123",
        project_name="test-project",
        runs=[
            TraceRun(
                id="run-1",
                name="test-run",
                run_type=RunType.LLM,
                inputs={"messages": [{"role": "user", "content": "test"}]},
                outputs={"content": "response"},
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                error=None,
                parent_run_id=None,
                trace_id="test-trace-123",
                dotted_order="0000",
                metadata={"model": "gpt-4"},
            )
        ],
        start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
        metadata={"format": "langfuse"},
    )


def create_mock_analysis():
    """Create a mock CompleteAnalysis object for testing."""
    return CompleteAnalysis(
        trace_analysis=TraceAnalysis(
            trace_id="test-trace-123",
            execution_flow=["Step 1: LLM call", "Step 2: Response"],
            context_at_each_step={"run-1": {"model": "gpt-4"}},
            data_transformations=[],
            error_propagation_path=None,
            identified_issues=["Test issue"],
            metadata={},
        ),
        gap_analysis=GapAnalysis(
            behavioral_differences=["Difference 1"],
            missing_context=["Missing context"],
            incorrect_assumptions=[],
            suggested_focus_areas=["Focus area 1"],
            metadata={},
        ),
        diagnosis=Diagnosis(
            failure_type=FailureType.PROMPT_ISSUE,
            root_cause="Test root cause - prompt needs improvement",
            evidence=["Evidence 1: Model output was generic", "Evidence 2: Context missing"],
            affected_components=["llm_call"],
            confidence=Confidence.HIGH,
            detailed_analysis="The prompt lacks specific instructions leading to generic output.",
            remediations=["Add specific instructions", "Provide more context"],
            next_actions=["Test with improved prompt", "Validate output quality"],
            top_findings=["Finding 1: Prompt too vague", "Finding 2: Missing examples"],
            metadata={},
        ),
    )


def create_mock_hypotheses():
    """Create mock Hypothesis objects for testing."""
    return [
        Hypothesis(
            id="hyp-1",
            description="Improve prompt specificity",
            rationale="Generic prompts lead to generic outputs",
            proposed_changes=["Add specific instructions", "Include examples"],
            confidence=Confidence.MEDIUM,
            risks=["May increase token usage"],
            example_before="Summarize this text.",
            example_after="Summarize this text in 3 bullet points, focusing on key technical details.",
        ),
        Hypothesis(
            id="hyp-2",
            description="Add context about user intent",
            rationale="Model needs to understand the use case",
            proposed_changes=["Add context preamble"],
            confidence=Confidence.HIGH,
            risks=["Minimal"],
            example_before="Process this request.",
            example_after="You are a technical documentation assistant. Process this request by...",
        ),
    ]


@pytest.fixture
def cli_runner():
    """Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def langfuse_trace_file(tmp_path):
    """Create a minimal valid Langfuse trace file."""
    trace = {
        "id": "test-trace-123",
        "observations": [
            {
                "id": "gen-1",
                "name": "ChatCompletion",
                "type": "GENERATION",
                "startTime": "2024-01-01T00:00:00Z",
                "endTime": "2024-01-01T00:00:05Z",
                "model": "gpt-4",
                "input": {"messages": [{"role": "user", "content": "Hello"}]},
                "output": {"content": "Hi there!"},
                "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
            },
            {
                "id": "span-1",
                "name": "ProcessRequest",
                "type": "SPAN",
                "startTime": "2024-01-01T00:00:00Z",
                "endTime": "2024-01-01T00:00:06Z",
                "parentObservationId": None,
            },
        ],
    }
    file_path = tmp_path / "langfuse_trace.json"
    file_path.write_text(json.dumps(trace))
    return str(file_path)


@pytest.fixture
def empty_langfuse_trace(tmp_path):
    """Create a Langfuse trace with no observations."""
    trace = {"id": "empty-trace", "observations": []}
    file_path = tmp_path / "empty_trace.json"
    file_path.write_text(json.dumps(trace))
    return str(file_path)


@pytest.fixture
def invalid_langfuse_trace(tmp_path):
    """Create an invalid Langfuse trace (missing required fields)."""
    trace = {"observations": [{"id": "obs-1"}]}  # Missing trace id
    file_path = tmp_path / "invalid_trace.json"
    file_path.write_text(json.dumps(trace))
    return str(file_path)


@pytest.fixture
def mock_orchestrator():
    """Mock the orchestrator to avoid real LLM calls."""
    with patch("refinery.cli.RefineryOrchestrator") as mock_orch_class:
        mock_orch = AsyncMock()
        mock_orch_class.return_value = mock_orch

        # Mock analysis results
        mock_orch.analyze_failure.return_value = {
            "summary": "Test analysis",
            "findings": ["Finding 1", "Finding 2"],
        }
        mock_orch.generate_hypotheses_from_trace.return_value = []

        yield mock_orch


class TestCLIVersion:
    """Test version and help commands."""

    def test_cli_version(self, cli_runner):
        """Test --version flag."""
        result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "Refinery v0.1.0" in result.output

    def test_cli_help(self, cli_runner):
        """Test --help flag."""
        result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Refinery" in result.output
        assert "chat" in result.output

    def test_chat_help(self, cli_runner):
        """Test chat --help."""
        result = cli_runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0
        assert "--trace-file" in result.output
        assert "--provider" in result.output


class TestCLIValidation:
    """Test CLI argument validation."""

    def test_chat_missing_trace_source(self, cli_runner):
        """Test error when no trace source provided."""
        result = cli_runner.invoke(main, ["chat"])
        assert result.exit_code == 1
        assert "Must provide either --trace-id or --trace-file" in result.output

    def test_chat_both_trace_sources(self, cli_runner, langfuse_trace_file):
        """Test error when both trace sources provided."""
        result = cli_runner.invoke(
            main, ["chat", "--trace-id", "abc123", "--trace-file", langfuse_trace_file]
        )
        assert result.exit_code == 1
        assert "Cannot provide both" in result.output

    def test_chat_file_not_found(self, cli_runner):
        """Test error when trace file doesn't exist."""
        result = cli_runner.invoke(
            main,
            ["chat", "--trace-file", "/nonexistent/trace.json"],
            catch_exceptions=True,
        )
        # Click should catch this before our code runs
        assert result.exit_code != 0


class TestLangfuseFileWorkflows:
    """Test Langfuse file-based workflows with proper mocking."""

    @patch("refinery.utils.file_helpers.load_files_from_path")
    @patch("refinery.core.orchestrator.create_orchestrator")
    @patch("refinery.core.trace_source_factory.TraceSourceFactory.create_for_cli")
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-fake-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-fake",
        "LANGFUSE_SECRET_KEY": "sk-test-fake"
    })
    def test_chat_with_langfuse_file_basic(
        self,
        mock_factory,
        mock_create_orch,
        mock_load_files,
        cli_runner,
        langfuse_trace_file,
        tmp_path
    ):
        """Test basic Langfuse file workflow loads trace successfully."""
        # Setup mock trace provider
        mock_provider = AsyncMock()
        mock_provider.fetch_trace = AsyncMock(return_value=create_mock_trace())
        mock_factory.return_value = mock_provider

        # Setup mock orchestrator
        mock_orch = AsyncMock()
        mock_orch._trace_cache = {}  # Critical: CLI injects trace into this cache
        mock_orch.analyze_failure = AsyncMock(return_value=create_mock_analysis())
        mock_orch.generate_hypotheses_from_trace = AsyncMock(return_value=[])
        mock_create_orch.return_value = mock_orch

        # Mock file loading (no prompts/evals provided)
        mock_load_files.return_value = {}

        # Run CLI command
        result = cli_runner.invoke(main, [
            "chat",
            "--trace-file", str(langfuse_trace_file),
            "--provider", "langfuse"
        ])

        # Assertions
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Analysis complete" in result.output or "Root Cause" in result.output
        mock_provider.fetch_trace.assert_called_once()
        mock_orch.analyze_failure.assert_called_once()

    @patch("refinery.utils.file_helpers.load_files_from_path")
    @patch("refinery.core.orchestrator.create_orchestrator")
    @patch("refinery.core.trace_source_factory.TraceSourceFactory.create_for_cli")
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-fake-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-fake",
        "LANGFUSE_SECRET_KEY": "sk-test-fake"
    })
    def test_chat_langfuse_with_yaml_output(
        self,
        mock_factory,
        mock_create_orch,
        mock_load_files,
        cli_runner,
        langfuse_trace_file,
        tmp_path
    ):
        """Test YAML output format is accepted (tests flag handling, not export functionality)."""
        # Setup mock trace provider
        mock_provider = AsyncMock()
        mock_provider.fetch_trace = AsyncMock(return_value=create_mock_trace())
        mock_factory.return_value = mock_provider

        # Setup mock orchestrator (no hypotheses to avoid export step)
        mock_orch = AsyncMock()
        mock_orch._trace_cache = {}
        mock_orch.analyze_failure = AsyncMock(return_value=create_mock_analysis())
        mock_orch.generate_hypotheses_from_trace = AsyncMock(return_value=[])  # Empty to skip export
        mock_create_orch.return_value = mock_orch

        # Mock file loading
        mock_load_files.return_value = {}

        # Output file path
        output_file = tmp_path / "output.yaml"

        # Run CLI command with YAML output
        result = cli_runner.invoke(main, [
            "chat",
            "--trace-file", str(langfuse_trace_file),
            "--provider", "langfuse",
            "--out", str(output_file),
            "--format", "yaml"
        ])

        # Assertions - verify workflow completed and flags were accepted
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Analysis complete" in result.output or "Root Cause" in result.output
        mock_provider.fetch_trace.assert_called_once()
        mock_orch.analyze_failure.assert_called_once()

    @patch("refinery.utils.file_helpers.load_files_from_path")
    @patch("refinery.core.orchestrator.create_orchestrator")
    @patch("refinery.core.trace_source_factory.TraceSourceFactory.create_for_cli")
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-fake-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-fake",
        "LANGFUSE_SECRET_KEY": "sk-test-fake"
    })
    def test_chat_langfuse_with_json_output(
        self,
        mock_factory,
        mock_create_orch,
        mock_load_files,
        cli_runner,
        langfuse_trace_file,
        tmp_path
    ):
        """Test JSON output format is accepted (tests flag handling, not export functionality)."""
        # Setup mock trace provider
        mock_provider = AsyncMock()
        mock_provider.fetch_trace = AsyncMock(return_value=create_mock_trace())
        mock_factory.return_value = mock_provider

        # Setup mock orchestrator (no hypotheses to avoid export step)
        mock_orch = AsyncMock()
        mock_orch._trace_cache = {}
        mock_orch.analyze_failure = AsyncMock(return_value=create_mock_analysis())
        mock_orch.generate_hypotheses_from_trace = AsyncMock(return_value=[])  # Empty to skip export
        mock_create_orch.return_value = mock_orch

        # Mock file loading
        mock_load_files.return_value = {}

        # Output file path
        output_file = tmp_path / "output.json"

        # Run CLI command with JSON output
        result = cli_runner.invoke(main, [
            "chat",
            "--trace-file", str(langfuse_trace_file),
            "--provider", "langfuse",
            "--out", str(output_file),
            "--format", "json"
        ])

        # Assertions - verify workflow completed and flags were accepted
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Analysis complete" in result.output or "Root Cause" in result.output
        mock_provider.fetch_trace.assert_called_once()
        mock_orch.analyze_failure.assert_called_once()

    @patch("refinery.utils.file_helpers.load_files_from_path")
    @patch("refinery.core.orchestrator.create_orchestrator")
    @patch("refinery.core.trace_source_factory.TraceSourceFactory.create_for_cli")
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test-fake-key",
        "LANGFUSE_PUBLIC_KEY": "pk-test-fake",
        "LANGFUSE_SECRET_KEY": "sk-test-fake"
    })
    def test_chat_langfuse_with_debug(
        self,
        mock_factory,
        mock_create_orch,
        mock_load_files,
        cli_runner,
        langfuse_trace_file
    ):
        """Test debug mode enables verbose logging."""
        # Setup mock trace provider
        mock_provider = AsyncMock()
        mock_provider.fetch_trace = AsyncMock(return_value=create_mock_trace())
        mock_factory.return_value = mock_provider

        # Setup mock orchestrator
        mock_orch = AsyncMock()
        mock_orch._trace_cache = {}
        mock_orch.analyze_failure = AsyncMock(return_value=create_mock_analysis())
        mock_orch.generate_hypotheses_from_trace = AsyncMock(return_value=[])
        mock_create_orch.return_value = mock_orch

        # Mock file loading
        mock_load_files.return_value = {}

        # Run CLI command with debug flag
        result = cli_runner.invoke(main, [
            "--debug",
            "chat",
            "--trace-file", str(langfuse_trace_file),
            "--provider", "langfuse"
        ])

        # Assertions
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Debug mode is enabled via flag, workflow should complete
        mock_provider.fetch_trace.assert_called_once()
        mock_orch.analyze_failure.assert_called_once()


class TestLangfuseErrorHandling:
    """Test error handling for Langfuse traces."""

    def test_chat_langfuse_directory_instead_of_file(self, cli_runner, tmp_path):
        """Test error when directory provided instead of file."""
        # Create a directory
        dir_path = tmp_path / "not_a_file"
        dir_path.mkdir()

        result = cli_runner.invoke(
            main,
            ["chat", "--trace-file", str(dir_path)],
            catch_exceptions=True,
        )

        # Should fail with clear error
        assert result.exit_code != 0
