#!/usr/bin/env bash
# Comprehensive test suite for Poly TUI

set -e

echo ""
echo "🧪 Poly TUI - Comprehensive Test Suite"
echo "========================================"
echo ""

# Test 1: Python compilation
echo "1️⃣  Testing Python compilation..."
python -m compileall poly > /dev/null 2>&1
echo "   ✓ All modules compile successfully"
echo ""

# Test 2: Import tests
echo "2️⃣  Testing imports and configuration..."
/opt/homebrew/bin/python3.11 test_setup.py | grep -A 5 "All tests passed" || exit 1
echo ""

# Test 3: App startup
echo "3️⃣  Testing app startup and CSS..."
/opt/homebrew/bin/python3.11 test_app_start.py | grep -A 2 "App can start successfully" || exit 1
echo ""

# Test 4: Quick syntax check
echo "4️⃣  Running syntax validation..."
/opt/homebrew/bin/python3.11 -c "
from poly.app import PolyApp
from poly.services.polymarket_client import PolymarketService
from poly.services.research import ResearchService
from poly.services.evaluator import PositionEvaluator
from poly.storage.trades import TradeRepository
print('   ✓ All imports validated')
"
echo ""

echo "========================================"
echo "✅ ALL TESTS PASSED!"
echo ""
echo "Your Poly TUI is ready to run:"
echo "  ./run.sh"
echo ""

