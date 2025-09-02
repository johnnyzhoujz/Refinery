"""
Implementation of the HypothesisGenerator interface for generating improvement hypotheses.

This module generates ranked hypotheses for fixing AI agent failures, leveraging
best practices and advanced prompting strategies.
"""

import json
import logging
import uuid
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime
from jinja2 import Template

from ..core.interfaces import HypothesisGenerator
from ..core.models import (
    Diagnosis, Hypothesis, FileChange, CodeContext,
    ChangeType, Confidence, FailureType
)
from ..utils.llm_provider import get_llm_provider
from ..knowledge.openai_guides import search_best_practices, get_model_specific_tips
from ..knowledge.gpt41_patterns import gpt41_knowledge
from ..utils.config import config

logger = logging.getLogger(__name__)


class AdvancedHypothesisGenerator(HypothesisGenerator):
    """Advanced implementation of HypothesisGenerator using multi-strategy generation."""
    
    def __init__(self):
        # Use hypothesis-specific LLM configuration
        self.llm = get_llm_provider(config)
        
        # Store hypothesis generation settings for metadata (deterministic)
        self.hypothesis_model = config.hypothesis_model
        self.hypothesis_temperature = 0.0  # Force temperature=0 for reproducible generations
        self.hypothesis_max_tokens = config.hypothesis_max_tokens
        
        # Initialize with embedded best practices
        self._best_practices_db = self._initialize_best_practices()
    
    async def search_best_practices(
        self,
        failure_type: str,
        model: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for relevant best practices using RAG-like approach."""
        logger.info(f"Searching best practices for {failure_type} with model {model}")
        
        # Build search query based on failure type and context
        search_query = self._build_search_query(failure_type, model, context)
        
        # Use LLM to search through best practices
        prompt = self._build_best_practices_search_prompt(
            search_query, 
            failure_type, 
            model,
            context
        )
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=BEST_PRACTICES_SEARCH_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for reproducible generations
            max_tokens=2000
        )
        
        # Parse and structure the best practices
        best_practices = self._parse_best_practices_response(response)
        
        # Enhance with embedded knowledge
        enhanced_practices = self._enhance_with_embedded_knowledge(
            best_practices, 
            failure_type, 
            model
        )
        
        return enhanced_practices
    
    async def generate_hypotheses(
        self,
        diagnosis: Diagnosis,
        trace: "Trace" = None,
        code_context: CodeContext = None,
        best_practices: List[Dict[str, Any]] = None
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the issue using multi-strategy approach."""
        logger.info(f"Generating hypotheses for {diagnosis.failure_type}")
        
        # Extract original prompts from trace if provided
        original_prompts = []
        if trace:
            from ..integrations.langsmith_client_simple import create_langsmith_client
            langsmith_client = await create_langsmith_client()
            extracted = langsmith_client.extract_prompts_from_trace(trace)
            original_prompts = extracted.get("system_prompts", []) + extracted.get("user_prompts", [])
            logger.info(f"Extracted {len(original_prompts)} prompts from trace")
        
        # If we have trace prompts, use trace-based generation
        if trace and original_prompts:
            hypothesis = await self._generate_trace_based_hypothesis(
                diagnosis, original_prompts, best_practices or []
            )
            return [hypothesis] if hypothesis else []
        
        # Fallback to original strategy-based approach
        hypotheses = []
        
        if diagnosis.failure_type == FailureType.PROMPT_ISSUE:
            hypotheses.extend(
                await self._generate_prompt_hypotheses(diagnosis, code_context, best_practices)
            )
        elif diagnosis.failure_type == FailureType.CONTEXT_ISSUE:
            hypotheses.extend(
                await self._generate_context_hypotheses(diagnosis, code_context, best_practices)
            )
        elif diagnosis.failure_type == FailureType.MODEL_LIMITATION:
            hypotheses.extend(
                await self._generate_model_hypotheses(diagnosis, code_context, best_practices)
            )
        elif diagnosis.failure_type == FailureType.ORCHESTRATION_ISSUE:
            hypotheses.extend(
                await self._generate_orchestration_hypotheses(diagnosis, code_context, best_practices)
            )
        elif diagnosis.failure_type == FailureType.RETRIEVAL_ISSUE:
            hypotheses.extend(
                await self._generate_retrieval_hypotheses(diagnosis, code_context, best_practices)
            )
        else:
            # Generic hypothesis generation
            hypotheses.extend(
                await self._generate_generic_hypotheses(diagnosis, code_context, best_practices)
            )
        
        # Ensure we have 3-5 hypotheses
        if len(hypotheses) < 3:
            additional = await self._generate_additional_hypotheses(
                diagnosis, code_context, best_practices, 3 - len(hypotheses)
            )
            hypotheses.extend(additional)
        
        # Add generation metadata to each hypothesis for reproducibility
        for hypothesis in hypotheses:
            hypothesis.generation_metadata = self._create_generation_metadata(diagnosis)
        
        # Limit to top 5
        return hypotheses[:5]
    
    async def rank_hypotheses(
        self,
        hypotheses: List[Hypothesis],
        context: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Rank hypotheses by likelihood of success and risk assessment."""
        logger.info(f"Ranking {len(hypotheses)} hypotheses")
        
        # Build ranking prompt
        prompt = self._build_ranking_prompt(hypotheses, context)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=HYPOTHESIS_RANKING_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=1500
        )
        
        # Parse ranking response
        rankings = self._parse_ranking_response(response)
        
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
    
    async def _generate_prompt_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses specifically for prompt issues."""
        prompt = self._build_prompt_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=PROMPT_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.PROMPT_MODIFICATION)
    
    async def _generate_context_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses for context issues."""
        prompt = self._build_context_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=CONTEXT_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.CONFIG_CHANGE)
    
    async def _generate_model_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses for model limitations."""
        prompt = self._build_model_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=MODEL_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.CONFIG_CHANGE)
    
    async def _generate_orchestration_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses for orchestration issues."""
        prompt = self._build_orchestration_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=ORCHESTRATION_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.ORCHESTRATION_SUGGESTION)
    
    async def _generate_retrieval_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses for retrieval issues."""
        prompt = self._build_retrieval_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=RETRIEVAL_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.CONFIG_CHANGE)
    
    async def _generate_generic_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate generic hypotheses for any failure type."""
        prompt = self._build_generic_hypothesis_prompt(diagnosis, code_context, best_practices)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=GENERIC_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for demo safety
            max_tokens=self.hypothesis_max_tokens
        )
        
        return self._parse_hypothesis_response(response, ChangeType.PROMPT_MODIFICATION)
    
    async def _generate_additional_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]],
        count: int
    ) -> List[Hypothesis]:
        """Generate additional hypotheses to meet minimum count."""
        prompt = f"""Generate {count} additional hypotheses for this failure:

