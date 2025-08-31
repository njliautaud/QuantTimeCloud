#!/usr/bin/env python3
"""
Persistent Node Status Manager
Stores node connection status in a JSON file to survive application restarts
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class NodeStatusManager:
    """Manages persistent node status storage"""
    
    def __init__(self, status_file: str = "data/node_status.json"):
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_status()
    
    def _load_status(self):
        """Load node status from file"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    self.node_status = json.load(f)
                logger.info(f"Loaded node status from {self.status_file}")
            else:
                self.node_status = {}
                logger.info("No existing node status file found, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load node status: {e}")
            self.node_status = {}
    
    def _save_status(self):
        """Save node status to file"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.node_status, f, indent=2, default=str)
            logger.debug(f"Saved node status to {self.status_file}")
        except Exception as e:
            logger.error(f"Failed to save node status: {e}")
    
    def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """Get status for a specific node"""
        return self.node_status.get(node_id, {
            "connected": False,
            "status": "🔴 Not Connected",
            "last_updated": None
        })
    
    def update_node_status(self, node_id: str, status_data: Dict[str, Any]):
        """Update status for a specific node"""
        current_time = datetime.now().isoformat()
        
        # Update the status
        self.node_status[node_id] = {
            **status_data,
            "last_updated": current_time
        }
        
        logger.info(f"Updated {node_id} status: connected={status_data.get('connected', False)}")
        self._save_status()
    
    def get_all_node_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all nodes"""
        return self.node_status.copy()
    
    def clear_node_status(self, node_id: str):
        """Clear status for a specific node"""
        if node_id in self.node_status:
            del self.node_status[node_id]
            logger.info(f"Cleared status for {node_id}")
            self._save_status()
    
    def clear_all_status(self):
        """Clear all node status"""
        self.node_status = {}
        logger.info("Cleared all node status")
        self._save_status()
    
    def get_connected_nodes(self) -> list:
        """Get list of connected node IDs"""
        return [node_id for node_id, status in self.node_status.items() 
                if status.get("connected", False)]
    
    def is_node_connected(self, node_id: str) -> bool:
        """Check if a specific node is connected"""
        return self.node_status.get(node_id, {}).get("connected", False)

# Global instance
node_status_manager = NodeStatusManager()
