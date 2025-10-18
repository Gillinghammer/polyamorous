# Setup Guide for Poly TUI

## Current Status ✅

The project is successfully installed and ready to run!

## Quick Run

You have multiple Python installations on your system. The app is installed to Homebrew's Python 3.11.12.

### Option 1: Use the installed `poly` command

```bash
# The poly command is installed at /opt/homebrew/bin/poly
poly
```

### Option 2: Run as Python module

```bash
# Use the Homebrew Python directly
/opt/homebrew/bin/python3.11 -m poly
```

### Option 3: Create an alias (recommended)

Add this to your `~/.zshrc`:

```bash
alias poly="/opt/homebrew/bin/python3.11 -m poly"
```

Then:
```bash
source ~/.zshrc
poly
```

## System Configuration

**Installed Dependencies:**
- ✅ textual 6.3.0 (TUI framework)
- ✅ py-clob-client 0.25.0 (Polymarket API)
- ✅ xai-sdk 1.3.1 (Grok research)
- ✅ All supporting packages

**Python Environments:**
- Anaconda Python 3.11.7 at `/opt/anaconda3/bin/python`
- Homebrew Python 3.11.12 at `/opt/homebrew/bin/python3.11` ⭐ (packages installed here)

**Installed Command:**
- `poly` command at `/opt/homebrew/bin/poly`

## Optional: xAI API Key Configuration

For real Grok research (instead of simulated research), set your xAI API key:

```bash
export XAI_API_KEY="your_xai_api_key_here"
```

Or add it to your shell profile:

```bash
echo 'export XAI_API_KEY="your_xai_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

> **Note**: The app works perfectly without an API key using offline sample markets and simulated research for development/testing.

## Configuration File (Optional)

Create `~/.poly/config.yml` to customize settings:

```yaml
paper_trading:
  default_stake: 100

research:
  min_confidence_threshold: 70
  min_edge_threshold: 0.10
  
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

## Navigation & Usage

Once running, use these keyboard shortcuts:

- `Tab` / `Shift+Tab` - Switch between views
- `Arrow keys` - Navigate lists
- `Enter` - Select/Confirm
- `r` - Refresh markets
- `q` - Quit application

## Views

1. **Polls** - Browse top 20 liquid non-sports Polymarket polls
2. **Research** - View live research progress (simulated or real Grok)
3. **Decision** - Review recommendations and enter/pass trades
4. **Dashboard** - Track paper trading performance metrics

## Troubleshooting

### Command not found: poly

The `poly` command is at `/opt/homebrew/bin/poly`. Make sure `/opt/homebrew/bin` is in your PATH:

```bash
echo $PATH | grep homebrew
```

If not, add to your `~/.zshrc`:

```bash
export PATH="/opt/homebrew/bin:$PATH"
```

### Wrong Python version

If you run `python -m poly` and get errors, you're using the Anaconda Python. Either:

1. Use the full path: `/opt/homebrew/bin/python3.11 -m poly`
2. Create an alias as shown above
3. Activate a different Python environment

## Development Testing

```bash
# Verify compilation
python -m compileall poly

# Test imports
/opt/homebrew/bin/python3.11 -c "from poly.cli import main; print('✓ Success')"

# Run the app
/opt/homebrew/bin/python3.11 -m poly
```

## What Works

✅ **Offline Mode** (no API keys needed):
- Sample markets display
- Simulated research (fast, for testing)
- Paper trading with SQLite persistence
- Dashboard with metrics
- Full TUI navigation

✅ **Online Mode** (with XAI_API_KEY):
- Real Polymarket data
- Real Grok 4 research (20-40 min per poll)
- Web + X search integration
- All offline features

---

**Status**: Ready to use! 🚀

Try running: `/opt/homebrew/bin/python3.11 -m poly`

