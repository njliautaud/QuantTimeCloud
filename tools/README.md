# QuantTime Tools

This directory contains utility scripts for managing and organizing the QuantTime project.

## Scripts

### Data Management
- `organize_data.py` - Comprehensive data organization script
- `organize_data_simple.py` - Simple data organization script
- `update_data_paths.py` - Updates data paths throughout the project
- `unzip_databento_data.py` - Unzips Databento data files

### Testing
- `test_data_management.py` - Tests the data management system
- `test_databento_unzip.py` - Tests Databento unzipping functionality
- `test_mbo_pipeline.py` - Tests MBO data pipeline

## Usage

Run any script from the project root directory:

```bash
python tools/script_name.py
```

## Data Organization

All data is now organized in the `data/` directory:

- `data/es_futures/mbo/` - ES futures MBO data
- `data/es_futures/mbp/` - ES futures MBP data  
- `data/es_futures/trades/` - ES futures trade data
- `data/es_futures/ohlcv/` - ES futures OHLCV data
- `data/es_futures/live_streams/` - Live streaming data
- `data/test_data/` - Test data files
- `data/archive/` - Archived files
- `data/backup/` - Backup files
