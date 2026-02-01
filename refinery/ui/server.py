import asyncio
import os
import json
import logging
import structlog
from typing import Optional, Dict, List, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from refinery.core.orchestrator import create_orchestrator, RefineryOrchestrator
from refinery.experiments.customer_experiment_manager import CustomerExperimentManager
from refinery.core.models import (
    Trace, CompleteAnalysis, Hypothesis, Diagnosis, 
    FailureType, Confidence, FileChange, ChangeType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)

app = FastAPI(title="Refinery UI Server")

# CORS for local development (allow frontend dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
class ServerState:
    orchestrator: Optional[RefineryOrchestrator] = None
    experiment_manager: Optional[CustomerExperimentManager] = None
    last_analysis: Optional[CompleteAnalysis] = None
    last_trace: Optional[Trace] = None
    progress_queue: asyncio.Queue = asyncio.Queue()

state = ServerState()

# Models
class TraceRequest(BaseModel):
    trace_id: str
    expected_behavior: str

class HypothesisRequest(BaseModel):
    diagnosis: Dict[str, Any]
    trace_id: str

class SaveExperimentRequest(BaseModel):
    hypothesis: Dict[str, Any]
    tag: str = "ui"
    description: str = "Saved via Web UI"

# Progress Callback
def progress_callback(event_type: str, payload: dict):
    """Push progress events to the queue."""
    try:
        asyncio.create_task(state.progress_queue.put({
            "event": event_type,
            "payload": payload,
            "timestamp": asyncio.get_event_loop().time()
        }))
    except RuntimeError:
        # Loop might not be running if called synchronously
        pass

# Mock Data Helpers
def get_mock_trace(trace_id: str):
    from datetime import datetime
    return Trace(
        trace_id=trace_id,
        project_name="mock-project",
        runs=[],
        start_time=datetime.now(),
        end_time=datetime.now(),
        metadata={"mock": True}
    )

def get_mock_analysis(trace_id: str):
    return CompleteAnalysis(
        trace_analysis={},
        gap_analysis={},
        diagnosis=Diagnosis(
            failure_type=FailureType.PROMPT_ISSUE,
            root_cause="The agent failed to verify the user's subscription tier before processing the request. It assumed the 'premium' flag was true without checking the database.",
            evidence=["Agent called process_refund without check_tier"],
            affected_components=["payment_agent"],
            confidence=Confidence.HIGH,
            detailed_analysis="Analysis shows skipping of validation step."
        )
    )

def get_mock_hypotheses():
    return [
        Hypothesis(
            id="hyp-mock-1",
            description="Add subscription check to system prompt",
            rationale="The model needs explicit instructions to verify subscription status via the 'check_tier' tool before proceeding.",
            confidence=Confidence.HIGH,
            risks=[],
            proposed_changes=[
                FileChange(
                    file_path="prompts/agent_system.md",
                    change_type=ChangeType.PROMPT_MODIFICATION,
                    original_content="You are a customer service agent. Help users with their requests.",
                    new_content="You are a customer service agent. Help users with their requests.\n\nIMPORTANT: You must ALWAYS call the `check_tier(user_id)` tool before processing any premium requests.",
                    description="Added mandatory tool use instruction"
                )
            ]
        )
    ]

