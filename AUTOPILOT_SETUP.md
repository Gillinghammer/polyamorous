# Autopilot Service Setup Guide

## Overview

The Polly Autopilot Service runs continuously in the background, monitoring your positions, re-researching when needed, and executing trades autonomously with your crypto wallet.

---

## Quick Start

### 1. Test Autopilot Manually

First, test the service in foreground mode:

```bash
# Make sure environment variables are set
export XAI_API_KEY="your_xai_api_key"
export POLYGON_PRIVATE_KEY="your_polygon_private_key"

# Run autopilot (will run until Ctrl+C)
python -m polly.autopilot
```

**What it does:**
- Checks wallet balance
- Monitors all active "real" mode positions
- Logs everything to `~/.polly/logs/`
- Runs trading cycle every hour (configurable in config.yml)

### 2. Run in Background

```bash
# Run as background process
nohup python -m polly.autopilot > /dev/null 2>&1 &

# Check it's running
ps aux | grep "polly.autopilot"

# View logs in real-time
tail -f ~/.polly/logs/autopilot.log
```

### 3. Monitor from CLI

While autopilot runs in background, use the CLI to monitor:

```bash
python -m polly
/autopilot status     # Check if running
/autopilot logs       # View recent logs
/portfolio            # See current positions
```

---

## Configuration

Edit `~/.polly/config.yml`:

```yaml
trading:
  mode: real                    # Must be "real" for autopilot
  price_refresh_seconds: 3600   # Check interval (3600 = 1 hour)
  
  # Your wallet settings
  chain_id: 137
  signature_type: 0
  clob_host: https://clob.polymarket.com
  polymarket_proxy_address: ""  # Leave empty for direct EOA

research:
  # Research settings for re-research
  default_rounds: 10  # Quick updates use fewer rounds
  min_confidence_threshold: 70.0
  min_edge_threshold: 0.10
```

---

## Production Deployment (Linux/macOS)

### Using Systemd

1. **Edit the service file:**

```bash
# Copy template
cp polly-autopilot.service /tmp/polly-autopilot.service

# Edit with your values
nano /tmp/polly-autopilot.service

# Replace:
# %USERNAME% with your username
# %INSTALL_PATH% with full path to polly directory
# %XAI_KEY% with your XAI API key
# %POLYGON_KEY% with your Polygon private key
# %LOG_PATH% with /home/yourusername/.polly/logs
```

2. **Install and start:**

```bash
# Copy to systemd
sudo cp /tmp/polly-autopilot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable (start on boot)
sudo systemctl enable polly-autopilot

# Start now
sudo systemctl start polly-autopilot

# Check status
sudo systemctl status polly-autopilot

# View logs
journalctl -u polly-autopilot -f
```

3. **Manage the service:**

```bash
# Stop
sudo systemctl stop polly-autopilot

# Restart
sudo systemctl restart polly-autopilot

# Disable (don't start on boot)
sudo systemctl disable polly-autopilot
```

---

## What Autopilot Does

### Every Hour (or configured interval)

**1. Check Wallet Balance**
```
💰 Available balance: $2,847.32 USDC
(Reserves $10 for gas)
```

**2. Monitor Active Positions**

For each position:
- Fetch current odds
- Calculate unrealized P&L
- Check days to expiry
- Log current state

**Future (Phase 2+):**
- Detect re-research triggers
- Re-research if needed
- Execute actions (exit/add/reduce)

**3. Risk Checks**
```
💼 Portfolio: $3,500 total ($2,847 cash, $653 in positions)
📊 Utilization: 18.7%
```

**4. Log Everything**

All actions logged to:
- `~/.polly/logs/autopilot.log` - Full details
- `~/.polly/logs/trades.log` - Trade executions
- `~/.polly/logs/errors.log` - Errors only

---

## Safety Features

### Built-in Protections

