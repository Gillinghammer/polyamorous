# Poly - TUI Polymarket Research & Paper Trading

A Python TUI (Terminal User Interface) application for researching Polymarket polls and making informed predictions with paper trading.

## Quick Start

### Installation

```bash
pip install -e .
```

### Configuration (Required)

Set your xAI API key for Grok research:

```bash
export XAI_API_KEY="your_xai_api_key_here"
```

### Initialize and Ingest

```bash
python -m polly init --starting-balance 10000
python -m polly ingest --open-only
```

### Run

```bash
python -m polly run
```

### Agent Settings

```bash
# View settings
python -m polly settings
# Enable agent and set window days
python -m polly settings --agent-enabled 1 --agent-window-days 3
# Run agent once (idempotent)
python -m polly agent-run
```

### Resolve Closed Markets

```bash
python -m polly resolve
```

## Notes

- Uses official Polymarket REST for market data
- Paper trading only; gateway designed for future real trading
- SQLite DB path: `~/.config/polly/polly.db`

## Features

- ✅ Display top 20 most liquid Polymarket polls (excluding sports)
- ✅ Deep multi-round agentic research using Grok 4 (Web + X search)
- ✅ Live progress indicators during research (20-40 minutes)
- ✅ Position evaluation algorithm (accuracy over frequency)
- ✅ Paper trading with fixed stakes
- ✅ Dashboard with win rate, profit, and projected APR metrics
- ✅ SQLite persistence for trades

## Navigation

- `Tab`/`Shift+Tab`: Switch between views
- `Arrow keys`: Navigate lists
- `Enter`: Select/Confirm
- `Esc`: Go back
- `q`: Quit application
- `r`: Refresh markets

## Views

1. **Polls** - Browse top liquid non-sports polls
2. **Research** - View research progress and findings
3. **Decision** - Review recommendations and enter/pass trades
4. **Dashboard** - Track performance metrics

## Configuration

Default config location: `~/.poly/config.yml`

```yaml
# App Configuration (~/.poly/config.yml)
paper_trading:
  default_stake: 100

research:
  # Thresholds
  min_confidence_threshold: 70     # 0-100
  min_edge_threshold: 0.10         # 10%
  # Depth & model
  model_name: grok-4-fast
  default_rounds: 20               # deep research (20–40 minutes)
  # Tools
  enable_code_execution: true      # use for quantitative checks
  enable_image_understanding: true
  enable_video_understanding: true
  # Cost estimation (USD per 1K tokens)
  prompt_token_price_per_1k: 0.0
  completion_token_price_per_1k: 0.0
  reasoning_token_price_per_1k: 0.0

polls:
  top_n: 20
  exclude_categories:
    - sports
    - esports
  liquidity_weight:
    open_interest: 0.7
    volume_24h: 0.3

database:
  path: ~/.poly/trades.db
```

## Tech Stack

- **Python 3.11+**
- **Textual 0.40+** - TUI framework
- **py-clob-client** - Polymarket API
- **xai-sdk** - Grok 4 research
- **SQLite** - Data persistence

## Development

### Testing

```bash
# Verify Python syntax
python -m compileall poly

# Run the app
python -m poly
```

## Documentation

- [`prd.md`](prd.md) - Complete product requirements
- [`AGENTS.md`](AGENTS.md) - Agent guidelines for contributors
- [`docs/textual-guide.md`](docs/textual-guide.md) - TUI framework patterns
- [`docs/grok-agentic-guide.md`](docs/grok-agentic-guide.md) - Agentic research implementation
- [`docs/polymarket-client-guide.md`](docs/polymarket-client-guide.md) - Market data fetching

## Phase 1 Scope

**IN SCOPE**:
- Paper trading only (no real money)
- Hold positions until poll expiry
- Top 20 liquid non-sports polls
- Deep multi-round Grok research
- Dashboard metrics

**OUT OF SCOPE**:
- Real money execution
- Early position exits
- Sports betting
- Portfolio optimization
- Multi-exchange support

---

Built with ❤️ for prediction market traders seeking asymmetric information advantages.


