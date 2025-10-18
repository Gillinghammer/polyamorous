# Implementation Plan for CLI Market Analyst

## 1. Architecture Overview
- **Command Interface**: Typer-powered CLI entry point `pm` with subcommands defined in `pm_analyst.cli`.
- **Services Layer**:
  - `PolymarketClient` for fetching and filtering market data (initially from bundled sample feed, future HTTP integration).
  - `ResearchOrchestrator` for coordinating Grok research runs (stubbed deterministic output for offline use, pluggable for real API).
  - `RiskEngine` for EV/APR calculations and sizing recommendations.
  - `Persistence` module using SQLModel + SQLite for markets, research, proposals, trades, positions.
- **TUI Rendering**: Rich-based layouts in `pm_analyst.tui` to render scan/review dashboards with a dark neon style.
- **Configuration**: YAML-driven settings with environment overrides, default path `~/.pm_analyst/config.yml`.
- **Utilities**: Logging helpers, environment management, citation opening.

## 2. Project Structure
```
polyamorous/
├── data/
│   └── sample_markets.json               # offline fixtures for scan/testing
├── docs/
│   └── plan.md                           # this implementation guide
├── pm_analyst/
│   ├── __init__.py
│   ├── __main__.py                       # enables `python -m pm_analyst`
│   ├── cli.py                            # Typer CLI commands
│   ├── config.py                         # settings loading + defaults
│   ├── logging.py                        # structured logging setup
│   ├── models/
│   │   ├── __init__.py
│   │   └── db.py                         # SQLModel definitions
│   ├── services/
│   │   ├── calculations.py               # EV/APR logic
│   │   ├── persistence.py                # Session manager + CRUD helpers
│   │   ├── polymarket.py                 # Market ingestion + filters
│   │   └── research.py                   # Grok orchestration stubs
│   ├── tui/
│   │   ├── __init__.py
│   │   └── views.py                      # Rich renderers for scan/review
│   └── utils/
│       └── paths.py                      # filesystem helpers
├── prd.md
└── pyproject.toml
```

## 3. Milestones & Tasks

1. **Foundation Setup**
   - Initialize Python project with `pyproject.toml` (typer, rich, sqlmodel, httpx, pydantic, tenacity).
   - Implement logging + configuration modules.
2. **Data Layer**
   - Define SQLModel tables for Markets, Research, Proposals, Trades, Positions, PriceTicks.
   - Provide migration/init helper to bootstrap SQLite file.
3. **Service Layer**
   - `PolymarketClient`: load sample data, apply liquidity/time filters, scoring.
   - `ResearchOrchestrator`: deterministic stub returning probability, rationale, citations; structured response models.
   - `RiskEngine`: compute edge, ROI, APR, stake suggestions.
4. **CLI Commands**
   - `scan` lists ranked markets.
   - `review` shows research summary + metrics in TUI layout.
   - `accept` records paper trade with computed metrics.
   - `positions` and `history` display stored records.
   - `settings` prints active config and instructions.
5. **TUI Rendering**
   - Build Rich layouts for dashboards with neon accent theme.
6. **Sample Data & Docs**
   - Provide `data/sample_markets.json` for offline run.
   - Document usage and assumptions in `docs/plan.md` (this file) and CLI help strings.
7. **Testing & Validation**
   - Ensure CLI commands run using sample data.
   - Provide instructions for hooking up live APIs later.

## 4. Risk & Mitigation
- **External API Dependencies**: Use fixture-driven simulation to avoid network reliance while keeping interfaces ready for live integration.
- **State Management**: Centralize DB session handling with context managers to prevent locking issues.
- **Configuration Drift**: Validate YAML schema with Pydantic models and fallback to defaults.

## 5. Next Steps
- Implement modules per structure above.
- Populate CLI commands and connect components.
- Expand stubs into production-ready integrations in subsequent iterations.
