#!/bin/bash
# Quick script to check autopilot logs

echo "========================================="
echo "Polly Autopilot Log Check"
echo "========================================="
echo ""

LOG_FILE="$HOME/.polly/logs/autopilot.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ No log file found at $LOG_FILE"
    echo ""
    echo "Autopilot hasn't run yet. To start:"
    echo "  export POLYGON_PRIVATE_KEY='your_key'"
    echo "  python -m polly.autopilot"
    exit 1
fi

echo "📄 Log file: $LOG_FILE"
echo ""

# Get last line
LAST_LINE=$(tail -1 "$LOG_FILE")
echo "Last entry:"
echo "  $LAST_LINE"
echo ""

# Count cycles
CYCLE_COUNT=$(grep -c "Cycle.*started" "$LOG_FILE")
echo "Total cycles logged: $CYCLE_COUNT"
echo ""

# Check if running (activity in last 5 minutes)
LAST_TIME=$(tail -1 "$LOG_FILE" | cut -d'|' -f1 | xargs)
echo "Last activity: $LAST_TIME"
echo ""

# Show recent activity
echo "Recent activity (last 20 lines):"
echo "─────────────────────────────────────────"
tail -20 "$LOG_FILE"
echo ""

echo "========================================="
echo "To view live: tail -f $LOG_FILE"
echo "========================================="
