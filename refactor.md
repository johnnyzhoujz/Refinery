Perfect—here's a tight, implementation‑level refactor plan to move your staged analysis to OpenAI Hosted Vector Store + Responses API (interactive). It assumes you keep your existing system prompts and stage prompts; we're only changing wiring and shapes.

⸻

Refactor Overview

From (current): Batch + (mixed schemas)
To (target): Interactive /v1/responses with the file_search tool bound to a hosted vector store.
Why: tiny request bodies (no 90k org queue issues), managed retrieval, minimal code, BYO key friendly.

⸻

# DETAILED REFACTOR PLAN

## Current State Analysis

### Working Components (Keep As-Is)
✅ **VectorStoreManager** (`refinery/integrations/vector_store_manager.py`)
- Already creates vector stores correctly
- Uploads files with proper indexing
- Polls for readiness
- Only minor updates needed for method names

✅ **Staged Schemas** (`refinery/agents/staged_schemas.py`)  
- All 4 schemas are comprehensive and correct
- Ready for use with Responses API
- No changes needed

✅ **Orchestrator** (`refinery/core/orchestrator.py`)
- Will remain unchanged (backward compatible)
- Calls same 3 methods on FailureAnalyst interface

### Broken Components (Must Fix)
❌ **StagedFailureAnalyst** (`refinery/agents/staged_failure_analyst.py`)
- Line 73-77: Uses Batch API submission
- Line 258-287: Uses wrong API format (client.responses.parse doesn't exist)
- Line 172-175: Wrong tool attachment (should be in tools array)
- All stages need conversion from Batch to Interactive

## API Format Mapping

### Current (BROKEN) - Batch Format
```python
# Line 167-207 in staged_failure_analyst.py
{
    "custom_id": "stage1_xxx",
    "method": "POST",
    "url": "/v1/chat/completions",
    "body": {
        "model": "gpt-4o",
        "tools": [{
            "type": "file_search",
            "vector_store_ids": [store_id],  # ❌ Wrong location
        }],
        "messages": [  # ❌ Should be "input"
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {  # ❌ Should be under "text.format"
            "type": "json_schema",
            ...
        }
    }
}
```

### Target (CORRECT) - Responses Format  
```python
{
    "model": "gpt-4o",
    "tools": [{
        "type": "file_search",
        "vector_store_ids": [store_id],  # ✅ Correct location
        "max_num_results": 8
    }],
    "input": [  # ✅ Not "messages"
        {
            "type": "message",
            "role": "system",
            "content": [
                {"type": "input_text", "text": system_text}  # ✅ "input_text"
            ]
        },
        {
            "type": "message", 
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_text}
            ]
        }
    ],
    "text": {  # ✅ Under "text.format"
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "stage_output",
                "strict": True,
                "schema": {...}
            }
        }
    }
}
```

## Files to Create/Modify

### 1. NEW: `refinery/integrations/responses_request_builder.py` ✅ CREATED
- `build_responses_body()` - Main request builder ✅
- `build_responses_body_no_tools()` - For Stage 4 without file_search ✅
- `build_canary_test_body()` - Connectivity test ✅
- Handles all API format complexity ✅
- Schema validation (ensures root type: "object") ✅

### 2. NEW: `refinery/integrations/responses_client.py` ✅ CREATED
- `create(body: dict) -> dict` - POST to /v1/responses ✅
- `parse_json_output(response: dict) -> dict` - Extract JSON from response ✅
- Handle 429 rate limits with sleep/retry ✅
- Format recovery if JSON parse fails ✅
- Module-level convenience functions ✅
- Async/await with aiohttp ✅

### 3. MODIFY: `refinery/agents/staged_failure_analyst.py` ✅ REFACTORED
Major changes completed:
- ✅ Removed all Batch API code (lines 73-77, 131-229, 402-462)
- ✅ Replaced `_submit_stage1_batch()` with `_run_stage1_interactive()`
- ✅ Fixed Stage 2-4 to use responses_client instead of non-existent client.responses.parse
- ✅ Updated all 4 stages to use `build_responses_body()` + `responses_client.create()`
- ✅ Integrated with versioned prompts from `staged_prompts.py`
- ✅ Maintained backward compatibility with orchestrator

### 3a. ENHANCED: `refinery/prompts/system_prompts.py` ✅ UPDATED
Enhanced system prompts for staged analysis:
- ✅ `FAILURE_ANALYST_SYSTEM_PROMPT_V3` - V2 research + file search protocol (comprehensive)
- ✅ `STAGE1_TRACE_ANALYSIS_PROMPT_V1` - Token-aware timeline analysis
- ✅ `STAGE2_GAP_ANALYSIS_PROMPT_V1` - Business-focused gap analysis  
- ✅ `STAGE3_DIAGNOSIS_PROMPT_V1` - Evidence-based root cause diagnosis
- ✅ `STAGE4_SYNTHESIS_PROMPT_V1` - Executive synthesis for domain experts
- ✅ Full integration with versioning system
- ✅ Eliminated separate staged_prompts.py file (cleaner architecture)

### 4. MINOR UPDATE: `refinery/integrations/vector_store_manager.py`
- Line 46: Already using `client.vector_stores` ✅
- Line 83-86: File batch creation syntax correct ✅
- No changes needed

## Stage-by-Stage Refactor Details

### Stage 1: Trace Analysis
**Current Issues:**
- Uses Batch API (lines 73-77)
- Creates JSONL file (lines 209-226)  
- Polls batch completion (lines 402-462)

**Refactor To:**
```python
async def _run_stage1_interactive(self) -> Dict[str, Any]:
    body = build_responses_body(
        model="gpt-4o",
        vector_store_id=self._vector_store_id,
        system_text=SYSTEM_PROMPT,  # Existing prompt
        user_text=STAGE1_USER_PROMPT,  # Existing prompt
        json_schema_obj=TRACE_ANALYSIS_SCHEMA,
        max_num_results=8,
        max_output_tokens=800
    )
    response = await responses_client.create(body)
    return responses_client.parse_json_output(response)
```

### Stage 2-4: Gap/Diagnosis/Synthesis
**Current Issues:**
- Line 258: `client.responses.parse` doesn't exist
- Wrong message format
- tool_resources instead of tools

**Refactor Pattern (same for all):**
```python
async def _run_stageX_interactive(self) -> Dict[str, Any]:
    # Include previous stage results in user_text
    user_text = f"{STAGE_X_PROMPT}\n\nPrevious Results:\n{json.dumps(previous_result)}"
    
    body = build_responses_body(
        model="gpt-4o",
        vector_store_id=self._vector_store_id,
        system_text=SYSTEM_PROMPT,
        user_text=user_text,
        json_schema_obj=STAGE_X_SCHEMA
    )
    response = await responses_client.create(body)
    return responses_client.parse_json_output(response)
```

## Error Handling Strategy

### 1. Rate Limits (429)
- Sleep 60-120 seconds on first 429
- Retry once
- If still fails, propagate error

### 2. JSON Parse Failures  
- Try parsing response["output_text"] first
- Fallback to concatenating output[0]["content"] items
- If parse fails, retry with "Return ONLY the JSON" prompt

### 3. Vector Store Issues
- Already handled in VectorStoreManager
- Ensure proper polling before analysis

### 4. Network/Auth Errors
- Log and propagate
- Suggest canary test in error message

## Testing Plan

### Phase 1: Component Testing
1. Test `build_responses_body()` output format
2. Verify canary test works
3. Test responses_client with mock response

### Phase 2: Integration Testing  
1. Create vector store with test data
2. Run Stage 1 only - verify JSON output
3. Run all 4 stages with small trace

### Phase 3: Full Testing
1. Use trace `60b467c0-b9db-4ee4-934a-ad23a15bd8cd`
2. Verify backward compatibility with orchestrator
3. Compare output quality to previous batch approach

## Rollback Plan

If issues arise:
1. Keep original `failure_analyst.py` (non-staged) as fallback
2. Can switch orchestrator back to original with single import change
3. Vector stores auto-expire after 24 hours (no cleanup needed)

## Success Criteria

✅ No more 90K token limit errors
✅ Request bodies under 2K tokens
✅ All 4 stages complete in <5 minutes total
✅ Orchestrator works unchanged
✅ Same quality output as batch approach

## Implementation Status

### ✅ Completed
1. **API Client Infrastructure**
   - Created `responses_request_builder.py` with proper API format
   - Created `responses_client.py` with error handling and retries
   - Both modules tested and ready

2. **Staged Analysis Refactor**
   - Converted all 4 stages from Batch to Interactive Responses API
   - Removed all batch-related code
   - Fixed API format issues (input vs messages, input_text vs text)

3. **Enhanced Prompt Integration**
   - Added `FAILURE_ANALYST_SYSTEM_PROMPT_V3` to `system_prompts.py`
   - Combined ALL V2 research improvements with file search protocol
   - Includes token failure patterns, few-shot examples, business context
   - Full integration with versioning system
   - Eliminated architectural complexity (no separate prompt file)

### Token Usage Update (Enhanced V3 Prompts)

With the comprehensive V3 prompts that include all V2 research improvements:

**Per Stage Token Usage:**
- System prompt: ~1,119 tokens (enhanced V3 vs ~228 minimal)
- User prompts: ~190-250 tokens per stage
- Schema: ~374-516 tokens per stage  
- Max output: 800-1000 tokens per stage
- **New Total per stage: ~2,500-3,500 tokens**

**Total Sequential Usage: ~12,500 tokens** (vs 11,600 with minimal prompts)

Still well within 30K TPM limit for single analysis, with much better analysis quality from V2 research improvements (token awareness, pattern recognition, business context).

### 🔄 Next Steps
1. Test with trace `60b467c0-b9db-4ee4-934a-ad23a15bd8cd`
2. Validate orchestrator compatibility  
3. Compare output quality with previous implementation
4. Monitor token usage in practice

## Sample Request Body for Validation

Here's a complete Stage 1 request body that should be sent to `/v1/responses`:

```json
{
    "model": "gpt-4o",
    "tools": [
        {
            "type": "file_search",
            "vector_store_ids": ["vs_abc123example"],
            "max_num_results": 8
        }
    ],
    "input": [
        {
            "type": "message",
            "role": "system",
            "content": [
                {
                    "type": "input_text",
                    "text": "You are an impartial agent-behavior analyst.\n\nUse the file_search tool to retrieve only what you need in bounded passes:\n- max_num_results per pass: 8\n- Stop after 6 passes OR if a pass yields no new sections\n- Track coverage: coverage.files_scanned[], coverage.remaining[]\n\nRules:\n- Cite evidence with {file, section_or_lines} when possible (rough is OK for POC).\n- Output VALID JSON only that matches the provided schema. No prose outside JSON.\n- If coverage is incomplete when you stop, state it explicitly in the JSON."
                }
            ]
        },
        {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Task: Produce an evidence-backed timeline of the agent execution.\n\nRetrieval protocol:\n1) Query for sections containing \"run\", \"tool\", \"input\", \"output\", \"error\", \"exception\".\n2) Iterate passes (max 6). In each pass, fetch at most 8 chunks. Avoid repeating already-seen sections.\n3) Build:\n   - timeline[]: ordered runs with key inputs/outputs and tool calls\n   - events[]: failures/retries/anomalies\n   - coverage: { files_scanned[], remaining[] }\n   - evidence[]: { file, section_or_lines, rationale }\n\nReturn JSON only per schema. If you hit the stop condition with remaining sections, include them in coverage.remaining."
                }
            ]
        }
    ],
    "text": {
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "stage_output",
                "strict": true,
                "schema": {
                    "type": "object",
                    "properties": {
                        "timeline": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sequence": {"type": "integer"},
                                    "run_id": {"type": "string"},
                                    "run_name": {"type": "string"},
                                    "action": {"type": "string"},
                                    "status": {"type": "string", "enum": ["success", "error", "partial"]},
                                    "citations": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["sequence", "run_id", "run_name", "action", "status", "citations"],
                                "additionalProperties": false
                            }
                        },
                        "events": {"type": "array"},
                        "coverage": {"type": "object"},
                        "evidence": {"type": "array"}
                    },
                    "required": ["timeline", "events", "coverage", "evidence"],
                    "additionalProperties": false
                }
            }
        }
    },
    "temperature": 0.2,
    "max_output_tokens": 800
}
```

## Prompts to Preserve

### System Prompt (All Stages)
```python
SYSTEM_PROMPT = """You are an impartial agent-behavior analyst.

Use the file_search tool to retrieve only what you need in bounded passes:
- max_num_results per pass: 8
- Stop after 6 passes OR if a pass yields no new sections
- Track coverage: coverage.files_scanned[], coverage.remaining[]

Rules:
- Cite evidence with {file, section_or_lines} when possible (rough is OK for POC).
- Output VALID JSON only that matches the provided schema. No prose outside JSON.
- If coverage is incomplete when you stop, state it explicitly in the JSON."""
```

### Stage 1: Trace Analysis
```python
STAGE1_USER_PROMPT = """Task: Produce an evidence-backed timeline of the agent execution.

Retrieval protocol:
1) Query for sections containing "run", "tool", "input", "output", "error", "exception".
2) Iterate passes (max 6). In each pass, fetch at most 8 chunks. Avoid repeating already-seen sections.
3) Build:
   - timeline[]: ordered runs with key inputs/outputs and tool calls
   - events[]: failures/retries/anomalies
   - coverage: { files_scanned[], remaining[] }
   - evidence[]: { file, section_or_lines, rationale }

Return JSON only per schema. If you hit the stop condition with remaining sections, include them in coverage.remaining."""
```

### Stage 2: Gap Analysis
```python
STAGE2_USER_PROMPT = """Task: Compare actual behavior vs expectations/evals using the Stage 1 JSON and eval files.

Retrieval protocol:
- Retrieve only spans cited in Stage 1 or matching expectation clauses.
- For each clause: status = {met, partial, missing} with at least one citation when not "met".
- Update coverage if you fetched new sections.

Return JSON only per schema.

Stage 1 Results:
{stage1_json}"""
```

### Stage 3: Diagnosis
```python
STAGE3_USER_PROMPT = """Task: Determine root causes with confidence.

Protocol:
- Re-retrieve only the specific spans cited in Stage 1/2 for verification.
- Build causal chains: {symptom -> mechanism -> cause} each with citations.
- Provide remediations and an overall confidence.

Return JSON only per schema.

Stage 1 Results:
{stage1_json}

Stage 2 Results:
{stage2_json}"""
```

### Stage 4: Synthesis
```python
STAGE4_USER_PROMPT = """Synthesize an executive summary and prioritized recommendations from prior JSON artifacts. No new retrieval unless needed. Return summary, top_findings[], actions_next[].

Stage 1 Results:
{stage1_json}

Stage 2 Results:
{stage2_json}

Stage 3 Results:
{stage3_json}"""
```

⸻

Module Changes (what to edit or add)

1) vector_store_manager.py

