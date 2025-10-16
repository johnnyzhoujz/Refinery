#!/usr/bin/env python3
"""
Demonstration of the Refinery Chat Interface

This script shows:
1. How the current simple CLI chat interface works
2. How easy it is to replace with other interfaces later
3. Example of what future interfaces might look like
"""

import asyncio
import sys
from pathlib import Path

# Add the refinery module to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from refinery.core.models import Confidence, Diagnosis, FailureType
from refinery.interfaces.chat_interface import BaseChatInterface


class MockNLInterface(BaseChatInterface):
    """Example of what a future Natural Language Interface might look like."""

    def __init__(self):
        self.conversation_history = []

    async def get_trace_id(self) -> str:
        # In real NL interface, this would parse natural language like:
        # "The trace abc123 failed" → extract "abc123"
        print("🤖 I can help you analyze AI agent failures!")
        print("🤖 What trace would you like me to look at?")
        input("You: ")
        # Mock NL parsing
        return "60b467c0-b9db-4ee4-934a-ad23a15bd8cd"  # Would extract from user_input

    async def get_expected_behavior(self) -> str:
        print("🤖 What should have happened instead?")
        input("You: ")
        # Mock NL understanding
        return "Agent should acknowledge memory limitations"  # Would process user_input

    async def get_project_name(self, default: str = "default") -> str:
        return "customer-service"  # Would infer from context

    async def confirm_action(self, message: str) -> bool:
        print(f"🤖 {message}")
        response = input("You: ").lower()
        return response in ["yes", "y", "sure", "ok", "apply it", "do it"]

    async def show_welcome(self):
        print("\n🤖 Hello! I'm your AI agent debugging assistant.")
        print("🤖 Just describe the problem in natural language and I'll help fix it.")

    async def show_analysis_progress(self):
        print("🤖 Let me analyze that trace for you...")

    async def show_diagnosis(self, diagnosis):
        print(f"\n🤖 I found the issue! {diagnosis.root_cause}")
        print(
            f"🤖 This looks like a {diagnosis.failure_type.value.replace('_', ' ')} problem."
        )
        print(f"🤖 I'm {diagnosis.confidence.value} confident about this diagnosis.")

    async def show_success(self, message: str):
        print(f"🤖 ✅ {message}")

    async def show_error(self, message: str):
        print(f"🤖 ❌ {message}")


def demo_current_interface():
    """Demonstrate the current simple CLI interface."""
    print("=" * 60)
    print("DEMO 1: Current Simple CLI Chat Interface")
    print("=" * 60)
    print("This is what users get today:")
    print("- Simple prompts for trace ID and expected behavior")
    print("- Rich console output with panels and formatting")
    print("- Uses existing Refinery analysis logic")
    print()
    print("To try it live, run:")
    print("  refinery chat --project demo")
    print()


def demo_future_interfaces():
    """Show how interfaces can be easily replaced."""
    print("=" * 60)
    print("DEMO 2: Future Interface Replacement")
    print("=" * 60)
    print("How easy it is to upgrade:")
    print()

    print("Current:")
    print("  interface = ChatInterface()  # Simple CLI prompts")
    print()

    print("Future - Natural Language:")
    print("  interface = NLInterface(llm_provider=create_llm_provider())")
    print("  # Users can say: 'trace abc123 failed because bot claimed memory'")
    print()

    print("Future - Web Interface:")
    print("  interface = StreamlitInterface(port=8501)")
    print("  # Rich web UI with forms, file uploads, visual results")
    print()

    print("Future - API Interface:")
    print("  interface = FastAPIInterface()")
    print("  # RESTful endpoints for integration with other tools")
    print()

    print("The core chat_session.py logic stays exactly the same!")


async def demo_mock_nl_interface():
    """Demo what a natural language interface might feel like."""
    print("=" * 60)
    print("DEMO 3: Mock Natural Language Interface")
    print("=" * 60)
    print("Simulating what a future NL interface might look like:")
    print("(This is just a demo - it doesn't actually analyze traces)")
    print()

    # Create mock interface
    interface = MockNLInterface()

    # Mock a simple interaction
    await interface.show_welcome()
    await interface.get_trace_id()
    await interface.get_expected_behavior()

    # Mock diagnosis
    mock_diagnosis = Diagnosis(
        failure_type=FailureType.CONTEXT_ISSUE,
        root_cause="Missing memory limitation instructions in prompts",
        confidence=Confidence.HIGH,
        evidence=["Agent claimed memory capabilities", "No memory disclaimers found"],
        detailed_analysis="The system prompts lack explicit instructions about memory limitations.",
        affected_components=["system_prompt", "user_interaction"],
    )

    await interface.show_diagnosis(mock_diagnosis)

    if await interface.confirm_action("Should I apply a fix?"):
        await interface.show_success(
            "Fix applied! Added memory limitation instructions to system prompt."
        )

    print("\n" + "=" * 60)
    print("End of NL interface demo")


def main():
    """Run all demos."""
    print("🚀 Refinery Chat Interface Demos")
    print("This shows the current implementation and future possibilities.")
    print()

    demo_current_interface()
    demo_future_interfaces()

    print()
    print("Would you like to see a mock natural language interface demo? (y/n)")
    if input().lower().startswith("y"):
        asyncio.run(demo_mock_nl_interface())

    print("\n🎯 Key Takeaways:")
    print("1. Current interface: Simple but functional - ready to ship")
    print("2. Future upgrades: Just swap the interface class")
    print("3. Core logic: Reusable across all interface types")
    print("4. Easy evolution: Add features without breaking changes")


if __name__ == "__main__":
    main()
