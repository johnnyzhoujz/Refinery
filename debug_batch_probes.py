#!/usr/bin/env python3
"""
Debug batch API with three methodical probes.
"""

import json
import asyncio
import tempfile
from pathlib import Path
import openai
from refinery.utils.config import config

async def run_probe(probe_num: int, batch_request: dict, description: str):
    """Run a single probe and report results."""
    print(f"\n{'='*60}")
    print(f"PROBE {probe_num}: {description}")
    print(f"{'='*60}")
    
    client = openai.Client(api_key=config.openai_api_key)
    
    # Write JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        json_line = json.dumps(batch_request)
        f.write(json_line + '\n')
        batch_file_path = f.name
    
    print(f"JSONL line:\n{json_line}\n")
    
    try:
        # Upload file
        with open(batch_file_path, 'rb') as f:
            batch_file = client.files.create(file=f, purpose="batch")
        print(f"✓ Uploaded file: {batch_file.id}")
        
        # Submit batch - note: endpoint should match the one in JSONL
        batch = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/responses",  # Must match JSONL endpoint
            completion_window="24h"
        )
        print(f"✓ Submitted batch: {batch.id}")
        
        # Poll for completion
        for i in range(30):  # Max 5 minutes
            batch = client.batches.retrieve(batch.id)
            
            if i == 0 or batch.status != "validating":
                print(f"  Attempt {i}: status={batch.status}", end="")
                if batch.request_counts:
                    counts = batch.request_counts
                    print(f" (total={counts.total}, completed={counts.completed}, failed={counts.failed})")
                else:
                    print()
            
            if batch.status == "completed":
                print(f"\n✅ BATCH COMPLETED!")
                
                # Check counts
                if batch.request_counts and batch.request_counts.completed > 0:
                    # Read output
                    result_file = client.files.content(batch.output_file_id)
                    result_content = result_file.content.decode('utf-8')
                    print(f"Output file ID: {batch.output_file_id}")
                    print(f"Output (first 500 chars):\n{result_content[:500]}")
                    
                    # Parse first line
                    first_line = result_content.strip().split('\n')[0]
                    result_json = json.loads(first_line)
                    if result_json.get("response", {}).get("status_code") == 200:
                        print("✅ Request successful!")
                    else:
                        print(f"❌ Request failed with status: {result_json.get('response', {}).get('status_code')}")
                else:
                    # Read error file
                    if batch.error_file_id:
                        error_file = client.files.content(batch.error_file_id)
                        error_content = error_file.content.decode('utf-8')
                        print(f"❌ NO SUCCESSFUL REQUESTS")
                        print(f"Error file ID: {batch.error_file_id}")
                        print(f"Error content:\n{error_content[:1000]}")
                break
                
            elif batch.status == "failed":
                print(f"\n❌ BATCH FAILED!")
                
                # Try to get error details
                if hasattr(batch, 'errors') and batch.errors:
                    print(f"Batch errors: {batch.errors}")
                
                if hasattr(batch, 'error_file_id') and batch.error_file_id:
                    try:
                        error_file = client.files.content(batch.error_file_id)
                        error_content = error_file.content.decode('utf-8')
                        print(f"Error file content:\n{error_content[:1000]}")
                    except Exception as e:
                        print(f"Could not read error file: {e}")
                break
            
            await asyncio.sleep(10)
        else:
            print(f"\n⏱ Timeout after 5 minutes")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    finally:
        # Cleanup
        Path(batch_file_path).unlink(missing_ok=True)


async def main():
    print("Starting Batch API Debug Probes")
    print(f"Base URL: https://api.openai.com/v1")
    print(f"Model: gpt-4o")
    
    # PROBE 1: Basic /v1/responses with no tools
    probe1 = {
        "custom_id": "probe1-responses-no-tools",
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": "gpt-4o",
            "input": [
                {"type": "message", "role": "system", "content": [{"type": "text", "text": "Reply with the word PONG only."}]},
                {"type": "message", "role": "user", "content": [{"type": "text", "text": "PING"}]}
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": [],
                        "additionalProperties": True
                    }
                }
            }
        }
    }
    
    await run_probe(1, probe1, "Basic /v1/responses with no tools")
    
    # PROBE 2: Add file_search tool without vector store
    probe2 = {
        "custom_id": "probe2-responses-tool-only",
        "method": "POST",
        "url": "/v1/responses",
        "body": {
            "model": "gpt-4o",
            "tools": [{"type": "file_search"}],
            "input": [
                {"type": "message", "role": "system", "content": [{"type": "text", "text": "Say the word READY only."}]}
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": {"type": "object"}
                }
            }
        }
    }
    
    await run_probe(2, probe2, "Add file_search tool without vector store")
    
    # PROBE 3: Full file_search with vector store
    # First create a simple vector store
    client = openai.Client(api_key=config.openai_api_key)
    
    # Create minimal vector store
    vs = client.vector_stores.create(name="probe3_test_store")
    print(f"\nCreated test vector store: {vs.id}")
    
    # Upload a simple test file
    test_content = "This is a test document for probe 3. It contains sample text."
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        test_file_path = f.name
    
    with open(test_file_path, 'rb') as f:
        test_file = client.files.create(file=f, purpose="assistants")
    
    # Add to vector store
    client.vector_stores.files.create(vector_store_id=vs.id, file_id=test_file.id)
    
    # Wait for indexing
    print("Waiting for vector store to be ready...")
    for _ in range(30):
        vs_status = client.vector_stores.retrieve(vs.id)
        if vs_status.status == "completed":
            print(f"✓ Vector store ready: {vs.id}")
            break
        await asyncio.sleep(2)
    
    probe3 = {
        "custom_id": "probe3-responses-file-search",
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
                {"type": "message", "role": "system", "content": [{"type": "text", "text": "Use file_search if needed. Reply OK."}]}
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": {"type": "object"}
                }
            }
        }
    }
    
    await run_probe(3, probe3, "Full file_search with vector store")
    
    # Cleanup
    Path(test_file_path).unlink(missing_ok=True)
    try:
        client.vector_stores.delete(vs.id)
        print(f"Cleaned up vector store: {vs.id}")
    except:
        pass
    
    print("\n" + "="*60)
    print("PROBES COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())