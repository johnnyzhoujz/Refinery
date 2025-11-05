"""
Implementation of the HypothesisGenerator interface for generating improvement hypotheses.

This module generates ranked hypotheses for fixing AI agent failures, leveraging
best practices and advanced prompting strategies.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Template

from ..core.interfaces import HypothesisGenerator
from ..core.models import (
    ChangeType,
    CodeContext,
    Confidence,
    Diagnosis,
    FailureType,
    FileChange,
    Hypothesis,
)
from ..integrations import responses_client
from ..integrations.responses_request_builder import build_responses_body_no_tools
from ..utils.config import config

logger = logging.getLogger(__name__)


class AdvancedHypothesisGenerator(HypothesisGenerator):
    """Advanced implementation of HypothesisGenerator using multi-strategy generation."""

    def __init__(self, progress_callback: Optional[Any] = None):
        # Store hypothesis generation settings for metadata (deterministic)
        self.hypothesis_model = config.hypothesis_model
        self.hypothesis_max_tokens = config.hypothesis_max_tokens
        self.hypothesis_reasoning_effort = config.hypothesis_reasoning_effort
        self._progress_callback = progress_callback

        if config.openai_api_key:
            responses_client.init_client(config.openai_api_key)

        # Initialize with embedded best practices
        self._best_practices_db = self._initialize_best_practices()

    def _is_reasoning_model(self) -> bool:
        """Return True when hypothesis generation should use GPT-5 reasoning modes."""
        model = (self.hypothesis_model or "").lower()
        return "gpt-5" in model

    def _should_use_background(self, requested: bool, reasoning_enabled: bool) -> bool:
        """Mirror Stage 4 behavior by forcing background polling when reasoning is active."""
        return requested or reasoning_enabled

    def _escalate_reasoning_effort(self, current: Optional[str]) -> Optional[str]:
        """Return the next reasoning effort level for a retry, or None when maxed."""
        levels = ["minimal", "low", "medium", "high"]
        if not current:
            return "high" if self._is_reasoning_model() else None
        try:
            idx = levels.index(current)
        except ValueError:
            return "high" if current != "high" else None
        if idx >= len(levels) - 1:
            return None
        return "high"

    def _increase_max_tokens(self, current: int) -> int:
        """Bump max tokens with a safety cap to recover from truncation."""
        return 64000  # GPT-5 supports up to 128k output tokens; use 64k for hypothesis generation with complex traces

    def _load_original_file(self, file_path: str) -> str:
        """Read original file contents when available on disk."""
        if not file_path:
            return ""
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except Exception:
            logger.debug(
                "Could not read original content for %s", file_path, exc_info=True
            )
            return ""

    def _emit_progress(
        self, event_type: str, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self._progress_callback:
            return
        try:
            self._progress_callback(event_type, payload or {})
        except Exception:
            logger.debug("Hypothesis progress callback raised", exc_info=True)

    def _format_code_context(
        self, code_context: Optional[CodeContext]
    ) -> Dict[str, Any]:
        if not code_context:
            return {
                "repository_path": "unknown",
                "main_language": "unknown",
                "framework": None,
                "relevant_files": [],
                "dependencies": {},
            }
        return {
            "repository_path": getattr(code_context, "repository_path", "unknown"),
            "main_language": getattr(code_context, "main_language", "unknown"),
            "framework": getattr(code_context, "framework", None),
            "relevant_files": list(getattr(code_context, "relevant_files", [])),
            "dependencies": getattr(code_context, "dependencies", {}),
        }

    def _format_best_practices(
        self, best_practices: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        if not best_practices:
            return []
        return best_practices

    async def _invoke_responses(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        background: bool = False,
        max_tokens: Optional[int] = None,
        reasoning: bool = True,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
        reasoning_effort_override: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Invoke the Responses API and return parsed JSON plus metadata."""

        use_reasoning = reasoning and self._is_reasoning_model()
        selected_effort = reasoning_effort_override or self.hypothesis_reasoning_effort
        effort = selected_effort if use_reasoning else None
        effective_background = self._should_use_background(background, use_reasoning)

        # Log configuration for debugging and regression analysis
        logger.info(
            "Building Responses API request: model=%s, reasoning_effort=%s, max_tokens=%s, background=%s, strict=%s",
            self.hypothesis_model,
            effort,
            max_tokens or self.hypothesis_max_tokens,
            effective_background,
            True,
        )

        body = build_responses_body_no_tools(
            model=self.hypothesis_model,
            system_text=system_prompt,
            user_text=user_prompt,
            json_schema_obj=schema,
            max_output_tokens=max_tokens or self.hypothesis_max_tokens,
            temperature=None,
            reasoning_effort=effort,
            seed=None,
            strict=True,
        )

        # Log request size for debugging
        import json

        body_json = json.dumps(body)
        body_size_kb = len(body_json.encode("utf-8")) / 1024
        logger.info(
            f"Responses API request body size: {body_size_kb:.2f} KB (strict=True)"
        )

        if effective_background:
            timeout = timeout or getattr(config, "background_timeout_s", 900)
            parsed, metadata = await responses_client.create_background(
                body,
                poll_interval=poll_interval,
                timeout=timeout,
            )
        else:
            parsed, metadata = await responses_client.create_with_retry(body)

        metadata.setdefault("schema_version", schema.get("$id"))
        metadata.setdefault(
            "background_mode", "background" if effective_background else "foreground"
        )
        metadata.setdefault(
            "max_tokens_requested", max_tokens or self.hypothesis_max_tokens
        )
        if effort:
            metadata.setdefault("reasoning_effort", effort)
        return parsed, metadata

    async def search_best_practices(
        self, failure_type: str, model: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for relevant best practices using RAG-like approach."""
        logger.info(f"Searching best practices for {failure_type} with model {model}")

        # Build search query based on failure type and context
        search_query = self._build_search_query(failure_type, model, context)

        prompt = self._build_best_practices_search_prompt(
            search_query,
            failure_type,
            model,
            context,
        )

        payload = {
            "failure_type": failure_type,
            "model": model,
            "search_query": search_query,
        }
        self._emit_progress("hypothesis_best_practices_start", payload)
        start_ts = time.perf_counter()

        try:
            parsed, metadata = await self._invoke_responses(
                system_prompt=BEST_PRACTICES_SEARCH_SYSTEM_PROMPT,
                user_prompt=prompt,
                schema=BEST_PRACTICES_SCHEMA,
                background=False,
                reasoning=False,
                max_tokens=1200,
            )
        except Exception as exc:
            self._emit_progress(
                "hypothesis_failed",
                {
                    **payload,
                    "stage": "best_practices",
                    "error": str(exc),
                },
            )
            raise

        elapsed = time.perf_counter() - start_ts
        best_practices = self._parse_best_practices_response(parsed)
        self._emit_progress(
            "hypothesis_best_practices_complete",
            {
                **payload,
                "elapsed_s": round(elapsed, 2),
                "count": len(best_practices),
                "response_id": metadata.get("response_id"),
            },
        )

        # Enhance with embedded knowledge
        enhanced_practices = self._enhance_with_embedded_knowledge(
            best_practices, failure_type, model
        )

        return enhanced_practices

    async def generate_hypotheses(
        self,
        diagnosis: Diagnosis,
        trace: "Trace" = None,
        code_context: CodeContext = None,
        best_practices: List[Dict[str, Any]] = None,
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the issue using multi-strategy approach."""
        logger.info(f"Generating hypotheses for {diagnosis.failure_type}")

        # Extract original prompts from trace if provided
        original_prompts = []
        if trace:
            from ..integrations.langsmith_client_simple import create_langsmith_client

            langsmith_client = await create_langsmith_client()
            extracted = langsmith_client.extract_prompts_from_trace(trace)

            # Add system prompts with inline metadata (no truncation - needed for surgical fixes)
            for i, p in enumerate(extracted.get("system_prompts", [])):
                if isinstance(p, dict):
                    prompt_text = f"[SYSTEM PROMPT from run: {p.get('run_name', 'unknown')}]\n{p.get('content', '')}"
                else:
                    prompt_text = f"[SYSTEM PROMPT {i}]\n{p}"
                original_prompts.append(prompt_text)

            logger.info(
                f"Extracted {len(original_prompts)} prompts from trace with metadata"
            )

        # If we have trace prompts, use trace-based generation first
        if trace and original_prompts:
            hypothesis = await self._generate_trace_based_hypothesis(
                diagnosis, original_prompts, best_practices or []
            )
            if hypothesis:
                return [hypothesis]

        # Fallback to original strategy-based approach
        hypotheses = []

        if diagnosis.failure_type == FailureType.PROMPT_ISSUE:
            hypotheses.extend(
                await self._generate_prompt_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )
        elif diagnosis.failure_type == FailureType.CONTEXT_ISSUE:
            hypotheses.extend(
                await self._generate_context_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )
        elif diagnosis.failure_type == FailureType.MODEL_LIMITATION:
            hypotheses.extend(
                await self._generate_model_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )
        elif diagnosis.failure_type == FailureType.ORCHESTRATION_ISSUE:
            hypotheses.extend(
                await self._generate_orchestration_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )
        elif diagnosis.failure_type == FailureType.RETRIEVAL_ISSUE:
            hypotheses.extend(
                await self._generate_retrieval_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )
        else:
            # Generic hypothesis generation
            hypotheses.extend(
                await self._generate_generic_hypotheses(
                    diagnosis, code_context, best_practices
                )
            )

        # Ensure we have 3-5 hypotheses
        if len(hypotheses) < 3:
            additional = await self._generate_additional_hypotheses(
                diagnosis, code_context, best_practices, 3 - len(hypotheses)
            )
            hypotheses.extend(additional)

        # Limit to top 5
        return hypotheses[:5]

    async def rank_hypotheses(
        self, hypotheses: List[Hypothesis], context: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Rank hypotheses by likelihood of success and risk assessment."""
        logger.info(f"Ranking {len(hypotheses)} hypotheses")

        # Build ranking prompt
        prompt = self._build_ranking_prompt(hypotheses, context)

        payload = {
            "stage": "ranking",
            "hypothesis_count": len(hypotheses),
        }
        self._emit_progress("hypothesis_rank_start", payload)
        start_ts = time.perf_counter()

        try:
            parsed, metadata = await self._invoke_responses(
                system_prompt=HYPOTHESIS_RANKING_SYSTEM_PROMPT,
                user_prompt=prompt,
                schema=HYPOTHESIS_RANKING_SCHEMA,
                background=False,
                reasoning=False,
                max_tokens=800,
            )
        except Exception as exc:
            self._emit_progress(
                "hypothesis_failed",
                {
                    **payload,
                    "error": str(exc),
                },
            )
            raise

        elapsed = time.perf_counter() - start_ts
        rankings = self._parse_ranking_response(parsed)
        self._emit_progress(
            "hypothesis_rank_complete",
            {
                **payload,
                "elapsed_s": round(elapsed, 2),
                "response_id": metadata.get("response_id"),
            },
        )

        # Reorder hypotheses based on rankings
        ranked_hypotheses = []
        for ranking in rankings:
            for hyp in hypotheses:
                if hyp.id == ranking["id"]:
                    # Update confidence based on ranking
                    hyp.confidence = Confidence(ranking["confidence"])
                    ranked_hypotheses.append(hyp)
                    break

        return ranked_hypotheses

    async def _run_generation_stage(
        self,
        *,
        stage_key: str,
        system_prompt: str,
        user_prompt: str,
        default_change_type: ChangeType,
        diagnosis: Diagnosis,
        background: bool,
        trace_prompts: Optional[List[str]] = None,
    ) -> List[Hypothesis]:
        payload = {
            "stage": stage_key,
            "failure_type": diagnosis.failure_type.value,
        }

        self._emit_progress("hypothesis_generation_start", payload)
        start_ts = time.perf_counter()

        # Stage 4 synthesis already forces background polling and reasoning for GPT-5;
        # mirror that contract here so trace rewriting stays on the stable path.
        use_reasoning = self._is_reasoning_model()
        effective_background = self._should_use_background(background, use_reasoning)
        max_tokens = self.hypothesis_max_tokens
        current_effort = self.hypothesis_reasoning_effort
        max_attempts = 2 if use_reasoning else 1
        attempt = 0
        last_error: Optional[Exception] = None
        data: Optional[Dict[str, Any]] = None
        metadata: Dict[str, Any] = {}

        while attempt < max_attempts:
            attempt += 1
            try:
                data, metadata = await self._invoke_responses(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=HYPOTHESIS_GENERATION_SCHEMA,
                    background=effective_background,
                    max_tokens=max_tokens,
                    reasoning=use_reasoning,
                    reasoning_effort_override=current_effort,
                )
                metadata.setdefault("attempts", attempt)
                break
            except Exception as exc:
                last_error = exc
                error_message = str(exc)
                logger.warning(
                    "Hypothesis generation %s attempt %s failed (effort=%s, max_tokens=%s): %s",
                    stage_key,
                    attempt,
                    current_effort,
                    max_tokens,
                    error_message,
                )
                self._emit_progress(
                    "hypothesis_generation_attempt_failed",
                    {
                        **payload,
                        "attempt": attempt,
                        "error": error_message,
                        "reasoning_effort": current_effort,
                        "max_tokens": max_tokens,
                    },
                )

                if attempt >= max_attempts or not use_reasoning:
                    self._emit_progress(
                        "hypothesis_failed",
                        {
                            **payload,
                            "error": error_message,
                        },
                    )
                    raise

                next_effort = self._escalate_reasoning_effort(current_effort)
                if not next_effort:
                    self._emit_progress(
                        "hypothesis_failed",
                        {
                            **payload,
                            "error": error_message,
                        },
                    )
                    raise

                if "max_output_tokens" in error_message:
                    max_tokens = self._increase_max_tokens(max_tokens)

                current_effort = next_effort
                self._emit_progress(
                    "hypothesis_generation_retry",
                    {
                        **payload,
                        "attempt": attempt + 1,
                        "prev_error": error_message,
                        "reasoning_effort": current_effort,
                        "max_tokens": max_tokens,
                    },
                )
        else:
            if last_error:
                raise last_error

        elapsed = time.perf_counter() - start_ts
        self._emit_progress(
            "hypothesis_generation_chunk_progress",
            {
                **payload,
                "progress": 1.0,
                "response_id": metadata.get("response_id"),
            },
        )

        hypotheses = self._parse_hypothesis_response(
            data,
            default_change_type,
            trace_prompts=trace_prompts,
        )
        for hypothesis in hypotheses:
            hypothesis.generation_metadata = self._create_generation_metadata(
                diagnosis,
                metadata,
            )

        self._emit_progress(
            "hypothesis_generation_complete",
            {
                **payload,
                "elapsed_s": round(elapsed, 2),
                "count": len(hypotheses),
                "response_id": metadata.get("response_id"),
            },
        )

        return hypotheses

    async def _generate_prompt_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate hypotheses specifically for prompt issues."""
        prompt = self._build_prompt_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="prompt",
            system_prompt=PROMPT_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.PROMPT_MODIFICATION,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_context_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate hypotheses for context issues."""
        prompt = self._build_context_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="context",
            system_prompt=CONTEXT_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.CONFIG_CHANGE,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_model_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate hypotheses for model limitations."""
        prompt = self._build_model_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="model",
            system_prompt=MODEL_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.CONFIG_CHANGE,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_orchestration_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate hypotheses for orchestration issues."""
        prompt = self._build_orchestration_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="orchestration",
            system_prompt=ORCHESTRATION_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.ORCHESTRATION_SUGGESTION,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_retrieval_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate hypotheses for retrieval issues."""
        prompt = self._build_retrieval_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="retrieval",
            system_prompt=RETRIEVAL_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.CONFIG_CHANGE,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_generic_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> List[Hypothesis]:
        """Generate generic hypotheses for any failure type."""
        prompt = self._build_generic_hypothesis_prompt(
            diagnosis, code_context, best_practices
        )
        return await self._run_generation_stage(
            stage_key="generic",
            system_prompt=GENERIC_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.PROMPT_MODIFICATION,
            diagnosis=diagnosis,
            background=True,
        )

    async def _generate_additional_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
        count: int,
    ) -> List[Hypothesis]:
        """Generate additional hypotheses to meet minimum count."""
        prompt = f"""Generate {count} additional hypotheses for this failure:

Root Cause: {diagnosis.root_cause}
Failure Type: {diagnosis.failure_type}

Focus on creative but practical solutions that weren't covered in the initial hypotheses.

Return as JSON array of hypothesis objects."""
        return await self._run_generation_stage(
            stage_key="additional",
            system_prompt=GENERIC_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.PROMPT_MODIFICATION,
            diagnosis=diagnosis,
            background=True,
        )

    def _initialize_best_practices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize embedded best practices database."""
        return {
            "prompt_engineering": [
                {
                    "practice": "Use clear task instructions",
                    "description": "Start prompts with clear, specific task descriptions",
                    "example": "Task: Analyze the sentiment of the following text and return 'positive', 'negative', or 'neutral'.",
                    "applicable_to": ["all models"],
                },
                {
                    "practice": "Provide examples (few-shot learning)",
                    "description": "Include 2-3 examples of desired input/output pairs",
                    "example": "Example 1: Input: 'I love this!' Output: 'positive'",
                    "applicable_to": ["all models"],
                },
                {
                    "practice": "Use chain-of-thought reasoning",
                    "description": "Ask the model to think step-by-step before answering",
                    "example": "Let's think step by step about this problem...",
                    "applicable_to": ["gpt-4", "claude", "llama"],
                },
                {
                    "practice": "Specify output format",
                    "description": "Clearly define the expected output structure",
                    "example": "Return your answer as JSON with keys: 'answer', 'confidence', 'reasoning'",
                    "applicable_to": ["all models"],
                },
            ],
            "context_management": [
                {
                    "practice": "Limit context window usage",
                    "description": "Keep prompts concise and relevant to avoid context overflow",
                    "technique": "Summarize long documents before including them",
                    "applicable_to": ["all models"],
                },
                {
                    "practice": "Structure context hierarchically",
                    "description": "Put most important information first",
                    "technique": "Use headers and clear sections",
                    "applicable_to": ["all models"],
                },
            ],
            "error_handling": [
                {
                    "practice": "Add validation instructions",
                    "description": "Tell the model to validate its own output",
                    "example": "After generating the response, verify it meets all requirements",
                    "applicable_to": ["all models"],
                },
                {
                    "practice": "Handle edge cases explicitly",
                    "description": "Provide instructions for handling edge cases",
                    "example": "If the input is empty or invalid, return an error message",
                    "applicable_to": ["all models"],
                },
            ],
        }

    def _build_search_query(
        self, failure_type: str, model: str, context: Dict[str, Any]
    ) -> str:
        """Build a search query for best practices."""
        return (
            f"{failure_type} {model} {context.get('specific_issue', '')} best practices"
        )

    def _build_best_practices_search_prompt(
        self, search_query: str, failure_type: str, model: str, context: Dict[str, Any]
    ) -> str:
        """Build prompt for searching best practices."""
        template = Template(BEST_PRACTICES_SEARCH_TEMPLATE)
        return template.render(
            search_query=search_query,
            failure_type=failure_type,
            model=model,
            context=json.dumps(context, indent=2),
            embedded_practices=json.dumps(self._best_practices_db, indent=2),
        )

    def _build_prompt_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for generating prompt-related hypotheses."""
        template = Template(PROMPT_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
            relevant_files=self._format_code_context(code_context)["relevant_files"][
                :5
            ],
        )

    def _build_context_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for context-related hypotheses."""
        template = Template(CONTEXT_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
        )

    def _build_model_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for model limitation hypotheses."""
        template = Template(MODEL_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
        )

    def _build_orchestration_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for orchestration hypotheses."""
        template = Template(ORCHESTRATION_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
        )

    def _build_retrieval_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for retrieval hypotheses."""
        template = Template(RETRIEVAL_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
        )

    def _build_generic_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for generic hypotheses."""
        template = Template(GENERIC_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=self._format_code_context(code_context),
            best_practices=json.dumps(
                self._format_best_practices(best_practices), indent=2
            ),
        )

    def _build_ranking_prompt(
        self, hypotheses: List[Hypothesis], context: Dict[str, Any]
    ) -> str:
        """Build prompt for ranking hypotheses."""
        template = Template(HYPOTHESIS_RANKING_TEMPLATE)

        # Prepare hypothesis data for template
        hyp_data = []
        for hyp in hypotheses:
            hyp_data.append(
                {
                    "id": hyp.id,
                    "description": hyp.description,
                    "rationale": hyp.rationale,
                    "num_changes": len(hyp.proposed_changes),
                    "risks": hyp.risks,
                    "confidence": hyp.confidence.value,
                }
            )

        return template.render(
            hypotheses=hyp_data, context=json.dumps(context, indent=2)
        )

    def _parse_best_practices_response(
        self, response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse best practices search response."""
        if not isinstance(response, dict):
            logger.error(
                "Best practices response must be an object, got %s", type(response)
            )
            return []
        matches = response.get("matches", [])
        if not isinstance(matches, list):
            logger.error("Best practices matches must be a list, got %s", type(matches))
            return []
        return matches

    def _parse_hypothesis_response(
        self,
        response: Dict[str, Any],
        default_change_type: ChangeType,
        trace_prompts: Optional[List[str]] = None,
    ) -> List[Hypothesis]:
        """Parse hypothesis generation response."""
        if not isinstance(response, dict):
            logger.error(
                "Hypothesis response must be an object, got %s", type(response)
            )
            return []

        hyp_data = response.get("hypotheses", [])
        if not isinstance(hyp_data, list):
            logger.error("Hypothesis list missing or invalid: %s", type(hyp_data))
            return []

        hypotheses: List[Hypothesis] = []
        prompt_iter = iter(trace_prompts or [])
        for data in hyp_data:
            if not isinstance(data, dict):
                logger.warning("Skipping malformed hypothesis entry: %r", data)
                continue

            changes = []
            for change in data.get("proposed_changes", []) or []:
                if not isinstance(change, dict):
                    continue
                change_type_value = change.get("change_type", default_change_type.value)
                try:
                    change_type = ChangeType(change_type_value)
                except ValueError:
                    change_type = default_change_type
                original_content = change.get("original_content")
                if not original_content:
                    original_content = next(prompt_iter, "")
                if not original_content:
                    original_content = self._load_original_file(
                        change.get("file_path", "")
                    )

                changes.append(
                    FileChange(
                        file_path=change.get("file_path", ""),
                        original_content=original_content or "",
                        new_content=change.get("new_content", ""),
                        change_type=change_type,
                        description=change.get("description", ""),
                    )
                )

            try:
                confidence = Confidence(data.get("confidence", "medium"))
            except ValueError:
                confidence = Confidence.MEDIUM

            # Normalize hypothesis ID to match schema pattern (hyp-NNN)
            raw_id = data.get("id", "")
            if raw_id:
                # Transform formats like "H1", "hyp1", "hypothesis-1" to "hyp-001"
                import re
                match = re.search(r'\d+', raw_id)
                if match:
                    num = int(match.group())
                    normalized_id = f"hyp-{num:03d}"
                else:
                    # Fallback if no number found: use index + 1
                    normalized_id = f"hyp-{len(hypotheses) + 1:03d}"
            else:
                # Fallback if no ID provided
                normalized_id = f"hyp-{len(hypotheses) + 1:03d}"

            hypothesis = Hypothesis(
                id=normalized_id,
                description=data.get("description", ""),
                rationale=data.get("rationale", ""),
                proposed_changes=changes,
                confidence=confidence,
                risks=data.get("risks", []),
                example_before=data.get("example_before"),
                example_after=data.get("example_after"),
            )
            hypotheses.append(hypothesis)

        return hypotheses

    def _parse_ranking_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse hypothesis ranking response."""
        if not isinstance(response, dict):
            logger.error("Ranking response must be an object, got %s", type(response))
            return []

        rankings = response.get("rankings", [])
        if not isinstance(rankings, list):
            logger.error("Ranking list missing or invalid: %s", type(rankings))
            return []

        valid_rankings = []
        for item in rankings:
            if not isinstance(item, dict):
                continue
            if "id" not in item or "confidence" not in item:
                continue
            valid_rankings.append(item)
        return valid_rankings

    def _enhance_with_embedded_knowledge(
        self, practices: List[Dict[str, Any]], failure_type: str, model: str
    ) -> List[Dict[str, Any]]:
        """Enhance search results with embedded best practices."""
        enhanced = practices.copy()

        # Add relevant embedded practices based on failure type
        if "prompt" in failure_type.lower():
            for practice in self._best_practices_db.get("prompt_engineering", []):
                if model in practice.get(
                    "applicable_to", []
                ) or "all models" in practice.get("applicable_to", []):
                    enhanced.append(practice)

        if "context" in failure_type.lower():
            for practice in self._best_practices_db.get("context_management", []):
                enhanced.append(practice)

        # Always add error handling practices
        enhanced.extend(self._best_practices_db.get("error_handling", []))

        return enhanced[:10]  # Limit to top 10 practices

    async def _generate_trace_based_hypothesis(
        self,
        diagnosis: Diagnosis,
        original_prompts: List[str],
        best_practices: List[Dict[str, Any]],
    ) -> Optional[Hypothesis]:
        """Generate hypothesis by rewriting prompts based on trace analysis and best practices."""
        if not original_prompts:
            return None

        model = config.hypothesis_model
        model_guide = self._get_model_prompting_guide(model)
        prompt = self._build_trace_based_hypothesis_prompt(
            diagnosis,
            original_prompts,
            self._format_best_practices(best_practices),
            model_guide,
        )

        # Log prompt sizes for debugging GPT-5 large context issues
        total_chars = sum(len(p) for p in original_prompts)
        logger.info(
            f"Trace-based hypothesis: {len(original_prompts)} prompts, {total_chars:,} total chars, reasoning_effort={self.hypothesis_reasoning_effort}"
        )

        hypotheses = await self._run_generation_stage(
            stage_key="trace",
            system_prompt=TRACE_BASED_HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            default_change_type=ChangeType.PROMPT_MODIFICATION,
            diagnosis=diagnosis,
            background=False,  # Allow foreground by default; GPT-5 reasoning path escalates to background inside
            trace_prompts=original_prompts,
        )

        return hypotheses[0] if hypotheses else None

    def _get_model_prompting_guide(self, model: str) -> str:
        """Get model-specific prompting guide."""
        # For now, return a basic guide. This can be expanded with actual model guides
        if "gpt" in model.lower():
            return """
GPT Best Practices:
- Be specific and clear in instructions
- Use examples when possible
- Structure prompts with clear sections
- Use system messages for role definition
- Be explicit about output format
"""
        elif "claude" in model.lower():
            return """
Claude Best Practices:
- Use clear, conversational language
- Provide context and reasoning
- Use XML tags for structure
- Be explicit about constraints
- Use examples for complex tasks
"""
        else:
            return """
General Best Practices:
- Clear and specific instructions
- Proper role definition
- Examples and context
- Explicit output requirements
"""

    def _build_trace_based_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        original_prompts: List[str],
        best_practices: List[Dict[str, Any]],
        model_guide: str,
    ) -> str:
        """Build prompt for generating trace-based hypothesis."""
        # Extract join operations to avoid backslashes in f-string expressions (Python 3.11 compatibility)
        prompts_text = chr(10).join([f"{p}\n" for p in original_prompts[:10]])
        practices_text = chr(10).join([f"- {bp.get('title', '')}: {bp.get('description', '')}" for bp in best_practices[:5]])

        return f"""
## DIAGNOSIS
Root Cause: {diagnosis.root_cause}
Failure Type: {diagnosis.failure_type.value}
Evidence: {diagnosis.evidence}
Confidence: {diagnosis.confidence.value}

## SYSTEM PROMPTS ({len(original_prompts)} total)
{prompts_text}

## MODEL-SPECIFIC GUIDE
{model_guide}

## BEST PRACTICES
{practices_text}

Output Requirements:
- Return valid JSON that matches the schema exactly.
- Preserve the full updated prompt text in `new_content` for each proposed change.
- Set `original_content` to an empty string ("") for every change; the system will backfill the existing prompt text after parsing.
"""

    def _create_generation_metadata(
        self,
        diagnosis: Diagnosis,
        source_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create metadata for reproducible hypothesis generation."""

        diagnosis_str = f"{diagnosis.root_cause}:{diagnosis.failure_type}:{diagnosis.confidence.value}"
        diagnosis_hash = hashlib.sha256(diagnosis_str.encode()).hexdigest()

        metadata = {
            "model": self.hypothesis_model,
            "provider": config.hypothesis_llm_provider,
            "max_tokens": self.hypothesis_max_tokens,
            "reasoning_effort": self.hypothesis_reasoning_effort,
            "diagnosis_hash": f"sha256:{diagnosis_hash}",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "schema_version": HYPOTHESIS_GENERATION_SCHEMA.get("$id"),
        }

        if source_metadata:
            clean_source = {k: v for k, v in source_metadata.items() if v is not None}
            metadata.update(clean_source)

            requested_tokens = clean_source.get("max_tokens_requested")
            if requested_tokens is not None:
                metadata["max_tokens"] = requested_tokens

            actual_effort = clean_source.get("reasoning_effort")
            if actual_effort:
                metadata["reasoning_effort"] = actual_effort

            attempts = clean_source.get("attempts")
            if attempts:
                metadata["attempts"] = attempts

        metadata.pop("max_tokens_requested", None)

        return metadata


# JSON Schemas for structured Responses API output
BEST_PRACTICES_SCHEMA: Dict[str, Any] = {
    "$id": "hypothesis_best_practices_v1",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title",
                    "description",
                    "practice",
                    "technique",
                    "example",
                    "applicable_to",
                    "expected_improvement",
                    "relevance_score",
                ],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "practice": {"type": "string"},
                    "technique": {"type": "string"},
                    "example": {"type": "string"},
                    "applicable_to": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "expected_improvement": {"type": "string"},
                    "relevance_score": {"type": ["number", "null"]},
                },
            },
        }
    },
    "required": ["matches"],
}

