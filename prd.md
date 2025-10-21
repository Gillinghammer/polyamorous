# PRD: Polly - Command-Based Polymarket Research & Paper Trading

## 1) Summary

A Python command-based application that helps users research Polymarket polls and make informed predictions. The app fetches polls filtered by time-to-expiry, runs deep agentic research using Grok 4 (Web + X search) to find asymmetric information, evaluates if the odds justify taking a position, and tracks paper trading performance. Users bring their own xAI (Grok) API key.

**📁 Documentation**: See `docs/` folder for implementation guides:
- `grok-agentic-guide.md` - Agentic research implementation  
- `polymarket-client-guide.md` - Market data fetching

## 2) Goals & Non‑Goals

**Phase 1 Goals**

* Fetch polls filtered by time-to-expiry (7, 14, 30, 180 days)
* Enable deep, multi-round agentic research to find asymmetric information
* Show research progress (research can take 20-40 minutes)
* Evaluate if current odds justify taking a position (accuracy over frequency)
* Track paper trades with win rate, profit metrics, and projected APR
* Hold positions until poll expiry (no early exits in Phase 1)
* Filter research results by status (completed, pending, archived)

**Non‑Goals (Phase 1)**

* Real money execution/custody - paper trading only
* Early position exits - hold until expiry
* Complex portfolio optimization
* Multi‑exchange support
* Mobile or web interface

## 3) Users & Use Cases

**Primary user**: Individual prediction market trader seeking asymmetric information advantages

**Top use cases**

1. **Browse** polls by time-to-expiry using `/polls [days]` command
2. **Research** selected poll using `/research <poll_id>` (20-40 min)
3. **Evaluate** if research findings justify taking a position at current odds
4. **Trade** paper positions held until poll expiry
5. **Monitor** portfolio performance using `/portfolio` command

## 4) Application Flow

**Launch**: User types `polly` to start the application

1. **Browse Polls**: Fetch polls by time-to-expiry
   - Command: `/polls` or `/polls [days]`
   - Options: 7, 14, 30, 180 days (optional)
   - Display: poll ID, question, options, current odds, time remaining
   
2. **Research Poll**: Run deep research on selected poll
   - Command: `/research <poll_id>`
   - Duration: 20-40 minutes
   - Process:
     * Run multiple rounds of Grok 4 agentic research (Web + X search)
     * Find asymmetric information to accurately forecast outcome
     * Show progress indicators during research
     * Iterate until confident understanding of all intricacies
   
3. **Evaluate Position**:
   - Research produces: prediction, confidence level, rationale, citations
   - Algorithm evaluates: Do current odds justify taking a position?
   - Recommendation: Enter position or pass (prioritize accuracy over frequency)
   
4. **Enter Trade** (if user accepts):
   - Record paper trade (poll, side, odds, stake, timestamp)
   - Position held until poll expiry (no early exits)
   
5. **View Research History**: Filter past research results
   - Command: `/history [status]`
   - Status filters: completed, pending, archived (optional)
   - Display: Poll ID, recommended bet, odds, potential payout for $100 stake
   
6. **View Portfolio**: Trading performance metrics
   - Command: `/portfolio`
   - Display: active positions, win rate, total profit, average profit, projected APR

## 5) Command Interface

**Launch**: `polly` command starts the application

**Visual Style**:
- Clean ASCII banner on startup
- Command-driven interface
- Clear output formatting
- Minimal clutter, focus on information density

**Available Commands**:

1. **Browse Polls**:
   - `/polls` - Show all available polls
   - `/polls 7` - Polls ending in 7 days
   - `/polls 14` - Polls ending in 14 days  
   - `/polls 30` - Polls ending in 30 days
   - `/polls 180` - Polls ending in 180 days
   - Output: Poll ID, question, options, current odds, time remaining

2. **Research Poll**:
   - `/research <poll_id>` - Run deep research on specific poll
   - Example: `/research 1`
   - Shows progress during 20-40 minute research process
   - Displays: recommendation, odds, potential payout for $100 stake

3. **Research History**:
   - `/history` - Show all research
   - `/history completed` - Research finished with recommendations
   - `/history pending` - Research in progress or not started
   - `/history archived` - Polls that have resolved
   - Display: Poll ID, recommended bet, odds, potential payout for $100

4. **Portfolio Performance**:
   - `/portfolio` - Show trading performance and metrics
   - Display: active positions count, win rate, total profit, average profit, projected APR
   - Lists active positions and recent resolved trades

5. **Utility**:
   - `/help` - Show all available commands
   - `/exit` - Quit application

## 6) Commands Summary

**Launch Command**: `polly`
- Starts the command-based application
- Shows ASCII banner with POLLY logo and getting started instructions

**Core Commands**:
- `/polls [days]` - Browse polls (optional filter: 7, 14, 30, 180 days)
- `/research <poll_id>` - Run deep research on a poll
- `/history [status]` - View research history (optional filter: completed, pending, archived)
- `/portfolio` - View trading performance and metrics
- `/help` - Show all available commands
- `/exit` - Quit application

