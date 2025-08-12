#!/usr/bin/env python3
"""
Test Vector Store creation and File Search integration.
"""
import asyncio
import json
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refinery.integrations.vector_store_manager import VectorStoreManager
from refinery.integrations.responses_client import ResponsesClient
from refinery.integrations.responses_request_builder import build_responses_body
from refinery.utils.config import config

async def test_vector_store_integration():
    """Test vector store creation and file search with Responses API."""
    
    if not config.openai_api_key:
        print("❌ OPENAI_API_KEY not configured")
        return False
    
    print("🧪 Testing Vector Store + File Search integration...")
    
    # Initialize managers
    vs_manager = VectorStoreManager()
    responses_client = ResponsesClient(config.openai_api_key)
    
    try:
        # Create vector store
        print("📦 Creating vector store...")
        vector_store = vs_manager.client.vector_stores.create(
            name=f"test_refinery_{int(asyncio.get_event_loop().time())}",
            expires_after={
                "anchor": "last_active_at",
                "days": 1
            }
        )
        vector_store_id = vector_store.id
        print(f"✅ Created vector store: {vector_store_id}")
        
        # Upload test file
        print("📁 Uploading test content...")
        test_content = """# Test Agent Trace
        
## Run 1: User Query
**Input**: "What is the weather today?"
**Output**: "I need to check the weather service for you."
**Status**: success

## Run 2: Weather Service Call
**Input**: {"location": "San Francisco", "date": "2024-08-12"}
**Output**: {"temperature": 72, "condition": "sunny"}
**Status**: success

## Run 3: Response Generation
**Input**: "Format weather response for user"
**Output**: "The weather in San Francisco today is 72°F and sunny."
**Status**: success
"""
        
        file_obj = await vs_manager._upload_file_content("test_trace.md", test_content)
        print(f"✅ Uploaded file: {file_obj.id}")
        
        # Add file to vector store
        vs_manager.client.vector_stores.file_batches.create(
            vector_store_id=vector_store_id,
            file_ids=[file_obj.id]
        )
        print("📋 Added file to vector store")
        
        # Wait for indexing
        print("⏳ Waiting for indexing to complete...")
        await vs_manager._poll_vector_store_ready(vector_store_id, max_wait_minutes=5)
        print("✅ Vector store ready")
        
        # Test file search with Responses API
        print("🔍 Testing file search...")
        
        # Create schema for search results
        search_schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "runs_found": {"type": "integer"}
            },
            "required": ["summary", "runs_found"],
            "additionalProperties": False
        }
        
        # Build request with file search
        body = build_responses_body(
            model="gpt-4o",
            vector_store_id=vector_store_id,
            system_text="You are a trace analyzer. Use file_search to find information about runs and weather data.",
            user_text="Search the trace and count the total number of runs. Provide a brief summary of what you found.",
            json_schema_obj=search_schema,
            max_num_results=5,
            max_output_tokens=500
        )
        
        print("📤 Sending search request...")
        response = await responses_client.create(body)
        
        # Parse result
        result = responses_client.parse_json_output(response)
        
        print("✅ File search successful!")
        print(f"📊 Search result: {json.dumps(result, indent=2)}")
        
        # Cleanup
        print("🧹 Cleaning up...")
        vs_manager.cleanup_vector_store(vector_store_id)
        print("✅ Vector store cleaned up")
        
        return True
        
    except Exception as e:
        print(f"❌ Vector store test failed: {str(e)}")
        # Try cleanup on error
        try:
            if 'vector_store_id' in locals():
                vs_manager.cleanup_vector_store(vector_store_id)
        except:
            pass
        return False

if __name__ == "__main__":
    success = asyncio.run(test_vector_store_integration())
    sys.exit(0 if success else 1)