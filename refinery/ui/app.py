import streamlit as st
import os
import asyncio
import time
from pathlib import Path
from refinery.core.orchestrator import create_orchestrator
from refinery.core.context import RefineryContext
from refinery.experiments.customer_experiment_manager import CustomerExperimentManager
from refinery.agents.hypothesis_generator import AdvancedHypothesisGenerator
from refinery.ui.utils import run_async, load_context_json, load_project_context_for_trace

st.set_page_config(page_title="Refinery Trace Analysis", page_icon="🔬")
st.title("🔬 Refinery Trace Analysis")

# Initialize cached managers (P0 CRITICAL)
if "orchestrator" not in st.session_state:
    try:
        st.session_state.orchestrator = run_async(create_orchestrator(os.getcwd()))
    except Exception as e:
        st.error(f"Failed to initialize orchestrator: {e}")
        st.stop()

if "experiment_manager" not in st.session_state:
    # Use CustomerExperimentManager for customer versions (P0 CRITICAL)
    st.session_state.experiment_manager = CustomerExperimentManager(Path(os.getcwd()))

if "hypothesis_generator" not in st.session_state:
    # Create hypothesis generator for trace-based generation
    st.session_state.hypothesis_generator = AdvancedHypothesisGenerator()

# Initialize conversation state
if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = "welcome"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_trace_id" not in st.session_state:
    st.session_state.user_trace_id = None
if "user_expected_behavior" not in st.session_state:
    st.session_state.user_expected_behavior = None

# Load context.json if available
context_data = load_context_json()

# Show welcome message on first load
if st.session_state.conversation_state == "welcome" and not st.session_state.messages:
    welcome_msg = """Hi! I'll help you analyze and fix AI agent failures.

I'll need:
1. **Trace ID** - The ID of the failed execution
2. **Expected Behavior** - What should have happened instead

Let's get started!"""
    
    st.session_state.messages.append({"role": "assistant", "content": welcome_msg})
    st.session_state.conversation_state = "waiting_for_trace"

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Dynamic chat input based on conversation state
if st.session_state.conversation_state == "waiting_for_trace":
    input_placeholder = "What's the trace ID?"
elif st.session_state.conversation_state == "waiting_for_expected":
    input_placeholder = "What should have happened instead?"
else:
    input_placeholder = "Enter your message..."

# Handle user input based on conversation state
if prompt := st.chat_input(input_placeholder):
    
    if st.session_state.conversation_state == "waiting_for_trace":
        # Store trace ID and ask for expected behavior
        st.session_state.user_trace_id = prompt.strip()
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"Got trace ID: `{st.session_state.user_trace_id}`\n\nWhat should have happened instead?"
        })
        st.session_state.conversation_state = "waiting_for_expected"
        st.rerun()
        
    elif st.session_state.conversation_state == "waiting_for_expected":
        # Store expected behavior and run analysis
        st.session_state.user_expected_behavior = prompt.strip()
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.conversation_state = "analyzing"
        st.rerun()  # Display the user's message before starting analysis

# Run analysis when in analyzing state
if st.session_state.conversation_state == "analyzing" and not st.session_state.get("analysis"):
    with st.chat_message("assistant"):
        try:
            # Stream progress messages (separate from results - P0 CRITICAL)
            def progress_stream():
                yield "🔍 Fetching trace from LangSmith...\n"
                time.sleep(1)
                yield "📊 Extracting prompts from trace...\n"
                time.sleep(1)
                yield "🧠 Running failure analysis...\n"
                time.sleep(2)
                yield "✅ Analysis complete!\n"
            
            # Show streaming progress
            st.write_stream(progress_stream)
            
            # Run actual analysis (capture result separately - P0 CRITICAL)
            with st.spinner("Processing..."):
                # First fetch the trace object for hypothesis generation
                trace = run_async(st.session_state.orchestrator.langsmith_client.fetch_trace(st.session_state.user_trace_id))
                
                # Extract and store prompts from trace automatically
                project_name = f"ui-{st.session_state.user_trace_id[:8]}"
                context_manager = RefineryContext(os.getcwd())
                
                # Check if prompts already exist for this trace
                existing_context = context_manager.get_project_context(project_name)
                if not existing_context or not existing_context.get("prompt_files"):
                    # Extract prompts from trace
                    extracted = st.session_state.orchestrator.langsmith_client.extract_prompts_from_trace(trace)
                    # Store extracted prompts as files
                    created_files = context_manager.store_trace_prompts(project_name, extracted, st.session_state.user_trace_id)
                    st.info(f"Extracted {len(created_files['prompt_files'])} prompt files, {len(created_files['eval_files'])} eval files from trace")
                
                # Load the project context with actual prompt/eval contents
                project_context = load_project_context_for_trace(project_name)
                
                result = run_async(
                    st.session_state.orchestrator.analyze_failure(
                        trace_id=st.session_state.user_trace_id,
                        project=project_name,
                        expected_behavior=st.session_state.user_expected_behavior,
                        prompt_contents=project_context.get("prompt_files", {}),
                        eval_contents=project_context.get("eval_files", {})
                    )
                )
            
            # Store results (P0 CRITICAL)
            st.session_state.analysis = result
            st.session_state.trace = trace  # Store trace object for hypothesis generation
            st.session_state.trace_id = st.session_state.user_trace_id
            st.session_state.conversation_state = "complete"
            
            st.success("Analysis complete!")
            
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            if st.button("Retry"):
                st.session_state.conversation_state = "waiting_for_expected"
                st.rerun()

