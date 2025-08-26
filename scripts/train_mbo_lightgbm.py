#!/usr/bin/env python3
"""
MBO LightGBM Training Script.

This script provides a comprehensive training pipeline for the MBO LightGBM model,
integrating data loading, feature engineering, model training, and evaluation.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from quanttime.models.mbo_lightgbm_model import MBOLightGBMModel, create_mbo_lightgbm_model
from quanttime.runtime.hist_service import load_databento_mbo_data, get_available_databento_dates
from quanttime.utils.memory_config import get_memory_config, get_optimal_training_config
from quanttime.utils.config import AppConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/mbo_training.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_training_data(start_date: str, 
                      end_date: str, 
                      symbol: str = "ES.FUT",
                      data_dir: str = "data/es_futures/mbo") -> pd.DataFrame:
    """
    Load MBO training data from Databento files.
    
    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        symbol: Trading symbol
        data_dir: Data directory path
        
    Returns:
        MBO DataFrame
    """
    logger.info(f"Loading MBO data: {symbol} from {start_date} to {end_date}")
    
    try:
        # Load MBO data
        mbo_df = load_databento_mbo_data(
            data_dir=data_dir,
            start_date=start_date,
            end_date=end_date,
            symbol=symbol
        )
        
        if mbo_df.empty:
            raise ValueError(f"No MBO data found for {symbol} from {start_date} to {end_date}")
        
        # Add datetime column if not present
        if 'datetime' not in mbo_df.columns and 'ts_event' in mbo_df.columns:
            mbo_df['datetime'] = pd.to_datetime(mbo_df['ts_event'], unit='ns')
        
        logger.info(f"Loaded {len(mbo_df)} MBO events")
        logger.info(f"Date range: {mbo_df['datetime'].min()} to {mbo_df['datetime'].max()}")
        logger.info(f"Columns: {list(mbo_df.columns)}")
        
        return mbo_df
        
    except Exception as e:
        logger.error(f"Failed to load MBO data: {e}")
        raise


def validate_mbo_data(mbo_df: pd.DataFrame) -> bool:
    """
    Validate MBO data quality.
    
    Args:
        mbo_df: MBO DataFrame
        
    Returns:
        True if data is valid
    """
    logger.info("Validating MBO data quality")
    
    # Check required columns
    required_columns = ['price', 'size', 'side', 'action']
    missing_columns = [col for col in required_columns if col not in mbo_df.columns]
    if missing_columns:
        logger.error(f"Missing required columns: {missing_columns}")
        return False
    
    # Check data types
    if not pd.api.types.is_numeric_dtype(mbo_df['price']):
        logger.error("Price column is not numeric")
        return False
    
    if not pd.api.types.is_numeric_dtype(mbo_df['size']):
        logger.error("Size column is not numeric")
        return False
    
    # Check for valid actions
    valid_actions = ['A', 'M', 'D', 'F']  # Add, Modify, Delete, Fill
    invalid_actions = mbo_df[~mbo_df['action'].isin(valid_actions)]['action'].unique()
    if len(invalid_actions) > 0:
        logger.warning(f"Found invalid actions: {invalid_actions}")
    
    # Check for valid sides
    valid_sides = ['B', 'S']  # Buy, Sell
    invalid_sides = mbo_df[~mbo_df['side'].isin(valid_sides)]['side'].unique()
    if len(invalid_sides) > 0:
        logger.warning(f"Found invalid sides: {invalid_sides}")
    
    # Check for reasonable price ranges
    price_stats = mbo_df['price'].describe()
    logger.info(f"Price statistics: {price_stats}")
    
    if price_stats['min'] <= 0:
        logger.error("Found non-positive prices")
        return False
    
    # Check for reasonable size ranges
    size_stats = mbo_df['size'].describe()
    logger.info(f"Size statistics: {size_stats}")
    
    if size_stats['min'] <= 0:
        logger.error("Found non-positive sizes")
        return False
    
    # Check for missing values
    missing_counts = mbo_df[required_columns].isnull().sum()
    if missing_counts.sum() > 0:
        logger.warning(f"Missing values: {missing_counts}")
    
    logger.info("MBO data validation completed successfully")
    return True


def create_model_config(orderbook_depth: int = 10,
                       sequence_length: int = 100,
                       feature_window: int = 50,
                       prediction_horizon: int = 10,
                       use_gpu: bool = True) -> Dict:
    """
    Create model configuration based on hardware and requirements.
    
    Args:
        orderbook_depth: Order book depth
        sequence_length: Sequence length for features
        feature_window: Feature window size
        prediction_horizon: Prediction horizon
        use_gpu: Use GPU acceleration
        
    Returns:
        Model configuration dictionary
    """
    # Get memory configuration
    memory_config = get_memory_config()
    
    # Get optimal training configuration
    training_config = get_optimal_training_config("lightgbm")
    
    model_config = {
        'orderbook_depth': orderbook_depth,
        'sequence_length': sequence_length,
        'feature_window': feature_window,
        'prediction_horizon': prediction_horizon,
        'use_gpu': use_gpu and memory_config.optimal_settings['use_gpu_optimization'],
        'use_mixed_precision': memory_config.optimal_settings['use_mixed_precision'],
        'max_gpu_memory_gb': memory_config.optimal_settings['max_gpu_memory_gb'],
        'max_ram_gb': memory_config.optimal_settings['max_ram_gb'],
        'batch_size': training_config['default_batch_size'],
        'model_params': training_config
    }
    
    logger.info(f"Model configuration:")
    for key, value in model_config.items():
        logger.info(f"  {key}: {value}")
    
    return model_config


def train_model(mbo_df: pd.DataFrame,
               model_config: Dict,
               validation_split: float = 0.2,
               test_split: float = 0.1,
               save_model: bool = True,
               model_path: str = "models/mbo_lightgbm_model.pkl") -> MBOLightGBMModel:
    """
    Train the MBO LightGBM model.
    
    Args:
        mbo_df: MBO training data
        model_config: Model configuration
        validation_split: Validation split ratio
        test_split: Test split ratio
        save_model: Whether to save the trained model
        model_path: Path to save the model
        
    Returns:
        Trained model
    """
    logger.info("Starting MBO LightGBM model training")
    
    try:
        # Create model
        model = create_mbo_lightgbm_model(
            orderbook_depth=model_config['orderbook_depth'],
            sequence_length=model_config['sequence_length'],
            feature_window=model_config['feature_window'],
            prediction_horizon=model_config['prediction_horizon'],
            use_gpu=model_config['use_gpu'],
            use_mixed_precision=model_config['use_mixed_precision']
        )
        
        # Train model
        training_results = model.train(
            mbo_df=mbo_df,
            validation_split=validation_split,
            test_split=test_split,
            random_state=42
        )
        
        # Log training results
        logger.info("Training completed successfully")
        logger.info(f"Training results: {training_results}")
        
        # Save model if requested
        if save_model:
            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            model.save_model(model_path)
            logger.info(f"Model saved to: {model_path}")
        
        return model
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


def evaluate_model(model: MBOLightGBMModel, test_data: pd.DataFrame) -> Dict:
    """
    Evaluate the trained model on test data.
    
    Args:
        model: Trained model
        test_data: Test data
        
    Returns:
        Evaluation results
    """
    logger.info("Evaluating model on test data")
    
    try:
        # Make predictions
        predictions = model.predict(test_data)
        
        # Get model summary
        model_summary = model.get_model_summary()
        
        logger.info("Model evaluation completed")
        logger.info(f"Model summary: {model_summary}")
        
        return model_summary
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description="Train MBO LightGBM Model")
    parser.add_argument("--start-date", type=str, required=True, help="Start date (YYYYMMDD)")
    parser.add_argument("--end-date", type=str, required=True, help="End date (YYYYMMDD)")
    parser.add_argument("--symbol", type=str, default="ES.FUT", help="Trading symbol")
    parser.add_argument("--data-dir", type=str, default="data/es_futures/mbo", help="Data directory")
    parser.add_argument("--orderbook-depth", type=int, default=10, help="Order book depth")
    parser.add_argument("--sequence-length", type=int, default=100, help="Sequence length")
    parser.add_argument("--feature-window", type=int, default=50, help="Feature window")
    parser.add_argument("--prediction-horizon", type=int, default=10, help="Prediction horizon")
    parser.add_argument("--use-gpu", action="store_true", help="Use GPU acceleration")
    parser.add_argument("--validation-split", type=float, default=0.2, help="Validation split")
    parser.add_argument("--test-split", type=float, default=0.1, help="Test split")
    parser.add_argument("--save-model", action="store_true", help="Save trained model")
    parser.add_argument("--model-path", type=str, default="models/mbo_lightgbm_model.pkl", help="Model save path")
    parser.add_argument("--optimize-hyperparams", action="store_true", help="Optimize hyperparameters")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of optimization trials")
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting MBO LightGBM training pipeline")
        logger.info(f"Arguments: {vars(args)}")
        
        # Load training data
        mbo_df = load_training_data(
            start_date=args.start_date,
            end_date=args.end_date,
            symbol=args.symbol,
            data_dir=args.data_dir
        )
        
        # Validate data
        if not validate_mbo_data(mbo_df):
            logger.error("Data validation failed")
            return 1
        
        # Create model configuration
        model_config = create_model_config(
            orderbook_depth=args.orderbook_depth,
            sequence_length=args.sequence_length,
            feature_window=args.feature_window,
            prediction_horizon=args.prediction_horizon,
            use_gpu=args.use_gpu
        )
        
        # Train model
        model = train_model(
            mbo_df=mbo_df,
            model_config=model_config,
            validation_split=args.validation_split,
            test_split=args.test_split,
            save_model=args.save_model,
            model_path=args.model_path
        )
        
        # Optimize hyperparameters if requested
        if args.optimize_hyperparams:
            logger.info("Starting hyperparameter optimization")
            optimization_results = model.optimize_hyperparameters(
                mbo_df=mbo_df,
                n_trials=args.n_trials
            )
            logger.info(f"Hyperparameter optimization completed: {optimization_results}")
            
            # Retrain with optimized parameters
            logger.info("Retraining model with optimized parameters")
            model = train_model(
                mbo_df=mbo_df,
                model_config=model_config,
                validation_split=args.validation_split,
                test_split=args.test_split,
                save_model=args.save_model,
                model_path=args.model_path
            )
        
        # Get final model summary
        model_summary = model.get_model_summary()
        logger.info("Training pipeline completed successfully")
        logger.info(f"Final model summary: {model_summary}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Training pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
