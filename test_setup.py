#!/usr/bin/env python3
"""Quick test to verify Poly TUI setup."""

import sys

def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...", end=" ")
    try:
        from poly.cli import main
        from poly.app import PolyApp
        from poly.config import AppConfig, load_config
        from poly.models import Market, Trade, PortfolioMetrics
        from poly.services.polymarket_client import PolymarketService
        from poly.services.research import ResearchService
        from poly.services.evaluator import PositionEvaluator
        from poly.storage.trades import TradeRepository
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_app_init():
    """Test that the app initializes."""
    print("Testing app initialization...", end=" ")
    try:
        from poly.app import PolyApp
        app = PolyApp()
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("Testing configuration...", end=" ")
    try:
        from poly.config import load_config
        config = load_config()
        assert config.paper_trading.default_stake == 100.0
        assert config.research.min_confidence_threshold == 70.0
        assert config.polls.top_n == 20
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def main():
    """Run all tests."""
    print("\n🧪 Poly TUI Setup Test\n")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config,
        test_app_init,
    ]
    
    results = [test() for test in tests]
    
    print("=" * 50)
    
    if all(results):
        print("\n✅ All tests passed! Poly TUI is ready to run.")
        print("\nRun the app with:")
        print("  ./run.sh")
        print("  or")
        print("  python -m poly")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

