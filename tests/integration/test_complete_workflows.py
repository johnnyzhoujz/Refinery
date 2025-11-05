"""
Comprehensive integration tests for all Refinery workflows.

Tests end-to-end integration of:
- LangSmith API workflow
- Langfuse API workflow
- Langfuse file workflow
- OTLP file workflow
- Format auto-detection
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from refinery.core.trace_source_factory import TraceSourceFactory
from refinery.core.orchestrator import RefineryOrchestrator
from refinery.core.models import Trace, PromptData
from refinery.integrations.local_file_provider import LocalFileTraceProvider
from refinery.integrations.langfuse_client import LangfuseClient
from refinery.integrations.langsmith_client_simple import SimpleLangSmithClient
from refinery.utils.config import config


@pytest.fixture
def langfuse_fixture_path():
    """Path to Langfuse test fixture."""
    return Path(__file__).parent.parent / "fixtures" / "langfuse_trace.json"


@pytest.fixture
def otlp_fixture_path():
    """Path to OTLP test fixture."""
    return Path(__file__).parent.parent / "fixtures" / "otlp_trace_tempo.json"


class TestTraceSourceFactoryIntegration:
    """Test TraceSourceFactory creates correct providers for all workflows."""

    def test_create_langsmith_provider(self):
        """Test LangSmith provider creation."""
        with patch.object(config, 'langsmith_api_key', 'test-key'):
            provider = TraceSourceFactory.create_from_provider("langsmith")
            assert isinstance(provider, SimpleLangSmithClient)

    def test_create_langfuse_provider(self):
        """Test Langfuse provider creation."""
        with patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', 'sk-test'):
            provider = TraceSourceFactory.create_from_provider("langfuse")
            assert isinstance(provider, LangfuseClient)

    def test_create_local_file_provider_langfuse(self, langfuse_fixture_path):
        """Test LocalFileTraceProvider creation for Langfuse file."""
        provider = TraceSourceFactory.create_for_cli(file_path=str(langfuse_fixture_path))
        assert isinstance(provider, LocalFileTraceProvider)

    def test_create_local_file_provider_otlp(self, otlp_fixture_path):
        """Test LocalFileTraceProvider creation for OTLP file."""
        provider = TraceSourceFactory.create_for_cli(file_path=str(otlp_fixture_path))
        assert isinstance(provider, LocalFileTraceProvider)

    def test_cli_auto_detection_from_file(self, langfuse_fixture_path):
        """Test CLI auto-detects file provider without explicit provider arg."""
        provider = TraceSourceFactory.create_for_cli(file_path=str(langfuse_fixture_path))
        assert isinstance(provider, LocalFileTraceProvider)

    def test_cli_defaults_to_langsmith_for_trace_id(self):
        """Test backward compatibility: trace_id defaults to LangSmith."""
        with patch.object(config, 'langsmith_api_key', 'test-key'):
            provider = TraceSourceFactory.create_for_cli(trace_id="abc123")
            assert isinstance(provider, SimpleLangSmithClient)


class TestLangfuseFileWorkflow:
    """Test complete Langfuse file-based workflow."""

    @pytest.mark.asyncio
    async def test_load_langfuse_file(self, langfuse_fixture_path):
        """Test loading Langfuse trace from file."""
        provider = LocalFileTraceProvider(str(langfuse_fixture_path))

        trace = await provider.fetch_trace()

        assert isinstance(trace, Trace)
        assert trace.trace_id == "trace-123"
        assert trace.metadata["format"] == "langfuse"
        assert trace.metadata["source"] == "file"
        assert len(trace.runs) == 5

    @pytest.mark.asyncio
    async def test_langfuse_file_with_orchestrator(self, langfuse_fixture_path):
        """Test Langfuse file workflow with orchestrator."""
        provider = TraceSourceFactory.create_for_cli(file_path=str(langfuse_fixture_path))

        # Create orchestrator with file provider
        orchestrator = RefineryOrchestrator(
            codebase_path=".",
            trace_provider=provider
        )

        # Initialize async components
        await orchestrator._init_async()

        # Verify prompt extractor was initialized
        assert orchestrator._prompt_extractor is not None

        # Fetch trace
        trace = await provider.fetch_trace()

        # Extract prompts (tests MultiStrategyPromptExtractor integration)
        prompts_dict = orchestrator._prompt_extractor.extract_prompts_from_trace(trace)

        assert isinstance(prompts_dict, dict)
        assert "system_prompts" in prompts_dict
        assert "user_prompts" in prompts_dict

    @pytest.mark.asyncio
    async def test_langfuse_file_caching(self, langfuse_fixture_path):
        """Test that traces are cached for performance."""
        provider = LocalFileTraceProvider(str(langfuse_fixture_path))

        # First fetch
        trace1 = await provider.fetch_trace()

        # Second fetch should return cached
        trace2 = await provider.fetch_trace()

        assert trace1 is trace2  # Same object reference


class TestOTLPFileWorkflow:
    """Test complete OTLP file-based workflow."""

    @pytest.mark.asyncio
    async def test_load_otlp_file(self, otlp_fixture_path):
        """Test loading OTLP trace from file."""
        provider = LocalFileTraceProvider(str(otlp_fixture_path))

        trace = await provider.fetch_trace()

        assert isinstance(trace, Trace)
        assert trace.metadata["format"] == "opentelemetry"
        assert trace.metadata["source"] == "file"
        assert len(trace.runs) > 0

    @pytest.mark.asyncio
    async def test_otlp_file_with_orchestrator(self, otlp_fixture_path):
        """Test OTLP file workflow with orchestrator."""
        provider = TraceSourceFactory.create_for_cli(file_path=str(otlp_fixture_path))

        # Create orchestrator with file provider
        orchestrator = RefineryOrchestrator(
            codebase_path=".",
            trace_provider=provider
        )

        # Initialize async components
        await orchestrator._init_async()

        # Fetch trace
        trace = await provider.fetch_trace()

        # Extract prompts
        prompts_dict = orchestrator._prompt_extractor.extract_prompts_from_trace(trace)

        assert isinstance(prompts_dict, dict)


class TestFormatAutoDetection:
    """Test automatic format detection for all file types."""

    @pytest.mark.asyncio
    async def test_auto_detect_langfuse(self, langfuse_fixture_path):
        """Test Langfuse format is auto-detected correctly."""
        provider = LocalFileTraceProvider(str(langfuse_fixture_path))

        trace = await provider.fetch_trace()

        assert trace.metadata["format"] == "langfuse"

    @pytest.mark.asyncio
    async def test_auto_detect_otlp(self, otlp_fixture_path):
        """Test OTLP format is auto-detected correctly."""
        provider = LocalFileTraceProvider(str(otlp_fixture_path))

        trace = await provider.fetch_trace()

        assert trace.metadata["format"] == "opentelemetry"

    @pytest.mark.asyncio
    async def test_format_detection_with_factory(self, langfuse_fixture_path, otlp_fixture_path):
        """Test format detection works through TraceSourceFactory."""
        # Langfuse file
        provider1 = TraceSourceFactory.create_for_cli(file_path=str(langfuse_fixture_path))
        trace1 = await provider1.fetch_trace()
        assert trace1.metadata["format"] == "langfuse"

        # OTLP file
        provider2 = TraceSourceFactory.create_for_cli(file_path=str(otlp_fixture_path))
        trace2 = await provider2.fetch_trace()
        assert trace2.metadata["format"] == "opentelemetry"


class TestMultiStrategyPromptExtraction:
    """Test prompt extraction works across all provider types."""

    @pytest.mark.asyncio
    async def test_prompt_extraction_langfuse_file(self, langfuse_fixture_path):
        """Test prompt extraction from Langfuse file."""
        from refinery.core.prompt_extraction import MultiStrategyPromptExtractor

        provider = LocalFileTraceProvider(str(langfuse_fixture_path))
        trace = await provider.fetch_trace()

        extractor = MultiStrategyPromptExtractor(provider)
        prompts_dict = extractor.extract_prompts_from_trace(trace)

        assert isinstance(prompts_dict, dict)
        assert "system_prompts" in prompts_dict or "user_prompts" in prompts_dict

    @pytest.mark.asyncio
    async def test_prompt_extraction_otlp_file(self, otlp_fixture_path):
        """Test prompt extraction from OTLP file."""
        from refinery.core.prompt_extraction import MultiStrategyPromptExtractor

        provider = LocalFileTraceProvider(str(otlp_fixture_path))
        trace = await provider.fetch_trace()

        extractor = MultiStrategyPromptExtractor(provider)
        prompts_dict = extractor.extract_prompts_from_trace(trace)

        assert isinstance(prompts_dict, dict)


class TestBackwardCompatibility:
    """Test that existing LangSmith workflows still work."""

    def test_langsmith_default_provider(self):
        """Test LangSmith is still the default provider."""
        with patch.object(config, 'langsmith_api_key', 'test-key'):
            # No provider specified, should default to LangSmith
            provider = TraceSourceFactory.create_for_cli()
            assert isinstance(provider, SimpleLangSmithClient)

    def test_langsmith_trace_id_workflow(self):
        """Test trace_id alone defaults to LangSmith (backward compatibility)."""
        with patch.object(config, 'langsmith_api_key', 'test-key'):
            provider = TraceSourceFactory.create_for_cli(trace_id="abc123")
            assert isinstance(provider, SimpleLangSmithClient)

    @pytest.mark.asyncio
    async def test_orchestrator_without_provider_defaults_langsmith(self):
        """Test orchestrator without provider defaults to LangSmith."""
        with patch('refinery.core.orchestrator.create_langsmith_client') as mock_create:
            mock_client = AsyncMock()
            mock_create.return_value = mock_client

            orchestrator = RefineryOrchestrator(codebase_path=".")
            await orchestrator._init_async()

            # Should have initialized with LangSmith client
            assert orchestrator.trace_provider == mock_client
            mock_create.assert_called_once()


class TestProviderAgnosticOrchestrator:
    """Test that orchestrator works with any TraceProvider."""

    @pytest.mark.asyncio
    async def test_orchestrator_accepts_langfuse_client(self):
        """Test orchestrator works with LangfuseClient."""
        from refinery.utils.config import config

        with patch.object(config, 'langfuse_public_key', 'pk-test'), \
             patch.object(config, 'langfuse_secret_key', 'sk-test'):
            provider = TraceSourceFactory.create_from_provider("langfuse")

            orchestrator = RefineryOrchestrator(
                codebase_path=".",
                trace_provider=provider
            )

            await orchestrator._init_async()

            assert orchestrator.trace_provider is provider
            assert orchestrator._prompt_extractor is not None

    @pytest.mark.asyncio
    async def test_orchestrator_accepts_file_provider(self, langfuse_fixture_path):
        """Test orchestrator works with LocalFileTraceProvider."""
        provider = LocalFileTraceProvider(str(langfuse_fixture_path))

        orchestrator = RefineryOrchestrator(
            codebase_path=".",
            trace_provider=provider
        )

        await orchestrator._init_async()

        assert orchestrator.trace_provider is provider
        assert orchestrator._prompt_extractor is not None


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows (minimal mocking)."""

    @pytest.mark.asyncio
    async def test_complete_file_workflow_langfuse(self, langfuse_fixture_path):
        """Test complete file workflow: Factory → Provider → Orchestrator → Extraction."""
        # 1. Create provider via factory
        provider = TraceSourceFactory.create_for_cli(file_path=str(langfuse_fixture_path))

        # 2. Fetch trace
        trace = await provider.fetch_trace()
        assert trace.trace_id == "trace-123"

        # 3. Create orchestrator
        orchestrator = RefineryOrchestrator(
            codebase_path=".",
            trace_provider=provider
        )
        await orchestrator._init_async()

        # 4. Extract prompts
        prompts_dict = orchestrator._prompt_extractor.extract_prompts_from_trace(trace)
        assert isinstance(prompts_dict, dict)

        # 5. Verify extraction worked
        assert "system_prompts" in prompts_dict or "user_prompts" in prompts_dict

    @pytest.mark.asyncio
    async def test_complete_file_workflow_otlp(self, otlp_fixture_path):
        """Test complete file workflow: Factory → Provider → Orchestrator → Extraction."""
        # 1. Create provider via factory
        provider = TraceSourceFactory.create_for_cli(file_path=str(otlp_fixture_path))

        # 2. Fetch trace
        trace = await provider.fetch_trace()
        assert trace.metadata["format"] == "opentelemetry"

        # 3. Create orchestrator
        orchestrator = RefineryOrchestrator(
            codebase_path=".",
            trace_provider=provider
        )
        await orchestrator._init_async()

        # 4. Extract prompts
        prompts_dict = orchestrator._prompt_extractor.extract_prompts_from_trace(trace)
        assert isinstance(prompts_dict, dict)
