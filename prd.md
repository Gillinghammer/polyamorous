# PRD: Poly - TUI Polymarket Research & Paper Trading

## 1) Summary

A Python TUI (Terminal User Interface) application that helps users research Polymarket polls and make informed predictions. The app displays top liquid polls (excluding sports), runs deep agentic research using Grok 4 (Web + X search) to find asymmetric information, evaluates if the odds justify taking a position, and tracks paper trading performance. Users bring their own xAI (Grok) API key.

**📁 Documentation**: See `docs/` folder for implementation guides:
- `textual-guide.md` - TUI framework patterns
- `grok-agentic-guide.md` - Agentic research implementation  
- `polymarket-client-guide.md` - Market data fetching

## 2) Goals & Non‑Goals

**Phase 1 Goals**

* Display top 20 most liquid Polymarket polls (excluding sports) in a clean TUI
* Enable deep, multi-round agentic research to find asymmetric information
* Show research progress (research can take 20-40 minutes)
* Evaluate if current odds justify taking a position (accuracy over frequency)
* Track paper trades with win rate, profit metrics, and projected APR
* Hold positions until poll expiry (no early exits in Phase 1)

**Non‑Goals (Phase 1)**

* Real money execution/custody - paper trading only
* Early position exits - hold until expiry
* Sports betting markets - exclude all sports polls
* Complex portfolio optimization
* Multi‑exchange support

## 3) Users & Use Cases

**Primary user**: Individual prediction market trader seeking asymmetric information advantages

**Top use cases**

1. **Browse** top 20 liquid non-sports polls with current odds and time remaining
2. **Research** selected poll using deep multi-round Grok agentic search (20-40 min)
3. **Evaluate** if research findings justify taking a position at current odds
4. **Trade** paper positions held until poll expiry
5. **Monitor** dashboard with win rate, profit metrics, and projected APR

## 4) Application Flow

**Launch**: User types `poly` to start the TUI application

1. **Load Markets**: Fetch and display top 20 most liquid Polymarket polls (excluding sports)
   - Show: poll question, options, current odds, time remaining, liquidity
   
2. **Select Poll**: User selects a poll to research

3. **Deep Research** (20-40 minutes):
   - Run multiple rounds of Grok 4 agentic research (Web + X search)
   - Goal: Find asymmetric information to accurately forecast outcome
   - Show progress indicators during long-running research
   - Iterate until confident understanding of all information intricacies
   
4. **Evaluate Position**:
   - Research produces: prediction, confidence level, rationale, citations
   - Algorithm evaluates: Do current odds justify taking a position?
   - Recommendation: Enter position or pass (prioritize accuracy over frequency)
   
5. **Enter Trade** (if user accepts):
   - Record paper trade (poll, side, odds, stake, timestamp)
   - Position held until poll expiry (no early exits)
   
6. **Dashboard**: Display performance metrics
   - Active positions count
   - Win rate
   - Total profit
   - Average profit
   - Projected annualized rate of return

## 5) TUI Experience (Textual Framework)

> **See**: `docs/textual-guide.md` for complete TUI implementation patterns, async workers, and widget examples

**Launch**: `poly` command starts the TUI application

**Visual Style**:
- Clean, modern interface using Textual components
- Dark theme with clear typography
- Minimal clutter, focus on information density
- Responsive layout optimized for terminal

**Main Views**:

1. **Polls List View** (Default):
   - Top 20 most liquid non-sports polls
   - Condensed format: Question | Options | Current Odds | Time Left | Liquidity
   - Navigate with arrow keys, Enter to select

2. **Research View** (During research):
   - Poll details at top
   - Progress indicator showing research status (critical for 20-40 min process)
   - Real-time updates: "Searching web...", "Analyzing X posts...", "Round 2/4..."
   - Live research notes as they develop

3. **Decision View** (After research):
   - Research summary with prediction & confidence
   - Key findings and citations
   - Current odds vs. recommended position
   - Action: [Enter Trade] [Pass] [View Details]

4. **Dashboard View**:
   - Active Positions: count
   - Win Rate: X/Y (Z%)
   - Total Profit: $X
   - Average Profit: $X per position
   - Projected APR: X%
   - Recent trades list

**Navigation**:
- Tab/Shift+Tab: Switch between views
- Arrow keys: Navigate lists
- Enter: Select/Confirm
- Esc: Go back
- q: Quit application

## 6) Command

**Single Command**: `poly`
- Launches the full TUI application
- No subcommands needed for Phase 1
- All functionality accessible within TUI

## 7) Functional Requirements

### 7.1 Poll Ingestion & Filtering

> **See**: `docs/polymarket-client-guide.md` for complete implementation examples

* Fetch active Polymarket polls with fields: `id, question, options[], current_odds{}, resolves_at, open_interest, volume_24h, category`
* **Exclude**: All sports-related polls (filter by category)
* **Select**: Top 20 by liquidity (open_interest + volume_24h combined metric)
* **Display**: Condensed list showing:
  - Poll question (truncated if long)
  - Options with current odds
  - Time remaining until resolution
  - Liquidity indicator (High/Med/Low badge)

