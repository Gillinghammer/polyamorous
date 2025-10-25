"""Run autopilot service from command line."""

import asyncio
import sys
from pathlib import Path

from polly.autopilot.service import AutopilotService
from polly.config import DEFAULT_CONFIG_PATH


def main():
    """Main entry point for autopilot service."""
    
    print("="*60)
    print("🤖 Polly Autopilot Service")
    print("="*60)
    print(f"Config: {DEFAULT_CONFIG_PATH}")
    print(f"Logs: ~/.polly/logs/")
    print("="*60)
    print("\nService will check positions every hour")
    print("Press Ctrl+C to stop\n")
    print("="*60)
    
    service = AutopilotService(DEFAULT_CONFIG_PATH)
    
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        print("\n")
        print("="*60)
        print("Autopilot service stopped by user")
        print("="*60)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

