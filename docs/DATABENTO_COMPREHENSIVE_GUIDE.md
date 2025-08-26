# Databento Comprehensive Data Guide

## Overview
This document provides comprehensive information about Databento's data formats, schemas, and conventions for MBO (Market By Order) Level 3 data processing in the QuantTime platform.

## Table of Contents
1. [Data Formats](#data-formats)
2. [Timestamps](#timestamps)
3. [Prices](#prices)
4. [Side Conventions](#side-conventions)
5. [Action Codes](#action-codes)
6. [Flags](#flags)
7. [Rtype](#rtype)
8. [DBN Encoding](#dbn-encoding)
9. [MBO Schema](#mbo-schema)
10. [Data Processing](#data-processing)

---

## Data Formats

### DBN (Databento Binary Encoding)
- **Format**: Binary encoding optimized for high-frequency data
- **Compression**: Zstandard (zst) compression
- **File Extension**: `.dbn.zst`
- **Schema**: Defined by `rtype` field
- **Endianness**: Little-endian
- **Timestamp Precision**: Nanoseconds (1e-9)

### MBO (Market By Order) Level 3
- **Schema**: `rtype = 160`
- **Data Type**: Order book events
- **Granularity**: Individual order events
- **Real-time**: Yes, with nanosecond precision

---

## Timestamps

### Timestamp Fields
- **`ts_event`**: Event timestamp (nanoseconds)
- **`ts_recv`**: Receive timestamp (nanoseconds)
- **`ts_in_delta`**: Input delta timestamp (nanoseconds)
- **`ts_out`**: Output timestamp (nanoseconds)

### Timestamp Processing
```python
# Convert nanoseconds to datetime
datetime.fromtimestamp(ts_event / 1e9)

# Convert datetime to nanoseconds
int(datetime.timestamp() * 1e9)
```

### Timezone Handling
- **Exchange Time**: All timestamps are in exchange local time
- **UTC Conversion**: Apply exchange-specific timezone offsets
- **Daylight Saving**: Handle DST transitions automatically

---

## Prices

### Price Precision
- **Fixed Precision**: 1e-9 (9 decimal places)
- **Example**: 5000.123456789
- **Range**: 0 to 2^64 - 1 in fixed-point units

### Price Conversion
```python
# Convert from Databento fixed-point to decimal
price_decimal = price_fixed / 1e9

# Convert from decimal to Databento fixed-point
price_fixed = int(price_decimal * 1e9)
```

### Special Price Values
- **`UNDEF_PRICE`**: 0x7FFFFFFFFFFFFFFF (undefined price)
- **`UNDEF_TIMESTAMP`**: 0x7FFFFFFFFFFFFFFF (undefined timestamp)

---

## Side Conventions

### Side Values
- **`'B'`**: Buy/Bid side
- **`'A'`**: Ask/Sell side
- **`'N'`**: No side (for certain events)

### Side Processing
```python
# Standardize side values
def standardize_side(side):
    if side in ['B', 'buy', 'bid']:
        return 'B'
    elif side in ['A', 'ask', 'sell']:
        return 'A'
    else:
        return 'N'
```

---

## Action Codes

### Databento Action Codes
- **`'A'`**: Add order
- **`'M'`**: Modify order
- **`'C'`**: Cancel order
- **`'T'`**: Trade/Execution
- **`'F'`**: Fill
- **`'R'`**: Replace order
- **`'N'`**: No action

### Action Descriptions
```python
ACTION_DESCRIPTIONS = {
    'A': 'Add new order to order book',
    'M': 'Modify existing order (price/size)',
    'C': 'Cancel order completely',
    'T': 'Trade execution (market order)',
    'F': 'Partial or full fill of limit order',
    'R': 'Replace order with new order ID',
    'N': 'No action (heartbeat/status)'
}
```

### Action Processing
```python
def process_action(action, order_data):
    if action == 'A':
        return add_order(order_data)
    elif action == 'M':
        return modify_order(order_data)
    elif action == 'C':
        return cancel_order(order_data)
    elif action == 'T':
        return process_trade(order_data)
    elif action == 'F':
        return process_fill(order_data)
    elif action == 'R':
        return replace_order(order_data)
    else:
        return process_no_action(order_data)
```

---

## Flags

### Flag Values
- **`0`**: No special flags
- **`1`**: End of snapshot
- **`2`**: End of transmission
- **`4`**: End of day
- **`8`**: End of week
- **`16`**: End of month
- **`32`**: End of quarter
- **`64`**: End of year

### Flag Processing
```python
def process_flags(flags):
    flag_descriptions = []
    
    if flags & 1:
        flag_descriptions.append("End of snapshot")
    if flags & 2:
        flag_descriptions.append("End of transmission")
    if flags & 4:
        flag_descriptions.append("End of day")
    if flags & 8:
        flag_descriptions.append("End of week")
    if flags & 16:
        flag_descriptions.append("End of month")
    if flags & 32:
        flag_descriptions.append("End of quarter")
    if flags & 64:
        flag_descriptions.append("End of year")
    
    return flag_descriptions
```

---

## Rtype

### Record Types
- **`160`**: MBO (Market By Order) Level 3
- **`161`**: MBP (Market By Price) Level 2
- **`162`**: OHLCV (Open/High/Low/Close/Volume)
- **`163`**: Trades
- **`164`**: Imbalances
- **`165`**: Statistics

### Schema Validation
```python
def validate_mbo_schema(df):
    required_columns = [
        'ts_recv', 'ts_event', 'rtype', 'publisher_id', 'instrument_id',
        'action', 'side', 'price', 'size', 'channel_id', 'order_id',
        'flags', 'ts_in_delta', 'sequence'
    ]
    
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        return False, f"Missing required columns: {missing_columns}"
    
    if 'rtype' in df.columns and not all(df['rtype'] == 160):
        return False, "Invalid rtype for MBO data"
    
    return True, "Schema validation passed"
```

---

## DBN Encoding

### Binary Structure
```
Header (32 bytes):
- Magic number: 0x44424E00 ("DBN\0")
- Version: 1
- Schema: rtype
- Start time: ts_event
- End time: ts_event
- Count: number of records

Records (variable length):
- Each record follows schema definition
- Fixed-width fields for performance
- Little-endian byte order
```

### DBN Processing
```python
def read_dbn_file(file_path):
    """Read DBN file and return DataFrame"""
    import databento as db
    
    # Load DBN file
    dbn = db.DBNStore(file_path)
    
    # Convert to DataFrame
    df = dbn.to_df()
    
    return df
```

---

## MBO Schema

### Required Fields
```python
MBO_REQUIRED_FIELDS = {
    'ts_recv': 'uint64',      # Receive timestamp (ns)
    'ts_event': 'uint64',     # Event timestamp (ns)
    'rtype': 'uint16',        # Record type (160 for MBO)
    'publisher_id': 'uint16', # Data publisher ID
    'instrument_id': 'uint32', # Instrument ID
    'action': 'char',         # Action code (A/M/C/T/F/R/N)
    'side': 'char',          # Side (B/A/N)
    'price': 'int64',        # Price (fixed-point 1e-9)
    'size': 'uint32',        # Order size
    'channel_id': 'uint16',  # Channel ID
    'order_id': 'uint64',    # Order ID
    'flags': 'uint8',        # Flags
    'ts_in_delta': 'uint32', # Input delta timestamp
    'sequence': 'uint32'     # Sequence number
}
```

### Optional Fields
```python
MBO_OPTIONAL_FIELDS = {
    'new_order_id': 'uint64', # New order ID (for replace)
    'new_price': 'int64',     # New price (for modify)
    'new_size': 'uint32',     # New size (for modify)
    'symbol': 'string'        # Symbol string
}
```

---

## Data Processing

### Order Book Reconstruction
```python
class OrderBook:
    def __init__(self):
        self.bids = {}  # price -> size
        self.asks = {}  # price -> size
        self.orders = {}  # order_id -> order_info
    
    def process_mbo_event(self, event):
        if event['action'] == 'A':
            self.add_order(event)
        elif event['action'] == 'M':
            self.modify_order(event)
        elif event['action'] == 'C':
            self.cancel_order(event)
        elif event['action'] == 'T':
            self.process_trade(event)
        elif event['action'] == 'F':
            self.process_fill(event)
```

### Sequence Gap Detection
```python
def detect_sequence_gaps(df):
    """Detect gaps in sequence numbers"""
    if 'sequence' not in df.columns:
        return []
    
    gaps = []
    sequences = df['sequence'].values
    
    for i in range(1, len(sequences)):
        if sequences[i] != sequences[i-1] + 1:
            gaps.append((sequences[i-1], sequences[i]))
    
    return gaps
```

### Data Quality Validation
```python
def validate_databento_data(df):
    """Comprehensive data validation"""
    issues = []
    
    # Check for required columns
    required_cols = ['ts_event', 'action', 'side', 'price', 'size']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")
    
    # Check for valid actions
    valid_actions = ['A', 'M', 'C', 'T', 'F', 'R', 'N']
    invalid_actions = set(df['action'].unique()) - set(valid_actions)
    if invalid_actions:
        issues.append(f"Invalid actions: {invalid_actions}")
    
    # Check for valid sides
    valid_sides = ['B', 'A', 'N']
    invalid_sides = set(df['side'].unique()) - set(valid_sides)
    if invalid_sides:
        issues.append(f"Invalid sides: {invalid_sides}")
    
    # Check for reasonable price ranges
    if 'price' in df.columns:
        price_range = df['price'].describe()
        if price_range['min'] < 0 or price_range['max'] > 1e12:
            issues.append("Price values out of reasonable range")
    
    return issues
```

---

## Best Practices

### Data Loading
1. **Always validate schema** before processing
2. **Handle sequence gaps** gracefully
3. **Process in batches** for large datasets
4. **Use appropriate data types** for memory efficiency

### Feature Engineering
1. **Preserve temporal order** in all processing
2. **Handle missing values** appropriately
3. **Normalize prices** to decimal format
4. **Track order book state** accurately

### Performance Optimization
1. **Use vectorized operations** where possible
2. **Minimize DataFrame copies**
3. **Use appropriate data types** (uint32 vs int64)
4. **Process in chunks** for large datasets

---

## Integration with QuantTime

### Data Pipeline Integration
```python
# In quanttime/adapter/databento_loader.py
def load_mbo_data(file_path):
    """Load and validate MBO data"""
    df = read_dbn_file(file_path)
    
    # Validate schema
    is_valid, message = validate_mbo_schema(df)
    if not is_valid:
        raise ValueError(f"Schema validation failed: {message}")
    
    # Process timestamps
    df = handle_databento_timestamps(df)
    
    # Sort by sequence
    df = sort_mbo_data(df)
    
    return df
```

### Feature Engineering Integration
```python
# In quanttime/features/mbo_features.py
def engineer_mbo_features(mbo_df):
    """Engineer features from MBO data"""
    # Ensure proper data types
    mbo_df = convert_databento_data_types(mbo_df)
    
    # Process order book
    order_book = reconstruct_order_book(mbo_df)
    
    # Generate features
    features = generate_order_flow_features(order_book, mbo_df)
    
    return features
```

This comprehensive guide ensures that all Databento data is processed correctly and consistently throughout the QuantTime platform.
