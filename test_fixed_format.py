#!/usr/bin/env python3
"""
Test the fixed batch format.
"""

import json
import asyncio
import tempfile
from pathlib import Path
import openai
from refinery.utils.config import config

async def main():
    client = openai.Client(api_key=config.openai_api_key)
    
    # Create minimal vector store for testing
    vs = client.vector_stores.create(name="test_fixed_format")
    print(f"Created vector store: {vs.id}")
    
    # Test request with corrected format
    batch_request = {
        "custom_id": "test-fixed-format",
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": "gpt-4o",
            "tools": [{"type": "file_search"}],
            "tool_resources": {
                "file_search": {
                    "vector_store_ids": [vs.id]
                }
            },
            "input": [
                {"type": "message", "role": "system", "content": [{"type": "text", "text": "Say WORKS"}]},
                {"type": "message", "role": "user", "content": [{"type": "text", "text": "Test"}]}
            ],
            "temperature": 0,
            "max_output_tokens": 100,
            "text": {
                "format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "test_response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string"}
                            },
                            "required": ["status"],
                            "additionalProperties": False
                        }
                    }
                }
            }
        }
    }
    
    # Write JSONL
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps(batch_request) + '\n')
        batch_file_path = f.name
    
    # Upload and submit
    with open(batch_file_path, 'rb') as f:
        batch_file = client.files.create(file=f, purpose="batch")
    
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/responses",
        completion_window="24h"
    )
    print(f"Submitted batch: {batch.id}")
    
    # Poll
    for i in range(30):
        batch = client.batches.retrieve(batch.id)
        print(f"  Attempt {i}: {batch.status}", end="")
        
        if batch.request_counts:
            print(f" (completed={batch.request_counts.completed}, failed={batch.request_counts.failed})")
        else:
            print()
        
        if batch.status == "completed":
            if batch.request_counts and batch.request_counts.completed > 0:
                result_file = client.files.content(batch.output_file_id)
                result_content = result_file.content.decode('utf-8')
                print(f"\n✅ SUCCESS! Output:\n{result_content}")
            else:
                error_file = client.files.content(batch.error_file_id)
                error_content = error_file.content.decode('utf-8')
                print(f"\n❌ Failed:\n{error_content}")
            break
        elif batch.status == "failed":
            print(f"\n❌ Batch failed!")
            if hasattr(batch, 'errors'):
                print(f"Errors: {batch.errors}")
            break
        
        await asyncio.sleep(10)
    
    # Cleanup
    Path(batch_file_path).unlink(missing_ok=True)
    client.vector_stores.delete(vs.id)
    print(f"Cleaned up vector store: {vs.id}")

if __name__ == "__main__":
    asyncio.run(main())