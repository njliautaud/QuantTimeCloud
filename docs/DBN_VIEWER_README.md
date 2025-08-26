# Data File Viewer

This directory contains a comprehensive data file viewer for both Databento DBN files and CSV files using the official Databento Python library and pandas.

## Script

### `quick_view_dbn.py` - Enhanced Data Viewer
A comprehensive tool for viewing DBN and CSV files with both command-line and GUI interfaces.

**Features:**
- **Multi-format Support**: `.dbn`, `.dbn.zst`, `.dbn.gz`, `.csv` files
- **File selection dialog** with support for all supported formats
- **Multiple View Formats**: Data Table, JSON View, CSV View, File Info
- **Export Capabilities**: Export to JSON or CSV files
- **Official Databento API**: Uses `DBNStore.from_file()` and `to_df()` methods for DBN files
- **Pandas Integration**: Uses `pd.read_csv()` for CSV files
- **Fast Loading**: Optimized for quick inspection (default 10 rows)
- **Complete MBO Data**: Full Level 3 order book and tick-by-tick data for DBN files
- **Structured Data**: Tabular data analysis for CSV files
- **Interactive GUI**: Tabbed interface with sorting and scrolling

**Features:**
- Command-line interface
- File metadata display
- Data summary with column information
- Sample data preview
- Configurable row limit

**Usage:**
```bash
# Opens file selection dialog with GUI viewer (recommended)
python quick_view_dbn.py

# Command line only (no GUI)
python quick_view_dbn.py --no-gui

# With custom row limit
python quick_view_dbn.py --max-rows 100

# Direct file path (still supported)
python quick_view_dbn.py "path/to/your/file.dbn.zst"
python quick_view_dbn.py "path/to/your/file.csv"

# Direct file path with custom row limit
python quick_view_dbn.py "path/to/your/file.dbn.zst" --max-rows 50
python quick_view_dbn.py "path/to/your/file.csv" --max-rows 50

# Examples
python quick_view_dbn.py  # Opens file dialog, shows 10 rows by default with GUI
python quick_view_dbn.py --no-gui  # Command line only
python quick_view_dbn.py "data/es_futures/mbo/glbx-mdp3-20250803.mbo.dbn.zst"
python quick_view_dbn.py "data/es_futures/mbo/glbx-mdp3-20250813.mbo.dbn.zst" --max-rows 20
python quick_view_dbn.py "data/your_data.csv" --max-rows 100
```

**Command Line Options:**
- `file_path`: Path to the data file (optional - opens file dialog if not provided)
- `--max-rows`: Maximum number of rows to display (default: 10)
- `--no-gui`: Disable GUI viewer (command line only)
- `--help`: Show help message

**Supported File Formats:**
- **DBN files**: `.dbn`, `.dbn.zst`, `.dbn.gz` (Databento Market By Order data)
- **CSV files**: `.csv` (Comma-separated values data)

**GUI Features:**
- **Data Table Tab**: Interactive table with sorting and scrolling
- **JSON View Tab**: Formatted JSON display of the data
- **CSV View Tab**: CSV format display
- **File Info Tab**: Complete file metadata and MBO data explanation
- **Export Buttons**: Save data as JSON or CSV files

## Supported Data Formats

### **DBN Format - Complete Market Microstructure**

The viewer displays **MBO (Market By Order)** data, which provides **complete market microstructure** for high-frequency trading and analysis. This format contains **ALL** tick-by-tick price data, **ALL** orderflow, and **FULL** Level 3 order book data.

### **CSV Format - Structured Tabular Data**

The viewer also supports **CSV (Comma-Separated Values)** files, which provide **structured tabular data** for general data analysis. This format is widely supported and can contain any type of structured data.

### **📊 Complete Data Coverage:**

**1. TICK-BY-TICK PRICE DATA:**
- **Every price change** is recorded as a separate tick
- **`ts_event`**: Exact timestamp of each tick (nanosecond precision)
- **`price`**: Price at that exact moment
- **Real-time price evolution** with complete historical trail

**2. COMPLETE ORDERFLOW:**
- **`action`**: Order action type
  - `A` = Add (new order placed)
  - `C` = Change (order modified)
  - `F` = Fill (order executed/traded)
  - `M` = Modify (order modification)
  - `R` = Remove (order cancelled)
  - `T` = Trade (execution)
