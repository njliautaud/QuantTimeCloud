#!/usr/bin/env python3
"""
Test script to verify MBO pipeline functionality.
"""

import sys
import os
sys.path.append('.')

from sierraflow.adapter.databento_mbo import DatabentoMBOReader, load_databento_mbo_data
from sierraflow.features.mbo_features import engineer_mbo_features, FeatureConfig
from sierraflow.backtest.mbo_backtest_engine import run_mbo_backtest, BacktestConfig, OrderSide, OrderType
import pandas as pd
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mbo_reader():
    """Test the MBO reader functionality."""
    print("=== Testing MBO Reader ===")
    
    try:
        # Initialize reader
        reader = DatabentoMBOReader("data/es_futures/mbo")
        
        # Get available dates
        dates = reader.get_available_dates()
        print(f"Available dates: {len(dates)} files")
        print(f"Date range: {dates[0]} to {dates[-1]}")
        
        # Get symbol mapping
        symbols = reader.get_symbol_mapping("ES.FUT")
        print(f"Symbol mapping: {len(symbols)} symbols")
        for sym, sym_id in list(symbols.items())[:5]:
            print(f"  {sym} -> {sym_id}")
        
        # Test reading a small file (20250720 is only 2MB)
        print("\nTesting file read...")
        small_date = "20250720"
        if small_date in dates:
            df = reader.read_mbo_file(small_date)
            print(f"Successfully read {len(df)} MBO events from {small_date}")
            if not df.empty:
                print(f"Columns: {list(df.columns)}")
                print(f"Sample data:")
                print(df.head(3))
                return df
        else:
            print(f"Small date {small_date} not found, trying first available date...")
            df = reader.read_mbo_file(dates[0])
            print(f"Successfully read {len(df)} MBO events from {dates[0]}")
            if not df.empty:
                print(f"Columns: {list(df.columns)}")
                print(f"Sample data:")
                print(df.head(3))
                return df
                
    except Exception as e:
        print(f"Error testing MBO reader: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_feature_engineering(mbo_df):
    """Test feature engineering functionality."""
    if mbo_df is None or mbo_df.empty:
        print("No MBO data available for feature engineering test")
        return None
        
    print("\n=== Testing Feature Engineering ===")
    
    try:
        # Use a small subset for testing
        test_df = mbo_df.head(1000)  # First 1000 events
        
        # Configure feature engineering
        config = FeatureConfig(
            short_window=1,
            medium_window=5,
            long_window=15,
            batch_size=1000  # Small batch for testing
        )
        
        print("Engineering features...")
        features_df = engineer_mbo_features(test_df, config)
        
        if not features_df.empty:
            print(f"Successfully engineered {len(features_df)} feature rows")
            print(f"Feature columns: {len(features_df.columns)}")
            print(f"Sample features:")
            print(features_df.head(3))
            
            # Show some key features
            key_features = ['mid_price', 'spread', 'imbalance_ratio', 'volume_5m']
            available_features = [f for f in key_features if f in features_df.columns]
            if available_features:
                print(f"Key features available: {available_features}")
            
            return features_df
        else:
            print("No features generated")
            return None
            
    except Exception as e:
        print(f"Error testing feature engineering: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_backtest_engine(mbo_df):
    """Test backtesting functionality."""
    if mbo_df is None or mbo_df.empty:
        print("No MBO data available for backtest test")
        return None
        
    print("\n=== Testing Backtest Engine ===")
    
    try:
        # Use a small subset for testing
        test_df = mbo_df.head(5000)  # First 5000 events
        
        # Configure backtest
        config = BacktestConfig(
            initial_capital=100000.0,
            commission_per_contract=2.4,
            slippage_ticks=0.5,
            max_position_size=10,
            max_daily_loss=1000.0,
            batch_size=1000
        )
        
        # Simple test strategy
        def test_strategy(engine, mbo_event):
            """Simple test strategy that places a few orders."""
            if not engine.current_price:
                return
            
            # Get order book features
            ob_features = engine.feature_engineer.get_order_book_features()
            if not ob_features:
                return
            
            # Simple logic: buy if imbalance is positive, sell if negative
            imbalance = ob_features.get('imbalance_ratio', 0)
            
            if imbalance > 0.05 and engine.position.size <= 0:
                engine.place_order(OrderSide.BUY, OrderType.MARKET, 1)
            elif imbalance < -0.05 and engine.position.size >= 0:
                engine.place_order(OrderSide.SELL, OrderType.MARKET, 1)
        
        print("Running backtest...")
        result = run_mbo_backtest(test_df, test_strategy, config)
        
        print("Backtest completed!")
        print(f"Total Return: {result.total_return:.2%}")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {result.max_drawdown:.2%}")
        print(f"Total Trades: {result.total_trades}")
        print(f"Win Rate: {result.win_rate:.2%}")
        print(f"Volume Traded: {result.total_volume_traded}")
        print(f"Avg Slippage: ${result.avg_slippage:.4f}")
        
        return result
        
    except Exception as e:
        print(f"Error testing backtest engine: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main test function."""
    print("Starting MBO Pipeline Test")
    print("=" * 50)
    
    # Test 1: MBO Reader
    mbo_df = test_mbo_reader()
    
    # Test 2: Feature Engineering
    features_df = test_feature_engineering(mbo_df)
    
    # Test 3: Backtest Engine
    backtest_result = test_backtest_engine(mbo_df)
    
    print("\n" + "=" * 50)
    print("Pipeline Test Summary:")
    print(f"✓ MBO Reader: {'PASS' if mbo_df is not None else 'FAIL'}")
    print(f"✓ Feature Engineering: {'PASS' if features_df is not None else 'FAIL'}")
    print(f"✓ Backtest Engine: {'PASS' if backtest_result is not None else 'FAIL'}")
    
    if all([mbo_df is not None, features_df is not None, backtest_result is not None]):
        print("\n🎉 All tests passed! The MBO pipeline is fully functional.")
    else:
        print("\n❌ Some tests failed. Check the error messages above.")

if __name__ == "__main__":
    main()