HYPOTHESIS_GENERATION_SCHEMA: Dict[str, Any] = {
    "$id": "hypothesis_generation_v1",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "description",
                    "rationale",
                    "proposed_changes",
                    "confidence",
                    "risks",
                    "example_before",
                    "example_after",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string", "maxLength": 200},
                    "rationale": {"type": "string", "maxLength": 1000},
                    "confidence": {
                        "type": "string",
                        "enum": [c.value for c in Confidence],
                    },
                    "risks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "example_before": {"type": "string", "maxLength": 500},
                    "example_after": {"type": "string", "maxLength": 500},
                    "proposed_changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "file_path",
                                "new_content",
                                "change_type",
                                "description",
                                "original_content",
                            ],
                            "properties": {
                                "file_path": {"type": "string", "pattern": r"^(prompts|config|orchestration|tests|evals)/.*"},
                                "description": {"type": "string", "maxLength": 200},
                                "original_content": {"type": "string"},
                                "new_content": {"type": "string"},
                                "change_type": {
                                    "type": "string",
                                    "enum": [c.value for c in ChangeType],
                                },
                            },
                        },
                    },
                },
            },
        }
    },
    "required": ["hypotheses"],
}

HYPOTHESIS_RANKING_SCHEMA: Dict[str, Any] = {
    "$id": "hypothesis_ranking_v1",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rankings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "confidence", "notes"],
                "properties": {
                    "id": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": [c.value for c in Confidence],
                    },
                    "notes": {"type": ["string", "null"]},
                },
            },
        }
    },
    "required": ["rankings"],
}

