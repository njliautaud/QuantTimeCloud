"""
Date Range Selector Component for QuantTime ML Trading Suite.

This module provides a calendar-style date range selector that shows available
dates as cards and allows users to select training date ranges.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

from ..adapter.databento_loader import get_databento_loader

logger = logging.getLogger(__name__)


def render_date_range_selector(
    data_dir: str = "data/es_futures/mbo",
    key_prefix: str = "training"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Render a calendar-style date range selector for training data.
    
    Args:
        data_dir: Directory containing DBN files
        key_prefix: Prefix for session state keys
        
    Returns:
        Tuple of (start_date, end_date) strings in YYYYMMDD format
    """
    st.subheader("📅 Training Date Range Selection")
    
    try:
        # Get available dates
        loader = get_databento_loader(data_dir=data_dir)
        available_dates = loader.get_available_dates()
        
        if not available_dates:
            st.warning("No data files found. Please ensure data is in the correct directory.")
            return None, None
        
        # Convert dates to datetime objects for better handling
        date_objects = []
        for date_str in available_dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y%m%d")
                date_objects.append(date_obj)
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}")
        
        if not date_objects:
            st.error("No valid dates found in data files.")
            return None, None
        
        # Sort dates
        date_objects.sort()
        
        # Display available dates as cards
        st.write("**Available Trading Days:**")
        
        # Create a grid of date cards
        cols = st.columns(7)  # 7 days per row
        selected_dates = []
        
        for i, date_obj in enumerate(date_objects):
            col_idx = i % 7
            with cols[col_idx]:
                # Create a card-like display for each date
                date_str = date_obj.strftime("%Y%m%d")
                display_date = date_obj.strftime("%m/%d")
                day_name = date_obj.strftime("%a")
                
                # Check if this date is selected
                start_key = f"{key_prefix}_start_date"
                end_key = f"{key_prefix}_end_date"
                
                start_date = st.session_state.get(start_key)
                end_date = st.session_state.get(end_key)
                
                is_selected = False
                if start_date and end_date:
                    if start_date <= date_str <= end_date:
                        is_selected = True
                
                # Style the card based on selection
                if is_selected:
                    st.markdown(f"""
                    <div style="
                        background-color: #4CAF50; 
                        color: white; 
                        padding: 10px; 
                        border-radius: 5px; 
                        text-align: center;
                        margin: 2px;
                    ">
                        <strong>{day_name}</strong><br>
                        {display_date}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background-color: #f0f0f0; 
                        color: #333; 
                        padding: 10px; 
                        border-radius: 5px; 
                        text-align: center;
                        margin: 2px;
                        cursor: pointer;
                    ">
                        <strong>{day_name}</strong><br>
                        {display_date}
                    </div>
                    """, unsafe_allow_html=True)
        
        st.write("---")
        
        # Date range selection
        st.write("**Select Training Date Range:**")
        
        # Convert to pandas datetime for easier handling
        df_dates = pd.DataFrame({
            'date': date_objects,
            'date_str': [d.strftime("%Y%m%d") for d in date_objects]
        })
        
        # Date range picker
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=date_objects[0].date(),
                min_value=date_objects[0].date(),
                max_value=date_objects[-1].date(),
                key=f"{key_prefix}_start_date_picker"
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=date_objects[-1].date(),
                min_value=date_objects[0].date(),
                max_value=date_objects[-1].date(),
                key=f"{key_prefix}_end_date_picker"
            )
        
        # Convert to string format
        start_date_str = start_date.strftime("%Y%m%d")
        end_date_str = end_date.strftime("%Y%m%d")
        
        # Validate date range
        if start_date > end_date:
            st.error("Start date must be before end date.")
            return None, None
        
        # Check if dates are available
        available_date_strs = [d.strftime("%Y%m%d") for d in date_objects]
        if start_date_str not in available_date_strs:
            st.error(f"Start date {start_date_str} not available in data.")
            return None, None
        
        if end_date_str not in available_date_strs:
            st.error(f"End date {end_date_str} not available in data.")
            return None, None
        
        # Store in session state
        st.session_state[f"{key_prefix}_start_date"] = start_date_str
        st.session_state[f"{key_prefix}_end_date"] = end_date_str
        
        # Display selected range info
        selected_dates = [d for d in available_date_strs if start_date_str <= d <= end_date_str]
        
        st.success(f"✅ Selected {len(selected_dates)} trading days: {start_date_str} to {end_date_str}")
        
        # Show selected dates
        if len(selected_dates) <= 10:
            st.write(f"**Selected dates:** {', '.join(selected_dates)}")
        else:
            st.write(f"**Selected dates:** {', '.join(selected_dates[:5])} ... {', '.join(selected_dates[-5:])}")
        
        return start_date_str, end_date_str
        
    except Exception as e:
        logger.error(f"Error in date range selector: {e}")
        st.error(f"Error loading available dates: {e}")
        return None, None


def get_available_dates_for_display(data_dir: str = "data/es_futures/mbo") -> List[str]:
    """
    Get available dates for display purposes.
    
    Args:
        data_dir: Directory containing DBN files
        
    Returns:
        List of available date strings
    """
    try:
        loader = get_databento_loader(data_dir=data_dir)
        return loader.get_available_dates()
    except Exception as e:
        logger.error(f"Error getting available dates: {e}")
        return []


def validate_date_range(start_date: str, end_date: str, available_dates: List[str]) -> bool:
    """
    Validate that the selected date range is available.
    
    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        available_dates: List of available dates
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if dates are in correct format
        datetime.strptime(start_date, "%Y%m%d")
        datetime.strptime(end_date, "%Y%m%d")
        
        # Check if start date is before end date
        if start_date > end_date:
            return False
        
        # Check if dates are available
        if start_date not in available_dates or end_date not in available_dates:
            return False
        
        return True
        
    except ValueError:
        return False