Root Cause: {diagnosis.root_cause}
Failure Type: {diagnosis.failure_type}

Focus on creative but practical solutions that weren't covered in the initial hypotheses.

Return as JSON array of hypothesis objects."""
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=GENERIC_HYPOTHESIS_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic even for additional hypotheses
            max_tokens=2000
        )
        
        return self._parse_hypothesis_response(response, ChangeType.PROMPT_MODIFICATION)
    
    def _initialize_best_practices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize embedded best practices database."""
        return {
            "prompt_engineering": [
                {
                    "practice": "Use clear task instructions",
                    "description": "Start prompts with clear, specific task descriptions",
                    "example": "Task: Analyze the sentiment of the following text and return 'positive', 'negative', or 'neutral'.",
                    "applicable_to": ["all models"]
                },
                {
                    "practice": "Provide examples (few-shot learning)",
                    "description": "Include 2-3 examples of desired input/output pairs",
                    "example": "Example 1: Input: 'I love this!' Output: 'positive'",
                    "applicable_to": ["all models"]
                },
                {
                    "practice": "Use chain-of-thought reasoning",
                    "description": "Ask the model to think step-by-step before answering",
                    "example": "Let's think step by step about this problem...",
                    "applicable_to": ["gpt-4", "claude", "llama"]
                },
                {
                    "practice": "Specify output format",
                    "description": "Clearly define the expected output structure",
                    "example": "Return your answer as JSON with keys: 'answer', 'confidence', 'reasoning'",
                    "applicable_to": ["all models"]
                }
            ],
            "context_management": [
                {
                    "practice": "Limit context window usage",
                    "description": "Keep prompts concise and relevant to avoid context overflow",
                    "technique": "Summarize long documents before including them",
                    "applicable_to": ["all models"]
                },
                {
                    "practice": "Structure context hierarchically",
                    "description": "Put most important information first",
                    "technique": "Use headers and clear sections",
                    "applicable_to": ["all models"]
                }
            ],
            "error_handling": [
                {
                    "practice": "Add validation instructions",
                    "description": "Tell the model to validate its own output",
                    "example": "After generating the response, verify it meets all requirements",
                    "applicable_to": ["all models"]
                },
                {
                    "practice": "Handle edge cases explicitly",
                    "description": "Provide instructions for handling edge cases",
                    "example": "If the input is empty or invalid, return an error message",
                    "applicable_to": ["all models"]
                }
            ]
        }
    
    def _build_search_query(
        self, 
        failure_type: str, 
        model: str, 
        context: Dict[str, Any]
    ) -> str:
        """Build a search query for best practices."""
        return f"{failure_type} {model} {context.get('specific_issue', '')} best practices"
    
    def _build_best_practices_search_prompt(
        self,
        search_query: str,
        failure_type: str,
        model: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for searching best practices."""
        template = Template(BEST_PRACTICES_SEARCH_TEMPLATE)
        return template.render(
            search_query=search_query,
            failure_type=failure_type,
            model=model,
            context=json.dumps(context, indent=2),
            embedded_practices=json.dumps(self._best_practices_db, indent=2)
        )
    
    def _build_prompt_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for generating prompt-related hypotheses."""
        template = Template(PROMPT_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2),
            relevant_files=code_context.relevant_files[:5]  # Limit to top 5 files
        )
    
    def _build_context_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for context-related hypotheses."""
        template = Template(CONTEXT_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2)
        )
    
    def _build_model_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for model limitation hypotheses."""
        template = Template(MODEL_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2)
        )
    
    def _build_orchestration_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for orchestration hypotheses."""
        template = Template(ORCHESTRATION_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2)
        )
    
    def _build_retrieval_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for retrieval hypotheses."""
        template = Template(RETRIEVAL_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2)
        )
    
    def _build_generic_hypothesis_prompt(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for generic hypotheses."""
        template = Template(GENERIC_HYPOTHESIS_TEMPLATE)
        return template.render(
            diagnosis=diagnosis,
            code_context=code_context,
            best_practices=json.dumps(best_practices, indent=2)
        )
    
    def _build_ranking_prompt(
        self,
        hypotheses: List[Hypothesis],
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for ranking hypotheses."""
        template = Template(HYPOTHESIS_RANKING_TEMPLATE)
        
        # Prepare hypothesis data for template
        hyp_data = []
        for hyp in hypotheses:
            hyp_data.append({
                "id": hyp.id,
                "description": hyp.description,
                "rationale": hyp.rationale,
                "num_changes": len(hyp.proposed_changes),
                "risks": hyp.risks,
                "confidence": hyp.confidence.value
            })
        
        return template.render(
            hypotheses=hyp_data,
            context=json.dumps(context, indent=2)
        )
    
    def _parse_best_practices_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse best practices search response."""
        try:
            # Extract JSON array from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse best practices response: {e}")
            return []
    
    def _parse_hypothesis_response(
        self, 
        response: str, 
        default_change_type: ChangeType
    ) -> List[Hypothesis]:
        """Parse hypothesis generation response."""
        try:
            # Extract JSON from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            hyp_data = json.loads(json_str)
            
            hypotheses = []
            for data in hyp_data:
                # Create FileChange objects
                changes = []
                for change in data.get("proposed_changes", []):
                    changes.append(FileChange(
                        file_path=change["file_path"],
                        original_content=change.get("original_content", ""),
                        new_content=change.get("new_content", ""),
                        change_type=ChangeType(change.get("change_type", default_change_type.value)),
                        description=change.get("description", "")
                    ))
                
                # Create Hypothesis
                hypothesis = Hypothesis(
                    id=str(uuid.uuid4()),
                    description=data["description"],
                    rationale=data["rationale"],
                    proposed_changes=changes,
                    confidence=Confidence(data.get("confidence", "medium")),
                    risks=data.get("risks", []),
                    example_before=data.get("example_before"),
                    example_after=data.get("example_after")
                )
                hypotheses.append(hypothesis)
            
            return hypotheses
        except Exception as e:
            logger.error(f"Failed to parse hypothesis response: {e}")
            return []
    
    def _parse_ranking_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse hypothesis ranking response."""
        try:
            # Extract JSON array from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse ranking response: {e}")
            return []
    
    def _enhance_with_embedded_knowledge(
        self,
        practices: List[Dict[str, Any]],
        failure_type: str,
        model: str
    ) -> List[Dict[str, Any]]:
        """Enhance search results with embedded best practices."""
        enhanced = practices.copy()
        
        # Add relevant embedded practices based on failure type
        if "prompt" in failure_type.lower():
            for practice in self._best_practices_db.get("prompt_engineering", []):
                if model in practice.get("applicable_to", []) or "all models" in practice.get("applicable_to", []):
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
        best_practices: List[Dict[str, Any]]
    ) -> Optional[Hypothesis]:
        """Generate hypothesis by rewriting prompts based on trace analysis and best practices."""
        if not original_prompts:
            return None
            
        # Get model-specific prompting guide
        model = config.hypothesis_model
        model_guide = self._get_model_prompting_guide(model)
        
        # Build comprehensive prompt for GPT-5 to rewrite the prompts
        prompt = self._build_trace_based_hypothesis_prompt(
            diagnosis, original_prompts, best_practices, model_guide
        )
        
        try:
            response = await self.llm.complete(
                prompt=prompt,
                system_prompt=TRACE_BASED_HYPOTHESIS_SYSTEM_PROMPT,
                temperature=0.0,  # Deterministic
                max_tokens=config.hypothesis_max_tokens
            )
            
            # Parse the response to extract the rewritten prompt
            new_prompt_content = self._parse_trace_based_response(response)
            
            if new_prompt_content:
                # Create FileChange with original and new content
                changes = [FileChange(
                    file_path="prompts/system.py",  # Default file path
                    original_content=original_prompts[0],  # Use first prompt as original
                    new_content=new_prompt_content,
                    change_type=ChangeType.PROMPT_MODIFICATION,
                    description="Complete prompt rewrite based on trace analysis and best practices"
                )]
                
                # Create hypothesis
                hypothesis = Hypothesis(
                    id=str(uuid.uuid4()),
                    description=f"Rewrite prompt to fix {diagnosis.failure_type.value.replace('_', ' ')}",
                    rationale=f"Based on diagnosis: {diagnosis.root_cause}. Applied {model} best practices.",
                    proposed_changes=changes,
                    confidence=diagnosis.confidence,
                    risks=["Prompt behavior may change", "Requires testing with existing workflows"],
                    example_before=original_prompts[0][:200] + "..." if len(original_prompts[0]) > 200 else original_prompts[0],
                    example_after=new_prompt_content[:200] + "..." if len(new_prompt_content) > 200 else new_prompt_content
                )
                
                # Add generation metadata
                hypothesis.generation_metadata = self._create_generation_metadata(diagnosis)
                
                return hypothesis
                
        except Exception as e:
            logger.error(f"Failed to generate trace-based hypothesis: {e}")
            
        return None
    
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
        model_guide: str
    ) -> str:
        """Build prompt for generating trace-based hypothesis."""
        return f"""
You are an expert prompt engineer tasked with rewriting prompts to fix AI agent failures.

## DIAGNOSIS
Root Cause: {diagnosis.root_cause}
Failure Type: {diagnosis.failure_type.value}
Evidence: {diagnosis.evidence}
Confidence: {diagnosis.confidence.value}

## ORIGINAL PROMPT
{original_prompts[0] if original_prompts else "No prompt available"}

## MODEL-SPECIFIC GUIDE
{model_guide}

## BEST PRACTICES
{chr(10).join([f"- {bp.get('title', '')}: {bp.get('description', '')}" for bp in best_practices[:5]])}

## TASK
Rewrite the original prompt to fix the identified issue. Your rewritten prompt should:
1. Address the specific failure identified in the diagnosis
2. Apply the model-specific best practices
3. Maintain the original intent and functionality
4. Be complete and ready to use (not a patch or diff)

## OUTPUT FORMAT
Provide ONLY the complete rewritten prompt. Do not include explanations, metadata, or comments.
Start your response with the prompt directly.
"""
    
    def _parse_trace_based_response(self, response: str) -> Optional[str]:
        """Parse response from trace-based hypothesis generation."""
        # For now, return the response directly as it should be the complete prompt
        # Future enhancement: Add validation and cleaning logic
        return response.strip() if response and response.strip() else None
    
    def _create_generation_metadata(self, diagnosis: Diagnosis) -> Dict[str, Any]:
        """Create metadata for reproducible hypothesis generation."""
        # Create diagnosis hash for reproducibility
        diagnosis_str = f"{diagnosis.root_cause}:{diagnosis.failure_type}:{diagnosis.confidence.value}"
        diagnosis_hash = hashlib.sha256(diagnosis_str.encode()).hexdigest()
        
        return {
            "model": self.hypothesis_model,
            "provider": config.hypothesis_llm_provider,
            "temperature": self.hypothesis_temperature,
            "top_p": 1.0,  # Default for deterministic sampling
            "max_tokens": self.hypothesis_max_tokens,
            "diagnosis_hash": f"sha256:{diagnosis_hash}",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "schema_version": 1
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

Return a JSON array of best practices in this format:
[
  {
    "practice": "Name of the practice",
    "description": "Detailed description",
    "technique": "Specific implementation technique",
    "example": "Code or prompt example if applicable",
    "relevance_score": 0.0-1.0,
    "applicable_to": ["model names"],
    "expected_improvement": "What this should fix"
  }
]

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

Return as JSON array:
[
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
    "confidence": "low/medium/high",
    "risks": ["potential risks"],
    "example_before": "Example of current behavior",
    "example_after": "Example of expected behavior after fix"
  }
]"""

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

Return as JSON array with proposed changes."""

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