# System prompts and templates

BEST_PRACTICES_SEARCH_SYSTEM_PROMPT = """You are an expert in AI agent best practices, specializing in prompting strategies, model-specific optimizations, and failure remediation.

Your knowledge includes:
- Advanced prompting techniques for various models (GPT-4, Claude, Llama, etc.)
- Model-specific strengths and limitations
- Common failure patterns and their solutions
- Industry best practices for AI agent development

When searching for best practices, focus on actionable, specific techniques that directly address the identified issues."""

BEST_PRACTICES_SEARCH_TEMPLATE = """Task: Search for best practices relevant to this AI agent failure.

Search Query: {{ search_query }}
Failure Type: {{ failure_type }}
Model: {{ model }}
Context: {{ context }}

Available Best Practices Database:
{{ embedded_practices }}

Based on the failure type and context, identify the most relevant best practices that could help fix this issue.

Return a JSON object in this format:
{
  "matches": [
    {
      "title": "Name of the practice",
      "description": "Detailed description",
      "practice": "Short label",
      "technique": "Specific implementation technique",
      "example": "Code or prompt example if applicable",
      "applicable_to": ["model names"],
      "expected_improvement": "What this should fix"
    }
  ]
}

Focus on practices that are:
1. Directly relevant to the failure type
2. Applicable to the specific model being used
3. Proven to work in similar scenarios
4. Implementable without major architectural changes"""

