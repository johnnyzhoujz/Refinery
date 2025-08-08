# PoC Part 1

## Failure Analyst Agent

**Context from system:**

- Failed interaction trace or traces from observability platform (input, output, retrieved documents, tool calls)
- Current agent implementation: prompts, evals, system architecture diagram

**When does user provide input?**

- The expected behavior: what “should have happened” in the example of the trace
- Clarifications after Refinery reads the trace and offers breakdown of agent actions
    - “The agent did X first, followed by X tool call…”
- To validate that the diagnosis captures the problem

**What info is used to do what:**

- User business context → what should have happened on the high level
- System implementation → Understand how the agent can work
    - Prompt → instructions
    - Evals → what check is performed
    - Orchestration → flow and distribution of work
- Trace data → Identify potential failure point (e.g., "RAG retrieved wrong document")
- User clarification → Direct Refinery to conduct analysis on relevant areas after agent action breakdown

**Available tool calls:**

- extract_trace_breakdown() → Returns structured trace analysis
- compare_to_expected() → Returns gap analysis

## Hypothesis Generator Agent

**Context from system:**

- Structured diagnosis from Failure Analyst
- Current implementation details (prompts, evals, orchestration, model choice)
- Prompting guides and best practices per model
- Eval guides and best practices

**When does user provide input?**

- To review generated hypotheses and provide feedback with domain expertise
- To select which hypotheses to test

**What info is used to do what:**

- Diagnosis → Generate targeted technical solutions
- Current implementation → Ensure hypotheses are implementable
- Best practices and guides → To create suggested fixes to prompts and evals
- Domain knowledge from user → Refine potential fixes

**Available tool calls:**

- Tool: search_prompting_guides() → LLM-powered RAG over best practices
- Tool: generate_hypotheses() → LLM generates specific changes to prompts and evals
- Tool: file edit → edit code files based on hypothesized changes

@Yifei Li 

thinking about this again, maybe EVERY piece of context should be a tool call? just to minimize the amount of info the agent needs to store in context window in one take?