"""Schema pinning tests for Responses client parsing."""

from __future__ import annotations

import asyncio
import json

import pytest

from refinery.integrations.responses_client import ResponsesClient
from refinery.integrations.responses_request_builder import build_responses_body


def _build_sample_response() -> dict:
    """Construct a minimal Responses payload with reasoning + file search."""
    return {
        "id": "resp_123",
        "status": "succeeded",
        "output": [
            {
                "type": "file_search_call",
                "id": "call_1",
                "results": [
                    {
                        "document_id": "doc_1",
                        "chunk_id": "chunk_1",
                        "score": 0.99,
                    }
                ],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "analysis": {
                                    "finding": "Agent acknowledged issue",
                                    "confidence": "high",
                                }
                            }
                        ),
                    }
                ],
            },
        ],
    }


def test_parse_json_output_includes_file_search_metadata() -> None:
    """Test that parsing extracts both JSON content and file search metadata."""
    client = ResponsesClient("sk-test")
    sample = _build_sample_response()

    # parse_json_output returns just the JSON content
    parsed = client.parse_json_output(sample)
    assert parsed["analysis"]["finding"] == "Agent acknowledged issue"
    assert parsed["analysis"]["confidence"] == "high"

    # Metadata extraction is tested via create_background (see test_create_background_polls_to_completion)


def test_parse_json_output_incomplete_raises() -> None:
    client = ResponsesClient("sk-test")
    sample = {
        "id": "resp_incomplete",
        "status": "incomplete",
        "incomplete_details": {"reason": "content_filter"},
        "output": [],
    }

    with pytest.raises(Exception):
        client.parse_json_output(sample)


def test_build_responses_body_gpt5_omits_legacy_params() -> None:
    body = build_responses_body(
        model="gpt-5",
        vector_store_id="vs_123",
        system_text="sys",
        user_text="user",
        json_schema_obj={"type": "object"},
        max_num_results=5,
        max_output_tokens=999,
        temperature=0.5,
        reasoning_effort="medium",
        seed=42,
    )

    assert "temperature" not in body
    assert body["max_output_tokens"] == 999
    assert body["reasoning"] == {"effort": "medium"}
    assert "seed" not in body


def test_build_responses_body_gpt4o_includes_legacy_params() -> None:
    body = build_responses_body(
        model="gpt-4o",
        vector_store_id="vs_123",
        system_text="sys",
        user_text="user",
        json_schema_obj={"type": "object"},
        max_num_results=5,
        max_output_tokens=999,
        temperature=0.5,
        reasoning_effort=None,
        seed=None,
    )

    assert body["temperature"] == 0.5
    assert body["max_output_tokens"] == 999
    assert "reasoning" not in body


def test_create_background_polls_to_completion(monkeypatch) -> None:
    client = ResponsesClient("sk-test")

    create_calls = {"count": 0}
    retrieve_calls = {"count": 0}

    async def fake_create(payload):
        create_calls["count"] += 1
        assert payload.get("background") is True
        assert payload.get("store") is True
        return {"id": "resp_bg", "status": "queued"}

    async def fake_retrieve(response_id):
        retrieve_calls["count"] += 1
        if retrieve_calls["count"] < 2:
            return {"id": response_id, "status": "in_progress"}
        final = _build_sample_response()
        final.update({"id": response_id, "status": "completed", "model": "gpt-5"})
        return final

    monkeypatch.setattr(client, "create", fake_create)
    monkeypatch.setattr(client, "retrieve", fake_retrieve)

    request_payload = {
        "model": "gpt-5",
        "input": [],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "stage_output",
                "strict": True,
                "schema": {"type": "object"},
            }
        },
    }

    async def _exercise():
        return await client.create_background(request_payload, poll_interval=0.0)

    parsed, metadata = asyncio.run(_exercise())

    assert parsed["analysis"]["finding"] == "Agent acknowledged issue"
    assert metadata["retrieved_chunk_ids"] == ["chunk_1"]
    assert create_calls["count"] == 1
    assert retrieve_calls["count"] == 2
    assert "background" not in request_payload
