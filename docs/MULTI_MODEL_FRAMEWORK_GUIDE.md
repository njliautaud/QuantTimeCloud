# Multi-Model Framework Guide for QuantTime ML Trading Suite

## Overview

This guide covers the comprehensive multi-model framework implemented in QuantTime, including LightGBM, LSTM, and Transformer models optimized for financial time series prediction with 1-5 minute horizons.

## Architecture Decision: Models vs Trade Engine

### **Recommendation: Separate Trade Engine Architecture**

**We recommend having the models predict price movements and send predictions to a separate decision-making trade engine.** Here's why:

#### **Why Separate Trade Engine is Better:**

1. **Risk Management**: Trade engine can implement position sizing, stop-losses, risk limits
2. **Market Conditions**: Trade engine can filter trades based on volatility, spread, liquidity
3. **Execution Logic**: Handle order types, timing, slippage, market impact
4. **Portfolio Management**: Balance multiple signals, correlation analysis
5. **Regulatory Compliance**: Audit trails, position limits, reporting
6. **Model Agnostic**: Can combine predictions from multiple models (LightGBM, LSTM, Transformer)

#### **Architecture:**
```
Models → Price Predictions → Trade Engine → Order Execution
```

#### **Benefits:**
- **Separation of Concerns**: Models focus on prediction, engine handles execution
- **Flexibility**: Easy to swap models or add new ones
- **Risk Control**: Centralized risk management
- **Scalability**: Can handle multiple models and strategies
- **Maintainability**: Clear boundaries between components

## Model Framework

### **Supported Model Types**

1. **LightGBM (Gradient Boosting)**
   - **Strengths**: Fast training, handles mixed data types, good for tabular data
   - **Weaknesses**: Limited sequence modeling, may miss temporal dependencies
   - **Best For**: Feature-rich prediction, quick prototyping

2. **LSTM (Long Short-Term Memory)**
   - **Strengths**: Excellent sequence modeling, captures temporal dependencies
   - **Weaknesses**: Slower training, requires more data, black-box nature
   - **Best For**: Complex time series patterns, long-term dependencies

3. **Transformer (Attention-based)**
   - **Strengths**: Parallel processing, attention mechanisms, state-of-the-art performance
   - **Weaknesses**: High computational cost, requires large datasets
   - **Best For**: Complex patterns, attention to specific time periods

### **Model Optimization Strategy**

Each model is optimized for the 1-5 minute scalping timeline with minimum 10-second trade duration:

#### **LightGBM Optimization:**
- GPU acceleration with `device: 'gpu'`
- Memory optimization with `max_bin` and `max_memory_usage`
- Feature engineering for order flow patterns
- Multi-horizon prediction (1, 2, 3, 5 minutes)

#### **LSTM Optimization:**
- Bidirectional LSTM for better context
- Attention mechanisms for sequence modeling
- Residual connections for gradient flow
- Mixed precision training for memory efficiency

#### **Transformer Optimization:**
- Multi-head self-attention for pattern recognition
- Positional encoding for temporal information
- Global attention pooling for sequence summarization
- Cosine annealing learning rate scheduling

## Implementation Details

### **Base Model Interface**

All models inherit from `ModelBase` and implement:

```python
class ModelBase(ABC):
    @abstractmethod
    def train(self, mbo_df: pd.DataFrame, ...) -> Dict[str, Any]:
        """Train the model on MBO data."""
        pass
    
    @abstractmethod
    def predict(self, mbo_df: pd.DataFrame, horizon: int = 1) -> np.ndarray:
        """Make predictions for given horizon."""
        pass
    
    @abstractmethod
    def evaluate(self, mbo_df: pd.DataFrame, horizon: int = 1) -> TrainingMetrics:
        """Evaluate model performance."""
        pass
```

### **Model Configuration**

```python
@dataclass
class ModelConfig:
    model_type: str  # 'lightgbm', 'lstm', 'transformer'
    prediction_horizons: List[int]  # [1, 2, 3, 5] minutes
    orderbook_depth: int = 20
    sequence_length: int = 200
    feature_window: int = 100
    use_gpu: bool = True
    use_mixed_precision: bool = True
    max_gpu_memory_gb: float = 7.0
    max_ram_gb: float = 14.0
    batch_size: int = 15000
    min_trade_duration_seconds: int = 10
```

### **Training Metrics**

Comprehensive financial metrics including:

- **Basic Metrics**: RMSE, MAE, R²
- **Financial Metrics**: Sharpe ratio, max drawdown, win rate, profit factor
- **Risk Metrics**: VaR (95%), CVaR (95%), Calmar ratio, Sortino ratio
- **Trading Metrics**: Total trades, profitable trades, average trade duration

## Usage Examples

### **Creating and Training Models**

