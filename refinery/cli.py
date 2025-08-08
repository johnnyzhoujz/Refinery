"""Command-line interface for Refinery."""

import asyncio
import click
import sys
import os
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.markdown import Markdown

from .utils.config import config
from .core.orchestrator import create_orchestrator
from .core.context import RefineryContext, load_or_create_context

console = Console()


@click.group()
@click.option('--debug/--no-debug', default=False, help='Enable debug mode')
@click.option('--config-file', help='Path to configuration file')
def main(debug: bool, config_file: str):
    """Refinery: AI-powered development platform for domain expert empowerment."""
    if debug:
        config.debug = True
        config.log_level = "DEBUG"
    
    try:
        config.validate()
    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.argument('trace_id')
@click.option('--project', required=True, help='LangSmith project name')
@click.option('--expected', required=True, help='What should have happened')
@click.option('--context', help='Additional business context')
@click.option('--codebase', default='.', help='Path to codebase')
@click.option('--prompt-files', multiple=True, help='Prompt files to analyze')
@click.option('--eval-files', multiple=True, help='Evaluation files to analyze')
@click.option('--config-files', multiple=True, help='Configuration files to analyze')
# Context management options (same as fix command)
@click.option('--add-prompt', multiple=True, help='Add prompt files to saved context')
@click.option('--add-eval', multiple=True, help='Add eval files to saved context')
@click.option('--remove-prompt', multiple=True, help='Remove prompt files from saved context')
@click.option('--remove-eval', multiple=True, help='Remove eval files from saved context')
@click.option('--update', is_flag=True, help='Replace saved context instead of appending')
# Option to extract prompts from trace
@click.option('--extract-from-trace', is_flag=True, help='Extract and save prompts from the trace itself')
@click.option('--apply', is_flag=True, help='Apply the best hypothesis instead of a dry run')
def analyze(trace_id: str, project: str, expected: str, context: str, codebase: str, 
            prompt_files: tuple, eval_files: tuple, config_files: tuple,
            add_prompt: tuple, add_eval: tuple, remove_prompt: tuple, remove_eval: tuple,
            update: bool, extract_from_trace: bool, apply: bool):
    """Analyze a failed trace and provide root cause diagnosis."""
    
    async def run_analysis():
        codebase_abs = os.path.abspath(codebase)
        context_manager = RefineryContext(codebase_abs)
        
        # Step 1: Handle context management (same as fix command)
        try:
            # Handle file removals first
            if remove_prompt or remove_eval:
                console.print("[blue]Removing files from context...[/blue]")
                context_manager.remove_files(
                    project,
                    prompt_files=list(remove_prompt) if remove_prompt else None,
                    eval_files=list(remove_eval) if remove_eval else None
                )
                console.print("✓ Files removed from context")
            
            # Handle file additions
            if add_prompt or add_eval:
                console.print("[blue]Adding files to context...[/blue]")
                context_manager.create_or_update_context(
                    project,
                    prompt_files=list(add_prompt) if add_prompt else None,
                    eval_files=list(add_eval) if add_eval else None,
                    append=True  # Always append when using --add-*
                )
                console.print("✓ Files added to context")
            
            # Handle full file specification (create/update context)
            if prompt_files or eval_files or config_files:
                console.print("[blue]Updating context with specified files...[/blue]")
                context_manager.create_or_update_context(
                    project,
                    prompt_files=list(prompt_files) if prompt_files else None,
                    eval_files=list(eval_files) if eval_files else None,
                    config_files=list(config_files) if config_files else None,
                    append=not update
                )
                console.print("✓ Context updated")
            
            # Step 2: Optional - Extract prompts from trace and save them
            if extract_from_trace:
                console.print("[blue]Extracting prompts from trace...[/blue]")
                orchestrator = await create_orchestrator(codebase_abs)
                # Fetch the trace
                trace = await orchestrator.langsmith_client.fetch_trace(trace_id)
                # Extract prompts from the trace
                extracted = orchestrator.langsmith_client.extract_prompts_from_trace(trace)
                # Store extracted prompts as files
                created_files = context_manager.store_trace_prompts(project, extracted, trace_id)
                console.print(f"[green]✓ Extracted and saved {len(created_files['prompt_files'])} prompt files, "
                            f"{len(created_files['eval_files'])} eval files[/green]")
            
            # Step 3: Load final context
            project_context, context_exists = load_or_create_context(codebase_abs, project)
            
            # Validate we have files to work with
            total_files = (len(project_context.get("prompt_files", [])) + 
                          len(project_context.get("eval_files", [])))
            
            if total_files == 0:
                console.print("[red]No files specified for analysis![/red]")
                console.print("\nOptions:")
                console.print("1. Specify files manually:")
                console.print("   refinery analyze <trace> --project <name> --prompt-files <files> --eval-files <files>")
                console.print("\n2. Extract from trace:")
                console.print("   refinery analyze <trace> --project <name> --extract-from-trace")
                console.print("\n3. Add files to existing project:")
                console.print("   refinery analyze <trace> --project <name> --add-prompt <file>")
                return
            
            # Show what files we're using
            if context_exists:
                console.print(f"[green]Using saved context for '{project}' ({total_files} files)[/green]")
            else:
                console.print(f"[yellow]Created new context for '{project}' ({total_files} files)[/yellow]")
            
            if config.debug:
                console.print(f"Prompt files: {project_context.get('prompt_files', [])}")
                console.print(f"Eval files: {project_context.get('eval_files', [])}")
                
        except Exception as e:
            console.print(f"[red]Context management error: {e}[/red]")
            return
        
        # Step 4: Read the actual file contents from saved context
        prompt_contents = {}
        eval_contents = {}
        
        # Get absolute file paths for reading
        file_paths = context_manager.get_file_paths(project)
        
        # Read prompt files
        if file_paths["prompt_files"]:
            console.print("[blue]Reading prompt files from context...[/blue]")
            for file_path in file_paths["prompt_files"]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        prompt_contents[file_path] = f.read()
                    console.print(f"[green]✓[/green] Read {os.path.basename(file_path)}")
                except Exception as e:
                    console.print(f"[red]✗[/red] Failed to read {file_path}: {e}")
        
        # Read eval files
        if file_paths["eval_files"]:
            console.print("[blue]Reading eval files from context...[/blue]")
            for file_path in file_paths["eval_files"]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        eval_contents[file_path] = f.read()
                    console.print(f"[green]✓[/green] Read {os.path.basename(file_path)}")
                except Exception as e:
                    console.print(f"[red]✗[/red] Failed to read {file_path}: {e}")
        
        # Step 5: Initialize orchestrator and run analysis
        with console.status("[bold blue]Initializing Refinery..."):
            if not extract_from_trace:  # Only create orchestrator if not already created
                orchestrator = await create_orchestrator(codebase_abs)
        
        console.print(f"[blue]Analyzing trace {trace_id} from project {project}...[/blue]")
        console.print(f"[dim]Using {len(prompt_contents)} prompt files and {len(eval_contents)} eval files[/dim]")
        
        try:
            with console.status("[bold blue]Fetching trace and analyzing failure..."):
                diagnosis = await orchestrator.analyze_failure(
                    trace_id=trace_id,
                    project=project, 
                    expected_behavior=expected,
                    business_context=context,
                    prompt_contents=prompt_contents,
                    eval_contents=eval_contents
                )
            
            # Display diagnosis
            console.print("\n" + "="*60)
            console.print(Panel.fit("[bold red]FAILURE DIAGNOSIS[/bold red]", style="red"))
            
            table = Table(title="Analysis Results")
            table.add_column("Aspect", style="cyan")
            table.add_column("Finding", style="white")
            
            table.add_row("Failure Type", diagnosis.failure_type.value.replace('_', ' ').title())
            table.add_row("Root Cause", diagnosis.root_cause)
            table.add_row("Confidence", diagnosis.confidence.value.upper())
            table.add_row("Affected Components", ", ".join(diagnosis.affected_components))
            
            console.print(table)
            
            console.print("\n[bold]Detailed Analysis:[/bold]")
            console.print(Panel(diagnosis.detailed_analysis, style="dim"))
            
            if diagnosis.evidence:
                console.print("\n[bold]Evidence:[/bold]")
                for i, evidence in enumerate(diagnosis.evidence, 1):
                    console.print(f"  {i}. {evidence}")
                    
        except Exception as e:
            console.print(f"[red]Error during analysis: {e}[/red]")
            if config.debug:
                import traceback
                console.print(traceback.format_exc())
    
    asyncio.run(run_analysis())


