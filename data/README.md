# QuantTime Data Directory

This directory contains all organized data for the QuantTime project.

## Directory Structure

### ES Futures Data (`es_futures/`)
- **mbo/**: Market By Order data (GLBX MBO files)
- **mbp/**: Market By Price data (GLBX MBP files)
- **trades/**: Trade data (GLBX trades files)
- **ohlcv/**: OHLCV bar data (GLBX OHLCV files)
- **live_streams/**: Live streaming data

### Test Data (`test_data/`)
- Databento test files and other test data

### Archive (`archive/`)
- Old data files and unrelated files moved here for safekeeping

### Backup (`backup/`)
- Backup copies of original data files

## Usage

The QuantTime system automatically looks for data in this directory structure.
All configuration files have been updated to point to these locations.

## Organization

Data is organized by:
1. **Instrument Type**: ES futures, other instruments
2. **Data Schema**: MBO, MBP, trades, OHLCV
3. **Date**: Files are organized by date for easy access
4. **Type**: Production data vs test data vs archived data

## File Formats

- **DBN**: Databento binary format
- **ZST**: Zstandard compressed files
- **GZ**: Gzip compressed files
- **Parquet**: Processed data files
- **CSV**: Exported data files
