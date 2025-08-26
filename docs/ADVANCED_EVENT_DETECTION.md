# Advanced Event-Driven Features for QuantTime

## Overview

This document describes the comprehensive event-driven feature detection system implemented in QuantTime's feature engineering pipeline. These features are available when using the `FeatureSet.COMPREHENSIVE` feature set and provide sophisticated detection of institutional flow patterns, market manipulation, and market microstructure anomalies.

## Feature Categories

### 1. Large Order Detection & Fragmentation

**Purpose**: Detect large institutional orders and identify fragmentation patterns used to minimize market impact.

**Detection Methods**:
- **Threshold-based**: Orders ≥ 1000 contracts flagged as large
- **Fragmentation Analysis**: Track order fragments across time
- **Completion Time**: Measure time from first to last fragment

**Features Generated**:
```python
{
    'large_order_fragmentation': float,  # 0-1 scale of fragmentation activity
    'large_order_events': int,          # Count of large orders in time window
    'fragment_count': int,              # Number of fragments per order
    'time_to_complete': int             # Time to complete fragmented order
}
```

**Use Cases**:
- Identify institutional participation
- Predict large order completion
- Measure market impact of large orders

### 2. Iceberg Order Detection

**Purpose**: Detect hidden liquidity (iceberg orders) based on replenishment patterns.

**Detection Methods**:
- **Replenishment Tracking**: Monitor consistent order replenishment at price levels
- **Pattern Consistency**: Analyze timing consistency of replenishments
- **Size Estimation**: Estimate hidden size (typically 5-10x visible size)

**Features Generated**:
```python
{
    'iceberg_detection': float,         # 0-1 confidence score
    'iceberg_events': int,              # Count of detected icebergs
    'visible_size': int,                # Visible portion of iceberg
    'estimated_hidden_size': int,       # Estimated hidden portion
    'confidence_score': float           # Detection confidence (0-1)
}
```

**Use Cases**:
- Identify hidden liquidity levels
- Predict price support/resistance
- Measure market depth accurately

### 3. Spoofing & Market Manipulation Detection

**Purpose**: Detect market manipulation techniques including spoofing, layering, and quote stuffing.

**Detection Methods**:
- **Order Lifecycle Tracking**: Monitor add → cancel patterns
- **Time-based Analysis**: Identify rapid cancellations (< 5 seconds)
- **Size Thresholds**: Focus on orders ≥ 500 contracts
- **Pattern Classification**: Distinguish between spoofing types

**Features Generated**:
```python
{
    'spoofing_events': int,             # Count of spoofing events
    'spoofing_score': float,            # 0-1 manipulation probability
    'spoofing_type': str,               # 'layering', 'spoofing', 'quote_stuffing'
    'time_to_cancel': int               # Time from add to cancel
}
```

**Use Cases**:
- Identify market manipulation
- Avoid false signals from spoofing
- Regulatory compliance monitoring

### 4. Institutional Flow Detection

**Purpose**: Detect and classify institutional order flow patterns.

**Detection Methods**:
- **Flow Strength Calculation**: Measure buy/sell pressure imbalance
- **Volume Analysis**: Track volume-weighted flow direction
- **Consistency Measurement**: Assess flow pattern consistency
- **Confidence Scoring**: Rate detection reliability

**Features Generated**:
```python
{
    'institutional_flow_strength': float,  # 0-1 flow strength
    'institutional_flow_events': int,      # Count of flow events
    'flow_type': str,                      # 'buy_pressure', 'sell_pressure', 'neutral'
    'flow_autocorrelation': float,         # Flow persistence measure
    'flow_predictability': float,          # Flow pattern consistency
    'flow_exhaustion_signals': float       # Flow exhaustion detection
}
```

**Use Cases**:
- Predict price direction
- Identify institutional sentiment
- Time entry/exit points

### 5. Market Regime Detection

**Purpose**: Identify and track market regime changes (trending, mean-reverting, volatile, quiet).

**Detection Methods**:
- **Volatility Analysis**: Measure price volatility levels
- **Trend Strength**: Calculate directional trend consistency
- **Liquidity Assessment**: Monitor market liquidity levels
- **Regime Transition**: Track regime change probabilities