PROMPT_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert prompt engineer specializing in fixing prompt-related failures in AI agents.

Your expertise includes:
- Advanced prompting techniques (chain-of-thought, few-shot learning, etc.)
- Model-specific prompt optimizations
- Clear instruction writing and task decomposition
- Output format specification and validation

Generate specific, implementable hypotheses that improve prompt effectiveness."""

PROMPT_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix prompt-related issues.

Diagnosis:
Root Cause: {{ diagnosis.root_cause }}
Evidence: {% for e in diagnosis.evidence %}
- {{ e }}{% endfor %}
Affected Components: {{ diagnosis.affected_components }}

Code Context:
Repository: {{ code_context.repository_path }}
Language: {{ code_context.main_language }}
Relevant Files: {% for f in relevant_files %}
- {{ f }}{% endfor %}

Best Practices:
{{ best_practices }}

Generate 3-5 specific hypotheses for fixing the prompt issues. Each hypothesis should:
1. Address the root cause directly
2. Apply relevant best practices
3. Include specific code changes
4. Consider potential risks

Return a JSON object with exactly this structure:
{
  "hypotheses": [
    {
      "description": "Clear description of the fix",
      "rationale": "Why this should work",
      "proposed_changes": [
        {
          "file_path": "path/to/file",
          "change_type": "prompt_modification",
          "description": "What to change",
          "original_content": "Current prompt or relevant code",
          "new_content": "Updated prompt or code"
        }
      ],
      "confidence": "low|medium|high",
      "risks": ["potential risks"],
      "example_before": "Example of current behavior",
      "example_after": "Example of expected behavior after fix"
    }
  ]
}"""

