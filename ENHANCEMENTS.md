# Polly Enhancements Log

## Version 0.1.1 - UI and Search Improvements

### Table Display Enhancements

#### 1. Improved Question Visibility
- **Before**: 50 characters wide (truncated at 47)
- **After**: 70 characters wide (truncated at 67)
- **Impact**: ~40% more question text visible, most polls fit on one line

#### 2. Compact Odds Display
- **Before**: `Yes: 13%, No: 87%` (verbose, 16+ characters)
- **After**: `No 87%` (compact, shows leading option)
- **Impact**: Easier to scan, immediately see which outcome is favored
- **Logic**: Shows the option with highest probability

#### 3. Volume Instead of Liquidity
- **Changed**: "Liquidity" column → "Volume" (24h trading volume)
- **Reason**: Volume data more readily available and meaningful
- **Format**: Uses "k" suffix (e.g., `$150k` instead of `$150,000`)
- **Fix**: Resolved $0 display bug

#### 4. Optimized Column Widths
- **ID**: 12 → 3 characters (displays 1-20)
- **Question**: 50 → 70 characters (+40%)
- **Odds**: 25 → 12 characters (more compact format)
- **Expires**: 10 → 8 characters (sufficient for "25d 8h")
- **Volume**: 12 → 10 characters (with k suffix)

#### 5. Sort by Expiry Date
- **Before**: Sorted by liquidity score (high volume first)
- **After**: Sorted by expiry date (soonest first)
- **Reason**: Users care about time-sensitive opportunities

### Search Functionality

#### New `/polls` Command Syntax

All of these patterns are now supported:

```bash
/polls                  # All polls, sorted by expiry
/polls 7                # Polls ending in 7 days
/polls bitcoin          # Polls mentioning "bitcoin"
/polls 7 bitcoin        # Polls ending in 7 days with "bitcoin"
/polls 14 trump         # Polls ending in 14 days with "trump"
/polls 30 fed rate      # Multi-word search supported
```

#### Search Implementation
- **Scope**: Searches question, description, and tags
- **Case**: Case-insensitive matching
- **Flexibility**: Works with or without days filter
- **Position**: Days filter (if present) must come first

#### Parsing Logic
```python
# Pattern: /polls [days] [search_term]
# Examples:
#   /polls           → days=None, search=None
#   /polls 7         → days=7, search=None
#   /polls bitcoin   → days=None, search="bitcoin"
#   /polls 7 bitcoin → days=7, search="bitcoin"
```

### User Experience Improvements

#### Enhanced Feedback
- Shows filter status in results message
- Examples:
  - `"Showing 15 of 148 markets (expiring in 7 days and matching 'bitcoin')"`
  - `"Showing 20 of 248 markets (sorted by expiry date)"`
  - `"No markets found matching 'xyz'"`

#### Updated Help Text
- Added search examples to `/help` command
- Documented all valid command patterns
- Clear usage examples for common scenarios

### Files Modified

1. **polly/ui/formatters.py**
   - `format_odds()`: Changed to show leading option only
   - `create_polls_table()`: Updated column widths and labels

2. **polly/commands/polls.py**
   - Added search term parsing
   - Implemented search filtering (question, description, tags)
   - Changed default sort to expiry date
   - Enhanced status messages

3. **polly/commands/help.py**
   - Updated command syntax documentation
   - Added search examples

4. **README.md**
   - Documented new search functionality
   - Updated examples

5. **QUICKSTART.md**
   - Added search examples to quick reference

### Testing

All parsing patterns validated:
```
✓ /polls              → days=None, search=None
✓ /polls 7            → days=7, search=None  
✓ /polls bitcoin      → days=None, search="bitcoin"
✓ /polls 7 bitcoin    → days=7, search="bitcoin"
✓ /polls 14 trump     → days=14, search="trump"
✓ /polls 30 fed rate  → days=30, search="fed rate"
```

### Benefits

1. **Better Readability**: More question text visible per line
2. **Faster Scanning**: Compact odds, clear expiry dates
3. **Better Discovery**: Search by keywords of interest
4. **Flexible Filtering**: Combine time and topic filters
5. **Time-Focused**: Sorted by urgency (expiry date)
6. **Accurate Data**: Fixed volume display bug

### Backward Compatibility

All existing commands continue to work:
- ✓ `/polls` - Shows all markets
- ✓ `/polls 7` - Time filter works as before
- ✓ `/polls 14`, `/polls 30`, `/polls 180` - All time filters work

New functionality is purely additive - no breaking changes.

---

## Version 0.1.2 - Category Column and Enhanced Search

### Category Display

#### Added Category Column
- **New column**: Shows market category (Politics, Crypto, Economics, etc.)
- **Position**: Second column (after ID, before Question)
- **Width**: 12 characters
- **Format**: Truncates with ".." if longer than 11 chars
- **Fallback**: Shows "Other" if category is missing

#### Adjusted Table Layout
- **ID**: 3 chars (unchanged)
- **Category**: 12 chars (NEW)
- **Question**: 55 chars (reduced from 70 to make room)
- **Odds**: 12 chars (unchanged)
- **Expires**: 8 chars (unchanged)
- **Volume**: 10 chars (unchanged)

### Enhanced Search

#### Category Search Support
Search terms now match against **four fields**:
1. Question text
2. **Category** (NEW)
3. Description
4. Tags

#### Category Search Examples
```bash
/polls politics         # Matches category="Politics"
/polls crypto           # Matches category="Crypto"
/polls 7 economics      # Markets ending in 7 days in Economics category
```