Responsibilities
	•	create_store(name: str) -> str → returns vector_store_id
	•	upload_files(store_id: str, paths: List[str]) -> List[str] → returns file_ids
	•	poll_ready(store_id: str, timeout_s=600, poll_s=3) -> None (wait until all files processed)
	•	delete_store(store_id: str) -> None (optional for cleanup)

Notes
	•	Upload text/markdown/PDF versions of trace, prompts, evals.
	•	Keep filenames stable; they’ll appear in citations.
	•	Ensure the same API key / project is used later by the caller.

⸻

2) responses_request_builder.py

New: a single builder that emits a valid Responses API body.

def build_responses_body(
    model: str,
    vector_store_id: str,
    system_text: str,     # your existing system prompt, unchanged
    user_text: str,       # your stage-specific user prompt, unchanged
    json_schema_obj: dict,  # your stage schema (root type "object")
    max_num_results: int = 8,
    max_output_tokens: int = 1000,
    temperature: float = 0.2,
) -> dict:
    return {
        "model": model,
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                "max_num_results": max_num_results
            }
        ],
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [
                    { "type": "input_text", "text": system_text }
                ]
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    { "type": "input_text", "text": user_text }
                ]
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "stage_output",
                    "strict": True,
                    "schema": json_schema_obj   # MUST be {"type":"object", ...}
                }
            }
        },
        "temperature": temperature,
        "max_output_tokens": max_output_tokens
    }

