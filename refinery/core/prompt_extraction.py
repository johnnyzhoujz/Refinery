"""
Multi-strategy prompt extraction coordinator.

Handles prompt extraction across different trace providers with fallback support.
"""

import asyncio
from typing import Dict, Any
import structlog
from .models import Trace, PromptData

logger = structlog.get_logger(__name__)


class MultiStrategyPromptExtractor:
    """Coordinates prompt extraction across different provider types."""

    def __init__(self, trace_provider=None):
        """
        Initialize extractor with optional provider for strategy detection.

        Args:
            trace_provider: Optional TraceProvider instance for type detection
        """
        self.trace_provider = trace_provider
        self.provider_name = self._detect_provider_type()
        self.extractor = self._create_extractor()

    def _detect_provider_type(self) -> str:
        """Detect provider type from instance."""
        if self.trace_provider is None:
            return "langsmith"  # Default for backward compatibility

        provider_class = type(self.trace_provider).__name__

        if "Langfuse" in provider_class:
            return "langfuse"
        elif "SimpleLangSmith" in provider_class or "LangSmith" in provider_class:
            return "langsmith"
        elif "LocalFile" in provider_class or "OTLP" in provider_class:
            return "otlp"
        else:
            # Default to unknown, will attempt OTLP extraction
            logger.warning("Unknown provider type, defaulting to OTLP", provider_class=provider_class)
            return "otlp"

    def _create_extractor(self):
        """Create appropriate extractor based on provider type."""
        from ..integrations.prompt_extractors import OTLPPromptExtractor, LangfusePromptExtractor

        if self.provider_name == "langfuse":
            return LangfusePromptExtractor(self.trace_provider)
        elif self.provider_name == "otlp":
            return OTLPPromptExtractor()
        else:
            # LangSmith uses direct method, no separate extractor
            return None

    def extract_prompts_from_trace(self, trace: Trace) -> Dict[str, Any]:
        """
        Extract prompts using provider-appropriate strategy.

        For backward compatibility, this method mimics the LangSmith
        extract_prompts_from_trace signature.

        Returns:
            Dict with keys: system_prompts, user_prompts, prompt_templates,
                           model_configs, eval_examples
        """
        if self.provider_name == "langsmith":
            # Use existing LangSmith extraction (direct method on client)
            if hasattr(self.trace_provider, 'extract_prompts_from_trace'):
                return self.trace_provider.extract_prompts_from_trace(trace)
            else:
                # Fallback: return empty result if no extraction method
                logger.warning("LangSmith provider lacks extract_prompts_from_trace method")
                return self._empty_extraction_result()

        elif self.extractor:
            # Use dedicated extractor for Langfuse/OTLP
            try:
                # Call async extract method (will be awaited by caller if needed)
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If in async context, create a task
                    prompt_data = asyncio.create_task(self.extractor.extract(trace))
                    # Wait for result
                    prompt_data = loop.run_until_complete(prompt_data)
                else:
                    # Not in async context, run synchronously
                    prompt_data = asyncio.run(self.extractor.extract(trace))

                # Convert to LangSmith-compatible format
                return self._convert_to_langsmith_format(prompt_data)
            except Exception as e:
                logger.warning(
                    "Extraction failed, returning empty results",
                    provider=self.provider_name,
                    error=str(e)
                )
                return self._empty_extraction_result()

        return self._empty_extraction_result()

    def _convert_to_langsmith_format(self, prompt_data: PromptData) -> Dict[str, Any]:
        """Convert PromptData to LangSmith extraction format."""
        result = {
            "system_prompts": [],
            "user_prompts": [],
            "prompt_templates": [],
            "model_configs": [],
            "eval_examples": [],
        }

        # Convert system prompts
        for content in prompt_data.system_prompts:
            result["system_prompts"].append({
                "content": content,
                "run_name": "",
            })

        # Convert user prompts
        for content in prompt_data.user_prompts:
            result["user_prompts"].append({
                "content": content,
                "run_name": "",
            })

        return result

    def _empty_extraction_result(self) -> Dict[str, Any]:
        """Return empty extraction result matching LangSmith format."""
        return {
            "system_prompts": [],
            "user_prompts": [],
            "prompt_templates": [],
            "model_configs": [],
            "eval_examples": [],
        }

    async def extract_prompts_from_trace_async(self, trace: Trace) -> Dict[str, Any]:
        """
        Async version of prompt extraction.

        This is the preferred method for async contexts.
        """
        if self.provider_name == "langsmith":
            # Use existing LangSmith extraction (synchronous)
            if hasattr(self.trace_provider, 'extract_prompts_from_trace'):
                return self.trace_provider.extract_prompts_from_trace(trace)
            else:
                logger.warning("LangSmith provider lacks extract_prompts_from_trace method")
                return self._empty_extraction_result()

        elif self.extractor:
            # Use dedicated extractor for Langfuse/OTLP
            try:
                prompt_data = await self.extractor.extract(trace)
                return self._convert_to_langsmith_format(prompt_data)
            except Exception as e:
                logger.warning(
                    "Async extraction failed, returning empty results",
                    provider=self.provider_name,
                    error=str(e)
                )
                return self._empty_extraction_result()

        return self._empty_extraction_result()
