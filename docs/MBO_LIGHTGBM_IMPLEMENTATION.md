# MBO LightGBM Implementation Guide

## Overview

This document describes the comprehensive implementation of a LightGBM model for Market By Order (MBO) data in the QuantTime ML Trading Suite. The implementation includes real-time tick-by-tick processing, comprehensive feature engineering, GPU optimization, and memory-efficient training.

## Architecture

### Core Components

1. **MBOFeatureEngineer** (`quanttime/features/mbo_feature_engineering.py`)
   - Real-time order book reconstruction
   - Market microstructure features
   - Technical indicators
   - Volume profile features
   - Time-based features

2. **MBOLightGBMModel** (`quanttime/models/mbo_lightgbm_model.py`)
   - GPU-optimized LightGBM training
   - Memory-efficient data handling
   - Model persistence and loading
   - Performance monitoring

3. **Training Script** (`scripts/train_mbo_lightgbm.py`)
   - End-to-end training pipeline
   - Data validation and preprocessing
   - Hyperparameter optimization
   - Model evaluation

4. **Dashboard Integration** (`quanttime/dashboard/app.py`)
   - Interactive model training
   - Real-time parameter configuration
   - Training progress monitoring
   - Model performance visualization

## Feature Engineering

### Order Book Features

The MBO feature engineer maintains a real-time order book and extracts the following features:

```python
# Bid features
'best_bid': float,              # Best bid price
'bid_depth': int,               # Number of bid levels
'bid_size_total': float,        # Total bid size
'bid_size_imbalance': float,    # Size imbalance at best bid
'bid_price_spread': float,      # Price spread across bid levels
'bid_size_weighted_price': float, # Size-weighted average bid price

# Ask features
'best_ask': float,              # Best ask price
'ask_depth': int,               # Number of ask levels
'ask_size_total': float,        # Total ask size
'ask_size_imbalance': float,    # Size imbalance at best ask
'ask_price_spread': float,      # Price spread across ask levels
'ask_size_weighted_price': float, # Size-weighted average ask price

# Spread features
'spread': float,                # Bid-ask spread
'spread_bps': float,            # Spread in basis points
'mid_price': float,             # Mid price
'size_imbalance': float,        # Overall size imbalance
```

### Price Action Features

```python
'price_change': float,          # Current price change
'price_change_pct': float,      # Percentage price change
'price_volatility': float,      # Rolling price volatility
'price_momentum': float,        # Price momentum over longer period
'price_acceleration': float,    # Change in momentum
```

### Volume Features

```python
'volume_change': float,         # Current volume change
'volume_change_pct': float,     # Percentage volume change
'volume_ma': float,             # Volume moving average
'volume_std': float,            # Volume standard deviation
'volume_imbalance': float,      # Buy/sell volume imbalance
'volume_momentum': float,       # Volume momentum
'volume_acceleration': float,   # Change in volume momentum
```

### Technical Indicators

```python
'rsi': float,                   # Relative Strength Index
'macd': float,                  # MACD indicator
'bollinger_upper': float,       # Bollinger Band upper
'bollinger_lower': float,       # Bollinger Band lower
'bollinger_position': float,    # Position within Bollinger Bands
'ema_short': float,             # Short-term EMA
'ema_long': float,              # Long-term EMA
```

### Time Features

```python
'hour': int,                    # Hour of day
'minute': int,                  # Minute of hour
'second': int,                  # Second of minute
'time_decimal': float,          # Decimal time representation
'market_session': float,        # Market session indicator
'session_progress': float,      # Progress through session
'is_market_open': float,        # Market open indicator
'weekday': int,                 # Day of week
'is_monday': float,             # Monday indicator
'is_friday': float,             # Friday indicator
'is_weekend': float,            # Weekend indicator
```

## Model Configuration

### Default Parameters

The model uses optimized default parameters for MBO data:

```python
base_params = {
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.9,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'random_state': 42
}
```

### GPU Optimization

When GPU acceleration is enabled:

```python
gpu_params = {
    'device': 'gpu',
    'gpu_platform_id': 0,
    'gpu_device_id': 0,
    'max_bin': 255,
    'min_data_in_bin': 3,
    'max_memory_usage': int(max_gpu_memory_gb * 1024),
    'force_col_wise': True,
    'gpu_use_dp': not use_mixed_precision
}
```

