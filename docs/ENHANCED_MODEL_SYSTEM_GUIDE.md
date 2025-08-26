# Enhanced Model System Guide for QuantTime ML Trading Suite

## Overview

The Enhanced Model System provides a comprehensive solution for training, managing, and deploying machine learning models for financial prediction. It features a card-based Kanban interface, advanced LightGBM models optimized for 1-5 minute ahead prediction, and seamless integration with the backtesting system.

## Key Features

### 🎯 Financial Prediction Optimized
- **Multi-horizon prediction**: 1, 2, 3, and 5-minute ahead forecasts
- **Real-time tick-by-tick updates**: Continuous prediction updates as new data arrives
- **Advanced feature engineering**: Orderbook, microstructure, and technical indicators
- **Anomaly detection**: Built-in outlier detection for robust predictions

### 🃏 Card-Based Model Management
- **Kanban-style interface**: Visual organization by model status
- **Comprehensive metadata**: Training metrics, parameters, and performance history
- **One-click actions**: View details, backtest, or delete models
- **Status tracking**: Trained → Ready for Backtest → Backtested → Deployed

### 🚀 GPU-Optimized Training
- **Memory-efficient**: Optimized for 16GB RAM and 8GB VRAM
- **Mixed precision**: Automatic float16/float32 optimization
- **Batch processing**: Dynamic batch size adjustment
- **Gradient accumulation**: Simulates larger batches without memory overflow

## Model Architecture

### Enhanced MBO LightGBM Model

The enhanced model incorporates best practices for financial prediction:

```python
# Model Configuration
model_config = {
    'prediction_horizons': [1, 2, 3, 5],  # Minutes ahead
    'orderbook_depth': 20,                 # Orderbook levels
    'sequence_length': 200,                # Historical sequence
    'feature_window': 100,                 # Feature calculation window
    'use_gpu': True,                       # GPU acceleration
    'use_mixed_precision': True,           # Memory optimization
    'max_gpu_memory_gb': 7.0,             # GPU memory limit
    'max_ram_gb': 14.0,                   # RAM limit
    'batch_size': 15000                   # Training batch size
}
```

### Feature Engineering Pipeline

1. **Orderbook Features**
   - Bid/ask levels and spreads
   - Order book imbalance
   - Depth and pressure indicators
   - Order book resilience

2. **Market Microstructure**
   - Order flow imbalance
   - Volume profile analysis
   - Price impact modeling
   - Market efficiency indicators

3. **Technical Indicators**
   - RSI, MACD, Bollinger Bands
   - Moving averages (SMA, EMA)
   - Volatility measures
   - Momentum indicators

4. **Time-Based Features**
   - Intraday patterns
   - Market session indicators
   - Time since market open
   - Seasonal patterns

## Training Pipeline

### 1. Data Loading
```python
# Load MBO data with memory optimization
mbo_df = load_databento_mbo_data(
    symbol="ES",
    start_date="20250714",
    end_date="20250813",
    max_dates=27
)
```

### 2. Feature Engineering
```python
# Advanced feature engineering
features_df = model._engineer_advanced_features(mbo_df)
# Includes: orderbook, microstructure, technical, time features
```

### 3. Target Creation
```python
# Multi-horizon targets
targets = model._create_targets(mbo_df)
# Creates log returns for 1, 2, 3, 5-minute horizons
```

### 4. Model Training
```python
# Train models for each horizon
training_results = model.train(
    mbo_df=mbo_df,
    validation_split=0.2,
    test_split=0.1,
    random_state=42
)
```

### 5. Model Registration
```python
# Automatic registration with metadata
model_id = model_registry.register_model(
    model=trained_model,
    model_name="ES_MBO_LightGBM_1min_v1",
    model_type="lightgbm",
    symbol="ES",
    data_source="mbo",
    training_data=training_info,
    performance_metrics=metrics,
    feature_importance=importance,
    model_params=params,
    training_config=config
)
```

## Card-Based Interface

### Model Cards Display

Each model is displayed as a card with:

- **Color-coded type**: LightGBM (green), LSTM (orange), Transformer (purple)
- **Performance metrics**: RMSE, R², training duration
- **Model parameters**: Orderbook depth, sequence length, batch size
- **Status indicators**: Ready for backtest, deployed, etc.
- **Action buttons**: View details, backtest, delete

### Kanban Board Organization

Models are organized into columns:

1. **✅ Trained**: Models ready for evaluation
2. **🧪 Ready for Backtest**: Models ready for backtesting
3. **📈 Backtested**: Models with backtest results
4. **🚀 Deployed**: Models in live trading

### Model Details View

Clicking "View" on a card shows:

- **📋 Overview**: Model information and training details
- **📊 Performance**: Metrics comparison and charts
- **🎯 Features**: Feature importance analysis
- **⚙️ Configuration**: Model parameters and hyperparameters
- **📈 Predictions**: Real-time prediction display

## Backtesting Integration

### Model Selection
```python
# Select model for backtesting
selected_model_id = render_backtest_model_selector()
```

### Strategy Integration
```python
# Use ML model predictions in strategy
if strategy_type == "ML Model Strategy":
    model = model_registry.get_model(selected_model_id)
    predictions = model.predict_single_tick(mbo_event)
    # Use predictions for trading decisions
```