#### Implementation
- Case-insensitive matching across all fields
- Category can be searched like any other term
- Combines seamlessly with days filter

### Use Cases

**Browse by Category**:
```bash
/polls politics         # All politics markets
/polls 7 crypto         # Crypto markets ending in 7 days
```

**Browse by Topic**:
```bash
/polls bitcoin          # Matches question/tags
/polls trump            # Matches question/description
```

**Hybrid Queries**:
- `/polls economics` might match category OR question text
- Flexible search covers all bases

### Testing

Verified category search across fields:
```
✓ /polls politics    → Matches category="Politics"
✓ /polls crypto      → Matches category="Crypto"
✓ /polls bitcoin     → Matches question + tags
✓ Category=None      → Handled gracefully (shows "Other")
```

### Files Modified

1. **polly/ui/formatters.py**
   - Added Category column to table
   - Adjusted Question width (70→55)
   - Added category truncation logic

2. **polly/commands/polls.py**
   - Added category to search filter
   - Handles None category gracefully

3. **polly/commands/help.py**
   - Added category example
   - Note about search fields

4. **README.md** & **QUICKSTART.md**
   - Documented category search
   - Updated examples

### Benefits

1. **Better Organization**: See market category at a glance
2. **Easier Filtering**: Search by category name
3. **More Context**: Understand market type before reading full question
4. **Flexible Discovery**: Find markets by topic OR category

---

## Version 0.1.3 - Command History with Prefix Search

### Advanced Command History

#### Implementation
Integrated `prompt_toolkit` library to provide professional command-line history features.

#### Features Added

**1. Standard History Navigation**
- **Up Arrow**: Previous command
- **Down Arrow**: Next command  
- Works like standard shell (bash, zsh, etc.)

**2. Prefix-Based Filtering** ⭐
- Type a prefix (e.g., `/p`)
- Press **Up** arrow
- Shows last command starting with `/p`
- Press **Up** again for earlier matches
- This is the "extra points" feature!

**3. Reverse Search**
- Press **Ctrl+R**
- Type search term
- Incrementally searches through history
- Press **Ctrl+R** again to find earlier matches

**4. Persistent History**
- Saved to `~/.polly/history.txt`
- Persists across sessions
- Unlimited entries
- Never lose your command history

### Usage Examples

**Scenario 1: Repeat recent command**
```bash
polly> /polls bitcoin
polly> /portfolio
polly> [Press Up]      # Shows /portfolio
polly> [Press Up]      # Shows /polls bitcoin
```

**Scenario 2: Prefix filtering** (The requested feature!)
```bash
polly> /polls 7 bitcoin
polly> /portfolio
polly> /polls crypto
polly> /research 1
polly> /p              # Type /p
polly> [Press Up]      # Shows /polls crypto (last /p command)
polly> [Press Up]      # Shows /portfolio (next /p command)
polly> [Press Up]      # Shows /polls 7 bitcoin (first /p command)
```

**Scenario 3: Reverse search**
```bash
polly> [Ctrl+R]
(reverse-i-search)`': 
# Type "bitcoin"
(reverse-i-search)`bitcoin': /polls 7 bitcoin
# Press Enter to use that command
```

### Technical Details

#### Library Used
- **prompt_toolkit** >= 3.0.0
- Industry-standard Python library
- Cross-platform (Windows, macOS, Linux)
- Used by IPython, ptpython, and many professional tools

#### Key Features
- **FileHistory**: Persists history to disk
- **enable_history_search**: Enables prefix-based filtering
- Automatic duplicate removal
- Thread-safe history handling

#### Implementation
```python
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

# Create session with history
session = PromptSession(
    history=FileHistory(str(HISTORY_FILE)),
    enable_history_search=True,
)

# Replace input() with session.prompt()
command = session.prompt("\npolly> ")
```

### Files Modified

1. **polly/cli.py**
   - Added `prompt_toolkit` imports
   - Created `HISTORY_FILE` constant (`~/.polly/history.txt`)
   - Replaced `input()` with `PromptSession.prompt()`
   - Enabled history search

2. **requirements.txt**
   - Added `prompt-toolkit>=3.0.0`

3. **pyproject.toml**
   - Added `prompt-toolkit>=3.0.0` to dependencies

4. **README.md**
   - Added "Command History" section
   - Documented navigation shortcuts
   - Provided usage examples

5. **QUICKSTART.md**
   - Added command history quick reference
   - Example of prefix search usage

### Benefits

1. **Professional UX**: Shell-like command history expected by users
2. **Efficiency**: Quickly repeat or modify previous commands
3. **Prefix Search**: The requested "extra points" feature - find commands by typing prefix
4. **Reverse Search**: Ctrl+R for powerful incremental search
5. **Persistence**: Never lose your command history across sessions
6. **Cross-Platform**: Works on Windows, macOS, and Linux

### Keyboard Shortcuts Summary

| Shortcut | Action |
|----------|--------|
| Up Arrow | Previous command (or prefix match if typed) |
| Down Arrow | Next command (or prefix match if typed) |
| Ctrl+R | Reverse incremental search |
| Ctrl+C | Cancel current input |
| Ctrl+D or /exit | Exit Polly |

### History File Location

- **Path**: `~/.polly/history.txt`
- **Format**: Plain text, one command per line
- **Management**: Automatically managed by prompt_toolkit
- **Cleanup**: Delete file to clear history (safe to do)

---

**Date**: October 21, 2025  
**Version**: 0.1.3  
**Status**: Complete and tested

