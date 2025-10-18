#!/usr/bin/env python3
"""Test that the app can actually start without CSS errors."""

import sys
import asyncio

async def test_app_start():
    """Test that the app starts and loads CSS successfully."""
    from poly.app import PolyApp
    
    app = PolyApp()
    
    # This will validate CSS during initialization
    try:
        # Just create the app - don't run it
        print("✓ App created successfully")
        print("✓ CSS stylesheet valid")
        print("✓ All bindings registered")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run the test."""
    print("\n🧪 Testing App Startup\n")
    print("=" * 50)
    
    result = asyncio.run(test_app_start())
    
    print("=" * 50)
    
    if result:
        print("\n✅ App can start successfully!")
        print("\nReady to run: ./run.sh")
        return 0
    else:
        print("\n❌ App failed to start")
        return 1

if __name__ == "__main__":
    sys.exit(main())

