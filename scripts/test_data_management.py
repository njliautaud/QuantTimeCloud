#!/usr/bin/env python3
"""
Test script for the Data Management System
Demonstrates scanning, unzipping, and organizing data
"""

import sys
from pathlib import Path
import logging

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from quanttime.data.data_manager import (
    DataManager,
    DataAggregationConfig,
    scan_and_organize_data,
    auto_unzip_all_data
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_data_scan():
    """Test data scanning functionality"""
    print("🔍 Testing Data Scanning...")
    print("=" * 50)
    
    try:
        # Create data manager with default config
        config = DataAggregationConfig(
            root_data_dir = "data_organized/es_futures",
            auto_unzip=True,
            remove_duplicates=True,
            max_workers=4
        )
        
        manager = DataManager(config)
        
        # Scan all data
        scan_results = manager.scan_all_data()
        
        # Display results
        summary = scan_results.get('summary', {})
        
        print(f"📊 Scan Results:")
        print(f"  Total Files: {summary.get('total_files', 0)}")
        print(f"  Compressed Files: {summary.get('compressed_files', 0)}")
        print(f"  Total Size: {summary.get('total_size_mb', 0):.2f} MB")
        print(f"  Datasets: {len(summary.get('datasets', []))}")
        print(f"  Schemas: {len(summary.get('schemas', []))}")
        
        # Date range
        date_range = summary.get('date_range', {})
        if date_range.get('start') and date_range.get('end'):
            print(f"  Date Range: {date_range['start']} to {date_range['end']}")
        
        # Show datasets
        datasets = summary.get('datasets', [])
        if datasets:
            print(f"\n📁 Datasets Found:")
            for dataset in datasets:
                print(f"  • {dataset}")
        
        # Show schemas
        schemas = summary.get('schemas', [])
        if schemas:
            print(f"\n📋 Data Schemas:")
            for schema in schemas:
                print(f"  • {schema}")
        
        # Show compression types
        compression_types = summary.get('compression_types', [])
        if compression_types:
            print(f"\n🗜️ Compression Types:")
            for comp_type in compression_types:
                print(f"  • {comp_type}")
        
        # Show some file details
        if 'data_files' in scan_results:
            print(f"\n📄 Sample Files:")
            file_count = 0
            for path, info in scan_results['data_files'].items():
                if file_count < 5:  # Show first 5 files
                    size_mb = info.get('file_size', 0) / (1024 * 1024)
                    print(f"  • {info.get('file_name', '')} ({size_mb:.2f} MB)")
                    file_count += 1
                else:
                    break
            
            if len(scan_results['data_files']) > 5:
                print(f"  ... and {len(scan_results['data_files']) - 5} more files")
        
        return manager, scan_results
        
    except Exception as e:
        print(f"❌ Error during data scan: {e}")
        return None, None

def test_auto_unzip(manager):
    """Test automatic unzipping functionality"""
    print("\n📦 Testing Auto Unzipping...")
    print("=" * 50)
    
    if not manager:
        print("❌ No manager available for unzipping test")
        return None
    
    try:
        # Auto unzip all compressed files
        unzip_results = manager.auto_unzip_data()
        
        print(f"📊 Unzipping Results:")
        print(f"  Status: {unzip_results.get('status', 'unknown')}")
        print(f"  Files Unzipped: {unzip_results.get('unzipped', 0)}")
        print(f"  Errors: {unzip_results.get('errors', 0)}")
        
        # Show details
        if 'details' in unzip_results and unzip_results['details']:
            print(f"\n📋 Unzipping Details:")
            for detail in unzip_results['details'][:5]:  # Show first 5
                status = detail.get('status', '')
                file_name = detail.get('file', '')
                if status == 'success':
                    extracted_to = detail.get('extracted_to', '')
                    print(f"  ✅ {file_name} → {extracted_to}")
                else:
                    error = detail.get('error', '')
                    print(f"  ❌ {file_name}: {error}")
            
            if len(unzip_results['details']) > 5:
                print(f"  ... and {len(unzip_results['details']) - 5} more files")
        
        return unzip_results
        
    except Exception as e:
        print(f"❌ Error during unzipping: {e}")
        return None

def test_data_aggregation(manager):
    """Test data aggregation functionality"""
    print("\n🔄 Testing Data Aggregation...")
    print("=" * 50)
    
    if not manager:
        print("❌ No manager available for aggregation test")
        return None
    
    try:
        # Aggregate all data
        aggregation_results = manager.aggregate_data()
        
        print(f"📊 Aggregation Results:")
        print(f"  Status: {aggregation_results.get('status', 'unknown')}")
        print(f"  Total Files: {aggregation_results.get('total_files', 0)}")
        print(f"  Extracted Files: {aggregation_results.get('extracted_files', 0)}")
        
        # Duplicate analysis
        duplicates = aggregation_results.get('duplicates', {})
        print(f"  Duplicate Groups: {duplicates.get('duplicate_groups', 0)}")
        print(f"  Duplicate Files: {duplicates.get('duplicate_files', 0)}")
        print(f"  Space Saved: {duplicates.get('space_saved_mb', 0):.2f} MB")
        
        # Organization details
        if 'organization' in aggregation_results:
            org = aggregation_results['organization']
            
            print(f"\n📊 Data Organization:")
            print(f"  Total Size: {org.get('total_size_mb', 0):.2f} MB")
            
            # By dataset
            if 'datasets' in org and org['datasets']:
                print(f"\n📁 By Dataset:")
                for dataset, info in org['datasets'].items():
                    print(f"  • {dataset}: {len(info['files'])} files, {info['total_size_mb']:.2f} MB")
            
            # By schema
            if 'by_schema' in org and org['by_schema']:
                print(f"\n📋 By Schema:")
                for schema, files in org['by_schema'].items():
                    total_size = sum(f['size_mb'] for f in files)
                    print(f"  • {schema}: {len(files)} files, {total_size:.2f} MB")
        
        return aggregation_results
        
    except Exception as e:
        print(f"❌ Error during aggregation: {e}")
        return None

def test_duplicate_detection(manager):
    """Test duplicate detection functionality"""
    print("\n🔍 Testing Duplicate Detection...")
    print("=" * 50)
    
    if not manager:
        print("❌ No manager available for duplicate detection test")
        return None
    
    try:
        # Detect duplicates
        duplicate_results = manager.detect_duplicates()
        
        print(f"📊 Duplicate Detection Results:")
        print(f"  Total Files: {duplicate_results.get('total_files', 0)}")
        print(f"  Unique Files: {duplicate_results.get('unique_files', 0)}")
        print(f"  Duplicate Files: {duplicate_results.get('duplicate_files', 0)}")
        print(f"  Duplicate Groups: {duplicate_results.get('duplicate_groups', 0)}")
        print(f"  Space Saved: {duplicate_results.get('space_saved_mb', 0):.2f} MB")
        
        # Show duplicate details
        if 'details' in duplicate_results and duplicate_results['details']:
            print(f"\n📋 Duplicate Groups:")
            for primary, duplicates in duplicate_results['details'].items():
                primary_name = Path(primary).name
                print(f"  📁 {primary_name} ({len(duplicates)} duplicates)")
                for dup in duplicates[:3]:  # Show first 3 duplicates
                    dup_name = Path(dup).name
                    print(f"    • {dup_name}")
                if len(duplicates) > 3:
                    print(f"    ... and {len(duplicates) - 3} more")
        
        return duplicate_results
        
    except Exception as e:
        print(f"❌ Error during duplicate detection: {e}")
        return None

def test_quick_functions():
    """Test quick utility functions"""
    print("\n⚡ Testing Quick Functions...")
    print("=" * 50)
    
    try:
        # Test quick scan and organize
        print("🔍 Quick scan and organize...")
        results = scan_and_organize_data()
        
        if results:
            print("✅ Quick scan completed successfully")
            scan_summary = results.get('scan', {}).get('summary', {})
            print(f"  Found {scan_summary.get('total_files', 0)} files")
            print(f"  Total size: {scan_summary.get('total_size_mb', 0):.2f} MB")
        else:
            print("❌ Quick scan failed")
        
        # Test quick unzip
        print("\n📦 Quick unzip all...")
        unzip_results = auto_unzip_all_data()
        
        if unzip_results:
            print("✅ Quick unzip completed successfully")
            print(f"  Unzipped: {unzip_results.get('unzipped', 0)} files")
            print(f"  Errors: {unzip_results.get('errors', 0)}")
        else:
            print("❌ Quick unzip failed")
        
    except Exception as e:
        print(f"❌ Error in quick functions: {e}")

def main():
    """Main test function"""
    print("🚀 QuantTime Data Management System Test")
    print("=" * 60)
    
    # Test data scanning
    manager, scan_results = test_data_scan()
    
    if manager:
        # Test auto unzipping
        unzip_results = test_auto_unzip(manager)
        
        # Test data aggregation
        aggregation_results = test_data_aggregation(manager)
        
        # Test duplicate detection
        duplicate_results = test_duplicate_detection(manager)
        
        # Test quick functions
        test_quick_functions()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        
        # Final summary
        if scan_results:
            summary = scan_results.get('summary', {})
            print(f"\n📊 Final Summary:")
            print(f"  Total Files: {summary.get('total_files', 0)}")
            print(f"  Total Size: {summary.get('total_size_mb', 0):.2f} MB")
            print(f"  Datasets: {len(summary.get('datasets', []))}")
            print(f"  Schemas: {len(summary.get('schemas', []))}")
    else:
        print("\n❌ Tests failed - no manager available")

if __name__ == "__main__":
    main()
