"""
Unit tests for OTLPPromptExtractor.

Tests extraction of prompts from OTLP traces using official OpenTelemetry
GenAI semantic conventions with fallback support.
"""

import json
from datetime import datetime

import pytest

from refinery.core.models import PromptData, RunType, Trace, TraceRun
from refinery.integrations.prompt_extractors import OTLPPromptExtractor


@pytest.fixture
def extractor():
    """Create OTLPPromptExtractor instance."""
    return OTLPPromptExtractor()


@pytest.fixture
def base_trace():
    """Create a base trace with no runs."""
    return Trace(
        trace_id="test-trace-1",
        project_name="test-project",
        runs=[],
        start_time=datetime(2025, 1, 1, 0, 0, 0),
        end_time=datetime(2025, 1, 1, 0, 0, 5),
        metadata={},
    )


def create_llm_run(
    run_id: str,
    metadata: dict = None,
    inputs: dict = None,
) -> TraceRun:
    """Helper to create LLM TraceRun for testing."""
    return TraceRun(
        id=run_id,
        name="llm.call",
        run_type=RunType.LLM,
        inputs=inputs or {},
        outputs=None,
        start_time=datetime(2025, 1, 1, 0, 0, 0),
        end_time=datetime(2025, 1, 1, 0, 0, 5),
        error=None,
        parent_run_id=None,
        trace_id="test-trace-1",
        dotted_order="1",
        metadata=metadata or {},
    )


class TestGenAIInputMessages:
    """Test extraction from gen_ai.input.messages attribute (official semantic convention)."""

    @pytest.mark.asyncio
    async def test_extract_from_gen_ai_input_messages_json_string(
        self, extractor, base_trace
    ):
        """Test extraction when gen_ai.input.messages is a JSON string."""
        messages_json = json.dumps(
            [
                {
                    "role": "system",
                    "parts": [{"type": "text", "content": "You are a helpful assistant."}],
                },
                {
                    "role": "user",
                    "parts": [{"type": "text", "content": "Hello, how are you?"}],
                },
            ]
        )

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages_json},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.system_prompts == ["You are a helpful assistant."]
        assert result.user_prompts == ["Hello, how are you?"]

    @pytest.mark.asyncio
    async def test_extract_from_gen_ai_input_messages_list(self, extractor, base_trace):
        """Test extraction when gen_ai.input.messages is already a list."""
        messages_list = [
            {
                "role": "system",
                "parts": [{"type": "text", "content": "System prompt here."}],
            },
            {
                "role": "user",
                "parts": [{"type": "text", "content": "User question here."}],
            },
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages_list},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.system_prompts == ["System prompt here."]
        assert result.user_prompts == ["User question here."]

    @pytest.mark.asyncio
    async def test_extract_multiple_text_parts(self, extractor, base_trace):
        """Test extraction with multiple text parts in a single message."""
        messages = [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "First part."},
                    {"type": "text", "content": "Second part."},
                    {"type": "text", "content": "Third part."},
                ],
            }
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.user_prompts == ["First part.\nSecond part.\nThird part."]

    @pytest.mark.asyncio
    async def test_extract_with_non_text_parts(self, extractor, base_trace):
        """Test that non-text parts are ignored (e.g., image parts)."""
        messages = [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "Text content."},
                    {"type": "image", "url": "https://example.com/image.jpg"},
                    {"type": "text", "content": "More text."},
                ],
            }
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.user_prompts == ["Text content.\nMore text."]

    @pytest.mark.asyncio
    async def test_extract_uses_content_field_not_text(self, extractor, base_trace):
        """Test that 'content' field is used, not 'text' (per OTLP spec)."""
        # Message with "text" field should NOT be extracted
        messages_wrong = [
            {
                "role": "user",
                "parts": [{"type": "text", "text": "This should not be extracted."}],
            }
        ]

        # Message with "content" field SHOULD be extracted
        messages_correct = [
            {
                "role": "user",
                "parts": [{"type": "text", "content": "This should be extracted."}],
            }
        ]

        run1 = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages_wrong},
        )
        base_trace.runs = [run1]

        result1 = await extractor.extract(base_trace)
        assert result1 is None  # Should not find anything

        run2 = create_llm_run(
            "run-2",
            metadata={"gen_ai.input.messages": messages_correct},
        )
        base_trace.runs = [run2]

        result2 = await extractor.extract(base_trace)
        assert result2 is not None
        assert result2.user_prompts == ["This should be extracted."]

    @pytest.mark.asyncio
    async def test_extract_multiple_messages_same_role(self, extractor, base_trace):
        """Test extraction with multiple messages of the same role."""
        messages = [
            {"role": "user", "parts": [{"type": "text", "content": "First question."}]},
            {
                "role": "user",
                "parts": [{"type": "text", "content": "Second question."}],
            },
            {"role": "user", "parts": [{"type": "text", "content": "Third question."}]},
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert len(result.user_prompts) == 3
        assert result.user_prompts == [
            "First question.",
            "Second question.",
            "Third question.",
        ]

    @pytest.mark.asyncio
    async def test_extract_legacy_format_with_direct_content(self, extractor, base_trace):
        """Test extraction from legacy format without parts array (direct content field)."""
        # Some OTLP implementations use {"role": "user", "content": "..."} instead of parts array
        messages_legacy = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages_legacy},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.system_prompts == ["You are a helpful assistant."]
        assert result.user_prompts == ["Hello, how are you?"]


