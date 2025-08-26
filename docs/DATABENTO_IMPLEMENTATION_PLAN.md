# Databento Implementation Plan for QuantTime

## Overview

This document outlines the comprehensive implementation plan for integrating Databento's official Python library and DBN specification into the QuantTime system. The goal is to leverage Databento's best practices and official tools for optimal performance and reliability.

## Current State Analysis

### What We Have
- ✅ Basic MBO data loading from `.dbn.zst` files
- ✅ Symbol mapping and front-month contract selection
- ✅ Tick data conversion from MBO events
- ✅ Basic charting with TradingView integration
- ✅ Streamlit dashboard interface

### What We Need to Improve
- 🔄 Replace manual DBN parsing with official Databento library
- 🔄 Implement proper live data streaming
- 🔄 Add comprehensive error handling and validation
- 🔄 Optimize performance with zero-copy operations
- 🔄 Add proper symbology resolution
- 🔄 Implement data compression and storage optimization

## Implementation Phases

### Phase 1: Core Library Integration (Priority: HIGH)

#### 1.1 Replace Manual DBN Parsing
**Current Issue**: Using manual parsing instead of official library
**Solution**: Integrate `databento.read_dbn()` and `DBNStore` classes

**Files to Modify**:
- `quanttime/adapter/databento_mbo.py`
- `quanttime/runtime/hist_service.py`

**Implementation**:
```python
# Replace manual parsing with official library
import databento as db

def read_mbo_file_official(self, date: str, symbol_ids: Optional[List[int]] = None) -> pd.DataFrame:
    """Read MBO data using official Databento library."""
    filepath = self._find_dbn_file(date)
    if not filepath:
        return pd.DataFrame()
    
    try:
        # Use official library
        dbn_store = db.read_dbn(filepath)
        df = dbn_store.to_df()
        
        # Filter by symbol if specified
        if symbol_ids and not df.empty:
            df = df[df['instrument_id'].isin(symbol_ids)]
        
        return df
    except Exception as e:
        logger.error(f"Failed to read with official library: {e}")
        return pd.DataFrame()
```

#### 1.2 Add Official Client Integration
**Implementation**:
```python
class DatabentoClient:
    """Official Databento client wrapper for QuantTime."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DATABENTO_API_KEY")
        self.historical_client = None
        self.live_client = None
        
        if self.api_key:
            self.historical_client = db.Historical(key=self.api_key)
    
    def get_historical_data(self, dataset: str, symbols: str, 
                          start: str, end: str, schema: str = "mbo"):
        """Get historical data using official client."""
        if not self.historical_client:
            raise ValueError("Historical client not initialized. Set DATABENTO_API_KEY.")
        
        return self.historical_client.timeseries.get_range(
            dataset=dataset,
            symbols=symbols,
            stype_in="continuous",
            start=start,
            end=end,
            schema=schema,
        )
```

### Phase 2: Live Data Streaming (Priority: HIGH)

#### 2.1 Live MBO Streaming
**Implementation**:
```python
class QuantTimeLiveStreamer:
    """Live data streaming for QuantTime."""
    
    def __init__(self, api_key: str, dataset: str = "GLBX.MDP3"):
        self.api_key = api_key
        self.dataset = dataset
        self.live_client = None
        self.order_book = {}
        self.ticks_buffer = []
        self.callbacks = []
    
    def start_streaming(self, symbols: List[str], schema: str = "mbo"):
        """Start live streaming."""
        self.live_client = db.Live(
            key=self.api_key,
            dataset=self.dataset,
        )
        
        self.live_client.subscribe(
            symbols=symbols,
            schema=schema,
            callback=self._on_message,
            buffer_size=1000,  # Buffer for performance
        )
    
    def _on_message(self, messages):
        """Process incoming messages."""
        for message in messages:
            # Update order book
            self._update_order_book(message)
            
            # Generate ticks for executions
            if message.action == 'F':
                tick = self._create_tick_from_message(message)
                self.ticks_buffer.append(tick)
            
            # Notify callbacks
            for callback in self.callbacks:
                callback(message)
    
    def _update_order_book(self, message):
        """Update order book with MBO event."""
        # Implementation for order book reconstruction
        pass
```

#### 2.2 Real-time Chart Updates
**Implementation**:
```python
class RealTimeChartUpdater:
    """Update charts with real-time data."""
    
    def __init__(self, chart_component):
        self.chart_component = chart_component
        self.ticks_buffer = []
        self.update_interval = 1.0  # seconds
    
    def on_tick(self, tick):
        """Handle new tick data."""
        self.ticks_buffer.append(tick)
        
        # Update chart periodically
        if len(self.ticks_buffer) >= 100:  # Update every 100 ticks
            self._update_chart()
    
    def _update_chart(self):
        """Update the chart with new data."""
        if self.ticks_buffer:
            new_data = pd.DataFrame(self.ticks_buffer)
            self.chart_component.add_data(new_data)
            self.ticks_buffer.clear()
```

### Phase 3: Data Validation and Quality (Priority: MEDIUM)

