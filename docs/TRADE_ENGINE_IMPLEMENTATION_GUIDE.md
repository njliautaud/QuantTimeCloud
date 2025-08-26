# Trade Engine Implementation Guide

## Overview

The Trade Engine is a comprehensive system that combines predictions from multiple ML models with order flow pattern recognition to execute trades. It provides risk management, position sizing, and performance tracking for both backtesting and live trading.

## Architecture

### Core Components

1. **TradeEngine**: Main orchestrator that combines model predictions and executes trades
2. **OrderFlowPatternDetector**: Detects order flow patterns (icebergs, order blocks, absorption)
3. **TradeEngineConfig**: Configuration for risk management and trading parameters
4. **TradeSignal**: Structured trade signals from model predictions
5. **Position**: Current trading position tracking

### Key Features

- **Multi-Model Ensemble**: Combines predictions from multiple models with configurable weights
- **Order Flow Pattern Recognition**: Detects iceberg orders, order blocks, and absorption patterns
- **Risk Management**: Stop-loss, take-profit, position sizing, and drawdown limits
- **Performance Tracking**: Comprehensive metrics for backtesting and live trading
- **Direction Accuracy**: Tracks prediction accuracy for price direction
- **Pattern Detection**: Evaluates order flow pattern prediction accuracy

## Implementation Details

### Trade Engine Configuration

```python
from quanttime.models.trade_engine import TradeEngineConfig, create_trade_engine

# Model weights (must sum to 100)
model_weights = {
    'lightgbm_model_1': 40.0,
    'lstm_model_1': 35.0,
    'transformer_model_1': 25.0
}

# Create trade engine
config = TradeEngineConfig(
    model_weights=model_weights,
    max_position_size=0.1,  # 10% of portfolio
    max_drawdown=0.05,      # 5% max drawdown
    stop_loss_pct=0.02,     # 2% stop loss
    take_profit_pct=0.04,   # 4% take profit
    min_confidence=0.6,     # Minimum confidence to trade
    min_direction_strength=0.3,  # Minimum direction strength
    base_position_size=0.05,     # 5% base position
    confidence_multiplier=2.0    # Multiply position by confidence
)

trade_engine = TradeEngine(config)
```

### Order Flow Pattern Detection

The system detects three main order flow patterns:

#### 1. Iceberg Orders
- **Detection**: Large volume imbalances with low price impact
- **Features**: Volume imbalance, price impact analysis
- **Confidence**: Based on imbalance strength and price stability

#### 2. Order Blocks
- **Detection**: Significant support/resistance levels with high volume
- **Features**: Price level analysis, volume concentration
- **Confidence**: Based on volume at price levels

#### 3. Absorption
- **Detection**: Price rejection at levels with high volume
- **Features**: Price reversal patterns, volume analysis
- **Confidence**: Based on reversal strength and volume

### Model Integration

Models must provide predictions in the following format:

```python
predictions = {
    'direction': 0.75,        # -1 to 1 (negative = down, positive = up)
    'price_change': 0.002,    # Predicted price change
    'confidence': 0.8,        # 0 to 1 confidence score
    'horizon': 1,             # Prediction horizon in minutes
    'patterns': {             # Order flow pattern predictions
        'iceberg_confidence': 0.6,
        'order_block_confidence': 0.4,
        'absorption_confidence': 0.3
    }
}
```

## Usage Examples

### Basic Trade Engine Setup

```python
from quanttime.models.trade_engine import create_trade_engine
from quanttime.models.model_registry import ModelRegistry

# Load trained models
registry = ModelRegistry()
lightgbm_model = registry.load_model('lightgbm_model_1')
lstm_model = registry.load_model('lstm_model_1')

# Create trade engine
model_weights = {
    'lightgbm_model_1': 60.0,
    'lstm_model_1': 40.0
}

trade_engine = create_trade_engine(
    model_weights=model_weights,
    max_position_size=0.1,
    stop_loss_pct=0.02,
    take_profit_pct=0.04
)
```

### Making Predictions and Executing Trades

```python
# Get model predictions
model_predictions = {}
for model_id, model in models.items():
    predictions = model.predict(mbo_data)
    model_predictions[model_id] = predictions

# Combine predictions and create trade signal
signal = trade_engine.combine_model_predictions(model_predictions, mbo_data)

# Execute trade if conditions are met
current_price = mbo_data['price'].iloc[-1]
trade_result = trade_engine.execute_trade(signal, current_price)

if trade_result:
    print(f"Trade executed: {trade_result['side']} {trade_result['size']} at {trade_result['entry_price']}")
```

### Backtesting Integration

```python
def run_backtest(trade_engine, models, data, initial_capital, commission_rate):
    """Run backtest with trade engine."""
    
    portfolio_value = initial_capital
    trades = []
    
    for i in range(len(data)):
        current_tick = data.iloc[i:i+1]
        
        # Get model predictions
        model_predictions = {}
        for model_id, model in models.items():
            predictions = model.predict(current_tick)
            model_predictions[model_id] = predictions
        
        # Combine predictions
        signal = trade_engine.combine_model_predictions(model_predictions, current_tick)
        
        # Execute trade
        current_price = current_tick['price'].iloc[0]
        trade_result = trade_engine.execute_trade(signal, current_price)
        
        if trade_result:
            trades.append(trade_result)
        
        # Update position
        exit_trade = trade_engine.update_position(current_price)
        if exit_trade:
            trades.append(exit_trade)
            portfolio_value += exit_trade['realized_pnl']
    
    # Get performance summary
    performance = trade_engine.get_performance_summary()
    
    return {
        'performance': performance,
        'trades': trades,
        'final_capital': portfolio_value
    }
```

