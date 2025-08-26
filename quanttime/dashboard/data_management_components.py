"""
Data Management Streamlit Components for QuantTime
Provides UI for data scanning, unzipping, and organization
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import time
from typing import Dict, Any, List

from quanttime.data.data_manager import (
    DataManager,
    DataAggregationConfig,
    create_data_manager,
    scan_and_organize_data,
    auto_unzip_all_data
)

def render_data_management_dashboard():
    """Main data management dashboard"""
    st.title("📊 Databento Data Management Dashboard")
    st.markdown("Comprehensive Databento data scanning, unzipping, and organization system")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Data directory
        data_dir = st.text_input(
            "Data Directory",
            value="data",
            help="Root directory for organized data"
        )
        
        # Auto-unzip toggle
        auto_unzip = st.checkbox(
            "Auto-unzip compressed files",
            value=True,
            help="Automatically unzip compressed data files"
        )
        
        # Remove duplicates toggle
        remove_duplicates = st.checkbox(
            "Remove duplicates",
            value=True,
            help="Remove duplicate files based on content hash"
        )
        
        # Max workers for parallel processing
        max_workers = st.slider(
            "Max Workers",
            min_value=1,
            max_value=8,
            value=4,
            help="Number of parallel workers for processing"
        )
        
        # Create configuration
        config = DataAggregationConfig(
            root_data_dir=data_dir,
            auto_unzip=auto_unzip,
            remove_duplicates=remove_duplicates,
            max_workers=max_workers
        )
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Data Scan", 
        "📦 Auto Unzip", 
        "🔄 Data Aggregation",
        "📊 Data Inventory",
        "🧹 Cleanup"
    ])
    
    with tab1:
        render_data_scan_tab(config)
    
    with tab2:
        render_auto_unzip_tab(config)
    
    with tab3:
        render_data_aggregation_tab(config)
    
    with tab4:
        render_data_inventory_tab(config)
    
    with tab5:
        render_cleanup_tab(config)

def render_data_scan_tab(config: DataAggregationConfig):
    """Data scanning tab"""
    st.header("🔍 Databento Data Scanning")
    st.markdown("Scan all available Databento data files in the project directory")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🚀 Start Scan", type="primary", key="scan_start_btn"):
            with st.spinner("Scanning data files..."):
                try:
                    manager = create_data_manager(config)
                    scan_results = manager.scan_all_data()
                    
                    # Store results in session state
                    st.session_state.scan_results = scan_results
                    st.session_state.data_manager = manager
                    
                    st.success("✅ Data scan completed!")
                    
                except Exception as e:
                    st.error(f"❌ Error during scan: {e}")
    
    with col2:
        if st.button("🔄 Refresh Results", key="scan_refresh_btn"):
            if 'scan_results' in st.session_state:
                st.success("Results refreshed!")
            else:
                st.warning("No scan results available. Run a scan first.")
    
    # Display scan results
    if 'scan_results' in st.session_state:
        results = st.session_state.scan_results
        
        # Summary metrics
        summary = results.get('summary', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Files",
                summary.get('total_files', 0)
            )
        
        with col2:
            st.metric(
                "Compressed Files",
                summary.get('compressed_files', 0)
            )
        
        with col3:
            st.metric(
                "Total Size (MB)",
                f"{summary.get('total_size_mb', 0):.1f}"
            )
        
        with col4:
            st.metric(
                "Datasets",
                len(summary.get('datasets', []))
            )
        
        # Detailed results
        st.subheader("📋 Scan Details")
        
        # Date range
        date_range = summary.get('date_range', {})
        if date_range.get('start') and date_range.get('end'):
            st.info(f"📅 Date Range: {date_range['start']} to {date_range['end']}")
        
        # Datasets
        datasets = summary.get('datasets', [])
        if datasets:
            st.write("**Datasets Found:**")
            for dataset in datasets:
                st.write(f"• {dataset}")
        
        # Schemas
        schemas = summary.get('schemas', [])
        if schemas:
            st.write("**Data Schemas:**")
            for schema in schemas:
                st.write(f"• {schema}")
        
        # Compression types
        compression_types = summary.get('compression_types', [])
        if compression_types:
            st.write("**Compression Types:**")
            for comp_type in compression_types:
                st.write(f"• {comp_type}")
        
        # File details (expandable)
        with st.expander("📁 File Details"):
            if 'data_files' in results:
                files_data = []
                for path, info in results['data_files'].items():
                    files_data.append({
                        'File': info.get('file_name', ''),
                        'Path': path,
                        'Size (MB)': f"{info.get('file_size', 0) / (1024*1024):.2f}",
                        'Compressed': 'Yes' if info.get('is_compressed') else 'No',
                        'Date': info.get('date', ''),
                        'Dataset': info.get('dataset', ''),
                        'Schema': info.get('schema', '')
                    })
                
                if files_data:
                    df = pd.DataFrame(files_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.write("No files found")

def render_auto_unzip_tab(config: DataAggregationConfig):
    """Auto unzip tab"""
    st.header("📦 Databento Data Unzipping")
    st.markdown("Automatically unzip all compressed Databento data files")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🚀 Start Unzipping", type="primary", key="unzip_start_btn"):
            with st.spinner("Unzipping compressed files..."):
                try:
                    # Use existing manager if available
                    if 'data_manager' in st.session_state:
                        manager = st.session_state.data_manager
                    else:
                        manager = create_data_manager(config)
                        manager.scan_all_data()
                    
                    unzip_results = manager.auto_unzip_data()
                    
                    # Store results
                    st.session_state.unzip_results = unzip_results
                    st.session_state.data_manager = manager
                    
                    st.success("✅ Unzipping completed!")
                    
                except Exception as e:
                    st.error(f"❌ Error during unzipping: {e}")
    
    with col2:
        if st.button("🔄 Refresh Results", key="unzip_refresh_btn"):
            if 'unzip_results' in st.session_state:
                st.success("Results refreshed!")
            else:
                st.warning("No unzip results available. Run unzipping first.")
    
    # Display unzip results
    if 'unzip_results' in st.session_state:
        results = st.session_state.unzip_results
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Files Unzipped",
                results.get('unzipped', 0)
            )
        
        with col2:
            st.metric(
                "Errors",
                results.get('errors', 0)
            )
        
        with col3:
            st.metric(
                "Status",
                results.get('status', 'unknown')
            )
        
        # Detailed results
        if 'details' in results and results['details']:
            st.subheader("📋 Unzipping Details")
            
            details_data = []
            for detail in results['details']:
                details_data.append({
                    'File': detail.get('file', ''),
                    'Status': detail.get('status', ''),
                    'Extracted To': detail.get('extracted_to', ''),
                    'Error': detail.get('error', '')
                })
            
            df = pd.DataFrame(details_data)
            st.dataframe(df, use_container_width=True)

def render_data_aggregation_tab(config: DataAggregationConfig):
    """Data aggregation tab"""
    st.header("🔄 Data Aggregation")
    st.markdown("Aggregate and organize all data files")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🚀 Start Aggregation", type="primary", key="aggregation_start_btn"):
            with st.spinner("Aggregating data..."):
                try:
                    # Use existing manager if available
                    if 'data_manager' in st.session_state:
                        manager = st.session_state.data_manager
                    else:
                        manager = create_data_manager(config)
                        manager.scan_all_data()
                    
                    aggregation_results = manager.aggregate_data()
                    
                    # Store results
                    st.session_state.aggregation_results = aggregation_results
                    st.session_state.data_manager = manager
                    
                    st.success("✅ Data aggregation completed!")
                    
                except Exception as e:
                    st.error(f"❌ Error during aggregation: {e}")
    
    with col2:
        if st.button("🔄 Refresh Results", key="aggregation_refresh_btn"):
            if 'aggregation_results' in st.session_state:
                st.success("Results refreshed!")
            else:
                st.warning("No aggregation results available. Run aggregation first.")
    
    # Display aggregation results
    if 'aggregation_results' in st.session_state:
        results = st.session_state.aggregation_results
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Files",
                results.get('total_files', 0)
            )
        
        with col2:
            st.metric(
                "Extracted Files",
                results.get('extracted_files', 0)
            )
        
        with col3:
            st.metric(
                "Duplicate Groups",
                results.get('duplicates', {}).get('duplicate_groups', 0)
            )
        
        with col4:
            st.metric(
                "Status",
                results.get('status', 'unknown')
            )
        
        # Organization details
        if 'organization' in results:
            org = results['organization']
            
            st.subheader("📊 Data Organization")
            
            # By dataset
            if 'datasets' in org and org['datasets']:
                st.write("**By Dataset:**")
                for dataset, info in org['datasets'].items():
                    with st.expander(f"📁 {dataset}"):
                        st.write(f"Files: {len(info['files'])}")
                        st.write(f"Total Size: {info['total_size_mb']:.2f} MB")
                        if info['date_range']['start']:
                            st.write(f"Date Range: {info['date_range']['start']} to {info['date_range']['end']}")
                        
                        # Show files
                        if info['files']:
                            files_df = pd.DataFrame(info['files'])
                            st.dataframe(files_df, use_container_width=True)
            
            # By date
            if 'by_date' in org and org['by_date']:
                st.write("**By Date:**")
                dates_data = []
                for date, files in org['by_date'].items():
                    total_size = sum(f['size_mb'] for f in files)
                    dates_data.append({
                        'Date': date,
                        'Files': len(files),
                        'Total Size (MB)': f"{total_size:.2f}"
                    })
                
                if dates_data:
                    dates_df = pd.DataFrame(dates_data)
                    st.dataframe(dates_df, use_container_width=True)
            
            # By schema
            if 'by_schema' in org and org['by_schema']:
                st.write("**By Schema:**")
                schemas_data = []
                for schema, files in org['by_schema'].items():
                    total_size = sum(f['size_mb'] for f in files)
                    schemas_data.append({
                        'Schema': schema,
                        'Files': len(files),
                        'Total Size (MB)': f"{total_size:.2f}"
                    })
                
                if schemas_data:
                    schemas_df = pd.DataFrame(schemas_data)
                    st.dataframe(schemas_df, use_container_width=True)

def render_data_inventory_tab(config: DataAggregationConfig):
    """Data inventory tab"""
    st.header("📊 Data Inventory")
    st.markdown("Current data inventory and statistics")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if st.button("🔄 Refresh Inventory", type="primary", key="inventory_refresh_btn"):
            try:
                if 'data_manager' in st.session_state:
                    manager = st.session_state.data_manager
                else:
                    manager = create_data_manager(config)
                    manager.scan_all_data()
                
                inventory = manager.get_data_inventory()
                st.session_state.inventory = inventory
                st.session_state.data_manager = manager
                
                st.success("✅ Inventory refreshed!")
                
            except Exception as e:
                st.error(f"❌ Error refreshing inventory: {e}")

    with col2:
        if st.button("📥 Export Inventory", key="inventory_export_btn"):
            if 'inventory' in st.session_state:
                inventory = st.session_state.inventory
                
                # Export as JSON
                json_str = json.dumps(inventory, indent=2, default=str)
                st.download_button(
                    label="📥 Download JSON",
                    data=json_str,
                    file_name=f"data_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    # Display inventory
    if 'inventory' in st.session_state:
        inventory = st.session_state.inventory
        
        # Summary
        summary = inventory.get('summary', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Files",
                summary.get('total_files', 0)
            )
        
        with col2:
            st.metric(
                "Compressed Files",
                summary.get('compressed_files', 0)
            )
        
        with col3:
            st.metric(
                "Extracted Files",
                summary.get('extracted_files', 0)
            )
        
        with col4:
            st.metric(
                "Duplicate Files",
                summary.get('duplicate_files', 0)
            )
        
        # Total size
        total_size = summary.get('total_size_mb', 0)
        st.metric("Total Size", f"{total_size:.2f} MB")
        
        # Date range
        date_range = summary.get('date_range', {})
        if date_range.get('start') and date_range.get('end'):
            st.info(f"📅 Date Range: {date_range['start']} to {date_range['end']}")
        
        # Detailed breakdown
        st.subheader("📋 Detailed Breakdown")
        
        # Files table
        if 'files' in inventory:
            files_data = []
            for path, info in inventory['files'].items():
                files_data.append({
                    'File': info.get('file_name', ''),
                    'Size (MB)': f"{info.get('file_size', 0) / (1024*1024):.2f}",
                    'Compressed': 'Yes' if info.get('is_compressed') else 'No',
                    'Duplicate': 'Yes' if info.get('is_duplicate') else 'No',
                    'Date': info.get('date', ''),
                    'Dataset': info.get('dataset', ''),
                    'Schema': info.get('schema', '')
                })
            
            if files_data:
                df = pd.DataFrame(files_data)
                st.dataframe(df, use_container_width=True)
        
        # Extracted files
        if 'extracted' in inventory and inventory['extracted']:
            st.write("**Extracted Files:**")
            extracted_data = []
            for original, extracted in inventory['extracted'].items():
                extracted_data.append({
                    'Original': Path(original).name,
                    'Extracted To': extracted
                })
            
            if extracted_data:
                extracted_df = pd.DataFrame(extracted_data)
                st.dataframe(extracted_df, use_container_width=True)
        
        # Duplicates
        if 'duplicates' in inventory and inventory['duplicates']:
            st.write("**Duplicate Groups:**")
            for primary, duplicates in inventory['duplicates'].items():
                with st.expander(f"📁 {Path(primary).name} ({len(duplicates)} duplicates)"):
                    st.write(f"Primary: {primary}")
                    st.write("Duplicates:")
                    for dup in duplicates:
                        st.write(f"• {dup}")

def render_cleanup_tab(config: DataAggregationConfig):
    """Cleanup tab"""
    st.header("🧹 Data Cleanup")
    st.markdown("Clean up duplicate files and organize data")
    
    # Duplicate cleanup
    st.subheader("🗑️ Duplicate Cleanup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Check Duplicates", type="primary"):
            try:
                if 'data_manager' in st.session_state:
                    manager = st.session_state.data_manager
                else:
                    manager = create_data_manager(config)
                    manager.scan_all_data()
                
                duplicate_results = manager.detect_duplicates()
                st.session_state.duplicate_results = duplicate_results
                st.session_state.data_manager = manager
                
                st.success("✅ Duplicate check completed!")
                
            except Exception as e:
                st.error(f"❌ Error checking duplicates: {e}")
    
    with col2:
        if st.button("🗑️ Cleanup Duplicates"):
            if 'data_manager' in st.session_state:
                manager = st.session_state.data_manager
                
                # First show dry run
                dry_run_results = manager.cleanup_duplicates(dry_run=True)
                
                if dry_run_results['would_delete'] > 0:
                    st.warning(f"Would delete {dry_run_results['would_delete']} files ({dry_run_results['space_freed_mb']:.2f} MB)")
                    
                    if st.button("⚠️ Confirm Deletion", type="secondary"):
                        with st.spinner("Deleting duplicates..."):
                            cleanup_results = manager.cleanup_duplicates(dry_run=False)
                            st.session_state.cleanup_results = cleanup_results
                            st.success(f"✅ Deleted {cleanup_results['deleted']} files")
                else:
                    st.info("No duplicates to clean up")
            else:
                st.warning("No data manager available. Run duplicate check first.")
    
    # Display duplicate results
    if 'duplicate_results' in st.session_state:
        results = st.session_state.duplicate_results
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Files",
                results.get('total_files', 0)
            )
        
        with col2:
            st.metric(
                "Unique Files",
                results.get('unique_files', 0)
            )
        
        with col3:
            st.metric(
                "Duplicate Files",
                results.get('duplicate_files', 0)
            )
        
        with col4:
            st.metric(
                "Space Saved (MB)",
                f"{results.get('space_saved_mb', 0):.2f}"
            )
        
        # Duplicate details
        if 'details' in results and results['details']:
            st.subheader("📋 Duplicate Details")
            
            for primary, duplicates in results['details'].items():
                with st.expander(f"📁 {Path(primary).name} ({len(duplicates)} duplicates)"):
                    st.write(f"**Primary:** {primary}")
                    st.write("**Duplicates:**")
                    for dup in duplicates:
                        st.write(f"• {dup}")
    
    # Display cleanup results
    if 'cleanup_results' in st.session_state:
        results = st.session_state.cleanup_results
        
        st.subheader("🧹 Cleanup Results")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Files Deleted",
                results.get('deleted', 0)
            )
        
        with col2:
            st.metric(
                "Errors",
                results.get('errors', 0)
            )
        
        with col3:
            st.metric(
                "Space Freed (MB)",
                f"{results.get('space_freed_mb', 0):.2f}"
            )

# Quick action functions
def quick_data_scan():
    """Quick data scan function"""
    try:
        results = scan_and_organize_data()
        return results
    except Exception as e:
        st.error(f"Error in quick scan: {e}")
        return None

def quick_unzip_all():
    """Quick unzip all function"""
    try:
        results = auto_unzip_all_data()
        return results
    except Exception as e:
        st.error(f"Error in quick unzip: {e}")
        return None
