"""
OTLP Prompt Extractor for OpenTelemetry traces.

This module extracts prompts from OTLP traces using official OpenTelemetry
GenAI semantic conventions with fallback support for non-compliant instrumentation.
"""

import json
from typing import Any, Dict, List, Optional

import structlog

from ...core.models import PromptData, RunType, Trace

logger = structlog.get_logger(__name__)


class OTLPPromptExtractor:
    """Extract prompts from OTLP traces using GenAI semantic conventions."""

    async def extract(self, trace: Trace) -> Optional[PromptData]:
        """
        Extract prompts from OTLP trace.

        Strategy (in priority order):
        1. Try official gen_ai.input.messages attribute (OpenTelemetry semantic convention)
        2. Try gen_ai.system_instructions attribute
        3. Minimal fallback for non-compliant instrumentation (inputs.messages, inputs.prompt)

        Args:
            trace: Trace object to extract prompts from

        Returns:
            PromptData with extracted prompts, or None if no prompts found
        """
        system_prompts = []
        user_prompts = []

        for run in trace.runs:
            if run.run_type != RunType.LLM:
                continue

            # 1. Try official gen_ai.input.messages (PRIMARY - OpenTelemetry standard)
            if "gen_ai.input.messages" in run.metadata:
                messages = self._parse_messages_attribute(
                    run.metadata["gen_ai.input.messages"]
                )
                for msg in messages:
                    role = msg.get("role", "")
                    # Try to extract content from parts array per OTLP spec
                    content = self._extract_content_from_parts(msg.get("parts", []))

                    # Fallback: If no parts array, try direct "content" field (legacy format)
                    if not content and "content" in msg:
                        content = msg["content"]

                    if content:
                        if role == "system":
                            system_prompts.append(content)
                        else:
                            user_prompts.append(content)
                continue

            # 2. Try official gen_ai.system_instructions
            if "gen_ai.system_instructions" in run.metadata:
                instructions = self._parse_messages_attribute(
                    run.metadata["gen_ai.system_instructions"]
                )
                for inst in instructions:
                    content = self._extract_content_from_parts(inst.get("parts", []))

                    # Fallback: If no parts array, try direct "content" field (legacy format)
                    if not content and "content" in inst:
                        content = inst["content"]

                    if content:
                        system_prompts.append(content)

            # 3. Minimal fallback for instrumentation drift
            if not system_prompts and not user_prompts:
                if isinstance(run.inputs, dict):
                    if "messages" in run.inputs:
                        for msg in run.inputs["messages"]:
                            if isinstance(msg, dict) and "content" in msg:
                                if msg.get("role") == "system":
                                    system_prompts.append(msg["content"])
                                else:
                                    user_prompts.append(msg["content"])
                    elif "prompt" in run.inputs:
                        user_prompts.append(run.inputs["prompt"])

        if not system_prompts and not user_prompts:
            return None

        return PromptData(
            system_prompts=system_prompts,
            user_prompts=user_prompts,
        )

    def _parse_messages_attribute(self, messages_data: Any) -> List[Dict]:
        """
        Parse gen_ai.input.messages JSON structure per OTLP spec.

        Args:
            messages_data: Either a JSON string or already-parsed list

        Returns:
            List of message dictionaries
        """
        if isinstance(messages_data, str):
            try:
                return json.loads(messages_data)
            except json.JSONDecodeError:
                logger.warning("Failed to parse messages JSON", data=messages_data)
                return []
        return messages_data if isinstance(messages_data, list) else []

    def _extract_content_from_parts(self, parts: List[Dict]) -> str:
        """
        Extract text content from message parts array per OTLP spec.

        OTLP spec (VERIFIED): parts = [{"type": "text", "content": "..."}, ...]
        Note: Field is "content" not "text" per official OpenTelemetry GenAI semantic conventions

        Args:
            parts: List of part dictionaries from the OTLP message structure

        Returns:
            Concatenated text content from all text parts
        """
        texts = []
        for part in parts:
            if isinstance(part, dict):
                if part.get("type") == "text" and "content" in part:
                    texts.append(part["content"])
        return "\n".join(texts) if texts else ""
