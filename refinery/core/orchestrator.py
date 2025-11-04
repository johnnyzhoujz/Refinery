"""Main orchestrator that coordinates the failure analysis and fix generation workflow."""

import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from ..agents.hypothesis_generator import AdvancedHypothesisGenerator
from ..agents.staged_failure_analyst import StagedFailureAnalyst
from ..experiments.customer_experiment_manager import CustomerExperimentManager
from ..integrations.code_manager import SafeCodeManager
from ..integrations.langsmith_client_simple import create_langsmith_client
from ..integrations.llm_provider import create_llm_provider
from ..utils.config import config
from .models import (
    CompleteAnalysis,
    Diagnosis,
    DomainExpertExpectation,
    Hypothesis,
    Trace,
)

# Removed AgentContextResolver - using simple file passing instead

logger = structlog.get_logger(__name__)


class RefineryOrchestrator:
    """Main orchestrator for the Refinery workflow."""

    def __init__(
        self,
        codebase_path: str,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        trace_provider: Optional[Any] = None,
    ):
        self.codebase_path = codebase_path
        self.trace_provider = trace_provider  # Provider-agnostic: supports LangSmith, Langfuse, OTLP
        self.llm_provider = create_llm_provider()
        self.code_manager = SafeCodeManager(codebase_path)
        self.analysis_seed = getattr(config, "analysis_seed", None)
        self.failure_analyst = StagedFailureAnalyst(
            model=getattr(config, "openai_model", "gpt-4o"),
            seed=self.analysis_seed,
            progress_callback=progress_callback,
        )  # Use staged approach to avoid token limits
        self.hypothesis_generator = AdvancedHypothesisGenerator(
            progress_callback=progress_callback
        )
        # Initialize customer experiment manager for hypothesis versions
        self.version_control = CustomerExperimentManager(codebase_path)
        # Caches for single-fetch invariants
        self._trace_cache: Dict[str, Trace] = {}
        self._prompt_eval_cache: Dict[str, Tuple[Dict[str, str], Dict[str, str]]] = {}
        self._trace_fetch_count: int = 0  # Renamed from _langsmith_fetch_count
        self._progress_callback = progress_callback
        self._prompt_extractor = None  # Initialized in _init_async()

    # Removed AgentContextResolver - using simple file passing instead

    async def _init_async(self):
        """Initialize async components."""
        # Initialize trace provider (backward compatible: defaults to LangSmith)
        if self.trace_provider is None:
            self.trace_provider = await create_langsmith_client()

        # Initialize prompt extractor with the trace provider
        from .prompt_extraction import MultiStrategyPromptExtractor
        self._prompt_extractor = MultiStrategyPromptExtractor(self.trace_provider)

    async def analyze_failure(
        self,
        trace_id: str,
        project: str,
        expected_behavior: str,
        business_context: Optional[str] = None,
        prompt_contents: Optional[dict] = None,
        eval_contents: Optional[dict] = None,
    ) -> CompleteAnalysis:
        """Analyze a failed trace and provide diagnosis."""
        logger.info("Starting failure analysis", trace_id=trace_id, project=project)
        if self._progress_callback:
            self._progress_callback(
                "analysis_started",
                {"trace_id": trace_id, "project": project},
            )

        # Initialize async components
        await self._init_async()

        # 1. Fetch trace from provider (single-fetch invariant)
        self._trace_fetch_count = 0
        trace, cache_hit = await self._get_or_fetch_trace(trace_id)
        logger.info("Fetched trace", runs_count=len(trace.runs), cache_hit=cache_hit)
        trace.metadata["trace_fetch_count"] = self._trace_fetch_count
        trace.metadata["trace_cache_hit"] = cache_hit
        trace.metadata["analysis_seed"] = self.analysis_seed

        # 2. Log provided files only when overrides supplied
        prompt_file_count = len(prompt_contents or {})
        eval_file_count = len(eval_contents or {})
        if prompt_file_count or eval_file_count:
            logger.info(
                "Using provided files",
                prompt_files=prompt_file_count,
                eval_files=eval_file_count,
            )

        # 3. Create domain expert expectation
        expectation = DomainExpertExpectation(
            description=expected_behavior, business_context=business_context
        )

        # Resolve prompts/evals (prefer LangSmith bundle, fall back to supplied context)
        resolved_prompts, resolved_evals = await self._resolve_analysis_context(
            trace, prompt_contents, eval_contents
        )

        # 4. Analyze the trace with resolved files
        trace_analysis = await self.failure_analyst.analyze_trace(
            trace, expectation, resolved_prompts, resolved_evals
        )
        logger.info("Completed trace analysis")

        # 5. Compare to expected behavior
        gap_analysis = await self.failure_analyst.compare_to_expected(
            trace_analysis, expectation, resolved_prompts, resolved_evals
        )
        logger.info("Completed gap analysis")

        # 6. Diagnose the failure
        diagnosis = await self.failure_analyst.diagnose_failure(
            trace_analysis, gap_analysis, resolved_prompts, resolved_evals
        )
        logger.info("Completed diagnosis", failure_type=diagnosis.failure_type.value)
        if self._progress_callback:
            self._progress_callback(
                "analysis_completed",
                {
                    "trace_id": trace_id,
                    "project": project,
                    "failure_type": diagnosis.failure_type.value,
                },
            )

        # Return complete analysis with all intermediate results
        return CompleteAnalysis(
            trace_analysis=trace_analysis,
            gap_analysis=gap_analysis,
            diagnosis=diagnosis,
        )

    async def generate_fixes(
        self, diagnosis: Diagnosis, max_hypotheses: int = 5
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the diagnosed failure."""
        logger.info(
            "Generating fix hypotheses", failure_type=diagnosis.failure_type.value
        )

        # 1. Analyze codebase context
        code_context = await self.code_manager.analyze_codebase(self.codebase_path)
        logger.info("Analyzed codebase", language=code_context.main_language)

        # 2. Search for relevant best practices
        best_practices = await self.hypothesis_generator.search_best_practices(
            diagnosis.failure_type.value,
            self.llm_provider.model,
            {"diagnosis": diagnosis.root_cause},
        )

        # 3. Generate hypotheses
        hypotheses = await self.hypothesis_generator.generate_hypotheses(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=best_practices,
        )

        # 4. Rank hypotheses
        context_summary = {}
        try:
            context_summary = {"code_context": code_context.model_dump()}
        except AttributeError:
            # Fallback for non-pydantic implementations
            context_summary = {
                "code_context": getattr(code_context, "__dict__", str(code_context))
            }

        ranked_hypotheses = await self.hypothesis_generator.rank_hypotheses(
            hypotheses,
            context_summary,
        )

        logger.info("Generated hypotheses", count=len(ranked_hypotheses))
        return ranked_hypotheses[:max_hypotheses]

    async def generate_hypotheses_from_trace(
        self, diagnosis: Diagnosis, trace: "Trace", max_hypotheses: int = 1
    ) -> List[Hypothesis]:
        """Generate hypotheses using trace for prompt extraction and rewriting."""
        logger.info(
            "Generating hypotheses from trace",
            failure_type=diagnosis.failure_type.value,
        )

        # Skip best practices search - it's unreliable and causes timeouts
        # Hypothesis generation works fine without it (proven by test_hypothesis_only.py)
        best_practices = []
        logger.info(
            "Skipping best practices search (not required for trace-based generation)"
        )

        # Generate hypotheses with full trace context (this will extract prompts internally)
        hypotheses = await self.hypothesis_generator.generate_hypotheses(
            diagnosis=diagnosis,
            trace=trace,  # Pass full trace for prompt extraction
            code_context=None,  # Not needed for trace-based generation
            best_practices=best_practices,
        )

        logger.info("Generated trace-based hypotheses", count=len(hypotheses))
        return hypotheses[:max_hypotheses]

    def get_cached_trace(self, trace_id: str) -> Optional[Trace]:
        """Return a cached trace if available."""
        return self._trace_cache.get(trace_id)

    def get_run_metadata(self) -> Dict[str, Any]:
        """Expose run metadata such as fetch counts and seed."""
        return {
            "trace_fetch_count": self._trace_fetch_count,
            "analysis_seed": self.analysis_seed,
        }

    async def ensure_trace(self, trace_id: str) -> Trace:
        """Ensure a trace is available, fetching it at most once."""
        trace, _ = await self._get_or_fetch_trace(trace_id)
        return trace

    async def _get_or_fetch_trace(self, trace_id: str) -> Tuple[Trace, bool]:
        """Return cached trace if available; otherwise fetch and cache it."""
        if trace_id in self._trace_cache:
            return self._trace_cache[trace_id], True

        trace = await self.trace_provider.fetch_trace(trace_id)
        self._trace_fetch_count += 1
        self._trace_cache[trace_id] = trace
        return trace, False

    async def _resolve_analysis_context(
        self,
        trace: Trace,
        prompt_contents: Optional[Dict[str, str]],
        eval_contents: Optional[Dict[str, str]],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Resolve prompt/eval bundles, preferring LangSmith extraction."""
        cache_key = trace.trace_id

        provided_prompts = dict(prompt_contents) if prompt_contents else None
        provided_evals = dict(eval_contents) if eval_contents else None

        if (
            cache_key in self._prompt_eval_cache
            and not provided_prompts
            and not provided_evals
        ):
            return self._prompt_eval_cache[cache_key]

        if not provided_prompts or not provided_evals:
            extracted_prompts, extracted_evals = self._extract_prompt_eval_bundle(trace)
        else:
            extracted_prompts, extracted_evals = {}, {}

        resolved_prompts = provided_prompts or extracted_prompts
        resolved_evals = provided_evals or extracted_evals

        self._prompt_eval_cache[cache_key] = (resolved_prompts, resolved_evals)
        logger.info(
            "Resolved analysis context",
            trace_id=trace.trace_id,
            prompt_files=len(resolved_prompts),
            eval_files=len(resolved_evals),
            source="provided" if provided_prompts or provided_evals else "extracted",
        )
        return resolved_prompts, resolved_evals

    def _extract_prompt_eval_bundle(
        self, trace: Trace
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Extract prompt/eval content from trace using multi-strategy extractor."""
        extracted = self._prompt_extractor.extract_prompts_from_trace(trace)

        prompt_files: Dict[str, str] = {}
        eval_files: Dict[str, str] = {}

        for idx, prompt in enumerate(extracted.get("system_prompts", []), start=1):
            content = prompt.get("content")
            if not content:
                continue
            label = prompt.get("run_name") or "system"
            filename = f"system_{idx:02d}_{self._sanitize_label(label)}.md"
            prompt_files[filename] = content

        for idx, prompt in enumerate(extracted.get("user_prompts", []), start=1):
            content = prompt.get("content")
            if not content:
                continue
            label = prompt.get("run_name") or "user"
            filename = f"user_{idx:02d}_{self._sanitize_label(label)}.md"
            prompt_files[filename] = content

        for idx, template in enumerate(extracted.get("prompt_templates", []), start=1):
            content = template.get("content")
            if not content:
                continue
            key = template.get("key") or "template"
            filename = f"template_{idx:02d}_{self._sanitize_label(key)}.md"
            prompt_files[filename] = content

        for idx, example in enumerate(extracted.get("eval_examples", []), start=1):
            filename = f"eval_case_{idx:02d}.json"
            eval_files[filename] = json.dumps(example, indent=2, default=str)

        return prompt_files, eval_files

    def _sanitize_label(self, label: str) -> str:
        sanitized = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label.lower()
        )
        sanitized = sanitized.strip("_")
        return sanitized or "item"

    async def apply_hypothesis(
        self,
        hypothesis: Hypothesis,
        dry_run: bool = True,
        save_version: bool = True,
        tag: Optional[str] = None,
    ) -> dict:
        """Apply a hypothesis (with optional dry run) and save version."""
        logger.info(
            "Applying hypothesis",
            hypothesis_id=hypothesis.id,
            dry_run=dry_run,
            save_version=save_version,
        )

        # Always save version first (for reproducibility and rollback)
        version_id = None
        if save_version:
            try:
                version_id = self.version_control.save_version(hypothesis, tag)
                logger.info("Saved hypothesis version", version_id=version_id)
            except Exception as e:
                logger.error("Failed to save version", error=str(e))
                # Continue with validation/application even if version save fails

        if dry_run:
            # Validate changes without applying
            results = []
            for change in hypothesis.proposed_changes:
                validation = await self.code_manager.validate_change(change)
                results.append(
                    {
                        "file": change.file_path,
                        "valid": validation.is_valid,
                        "issues": validation.issues,
                        "warnings": validation.warnings,
                    }
                )

            return {
                "dry_run": True,
                "hypothesis_id": hypothesis.id,
                "version_id": version_id,
                "validation_results": results,
                "all_valid": all(r["valid"] for r in results),
            }
        else:
            # Actually apply the changes
            try:
                result = await self.code_manager.apply_changes(
                    hypothesis.proposed_changes, f"Fix: {hypothesis.description}"
                )
                result["version_id"] = version_id  # Include version info in result
                logger.info(
                    "Successfully applied hypothesis",
                    commit_id=result.get("commit_id"),
                    version_id=version_id,
                )
                return result
            except Exception as e:
                logger.error("Failed to apply hypothesis", error=str(e))
                raise

    async def rollback_changes(self, commit_id: str) -> bool:
        """Rollback changes to a previous state."""
        logger.info("Rolling back changes", commit_id=commit_id)
        return await self.code_manager.rollback_changes(commit_id)

    # Version control convenience methods
    def list_versions(self) -> List[dict]:
        """List all saved versions."""
        return self.version_control.list_versions()

    def get_version(self, version_id: str) -> Optional[dict]:
        """Get version metadata."""
        return self.version_control.get_version(version_id)

    def stage_version(self, version_id: str) -> str:
        """Stage version for testing."""
        staged_path = self.version_control.stage_version(version_id)
        logger.info(
            "Staged version for testing", version_id=version_id, path=str(staged_path)
        )
        return str(staged_path)

    def deploy_version(self, version_id: str, confirm: bool = False) -> str:
        """Deploy version to production with backup."""
        if not confirm:
            raise ValueError("Deploy requires explicit confirmation (confirm=True)")

        backup_id = self.version_control.deploy_version(version_id, confirm=True)
        logger.info(
            "Deployed version to production", version_id=version_id, backup_id=backup_id
        )
        return backup_id

    def diff_versions(self, version1_id: str, version2_id: str) -> dict:
        """Compare two versions."""
        return self.version_control.diff_versions(version1_id, version2_id)

    async def read_existing_implementation(self, file_patterns: List[str]) -> dict:
        """Read existing prompt/eval files to understand current implementation."""
        logger.info("Reading existing implementation", patterns=file_patterns)

        implementation = {}
        for pattern in file_patterns:
            # Use glob to find matching files
            import glob

            matching_files = glob.glob(
                os.path.join(self.codebase_path, pattern), recursive=True
            )

            for file_path in matching_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    rel_path = os.path.relpath(file_path, self.codebase_path)
                    implementation[rel_path] = {
                        "content": content,
                        "size": len(content),
                        "type": self._detect_file_type(file_path),
                    }
                except Exception as e:
                    logger.warning("Could not read file", file=file_path, error=str(e))

        logger.info("Read implementation files", count=len(implementation))
        return implementation

    def _detect_file_type(self, file_path: str) -> str:
        """Detect the type of file (prompt, eval, config, etc.)."""
        file_path_lower = file_path.lower()

        if any(keyword in file_path_lower for keyword in ["prompt", "template"]):
            return "prompt"
        elif any(
            keyword in file_path_lower for keyword in ["eval", "test", "validation"]
        ):
            return "eval"
        elif any(keyword in file_path_lower for keyword in ["config", "setting"]):
            return "config"
        elif file_path_lower.endswith((".py", ".js", ".ts")):
            return "code"
        elif file_path_lower.endswith((".yml", ".yaml")):
            return "yaml"
        elif file_path_lower.endswith(".json"):
            return "json"
        else:
            return "unknown"


async def create_orchestrator(
    codebase_path: str,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    trace_provider: Optional[Any] = None,
) -> RefineryOrchestrator:
    """Factory function to create an orchestrator."""
    orchestrator = RefineryOrchestrator(
        codebase_path,
        progress_callback=progress_callback,
        trace_provider=trace_provider,
    )
    # Ensure async dependencies (e.g., trace provider, prompt extractor) are initialized
    await orchestrator._init_async()
    return orchestrator