CONTEXT_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert in context management for AI agents, specializing in information architecture and context window optimization.

Focus on:
- Efficient context structuring
- Information prioritization
- Context window management
- Relevant data selection"""

CONTEXT_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix context-related issues.

Diagnosis:
Root Cause: {{ diagnosis.root_cause }}
Evidence: {% for e in diagnosis.evidence %}
- {{ e }}{% endfor %}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate hypotheses that improve context handling. Consider:
- Context window limits
- Information ordering
- Data filtering
- Context augmentation strategies

Return a JSON object where the "hypotheses" array follows the same structure described above."""

MODEL_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert in working around model limitations and optimizing model selection for AI agents.

Specialties:
- Model capability assessment
- Workaround strategies for model limitations
- Model selection and configuration
- Task decomposition for complex problems"""

MODEL_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to address model limitations.

Diagnosis:
Root Cause: {{ diagnosis.root_cause }}
Model-specific Issue: {{ diagnosis.detailed_analysis }}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate creative workarounds or alternative approaches. Consider:
- Breaking down complex tasks
- Using model strengths effectively
- Alternative model configurations
- Hybrid approaches

Return a JSON object where the "hypotheses" array follows the same structure described above."""

ORCHESTRATION_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert in AI agent orchestration and architecture, specializing in control flow and system design.

