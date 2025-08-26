"""
Databento MBO Reader - Stub implementation

This is a stub file to fix import errors in the app.
The actual MBO processing is now handled by mbo_processor.py
"""

import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DatabentoMBOReader:
    """
    Stub implementation of DatabentoMBOReader for compatibility.
    The actual MBO processing is now handled by mbo_processor.py
    """
    
    def __init__(self, data_dir: str):
        """
        Initialize the MBO reader.
        
        Args:
            data_dir: Directory containing MBO data files
        """
        self.data_dir = data_dir
        logger.warning("DatabentoMBOReader is a stub. Use mbo_processor.py for actual MBO processing.")
    
    def get_available_dates(self) -> List[str]:
        """Get list of available dates."""
        logger.warning("get_available_dates() not implemented in stub")
        return []
    
    def get_symbol_mapping(self, symbol: str) -> Optional[Dict[str, int]]:
        """Get symbol mapping."""
        logger.warning("get_symbol_mapping() not implemented in stub")
        return None
    
    def read_mbo_file(self, date: str, symbol_ids: List[int]) -> pd.DataFrame:
        """Read MBO file for given date and symbols."""
        logger.warning("read_mbo_file() not implemented in stub")
        return pd.DataFrame()
