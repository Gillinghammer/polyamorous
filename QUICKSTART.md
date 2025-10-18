# 🚀 Poly TUI - Quickstart

## ✅ Setup Complete!

Your Poly TUI application is fully installed and ready to use.

## Test Your Setup

First, verify everything is working:

```bash
python test_setup.py
```

You should see all tests pass ✓

## Run the App (Choose One)

### Option 1: Simple Script (Recommended)
```bash
./run.sh
```

### Option 2: Direct Command
```bash
/opt/homebrew/bin/python3.11 -m poly
```

### Option 3: Installed Command
```bash
/opt/homebrew/bin/poly
```

## First Launch

When you run the app for the first time:

1. **Polls View** loads automatically showing sample markets (offline mode)
2. Use **arrow keys** to navigate the table
3. Press **Enter** on a poll to start research
4. Research will be simulated (fast) without an API key

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Switch between views |
| `Arrow keys` | Navigate lists |
| `Enter` | Select/Confirm |
| `r` | Refresh markets |
| `q` | Quit |
| `Esc` | Go back |

## Four Main Views

1. **📊 Polls** - Top 20 liquid non-sports Polymarket polls
2. **🔍 Research** - Live research progress (20-40 min with API)
3. **✅ Decision** - Review findings and enter/pass trades
4. **📈 Dashboard** - Track your paper trading performance

## Offline vs Online Mode

### Offline Mode (No API Key)
- ✅ Sample markets
- ✅ Simulated research (instant)
- ✅ Paper trading
- ✅ Full navigation

### Online Mode (With API Key)
- ✅ Real Polymarket data
- ✅ Real Grok 4 research (20-40 min)
- ✅ Web + X search
- ✅ Everything from offline mode

## Enable Online Mode

```bash
export XAI_API_KEY="your_key_here"
./run.sh
```

Or add to `~/.zshrc`:
```bash
echo 'export XAI_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

## What to Expect

### Polls Tab
- Browse 20 most liquid polls
- See current odds, time remaining, liquidity
- Select a poll to research

### Research Tab
- Progress bar shows research rounds
- Live log shows what's happening
- Takes 20-40 minutes with real Grok
- Instant with simulated research

### Decision Tab
- See prediction, confidence, edge
- Read key findings and citations
- Choose: Enter Trade or Pass

### Dashboard Tab
- Active positions count
- Win rate percentage
- Total & average profit
- Recent trades list

## Data Storage

Your paper trades are saved in:
```
~/.poly/trades.db
```

This SQLite database persists between sessions.

## Tips

1. **Start in offline mode** to learn the interface
2. **Research takes time** - go do something else during real research
3. **Accuracy over frequency** - the algorithm only recommends high-conviction trades
4. **Paper trading only** - no real money in Phase 1

## Troubleshooting

### App won't start?
```bash
# Verify Python setup
/opt/homebrew/bin/python3.11 -c "from poly.cli import main; print('✓ OK')"

# Re-run installation
pip install -e .
```

### Import errors?
You may have multiple Python installations. Use the full path:
```bash
/opt/homebrew/bin/python3.11 -m poly
```

## Next Steps

1. **Launch the app**: `./run.sh`
2. **Explore the Polls tab**: Browse sample markets
3. **Try research**: Select a poll and watch the simulated research
4. **Enter a paper trade**: Accept a recommendation in the Decision tab
5. **Check Dashboard**: View your paper trading performance

## Documentation

- **[README.md](README.md)** - Full documentation
- **[SETUP.md](SETUP.md)** - Detailed setup guide
- **[prd.md](prd.md)** - Product requirements
- **[AGENTS.md](AGENTS.md)** - Development guidelines

---

**Ready to start?** Run: `./run.sh`

Enjoy finding asymmetric information! 📊🔍

