# Grok Agentic Server-Side Tool Calling Guide

> **Note**: This guide is for reference only. If you need clarity or more information, use the Context7 MCP tool to fetch the latest documentation.

## Overview

Grok 4 provides powerful agentic capabilities through server-side tool calling, allowing the model to autonomously use Web Search, X (Twitter) Search, and Code Execution to gather information and solve complex problems.

## Installation

```bash
pip install xai-sdk>=1.3.0
```

Set your API key:
```bash
export XAI_API_KEY=your_api_key_here
```

## Basic Setup

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search, code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))
```

## Available Server-Side Tools

### 1. Web Search
Search the web for information, news, and analysis.

```python
from xai_sdk.tools import web_search

chat = client.chat.create(
    model="grok-4-fast",
    tools=[web_search()],
)
```

**Advanced Web Search Options:**

```python
# Restrict to specific domains
web_search(allowed_domains=["wikipedia.org", "reuters.com"])

# Exclude specific domains
web_search(excluded_domains=["example.com"])

# Enable image understanding (increases token usage)
web_search(enable_image_understanding=True)
```

### 2. X (Twitter) Search
Search X posts for real-time sentiment and insider knowledge.

```python
from xai_sdk.tools import x_search

chat = client.chat.create(
    model="grok-4-fast",
    tools=[x_search()],
)
```

**Advanced X Search Options:**

```python
# Filter by specific X handles
x_search(allowed_x_handles=["elonmusk", "xai"])

# Exclude specific X handles
x_search(excluded_x_handles=["spam_account"])

# Filter by date range
from datetime import datetime
x_search(
    from_date=datetime(2025, 1, 1),
    to_date=datetime(2025, 10, 18)
)

# Enable image understanding
x_search(enable_image_understanding=True)

# Enable video understanding
x_search(enable_video_understanding=True)
```

### 3. Code Execution
Run Python code for calculations and data analysis.

```python
from xai_sdk.tools import code_execution

chat = client.chat.create(
    model="grok-4-fast",
    tools=[code_execution()],
)
```

## Research Workflow Pattern

For deep research (like our Polymarket use case), combine multiple tools:

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Enable both web and X search for comprehensive research
chat = client.chat.create(
    model="grok-4-fast",
    tools=[
        web_search(),
        x_search(),
    ],
)

chat.append(user("What is the latest update from xAI?"))
```

## Streaming Responses (Critical for Long Research)

For research that takes 20-40 minutes, streaming is **essential** for UX:

```python
chat.append(user("Research this Polymarket poll..."))

is_thinking = True
for response, chunk in chat.stream():
    # Show tool calls in real-time
    for tool_call in chunk.tool_calls:
        print(f"\nCalling tool: {tool_call.function.name}")
        print(f"Arguments: {tool_call.function.arguments}")
    
    # Show thinking progress
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\rThinking... ({response.usage.reasoning_tokens} tokens)", 
              end="", flush=True)
    
    # Show final response
    if chunk.content and is_thinking:
        print("\n\nFinal Response:")
        is_thinking = False
    
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

# Access final results
print("\n\nCitations:")
print(response.citations)

print("\n\nUsage:")
print(response.usage)
print(response.server_side_tool_usage)

print("\n\nAll Tool Calls:")
print(response.tool_calls)
```

## Synchronous (Non-Streaming) Request

When streaming is not needed:

```python
chat.append(user("What is the weather in San Francisco?"))

# Get the final response in one go
response = chat.sample()

print("Final Response:")
print(response.content)

print("\nCitations:")
print(response.citations)

print("\nUsage:")
print(response.usage)
```

## Understanding Tool Calls vs Tool Usage

### `tool_calls` - All Attempted Calls
Returns **every** tool call attempt, including failures:

```python
response.tool_calls
# Returns: [
#   {id: "call_123", function: {name: "web_search", arguments: "..."}},
#   {id: "call_456", function: {name: "x_search", arguments: "..."}},
# ]
```

### `server_side_tool_usage` - Successful Calls (Billable)
Returns only successful calls that count toward billing:

```python
response.server_side_tool_usage
# Returns: {
#   'SERVER_SIDE_TOOL_WEB_SEARCH': 2,
#   'SERVER_SIDE_TOOL_X_SEARCH': 3
# }
```

### Function Name Mapping

| Usage Category | Function Names |
|---|---|
| `SERVER_SIDE_TOOL_WEB_SEARCH` | `web_search`, `web_search_with_snippets`, `browse_page` |
| `SERVER_SIDE_TOOL_X_SEARCH` | `x_user_search`, `x_keyword_search`, `x_semantic_search`, `x_thread_fetch` |
| `SERVER_SIDE_TOOL_CODE_EXECUTION` | `code_execution` |
| `SERVER_SIDE_TOOL_VIEW_IMAGE` | `view_image` |
| `SERVER_SIDE_TOOL_VIEW_X_VIDEO` | `view_x_video` |

