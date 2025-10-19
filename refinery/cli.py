"""Command-line interface for Refinery."""

import asyncio
import os
import sys

import click
from rich.console import Console

from .utils.config import config

console = Console()


def print_version(ctx, param, value):
    if value:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        console.print(f"Refinery v0.1.0 (GPT-5, Python {python_version})")
        ctx.exit()


@click.group()
@click.option("--debug/--no-debug", default=False, help="Enable debug mode")
@click.option("--config-file", help="Path to configuration file")
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show version and exit",
)
def main(debug: bool, config_file: str):
    """Refinery - AI-powered prompt analysis for LangSmith traces."""
    if debug:
        config.debug = True
        config.log_level = "DEBUG"

    # Config validation is now done lazily in each command based on workflow needs


@main.command()
@click.option("--trace-id", help="LangSmith trace ID to analyze")
@click.option(
    "--project", default="default", help="LangSmith project name (default: default)"
)
@click.option(
    "--trace-file",
    type=click.Path(exists=True),
    help="Local trace JSON file to analyze",
)
@click.option(
    "--prompts",
    help="Path or glob pattern to prompt files (e.g., './prompts/*.txt')",
)
@click.option(
    "--evals",
    help="Path or glob pattern to eval/test files (e.g., './tests/*.py')",
)
@click.option(
    "--expected-behavior",
    help="Description of expected agent behavior",
)
@click.option(
    "--out", type=click.Path(), help="Output file for hypothesis pack (YAML/JSON)"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format (default: yaml)",
)
@click.option(
    "--codebase", default=".", help="Path to codebase (default: current directory)"
)
def chat(
    trace_id: str,
    project: str,
    trace_file: str,
    prompts: str,
    evals: str,
    expected_behavior: str,
    out: str,
    output_format: str,
    codebase: str,
):
    """Interactive chat mode for analyzing AI agent failures."""

    async def run_chat():
        # Import here to avoid circular imports
        from .integrations.trace_sources import LangSmithAPISource, LocalFileSource
        from .interfaces.chat_interface import ChatInterface
        from .interfaces.chat_session import run_chat_session
        from .utils.file_helpers import load_files_from_path

        # Validate: must provide one trace source
        if not trace_id and not trace_file:
            console.print(
                "[red]Error: Must provide either --trace-id or --trace-file[/red]"
            )
            console.print("\n[bold]Choose your workflow:[/bold]")
            console.print("\n[cyan]1. LangSmith (native integration):[/cyan]")
            console.print("   refinery chat --trace-id abc123 --project my-project")
            console.print("   [dim]Requires: LANGSMITH_API_KEY and OPENAI_API_KEY[/dim]")
            console.print("\n[cyan]2. Local JSON file (any trace format):[/cyan]")
            console.print("   refinery chat --trace-file trace.json --prompts ./prompts/ --evals ./tests/")
            console.print("   [dim]Requires: OPENAI_API_KEY only[/dim]")
            console.print("   [dim]Supports: LangSmith, OpenTelemetry, Langfuse, custom JSON[/dim]")
            sys.exit(1)

        if trace_id and trace_file:
            console.print(
                "[red]Error: Cannot provide both --trace-id and --trace-file[/red]"
            )
            sys.exit(1)

        # Warn if using trace file without explicit prompts/evals
        if trace_file and not prompts:
            console.print(
                "[yellow]Warning: No --prompts provided. Analysis may be limited without prompt context.[/yellow]"
            )

        if trace_file and not evals:
            console.print(
                "[yellow]Warning: No --evals provided. Analysis will proceed without eval context.[/yellow]"
            )

        # Lazy validation based on workflow
        try:
            if trace_id:
                # LangSmith API workflow: need both LangSmith and OpenAI keys
                config.validate_langsmith()
                config.validate_openai()
                trace_source = LangSmithAPISource(trace_id, project)
            else:
                # Local file workflow: only need OpenAI key
                config.validate_openai()
                trace_source = LocalFileSource(trace_file)
        except ValueError as e:
            console.print(f"[red]Configuration error: {e}[/red]")
            sys.exit(1)

        # Implement full analysis workflow
        console.print(
            f"[blue]Starting analysis of trace from {trace_file if trace_file else f'LangSmith trace ID {trace_id}'}...[/blue]"
        )
        console.print("")

        try:
            import time
            start_time = time.time()

            # 1. Fetch trace from source
            console.print("[cyan]Step 1/4: Fetching trace...[/cyan]")
            trace = await trace_source.fetch_trace()
            console.print(
                f"[green]✓ Loaded trace {trace.trace_id} ({len(trace.runs)} runs)[/green]"
            )

            # 2. Create orchestrator with progress callback
            console.print("[cyan]Step 2/4: Running failure analysis...[/cyan]")

            def progress_callback(event_type: str, payload: dict):
                """Simple progress callback for CLI."""
                if event_type in ["stage1_interactive_complete", "stage2_complete", "stage3_complete", "stage4_complete"]:
                    console.print(f"  [dim]{event_type}: {payload}[/dim]")

            from .core.orchestrator import create_orchestrator

            orchestrator = await create_orchestrator(
                codebase, progress_callback=progress_callback
            )

            # Inject trace into orchestrator's cache to bypass LangSmith fetch
            orchestrator._trace_cache[trace.trace_id] = trace

            # Load prompts and evals if provided
            prompt_contents = None
            eval_contents = None

            if prompts:
                console.print(f"[cyan]Loading prompts from: {prompts}[/cyan]")
                prompt_contents = load_files_from_path(prompts)
                console.print(f"[green]✓ Loaded {len(prompt_contents)} prompt file(s)[/green]")

            if evals:
                console.print(f"[cyan]Loading evals from: {evals}[/cyan]")
                eval_contents = load_files_from_path(evals)
                console.print(f"[green]✓ Loaded {len(eval_contents)} eval file(s)[/green]")

            # Define expected behavior (use user-provided or fallback to demo)
            if expected_behavior:
                expected_behavior_text = expected_behavior
            else:
                expected_behavior_text = (
                    "Agent should correctly classify billing/subscription queries and route to appropriate handlers, "
                    "providing accurate responses about cancellations and refunds."
                )

            # Run analysis (orchestrator finds trace in cache)
            with console.status(
                "[bold blue]Analyzing trace...[/bold blue]", spinner="dots"
            ):
                complete_analysis = await orchestrator.analyze_failure(
                    trace_id=trace.trace_id,
                    project=trace.project_name,
                    expected_behavior=expected_behavior_text,
                    prompt_contents=prompt_contents,
                    eval_contents=eval_contents,
                )

            console.print(
                f"[green]✓ Analysis complete: {complete_analysis.diagnosis.failure_type.value}[/green]"
            )
            console.print(
                f"  Root cause: {complete_analysis.diagnosis.root_cause[:100]}..."
            )

            # 3. Generate hypotheses
            console.print("[cyan]Step 3/4: Generating hypotheses...[/cyan]")

            with console.status(
                "[bold blue]Generating fix hypotheses...[/bold blue]", spinner="dots"
            ):
                hypotheses = await orchestrator.generate_hypotheses_from_trace(
                    diagnosis=complete_analysis.diagnosis, trace=trace, max_hypotheses=3
                )

            if hypotheses:
                console.print(f"[green]✓ Generated {len(hypotheses)} hypothesis(es)[/green]")
                for hyp in hypotheses:
                    console.print(
                        f"  - {hyp.id}: {hyp.description} (confidence: {hyp.confidence.value})"
                    )
                    if hyp.example_before:
                        console.print(f"    [dim]Current: {hyp.example_before}[/dim]")
                    if hyp.example_after:
                        console.print(f"    [dim]Expected: {hyp.example_after}[/dim]")
            else:
                console.print("[yellow]⚠ No hypotheses generated[/yellow]")

            # 4. Export hypothesis pack if --out specified
            if out and hypotheses:
                console.print("[cyan]Step 4/4: Exporting hypothesis pack...[/cyan]")

                from .schemas.hypothesis_pack_v1 import create_hypothesis_pack

                analysis_time_ms = int((time.time() - start_time) * 1000)

                pack = create_hypothesis_pack(
                    trace_id=trace.trace_id,
                    project=trace.project_name,
                    diagnosis=complete_analysis.diagnosis,
                    hypotheses_list=hypotheses,
                    refinery_version="0.1.0",
                    analysis_model=getattr(config, "analysis_model", "gpt-5-preview"),
                    hypothesis_model=getattr(
                        config, "hypothesis_model", "gpt-5-preview"
                    ),
                    total_analysis_time_ms=analysis_time_ms,
                )

                # Export to file
                content = pack.to_yaml() if output_format == "yaml" else pack.to_json()

                with open(out, "w") as f:
                    f.write(content)

                console.print(
                    f"[green]✓ Hypothesis pack exported to {out} ({output_format.upper()})[/green]"
                )
            elif out and not hypotheses:
                console.print(
                    "[yellow]⚠ No hypotheses to export (--out ignored)[/yellow]"
                )
            else:
                console.print("[dim]Step 4/4: No output file specified (--out)[/dim]")

            console.print("")
            console.print(
                f"[green bold]✓ Analysis complete in {time.time() - start_time:.1f}s[/green bold]"
            )

        except Exception as e:
            console.print(f"[red]Error during analysis: {e}[/red]")
            if config.debug:
                import traceback

                console.print("[red]" + traceback.format_exc() + "[/red]")
            sys.exit(1)

    asyncio.run(run_chat())


