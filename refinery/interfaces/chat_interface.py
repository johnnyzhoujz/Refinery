"""
Base chat interface for interacting with Refinery.

This provides the foundation for different interaction modes:
- Simple CLI prompts (current implementation)
- Future: Natural language understanding
- Future: Web-based UI
"""

from abc import ABC, abstractmethod
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from ..core.models import Diagnosis, CompleteAnalysis, TraceAnalysis, GapAnalysis


class BaseChatInterface(ABC):
    """Abstract base class for chat interfaces - easily replaceable."""
    
    @abstractmethod
    async def get_trace_id(self) -> str:
        """Get trace ID from user input."""
        pass
    
    @abstractmethod
    async def get_expected_behavior(self) -> str:
        """Get expected behavior description from user."""
        pass
    
    @abstractmethod
    async def get_project_name(self, default: str = "default") -> str:
        """Get project name from user."""
        pass
    
    @abstractmethod
    async def confirm_action(self, message: str) -> bool:
        """Ask user to confirm an action."""
        pass
    
    @abstractmethod
    async def show_welcome(self):
        """Display welcome message."""
        pass
    
    @abstractmethod
    async def show_progress(self, message: str):
        """Show progress with specific message."""
        pass
    
    @abstractmethod
    async def show_complete_analysis(self, analysis: CompleteAnalysis):
        """Display all analysis results (trace, gap, diagnosis)."""
        pass
    
    @abstractmethod
    async def show_trace_analysis(self, trace_analysis: TraceAnalysis):
        """Display trace analysis results."""
        pass
    
    @abstractmethod
    async def show_gap_analysis(self, gap_analysis: GapAnalysis):
        """Display gap analysis results."""
        pass
    
    @abstractmethod
    async def show_diagnosis(self, diagnosis: Diagnosis):
        """Display diagnosis results."""
        pass
    
    @abstractmethod
    async def show_recommendations(self, diagnosis: Diagnosis):
        """Display actionable recommendations."""
        pass
    
    @abstractmethod
    async def show_success(self, message: str):
        """Display success message."""
        pass
    
    @abstractmethod
    async def show_error(self, message: str):
        """Display error message."""
        pass


