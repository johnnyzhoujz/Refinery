"""Smart truncation that preserves complete runs when possible."""

import json
from typing import Any, Dict, List

from ..core.models import TraceRun
from ..utils.token_counter import TokenCounter


class SmartTruncator:
    """Intelligently truncate traces to fit within token limits."""

    def __init__(self, max_tokens: int = 50000):
        """Initialize with token budget.

        Args:
            max_tokens: Maximum tokens for trace data (excluding prompts)
        """
        self.max_tokens = max_tokens
        self.counter = TokenCounter()

    def truncate_trace_runs(self, runs: List[TraceRun]) -> List[Dict[str, Any]]:
        """Truncate runs intelligently to fit within token budget."""
        # First, count tokens for each run WITHOUT truncation
        run_tokens = []
        for run in runs:
            run_json = {
                "id": run.id,
                "name": run.name,
                "type": run.run_type.value,
                "inputs": json.dumps(run.inputs) if run.inputs else "",
                "outputs": json.dumps(run.outputs) if run.outputs else "",
                "error": run.error or "",
                "parent_id": run.parent_run_id,
                "dotted_order": run.dotted_order,
            }
            tokens = self.counter.count_text(json.dumps(run_json))
            run_tokens.append((run, run_json, tokens))

        # Sort by importance: failed runs first, then root runs, then by size
        def run_priority(item):
            run, _, tokens = item
            if run.error:
                return 0  # Highest priority
            elif not run.parent_run_id:
                return 1  # Root runs
            else:
                return 2 + tokens / 10000  # Regular runs, prefer smaller

        run_tokens.sort(key=run_priority)

        # Build result keeping whole runs when possible
        result = []
        total_tokens = 0

        for run, run_json, tokens in run_tokens:
            if total_tokens + tokens <= self.max_tokens:
                # Include complete run
                result.append(run_json)
                total_tokens += tokens
            elif total_tokens < self.max_tokens * 0.8:  # Still have 20% budget
                # Truncate this run to fit
                remaining_budget = self.max_tokens - total_tokens
                truncated_json = self._truncate_run_to_fit(run_json, remaining_budget)
                result.append(truncated_json)
                total_tokens += self.counter.count_text(json.dumps(truncated_json))
                break  # Don't include more after truncation

        return result

    def _truncate_run_to_fit(
        self, run_json: Dict[str, Any], token_budget: int
    ) -> Dict[str, Any]:
        """Truncate a single run to fit within token budget."""
        # Start with metadata (always keep)
        result = {
            "id": run_json["id"],
            "name": run_json["name"],
            "type": run_json["type"],
            "parent_id": run_json["parent_id"],
            "dotted_order": run_json["dotted_order"],
            "error": run_json["error"],
        }

        # Calculate remaining budget for inputs/outputs
        base_tokens = self.counter.count_text(json.dumps(result))
        remaining = token_budget - base_tokens

        # Split remaining budget between inputs and outputs
        input_budget = remaining // 2
        output_budget = remaining // 2

        # Truncate inputs
        inputs_str = run_json["inputs"]
        if self.counter.count_text(inputs_str) > input_budget:
            # Character estimate (rough: 4 chars per token)
            char_limit = input_budget * 4
            inputs_str = inputs_str[:char_limit] + "... [truncated]"
        result["inputs"] = inputs_str

        # Truncate outputs
        outputs_str = run_json["outputs"]
        if self.counter.count_text(outputs_str) > output_budget:
            char_limit = output_budget * 4
            outputs_str = outputs_str[:char_limit] + "... [truncated]"
        result["outputs"] = outputs_str

        return result

    def extract_prompts_from_runs(self, runs: List[TraceRun]) -> Dict[str, List[str]]:
        """Extract all prompts from runs for separate handling."""
        prompts = {"system_prompts": [], "user_prompts": [], "templates": []}

        for run in runs:
            if run.run_type.value == "llm" and run.inputs:
                # OpenAI format
                if "messages" in run.inputs:
                    for msg in run.inputs.get("messages", []):
                        if isinstance(msg, dict):
                            role = msg.get("role", "")
                            content = msg.get("content", "")
                            if role == "system" and content:
                                prompts["system_prompts"].append(content)
                            elif role == "user" and content:
                                prompts["user_prompts"].append(content)

                # Anthropic format
                elif "prompt" in run.inputs:
                    prompt = run.inputs["prompt"]
                    if isinstance(prompt, str):
                        prompts["user_prompts"].append(prompt)

        # Deduplicate
        for key in prompts:
            prompts[key] = list(set(prompts[key]))

        return prompts