Important differences from Chat Completions
	•	Use input (not messages).
	•	Each content part uses type: "input_text" (not "text").
	•	Attach the vector store inside the tool (vector_store_ids), not tool_resources.
	•	Structured output goes under text.format.json_schema with name and schema (and optionally strict: true).

⸻

3) responses_client.py

Responsibilities
	•	create(body: dict) -> dict → POST https://api.openai.com/v1/responses
	•	Parse final JSON from the response.

Parsing guidance
	•	When text.format is used, the model returns the JSON as text in the output content. Safest extractor:
	•	Prefer response["output_text"] if present (some SDKs expose this).
	•	Else, concatenate any content items of type output_text from response["output"][0]["content"] and json.loads(...).
	•	If parse fails:
	•	Do one format‑only re‑ask: reuse the same body but replace the user content with “Return ONLY the exact JSON again” and include the raw model string. (POC‑level fix.)

429 handling (POC)
	•	On 429: sleep(60–120s) and retry once.
	•	No other fancy backoff needed.

⸻

4) staged_failure_analyst.py (controller)

Keep your class; just swap call sites to Responses.

class StagedFailureAnalyst(FailureAnalyst):
    def __init__(self, model="gpt-4o"):
        self.model = model

    async def analyze_trace(self, store_id, system_prompt, user_prompt, schema) -> TraceAnalysis:
        body = build_responses_body(
            model=self.model,
            vector_store_id=store_id,
            system_text=system_prompt,   # unchanged
            user_text=user_prompt,       # unchanged (your Stage 1 message)
            json_schema_obj=schema
        )
        resp = await responses.create(body)
        return parse_trace_analysis(resp)  # your parser → dataclass

    async def compare_to_expected(self, store_id, system_prompt, user_prompt, schema) -> GapAnalysis:
        body = build_responses_body(self.model, store_id, system_prompt, user_prompt, schema)
        resp = await responses.create(body)
        return parse_gap_analysis(resp)

    async def diagnose_failure(self, store_id, system_prompt, user_prompt, schema) -> Diagnosis:
        body = build_responses_body(self.model, store_id, system_prompt, user_prompt, schema)
        resp = await responses.create(body)
        return parse_diagnosis(resp)

