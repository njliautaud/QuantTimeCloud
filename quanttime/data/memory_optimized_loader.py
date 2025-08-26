"""
Memory-Optimized Data Loader for QuantTime ML Trading Suite.

This module implements memory-efficient data loading using:
- Memory mapping (numpy.memmap, h5py)
- Streaming data generators
- Mixed precision (float16/float32)
- Batching for training
- Out-of-core processing

Key Features:
- Memory mapping for large datasets
- Streaming data generators
- Mixed precision support
- Configurable batch sizes
- Automatic memory management
"""

import os
import logging
import gc
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator, Tuple, Union, TYPE_CHECKING
from datetime import datetime, timedelta
import warnings

import numpy as np
import pandas as pd
import h5py

# Required imports
from numba import jit

# Optional imports
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    warnings.warn("psutil not available - memory monitoring disabled")

# Memory optimization imports
try:
    import vaex
    VAEX_AVAILABLE = True
except ImportError:
    VAEX_AVAILABLE = False
    warnings.warn("vaex not available - some memory optimizations disabled")

try:
    import dask.dataframe as dd
    DASK_AVAILABLE = True
except ImportError:
    DASK_AVAILABLE = False
    warnings.warn("dask not available - some memory optimizations disabled")

logger = logging.getLogger(__name__)

# Forward references for type checking
if TYPE_CHECKING:
    import dask.dataframe as dd