```python
from quanttime.models import create_model

# Create LightGBM model
lightgbm_model = create_model('lightgbm', 
                             prediction_horizons=[1, 2, 3, 5],
                             orderbook_depth=20,
                             use_gpu=True)

# Create LSTM model
lstm_model = create_model('lstm',
                         prediction_horizons=[1, 2, 3, 5],
                         sequence_length=200,
                         use_gpu=True)

# Create Transformer model
transformer_model = create_model('transformer',
                               prediction_horizons=[1, 2, 3, 5],
                               d_model=256,
                               nhead=8,
                               use_gpu=True)

# Train models
results = model.train(mbo_df, validation_split=0.2, test_split=0.1)
```

### **Making Predictions**

```python
# Make predictions for 1-minute horizon
predictions_1min = model.predict(mbo_df, horizon=1)

# Make predictions for 5-minute horizon
predictions_5min = model.predict(mbo_df, horizon=5)
```

### **Model Evaluation**

```python
# Evaluate model performance
metrics = model.evaluate(mbo_df, horizon=1)

print(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
print(f"Max Drawdown: {metrics.max_drawdown:.3f}")
print(f"Win Rate: {metrics.win_rate:.1%}")
print(f"Profit Factor: {metrics.profit_factor:.2f}")
```

## Dashboard Integration

### **Training Interface**

The Streamlit dashboard provides:

1. **Model Selection**: Choose between LightGBM, LSTM, and Transformer
2. **Parameter Configuration**: Adjust model-specific parameters
3. **Training Progress**: Real-time progress tracking with memory monitoring
4. **Results Display**: Comprehensive metrics and financial analysis
5. **Model Management**: Save and register models in the model registry

### **Model Registry**

Models are automatically registered with metadata including:

- Model ID and name
- Training parameters and performance metrics
- File path and size
- Training duration and sample count
- Status tracking (trained, ready_for_backtest, backtested, deployed)

## Performance Expectations

### **Training Times (Approximate)**

- **LightGBM**: 5-15 minutes (GPU accelerated)
- **LSTM**: 30-60 minutes (depending on sequence length)
- **Transformer**: 45-90 minutes (depending on model size)

### **Memory Usage**

- **LightGBM**: 2-4 GB RAM, 2-4 GB GPU
- **LSTM**: 4-8 GB RAM, 4-6 GB GPU
- **Transformer**: 6-12 GB RAM, 6-8 GB GPU

### **Prediction Speed**

- **LightGBM**: ~1000 predictions/second
- **LSTM**: ~100 predictions/second
- **Transformer**: ~50 predictions/second

## Best Practices

### **Model Selection**

1. **Start with LightGBM**: Fast training, good baseline performance
2. **Try LSTM**: If you need better sequence modeling
3. **Use Transformer**: For complex patterns and large datasets

### **Hyperparameter Tuning**

1. **Sequence Length**: 100-500 for LSTM/Transformer
2. **Order Book Depth**: 10-50 levels
3. **Batch Size**: 5000-20000 (memory dependent)
4. **Learning Rate**: 0.001-0.0001 for neural networks

### **Feature Engineering**

1. **Order Flow Features**: Buy/sell imbalance, volume profiles
2. **Market Microstructure**: Spread, depth, resilience
3. **Technical Indicators**: RSI, MACD, Bollinger Bands
4. **Time Features**: Hour, day of week, market sessions

## Troubleshooting

### **Common Issues**

1. **Memory Errors**: Reduce batch size or sequence length
2. **Slow Training**: Enable GPU acceleration and mixed precision
3. **Poor Performance**: Check feature engineering and data quality
4. **Overfitting**: Increase regularization or reduce model complexity

### **Performance Optimization**

1. **GPU Memory**: Monitor with `nvidia-smi`
2. **RAM Usage**: Use memory mapping for large datasets
3. **Training Speed**: Enable mixed precision and gradient accumulation
4. **Prediction Speed**: Use model quantization for inference

## Future Enhancements

### **Planned Features**

1. **Ensemble Methods**: Combine predictions from multiple models
2. **Online Learning**: Continuous model updates with new data
3. **Model Compression**: Quantization and pruning for faster inference
4. **Advanced Attention**: Temporal attention mechanisms
5. **Multi-Asset Support**: Extend to other futures and instruments

### **Research Directions**

1. **Graph Neural Networks**: For order book relationships
2. **Reinforcement Learning**: For optimal trading strategies
3. **Meta-Learning**: For quick adaptation to new market conditions
4. **Causal Inference**: For understanding market causality

## Conclusion

The multi-model framework provides a comprehensive solution for financial time series prediction with:

- **Flexible Architecture**: Easy to add new model types
- **Optimized Performance**: GPU acceleration and memory management
- **Comprehensive Metrics**: Financial and risk evaluation
- **Production Ready**: Model registry and management system
- **Scalable Design**: Separate trade engine for execution

This framework enables systematic model development and comparison while maintaining the flexibility to adapt to changing market conditions and requirements.
