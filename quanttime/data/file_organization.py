"""
File Organization System for QuantTime MBO L3 Pipeline.

This module manages the directory structure, naming conventions, and file organization
for raw MBO data vs processed/normalized data. It ensures consistent file organization
across the entire pipeline.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

from .schema import DataType, NormalizationType, FeatureSet, get_unified_schema

logger = logging.getLogger(__name__)


class FileOrganizationManager:
    """
    Manages file organization for the MBO L3 pipeline.
    
    Handles directory structure, naming conventions, and file organization
    for raw vs processed data.
    """
    
    def __init__(self, base_data_dir: str = "data"):
        """
        Initialize file organization manager.
        
        Args:
            base_data_dir: Base directory for all data
        """
        self.base_data_dir = Path(base_data_dir)
        self.schema = get_unified_schema()
        
        # Create directory structure
        self._create_directory_structure()
    
    def _create_directory_structure(self):
        """Create the standard directory structure."""
        directories = [
            # Raw data directories
            self.base_data_dir / "raw" / "mbo",
            self.base_data_dir / "raw" / "mbp",
            self.base_data_dir / "raw" / "trades",
            
            # Processed data directories
            self.base_data_dir / "processed" / "mbo",
            self.base_data_dir / "processed" / "mbp",
            self.base_data_dir / "processed" / "trades",
            
            # Schema-specific directories
            self.base_data_dir / "processed" / "schemas",
            
            # Archive directories
            self.base_data_dir / "archive" / "raw",
            self.base_data_dir / "archive" / "processed",
            
            # Live data directories
            self.base_data_dir / "live" / "raw",
            self.base_data_dir / "live" / "processed",
            
            # Metadata directories
            self.base_data_dir / "metadata",
            self.base_data_dir / "logs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
    
    def get_raw_data_dir(self, data_type: str = "mbo") -> Path:
        """Get raw data directory for a specific data type."""
        return self.base_data_dir / "raw" / data_type
    
    def get_processed_data_dir(self, data_type: str = "mbo") -> Path:
        """Get processed data directory for a specific data type."""
        return self.base_data_dir / "processed" / data_type
    
    def get_schema_dir(self, schema_name: str) -> Path:
        """Get directory for a specific schema."""
        return self.base_data_dir / "processed" / "schemas" / schema_name
    
    def get_live_data_dir(self, data_type: str = "mbo", processed: bool = True) -> Path:
        """Get live data directory."""
        if processed:
            return self.base_data_dir / "live" / "processed" / data_type
        else:
            return self.base_data_dir / "live" / "raw" / data_type
    
    def parse_raw_filename(self, filename: str) -> Dict[str, Any]:
        """
        Parse raw DBN filename to extract metadata.
        
        Expected format: glbx-mdp3-YYYYMMDD.mbo.dbn.zst
        """
        pattern = r"glbx-mdp3-(\d{8})\.(\w+)\.dbn(?:\.(zst|gz))?"
        match = re.match(pattern, filename)
        
        if match:
            date_str = match.group(1)
            data_type = match.group(2)
            compression = match.group(3) if match.group(3) else None
            
            return {
                'date': date_str,
                'data_type': data_type,
                'compression': compression,
                'exchange': 'glbx',
                'dataset': 'mdp3'
            }
        
        return {}
    
    def generate_processed_filename(self, 
                                  raw_filename: str,
                                  schema_name: str,
                                  date_str: str,
                                  intensity_level: str = "medium") -> str:
        """
        Generate processed filename from raw filename and schema.
        
        Args:
            raw_filename: Original raw filename
            schema_name: Schema name for the processed data
            date_str: Date string (YYYYMMDD)
            intensity_level: Feature engineering intensity level (light, medium, heavy, extreme)
            
        Returns:
            Processed filename
        """
        # Parse raw filename
        raw_info = self.parse_raw_filename(raw_filename)
        data_type = raw_info.get('data_type', 'mbo')
        
        # Get schema info
        schema_info = self.schema.get_data_type_info(schema_name)
        
        # Generate processed filename with intensity level
        processed_filename = f"{date_str}_{data_type}_{intensity_level}_{schema_name}.parquet"
        
        return processed_filename
    
    def get_file_paths(self, 
                      date_str: str,
                      data_type: str = "mbo",
                      schema_name: Optional[str] = None) -> Dict[str, Path]:
        """
        Get file paths for a specific date and data type.
        
        Args:
            date_str: Date string (YYYYMMDD)
            data_type: Data type (mbo, mbp, trades)
            schema_name: Optional schema name for processed data
            
        Returns:
            Dictionary of file paths
        """
        paths = {}
        
        # Raw data path
        raw_dir = self.get_raw_data_dir(data_type)
        raw_pattern = f"glbx-mdp3-{date_str}.{data_type}.dbn*"
        raw_files = list(raw_dir.glob(raw_pattern))
        
        if raw_files:
            paths['raw'] = raw_files[0]  # Take first match
        
        # Processed data paths
        if schema_name:
            processed_dir = self.get_schema_dir(schema_name)
            processed_pattern = f"{date_str}_{data_type}_{schema_name}.parquet"
            processed_files = list(processed_dir.glob(processed_pattern))
            
            if processed_files:
                paths['processed'] = processed_files[0]
        
        return paths
    
    def list_available_dates(self, 
                           data_type: str = "mbo",
                           schema_name: Optional[str] = None) -> List[str]:
        """
        List available dates for a specific data type and schema.
        
        Args:
            data_type: Data type (mbo, mbp, trades)
            schema_name: Optional schema name for processed data
            
        Returns:
            List of available date strings
        """
        dates = set()
        
        # Get raw dates
        raw_dir = self.get_raw_data_dir(data_type)
        raw_pattern = f"glbx-mdp3-*.{data_type}.dbn*"
        raw_files = list(raw_dir.glob(raw_pattern))
        
        for file_path in raw_files:
            raw_info = self.parse_raw_filename(file_path.name)
            if 'date' in raw_info:
                dates.add(raw_info['date'])
        
        # Get processed dates if schema specified
        if schema_name:
            processed_dir = self.get_schema_dir(schema_name)
            
            # Look for Parquet files only (production-ready)
            # Pattern: YYYYMMDD_data_type_intensity_schema_trading_hours.parquet
            parquet_pattern = f"*_{data_type}_*_{schema_name}*.parquet"
            processed_files = list(processed_dir.glob(parquet_pattern))
            
            for file_path in processed_files:
                # Extract date from processed filename
                # Parquet format: YYYYMMDD_data_type_intensity_schema_trading_hours.parquet
                match = re.match(r"(\d{8})_", file_path.name)
                if match:
                    dates.add(match.group(1))
        
        return sorted(list(dates), reverse=True)
    
    def get_data_type_summary(self) -> Dict[str, Any]:
        """
        Get summary of available data types and schemas.
        
        Returns:
            Dictionary with data type summary
        """
        summary = {
            'raw_data_types': {},
            'processed_schemas': {},
            'total_files': 0,
            'total_size_gb': 0.0
        }
        
        # Scan raw data
        for data_type in ['mbo', 'mbp', 'trades']:
            raw_dir = self.get_raw_data_dir(data_type)
            if raw_dir.exists():
                files = list(raw_dir.glob("*.dbn*"))
                dates = self.list_available_dates(data_type)
                
                total_size = sum(f.stat().st_size for f in files)
                
                summary['raw_data_types'][data_type] = {
                    'files': len(files),
                    'dates': len(dates),
                    'size_gb': total_size / (1024**3),
                    'date_range': f"{min(dates)} to {max(dates)}" if dates else None
                }
                
                summary['total_files'] += len(files)
                summary['total_size_gb'] += total_size / (1024**3)
        
        # Scan processed schemas
        schemas_dir = self.base_data_dir / "processed" / "schemas"
        if schemas_dir.exists():
            for schema_dir in schemas_dir.iterdir():
                if schema_dir.is_dir():
                    schema_name = schema_dir.name
                    
                    # Look for Parquet files only (production-ready)
                    parquet_files = list(schema_dir.glob("*.parquet"))
                    
                    total_size = sum(f.stat().st_size for f in parquet_files)
                    
                    summary['processed_schemas'][schema_name] = {
                        'files': len(parquet_files),
                        'parquet_files': len(parquet_files),
                        'size_gb': total_size / (1024**3),
                        'schema_info': self.schema.get_data_type_info(schema_name)
                    }
        
        return summary
    
    def create_schema_directory(self, schema_name: str) -> Path:
        """
        Create directory for a specific schema.
        
        Args:
            schema_name: Schema name
            
        Returns:
            Path to created directory
        """
        schema_dir = self.get_schema_dir(schema_name)
        schema_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created schema directory: {schema_dir}")
        return schema_dir
    
    def get_file_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata for a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file metadata
        """
        if not file_path.exists():
            return {}
        
        stat = file_path.stat()
        
        metadata = {
            'filename': file_path.name,
            'size_bytes': stat.st_size,
            'size_mb': stat.st_size / (1024**2),
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat()
        }
        
        # Parse filename for additional metadata
        if file_path.suffix == '.parquet':
            # Processed Parquet file
            match = re.match(r"(\d{8})_(\w+)_(.+)\.parquet", file_path.name)
            if match:
                metadata.update({
                    'date': match.group(1),
                    'data_type': match.group(2),
                    'schema_name': match.group(3),
                    'file_type': 'processed_parquet'
                })
        elif file_path.name.endswith('.dbn') or file_path.name.endswith('.dbn.zst'):
            # Raw DBN file only
            raw_info = self.parse_raw_filename(file_path.name)
            metadata.update(raw_info)
            metadata['file_type'] = 'raw'
        else:
            # Raw file
            raw_info = self.parse_raw_filename(file_path.name)
            metadata.update(raw_info)
            metadata['file_type'] = 'raw'
        
        return metadata


# Global file organization manager
_file_manager = None

def get_file_manager(base_data_dir: str = "data") -> FileOrganizationManager:
    """Get global file organization manager."""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileOrganizationManager(base_data_dir)
    return _file_manager


def get_data_type_summary() -> Dict[str, Any]:
    """Get summary of available data types and schemas."""
    manager = get_file_manager()
    return manager.get_data_type_summary()


def list_available_dates(data_type: str = "mbo", 
                        schema_name: Optional[str] = None) -> List[str]:
    """List available dates for a specific data type and schema."""
    manager = get_file_manager()
    return manager.list_available_dates(data_type, schema_name)


def get_file_paths(date_str: str,
                  data_type: str = "mbo",
                  schema_name: Optional[str] = None) -> Dict[str, Path]:
    """Get file paths for a specific date and data type."""
    manager = get_file_manager()
    return manager.get_file_paths(date_str, data_type, schema_name)