### Memory Optimization

```python
memory_params = {
    'max_memory_usage': int(max_ram_gb * 1024),
    'num_threads': 4,
    'histogram_pool_size': -1,
    'max_depth': 6,
    'min_child_samples': 20,
    'min_split_gain': 0.0
}
```

## Training Pipeline

### Data Loading

```python
# Load MBO data from Databento files
mbo_df = load_databento_mbo_data(
    data_dir="GLBX-20250814-LPE95B5DRD",
    start_date="20250714",
    end_date="20250813",
    symbol="ES.FUT"
)
```

### Data Validation

The pipeline validates:
- Required columns (price, size, side, action)
- Data types (numeric prices and sizes)
- Valid actions (A, M, D, F)
- Valid sides (B, S)
- Reasonable price and size ranges
- Missing value handling

### Feature Engineering

```python
# Create feature engineer
feature_engineer = create_mbo_features_pipeline(
    orderbook_depth=10,
    sequence_length=100,
    feature_window=50,
    use_mixed_precision=True
)

# Process MBO data
features_df, targets_series = feature_engineer.process_mbo_dataframe(mbo_df)
```

### Model Training

```python
# Create model
model = create_mbo_lightgbm_model(
    orderbook_depth=10,
    sequence_length=100,
    feature_window=50,
    prediction_horizon=10,
    use_gpu=True,
    use_mixed_precision=True
)

# Train model
training_results = model.train(
    mbo_df=mbo_df,
    validation_split=0.2,
    test_split=0.1,
    random_state=42
)
```

## Usage Examples

### Command Line Training

```bash
# Basic training
python scripts/train_mbo_lightgbm.py \
    --start-date 20250714 \
    --end-date 20250813 \
    --symbol ES.FUT \
    --use-gpu \
    --save-model

# With hyperparameter optimization
python scripts/train_mbo_lightgbm.py \
    --start-date 20250714 \
    --end-date 20250813 \
    --symbol ES.FUT \
    --use-gpu \
    --optimize-hyperparams \
    --n-trials 100 \
    --save-model
```

### Python API

```python
from quanttime.models.mbo_lightgbm_model import create_mbo_lightgbm_model
from quanttime.runtime.hist_service import load_databento_mbo_data

# Load data
mbo_df = load_databento_mbo_data(
    data_dir="GLBX-20250814-LPE95B5DRD",
    start_date="20250714",
    end_date="20250813",
    symbol="ES.FUT"
)

# Create and train model
model = create_mbo_lightgbm_model(
    orderbook_depth=10,
    sequence_length=100,
    feature_window=50,
    prediction_horizon=10,
    use_gpu=True,
    use_mixed_precision=True
)

# Train
training_results = model.train(mbo_df)

# Make predictions
predictions = model.predict(mbo_df)

# Single tick prediction
sample_event = {
    'price': 5000.0,
    'size': 100,
    'side': 'B',
    'action': 'F',
    'timestamp': datetime.now()
}
prediction = model.predict_single_tick(sample_event)
```

### Dashboard Usage

1. **Load Data**: Use the "Load DBN Data for Training" button in the Train tab
2. **Configure Parameters**: Set order book depth, sequence length, feature window, etc.
3. **Train Model**: Click "Train MBO LightGBM Model"
4. **Monitor Progress**: View training metrics and feature importance
5. **Save/Load**: Use model action buttons to save or load trained models

## Performance Optimization

### Memory Management

- **Mixed Precision**: Uses float32/float16 for memory efficiency
- **Memory Mapping**: Large datasets stream from disk
- **Batch Processing**: Processes data in configurable chunks
- **Garbage Collection**: Automatic memory cleanup

### GPU Optimization

- **GPU Memory Management**: Monitors and optimizes GPU memory usage
- **Mixed Precision Training**: Reduces memory usage by 50%
- **Gradient Accumulation**: Simulates large batch sizes
- **Dynamic Batch Sizing**: Adjusts based on available memory

### Training Optimization

