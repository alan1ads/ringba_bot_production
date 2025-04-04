"""
Ringba RPC Monitor - Cron Version
For running as a scheduled cron job on Render.com
"""

import asyncio
import sys
import os
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure downloads directory exists
os.makedirs(os.path.join(os.getcwd(), "downloads"), exist_ok=True)

# Import after ensuring directories exist
from ringba_bot_production import check_rpc_values, ensure_packages_installed

# Run the check immediately without scheduling
if __name__ == "__main__":
    print("==== Ringba RPC Monitor - Cron Job ====")
    logger.info("Starting Ringba RPC Monitor cron job")
    
    try:
        # Ensure required packages are installed
        ensure_packages_installed()
        
        # Run the check
        asyncio.run(check_rpc_values())
        logger.info("RPC check completed successfully")
        sys.exit(0)
    except Exception as e:
        error_text = f"ERROR: {e}\n{traceback.format_exc()}"
        logger.error(error_text)
        print(error_text)
        sys.exit(1)
