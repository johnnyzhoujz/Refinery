#!/usr/bin/env python3
"""
Minimal POC test script for staged analysis.
Tests the complete flow from vector store creation to final synthesis.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add refinery to path
sys.path.insert(0, str(Path(__file__).parent))

from refinery.agents.staged_failure_analyst import StagedFailureAnalyst
from refinery.core.models import Trace, DomainExpertExpectation
from refinery.integrations.langsmith_client_simple import SimpleLangSmithClient
from refinery.utils.config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_staged_poc():
    """Run end-to-end POC test with real trace."""
    
    # Test trace ID
    trace_id = "60b467c0-b9db-4ee4-934a-ad23a15bd8cd"
    
    logger.info("=" * 80)
    logger.info("STAGED ANALYSIS POC TEST")
    logger.info("=" * 80)
    logger.info(f"Trace ID: {trace_id}")
    
    # 1. Fetch trace from LangSmith
    logger.info("\n1. Fetching trace from LangSmith...")
    langsmith = SimpleLangSmithClient()
    trace = await langsmith.fetch_trace(trace_id)
    logger.info(f"   ✓ Fetched trace with {len(trace.runs)} runs")
    
    # 2. Define expectation
    expectation = DomainExpertExpectation(
        description="Agent should acknowledge that it cannot store memory as requested, but explain that over time it will learn to exclude similar transactions",
        business_context="User requested the agent to remember to exclude certain transactions. Agent needs to be transparent about memory limitations while explaining future learning capabilities",
        specific_issues=["Should acknowledge it cannot store/remember specific requests",
                        "Should explain that each conversation starts fresh without memory",
                        "Should clarify that over time the system will learn patterns to exclude similar transactions",
                        "Should not falsely claim to have memory storage capabilities"]
    )
    logger.info(f"\n2. Expectation: {expectation.description}")
    
    # 3. Initialize staged analyst
    logger.info("\n3. Initializing staged failure analyst...")
    analyst = StagedFailureAnalyst()
    
    # 4. Run Stage 1: Trace Analysis (Batch)
    logger.info("\n4. Running Stage 1: Trace Analysis (Batch API)...")
    logger.info("   This will take 10-15 minutes for batch processing...")
    
    try:
        trace_analysis = await analyst.analyze_trace(
            trace=trace,
            expectation=expectation
        )
        logger.info("   ✓ Stage 1 complete!")
        logger.info(f"   Timeline events: {len(analyst._stage1_result.get('timeline', []))}")
        logger.info(f"   Critical events: {len(analyst._stage1_result.get('events', []))}")
        
        # Show coverage info
        coverage = analyst._stage1_result.get('coverage', {})
        logger.info(f"   Files scanned: {len(coverage.get('files_scanned', []))}")
        if coverage.get('remaining'):
            logger.info(f"   ⚠ Incomplete coverage - remaining: {coverage['remaining'][:3]}...")
            
    except Exception as e:
        logger.error(f"   ✗ Stage 1 failed: {e}")
        return
    
    # 5. Run Stage 2: Gap Analysis (Interactive)
    logger.info("\n5. Running Stage 2: Gap Analysis (Interactive)...")
    
    try:
        gap_analysis = await analyst.compare_to_expected(
            analysis=trace_analysis,
            expectation=expectation
        )
        logger.info("   ✓ Stage 2 complete!")
        
        gaps = analyst._stage2_result.get('gaps', [])
        critical_gaps = [g for g in gaps if g.get('severity') == 'critical']
        logger.info(f"   Total gaps: {len(gaps)}")
        logger.info(f"   Critical gaps: {len(critical_gaps)}")
        
        # Show metrics
        metrics = analyst._stage2_result.get('metrics', {})
        if metrics:
            logger.info(f"   Success rate: {metrics.get('success_rate', 0):.1%}")
            
    except Exception as e:
        logger.error(f"   ✗ Stage 2 failed: {e}")
        return
    
    # 6. Run Stage 3: Diagnosis (Interactive) 
    logger.info("\n6. Running Stage 3: Diagnosis (Interactive)...")
    
    try:
        diagnosis = await analyst.diagnose_failure(
            trace_analysis=trace_analysis,
            gap_analysis=gap_analysis
        )
        logger.info("   ✓ Stage 3 complete!")
        
        causes = analyst._stage3_result.get('causes', [])
        logger.info(f"   Root causes identified: {len(causes)}")
        
        if causes:
            primary = causes[0]
            logger.info(f"   Primary cause: {primary.get('hypothesis', 'Unknown')}")
            logger.info(f"   Likelihood: {primary.get('likelihood', 'Unknown')}")
            logger.info(f"   Category: {primary.get('category', 'Unknown')}")
            
        # Show confidence
        confidence = analyst._stage3_result.get('confidence', {})
        logger.info(f"   Overall confidence: {confidence.get('overall', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"   ✗ Stage 3 failed: {e}")
        return
    
    # 7. Stage 4 results (if generated)
    if analyst._stage4_result:
        logger.info("\n7. Stage 4: Synthesis Results")
        summary = analyst._stage4_result.get('summary', {})
        logger.info(f"   Business impact: {summary.get('business_impact', 'Unknown')}")
        logger.info(f"   Time to resolution: {summary.get('time_to_resolution', 'Unknown')}")
        
        # Show top findings
        findings = analyst._stage4_result.get('top_findings', [])
        if findings:
            logger.info(f"   Top findings: {len(findings)}")
            for i, finding in enumerate(findings[:3], 1):
                logger.info(f"     {i}. {finding.get('finding', '')[:80]}...")
    
    # 8. Summary
    logger.info("\n" + "=" * 80)
    logger.info("POC TEST COMPLETE!")
    logger.info("=" * 80)
    
    # Save results for inspection
    output_file = Path("staged_poc_results.json")
    results = {
        "trace_id": trace_id,
        "expectation": expectation.description,
        "stage1": analyst._stage1_result,
        "stage2": analyst._stage2_result,
        "stage3": analyst._stage3_result,
        "stage4": analyst._stage4_result
    }
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to: {output_file}")
    logger.info("\n✅ All stages completed successfully!")
    

if __name__ == "__main__":
    # Check for API keys
    if not config.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in environment or .env file")
        sys.exit(1)
    
    if not config.langsmith_api_key:
        print("ERROR: LANGSMITH_API_KEY not set in environment or .env file")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_staged_poc())