## Citations

Access all sources the agent used:

```python
response.citations
# Returns: [
#   'https://x.com/xai/status/...',
#   'https://x.ai/news',
#   'https://docs.x.ai/...',
# ]
```

**Note:** Citations are only available after the request completes (not during streaming).

## Multi-Round Research Pattern

For deep research with multiple iterations:

```python
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))

chat = client.chat.create(
    model="grok-4-fast",
    tools=[web_search(), x_search()],
)

# Initial research question
chat.append(user("""
Research this Polymarket poll: "Will candidate X win the election?"

Your goal is to find information asymmetries that the market might be missing.

Phase 1: Identify what key factors determine this outcome
Phase 2: Search for recent news, polls, expert analysis
Phase 3: Look for insider knowledge on X
Phase 4: Synthesize findings and identify what the market might be missing

Continue researching until you have high confidence OR hit diminishing returns.
"""))

# Stream the research process
all_tool_calls = []
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        all_tool_calls.append(tool_call)
        print(f"\n[Round {len(all_tool_calls)}] {tool_call.function.name}")
        print(f"  Query: {tool_call.function.arguments}")
    
    if chunk.content:
        print(f"\n{chunk.content}", end="", flush=True)

# Final results
print(f"\n\nCompleted {len(all_tool_calls)} research rounds")
print(f"Sources consulted: {len(response.citations)}")
```

## Tool Combinations for Different Use Cases

```python
from xai_sdk.tools import web_search, x_search, code_execution

# Research + Analysis
research_tools = [web_search(), code_execution()]

# News Aggregation
news_tools = [web_search(), x_search()]

# Comprehensive Research (for Polymarket)
comprehensive_tools = [web_search(), x_search(), code_execution()]
```

## Error Handling

```python
try:
    chat.append(user("Research this topic..."))
    response = chat.sample()
    print(response.content)
except Exception as e:
    print(f"Error during research: {e}")
    # Save any partial results if available
```

## Best Practices for Long Research Sessions

1. **Always use streaming** for operations > 30 seconds
2. **Show progress indicators** to users
3. **Save intermediate results** in case of failures
4. **Monitor token usage** via `response.usage`
5. **Track tool calls** to understand the research path
6. **Access citations** for transparency

## Example: Polymarket Poll Research

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search

client = Client(api_key=os.getenv("XAI_API_KEY"))

chat = client.chat.create(
    model="grok-4-fast",
    tools=[web_search(), x_search()],
)

poll_question = "Will GDP growth exceed 3% in Q4 2025?"
current_odds = {"yes": 0.45, "no": 0.55}

research_prompt = f"""
Research this Polymarket poll: "{poll_question}"

Current market odds: Yes {current_odds['yes']}, No {current_odds['no']}

Your goal: Find asymmetric information to accurately forecast the outcome.

Phase 1: Identify Information Gaps
- What key factors determine GDP growth?
- What information is the market potentially missing?
- What sources would have the best insights?

Phase 2: Deep Research
- Search for recent economic data, forecasts, expert analysis
- Look for real-time insights on X from economists
- Cross-reference multiple sources
- Identify sentiment vs. facts

Phase 3: Synthesize
- Which option is most likely? (probability 0-1)
- How confident are you? (0-100%)
- What are the key reasons? (bullet points)
- What information asymmetries did you find?
- List all sources used

Continue researching until you have high confidence OR hit diminishing returns.
"""

chat.append(user(research_prompt))

print("Starting research (this may take 20-40 minutes)...\n")

round_count = 0
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        round_count += 1
        print(f"\n[Research Round {round_count}]")
        print(f"Tool: {tool_call.function.name}")
        print(f"Args: {tool_call.function.arguments[:100]}...")
    
    if response.usage.reasoning_tokens:
        print(f"\rAnalyzing... ({response.usage.reasoning_tokens} tokens)", 
              end="", flush=True)
    
    if chunk.content:
        print("\n\n=== RESEARCH COMPLETE ===\n")
        print(chunk.content, end="", flush=True)

print(f"\n\n=== METADATA ===")
print(f"Research rounds: {round_count}")
print(f"Sources consulted: {len(response.citations)}")
print(f"Token usage: {response.usage.total_tokens}")
print(f"\nCitations:")
for i, citation in enumerate(response.citations[:10], 1):
    print(f"{i}. {citation}")
```

## Monitoring Token Usage

```python
print(f"Reasoning tokens: {response.usage.reasoning_tokens}")
print(f"Total tokens: {response.usage.total_tokens}")
print(f"Tool usage: {response.server_side_tool_usage}")
```

## Resources

- [xAI API Docs](https://docs.x.ai/)
- [xAI SDK GitHub](https://github.com/xai-org/xai-sdk-python)
- [Tool Calling Guide](https://docs.x.ai/docs/guides/tools/overview)
- [Search Tools Guide](https://docs.x.ai/docs/guides/tools/search-tools)