- **Feature Caching**: Caches computed features
- **Parallel Processing**: Uses multiple workers for data loading
- **Early Stopping**: Prevents overfitting
- **Model Checkpointing**: Saves intermediate states

## Model Evaluation

### Metrics

The model tracks comprehensive performance metrics:

```python
metrics = {
    'train_rmse': float,        # Training RMSE
    'train_mae': float,         # Training MAE
    'train_r2': float,          # Training R²
    'val_rmse': float,          # Validation RMSE
    'val_mae': float,           # Validation MAE
    'val_r2': float,            # Validation R²
    'test_rmse': float,         # Test RMSE
    'test_mae': float,          # Test MAE
    'test_r2': float,           # Test R²
    'train_target_std': float,  # Training target std
    'val_target_std': float,    # Validation target std
    'test_target_std': float    # Test target std
}
```

### Feature Importance

The model provides feature importance analysis:

```python
feature_importance = model.feature_importance
# Returns DataFrame with feature names and importance scores
```

### Model Summary

```python
summary = model.get_model_summary()
# Returns comprehensive model information including:
# - Configuration
# - Performance metrics
# - Feature importance
# - Data splits
```

## Model Persistence

### Saving Models

```python
model.save_model("models/mbo_lightgbm_model.pkl")
```

Saves:
- Trained LightGBM model
- Feature scaler
- Feature names
- Model parameters
- Training history
- Feature importance
- Configuration

### Loading Models

```python
model = create_mbo_lightgbm_model()
model.load_model("models/mbo_lightgbm_model.pkl")
```

## Hyperparameter Optimization

### Optuna Integration

The model supports hyperparameter optimization using Optuna:

```python
optimization_results = model.optimize_hyperparameters(
    mbo_df=mbo_df,
    param_grid={
        'num_leaves': [15, 31, 63, 127],
        'learning_rate': [0.01, 0.05, 0.1, 0.2],
        'feature_fraction': [0.7, 0.8, 0.9, 1.0],
        'bagging_fraction': [0.7, 0.8, 0.9, 1.0],
        'min_child_samples': [10, 20, 50, 100],
        'reg_alpha': [0, 0.1, 0.5, 1.0],
        'reg_lambda': [0, 0.1, 0.5, 1.0]
    },
    cv_folds=3,
    n_trials=50
)
```

## Real-Time Prediction

### Single Tick Prediction

```python
# Process single MBO event
mbo_event = {
    'price': 5000.0,
    'size': 100,
    'side': 'B',
    'action': 'F',
    'timestamp': datetime.now()
}

prediction = model.predict_single_tick(mbo_event)
```

### Batch Prediction

```python
# Process multiple MBO events
predictions = model.predict(mbo_df)
```

## Troubleshooting

### Common Issues

1. **Memory Errors**
   - Reduce batch size
   - Enable mixed precision
   - Use memory mapping
   - Reduce feature window

2. **GPU Errors**
   - Check GPU memory availability
   - Reduce model complexity
   - Use CPU fallback

3. **Data Quality Issues**
   - Validate input data
   - Check for missing values
   - Verify data types

4. **Training Issues**
   - Check learning rate
   - Adjust regularization
   - Monitor overfitting

### Performance Tuning

1. **For Better Accuracy**
   - Increase sequence length
   - Add more features
   - Optimize hyperparameters
   - Use more training data

2. **For Faster Training**
   - Reduce batch size
   - Use GPU acceleration
   - Enable mixed precision
   - Reduce feature count

3. **For Memory Efficiency**
   - Use memory mapping
   - Enable mixed precision
   - Reduce batch size
   - Use feature selection

## Future Enhancements

1. **Multi-Symbol Support**
   - Train on multiple symbols
   - Cross-symbol features
   - Ensemble models

2. **Advanced Features**
   - Market microstructure indicators
   - Order flow imbalance
   - Liquidity measures
   - Volatility forecasting

3. **Model Improvements**
   - Deep learning integration
   - Attention mechanisms
   - Multi-task learning
   - Online learning

4. **Deployment**
   - Real-time inference
   - Model serving
   - A/B testing
   - Performance monitoring

This implementation provides a comprehensive, production-ready solution for MBO-based machine learning in quantitative trading.