## Memory Optimization

### GPU Memory Management
- **7GB VRAM limit**: Leaves 1GB buffer for system
- **Mixed precision**: Reduces memory usage by ~50%
- **Dynamic batching**: Adjusts batch size based on available memory
- **Gradient accumulation**: Simulates larger batches

### System RAM Management
- **14GB RAM limit**: Leaves 2GB buffer for system processes
- **Memory mapping**: Datasets loaded via `numpy.memmap`
- **Out-of-core processing**: Data streams from SSD when needed
- **Feature selection**: Removes redundant features

## Usage Examples

### Training a New Model

1. **Navigate to Train tab**
2. **Load MBO data**: Select symbol, date range, max dates
3. **Configure model**: Set parameters for your hardware
4. **Start training**: Click "Train Enhanced MBO LightGBM Model"
5. **Monitor progress**: Real-time training metrics
6. **View results**: Performance metrics and feature importance

### Managing Models

1. **Navigate to Models tab**
2. **View Kanban board**: See all models organized by status
3. **Filter models**: By type, symbol, or status
4. **View details**: Click "View" on any card
5. **Backtest model**: Click "Backtest" to run backtest
6. **Delete model**: Click "Delete" to remove

### Running Backtests

1. **Navigate to Backtests tab**
2. **Select model**: Choose from trained models
3. **Configure parameters**: Set capital, commission, etc.
4. **Choose strategy**: Select "ML Model Strategy"
5. **Run backtest**: Click "Run Backtest"
6. **View results**: Performance metrics and charts

## Performance Expectations

### Training Performance
- **Training time**: 15-30 minutes for 27 days of ES data
- **Memory usage**: ~6-8GB GPU, ~8-10GB RAM
- **Model size**: ~50-100MB saved model file
- **Feature count**: 100-200 engineered features

### Prediction Performance
- **Latency**: <1ms for single tick predictions
- **Accuracy**: RMSE typically 0.001-0.005 for log returns
- **R² score**: 0.1-0.3 for financial time series
- **Horizon accuracy**: 1min > 2min > 3min > 5min

### System Requirements
- **GPU**: 8GB VRAM (NVIDIA GTX 1070 or better)
- **RAM**: 16GB system memory
- **Storage**: SSD recommended for data loading
- **CPU**: 4+ cores for data preprocessing

## Best Practices

### Model Training
1. **Use GPU acceleration**: Always enable for faster training
2. **Enable mixed precision**: Reduces memory usage significantly
3. **Monitor memory usage**: Watch GPU and RAM utilization
4. **Validate results**: Check for overfitting and data leakage
5. **Save models**: Always register models in the registry

### Feature Engineering
1. **Include orderbook features**: Essential for MBO data
2. **Add time features**: Market microstructure is time-dependent
3. **Handle missing values**: Use forward/backward fill
4. **Remove correlations**: Drop highly correlated features
5. **Scale features**: Use RobustScaler for financial data

### Model Management
1. **Use descriptive names**: Include symbol, type, and version
2. **Add notes**: Document model purpose and assumptions
3. **Track performance**: Monitor metrics over time
4. **Version control**: Keep track of model versions
5. **Regular cleanup**: Delete old or poor-performing models

## Troubleshooting

### Common Issues

**Memory Errors**
- Reduce batch size
- Enable mixed precision
- Close other applications
- Use fewer training dates

**Training Failures**
- Check data quality
- Verify feature engineering
- Monitor GPU memory
- Check for NaN values

**Poor Performance**
- Increase training data
- Adjust hyperparameters
- Add more features
- Check for data leakage

### Performance Optimization

**GPU Memory**
```python
# Reduce GPU memory usage
model_config = {
    'max_gpu_memory_gb': 6.0,  # Reduce from 7.0
    'batch_size': 10000,       # Reduce from 15000
    'use_mixed_precision': True
}
```

**System RAM**
```python
# Reduce RAM usage
model_config = {
    'max_ram_gb': 12.0,        # Reduce from 14.0
    'feature_window': 50,       # Reduce from 100
    'sequence_length': 100      # Reduce from 200
}
```

## Future Enhancements

### Planned Features
- **Model ensembles**: Combine multiple models
- **Online learning**: Continuous model updates
- **Hyperparameter optimization**: Automated tuning
- **Model versioning**: Git-like version control
- **A/B testing**: Compare model performance
- **Live deployment**: Real-time trading integration

### Advanced Capabilities
- **Multi-asset models**: Train on multiple symbols
- **Cross-validation**: More robust evaluation
- **Feature selection**: Automated feature importance
- **Model interpretability**: SHAP values and explanations
- **Risk management**: Built-in risk controls
- **Performance monitoring**: Real-time model health

## Conclusion

The Enhanced Model System provides a complete solution for financial prediction with:

- **Advanced models**: Optimized for 1-5 minute ahead prediction
- **Efficient training**: GPU-optimized with memory management
- **Visual management**: Card-based interface with Kanban organization
- **Seamless integration**: Works with existing backtesting system
- **Best practices**: Financial prediction and ML best practices

This system enables rapid development, testing, and deployment of machine learning models for quantitative trading strategies.
