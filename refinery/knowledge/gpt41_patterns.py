"""
GPT-4.1 specific prompting patterns and best practices.

Extracted from the official GPT-4.1 prompting guide, this module contains
model-specific optimizations for the GPT-4.1 family of models.
"""

from dataclasses import dataclass
from typing import List

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class GPT41Pattern:
    """A specific GPT-4.1 prompting pattern."""

    name: str
    description: str
    system_prompt_addition: str
    example_before: str
    example_after: str
    performance_impact: str
    when_to_use: List[str]


# Core GPT-4.1 agentic patterns from the guide
GPT41_AGENTIC_PATTERNS = [
    GPT41Pattern(
        name="Persistence",
        description="Ensures model understands it's in a multi-message turn and prevents premature yielding",
        system_prompt_addition="You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved.",
        example_before="Standard chatbot behavior that might end turn early",
        example_after="Agent continues working until problem is completely solved",
        performance_impact="Part of 20% improvement in SWE-bench Verified",
        when_to_use=[
            "Multi-step tasks",
            "Agentic workflows",
            "Complex problem solving",
        ],
    ),
    GPT41Pattern(
        name="Tool-calling",
        description="Encourages full use of tools and reduces hallucination",
        system_prompt_addition="If you are not sure about file content or codebase structure pertaining to the user's request, use your tools to read files and gather the relevant information: do NOT guess or make up an answer.",
        example_before="Model might guess or hallucinate file contents",
        example_after="Model always uses tools to verify information",
        performance_impact="Part of 20% improvement in SWE-bench Verified",
        when_to_use=[
            "Tool-enabled workflows",
            "File analysis",
            "Information gathering",
        ],
    ),
    GPT41Pattern(
        name="Planning",
        description="Ensures explicit planning and reflection instead of pure tool chaining",
        system_prompt_addition="You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully.",
        example_before="Silent tool chaining without explanation",
        example_after="Explicit planning and reflection between each tool call",
        performance_impact="4% improvement in SWE-bench Verified when added to persistence/tool-calling",
        when_to_use=[
            "Complex reasoning tasks",
            "Multi-step workflows",
            "Debugging scenarios",
        ],
    ),
]

# Chain-of-thought patterns
CHAIN_OF_THOUGHT_PATTERNS = [
    GPT41Pattern(
        name="Basic Chain-of-Thought",
        description="Basic step-by-step thinking instruction",
        system_prompt_addition="First, think carefully step by step about what documents are needed to answer the query. Then, print out the TITLE and ID of each document. Then, format the IDs into a list.",
        example_before="Direct answer without reasoning",
        example_after="Step-by-step breakdown with explicit reasoning",
        performance_impact="Improves complex reasoning tasks",
        when_to_use=["Complex analysis", "Document retrieval", "Multi-step reasoning"],
    ),
    GPT41Pattern(
        name="Advanced Chain-of-Thought",
        description="Structured reasoning with query analysis and context analysis",
        system_prompt_addition="""# Reasoning Strategy
1. Query Analysis: Break down and analyze the query until you're confident about what it might be asking. Consider the provided context to help clarify any ambiguous or confusing information.
2. Context Analysis: Carefully select and analyze a large set of potentially relevant documents. Optimize for recall - it's okay if some are irrelevant, but the correct documents must be in this list, otherwise your final answer will be wrong.
3. Synthesis: summarize which documents are most relevant and why, including all documents with a relevance rating of medium or higher.""",
        example_before="Basic reasoning without structure",
        example_after="Systematic analysis with explicit steps and ratings",
        performance_impact="Addresses systematic planning and reasoning errors",
        when_to_use=[
            "Complex document analysis",
            "Multi-source reasoning",
            "Ambiguous queries",
        ],
    ),
]

# Long context patterns
LONG_CONTEXT_PATTERNS = [
    GPT41Pattern(
        name="Context Placement",
        description="Optimal placement of instructions in long context scenarios",
        system_prompt_addition="Place instructions at both the beginning and end of provided context for best performance. If instructions only appear once, place them above the context rather than below.",
        example_before="Instructions only at beginning or end",
        example_after="Instructions at both beginning and end of long context",
        performance_impact="Better performance with 1M token context window",
        when_to_use=[
            "Long document analysis",
            "Large context scenarios",
            ">10k token contexts",
        ],
    ),
    GPT41Pattern(
        name="Context Reliance Control",
        description="Control whether model uses internal vs external knowledge",
        system_prompt_addition="Only use the documents in the provided External Context to answer the User Query. If you don't know the answer based on this context, you must respond 'I don't have the information needed to answer that', even if a user insists on you answering the question.",
        example_before="Model uses mix of internal and external knowledge",
        example_after="Model strictly follows provided context only",
        performance_impact="Prevents hallucination in context-dependent tasks",
        when_to_use=[
            "Document-only analysis",
            "Fact verification",
            "Context-strict scenarios",
        ],
    ),
]