Passing prior stage outputs
	•	Keep them short and include in the user message text (e.g., “Here is the JSON from Stage 1:” + serialized compact JSON).
	•	You can also upload these small JSONs into the same vector store and refer to them by name in your existing prompts—both approaches work. (POC: user text is simplest.)

⸻

End‑to‑End Flow
	1.	Create store & upload
	•	store_id = create_store(run_name)
	•	upload_files(store_id, [trace.md, prompts.md, evals.md, ...])
	•	poll_ready(store_id)
	2.	Stage 1 → TraceAnalysis
	•	body = build_responses_body(..., vector_store_id=store_id, system_text=<existing>, user_text=<existing stage 1>, schema=TRACE_ANALYSIS_SCHEMA)
	•	resp = responses.create(body) → parse JSON → trace_analysis.json
	3.	Stage 2 → GapAnalysis
	•	user_text = <existing stage 2 prompt> + "\n\nTraceAnalysis JSON:\n" + compact(trace_analysis_json) + "\n\nExpectations:\n" + expectations_text
	•	Call Responses as above → gap_analysis.json
	4.	Stage 3 → Diagnosis
	•	user_text = <existing stage 3 prompt> + "\n\nTraceAnalysis JSON:\n" + compact(...) + "\n\nGapAnalysis JSON:\n" + compact(...)
	•	Call Responses → diagnosis.json

