# MBO L3 Execution-Aware Data Pipeline Specification

## **Overview**

This document extends the unified MBO L3 data pipeline with execution-aware footprint features and comprehensive multi-horizon analysis. The goal is to distinguish real traded liquidity from phantom liquidity and generate alpha signals that persist beyond HFT noise horizons.

## **Key Principles**

1. **Execution-Aware**: Distinguish between posted liquidity (quotes) and executed liquidity (trades)
2. **Multi-Horizon**: Features computed across microseconds to 20+ minute horizons
3. **Alpha Generation**: More features rather than less - let the model decide what's useful
4. **Latency-Conscious**: Focus on signal horizons that survive real-world latency constraints

---

## **1. Execution-Aware Feature Engineering (Footprint Layer)**

### **1.1 Trade Flow Features (from EXECUTE events)**

#### **Aggressor Side Volume**
- `buy_volume`: Volume executed against resting asks (market buy orders)
- `sell_volume`: Volume executed against resting bids (market sell orders)
- `passive_buy_volume`: Volume from limit buy orders that got filled
- `passive_sell_volume`: Volume from limit sell orders that got filled

#### **Delta (Signed Volume)**
- `delta = buy_volume - sell_volume` per time window
- `aggressive_delta = aggressive_buy - aggressive_sell`
- `passive_delta = passive_buy - passive_sell`

#### **Cumulative Delta**
- Rolling sum of delta over session or configurable horizon
- `cumulative_delta_session`: Session-wide cumulative delta
- `cumulative_delta_1m`: Rolling 1-minute cumulative delta
- `cumulative_delta_5m`: Rolling 5-minute cumulative delta
- `cumulative_delta_20m`: Rolling 20-minute cumulative delta

#### **Absorption Metrics**
- High executed volume at a level without price moving → absorption
- `absorption_ratio = executed_volume / posted_volume_at_level`
- `absorption_strength`: Sustained absorption over multiple time windows
- `absorption_exhaustion`: When resting liquidity vanishes after repeated trades

#### **Exhaustion Signals**
- `liquidity_exhaustion_rate`: Rate at which resting liquidity disappears
- `depth_depletion_speed`: How quickly order book depth thins near touch
- `refill_rate`: Speed at which liquidity gets replenished after exhaustion

### **1.2 Fair Price Features (Footprint-Informed Mid)**

#### **Volume-Weighted Pricing**
- `vwap_mid`: Volume-weighted midprice using executed trades
- `trade_weighted_average_price`: Simple average of trade prices in time horizon
- `execution_weighted_mid`: Midprice weighted by execution intensity

#### **Imbalance Adjusted Pricing**
- `imbalance_adjusted_mid = midprice + α * (delta / depth_near_mid)`
- `footprint_fair_value`: Fair value derived from execution footprint
- `absorption_adjusted_price`: Price adjusted for absorption effects

### **1.3 Execution-to-Book Ratios**

#### **Fill Ratios**
- `fill_ratio = executed_volume / (executed_volume + resting_volume)`
- `posted_to_filled_ratio`: Ratio of posted vs actually filled liquidity
- `phantom_liquidity_ratio`: Measure of far-off quotes that never fill

#### **Liquidity Conversion Efficiency**
- How much posted liquidity actually turns into trades
- `conversion_efficiency_by_level`: Per price level conversion rates
- `conversion_efficiency_by_time`: Time-based conversion patterns

#### **Phantom Liquidity Detection**
- Orders far from mid with negligible fill probability
- `phantom_flag`: Binary flag for phantom liquidity
- `phantom_distance`: Distance from mid where orders become phantom
- `phantom_volume_ratio`: Ratio of phantom to real liquidity

### **1.4 Footprint Grid (Price × Time Matrix)**

#### **2D Footprint Matrix**
- Indexed by price level × time bucket
- Each cell contains: `buy_volume`, `sell_volume`, `delta`, `absorption`
- Encodes absorption and imbalance patterns visually/numerically

#### **Footprint Patterns**
- `footprint_cluster_strength`: Clustering of execution at specific levels
- `footprint_migration`: How execution patterns move across price levels
- `footprint_persistence`: How long execution patterns persist

---

## **2. Multi-Horizon Feature Engineering**

### **2.1 Horizon Definitions**

#### **Micro-Horizons (HFT Territory - Optional)**
- `10ms`: Ultra-fast microstructure (mostly for completeness)
- `50ms`: Fast microstructure patterns
- `100ms`: Short-term order flow bursts

#### **Short-Horizons (Tactical Trading)**
- `500ms`: Sub-second patterns
- `1s`: Second-level patterns
- `3s`: Multi-second trends
- `10s`: Short tactical moves

#### **Medium-Horizons (Strategic Trading)**
- `30s`: Half-minute trends
- `1m`: Minute-level patterns
- `2m`: Multi-minute flows
- `5m`: Medium-term institutional flows