- **`side`**: Order side
  - `A` = Ask (sell order)
  - `B` = Bid (buy order)
  - `N` = Neutral
- **`size`**: Order size at that tick
- **`order_id`**: Unique identifier for each order

**3. FULL LEVEL 3 ORDER BOOK:**
- **Every order book change** is recorded
- **Bid/Ask orders** tracked separately
- **Order modifications and cancellations** captured
- **Complete order book state** at each tick
- **Market depth** at every price level

**4. SEQUENCE INFORMATION:**
- **`sequence`**: Order of events (for reconstruction)
- **`ts_in_delta`**: Input timestamp delta
- **`flags`**: Order flags and metadata
- **`channel_id`**: Data channel identifier

### **🔍 Data Columns:**

| Column | Description | Data Type |
|--------|-------------|-----------|
| `ts_event` | Timestamp of the event (UTC) | datetime64[ns, UTC] |
| `rtype` | Record type | uint8 |
| `publisher_id` | Publisher identifier | uint16 |
| `instrument_id` | Instrument identifier | uint32 |
| `action` | Order action (A/C/F/M/R/T) | object |
| `side` | Order side (A/B/N) | object |
| `price` | Order price | float64 |
| `size` | Order size | uint32 |
| `channel_id` | Channel identifier | uint8 |
| `order_id` | Order identifier | uint64 |
| `flags` | Order flags | uint8 |
| `ts_in_delta` | Input timestamp delta | int32 |
| `sequence` | Sequence number | uint32 |
| `symbol` | Symbol name | object |

### **🚀 Why This Format Provides Complete Data:**

**✅ TICK-BY-TICK PRICE DATA:**
- Every price movement is captured
- No gaps in price history
- Nanosecond precision timestamps
- Complete price evolution trail

**✅ ALL ORDERFLOW:**
- Every order placed, modified, or cancelled
- Complete order lifecycle tracking
- Trade executions with exact timing
- Order book dynamics

**✅ FULL LEVEL 3 ORDER BOOK:**
- Complete market depth at every tick
- All price levels with sizes
- Order book state reconstruction possible
- Market microstructure analysis

**✅ SEQUENCE INTEGRITY:**
- Events in correct chronological order
- No missing data points
- Complete market picture
- High-frequency trading ready

### **📊 CSV Data Format - Structured Analysis:**

**✅ STRUCTURED DATA:**
- Data organized in rows and columns
- Each row represents a record
- Each column represents a field
- Flexible format for various data types

**✅ DATA TYPES:**
- Automatically detected by pandas
- Supports text, numbers, dates, and more
- Intelligent type inference
- Handles missing values gracefully

**✅ COMPATIBILITY:**
- Widely supported format
- Easy to import/export
- Works with most data analysis tools
- Standard format for data exchange

**✅ FEATURES:**
- Fast loading with pandas
- Memory efficient
- Supports large datasets
- Easy to process and analyze

## Reference Implementation

The viewer uses the **official Databento Python library** and follows the same protocol as the main QuantTime project:

### **🔗 Official Databento API Usage:**

**File Loading:**
```python
# Reference: databento-python-main/examples/historical_timeseries_from_file.py
dbn_store = DBNStore.from_file(file_path)
```

**DataFrame Conversion:**
```python
# Reference: databento-python-main/examples/historical_timeseries_to_df.py
df = dbn_store.to_df(
    price_type=PriceType.FLOAT,
    pretty_ts=True,
    map_symbols=True
)
```

### **🔄 Project Integration:**

The main QuantTime project uses **identical** data loading protocols:

**`quanttime/adapter/databento_loader.py`:**
- Uses `DBNStore.from_file()` for local DBN files
- Uses `Historical` client for live data
- Uses `to_df()` with same parameters
- Follows official Databento patterns

**Training and Analysis:**
- All ML models use the same data format
- All backtesting uses identical data loading
- All charting uses the same DataFrame structure
- Complete consistency across the entire project

### **📚 Official References:**
- **Reference**: `databento-python-main/examples/historical_timeseries_from_file.py` - File loading patterns
- **Reference**: `databento-python-main/examples/historical_timeseries_to_df.py` - DataFrame conversion patterns
- **Reference**: `databento-python-main/databento/__init__.py` - Schema definitions and data types

## Installation

Ensure the `databento-python-main` library is available in the project root directory:

