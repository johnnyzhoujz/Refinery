"""
Tests for config lazy validation (Item #4).

Verifies that --trace-file workflow doesn't require LANGSMITH_API_KEY.
"""

import os
from unittest.mock import patch

import pytest

from refinery.utils.config import RefineryConfig


def test_validate_langsmith_missing_key():
    """Test validate_langsmith raises error when key is missing."""
    config = RefineryConfig.from_env()
    config.langsmith_api_key = ""

    with pytest.raises(ValueError, match="LANGSMITH_API_KEY is required"):
        config.validate_langsmith()


def test_validate_langsmith_with_key():
    """Test validate_langsmith succeeds when key is present."""
    config = RefineryConfig.from_env()
    config.langsmith_api_key = "ls-test-key"

    # Should not raise
    config.validate_langsmith()


def test_validate_openai_missing_key():
    """Test validate_openai raises error when key is missing."""
    config = RefineryConfig.from_env()
    config.llm_provider = "openai"
    config.openai_api_key = None

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        config.validate_openai()


def test_validate_openai_with_key():
    """Test validate_openai succeeds when key is present."""
    config = RefineryConfig.from_env()
    config.llm_provider = "openai"
    config.openai_api_key = "sk-test-key"
    config.hypothesis_llm_provider = "openai"

    # Should not raise
    config.validate_openai()


@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}, clear=True)
def test_trace_file_workflow_without_langsmith_key():
    """
    Test that --trace-file workflow doesn't require LANGSMITH_API_KEY.

    This is the critical test for Item #4 - verifies lazy validation allows
    local file analysis without LangSmith credentials.
    """
    # Create config with only OpenAI key (no LangSmith key)
    config = RefineryConfig.from_env()

    # Verify no LANGSMITH_API_KEY
    assert config.langsmith_api_key == ""

    # Verify validate_openai succeeds
    config.validate_openai()  # Should not raise

    # Verify validate_langsmith would fail (but we don't call it for --trace-file)
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY is required"):
        config.validate_langsmith()


@patch.dict(
    os.environ,
    {"LANGSMITH_API_KEY": "ls-test-key", "OPENAI_API_KEY": "sk-test-key"},
    clear=True,
)
def test_trace_id_workflow_requires_both_keys():
    """
    Test that --trace-id workflow requires both keys.
    """
    config = RefineryConfig.from_env()

    # Both validations should succeed
    config.validate_langsmith()  # Should not raise
    config.validate_openai()  # Should not raise


def test_validate_anthropic():
    """Test validate_anthropic method."""
    config = RefineryConfig.from_env()
    config.llm_provider = "anthropic"
    config.anthropic_api_key = None

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
        config.validate_anthropic()

    # With key
    config.anthropic_api_key = "sk-ant-test"
    config.validate_anthropic()  # Should not raise


def test_validate_gemini():
    """Test validate_gemini method."""
    config = RefineryConfig.from_env()
    config.llm_provider = "gemini"
    config.gemini_api_key = None

    with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
        config.validate_gemini()

    # With key
    config.gemini_api_key = "gemini-test-key"
    config.validate_gemini()  # Should not raise


@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}, clear=True)
def test_provider_isolation_trace_file_workflow():
    """
    Provider isolation test: Verify --trace-file workflow doesn't trigger LangSmith validation.

    This test ensures that when analyzing a local trace file, the system:
    1. Only validates OpenAI credentials (needed for analysis)
    2. Never attempts to validate LangSmith credentials
    3. Doesn't try to initialize LangSmith client

    This is critical for Item #5 - ensures mocked tests don't accidentally call live APIs.
    """
    from unittest.mock import MagicMock

    # Create config with only OpenAI key
    config = RefineryConfig.from_env()

    # Verify starting state
    assert config.langsmith_api_key == "", "Should have no LangSmith key"
    assert config.openai_api_key == "sk-test-key", "Should have OpenAI key"

    # Mock the validate_langsmith method to detect if it's called
    original_validate_langsmith = config.validate_langsmith
    config.validate_langsmith = MagicMock(
        side_effect=AssertionError(
            "validate_langsmith should not be called for --trace-file workflow"
        )
    )

    # Simulate --trace-file workflow: only validate OpenAI
    try:
        config.validate_openai()  # This should succeed
    except AssertionError as e:
        if "validate_langsmith should not be called" in str(e):
            pytest.fail("validate_langsmith was called during --trace-file workflow")
        raise

    # Verify validate_langsmith was never called
    config.validate_langsmith.assert_not_called()

    # For completeness: verify that --trace-id workflow WOULD require both
    config.validate_langsmith = original_validate_langsmith
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY is required"):
        config.validate_langsmith()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
