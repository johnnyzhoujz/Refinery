"""Token counting utilities for analyzing trace sizes."""

import json
from typing import Any, Dict

import tiktoken

from ..core.models import Trace


class TokenCounter:
    """Count tokens for various inputs to understand usage."""

    def __init__(self, model: str = "gpt-4"):
        """Initialize with specific model's tokenizer."""
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_text(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self.encoding.encode(text))

    def count_trace_raw(self, trace: Trace) -> Dict[str, Any]:
        """Count tokens in a raw trace without any truncation."""
        stats = {
            "total_tokens": 0,
            "runs_count": len(trace.runs),
            "by_run_type": {},
            "largest_runs": [],
            "inputs_tokens": 0,
            "outputs_tokens": 0,
            "errors_tokens": 0,
        }

        run_tokens = []

        for run in trace.runs:
            # Count tokens for this run
            run_data = {
                "id": run.id,
                "name": run.name,
                "type": run.run_type.value,
                "inputs": json.dumps(run.inputs) if run.inputs else "",
                "outputs": json.dumps(run.outputs) if run.outputs else "",
                "error": run.error or "",
            }

            # Count individual components
            inputs_tokens = self.count_text(run_data["inputs"])
            outputs_tokens = self.count_text(run_data["outputs"])
            error_tokens = self.count_text(run_data["error"])
            metadata_tokens = self.count_text(
                f"{run.id} {run.name} {run.run_type.value}"
            )

            total_run_tokens = (
                inputs_tokens + outputs_tokens + error_tokens + metadata_tokens
            )

            # Update stats
            stats["inputs_tokens"] += inputs_tokens
            stats["outputs_tokens"] += outputs_tokens
            stats["errors_tokens"] += error_tokens
            stats["total_tokens"] += total_run_tokens

            # Track by run type
            run_type = run.run_type.value
            if run_type not in stats["by_run_type"]:
                stats["by_run_type"][run_type] = {"count": 0, "tokens": 0}
            stats["by_run_type"][run_type]["count"] += 1
            stats["by_run_type"][run_type]["tokens"] += total_run_tokens

            # Track largest runs
            run_tokens.append(
                {
                    "run_id": run.id,
                    "run_name": run.name,
                    "tokens": total_run_tokens,
                    "inputs_tokens": inputs_tokens,
                    "outputs_tokens": outputs_tokens,
                }
            )

        # Sort and get top 5 largest runs
        stats["largest_runs"] = sorted(
            run_tokens, key=lambda x: x["tokens"], reverse=True
        )[:5]

        return stats

    def count_trace_truncated(self, trace: Trace) -> Dict[str, Any]:
        """Count tokens after Refinery's truncation logic is applied."""
        # Simulate the truncation that happens in langsmith_client_simple.py
        truncated_runs = []

        for run in trace.runs[:10]:  # Only first 10 runs
            inputs = run.inputs or {}
            outputs = run.outputs

            # Apply truncation logic
            if isinstance(inputs, dict):
                inputs = {
                    k: str(v)[:1000] + "..." if len(str(v)) > 1000 else v
                    for k, v in inputs.items()
                }

            if isinstance(outputs, dict):
                outputs = {
                    k: str(v)[:1000] + "..." if len(str(v)) > 1000 else v
                    for k, v in outputs.items()
                }
            elif isinstance(outputs, str) and len(outputs) > 1000:
                outputs = outputs[:1000] + "..."

            truncated_runs.append(
                {
                    "inputs": json.dumps(inputs),
                    "outputs": json.dumps(outputs) if outputs else "None",
                }
            )

        # Count tokens in truncated version
        total_truncated = 0
        for run_data in truncated_runs:
            # Further truncation in failure_analyst.py (500 chars)
            inputs_str = run_data["inputs"]
            if len(inputs_str) > 500:
                inputs_str = inputs_str[:500] + "... [truncated]"

            outputs_str = run_data["outputs"]
            if len(outputs_str) > 500:
                outputs_str = outputs_str[:500] + "... [truncated]"

            total_truncated += self.count_text(inputs_str + outputs_str)

        return {
            "truncated_tokens": total_truncated,
            "runs_included": len(truncated_runs),
        }

    def analyze_prompts_in_trace(self, trace: Trace) -> Dict[str, Any]:
        """Analyze prompt content specifically in the trace."""
        prompt_stats = {
            "system_prompts": [],
            "user_prompts": [],
            "total_prompt_tokens": 0,
            "llm_calls": 0,
        }

        for run in trace.runs:
            if run.run_type.value == "llm":
                prompt_stats["llm_calls"] += 1
                inputs = run.inputs or {}

                # Check for OpenAI format
                if "messages" in inputs and isinstance(inputs["messages"], list):
                    for msg in inputs["messages"]:
                        if isinstance(msg, dict):
                            content = msg.get("content", "")
                            role = msg.get("role", "")
                            tokens = self.count_text(content)

                            if role == "system":
                                prompt_stats["system_prompts"].append(
                                    {
                                        "tokens": tokens,
                                        "preview": (
                                            content[:100] + "..."
                                            if len(content) > 100
                                            else content
                                        ),
                                    }
                                )
                            elif role == "user":
                                prompt_stats["user_prompts"].append(
                                    {
                                        "tokens": tokens,
                                        "preview": (
                                            content[:100] + "..."
                                            if len(content) > 100
                                            else content
                                        ),
                                    }
                                )

                            prompt_stats["total_prompt_tokens"] += tokens

                # Check for Anthropic format
                elif "prompt" in inputs:
                    prompt = inputs["prompt"]
                    if isinstance(prompt, str):
                        tokens = self.count_text(prompt)
                        prompt_stats["user_prompts"].append(
                            {
                                "tokens": tokens,
                                "preview": (
                                    prompt[:100] + "..."
                                    if len(prompt) > 100
                                    else prompt
                                ),
                            }
                        )
                        prompt_stats["total_prompt_tokens"] += tokens

        return prompt_stats

    def generate_token_report(self, trace: Trace) -> str:
        """Generate a comprehensive token analysis report."""
        raw_stats = self.count_trace_raw(trace)
        truncated_stats = self.count_trace_truncated(trace)
        prompt_stats = self.analyze_prompts_in_trace(trace)

        report = f"""
TOKEN ANALYSIS REPORT
====================

Trace ID: {trace.trace_id}
Total Runs: {raw_stats['runs_count']}

RAW TRACE TOKENS
----------------
Total Tokens: {raw_stats['total_tokens']:,}
- Inputs: {raw_stats['inputs_tokens']:,}
- Outputs: {raw_stats['outputs_tokens']:,}
- Errors: {raw_stats['errors_tokens']:,}

By Run Type:
"""
        for run_type, data in raw_stats["by_run_type"].items():
            report += f"  {run_type}: {data['count']} runs, {data['tokens']:,} tokens\n"

        report += """
Largest Runs:
"""
        for run in raw_stats["largest_runs"]:
            report += f"  - {run['run_name']}: {run['tokens']:,} tokens (inputs: {run['inputs_tokens']:,}, outputs: {run['outputs_tokens']:,})\n"

        report += f"""
TRUNCATED TRACE TOKENS (What Refinery Actually Sees)
----------------------------------------------------
Tokens after truncation: {truncated_stats['truncated_tokens']:,}
Runs included: {truncated_stats['runs_included']} (out of {raw_stats['runs_count']})
Token reduction: {(1 - truncated_stats['truncated_tokens']/raw_stats['total_tokens'])*100:.1f}%

PROMPT ANALYSIS
---------------
LLM Calls: {prompt_stats['llm_calls']}
Total Prompt Tokens: {prompt_stats['total_prompt_tokens']:,}
System Prompts: {len(prompt_stats['system_prompts'])}
User Prompts: {len(prompt_stats['user_prompts'])}
"""

        if prompt_stats["system_prompts"]:
            report += "\nSystem Prompt Samples:\n"
            for i, prompt in enumerate(prompt_stats["system_prompts"][:3]):
                report += f"  {i+1}. {prompt['tokens']} tokens: {prompt['preview']}\n"

        return report


async def analyze_trace_tokens(trace_id: str) -> str:
    """Analyze token usage for a specific trace."""
    from ..integrations.langsmith_client_simple import create_langsmith_client

    client = await create_langsmith_client()
    trace = await client.fetch_trace(trace_id)

    counter = TokenCounter()
    return counter.generate_token_report(trace)