```bash
# The library should already be installed in editable mode
pip install -e databento-python-main
```

## Example Output

```
Quick DBN File Viewer - Databento MBO Data Inspector
Reference: databento-python-main/examples/historical_timeseries_from_file.py
Reference: databento-python-main/examples/historical_timeseries_to_df.py

Loading DBN file: data/es_futures/mbo/glbx-mdp3-20250803.mbo.dbn.zst
============================================================
FILE INFORMATION:
  File: glbx-mdp3-20250803.mbo.dbn.zst
  Size: 6,062,375 bytes
  Schema: mbo
  Compression: zstd
  Dataset: GLBX.MDP3
  Start Time: 2025-08-03 00:00:00+00:00
  End Time: 2025-08-04 00:00:00+00:00
  Limit: None

DATA SUMMARY:
  Total Records: 346,384
  Columns: ['ts_event', 'rtype', 'publisher_id', 'instrument_id', 'action', 'side', 'price', 'size', 'channel_id', 'order_id', 'flags', 'ts_in_delta', 'sequence', 'symbol']
  Data Types:
    ts_event: datetime64[ns, UTC]
    rtype: uint8
    publisher_id: uint16
    instrument_id: uint32
    action: object
    side: object
    price: float64
    size: uint32
    channel_id: uint8
    order_id: uint64
    flags: uint8
    ts_in_delta: int32
    sequence: uint32
    symbol: object

  Actions: ['A', 'C', 'F', 'M', 'R', 'T']
  Sides: ['A', 'B', 'N']
  Symbols: ['ESH0', 'ESH6', 'ESH6-ESM6', 'ESH6-ESU6', 'ESH6-ESZ6', 'ESH7', 'ESH7-ESM7', 'ESH8', 'ESH9', 'ESM0', 'ESM6', 'ESM6-ESH7', 'ESM6-ESU6', 'ESM6-ESZ6', 'ESM7', 'ESM7-ESU7', 'ESM8', 'ESM9', 'ESU0', 'ESU5', 'ESU5-ESH6', 'ESU5-ESM6', 'ESU5-ESU6', 'ESU5-ESZ5', 'ESU6', 'ESU6-ESH7', 'ESU6-ESZ6', 'ESU7', 'ESU8', 'ESU9', 'ESZ5', 'ESZ5-ESH6', 'ESZ5-ESM6', 'ESZ5-ESU6', 'ESZ5-ESZ6', 'ESZ6', 'ESZ6-ESH7', 'ESZ6-ESM7', 'ESZ7', 'ESZ8', 'ESZ9']

  Time Range: 2025-08-03 14:06:42.125108895+00:00 to 2025-08-03 23:59:59.963280499+00:00

SAMPLE DATA (first 5 rows):
------------------------------------------------------------
                           ts_event  rtype  publisher_id  instrument_id action side  price  size  channel_id  order_id  flags  ts_in_delta  sequence symbol
2025-08-03 14:06:42.125108895+00:00    160             1       42140870      R    N    NaN     0         0         0      8            0         0   ESU6
2025-08-03 14:06:42.125108895+00:00    160             1       42004134      R    N    NaN     0         0         0      8            0         0   ESZ9
2025-08-03 14:06:42.125108895+00:00    160             1       42140856      R    N    NaN     0         0         0      8            0         0   ESM7
2025-08-03 14:06:42.125108895+00:00    160             1       42000746      R    N    NaN     0         0         0      8            0         0   ESH0
2025-08-03 14:06:42.125108895+00:00    160             1         294973      R    N    NaN     0         0         0      8            0         0   ESZ5

... and 346,379 more rows

============================================================
DBN file inspection complete!
```

## Troubleshooting

### Import Errors
If you encounter import errors, ensure:
1. The `databento-python-main` directory is in the project root
2. The library is installed in editable mode: `pip install -e databento-python-main`

### File Not Found
- Check that the file path is correct
- Ensure the file has a `.dbn`, `.dbn.zst`, or `.dbn.gz` extension
- Verify the file exists and is readable

### Memory Issues
For very large files, use the `--max-rows` parameter to limit the number of rows displayed:
```bash
python quick_view_dbn.py  # Default shows only 10 rows
python quick_view_dbn.py --max-rows 5  # Shows only 5 rows
python quick_view_dbn.py "large_file.dbn.zst" --max-rows 10
```
