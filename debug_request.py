#!/usr/bin/env python3
"""Debug the exact request being sent"""

import json
from refinery.agents.staged_schemas import TRACE_ANALYSIS_SCHEMA

# Recreate the exact request structure
system_prompt = """You are an impartial agent-behavior analyst.

Use the file_search tool to retrieve only what you need in bounded passes:
- max_num_results per pass: 8
- Stop after 6 passes OR if a pass yields no new sections
- Track coverage: coverage.files_scanned[], coverage.remaining[]

Rules:
- Cite evidence with {file, section_or_lines} when possible (rough is OK for POC).
- Output VALID JSON only that matches the provided schema. No prose outside JSON.
- If coverage is incomplete when you stop, state it explicitly in the JSON."""

user_prompt = """Task: Produce an evidence-backed timeline of the agent execution.

Retrieval protocol:
1) Query for sections containing "run", "tool", "input", "output", "error", "exception".
2) Iterate passes (max 6). In each pass, fetch at most 8 chunks. Avoid repeating already-seen sections.
3) Build:
   - timeline[]: ordered runs with key inputs/outputs and tool calls
   - events[]: failures/retries/anomalies
   - coverage: { files_scanned[], remaining[] }
   - evidence[]: { file, section_or_lines, rationale }

Return JSON only per schema. If you hit the stop condition with remaining sections, include them in coverage.remaining."""

batch_body = {
    "model": "gpt-4o",
    "tools": [
        {
            "type": "file_search",
            "vector_store_ids": ["vs_test"],
            "max_num_results": 8
        }
    ],
    "input": [
        {
            "type": "message",
            "role": "system", 
            "content": [{"type": "input_text", "text": system_prompt}]
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt}]
        }
    ],
    "temperature": 0.2,
    "max_output_tokens": 800,
    "text": {
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "trace_analysis",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "timeline": {"type": "array"},
                        "events": {"type": "array"},
                        "coverage": {"type": "object"},
                        "evidence": {"type": "array"}
                    },
                    "required": ["timeline", "events", "coverage", "evidence"],
                    "additionalProperties": False
                }
            }
        }
    }
}

batch_request = {
    "custom_id": "debug_test",
    "method": "POST",
    "url": "/v1/responses",
    "body": batch_body
}

print("=== BATCH REQUEST DEBUG ===")
print(json.dumps(batch_request, indent=2))

print("\n=== STRUCTURE CHECK ===")
print(f"Has text: {'text' in batch_body}")
print(f"Has text.format: {'format' in batch_body.get('text', {})}")
print(f"Has json_schema: {'json_schema' in batch_body.get('text', {}).get('format', {})}")

format_obj = batch_body.get('text', {}).get('format', {})
json_schema_obj = format_obj.get('json_schema', {})

print(f"format keys: {list(format_obj.keys())}")
print(f"json_schema keys: {list(json_schema_obj.keys())}")

print(f"\nname in json_schema: {'name' in json_schema_obj}")
print(f"name value: {json_schema_obj.get('name', 'MISSING')}")

print("\n=== PATH CHECK ===")
try:
    name_path = batch_body['text']['format']['json_schema']['name']
    print(f"✅ text.format.json_schema.name = {name_path}")
except KeyError as e:
    print(f"❌ Missing path: {e}")