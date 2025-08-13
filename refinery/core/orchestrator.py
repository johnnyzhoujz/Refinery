"""Main orchestrator that coordinates the failure analysis and fix generation workflow."""

import asyncio
import os
from typing import List, Optional
import structlog

from .models import (
    Trace, DomainExpertExpectation, CodeContext, 
    Diagnosis, Hypothesis, FileChange, CompleteAnalysis
)
from ..integrations.langsmith_client_simple import create_langsmith_client
from ..integrations.llm_provider import create_llm_provider
from ..integrations.code_manager import SafeCodeManager
from ..agents.staged_failure_analyst import StagedFailureAnalyst
from ..agents.hypothesis_generator import AdvancedHypothesisGenerator
from ..analysis.simple_code_reader import build_simple_context
from ..knowledge.gpt41_patterns import gpt41_knowledge
# Removed AgentContextResolver - using simple file passing instead

logger = structlog.get_logger(__name__)


class RefineryOrchestrator:
    """Main orchestrator for the Refinery workflow."""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = codebase_path
        self.langsmith_client = None
        self.llm_provider = create_llm_provider()
        self.code_manager = SafeCodeManager(codebase_path)
        self.failure_analyst = StagedFailureAnalyst()  # Use staged approach to avoid token limits
        self.hypothesis_generator = AdvancedHypothesisGenerator()