(Optional) Stage 4 → Synthesis (small JSON summary) using same pattern.

⸻

Minimal Schemas (keep them small for POC)
	•	Ensure root is { "type": "object" }; add required arrays/objects as needed.
	•	You can start with { "type": "object" } and expand later.

⸻

Sanity & Troubleshooting (copy into your README)

Preflight
	•	Files must be processed before calling /responses; otherwise retrieval returns nothing.
	•	Keep request bodies tiny (1–2k tokens); max_output_tokens ≤ 1000.

Common errors
	•	Invalid value: 'text' ... input[0].content[0].type → use type: "input_text".
	•	Unsupported parameter: response_format → use text.format.json_schema.
	•	Unknown parameter: tool_resources → move vector_store_ids into the file_search tool.
	•	“No results” → you probably didn’t wait for indexing; repoll until ready.

Canary test (once per session)

{
  "model":"gpt-4o",
  "input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"Reply PONG"}]}],
  "text":{"format":{"type":"json_schema","json_schema":{"name":"check","schema":{"type":"object"}}}}
}

If this fails, fix auth/base URL before debugging tools.

⸻

Distribution (local package, BYO key)
	•	Expect OPENAI_API_KEY (and optional OPENAI_PROJECT) from env.
	•	Provide two CLI commands:
	•	init: creates store, uploads files, waits ready; prints/store_id
	•	analyze: runs the three stages against a given store_id; writes JSON artifacts
	•	No local DB; zero extra dependencies for users.

⸻

Cutover Checklist
	•	Replace Batch calls with responses.create (interactive).
	•	Switch message shapes to input[].content[].type = "input_text".
	•	Attach vector store IDs on the tool (file_search).
	•	Move schema to text.format.json_schema with name + schema.
	•	Confirm responses parsing (prefer output_text or content items of type output_text).
	•	One end‑to‑end run on a real trace → ✅

That’s everything your coding tool needs to refactor the current code to hosted Vector Store + interactive Responses, without touching your prompts. If you paste one redacted body you plan to send, I’ll do a final field‑by‑field validation before you wire it up.