# PM Analyst

Prototype CLI for researching Polymarket opportunities using an agentic Grok workflow.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# show available commands
pm --help
```

Place your xAI API key in the environment (defaults to `XAI_API_KEY`).

## Key commands

| Command | Description |
| --- | --- |
| `pm scan` | Pull and rank Polymarket markets that pass liquidity screens, persisting the snapshot locally. |
| `pm review <market_id>` | Run Grok research against a market, evaluate edge/ROI, and generate a proposal when thresholds are met. |
| `pm accept <market_id>` | Accept the latest proposal for a market, recording a paper trade and updating positions. |
| `pm positions` | Display open positions with mark pricing and unrealized P&L. |
| `pm history [--csv path]` | Render the trade ledger or export to CSV. |
| `pm settings` | Print the resolved configuration, including thresholds and sizing policy. |

Refer to `docs/plan.md` and `prd.md` for requirements and implementation details.
