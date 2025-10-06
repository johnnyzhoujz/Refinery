"""
Core chat session logic that works with any interface type.

This module contains the reusable business logic for conducting
a chat session with the user, separated from the specific interface
implementation (CLI, NL, Web, etc).
"""

import os
from typing import Optional

from .chat_interface import BaseChatInterface
from ..core.orchestrator import create_orchestrator
from ..core.context import RefineryContext, load_or_create_context
from ..utils.config import config


async def run_chat_session(
    interface: BaseChatInterface, 
    codebase: str = ".",
    default_project: str = "default"
):
    """
    Run a complete chat session using the provided interface.
    
    This is the core reusable logic that works with any interface type:
    - CLI prompts (current)
    - Natural language interface (future)  
    - Web interface (future)
    
    Args:
        interface: The chat interface to use for user interaction
        codebase: Path to the codebase (default: current directory)
        default_project: Default project name if not specified
    """
    
    # Welcome the user
    await interface.show_welcome()
    
    try:
        # Step 1: Get basic information from user
        trace_id = await interface.get_trace_id()
        if not trace_id.strip():
            await interface.show_error("Trace ID is required")
            return
            
        expected_behavior = await interface.get_expected_behavior()
        if not expected_behavior.strip():
            await interface.show_error("Expected behavior description is required")
            return
            
        project = await interface.get_project_name(default_project)
        
        # Step 2: Set up context and orchestrator
        codebase_abs = os.path.abspath(codebase)
        context_manager = RefineryContext(codebase_abs)
        
        # Load existing context or create new one
        project_context, context_exists = load_or_create_context(codebase_abs, project)
        
        # Check if we have files to work with
        total_files = (
            len(project_context.get("prompt_files", [])) + 
            len(project_context.get("eval_files", []))
        )
        
        if total_files == 0:
            await interface.show_error(
                f"No files configured for project '{project}'. "
                f"Use 'refinery analyze --extract-from-trace' to extract files from the trace, "
                f"or configure files manually with the analyze command first."
            )
            return
        
        # Step 3: Read file contents from saved context
        file_paths = context_manager.get_file_paths(project)
        prompt_contents = {}
        eval_contents = {}
        
        # Read prompt files
        for file_path in file_paths["prompt_files"]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompt_contents[file_path] = f.read()
            except Exception as e:
                await interface.show_error(f"Failed to read {file_path}: {e}")
                return
        
        # Read eval files
        for file_path in file_paths["eval_files"]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    eval_contents[file_path] = f.read()
            except Exception as e:
                await interface.show_error(f"Failed to read {file_path}: {e}")
                return
        
        # Step 4: Run the analysis with progress indicators
        await interface.show_progress("🔍 Fetching trace from LangSmith...")
        
        def handle_progress(event_type: str, payload: dict) -> None:
            try:
                log = interface.console.log

                if event_type == "analysis_started":
                    log(f"[blue]Starting analysis for trace {payload.get('trace_id', '')}[/blue]")
                elif event_type == "stage1_planning":
                    mode = "chunked" if payload.get("chunking") else "single-call"
                    log(
                        f"[cyan]Stage 1 planning: {payload.get('total_runs', '?')} runs → {mode}[/cyan]"
                    )
                elif event_type == "vector_store_upload_start":
                    log(
                        f"[cyan]Staging files for vector store ({payload.get('mode', 'unknown')} mode): "
                        f"{payload.get('total_files', 0)} files (batch size {payload.get('batch_size', '?')}).[/cyan]"
                    )
                elif event_type == "vector_store_batch_start":
                    log(
                        f"[white]Uploading batch {payload.get('batch_number')}/{payload.get('total_batches')} "
                        f"to vector store…[/white]"
                    )
                elif event_type == "vector_store_batch_complete":
                    log(
                        f"[green]Uploaded batch {payload.get('batch_number')}/{payload.get('total_batches')} "
                        f"({payload.get('completed_files', 0)} files, {payload.get('duration_seconds', 0)}s).[/green]"
                    )
                elif event_type == "vector_store_batch_failed":
                    log(
                        f"[red]Vector store batch {payload.get('batch_number')} failed ({payload.get('failed_files', 0)} files).[/red]"
                    )
                elif event_type == "vector_store_upload_complete":
                    log(
                        f"[green]Vector store staging complete in {payload.get('duration_seconds', 0)}s.[/green]"
                    )
                elif event_type == "stage1_chunked_enqueued":
                    log(
                        f"[cyan]Stage 1 chunked: {payload.get('total_groups')} groups, group size {payload.get('group_size')}[/cyan]"
                    )
                elif event_type == "stage1_single_call_enqueued":
                    log("[cyan]Stage 1 single-call mode queued.[/cyan]")
                elif event_type == "stage1_group_start":
                    log(
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
                    log(
                        f"[yellow]Stage 1 chunk {payload.get('group_index')} retrying in {payload.get('backoff_seconds')}s "
                        f"(attempt {next_attempt}/{max_attempts})"
                        + (f" – {error_summary}" if error_summary else "")
                        + "[/yellow]"
                    )
                elif event_type == "stage1_group_rate_limited":
                    log(
                        f"[yellow]Stage 1 chunk {payload.get('group_index')} waiting {payload.get('wait_seconds')}s for TPM[/yellow]"
                    )
                elif event_type == "stage1_group_complete":
                    log(
                        f"[green]Stage 1 chunk {payload.get('group_index')} completed (attempts: {payload.get('attempts')})[/green]"
                    )
                elif event_type == "stage1_group_failed":
                    log(
                        f"[red]Stage 1 chunk {payload.get('group_index')} exhausted retries; continuing with placeholders ({payload.get('error')})[/red]"
                    )
                elif event_type == "stage1_group_connection_failed":
                    log(
                        f"[red]Stage 1 chunk {payload.get('group_index')} hit repeated connection failures: {payload.get('error', '')[:160]}[/red]"
                    )
                elif event_type == "stage1_group_sleep":
                    log(
                        f"[white]Stage 1 pausing {payload.get('sleep_seconds')}s before next chunk (completed {payload.get('completed_groups')} groups).[/white]"
                    )
                elif event_type == "stage1_chunked_complete":
                    log(
                        f"[green]Stage 1 chunked run complete ({payload.get('merged_timeline_items', 0)} timeline items).[/green]"
                    )
                elif event_type == "stage1_interactive_complete":
                    log(
                        f"[green]Stage 1 completed with {payload.get('timeline_items', 0)} timeline items.[/green]"
                    )
                elif event_type == "stage2_start":
                    log("[cyan]Stage 2 (Gap Analysis) started.[/cyan]")
                elif event_type == "stage2_retry":
                    stage2_error = payload.get("error")
                    note = ""
                    if stage2_error:
                        stage2_error = stage2_error.strip()
                        if len(stage2_error) > 120:
                            stage2_error = stage2_error[:117] + "..."
                        note = f" – {stage2_error}"
                    log(
                        f"[yellow]Stage 2 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage2_failed":
                    log(
                        f"[red]Stage 2 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage2_complete":
                    log("[green]Stage 2 complete.[/green]")
                elif event_type == "stage3_start":
                    log("[cyan]Stage 3 (Diagnosis) started.[/cyan]")
                elif event_type == "stage3_retry":
                    stage3_error = payload.get("error")
                    note = ""
                    if stage3_error:
                        stage3_error = stage3_error.strip()
                        if len(stage3_error) > 120:
                            stage3_error = stage3_error[:117] + "..."
                        note = f" – {stage3_error}"
                    log(
                        f"[yellow]Stage 3 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage3_failed":
                    log(
                        f"[red]Stage 3 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage3_complete":
                    log(
                        f"[green]Stage 3 complete – root cause: {payload.get('root_cause', 'n/a')}[/green]"
                    )
                elif event_type == "stage4_start":
                    log("[cyan]Stage 4 (Synthesis) started.[/cyan]")
                elif event_type == "stage4_retry":
                    stage4_error = payload.get("error")
                    note = ""
                    if stage4_error:
                        stage4_error = stage4_error.strip()
                        if len(stage4_error) > 120:
                            stage4_error = stage4_error[:117] + "..."
                        note = f" – {stage4_error}"
                    log(
                        f"[yellow]Stage 4 retrying in {payload.get('backoff_seconds')}s (attempt {payload.get('attempt') + 1}).{note}[/yellow]"
                    )
                elif event_type == "stage4_failed":
                    log(
                        f"[red]Stage 4 failed: {payload.get('error')}[/red]"
                    )
                elif event_type == "stage4_complete":
                    log("[green]Stage 4 complete. Preparing final summary...[/green]")
                elif event_type == "analysis_completed":
                    log(
                        f"[green]Analysis finished – failure type: {payload.get('failure_type', 'unknown')}[/green]"
                    )
                elif event_type == "hypothesis_best_practices_start":
                    log("[cyan]Hypothesis: fetching best practices...[/cyan]")
                elif event_type == "hypothesis_best_practices_complete":
                    log(
                        f"[green]Hypothesis best practices ready ({payload.get('count', 0)} matches, {payload.get('elapsed_s', 0)}s).[/green]"
                    )
                elif event_type == "hypothesis_generation_start":
                    log(
                        f"[cyan]Hypothesis generation ({payload.get('stage', 'unknown')}) started.[/cyan]"
                    )
                elif event_type == "hypothesis_generation_chunk_progress":
                    log(
                        f"[white]Hypothesis generation progress ({payload.get('stage', 'unknown')}): {int(payload.get('progress', 0)*100)}%.[/white]"
                    )
                elif event_type == "hypothesis_generation_complete":
                    log(
                        f"[green]Hypothesis generation ({payload.get('stage', 'unknown')}) complete – {payload.get('count', 0)} candidates in {payload.get('elapsed_s', 0)}s.[/green]"
                    )
                elif event_type == "hypothesis_rank_start":
                    log("[cyan]Ranking hypotheses...[/cyan]")
                elif event_type == "hypothesis_rank_complete":
                    log(
                        f"[green]Hypothesis ranking complete ({payload.get('elapsed_s', 0)}s).[/green]"
                    )
                elif event_type == "hypothesis_failed":
                    log(
                        f"[red]Hypothesis stage failed ({payload.get('stage', 'unknown')}): {payload.get('error', 'unknown error')}[/red]"
                    )
            except Exception:
                if config.debug:
                    interface.console.log(f"[red]Progress callback error for {event_type}[/red]")

        orchestrator = await create_orchestrator(codebase_abs, progress_callback=handle_progress)
        
        await interface.show_progress("📊 Analyzing trace execution flow... (this may take a minute)")
        
        # Use Rich status spinner during the long analysis operation
        with interface.console.status("[bold blue]🔬 Analyzing trace data...[/bold blue]", spinner="dots"):
            complete_analysis = await orchestrator.analyze_failure(
                trace_id=trace_id,
                project=project,
                expected_behavior=expected_behavior,
                prompt_contents=prompt_contents,
                eval_contents=eval_contents
            )
        
        # Step 5: Show comprehensive results
        await interface.show_complete_analysis(complete_analysis)
        
        # Step 6: Offer hypothesis generation
        if await interface.ask_yes_no("Generate improved prompts using GPT-5?"):
            await interface.show_progress("🤖 Generating improved prompts...")
            
            try:
                # Get the trace for prompt extraction
                trace = await orchestrator.ensure_trace(trace_id)
                
                # Generate hypothesis with rewritten prompts
                hypotheses = await orchestrator.generate_hypotheses_from_trace(
                    diagnosis=complete_analysis.diagnosis,
                    trace=trace,
                    max_hypotheses=1  # One good hypothesis for now
                )
                
                if hypotheses:
                    hypothesis = hypotheses[0]
                    
                    # Show before/after comparison
                    await interface.show_hypothesis_comparison(hypothesis)
                    
                    # Save to customer experiment system
                    from ..experiments.customer_experiment_manager import CustomerExperimentManager
                    experiment_manager = CustomerExperimentManager(codebase_abs)
                    version_id = experiment_manager.save_version(hypothesis)
                    
                    await interface.show_success(
                        f"💾 Saved as experiment version: {version_id}\n"
                        f"   Test with: refinery test {version_id}"
                    )
                else:
                    await interface.show_error("Failed to generate hypothesis. Please try again.")
                    
            except Exception as e:
                await interface.show_error(f"Error generating hypothesis: {e}")
        else:
            await interface.show_success(
                "Analysis complete! Use 'refinery analyze --apply' with this trace ID if you want to generate and apply fixes later."
            )
    
    except Exception as e:
        await interface.show_error(f"An error occurred: {e}")
        raise  # Re-raise for debugging if needed
