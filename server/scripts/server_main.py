"""
QuantTime Server Main Entry Point

Main script to start the distributed computing server.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from server.core.server_api import app, run_server
from server.core.auth import auth_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/server.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

async def main():
    """Main server startup"""
    try:
        # Set signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start auth manager
        await auth_manager.start()
        
        # Start the FastAPI server
        host = os.getenv('QUANTTIME_SERVER_HOST', '0.0.0.0')
        port = int(os.getenv('QUANTTIME_SERVER_PORT', 8000))
        workers = int(os.getenv('QUANTTIME_SERVER_WORKERS', 1))
        
        logger.info(f"🚀 Starting QuantTime Server on {host}:{port}")
        run_server(host=host, port=port, workers=workers)
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
