#!/usr/bin/env python3
"""
Test orchestrator backward compatibility with staged analysis system.
"""
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refinery.core.orchestrator import create_orchestrator
from refinery.core.models import (
    Trace, TraceRun, DomainExpertExpectation, RunType
)
from refinery.utils.config import config

def create_test_trace():
    """Create a minimal test trace for compatibility testing."""
    
    # Create test runs
    run1 = TraceRun(
        id="test_run_1",
        name="User Query",
        run_type=RunType.CHAIN,
        dotted_order="1",
        start_time=datetime.now(),
        end_time=datetime.now(),
        duration_ms=100,
        inputs={"query": "What is the weather?"},
        outputs={"response": "Let me check the weather for you."},
        error=None,
        parent_run_id=None
    )
    
    run2 = TraceRun(
        id="test_run_2", 
        name="Weather Service",
        run_type=RunType.TOOL,
        dotted_order="2",
        start_time=datetime.now(),
        end_time=datetime.now(),
        duration_ms=500,
        inputs={"location": "San Francisco"},
        outputs={"temperature": "72F", "condition": "sunny"},
        error=None,
        parent_run_id="test_run_1"
    )
    
    # Create trace
    trace = Trace(
        trace_id="test_trace_compat",
        project_name="test_project",
        runs=[run1, run2],
        start_time=datetime.now(),
        end_time=datetime.now(),
        duration_ms=600
    )
    
    return trace

async def test_orchestrator_compatibility():
    """Test that orchestrator works with staged analysis system."""
    
    if not config.openai_api_key:
        print("❌ OPENAI_API_KEY not configured")
        return False
    
    print("🧪 Testing orchestrator backward compatibility...")
    
    try:
        # Create orchestrator - this should use StagedFailureAnalyst
        orchestrator = await create_orchestrator(codebase_path=".")
        print("✅ Orchestrator created successfully")
        
        # Create test data
        trace = create_test_trace()
        expectation = DomainExpertExpectation(
            description="Agent should provide accurate weather information",
            business_context="Weather service integration test",
            specific_issues=None,
            expected_output="Temperature and condition information"
        )
        
        print("📋 Test data created")
        print(f"   Trace ID: {trace.trace_id}")
        print(f"   Runs: {len(trace.runs)}")
        print(f"   Expectation: {expectation.description}")
        
        # Test the 3-stage analysis workflow
        print("\n🔄 Testing orchestrator analyze_failure method...")
        
        # This should call the staged analysis system:
        # 1. analyze_trace() -> Stage 1 + vector store creation
        # 2. compare_to_expected() -> Stage 2  
        # 3. diagnose_failure() -> Stage 3 + 4
        
        # Use real trace ID from BUILD_SUMMARY.md
        real_trace_id = "60b467c0-b9db-4ee4-934a-ad23a15bd8cd"
        
        result = await orchestrator.analyze_failure(
            trace_id=real_trace_id,
            project="test_project",
            expected_behavior="Agent should acknowledge memory limitations and explain learning over time",
            business_context="Testing memory capability communication",
            prompt_contents={"system.txt": "You are a helpful AI assistant."},
            eval_contents={"memory_test.py": "def test_memory(): assert 'memory' in response"}
        )
        
        print("✅ Orchestrator analysis completed!")
        print(f"📊 Result type: {type(result)}")
        
        # Check result structure (should be Diagnosis object)
        if hasattr(result, 'failure_type') and hasattr(result, 'root_cause') and hasattr(result, 'confidence'):
            print("✅ Result has expected Diagnosis structure")
            print(f"   Failure type: {result.failure_type}")
            print(f"   Root cause: {result.root_cause[:100]}...")
            print(f"   Confidence: {result.confidence}")
            print(f"   Evidence count: {len(result.evidence) if result.evidence else 0}")
        else:
            print("❌ Result structure unexpected")
            print(f"   Available attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator compatibility test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_orchestrator_compatibility())
    sys.exit(0 if success else 1)