Focus areas:
- Agent workflow optimization
- Error handling and recovery
- State management
- Component interaction patterns"""

ORCHESTRATION_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix orchestration issues.

Diagnosis:
Root Cause: {{ diagnosis.root_cause }}
Affected Flow: {{ diagnosis.affected_components }}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate architectural improvements. Consider:
- Workflow restructuring
- Error propagation handling
- State management improvements
- Component decoupling

Return a JSON object where the "hypotheses" array follows the same structure described above."""

RETRIEVAL_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert in retrieval-augmented generation (RAG) and information retrieval for AI agents.

Expertise:
- Vector database optimization
- Retrieval strategies
- Document chunking and indexing
- Relevance scoring"""

RETRIEVAL_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix retrieval issues.

Diagnosis:
Root Cause: {{ diagnosis.root_cause }}
Retrieval Problems: {{ diagnosis.detailed_analysis }}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate retrieval improvements. Consider:
- Chunking strategies
- Embedding optimization
- Query enhancement
- Relevance filtering

Return a JSON object where the "hypotheses" array follows the same structure described above."""

GENERIC_HYPOTHESIS_SYSTEM_PROMPT = """You are a comprehensive AI agent improvement specialist with broad expertise across all aspects of AI system optimization."""

GENERIC_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix this AI agent failure.

