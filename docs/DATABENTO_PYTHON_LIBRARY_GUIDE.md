# Databento Python Library Guide

## Overview

The Databento Python library provides a comprehensive interface for accessing Databento's market data services. It supports both historical data retrieval and live data streaming, with full DBN (Databento Binary Encoding) support.

## Installation

```bash
pip install databento
```

## Core Components

### 1. Client Initialization

```python
import databento as db

# Initialize client with API key
client = db.Historical(
    key="your_api_key_here",
    # Optional parameters
    # gateway="bo1",  # Gateway selection
    # port=443,       # Port number
    # timeout=30,     # Timeout in seconds
)
```

### 2. Historical Data Access

#### Basic Historical Data Request

```python
# Request historical data
data = client.timeseries.get_range(
    dataset="GLBX.MDP3",           # Dataset identifier
    symbols="ES.c.0",              # Symbol(s) to request
    stype_in="continuous",         # Input symbology type
    start="2024-01-01T00:00:00",  # Start time
    end="2024-01-02T00:00:00",    # End time
    schema="ohlcv-1m",            # Data schema
)

# Convert to pandas DataFrame
df = data.to_df()
```

#### Available Schemas

| Schema | Description | Use Case |
|--------|-------------|----------|
| `ohlcv-1m` | 1-minute OHLCV bars | Technical analysis, charting |
| `ohlcv-1h` | 1-hour OHLCV bars | Daily analysis |
| `ohlcv-1d` | Daily OHLCV bars | Long-term analysis |
| `trades` | Individual trades | Tick-by-tick analysis |
| `mbo` | Market by Order (Level 3) | Order book reconstruction |
| `mbp-1` | Market by Price (Level 1) | Top of book |
| `mbp-10` | Market by Price (Level 2) | Depth of market |
| `definition` | Instrument definitions | Symbol mapping |
| `statistics` | Market statistics | Volume analysis |

#### Symbol Types (stype_in/stype_out)

| Type | Description | Example |
|------|-------------|---------|
| `native` | Exchange-specific symbols | `ESU4` |
| `continuous` | Continuous contract symbols | `ES.c.0` |
| `parent` | Parent contract symbols | `ES` |
| `instrument_id` | Numeric instrument IDs | `12345` |
| `product_id` | Product-level symbols | `ES` |

### 3. Live Data Streaming

#### Initialize Live Client

```python
# Initialize live client
live_client = db.Live(
    key="your_api_key_here",
    dataset="GLBX.MDP3",
)

# Define callback for incoming data
def on_message(message):
    print(f"Received: {message}")

# Start streaming
live_client.subscribe(
    symbols=["ES.c.0"],
    schema="mbo",
    callback=on_message,
)
```

#### Live Streaming with Context Manager

```python
with db.Live(key="your_api_key_here", dataset="GLBX.MDP3") as live:
    live.subscribe(
        symbols=["ES.c.0"],
        schema="mbo",
        callback=on_message,
    )
    
    # Keep streaming for specified duration
    import time
    time.sleep(3600)  # Stream for 1 hour
```

### 4. DBN File Operations

#### Reading DBN Files

```python
# Read DBN file directly
dbn_store = db.read_dbn("path/to/file.dbn")

# Convert to DataFrame
df = dbn_store.to_df()

# Access metadata
metadata = dbn_store.metadata
print(f"Dataset: {metadata.dataset}")
print(f"Schema: {metadata.schema}")
print(f"Start: {metadata.start}")
print(f"End: {metadata.end}")
```

#### Writing DBN Files

```python
# Create DBN store from DataFrame
dbn_store = db.DBNStore.from_df(
    df=your_dataframe,
    dataset="GLBX.MDP3",
    schema="mbo",
)

# Write to file
dbn_store.to_file("output.dbn")
```

### 5. Advanced Features

#### Batch Processing

```python
# Process multiple symbols efficiently
symbols = ["ES.c.0", "NQ.c.0", "YM.c.0"]
data = client.timeseries.get_range(
    dataset="GLBX.MDP3",
    symbols=symbols,
    schema="ohlcv-1m",
    start="2024-01-01T00:00:00",
    end="2024-01-02T00:00:00",
)
```