**Features Generated**:
```python
{
    'volatility_regime': float,              # 0-1 volatility level
    'market_regime_events': int,             # Count of regime events
    'regime_type': str,                      # 'trending', 'mean_reverting', 'volatile', 'quiet'
    'regime_transition_probability': float,  # Probability of regime change
    'regime_persistence': float              # Current regime stability
}
```

**Use Cases**:
- Adapt strategy to market conditions
- Predict regime changes
- Optimize position sizing

### 6. Liquidity Stress Detection

**Purpose**: Detect liquidity stress events and market dysfunction.

**Detection Methods**:
- **Spread Widening**: Monitor bid-ask spread expansion
- **Depth Reduction**: Track order book depth depletion
- **Stress Scoring**: Calculate composite stress indicators
- **Recovery Tracking**: Monitor liquidity recovery patterns

**Features Generated**:
```python
{
    'liquidity_regime': float,               # 0-1 stress level
    'liquidity_stress_events': int,          # Count of stress events
    'liquidity_stress_indicators': float,    # Current stress level
    'liquidity_recovery_signals': float,     # Recovery detection
    'spread_widening': float,                # Spread expansion measure
    'depth_reduction': float                 # Depth depletion measure
}
```

**Use Cases**:
- Avoid trading during stress periods
- Predict market dysfunction
- Risk management during illiquidity

### 7. Order Flow Anomaly Detection

**Purpose**: Detect unusual order flow patterns and market microstructure anomalies.

**Detection Methods**:
- **Volume Spike Detection**: Identify unusual volume activity
- **Price Jump Detection**: Monitor sudden price movements
- **Spread Anomaly Detection**: Track unusual spread behavior
- **Impact Scoring**: Measure anomaly market impact

**Features Generated**:
```python
{
    'order_flow_anomalies': int,         # Count of anomalies
    'anomaly_type': str,                 # 'volume_spike', 'price_jump', 'spread_widening'
    'severity': float,                   # 0-1 anomaly severity
    'impact_score': float                # Market impact measure
}
```

**Use Cases**:
- Identify market microstructure changes
- Predict short-term price movements
- Risk management during anomalies

## Multi-Horizon Integration

All event-driven features are integrated into the multi-horizon system, providing event counts across different time windows:

- **10ms**: Ultra-short-term event detection
- **50ms**: Short-term event patterns
- **100ms**: Immediate event analysis
- **500ms**: Quick event trends
- **1s**: Second-level event patterns
- **3s**: Multi-second event analysis
- **10s**: Short-term event trends
- **30s**: Medium-term event patterns
- **1m**: Minute-level event analysis
- **2m**: Multi-minute event trends
- **5m**: Short-term event cycles
- **10m**: Medium-term event patterns
- **20m**: Long-term event trends
- **30m**: Extended event analysis
- **1h**: Hour-level event patterns

## Usage Examples

### Basic Usage

```python
from quanttime.data.features import FeatureEngine, FeatureSet

# Initialize with comprehensive features
engine = FeatureEngine(feature_set=FeatureSet.COMPREHENSIVE)

# Process events
features = engine.process_event(
    ts_event=1704067200000000000,
    action="A",
    side="B",
    order_id=123456,
    price=5000.25,
    size=1500,
    flags=0,
    sequence=1,
    instrument="ES"
)

# Access advanced features
print(f"Large order fragmentation: {features.get('large_order_fragmentation', 0)}")
print(f"Iceberg detection: {features.get('iceberg_detection', 0)}")
print(f"Spoofing events: {features.get('spoofing_events', 0)}")
```

### Batch Processing

```python
from quanttime.data.features import compute_mbo_features, FeatureSet

# Process DataFrame with comprehensive features
df_with_features = compute_mbo_features(
    df=raw_mbo_df,
    feature_set=FeatureSet.COMPREHENSIVE,
    normalization_type=NormalizationType.TICK_RELATIVE,
    intensity_level="extreme"
)

# Access multi-horizon event features
print(f"1s large order events: {df_with_features['1s_large_order_events'].iloc[-1]}")
print(f"1m institutional flow: {df_with_features['1m_institutional_flow_events'].iloc[-1]}")
```