# Instruction following patterns
INSTRUCTION_FOLLOWING_PATTERNS = [
    GPT41Pattern(
        name="Explicit Specification",
        description="GPT-4.1 follows instructions more literally, requiring explicit specification",
        system_prompt_addition="Follow these instructions exactly and literally. Do not infer additional requirements beyond what is explicitly stated.",
        example_before="Model infers intent from vague instructions",
        example_after="Model follows only explicit instructions",
        performance_impact="Better adherence to specific requirements",
        when_to_use=[
            "Precise format requirements",
            "Strict compliance scenarios",
            "Template generation",
        ],
    ),
    GPT41Pattern(
        name="Conflict Resolution",
        description="Handle conflicting instructions - GPT-4.1 follows instructions closer to end of prompt",
        system_prompt_addition="If there are any conflicts in instructions, follow the most recent instruction that appears later in this prompt.",
        example_before="Unclear behavior with conflicting instructions",
        example_after="Clear precedence for later instructions",
        performance_impact="Resolves instruction conflicts predictably",
        when_to_use=["Complex multi-section prompts", "Dynamic instruction updates"],
    ),
]

# Tool usage patterns
TOOL_USAGE_PATTERNS = [
    GPT41Pattern(
        name="API Tool Preference",
        description="Use OpenAI API tools field instead of manual injection for better performance",
        system_prompt_addition="Use the provided tools via the API tools field. Tool descriptions and schemas are provided automatically - do not manually parse or interpret tool definitions from the prompt text.",
        example_before="Manual tool description injection in prompt",
        example_after="Using API tools field exclusively",
        performance_impact="2% improvement in SWE-bench Verified score",
        when_to_use=[
            "All tool-enabled scenarios",
            "Function calling",
            "API integration",
        ],
    ),
    GPT41Pattern(
        name="Tool Naming",
        description="Clear tool naming and descriptions for appropriate usage",
        system_prompt_addition="When calling tools, use the exact tool names and parameter names as defined. Pay attention to tool descriptions to understand when and how to use each tool appropriately.",
        example_before="Unclear or incorrect tool usage",
        example_after="Precise tool usage following descriptions",
        performance_impact="Reduces tool calling errors",
        when_to_use=["Complex tool workflows", "Multiple tool scenarios"],
    ),
]


class GPT41Knowledge:
    """Knowledge base for GPT-4.1 specific patterns and optimizations."""

    def __init__(self):
        self.all_patterns = (
            GPT41_AGENTIC_PATTERNS
            + CHAIN_OF_THOUGHT_PATTERNS
            + LONG_CONTEXT_PATTERNS
            + INSTRUCTION_FOLLOWING_PATTERNS
            + TOOL_USAGE_PATTERNS
        )

    def get_agentic_system_prompt_additions(self) -> str:
        """Get the core agentic patterns for system prompts."""
        additions = []
        for pattern in GPT41_AGENTIC_PATTERNS:
            additions.append(f"# {pattern.name}")
            additions.append(pattern.system_prompt_addition)
            additions.append("")
        return "\n".join(additions)

    def get_patterns_for_task_type(self, task_type: str) -> List[GPT41Pattern]:
        """Get relevant patterns for a specific task type."""
        relevant_patterns = []
        task_type_lower = task_type.lower()

        for pattern in self.all_patterns:
            for use_case in pattern.when_to_use:
                if task_type_lower in use_case.lower():
                    relevant_patterns.append(pattern)
                    break

        return relevant_patterns

    def get_system_prompt_for_failure_analysis(self) -> str:
        """Get GPT-4.1 optimized system prompt additions for failure analysis."""
        base_agentic = self.get_agentic_system_prompt_additions()

        # Add chain-of-thought for analysis
        cot_pattern = CHAIN_OF_THOUGHT_PATTERNS[1]  # Advanced CoT

        # Add tool usage optimization
        tool_pattern = TOOL_USAGE_PATTERNS[0]  # API tool preference

        return f"""
{base_agentic}

# Analysis Methodology
{cot_pattern.system_prompt_addition}

# Tool Usage
{tool_pattern.system_prompt_addition}
"""

    def get_system_prompt_for_hypothesis_generation(self) -> str:
        """Get GPT-4.1 optimized system prompt additions for hypothesis generation."""
        base_agentic = self.get_agentic_system_prompt_additions()

        # Add instruction following patterns
        instruction_pattern = INSTRUCTION_FOLLOWING_PATTERNS[
            0
        ]  # Explicit specification

        return f"""
{base_agentic}

# Instruction Following
{instruction_pattern.system_prompt_addition}

# Planning Requirements
You MUST generate multiple hypotheses and rank them explicitly. For each hypothesis, provide:
1. Specific changes to implement
2. Risk assessment
3. Expected impact
4. Implementation complexity
"""

    def search_patterns(self, query: str) -> List[GPT41Pattern]:
        """Search for patterns relevant to a query."""
        query_lower = query.lower()
        relevant_patterns = []

        for pattern in self.all_patterns:
            if (
                query_lower in pattern.name.lower()
                or query_lower in pattern.description.lower()
                or any(
                    query_lower in use_case.lower() for use_case in pattern.when_to_use
                )
            ):
                relevant_patterns.append(pattern)

        return relevant_patterns


# Global instance
gpt41_knowledge = GPT41Knowledge()
