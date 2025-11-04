"""
Unit tests for LangfusePromptExtractor.

Tests all extraction scenarios including managed prompts via Prompt API
and ad-hoc prompts from observation payloads.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import pytest

from refinery.core.models import Trace, TraceRun, RunType, PromptData
from refinery.integrations.prompt_extractors.langfuse_extractor import LangfusePromptExtractor


def create_trace_run(
    id: str,
    name: str,
    run_type: RunType,
    trace_id: str,
    dotted_order: str,
    inputs=None,
    metadata=None,
    **kwargs
):
    """Helper to create TraceRun with defaults for testing."""
    return TraceRun(
        id=id,
        name=name,
        run_type=run_type,
        inputs=inputs or {},
        outputs=kwargs.get('outputs'),
        start_time=kwargs.get('start_time', datetime.now()),
        end_time=kwargs.get('end_time'),
        error=kwargs.get('error'),
        parent_run_id=kwargs.get('parent_run_id'),
        trace_id=trace_id,
        dotted_order=dotted_order,
        metadata=metadata or {}
    )


class TestLangfusePromptExtractor:
    """Test suite for LangfusePromptExtractor."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LangfuseClient."""
        client = MagicMock()
        client.fetch_prompt = AsyncMock()
        return client

    @pytest.fixture
    def base_trace(self):
        """Create a base trace for testing."""
        return Trace(
            trace_id="test-trace-123",
            project_name="test-project",
            runs=[],
            start_time=datetime.now(),
            end_time=None,
            metadata={}
        )

    @pytest.mark.asyncio
    async def test_managed_prompt_chat_type(self, mock_client, base_trace):
        """Test extraction from Prompt Management API with chat type."""
        # Setup mock to return chat prompt
        mock_client.fetch_prompt.return_value = {
            "type": "chat",
            "prompt": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"}
            ]
        }

        # Create LLM run with promptName metadata
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={
                "promptName": "test-prompt",
                "promptVersion": 2
            },
            inputs={"messages": [{"role": "user", "content": "This should be ignored"}]}
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify API was called with correct parameters
        mock_client.fetch_prompt.assert_called_once_with(
            name="test-prompt",
            version=2
        )

        # Verify extracted prompts
        assert len(result.system_prompts) == 1
        assert "You are helpful" in result.system_prompts
        assert len(result.user_prompts) == 3  # user + assistant + user messages
        assert "Hello" in result.user_prompts
        assert "How are you?" in result.user_prompts
        assert "Hi there!" in result.user_prompts  # Assistant messages are included as user prompts

    @pytest.mark.asyncio
    async def test_managed_prompt_text_type(self, mock_client, base_trace):
        """Test extraction from Prompt Management API with text type."""
        # Setup mock to return text prompt
        mock_client.fetch_prompt.return_value = {
            "type": "text",
            "prompt": "Generate a summary of the following text"
        }

        # Create LLM run with promptName metadata
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={
                "promptName": "summarizer",
                "promptVersion": None  # Test with no version
            }
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify API was called
        mock_client.fetch_prompt.assert_called_once_with(
            name="summarizer",
            version=None
        )

        # Verify extracted prompts
        assert len(result.system_prompts) == 0
        assert len(result.user_prompts) == 1
        assert "Generate a summary of the following text" in result.user_prompts

    @pytest.mark.asyncio
    async def test_managed_prompt_api_failure_fallback(self, mock_client, base_trace):
        """Test fallback to observation parsing when Prompt API fails."""
        # Setup mock to raise exception
        mock_client.fetch_prompt.side_effect = Exception("API connection failed")

        # Create LLM run with promptName and fallback data
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            start_time=datetime.now(),
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={
                "promptName": "test-prompt",
                "promptVersion": 1
            },
            inputs={
                "messages": [
                    {"role": "system", "content": "Fallback system prompt"},
                    {"role": "user", "content": "Fallback user message"}
                ]
            }
        )
        base_trace.runs = [run]

        # Extract prompts with logging capture
        extractor = LangfusePromptExtractor(mock_client)

        # Mock logger to verify warning was logged
        import structlog.testing
        with structlog.testing.capture_logs() as cap_logs:
            result = await extractor.extract(base_trace)

        # Verify API was attempted
        mock_client.fetch_prompt.assert_called_once()

        # Verify warning was logged
        assert any("Failed to fetch managed prompt" in log["event"] for log in cap_logs)

        # Verify fallback extraction worked
        assert len(result.system_prompts) == 1
        assert "Fallback system prompt" in result.system_prompts
        assert len(result.user_prompts) == 1
        assert "Fallback user message" in result.user_prompts

    @pytest.mark.asyncio
    async def test_adhoc_prompts_messages_array(self, mock_client, base_trace):
        """Test extraction from observation inputs with messages array."""
        # Create LLM run without promptName (ad-hoc prompt)
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            start_time=datetime.now(),
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={},
            inputs={
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "What is Python?"},
                    {"role": "assistant", "content": "Python is a programming language"},
                    {"role": "user", "content": "Tell me more"}
                ]
            }
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify no API call was made
        mock_client.fetch_prompt.assert_not_called()

        # Verify extracted prompts
        assert len(result.system_prompts) == 1
        assert "You are a helpful assistant" in result.system_prompts
        assert len(result.user_prompts) == 3  # user + assistant + user messages
        assert "What is Python?" in result.user_prompts
        assert "Tell me more" in result.user_prompts
        # Assistant messages are included as user prompts (non-system)
        assert "Python is a programming language" in result.user_prompts

    @pytest.mark.asyncio
    async def test_adhoc_prompts_simple_string(self, mock_client, base_trace):
        """Test extraction from observation inputs with simple prompt string."""
        # Create LLM run with simple prompt string
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            start_time=datetime.now(),
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={},
            inputs={
                "prompt": "Translate this to French: Hello world"
            }
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify no API call was made
        mock_client.fetch_prompt.assert_not_called()

        # Verify extracted prompts
        assert len(result.system_prompts) == 0
        assert len(result.user_prompts) == 1
        assert "Translate this to French: Hello world" in result.user_prompts

    @pytest.mark.asyncio
    async def test_empty_prompts(self, mock_client, base_trace):
        """Test extraction when no prompts are found."""
        # Create LLM run with no prompt data
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            start_time=datetime.now(),
            trace_id="test-trace-123",
            dotted_order="0000",
            metadata={},
            inputs={}
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify returns PromptData (not None)
        assert isinstance(result, PromptData)
        assert len(result.system_prompts) == 0
        assert len(result.user_prompts) == 0

    @pytest.mark.asyncio
    async def test_mixed_runs_only_llm_processed(self, mock_client, base_trace):
        """Test trace with mixed run types - only LLM runs are processed."""
        # Create mixed runs
        runs = [
            create_trace_run(
                id="run-1",
                name="Chain",
                run_type=RunType.CHAIN,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0000",
                inputs={"prompt": "This should be ignored"}
            ),
            create_trace_run(
                id="run-2",
                name="LLM Call",
                run_type=RunType.LLM,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0001",
                inputs={"prompt": "This should be extracted"}
            ),
            create_trace_run(
                id="run-3",
                name="Tool",
                run_type=RunType.TOOL,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0002",
                inputs={"messages": [{"role": "user", "content": "Also ignored"}]}
            )
        ]
        base_trace.runs = runs

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify only LLM run was processed
        assert len(result.user_prompts) == 1
        assert "This should be extracted" in result.user_prompts
        assert "This should be ignored" not in result.user_prompts
        assert "Also ignored" not in result.user_prompts

    @pytest.mark.asyncio
    async def test_multiple_llm_runs_aggregation(self, mock_client, base_trace):
        """Test aggregation of prompts from multiple LLM runs."""
        # Setup mock for one managed prompt
        mock_client.fetch_prompt.return_value = {
            "type": "chat",
            "prompt": [
                {"role": "system", "content": "Managed system prompt"}
            ]
        }

        # Create multiple LLM runs
        runs = [
            create_trace_run(
                id="run-1",
                name="First LLM",
                run_type=RunType.LLM,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0000",
                metadata={"promptName": "managed-prompt"},
                inputs={}
            ),
            create_trace_run(
                id="run-2",
                name="Second LLM",
                run_type=RunType.LLM,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0001",
                inputs={
                    "messages": [
                        {"role": "system", "content": "Ad-hoc system prompt"},
                        {"role": "user", "content": "User message 1"}
                    ]
                }
            ),
            create_trace_run(
                id="run-3",
                name="Third LLM",
                run_type=RunType.LLM,
                start_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="0002",
                inputs={
                    "prompt": "Simple prompt text"
                }
            )
        ]
        base_trace.runs = runs

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify all prompts were aggregated
        assert len(result.system_prompts) == 2
        assert "Managed system prompt" in result.system_prompts
        assert "Ad-hoc system prompt" in result.system_prompts

        assert len(result.user_prompts) == 2
        assert "User message 1" in result.user_prompts
        assert "Simple prompt text" in result.user_prompts

    @pytest.mark.asyncio
    async def test_edge_cases(self, mock_client, base_trace):
        """Test various edge cases in prompt extraction."""
        # Create run with edge case inputs
        run = create_trace_run(
            id="run-1",
            name="LLM Call",
            run_type=RunType.LLM,
            start_time=datetime.now(),
            trace_id="test-trace-123",
            dotted_order="0000",
            inputs={
                "messages": [
                    {"role": "system", "content": ""},  # Empty content
                    {"role": "user"},  # Missing content
                    {"content": "No role specified"},  # Missing role
                    {"role": "user", "content": "Valid message"},
                    None,  # None message
                    "Not a dict"  # Invalid message format
                ],
                "prompt": 123  # Non-string prompt
            }
        )
        base_trace.runs = [run]

        # Extract prompts
        extractor = LangfusePromptExtractor(mock_client)
        result = await extractor.extract(base_trace)

        # Verify only valid messages were extracted
        assert len(result.system_prompts) == 0
        assert len(result.user_prompts) == 2
        assert "No role specified" in result.user_prompts
        assert "Valid message" in result.user_prompts