# Portfolio Optimization for Multi-Outcome Markets

## Overview

Your group research now supports **sophisticated portfolio-level optimization** with varying position sizes across multiple candidates to create optimal hedge strategies.

---

## How It Works

### 1. Research Analyzes Full Portfolio

When researching a grouped event (e.g., "2028 Presidential Nominee"), the AI:

- Analyzes ALL viable candidates
- Identifies undervalued opportunities
- Calculates optimal position sizing
- Recommends 1-5 positions with varying stakes
- Explains how positions work together as a hedge

### 2. Varying Position Sizes

Instead of uniform $100 stakes, research now recommends:

**Example Strategy for $500 budget:**
```
Position 1: Primary Pick (largest edge)    → $300 (60% of portfolio)
Position 2: Hedge Pick (moderate edge)     → $150 (30% of portfolio)  
Position 3: Value Longshot (small edge)    → $50  (10% of portfolio)
```

**Why this is better:**
- Allocates more capital to higher-confidence positions
- Reduces variance through diversification
- Maintains positive EV across portfolio
- Uses Kelly criterion-style optimal sizing

### 3. Combined EV Calculation

The system calculates:
- Individual EV for each position
- Combined portfolio EV
- Risk-adjusted returns
- Portfolio allocation percentages

---

## Updated Data Model

### MarketRecommendation
```python
@dataclass
class MarketRecommendation:
    market_id: str
    market_question: str
    prediction: str                  # "Yes" or "No"
    probability: float               # Your assessed probability
    confidence: float
    rationale: str
    entry_suggested: bool
    suggested_stake: float = 100.0   # ← NEW: Varying stake amounts
```

---

## Enhanced Research Prompt

The group research prompt now includes:

### Portfolio Optimization Section
```
PORTFOLIO OPTIMIZATION: You should recommend positions on MULTIPLE candidates (1-5) when:
- There are multiple viable contenders → hedge reduces variance
- You find undervalued candidates with positive EV
- Combined positions improve risk-adjusted returns

POSITION SIZING: Allocate capital proportionally based on:
- Edge size (probability vs market odds)
- Confidence level
- Liquidity available
- Kelly criterion or similar for optimal sizing

Example strategy: If total budget is $500:
- Primary pick (60% edge): $300 stake
- Hedge pick (20% edge): $150 stake  
- Value longshot (10% edge): $50 stake
This diversifies risk while maintaining positive EV.
```

### JSON Output Format
```json
{
  "prediction": "Catherine Connolly",
  "probability": 0.95,
  "confidence": 85,
  "rationale": "Overall strategy explanation...",
  "key_findings": ["...", "..."],
  "recommendations": [
    {
      "market_id": "0x123...",
      "market_question": "Will Catherine Connolly win?",
      "prediction": "Yes",
      "probability": 0.95,
      "confidence": 85,
      "rationale": "Clear frontrunner...",
      "entry_suggested": true,
      "suggested_stake": 300.0
    },
    {
      "market_id": "0x456...",
      "market_question": "Will Heather Humphreys win?",
      "prediction": "Yes", 
      "probability": 0.15,
      "confidence": 60,
      "rationale": "Undervalued hedge...",
      "entry_suggested": true,
      "suggested_stake": 150.0
    },
    {
      "market_id": "0x789...",
      "market_question": "Will Conor McGregor win?",
      "prediction": "Yes",
      "probability": 0.05,
      "confidence": 40,
      "rationale": "Value longshot with upside...",
      "entry_suggested": true,
      "suggested_stake": 50.0
    }
  ]
}
```

---

## Display Example

When research completes, you'll see:

```
╭─────────────────────────────────────────────────────────╮
│ Group Research Results                                  │
├─────────────────────────────────────────────────────────┤
│ Event: Ireland Presidential Election                    │
│ Total Markets: 29                                       │
│                                                         │
│ RECOMMENDATIONS (3 positions):                          │
│ Total portfolio allocation: $500                        │
│                                                         │
│ 1. Catherine Connolly - Yes                            │
│    Win Probability: 95.0% | Current Odds: 95.5% | Confidence: 85%
│    ✓ ENTER: $300 (60% of portfolio)                    │
│    Expected Value: +$14.00                              │
│    Clear frontrunner with institutional backing...      │
│                                                         │
│ 2. Heather Humphreys - Yes                             │
│    Win Probability: 15.0% | Current Odds: 4.1% | Confidence: 60%
│    ✓ ENTER: $150 (30% of portfolio)                    │
│    Expected Value: +$400.00                             │
│    Significantly undervalued, strong second choice...   │
│                                                         │
│ 3. Conor McGregor - Yes                                │
│    Win Probability: 5.0% | Current Odds: 0.1% | Confidence: 40%
│    ✓ ENTER: $50 (10% of portfolio)                     │
│    Expected Value: +$2,450.00                           │
│    Massive upside if celebrity appeal matters...        │
│                                                         │
│ Overall Analysis:                                       │
│ Strategy combines safe bet on frontrunner with         │
│ calculated hedges on undervalued alternatives...        │
╰─────────────────────────────────────────────────────────╯

Research suggests 3 position(s):
Portfolio-optimized strategy with varying position sizes:

  1. Catherine Connolly Yes @ 95.5%
     Stake: $300 (60% of portfolio)
     Potential: $314 | EV: +$14.00

  2. Heather Humphreys Yes @ 4.1%
     Stake: $150 (30% of portfolio)
     Potential: $3,658 | EV: +$400.00

  3. Conor McGregor Yes @ 0.1%
     Stake: $50 (10% of portfolio)
     Potential: $50,000 | EV: +$2,450.00

Portfolio Summary:
  Total Stake: $500
  Combined EV: +$2,864.00
  Strategy: Diversified hedge across 3 positions
```

