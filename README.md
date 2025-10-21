# Polly - Polymarket Research & Paper Trading

A command-based application for researching Polymarket prediction markets using deep AI analysis (Grok 4) and tracking paper trades.

## Features

- **Browse Polls**: Fetch and filter Polymarket markets by time-to-expiry
- **Deep Research**: Run multi-round AI research (20-40 min) using Grok 4 with Web + X search
- **Position Evaluation**: Algorithmic evaluation of whether current odds justify taking a position
- **Paper Trading**: Track hypothetical trades with performance metrics
- **Research History**: View past research and recommendations
- **Portfolio Analytics**: Win rate, profit metrics, and projected APR

## Installation

### Prerequisites

- Python 3.11+
- xAI API Key (get from [console.x.ai](https://console.x.ai/))

### Setup

1. Clone this repository:
```bash
git clone <repository-url>
cd polyamorous
```

2. Install the package:
```bash
pip install -e .
```

3. Set your xAI API key:
```bash
export XAI_API_KEY='your_api_key_here'
```

Or create a `.env` file:
```bash
echo "XAI_API_KEY=your_api_key_here" > .env
```

## Usage

### Launch Polly

```bash
polly
```

Or run as a module:
```bash
python -m polly
```

### Available Commands

Once launched, use these commands:

#### Browse Polls
```bash
polly> /polls              # Show all polls (sorted by expiry date)
polly> /polls 7            # Polls ending in 7 days
polly> /polls politics     # Polls in "politics" category
polly> /polls bitcoin      # Polls mentioning "bitcoin"
polly> /polls 7 bitcoin    # Polls ending in 7 days mentioning "bitcoin"
polly> /polls 14 trump     # Polls ending in 14 days mentioning "trump"
```

Search terms match against poll question, category, description, and tags (case-insensitive).

#### Research a Poll
```bash
polly> /research <poll_id>  # Run deep research (20-40 minutes)
```

Example:
```bash
polly> /polls 7            # See available polls
polly> /research 1         # Research poll #1 from the list
```

#### View Research History
```bash
polly> /history              # Show all research
polly> /history completed    # Research with recommendations
polly> /history pending      # Research not yet completed
polly> /history archived     # Polls that have resolved
```

#### View Portfolio
```bash
polly> /portfolio           # Show performance metrics and active positions
```

#### Help
```bash
polly> /help               # Show command reference
```

#### Exit
```bash
polly> /exit               # Quit Polly
```

## Command History

Polly includes advanced command history features powered by `prompt_toolkit`:

### Navigation
- **Up/Down Arrows**: Cycle through previous commands
- **Ctrl+R**: Reverse search through history
- **Prefix Search**: Type part of a command (e.g., `/p`) then press Up to find the last command starting with `/p`

### Examples
```bash
polly> /polls bitcoin    # Run command
polly> /portfolio        # Run another command
polly> /p                # Type /p
# Press Up → shows "/polls bitcoin" (last command starting with /p)
# Press Up again → shows any other commands starting with /p
```

### History Storage
- Saved to `~/.polly/history.txt`
- Persists across sessions
- Unlimited history entries

## Configuration

Polly creates a config file at `~/.polly/config.yml` on first run. Customize settings:

```yaml
research:
  min_confidence_threshold: 70    # Minimum confidence to recommend entry (0-100)
  min_edge_threshold: 0.10        # Minimum edge over market odds (10%)
  model_name: "grok-4-fast"       # Grok model to use
  default_rounds: 20              # Number of research rounds

paper_trading:
  default_stake: 100              # Fixed stake per trade ($)
  starting_cash: 10000            # Initial paper trading balance ($)

polls:
  top_n: 20                       # Number of polls to display
  exclude_categories:             # Categories to filter out
    - sports
    - esports

database:
  path: ~/.polly/trades.db        # SQLite database location
```

## How It Works

### Research Flow

1. **Meta Planning**: Grok identifies key topics/questions to research
2. **Multi-Round Research**: Uses Web Search and X Search to gather information
3. **Synthesis**: Converts findings into probability estimates
4. **Evaluation**: Compares predicted odds vs market odds to calculate edge
5. **Recommendation**: Enter position if confidence and edge thresholds met

### Position Evaluation Algorithm

```python
# Calculate expected value
EV = (predicted_prob * payout) - (1 - predicted_prob) * stake

# Calculate edge vs market
edge = predicted_prob - implied_prob_from_odds

# Adjust for confidence
adjusted_edge = edge * (confidence / 100)

# Recommend ENTER if:
# - adjusted_edge > min_threshold (e.g., 10%)
# - confidence > min_confidence (e.g., 70%)
# - EV > 0
```

### Paper Trading

- Fixed stake per trade (default: $100)
- Positions held until poll expiry (no early exits in Phase 1)
- Automatic P&L calculation on resolution
- Performance tracking: win rate, total profit, projected APR

## Example Session

```bash
$ polly

╔═══════════════════════════════════════════════╗
║   ██████╗  ██████╗ ██╗     ██╗  ██╗   ██╗    ║
║   ██╔══██╗██╔═══██╗██║     ██║  ╚██╗ ██╔╝    ║
║   ██████╔╝██║   ██║██║     ██║   ╚████╔╝     ║
║   ██╔═══╝ ██║   ██║██║     ██║    ╚██╔╝      ║
║   ██║     ╚██████╔╝███████╗███████╗██║       ║
║   ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝       ║
║                                               ║
║   Polymarket Research & Paper Trading         ║
╚═══════════════════════════════════════════════╝

Welcome! Type /help to see available commands.

polly> /polls 7
Fetching markets from Polymarket...

┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
║ ID ║ Question                  ║ Odds          ║ Expires  ║ Liquidity ║
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ 1  │ Will Senate pass bill?    │ Yes: 58%...   │ 6d 14h   │ $1,250... │
└────┴───────────────────────────┴───────────────┴──────────┴───────────┘

polly> /research 1
Researching: Will Senate pass bill?
Starting deep research... This may take 20-40 minutes.

[Research progress updates...]

✓ Research completed!

[Research results panel with prediction, confidence, rationale...]

RECOMMENDATION: ENTER
Bet on: Yes at 58%
Potential payout for $100: $172.41 (+72%)

Enter trade with $100 stake? (y/n): y

✓ Trade recorded! Position ID: 1
```

## Project Structure

```
polly/
├── __init__.py
├── __main__.py          # Entry point
├── cli.py               # Command loop and routing
├── config.py            # Configuration management
├── models.py            # Data models
├── commands/            # Command handlers
│   ├── polls.py
│   ├── research.py
│   ├── history.py
│   ├── portfolio.py
│   └── help.py
├── services/            # Business logic
│   ├── polymarket.py    # Market data fetching
│   ├── research.py      # Grok research orchestration
│   └── evaluator.py     # Position evaluation
├── storage/             # Data persistence
│   ├── trades.py        # Trade repository (SQLite)
│   └── research.py      # Research repository (SQLite)
└── ui/                  # Terminal formatting
    ├── banner.py        # ASCII art
    └── formatters.py    # Rich formatting helpers
```

## Documentation

See the `docs/` folder for detailed implementation guides:
- `grok-agentic-guide.md` - Agentic research patterns
- `polymarket-client-guide.md` - Market data fetching

## Troubleshooting

### API Key Not Found
```
Error: XAI_API_KEY environment variable not set.
```
**Solution**: Set your xAI API key in `.env` or export as environment variable.

### Import Errors
```
ModuleNotFoundError: No module named 'polly'
```
**Solution**: Install the package with `pip install -e .`

### Database Locked
```
Error: database is locked
```
**Solution**: Ensure no other Polly instances are running. If persists, remove `~/.polly/trades.db` (will lose trade history).

## Phase 1 Limitations

- Paper trading only (no real money)
- Positions held until expiry (no early exits)
- Fixed stake per trade
- No portfolio optimization
- Command-line interface only

## Contributing

This is a personal project. See `prd.md` for product requirements and roadmap.

## License

See LICENSE file.
