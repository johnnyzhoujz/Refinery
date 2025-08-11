#!/usr/bin/env python3
"""Test script to verify prompt extraction from traces."""

import asyncio
import json
import os
from pprint import pprint
from refinery.integrations.langsmith_client_simple import create_langsmith_client
from refinery.core.orchestrator import create_orchestrator
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

async def test_prompt_extraction(trace_id: str = None):
    """Test that we can extract prompts from a trace."""
    
    console.print("[bold blue]Testing Prompt Extraction from Traces[/bold blue]\n")
    
    # If no trace_id provided, ask user
    if not trace_id:
        trace_id = input("Enter a trace ID to test with: ").strip()
    
    try:
        # Initialize the LangSmith client
        console.print("[yellow]1. Initializing LangSmith client...[/yellow]")
        client = await create_langsmith_client()
        
        # Fetch the trace
        console.print(f"[yellow]2. Fetching trace {trace_id}...[/yellow]")
        trace = await client.fetch_trace(trace_id)
        console.print(f"[green]✓ Fetched trace with {len(trace.runs)} runs[/green]\n")
        
        # Extract prompts from the trace
        console.print("[yellow]3. Extracting prompts from trace...[/yellow]")
        extracted = client.extract_prompts_from_trace(trace)
        
        # Display results
        console.print("\n[bold green]Extraction Results:[/bold green]\n")
        
        # System prompts
        if extracted["system_prompts"]:
            console.print(f"[cyan]Found {len(extracted['system_prompts'])} System Prompts:[/cyan]")
            for i, prompt in enumerate(extracted["system_prompts"], 1):
                console.print(f"\n[dim]System Prompt {i} (from {prompt['run_name']}):[/dim]")
                # Truncate long prompts for display
                content = prompt["content"]
                if len(content) > 500:
                    content = content[:500] + "..."
                console.print(Panel(content, style="blue"))
        else:
            console.print("[yellow]No system prompts found[/yellow]")
        
        # User prompts
        if extracted["user_prompts"]:
            console.print(f"\n[cyan]Found {len(extracted['user_prompts'])} User Prompts:[/cyan]")
            for i, prompt in enumerate(extracted["user_prompts"], 1):
                console.print(f"\n[dim]User Prompt {i} (from {prompt['run_name']}):[/dim]")
                content = prompt["content"]
                if len(content) > 500:
                    content = content[:500] + "..."
                console.print(Panel(content, style="green"))
                if prompt.get("has_variables"):
                    console.print("  [yellow]⚠️  Contains template variables[/yellow]")
        else:
            console.print("[yellow]No user prompts found[/yellow]")
        
        # Prompt templates
        if extracted["prompt_templates"]:
            console.print(f"\n[cyan]Found {len(extracted['prompt_templates'])} Prompt Templates:[/cyan]")
            for i, template in enumerate(extracted["prompt_templates"], 1):
                console.print(f"\n[dim]Template {i} (key: {template['key']}):[/dim]")
                console.print(f"  Variables: {template['variables']}")
                content = template["content"]
                if len(content) > 300:
                    content = content[:300] + "..."
                console.print(Panel(content, style="magenta"))
        else:
            console.print("[yellow]No prompt templates found[/yellow]")
        
        # Model configurations
        if extracted["model_configs"]:
            console.print(f"\n[cyan]Found {len(extracted['model_configs'])} Model Configurations:[/cyan]")
            for config in extracted["model_configs"]:
                console.print(f"  • {config.get('model_name', config.get('model', 'unknown'))}: "
                            f"temp={config.get('temperature', 'N/A')}, "
                            f"max_tokens={config.get('max_tokens', 'N/A')}")
        
        # Eval examples (potential test cases)
        if extracted["eval_examples"]:
            console.print(f"\n[cyan]Found {len(extracted['eval_examples'])} Potential Test Cases[/cyan]")
            console.print(f"  [dim](Input/output pairs from successful runs)[/dim]")
        
        # Test using in analysis
        console.print("\n[yellow]4. Testing usage in analysis...[/yellow]")
        
        # Create a simple test to verify the prompts would be used
        if extracted["system_prompts"] or extracted["user_prompts"]:
            # Simulate what the CLI does with --extract-from-trace
            prompt_contents = {}
            eval_contents = {}
            
            # Convert extracted prompts to file-like content
            for i, system_prompt in enumerate(extracted["system_prompts"]):
                key = f"system_prompt_{i}.txt"
                prompt_contents[key] = system_prompt["content"]
            
            for i, user_prompt in enumerate(extracted["user_prompts"]):
                key = f"user_prompt_{i}.txt"
                prompt_contents[key] = user_prompt["content"]
            
            console.print(f"[green]✓ Would pass {len(prompt_contents)} prompt files to analysis[/green]")
            console.print(f"[green]✓ Would pass {len(eval_contents)} eval files to analysis[/green]")
            
            # Show what would be passed
            if prompt_contents:
                console.print("\n[dim]Sample of what would be passed to analysis:[/dim]")
                first_key = list(prompt_contents.keys())[0]
                content = prompt_contents[first_key][:200] + "..." if len(prompt_contents[first_key]) > 200 else prompt_contents[first_key]
                console.print(f"  {first_key}: {content}")
        
        # Save extraction results for inspection
        output_file = f"trace_{trace_id[:8]}_extracted.json"
        with open(output_file, 'w') as f:
            # Convert to serializable format
            serializable = {
                "trace_id": trace_id,
                "system_prompts_count": len(extracted["system_prompts"]),
                "user_prompts_count": len(extracted["user_prompts"]),
                "templates_count": len(extracted["prompt_templates"]),
                "model_configs_count": len(extracted["model_configs"]),
                "eval_examples_count": len(extracted["eval_examples"]),
                "sample_system_prompt": extracted["system_prompts"][0]["content"][:500] if extracted["system_prompts"] else None,
                "sample_user_prompt": extracted["user_prompts"][0]["content"][:500] if extracted["user_prompts"] else None,
            }
            json.dump(serializable, f, indent=2)
        
        console.print(f"\n[green]✓ Full extraction results saved to {output_file}[/green]")
        
        return extracted
        
    except Exception as e:
        console.print(f"[red]Error during testing: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return None


async def test_full_analysis_with_extraction(trace_id: str = None, project: str = None):
    """Test the full analysis workflow with prompt extraction."""
    
    console.print("\n[bold blue]Testing Full Analysis with Extracted Prompts[/bold blue]\n")
    
    if not trace_id:
        trace_id = input("Enter trace ID: ").strip()
    if not project:
        project = input("Enter project name: ").strip()
    
    expected = input("What should have happened? ").strip()
    
    try:
        # Initialize orchestrator
        console.print("[yellow]Initializing orchestrator...[/yellow]")
        orchestrator = await create_orchestrator(os.getcwd())
        
        # Fetch and extract prompts
        console.print("[yellow]Fetching trace and extracting prompts...[/yellow]")
        trace = await orchestrator.langsmith_client.fetch_trace(trace_id)
        extracted = orchestrator.langsmith_client.extract_prompts_from_trace(trace)
        
        # Convert to file contents format
        prompt_contents = {}
        for i, prompt in enumerate(extracted["system_prompts"]):
            prompt_contents[f"system_{i}.txt"] = prompt["content"]
        for i, prompt in enumerate(extracted["user_prompts"]):
            prompt_contents[f"user_{i}.txt"] = prompt["content"]
        
        console.print(f"[green]✓ Extracted {len(prompt_contents)} prompts[/green]")
        
        # Run analysis with extracted prompts
        console.print("\n[yellow]Running analysis with extracted prompts...[/yellow]")
        diagnosis = await orchestrator.analyze_failure(
            trace_id=trace_id,
            project=project,
            expected_behavior=expected,
            prompt_contents=prompt_contents if prompt_contents else None,
            eval_contents={}
        )
        
        # Display results
        console.print("\n[bold green]Analysis Results:[/bold green]")
        console.print(f"Failure Type: {diagnosis.failure_type.value}")
        console.print(f"Root Cause: {diagnosis.root_cause}")
        console.print(f"Confidence: {diagnosis.confidence.value}")
        console.print(f"\n[dim]Analysis used {len(prompt_contents)} extracted prompts[/dim]")
        
        return diagnosis
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return None


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--full":
            # Test full analysis
            trace_id = sys.argv[2] if len(sys.argv) > 2 else None
            project = sys.argv[3] if len(sys.argv) > 3 else None
            asyncio.run(test_full_analysis_with_extraction(trace_id, project))
        else:
            # Just test extraction
            trace_id = sys.argv[1]
            asyncio.run(test_prompt_extraction(trace_id))
    else:
        console.print("Usage:")
        console.print("  python test_prompt_extraction.py [TRACE_ID]  - Test extraction only")
        console.print("  python test_prompt_extraction.py --full [TRACE_ID] [PROJECT]  - Test full analysis")
        console.print("\nIf no trace ID provided, you'll be prompted for one.")
        
        # Run basic extraction test
        asyncio.run(test_prompt_extraction())