Diagnosis:
Failure Type: {{ diagnosis.failure_type }}
Root Cause: {{ diagnosis.root_cause }}
Full Analysis: {{ diagnosis.detailed_analysis }}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate diverse, practical hypotheses that could fix this issue.

Return a JSON object where the "hypotheses" array follows the same structure described above."""

HYPOTHESIS_RANKING_SYSTEM_PROMPT = """You are an expert at evaluating and ranking AI agent improvement hypotheses based on likelihood of success, implementation complexity, and risk assessment."""

HYPOTHESIS_RANKING_TEMPLATE = """Task: Rank these hypotheses by likelihood of success.

Hypotheses:
{% for hyp in hypotheses %}
{{ loop.index }}. {{ hyp.description }}
   - Rationale: {{ hyp.rationale }}
   - Changes: {{ hyp.num_changes }} files
   - Risks: {{ hyp.risks }}
   - Current Confidence: {{ hyp.confidence }}
{% endfor %}

Additional Context: {{ context }}

Evaluate each hypothesis considering:
1. How well it addresses the root cause
2. Implementation complexity and risk
3. Likelihood of introducing new issues
4. Alignment with best practices

Return rankings as a JSON object with this structure:
{
  "rankings": [
    {
      "id": "hypothesis_id",
      "confidence": "low|medium|high",
      "reasoning": "Why this ranking"
    }
  ]
}

