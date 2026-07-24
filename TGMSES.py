#!/usr/bin/env python3
"""
TGMSES - Telegram Multi-Account Hub (Entry Point)
Developer: Younus Ali | GitHub: https://github.com/Younusgit
"""

import asyncio
import logging
import sys
import os

# Import custom modules
from main_logic import run_bot, setup_logging
from account_manager import load_or_create_config

# Setup logging
log = logging.getLogger("TGMSES")

def main():
    # Print Developer Banner
    banner = """
╔════════════════════════════════════════════════════════════╗
║   🚀 TGMSES - Telegram Multi-Account Hub                  ║
║   Version: 1.0.0                                            ║
║   Developer: Younus Ali                                     ║
║   GitHub: https://github.com/Younusgit                      ║
╚════════════════════════════════════════════════════════════╝
"""
    print(banner)
    
    # Set up logging
    setup_logging()
    
    # Load configuration
    config = load_or_create_config()
    
    # Run the bot
    try:
        asyncio.run(run_bot(config))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Stopping...")
        sys.exit(0)
    except Exception as e:
        log.critical(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
