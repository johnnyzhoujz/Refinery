"""
Vector Store management for staged analysis with File Search.

This module handles creating vector stores, uploading files, and polling for readiness.
"""

import json
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
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
    
    async def create_single_store_with_all_files(
        self,
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: Dict[str, str],
        eval_contents: Dict[str, str],
        group_size: int = 6
    ) -> str:
        """
        Create single vector store with grouped trace files + prompt/eval files for chunked analysis.
        
        Args:
            trace: The trace to analyze
            expectation: Domain expert expectation
            prompt_contents: Dict of prompt filename -> content
            eval_contents: Dict of eval filename -> content
            group_size: Number of runs per group (default 6)
        
        Returns:
            vector_store_id: The ID of the created and indexed vector store
        """
        logger.info(f"Creating single vector store for chunked analysis: trace_id={trace.trace_id}")
        
        # Create vector store (TTL may fail on some org policies - fall back to no TTL if needed)
        try:
            vector_store = self.client.vector_stores.create(
                name=f"refinery_chunked_{trace.trace_id}_{int(datetime.now().timestamp())}",
                expires_after={"anchor": "last_active_at", "days": 1}
            )
        except Exception as e:
            logger.warning(f"Failed to create vector store with TTL, retrying without: {e}")
            vector_store = self.client.vector_stores.create(
                name=f"refinery_chunked_{trace.trace_id}_{int(datetime.now().timestamp())}"
            )
        
        logger.info(f"Created chunked vector store: {vector_store.id}")
        
        # Prepare all files
        files_to_upload = []
        
        # 1. Grouped trace files (no expectations embedded)
        grouped_files = self._create_grouped_trace_files(trace, group_size)
        files_to_upload.extend(grouped_files)
        logger.info(f"Created {len(grouped_files)} grouped trace files")
        
        # 2. Single expectations file (do not duplicate per group)
        expectations_content = self._create_expectations_file(expectation)
        files_to_upload.append(("expectations.md", expectations_content))
        
        # 3. Prompt and eval files
        for filename, content in prompt_contents.items():
            files_to_upload.append((f"prompts/{filename}", content))
        for filename, content in eval_contents.items():
            files_to_upload.append((f"evals/{filename}", content))
        
        logger.info(f"Total files to upload: {len(files_to_upload)}")
        
        # Upload and index all files
        file_ids = []
        for filename, content in files_to_upload:
            file_obj = await self._upload_file_content(filename, content)
            file_ids.append(file_obj.id)
            logger.debug(f"Uploaded chunked file: {filename} (id: {file_obj.id})")
        
        # Add all files to vector store in batch
        self.client.vector_stores.file_batches.create(
            vector_store_id=vector_store.id, file_ids=file_ids
        )
        
        logger.info(f"Added {len(file_ids)} files to chunked vector store {vector_store.id}")
        
        # Poll for indexing completion
        await self._poll_vector_store_ready(vector_store.id)
        
        logger.info(f"Chunked vector store ready: {vector_store.id}")
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
    
    def _create_grouped_trace_files(self, trace: Trace, group_size: int = 6) -> List[Tuple[str, str]]:
        """
        Create trace files grouped for chunked analysis.
        
        Args:
            trace: The trace to analyze
            group_size: Number of runs per group (default 6)
        
        Returns:
            List of (filename, content) tuples for grouped trace files
        """
        files = []
        total_runs = len(trace.runs)
        num_groups = (total_runs + group_size - 1) // group_size
        
        logger.info(f"Creating {num_groups} groups for {total_runs} runs (group_size={group_size})")
        
        for group_idx in range(num_groups):
            start_idx = group_idx * group_size
            end_idx = min(start_idx + group_size, total_runs)
            group_runs = trace.runs[start_idx:end_idx]
            group_id = f"g{group_idx + 1:02d}"
            
            # Create content with explicit group marker (no expectations)
            content = f"""GROUP: {group_id}

# Trace Analysis Group {group_idx + 1} of {num_groups}
# Runs {start_idx + 1} to {end_idx} of {total_runs}

## Metadata
- **Trace ID**: {trace.trace_id}
- **Group**: {group_id}
- **Runs in Group**: {len(group_runs)}
- **Total Trace Runs**: {total_runs}
- **Project**: {trace.project_name}

## Execution Trace (Group {group_id})

"""
            # Add run details with timestamps for sorting
            for i, run in enumerate(group_runs, start=start_idx + 1):
                start_iso = getattr(run.start_time, "isoformat", lambda: None)() or "N/A"
                content += f"""### Run {i}: {run.name}
GROUP: {group_id}
**Run Metadata**:
- **ID**: {run.id}
- **Type**: {run.run_type.value}
- **Order**: {run.dotted_order}
- **Status**: {"failed" if run.error else "success"}
- **Duration**: {run.duration_ms}ms if run.duration_ms else "N/A"
- **Start Time**: {start_iso}
- **Parent**: {run.parent_run_id or "None"}
- **Group Index**: {group_idx}
- **Run Order**: {i}

**Inputs**:
```json
{json.dumps(run.inputs, indent=2) if run.inputs else "None"}
```

**Outputs**:
```json
{json.dumps(run.outputs, indent=2) if run.outputs else "None"}
```

**Error**: {run.error or "None"}

---

"""
            
            # Use simple filename with group prefix for scoping
            filename = f"{group_id}_trace_runs_{start_idx+1:03d}-{end_idx:03d}.md"
            files.append((filename, content))
            
            logger.debug(f"Created group file: {filename} with {len(group_runs)} runs")
        
        return files

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