@main.command()
@click.argument('trace_id')
@click.option('--project', required=True, help='LangSmith project name')
@click.option('--expected', required=True, help='Expected behavior description')
@click.option('--context', help='Additional business context')
@click.option('--codebase', default='.', help='Path to codebase')
@click.option('--apply', is_flag=True, help='Apply the best hypothesis (otherwise dry run)')
# File specification options
@click.option('--prompt-files', multiple=True, help='Prompt files to analyze')
@click.option('--eval-files', multiple=True, help='Evaluation files to analyze')
@click.option('--config-files', multiple=True, help='Configuration files to analyze')
# Context management options
@click.option('--add-prompt', multiple=True, help='Add prompt files to saved context')
@click.option('--add-eval', multiple=True, help='Add eval files to saved context')
@click.option('--remove-prompt', multiple=True, help='Remove prompt files from saved context')
@click.option('--remove-eval', multiple=True, help='Remove eval files from saved context')
@click.option('--update', is_flag=True, help='Replace saved context instead of appending')
def fix(trace_id: str, project: str, expected: str, context: str, codebase: str, apply: bool,
        prompt_files: tuple, eval_files: tuple, config_files: tuple,
        add_prompt: tuple, add_eval: tuple, remove_prompt: tuple, remove_eval: tuple,
        update: bool):
    """Analyze a failure and generate hypotheses to fix it."""
    
    async def run_fix():
        codebase_abs = os.path.abspath(codebase)
        context_manager = RefineryContext(codebase_abs)
        
        # Step 1: Handle context management
        try:
            # Handle file removals first
            if remove_prompt or remove_eval:
                console.print("[blue]Removing files from context...[/blue]")
                context_manager.remove_files(
                    project,
                    prompt_files=list(remove_prompt) if remove_prompt else None,
                    eval_files=list(remove_eval) if remove_eval else None
                )
                console.print("✓ Files removed from context")
            
            # Handle file additions
            if add_prompt or add_eval:
                console.print("[blue]Adding files to context...[/blue]")
                context_manager.create_or_update_context(
                    project,
                    prompt_files=list(add_prompt) if add_prompt else None,
                    eval_files=list(add_eval) if add_eval else None,
                    append=True  # Always append when using --add-*
                )
                console.print("✓ Files added to context")
            
            # Handle full file specification (create/update context)
            if prompt_files or eval_files or config_files:
                console.print("[blue]Updating context with specified files...[/blue]")
                context_manager.create_or_update_context(
                    project,
                    prompt_files=list(prompt_files) if prompt_files else None,
                    eval_files=list(eval_files) if eval_files else None,
                    config_files=list(config_files) if config_files else None,
                    append=not update
                )
                console.print("✓ Context updated")
            
            # Load final context
            project_context, context_exists = load_or_create_context(codebase_abs, project)
            
            # Validate we have files to work with
            total_files = (len(project_context.get("prompt_files", [])) + 
                          len(project_context.get("eval_files", [])))
            
            if total_files == 0:
                console.print("[red]No files specified for analysis![/red]")
                console.print("\nFirst time setup:")
                console.print("  refinery fix <trace> --project <name> --prompt-files <files> --eval-files <files>")
                console.print("\nAdd more files:")
                console.print("  refinery fix <trace> --project <name> --add-prompt <file>")
                return
            
            # Show what files we're using
            if context_exists:
                console.print(f"[green]Using saved context for '{project}' ({total_files} files)[/green]")
            else:
                console.print(f"[yellow]Created new context for '{project}' ({total_files} files)[/yellow]")
            
            if config.debug:
                console.print(f"Prompt files: {project_context.get('prompt_files', [])}")
                console.print(f"Eval files: {project_context.get('eval_files', [])}")
            
        except Exception as e:
            console.print(f"[red]Context management error: {e}[/red]")
            return
        
        # Step 2: Initialize orchestrator and run analysis
        try:
            with console.status("[bold blue]Initializing Refinery..."):
                orchestrator = await create_orchestrator(codebase_abs)
            
            # Get absolute file paths for the orchestrator
            file_paths = context_manager.get_file_paths(project)
            
            # Read the files specified in context
            all_files = (file_paths["prompt_files"] + 
                        file_paths["eval_files"] + 
                        file_paths["config_files"])
            
            if all_files:
                console.print(f"[blue]Reading {len(all_files)} files from context...[/blue]")
                implementation = await orchestrator.read_existing_implementation(all_files)
                console.print(f"✓ Read {len(implementation)} files")
            
            # Step 3: Analyze failure
            with console.status("[bold blue]Analyzing failure..."):
                diagnosis = await orchestrator.analyze_failure(
                    trace_id=trace_id,
                    project=project,
                    expected_behavior=expected,
                    business_context=context
                )
            
            console.print(f"[green]✓[/green] Diagnosed: {diagnosis.failure_type.value}")
            
            # Step 4: Generate hypotheses
            with console.status("[bold blue]Generating fix hypotheses..."):
                hypotheses = await orchestrator.generate_fixes(diagnosis)
            
            console.print(f"[green]✓[/green] Generated {len(hypotheses)} hypotheses")
            
            # Step 5: Display hypotheses
            console.print("\n" + "="*60)
            console.print(Panel.fit("[bold green]FIX HYPOTHESES[/bold green]", style="green"))
            
            for i, hypothesis in enumerate(hypotheses, 1):
                console.print(f"\n[bold cyan]Hypothesis {i}:[/bold cyan] {hypothesis.description}")
                console.print(f"[dim]Confidence: {hypothesis.confidence.value} | Risk: {hypothesis.get_risk_level()}[/dim]")
                console.print(f"[yellow]Rationale:[/yellow] {hypothesis.rationale}")
                
                if hypothesis.proposed_changes:
                    console.print(f"[blue]Changes ({len(hypothesis.proposed_changes)} files):[/blue]")
                    for change in hypothesis.proposed_changes:
                        console.print(f"  • {change.file_path} ({change.change_type.value})")
                
                if hypothesis.risks:
                    console.print(f"[red]Risks:[/red]")
                    for risk in hypothesis.risks:
                        console.print(f"  ⚠️  {risk}")
            
            # Step 6: Apply or dry-run best hypothesis
            if hypotheses:
                best_hypothesis = hypotheses[0]
                
                if apply:
                    console.print(f"\n[bold yellow]Applying best hypothesis...[/bold yellow]")
                    result = await orchestrator.apply_hypothesis(best_hypothesis, dry_run=False)
                    
                    if result.get("success"):
                        console.print(f"[green]✓ Successfully applied changes![/green]")
                        console.print(f"Commit ID: {result.get('commit_id')}")
                    else:
                        console.print(f"[red]✗ Failed to apply changes[/red]")
                else:
                    console.print(f"\n[bold blue]Dry run of best hypothesis...[/bold blue]")
                    result = await orchestrator.apply_hypothesis(best_hypothesis, dry_run=True)
                    
                    console.print(f"Validation results:")
                    for validation in result["validation_results"]:
                        status = "✓" if validation["valid"] else "✗"
                        console.print(f"  {status} {validation['file']}")
                        if validation["issues"]:
                            for issue in validation["issues"]:
                                console.print(f"    ⚠️  {issue}")
                    
                    if result["all_valid"]:
                        console.print("\n[green]All changes are valid! Run with --apply to implement.[/green]")
                    else:
                        console.print("\n[red]Some changes have issues. Please review before applying.[/red]")
                        
        except Exception as e:
            console.print(f"[red]Error during analysis: {e}[/red]")
            if config.debug:
                import traceback
                console.print(traceback.format_exc())
    
    asyncio.run(run_fix())


