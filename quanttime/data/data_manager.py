"""
Comprehensive Data Management System for QuantTime
Handles automatic unzipping, data aggregation, and duplicate prevention
"""

import os
import shutil
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from datetime import datetime, timedelta
import json
import hashlib
from dataclasses import dataclass, asdict
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import zstandard as zstd
import gzip
import tarfile
import zipfile

logger = logging.getLogger(__name__)

@dataclass
class DataFileInfo:
    """Information about a data file"""
    file_path: str
    file_name: str
    file_size: int
    file_hash: str
    is_compressed: bool
    compression_type: Optional[str]
    date: Optional[datetime]
    dataset: Optional[str]
    schema: Optional[str]
    extracted_path: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

@dataclass
class DataAggregationConfig:
    """Configuration for data aggregation"""
    root_data_dir: str = "data/es_futures"
    auto_unzip: bool = True
    remove_duplicates: bool = True
    max_workers: int = 4
    supported_compression: List[str] = None
    data_organizations: Dict[str, str] = None
    
    def __post_init__(self):
        if self.supported_compression is None:
            # Focus on Databento compression formats
            self.supported_compression = ['.zst', '.gz']
        if self.data_organizations is None:
            self.data_organizations = {
                'GLBX': 'ES_GLBX',
                'XNAS': 'ES_XNAS',
                'OPRA': 'ES_OPRA'
            }

