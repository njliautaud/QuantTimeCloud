# Databento Binary Encoding (DBN) Specification

## Overview

Databento Binary Encoding (DBN) is an extremely fast message encoding and storage format for normalized market data. The DBN specification includes a simple, self-describing metadata header and a fixed set of struct definitions, which enforce a standardized way to normalize market data.

## Key Advantages

### End-to-End Solution
- **Single Format**: DBN can be used to store and transport normalized data across all components of a typical trading system
- **Multiple Use Cases**: File format for efficient storage, message encoding for fast real-time streaming, and in-memory representation for low latency systems
- **Consistency**: Ensures market data is immutable, lossless, and consistent as it passes between components

### Performance Benefits
- **Zero-Copy**: Data is structured the same way whether in-memory, on the wire, or on disk
- **Highly Compressible**: Strict fixed lengths and offsets enable high compression ratios with zstd and lz4
- **CPU Optimized**: Predictable layout allows highly-optimized sequential access patterns
- **Cache Friendly**: Most records fit into a single cache line

### Trading System Benefits
- **Same Code for Historical and Live**: Use identical event-driven trading platform code in backtest and production
- **Symbology Metadata**: Lightweight header provides metadata for interpreting market data
- **Normalization Format**: Adopts best practices from top-tier trading firms

## Layout Structure