Order from most to least likely to succeed."""

TRACE_BASED_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert prompt engineer specializing in fixing AI agent failures through system prompt optimization.

## CONTEXT
You will receive multiple SYSTEM prompts from an AI agent trace:
- Main orchestrator system prompt (controls overall agent behavior)
- Sub-agent system prompts (control specific tool/function behaviors)

## REASONING REQUIREMENTS
For EACH system prompt you analyze:
1. First state whether it needs modification (YES/NO)
2. If YES, explain WHY this prompt contributes to the failure (2-3 sentences)
3. Identify SPECIFIC sections/instructions causing issues
4. Explain how your changes will fix the problem

## CRITICAL MODIFICATION CONSTRAINTS
- LENGTH GUIDANCE:
  * For prompts > 500 chars: Stay within ±20% of original length (surgical edits only)
  * For prompts 100-500 chars: Stay within ±50% of original length (targeted additions allowed)
  * For prompts < 100 chars: May expand up to 1000 chars if necessary to add critical guardrails
- Make targeted fixes - not complete rewrites
- Preserve original intent, tone, and role definition
- Focus only on fixing the diagnosed failure with minimal changes

## JSON OUTPUT STRUCTURE
You will return structured JSON with hypotheses containing proposed_changes. Each change must include:

**file_path** (CRITICAL - Follow Format Exactly):
- Use descriptive paths that match the actual component/agent being modified
- MUST start with one of these allowed prefixes: "prompts/", "config/", "orchestration/", "tests/", "evals/"
- Examples: "prompts/conversation_handler/system.txt", "config/agents/classifier.yaml", "orchestration/pipeline.yaml"
- For system prompts extracted from trace, use semantic names based on run_name metadata
- Path format should reflect the logical structure of the codebase

**original_content**:
- Extract the EXACT prompt text, stripping the metadata header "[SYSTEM PROMPT from run: ...]"
- Should contain ONLY the actual prompt content, not the metadata

**new_content**:
- Your improved version of the prompt
- MUST respect ±20% length constraint relative to original_content
- Focus surgical changes on diagnosed failure only

**description**:
- One clear sentence describing what you changed

**rationale**:
- 2-3 sentences explaining WHY this change fixes the diagnosed failure
- Connect to specific evidence from the diagnosis

**change_type**:
- Use "prompt_modification" for system prompt changes

**example_before** / **example_after**:
- Concrete examples showing how agent behavior will change
- Keep brief but specific

Remember: You may return 0, 1, or multiple modifications depending on where the failure originates. Multiple hypotheses can propose different fix strategies."""
