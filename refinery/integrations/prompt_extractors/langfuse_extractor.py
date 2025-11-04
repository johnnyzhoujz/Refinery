"""
Langfuse prompt extractor for extracting prompts from traces.

This module provides extraction of prompts from Langfuse traces using both
the Prompt Management API for managed prompts and observation payload parsing
for ad-hoc prompts.
"""

from typing import Optional
import structlog
from ...core.models import Trace, RunType, PromptData

logger = structlog.get_logger(__name__)


class LangfusePromptExtractor:
    """Extract prompts from Langfuse using Prompt Management API."""

    def __init__(self, client):
        """
        Initialize extractor with Langfuse client.

        Args:
            client: LangfuseClient instance
        """
        self.client = client

    async def extract(self, trace: Trace) -> PromptData:
        """
        Extract prompts from Langfuse traces.

        Strategy:
        1. Check for promptName metadata → fetch from prompt API (native support)
        2. Fall back to observation payloads for ad hoc prompts (common case)

        Returns:
            PromptData with extracted prompts (never None, may be empty)
        """
        system_prompts = []
        user_prompts = []

        for run in trace.runs:
            if run.run_type != RunType.LLM:
                continue

            # Strategy 1: Try Langfuse Prompt Management API (for managed prompts)
            prompt_name = run.metadata.get("promptName")
            prompt_version = run.metadata.get("promptVersion")

            if prompt_name:
                try:
                    prompt_data = await self.client.fetch_prompt(
                        name=prompt_name,
                        version=prompt_version
                    )
                    # Parse prompt registry format
                    if prompt_data.get("type") == "chat":
                        # Chat prompt with messages array
                        for msg in prompt_data.get("prompt", []):
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if content:
                                if role == "system":
                                    system_prompts.append(content)
                                else:
                                    user_prompts.append(content)
                    elif prompt_data.get("type") == "text":
                        # Text prompt
                        content = prompt_data.get("prompt", "")
                        if content:
                            user_prompts.append(content)

                    continue  # Skip observation parsing if we got prompts from API

                except Exception as e:
                    logger.warning(
                        "Failed to fetch managed prompt, falling back to observation",
                        prompt_name=prompt_name,
                        error=str(e)
                    )

            # Strategy 2: Parse observation inputs/outputs for ad-hoc prompts
            if isinstance(run.inputs, dict):
                # Handle various Langfuse input formats
                if "messages" in run.inputs:
                    messages = run.inputs["messages"]
                    if isinstance(messages, list):
                        for msg in messages:
                            if isinstance(msg, dict):
                                role = msg.get("role", "")
                                content = msg.get("content", "")
                                if content:
                                    if role == "system":
                                        system_prompts.append(content)
                                    else:
                                        user_prompts.append(content)

                elif "prompt" in run.inputs:
                    # Simple prompt string
                    prompt = run.inputs["prompt"]
                    if isinstance(prompt, str) and prompt:
                        user_prompts.append(prompt)

        return PromptData(
            system_prompts=system_prompts,
            user_prompts=user_prompts,
        )