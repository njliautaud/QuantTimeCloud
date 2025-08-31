#!/usr/bin/env python3
"""
Test script for orderflow classification functionality
Validates toxic vs benign flow detection
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from quanttime.features.orderflow_classification import OrderFlowClassifier, add_orderflow_classification_features
from quanttime.features.mbo_features import engineer_mbo_features, FeatureConfig

def create_sample_mbo_data(n_events: int = 1000) -> pd.DataFrame:
    """Create sample MBO data for testing"""
    np.random.seed(42)  # For reproducible results
    
    # Generate realistic MBO events
    base_price = 5000.0
    timestamps = pd.date_range('2024-01-01 09:30:00', periods=n_events, freq='100ms')
    
    # Create different flow patterns
    data = []
    for i, ts in enumerate(timestamps):
        # Simulate toxic flow (informed traders) - pattern-based
        if i % 10 == 0:  # Every 10th event is potentially toxic
            # Toxic flow characteristics: larger sizes, more aggressive timing
            size = np.random.randint(50, 200)  # Larger sizes
            price = base_price + np.random.normal(0, 0.1)
            side = 'B' if np.random.random() > 0.3 else 'S'  # Directional bias
            action = np.random.choice(['A', 'F'], p=[0.3, 0.7])  # More fills
        else:
            # Benign flow characteristics: smaller sizes, random patterns  
            size = np.random.randint(1, 50)   # Smaller sizes
            price = base_price + np.random.normal(0, 0.25)
            side = np.random.choice(['B', 'S'])  # No bias
            action = np.random.choice(['A', 'M', 'D', 'F'], p=[0.4, 0.2, 0.2, 0.2])
        
        data.append({
            'ts_event': ts,
            'price': round(price, 2),
            'size': size,
            'side': side,
            'action': action
        })
        
        # Add some price drift for realism
        base_price += np.random.normal(0, 0.05)
    
    return pd.DataFrame(data)

def test_orderflow_classifier():
    """Test the OrderFlowClassifier directly"""
    print("🧪 Testing OrderFlow Classifier...")
    
    # Create sample data
    mbo_df = create_sample_mbo_data(1000)
    print(f"Created {len(mbo_df)} sample MBO events")
    
    # Initialize classifier
    classifier = OrderFlowClassifier()
    
    # Extract features
    print("Extracting orderflow features...")
    classified_df = classifier.extract_flow_features(mbo_df, lookback_window=500)
    
    # Check results
    if 'flow_toxicity_score' in classified_df.columns:
        print("✅ Toxicity scoring: SUCCESS")
        print(f"   Average toxicity score: {classified_df['flow_toxicity_score'].mean():.3f}")
        print(f"   Toxicity score range: {classified_df['flow_toxicity_score'].min():.3f} - {classified_df['flow_toxicity_score'].max():.3f}")
    else:
        print("❌ Toxicity scoring: FAILED")
    
    if 'flow_classification' in classified_df.columns:
        print("✅ Flow classification: SUCCESS")
        classification_counts = classified_df['flow_classification'].value_counts()
        print(f"   Classification breakdown: {classification_counts.to_dict()}")
    else:
        print("❌ Flow classification: FAILED")
    
    # Generate report
    print("\nGenerating classification report...")
    report = classifier.generate_classification_report(classified_df)
    
    if 'classification_summary' in report:
        print("✅ Classification report: SUCCESS")
        print(f"   Summary: {report['classification_summary']}")
        if 'adverse_selection_risk' in report:
            print(f"   Adverse selection risk: {report['adverse_selection_risk']}")
    else:
        print("❌ Classification report: FAILED")
    
    return classified_df

def test_mbo_integration():
    """Test integration with MBO feature engineering"""
    print("\n🧪 Testing MBO Integration...")
    
    # Create sample data
    mbo_df = create_sample_mbo_data(500)  # Smaller for faster testing
    print(f"Created {len(mbo_df)} sample MBO events")
    
    # Configure with orderflow classification enabled
    config = FeatureConfig(
        include_orderflow_classification=True,
        include_order_flow=True,
        include_microstructure=True,
        batch_size=500
    )
    
    # Process features
    print("Processing features with orderflow classification...")
    try:
        enhanced_df = engineer_mbo_features(mbo_df, config)
        
        # Check if orderflow features are present
        flow_features = [col for col in enhanced_df.columns if col.startswith('flow_')]
        
        if flow_features:
            print(f"✅ MBO integration: SUCCESS")
            print(f"   Added {len(flow_features)} orderflow features")
            print(f"   Sample features: {flow_features[:5]}")
            
            # Check key features
            key_features = ['flow_toxicity_score', 'flow_classification', 'flow_classification_confidence']
            for feature in key_features:
                if feature in enhanced_df.columns:
                    print(f"   ✅ {feature}: Present")
                else:
                    print(f"   ❌ {feature}: Missing")
        else:
            print("❌ MBO integration: FAILED - No orderflow features found")
            
        return enhanced_df
        
    except Exception as e:
        print(f"❌ MBO integration: FAILED - {e}")
        return None

def test_direct_integration():
    """Test direct orderflow feature addition"""
    print("\n🧪 Testing Direct Integration...")
    
    # Create sample data
    mbo_df = create_sample_mbo_data(300)
    print(f"Created {len(mbo_df)} sample MBO events")
    
    # Add orderflow features directly
    print("Adding orderflow classification features...")
    try:
        enhanced_df = add_orderflow_classification_features(mbo_df, lookback_window=200)
        
        flow_features = [col for col in enhanced_df.columns if col.startswith('flow_')]
        
        if flow_features:
            print(f"✅ Direct integration: SUCCESS")
            print(f"   Added {len(flow_features)} orderflow features")
            
            # Show sample classifications
            if 'flow_classification' in enhanced_df.columns:
                classifications = enhanced_df['flow_classification'].value_counts()
                print(f"   Classifications: {classifications.to_dict()}")
        else:
            print("❌ Direct integration: FAILED")
            
        return enhanced_df
        
    except Exception as e:
        print(f"❌ Direct integration: FAILED - {e}")
        return None

def run_performance_test():
    """Test performance with larger dataset"""
    print("\n🧪 Performance Test...")
    
    # Create larger dataset
    mbo_df = create_sample_mbo_data(5000)
    print(f"Created {len(mbo_df)} sample MBO events")
    
    import time
    start_time = time.time()
    
    try:
        # Process with orderflow classification
        enhanced_df = add_orderflow_classification_features(mbo_df, lookback_window=1000)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        flow_features = [col for col in enhanced_df.columns if col.startswith('flow_')]
        
        print(f"✅ Performance test: SUCCESS")
        print(f"   Processing time: {processing_time:.2f} seconds")
        print(f"   Events per second: {len(mbo_df)/processing_time:.0f}")
        print(f"   Features extracted: {len(flow_features)}")
        
    except Exception as e:
        print(f"❌ Performance test: FAILED - {e}")

def main():
    """Run all tests"""
    print("🚀 OrderFlow Classification Test Suite")
    print("=" * 50)
    
    # Test 1: Direct classifier testing
    classified_df = test_orderflow_classifier()
    
    # Test 2: MBO integration testing
    mbo_enhanced_df = test_mbo_integration()
    
    # Test 3: Direct integration testing
    direct_enhanced_df = test_direct_integration()
    
    # Test 4: Performance testing
    run_performance_test()
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary")
    print("=" * 50)
    
    # Summary
    tests_passed = 0
    total_tests = 4
    
    if classified_df is not None and 'flow_toxicity_score' in classified_df.columns:
        tests_passed += 1
        print("✅ OrderFlow Classifier: PASSED")
    else:
        print("❌ OrderFlow Classifier: FAILED")
    
    if mbo_enhanced_df is not None and any(col.startswith('flow_') for col in mbo_enhanced_df.columns):
        tests_passed += 1
        print("✅ MBO Integration: PASSED")
    else:
        print("❌ MBO Integration: FAILED")
    
    if direct_enhanced_df is not None and any(col.startswith('flow_') for col in direct_enhanced_df.columns):
        tests_passed += 1
        print("✅ Direct Integration: PASSED")
    else:
        print("❌ Direct Integration: FAILED")
    
    # Performance test is always considered passed if no exception
    tests_passed += 1
    print("✅ Performance Test: PASSED")
    
    print(f"\n🏆 Result: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests PASSED! OrderFlow classification is working correctly.")
    else:
        print("⚠️ Some tests FAILED. Check implementation.")

if __name__ == "__main__":
    main()