## Dashboard Integration

### Model Selection with Weights

The dashboard provides a visual interface for:
- Selecting multiple models
- Setting weights (must sum to 100%)
- Configuring risk parameters
- Running backtests with the trade engine

### Performance Metrics Display

The system displays comprehensive metrics:
- **Direction Accuracy**: How often the model correctly predicts price direction
- **Pattern Detection Accuracy**: Accuracy of order flow pattern predictions
- **Financial Metrics**: Sharpe ratio, max drawdown, win rate, profit factor
- **Risk Metrics**: VaR, CVaR, volatility analysis

## Model Scoring System

### Direction Accuracy
- **Metric**: Percentage of correct direction predictions
- **Calculation**: (Correct predictions / Total predictions) * 100
- **Target**: >60% for profitable trading

### Price Target Accuracy
- **Metric**: How close predictions are to actual price targets
- **Calculation**: 1 - (|Predicted - Actual| / Actual)
- **Target**: >70% accuracy for 1-5 minute predictions

### Pattern Detection Accuracy
- **Metric**: Accuracy of order flow pattern predictions
- **Patterns**: Iceberg orders, order blocks, absorption
- **Target**: >50% pattern detection accuracy

## Risk Management

### Position Sizing
- **Base Position**: Configurable percentage of portfolio
- **Confidence Multiplier**: Adjust position size based on prediction confidence
- **Maximum Position**: Hard limit on position size

### Stop Loss and Take Profit
- **Stop Loss**: Automatic exit at configured loss percentage
- **Take Profit**: Automatic exit at configured profit percentage
- **Trailing Stops**: Optional trailing stop functionality

### Drawdown Protection
- **Maximum Drawdown**: Stop trading if drawdown exceeds limit
- **Daily Loss Limits**: Optional daily loss limits
- **Position Limits**: Maximum number of concurrent positions

## Performance Optimization

### Memory Management
- **Batch Processing**: Process data in batches to manage memory
- **Lazy Loading**: Load models only when needed
- **Garbage Collection**: Regular cleanup of unused objects

### Computational Efficiency
- **Vectorized Operations**: Use NumPy/Pandas for fast computations
- **Caching**: Cache frequently used calculations
- **Parallel Processing**: Optional parallel model predictions

## Best Practices

### Model Selection
1. **Diversify Models**: Use different model types (LightGBM, LSTM, Transformer)
2. **Weight Optimization**: Regularly optimize model weights based on performance
3. **Ensemble Benefits**: Combine models to reduce overfitting and improve stability

### Risk Management
1. **Start Conservative**: Begin with small position sizes and tight stops
2. **Monitor Drawdown**: Keep drawdown below 5% for sustainable trading
3. **Regular Rebalancing**: Adjust model weights based on recent performance

### Pattern Recognition
1. **Validate Patterns**: Ensure pattern detection is accurate before trading
2. **Combine Signals**: Use multiple pattern confirmations for stronger signals
3. **Adapt to Market**: Adjust pattern thresholds based on market conditions

## Troubleshooting

### Common Issues

1. **Model Loading Failures**
   - Check model file paths
   - Verify model compatibility
   - Ensure all dependencies are installed

2. **Prediction Errors**
   - Validate input data format
   - Check model training status
   - Verify feature engineering pipeline

3. **Performance Issues**
   - Monitor memory usage
   - Optimize batch sizes
   - Use GPU acceleration when available

### Debugging Tips

1. **Enable Logging**: Set appropriate log levels for debugging
2. **Validate Predictions**: Check prediction ranges and formats
3. **Monitor Metrics**: Track accuracy metrics over time
4. **Test Incrementally**: Test components individually before integration

## Future Enhancements

### Planned Features
1. **Advanced Pattern Recognition**: More sophisticated order flow patterns
2. **Machine Learning Integration**: ML-based pattern detection
3. **Real-time Optimization**: Dynamic parameter adjustment
4. **Multi-Asset Support**: Extend to other instruments
5. **Advanced Risk Models**: VaR, stress testing, scenario analysis

### Performance Improvements
1. **GPU Acceleration**: Full GPU support for all operations
2. **Distributed Computing**: Multi-machine backtesting
3. **Streaming Processing**: Real-time data processing
4. **Optimized Algorithms**: Faster pattern detection algorithms

## Conclusion

The Trade Engine provides a robust foundation for algorithmic trading with:
- Comprehensive model ensemble capabilities
- Advanced order flow pattern recognition
- Sophisticated risk management
- Detailed performance tracking
- Easy integration with existing models

This implementation addresses the user's requirements for:
- Model scoring on direction and price accuracy
- Order flow pattern incorporation
- Separate trade engine architecture
- Multi-model ensemble with weights
- Comprehensive backtesting capabilities

The system is designed to be extensible, allowing for future enhancements while maintaining the core functionality needed for profitable algorithmic trading.