1. **Gas Reserve:** Always keeps $10 for transaction fees
2. **Position Limits:** Max 5% of portfolio per position
3. **Balance Checks:** Never tries to spend more than available
4. **Error Handling:** Continues running even if individual cycle fails
5. **Comprehensive Logging:** Can audit every decision

### Current Limitations (v1)

**Right now, autopilot ONLY monitors:**
- Checks positions every hour
- Logs current state
- Performs risk checks

**Future versions will:**
- Re-research when triggered
- Execute exits/adds/reductions
- Scan for new opportunities
- Fully automated trading

**This is intentional** - Start with monitoring, then gradually enable automated actions after testing!

---

## Logs

### Log File Locations

```bash
~/.polly/logs/
├── autopilot.log       # Everything (DEBUG level)
├── trades.log          # Trade executions only
├── errors.log          # Errors and exceptions
└── research.log        # Research summaries
```

### Example Log Output

**autopilot.log:**
```
2025-10-25 14:00:00 | INFO     | autopilot | ============================================================
2025-10-25 14:00:00 | INFO     | autopilot | Cycle 1 started
2025-10-25 14:00:00 | INFO     | autopilot | ============================================================
2025-10-25 14:00:01 | INFO     | autopilot | 💰 Available balance: $2,847.32 USDC
2025-10-25 14:00:02 | INFO     | autopilot | 📊 Monitoring 3 active position(s)...
2025-10-25 14:00:02 | INFO     | autopilot | 
2025-10-25 14:00:02 | INFO     | autopilot | ────────────────────────────────────────
2025-10-25 14:00:02 | INFO     | autopilot | Position #23: Virginia Governor - Earle-Sears
2025-10-25 14:00:03 | INFO     | autopilot |   Entry: 5.2% → Current: 5.5% (+0.3%)
2025-10-25 14:00:03 | INFO     | autopilot |   Unrealized P&L: $+8.65
2025-10-25 14:00:03 | INFO     | autopilot |   Days left: 18
2025-10-25 14:00:03 | INFO     | autopilot |   → Hold (monitoring only - actions coming soon)
```

### Viewing Logs

```bash
# Real-time view
tail -f ~/.polly/logs/autopilot.log

# Last 100 lines
tail -100 ~/.polly/logs/autopilot.log

# Search for errors
grep ERROR ~/.polly/logs/autopilot.log

# View trades only
cat ~/.polly/logs/trades.log

# From CLI
python -m polly
/autopilot logs 50
```

---

## Troubleshooting

### Service Won't Start

**Check:**
1. Environment variables set correctly
2. `POLYGON_PRIVATE_KEY` is valid
3. Network connectivity
4. Sufficient disk space for logs

**View errors:**
```bash
# If running manually
python -m polly.autopilot

# If running as service
sudo journalctl -u polly-autopilot -n 50
```

### No Active Positions

Autopilot only monitors "real" mode trades. If you have paper trades, it will show:
```
📊 No active positions to monitor
```

Create real trades via `/trade` command or wait for autopilot to enter positions (future feature).

### Balance Shows $0

**Possible causes:**
1. Trading service not initialized (check POLYGON_PRIVATE_KEY)
2. Network error fetching balance
3. Wallet actually empty

**Check manually:**
```bash
python -m polly
/portfolio  # Shows on-chain balances
```

---

## Next Steps

### Current (v1): Monitoring Only
- ✅ Runs continuously
- ✅ Checks positions every hour
- ✅ Logs everything
- ✅ Tracks unrealized P&L
- ⏳ No automated actions yet

### Coming Soon (v2): Active Management
- Re-research triggers
- Automatic exits
- Position adjustments
- New opportunity scanning

### Future (v3): Full Autopilot
- Fully automated trading
- Portfolio optimization
- Risk management
- Performance tracking

---

## Summary

**To run autopilot:**
```bash
python -m polly.autopilot
```

**To monitor:**
```bash
tail -f ~/.polly/logs/autopilot.log
```

**To control via CLI:**
```bash
python -m polly
/autopilot status
```

The service is designed to run safely and continuously, logging all activity for review!

