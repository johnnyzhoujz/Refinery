#!/usr/bin/env python3
"""Development setup script for Refinery."""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error: {result.stderr}")
            return False
        print(f"✅ {description} completed")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Set up development environment."""
    print("🚀 Setting up Refinery development environment...\n")
    
    # Install in editable mode
    if not run_command("pip install -e .", "Installing Refinery in editable mode"):
        return False
    
    # Install development dependencies
    if not run_command("pip install pytest pytest-asyncio black ruff mypy", "Installing dev dependencies"):
        return False
    
    # Check if .env exists
    if not os.path.exists('.env'):
        print("\n📝 Creating .env file from template...")
        if os.path.exists('.env.example'):
            run_command("cp .env.example .env", "Copying .env template")
            print("✅ Please edit .env with your API keys")
        else:
            print("❌ .env.example not found")
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env with your LangSmith and OpenAI/Anthropic API keys")
    print("2. Test configuration: refinery config-check")
    print("3. Analyze a trace: refinery analyze <trace_id> --project <project> --expected 'description'")
    print("4. Generate fixes: refinery fix <trace_id> --project <project> --expected 'description'")
    
    # Test basic import
    try:
        import refinery
        print(f"\n✅ Refinery {refinery.__version__} successfully installed")
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)