#### Symbol Resolution

```python
# Get symbol mappings
mappings = client.symbology.resolve(
    dataset="GLBX.MDP3",
    symbols=["ESU4", "NQU4"],
    stype_in="native",
    stype_out="instrument_id",
)

# Access mapping information
for mapping in mappings:
    print(f"Symbol: {mapping.raw_symbol}")
    for interval in mapping.intervals:
        print(f"  {interval.start_date} - {interval.end_date}: {interval.symbol}")
```

#### Dataset Information

```python
# Get available datasets
datasets = client.metadata.list_datasets()
for dataset in datasets:
    print(f"Dataset: {dataset.dataset}")
    print(f"Description: {dataset.description}")
    print(f"Schemas: {dataset.schemas}")

# Get dataset details
details = client.metadata.get_dataset_schema("GLBX.MDP3")
print(f"Available schemas: {details.schemas}")
```

### 6. Error Handling

```python
import databento as db
from databento.common import DatabentoError

try:
    data = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols="INVALID.SYMBOL",
        schema="ohlcv-1m",
        start="2024-01-01T00:00:00",
        end="2024-01-02T00:00:00",
    )
except DatabentoError as e:
    print(f"Databento error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 7. Performance Optimization

#### Streaming with Buffering

```python
def buffered_callback(messages):
    """Process multiple messages at once for better performance"""
    for message in messages:
        # Process individual message
        process_message(message)

live_client.subscribe(
    symbols=["ES.c.0"],
    schema="mbo",
    callback=buffered_callback,
    buffer_size=1000,  # Buffer 1000 messages before calling callback
)
```

#### Parallel Processing

```python
import concurrent.futures
from datetime import datetime, timedelta

def fetch_day_data(date):
    """Fetch data for a specific date"""
    start = date.strftime("%Y-%m-%dT00:00:00")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    
    return client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols="ES.c.0",
        schema="ohlcv-1m",
        start=start,
        end=end,
    )

# Fetch multiple days in parallel
dates = [datetime(2024, 1, i) for i in range(1, 8)]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(fetch_day_data, dates))
```

### 8. Integration with QuantTime

#### MBO Data Processing

```python
def process_mbo_data(dbn_store):
    """Process MBO data for QuantTime system"""
    df = dbn_store.to_df()
    
    # Filter for execution events
    executions = df[df['action'] == 'F'].copy()
    
    # Convert to tick format
    ticks = []
    for _, row in executions.iterrows():
        tick = {
            'ts': pd.to_datetime(row['ts_event'], unit='ns'),
            'price': row['price'],
            'size': row['size'],
            'side': row['side']
        }
        ticks.append(tick)
    
    return pd.DataFrame(ticks)

# Usage in QuantTime
mbo_data = client.timeseries.get_range(
    dataset="GLBX.MDP3",
    symbols="ES.c.0",
    schema="mbo",
    start="2024-01-01T00:00:00",
    end="2024-01-02T00:00:00",
)

ticks_df = process_mbo_data(mbo_data)
```

#### Live Data Integration

```python
class QuantTimeLiveProcessor:
    def __init__(self):
        self.order_book = {}
        self.ticks = []
    
    def on_mbo_message(self, message):
        """Process live MBO messages"""
        # Update order book
        self.update_order_book(message)
        
        # Generate ticks for execution events
        if message.action == 'F':
            tick = {
                'ts': pd.to_datetime(message.ts_event, unit='ns'),
                'price': message.price,
                'size': message.size,
                'side': message.side
            }
            self.ticks.append(tick)
    
    def update_order_book(self, message):
        """Update order book with MBO event"""
        price = message.price
        order_id = message.order_id
        size = message.size
        
        if message.action == 'A':  # Add
            if price not in self.order_book:
                self.order_book[price] = {}
            self.order_book[price][order_id] = size
        elif message.action in ['C', 'D']:  # Cancel/Delete
            if price in self.order_book and order_id in self.order_book[price]:
                del self.order_book[price][order_id]
                if not self.order_book[price]:
                    del self.order_book[price]
        elif message.action == 'F':  # Fill
            if price in self.order_book and order_id in self.order_book[price]:
                self.order_book[price][order_id] -= size
                if self.order_book[price][order_id] <= 0:
                    del self.order_book[price][order_id]
                    if not self.order_book[price]:
                        del self.order_book[price]