Return as JSON array with specific implementations."""

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

Return as JSON array with implementation details."""

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

Return as JSON array with specific changes."""

GENERIC_HYPOTHESIS_SYSTEM_PROMPT = """You are a comprehensive AI agent improvement specialist with broad expertise across all aspects of AI system optimization."""

GENERIC_HYPOTHESIS_TEMPLATE = """Task: Generate hypotheses to fix this AI agent failure.

Diagnosis:
Failure Type: {{ diagnosis.failure_type }}
Root Cause: {{ diagnosis.root_cause }}
Full Analysis: {{ diagnosis.detailed_analysis }}

Code Context: {{ code_context }}
Best Practices: {{ best_practices }}

Generate diverse, practical hypotheses that could fix this issue.

Return as JSON array with complete implementation details."""

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

Return rankings as JSON array:
[
  {
    "id": "hypothesis_id",
    "rank": 1,
    "confidence": "low/medium/high",
    "reasoning": "Why this ranking"
  }
]

Order from most to least likely to succeed."""

TRACE_BASED_HYPOTHESIS_SYSTEM_PROMPT = """You are an expert prompt engineer with deep knowledge of AI model behavior and prompt optimization.

Your expertise includes:
- Analyzing AI agent failures and identifying root causes in prompts
- Model-specific prompt engineering (GPT, Claude, etc.)
- Best practices for clear, effective instruction writing
- Prompt optimization for specific use cases and behaviors

You specialize in rewriting prompts to fix specific issues while maintaining the original intent and functionality. 

Your responses should be complete, production-ready prompts that directly address the identified failures."""