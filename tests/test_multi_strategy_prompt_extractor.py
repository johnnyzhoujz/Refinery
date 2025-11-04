"""Tests for MultiStrategyPromptExtractor."""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from refinery.core.prompt_extraction import MultiStrategyPromptExtractor
from refinery.core.models import Trace, TraceRun, RunType, PromptData
from datetime import datetime


@pytest.fixture
def mock_langsmith_client():
    """Mock LangSmith client."""
    client = Mock()
    client.__class__.__name__ = "SimpleLangSmithClient"
    client.extract_prompts_from_trace = Mock(return_value={
        "system_prompts": [{"content": "LangSmith system", "run_name": "test"}],
        "user_prompts": [{"content": "LangSmith user", "run_name": "test"}],
        "prompt_templates": [],
        "model_configs": [],
        "eval_examples": [],
    })
    return client


@pytest.fixture
def mock_langfuse_client():
    """Mock Langfuse client."""
    client = Mock()
    client.__class__.__name__ = "LangfuseClient"
    return client


@pytest.fixture
def mock_otlp_provider():
    """Mock OTLP provider."""
    provider = Mock()
    provider.__class__.__name__ = "LocalFileTraceProvider"
    return provider


@pytest.fixture
def sample_trace():
    """Sample trace for testing."""
    return Trace(
        trace_id="test-trace-123",
        project_name="test-project",
        runs=[
            TraceRun(
                id="run-1",
                name="llm.call",
                run_type=RunType.LLM,
                start_time=datetime.now(),
                end_time=datetime.now(),
                trace_id="test-trace-123",
                dotted_order="1",
                inputs={"messages": [{"role": "user", "content": "Hello"}]},
                outputs={"messages": [{"role": "assistant", "content": "Hi"}]},
                error=None,
                parent_run_id=None,
                metadata={"gen_ai.input.messages": '[{"role": "user", "content": "Hello"}]'},
            )
        ],
        start_time=datetime.now(),
        end_time=datetime.now(),
        metadata={},
    )


class TestProviderDetection:
    """Test provider type detection logic."""

    def test_detect_langsmith_provider(self, mock_langsmith_client):
        """Test detection of LangSmith provider."""
        extractor = MultiStrategyPromptExtractor(mock_langsmith_client)
        assert extractor.provider_name == "langsmith"

    def test_detect_langfuse_provider(self, mock_langfuse_client):
        """Test detection of Langfuse provider."""
        extractor = MultiStrategyPromptExtractor(mock_langfuse_client)
        assert extractor.provider_name == "langfuse"

    def test_detect_otlp_provider(self, mock_otlp_provider):
        """Test detection of OTLP provider."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)
        assert extractor.provider_name == "otlp"

    def test_default_to_langsmith_without_provider(self):
        """Test backward compatibility: defaults to LangSmith without provider."""
        extractor = MultiStrategyPromptExtractor(None)
        assert extractor.provider_name == "langsmith"

    def test_detect_otlp_prefix_provider(self):
        """Test detection of OTLP-prefixed provider."""
        provider = Mock()
        provider.__class__.__name__ = "OTLPFileProvider"
        extractor = MultiStrategyPromptExtractor(provider)
        assert extractor.provider_name == "otlp"

    def test_unknown_provider_defaults_to_otlp(self):
        """Test unknown provider defaults to OTLP with warning."""
        provider = Mock()
        provider.__class__.__name__ = "UnknownProvider"

        with patch("refinery.core.prompt_extraction.logger") as mock_logger:
            extractor = MultiStrategyPromptExtractor(provider)
            assert extractor.provider_name == "otlp"
            mock_logger.warning.assert_called_once()


class TestExtractorCreation:
    """Test extractor creation based on provider type."""

    def test_create_langfuse_extractor(self, mock_langfuse_client):
        """Test creation of Langfuse extractor."""
        extractor = MultiStrategyPromptExtractor(mock_langfuse_client)
        assert extractor.extractor is not None
        assert extractor.extractor.__class__.__name__ == "LangfusePromptExtractor"

    def test_create_otlp_extractor(self, mock_otlp_provider):
        """Test creation of OTLP extractor."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)
        assert extractor.extractor is not None
        assert extractor.extractor.__class__.__name__ == "OTLPPromptExtractor"

    def test_langsmith_no_separate_extractor(self, mock_langsmith_client):
        """Test LangSmith doesn't create separate extractor."""
        extractor = MultiStrategyPromptExtractor(mock_langsmith_client)
        assert extractor.extractor is None