class ChatInterface(BaseChatInterface):
    """Simple CLI-based chat interface using Rich console."""
    
    def __init__(self):
        self.console = Console()
    
    async def get_trace_id(self) -> str:
        """Get trace ID from user via CLI prompt."""
        self.console.print()
        return self.console.input("[bold cyan]What's the trace ID?[/bold cyan] ")
    
    async def get_expected_behavior(self) -> str:
        """Get expected behavior from user via CLI prompt."""
        return self.console.input("[bold cyan]What should have happened?[/bold cyan] ")
    
    async def get_project_name(self, default: str = "default") -> str:
        """Get project name from user via CLI prompt."""
        project = self.console.input(f"[bold cyan]Project name[/bold cyan] (default: {default}): ").strip()
        return project if project else default
    
    async def confirm_action(self, message: str) -> bool:
        """Ask user to confirm an action via CLI prompt."""
        response = self.console.input(f"[bold yellow]{message}[/bold yellow] (y/n): ").strip().lower()
        return response in ['y', 'yes']
    
    async def show_welcome(self):
        """Display welcome message with Rich formatting."""
        welcome_text = """
# 🤖 Refinery Agent

Hi! I'll help you analyze and fix AI agent failures.

I'll need:
1. **Trace ID** - The ID of the failed execution
2. **Expected Behavior** - What should have happened instead

Let's get started!
        """.strip()
        
        self.console.print(Panel(
            Markdown(welcome_text),
            title="Welcome",
            border_style="cyan"
        ))
    
    async def show_progress(self, message: str):
        """Show progress with specific message."""
        self.console.print(f"\n[yellow]{message}[/yellow]")
    
    async def show_diagnosis(self, diagnosis: Diagnosis):
        """Display diagnosis results with Rich formatting."""
        diagnosis_text = "## 💡 Root Cause Diagnosis\n\n"
        
        diagnosis_text += f"**Failure Type:** {diagnosis.failure_type.value.replace('_', ' ').title()}\n\n"
        diagnosis_text += f"**Confidence:** {diagnosis.confidence.value.upper()}\n\n"
        diagnosis_text += f"**Root Cause:**\n{diagnosis.root_cause}\n\n"
        
        if diagnosis.evidence:
            diagnosis_text += "**Evidence:**\n"
            for evidence in diagnosis.evidence[:3]:  # Show top 3 pieces of evidence
                diagnosis_text += f"• {evidence}\n"
        
        if diagnosis.affected_components:
            diagnosis_text += f"\n**Affected Components:** {', '.join(diagnosis.affected_components)}\n"
        
        if diagnosis.detailed_analysis:
            analysis_preview = diagnosis.detailed_analysis[:200] + "..." if len(diagnosis.detailed_analysis) > 200 else diagnosis.detailed_analysis
            diagnosis_text += f"\n**Detailed Analysis:**\n{analysis_preview}\n"
        
        self.console.print(Panel(
            Markdown(diagnosis_text.strip()),
            title="Root Cause Diagnosis",
            border_style="green"
        ))
    
    async def show_success(self, message: str):
        """Display success message."""
        self.console.print(f"\n[bold green]✅ {message}[/bold green]")
    
    async def show_complete_analysis(self, analysis: CompleteAnalysis):
        """Display all analysis results with Rich formatting."""
        self.console.print()
        
        # Show trace analysis
        await self.show_trace_analysis(analysis.trace_analysis)
        
        # Show gap analysis  
        await self.show_gap_analysis(analysis.gap_analysis)
        
        # Show diagnosis
        await self.show_diagnosis(analysis.diagnosis)
        
        # Show recommendations if available
        await self.show_recommendations(analysis.diagnosis)
    
    async def show_trace_analysis(self, trace_analysis: TraceAnalysis):
        """Display trace analysis results."""
        trace_text = "## 🔍 Trace Analysis\n\n"
        
        if trace_analysis.execution_flow:
            trace_text += "**Execution Flow:**\n"
            
            # Handle both string and list formats
            if isinstance(trace_analysis.execution_flow, str):
                trace_text += f"• {trace_analysis.execution_flow}\n"
            elif isinstance(trace_analysis.execution_flow, list):
                for i, step in enumerate(trace_analysis.execution_flow[:5], 1):  # Show first 5 steps
                    if isinstance(step, dict):
                        step_desc = step.get('description', str(step))[:100]
                    else:
                        step_desc = str(step)[:100]
                    trace_text += f"• Step {i}: {step_desc}\n"
                if len(trace_analysis.execution_flow) > 5:
                    trace_text += f"• ... and {len(trace_analysis.execution_flow) - 5} more steps\n"
        
        if trace_analysis.identified_issues:
            trace_text += "\n**Issues Identified:**\n"
            
            # Handle both string and list formats
            if isinstance(trace_analysis.identified_issues, str):
                trace_text += f"• {trace_analysis.identified_issues}\n"
            elif isinstance(trace_analysis.identified_issues, list):
                for issue in trace_analysis.identified_issues[:3]:  # Show top 3 issues
                    if isinstance(issue, dict):
                        issue_desc = issue.get('description', str(issue))[:100]
                    else:
                        issue_desc = str(issue)[:100]
                    trace_text += f"• {issue_desc}\n"
        
        self.console.print(Panel(
            Markdown(trace_text.strip()),
            title="Trace Analysis",
            border_style="blue"
        ))
    
    async def show_gap_analysis(self, gap_analysis: GapAnalysis):
        """Display gap analysis results."""
        gap_text = "## 🎯 Gap Analysis\n\n"
        
        if gap_analysis.behavioral_differences:
            gap_text += "**Behavioral Differences:**\n"
            for diff in gap_analysis.behavioral_differences[:3]:
                gap_text += f"• {diff}\n"
        
        if gap_analysis.missing_context:
            gap_text += "\n**Missing Context:**\n"
            for context in gap_analysis.missing_context[:3]:
                gap_text += f"• {context}\n"
        
        if gap_analysis.incorrect_assumptions:
            gap_text += "\n**Incorrect Assumptions:**\n"
            for assumption in gap_analysis.incorrect_assumptions[:3]:
                gap_text += f"• {assumption}\n"
        
        self.console.print(Panel(
            Markdown(gap_text.strip()),
            title="Gap Analysis",
            border_style="magenta"
        ))
    
    async def show_recommendations(self, diagnosis: Diagnosis):
        """Display actionable recommendations."""
        recommendations_text = ""
        
        # Show remediations from Stage 3
        if diagnosis.remediations:
            recommendations_text += "## 🛠️ Recommended Fixes\n\n"
            for remediation in diagnosis.remediations[:5]:  # Show top 5 remediations
                action = remediation.get("action", "Unknown action")
                priority = remediation.get("priority", "medium").upper()
                effort = remediation.get("effort_estimate", "unknown")
                impact = remediation.get("expected_impact", "")
                
                recommendations_text += f"**Priority: {priority}** | **Effort: {effort.title()}**\n"
                recommendations_text += f"• {action}\n"
                if impact:
                    recommendations_text += f"  *Expected impact: {impact}*\n"
                recommendations_text += "\n"
        
        # Show next actions from Stage 4 (filter out owner/timeline as requested)
        if diagnosis.next_actions:
            if recommendations_text:
                recommendations_text += "\n"
            recommendations_text += "## 🎯 Next Actions\n\n"
            for action_item in diagnosis.next_actions[:5]:  # Show top 5 next actions
                action = action_item.get("action", "Unknown action")
                priority = action_item.get("priority", "medium").upper()
                success_criteria = action_item.get("success_criteria", "")
                
                recommendations_text += f"**Priority: {priority}**\n"
                recommendations_text += f"• {action}\n"
                if success_criteria:
                    recommendations_text += f"  *Success criteria: {success_criteria}*\n"
                recommendations_text += "\n"
        
        # Show top findings
        if diagnosis.top_findings:
            if recommendations_text:
                recommendations_text += "\n"
            recommendations_text += "## 💡 Key Findings\n\n"
            for finding in diagnosis.top_findings[:3]:  # Show top 3 findings
                finding_text = finding.get("finding", "Unknown finding")
                confidence = finding.get("confidence", "medium")
                
                recommendations_text += f"• {finding_text} *(Confidence: {confidence})*\n"
        
        if recommendations_text:
            self.console.print(Panel(
                Markdown(recommendations_text.strip()),
                title="Actionable Recommendations",
                border_style="yellow"
            ))
    
    async def show_error(self, message: str):
        """Display error message."""
        self.console.print(f"\n[bold red]❌ {message}[/bold red]")