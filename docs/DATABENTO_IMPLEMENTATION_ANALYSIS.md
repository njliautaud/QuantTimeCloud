# Databento Implementation Analysis

## Executive Summary

This document provides a surgical analysis of our current implementation against the comprehensive Databento documentation to ensure we're properly handling all data types, formats, and schemas. The analysis reveals several critical areas that need immediate attention to ensure full compatibility and proper data handling.

## Critical Issues Identified

### 1. **Timestamp Handling Issues**

#### Current Implementation Problems:
- **File**: `quanttime/adapter/databento_loader.py` (lines 280-290)
- **Issue**: Inconsistent timestamp column handling
- **Problem**: Code assumes `ts_event` or `datetime` columns but doesn't handle all Databento timestamp types
- **Impact**: May miss critical timing information

#### Required Fixes:
```python
# Current problematic code:
if 'ts_event' in df.columns:
    df['datetime'] = pd.to_datetime(df['ts_event'], unit='ns')
elif 'datetime' in df.columns:
    pass  # Already converted
else:
    logger.warning("No timestamp column found for filtering")
    return df
```

**Should be:**
```python
# Handle all Databento timestamp types
timestamp_columns = ['ts_event', 'ts_recv', 'ts_in_delta', 'ts_out']
found_timestamp = None

for col in timestamp_columns:
    if col in df.columns:
        found_timestamp = col
        break

if found_timestamp:
    if found_timestamp == 'ts_in_delta':
        # Calculate actual timestamp: ts_recv - ts_in_delta
        if 'ts_recv' in df.columns:
            df['datetime'] = pd.to_datetime(df['ts_recv'] - df['ts_in_delta'], unit='ns')
        else:
            logger.warning("ts_in_delta found but ts_recv missing")
    else:
        df['datetime'] = pd.to_datetime(df[found_timestamp], unit='ns')
else:
    logger.warning("No Databento timestamp columns found")
    return df
```

### 2. **Action Field Inconsistencies**

#### Current Implementation Problems:
- **File**: `quanttime/adapter/mbo_processor.py` (lines 120-140)
- **Issue**: Incorrect action field mapping
- **Problem**: Using lowercase actions ('add', 'cancel', 'fill') instead of Databento standard ('A', 'C', 'F')
- **Impact**: Order book reconstruction failures

#### Required Fixes:
```python
# Current problematic code:
if action == 'A':  # Add order
    self._add_order(price, side, size, order_id)
elif action == 'R':  # Remove order
    self._remove_order(order_id)
elif action == 'M':  # Modify order
    self._modify_order(order_id, price, size)
elif action == 'F':  # Fill/Execute order
    self._fill_order(order_id, size)
elif action == 'C':  # Change order
    self._change_order(order_id, price, size)
elif action == 'T':  # Trade
    self._fill_order(order_id, size)
```

**Should be:**
```python
# Proper Databento action handling
if action == 'A':  # Add - Insert new order into book
    self._add_order(price, side, size, order_id)
elif action == 'M':  # Modify - Change order's price and/or size
    self._modify_order(order_id, price, size)
elif action == 'C':  # Cancel - Fully or partially cancel order
    self._cancel_order(order_id, size)
elif action == 'R':  # Clear - Remove all resting orders for instrument
    self._clear_book()
elif action == 'T':  # Trade - Aggressing order traded (doesn't affect book)
    self._process_trade(price, side, size, order_id)
elif action == 'F':  # Fill - Resting order was filled (doesn't affect book)
    self._process_fill(order_id, size)
elif action == 'N':  # None - No action (may carry flags or other information)
    self._process_none_action(row)
```

### 3. **Side Field Standardization Issues**

#### Current Implementation Problems:
- **File**: `quanttime/features/engineer.py` (lines 15-20)
- **Issue**: Inconsistent side field handling
- **Problem**: Using 'buy'/'sell' instead of Databento standard 'B'/'A'
- **Impact**: Feature calculation errors

#### Required Fixes:
```python
# Current problematic code:
df["delta"] = df["size"].where(df["side"].eq("buy"), -df["size"]).fillna(0)
df["buy_size"] = df["size"].where(df["side"].eq("buy"), 0.0)
df["sell_size"] = df["size"].where(df["side"].eq("sell"), 0.0)
```

**Should be:**
```python
# Proper Databento side handling
df["delta"] = df["size"].where(df["side"].eq("B"), -df["size"]).fillna(0)
df["buy_size"] = df["size"].where(df["side"].eq("B"), 0.0)
df["sell_size"] = df["size"].where(df["side"].eq("A"), 0.0)
```

