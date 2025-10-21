# Polly Quickstart Guide

## Installation

1. **Set your xAI API key**:
   ```bash
   export XAI_API_KEY='your_api_key_here'
   ```
   
   Or create `.env` file:
   ```bash
   echo "XAI_API_KEY=your_api_key_here" > .env
   ```

2. **(Optional) For Real Trading - Add Polygon Private Key**:
   ```bash
   echo "POLYGON_PRIVATE_KEY=your_polygon_private_key_here" >> .env
   ```
   ⚠️ **Security**: Keep your `.env` file private! Never commit it to git.

3. **Install Polly**:
   ```bash
   pip install -e .
   ```

4. **Launch**:
   ```bash
   polly
   ```

## Quick Commands

```bash
# Browse markets
/polls              # All markets (sorted by expiry)
/polls 7            # Markets expiring in 7 days
/polls politics     # Markets in "politics" category
/polls bitcoin      # Markets mentioning "bitcoin"
/polls 7 bitcoin    # Markets expiring in 7 days with "bitcoin"

# Research a market
/research 1         # Research poll #1 from list

# View your portfolio
/portfolio

# View research history
/history

# Manual trading (real mode only)
/trade 5 Yes 100    # Trade $100 on "Yes" for market #5
/close 12           # Close trade #12

# Get help
/help

# Exit
/exit
```

## Command History

**Navigation:**
- Press **Up/Down** arrows to cycle through previous commands
- Press **Ctrl+R** for reverse search
- Type a prefix (e.g., `/p`) then press **Up** to filter by prefix

**Example:**
```bash
polly> /polls bitcoin
polly> /portfolio  
polly> /p          # Type /p then press Up
# Shows: /polls bitcoin (last command starting with /p)
```

History is saved to `~/.polly/history.txt` and persists across sessions.

## Trading Modes

### Paper Trading (Default)
- No real money required
- Perfect for testing and learning
- Simulated trades tracked locally

### Real Trading (Phase 2)
- Execute actual trades on Polymarket
- Requires: Polygon wallet private key + USDC balance
- Enable by editing `~/.polly/config.yml`:
  ```yaml
  trading:
    mode: real  # Change from "paper" to "real"
  ```
- ⚠️ **Always test with paper trading first!**

## First Time Setup

On first launch, Polly will:
- Check for XAI_API_KEY
- Create `~/.polly/config.yml` with default settings
- Create `~/.polly/trades.db` for data storage

## Configuration

Edit `~/.polly/config.yml` to customize:

```yaml
research:
  min_confidence_threshold: 70    # Min confidence to recommend trade
  min_edge_threshold: 0.10        # Min edge over market (10%)
  default_rounds: 20              # Research depth

trading:
  mode: paper                     # "paper" or "real"
  default_stake: 100              # Stake per trade
  starting_cash: 10000            # Starting balance
  chain_id: 137                   # Polygon network (for real trading)
```

## Typical Workflow

1. **Browse markets**: `/polls 7` to see markets ending soon
2. **Pick interesting poll**: Note the poll ID
3. **Deep research**: `/research 3` (takes 20-40 min)
4. **Review recommendation**: ENTER or PASS
5. **Accept trade**: Type `y` if you agree with ENTER recommendation
6. **Track performance**: `/portfolio` to see your results

## Data Location

- Config: `~/.polly/config.yml`
- Database: `~/.polly/trades.db`
- Research results and trades persist across sessions

## Troubleshooting

**"XAI_API_KEY not set"**
- Set environment variable or create `.env` file

**"No module named polly"**
- Run `pip install -e .` from project root

**"Poll not in cache"**
- Run `/polls` first before `/research`

## What's Next?

- Run `/polls` to see available markets
- Try `/research` on a market that interests you
- Check `/portfolio` after you have some trades
- Use `/history` to review past research

Enjoy trading! 📊