#### **Long-Horizons (Positional Alpha)**
- `10m`: Long-term institutional activity
- `20m`: Extended positional flows
- `30m`: Half-hour institutional patterns
- `1h`: Hourly trend analysis

### **2.2 Multi-Horizon Feature Implementation**

#### **For Each Horizon, Compute:**

##### **Volume Features**
- `buy_volume_Xm`: Executed buy volume over X minutes
- `sell_volume_Xm`: Executed sell volume over X minutes
- `total_volume_Xm`: Total executed volume over X minutes
- `average_trade_size_Xm`: Average trade size over X minutes

##### **Delta Features**
- `delta_Xm`: Net delta (buy - sell) over X minutes
- `cumulative_delta_Xm`: Rolling cumulative delta
- `delta_momentum_Xm`: Rate of change in delta
- `delta_acceleration_Xm`: Second derivative of delta

##### **Absorption Features**
- `absorption_ratio_Xm`: Average absorption ratio over X minutes
- `absorption_events_Xm`: Count of significant absorption events
- `absorption_strength_Xm`: Weighted absorption strength
- `exhaustion_events_Xm`: Count of liquidity exhaustion events

##### **Imbalance Features**
- `order_flow_imbalance_Xm`: Traditional OFI over X minutes
- `execution_imbalance_Xm`: Execution-based imbalance
- `depth_weighted_imbalance_Xm`: Imbalance weighted by depth
- `distance_weighted_imbalance_Xm`: Imbalance weighted by distance from mid

##### **Price Movement Features**
- `price_change_Xm`: Price change over X minutes
- `volatility_Xm`: Volatility estimate over X minutes
- `trend_strength_Xm`: Strength of price trend
- `reversal_probability_Xm`: Probability of trend reversal

##### **Liquidity Features**
- `average_spread_Xm`: Average spread over X minutes
- `depth_at_touch_Xm`: Average depth at best bid/ask
- `depth_profile_Xm`: Depth distribution profile
- `liquidity_replenishment_rate_Xm`: Rate of liquidity refill

### **2.3 Cross-Horizon Features**

#### **Horizon Correlation Analysis**
- `delta_correlation_1m_5m`: Correlation between 1m and 5m deltas
- `momentum_persistence`: How momentum persists across horizons
- `reversal_signals`: Cross-horizon reversal indicators

#### **Horizon Momentum Features**
- `short_to_long_momentum`: Ratio of short to long horizon momentum
- `acceleration_across_horizons`: Acceleration patterns across time scales
- `divergence_signals`: When different horizons diverge

---

## **3. Advanced Execution Features**

### **3.1 Order Flow Patterns**

#### **Execution Clustering**
- `execution_cluster_strength`: How clustered executions are at specific levels
- `execution_cluster_migration`: How clusters move across price levels
- `execution_cluster_persistence`: How long clusters persist

#### **Aggressor Patterns**
- `aggressor_size_distribution`: Distribution of aggressor order sizes
- `aggressor_frequency`: Frequency of aggressive orders
- `aggressor_persistence`: How long aggressive patterns persist

#### **Market Structure Indicators**
- `market_impact_curve`: How much volume moves price
- `liquidity_resilience`: How quickly liquidity recovers after exhaustion
- `quote_stability`: Stability of posted quotes

### **3.2 Institutional Flow Detection**

#### **Meta-Order Detection**
- `large_order_fragmentation`: Detection of fragmented large orders
- `institutional_flow_strength`: Strength of institutional flows
- `iceberg_detection`: Detection of iceberg orders

#### **Flow Persistence**
- `flow_autocorrelation`: Autocorrelation of order flows
- `flow_predictability`: Predictability of future flows
- `flow_exhaustion_signals`: When institutional flows exhaust

### **3.3 Market Regime Features**

#### **Volatility Regimes**
- `volatility_regime`: Current volatility regime classification
- `regime_transition_probability`: Probability of regime change
- `regime_persistence`: How long regimes typically last

#### **Liquidity Regimes**
- `liquidity_regime`: Current liquidity regime classification
- `liquidity_stress_indicators`: Indicators of liquidity stress
- `liquidity_recovery_signals`: Signals of liquidity recovery

---

## **4. Implementation Architecture**

### **4.1 Ring Buffer System**

#### **Multi-Horizon Buffers**
```python
class MultiHorizonBuffer:
    def __init__(self):
        self.horizons = {
            '10ms': RingBuffer(maxlen=6000),    # 1 minute of 10ms buckets
            '100ms': RingBuffer(maxlen=18000),  # 30 minutes of 100ms buckets
            '1s': RingBuffer(maxlen=7200),      # 2 hours of 1s buckets
            '10s': RingBuffer(maxlen=2160),     # 6 hours of 10s buckets
            '1m': RingBuffer(maxlen=1440),      # 24 hours of 1m buckets
            '5m': RingBuffer(maxlen=576),       # 48 hours of 5m buckets
            '20m': RingBuffer(maxlen=216),      # 72 hours of 20m buckets
            '1h': RingBuffer(maxlen=168),       # 1 week of 1h buckets
        }
```

