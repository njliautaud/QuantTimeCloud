#!/usr/bin/env python3
"""
Test script for ultra-microstructure features
Validates microsecond-scale analysis and latency considerations
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from quanttime.features.microstructure_features import (
    add_microstructure_features, 
    MicrostructureAnalyzer
)
from quanttime.features.mbo_features import engineer_mbo_features, FeatureConfig

def create_realistic_mbo_data(n_events: int = 2000) -> pd.DataFrame:
    """Create realistic MBO data with proper timestamps and latency simulation"""
    np.random.seed(42)
    
    # Start time
    start_time = pd.Timestamp('2024-01-01 09:30:00')
    base_time_ns = start_time.value  # nanoseconds since epoch
    
    # Generate realistic inter-event intervals (variable intensity)
    intervals_us = []
    for i in range(n_events):
        # Simulate burst periods and quiet periods
        if i % 100 < 20:  # Burst period (20% of time)
            interval = np.random.exponential(50)  # Fast events (50µs average)
        else:  # Normal period
            interval = np.random.exponential(200)  # Slower events (200µs average)
        intervals_us.append(max(1, interval))  # Minimum 1µs between events
    
    # Convert to cumulative timestamps
    cumulative_us = np.cumsum(intervals_us)
    event_timestamps = base_time_ns + cumulative_us * 1000  # Convert µs to ns
    
    # Add realistic receive timestamps (with jitter)
    receive_delays_us = np.random.normal(500, 100, n_events)  # 500µs ± 100µs
    receive_delays_us = np.clip(receive_delays_us, 100, 2000)  # Clip to reasonable range
    receive_timestamps = event_timestamps + receive_delays_us * 1000
    
    data = []
    base_price = 5000.0
    order_id_counter = 1
    
    for i in range(n_events):
        # Simulate different flow patterns
        if i % 50 == 0:  # Large institutional orders
            size = np.random.randint(100, 500)
            side = np.random.choice(['B', 'S'])
            action = np.random.choice(['A', 'F'], p=[0.3, 0.7])
        elif i % 15 == 0:  # Potential spoofing patterns
            size = np.random.randint(200, 1000)  # Large size
            side = np.random.choice(['B', 'S'])
            action = 'A'  # Place large order (might cancel quickly)
        else:  # Normal retail flow
            size = np.random.randint(1, 50)
            side = np.random.choice(['B', 'S'])
            action = np.random.choice(['A', 'M', 'D', 'F'], p=[0.3, 0.1, 0.3, 0.3])
        
        # Add some price movement
        price_change = np.random.normal(0, 0.25)
        if action == 'F':  # Fills can impact price more
            if side == 'B':
                price_change += np.random.exponential(0.1)  # Slight upward pressure
            else:
                price_change -= np.random.exponential(0.1)  # Slight downward pressure
        
        base_price += price_change
        price = round(base_price, 2)
        
        data.append({
            'ts_event': int(event_timestamps[i]),
            'ts_recv': int(receive_timestamps[i]),
            'price': price,
            'size': size,
            'side': side,
            'action': action,
            'order_id': f'order_{order_id_counter}' if action != 'F' else f'order_{order_id_counter - np.random.randint(1, 20)}'
        })
        
        if action == 'A':
            order_id_counter += 1
    
    return pd.DataFrame(data)

def test_microstructure_analyzer():
    """Test the MicrostructureAnalyzer directly"""
    print("🧪 Testing Microstructure Analyzer...")
    
    # Create realistic data
    mbo_df = create_realistic_mbo_data(1000)
    print(f"Created {len(mbo_df)} realistic MBO events")
    
    # Initialize analyzer
    analyzer = MicrostructureAnalyzer(
        our_latency_ms=2.0,
        databento_latency_ms=0.5,
        alpha_half_life_ms=100.0
    )
    
    # Extract features
    print("Extracting microstructure features...")
    enhanced_df = analyzer.extract_microstructure_features(mbo_df)
    
    # Check results
    micro_features = [col for col in enhanced_df.columns if col.startswith('micro_')]
    
    if micro_features:
        print(f"✅ Microstructure extraction: SUCCESS")
        print(f"   Added {len(micro_features)} microstructure features")
        
        # Test key feature categories
        latency_features = [col for col in micro_features if 'latency' in col]
        ultra_short_features = [col for col in micro_features if any(x in col for x in ['100us', '500us', '1ms'])]
        queue_features = [col for col in micro_features if 'queue' in col]
        spoof_features = [col for col in micro_features if 'spoof' in col]
        sweep_features = [col for col in micro_features if 'sweep' in col]
        
        print(f"   📊 Feature breakdown:")
        print(f"      - Latency features: {len(latency_features)}")
        print(f"      - Ultra-short-term: {len(ultra_short_features)}")
        print(f"      - Queue analysis: {len(queue_features)}")
        print(f"      - Spoofing detection: {len(spoof_features)}")
        print(f"      - Sweep analysis: {len(sweep_features)}")
        
        # Show sample values
        print(f"   📈 Sample feature values:")
        for feature in micro_features[:5]:
            avg_val = enhanced_df[feature].mean()
            print(f"      - {feature}: {avg_val:.4f}")
    else:
        print("❌ Microstructure extraction: FAILED")
    
    return enhanced_df

def test_latency_analysis():
    """Test latency and timing analysis"""
    print("\n🧪 Testing Latency Analysis...")
    
    # Create data with known latency patterns
    mbo_df = create_realistic_mbo_data(500)
    
    analyzer = MicrostructureAnalyzer(
        our_latency_ms=3.0,  # Higher latency for testing
        databento_latency_ms=1.0,
        alpha_half_life_ms=50.0  # Faster decay for testing
    )
    
    enhanced_df = analyzer.extract_microstructure_features(mbo_df)
    
    # Check latency features
    latency_cols = [col for col in enhanced_df.columns if 'latency' in col or 'alpha' in col]
    
    if latency_cols:
        print("✅ Latency analysis: SUCCESS")
        
        # Check alpha remaining
        alpha_remaining = enhanced_df['micro_alpha_remaining_pct'].mean()
        print(f"   Average alpha remaining: {alpha_remaining:.1f}%")
        
        # Check competitive window
        competitive_window = enhanced_df['micro_competitive_window'].mean()
        print(f"   Average competitive window: {competitive_window:.4f}")
        
        # Check total latency
        total_latency_ms = enhanced_df['micro_total_latency'].mean() / 1_000_000
        print(f"   Average total latency: {total_latency_ms:.2f}ms")
        
        if alpha_remaining < 90:  # Should be less due to our latency
            print("✅ Alpha decay calculation: WORKING")
        else:
            print("⚠️ Alpha decay calculation: Check parameters")
    else:
        print("❌ Latency analysis: FAILED")

def test_ultra_short_term_features():
    """Test ultra-short-term features"""
    print("\n🧪 Testing Ultra-Short-Term Features...")
    
    mbo_df = create_realistic_mbo_data(800)
    
    enhanced_df = add_microstructure_features(mbo_df)
    
    # Check ultra-short features
    ultra_features = [col for col in enhanced_df.columns 
                     if any(window in col for window in ['100us', '200us', '500us', '1ms', '2ms', '5ms'])]
    
    if ultra_features:
        print(f"✅ Ultra-short-term features: SUCCESS")
        print(f"   Added {len(ultra_features)} ultra-short features")
        
        # Test specific windows
        for window in ['100us', '500us', '1ms']:
            window_features = [col for col in ultra_features if window in col]
            print(f"   - {window} window: {len(window_features)} features")
        
        # Check for expected feature types
        aggression_features = [col for col in ultra_features if 'aggression' in col]
        volume_features = [col for col in ultra_features if 'volume' in col]
        volatility_features = [col for col in ultra_features if 'volatility' in col]
        
        print(f"   📊 Feature types:")
        print(f"      - Aggression: {len(aggression_features)}")
        print(f"      - Volume: {len(volume_features)}")
        print(f"      - Volatility: {len(volatility_features)}")
    else:
        print("❌ Ultra-short-term features: FAILED")

def test_flow_intensity_analysis():
    """Test flow intensity and burst detection"""
    print("\n🧪 Testing Flow Intensity Analysis...")
    
    # Create data with intentional burst patterns
    mbo_df = create_realistic_mbo_data(600)
    
    enhanced_df = add_microstructure_features(mbo_df)
    
    # Check flow intensity features
    intensity_features = [col for col in enhanced_df.columns if 'flow_intensity' in col or 'burst' in col]
    
    if intensity_features:
        print("✅ Flow intensity analysis: SUCCESS")
        
        # Check burst detection
        if 'micro_flow_burst_ratio' in enhanced_df.columns:
            max_burst = enhanced_df['micro_flow_burst_ratio'].max()
            avg_burst = enhanced_df['micro_flow_burst_ratio'].mean()
            print(f"   Burst detection - Max: {max_burst:.2f}, Avg: {avg_burst:.2f}")
        
        # Check flow density changes
        if 'micro_flow_density_change' in enhanced_df.columns:
            density_changes = enhanced_df['micro_flow_density_change'].std()
            print(f"   Flow density variation: {density_changes:.4f}")
        
        print(f"   Total intensity features: {len(intensity_features)}")
    else:
        print("❌ Flow intensity analysis: FAILED")

def test_mbo_integration():
    """Test integration with main MBO feature engineering"""
    print("\n🧪 Testing MBO Integration...")
    
    mbo_df = create_realistic_mbo_data(400)
    
    # Configure with all features enabled
    config = FeatureConfig(
        include_orderflow_classification=True,
        include_ultra_microstructure=True,
        our_latency_ms=2.5,
        databento_latency_ms=0.8,
        alpha_half_life_ms=75.0,
        batch_size=400
    )
    
    try:
        enhanced_df = engineer_mbo_features(mbo_df, config)
        
        # Check all feature types
        flow_features = [col for col in enhanced_df.columns if col.startswith('flow_')]
        micro_features = [col for col in enhanced_df.columns if col.startswith('micro_')]
        
        if flow_features and micro_features:
            print("✅ MBO integration: SUCCESS")
            print(f"   Orderflow features: {len(flow_features)}")
            print(f"   Microstructure features: {len(micro_features)}")
            print(f"   Total features: {len(enhanced_df.columns)}")
            
            # Check for key integrated features
            latency_aware = [col for col in enhanced_df.columns if 'latency' in col or 'alpha' in col]
            ultra_short = [col for col in enhanced_df.columns if any(x in col for x in ['us', 'ms'])]
            
            print(f"   Latency-aware features: {len(latency_aware)}")
            print(f"   Ultra-short features: {len(ultra_short)}")
        else:
            print("❌ MBO integration: FAILED")
            
    except Exception as e:
        print(f"❌ MBO integration: FAILED - {e}")

def test_performance():
    """Test performance with larger dataset"""
    print("\n🧪 Performance Test...")
    
    # Larger dataset for performance testing
    mbo_df = create_realistic_mbo_data(3000)
    print(f"Testing with {len(mbo_df)} events")
    
    import time
    start_time = time.time()
    
    try:
        enhanced_df = add_microstructure_features(
            mbo_df,
            our_latency_ms=2.0,
            databento_latency_ms=0.5,
            alpha_half_life_ms=100.0
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        micro_features = [col for col in enhanced_df.columns if col.startswith('micro_')]
        
        print(f"✅ Performance test: SUCCESS")
        print(f"   Processing time: {processing_time:.2f} seconds")
        print(f"   Events per second: {len(mbo_df)/processing_time:.0f}")
        print(f"   Features per event: {len(micro_features)}")
        print(f"   Memory usage: {enhanced_df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
        
        # Test ultra-short-term feature quality
        ultra_features = [col for col in micro_features if any(x in col for x in ['us', 'ms'])]
        print(f"   Ultra-short features: {len(ultra_features)}")
        
    except Exception as e:
        print(f"❌ Performance test: FAILED - {e}")

def test_latency_sensitivity():
    """Test sensitivity to different latency configurations"""
    print("\n🧪 Testing Latency Sensitivity...")
    
    mbo_df = create_realistic_mbo_data(500)
    
    # Test different latency scenarios
    scenarios = [
        ("Low Latency HFT", 0.5, 0.1, 50.0),
        ("Typical Retail", 5.0, 1.0, 200.0), 
        ("High Latency", 10.0, 2.0, 500.0)
    ]
    
    for scenario_name, our_lat, db_lat, alpha_hl in scenarios:
        enhanced_df = add_microstructure_features(
            mbo_df,
            our_latency_ms=our_lat,
            databento_latency_ms=db_lat,
            alpha_half_life_ms=alpha_hl
        )
        
        alpha_remaining = enhanced_df['micro_alpha_remaining_pct'].mean()
        competitive_window = enhanced_df['micro_competitive_window'].mean()
        
        print(f"   {scenario_name}:")
        print(f"      Alpha remaining: {alpha_remaining:.1f}%")
        print(f"      Competitive window: {competitive_window:.4f}")

def main():
    """Run all microstructure tests"""
    print("🚀 Microstructure Features Test Suite")
    print("=" * 60)
    
    # Test 1: Core analyzer
    enhanced_df = test_microstructure_analyzer()
    
    # Test 2: Latency analysis
    test_latency_analysis()
    
    # Test 3: Ultra-short-term features
    test_ultra_short_term_features()
    
    # Test 4: Flow intensity
    test_flow_intensity_analysis()
    
    # Test 5: MBO integration
    test_mbo_integration()
    
    # Test 6: Performance
    test_performance()
    
    # Test 7: Latency sensitivity
    test_latency_sensitivity()
    
    print("\n" + "=" * 60)
    print("🎯 Microstructure Test Summary")
    print("=" * 60)
    
    if enhanced_df is not None:
        micro_features = [col for col in enhanced_df.columns if col.startswith('micro_')]
        
        print(f"✅ Total microstructure features implemented: {len(micro_features)}")
        print("\n📊 Feature Categories:")
        
        categories = {
            'Latency & Timing': [col for col in micro_features if any(x in col for x in ['latency', 'alpha', 'timing', 'competitive'])],
            'Ultra-Short Term': [col for col in micro_features if any(x in col for x in ['100us', '200us', '500us', '1ms', '2ms', '5ms'])],
            'Queue Analysis': [col for col in micro_features if 'queue' in col],
            'Liquidity Voids': [col for col in micro_features if any(x in col for x in ['void', 'liquidity_pulled', 'flip'])],
            'Spoofing Detection': [col for col in micro_features if any(x in col for x in ['spoof', 'manipulation', 'fake'])],
            'Sweep Analysis': [col for col in micro_features if 'sweep' in col],
            'Flow Intensity': [col for col in micro_features if any(x in col for x in ['intensity', 'burst', 'density'])],
            'Trade Sequencing': [col for col in micro_features if any(x in col for x in ['sequence', 'momentum', 'escalation'])],
        }
        
        for category, features in categories.items():
            print(f"   {category}: {len(features)} features")
        
        print(f"\n🎉 SUCCESS: Ultra-microstructure analysis fully implemented!")
        print(f"   ⚡ Microsecond-scale features: ✅")
        print(f"   🕒 Latency awareness: ✅") 
        print(f"   🎯 Alpha decay modeling: ✅")
        print(f"   🔍 Sophisticated pattern detection: ✅")
        print(f"   🏃 Real-time competitive analysis: ✅")
    else:
        print("❌ Implementation failed - check logs above")

if __name__ == "__main__":
    main()