---

## Benefits

### 1. Risk Management
- Hedges against prediction uncertainty
- Reduces variance through diversification
- Multiple ways to win

### 2. Capital Efficiency
- Allocates more to high-confidence picks
- Smaller bets on longshots with asymmetric upside
- Follows modern portfolio theory

### 3. EV Maximization
- Doesn't just pick the favorite
- Finds undervalued candidates
- Combined EV often higher than single bet

### 4. Realistic Strategy
- Matches how professional traders operate
- Accounts for uncertainty
- Balances risk and reward

---

## How Research Makes Decisions

### Position Sizing Logic

The AI is prompted to use:

1. **Kelly Criterion-style sizing:**
   - Larger stakes for bigger edges
   - Scale by confidence level
   - Consider liquidity constraints

2. **Portfolio allocation:**
   - Primary pick: 40-70% of budget
   - Secondary positions: 15-30% each
   - Longshots: 5-15% each
   - Total: ~100% of allocated budget

3. **Edge-based weighting:**
   - High edge + high confidence = large stake
   - Moderate edge + moderate confidence = medium stake  
   - Small edge + lower confidence = small stake

---

## Implementation Details

### Updated Components

**MarketRecommendation** (`polly/models.py`):
- Added `suggested_stake: float` field

**Research Prompt** (`polly/services/research.py`):
- Portfolio optimization section
- Position sizing guidance
- Multi-position examples
- Clearer JSON output format

**Evaluator** (`polly/services/evaluator.py`):
- Uses `rec.suggested_stake` instead of fixed $100
- Calculates portfolio-level metrics
- Returns `portfolio_pct` for each position

**Display** (`polly/commands/research.py`):
- Shows varying stake amounts
- Displays portfolio percentages
- Shows individual and combined EV
- Explains strategy composition

---

## Example Use Cases

### Scenario 1: Clear Favorite with Hedge
```
Event: Ireland Presidential Election
Research finds: Catherine Connolly 95% likely

Strategy:
- $400 on Connolly (primary)
- $100 on Humphreys (hedge against upset)
Total: $500, Combined EV: +$450
```

### Scenario 2: Uncertain Race
```
Event: 2028 Democratic Nominee
Research finds: 3 viable candidates

Strategy:
- $250 on Whitmer (35% prob, highest edge)
- $200 on Newsom (30% prob, good hedge)
- $50 on Harris (15% prob, value play)
Total: $500, Combined EV: +$180
```

### Scenario 3: Longshot Value Play
```
Event: Next CEO of X
Research finds: Market mispricing on specific candidate

Strategy:
- $100 on Susan Wojcicki (market underpriced 2:1)
- $50 on dark horse (massive asymmetric upside)
Total: $150, Combined EV: +$200
```

---

## Testing the New Capability

Run group research on a multi-outcome event:

```bash
python -m polly
/polls election
/research 1
```

**The AI will now:**
1. Analyze all candidates thoroughly
2. Calculate optimal position sizes
3. Recommend 1-5 positions with varying stakes
4. Show combined portfolio EV
5. Explain the hedge strategy

**You'll see output like:**
```
Portfolio Summary:
  Total Stake: $500
  Combined EV: +$2,864.00
  Strategy: Diversified hedge across 3 positions
```

Instead of just "Bet $100 on the favorite"!

---

## Autopilot Implications

This portfolio optimization approach is **perfect for autopilot** because:

- ✅ Automatically diversifies risk
- ✅ Optimizes capital allocation
- ✅ Finds multi-position arbitrage opportunities
- ✅ Reduces impact of any single prediction error
- ✅ Maximizes long-term Kelly growth rate

When you eventually enable autopilot, it can:
1. Research multiple events simultaneously
2. Build diversified portfolio across events
3. Allocate capital optimally across all opportunities
4. Rebalance as odds change
5. Exit positions strategically

---

## Summary

Your Polly app now has **institutional-grade portfolio optimization** for multi-outcome markets:

✅ Varying position sizes based on edge and confidence  
✅ Multi-position hedge strategies  
✅ Combined EV calculation  
✅ Portfolio-level thinking  
✅ Risk management through diversification  
✅ Capital efficiency optimization  

This is exactly what you need for serious prediction market trading! 🎯