class TestGenAISystemInstructions:
    """Test extraction from gen_ai.system_instructions attribute."""

    @pytest.mark.asyncio
    async def test_extract_from_system_instructions(self, extractor, base_trace):
        """Test extraction from gen_ai.system_instructions attribute."""
        instructions = [
            {
                "parts": [
                    {"type": "text", "content": "You are a helpful coding assistant."}
                ]
            }
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.system_instructions": instructions},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.system_prompts == ["You are a helpful coding assistant."]
        assert result.user_prompts == []

    @pytest.mark.asyncio
    async def test_extract_both_input_messages_and_system_instructions(
        self, extractor, base_trace
    ):
        """Test that gen_ai.input.messages takes priority over system_instructions."""
        # When both are present, input.messages should be used and system_instructions skipped
        messages = [
            {
                "role": "user",
                "parts": [{"type": "text", "content": "User message from input.messages"}],
            }
        ]
        instructions = [
            {
                "parts": [
                    {"type": "text", "content": "System from system_instructions"}
                ]
            }
        ]

        run = create_llm_run(
            "run-1",
            metadata={
                "gen_ai.input.messages": messages,
                "gen_ai.system_instructions": instructions,
            },
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        # Only input.messages should be processed (continue statement in code)
        assert result.user_prompts == ["User message from input.messages"]
        assert result.system_prompts == []


class TestFallbackExtraction:
    """Test fallback extraction for non-compliant instrumentation."""

    @pytest.mark.asyncio
    async def test_fallback_to_inputs_messages(self, extractor, base_trace):
        """Test fallback to run.inputs['messages'] format."""
        run = create_llm_run(
            "run-1",
            inputs={
                "messages": [
                    {"role": "system", "content": "System from inputs.messages"},
                    {"role": "user", "content": "User from inputs.messages"},
                ]
            },
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.system_prompts == ["System from inputs.messages"]
        assert result.user_prompts == ["User from inputs.messages"]

    @pytest.mark.asyncio
    async def test_fallback_to_inputs_prompt(self, extractor, base_trace):
        """Test fallback to run.inputs['prompt'] format."""
        run = create_llm_run(
            "run-1",
            inputs={"prompt": "Simple prompt from inputs.prompt"},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.user_prompts == ["Simple prompt from inputs.prompt"]
        assert result.system_prompts == []

    @pytest.mark.asyncio
    async def test_fallback_only_when_no_official_attributes(self, extractor, base_trace):
        """Test that fallback is only used when official attributes are missing."""
        # If official attributes exist, fallback should not be used
        messages = [
            {"role": "user", "parts": [{"type": "text", "content": "Official message"}]}
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
            inputs={"prompt": "This should be ignored"},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert result.user_prompts == ["Official message"]
        # Fallback should not be used
        assert "This should be ignored" not in result.user_prompts


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_trace(self, extractor, base_trace):
        """Test extraction from trace with no runs."""
        result = await extractor.extract(base_trace)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_llm_runs(self, extractor, base_trace):
        """Test extraction from trace with only non-LLM runs."""
        tool_run = TraceRun(
            id="run-1",
            name="tool.call",
            run_type=RunType.TOOL,
            inputs={},
            outputs=None,
            start_time=datetime(2025, 1, 1, 0, 0, 0),
            end_time=datetime(2025, 1, 1, 0, 0, 5),
            error=None,
            parent_run_id=None,
            trace_id="test-trace-1",
            dotted_order="1",
            metadata={},
        )
        base_trace.runs = [tool_run]

        result = await extractor.extract(base_trace)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_prompts_found(self, extractor, base_trace):
        """Test when LLM runs exist but no prompts can be extracted."""
        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.system": "anthropic"},  # No prompt attributes
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_in_messages(self, extractor, base_trace):
        """Test handling of invalid JSON in gen_ai.input.messages."""
        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": "invalid{json}"},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_parts_array(self, extractor, base_trace):
        """Test message with empty parts array."""
        messages = [{"role": "user", "parts": []}]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)
        assert result is None  # No content extracted

    @pytest.mark.asyncio
    async def test_missing_role_defaults_to_user(self, extractor, base_trace):
        """Test that messages without role are treated as user messages."""
        messages = [
            {
                # No role specified
                "parts": [{"type": "text", "content": "Message without role."}]
            }
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        # Should be treated as user message (role defaults to empty string, not "system")
        assert result.user_prompts == ["Message without role."]
        assert result.system_prompts == []

    @pytest.mark.asyncio
    async def test_multiple_llm_runs_aggregate_prompts(self, extractor, base_trace):
        """Test that prompts from multiple LLM runs are aggregated."""
        run1 = create_llm_run(
            "run-1",
            metadata={
                "gen_ai.input.messages": [
                    {"role": "user", "parts": [{"type": "text", "content": "First run."}]}
                ]
            },
        )
        run2 = create_llm_run(
            "run-2",
            metadata={
                "gen_ai.input.messages": [
                    {"role": "user", "parts": [{"type": "text", "content": "Second run."}]}
                ]
            },
        )
        base_trace.runs = [run1, run2]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert len(result.user_prompts) == 2
        assert "First run." in result.user_prompts
        assert "Second run." in result.user_prompts

    @pytest.mark.asyncio
    async def test_role_based_separation(self, extractor, base_trace):
        """Test that system and user prompts are correctly separated by role."""
        messages = [
            {
                "role": "system",
                "parts": [{"type": "text", "content": "System prompt 1"}],
            },
            {"role": "user", "parts": [{"type": "text", "content": "User prompt 1"}]},
            {
                "role": "system",
                "parts": [{"type": "text", "content": "System prompt 2"}],
            },
            {"role": "user", "parts": [{"type": "text", "content": "User prompt 2"}]},
            {
                "role": "assistant",
                "parts": [{"type": "text", "content": "Assistant response"}],
            },  # Should go to user_prompts
        ]

        run = create_llm_run(
            "run-1",
            metadata={"gen_ai.input.messages": messages},
        )
        base_trace.runs = [run]

        result = await extractor.extract(base_trace)

        assert result is not None
        assert len(result.system_prompts) == 2
        assert len(result.user_prompts) == 3  # user + user + assistant
        assert result.system_prompts == ["System prompt 1", "System prompt 2"]
        assert "User prompt 1" in result.user_prompts
        assert "User prompt 2" in result.user_prompts
        assert "Assistant response" in result.user_prompts