#### 3.1 Comprehensive Data Validation
**Implementation**:
```python
class DatabentoDataValidator:
    """Validate Databento data quality."""
    
    @staticmethod
    def validate_mbo_data(df: pd.DataFrame) -> Dict[str, Any]:
        """Validate MBO data quality."""
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        # Check required columns
        required_columns = ['ts_event', 'action', 'price', 'size', 'side', 'order_id']
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            validation_results['is_valid'] = False
            validation_results['errors'].append(f"Missing columns: {missing_columns}")
        
        # Check data types
        if not df.empty:
            if not pd.api.types.is_numeric_dtype(df['price']):
                validation_results['is_valid'] = False
                validation_results['errors'].append("Price column must be numeric")
            
            if not pd.api.types.is_numeric_dtype(df['size']):
                validation_results['is_valid'] = False
                validation_results['errors'].append("Size column must be numeric")
        
        # Check for valid actions
        valid_actions = ['A', 'C', 'D', 'F']  # Add, Cancel, Delete, Fill
        if not df.empty:
            invalid_actions = set(df['action'].unique()) - set(valid_actions)
            if invalid_actions:
                validation_results['warnings'].append(f"Invalid actions: {invalid_actions}")
        
        # Generate statistics
        if not df.empty:
            validation_results['statistics'] = {
                'total_events': len(df),
                'unique_actions': df['action'].value_counts().to_dict(),
                'price_range': {'min': float(df['price'].min()), 'max': float(df['price'].max())},
                'time_range': {'start': df['ts_event'].min(), 'end': df['ts_event'].max()},
                'unique_orders': df['order_id'].nunique(),
                'total_volume': int(df['size'].sum())
            }
        
        return validation_results
```

#### 3.2 Data Quality Monitoring
**Implementation**:
```python
class DataQualityMonitor:
    """Monitor data quality in real-time."""
    
    def __init__(self):
        self.quality_metrics = {}
        self.alert_thresholds = {
            'missing_data_threshold': 0.1,  # 10% missing data
            'price_anomaly_threshold': 3.0,  # 3 standard deviations
            'volume_anomaly_threshold': 5.0,  # 5 standard deviations
        }
    
    def monitor_stream_quality(self, messages: List) -> Dict[str, Any]:
        """Monitor quality of streaming data."""
        if not messages:
            return {'status': 'no_data'}
        
        # Calculate quality metrics
        metrics = {
            'message_count': len(messages),
            'execution_rate': sum(1 for m in messages if m.action == 'F') / len(messages),
            'avg_price': np.mean([m.price for m in messages if hasattr(m, 'price')]),
            'avg_size': np.mean([m.size for m in messages if hasattr(m, 'size')]),
        }
        
        # Check for anomalies
        alerts = []
        if metrics['execution_rate'] < 0.1:  # Less than 10% executions
            alerts.append('Low execution rate detected')
        
        self.quality_metrics = metrics
        return {'metrics': metrics, 'alerts': alerts}
```

### Phase 4: Performance Optimization (Priority: MEDIUM)

#### 4.1 Zero-Copy Operations
**Implementation**:
```python
class ZeroCopyProcessor:
    """Process data with zero-copy operations."""
    
    def __init__(self):
        self.memory_pool = {}
    
    def process_dbn_store(self, dbn_store: db.DBNStore) -> pd.DataFrame:
        """Process DBN store with minimal copying."""
        # Use DBN store's native DataFrame conversion
        df = dbn_store.to_df()
        
        # Apply filters without copying when possible
        if 'instrument_id' in df.columns:
            # Use boolean indexing for zero-copy filtering
            mask = df['instrument_id'].isin(self.target_instruments)
            df = df[mask]
        
        return df
    
    def batch_process(self, dbn_files: List[str]) -> pd.DataFrame:
        """Process multiple DBN files efficiently."""
        dfs = []
        for file_path in dbn_files:
            dbn_store = db.read_dbn(file_path)
            df = self.process_dbn_store(dbn_store)
            dfs.append(df)
        
        # Concatenate efficiently
        return pd.concat(dfs, ignore_index=True, copy=False)
```

#### 4.2 Memory Management
**Implementation**:
```python
class MemoryEfficientProcessor:
    """Process large datasets with memory efficiency."""
    
    def __init__(self, max_memory_gb: float = 8.0):
        self.max_memory_gb = max_memory_gb
        self.chunk_size = self._calculate_chunk_size()
    
    def _calculate_chunk_size(self) -> int:
        """Calculate optimal chunk size based on available memory."""
        # Estimate memory usage per record (rough estimate)
        bytes_per_record = 100  # Approximate
        max_records = int((self.max_memory_gb * 1e9) / bytes_per_record)
        return max_records
    
    def process_large_dataset(self, dataset: str, start: str, end: str) -> Iterator[pd.DataFrame]:
        """Process large dataset in chunks."""
        current_start = pd.Timestamp(start)
        end_time = pd.Timestamp(end)
        
        while current_start < end_time:
            current_end = min(current_start + pd.Timedelta(hours=1), end_time)
            
            # Fetch chunk
            data = self.client.timeseries.get_range(
                dataset=dataset,
                symbols="ES.c.0",
                schema="mbo",
                start=current_start.isoformat(),
                end=current_end.isoformat(),
            )
            
            # Process chunk
            df = data.to_df()
            yield df
            
            # Move to next chunk
            current_start = current_end
            
            # Optional: Add delay to avoid rate limiting
            time.sleep(0.1)
```

