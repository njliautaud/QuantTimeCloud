# Databento Implementation Guide for QuantTime

## Overview
This guide provides implementation details for integrating Databento MBO Level 3 data into the QuantTime platform, ensuring proper data handling, feature engineering, and model training.

## Table of Contents
1. [Data Loading](#data-loading)
2. [Schema Validation](#schema-validation)
3. [Feature Engineering](#feature-engineering)
4. [Order Book Reconstruction](#order-book-reconstruction)
5. [Model Integration](#model-integration)
6. [Performance Optimization](#performance-optimization)

---

## Data Loading

### File Structure
```
GLBX-20250814-LPE95B5DRD/
├── manifest.json          # File manifest
├── metadata.json          # Dataset metadata
├── symbology.json         # Symbol mappings
└── glbx-mdp3-YYYYMMDD.mbo.dbn.zst  # MBO data files
```

### Loading Process
```python
def load_databento_mbo_data(data_dir: str, date: str) -> pd.DataFrame:
    """Load MBO data from Databento DBN files"""
    
    # Construct file path
    file_path = f"{data_dir}/glbx-mdp3-{date}.mbo.dbn.zst"
    
    # Load DBN file
    import databento as db
    dbn = db.DBNStore(file_path)
    df = dbn.to_df()
    
    # Validate schema
    is_valid, message = validate_mbo_schema(df)
    if not is_valid:
        raise ValueError(f"Schema validation failed: {message}")
    
    return df
```

### Data Validation
```python
def validate_mbo_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """Comprehensive MBO data quality validation"""
    
    validation_results = {
        'total_records': len(df),
        'date_range': {
            'start': pd.to_datetime(df['ts_event'].min(), unit='ns'),
            'end': pd.to_datetime(df['ts_event'].max(), unit='ns')
        },
        'actions': df['action'].value_counts().to_dict(),
        'sides': df['side'].value_counts().to_dict(),
        'sequence_gaps': detect_sequence_gaps(df),
        'price_range': {
            'min': df['price'].min() / 1e9,
            'max': df['price'].max() / 1e9,
            'mean': df['price'].mean() / 1e9
        },
        'issues': []
    }
    
    # Check for data quality issues
    if validation_results['sequence_gaps']:
        validation_results['issues'].append(
            f"Found {len(validation_results['sequence_gaps'])} sequence gaps"
        )
    
    if df['price'].isnull().any():
        validation_results['issues'].append("Found null prices")
    
    return validation_results
```

---

## Schema Validation

### Required Fields Check
```python
def validate_mbo_schema(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate DataFrame against MBO schema requirements"""
    
    required_columns = [
        'ts_recv', 'ts_event', 'rtype', 'publisher_id', 'instrument_id',
        'action', 'side', 'price', 'size', 'channel_id', 'order_id',
        'flags', 'ts_in_delta', 'sequence'
    ]
    
    # Check for required columns
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        return False, f"Missing required columns: {missing_columns}"
    
    # Check rtype
    if 'rtype' in df.columns and not all(df['rtype'] == 160):
        return False, "Invalid rtype for MBO data (expected 160)"
    
    # Check data types
    expected_dtypes = {
        'ts_recv': 'uint64',
        'ts_event': 'uint64',
        'rtype': 'uint16',
        'publisher_id': 'uint16',
        'instrument_id': 'uint32',
        'action': 'object',  # char
        'side': 'object',    # char
        'price': 'int64',
        'size': 'uint32',
        'channel_id': 'uint16',
        'order_id': 'uint64',
        'flags': 'uint8',
        'ts_in_delta': 'uint32',
        'sequence': 'uint32'
    }
    
    for col, expected_dtype in expected_dtypes.items():
        if col in df.columns:
            actual_dtype = str(df[col].dtype)
            if expected_dtype not in actual_dtype:
                return False, f"Column {col} has wrong dtype: {actual_dtype} (expected {expected_dtype})"
    
    return True, "Schema validation passed"
```

---

## Feature Engineering

### Order Flow Features
```python
def engineer_order_flow_features(mbo_df: pd.DataFrame) -> pd.DataFrame:
    """Engineer order flow features from MBO data"""
    
    features_df = pd.DataFrame()
    
    # Basic order flow features
    features_df['volume_imbalance'] = calculate_volume_imbalance(mbo_df)
    features_df['price_impact'] = calculate_price_impact(mbo_df)
    features_df['order_flow_intensity'] = calculate_order_flow_intensity(mbo_df)
    
    # Temporal features
    features_df['time_since_last_event'] = calculate_time_deltas(mbo_df)
    features_df['event_frequency'] = calculate_event_frequency(mbo_df)
    
    # Order book features
    features_df['bid_ask_spread'] = calculate_spread(mbo_df)
    features_df['order_book_imbalance'] = calculate_order_book_imbalance(mbo_df)
    
    # Pattern detection features
    features_df['iceberg_detection'] = detect_iceberg_orders(mbo_df)
    features_df['absorption_detection'] = detect_absorption_patterns(mbo_df)
    features_df['order_block_detection'] = detect_order_blocks(mbo_df)
    
    return features_df

def calculate_volume_imbalance(mbo_df: pd.DataFrame) -> pd.Series:
    """Calculate volume imbalance between buy and sell orders"""
    
    # Group by time windows and calculate imbalance
    window_size = '1T'  # 1 minute windows
    
    buy_volume = mbo_df[mbo_df['side'] == 'B']['size'].rolling(window=window_size).sum()
    sell_volume = mbo_df[mbo_df['side'] == 'A']['size'].rolling(window=window_size).sum()
    
    total_volume = buy_volume + sell_volume
    imbalance = (buy_volume - sell_volume) / total_volume
    
    return imbalance.fillna(0)

def detect_iceberg_orders(mbo_df: pd.DataFrame) -> pd.Series:
    """Detect potential iceberg orders"""
    
    # Iceberg detection logic
    large_orders = mbo_df['size'] > mbo_df['size'].rolling(window=100).quantile(0.95)
    low_price_impact = mbo_df['price'].pct_change().abs() < 0.001
    
    iceberg_signal = large_orders & low_price_impact
    
    return iceberg_signal.astype(int)
```

### Rolling Features
```python
def add_rolling_features(features_df: pd.DataFrame, windows: List[int] = None) -> pd.DataFrame:
    """Add rolling window features"""
    
    if windows is None:
        windows = [1, 5, 15]  # 1, 5, 15 minute windows
    
    df = features_df.copy()
    
    # Price-based rolling features
    if 'mid_price' in df.columns:
        for window in windows:
            window_str = f'{window}T'
            df[f'price_ma_{window}m'] = df['mid_price'].rolling(window=window_str).mean()
            df[f'price_std_{window}m'] = df['mid_price'].rolling(window=window_str).std()
            df[f'price_momentum_{window}m'] = df['mid_price'].pct_change(window)
    
    # Volume-based rolling features
    volume_cols = [col for col in df.columns if 'volume' in col and 'ratio' not in col]
    for col in volume_cols:
        for window in windows:
            window_str = f'{window}T'
            df[f'{col}_ma_{window}m'] = df[col].rolling(window=window_str).mean()
            df[f'{col}_std_{window}m'] = df[col].rolling(window=window_str).std()
    
    return df
```

---

## Order Book Reconstruction

### Real-time Order Book
```python
class RealTimeOrderBook:
    """Real-time order book reconstruction from MBO events"""
    
    def __init__(self, max_depth: int = 10):
        self.max_depth = max_depth
        self.bids = {}  # price -> {size: int, orders: List[order_id]}
        self.asks = {}  # price -> {size: int, orders: List[order_id]}
        self.orders = {}  # order_id -> order_info
        self.sequence = 0
    
    def process_event(self, event: Dict) -> Dict[str, Any]:
        """Process MBO event and update order book"""
        
        self.sequence += 1
        
        if event['action'] == 'A':
            return self.add_order(event)
        elif event['action'] == 'M':
            return self.modify_order(event)
        elif event['action'] == 'C':
            return self.cancel_order(event)
        elif event['action'] == 'T':
            return self.process_trade(event)
        elif event['action'] == 'F':
            return self.process_fill(event)
        else:
            return self.process_no_action(event)
    
    def add_order(self, event: Dict) -> Dict[str, Any]:
        """Add new order to order book"""
        
        order_id = event['order_id']
        price = event['price']
        size = event['size']
        side = event['side']
        
        # Store order information
        self.orders[order_id] = {
            'price': price,
            'size': size,
            'side': side,
            'timestamp': event['ts_event']
        }
        
        # Update order book
        if side == 'B':
            if price not in self.bids:
                self.bids[price] = {'size': 0, 'orders': []}
            self.bids[price]['size'] += size
            self.bids[price]['orders'].append(order_id)
        else:  # side == 'A'
            if price not in self.asks:
                self.asks[price] = {'size': 0, 'orders': []}
            self.asks[price]['size'] += size
            self.asks[price]['orders'].append(order_id)
        
        return self.get_order_book_snapshot()
    
    def get_order_book_snapshot(self) -> Dict[str, Any]:
        """Get current order book snapshot"""
        
        # Sort bids (descending) and asks (ascending)
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:self.max_depth]
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])[:self.max_depth]
        
        return {
            'bids': sorted_bids,
            'asks': sorted_asks,
            'best_bid': sorted_bids[0][0] if sorted_bids else None,
            'best_ask': sorted_asks[0][0] if sorted_asks else None,
            'spread': (sorted_asks[0][0] - sorted_bids[0][0]) if (sorted_bids and sorted_asks) else None,
            'mid_price': (sorted_bids[0][0] + sorted_asks[0][0]) / 2 if (sorted_bids and sorted_asks) else None,
            'sequence': self.sequence
        }
```

---

## Model Integration

### Feature Matrix Creation
```python
def create_feature_matrix(mbo_df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Create feature matrix for model training"""
    
    # Engineer basic features
    features_df = engineer_order_flow_features(mbo_df)
    
    # Add rolling features
    if config.include_rolling_features:
        features_df = add_rolling_features(features_df, config.rolling_windows)
    
    # Add cross features
    if config.include_cross_features:
        features_df = add_cross_features(features_df)
    
    # Create target variables
    features_df = create_target_variables(features_df, config.target_horizons)
    
    # Handle missing values
    features_df = features_df.fillna(method='ffill').fillna(0)
    
    return features_df

def create_target_variables(features_df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    """Create target variables for different prediction horizons"""
    
    df = features_df.copy()
    
    # Ensure datetime index
    if 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['ts_event'], unit='ns')
    
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Create price targets for different horizons
    if 'mid_price' in df.columns:
        for horizon in horizons:
            # Future price
            df[f'price_target_{horizon}m'] = df['mid_price'].shift(-horizon)
            
            # Price change
            df[f'price_change_{horizon}m'] = df['mid_price'].pct_change(horizon).shift(-horizon)
            
            # Direction (1 for up, 0 for down)
            df[f'direction_{horizon}m'] = (df[f'price_change_{horizon}m'] > 0).astype(int)
    
    return df
```

---

## Performance Optimization

### Memory Management
```python
def optimize_memory_usage(df: pd.DataFrame) -> pd.DataFrame:
    """Optimize DataFrame memory usage"""
    
    # Downcast numeric columns
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    # Optimize object columns
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() / len(df) < 0.5:  # Low cardinality
            df[col] = df[col].astype('category')
    
    return df

def process_in_chunks(df: pd.DataFrame, chunk_size: int = 10000) -> Generator[pd.DataFrame, None, None]:
    """Process DataFrame in chunks to manage memory"""
    
    for start_idx in range(0, len(df), chunk_size):
        end_idx = min(start_idx + chunk_size, len(df))
        chunk = df.iloc[start_idx:end_idx].copy()
        
        yield chunk
        
        # Clear chunk from memory
        del chunk
```

### Batch Processing
```python
def batch_feature_engineering(mbo_df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Process feature engineering in batches"""
    
    total_rows = len(mbo_df)
    batch_size = config.batch_size
    feature_dfs = []
    
    for start_idx in range(0, total_rows, batch_size):
        end_idx = min(start_idx + batch_size, total_rows)
        batch = mbo_df.iloc[start_idx:end_idx].copy()
        
        # Process batch
        batch_features = create_feature_matrix(batch, config)
        feature_dfs.append(batch_features)
        
        # Clear batch from memory
        del batch
    
    # Combine all batches
    combined_df = pd.concat(feature_dfs, ignore_index=True)
    del feature_dfs
    
    return combined_df
```

---

## Integration with QuantTime Models

### Model Training Integration
```python
def train_model_with_databento_data(mbo_df: pd.DataFrame, model_config: ModelConfig) -> Model:
    """Train model with Databento MBO data"""
    
    # Create feature matrix
    features_df = create_feature_matrix(mbo_df, model_config.feature_config)
    
    # Split data
    train_df, val_df, test_df = split_data_by_time(features_df)
    
    # Prepare training data
    X_train, y_train = prepare_training_data(train_df, model_config.target_horizons)
    X_val, y_val = prepare_training_data(val_df, model_config.target_horizons)
    X_test, y_test = prepare_training_data(test_df, model_config.target_horizons)
    
    # Train model
    model = create_model(model_config)
    model.fit(X_train, y_train, validation_data=(X_val, y_val))
    
    # Evaluate model
    test_metrics = model.evaluate(X_test, y_test)
    
    return model, test_metrics

def prepare_training_data(features_df: pd.DataFrame, target_horizons: List[int]) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare training data for model"""
    
    # Select feature columns (exclude target columns)
    feature_cols = [col for col in features_df.columns 
                   if not any(f'target_{h}m' in col or f'direction_{h}m' in col 
                            for h in target_horizons)]
    
    X = features_df[feature_cols].values
    
    # Create multi-target for all horizons
    y_targets = []
    for horizon in target_horizons:
        target_col = f'direction_{horizon}m'
        if target_col in features_df.columns:
            y_targets.append(features_df[target_col].values)
    
    y = np.column_stack(y_targets)
    
    # Remove rows with NaN values
    valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y).any(axis=1))
    X = X[valid_mask]
    y = y[valid_mask]
    
    return X, y
```

This implementation guide ensures proper integration of Databento MBO data into the QuantTime platform while maintaining data quality and performance.
