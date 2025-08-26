#!/usr/bin/env python3
"""
Update Data Paths Script
Updates all data paths in the codebase to use the new organized data structure.
"""

import os
import re
from pathlib import Path

def update_file_paths(file_path: Path):
    """Update data paths in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Update various data path patterns
        replacements = [
            # Data directory patterns
            (r'data_dir\s*=\s*["\']data["\']', 'data_dir = "data_organized/es_futures"'),
            (r'root_data_dir\s*=\s*["\']data["\']', 'root_data_dir = "data_organized/es_futures"'),
            (r'data_dir\s*=\s*["\']\./data["\']', 'data_dir = "./data_organized/es_futures"'),
            (r'data_dir\s*=\s*["\']\./data["\']', 'data_dir = "./data_organized/es_futures"'),
            
            # Archive directory patterns
            (r'archive_dir\s*=\s*["\']\./archive["\']', 'archive_dir = "./data_organized/archive"'),
            (r'archive_dir\s*=\s*["\']archive["\']', 'archive_dir = "data_organized/archive"'),
            
            # Live stream directory patterns
            (r'live_stream_dir\s*=\s*["\']\./live_streams["\']', 'live_stream_dir = "./data_organized/es_futures/live_streams"'),
            (r'live_stream_dir\s*=\s*["\']live_streams["\']', 'live_stream_dir = "data_organized/es_futures/live_streams"'),
            
            # Path patterns in strings
            (r'["\']data/["\']', '"data_organized/es_futures/"'),
            (r'["\']\./data/["\']', '"./data_organized/es_futures/"'),
            
            # GLBX directory patterns
            (r'["\']GLBX-["\']', '"data_organized/es_futures/mbo/"'),
            (r'["\']\./GLBX-["\']', '"./data_organized/es_futures/mbo/"'),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {file_path}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def main():
    """Main function to update all data paths."""
    print("=" * 60)
    print("QuantTime Data Path Update Script")
    print("=" * 60)
    
    # Files to update
    files_to_update = [
        "quanttime/data/data_manager.py",
        "quanttime/data/pipeline.py", 
        "quanttime/adapter/databento_mbo.py",
        "quanttime/adapter/databento_all_data.py",
        "quanttime/dashboard/data_management_components.py",
        "quanttime/dashboard/databento_components.py",
        "quanttime/runtime/hist_service.py",
        "quanttime/runtime/collector_service.py",
        "scripts/collect.py",
        "scripts/backtest.py",
        "test_data_management.py",
        "test_databento_unzip.py",
        "unzip_databento_data.py"
    ]
    
    updated_count = 0
    
    for file_path in files_to_update:
        path = Path(file_path)
        if path.exists():
            if update_file_paths(path):
                updated_count += 1
        else:
            print(f"File not found: {file_path}")
    
    print(f"\nUpdated {updated_count} files.")
    print("\nData paths have been updated to use the new organized structure:")
    print("- ES data: data_organized/es_futures/")
    print("- MBO data: data_organized/es_futures/mbo/")
    print("- Archive: data_organized/archive/")
    print("- Test data: data_organized/test_data/")
    
    print("\nNext steps:")
    print("1. Test your application to ensure it works with the new paths")
    print("2. Remove the old 'data' directory if everything works correctly")
    print("3. Update any hardcoded paths in your configuration files")

if __name__ == "__main__":
    main()