class MemoryOptimizedLoader:
    """
    Memory-optimized data loader with memory mapping, batching, and mixed precision.
    
    Features:
    - Memory mapping for large datasets
    - Streaming data generators
    - Mixed precision support (float16/float32)
    - Configurable batch sizes
    - Automatic memory management
    - Out-of-core processing
    """
    
    def __init__(self, 
                 data_dir: str = "data",
                 max_memory_gb: float = 8.0,
                 batch_size: int = 10000,
                 use_mixed_precision: bool = True,
                 dtype_float: str = "float32"):
        """
        Initialize memory-optimized loader.
        
        Args:
            data_dir: Directory containing data files
            max_memory_gb: Maximum memory usage in GB
            batch_size: Default batch size for training
            use_mixed_precision: Use mixed precision (float16/float32)
            dtype_float: Default float dtype (float16, float32, float64)
        """
        self.data_dir = Path(data_dir)
        self.max_memory_gb = max_memory_gb
        self.max_memory_bytes = max_memory_gb * 1024**3
        self.batch_size = batch_size
        self.use_mixed_precision = use_mixed_precision
        self.dtype_float = dtype_float
        
        # Memory monitoring
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process()
        else:
            self.process = None
        
        # Create optimized data directory
        self.optimized_dir = self.data_dir / "optimized"
        self.optimized_dir.mkdir(exist_ok=True)
        
        logger.info(f"Memory-optimized loader initialized:")
        logger.info(f"  Max memory: {max_memory_gb} GB")
        logger.info(f"  Batch size: {batch_size:,}")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Float dtype: {dtype_float}")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        if not PSUTIL_AVAILABLE or self.process is None:
            return {
                'rss_gb': 0.0,
                'vms_gb': 0.0,
                'percent': 0.0,
                'available_gb': 0.0
            }
        
        memory_info = self.process.memory_info()
        return {
            'rss_gb': memory_info.rss / 1024**3,
            'vms_gb': memory_info.vms / 1024**3,
            'percent': self.process.memory_percent(),
            'available_gb': psutil.virtual_memory().available / 1024**3
        }
    
    def check_memory_limit(self) -> bool:
        """Check if current memory usage is within limits."""
        memory_usage = self.get_memory_usage()
        return memory_usage['rss_gb'] < self.max_memory_gb
    
    def force_garbage_collection(self):
        """Force garbage collection to free memory."""
        gc.collect()
        logger.debug("Forced garbage collection")
    
    def create_memory_mapped_array(self, 
                                 data: np.ndarray, 
                                 filename: str,
                                 dtype: Optional[str] = None) -> np.memmap:
        """
        Create a memory-mapped array for large datasets.
        
        Args:
            data: Input numpy array
            filename: Output filename
            dtype: Data type for memory mapping
            
        Returns:
            Memory-mapped array
        """
        if dtype is None:
            dtype = data.dtype
        
        # Optimize dtype for memory usage
        if self.use_mixed_precision:
            if dtype == np.float64:
                dtype = np.float32
            elif dtype == np.float32 and self.dtype_float == "float16":
                dtype = np.float16
        
        filepath = self.optimized_dir / f"{filename}.npy"
        
        # Save array to disk
        np.save(filepath, data.astype(dtype))
        
        # Create memory-mapped array
        mmap_array = np.load(filepath, mmap_mode='r')
        
        logger.info(f"Created memory-mapped array: {filepath}")
        logger.info(f"  Shape: {mmap_array.shape}")
        logger.info(f"  Dtype: {mmap_array.dtype}")
        logger.info(f"  Size: {mmap_array.nbytes / 1024**2:.1f} MB")
        
        return mmap_array
    
    def load_parquet_memory_mapped(self, 
                                  filepath: Union[str, Path],
                                  columns: Optional[List[str]] = None,
                                  use_dask: bool = True) -> Union[pd.DataFrame, 'dd.DataFrame']:
        """
        Load Parquet file with memory mapping.
        
        Args:
            filepath: Path to Parquet file
            columns: Columns to load (None = all)
            use_dask: Use Dask for out-of-core processing
            
        Returns:
            DataFrame (pandas or dask)
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Check file size
        file_size_gb = filepath.stat().st_size / 1024**3
        logger.info(f"Loading Parquet file: {filepath}")
        logger.info(f"  Size: {file_size_gb:.2f} GB")
        
        # Use Dask for large files or when requested
        if use_dask and DASK_AVAILABLE and file_size_gb > 1.0:
            logger.info("Using Dask for out-of-core processing")
            df = dd.read_parquet(filepath, columns=columns)
            
            # Optimize dtypes for memory usage
            if self.use_mixed_precision:
                df = self._optimize_dask_dtypes(df)
            
            return df
        else:
            # Use pandas with memory optimization
            logger.info("Using pandas with memory optimization")
            
            # Read in chunks if file is large
            if file_size_gb > 0.5:  # 500 MB threshold
                logger.info("Reading large file in chunks")
                chunks = []
                chunk_size = int(self.batch_size * 100)  # Larger chunks for reading
                
                for chunk in pd.read_parquet(filepath, columns=columns, chunksize=chunk_size):
                    # Optimize dtypes
                    chunk = self._optimize_pandas_dtypes(chunk)
                    chunks.append(chunk)
                    
                    # Check memory usage
                    if not self.check_memory_limit():
                        logger.warning("Memory limit reached, forcing garbage collection")
                        self.force_garbage_collection()
                
                df = pd.concat(chunks, ignore_index=True)
                del chunks
                self.force_garbage_collection()
            else:
                df = pd.read_parquet(filepath, columns=columns)
                df = self._optimize_pandas_dtypes(df)
            
            return df
    
    def _optimize_pandas_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize pandas DataFrame dtypes for memory usage."""
        if not self.use_mixed_precision:
            return df
        
        # Optimize float columns
        float_columns = df.select_dtypes(include=['float64']).columns
        for col in float_columns:
            if self.dtype_float == "float16":
                df[col] = df[col].astype(np.float16)
            else:
                df[col] = df[col].astype(np.float32)
        
        # Optimize int columns
        int_columns = df.select_dtypes(include=['int64']).columns
        for col in int_columns:
            col_min = df[col].min()
            col_max = df[col].max()
            
            if col_min >= np.iinfo(np.int8).min and col_max <= np.iinfo(np.int8).max:
                df[col] = df[col].astype(np.int8)
            elif col_min >= np.iinfo(np.int16).min and col_max <= np.iinfo(np.int16).max:
                df[col] = df[col].astype(np.int16)
            elif col_min >= np.iinfo(np.int32).min and col_max <= np.iinfo(np.int32).max:
                df[col] = df[col].astype(np.int32)
        
        return df
    
    def _optimize_dask_dtypes(self, df: 'dd.DataFrame') -> 'dd.DataFrame':
        """Optimize Dask DataFrame dtypes for memory usage."""
        if not self.use_mixed_precision:
            return df
        
        # Get dtypes
        dtypes = df.dtypes
        
        # Create optimized dtypes dict
        optimized_dtypes = {}
        for col, dtype in dtypes.items():
            if dtype == 'float64':
                if self.dtype_float == "float16":
                    optimized_dtypes[col] = 'float16'
                else:
                    optimized_dtypes[col] = 'float32'
            elif dtype == 'int64':
                optimized_dtypes[col] = 'int32'
        
        if optimized_dtypes:
            df = df.astype(optimized_dtypes)
        
        return df
    
    def create_data_generator(self, 
                            df: Union[pd.DataFrame, 'dd.DataFrame'],
                            batch_size: Optional[int] = None,
                            shuffle: bool = True,
                            infinite: bool = True) -> Iterator[pd.DataFrame]:
        """
        Create a memory-efficient data generator for training.
        
        Args:
            df: Input DataFrame
            batch_size: Batch size (uses default if None)
            shuffle: Shuffle data
            infinite: Generate infinite batches
            
        Yields:
            DataFrame batches
        """
        if batch_size is None:
            batch_size = self.batch_size
        
        if isinstance(df, dd.DataFrame):
            # Dask DataFrame generator
            return self._dask_data_generator(df, batch_size, shuffle, infinite)
        else:
            # Pandas DataFrame generator
            return self._pandas_data_generator(df, batch_size, shuffle, infinite)
    
    def _pandas_data_generator(self, 
                             df: pd.DataFrame,
                             batch_size: int,
                             shuffle: bool,
                             infinite: bool) -> Iterator[pd.DataFrame]:
        """Pandas DataFrame generator."""
        n_samples = len(df)
        indices = np.arange(n_samples)
        
        while True:
            if shuffle:
                np.random.shuffle(indices)
            
            for i in range(0, n_samples, batch_size):
                batch_indices = indices[i:i + batch_size]
                batch = df.iloc[batch_indices].copy()
                
                # Optimize batch dtypes
                batch = self._optimize_pandas_dtypes(batch)
                
                yield batch
            
            if not infinite:
                break
    
    def _dask_data_generator(self, 
                           df: 'dd.DataFrame',
                           batch_size: int,
                           shuffle: bool,
                           infinite: bool) -> Iterator[pd.DataFrame]:
        """Dask DataFrame generator."""
        # Repartition for optimal batch size
        df = df.repartition(partition_size=batch_size)
        
        while True:
            # Convert to pandas partitions
            for partition in df.map_partitions(lambda pdf: pdf).compute():
                if len(partition) == 0:
                    continue
                
                # Split partition into batches
                for i in range(0, len(partition), batch_size):
                    batch = partition.iloc[i:i + batch_size].copy()
                    
                    # Optimize batch dtypes
                    batch = self._optimize_pandas_dtypes(batch)
                    
                    yield batch
            
            if not infinite:
                break
    
    def load_databento_memory_mapped(self, 
                                   date_str: str,
                                   loader_func,
                                   chunk_size: int = 100000) -> np.memmap:
        """
        Load Databento data with memory mapping.
        
        Args:
            date_str: Date string
            loader_func: Function to load data
            chunk_size: Size of chunks to process
            
        Returns:
            Memory-mapped array
        """
        logger.info(f"Loading Databento data with memory mapping: {date_str}")
        
        # Load data in chunks
        chunks = []
        total_rows = 0
        
        try:
            # Load data using the provided loader function
            df = loader_func(date_str)
            
            if df is None or df.empty:
                logger.warning(f"No data found for {date_str}")
                return None
            
            # Convert to numpy array with optimized dtypes
            if self.use_mixed_precision:
                # Optimize dtypes before conversion
                df = self._optimize_pandas_dtypes(df)
            
            # Convert to numpy array
            data = df.to_numpy()
            
            # Create memory-mapped array
            filename = f"databento_{date_str}"
            mmap_array = self.create_memory_mapped_array(data, filename)
            
            logger.info(f"Successfully created memory-mapped array for {date_str}")
            logger.info(f"  Shape: {mmap_array.shape}")
            logger.info(f"  Memory usage: {self.get_memory_usage()['rss_gb']:.2f} GB")
            
            return mmap_array
            
        except Exception as e:
            logger.error(f"Failed to load Databento data with memory mapping: {e}")
            return None
    
    def create_h5_dataset(self, 
                         data: np.ndarray,
                         filename: str,
                         dataset_name: str = "data",
                         compression: str = "gzip",
                         compression_opts: int = 9) -> str:
        """
        Create HDF5 dataset for memory-efficient storage.
        
        Args:
            data: Input numpy array
            filename: Output filename
            dataset_name: Dataset name in HDF5 file
            compression: Compression algorithm
            compression_opts: Compression options
            
        Returns:
            Path to created HDF5 file
        """
        filepath = self.optimized_dir / f"{filename}.h5"
        
        with h5py.File(filepath, 'w') as f:
            # Create dataset with compression
            dset = f.create_dataset(
                dataset_name,
                data=data,
                compression=compression,
                compression_opts=compression_opts,
                chunks=True
            )
            
            logger.info(f"Created HDF5 dataset: {filepath}")
            logger.info(f"  Shape: {dset.shape}")
            logger.info(f"  Dtype: {dset.dtype}")
            logger.info(f"  Size: {dset.nbytes / 1024**2:.1f} MB")
            logger.info(f"  Compression: {compression}")
        
        return str(filepath)
    
    def load_h5_dataset(self, 
                       filepath: str,
                       dataset_name: str = "data",
                       start_idx: Optional[int] = None,
                       end_idx: Optional[int] = None) -> np.ndarray:
        """
        Load HDF5 dataset with memory mapping.
        
        Args:
            filepath: Path to HDF5 file
            dataset_name: Dataset name
            start_idx: Start index for slicing
            end_idx: End index for slicing
            
        Returns:
            Numpy array (memory-mapped)
        """
        with h5py.File(filepath, 'r') as f:
            dset = f[dataset_name]
            
            if start_idx is not None or end_idx is not None:
                data = dset[start_idx:end_idx]
            else:
                data = dset[:]
            
            logger.info(f"Loaded HDF5 dataset: {filepath}")
            logger.info(f"  Shape: {data.shape}")
            logger.info(f"  Memory usage: {self.get_memory_usage()['rss_gb']:.2f} GB")
            
            return data
    
    def batch_process_data(self, 
                          data: Union[np.ndarray, pd.DataFrame, 'dd.DataFrame'],
                          process_func,
                          batch_size: Optional[int] = None,
                          **kwargs) -> List[Any]:
        """
        Process data in batches to manage memory usage.
        
        Args:
            data: Input data
            process_func: Function to process each batch
            batch_size: Batch size
            **kwargs: Additional arguments for process_func
            
        Returns:
            List of processed results
        """
        if batch_size is None:
            batch_size = self.batch_size
        
        results = []
        
        if isinstance(data, np.ndarray):
            # Numpy array batching
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                result = process_func(batch, **kwargs)
                results.append(result)
                
                # Check memory usage
                if not self.check_memory_limit():
                    logger.warning("Memory limit reached during batch processing")
                    self.force_garbage_collection()
        
        elif isinstance(data, pd.DataFrame):
            # Pandas DataFrame batching
            for i in range(0, len(data), batch_size):
                batch = data.iloc[i:i + batch_size]
                result = process_func(batch, **kwargs)
                results.append(result)
                
                if not self.check_memory_limit():
                    logger.warning("Memory limit reached during batch processing")
                    self.force_garbage_collection()
        
        elif isinstance(data, dd.DataFrame):
            # Dask DataFrame batching
            for partition in data.map_partitions(process_func, **kwargs).compute():
                results.append(partition)
        
        logger.info(f"Batch processing completed: {len(results)} batches")
        return results

    def load_dbn_files_memory_optimized(self, 
                                       date_range: List[str],
                                       max_memory_gb: float = 12.0,
                                       progress_callback=None) -> pd.DataFrame:
        """
        Load DBN files with memory optimization and progress tracking.
        
        Args:
            date_range: List of date strings to load
            max_memory_gb: Maximum memory usage in GB
            progress_callback: Callback function for progress updates
            
        Returns:
            Combined DataFrame with all loaded data
        """
        import psutil
        import gc
        
        logger.info(f"Starting memory-optimized loading of {len(date_range)} dates")
        logger.info(f"Max memory: {max_memory_gb}GB")
        
        all_dataframes = []
        total_files = len(date_range)
        
        for file_idx, date_str in enumerate(date_range):
            try:
                # Update progress
                if progress_callback:
                    progress_callback(
                        task=f"Loading DBN file {file_idx + 1}/{total_files}",
                        current=file_idx + 1,
                        total=total_files,
                        subtask=f"Loading {date_str}",
                        subprogress=0.0
                    )
                
                logger.info(f"Processing file {file_idx + 1}/{total_files}: {date_str}")
                
                # Load DBN file
                dbn_store = self.load_date_data(date_str)
                if dbn_store is None:
                    logger.warning(f"Failed to load DBN file for {date_str}")
                    continue
                
                # Update progress - converting to DataFrame
                if progress_callback:
                    progress_callback(
                        task=f"Loading DBN file {file_idx + 1}/{total_files}",
                        current=file_idx + 1,
                        total=total_files,
                        subtask=f"Converting {date_str} to DataFrame",
                        subprogress=0.5
                    )
                
                # Convert entire DBNStore to DataFrame (DBNStore doesn't support slicing)
                try:
                    df = dbn_store.to_df(
                        price_type=PriceType.FLOAT,
                        pretty_ts=True,
                        map_symbols=True
                    )
                    
                    if df is not None and not df.empty:
                        df['source_date'] = date_str
                        all_dataframes.append(df)
                        
                        logger.info(f"Completed {date_str}: {len(df):,} records")
                        
                        # Memory management after each file
                        self._manage_memory(max_memory_gb)
                        
                        # Force garbage collection
                        gc.collect()
                    
                except Exception as e:
                    logger.error(f"Error converting {date_str} to DataFrame: {e}")
                    continue
                
                # Update progress - completed
                if progress_callback:
                    progress_callback(
                        task=f"Loading DBN file {file_idx + 1}/{total_files}",
                        current=file_idx + 1,
                        total=total_files,
                        subtask=f"Completed {date_str}",
                        subprogress=1.0
                    )
                
            except Exception as e:
                logger.error(f"Error processing file {date_str}: {e}")
                continue
        
        # Combine all dataframes
        if all_dataframes:
            logger.info("Combining all dataframes...")
            combined_df = pd.concat(all_dataframes, ignore_index=True)
            logger.info(f"Final combined dataset: {len(combined_df):,} records")
            
            # Clear individual dataframes to free memory
            all_dataframes.clear()
            gc.collect()
            
            return combined_df
        else:
            logger.warning("No data loaded")
            return pd.DataFrame()
    

    
    def _manage_memory(self, max_memory_gb: float):
        """
        Monitor and manage memory usage.
        
        Args:
            max_memory_gb: Maximum memory usage in GB
        """
        try:
            import psutil
            
            # Get current memory usage
            memory = psutil.virtual_memory()
            memory_gb = memory.used / (1024**3)
            
            if memory_gb > max_memory_gb:
                logger.warning(f"Memory usage high: {memory_gb:.1f}GB > {max_memory_gb}GB")
                
                # Force garbage collection
                import gc
                gc.collect()
                
                # Check memory again
                memory = psutil.virtual_memory()
                memory_gb = memory.used / (1024**3)
                logger.info(f"After GC: {memory_gb:.1f}GB")
                
        except ImportError:
            # psutil not available, skip memory management
            pass
        except Exception as e:
            logger.warning(f"Error in memory management: {e}")


