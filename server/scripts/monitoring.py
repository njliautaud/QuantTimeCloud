"""
QuantTime Monitoring Service

Real-time monitoring and alerting service for the distributed computing cluster.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from server.core.health_checker import HealthChecker
from server.core.resource_monitor import ResourceMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitoring.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class MonitoringService:
    """Monitoring service for cluster health and performance"""
    
    def __init__(self):
        """Initialize monitoring service"""
        self.running = False
        self.health_checker = HealthChecker()
        self.resource_monitor = ResourceMonitor()
        
    async def start(self):
        """Start the monitoring service"""
        try:
            logger.info("🚀 Starting Monitoring Service...")
            
            # Start health checker
            await self.health_checker.start()
            
            # Start resource monitor
            await self.resource_monitor.start()
            
            self.running = True
            logger.info("✅ Monitoring Service started successfully")
            
            # Keep service running
            while self.running:
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"❌ Monitoring Service failed: {e}")
            raise
    
    async def stop(self):
        """Stop the monitoring service"""
        self.running = False
        
        # Stop components
        await self.health_checker.stop()
        await self.resource_monitor.stop()
        
        logger.info("✅ Monitoring Service stopped")

async def main():
    """Main entry point"""
    service = MonitoringService()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