### 4. **Price Precision Handling**

#### Current Implementation Problems:
- **File**: Multiple files
- **Issue**: Not handling Databento's 1e-9 price precision
- **Problem**: Assuming decimal prices instead of fixed-precision integers
- **Impact**: Price calculation errors

#### Required Fixes:
```python
# Add price conversion utility
def convert_databento_price(price_int: int) -> float:
    """Convert Databento fixed-precision price to decimal."""
    if price_int == 9223372036854775807:  # UNDEF_PRICE
        return np.nan
    return price_int * 1e-9

def convert_to_databento_price(price_float: float) -> int:
    """Convert decimal price to Databento fixed-precision."""
    if pd.isna(price_float):
        return 9223372036854775807  # UNDEF_PRICE
    return int(price_float * 1e9)
```

### 5. **Flag Field Handling Missing**

#### Current Implementation Problems:
- **File**: All MBO processing files
- **Issue**: Not processing Databento flag field
- **Problem**: Missing critical information about message characteristics
- **Impact**: Incorrect order book state

#### Required Fixes:
```python
# Add flag processing
class DatabentoFlags:
    F_LAST = 1 << 7  # 128 - Last record in single event
    F_TOB = 1 << 6   # 64 - Top-of-book message
    F_SNAPSHOT = 1 << 5  # 32 - Message from replay/snapshot
    F_MBP = 1 << 4   # 16 - Aggregated price level message
    F_BAD_TS_RECV = 1 << 3  # 8 - ts_recv inaccurate
    F_MAYBE_BAD_BOOK = 1 << 2  # 4 - Unrecoverable gap detected
    F_PUBLISHER_SPECIFIC = 1 << 1  # 2 - Publisher-specific semantics
    RESERVED = 1 << 0  # 1 - Reserved for internal use

def process_flags(flags: int) -> Dict[str, bool]:
    """Process Databento flags and return dictionary of flag states."""
    return {
        'is_last': bool(flags & DatabentoFlags.F_LAST),
        'is_tob': bool(flags & DatabentoFlags.F_TOB),
        'is_snapshot': bool(flags & DatabentoFlags.F_SNAPSHOT),
        'is_mbp': bool(flags & DatabentoFlags.F_MBP),
        'bad_ts_recv': bool(flags & DatabentoFlags.F_BAD_TS_RECV),
        'maybe_bad_book': bool(flags & DatabentoFlags.F_MAYBE_BAD_BOOK),
        'publisher_specific': bool(flags & DatabentoFlags.F_PUBLISHER_SPECIFIC)
    }
```

### 6. **Publisher ID and Instrument ID Handling**

#### Current Implementation Problems:
- **File**: All data loading files
- **Issue**: Not tracking publisher_id and instrument_id
- **Problem**: Missing critical metadata for data validation
- **Impact**: Data quality issues

#### Required Fixes:
```python
# Add publisher and instrument tracking
class DatabentoMetadata:
    def __init__(self):
        self.publisher_id: Optional[int] = None
        self.instrument_id: Optional[int] = None
        self.dataset: Optional[str] = None
        self.schema: Optional[str] = None
        self.symbols: List[str] = []
        self.start_ts: Optional[int] = None
        self.end_ts: Optional[int] = None

def validate_databento_data(df: pd.DataFrame, metadata: DatabentoMetadata) -> bool:
    """Validate that DataFrame contains expected Databento data."""
    if 'publisher_id' not in df.columns:
        logger.error("Missing publisher_id column")
        return False
    
    if 'instrument_id' not in df.columns:
        logger.error("Missing instrument_id column")
        return False
    
    # Check for expected publisher_id
    if metadata.publisher_id and not df['publisher_id'].eq(metadata.publisher_id).all():
        logger.warning("Unexpected publisher_id values found")
    
    return True
```

### 7. **Sequence Number Handling**

#### Current Implementation Problems:
- **File**: `quanttime/adapter/mbo_processor.py`
- **Issue**: Not using sequence numbers for ordering
- **Problem**: Relying only on timestamps for ordering
- **Impact**: Incorrect event ordering