# Memory optimization utilities
@jit(nopython=True)
def optimize_array_dtypes(arr: np.ndarray) -> np.ndarray:
    """
    Optimize array dtypes for memory usage using Numba JIT.
    
    Args:
        arr: Input numpy array
        
    Returns:
        Optimized array
    """
    # This is a placeholder for Numba-optimized dtype conversion
    # In practice, you'd implement specific optimizations based on data characteristics
    return arr


def get_optimal_batch_size(memory_gb: float, 
                          feature_dim: int,
                          dtype_size: int = 4) -> int:
    """
    Calculate optimal batch size based on available memory.
    
    Args:
        memory_gb: Available memory in GB
        feature_dim: Number of features
        dtype_size: Size of data type in bytes
        
    Returns:
        Optimal batch size
    """
    # Reserve 50% of memory for other operations
    available_memory = memory_gb * 0.5 * 1024**3  # Convert to bytes
    
    # Calculate batch size
    batch_size = int(available_memory / (feature_dim * dtype_size))
    
    # Ensure reasonable bounds
    batch_size = max(100, min(batch_size, 50000))
    
    return batch_size


def monitor_memory_usage(func):
    """Decorator to monitor memory usage of functions."""
    def wrapper(*args, **kwargs):
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024**3
            
            result = func(*args, **kwargs)
            
            end_memory = process.memory_info().rss / 1024**3
            memory_diff = end_memory - start_memory
            
            logger.info(f"{func.__name__} memory usage: {memory_diff:+.2f} GB")
        else:
            result = func(*args, **kwargs)
            logger.info(f"{func.__name__} executed (memory monitoring disabled)")
        
        return result
    
    return wrapper
