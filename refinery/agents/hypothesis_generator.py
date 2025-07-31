"""
Implementation of the HypothesisGenerator interface for generating improvement hypotheses.

This module generates ranked hypotheses for fixing AI agent failures, leveraging
best practices and advanced prompting strategies.
"""

import json
import logging
import uuid
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
        self.llm = get_llm_provider(config)
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
            temperature=0.3,
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
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the issue using multi-strategy approach."""
        logger.info(f"Generating hypotheses for {diagnosis.failure_type}")
        
        # Use different strategies based on failure type
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.7,
            max_tokens=3000
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
            temperature=0.8,
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