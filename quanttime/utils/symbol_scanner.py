"""
Symbol Scanner Utility

This module scans the organized data structure to find available symbols
and provides them in a format suitable for dropdown selection.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SymbolScanner:
    """Scans the data directory for available symbols and their file locations."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.symbol_cache = {}
        self._scan_symbols()
    
    def _scan_symbols(self):
        """Scan the data directory for available symbols."""
        logger.info(f"Scanning for symbols in {self.data_dir}")
        
        # Scan ES futures MBO data
        es_mbo_dir = self.data_dir / "es_futures" / "mbo"
        if es_mbo_dir.exists():
            self._scan_es_mbo_data(es_mbo_dir)
        
        logger.info(f"Found {len(self.symbol_cache)} total symbols")
    
    def _scan_es_mbo_data(self, mbo_dir: Path):
        """Scan ES MBO directory for available dates."""
        # We only have ES ticker, so we scan for available dates
        available_dates = []
        
        # Look for date folders (YYYYMMDD format)
        for item in mbo_dir.iterdir():
            if item.is_dir() and item.name.startswith("glbx-mdp3-") and item.name.endswith(".mbo.dbn"):
                # Extract date from folder name: glbx-mdp3-20250714.mbo.dbn
                date_part = item.name.replace("glbx-mdp3-", "").replace(".mbo.dbn", "")
                if len(date_part) == 8 and date_part.isdigit():
                    available_dates.append(date_part)
        
        # Also look for compressed files
        for item in mbo_dir.iterdir():
            if item.is_file() and item.name.startswith("glbx-mdp3-") and item.name.endswith(".mbo.dbn.zst"):
                # Extract date from filename: glbx-mdp3-20250714.mbo.dbn.zst
                date_part = item.name.replace("glbx-mdp3-", "").replace(".mbo.dbn.zst", "")
                if len(date_part) == 8 and date_part.isdigit():
                    available_dates.append(date_part)
        
        # Remove duplicates and sort
        available_dates = sorted(list(set(available_dates)))
        
        # Create symbol entries for each available date
        for date_str in available_dates:
            # Format date for display
            try:
                date_obj = datetime.strptime(date_str, "%Y%m%d")
                display_date = date_obj.strftime("%Y-%m-%d")
            except:
                display_date = date_str
            
            symbol_key = f"ES_{date_str}"
            file_location = f"data/es_futures/mbo/glbx-mdp3-{date_str}.mbo.dbn.zst"
            
            self.symbol_cache[symbol_key] = {
                'type': 'ES_MBO',
                'location': file_location,
                'date': date_str,
                'display_date': display_date,
                'description': f"ES - {display_date}",
                'ticker': 'ES'
            }
        
        logger.info(f"Found {len(available_dates)} available ES trading dates")
    
    def get_available_symbols(self) -> List[Tuple[str, str]]:
        """
        Get list of available symbols for dropdown.
        
        Returns:
            List of tuples: (display_text, symbol_key)
            display_text includes symbol name and file location in light gray
        """
        symbols = []
        
        for symbol_key, info in self.symbol_cache.items():
            # Create display text with file location in light gray
            display_text = f"{info['description']} <span style='color: #888888; font-size: 0.8em;'>({info['location']})</span>"
            symbols.append((display_text, symbol_key))
        
        # Sort by date (newest first)
        symbols.sort(key=lambda x: self.symbol_cache[x[1]]['date'], reverse=True)
        
        return symbols
    
    def get_symbol_info(self, symbol_key: str) -> Optional[Dict]:
        """Get detailed information about a specific symbol."""
        return self.symbol_cache.get(symbol_key)
    
    def get_available_dates(self) -> List[str]:
        """Get list of available trading dates."""
        dates = []
        for info in self.symbol_cache.values():
            dates.append(info['date'])
        return sorted(dates, reverse=True)  # Newest first
    
    def get_es_symbols(self) -> List[Tuple[str, str]]:
        """Get ES symbols specifically."""
        return self.get_available_symbols()  # All symbols are ES
    
    def get_symbol_by_date(self, date_str: str) -> Optional[str]:
        """Get symbol key for a specific date."""
        symbol_key = f"ES_{date_str}"
        return symbol_key if symbol_key in self.symbol_cache else None


def get_symbol_scanner() -> SymbolScanner:
    """Get a singleton symbol scanner instance."""
    if not hasattr(get_symbol_scanner, '_instance'):
        get_symbol_scanner._instance = SymbolScanner()
    return get_symbol_scanner._instance


def get_available_symbols_for_dropdown() -> List[Tuple[str, str]]:
    """Convenience function to get symbols for dropdown."""
    scanner = get_symbol_scanner()
    return scanner.get_available_symbols()


def get_es_symbols_for_dropdown() -> List[Tuple[str, str]]:
    """Convenience function to get ES symbols for dropdown."""
    scanner = get_symbol_scanner()
    return scanner.get_es_symbols()


def get_symbol_info(symbol_key: str) -> Optional[Dict]:
    """Convenience function to get symbol info."""
    scanner = get_symbol_scanner()
    return scanner.get_symbol_info(symbol_key)


def get_available_dates() -> List[str]:
    """Convenience function to get available trading dates."""
    scanner = get_symbol_scanner()
    return scanner.get_available_dates()


def get_symbol_by_date(date_str: str) -> Optional[str]:
    """Convenience function to get symbol key for a specific date."""
    scanner = get_symbol_scanner()
    return scanner.get_symbol_by_date(date_str)