class DataManager:
    """
    Comprehensive data management system for QuantTime
    Handles automatic unzipping, data aggregation, and duplicate prevention
    """
    
    def __init__(self, config: DataAggregationConfig):
        self.config = config
        self.root_path = Path(config.root_data_dir)
        self.root_path.mkdir(exist_ok=True)
        
        # Track all data files
        self.data_files: Dict[str, DataFileInfo] = {}
        self.extracted_files: Dict[str, str] = {}
        self.duplicates: Dict[str, List[str]] = {}
        
        # Threading
        self.lock = threading.Lock()
        
        logger.info(f"DataManager initialized with root directory: {self.root_path}")
    
    def scan_all_data(self) -> Dict[str, Any]:
        """
        Scan all available data in the project directory
        Returns comprehensive data inventory
        """
        logger.info("Starting comprehensive data scan...")
        
        # Scan root directory and all subdirectories
        all_files = []
        
        # Scan current directory and immediate subdirectories
        for item in Path('.').iterdir():
            if item.is_dir():
                all_files.extend(self._scan_directory(item))
            elif item.is_file() and self._is_data_file(item):
                all_files.append(item)
        
        # Process all found files
        self._process_data_files(all_files)
        
        # Generate comprehensive report
        report = self._generate_data_report()
        
        logger.info(f"Data scan complete. Found {len(self.data_files)} data files")
        return report
    
    def _scan_directory(self, directory: Path) -> List[Path]:
        """Recursively scan directory for data files"""
        data_files = []
        
        try:
            for item in directory.iterdir():
                if item.is_file() and self._is_data_file(item):
                    data_files.append(item)
                elif item.is_dir() and not item.name.startswith('.'):
                    # Recursively scan subdirectories
                    data_files.extend(self._scan_directory(item))
        except PermissionError:
            logger.warning(f"Permission denied accessing directory: {directory}")
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return data_files
    
    def _is_data_file(self, file_path: Path) -> bool:
        """Check if file is a Databento data file we should process"""
        # Only process Databento-specific data files
        file_name = file_path.name.lower()
        
        # Databento data file patterns
        databento_patterns = [
            # MBO files
            'mbo.dbn', 'mbo.dbn.zst', 'mbo.dbn.gz',
            # MBP files  
            'mbp.dbn', 'mbp.dbn.zst', 'mbp.dbn.gz',
            # Trades files
            'trades.dbn', 'trades.dbn.zst', 'trades.dbn.gz',
            # OHLCV files
            'ohlcv.dbn', 'ohlcv.dbn.zst', 'ohlcv.dbn.gz',
            # Specific dataset patterns
            'glbx-mdp3', 'xnas-itch', 'opra-pillar'
        ]
        
        # Check for Databento patterns
        if any(pattern in file_name for pattern in databento_patterns):
            return True
        
        # Check for Databento file extensions in specific directories
        if file_path.suffix.lower() in ['.dbn', '.zst', '.gz']:
            # Only process if in a Databento-related directory
            parent_dir = file_path.parent.name.lower()
            databento_dirs = ['glbx', 'xnas', 'opra', 'es_glbx', 'es_xnas', 'es_opra']
            if any(dir_pattern in parent_dir for dir_pattern in databento_dirs):
                return True
        
        return False
    
    def _process_data_files(self, files: List[Path]):
        """Process all found data files"""
        logger.info(f"Processing {len(files)} data files...")
        
        for file_path in files:
            try:
                file_info = self._analyze_file(file_path)
                if file_info:
                    self.data_files[str(file_path)] = file_info
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
    
    def _analyze_file(self, file_path: Path) -> Optional[DataFileInfo]:
        """Analyze a single file and extract metadata"""
        try:
            # Basic file info
            stat = file_path.stat()
            file_size = stat.st_size
            
            # Calculate file hash for duplicate detection
            file_hash = self._calculate_file_hash(file_path)
            
            # Check compression
            is_compressed, compression_type = self._check_compression(file_path)
            
            # Extract date and dataset info from filename
            date, dataset, schema = self._extract_metadata_from_filename(file_path.name)
            
            return DataFileInfo(
                file_path=str(file_path),
                file_name=file_path.name,
                file_size=file_size,
                file_hash=file_hash,
                is_compressed=is_compressed,
                compression_type=compression_type,
                date=date,
                dataset=dataset,
                schema=schema
            )
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return None
    
    def _calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA256 hash of file for duplicate detection"""
        hash_sha256 = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def _check_compression(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Check if file is compressed and determine compression type"""
        file_name = file_path.name.lower()
        
        if file_name.endswith('.zst'):
            return True, 'zstd'
        elif file_name.endswith('.gz'):
            return True, 'gzip'
        elif file_name.endswith('.zip'):
            return True, 'zip'
        elif file_name.endswith('.tar.gz'):
            return True, 'tar.gz'
        
        return False, None
    
    def _extract_metadata_from_filename(self, filename: str) -> Tuple[Optional[datetime], Optional[str], Optional[str]]:
        """Extract date, dataset, and schema from filename"""
        try:
            # Common patterns
            patterns = [
                # glbx-mdp3-20250714.mbo.dbn
                r'(\w+)-(\w+)-(\d{8})\.(\w+)\.dbn',
                # glbx-mdp3-20250714.mbo.dbn.zst
                r'(\w+)-(\w+)-(\d{8})\.(\w+)\.dbn\.(\w+)',
                # 20250714-glbx-mdp3-mbo.dbn
                r'(\d{8})-(\w+)-(\w+)-(\w+)\.dbn',
            ]
            
            import re
            for pattern in patterns:
                match = re.match(pattern, filename)
                if match:
                    if len(match.groups()) >= 4:
                        if match.group(1).isdigit():
                            # Date first pattern
                            date_str = match.group(1)
                            dataset = f"{match.group(2)}-{match.group(3)}"
                            schema = match.group(4)
                        else:
                            # Dataset first pattern
                            dataset = f"{match.group(1)}-{match.group(2)}"
                            date_str = match.group(3)
                            schema = match.group(4)
                        
                        date = datetime.strptime(date_str, '%Y%m%d')
                        return date, dataset, schema
            
            return None, None, None
            
        except Exception as e:
            logger.debug(f"Could not extract metadata from filename {filename}: {e}")
            return None, None, None
    
    def auto_unzip_data(self) -> Dict[str, Any]:
        """
        Automatically unzip all compressed data files
        Returns summary of unzipping operations
        """
        if not self.config.auto_unzip:
            logger.info("Auto-unzip is disabled in configuration")
            return {"status": "disabled", "unzipped": 0, "errors": 0}
        
        logger.info("Starting automatic unzipping of compressed data files...")
        
        compressed_files = [
            file_info for file_info in self.data_files.values()
            if file_info.is_compressed
        ]
        
        if not compressed_files:
            logger.info("No compressed files found to unzip")
            return {"status": "no_files", "unzipped": 0, "errors": 0}
        
        results = {
            "status": "completed",
            "unzipped": 0,
            "errors": 0,
            "details": []
        }
        
        # Use ThreadPoolExecutor for parallel unzipping
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_file = {
                executor.submit(self._unzip_file, file_info): file_info
                for file_info in compressed_files
            }
            
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    result = future.result()
                    if result["success"]:
                        results["unzipped"] += 1
                        results["details"].append({
                            "file": file_info.file_name,
                            "status": "success",
                            "extracted_to": result["extracted_path"]
                        })
                    else:
                        results["errors"] += 1
                        results["details"].append({
                            "file": file_info.file_name,
                            "status": "error",
                            "error": result["error"]
                        })
                except Exception as e:
                    results["errors"] += 1
                    results["details"].append({
                        "file": file_info.file_name,
                        "status": "error",
                        "error": str(e)
                    })
        
        logger.info(f"Unzipping complete: {results['unzipped']} files unzipped, {results['errors']} errors")
        return results
    
    def _unzip_file(self, file_info: DataFileInfo) -> Dict[str, Any]:
        """Unzip a single compressed file"""
        try:
            file_path = Path(file_info.file_path)
            compression_type = file_info.compression_type
            
            # Determine extraction directory
            if file_info.date and file_info.dataset:
                # Create organized directory structure
                date_str = file_info.date.strftime('%Y%m%d')
                extract_dir = self.root_path / f"{file_info.dataset}-{date_str}.{file_info.schema}.dbn"
            else:
                # Fallback to simple extraction
                extract_dir = self.root_path / file_path.stem
            
            # Check if already extracted
            if extract_dir.exists():
                logger.debug(f"File already extracted: {extract_dir}")
                return {
                    "success": True,
                    "extracted_path": str(extract_dir),
                    "already_exists": True
                }
            
            # Create extraction directory
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract based on compression type
            if compression_type == 'zstd':
                self._extract_zstd(file_path, extract_dir)
            elif compression_type == 'gzip':
                self._extract_gzip(file_path, extract_dir)
            elif compression_type == 'zip':
                self._extract_zip(file_path, extract_dir)
            elif compression_type == 'tar.gz':
                self._extract_targz(file_path, extract_dir)
            else:
                raise ValueError(f"Unsupported compression type: {compression_type}")
            
            # Update file info
            with self.lock:
                file_info.extracted_path = str(extract_dir)
                self.extracted_files[file_info.file_path] = str(extract_dir)
            
            logger.debug(f"Successfully extracted {file_path} to {extract_dir}")
            return {
                "success": True,
                "extracted_path": str(extract_dir)
            }
            
        except Exception as e:
            logger.error(f"Error unzipping {file_info.file_path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_zstd(self, file_path: Path, extract_dir: Path):
        """Extract zstd compressed file"""
        dctx = zstd.ZstdDecompressor()
        
        with open(file_path, 'rb') as compressed_file:
            with open(extract_dir / file_path.stem, 'wb') as output_file:
                dctx.copy_stream(compressed_file, output_file)
    
    def _extract_gzip(self, file_path: Path, extract_dir: Path):
        """Extract gzip compressed file"""
        with gzip.open(file_path, 'rb') as compressed_file:
            with open(extract_dir / file_path.stem, 'wb') as output_file:
                shutil.copyfileobj(compressed_file, output_file)
    
    def _extract_zip(self, file_path: Path, extract_dir: Path):
        """Extract zip file"""
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    
    def _extract_targz(self, file_path: Path, extract_dir: Path):
        """Extract tar.gz file"""
        with tarfile.open(file_path, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_dir)
    
    def detect_duplicates(self) -> Dict[str, Any]:
        """
        Detect duplicate files based on content hash
        Returns duplicate analysis
        """
        logger.info("Detecting duplicate files...")
        
        hash_groups = {}
        
        # Group files by hash
        for file_path, file_info in self.data_files.items():
            if file_info.file_hash:
                if file_info.file_hash not in hash_groups:
                    hash_groups[file_info.file_hash] = []
                hash_groups[file_info.file_hash].append(file_info)
        
        # Find duplicates
        duplicates = {}
        total_duplicates = 0
        space_saved = 0
        
        for file_hash, files in hash_groups.items():
            if len(files) > 1:
                # Sort by file size (keep the largest as primary)
                files.sort(key=lambda x: x.file_size, reverse=True)
                
                primary_file = files[0]
                duplicate_files = files[1:]
                
                duplicates[primary_file.file_path] = [f.file_path for f in duplicate_files]
                
                # Mark duplicate files
                for duplicate_file in duplicate_files:
                    duplicate_file.is_duplicate = True
                    duplicate_file.duplicate_of = primary_file.file_path
                    total_duplicates += 1
                    space_saved += duplicate_file.file_size
        
        self.duplicates = duplicates
        
        result = {
            "total_files": len(self.data_files),
            "unique_files": len(self.data_files) - total_duplicates,
            "duplicate_files": total_duplicates,
            "space_saved_mb": space_saved / (1024 * 1024),
            "duplicate_groups": len(duplicates),
            "details": duplicates
        }
        
        logger.info(f"Duplicate detection complete: {total_duplicates} duplicates found")
        return result
    
    def aggregate_data(self) -> Dict[str, Any]:
        """
        Aggregate all data files into organized structure
        Returns aggregation summary
        """
        logger.info("Starting data aggregation...")
        
        # First, ensure all compressed files are unzipped
        unzip_results = self.auto_unzip_data()
        
        # Detect duplicates
        duplicate_results = self.detect_duplicates()
        
        # Organize data by dataset and date
        organized_data = self._organize_data()
        
        # Generate final report
        report = {
            "status": "completed",
            "unzipping": unzip_results,
            "duplicates": duplicate_results,
            "organization": organized_data,
            "total_files": len(self.data_files),
            "extracted_files": len(self.extracted_files),
            "data_summary": self._generate_data_summary()
        }
        
        logger.info("Data aggregation complete")
        return report
    
    def _organize_data(self) -> Dict[str, Any]:
        """Organize data into logical structure"""
        organized = {
            "datasets": {},
            "by_date": {},
            "by_schema": {},
            "total_size_mb": 0
        }
        
        total_size = 0
        
        for file_info in self.data_files.values():
            # Skip duplicates if configured
            if self.config.remove_duplicates and file_info.is_duplicate:
                continue
            
            file_size_mb = file_info.file_size / (1024 * 1024)
            total_size += file_size_mb
            
            # Organize by dataset
            if file_info.dataset:
                if file_info.dataset not in organized["datasets"]:
                    organized["datasets"][file_info.dataset] = {
                        "files": [],
                        "total_size_mb": 0,
                        "date_range": {"start": None, "end": None}
                    }
                
                organized["datasets"][file_info.dataset]["files"].append({
                    "name": file_info.file_name,
                    "path": file_info.file_path,
                    "size_mb": file_size_mb,
                    "date": file_info.date.isoformat() if file_info.date else None,
                    "schema": file_info.schema
                })
                organized["datasets"][file_info.dataset]["total_size_mb"] += file_size_mb
                
                # Update date range
                if file_info.date:
                    if not organized["datasets"][file_info.dataset]["date_range"]["start"]:
                        organized["datasets"][file_info.dataset]["date_range"]["start"] = file_info.date.isoformat()
                    organized["datasets"][file_info.dataset]["date_range"]["end"] = file_info.date.isoformat()
            
            # Organize by date
            if file_info.date:
                date_str = file_info.date.strftime('%Y-%m-%d')
                if date_str not in organized["by_date"]:
                    organized["by_date"][date_str] = []
                organized["by_date"][date_str].append({
                    "name": file_info.file_name,
                    "dataset": file_info.dataset,
                    "schema": file_info.schema,
                    "size_mb": file_size_mb
                })
            
            # Organize by schema
            if file_info.schema:
                if file_info.schema not in organized["by_schema"]:
                    organized["by_schema"][file_info.schema] = []
                organized["by_schema"][file_info.schema].append({
                    "name": file_info.file_name,
                    "dataset": file_info.dataset,
                    "date": file_info.date.isoformat() if file_info.date else None,
                    "size_mb": file_size_mb
                })
        
        organized["total_size_mb"] = total_size
        return organized
    
    def _generate_data_summary(self) -> Dict[str, Any]:
        """Generate comprehensive data summary"""
        summary = {
            "total_files": len(self.data_files),
            "compressed_files": len([f for f in self.data_files.values() if f.is_compressed]),
            "extracted_files": len(self.extracted_files),
            "duplicate_files": len([f for f in self.data_files.values() if f.is_duplicate]),
            "total_size_mb": sum(f.file_size for f in self.data_files.values()) / (1024 * 1024),
            "datasets": list(set(f.dataset for f in self.data_files.values() if f.dataset)),
            "schemas": list(set(f.schema for f in self.data_files.values() if f.schema)),
            "date_range": self._get_date_range(),
            "compression_types": list(set(f.compression_type for f in self.data_files.values() if f.compression_type))
        }
        
        return summary
    
    def _get_date_range(self) -> Dict[str, Optional[str]]:
        """Get overall date range of data"""
        dates = [f.date for f in self.data_files.values() if f.date]
        
        if not dates:
            return {"start": None, "end": None}
        
        return {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat()
        }
    
    def _generate_data_report(self) -> Dict[str, Any]:
        """Generate comprehensive data report"""
        return {
            "scan_timestamp": datetime.now().isoformat(),
            "data_files": {path: asdict(info) for path, info in self.data_files.items()},
            "extracted_files": self.extracted_files,
            "duplicates": self.duplicates,
            "summary": self._generate_data_summary()
        }
    
    def get_data_inventory(self) -> Dict[str, Any]:
        """Get current data inventory"""
        return {
            "files": {path: asdict(info) for path, info in self.data_files.items()},
            "extracted": self.extracted_files,
            "duplicates": self.duplicates,
            "summary": self._generate_data_summary()
        }
    
    def cleanup_duplicates(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up duplicate files
        Args:
            dry_run: If True, only report what would be deleted
        """
        if not self.config.remove_duplicates:
            return {"status": "disabled", "deleted": 0, "space_freed_mb": 0}
        
        duplicates_to_remove = [
            file_info for file_info in self.data_files.values()
            if file_info.is_duplicate
        ]
        
        if not duplicates_to_remove:
            return {"status": "no_duplicates", "deleted": 0, "space_freed_mb": 0}
        
        total_space = sum(f.file_size for f in duplicates_to_remove) / (1024 * 1024)
        
        if dry_run:
            return {
                "status": "dry_run",
                "would_delete": len(duplicates_to_remove),
                "space_freed_mb": total_space,
                "files": [f.file_path for f in duplicates_to_remove]
            }
        
        # Actually delete duplicates
        deleted_count = 0
        errors = 0
        
        for file_info in duplicates_to_remove:
            try:
                Path(file_info.file_path).unlink()
                deleted_count += 1
                logger.info(f"Deleted duplicate: {file_info.file_path}")
            except Exception as e:
                errors += 1
                logger.error(f"Error deleting {file_info.file_path}: {e}")
        
        return {
            "status": "completed",
            "deleted": deleted_count,
            "errors": errors,
            "space_freed_mb": total_space
        }

# Factory function for easy creation
def create_data_manager(config: Optional[DataAggregationConfig] = None) -> DataManager:
    """Create a DataManager instance with default or custom configuration"""
    if config is None:
        config = DataAggregationConfig()
    
    return DataManager(config)

# Utility functions for common operations
def scan_and_organize_data(root_dir: str = "data") -> Dict[str, Any]:
    """Quick function to scan and organize all data"""
    config = DataAggregationConfig(root_data_dir=root_dir)
    manager = DataManager(config)
    
    # Scan all data
    scan_results = manager.scan_all_data()
    
    # Aggregate data
    aggregation_results = manager.aggregate_data()
    
    return {
        "scan": scan_results,
        "aggregation": aggregation_results,
        "inventory": manager.get_data_inventory()
    }

def auto_unzip_all_data(root_dir: str = "data") -> Dict[str, Any]:
    """Quick function to unzip all compressed data"""
    config = DataAggregationConfig(root_data_dir=root_dir)
    manager = DataManager(config)
    
    # Scan for data files
    manager.scan_all_data()
    
    # Unzip all compressed files
    return manager.auto_unzip_data()