# Initialize live processor
processor = QuantTimeLiveProcessor()

# Start live streaming
with db.Live(key="your_api_key", dataset="GLBX.MDP3") as live:
    live.subscribe(
        symbols=["ES.c.0"],
        schema="mbo",
        callback=processor.on_mbo_message,
    )
```

### 9. Best Practices

#### Configuration Management

```python
import os
from dataclasses import dataclass

@dataclass
class DatabentoConfig:
    api_key: str
    dataset: str = "GLBX.MDP3"
    gateway: str = "bo1"
    timeout: int = 30
    
    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("DATABENTO_API_KEY"),
            dataset=os.getenv("DATABENTO_DATASET", "GLBX.MDP3"),
            gateway=os.getenv("DATABENTO_GATEWAY", "bo1"),
            timeout=int(os.getenv("DATABENTO_TIMEOUT", "30")),
        )

# Usage
config = DatabentoConfig.from_env()
client = db.Historical(
    key=config.api_key,
    gateway=config.gateway,
    timeout=config.timeout,
)
```

#### Data Validation

```python
def validate_mbo_data(df):
    """Validate MBO data quality"""
    required_columns = ['ts_event', 'action', 'price', 'size', 'side', 'order_id']
    
    # Check required columns
    missing_columns = set(required_columns) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # Check data types
    if not pd.api.types.is_numeric_dtype(df['price']):
        raise ValueError("Price column must be numeric")
    
    if not pd.api.types.is_numeric_dtype(df['size']):
        raise ValueError("Size column must be numeric")
    
    # Check for valid actions
    valid_actions = ['A', 'C', 'D', 'F']  # Add, Cancel, Delete, Fill
    invalid_actions = set(df['action'].unique()) - set(valid_actions)
    if invalid_actions:
        raise ValueError(f"Invalid actions found: {invalid_actions}")
    
    return True
```

#### Memory Management

```python
def process_large_dataset(dataset, start, end, chunk_size="1D"):
    """Process large datasets in chunks to manage memory"""
    current_start = pd.Timestamp(start)
    end_time = pd.Timestamp(end)
    
    while current_start < end_time:
        current_end = min(current_start + pd.Timedelta(chunk_size), end_time)
        
        # Fetch chunk
        data = client.timeseries.get_range(
            dataset=dataset,
            symbols="ES.c.0",
            schema="mbo",
            start=current_start.isoformat(),
            end=current_end.isoformat(),
        )
        
        # Process chunk
        df = data.to_df()
        process_chunk(df)
        
        # Move to next chunk
        current_start = current_end
        
        # Optional: Add delay to avoid rate limiting
        time.sleep(0.1)
```

### 10. Troubleshooting

#### Common Issues

1. **Authentication Errors**
   ```python
   # Check API key
   print(f"API key length: {len(config.api_key)}")
   # Ensure key is valid and has proper permissions
   ```

2. **Symbol Resolution Issues**
   ```python
   # Check available symbols
   symbols = client.symbology.list_symbols("GLBX.MDP3")
   print(f"Available symbols: {symbols[:10]}")  # First 10 symbols
   ```

3. **Rate Limiting**
   ```python
   # Implement exponential backoff
   import time
   import random
   
   def fetch_with_retry(client, **kwargs):
       max_retries = 3
       for attempt in range(max_retries):
           try:
               return client.timeseries.get_range(**kwargs)
           except DatabentoError as e:
               if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                   wait_time = (2 ** attempt) + random.uniform(0, 1)
                   time.sleep(wait_time)
                   continue
               raise
   ```

This guide provides a comprehensive overview of the Databento Python library and its integration with the QuantTime system. The library offers powerful tools for both historical data analysis and live trading applications.
