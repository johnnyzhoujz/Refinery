"""
Vector Store management for staged analysis with File Search.

This module handles creating vector stores, uploading files, and polling for readiness.
"""

import json
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

import openai
from ..core.models import Trace, DomainExpertExpectation
from ..utils.config import config

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector stores for trace analysis with File Search."""
    
    def __init__(self):
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required for vector store operations")
        self.client = openai.Client(api_key=config.openai_api_key)
    
    async def create_analysis_vector_store(
        self,
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: Dict[str, str],
        eval_contents: Dict[str, str]
    ) -> str:
        """
        Create vector store with all analysis files.
        
        Returns:
            vector_store_id: The ID of the created and indexed vector store
        """
        logger.info(f"Creating vector store for analysis: trace_id={trace.trace_id}")
        
        # Create vector store
        vector_store = self.client.vector_stores.create(
            name=f"refinery_analysis_{trace.trace_id}_{int(datetime.now().timestamp())}",
            expires_after={
                "anchor": "last_active_at",
                "days": 1  # Clean up after 24 hours
            }
        )
        
        logger.info(f"Created vector store: {vector_store.id}")
        
        # Prepare files for upload
        files_to_upload = []
        
        # 1. Trace file (comprehensive markdown format)
        trace_file = self._create_trace_file(trace, expectation)
        files_to_upload.append(("trace_data.md", trace_file))
        
        # 2. Prompt files
        for filename, content in prompt_contents.items():
            files_to_upload.append((f"prompts/{filename}", content))
        
        # 3. Eval files
        for filename, content in eval_contents.items():
            files_to_upload.append((f"evals/{filename}", content))
        
        # 4. Expectations file
        expectations_content = self._create_expectations_file(expectation)
        files_to_upload.append(("expectations.md", expectations_content))
        
        # Upload files in batch
        file_ids = []
        for filename, content in files_to_upload:
            file_obj = await self._upload_file_content(filename, content)
            file_ids.append(file_obj.id)
            logger.info(f"Uploaded file: {filename} (id: {file_obj.id})")
        
        # Add files to vector store
        self.client.vector_stores.file_batches.create(
            vector_store_id=vector_store.id,
            file_ids=file_ids
        )
        
        logger.info(f"Added {len(file_ids)} files to vector store {vector_store.id}")
        
        # Poll for indexing completion
        await self._poll_vector_store_ready(vector_store.id)
        
        logger.info(f"Vector store ready: {vector_store.id}")
        return vector_store.id
    
    def _create_trace_file(self, trace: Trace, expectation: DomainExpertExpectation) -> str:
        """Create comprehensive trace file in markdown format for optimal retrieval."""
        
        content = f"""# Trace Analysis: {trace.trace_id}

## Metadata
- **Trace ID**: {trace.trace_id}
- **Project**: {trace.project_name}
- **Total Runs**: {len(trace.runs)}
- **Start Time**: {trace.start_time.isoformat()}
- **End Time**: {trace.end_time.isoformat() if trace.end_time else "N/A"}
- **Duration**: {trace.duration_ms}ms

## Expected Behavior
**Description**: {expectation.description}
**Business Context**: {expectation.business_context or "Not specified"}
**Specific Issues**: {expectation.specific_issues or "None specified"}
**Expected Output**: {expectation.expected_output or "Not specified"}

## Execution Trace

"""
        
        # Add runs with detailed metadata for optimal search
        for i, run in enumerate(trace.runs):
            content += f"""### Run {i+1}: {run.name}

**Run Metadata**:
- **ID**: {run.id}
- **Type**: {run.run_type.value}
- **Order**: {run.dotted_order}
- **Duration**: {run.duration_ms}ms
- **Parent**: {run.parent_run_id or "None"}
- **Status**: {"failed" if run.error else "success"}
- **Start**: {run.start_time.isoformat()}
- **End**: {run.end_time.isoformat() if run.end_time else "N/A"}

**Inputs**:
```json
{json.dumps(run.inputs, indent=2) if run.inputs else "None"}
```

**Outputs**:
```json
{json.dumps(run.outputs, indent=2) if run.outputs else "None"}
```

**Error**:
```
{run.error or "None"}
```


---

"""
        
        return content
    
    def _create_expectations_file(self, expectation: DomainExpertExpectation) -> str:
        """Create expectations file for evaluation comparison."""
        
        return f"""# Analysis Expectations

## Primary Expectation
{expectation.description}

## Business Context
{expectation.business_context or "Not specified"}

## Specific Issues to Watch For
{expectation.specific_issues or "None specified"}

## Expected Output Format/Content
{expectation.expected_output or "Not specified"}

## Success Criteria
The agent should demonstrate the expected behavior described above. Any deviation from this expected behavior should be identified and analyzed.
"""

    async def _upload_file_content(self, filename: str, content: str) -> Any:
        """Upload file content to OpenAI Files API."""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            f.flush()
            
            # Upload to Files API
            with open(f.name, 'rb') as file_obj:
                file_response = self.client.files.create(
                    file=file_obj,
                    purpose="assistants"
                )
        
        # Clean up temp file
        Path(f.name).unlink()
        
        return file_response
    
    async def _poll_vector_store_ready(self, vector_store_id: str, max_wait_minutes: int = 10) -> None:
        """Poll vector store until indexing is complete."""
        
        max_iterations = max_wait_minutes * 6  # Check every 10 seconds
        
        for i in range(max_iterations):
            vector_store = self.client.vector_stores.retrieve(vector_store_id)
            
            logger.info(f"Vector store status: {vector_store_id} - {vector_store.status}")
            
            if vector_store.status == "completed":
                return
            elif vector_store.status == "failed":
                raise Exception(f"Vector store indexing failed: {vector_store_id}")
            
            await asyncio.sleep(10)
        
        raise Exception(f"Vector store indexing timeout after {max_wait_minutes} minutes: {vector_store_id}")
    
    def cleanup_vector_store(self, vector_store_id: str) -> None:
        """Clean up vector store and associated files."""
        try:
            # Delete vector store (this also removes file associations)
            self.client.vector_stores.delete(vector_store_id)
            logger.info(f"Cleaned up vector store: {vector_store_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup vector store {vector_store_id}: {e}")