## Performance Considerations

### Computational Complexity
- **Event Detection**: O(1) per event for most detectors
- **Memory Usage**: Bounded by event history limits (1000 events per type)
- **Real-time Processing**: Designed for streaming data processing

### Memory Management
- **Event History**: Limited to 1000 events per event type
- **Buffer Management**: Automatic cleanup of expired events
- **State Persistence**: Maintains state across processing sessions

### Optimization Tips
1. **Use Appropriate Feature Sets**: Only use COMPREHENSIVE when needed
2. **Monitor Event Counts**: High event counts may indicate market stress
3. **Combine with Basic Features**: Use event features with traditional indicators
4. **Time Window Selection**: Choose appropriate horizons for your strategy

## Configuration Parameters

### Large Order Detection
```python
LARGE_ORDER_THRESHOLD = 1000      # Minimum size for large order
VERY_LARGE_ORDER_THRESHOLD = 5000 # Size for very large orders
```

### Iceberg Detection
```python
ICEBERG_REPLENISHMENT_THRESHOLD = 3  # Minimum replenishments
ICEBERG_SIZE_THRESHOLD = 500         # Minimum size to consider
ICEBERG_TIME_WINDOW = 60000000000    # 60 seconds in nanoseconds
```

### Spoofing Detection
```python
SPOOFING_SIZE_THRESHOLD = 500        # Minimum size to consider
SPOOFING_TIME_THRESHOLD = 5000000000 # 5 seconds in nanoseconds
SPOOFING_CANCEL_THRESHOLD = 0.8      # 80% cancellation threshold
```

### Institutional Flow Detection
```python
FLOW_IMBALANCE_THRESHOLD = 0.3       # Significant imbalance threshold
FLOW_WINDOW_SIZE = 100               # Events for flow calculation
```

### Anomaly Detection
```python
VOLUME_SPIKE_THRESHOLD = 3.0         # 3x average volume
PRICE_JUMP_THRESHOLD = 5.0           # 5 tick price jump
SPREAD_WIDENING_THRESHOLD = 2.0      # 2x average spread
```

## Integration with Trading Strategies

### Signal Generation
```python
def generate_signals(features):
    signals = {}
    
    # Institutional flow signals
    if features['institutional_flow_strength'] > 0.7:
        if features['flow_type'] == 'buy_pressure':
            signals['long'] = features['institutional_flow_strength']
        elif features['flow_type'] == 'sell_pressure':
            signals['short'] = features['institutional_flow_strength']
    
    # Spoofing avoidance
    if features['spoofing_events'] > 5:
        signals['avoid_trading'] = True
    
    # Liquidity stress signals
    if features['liquidity_stress_indicators'] > 0.8:
        signals['reduce_position'] = True
    
    return signals
```

### Risk Management
```python
def risk_assessment(features):
    risk_score = 0.0
    
    # High spoofing activity
    if features['spoofing_events'] > 10:
        risk_score += 0.3
    
    # Liquidity stress
    if features['liquidity_stress_indicators'] > 0.7:
        risk_score += 0.4
    
    # Market regime volatility
    if features['volatility_regime'] > 0.8:
        risk_score += 0.3
    
    return min(1.0, risk_score)
```

## Future Enhancements

### Planned Features
1. **Machine Learning Integration**: Use ML models for event classification
2. **Cross-Asset Correlation**: Detect events across multiple instruments
3. **Regulatory Reporting**: Automated compliance monitoring
4. **Real-time Alerts**: Streaming event notifications
5. **Backtesting Integration**: Historical event analysis

### Research Areas
1. **Event Causality**: Understanding event relationships
2. **Predictive Modeling**: Forecasting event occurrence
3. **Market Impact**: Quantifying event market effects
4. **Regime Transitions**: Predicting market regime changes

## Conclusion

The advanced event-driven feature system provides comprehensive detection of institutional flow patterns, market manipulation, and microstructure anomalies. These features enable sophisticated trading strategies that can adapt to changing market conditions and avoid common pitfalls associated with market manipulation and liquidity stress.

By integrating these features with traditional technical indicators and multi-horizon analysis, traders can develop more robust and adaptive trading systems that perform well across different market regimes.