#### Required Fixes:
```python
# Proper sequence number handling
def sort_mbo_data(df: pd.DataFrame) -> pd.DataFrame:
    """Sort MBO data by timestamp and sequence number."""
    if 'sequence' in df.columns:
        return df.sort_values(['ts_event', 'sequence']).reset_index(drop=True)
    else:
        return df.sort_values('ts_event').reset_index(drop=True)

def detect_sequence_gaps(df: pd.DataFrame) -> List[Tuple[int, int]]:
    """Detect gaps in sequence numbers."""
    if 'sequence' not in df.columns:
        return []
    
    gaps = []
    sequences = df['sequence'].values
    
    for i in range(1, len(sequences)):
        if sequences[i] != sequences[i-1] + 1:
            gaps.append((sequences[i-1], sequences[i]))
    
    return gaps
```

### 8. **Schema Validation Missing**

#### Current Implementation Problems:
- **File**: All data loading files
- **Issue**: Not validating against Databento schemas
- **Problem**: No schema compliance checking
- **Impact**: Data format errors

#### Required Fixes:
```python
# Add schema validation
from databento_dbn import Schema

def validate_mbo_schema(df: pd.DataFrame) -> bool:
    """Validate DataFrame against MBO schema."""
    required_columns = [
        'ts_recv', 'ts_event', 'rtype', 'publisher_id', 'instrument_id',
        'action', 'side', 'price', 'size', 'channel_id', 'order_id',
        'flags', 'ts_in_delta', 'sequence'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing required MBO columns: {missing_columns}")
        return False
    
    # Validate rtype
    if not df['rtype'].eq(160).all():  # MBO rtype
        logger.error("Invalid rtype values for MBO schema")
        return False
    
    return True
```

## Implementation Priority

### **HIGH PRIORITY (Critical for Data Integrity)**
1. **Action Field Standardization** - Fix immediately
2. **Side Field Standardization** - Fix immediately  
3. **Timestamp Handling** - Fix immediately
4. **Price Precision** - Fix immediately

### **MEDIUM PRIORITY (Important for Robustness)**
5. **Flag Field Processing** - Implement within 1 week
6. **Sequence Number Handling** - Implement within 1 week
7. **Schema Validation** - Implement within 1 week

### **LOW PRIORITY (Enhancement)**
8. **Publisher/Instrument ID Tracking** - Implement within 2 weeks

## Testing Strategy

### **Unit Tests Required**
1. **Timestamp Conversion Tests**
   - Test all timestamp types (ts_event, ts_recv, ts_in_delta, ts_out)
   - Test UNDEF_TIMESTAMP handling
   - Test timezone conversions

2. **Action Processing Tests**
   - Test all action types (A, M, C, R, T, F, N)
   - Test action combinations with flags
   - Test edge cases (empty orders, invalid actions)

3. **Side Field Tests**
   - Test B/A/N side values
   - Test side consistency across actions
   - Test side validation

4. **Price Precision Tests**
   - Test 1e-9 precision conversion
   - Test UNDEF_PRICE handling
   - Test negative prices
   - Test price validation

5. **Flag Processing Tests**
   - Test all flag combinations
   - Test flag interpretation
   - Test flag validation

### **Integration Tests Required**
1. **End-to-End MBO Processing**
   - Test complete order book reconstruction
   - Test cumulative delta calculation
   - Test volume tracking

2. **Data Loading Pipeline**
   - Test DBN file loading
   - Test DataFrame conversion
   - Test memory optimization

3. **Feature Engineering Pipeline**
   - Test feature calculation with proper data types
   - Test feature validation
   - Test performance with large datasets

## Migration Plan

### **Phase 1: Critical Fixes (Week 1)**
1. Update action field handling in all files
2. Update side field handling in all files
3. Fix timestamp handling in databento_loader.py
4. Add price precision conversion utilities

### **Phase 2: Robustness Improvements (Week 2)**
1. Add flag field processing
2. Add sequence number handling
3. Add schema validation
4. Update test data generator

### **Phase 3: Enhancement (Week 3)**
1. Add publisher/instrument ID tracking
2. Add comprehensive error handling
3. Add data quality metrics
4. Update documentation

### **Phase 4: Testing & Validation (Week 4)**
1. Implement comprehensive test suite
2. Run integration tests
3. Performance testing
4. Documentation updates

## Conclusion

The analysis reveals that while our current implementation works for basic functionality, it's not fully compliant with Databento's comprehensive data format specifications. The critical issues identified must be addressed to ensure:

1. **Data Integrity**: Proper handling of all Databento data types
2. **Robustness**: Error handling for edge cases and data quality issues
3. **Performance**: Optimized processing of large datasets
4. **Maintainability**: Clear separation of concerns and proper abstraction

The implementation plan provides a structured approach to address these issues while maintaining system stability and functionality.