# Display analysis results if available (button placement based on state - P0 CRITICAL)
if st.session_state.get("analysis"):
    st.markdown("---")
    st.markdown("### 📋 Analysis Results")
    
    # JSON-safe rendering (P0 CRITICAL)
    result = st.session_state.analysis
    try:
        if hasattr(result, 'dict'):
            st.json(result.dict())
        elif hasattr(result, '__dict__'):
            st.json(result.__dict__)
        else:
            st.json(str(result))
    except Exception:
        st.text(str(result))
    
    # Hypothesis generation button (rendered based on state - P0 CRITICAL)
    if st.button("🚀 Generate Hypotheses with GPT-5", use_container_width=True):
        with st.chat_message("assistant"):
            try:
                # Stream hypothesis generation
                def hypothesis_stream():
                    import time
                    start_time = time.time()
                    
                    # Count system prompts from extracted data
                    extracted = st.session_state.orchestrator.langsmith_client.extract_prompts_from_trace(st.session_state.trace)
                    num_prompts = len(extracted.get("system_prompts", []))
                    
                    yield f"🔍 Analyzing {num_prompts} system prompts from trace...\n"
                    time.sleep(1)
                    yield f"🤔 GPT-5 reasoning about which prompts need modification...\n"
                    time.sleep(1)
                    yield f"⏱️ Processing (elapsed: {int(time.time() - start_time)}s)...\n"
                    time.sleep(1)
                    yield "📝 Applying 20% length constraint to modifications...\n"
                    time.sleep(1)
                    yield "✅ Hypothesis generation complete!\n"
                
                st.write_stream(hypothesis_stream)
                
                # Generate hypothesis using the working approach from test file
                with st.spinner("Generating..."):
                    hypotheses = run_async(
                        st.session_state.hypothesis_generator.generate_hypotheses(
                            diagnosis=st.session_state.analysis.diagnosis,
                            trace=st.session_state.trace,  # Use the stored trace object
                            code_context=None,
                            best_practices=None
                        )
                    )
                
                if hypotheses:
                    st.session_state.hypothesis = hypotheses[0]
                    st.success("Hypothesis generated!")
                else:
                    st.error("No hypotheses generated.")
                    st.info("💡 This could mean:")
                    st.write("• GPT-5 determined no prompts need modification (all were skipped)")
                    st.write("• Response parsing failed - GPT-5 may have used unexpected format")
                    st.write("• An error occurred during generation - check browser console for details")
                
            except Exception as e:
                st.error(f"Hypothesis generation failed: {str(e)}")
                if st.button("Retry Hypothesis"):
                    st.rerun()

# Display hypothesis if available
if st.session_state.get("hypothesis"):
    st.markdown("---")
    st.markdown("### 💡 Generated Hypothesis")
    
    hypothesis = st.session_state.hypothesis
    
    # Before/after comparison with proper debugging
    col1, col2 = st.columns(2)
    
    # Get the file change details
    change = None
    prompt_name = "Unknown"
    if hypothesis.proposed_changes and len(hypothesis.proposed_changes) > 0:
        change = hypothesis.proposed_changes[0]
        # Extract prompt name from file path (e.g., "prompts/prompt_0.txt" -> "prompt_0")
        prompt_name = Path(change.file_path).stem if change.file_path else "Unknown"
    
    with col1:
        st.markdown(f"**📄 Original: {prompt_name}**")
        original = 'Original not available'
        if change:
            original = change.original_content
            # Debug info
            st.caption(f"Length: {len(original)} chars | Type: {change.change_type.value}")
        st.code(original, language="text")
    
    with col2:
        st.markdown(f"**✨ Improved: {prompt_name}**")
        improved = 'Improved not available'
        if change:
            improved = change.new_content
            # Debug info
            st.caption(f"Length: {len(improved)} chars | File: {change.file_path}")
        st.code(improved, language="text")
    
    # Debug section (can be removed later)
    with st.expander("🐛 Debug Info"):
        if change:
            st.write(f"**File Path:** {change.file_path}")
            st.write(f"**Change Type:** {change.change_type.value}")
            st.write(f"**Description:** {change.description}")
            st.write(f"**Original Length:** {len(change.original_content)} chars")
            st.write(f"**Improved Length:** {len(change.new_content)} chars")
            st.write(f"**First 100 chars of original:** {change.original_content[:100]}...")
            st.write(f"**First 100 chars of improved:** {change.new_content[:100]}...")
        else:
            st.write("No proposed changes found in hypothesis")
    
    # Save to customer version store (P0 CRITICAL - correct system)
    if st.button("💾 Save as Experiment", use_container_width=True):
        try:
            version_id = st.session_state.experiment_manager.save_version(
                changes=[hypothesis],
                tag="streamlit_ui",
                description="Generated via Streamlit UI"
            )
            st.success(f"✅ Saved version: {version_id}")
            
        except Exception as e:
            st.error(f"Failed to save: {str(e)}")

# View saved experiments
st.markdown("---")
if st.button("🧪 View Saved Experiments"):
    try:
        versions = st.session_state.experiment_manager.list_versions()
        
        if versions:
            st.markdown(f"### 📊 {len(versions)} Saved Experiments")
            for version in versions:
                version_id = version.get("version_id", "unknown")
                created_at = version.get("created_at", "unknown")
                
                with st.expander(f"🗂️ Version {version_id[:8]}... - {created_at}"):
                    st.json(version)
        else:
            st.info("No saved experiments yet.")
            
    except Exception as e:
        st.error(f"Failed to load experiments: {str(e)}")

# Reset functionality (P0 CRITICAL)
if st.button("🗑️ Start New Analysis"):
    # Clear everything except cached managers
    keys_to_clear = ["messages", "analysis", "hypothesis", "trace_id", "trace", "conversation_state", "user_trace_id", "user_expected_behavior"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# Sidebar branding
with st.sidebar:
    st.markdown("# Refinery")
    st.markdown("---")