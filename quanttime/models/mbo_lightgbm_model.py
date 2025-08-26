"""
MBO LightGBM Model for Tick-by-Tick Trading.

This module implements a comprehensive LightGBM model specifically designed for
Market By Order (MBO) data with GPU optimization and real-time training capabilities.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
import pickle
import joblib
from pathlib import Path
import warnings

# GPU optimization imports
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    warnings.warn("lightgbm not available - GPU optimization disabled")

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler, RobustScaler

from ..features.mbo_feature_engineering import MBOFeatureEngineer, create_mbo_features_pipeline
from ..ml.gpu_optimized_training import GPUOptimizedLightGBMTrainer
from ..utils.memory_config import get_optimal_training_config
from ..models.base import ModelBase

logger = logging.getLogger(__name__)


class MBOLightGBMModel(ModelBase):
    """
    LightGBM model for MBO data with comprehensive feature engineering and GPU optimization.
    
    Features:
    - Real-time tick-by-tick processing
    - Comprehensive feature engineering
    - GPU-optimized training
    - Memory-efficient data handling
    - Model persistence and loading
    - Performance monitoring
    - Hyperparameter optimization
    """
    
    def __init__(self,
                 orderbook_depth: int = 10,
                 sequence_length: int = 100,
                 feature_window: int = 50,
                 prediction_horizon: int = 10,
                 use_gpu: bool = True,
                 use_mixed_precision: bool = True,
                 max_gpu_memory_gb: float = 7.0,
                 max_ram_gb: float = 14.0,
                 batch_size: int = 10000,
                 model_params: Optional[Dict] = None):
        """
        Initialize MBO LightGBM model.
        
        Args:
            orderbook_depth: Number of order book levels to maintain
            sequence_length: Length of price/volume sequences
            feature_window: Window size for rolling features
            prediction_horizon: Number of ticks to predict ahead
            use_gpu: Use GPU acceleration
            use_mixed_precision: Use mixed precision for memory optimization
            max_gpu_memory_gb: Maximum GPU memory usage in GB
            max_ram_gb: Maximum RAM usage in GB
            batch_size: Batch size for training
            model_params: LightGBM model parameters
        """
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("lightgbm not installed. Install with: pip install lightgbm")
        
        self.orderbook_depth = orderbook_depth
        self.sequence_length = sequence_length
        self.feature_window = feature_window
        self.prediction_horizon = prediction_horizon
        self.use_gpu = use_gpu
        self.use_mixed_precision = use_mixed_precision
        self.max_gpu_memory_gb = max_gpu_memory_gb
        self.max_ram_gb = max_ram_gb
        self.batch_size = batch_size
        
        # Initialize feature engineer
        self.feature_engineer = create_mbo_features_pipeline(
            orderbook_depth=orderbook_depth,
            sequence_length=sequence_length,
            feature_window=feature_window,
            use_mixed_precision=use_mixed_precision
        )
        
        # Initialize GPU trainer
        self.gpu_trainer = GPUOptimizedLightGBMTrainer(
            max_gpu_memory_gb=max_gpu_memory_gb,
            max_ram_gb=max_ram_gb,
            use_mixed_precision=use_mixed_precision,
            batch_size=batch_size,
            device="cuda" if use_gpu else "cpu"
        )
        
        # Model components
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_params = self._get_default_params()
        if model_params:
            self.model_params.update(model_params)
        
        # Training state
        self.is_trained = False
        self.training_history = {}
        self.feature_importance = None
        
        logger.info(f"MBO LightGBM Model initialized:")
        logger.info(f"  Order book depth: {orderbook_depth}")
        logger.info(f"  Sequence length: {sequence_length}")
        logger.info(f"  Feature window: {feature_window}")
        logger.info(f"  Prediction horizon: {prediction_horizon}")
        logger.info(f"  GPU acceleration: {use_gpu}")
        logger.info(f"  Mixed precision: {use_mixed_precision}")
        logger.info(f"  Max GPU memory: {max_gpu_memory_gb} GB")
        logger.info(f"  Max RAM: {max_ram_gb} GB")
        logger.info(f"  Batch size: {batch_size}")
    
    def _get_default_params(self) -> Dict[str, Any]:
        """Get default LightGBM parameters optimized for MBO data."""
        base_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        }
        
        # GPU optimization parameters
        if self.use_gpu:
            gpu_params = {
                'device': 'gpu',
                'gpu_platform_id': 0,
                'gpu_device_id': 0,
                'max_bin': 255,
                'min_data_in_bin': 3,
                'max_memory_usage': int(self.max_gpu_memory_gb * 1024),  # MB
                'force_col_wise': True,
                'gpu_use_dp': not self.use_mixed_precision  # Use double precision if not mixed
            }
            base_params.update(gpu_params)
        
        # Memory optimization parameters
        memory_params = {
            'max_memory_usage': int(self.max_ram_gb * 1024),  # MB
            'num_threads': 4,  # Limit threads to save memory
            'histogram_pool_size': -1,  # Auto-detect
            'max_depth': 6,  # Limit depth for memory efficiency
            'min_child_samples': 20,
            'min_split_gain': 0.0
        }
        base_params.update(memory_params)
        
        return base_params
    
    def preprocess_mbo_data(self, mbo_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Preprocess MBO data and extract features.
        
        Args:
            mbo_df: Raw MBO DataFrame
            
        Returns:
            Tuple of (features_df, targets_series)
        """
        logger.info(f"Preprocessing MBO data with {len(mbo_df)} events")
        
        # Validate input data
        required_columns = ['price', 'size', 'side', 'action']
        missing_columns = [col for col in required_columns if col not in mbo_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Process MBO data to extract features
        features_df, targets_series = self.feature_engineer.process_mbo_dataframe(mbo_df)
        
        # Store feature names
        self.feature_names = list(features_df.columns)
        
        # Handle missing values
        features_df = self._handle_missing_values(features_df)
        
        # Remove rows with invalid targets
        valid_mask = np.isfinite(targets_series) & (targets_series != 0)
        features_df = features_df[valid_mask]
        targets_series = targets_series[valid_mask]
        
        logger.info(f"Preprocessing completed:")
        logger.info(f"  Features shape: {features_df.shape}")
        logger.info(f"  Targets shape: {targets_series.shape}")
        logger.info(f"  Feature count: {len(self.feature_names)}")
        
        return features_df, targets_series
    
    def _handle_missing_values(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in features."""
        # Fill missing values with appropriate defaults
        numeric_columns = features_df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_columns:
            if features_df[col].isnull().any():
                if col.startswith('price_') or col.startswith('volume_'):
                    # Use forward fill for price/volume features
                    features_df[col] = features_df[col].fillna(method='ffill')
                else:
                    # Use median for other features
                    features_df[col] = features_df[col].fillna(features_df[col].median())
        
        # Fill remaining missing values with 0
        features_df = features_df.fillna(0)
        
        return features_df
    
    def scale_features(self, features_df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """
        Scale features using robust scaling.
        
        Args:
            features_df: Features DataFrame
            fit: Whether to fit the scaler (True for training, False for prediction)
            
        Returns:
            Scaled features DataFrame
        """
        if fit:
            self.scaler = RobustScaler()
            scaled_features = self.scaler.fit_transform(features_df)
        else:
            if self.scaler is None:
                raise ValueError("Scaler not fitted. Call fit() first.")
            scaled_features = self.scaler.transform(features_df)
        
        return pd.DataFrame(scaled_features, columns=features_df.columns, index=features_df.index)
    
    def train(self, 
              mbo_df: pd.DataFrame,
              validation_split: float = 0.2,
              test_split: float = 0.1,
              random_state: int = 42) -> Dict[str, Any]:
        """
        Train the LightGBM model on MBO data.
        
        Args:
            mbo_df: Raw MBO DataFrame
            validation_split: Fraction of data for validation
            test_split: Fraction of data for testing
            random_state: Random seed for reproducibility
            
        Returns:
            Training results dictionary
        """
        logger.info("Starting MBO LightGBM model training")
        
        # Preprocess data
        features_df, targets_series = self.preprocess_mbo_data(mbo_df)
        
        # Split data
        train_val_features, test_features, train_val_targets, test_targets = train_test_split(
            features_df, targets_series, test_size=test_split, random_state=random_state
        )
        
        train_features, val_features, train_targets, val_targets = train_test_split(
            train_val_features, train_val_targets, test_size=validation_split, random_state=random_state
        )
        
        logger.info(f"Data splits:")
        logger.info(f"  Training: {len(train_features)} samples")
        logger.info(f"  Validation: {len(val_features)} samples")
        logger.info(f"  Test: {len(test_features)} samples")
        
        # Scale features
        train_features_scaled = self.scale_features(train_features, fit=True)
        val_features_scaled = self.scale_features(val_features, fit=False)
        test_features_scaled = self.scale_features(test_features, fit=False)
        
        # Train model using GPU-optimized trainer
        logger.info("Training LightGBM model with GPU optimization")
        
        try:
            self.model = self.gpu_trainer.train(
                X=train_features_scaled,
                y=train_targets,
                **self.model_params
            )
            
            # Evaluate model
            train_predictions = self.model.predict(train_features_scaled)
            val_predictions = self.model.predict(val_features_scaled)
            test_predictions = self.model.predict(test_features_scaled)
            
            # Calculate metrics
            metrics = self._calculate_metrics(
                train_targets, train_predictions,
                val_targets, val_predictions,
                test_targets, test_predictions
            )
            
            # Store feature importance
            self.feature_importance = self._get_feature_importance()
            
            # Update training state
            self.is_trained = True
            self.training_history = {
                'metrics': metrics,
                'feature_importance': self.feature_importance,
                'model_params': self.model_params,
                'data_splits': {
                    'train_size': len(train_features),
                    'val_size': len(val_features),
                    'test_size': len(test_features)
                }
            }
            
            logger.info("Training completed successfully")
            logger.info(f"Model performance:")
            logger.info(f"  Train RMSE: {metrics['train_rmse']:.6f}")
            logger.info(f"  Val RMSE: {metrics['val_rmse']:.6f}")
            logger.info(f"  Test RMSE: {metrics['test_rmse']:.6f}")
            logger.info(f"  Test R²: {metrics['test_r2']:.6f}")
            
            return self.training_history
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def _calculate_metrics(self, 
                          train_targets: pd.Series, train_predictions: np.ndarray,
                          val_targets: pd.Series, val_predictions: np.ndarray,
                          test_targets: pd.Series, test_predictions: np.ndarray) -> Dict[str, float]:
        """Calculate comprehensive model metrics."""
        metrics = {}
        
        # Training metrics
        metrics['train_rmse'] = np.sqrt(mean_squared_error(train_targets, train_predictions))
        metrics['train_mae'] = mean_absolute_error(train_targets, train_predictions)
        metrics['train_r2'] = r2_score(train_targets, train_predictions)
        
        # Validation metrics
        metrics['val_rmse'] = np.sqrt(mean_squared_error(val_targets, val_predictions))
        metrics['val_mae'] = mean_absolute_error(val_targets, val_predictions)
        metrics['val_r2'] = r2_score(val_targets, val_predictions)
        
        # Test metrics
        metrics['test_rmse'] = np.sqrt(mean_squared_error(test_targets, test_predictions))
        metrics['test_mae'] = mean_absolute_error(test_targets, test_predictions)
        metrics['test_r2'] = r2_score(test_targets, test_predictions)
        
        # Additional metrics
        metrics['train_target_std'] = train_targets.std()
        metrics['val_target_std'] = val_targets.std()
        metrics['test_target_std'] = test_targets.std()
        
        return metrics
    
    def _get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from the trained model."""
        if self.model is None:
            return pd.DataFrame()
        
        importance = self.model.feature_importance(importance_type='gain')
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        return feature_importance_df
    
    def predict(self, mbo_df: pd.DataFrame) -> np.ndarray:
        """
        Make predictions on new MBO data.
        
        Args:
            mbo_df: Raw MBO DataFrame
            
        Returns:
            Predictions array
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        
        # Preprocess data
        features_df, _ = self.preprocess_mbo_data(mbo_df)
        
        # Scale features
        features_scaled = self.scale_features(features_df, fit=False)
        
        # Make predictions
        predictions = self.model.predict(features_scaled)
        
        return predictions
    
    def predict_single_tick(self, mbo_event: Dict) -> float:
        """
        Make prediction for a single MBO event (real-time).
        
        Args:
            mbo_event: Single MBO event dictionary
            
        Returns:
            Prediction value
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")
        
        # Extract features for single event
        features = self.feature_engineer.process_tick(mbo_event)
        features_df = pd.DataFrame([features])
        
        # Scale features
        features_scaled = self.scale_features(features_df, fit=False)
        
        # Make prediction
        prediction = self.model.predict(features_scaled)[0]
        
        return prediction
    
    def save_model(self, filepath: str) -> None:
        """
        Save the trained model to disk.
        
        Args:
            filepath: Path to save the model
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Cannot save untrained model.")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_params': self.model_params,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'config': {
                'orderbook_depth': self.orderbook_depth,
                'sequence_length': self.sequence_length,
                'feature_window': self.feature_window,
                'prediction_horizon': self.prediction_horizon,
                'use_gpu': self.use_gpu,
                'use_mixed_precision': self.use_mixed_precision
            }
        }
        
        # Create directory if it doesn't exist
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Save model
        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to: {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """
        Load a trained model from disk.
        
        Args:
            filepath: Path to the saved model
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        # Load model data
        model_data = joblib.load(filepath)
        
        # Restore model components
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.model_params = model_data['model_params']
        self.training_history = model_data['training_history']
        self.feature_importance = model_data['feature_importance']
        
        # Restore configuration
        config = model_data['config']
        self.orderbook_depth = config['orderbook_depth']
        self.sequence_length = config['sequence_length']
        self.feature_window = config['feature_window']
        self.prediction_horizon = config['prediction_horizon']
        self.use_gpu = config['use_gpu']
        self.use_mixed_precision = config['use_mixed_precision']
        
        # Update training state
        self.is_trained = True
        
        logger.info(f"Model loaded from: {filepath}")
        logger.info(f"Model performance: Test RMSE = {self.training_history['metrics']['test_rmse']:.6f}")
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get comprehensive model summary."""
        if not self.is_trained:
            return {'status': 'Not trained'}
        
        summary = {
            'status': 'Trained',
            'model_type': 'LightGBM',
            'config': {
                'orderbook_depth': self.orderbook_depth,
                'sequence_length': self.sequence_length,
                'feature_window': self.feature_window,
                'prediction_horizon': self.prediction_horizon,
                'use_gpu': self.use_gpu,
                'use_mixed_precision': self.use_mixed_precision
            },
            'performance': self.training_history['metrics'],
            'feature_count': len(self.feature_names),
            'top_features': self.feature_importance.head(10).to_dict('records') if self.feature_importance is not None else [],
            'data_splits': self.training_history.get('data_splits', {})
        }
        
        return summary
    
    def optimize_hyperparameters(self, 
                               mbo_df: pd.DataFrame,
                               param_grid: Optional[Dict] = None,
                               cv_folds: int = 3,
                               n_trials: int = 50) -> Dict[str, Any]:
        """
        Optimize hyperparameters using Optuna.
        
        Args:
            mbo_df: Training data
            param_grid: Parameter grid for optimization
            cv_folds: Number of cross-validation folds
            n_trials: Number of optimization trials
            
        Returns:
            Optimization results
        """
        try:
            import optuna
        except ImportError:
            raise ImportError("optuna not installed. Install with: pip install optuna")
        
        logger.info(f"Starting hyperparameter optimization with {n_trials} trials")
        
        # Default parameter grid
        if param_grid is None:
            param_grid = {
                'num_leaves': [15, 31, 63, 127],
                'learning_rate': [0.01, 0.05, 0.1, 0.2],
                'feature_fraction': [0.7, 0.8, 0.9, 1.0],
                'bagging_fraction': [0.7, 0.8, 0.9, 1.0],
                'min_child_samples': [10, 20, 50, 100],
                'reg_alpha': [0, 0.1, 0.5, 1.0],
                'reg_lambda': [0, 0.1, 0.5, 1.0]
            }
        
        # Preprocess data
        features_df, targets_series = self.preprocess_mbo_data(mbo_df)
        
        def objective(trial):
            # Sample parameters
            params = {
                'num_leaves': trial.suggest_categorical('num_leaves', param_grid['num_leaves']),
                'learning_rate': trial.suggest_categorical('learning_rate', param_grid['learning_rate']),
                'feature_fraction': trial.suggest_categorical('feature_fraction', param_grid['feature_fraction']),
                'bagging_fraction': trial.suggest_categorical('bagging_fraction', param_grid['bagging_fraction']),
                'min_child_samples': trial.suggest_categorical('min_child_samples', param_grid['min_child_samples']),
                'reg_alpha': trial.suggest_categorical('reg_alpha', param_grid['reg_alpha']),
                'reg_lambda': trial.suggest_categorical('reg_lambda', param_grid['reg_lambda'])
            }
            
            # Update model parameters
            trial_params = self.model_params.copy()
            trial_params.update(params)
            
            # Cross-validation
            from sklearn.model_selection import cross_val_score
            from sklearn.metrics import make_scorer, mean_squared_error
            
            rmse_scorer = make_scorer(lambda y_true, y_pred: np.sqrt(mean_squared_error(y_true, y_pred)))
            
            # Scale features
            features_scaled = self.scale_features(features_df, fit=True)
            
            # Perform cross-validation
            scores = cross_val_score(
                lgb.LGBMRegressor(**trial_params),
                features_scaled,
                targets_series,
                cv=cv_folds,
                scoring=rmse_scorer
            )
            
            return scores.mean()
        
        # Run optimization
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials)
        
        # Update model parameters with best values
        self.model_params.update(study.best_params)
        
        logger.info(f"Hyperparameter optimization completed:")
        logger.info(f"  Best RMSE: {study.best_value:.6f}")
        logger.info(f"  Best parameters: {study.best_params}")
        
        return {
            'best_params': study.best_params,
            'best_score': study.best_value,
            'study': study
        }


def create_mbo_lightgbm_model(orderbook_depth: int = 10,
                             sequence_length: int = 100,
                             feature_window: int = 50,
                             prediction_horizon: int = 10,
                             use_gpu: bool = True,
                             use_mixed_precision: bool = True) -> MBOLightGBMModel:
    """
    Create a configured MBO LightGBM model.
    
    Args:
        orderbook_depth: Number of order book levels
        sequence_length: Length of price/volume sequences
        feature_window: Window for rolling calculations
        prediction_horizon: Number of ticks to predict ahead
        use_gpu: Use GPU acceleration
        use_mixed_precision: Use mixed precision for memory optimization
        
    Returns:
        Configured MBOLightGBMModel instance
    """
    return MBOLightGBMModel(
        orderbook_depth=orderbook_depth,
        sequence_length=sequence_length,
        feature_window=feature_window,
        prediction_horizon=prediction_horizon,
        use_gpu=use_gpu,
        use_mixed_precision=use_mixed_precision
    )
