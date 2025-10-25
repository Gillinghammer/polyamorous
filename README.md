# Polly - Polymarket Research & Trading CLI

A command-line application for researching Polymarket prediction markets and executing informed trading strategies using deep AI-powered research.

## Overview

Polly helps you find edge in prediction markets through:
- **Deep Research**: Multi-round AI research using Grok 4 to find information asymmetries
- **Smart Trading**: Paper and real trading with position evaluation algorithms
- **Multi-Outcome Support**: Handle both binary markets and grouped multi-outcome events
- **Portfolio Tracking**: Monitor positions, P&L, and strategy performance

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure your API key
export XAI_API_KEY="your_xai_api_key_here"

# Launch the app
python -m polly
```

## Core Commands

- `/polls` - Browse available markets (binary + grouped events)
- `/research <id>` - Run deep research on a market or event
- `/portfolio` - View active positions and performance
- `/history` - View past research and trades
- `/help` - Show all commands

## Architecture

- **Multi-Outcome Support**: Events with multiple markets (e.g., "2028 Presidential Nominee" with 128 candidates) are treated as grouped events
- **Strategy-Aware**: Research can recommend multiple correlated positions for hedging or improved EV
- **Autopilot-Ready**: Architecture designed for future automated trading

## Documentation

- **`prd.md`** - Complete product requirements and implementation plan
- **`docs/grok-agentic-guide.md`** - AI research implementation guide
- **`docs/polymarket-client-guide.md`** - Market data fetching guide

## Current Status

✅ **Phase 1 Complete**: Binary market research & paper trading
🚧 **Phase 2 In Progress**: Multi-outcome market support (see prd.md Section 15)

## Tech Stack

- Python 3.11+
- xAI Grok 4 (research)
- Polymarket Gamma API (market data)
- SQLite (persistence)
- Rich (UI)

## Contributing

See `prd.md` for the full implementation plan and roadmap.