@main.command(name='token-analysis')
@click.argument('trace_id')
def token_analysis(trace_id: str):
    """Analyze token usage for a trace."""
    from .utils.token_counter import analyze_trace_tokens
    
    async def run_analysis():
        try:
            with console.status("[bold blue]Analyzing trace tokens..."):
                report = await analyze_trace_tokens(trace_id)
            
            console.print(report)
            
        except Exception as e:
            console.print(f"[red]Error analyzing tokens: {e}[/red]")
            if config.debug:
                import traceback
                console.print(traceback.format_exc())
    
    asyncio.run(run_analysis())


@main.command(name='config-check')
def config_check():
    """Check configuration status."""
    table = Table(title="Refinery Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")
    
    # LangSmith
    table.add_row(
        "LangSmith API Key", 
        "✓ Set" if config.langsmith_api_key else "✗ Missing",
        "OK" if config.langsmith_api_key else "ERROR"
    )
    
    # LLM Provider
    table.add_row("LLM Provider", config.llm_provider, "OK")
    
    if config.llm_provider == "openai":
        table.add_row(
            "OpenAI API Key",
            "✓ Set" if config.openai_api_key else "✗ Missing",
            "OK" if config.openai_api_key else "ERROR"
        )
        table.add_row("OpenAI Model", config.openai_model, "OK")
    
    elif config.llm_provider == "anthropic":
        table.add_row(
            "Anthropic API Key",
            "✓ Set" if config.anthropic_api_key else "✗ Missing",
            "OK" if config.anthropic_api_key else "ERROR"
        )
        table.add_row("Anthropic Model", config.anthropic_model, "OK")
    
    elif config.llm_provider == "gemini":
        table.add_row(
            "Gemini API Key",
            "✓ Set" if config.gemini_api_key else "✗ Missing",
            "OK" if config.gemini_api_key else "ERROR"
        )
        table.add_row("Gemini Model", config.gemini_model, "OK")
    
    console.print(table)