# Removed AgentContextResolver - using simple file passing instead
    
    async def _init_async(self):
        """Initialize async components."""
        if self.langsmith_client is None:
            self.langsmith_client = await create_langsmith_client()
    
    async def analyze_failure(
        self, 
        trace_id: str, 
        project: str,
        expected_behavior: str,
        business_context: Optional[str] = None,
        prompt_contents: Optional[dict] = None,
        eval_contents: Optional[dict] = None
    ) -> CompleteAnalysis:
        """Analyze a failed trace and provide diagnosis."""
        logger.info("Starting failure analysis", trace_id=trace_id, project=project)
        
        # Initialize async components
        await self._init_async()
        
        # 1. Fetch trace from LangSmith
        trace = await self.langsmith_client.fetch_trace(trace_id)
        logger.info("Fetched trace", runs_count=len(trace.runs))
        
        # 2. Log provided files
        prompt_file_count = len(prompt_contents or {})
        eval_file_count = len(eval_contents or {})
        logger.info("Using provided files", 
                   prompt_files=prompt_file_count,
                   eval_files=eval_file_count)
        
        # 3. Create domain expert expectation
        expectation = DomainExpertExpectation(
            description=expected_behavior,
            business_context=business_context
        )
        
        # 4. Analyze the trace with provided files
        trace_analysis = await self.failure_analyst.analyze_trace(
            trace, expectation, prompt_contents, eval_contents
        )
        logger.info("Completed trace analysis")
        
        # 5. Compare to expected behavior
        gap_analysis = await self.failure_analyst.compare_to_expected(
            trace_analysis, expectation, prompt_contents, eval_contents
        )
        logger.info("Completed gap analysis")
        
        # 6. Diagnose the failure
        diagnosis = await self.failure_analyst.diagnose_failure(
            trace_analysis, gap_analysis, prompt_contents, eval_contents
        )
        logger.info("Completed diagnosis", failure_type=diagnosis.failure_type.value)
        
        # Return complete analysis with all intermediate results
        return CompleteAnalysis(
            trace_analysis=trace_analysis,
            gap_analysis=gap_analysis,
            diagnosis=diagnosis
        )
    
    async def generate_fixes(
        self,
        diagnosis: Diagnosis,
        max_hypotheses: int = 5
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the diagnosed failure."""
        logger.info("Generating fix hypotheses", failure_type=diagnosis.failure_type.value)
        
        # 1. Analyze codebase context
        code_context = await self.code_manager.analyze_codebase(self.codebase_path)
        logger.info("Analyzed codebase", language=code_context.main_language)
        
        # 2. Search for relevant best practices
        best_practices = await self.hypothesis_generator.search_best_practices(
            diagnosis.failure_type.value,
            self.llm_provider.model,
            {"diagnosis": diagnosis.root_cause}
        )
        
        # 3. Generate hypotheses
        hypotheses = await self.hypothesis_generator.generate_hypotheses(
            diagnosis, 
            code_context, 
            best_practices
        )
        
        # 4. Rank hypotheses
        ranked_hypotheses = await self.hypothesis_generator.rank_hypotheses(
            hypotheses, 
            {"code_context": code_context}
        )
        
        logger.info("Generated hypotheses", count=len(ranked_hypotheses))
        return ranked_hypotheses[:max_hypotheses]
    
    async def apply_hypothesis(
        self,
        hypothesis: Hypothesis,
        dry_run: bool = True
    ) -> dict:
        """Apply a hypothesis (with optional dry run)."""
        logger.info("Applying hypothesis", hypothesis_id=hypothesis.id, dry_run=dry_run)
        
        if dry_run:
            # Validate changes without applying
            results = []
            for change in hypothesis.proposed_changes:
                validation = await self.code_manager.validate_change(change)
                results.append({
                    "file": change.file_path,
                    "valid": validation.is_valid,
                    "issues": validation.issues,
                    "warnings": validation.warnings
                })
            
            return {
                "dry_run": True,
                "hypothesis_id": hypothesis.id,
                "validation_results": results,
                "all_valid": all(r["valid"] for r in results)
            }
        else:
            # Actually apply the changes
            try:
                result = await self.code_manager.apply_changes(
                    hypothesis.proposed_changes,
                    f"Fix: {hypothesis.description}"
                )
                logger.info("Successfully applied hypothesis", commit_id=result.get("commit_id"))
                return result
            except Exception as e:
                logger.error("Failed to apply hypothesis", error=str(e))
                raise
    
    async def rollback_changes(self, commit_id: str) -> bool:
        """Rollback changes to a previous state."""
        logger.info("Rolling back changes", commit_id=commit_id)
        return await self.code_manager.rollback_changes(commit_id)
    
    async def read_existing_implementation(self, file_patterns: List[str]) -> dict:
        """Read existing prompt/eval files to understand current implementation."""
        logger.info("Reading existing implementation", patterns=file_patterns)
        
        implementation = {}
        for pattern in file_patterns:
            # Use glob to find matching files
            import glob
            matching_files = glob.glob(os.path.join(self.codebase_path, pattern), recursive=True)
            
            for file_path in matching_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    rel_path = os.path.relpath(file_path, self.codebase_path)
                    implementation[rel_path] = {
                        "content": content,
                        "size": len(content),
                        "type": self._detect_file_type(file_path)
                    }
                except Exception as e:
                    logger.warning("Could not read file", file=file_path, error=str(e))
        
        logger.info("Read implementation files", count=len(implementation))
        return implementation
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect the type of file (prompt, eval, config, etc.)."""
        file_path_lower = file_path.lower()
        
        if any(keyword in file_path_lower for keyword in ['prompt', 'template']):
            return "prompt"
        elif any(keyword in file_path_lower for keyword in ['eval', 'test', 'validation']):
            return "eval"
        elif any(keyword in file_path_lower for keyword in ['config', 'setting']):
            return "config"
        elif file_path_lower.endswith(('.py', '.js', '.ts')):
            return "code"
        elif file_path_lower.endswith(('.yml', '.yaml')):
            return "yaml"
        elif file_path_lower.endswith('.json'):
            return "json"
        else:
            return "unknown"


async def create_orchestrator(codebase_path: str) -> RefineryOrchestrator:
    """Factory function to create an orchestrator."""
    orchestrator = RefineryOrchestrator(codebase_path)
    # Ensure async dependencies (e.g., LangSmith client) are initialized
    await orchestrator._init_async()
    return orchestrator