### 7.2 Deep Agentic Research (Grok 4)

> **See**: `docs/grok-agentic-guide.md` for streaming implementation and multi-round patterns

**Goal**: Find asymmetric information to accurately forecast poll outcome

**Tools**: Grok 4 with Web Search and X Search capabilities

**Process**:
1. Initial research round analyzes poll question and identifies key information gaps
2. Multiple iterative rounds (no hard limit) to gather information:
   - Web search for news, analysis, data
   - X search for real-time sentiment, insider knowledge
   - Each round builds on previous findings
3. Continue until confident in understanding all intricacies OR diminishing returns
4. Expected duration: 20-40 minutes per poll

**Output**:
- Prediction: Which option is most likely (with probability)
- Confidence: 0-100% confidence in the prediction
- Rationale: Key findings explaining the prediction
- Citations: Sources used (web links, X posts)
- Information asymmetries: What the market might be missing

**UX Requirements**:
- MUST show live progress during research (critical for long duration)
- Display current research round/activity
- Show interim findings as they develop
- Allow user to monitor without blocking TUI

**Implementation**: Use Grok's streaming API with real-time tool call monitoring (see guide)

### 7.3 Position Evaluation Algorithm

**Philosophy**: Accuracy over frequency. Only enter when edge is clear.

**Inputs**:
- Research prediction: probability for each option
- Research confidence: 0-100%
- Current market odds for each option
- Time to expiry

**Algorithm**:
1. Calculate expected value for each option:
   ```
   EV = (predicted_prob * payout) - (1 - predicted_prob) * stake
   ```
2. Calculate edge vs. market:
   ```
   edge = predicted_prob - implied_prob_from_odds
   ```
3. Adjust for confidence:
   ```
   adjusted_edge = edge * (confidence / 100)
   ```
4. Decision criteria (all must be true):
   - `adjusted_edge > minimum_threshold` (e.g., 10%)
   - `confidence > minimum_confidence` (e.g., 70%)
   - `EV > 0` (positive expected value)

**Recommendation**:
- ENTER: Option to bet on + suggested stake
- PASS: Why the position isn't justified (weak edge, low confidence, etc.)

### 7.4 Paper Trading

> **See**: `docs/textual-guide.md` for async worker patterns to handle long-running operations without blocking UI

**Phase 1 Constraints**:
- Paper trading only (no real money)
- Fixed stake amount per trade (e.g., $100)
- Hold until poll expiry (no early exits)
- Track all positions to conclusion

**Trade Record**:
```
{
  poll_id, 
  question,
  selected_option,
  entry_odds,
  stake_amount,
  entry_timestamp,
  predicted_probability,
  confidence,
  research_summary,
  status: "active" | "won" | "lost",
  resolves_at,
  actual_outcome: null | option_name,
  profit_loss: null | number
}
```

**User Decision Flow**:
1. Review research findings and recommendation
2. See: "Recommendation: BET on [Option X] at current odds of [Y]"
3. Action: [Enter Trade with $100] or [Pass]
4. If Enter: Record paper trade, add to active positions
5. Position held until poll resolves

### 7.5 Dashboard & Performance Metrics

**Key Metrics**:
1. **Active Positions**: Count of current open trades
2. **Win Rate**: Resolved wins / total resolved trades (e.g., "12/15 (80%)")
3. **Total Profit**: Sum of all P&L from resolved trades
4. **Average Profit**: Total profit / number of resolved trades
5. **Projected APR**: Annualized return based on average profit and holding period

**Calculations**:
- Win when actual outcome matches our position
- Loss when actual outcome differs
- Profit = (stake * odds) - stake [if win], or -stake [if loss]
- APR = (total_profit / total_staked) * (365 / avg_days_held) * 100

**Display**:
- Show metrics prominently in dashboard view
- List active positions with: poll question, our bet, odds, days left
- List recent resolved trades with: outcome, profit/loss, duration

## 8) Non‑Functional Requirements

* **Performance**: 
  - Polls list loads in < 3 seconds
  - Research runs 20-40 minutes (acceptable, must show progress)
  - TUI remains responsive during long operations
  
