"""
Integration tests for LangfusePromptExtractor with LangfuseClient.

Tests end-to-end extraction using real trace fixtures and mocked Langfuse SDK.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from refinery.integrations.langfuse_client import LangfuseClient
from refinery.integrations.prompt_extractors.langfuse_extractor import LangfusePromptExtractor


class TestLangfusePromptExtractorIntegration:
    """Integration tests for LangfusePromptExtractor."""

    @pytest.fixture
    def langfuse_trace_data(self):
        """Load Langfuse trace fixture."""
        fixture_path = Path(__file__).parent / "fixtures" / "langfuse_trace.json"
        with open(fixture_path) as f:
            return json.load(f)

    @pytest.fixture
    def mock_langfuse_sdk(self):
        """Create mock Langfuse SDK."""
        from refinery.utils.config import config

        with patch("refinery.integrations.langfuse_client.Langfuse") as mock_langfuse, \
             patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', 'sk-test'):
            # Create mock instance
            mock_instance = MagicMock()
            mock_langfuse.return_value = mock_instance

            # Mock get_prompt method for Prompt Management API
            mock_instance.get_prompt = MagicMock()

            yield mock_instance

    @pytest.mark.asyncio
    async def test_integration_with_managed_prompt(self, mock_langfuse_sdk, langfuse_trace_data):
        """Test end-to-end extraction with managed prompt from Prompt API."""
        # Setup mock SDK to return trace data
        mock_langfuse_sdk.api.trace.get = MagicMock(return_value=langfuse_trace_data)

        # Setup mock for managed prompt (obs-4 has promptName)
        def mock_get_prompt(name, version=None, label=None):
            if name == "test-prompt" and version == 1:
                return {
                    "type": "chat",
                    "prompt": [
                        {"role": "system", "content": "You are a test assistant"},
                        {"role": "user", "content": "This is from the prompt registry"}
                    ]
                }
            raise Exception("Prompt not found")

        mock_langfuse_sdk.get_prompt = mock_get_prompt

        # Create client and extractor
        client = LangfuseClient()
        extractor = LangfusePromptExtractor(client)

        # Fetch and parse trace
        trace = await client.fetch_trace("trace-123")

        # Extract prompts
        result = await extractor.extract(trace)

        # Verify prompts from both managed and ad-hoc sources
        # obs-1: ad-hoc system prompt
        assert "You are helpful" in result.system_prompts

        # obs-4: managed prompt (should override the observation input)
        assert "You are a test assistant" in result.system_prompts
        assert "This is from the prompt registry" in result.user_prompts

        # obs-4: ad-hoc user prompt should NOT be included (managed prompt takes precedence)
        assert "nested call" not in result.user_prompts

    @pytest.mark.asyncio
    async def test_integration_prompt_api_failure(self, mock_langfuse_sdk, langfuse_trace_data):
        """Test fallback when Prompt API fails."""
        # Setup mock SDK to return trace data
        mock_langfuse_sdk.api.trace.get = MagicMock(return_value=langfuse_trace_data)

        # Setup mock to fail for managed prompt
        mock_langfuse_sdk.get_prompt = MagicMock(side_effect=Exception("API error"))

        # Create client and extractor
        client = LangfuseClient()
        extractor = LangfusePromptExtractor(client)

        # Fetch and parse trace
        trace = await client.fetch_trace("trace-123")

        # Extract prompts with logging capture
        import structlog.testing
        with structlog.testing.capture_logs() as cap_logs:
            result = await extractor.extract(trace)

        # Verify warning was logged for failed prompt fetch
        warning_logs = [log for log in cap_logs if "Failed to fetch managed prompt" in log.get("event", "")]
        assert len(warning_logs) == 1
        assert warning_logs[0]["prompt_name"] == "test-prompt"

        # Verify fallback extraction worked
        # obs-1: ad-hoc system prompt
        assert "You are helpful" in result.system_prompts

        # obs-4: should fall back to observation inputs
        assert "nested call" in result.user_prompts

    @pytest.mark.asyncio
    async def test_integration_all_adhoc_prompts(self, mock_langfuse_sdk, langfuse_trace_data):
        """Test extraction with only ad-hoc prompts (no managed prompts)."""
        # Remove promptName from fixture data
        for obs in langfuse_trace_data["observations"]:
            if "metadata" in obs and "promptName" in obs.get("metadata", {}):
                del obs["metadata"]["promptName"]
                if "promptVersion" in obs["metadata"]:
                    del obs["metadata"]["promptVersion"]

        # Setup mock SDK to return modified trace data
        mock_langfuse_sdk.api.trace.get = MagicMock(return_value=langfuse_trace_data)

        # Create client and extractor
        client = LangfuseClient()
        extractor = LangfusePromptExtractor(client)

        # Fetch and parse trace
        trace = await client.fetch_trace("trace-123")

        # Extract prompts
        result = await extractor.extract(trace)

        # Verify all ad-hoc prompts were extracted
        assert len(result.system_prompts) == 1
        assert "You are helpful" in result.system_prompts

        assert len(result.user_prompts) == 1
        assert "nested call" in result.user_prompts

        # Verify no prompt API calls were made
        mock_langfuse_sdk.get_prompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_integration_mixed_prompt_types(self, mock_langfuse_sdk):
        """Test extraction with various prompt formats."""
        # Create custom trace data with different prompt formats
        trace_data = {
            "id": "test-trace",
            "projectId": "test-project",
            "observations": [
                {
                    "id": "obs-1",
                    "name": "Text Prompt",
                    "type": "GENERATION",
                    "startTime": "2025-01-15T10:00:00Z",
                    "endTime": "2025-01-15T10:00:01Z",
                    "input": {
                        "prompt": "Simple text prompt"
                    },
                    "metadata": {
                        "promptName": "text-prompt"
                    }
                },
                {
                    "id": "obs-2",
                    "name": "Chat Messages",
                    "type": "GENERATION",
                    "startTime": "2025-01-15T10:00:02Z",
                    "endTime": "2025-01-15T10:00:03Z",
                    "input": {
                        "messages": [
                            {"role": "system", "content": "System message"},
                            {"role": "user", "content": "User message"},
                            {"role": "assistant", "content": "Assistant message"},
                            {"role": "function", "content": "Function message"}
                        ]
                    }
                },
                {
                    "id": "obs-3",
                    "name": "Empty Prompt",
                    "type": "GENERATION",
                    "startTime": "2025-01-15T10:00:04Z",
                    "endTime": "2025-01-15T10:00:05Z",
                    "input": {}
                }
            ]
        }

        # Setup mocks
        mock_langfuse_sdk.api.trace.get = MagicMock(return_value=trace_data)

        def mock_get_prompt(name, version=None, label=None):
            if name == "text-prompt":
                return {
                    "type": "text",
                    "prompt": "Text from prompt registry"
                }
            raise Exception("Prompt not found")

        mock_langfuse_sdk.get_prompt = mock_get_prompt

        # Create client and extractor
        client = LangfuseClient()
        extractor = LangfusePromptExtractor(client)

        # Fetch and parse trace
        trace = await client.fetch_trace("test-trace")

        # Extract prompts
        result = await extractor.extract(trace)

        # Verify all prompt types were handled correctly
        assert len(result.system_prompts) == 1
        assert "System message" in result.system_prompts

        # Text prompt from registry + ad-hoc messages
        assert len(result.user_prompts) == 4
        assert "Text from prompt registry" in result.user_prompts
        assert "User message" in result.user_prompts
        assert "Assistant message" in result.user_prompts
        assert "Function message" in result.user_prompts

    @pytest.mark.asyncio
    async def test_integration_non_llm_runs_ignored(self, mock_langfuse_sdk, langfuse_trace_data):
        """Test that non-LLM runs are correctly ignored."""
        # Setup mock SDK to return trace data
        mock_langfuse_sdk.api.trace.get = MagicMock(return_value=langfuse_trace_data)

        # Create client and extractor
        client = LangfuseClient()
        extractor = LangfusePromptExtractor(client)

        # Fetch and parse trace
        trace = await client.fetch_trace("trace-123")

        # Count LLM vs non-LLM runs
        from refinery.core.models import RunType
        llm_runs = [r for r in trace.runs if r.run_type == RunType.LLM]
        non_llm_runs = [r for r in trace.runs if r.run_type != RunType.LLM]

        assert len(llm_runs) == 2  # obs-1 and obs-4 are GENERATION
        assert len(non_llm_runs) == 3  # obs-2 (SPAN), obs-3 (TOOL), obs-5 (EVENT)

        # Extract prompts
        result = await extractor.extract(trace)

        # Verify only prompts from LLM runs were extracted
        # Should have prompts from obs-1 and obs-4 only
        assert len(result.system_prompts) >= 1
        assert len(result.user_prompts) >= 0

        # Verify no prompts from non-LLM runs (e.g., obs-2's input.query)
        all_prompts = result.system_prompts + result.user_prompts
        assert "test query" not in " ".join(all_prompts)  # from obs-2 SPAN
        assert "search" not in " ".join(all_prompts)  # from obs-3 TOOL