### Phase 5: Advanced Features (Priority: LOW)

#### 5.1 Symbology Resolution
**Implementation**:
```python
class SymbologyResolver:
    """Resolve symbols using Databento's symbology service."""
    
    def __init__(self, client: db.Historical):
        self.client = client
    
    def resolve_symbols(self, symbols: List[str], 
                       stype_in: str = "continuous",
                       stype_out: str = "instrument_id") -> Dict[str, int]:
        """Resolve symbols to instrument IDs."""
        try:
            mappings = self.client.symbology.resolve(
                dataset="GLBX.MDP3",
                symbols=symbols,
                stype_in=stype_in,
                stype_out=stype_out,
            )
            
            # Convert to dictionary
            symbol_map = {}
            for mapping in mappings:
                for interval in mapping.intervals:
                    symbol_map[mapping.raw_symbol] = int(interval.symbol)
            
            return symbol_map
        except Exception as e:
            logger.error(f"Failed to resolve symbols: {e}")
            return {}
    
    def get_available_symbols(self, dataset: str = "GLBX.MDP3") -> List[str]:
        """Get list of available symbols."""
        try:
            return self.client.symbology.list_symbols(dataset)
        except Exception as e:
            logger.error(f"Failed to get symbols: {e}")
            return []
```

#### 5.2 Data Compression and Storage
**Implementation**:
```python
class CompressedDataManager:
    """Manage compressed data storage."""
    
    def __init__(self, storage_dir: str = "data/compressed"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_compressed_data(self, df: pd.DataFrame, filename: str) -> str:
        """Save data in compressed format."""
        filepath = self.storage_dir / f"{filename}.parquet"
        
        # Save as compressed Parquet
        df.to_parquet(filepath, compression='zstd', index=False)
        
        return str(filepath)
    
    def load_compressed_data(self, filename: str) -> pd.DataFrame:
        """Load compressed data."""
        filepath = self.storage_dir / f"{filename}.parquet"
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        return pd.read_parquet(filepath)
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        files = list(self.storage_dir.glob("*.parquet"))
        
        total_size = sum(f.stat().st_size for f in files)
        file_count = len(files)
        
        return {
            'total_files': file_count,
            'total_size_gb': total_size / (1024**3),
            'avg_file_size_mb': (total_size / file_count) / (1024**2) if file_count > 0 else 0,
        }
```

## Implementation Timeline

### Week 1: Core Integration
- [ ] Replace manual DBN parsing with official library
- [ ] Implement DatabentoClient wrapper
- [ ] Update existing code to use official library
- [ ] Test with existing data files

### Week 2: Live Streaming
- [ ] Implement QuantTimeLiveStreamer
- [ ] Add real-time chart updates
- [ ] Integrate with Streamlit dashboard
- [ ] Test live data streaming

### Week 3: Data Quality
- [ ] Implement DatabentoDataValidator
- [ ] Add DataQualityMonitor
- [ ] Integrate validation into pipeline
- [ ] Add quality alerts to dashboard

### Week 4: Performance Optimization
- [ ] Implement ZeroCopyProcessor
- [ ] Add MemoryEfficientProcessor
- [ ] Optimize existing operations
- [ ] Performance testing and benchmarking

### Week 5: Advanced Features
- [ ] Implement SymbologyResolver
- [ ] Add CompressedDataManager
- [ ] Integrate advanced features
- [ ] Documentation and testing

## Success Metrics

### Performance Metrics
- **Data Loading Speed**: 50% improvement in MBO data loading
- **Memory Usage**: 30% reduction in memory consumption
- **Live Streaming Latency**: < 10ms end-to-end latency
- **Chart Update Frequency**: Real-time updates with < 100ms delay

### Quality Metrics
- **Data Validation**: 100% of data validated before processing
- **Error Detection**: 95% of data quality issues detected
- **Recovery Rate**: 99% successful recovery from data errors

### User Experience Metrics
- **Dashboard Responsiveness**: < 2 second load times
- **Chart Performance**: Smooth real-time updates
- **Error Handling**: Clear error messages and recovery options

## Risk Mitigation

### Technical Risks
- **API Rate Limits**: Implement exponential backoff and caching
- **Memory Issues**: Use chunked processing and memory monitoring
- **Data Quality**: Implement comprehensive validation and fallback mechanisms

### Operational Risks
- **API Key Management**: Secure storage and rotation procedures
- **Data Loss**: Implement backup and recovery procedures
- **Performance Degradation**: Monitor and optimize continuously

## Conclusion

This implementation plan provides a comprehensive roadmap for integrating Databento's official tools and best practices into the QuantTime system. The phased approach ensures minimal disruption while delivering significant improvements in performance, reliability, and functionality.

The plan prioritizes core functionality first, followed by advanced features, ensuring that the most critical improvements are delivered early while maintaining system stability throughout the implementation process.