## 7) Functional Requirements

### 7.1 Poll Ingestion & Filtering

> **See**: `docs/polymarket-client-guide.md` for complete implementation examples

* Fetch active Polymarket prediction market polls with fields: `id, question, options[], current_odds{}, resolves_at, open_interest, volume_24h, category`
* **Filter by time-to-expiry**: 
  - `/polls` - All active polls
  - `/polls 7` - Polls ending in 7 days
  - `/polls 14` - Polls ending in 14 days
  - `/polls 30` - Polls ending in 30 days
  - `/polls 180` - Polls ending in 180 days
* **Display**: List showing:
  - Poll ID (for research command)
  - Poll question (prediction market)
  - Options with current odds
  - Time remaining until resolution

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
- Allow user to monitor without blocking command interface

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

### 7.4 Paper Trading & Research History

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
1. After research completes, display recommendation
2. Show: "Recommendation: BET on [Option X] at current odds of [Y]" or "PASS - [reason]"
3. If ENTER recommended, prompt: "Enter trade with $100 stake? (y/n)"
4. If user confirms (y): Record paper trade, add to active positions
5. Position held until poll resolves

**Research History Display**:
- Filter options:
  * `completed` - Research finished, recommendation available
  * `pending` - Research in progress or not yet started
  * `archived` - Poll has resolved
- For each research result, display:
  * Poll ID
  * Recommended bet (option name or "PASS")
  * Odds (if bet recommended)
  * Potential payout if invested $100 (calculated from odds)

### 7.5 Portfolio & Performance Metrics

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

**Display** (via `/portfolio` command):
- Show metrics at top
- List active positions: poll question, our bet, odds, days left
- List recent resolved trades: outcome, profit/loss, duration

## 8) Non‑Functional Requirements

* **Performance**: 
  - Polls list loads in < 3 seconds
  - Research runs 20-40 minutes (acceptable, must show progress)
  - Application remains responsive during long operations
  
* **Resilience**: 
  - Handle API errors gracefully with retries
  - Save research progress (don't lose 40min of work on crash)
  - Persist trades to disk (SQLite)
  
* **UX**:
  - Live progress indicators for long operations
  - Clear, readable output (no terminal clutter)
  - Intuitive command syntax with helpful error messages
  
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
- rich (terminal formatting and output)

**📚 Implementation Guides**:
- `docs/grok-agentic-guide.md` - Agentic research with streaming, multi-round patterns, citations
- `docs/polymarket-client-guide.md` - Fetch and filter markets, read-only mode for Phase 1

> **Note**: All documentation guides include a note to use Context7 MCP tool for latest information and clarification.

## 10) Data Sources

* **Polymarket API**: 
  - Fetch active polls with metadata (question, options, odds, resolution date, liquidity)
  - Filter by time-to-expiry (7, 14, 30, 180 days)
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
  prediction: str,  # which option (or "PASS")
  probability: float,  # 0-1
  confidence: float,  # 0-100
  rationale: str,
  key_findings: list[str],
  citations: list[str],
  rounds_completed: int,
  status: "pending" | "completed" | "archived",
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
- ✅ Command-based app launched with `polly` command
- ✅ `/polls [days]` - Browse Polymarket prediction polls filtered by time-to-expiry (see `docs/polymarket-client-guide.md`)
- ✅ `/research <poll_id>` - Deep multi-round Grok research to find information asymmetries (see `docs/grok-agentic-guide.md`)
- ✅ `/history [status]` - View research history with filtering (completed, pending, archived)
- ✅ `/portfolio` - View trading performance metrics (win rate, profit, APR)
- ✅ Live progress indicators during research
- ✅ Position evaluation algorithm (accuracy > frequency)
- ✅ Paper trading with fixed $100 stakes
- ✅ Hold positions until poll expiry
- ✅ Display potential payout for $100 stake
- ✅ SQLite persistence

**OUT OF SCOPE** (Future Phases):
- ❌ Real money execution
- ❌ Early position exits
- ❌ Portfolio optimization
- ❌ Multiple exchanges
- ❌ Advanced risk management
- ❌ User authentication
- ❌ Mobile/web interface
- ❌ Automated trading/position management

## 14) Configuration

**Environment Variables** (`.env`):
```
XAI_API_KEY=your_xai_api_key_here
```

**App Configuration** (`~/.polly/config.yml`):
```yaml
# Phase 1 Settings
paper_trading:
  default_stake: 100  # Fixed stake per trade

research:
  min_confidence_threshold: 70  # 0-100
  min_edge_threshold: 0.10      # 10%
  
polls:
  time_filters:                 # Available time-to-expiry filters (in days)
    - 7
    - 14
    - 30
    - 180

database:
  path: ~/.polly/trades.db      # SQLite database
```