class TestSyncExtraction:
    """Test synchronous prompt extraction."""

    def test_extract_from_langsmith(self, mock_langsmith_client, sample_trace):
        """Test extraction from LangSmith provider."""
        extractor = MultiStrategyPromptExtractor(mock_langsmith_client)
        result = extractor.extract_prompts_from_trace(sample_trace)

        assert "system_prompts" in result
        assert "user_prompts" in result
        assert len(result["system_prompts"]) == 1
        assert len(result["user_prompts"]) == 1
        assert result["system_prompts"][0]["content"] == "LangSmith system"
        mock_langsmith_client.extract_prompts_from_trace.assert_called_once_with(sample_trace)

    def test_extract_from_langsmith_fallback_no_method(self, sample_trace):
        """Test LangSmith fallback when extraction method missing."""
        client = Mock()
        client.__class__.__name__ = "SimpleLangSmithClient"
        # Remove extract_prompts_from_trace method
        del client.extract_prompts_from_trace

        extractor = MultiStrategyPromptExtractor(client)

        with patch("refinery.core.prompt_extraction.logger") as mock_logger:
            result = extractor.extract_prompts_from_trace(sample_trace)

            # Should return empty result
            assert result == {
                "system_prompts": [],
                "user_prompts": [],
                "prompt_templates": [],
                "model_configs": [],
                "eval_examples": [],
            }
            mock_logger.warning.assert_called()

    @patch("refinery.core.prompt_extraction.asyncio")
    def test_extract_from_otlp_sync_context(self, mock_asyncio, mock_otlp_provider, sample_trace):
        """Test OTLP extraction in synchronous context."""
        # Setup mock async behavior
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_asyncio.get_event_loop.return_value = mock_loop
        mock_asyncio.run.return_value = PromptData(
            system_prompts=["System prompt"],
            user_prompts=["User prompt"],
        )

        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)
        result = extractor.extract_prompts_from_trace(sample_trace)

        assert len(result["system_prompts"]) == 1
        assert len(result["user_prompts"]) == 1
        assert result["system_prompts"][0]["content"] == "System prompt"
        assert result["user_prompts"][0]["content"] == "User prompt"

    @patch("refinery.core.prompt_extraction.asyncio")
    def test_extract_handles_exception(self, mock_asyncio, mock_otlp_provider, sample_trace):
        """Test extraction handles exceptions gracefully."""
        # Setup mock to simulate exception in asyncio.run
        mock_loop = Mock()
        mock_loop.is_running.return_value = False
        mock_asyncio.get_event_loop.return_value = mock_loop
        mock_asyncio.run.side_effect = Exception("Extraction failed")

        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)

        with patch("refinery.core.prompt_extraction.logger") as mock_logger:
            result = extractor.extract_prompts_from_trace(sample_trace)

            # Should return empty result
            assert result == {
                "system_prompts": [],
                "user_prompts": [],
                "prompt_templates": [],
                "model_configs": [],
                "eval_examples": [],
            }
            mock_logger.warning.assert_called()


class TestAsyncExtraction:
    """Test asynchronous prompt extraction."""

    @pytest.mark.asyncio
    async def test_extract_from_langsmith_async(self, mock_langsmith_client, sample_trace):
        """Test async extraction from LangSmith provider."""
        extractor = MultiStrategyPromptExtractor(mock_langsmith_client)
        result = await extractor.extract_prompts_from_trace_async(sample_trace)

        assert "system_prompts" in result
        assert "user_prompts" in result
        mock_langsmith_client.extract_prompts_from_trace.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_from_otlp_async(self, mock_otlp_provider, sample_trace):
        """Test async extraction from OTLP provider."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)

        # Mock the extractor's extract method
        extractor.extractor.extract = AsyncMock(return_value=PromptData(
            system_prompts=["System prompt"],
            user_prompts=["User prompt"],
        ))

        result = await extractor.extract_prompts_from_trace_async(sample_trace)

        assert len(result["system_prompts"]) == 1
        assert len(result["user_prompts"]) == 1
        assert result["system_prompts"][0]["content"] == "System prompt"

    @pytest.mark.asyncio
    async def test_extract_async_handles_exception(self, mock_otlp_provider, sample_trace):
        """Test async extraction handles exceptions gracefully."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)
        extractor.extractor.extract = AsyncMock(side_effect=Exception("Async extraction failed"))

        with patch("refinery.core.prompt_extraction.logger") as mock_logger:
            result = await extractor.extract_prompts_from_trace_async(sample_trace)

            # Should return empty result
            assert result == {
                "system_prompts": [],
                "user_prompts": [],
                "prompt_templates": [],
                "model_configs": [],
                "eval_examples": [],
            }
            mock_logger.warning.assert_called()


class TestFormatConversion:
    """Test PromptData to LangSmith format conversion."""

    def test_convert_to_langsmith_format(self, mock_otlp_provider):
        """Test conversion from PromptData to LangSmith format."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)

        prompt_data = PromptData(
            system_prompts=["System 1", "System 2"],
            user_prompts=["User 1", "User 2", "User 3"],
        )

        result = extractor._convert_to_langsmith_format(prompt_data)

        assert len(result["system_prompts"]) == 2
        assert len(result["user_prompts"]) == 3
        assert result["system_prompts"][0]["content"] == "System 1"
        assert result["system_prompts"][1]["content"] == "System 2"
        assert result["user_prompts"][0]["content"] == "User 1"
        assert result["user_prompts"][2]["content"] == "User 3"
        assert result["system_prompts"][0]["run_name"] == ""
        assert result["prompt_templates"] == []
        assert result["model_configs"] == []
        assert result["eval_examples"] == []

    def test_convert_empty_prompt_data(self, mock_otlp_provider):
        """Test conversion of empty PromptData."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)

        prompt_data = PromptData(
            system_prompts=[],
            user_prompts=[],
        )

        result = extractor._convert_to_langsmith_format(prompt_data)

        assert result["system_prompts"] == []
        assert result["user_prompts"] == []


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_no_provider_defaults_langsmith(self):
        """Test that no provider maintains backward compatibility."""
        extractor = MultiStrategyPromptExtractor()
        assert extractor.provider_name == "langsmith"
        assert extractor.trace_provider is None

    def test_empty_result_structure_matches_langsmith(self, mock_otlp_provider):
        """Test empty result structure matches LangSmith format."""
        extractor = MultiStrategyPromptExtractor(mock_otlp_provider)
        result = extractor._empty_extraction_result()

        # Verify structure matches LangSmith format
        expected_keys = {"system_prompts", "user_prompts", "prompt_templates",
                        "model_configs", "eval_examples"}
        assert set(result.keys()) == expected_keys
        assert all(isinstance(result[k], list) for k in expected_keys)
        assert all(len(result[k]) == 0 for k in expected_keys)