@main.command()
@click.option("--trace-id", help="LangSmith trace ID to analyze")
@click.option(
    "--project", default="default", help="LangSmith project name (default: default)"
)
@click.option(
    "--trace-file",
    type=click.Path(exists=True),
    help="Local trace JSON file to analyze",
)
@click.option(
    "--prompts",
    help="Path or glob pattern to prompt files (e.g., './prompts/*.txt')",
)
@click.option(
    "--evals",
    help="Path or glob pattern to eval/test files (e.g., './tests/*.py')",
)
@click.option(
    "--expected-behavior",
    help="Description of expected agent behavior",
)
@click.option(
    "--out", type=click.Path(), help="Output file for hypothesis pack (YAML/JSON)"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format (default: yaml)",
)
@click.option(
    "--codebase", default=".", help="Path to codebase (default: current directory)"
)
def analyze(
    trace_id: str,
    project: str,
    trace_file: str,
    prompts: str,
    evals: str,
    expected_behavior: str,
    out: str,
    output_format: str,
    codebase: str,
):
    """Alias for 'chat' - analyze AI agent failures."""
    # Delegate to chat command
    chat.callback(trace_id, project, trace_file, prompts, evals, expected_behavior, out, output_format, codebase)


@main.command()
def ui():
    """Launch Streamlit UI."""
    import subprocess
    import sys
    from pathlib import Path

    # Set environment to skip Streamlit welcome screen
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    console.print("[blue]🔬 Launching Refinery Web UI...[/blue]")
    console.print("[dim]Starting server and opening browser...[/dim]")

    ui_path = Path(__file__).parent / "ui" / "app.py"

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ui_path),
                "--server.headless=false",
                "--browser.gatherUsageStats=false",
                "--global.showWarningOnDirectExecution=false",
            ],
            env=env,
        )
    except KeyboardInterrupt:
        console.print("[yellow]UI server stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error launching UI: {e}[/red]")
        console.print(
            "[blue]Try running manually: streamlit run refinery/ui/app.py[/blue]"
        )


if __name__ == "__main__":
    main()
