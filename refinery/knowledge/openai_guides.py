"""OpenAI-specific prompting guides and best practices.

This module contains structured OpenAI prompting knowledge including GPT-4.1
specific patterns and general prompting best practices.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import structlog
from .gpt41_patterns import gpt41_knowledge, GPT41Pattern

logger = structlog.get_logger(__name__)


@dataclass
class BestPractice:
    """A specific prompting best practice."""
    technique: str
    description: str
    example_before: str
    example_after: str
    use_cases: List[str]
    model_compatibility: List[str]  # ["gpt-4", "gpt-3.5-turbo", etc.]
    

@dataclass
class OpenAIGuide:
    """Complete OpenAI prompting guide."""
    techniques: List[BestPractice]
    common_issues: List[str]
    optimization_patterns: List[str]
    model_specific_tips: Dict[str, List[str]]  # model -> tips


# Placeholder - will be populated with actual OpenAI guide content
OPENAI_PROMPTING_GUIDE = OpenAIGuide(
    techniques=[
        BestPractice(
            technique="Write clear instructions",
            description="The model can't read your mind. Be explicit about what you want.",
            example_before="Write a poem",
            example_after="Write a 4-line poem about a cat, using ABAB rhyme scheme",
            use_cases=["All prompt types"],
            model_compatibility=["gpt-4", "gpt-3.5-turbo"]
        ),
        # More techniques will be added from the official guide
    ],
    common_issues=[
        "Ambiguous instructions leading to unexpected outputs",
        "Missing context causing hallucinations",
        "Poor example formatting reducing few-shot effectiveness",
        # More issues from the guide
    ],
    optimization_patterns=[
        "Use delimiters to separate sections",
        "Ask for structured output (JSON, markdown tables)",
        "Give the model time to think with chain-of-thought",
        # More patterns from the guide
    ],
    model_specific_tips={
        "gpt-4": [
            "Can handle longer, more complex instructions",
            "Better at following multi-step processes",
            "More reliable for structured output generation"
        ],
        "gpt-3.5-turbo": [
            "Keep instructions concise and clear",
            "Use more examples for complex tasks",
            "May need more explicit formatting instructions"
        ]
    }
)


def search_best_practices(query: str, failure_type: str, model: str = "gpt-4") -> List[BestPractice]:
    """Search for relevant best practices based on the failure type and query."""
    relevant_practices = []
    
    # First, get GPT-4.1 specific patterns if using GPT-4.1
    if "gpt-4.1" in model.lower():
        gpt41_patterns = gpt41_knowledge.search_patterns(query)
        # Convert GPT-4.1 patterns to BestPractice format
        for pattern in gpt41_patterns:
            practice = BestPractice(
                technique=pattern.name,
                description=pattern.description,
                example_before=pattern.example_before,
                example_after=pattern.example_after,
                use_cases=pattern.when_to_use,
                model_compatibility=["gpt-4.1"]
            )
            relevant_practices.append(practice)
    
    # Then search general practices
    query_lower = query.lower()
    for practice in OPENAI_PROMPTING_GUIDE.techniques:
        if (query_lower in practice.description.lower() or 
            query_lower in practice.technique.lower() or
            failure_type in str(practice.use_cases).lower()):
            relevant_practices.append(practice)
    
    return relevant_practices


def get_model_specific_tips(model: str) -> List[str]:
    """Get tips specific to a model version."""
    return OPENAI_PROMPTING_GUIDE.model_specific_tips.get(model, [])


# This function will be called to load the actual guide content
def load_openai_guide_from_file(file_path: str):
    """Load the OpenAI prompting guide from a file.
    
    This will be used to populate the guide with actual content
    once the official guide is provided.
    """
    logger.info("Ready to load OpenAI guide from file", file_path=file_path)
    # Implementation will parse the provided guide file
    pass