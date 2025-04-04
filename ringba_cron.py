"""
Ringba RPC Monitor - Cron Version
For running as a scheduled cron job on Render.com
"""

import asyncio
import sys
from ringba_bot_production import check_rpc_values, ensure_packages_installed

# Run the check immediately without scheduling
if __name__ == "__main__":
    print("==== Ringba RPC Monitor - Cron Job ====")
    ensure_packages_installed()
    try:
        asyncio.run(check_rpc_values())
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
