# PRD: CLI Market Analyst for Polymarket (Grok Agentic)

## 1) Summary

A Python command‑line tool that scans active Polymarket markets, runs autonomous Grok research (Web + X search + code execution) to estimate outcome probabilities, compares them to market odds, evaluates edge vs. a configurable risk‑free rate over time‑to‑expiry, and recommends trades. Users review transparent research with citations, accept or reject each proposed trade, and monitor P&L and positions in a clean, futuristic TUI. No web frontend. Users bring their own xAI (Grok) API key.

## 2) Goals & Non‑Goals

**Goals**

* Identify high‑quality Polymarket opportunities with enough liquidity.
* Provide explainable, cited research that leads to a model‑driven probability estimate per market.
* Compute expected value (EV) and annualized return vs. risk‑free alternative.
* Let users accept/reject each recommendation and track positions, P&L, and history in a minimalist TUI.
* Near real‑time position and price updates when feasible.

**Non‑Goals (MVP)**

* Automated trade execution/custody. MVP recommends and logs “paper” orders. (Optional execution plugin is an extension.)
* Advanced portfolio optimization beyond simple risk budgets and confidence‑weighted sizing.
* Multi‑exchange support. MVP is Polymarket only.

## 3) Users & Use Cases

**Primary user**: Individual or small fund operator who bets on prediction markets and wants a research copilot.

**Top use cases**

1. **Scan & shortlist** markets that meet liquidity and time‑left constraints.
2. **Deep‑research** a selected market via Grok Agentic tool calling until confident.
3. **Compare** model probability vs. implied odds and risk‑free APR.
4. **Decide**: accept or reject a proposed stake and side.
5. **Monitor**: see live positions, unrealized/realized P&L, and history.

## 4) High‑Level Flow

1. **Scan**: Pull active Polymarket markets, filter by liquidity thresholds.
2. **Research**: For each candidate, call Grok with a meta‑prompt to run Web Search and/or X Search. Iterate until confidence threshold or max rounds.
3. **Price & Edge**: Fetch current market odds. Compute EV, ROI to expiry, and annualized APR. Compare to risk‑free APR.
4. **Recommend**: Produce a trade suggestion (side, stake, rationale, citations, confidence) and display in TUI.
5. **Decision**: User accepts or rejects. On accept, record a “paper” trade and track position.
6. **Monitor**: Stream quotes to update positions and P&L. Persist history.

## 5) CLI/TUI Experience (Rich/Textual style)

* **Global top bar**: clock, network, positions count, total bankroll, unrealized/realized P&L.
* **Left pane**: market list (title, time left, price YES/NO, 24h vol, OI/liquidity badge).
* **Right pane**: selected market details, agentic research summary, citations list (openable via hotkey), confidence, EV, APR vs. risk‑free, suggested side/stake.
* **Action footer**: `[A] Accept  [R] Reject  [D] Details  [C] Citations  [H] History  [S] Settings`.
* **History view**: chronological trades with outcome, stake, entry price, exit (expiry) result, P&L.
* Visual style: dark, monospace, neon accents, spacious padding, clear typographic hierarchy, no ASCII noise.

## 6) Commands (Typer)

* `pm scan` — scan and rank candidate markets.
* `pm review <market_id>` — open research view, compute EV/APR, propose trade.
* `pm accept <market_id> [--stake 250] [--side yes|no]` — accept proposal or override.
* `pm positions` — live positions dashboard.
* `pm history` — trade ledger with export (`--csv`).
* `pm settings` — configure liquidity floors, risk‑free source, bankroll, sizing policy, update intervals.

## 7) Functional Requirements

### 7.1 Market ingestion & filters

* Ingest active Polymarket markets with fields: `id, slug, question, resolves_at, prices {yes,no}, volume_24h, open_interest, orderbook_depth, category`.
* **Liquidity filter** (configurable): must satisfy all of:

  * `open_interest >= MIN_OI`
  * `volume_24h >= MIN_VOL_24H`
  * `top_of_book_depth >= MIN_DEPTH` (sum on both sides within ±1% spread)
* **Time filter**: `min_hours_to_expiry <= time_left <= max_days_to_expiry`.
* Sort candidates by a score: `liquidity_score + time_weight + volatility_hint` (weights configurable).

### 7.2 Agentic research (Grok)

* Use `grok-4-fast` with server‑side tools: Web Search, X Search, Code Execution.
* **Meta‑prompt** (sketch):

  * Provide market title, description, constraints, and resolution criteria.
  * Ask Grok to:

    1. Outline key uncertainties and information needs.
    2. Run Web and/or X search in iterative rounds until confidence converges or max rounds.
    3. Produce a probability estimate `p` for YES (0–1), a confidence score `c` (0–1), and a concise, sourced rationale with citations.
    4. Return a JSON block with `{p, c, rationale, citations[]}` plus any time‑sensitive caveats.
* Enforce max rounds and time budget per market.
* Store research artifacts for audit.

### 7.3 Edge, EV, and APR vs. risk‑free

* **Implied probability** from price: `p_implied_yes = price_yes` (Polymarket $1 payout convention).
* **Edge**: `edge = p_model - p_implied_yes` (for YES; for NO use `edge_no = (1 - p_model) - price_no`).
* **ROI to expiry (YES)**: `roi = (p_model*1 + (1-p_model)*0 - price_yes) / price_yes = (p_model - price_yes)/price_yes`.
* **Annualized APR**: `apr = roi * (365 / days_to_expiry)`.
* Compare `apr` against configured **risk‑free APR** (source: configurable provider or manual input). Flag green if `apr >= rf_apr + min_spread`.

