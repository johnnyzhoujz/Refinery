"""
Pytest configuration and fixtures for Refinery tests.

This module provides reusable fixtures for mocking LangSmith and LLM clients,
enabling tests to run without API calls or environment variables.
"""

import os
from typing import Any, Dict
from unittest.mock import patch

import pytest

from refinery.utils.config import config
from tests.mocks.langsmith_mock import MockLangSmithClient, create_mock_trace_data
from tests.mocks.llm_mock import (
    MockLLMProvider,
    MockResponsesClient,
    create_mock_diagnosis_response,
    create_mock_hypotheses_response,
)


@pytest.fixture
def mock_langsmith_client():
    """
    Fixture providing a MockLangSmithClient with a basic trace.

    Usage:
        def test_something(mock_langsmith_client):
            trace = await mock_langsmith_client.fetch_trace("mock-trace-001")
    """
    trace_data = create_mock_trace_data()
    return MockLangSmithClient(fixed_responses={"mock-trace-001": trace_data})


@pytest.fixture
def mock_langsmith_client_with_custom_trace():
    """
    Factory fixture for creating MockLangSmithClient with custom trace data.

    Usage:
        def test_something(mock_langsmith_client_with_custom_trace):
            client = mock_langsmith_client_with_custom_trace({
                "trace-123": {"runs": [...]}
            })
    """

    def _create_client(trace_responses: Dict[str, Any]):
        return MockLangSmithClient(fixed_responses=trace_responses)

    return _create_client


@pytest.fixture
def mock_responses_client():
    """
    Fixture providing a MockResponsesClient with diagnosis + hypotheses responses.

    Usage:
        def test_something(mock_responses_client):
            response = await mock_responses_client.create_with_retry(body={...})
    """
    seeded_responses = [
        create_mock_diagnosis_response(),
        create_mock_hypotheses_response(),
    ]
    return MockResponsesClient(seeded_responses=seeded_responses)


@pytest.fixture
def mock_responses_client_with_custom_responses():
    """
    Factory fixture for creating MockResponsesClient with custom seeded responses.

    Usage:
        def test_something(mock_responses_client_with_custom_responses):
            client = mock_responses_client_with_custom_responses([
                {"role": "assistant", "content": '{"result": "test"}'}
            ])
    """

    def _create_client(seeded_responses: list):
        return MockResponsesClient(seeded_responses=seeded_responses)

    return _create_client


@pytest.fixture
def mock_llm_provider():
    """
    Fixture providing a MockLLMProvider for simple completions.

    Usage:
        def test_something(mock_llm_provider):
            response = await mock_llm_provider.complete("test prompt")
    """
    return MockLLMProvider(fixed_response="Mock LLM response")


def create_sample_trace_data(
    trace_id: str = "test-trace", with_failure: bool = True
) -> Dict[str, Any]:
    """
    Helper function to create sample trace data for tests.

    Args:
        trace_id: The trace ID to use
        with_failure: Whether to include a failed run

    Returns:
        Dict containing trace data compatible with MockLangSmithClient
    """
    runs = [
        {
            "id": "run-001",
            "name": "RootChain",
            "run_type": "chain",
            "inputs": {"query": "test query"},
            "outputs": {"result": "test result"},
            "start_time": "2025-10-15T10:00:00.000Z",
            "end_time": "2025-10-15T10:00:10.000Z",
            "error": None,
            "parent_run_id": None,
            "dotted_order": "1",
            "metadata": {},
        }
    ]

    if with_failure:
        runs.append(
            {
                "id": "run-002",
                "name": "FailedLLMCall",
                "run_type": "llm",
                "inputs": {"prompt": "test prompt"},
                "outputs": None,
                "start_time": "2025-10-15T10:00:01.000Z",
                "end_time": "2025-10-15T10:00:05.000Z",
                "error": "API rate limit exceeded",
                "parent_run_id": "run-001",
                "dotted_order": "1.1",
                "metadata": {},
            }
        )

    return {
        "trace_id": trace_id,
        "project_name": "test-project",
        "runs": runs,
        "metadata": {"source": "test"},
    }


def create_hypothesis_response_for_trace(trace_id: str) -> Dict[str, Any]:
    """
    Helper function to create a hypothesis response that matches a trace.

    Args:
        trace_id: The trace ID this hypothesis is for

    Returns:
        Dict containing hypothesis response in expected format
    """
    import json

    return {
        "role": "assistant",
        "content": json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "hyp-001",
                        "description": f"Fix for trace {trace_id}",
                        "rationale": "This fix addresses the root cause identified in the diagnosis",
                        "confidence": "high",
                        "risks": ["May require testing with production data"],
                        "example_before": "Current behavior shows error",
                        "example_after": "Expected behavior after fix",
                        "proposed_changes": [
                            {
                                "file_path": "prompts/system_prompt.txt",
                                "change_type": "prompt_modification",
                                "original_content": "Current system prompt",
                                "new_content": "Improved system prompt with better instructions",
                                "description": "Add explicit error handling instructions",
                            }
                        ],
                    }
                ]
            }
        ),
    }


# Environment variable management for tests
@pytest.fixture(autouse=True)
def preserve_env():
    """
    Automatically preserve and restore environment variables for each test.

    This ensures tests don't pollute each other's environment.
    """
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def mock_llm_config():
    """
    Automatically provide OpenAI API key for all tests.

    This allows tests that instantiate RefineryOrchestrator to run without
    real API credentials in CI environments. The orchestrator eagerly initializes
    the LLM provider in __init__, which validates the OpenAI key even if the
    test never uses LLM functionality.

    Tests that actually need to test LLM behavior can override this fixture
    or provide their own mocks.
    """
    with patch.object(config, 'openai_api_key', 'test-key-for-ci'):
        yield


# Mark for live tests that require API keys
def pytest_configure(config):
    """Register custom markers for pytest."""
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring live API access (skipped unless REFINERY_RUN_LIVE_TESTS is set)",
    )
