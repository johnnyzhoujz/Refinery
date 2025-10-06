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

        def handle_progress(event_type: str, payload: dict) -> None:
            """Stream analysis milestones to the console for better UX."""

            try:
                if event_type == "analysis_started":
                    console.log(
                        f"[blue]Starting analysis for trace {payload.get('trace_id', '')}[/blue]"
                    )
                elif event_type == "stage1_planning":
                    mode = "chunked" if payload.get("chunking") else "single-call"
                    console.log(
                        f"[cyan]Stage 1 planning: {payload.get('total_runs', '?')} runs → {mode}[/cyan]"
                    )
                elif event_type == "vector_store_upload_start":
                    console.log(
                        f"[cyan]Staging files for vector store ({payload.get('mode', 'unknown')} mode): "
                        f"{payload.get('total_files', 0)} files (batch size {payload.get('batch_size', '?')}).[/cyan]"
                    )
                elif event_type == "vector_store_batch_start":
                    console.log(
                        f"[white]Uploading batch {payload.get('batch_number')}/{payload.get('total_batches')} "
                        f"to vector store…[/white]"
                    )
                elif event_type == "vector_store_batch_complete":
                    console.log(
                        f"[green]Uploaded batch {payload.get('batch_number')}/{payload.get('total_batches')} "
                        f"({payload.get('completed_files', 0)} files, {payload.get('duration_seconds', 0)}s).[/green]"
                    )
                elif event_type == "vector_store_batch_failed":
                    console.log(
                        f"[red]Vector store batch {payload.get('batch_number')} failed ({payload.get('failed_files', 0)} files).[/red]"
                    )
                elif event_type == "vector_store_upload_complete":
                    console.log(
                        f"[green]Vector store staging complete in {payload.get('duration_seconds', 0)}s.[/green]"
                    )
                elif event_type == "stage1_chunked_enqueued":
                    console.log(
                        f"[cyan]Stage 1 chunked: {payload.get('total_groups')} groups, group size {payload.get('group_size')}[/cyan]"
                    )
                elif event_type == "stage1_single_call_enqueued":
                    console.log("[cyan]Stage 1 single-call mode queued.[/cyan]")
                elif event_type == "stage1_group_start":
                    console.log(
                        f"[white]Stage 1 chunk {payload.get('group_index')}/{payload.get('total_groups')} started[/white]"
                    )
                elif event_type == "stage1_group_retry":
                    attempt = payload.get("attempt") or 0
                    max_attempts = payload.get("max_attempts") or (attempt + 1)
                    next_attempt = min(attempt + 1, max_attempts)
                    error_summary = payload.get("error")
                    if error_summary:
                        error_summary = error_summary.strip()
                        if len(error_summary) > 120:
                            error_summary = error_summary[:117] + "..."
                    console.log(
                        f"[yellow]Stage 1 chunk {payload.get('group_index')} retrying in {payload.get('backoff_seconds')}s "
                        f"(attempt {next_attempt}/{max_attempts})"
                        + (f" – {error_summary}" if error_summary else "")
                        + "[/yellow]"
                    )
                elif event_type == "stage1_group_rate_limited":
                    console.log(
                        f"[yellow]Stage 1 chunk {payload.get('group_index')} waiting {payload.get('wait_seconds')}s for TPM[/yellow]"
                    )
                elif event_type == "stage1_group_complete":
                    console.log(
                        f"[green]Stage 1 chunk {payload.get('group_index')} completed (attempts: {payload.get('attempts')})[/green]"
                    )
                elif event_type == "stage1_group_failed":
                    console.log(
                        f"[red]Stage 1 chunk {payload.get('group_index')} exhausted retries; continuing with placeholders ({payload.get('error')})[/red]"
                    )
                elif event_type == "stage1_group_connection_failed":
                    console.log(
                        f"[red]Stage 1 chunk {payload.get('group_index')} hit repeated connection failures: {payload.get('error')[:160]}[/red]"
                    )
                elif event_type == "stage1_group_sleep":
                    console.log(
                        f"[white]Stage 1 pausing {payload.get('sleep_seconds')}s before next chunk (completed {payload.get('completed_groups')} groups).[/white]"
                    )
                elif event_type == "stage1_chunked_complete":
                    console.log(
                        f"[green]Stage 1 chunked run complete ({payload.get('merged_timeline_items', 0)} timeline items).[/green]"
                    )
                elif event_type == "stage1_interactive_complete":
                    console.log(
                        f"[green]Stage 1 completed with {payload.get('timeline_items', 0)} timeline items.[/green]"
                    )
                elif event_type == "stage2_start":
                    console.log("[cyan]Stage 2 (Gap Analysis) started.[/cyan]")
                elif event_type == "stage2_retry":
                    stage2_error = payload.get("error")
                    note = ""
                    if stage2_error:
                        stage2_error = stage2_error.strip()
                        if len(stage2_error) > 120:
                            stage2_error = stage2_error[:117] + "..."
                        note = f" – {stage2_error}"
                    console.log(
                        f"[yellow]Stage 2 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage2_failed":
                    console.log(
                        f"[red]Stage 2 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage2_complete":
                    console.log("[green]Stage 2 complete.[/green]")
                elif event_type == "stage3_start":
                    console.log("[cyan]Stage 3 (Diagnosis) started.[/cyan]")
                elif event_type == "stage3_retry":
                    stage3_error = payload.get("error")
                    note = ""
                    if stage3_error:
                        stage3_error = stage3_error.strip()
                        if len(stage3_error) > 120:
                            stage3_error = stage3_error[:117] + "..."
                        note = f" – {stage3_error}"
                    console.log(
                        f"[yellow]Stage 3 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage3_failed":
                    console.log(
                        f"[red]Stage 3 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage3_complete":
                    console.log(
                        f"[green]Stage 3 complete – root cause: {payload.get('root_cause', 'n/a')}[/green]"
                    )
                elif event_type == "stage4_start":
                    console.log("[cyan]Stage 4 (Synthesis) started.[/cyan]")
                elif event_type == "stage4_retry":
                    stage4_error = payload.get("error")
                    note = ""
                    if stage4_error:
                        stage4_error = stage4_error.strip()
                        if len(stage4_error) > 120:
                            stage4_error = stage4_error[:117] + "..."
                        note = f" – {stage4_error}"
                    console.log(
                        f"[yellow]Stage 4 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage4_failed":
                    console.log(
                        f"[red]Stage 4 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage4_complete":
                    console.log("[green]Stage 4 complete. Preparing final summary...[/green]")
                elif event_type == "analysis_completed":
                    console.log(
                        f"[green]Analysis finished – failure type: {payload.get('failure_type', 'unknown')}[/green]"
                    )
                elif event_type == "hypothesis_best_practices_start":
                    console.log(
                        "[cyan]Hypothesis: fetching best practices...[/cyan]"
                    )
                elif event_type == "hypothesis_best_practices_complete":
                    console.log(
                        f"[green]Hypothesis best practices ready ({payload.get('count', 0)} matches, {payload.get('elapsed_s', 0)}s).[/green]"
                    )
                elif event_type == "hypothesis_generation_start":
                    console.log(
                        f"[cyan]Hypothesis generation ({payload.get('stage', 'unknown')}) started.[/cyan]"
                    )
                elif event_type == "hypothesis_generation_chunk_progress":
                    console.log(
                        f"[white]Hypothesis generation progress ({payload.get('stage', 'unknown')}): {int(payload.get('progress', 0)*100)}%.[/white]"
                    )
                elif event_type == "hypothesis_generation_complete":
                    console.log(
                        f"[green]Hypothesis generation ({payload.get('stage', 'unknown')}) complete – {payload.get('count', 0)} candidates in {payload.get('elapsed_s', 0)}s.[/green]"
                    )
                elif event_type == "hypothesis_rank_start":
                    console.log(
                        "[cyan]Ranking hypotheses...[/cyan]"
                    )
                elif event_type == "hypothesis_rank_complete":
                    console.log(
                        f"[green]Hypothesis ranking complete ({payload.get('elapsed_s', 0)}s).[/green]"
                    )
                elif event_type == "hypothesis_failed":
                    console.log(
                        f"[red]Hypothesis stage failed ({payload.get('stage', 'unknown')}): {payload.get('error', 'unknown error')}[/red]"
                    )
            except Exception:
                # Progress should never interrupt analysis; log quietly in debug builds
                if config.debug:
                    console.log(f"[red]Progress callback error for {event_type}[/red]")

        
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
                orchestrator = await create_orchestrator(
                    codebase_abs, progress_callback=handle_progress
                )
                # Fetch the trace (ensures single LangSmith call per run)
                trace = await orchestrator.ensure_trace(trace_id)
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
                console.print("[yellow]No local context files configured; defaulting to LangSmith prompts/evals.[/yellow]")
            else:
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
        prompt_contents = None
        eval_contents = None
        
        # Get absolute file paths for reading
        file_paths = context_manager.get_file_paths(project)
        
        # Read prompt files
        if file_paths["prompt_files"]:
            console.print("[blue]Reading prompt files from context...[/blue]")
            prompt_contents = {}
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
            eval_contents = {}
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
                orchestrator = await create_orchestrator(
                    codebase_abs, progress_callback=handle_progress
                )

        console.print(f"[blue]Analyzing trace {trace_id} from project {project}...[/blue]")

        try:
            with console.status("[bold blue]Fetching trace and analyzing failure..."):
                complete_analysis = await orchestrator.analyze_failure(
                    trace_id=trace_id,
                    project=project, 
                    expected_behavior=expected,
                    business_context=context,
                    prompt_contents=prompt_contents,
                    eval_contents=eval_contents
                )
            
            # Extract diagnosis from complete analysis
            diagnosis = complete_analysis.diagnosis
            
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
            
            # Display enhanced recommendations if available
            if diagnosis.remediations:
                console.print("\n[bold]Recommended Fixes:[/bold]")
                for i, remediation in enumerate(diagnosis.remediations[:5], 1):
                    action = remediation.get("action", "Unknown action")
                    priority = remediation.get("priority", "medium").upper()
                    console.print(f"  {i}. [{priority}] {action}")
            
            if diagnosis.next_actions:
                console.print("\n[bold]Next Actions:[/bold]")
                for i, action in enumerate(diagnosis.next_actions[:5], 1):
                    action_text = action.get("action", "Unknown action")
                    priority = action.get("priority", "medium").upper()
                    console.print(f"  {i}. [{priority}] {action_text}")
                    
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
                analysis = await orchestrator.analyze_failure(
                    trace_id=trace_id,
                    project=project,
                    expected_behavior=expected,
                    business_context=context
                )

            diagnosis = analysis.diagnosis
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


# Version Control Commands (GPT-5 Integration)

@main.command()
@click.argument('trace_id')
@click.option('--project', required=True, help='Project name for context')
@click.option('--expected', required=True, help='What should have happened')
@click.option('--tag', help='Optional tag for this version')
@click.option('--codebase', default='.', help='Path to codebase')
def generate(trace_id: str, project: str, expected: str, tag: str, codebase: str):
    """Generate hypothesis version from trace analysis (GPT-5 powered)."""
    
    async def run_generate():
        console.print(f"[blue]Generating hypothesis version for trace {trace_id}...[/blue]")
        
        try:
            # Use existing context for the project
            codebase_abs = os.path.abspath(codebase)
            context_manager = RefineryContext(codebase_abs)
            
            # Try to load existing context first
            prompt_contents, eval_contents, config_contents = context_manager.load_context_for_project(project)
            
            if not prompt_contents and not eval_contents:
                console.print(f"[yellow]No saved context found for project '{project}'. Please run 'refinery analyze' first to set up context.[/yellow]")
                return
            
            # Create orchestrator and run analysis
            orchestrator = await create_orchestrator(codebase_abs)
            
            console.print("[blue]Running failure analysis with GPT-4o...[/blue]")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                task = progress.add_task("Analyzing trace...", total=None)
                
                analysis = await orchestrator.analyze_failure(
                    trace_id=trace_id,
                    project=project,
                    expected_behavior=expected,
                    prompt_contents=prompt_contents,
                    eval_contents=eval_contents
                )
                
                progress.update(task, description="Generating hypotheses with GPT-5...")
                
                hypotheses = await orchestrator.generate_hypotheses(
                    diagnosis=analysis.diagnosis,
                    code_context=analysis.code_context,
                    max_hypotheses=3
                )
            
            if not hypotheses:
                console.print("[red]No hypotheses generated.[/red]")
                return
            
            # Apply the best hypothesis with version saving
            best_hypothesis = hypotheses[0]
            console.print(f"[green]Generated hypothesis: {best_hypothesis.description}[/green]")
            
            result = await orchestrator.apply_hypothesis(
                best_hypothesis, 
                dry_run=True,  # Generate version but don't deploy yet
                save_version=True,
                tag=tag
            )
            
            version_id = result.get('version_id')
            if version_id:
                console.print(f"[green]✅ Saved as version: {version_id}[/green]")
                console.print(f"[blue]Use 'refinery test {version_id}' to stage for testing[/blue]")
                console.print(f"[blue]Use 'refinery deploy {version_id} --confirm' to apply to production[/blue]")
            else:
                console.print("[red]Failed to save version[/red]")
        
        except Exception as e:
            console.print(f"[red]Error generating version: {e}[/red]")
    
    asyncio.run(run_generate())


@main.command()
@click.argument('version_id')
@click.option('--codebase', default='.', help='Path to codebase')
def test(version_id: str, codebase: str):
    """Stage version for testing in .refinery/staging/."""
    
    async def run_test():
        try:
            codebase_abs = os.path.abspath(codebase)
            orchestrator = create_orchestrator(codebase_abs)
            
            console.print(f"[blue]Staging version {version_id} for testing...[/blue]")
            staged_path = orchestrator.stage_version(version_id)
            
            console.print(f"[green]✅ Staged at: {staged_path}[/green]")
            console.print(f"[blue]Run your tests against files in this directory[/blue]")
            console.print(f"[blue]Use 'refinery deploy {version_id} --confirm' when ready to apply[/blue]")
        
        except Exception as e:
            console.print(f"[red]Error staging version: {e}[/red]")
    
    asyncio.run(run_test())


@main.command()
@click.argument('version1_id')
@click.argument('version2_id', required=False)
@click.option('--codebase', default='.', help='Path to codebase')
def diff(version1_id: str, version2_id: str, codebase: str):
    """Compare two versions (or version vs current)."""
    
    async def run_diff():
        try:
            codebase_abs = os.path.abspath(codebase)
            orchestrator = create_orchestrator(codebase_abs)
            
            if version2_id:
                console.print(f"[blue]Comparing {version1_id} vs {version2_id}...[/blue]")
                diff_result = orchestrator.diff_versions(version1_id, version2_id)
            else:
                console.print(f"[blue]Showing version {version1_id} details...[/blue]")
                version_info = orchestrator.get_version(version1_id)
                if not version_info:
                    console.print(f"[red]Version {version1_id} not found[/red]")
                    return
                
                # Show version details
                table = Table(title=f"Version {version1_id}")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")
                
                table.add_row("Created", version_info.get("created_at", "Unknown"))
                table.add_row("Description", version_info.get("description", "No description"))
                table.add_row("Tag", version_info.get("tag", "None"))
                table.add_row("Files", str(len(version_info.get("files", []))))
                
                console.print(table)
                
                if version_info.get("files"):
                    console.print("\n[bold]Files in this version:[/bold]")
                    for file_info in version_info["files"]:
                        console.print(f"  • {file_info['path']}")
                return
            
            # Show diff results
            changes = diff_result.get("changes", [])
            if not changes:
                console.print("[green]No differences found[/green]")
                return
            
            table = Table(title=f"Differences: {version1_id} → {version2_id}")
            table.add_column("Change Type", style="cyan")
            table.add_column("File Path", style="white")
            
            for change in changes:
                change_type = change["type"]
                if change_type == "added":
                    table.add_row(f"[green]+[/green] Added", change["path"])
                elif change_type == "removed":
                    table.add_row(f"[red]-[/red] Removed", change["path"])
                else:
                    table.add_row(f"[yellow]~[/yellow] Modified", change["path"])
            
            console.print(table)
        
        except Exception as e:
            console.print(f"[red]Error comparing versions: {e}[/red]")
    
    asyncio.run(run_diff())


@main.command()
@click.argument('version_id')
@click.option('--confirm', is_flag=True, help='Confirm deployment (required)')
@click.option('--codebase', default='.', help='Path to codebase')
def deploy(version_id: str, confirm: bool, codebase: str):
    """Deploy version to production with automatic backup."""
    
    async def run_deploy():
        if not confirm:
            console.print("[red]Deploy requires explicit confirmation: --confirm[/red]")
            console.print("[blue]This will modify your prompt files. Use --confirm to proceed.[/blue]")
            return
        
        try:
            codebase_abs = os.path.abspath(codebase)
            orchestrator = create_orchestrator(codebase_abs)
            
            # Show version info first
            version_info = orchestrator.get_version(version_id)
            if not version_info:
                console.print(f"[red]Version {version_id} not found[/red]")
                return
            
            console.print(f"[yellow]⚠️  About to deploy version {version_id} to production[/yellow]")
            console.print(f"Description: {version_info.get('description', 'No description')}")
            console.print(f"Files to modify: {len(version_info.get('files', []))}")
            
            for file_info in version_info.get("files", []):
                console.print(f"  • {file_info['path']}")
            
            console.print(f"[blue]Deploying with automatic backup...[/blue]")
            backup_id = orchestrator.deploy_version(version_id, confirm=True)
            
            console.print(f"[green]✅ Successfully deployed version {version_id}[/green]")
            console.print(f"[blue]Backup saved as: {backup_id}[/blue]")
            console.print(f"[blue]Files are now live in your prompts/ directory[/blue]")
        
        except Exception as e:
            console.print(f"[red]Error deploying version: {e}[/red]")
    
    asyncio.run(run_deploy())


@main.command(name='list-versions')
@click.option('--codebase', default='.', help='Path to codebase')
def list_versions_cmd(codebase: str):
    """List all saved versions."""
    
    try:
        codebase_abs = os.path.abspath(codebase)
        orchestrator = create_orchestrator(codebase_abs)
        
        versions = orchestrator.list_versions()
        
        if not versions:
            console.print("[yellow]No versions found[/yellow]")
            return
        
        table = Table(title="Saved Versions")
        table.add_column("Version ID", style="cyan")
        table.add_column("Created", style="white")
        table.add_column("Tag", style="green")
        table.add_column("Description", style="white")
        table.add_column("Files", justify="right", style="blue")
        
        for version in versions:
            table.add_row(
                version["version_id"],
                version["created_at"][:19] if version.get("created_at") else "Unknown",
                version.get("tag") or "None",
                (version.get("description") or "No description")[:60],
                str(version.get("files_count", 0))
            )
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error listing versions: {e}[/red]")


@main.command()
@click.option('--project', default='default', help='Project name (default: default)')
@click.option('--codebase', default='.', help='Path to codebase (default: current directory)')
def chat(project: str, codebase: str):
    """Interactive chat mode for analyzing AI agent failures."""
    
    async def run_chat():
        # Import here to avoid circular imports
        from .interfaces.chat_interface import ChatInterface
        from .interfaces.chat_session import run_chat_session
        
        interface = ChatInterface()
        await run_chat_session(interface, codebase, project)
    
    asyncio.run(run_chat())


@main.command()
def ui():
    """Launch Streamlit UI."""
    import subprocess
    import sys
    import os
    from pathlib import Path
    
    # Set environment to skip Streamlit welcome screen
    env = os.environ.copy()
    env['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    
    console.print("[blue]🔬 Launching Refinery Web UI...[/blue]")
    console.print("[dim]Starting server and opening browser...[/dim]")
    
    ui_path = Path(__file__).parent / "ui" / "app.py"
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(ui_path),
            "--server.headless=false",
            "--browser.gatherUsageStats=false",
            "--global.showWarningOnDirectExecution=false"
        ], env=env)
    except KeyboardInterrupt:
        console.print("[yellow]UI server stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error launching UI: {e}[/red]")
        console.print("[blue]Try running manually: streamlit run refinery/ui/app.py[/blue]")


if __name__ == "__main__":
    main()