# Removed create-manifest command - using simple file passing instead


@main.command()
@click.option('--project', help='Show context for specific project')
@click.option('--list', 'list_projects', is_flag=True, help='List all projects with saved contexts')
@click.option('--clear', help='Clear context for specified project')
@click.option('--codebase', default='.', help='Path to codebase')
def context(project: str, list_projects: bool, clear: str, codebase: str):
    """Manage Refinery project contexts."""
    codebase_abs = os.path.abspath(codebase)
    context_manager = RefineryContext(codebase_abs)
    
    if list_projects:
        projects = context_manager.list_projects()
        if projects:
            console.print("[bold blue]Projects with saved contexts:[/bold blue]")
            for proj in projects:
                console.print(f"  • {proj}")
        else:
            console.print("[yellow]No saved contexts found.[/yellow]")
        return
    
    if clear:
        try:
            context_manager.clear_project_context(clear)
            console.print(f"[green]✓ Cleared context for project '{clear}'[/green]")
        except Exception as e:
            console.print(f"[red]Error clearing context: {e}[/red]")
        return
    
    if project:
        project_context = context_manager.get_project_context(project)
        if not project_context:
            console.print(f"[red]No context found for project '{project}'[/red]")
            return
        
        # Validate and show context
        validation_result = context_manager.validate_and_clean_context(project)
        context_data = validation_result["context"]
        missing_files = validation_result["missing_files"]
        
        console.print(f"[bold blue]Context for project '{project}':[/bold blue]")
        
        table = Table(title="Saved Files")
        table.add_column("Type", style="cyan")
        table.add_column("Files", style="white")
        
        prompt_files = context_data.get("prompt_files", [])
        eval_files = context_data.get("eval_files", [])
        config_files = context_data.get("config_files", [])
        
        table.add_row("Prompts", f"{len(prompt_files)} files")
        table.add_row("Evaluations", f"{len(eval_files)} files")
        table.add_row("Configurations", f"{len(config_files)} files")
        
        console.print(table)
        
        if config.debug:
            console.print("\n[dim]Detailed file list:[/dim]")
            if prompt_files:
                console.print("  [cyan]Prompt files:[/cyan]")
                for f in prompt_files:
                    console.print(f"    {f}")
            if eval_files:
                console.print("  [cyan]Eval files:[/cyan]")
                for f in eval_files:
                    console.print(f"    {f}")
            if config_files:
                console.print("  [cyan]Config files:[/cyan]")
                for f in config_files:
                    console.print(f"    {f}")
        
        if missing_files:
            console.print(f"\n[yellow]⚠️  {len(missing_files)} files were removed (no longer exist):[/yellow]")
            for f in missing_files:
                console.print(f"    {f}")
        
        metadata = context_data.get("metadata", {})
        if metadata.get("last_updated"):
            console.print(f"\n[dim]Last updated: {metadata['last_updated']}[/dim]")
        
    else:
        console.print("[yellow]Please specify --project, --list, or --clear[/yellow]")
        console.print("\nExamples:")
        console.print("  refinery context --list")
        console.print("  refinery context --project my-agent")
        console.print("  refinery context --clear my-agent")


@main.command()
@click.option('--project', required=True, help='LangSmith project name')
@click.option('--limit', default=10, help='Number of failed traces to show')
def list_failures(project: str, limit: int):
    """List recent failed traces."""
    console.print(f"[blue]Fetching {limit} recent failures from {project}...[/blue]")
    
    # This will be implemented by the LangSmith integration subagent
    console.print("[yellow]This command will be implemented by the LangSmith subagent.[/yellow]")


if __name__ == "__main__":
    main()