### **4.2 Feature State Management**

#### **Execution State**
```python
@dataclass
class ExecutionState:
    # Volume tracking
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    total_volume: float = 0.0
    
    # Delta tracking
    delta: float = 0.0
    cumulative_delta: float = 0.0
    
    # Absorption tracking
    absorption_events: List[AbsorptionEvent] = field(default_factory=list)
    exhaustion_events: List[ExhaustionEvent] = field(default_factory=list)
    
    # Multi-horizon states
    horizon_states: Dict[str, HorizonState] = field(default_factory=dict)
```

### **4.3 O(1) Feature Updates**

#### **Incremental Computation**
- All features updated incrementally with O(1) complexity
- Ring buffers maintain rolling windows efficiently
- EMA-based normalization for constant-time updates

#### **Memory Efficiency**
- Compact representation of execution events
- Efficient storage of multi-horizon features
- Garbage collection of expired data

---

## **5. Normalization Strategy**

### **5.1 Execution Volume Normalization**

#### **Multi-Scale Normalization**
- `volume_norm = log(1 + volume) / log(1 + EMA_volume_horizon)`
- Different EMAs for different horizons
- Session reset for daily patterns

#### **Delta Normalization**
- `delta_norm = delta / rolling_average_trade_size`
- Bounded normalization: `tanh(delta_norm / volatility_estimate)`

### **5.2 Cross-Horizon Normalization**

#### **Horizon-Specific Scaling**
- Each horizon has its own normalization parameters
- Account for natural scaling differences across time frames
- Preserve relative magnitude across horizons

---

## **6. Model Integration**

### **6.1 Feature Selection by Horizon**

#### **Model-Specific Horizons**
- **Scalping Models**: Focus on 100ms - 10s features
- **Tactical Models**: Focus on 1s - 5m features  
- **Strategic Models**: Focus on 1m - 1h features
- **Hybrid Models**: Use all horizons, let model decide

### **6.2 Latency-Aware Training**

#### **Realistic Backtesting**
- Inject 100ms - 500ms latency in backtests
- Validate PnL with delayed execution
- Train models to survive real-world constraints

#### **Signal Persistence Validation**
- Ensure signals persist beyond model decision time
- Test signal decay over different horizons
- Optimize for signal durability, not just accuracy

---

## **7. Alpha Generation Philosophy**

### **7.1 Feature Abundance**

#### **More is Better**
- Generate comprehensive feature set across all horizons
- Let models discover what's useful through feature selection
- Avoid premature optimization - compute everything

#### **Feature Categories**
1. **Price-Based**: All price movement patterns across horizons
2. **Volume-Based**: All volume patterns and distributions
3. **Delta-Based**: All delta and cumulative delta patterns
4. **Absorption-Based**: All absorption and exhaustion patterns
5. **Cross-Horizon**: All relationships between different time scales
6. **Regime-Based**: All market regime and structural patterns

### **7.2 Signal Discovery**

#### **Automated Feature Engineering**
- Polynomial features across horizons
- Interaction terms between different feature types
- Rolling statistics (mean, std, skew, kurtosis) across all horizons

#### **Pattern Recognition**
- Clustering of similar market conditions
- Anomaly detection for unusual patterns
- Sequence pattern matching across horizons

---

## **8. Implementation Priority**

### **8.1 Phase 1: Core Execution Features**
1. Basic trade flow tracking (buy/sell volume, delta)
2. Absorption and exhaustion detection
3. Multi-horizon delta computation

### **8.2 Phase 2: Advanced Footprint Features**
1. Footprint grid implementation
2. Fair value computation
3. Phantom liquidity detection

### **8.3 Phase 3: Cross-Horizon Analysis**
1. Horizon correlation features
2. Cross-horizon momentum
3. Regime detection

### **8.4 Phase 4: Alpha Generation**
1. Automated feature engineering
2. Pattern recognition
3. Signal validation and persistence testing

---

## **9. Success Metrics**

### **9.1 Feature Quality**
- Signal-to-noise ratio across horizons
- Feature importance in trained models
- Correlation structure stability

### **9.2 Alpha Generation**
- Out-of-sample Sharpe ratio
- Maximum drawdown characteristics
- Signal persistence under latency

### **9.3 Practical Performance**
- Real-world trading performance
- Slippage and execution costs
- Risk-adjusted returns

---

This specification provides a comprehensive framework for execution-aware, multi-horizon MBO L3 feature engineering that can generate sustainable alpha beyond HFT noise while accounting for real-world latency constraints.