@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator and managers."""
    cwd = os.getcwd()
    logger.info("Initializing Refinery Server", cwd=cwd)
    
    if os.environ.get("REFINERY_MOCK_MODE") == "true":
        logger.info("MOCK MODE ENABLED - Orchestrator will be bypassed")
        state.experiment_manager = CustomerExperimentManager(Path(cwd))
        # We don't init orchestrator in mock mode to avoid API key checks
        return
    
    try:
        state.orchestrator = await create_orchestrator(
            codebase_path=cwd,
            progress_callback=progress_callback
        )
    except Exception as e:
        logger.warning(f"Orchestrator init failed (likely missing API keys). UI will work but analysis will fail unless in --mock mode. Error: {e}")
    
    state.experiment_manager = CustomerExperimentManager(Path(cwd))
    logger.info("Server Ready")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "cwd": os.getcwd(), "mock": os.environ.get("REFINERY_MOCK_MODE") == "true"}

@app.get("/api/trace/{trace_id}")
async def get_trace(trace_id: str):
    """Fetch and cache trace."""
    if os.environ.get("REFINERY_MOCK_MODE") == "true":
        trace = get_mock_trace(trace_id)
        state.last_trace = trace
        return trace.dict() if hasattr(trace, "dict") else trace.__dict__

    if not state.orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized. Check server logs.")

    try:
        trace = await state.orchestrator.ensure_trace(trace_id)
        state.last_trace = trace
        # Convert to dict safely
        return trace.dict() if hasattr(trace, "dict") else trace.__dict__
    except Exception as e:
        logger.error("Failed to fetch trace", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_failure(req: TraceRequest):
    """Trigger analysis (streaming progress via separate endpoint or response)."""
    if os.environ.get("REFINERY_MOCK_MODE") == "true":
        # Simulate delay and progress
        await asyncio.sleep(0.5)
        progress_callback("analysis_started", {"trace_id": req.trace_id, "project": "mock-project"})
        await asyncio.sleep(0.8)
        progress_callback("stage1_complete", "Fetching trace data...")
        await asyncio.sleep(0.8)
        progress_callback("stage2_complete", "Identifying failure patterns...")
        await asyncio.sleep(0.8)
        progress_callback("stage3_complete", "Diagnosing root cause...")
        await asyncio.sleep(0.5)
        progress_callback("analysis_completed", {"trace_id": req.trace_id, "failure_type": "prompt_issue"})
        
        result = get_mock_analysis(req.trace_id)
        state.last_analysis = result
        return result.dict() if hasattr(result, "dict") else result.__dict__

    if not state.orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    try:
        # Clear previous progress
        while not state.progress_queue.empty():
            state.progress_queue.get_nowait()
            
        trace = await state.orchestrator.ensure_trace(req.trace_id)
        state.last_trace = trace
        
        project_name = f"ui-{req.trace_id[:8]}"
        
        result = await state.orchestrator.analyze_failure(
            trace_id=req.trace_id,
            project=project_name,
            expected_behavior=req.expected_behavior
        )
        
        state.last_analysis = result
        return result.dict() if hasattr(result, "dict") else result
    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress")
async def stream_progress(request: Request):
    """Stream progress events using SSE."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
                
            try:
                # Wait for next event with timeout to send keep-alive
                event = await asyncio.wait_for(state.progress_queue.get(), timeout=1.0)
                yield {
                    "event": "message",
                    "data": json.dumps(event, default=str)
                }
            except asyncio.TimeoutError:
                # Keep connection alive
                yield {"event": "ping", "data": ""}
            except Exception as e:
                logger.error("Error in event stream", error=str(e))
                break

    return EventSourceResponse(event_generator())

@app.post("/api/hypothesize")
async def generate_hypotheses(req: HypothesisRequest):
    """Generate hypotheses based on diagnosis."""
    if os.environ.get("REFINERY_MOCK_MODE") == "true":
        await asyncio.sleep(1.5) # Simulate thinking
        hypotheses = get_mock_hypotheses()
        return [h.dict() if hasattr(h, "dict") else h.__dict__ for h in hypotheses]

    if not state.orchestrator or not state.last_trace:
        raise HTTPException(status_code=400, detail="No trace context available. Run analysis first.")

    try:
        # Reconstruct diagnosis object if needed, or use cached
        diagnosis = state.last_analysis.diagnosis if state.last_analysis else None
        
        if not diagnosis:
             raise HTTPException(status_code=400, detail="No diagnosis available.")

        hypotheses = await state.orchestrator.generate_hypotheses_from_trace(
            diagnosis=diagnosis,
            trace=state.last_trace,
            max_hypotheses=1
        )
        
        return [h.dict() for h in hypotheses]
    except Exception as e:
        logger.error("Hypothesis generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/experiments")
async def save_experiment(req: SaveExperimentRequest):
    """Save a hypothesis as an experiment version."""
    if not state.experiment_manager:
        raise HTTPException(status_code=503, detail="Experiment manager not ready")

    try:
        # Minimal reconstruction for the manager
        h_data = req.hypothesis
        
        changes = []
        for c in h_data.get("proposed_changes", []):
            changes.append(FileChange(
                file_path=c.get("file_path"),
                original_content=c.get("original_content"),
                new_content=c.get("new_content"),
                change_type=ChangeType(c.get("change_type", "prompt_modification")), # Safe default
                description=c.get("description", "")
            ))
            
        hypothesis = Hypothesis(
            id=h_data.get("id"),
            description=h_data.get("description", ""),
            rationale=h_data.get("rationale", ""),
            proposed_changes=changes,
            confidence=Confidence(h_data.get("confidence", "high")),
            risks=h_data.get("risks", [])
        )

        version_id = state.experiment_manager.save_version(
            hypothesis,
            tag=req.tag
        )
        return {"version_id": version_id, "status": "saved"}
    except Exception as e:
        logger.error("Failed to save experiment", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/experiments")
async def list_experiments():
    """List saved experiments."""
    if not state.experiment_manager:
        raise HTTPException(status_code=503, detail="Experiment manager not ready")
    return state.experiment_manager.list_versions()

# Serve Frontend Static Files
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/")
    def index():
        return {"message": "Refinery API Server running. Frontend not found (run 'npm run build' in refinery/ui/frontend)."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
