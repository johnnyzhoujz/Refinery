#!/usr/bin/env python3
"""
Test if text.format vs response_format makes the difference for Responses API.
"""

import json
import tiktoken
import tempfile
import openai
from pathlib import Path
from refinery.utils.config import config
from refinery.agents.staged_schemas import TRACE_ANALYSIS_SCHEMA

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken"""
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

def test_text_format():
    """Test using text.format structure as mentioned in status doc"""
    
    print("\n🧪 TESTING WITH text.format STRUCTURE")
    
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
    
    client = openai.Client(api_key=config.openai_api_key)
    empty_vector_store = client.vector_stores.create(
        name="text_format_test",
        expires_after={"anchor": "last_active_at", "days": 1}
    )
    
    # Create batch using text.format structure from status doc
    batch_body = {
        "model": "gpt-4o",
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [empty_vector_store.id],
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
        "text": {  # Using text.format instead of response_format
            "format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "trace_analysis",
                    "strict": True,
                    "schema": TRACE_ANALYSIS_SCHEMA  # Full schema
                }
            }
        }
    }
    
    batch_request = {
        "custom_id": "text_format_test",
        "method": "POST",
        "url": "/v1/responses",
        "body": batch_body
    }
    
    # Check token count
    jsonl_content = json.dumps(batch_request)
    final_tokens = count_tokens(jsonl_content)
    
    print(f"📊 TOKEN BREAKDOWN (text.format):")
    print(f"Final request: {final_tokens} tokens")
    
    # Test submission
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(jsonl_content + '\n')
            batch_file_path = f.name
        
        with open(batch_file_path, 'rb') as f:
            batch_file = client.files.create(file=f, purpose="batch")
        
        batch = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/responses",
            completion_window="24h"
        )
        
        print(f"✅ SUCCESS: text.format batch submitted - {batch.id}")
        
        try:
            client.batches.cancel(batch.id)
            print(f"✅ Cancelled: {batch.id}")
        except:
            pass
        
        result = "SUCCESS"
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        if "90" in str(e) and ("token" in str(e).lower() or "limit" in str(e).lower()):
            print(f"🎯 This is the 90K token limit error!")
        result = f"FAILED: {e}"
    
    # Cleanup
    Path(batch_file_path).unlink()
    try:
        client.vector_stores.delete(empty_vector_store.id)
    except:
        pass
    
    return result, final_tokens

def main():
    print("🔬 TESTING text.format vs response_format")
    print("=" * 50)
    
    result, tokens = test_text_format()
    
    print(f"\n🎯 RESULT:")
    print(f"text.format test: {result}")
    print(f"Total tokens: {tokens}")
    
    if "SUCCESS" in result:
        print(f"\n✅ text.format works at {tokens} tokens")
        print(f"   → This format is compatible with Responses API")
    else:
        print(f"\n❌ text.format failed!")
        print(f"   → This might be the format issue mentioned in status doc")

if __name__ == "__main__":
    main()