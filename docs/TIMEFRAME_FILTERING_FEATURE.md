# Timeframe Filtering Feature

## Overview

The Timeframe Filtering feature allows you to train models and run backtests on specific market hours, focusing on high-volume periods and avoiding low-volume overnight sessions. This is particularly useful for options trading strategies that perform better during active market hours.

## Key Benefits

- **Focus on High-Volume Periods**: Train models on 9:00 AM - 4:30 PM EST when markets are most active
- **Avoid Low-Volume Noise**: Exclude overnight sessions with minimal liquidity
- **Model Labeling**: Automatically tag trained models with timeframe information
- **Consistent Backtesting**: Ensure backtests use the same timeframe as training
- **Multiple Timeframe Options**: Choose from various predefined timeframes

## Available Timeframes

### 1. Market Hours (9:00 AM - 4:30 PM EST) - **Default**
- **Best for**: Most trading strategies
- **Covers**: Regular market hours with highest volume
- **Tag**: `market_hours_0900-1630_EST`

### 2. 24 Hour Trading
- **Best for**: Cryptocurrency or futures strategies
- **Covers**: All hours including overnight sessions
- **Tag**: `market_hours_0000-2359_EST`

### 3. Extended Hours (8:00 AM - 5:00 PM EST)
- **Best for**: Pre-market and after-hours strategies
- **Covers**: Extended trading hours
- **Tag**: `market_hours_0800-1700_EST`

### 4. Core Hours (9:30 AM - 4:00 PM EST)
- **Best for**: Conservative strategies
- **Covers**: Core market hours only
- **Tag**: `market_hours_0930-1600_EST`

## Usage

### Training with Timeframe Filter

1. **Load your data** in the Streamlit dashboard
2. **Select timeframe** from the dropdown in the Training section
3. **Click "Train Model on This Data"**
4. **View filtering statistics** showing percentage of data used
5. **Model is automatically tagged** with timeframe information

```python
# Example: Training with market hours filter
from quanttime.utils.timeframe_filter import create_market_hours_filter

timeframe_filter = create_market_hours_filter()
filtered_data = timeframe_filter.filter_dataframe(your_data)
# Train model on filtered_data
```

### Backtesting with Timeframe Filter

1. **Select models** for backtesting
2. **Choose timeframe** from the Backtest Configuration section
3. **Set date range** and other parameters
4. **Click "Run Backtest"**
5. **View results** filtered to the selected timeframe

```python
# Example: Backtesting with timeframe filter
from quanttime.backtest.mbo_backtest_engine import run_mbo_backtest

results = run_mbo_backtest(
    data=your_data,
    strategy_func=your_strategy,
    timeframe_filter=timeframe_filter
)
```

## Model Metadata

Trained models automatically include timeframe information:

- **Model Name**: Includes timeframe tag (e.g., `my_model_market_hours_0900-1630_EST`)
- **Dataset Description**: Shows timeframe used for training
- **Model Cards**: Display timeframe badge in the dashboard
- **Database**: Timeframe stored in ModelRun table

## Implementation Details

### TimeframeFilter Class

```python
class TimeframeFilter:
    def __init__(self, 
                 start_time: time = time(9, 0),  # 9:00 AM EST
                 end_time: time = time(16, 30),  # 4:30 PM EST
                 timezone: str = "US/Eastern"):
        self.start_time = start_time
        self.end_time = end_time
        self.timezone = pytz.timezone(timezone)
        self.tag = f"market_hours_{start_time.hour:02d}{start_time.minute:02d}-{end_time.hour:02d}{end_time.minute:02d}_EST"
```

### Key Methods

- `filter_dataframe(df, timestamp_col='ts')`: Filter data to timeframe
- `get_filter_stats(df)`: Get filtering statistics
- `tag`: Unique identifier for the timeframe

### Data Processing

1. **Timestamp Conversion**: Converts timestamps to EST timezone
2. **Time Extraction**: Extracts time component from datetime
3. **Filtering**: Applies time-based mask to dataframe
4. **Statistics**: Calculates filtering impact

## Configuration

### Default Settings

- **Default Timeframe**: Market Hours (9:00 AM - 4:30 PM EST)
- **Timezone**: US/Eastern (EST/EDT)
- **Timestamp Column**: 'ts' (configurable)

### Custom Timeframes

```python
from datetime import time
from quanttime.utils.timeframe_filter import TimeframeFilter

# Custom timeframe: 10:00 AM - 3:00 PM EST
custom_filter = TimeframeFilter(
    start_time=time(10, 0),
    end_time=time(15, 0),
    timezone="US/Eastern"
)
```

## Performance Impact

### Data Reduction

- **Market Hours**: ~30-35% of total data (typical)
- **Extended Hours**: ~40-45% of total data
- **Core Hours**: ~25-30% of total data
- **24 Hour**: 100% of data

### Training Benefits

- **Faster Training**: Reduced data volume
- **Better Focus**: Models learn from high-volume periods
- **Reduced Noise**: Less overnight volatility impact
- **Consistent Performance**: Aligned with trading hours

## Best Practices

### 1. Match Training and Backtest Timeframes
Always use the same timeframe for training and backtesting to ensure consistency.

### 2. Consider Your Strategy
- **Day Trading**: Use Market Hours or Core Hours
- **Swing Trading**: Consider Extended Hours
- **Futures/Crypto**: May use 24 Hour

### 3. Monitor Filtering Statistics
Check the percentage of data retained to ensure sufficient training samples.

### 4. Document Timeframe Choices
Note why you chose a specific timeframe in your strategy documentation.

## Troubleshooting

### Common Issues

1. **No Data After Filtering**
   - Check if timestamps are in correct format
   - Verify timezone settings
   - Ensure data spans the selected timeframe

2. **Incorrect Filtering**
   - Verify timestamp column name
   - Check timezone conversion
   - Review start/end times

3. **Performance Issues**
   - Consider using smaller timeframes for large datasets
   - Monitor memory usage during filtering

### Debug Information

The system provides detailed logging:
```
INFO: Filtered 10000 rows to 3500 market hours rows (35.0% of original data)
INFO: Applying timeframe filter for backtest: market_hours_0900-1630_EST
```

## Future Enhancements

- **Custom Timeframes**: User-defined time ranges
- **Multiple Timezones**: Support for different markets
- **Dynamic Filtering**: Adaptive timeframes based on volume
- **Session Detection**: Automatic market session identification
- **Holiday Handling**: Exclude market holidays automatically