* **Resilience**: 
  - Handle API errors gracefully with retries
  - Save research progress (don't lose 40min of work on crash)
  - Persist trades to disk (SQLite)
  
* **UX**:
  - Live progress indicators for long operations
  - Clear, readable output (no terminal clutter)
  - Smooth navigation between views
  
* **Security**: 
  - Load xAI API key from environment variable
  - Never log API keys
  - Store data locally only
  
* **Data Persistence**:
  - SQLite database for trades, research, positions
  - Survive app restarts
  - Export capability (future: CSV/JSON)

## 9) Tech Stack

**Core**:
- Python 3.11+
- Textual 0.40+ (TUI framework from textualize.io) - See `docs/textual-guide.md`
- py-clob-client (Polymarket API) - See `docs/polymarket-client-guide.md`
- pydantic (data validation)
- SQLModel + SQLite (persistence)

**AI/Research**:
- xAI SDK for Grok 4 - See `docs/grok-agentic-guide.md`
- Model: `grok-4-fast` (or latest)
- Tools: Web Search, X Search

**Utilities**:
- tenacity (retries)
- asyncio (async operations)
- python-dotenv (environment vars)

**📚 Implementation Guides**:
- `docs/textual-guide.md` - Complete TUI framework guide with async workers, widgets, and layouts
- `docs/grok-agentic-guide.md` - Agentic research with streaming, multi-round patterns, citations
- `docs/polymarket-client-guide.md` - Fetch and filter markets, read-only mode for Phase 1

> **Note**: All documentation guides include a note to use Context7 MCP tool for latest information and clarification.

## 10) Data Sources

* **Polymarket API**: 
  - Fetch active polls with metadata
  - Filter by category (exclude sports)
  - Sort by liquidity metrics
  - Get current odds in real-time
  
* **xAI Grok API**:
  - Agentic research with tool calling
  - Web search for news/analysis
  - X search for real-time sentiment

## 11) Data Model

**Poll**:
```python
{
  id: str,
  question: str,
  options: list[str],
  current_odds: dict[str, float],  # option -> odds
  resolves_at: datetime,
  open_interest: float,
  volume_24h: float,
  category: str,
  status: "active" | "resolved"
}
```

**Research**:
```python
{
  id: int,
  poll_id: str,
  prediction: str,  # which option
  probability: float,  # 0-1
  confidence: float,  # 0-100
  rationale: str,
  key_findings: list[str],
  citations: list[str],
  rounds_completed: int,
  created_at: datetime,
  duration_minutes: int
}
```

**Trade**:
```python
{
  id: int,
  poll_id: str,
  question: str,
  selected_option: str,
  entry_odds: float,
  stake_amount: float,
  entry_timestamp: datetime,
  predicted_probability: float,
  confidence: float,
  research_id: int,
  status: "active" | "won" | "lost",
  resolves_at: datetime,
  actual_outcome: str | null,
  profit_loss: float | null,
  closed_at: datetime | null
}
```

## 12) Research Prompt Strategy

**Goal**: Find asymmetric information to forecast poll outcome accurately

**Prompt Template**:
```
You are a prediction market analyst researching this poll:

Question: {poll_question}
Options: {options}
Current market odds: {current_odds}
Resolves: {resolution_date}

Your goal is to find information asymmetries that could give us edge over the market.

Phase 1: Identify Information Gaps
- What key factors determine this outcome?
- What information is the market potentially missing?
- What sources would have the best insights?

Phase 2: Deep Research (use Web Search and X Search)
- Search for recent news, analysis, data
- Look for expert opinions, insider knowledge
- Cross-reference multiple sources
- Identify sentiment vs. facts

Phase 3: Synthesize
- Which option is most likely? (probability 0-1)
- How confident are you? (0-100%)
- What are the key reasons? (bullet points)
- What information asymmetries did you find?
- List all sources used

Continue researching until you have high confidence OR hit diminishing returns.
```

## 13) Phase 1 Scope Summary

> **Implementation Reference**: All features have corresponding examples in `docs/` guides

**IN SCOPE**:
- ✅ TUI app launched with `poly` command (see `docs/textual-guide.md`)
- ✅ Display top 20 liquid non-sports polls (see `docs/polymarket-client-guide.md`)
- ✅ User selects poll to research (ListView widget examples in textual guide)
- ✅ Deep multi-round Grok research (see `docs/grok-agentic-guide.md`)
- ✅ Live progress indicators during research (async workers in textual guide)
- ✅ Position evaluation algorithm (accuracy > frequency)
- ✅ Paper trading with fixed stakes
- ✅ Hold positions until expiry
- ✅ Dashboard with win rate, profit, APR metrics
- ✅ SQLite persistence

**OUT OF SCOPE** (Future Phases):
- ❌ Real money execution
- ❌ Early position exits
- ❌ Sports betting
- ❌ Portfolio optimization
- ❌ Multiple exchanges
- ❌ Advanced risk management
- ❌ User authentication
- ❌ Mobile/web interface

## 14) Configuration

**Environment Variables** (`.env`):
```
XAI_API_KEY=your_xai_api_key_here
```

**App Configuration** (`~/.poly/config.yml`):
```yaml
# Phase 1 Settings
paper_trading:
  default_stake: 100  # Fixed stake per trade

research:
  min_confidence_threshold: 70  # 0-100
  min_edge_threshold: 0.10      # 10%
  
polls:
  top_n: 20                     # Show top 20 liquid polls
  exclude_categories:           # Exclude sports
    - sports
    - esports
  liquidity_weight:             # Sort by liquidity
    open_interest: 0.7
    volume_24h: 0.3

database:
  path: ~/.poly/trades.db       # SQLite database
```
