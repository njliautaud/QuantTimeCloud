"""
Model Registry for QuantTime ML Trading Suite.
Manages model metadata, persistence, and card-based display.
"""
import os
import json
import pickle
import joblib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import uuid
import hashlib

import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

logger = logging.getLogger(__name__)

@dataclass
class ModelMetadata:
    """Model metadata for tracking and display."""
    model_id: str
    model_name: str
    model_type: str  # 'lightgbm', 'lstm', 'transformer', etc.
    symbol: str
    data_source: str  # 'mbo', 'ohlcv', etc.
    training_start_date: str
    training_end_date: str
    training_duration_minutes: float
    training_samples: int
    validation_samples: int
    test_samples: int
    
    # Model parameters
    orderbook_depth: int
    sequence_length: int
    feature_window: int
    prediction_horizon: int
    batch_size: int
    learning_rate: float
    
    # Performance metrics
    train_rmse: float
    val_rmse: float
    test_rmse: float
    train_mae: float
    val_mae: float
    test_mae: float
    train_r2: float
    val_r2: float
    test_r2: float
    
    # Feature importance (top 10)
    top_features: List[str]
    feature_importance_scores: List[float]
    
    # Model file info
    model_file_path: str
    model_size_mb: float
    created_at: str
    last_updated: str
    
    # Status
    status: str  # 'trained', 'ready_for_backtest', 'backtested', 'deployed'
    ready_for_backtest: bool = True
    ready_for_deployment: bool = False
    
    # Additional metadata
    hyperparameters: Dict[str, Any] = None
    training_config: Dict[str, Any] = None
    notes: str = ""
    timeframe: str = ""  # Timeframe filter used during training

