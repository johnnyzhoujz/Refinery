"""
Mock LLM provider for testing without API calls.

This module provides mock implementations for OpenAI Responses API
to enable testing without making actual API calls or incurring token costs.
"""

import json
from typing import Any, Dict, Iterator, List, Optional


class MockResponsesClient:
    """
    Mock OpenAI Responses client for testing.

    Usage:
        mock_client = MockResponsesClient(seeded_responses=[
            {"role": "assistant", "content": '{"diagnosis": "..."}'},
            {"role": "assistant", "content": '{"hypotheses": [...]}'}
        ])

        response = await mock_client.create_with_retry(body={...})
    """

    def __init__(self, seeded_responses: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize mock client with seeded responses.

        Args:
            seeded_responses: List of response dicts to return in sequence
        """
        self.seeded_responses = seeded_responses or []
        self._response_iter: Iterator[Dict[str, Any]] = iter(self.seeded_responses)
        self.call_count = 0
        self.last_request = None

    async def create_with_retry(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock create_with_retry that returns the next seeded response.

        Args:
            body: Request body (stored but not used)

        Returns:
            Dict: Next seeded response

        Raises:
            StopIteration: If no more seeded responses
        """
        self.call_count += 1
        self.last_request = body

        try:
            response = next(self._response_iter)
            return {
                "id": f"mock-response-{self.call_count}",
                "model": body.get("model", "gpt-4o"),
                "choices": [{"message": response, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "total_tokens": 300,
                },
            }
        except StopIteration:
            raise ValueError(
                f"Mock: No more seeded responses available (called {self.call_count} times)"
            )

    def reset(self) -> None:
        """Reset the mock client to reuse seeded responses."""
        self._response_iter = iter(self.seeded_responses)
        self.call_count = 0
        self.last_request = None


class MockLLMProvider:
    """
    Mock LLM provider for simple completions.

    Usage:
        mock_provider = MockLLMProvider(fixed_response="This is a mock response")
        response = await mock_provider.complete("test prompt")
    """

    def __init__(self, fixed_response: Optional[str] = None):
        """
        Initialize mock provider with optional fixed response.

        Args:
            fixed_response: Response to return for all requests
        """
        self.fixed_response = fixed_response or "Mock LLM response"
        self.call_count = 0
        self.last_prompt = None
        self.last_system_prompt = None

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Mock completion that returns fixed response.

        Args:
            prompt: User prompt (stored but not used)
            system_prompt: System prompt (stored but not used)
            temperature: Temperature (ignored)
            max_tokens: Max tokens (ignored)

        Returns:
            str: Fixed response string
        """
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return self.fixed_response

    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mock tool-based completion.

        Args:
            prompt: User prompt
            tools: Available tools
            system_prompt: System prompt

        Returns:
            Dict: Mock tool call response
        """
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        return {"content": self.fixed_response, "tool_calls": []}


def create_mock_diagnosis_response() -> Dict[str, Any]:
    """
    Create a mock diagnosis response for testing.

    Returns:
        Dict: Mock diagnosis in expected format
    """
    return {
        "role": "assistant",
        "content": json.dumps(
            {
                "failure_type": "prompt_issue",
                "root_cause": "Intent classifier prompt lacks explicit examples for billing/subscription intents",
                "evidence": [
                    "Intent classified as 'general_inquiry' with only 65% confidence",
                    "Customer query explicitly mentions 'cancel subscription' and 'refund'",
                    "Knowledge base retrieval returned general FAQ content instead of billing procedures",
                ],
                "affected_components": ["IntentClassifier", "RetrieveKnowledgeBase"],
                "confidence": "high",
                "detailed_analysis": "The intent classifier prompt does not provide clear examples of billing-related intents, causing misclassification of subscription/refund queries.",
            }
        ),
    }


def create_mock_hypotheses_response() -> Dict[str, Any]:
    """
    Create a mock hypotheses response for testing.

    Returns:
        Dict: Mock hypotheses in expected format
    """
    return {
        "role": "assistant",
        "content": json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "hyp-001",
                        "description": "Add explicit billing intent examples to classifier prompt",
                        "rationale": "Adding examples will help the classifier distinguish billing queries from general inquiries",
                        "confidence": "high",
                        "risks": [
                            "May increase prompt length",
                            "Requires testing with varied billing queries",
                        ],
                        "proposed_changes": [
                            {
                                "file_path": "prompts/intent_classifier.txt",
                                "change_type": "prompt_modification",
                                "original_content": "Classify intent into: [general_inquiry, technical_support, account_issue]",
                                "new_content": "Classify intent into: [general_inquiry, technical_support, account_issue, billing_issue]\n\nExamples:\n- 'cancel subscription' → billing_issue\n- 'refund request' → billing_issue",
                                "description": "Add billing intent category with examples",
                            }
                        ],
                    }
                ]
            }
        ),
    }


def create_mock_vector_store_response() -> Dict[str, Any]:
    """
    Create a mock vector store creation response.

    Returns:
        Dict: Mock vector store metadata
    """
    return {
        "id": "vs_mock_123",
        "object": "vector_store",
        "created_at": 1729000000,
        "name": "mock_trace_analysis",
        "status": "completed",
        "file_counts": {
            "in_progress": 0,
            "completed": 1,
            "failed": 0,
            "cancelled": 0,
            "total": 1,
        },
    }
