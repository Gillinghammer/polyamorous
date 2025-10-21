# Research Progress Streaming Fix

## Issues Fixed

### 1. Critical Indentation Bug
**Problem:** The streaming loop had incorrect indentation that prevented tool calls from being processed inside the `async for` loop.

**Location:** `polly/services/research.py` line 172

**Before:**
```python
async for response, chunk in chat.stream():
    # ... initialization code ...
if getattr(chunk, "tool_calls", None):  # ❌ WRONG - outside the loop!
```

**After:**
```python
async for response, chunk in chat.stream():
    # ... initialization code ...
    
    # Process tool calls
    if getattr(chunk, "tool_calls", None):  # ✅ CORRECT - inside the loop!
```

**Impact:** This bug caused all streaming updates to be skipped, making research appear to complete instantly without showing progress.

### 2. Citations Now Stream in Real-Time
**Enhancement:** Citations are now emitted incrementally as they're discovered, not just at the end.

**Implementation:**
```python
# Collect citations as they appear
if response and getattr(response, "citations", None):
    new_citations = list(response.citations)
    # Emit new citations incrementally
    if len(new_citations) > len(citations):
        for cite in new_citations[len(citations):]:
            callback(ResearchProgress(
                message=f"📎 Found: {cite}",
                round_number=current_round,
                total_rounds=total_rounds,
            ))
    citations = new_citations
```

**Result:** Users see `📎 Found: https://example.com` messages as sources are discovered.

### 3. Improved Progress Display
**Enhancements:**
- Show **15 messages** instead of 5 (better context)
- **Color coding** for different message types:
  - 🔵 Cyan: Tool calls (web_search, x_search)
  - 🟢 Green: Citations found
  - 🟡 Yellow: AI thinking progress
  - 🟣 Magenta: Usage summaries
- **Citation counter** in progress bar
- **Faster refresh rate** (4 times/sec instead of 2)

**Display Format:**
```
╭─ Research Progress ────────────────────────────────────╮
│ Round 1/20: web_search — "Fed rate cuts 2025"         │
│ 📎 Found: https://federalreserve.gov/...               │
│ 📎 Found: https://reuters.com/...                      │
│ Round 2/20: x_search — "Jerome Powell rates"          │
│ Thinking... (295 reasoning tokens)                     │
│ Usage so far: web_search:2, x_search:1                 │
│                                                         │
│ Round 2/20 | 3 citations found                         │
╰────────────────────────────────────────────────────────╯
```

## User Experience Improvements

### Before
```
Starting deep research... This may take 20-40 minutes.

╭─ Research Progress ──────────────────────────╮
│ Research running… awaiting first tool call   │
│ [pause... nothing happens...]                │
│ ✓ Research complete!                         │
╰──────────────────────────────────────────────╯
```

### After
```
Starting deep research...

╭─ Research Progress ──────────────────────────────────╮
│ Starting Grok research (grok-4-fast)...              │
│ Round 1/20: web_search — "Fed rate cuts 2025"       │
│ 📎 Found: https://www.federalreserve.gov/...        │
│ 📎 Found: https://www.reuters.com/markets/...       │
│ 📎 Found: https://www.bloomberg.com/...             │
│ Round 2/20: x_search — "Jerome Powell"              │
│ 📎 Found: https://twitter.com/user/status/...       │
│ Thinking... (412 reasoning tokens)                   │
│ Round 3/20: web_search — "inflation data 2025"      │
│ Usage so far: web_search:2, x_search:1              │
│                                                      │
│ Round 3/20 | 5 citations found                      │
╰──────────────────────────────────────────────────────╯
```

## Technical Details

### Streaming Architecture

The research service uses xAI SDK's streaming API:

```python
async for response, chunk in chat.stream():
    # Process tool calls (web_search, x_search)
    if getattr(chunk, "tool_calls", None):
        callback(ResearchProgress(...))  # Emit to UI
    
    # Process citations
    if response and getattr(response, "citations", None):
        # Emit new citations incrementally
        callback(ResearchProgress(...))
    
    # Process thinking tokens
    if usage and getattr(usage, "reasoning_tokens", None):
        callback(ResearchProgress(...))
```

### Callback Flow

```
ResearchService
    ↓ (emits progress)
ResearchProgress objects
    ↓ (via callback)
update_callback() in commands/research.py
    ↓ (updates)
Rich Live Display
    ↓ (renders)
Terminal UI (4 times/second)
```

## Files Modified

### 1. polly/services/research.py
- Fixed indentation bug (line 172)
- Added incremental citation emission (lines 229-239)
- Proper nesting of all streaming event handlers

### 2. polly/commands/research.py
- Increased visible messages from 5 to 15
- Added color coding for message types
- Added citation counter
- Increased refresh rate to 4 times/second
- Removed "may take 20-40 minutes" (misleading)

## Testing

Run a research command and observe:

✅ Tool calls appear in real-time  
✅ Citations stream as discovered  
✅ Thinking progress updates  
✅ Round counter increments  
✅ Citation count displays  
✅ Color-coded messages  

## Performance

- **Refresh rate:** 4 times per second
- **Message buffer:** Last 15 messages
- **Citation tracking:** Incremental (no duplicates)
- **Memory efficient:** Messages array bounded

## Why This Matters

1. **Transparency:** Users see what the AI is actually doing
2. **Trust:** Visible sources build confidence in research
3. **Progress feedback:** No "black box" waiting period
4. **Debugging:** Easy to see if research is stuck
5. **Educational:** Users learn what makes good research

---

**Date:** October 21, 2025  
**Impact:** Critical bug fix + UX enhancement  
**Status:** Tested and working

