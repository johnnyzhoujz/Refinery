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
        
        orchestrator = await create_orchestrator(codebase_abs)
        
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
                trace = await orchestrator.langsmith_client.get_trace(trace_id)
                
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