### 7.4 Sizing & decisioning

* **Confidence‑aware sizing** (two policies):

  * **Flat**: `stake = bankroll * risk_budget * c`.
  * **Scaled Kelly (optional)**: compute Kelly fraction for binary payoff, then multiply by `c` and cap by `max_fraction`.
* **Recommendation**: choose side with higher `apr` and positive EV subject to min confidence `c_min` and min edge `edge_min`.
* **User gate**: user must accept or reject. On accept, create a **paper trade** record with `market_id, side, stake, entry_price, timestamp, research_id`.

### 7.5 Positions, pricing, and P&L

* Fetch near real‑time quotes (polling or websocket if available). Update position `mark_price` and `unrealized_pnl`.
* On resolution, compute `realized_pnl` and archive.
* **Dashboard** always shows: total bankroll, cash, risk in play, unrealized P&L, realized P&L, positions table.

### 7.6 Transparency & citations

* For every recommendation, display:

  * Short rationale paragraph.
  * Top citations (open via `o` to launch in default browser).
  * Research JSON (collapsible) for audit.

### 7.7 Persistence & exports

* Use SQLite (SQLModel) for `markets, research, proposals, trades, positions, fills, prices`.
* `pm history --csv` exports trades with research linkage.

## 8) Non‑Functional Requirements

* **Performance**: scan + initial research on 5–10 markets within a target runtime budget.
* **Resilience**: handle transient API errors with retries and backoff.
* **Security**: API keys loaded from env or local config file, never logged. No user auth system.
* **Observability**: structured logs with levels; optional debugging view that streams Grok tool‑call notifications.
* **Compliance**: clear “not investment advice” notice; user is responsible for execution and risk.

## 9) Tech Stack

* Python 3.11+
* Libraries: `typer` (CLI), `textual` or `rich` (TUI), `httpx` (async API), `pydantic`, `sqlmodel` (SQLite), `tenacity` (retries).
* xAI: `xai_sdk>=1.3.1`, model `grok-4-fast`, tools `web_search`, `x_search`, `code_execution`.
* Optional: `websockets` if Polymarket provides a stream.

## 10) Integrations

* **Polymarket data**: public market list, prices, OI, 24h volume, orderbook depth. (Exact endpoints encapsulated in an adapter.)
* **Risk‑free source**: configurable (e.g., 4‑week bill). Fallback manual APR in settings.
* **Open URL**: platform‑agnostic open command for citations.

## 11) Data Model (sketch)

* `Market(id, slug, title, resolves_at, price_yes, price_no, oi, vol24h, depth, category)`
* `Research(id, market_id, p, c, rationale, citations[], rounds, created_at)`
* `Proposal(id, market_id, side, stake, edge, apr, rf_apr, accepted, created_at)`
* `Trade(id, market_id, side, stake, entry_price, timestamp, research_id)`
* `Position(id, market_id, side, stake, entry_price, mark_price, unrealized_pnl, status)`
* `Fill(id, trade_id, price, qty, timestamp)` (reserved for future execution plugin)
* `PriceTick(market_id, price_yes, price_no, ts)`

## 12) Example Meta‑Prompt (condensed)

> You are an analyst estimating the probability of the **YES** outcome for a Polymarket market. Use Web Search and X Search tools in iterative rounds. Identify key uncertainties, gather recent, credible sources, and avoid stale info. Return JSON with fields: `p` (0–1), `c` (0–1), `rationale` (<= 8 sentences), `citations` (list of URLs). If confidence is low, explain blockers and stop early.

System appends: market title, resolution criteria, time to expiry, recent price history snapshot.

## 13) Sample Screens (ASCII)

```
┌────────────────────────────────── CLI Analyst ──────────────────────────────────┐
│  21:04  •  Bankroll: $50,000  •  In‑Play: $3,750  •  UPNL: +$420  •  RPNL: $0  │
├──────────────────── Markets (filtered) ───────────────────┬─────────────────────┤
│ [A] Election X leads?        T‑3d  YES 0.62  OI $1.2M   │ EV: +0.06  APR: 58% │
│ [B] CPI > 3.2% Nov?          T‑11d YES 0.44  OI $0.6M   │ Conf: 0.72          │
│ [C] Company Y acquires Z?    T‑27d YES 0.31  OI $0.3M   │ Risk‑free: 4.8% APR │
├────────────────── Selected: [A] Election X leads? ──────────────────────────────┤
│ p=0.68  c=0.70  price_yes=0.62  edge=+0.06  roi=+9.7%  apr=+118%              │
│ Rationale: Recent polls from ...; turnout models ...; swing state updates ...  │
│ Citations: [1] https://...  [2] https://x.com/...  [3] https://...             │
├──────────────────────────────── Actions ────────────────────────────────────────┤
│ [A] Accept (stake $350)   [R] Reject   [D] Details   [C] Open citations         │
└────────────────────────────────────────────────────────────────────────────────┘
```

## 14) Configuration

`~/.pm_analyst/config.yml`

```yaml
xai_api_key_env: XAI_API_KEY
risk_free_apr: 0.048          # fallback if provider disabled
risk_free_provider: treasury   # treasury|manual
liquidity:
  min_oi: 200000
  min_vol24h: 50000
  min_depth: 10000
research:
  max_rounds: 4
  min_confidence: 0.6
  min_edge: 0.03
sizing:
  policy: flat                 # flat|kelly
  bankroll: 50000
  risk_budget: 0.02            # 2% per trade before confidence
  max_fraction: 0.05           # cap for kelly
updates:
  quotes_interval_se
```
≈
