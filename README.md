# Poly - TUI Polymarket Research & Paper Trading

A Python TUI (Terminal User Interface) application for researching Polymarket polls and making informed predictions with paper trading.

## Quick Start

### Installation

```bash
# Install in editable mode with all dependencies
pip install -e .
```

### Configuration (Optional)

Set up your xAI API key for Grok research:

```bash
export XAI_API_KEY="your_xai_api_key_here"
```

Or create a `.env` file in the project root:
```
XAI_API_KEY=your_xai_api_key_here
```

> **Note**: The app works without an API key using offline sample data and simulated research.

### Run

```bash
poly
```

Or:

```bash
python -m poly
```

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

