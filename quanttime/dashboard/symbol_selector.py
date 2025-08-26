"""
Custom Symbol Selector Component

This module provides a custom symbol selector that displays available symbols
with their file locations in light gray text.
"""

import streamlit as st
from typing import List, Tuple, Optional
import html
from quanttime.utils.symbol_scanner import get_available_symbols_for_dropdown, get_symbol_info, get_available_dates


def symbol_dropdown(
    label: str = "Symbol",
    key: str = "symbol_selector",
    default_value: Optional[str] = None,
    help_text: str = "Select a symbol from available data files"
) -> Optional[str]:
    """
    Custom symbol dropdown that shows file locations in light gray.
    
    Args:
        label: Label for the dropdown
        key: Unique key for the Streamlit component
        default_value: Default selected value
        help_text: Help text to display
        
    Returns:
        Selected symbol key or None
    """
    
    # Get available symbols
    symbols = get_available_symbols_for_dropdown()
    
    if not symbols:
        st.warning("No symbols found in data directory. Please ensure data is properly organized.")
        return None
    
    # Create options for the dropdown
    options = ["Select a symbol..."] + [display_text for display_text, symbol_key in symbols]
    symbol_keys = [None] + [symbol_key for display_text, symbol_key in symbols]
    
    # Find default index
    default_index = 0  # "Select a symbol..."
    if default_value:
        for i, symbol_key in enumerate(symbol_keys):
            if symbol_key == default_value:
                default_index = i
                break
    
    # Create the dropdown
    selected_index = st.selectbox(
        label,
        options=range(len(options)),
        index=default_index,
        key=key,
        help=help_text,
        format_func=lambda i: _format_symbol_option(options[i]) if i < len(options) else "Invalid"
    )
    
    # Return the selected symbol key
    if selected_index > 0 and selected_index < len(symbol_keys):
        return symbol_keys[selected_index]
    
    return None


def _format_symbol_option(option: str) -> str:
    """
    Format the symbol option for display in the dropdown.
    This strips HTML tags for the dropdown display.
    """
    if option == "Select a symbol...":
        return option
    
    # Remove HTML tags for dropdown display
    # The full HTML will be shown in the help text
    if "<span" in option:
        # Extract the main part before the span
        main_part = option.split("<span")[0].strip()
        return main_part
    
    return option


def symbol_dropdown_with_info(
    label: str = "Symbol",
    key: str = "symbol_selector_info",
    default_value: Optional[str] = None,
    show_info: bool = True
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Symbol dropdown that also returns symbol information.
    
    Returns:
        Tuple of (selected_symbol_key, symbol_info_dict)
    """
    selected_symbol = symbol_dropdown(label, key, default_value)
    
    if selected_symbol and show_info:
        symbol_info = get_symbol_info(selected_symbol)
        if symbol_info:
            # Display symbol information
            with st.expander("Symbol Information", expanded=False):
                st.json(symbol_info)
        
        return selected_symbol, symbol_info
    
    return selected_symbol, None


def es_date_dropdown(
    label: str = "ES Trading Date",
    key: str = "es_date",
    default_value: Optional[str] = None
) -> Optional[str]:
    """
    Dropdown specifically for ES trading dates.
    """
    available_dates = get_available_dates()
    
    if not available_dates:
        st.warning("No ES trading dates found. Please ensure ES MBO data is available.")
        return None
    
    # Create display options with formatted dates
    options = ["Select a trading date..."]
    date_keys = [None]
    
    for date_str in available_dates:
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            display_date = date_obj.strftime("%Y-%m-%d (%A)")
        except:
            display_date = date_str
        
        options.append(display_date)
        date_keys.append(date_str)
    
    # Find default index
    default_index = 0
    if default_value:
        for i, date_key in enumerate(date_keys):
            if date_key == default_value:
                default_index = i
                break
    
    # Create the dropdown
    selected_index = st.selectbox(
        label,
        options=range(len(options)),
        index=default_index,
        key=key,
        help="Select an ES trading date from available data files"
    )
    
    # Return the selected date
    if selected_index > 0 and selected_index < len(date_keys):
        return date_keys[selected_index]
    
    return None


def symbol_dropdown_simple(
    label: str = "Symbol",
    key: str = "symbol_simple",
    default_value: Optional[str] = None
) -> Optional[str]:
    """
    Simple symbol dropdown without HTML formatting.
    """
    symbols = get_available_symbols_for_dropdown()
    
    if not symbols:
        st.warning("No symbols found in data directory.")
        return None
    
    # Create simple options (just the description without file location)
    options = ["Select a symbol..."]
    symbol_keys = [None]
    
    for display_text, symbol_key in symbols:
        # Extract just the description part
        if "<span" in display_text:
            description = display_text.split("<span")[0].strip()
        else:
            description = display_text
        options.append(description)
        symbol_keys.append(symbol_key)
    
    # Find default index
    default_index = 0
    if default_value:
        for i, symbol_key in enumerate(symbol_keys):
            if symbol_key == default_value:
                default_index = i
                break
    
    # Create the dropdown
    selected_index = st.selectbox(
        label,
        options=range(len(options)),
        index=default_index,
        key=key,
        format_func=lambda i: options[i] if i < len(options) else "Invalid"
    )
    
    # Return the selected symbol key
    if selected_index > 0 and selected_index < len(symbol_keys):
        return symbol_keys[selected_index]
    
    return None


def display_symbol_info(symbol_key: str):
    """
    Display detailed information about a selected symbol.
    """
    if not symbol_key:
        return
    
    symbol_info = get_symbol_info(symbol_key)
    if not symbol_info:
        st.warning(f"No information found for symbol: {symbol_key}")
        return
    
    with st.expander("Symbol Details", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Type:**", symbol_info.get('type', 'Unknown'))
            st.write("**Description:**", symbol_info.get('description', 'Unknown'))
            if 'date' in symbol_info:
                st.write("**Date:**", symbol_info['date'])
            if 'display_date' in symbol_info:
                st.write("**Display Date:**", symbol_info['display_date'])
            if 'ticker' in symbol_info:
                st.write("**Ticker:**", symbol_info['ticker'])
        
        with col2:
            st.write("**File Location:**")
            st.code(symbol_info.get('location', 'Unknown'), language='text')
        
        # Show full info as JSON
        st.write("**Full Information:**")
        st.json(symbol_info)
