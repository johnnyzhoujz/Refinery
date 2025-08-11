#!/usr/bin/env python3
"""Debug script to examine the actual structure of runs in a trace."""

import asyncio
import json
from refinery.integrations.langsmith_client_simple import create_langsmith_client
from rich.console import Console
from rich.tree import Tree
from rich.table import Table

console = Console()

async def examine_trace_structure(trace_id: str):
    """Examine the structure of runs in a trace to understand how prompts are stored."""
    
    console.print(f"[bold blue]Examining trace structure for {trace_id}[/bold blue]\n")
    
    # Initialize client and fetch trace
    client = await create_langsmith_client()
    trace = await client.fetch_trace(trace_id)
    
    console.print(f"Total runs: {len(trace.runs)}\n")
    
    # Create a tree view of run types
    tree = Tree("[bold]Trace Structure[/bold]")
    
    # Group runs by type
    runs_by_type = {}
    for run in trace.runs:
        run_type = run.run_type.value
        if run_type not in runs_by_type:
            runs_by_type[run_type] = []
        runs_by_type[run_type].append(run)
    
    # Display runs by type
    for run_type, runs in runs_by_type.items():
        type_branch = tree.add(f"[cyan]{run_type}[/cyan] ({len(runs)} runs)")
        
        for i, run in enumerate(runs[:3]):  # Show first 3 of each type
            run_branch = type_branch.add(f"[dim]{run.name}[/dim]")
            
            # Show input structure
            if run.inputs:
                input_keys = list(run.inputs.keys())[:5]  # First 5 keys
                run_branch.add(f"[green]Inputs:[/green] {', '.join(input_keys)}")
                
                # Check for prompts in various locations
                if "messages" in run.inputs:
                    run_branch.add("[yellow]✓ Has 'messages' field (OpenAI format)[/yellow]")
                if "prompt" in run.inputs:
                    run_branch.add("[yellow]✓ Has 'prompt' field (Anthropic format)[/yellow]")
                if "system" in run.inputs:
                    run_branch.add("[yellow]✓ Has 'system' field[/yellow]")
                if "human" in run.inputs:
                    run_branch.add("[yellow]✓ Has 'human' field[/yellow]")
                
                # Look for nested prompt structures
                for key, value in run.inputs.items():
                    if isinstance(value, dict):
                        if "messages" in value:
                            run_branch.add(f"[yellow]✓ Has nested 'messages' in '{key}'[/yellow]")
                        if "prompt" in value:
                            run_branch.add(f"[yellow]✓ Has nested 'prompt' in '{key}'[/yellow]")
            
            # Show output structure briefly
            if run.outputs:
                output_keys = list(run.outputs.keys())[:3]
                run_branch.add(f"[blue]Outputs:[/blue] {', '.join(output_keys)}")
    
    console.print(tree)
    
    # Now look specifically for LLM runs and their structure
    console.print("\n[bold]Detailed LLM Run Analysis:[/bold]")
    llm_runs = [r for r in trace.runs if r.run_type.value == "llm"]
    
    if llm_runs:
        for i, run in enumerate(llm_runs[:2]):  # Examine first 2 LLM runs in detail
            console.print(f"\n[cyan]LLM Run {i+1}: {run.name}[/cyan]")
            
            if run.inputs:
                console.print("Input structure:")
                # Pretty print the structure (not the full content)
                structure = get_structure(run.inputs)
                console.print(json.dumps(structure, indent=2))
                
                # If there are messages, show one example
                if "messages" in run.inputs and isinstance(run.inputs["messages"], list):
                    if len(run.inputs["messages"]) > 0:
                        first_msg = run.inputs["messages"][0]
                        if isinstance(first_msg, dict):
                            console.print(f"\nFirst message example:")
                            console.print(f"  Role: {first_msg.get('role', 'N/A')}")
                            content = first_msg.get('content', '')
                            if content:
                                preview = content[:200] + "..." if len(content) > 200 else content
                                console.print(f"  Content preview: {preview}")
    else:
        console.print("[yellow]No LLM runs found in this trace[/yellow]")
        console.print("\nThis trace might be using a different structure for prompts.")
        console.print("Let's check what's actually in the Chain/Tool runs...")
        
        # Check chain runs
        chain_runs = [r for r in trace.runs if r.run_type.value == "chain"]
        if chain_runs and chain_runs[0].inputs:
            console.print(f"\n[cyan]First Chain Run Input Keys:[/cyan]")
            first_chain = chain_runs[0]
            for key in list(first_chain.inputs.keys())[:10]:
                value = first_chain.inputs[key]
                value_type = type(value).__name__
                console.print(f"  • {key}: {value_type}")
                
                # If it's a string that might be a prompt
                if isinstance(value, str) and len(value) > 100:
                    console.print(f"    [dim](Large string, possible prompt)[/dim]")

def get_structure(obj, max_depth=3, current_depth=0):
    """Get the structure of an object without the actual values."""
    if current_depth >= max_depth:
        return "..."
    
    if isinstance(obj, dict):
        return {k: get_structure(v, max_depth, current_depth + 1) for k, v in list(obj.items())[:5]}
    elif isinstance(obj, list):
        if len(obj) > 0:
            return [get_structure(obj[0], max_depth, current_depth + 1), f"... ({len(obj)} items)"]
        return []
    elif isinstance(obj, str):
        return f"<string: {len(obj)} chars>"
    elif isinstance(obj, (int, float, bool)):
        return f"<{type(obj).__name__}>"
    else:
        return f"<{type(obj).__name__}>"

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        trace_id = sys.argv[1]
    else:
        trace_id = input("Enter trace ID: ").strip()
    
    asyncio.run(examine_trace_structure(trace_id))