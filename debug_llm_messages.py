#!/usr/bin/env python3
"""Debug script to examine the actual messages in LLM runs."""

import asyncio
import json
from refinery.integrations.langsmith_client_simple import create_langsmith_client
from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel

console = Console()

async def examine_llm_messages(trace_id: str):
    """Examine the actual messages in LLM runs."""
    
    console.print(f"[bold blue]Examining LLM messages for {trace_id}[/bold blue]\n")
    
    # Initialize client and fetch trace
    client = await create_langsmith_client()
    trace = await client.fetch_trace(trace_id)
    
    # Find LLM runs
    llm_runs = [r for r in trace.runs if r.run_type.value == "llm"]
    console.print(f"Found {len(llm_runs)} LLM runs\n")
    
    for i, run in enumerate(llm_runs):
        console.print(f"[cyan]LLM Run {i+1}: {run.name}[/cyan]")
        console.print(f"Run ID: {run.id}")
        
        if "messages" in run.inputs:
            messages = run.inputs["messages"]
            console.print(f"Messages type: {type(messages)}")
            console.print(f"Messages length: {len(messages) if isinstance(messages, str) else 'N/A'}")
            
            # If it's a string, try to parse it
            if isinstance(messages, str):
                console.print("\n[yellow]Messages field contains a string, attempting to parse...[/yellow]")
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(messages)
                    console.print(f"Successfully parsed as JSON! Type: {type(parsed)}")
                    
                    if isinstance(parsed, list):
                        console.print(f"Found {len(parsed)} messages:")
                        
                        for j, msg in enumerate(parsed):
                            if isinstance(msg, dict):
                                role = msg.get('role', 'unknown')
                                content = msg.get('content', '')
                                console.print(f"\n[green]Message {j+1}:[/green]")
                                console.print(f"  Role: [bold]{role}[/bold]")
                                
                                # Show content preview
                                if content:
                                    if len(content) > 300:
                                        preview = content[:300] + "..."
                                    else:
                                        preview = content
                                    
                                    console.print(Panel(preview, title=f"Content ({len(content)} chars)", style="dim"))
                                
                except json.JSONDecodeError:
                    console.print("[red]Failed to parse as JSON[/red]")
                    # Show raw preview
                    preview = messages[:500] + "..." if len(messages) > 500 else messages
                    console.print(Panel(preview, title="Raw Messages Content", style="red"))
            
            elif isinstance(messages, list):
                console.print(f"\n[green]Messages is already a list with {len(messages)} items[/green]")
                for j, msg in enumerate(messages):
                    if isinstance(msg, dict):
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        console.print(f"\n  Message {j+1} - Role: {role}")
                        if content:
                            preview = content[:200] + "..." if len(content) > 200 else content
                            console.print(f"  Content: {preview}")
        
        # Check outputs too
        if run.outputs and "generations" in run.outputs:
            generations = run.outputs["generations"]
            if isinstance(generations, list) and len(generations) > 0:
                first_gen = generations[0]
                if isinstance(first_gen, dict) and "text" in first_gen:
                    response = first_gen["text"]
                    console.print(f"\n[blue]Response preview:[/blue] {response[:200]}...")
        
        console.print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        trace_id = sys.argv[1]
    else:
        trace_id = input("Enter trace ID: ").strip()
    
    asyncio.run(examine_llm_messages(trace_id))