### Version 1 Layout
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|             magic string = "DBN"              |  version = 1  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            length                             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                            dataset                            +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|             schema            |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                       start (UNIX nanos)                      |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                        end (UNIX nanos)                       |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                      limit (max records)                      |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |   stype_in    |   stype_out   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    ts_out     |                                               |
+-+-+-+-+-+-+-+-+                                               +
|                                                               |
+                 reserved (47 bytes of padding)                +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    schema_definition_length                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  schema_definition (variable)                 |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         symbols_count                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       symbols (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         partial_count                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       partial (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        not_found_count                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      not_found (variable)                     |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         mappings_count                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      mappings (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-end metadata; begin body--+-+-+-+-+-+-+-+-+-+
|                            records                            |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Version 2+ Layout
```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|             magic string = "DBN"              |    version    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                            length                             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                            dataset                            +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|             schema            |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                       start (UNIX nanos)                      |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                        end (UNIX nanos)                       |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               +
|                      limit (max records)                      |
+                               +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |   stype_in    |   stype_out   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    ts_out     |        symbol_cstr_len        |               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               |
|                                                               |
+                 reserved (53 bytes of padding)                +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    schema_definition_length                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  schema_definition (variable)                 |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         symbols_count                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       symbols (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         partial_count                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       partial (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        not_found_count                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      not_found (variable)                     |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         mappings_count                        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      mappings (variable)                      |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-end metadata; begin body--+-+-+-+-+-+-+-+-+-+
|                            records                            |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

## Metadata Fields

All fields are little-endian and appear in the following order:

| Field | Type | Description |
|-------|------|-------------|
| version | char[4] | "DBN" followed by the version of DBN the file is encoded in as a u8 |
| length | uint32_t | The length of the remaining metadata header, excluding version and length |
| dataset | char[16] | The dataset code (string identifier) |
| schema | uint16_t | The data record schema. u16::MAX indicates a potential mix of schemas |
| start | uint64_t | The start time of query range in UNIX epoch nanoseconds |
| end | uint64_t | The end time of query range in UNIX epoch nanoseconds. u64::MAX indicates no end time |
| limit | uint64_t | The maximum number of records to return. 0 indicates no limit |
| stype_in | uint8_t | The symbology type of input symbols. u8::MAX indicates a potential mix of types |
| stype_out | uint8_t | The symbology type of output symbols |
| ts_out | uint8_t | Whether each record has an appended gateway send timestamp |
| symbol_cstr_len | uint16_t | The number of bytes in fixed-length string symbols (Version 2+) |
| schema_definition_length | uint32_t | Number of bytes in the schema definition |
| schema_definition | uint8_t[schema_definition_length] | Self-describing schema (future implementation) |
| symbols_length | uint32_t | Number of symbols in the original query |
| symbols | char[symbols_length][symbol_cstr_len] | The symbols from the original query |
| partial_length | uint32_t | The number of symbols partially resolved |
| partial | char[partial_length][symbol_cstr_len] | The partially resolved symbols |
| not_found_length | uint32_t | The number of unresolved symbols |
| not_found | char[not_found_length][symbol_cstr_len] | The unresolved symbols |
| mappings_length | uint32_t | The number of symbols at least partially resolved |
| mappings | SymbolMapping[mappings_length] | The SymbolMappings, one for each resolved symbol |

### SymbolMapping Structure
```c
struct SymbolMapping {
    char raw_symbol[symbol_cstr_len];  // The symbol requested symbol stype_in
    uint32_t interval_length;          // The number of MappingIntervals in intervals
    MappingInterval intervals[interval_length];  // The MappingIntervals associated with raw_symbol
};
```

### MappingInterval Structure
```c
struct MappingInterval {
    uint32_t start_date;  // The start date of the interval, as a YYYYMMDD integer
    uint32_t end_date;    // The end date of the interval, as a YYYYMMDD integer
    char symbol[symbol_cstr_len];  // The symbol in stype_out for this interval
};
```

## Record Structure

All records begin with the same 16-byte RecordHeader:

```c
struct RecordHeader {
    uint8_t length;        // The length of the record in 32-bit words
    uint8_t rtype;         // The record type. Each schema corresponds with a single rtype value
    uint16_t publisher_id; // The publisher ID assigned by Databento
    uint32_t instrument_id; // The numeric instrument ID
    uint64_t ts_event;     // The event timestamp as nanoseconds since UNIX epoch
};
```

## Version History

### Version 2 Changes
- Sets version to 2
- Adds symbol_cstr_len field
- Rearranges padding
- Fixed-length strings now have symbol_cstr_len characters (71) instead of 22
- InstrumentDefMsg: raw_symbol now has symbol_cstr_len characters
- SymbolMappingMsg: stype_in_symbol and stype_out_symbol now have symbol_cstr_len characters
- ErrorMsg: Adds space for longer error messages, adds code and is_last fields
- SystemMsg: Adds space for longer messages, adds code field

### Version 3 Changes
- Added 8-byte alignment padding to the end of metadata
- Expanded quantity to 64 bits in StatMsg
- InstrumentDefMsg: Added strategy leg support with multiple new fields
- Expanded asset to 11 bytes
- Expanded raw_instrument_id to 64 bits
- Removed statistics-schema related fields
- Removed status-schema related field

## Comparison with Other Formats

| Feature | DBN | SBE | Parquet | Arrow |
|---------|-----|-----|---------|-------|
| Schema definition | Fixed schemas | XML | Thrift, Avro, Protobuf | Arrow object model |
| Layout | Sequential | Sequential | Column-oriented | Column-oriented |
| Zero copy | Yes | Yes | No | Limited support |
| Real-time messaging | Yes | Yes | No | No |
| File format | Yes | Yes | Yes | Through Feather |
| Metadata | Yes | No, user-defined | No, user-defined | No |
| Sequential read | Fastest | Fast | Moderate | Moderate |
| Sequential write | Fastest | Fast | Slowest | Moderate (Feather) |
| Compressed size | Small | Moderate | Smallest | Largest (Feather) |
| Transcoding to CSV | Yes | No | Through pandas | Yes |
| Transcoding to JSON | Yes | No | Through pandas | No |
| Mapping to pandas | Yes | No | Yes | Yes |
| Package size | 16.0k lines | 55.7k lines | 108.5k lines | 1.6M lines |
| Language support | Python, C++, Rust, C | C++, Java, C# | 11+ languages | 11+ languages |
| Use case | Market data (storage, replay, research, real-time messaging, normalization, OMS, EMS, GUIs) | Direct venue connectivity | Storage file format | Data exploration |

## When to Use DBN

### Use DBN When:
- Building a trading system that needs end-to-end data consistency
- Requiring high-performance market data processing
- Working with both historical and live data
- Needing zero-copy data handling
- Wanting to use the same code for backtesting and live trading

### Don't Use DBN When:
- Depending heavily on Apache ecosystem tools
- Only trading on one venue with direct connectivity
- Academic/toy projects with small amounts of historical data
- Supporting many teams with different trading styles and low-frequency data needs

## Implementation Notes

### Performance Characteristics
- **Speed**: 6.1 microseconds median internal latency
- **Throughput**: 19.1 million messages per second (C++ client library)
- **Storage**: 4 PB and over 30 trillion records stored internally
- **Daily Volume**: Billions of messages per day at 60 Gbps peak rates

### Integration
- All official Databento client libraries use DBN under the hood
- DBN is the default encoding for all Databento APIs
- Supports live data streaming, historical data streaming, and batch flat files
- Provides transcoders to CSV and JSON formats

### Best Practices
- Use DBN for all three use cases: file format, real-time messaging, and in-memory representation
- Leverage the zero-copy nature for maximum performance
- Take advantage of the self-describing metadata for symbology mappings
- Use the same code paths for historical and live data processing