class ModelRegistry:
    """
    Model registry for managing trained models with metadata and card-based display.
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.models_dir / "model_registry.json"
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict[str, ModelMetadata]:
        """Load existing model metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    return {k: ModelMetadata(**v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"Failed to load model metadata: {e}")
        return {}
    
    def _save_metadata(self):
        """Save model metadata to file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump({k: asdict(v) for k, v in self.metadata.items()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save model metadata: {e}")
    
    def register_model(self, 
                      model: Any,
                      model_name: str,
                      model_type: str,
                      symbol: str,
                      data_source: str,
                      training_data: Dict[str, Any],
                      performance_metrics: Dict[str, float],
                      feature_importance: Dict[str, float],
                      model_params: Dict[str, Any],
                      training_config: Dict[str, Any],
                      notes: str = "") -> str:
        """
        Register a trained model with comprehensive metadata.
        
        Args:
            model: Trained model object
            model_name: Human-readable model name
            model_type: Type of model (lightgbm, lstm, etc.)
            symbol: Trading symbol
            data_source: Data source type
            training_data: Training data information
            performance_metrics: Model performance metrics
            feature_importance: Feature importance scores
            model_params: Model parameters
            training_config: Training configuration
            notes: Additional notes
            
        Returns:
            Model ID
        """
        model_id = str(uuid.uuid4())
        
        # Calculate model file size
        model_file_path = self.models_dir / f"{model_id}_{model_name}.joblib"
        joblib.dump(model, model_file_path)
        model_size_mb = model_file_path.stat().st_size / (1024 * 1024)
        
        # Get top features
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        top_features = [f[0] for f in sorted_features[:10]]
        feature_scores = [f[1] for f in sorted_features[:10]]
        
        # Create metadata
        metadata = ModelMetadata(
            model_id=model_id,
            model_name=model_name,
            model_type=model_type,
            symbol=symbol,
            data_source=data_source,
            training_start_date=training_data.get('start_date', ''),
            training_end_date=training_data.get('end_date', ''),
            training_duration_minutes=training_data.get('duration_minutes', 0.0),
            training_samples=training_data.get('train_samples', 0),
            validation_samples=training_data.get('val_samples', 0),
            test_samples=training_data.get('test_samples', 0),
            orderbook_depth=model_params.get('orderbook_depth', 0),
            sequence_length=model_params.get('sequence_length', 0),
            feature_window=model_params.get('feature_window', 0),
            prediction_horizon=model_params.get('prediction_horizon', 0),
            batch_size=model_params.get('batch_size', 0),
            learning_rate=model_params.get('learning_rate', 0.0),
            train_rmse=performance_metrics.get('train_rmse', 0.0),
            val_rmse=performance_metrics.get('val_rmse', 0.0),
            test_rmse=performance_metrics.get('test_rmse', 0.0),
            train_mae=performance_metrics.get('train_mae', 0.0),
            val_mae=performance_metrics.get('val_mae', 0.0),
            test_mae=performance_metrics.get('test_mae', 0.0),
            train_r2=performance_metrics.get('train_r2', 0.0),
            val_r2=performance_metrics.get('val_r2', 0.0),
            test_r2=performance_metrics.get('test_r2', 0.0),
            top_features=top_features,
            feature_importance_scores=feature_scores,
            model_file_path=str(model_file_path),
            model_size_mb=model_size_mb,
            created_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat(),
            status='trained',
            ready_for_backtest=True,
            ready_for_deployment=False,
            hyperparameters=model_params,
            training_config=training_config,
            notes=notes
        )
        
        self.metadata[model_id] = metadata
        self._save_metadata()
        
        logger.info(f"Registered model {model_name} with ID {model_id}")
        return model_id
    
    def get_model(self, model_id: str) -> Optional[Any]:
        """Load a model by ID."""
        if model_id not in self.metadata:
            return None
        
        metadata = self.metadata[model_id]
        model_path = Path(metadata.model_file_path)
        
        if not model_path.exists():
            logger.error(f"Model file not found: {model_path}")
            return None
        
        try:
            return joblib.load(model_path)
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            return None
    
    def get_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Get model metadata by ID."""
        return self.metadata.get(model_id)
    
    def list_models(self, 
                   model_type: Optional[str] = None,
                   symbol: Optional[str] = None,
                   status: Optional[str] = None) -> List[ModelMetadata]:
        """List models with optional filtering."""
        models = list(self.metadata.values())
        
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        if symbol:
            models = [m for m in models if m.symbol == symbol]
        if status:
            models = [m for m in models if m.status == status]
        
        return sorted(models, key=lambda x: x.created_at, reverse=True)
    
    def delete_model(self, model_id: str) -> bool:
        """Delete a model and its metadata."""
        if model_id not in self.metadata:
            return False
        
        metadata = self.metadata[model_id]
        model_path = Path(metadata.model_file_path)
        
        try:
            if model_path.exists():
                model_path.unlink()
            del self.metadata[model_id]
            self._save_metadata()
            logger.info(f"Deleted model {model_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_id}: {e}")
            return False
    
    def update_model_status(self, model_id: str, status: str) -> bool:
        """Update model status."""
        if model_id not in self.metadata:
            return False
        
        self.metadata[model_id].status = status
        self.metadata[model_id].last_updated = datetime.now().isoformat()
        self._save_metadata()
        return True
    
    def get_model_cards(self, 
                       model_type: Optional[str] = None,
                       symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get model data formatted for card display.
        
        Returns:
            List of model card data for Streamlit display
        """
        models = self.list_models(model_type=model_type, symbol=symbol)
        cards = []
        
        for model in models:
            # Determine card color based on model type
            color_map = {
                'lightgbm': '#00ff88',
                'lstm': '#ff8800',
                'transformer': '#8800ff',
                'cnn': '#0088ff',
                'ensemble': '#ff0088'
            }
            card_color = color_map.get(model.model_type, '#888888')
            
            # Format performance metrics
            performance_summary = f"RMSE: {model.test_rmse:.4f} | R²: {model.test_r2:.3f}"
            
            # Format training info
            training_info = f"{model.training_samples:,} samples | {model.training_duration_minutes:.1f}min"
            
            # Format parameters
            params_summary = f"Depth:{model.orderbook_depth} | Seq:{model.sequence_length} | Batch:{model.batch_size}"
            
            card = {
                'id': model.model_id,
                'title': model.model_name,
                'subtitle': f"{model.symbol} - {model.data_source.upper()}",
                'model_type': model.model_type,
                'card_color': card_color,
                'performance': performance_summary,
                'training_info': training_info,
                'parameters': params_summary,
                'created_at': model.created_at,
                'status': model.status,
                'ready_for_backtest': model.ready_for_backtest,
                'ready_for_deployment': model.ready_for_deployment,
                'top_features': model.top_features[:5],  # Top 5 features
                'model_size_mb': model.model_size_mb,
                'notes': model.notes,
                'timeframe': model.timeframe  # Add timeframe information
            }
            cards.append(card)
        
        return cards
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """Get overall model registry statistics."""
        if not self.metadata:
            return {}
        
        models = list(self.metadata.values())
        
        stats = {
            'total_models': len(models),
            'models_by_type': {},
            'models_by_symbol': {},
            'models_by_status': {},
            'avg_training_time': 0.0,
            'avg_test_rmse': 0.0,
            'avg_test_r2': 0.0,
            'total_training_samples': 0
        }
        
        for model in models:
            # Count by type
            stats['models_by_type'][model.model_type] = stats['models_by_type'].get(model.model_type, 0) + 1
            
            # Count by symbol
            stats['models_by_symbol'][model.symbol] = stats['models_by_symbol'].get(model.symbol, 0) + 1
            
            # Count by status
            stats['models_by_status'][model.status] = stats['models_by_status'].get(model.status, 0) + 1
            
            # Accumulate metrics
            stats['avg_training_time'] += model.training_duration_minutes
            stats['avg_test_rmse'] += model.test_rmse
            stats['avg_test_r2'] += model.test_r2
            stats['total_training_samples'] += model.training_samples
        
        # Calculate averages
        if models:
            stats['avg_training_time'] /= len(models)
            stats['avg_test_rmse'] /= len(models)
            stats['avg_test_r2'] /= len(models)
        
        return stats
