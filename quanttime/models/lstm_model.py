"""
Enhanced LSTM Model for Financial Time Series Prediction.

This module implements an LSTM-based model optimized for MBO data prediction
with comprehensive order flow understanding and model-driven alpha generation.

Core Philosophy: Model-Driven Alpha Generation
- Models determine their own alpha using all available data
- No manual feature selection or removal
- Comprehensive order flow understanding
- Full market microstructure analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
import logging
import time
from datetime import datetime
import warnings

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    warnings.warn("PyTorch not available - LSTM model disabled")

from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from .base import ModelBase, ModelConfig, TrainingMetrics
from ..features.mbo_feature_engineering import MBOFeatureEngineer
from ..features.comprehensive_order_flow import ComprehensiveOrderFlowEngineer, OrderFlowConfig
from ..features.smart_feature_selection import SmartFeatureSelector, FeatureImportanceConfig
from ..ml.gpu_optimized_training import GPUOptimizedTrainer

logger = logging.getLogger(__name__)


class LSTMModel(nn.Module):
    """
    Enhanced LSTM model for financial time series prediction with comprehensive order flow understanding.
    
    Features:
    - Multi-layer LSTM with dropout for temporal modeling
    - Attention mechanism for order flow focus
    - Bidirectional LSTM for better context
    - Residual connections for gradient flow
    - Multi-head output for different horizons
    - Order flow intelligence features
    - Market microstructure understanding
    - Temporal relationship preservation
    """
    
    def __init__(self, 
                 input_size: int,
                 hidden_size: int = 256,  # Increased for comprehensive features
                 num_layers: int = 4,     # Increased for complex patterns
                 num_horizons: int = 4,
                 dropout: float = 0.2,
                 bidirectional: bool = True,
                 use_order_flow_attention: bool = True,
                 use_microstructure_features: bool = True):
        """
        Initialize Enhanced LSTM model with comprehensive order flow understanding.
        
        Args:
            input_size: Number of input features (comprehensive order flow features)
            hidden_size: LSTM hidden size (increased for complex patterns)
            num_layers: Number of LSTM layers (increased for deep learning)
            num_horizons: Number of prediction horizons
            dropout: Dropout rate
            bidirectional: Use bidirectional LSTM
            use_order_flow_attention: Use attention for order flow focus
            use_microstructure_features: Include market microstructure features
        """
        super(LSTMModel, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_horizons = num_horizons
        self.bidirectional = bidirectional
        self.direction_multiplier = 2 if bidirectional else 1
        self.use_order_flow_attention = use_order_flow_attention
        self.use_microstructure_features = use_microstructure_features
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional,
            batch_first=True
        )
        
        # Enhanced attention mechanism for order flow focus
        if self.use_order_flow_attention:
            # Multi-head attention for order flow patterns
            self.order_flow_attention = nn.MultiheadAttention(
                embed_dim=hidden_size * self.direction_multiplier,
                num_heads=8,
                dropout=dropout,
                batch_first=True
            )
            
            # Temporal attention for sequence modeling
            self.temporal_attention = nn.MultiheadAttention(
                embed_dim=hidden_size * self.direction_multiplier,
                num_heads=4,
                dropout=dropout,
                batch_first=True
            )
            
            # Feature attention for microstructure focus
            if self.use_microstructure_features:
                self.microstructure_attention = nn.MultiheadAttention(
                    embed_dim=hidden_size * self.direction_multiplier,
                    num_heads=4,
                    dropout=dropout,
                    batch_first=True
                )
        else:
            # Standard attention mechanism
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_size * self.direction_multiplier,
                num_heads=8,
                dropout=dropout,
                batch_first=True
            )
        
        # Output layers for each horizon
        self.horizon_outputs = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_size * self.direction_multiplier, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size // 2, 1)
            ) for _ in range(num_horizons)
        ])
        
        # Residual connection
        self.residual_projection = nn.Linear(input_size, hidden_size * self.direction_multiplier)
        
        # Layer normalization
        self.layer_norm = nn.LayerNorm(hidden_size * self.direction_multiplier)
        
        logger.info(f"LSTM Model initialized:")
        logger.info(f"  Input size: {input_size}")
        logger.info(f"  Hidden size: {hidden_size}")
        logger.info(f"  Layers: {num_layers}")
        logger.info(f"  Horizons: {num_horizons}")
        logger.info(f"  Bidirectional: {bidirectional}")
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Enhanced forward pass through LSTM model with comprehensive order flow understanding.
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
            
        Returns:
            Output tensor of shape (batch_size, num_horizons)
        """
        batch_size, seq_len, input_size = x.shape
        
        # LSTM forward pass for temporal modeling
        lstm_out, _ = self.lstm(x)  # (batch_size, seq_len, hidden_size * direction_multiplier)
        
        if self.use_order_flow_attention:
            # Multi-head attention for order flow patterns
            order_flow_attn, _ = self.order_flow_attention(lstm_out, lstm_out, lstm_out)
            
            # Temporal attention for sequence modeling
            temporal_attn, _ = self.temporal_attention(lstm_out, lstm_out, lstm_out)
            
            # Combine attention mechanisms
            attn_out = order_flow_attn + temporal_attn
            
            # Microstructure attention if enabled
            if self.use_microstructure_features:
                microstructure_attn, _ = self.microstructure_attention(lstm_out, lstm_out, lstm_out)
                attn_out = attn_out + microstructure_attn
        else:
            # Standard attention mechanism
            attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Residual connection for gradient flow
        residual = self.residual_projection(x)
        attn_out = attn_out + residual
        
        # Layer normalization
        attn_out = self.layer_norm(attn_out)
        
        # Take the last output for prediction (preserving temporal relationships)
        last_output = attn_out[:, -1, :]  # (batch_size, hidden_size * direction_multiplier)
        
        # Generate predictions for each horizon
        predictions = []
        for horizon_output in self.horizon_outputs:
            pred = horizon_output(last_output)  # (batch_size, 1)
            predictions.append(pred)
        
        # Stack predictions
        output = torch.cat(predictions, dim=1)  # (batch_size, num_horizons)
        
        return output


class MBOLSTMModel(ModelBase):
    """
    Enhanced LSTM model for MBO data prediction with comprehensive order flow understanding.
    
    Optimized for:
    - 1-5 minute prediction horizons
    - Price movement as primary target
    - Comprehensive order flow features (ALL possible concepts)
    - Real-time tick-by-tick updates
    - GPU acceleration
    - Model-driven alpha generation
    - Full market microstructure analysis
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize MBO LSTM model.
        
        Args:
            config: Model configuration
        """
        super().__init__(config)
        
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for LSTM model")
        
        # Initialize comprehensive feature engineer (ALL order flow features)
        self.comprehensive_engineer = ComprehensiveOrderFlowEngineer(OrderFlowConfig())
        
        # Initialize legacy feature engineer for backward compatibility
        self.feature_engineer = MBOFeatureEngineer(
            orderbook_depth=config.orderbook_depth,
            sequence_length=config.sequence_length,
            feature_window=config.feature_window,
            use_mixed_precision=config.use_mixed_precision
        )
        
        # Initialize smart feature selector (analysis only, no removal)
        self.feature_selector = SmartFeatureSelector(FeatureImportanceConfig())
        
        # Initialize scalers
        self.feature_scaler = RobustScaler()
        self.target_scaler = StandardScaler()
        
        # Model components
        self.models = {}  # One model per horizon
        self.optimizers = {}
        self.schedulers = {}
        
        # Training components - will be initialized during training
        self.gpu_trainer = None
        self.gpu_config = {
            'max_gpu_memory_gb': config.max_gpu_memory_gb,
            'max_ram_gb': config.max_ram_gb,
            'use_mixed_precision': config.use_mixed_precision
        }
        
        # LSTM-specific parameters (will be set by factory function)
        self.lstm_params = {}
        
        # Device setup
        self.device = torch.device('cuda' if torch.cuda.is_available() and config.use_gpu else 'cpu')
        logger.info(f"Using device: {self.device}")
        
        # Training state
        self.best_models = {}
        self.training_losses = {}
        self.validation_losses = {}
    
    def _prepare_sequences(self, 
                          features: np.ndarray, 
                          targets: np.ndarray,
                          sequence_length: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequences for LSTM training.
        
        Args:
            features: Feature array
            targets: Target array
            sequence_length: Length of input sequences
            
        Returns:
            Tuple of (X, y) arrays
        """
        X, y = [], []
        
        for i in range(sequence_length, len(features)):
            X.append(features[i-sequence_length:i])
            y.append(targets[i])
        
        return np.array(X), np.array(y)
    
    def _create_data_loaders(self, 
                           X_train: np.ndarray, 
                           y_train: np.ndarray,
                           X_val: np.ndarray, 
                           y_val: np.ndarray,
                           batch_size: int) -> Tuple[DataLoader, DataLoader]:
        """
        Create PyTorch data loaders.
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            batch_size: Batch size
            
        Returns:
            Tuple of (train_loader, val_loader)
        """
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train).to(self.device)
        y_train_tensor = torch.FloatTensor(y_train).to(self.device)
        X_val_tensor = torch.FloatTensor(X_val).to(self.device)
        y_val_tensor = torch.FloatTensor(y_val).to(self.device)
        
        # Create datasets
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
        
        # Create loaders
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        return train_loader, val_loader
    
    def _train_single_horizon(self, 
                             horizon: int,
                             train_loader: DataLoader,
                             val_loader: DataLoader,
                             progress_callback: Optional[Any] = None,
                             epochs: int = 100,
                             patience: int = 10) -> Dict[str, Any]:
        """
        Train LSTM model for a single horizon.
        
        Args:
            horizon: Prediction horizon
            train_loader: Training data loader
            val_loader: Validation data loader
            epochs: Number of training epochs
            patience: Early stopping patience
            
        Returns:
            Training results dictionary
        """
        # Initialize model for this horizon
        input_size = next(iter(train_loader))[0].shape[-1]
        model = LSTMModel(
            input_size=input_size,
            hidden_size=128,
            num_layers=3,
            num_horizons=1,  # Single horizon model
            dropout=0.2,
            bidirectional=True
        ).to(self.device)
        
        # Initialize optimizer and scheduler
        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5, verbose=True
        )
        
        # Loss function
        criterion = nn.MSELoss()
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        train_losses = []
        val_losses = []
        
        logger.info(f"Training LSTM model for {horizon}-minute horizon")
        
        for epoch in range(epochs):
            # Training phase
            model.train()
            train_loss = 0.0
            
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                
                # Forward pass
                outputs = model(batch_X)
                loss = criterion(outputs.squeeze(), batch_y)
                
                # Backward pass
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                
                train_loss += loss.item()
            
            # Validation phase
            model.eval()
            val_loss = 0.0
            
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    outputs = model(batch_X)
                    loss = criterion(outputs.squeeze(), batch_y)
                    val_loss += loss.item()
            
            # Calculate average losses
            avg_train_loss = train_loss / len(train_loader)
            avg_val_loss = val_loss / len(val_loader)
            
            # Calculate R² scores (approximate)
            train_r2 = max(0, 1 - avg_train_loss) if avg_train_loss > 0 else 0.0
            val_r2 = max(0, 1 - avg_val_loss) if avg_val_loss > 0 else 0.0
            
            # Update progress callback
            if progress_callback:
                progress_callback.on_epoch_end(
                    epoch=epoch + 1,
                    total_epochs=epochs,
                    train_loss=avg_train_loss,
                    val_loss=avg_val_loss,
                    train_r2=train_r2,
                    val_r2=val_r2,
                    learning_rate=optimizer.param_groups[0]['lr']
                )
            
            train_losses.append(avg_train_loss)
            val_losses.append(avg_val_loss)
            
            # Learning rate scheduling
            scheduler.step(avg_val_loss)
            
            # Early stopping
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                # Save best model
                self.best_models[horizon] = model.state_dict().copy()
            else:
                patience_counter += 1
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: Train Loss: {avg_train_loss:.6f}, Val Loss: {avg_val_loss:.6f}")
            
            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch}")
                break
        
        # Store training history
        self.training_losses[horizon] = train_losses
        self.validation_losses[horizon] = val_losses
        
        return {
            'best_val_loss': best_val_loss,
            'final_train_loss': train_losses[-1],
            'final_val_loss': val_losses[-1],
            'epochs_trained': len(train_losses)
        }
    
    def _analyze_feature_importance(self, features_df: pd.DataFrame) -> None:
        """Analyze feature importance while preserving ALL features for model-driven alpha generation."""
        
        try:
            logger.info("🔍 Starting comprehensive feature importance analysis...")
            
            # Create target variables for analysis
            if 'price' in features_df.columns:
                # Create direction targets for different horizons
                for horizon in self.config.prediction_horizons:
                    target_col = f'direction_{horizon}m'
                    if target_col in features_df.columns:
                        # Prepare feature matrix (exclude target columns)
                        feature_cols = [col for col in features_df.columns 
                                       if not any(f'target_{h}m' in col or f'direction_{h}m' in col 
                                                for h in self.config.prediction_horizons)]
                        
                        X = features_df[feature_cols].fillna(0)
                        y = features_df[target_col].fillna(0)
                        
                        # Analyze feature importance
                        importance_results = self.feature_selector.analyze_feature_importance(
                            X, y, target_type='classification'
                        )
                        
                        logger.info(f"✅ Feature importance analysis completed for {horizon}m horizon")
                        logger.info(f"📊 Analyzed {len(feature_cols)} features")
                        
                        # Log top features but emphasize we keep ALL
                        top_features = importance_results['rankings'].get('lightgbm', [])[:10]
                        logger.info(f"🏆 Top 10 features for {horizon}m horizon: {top_features}")
                        logger.info(f"💡 Keeping ALL {len(feature_cols)} features for model-driven alpha generation")
            
            # Specialized order flow analysis
            self._analyze_order_flow_features(features_df)
            
        except Exception as e:
            logger.error(f"Error in feature importance analysis: {e}")
            logger.info("Continuing with all features as per QuantTime philosophy")
    
    def _analyze_order_flow_features(self, features_df: pd.DataFrame) -> None:
        """Specialized analysis of order flow features for comprehensive understanding."""
        
        try:
            logger.info("🌊 Analyzing comprehensive order flow features...")
            
            # Identify all order flow related features
            order_flow_keywords = [
                'volume', 'imbalance', 'absorption', 'iceberg', 'order_block',
                'bid', 'ask', 'spread', 'flow', 'pressure', 'momentum',
                'delta', 'gamma', 'theta', 'vega', 'greeks',
                'liquidity', 'depth', 'resistance', 'support',
                'breakout', 'breakdown', 'consolidation', 'accumulation',
                'distribution', 'divergence', 'convergence', 'momentum',
                'volatility', 'skew', 'kurtosis', 'correlation',
                'regime', 'regime_change', 'market_microstructure',
                'order_flow', 'trade_flow', 'institutional_flow',
                'retail_flow', 'smart_money', 'dumb_money',
                'alpha', 'beta', 'sharpe', 'sortino', 'calmar',
                'max_drawdown', 'var', 'cvar', 'expected_shortfall'
            ]
            
            order_flow_features = [
                col for col in features_df.columns 
                if any(keyword in col.lower() for keyword in order_flow_keywords)
            ]
            
            logger.info(f"🌊 Identified {len(order_flow_features)} order flow features")
            
            # Analyze order flow feature categories
            order_flow_categories = {
                'volume_analysis': [col for col in order_flow_features if 'volume' in col.lower()],
                'imbalance_analysis': [col for col in order_flow_features if 'imbalance' in col.lower()],
                'pattern_detection': [col for col in order_flow_features if any(x in col.lower() for x in ['pattern', 'detection', 'iceberg', 'absorption'])],
                'price_action': [col for col in order_flow_features if any(x in col.lower() for x in ['price', 'spread', 'bid', 'ask'])],
                'temporal_features': [col for col in order_flow_features if any(x in col.lower() for x in ['time', 'momentum', 'trend'])],
                'statistical_features': [col for col in order_flow_features if any(x in col.lower() for x in ['std', 'mean', 'skew', 'kurtosis', 'correlation'])],
                'market_microstructure': [col for col in order_flow_features if any(x in col.lower() for x in ['microstructure', 'liquidity', 'depth', 'flow'])],
                'regime_features': [col for col in order_flow_features if any(x in col.lower() for x in ['regime', 'state', 'condition'])],
                'risk_features': [col for col in order_flow_features if any(x in col.lower() for x in ['risk', 'var', 'drawdown', 'volatility'])]
            }
            
            # Log category breakdown
            for category, features in order_flow_categories.items():
                if features:
                    logger.info(f"📊 {category}: {len(features)} features")
            
            logger.info("✅ Comprehensive order flow analysis completed")
            
        except Exception as e:
            logger.error(f"Error in order flow analysis: {e}")
            logger.info("Continuing with all order flow features")
    
    def train(self, 
              mbo_df: pd.DataFrame,
              validation_split: float = 0.2,
              test_split: float = 0.1,
              random_state: int = 42) -> Dict[str, Any]:
        """
        Train the LSTM model on MBO data.
        
        Args:
            mbo_df: MBO dataframe
            validation_split: Validation split ratio
            test_split: Test split ratio
            random_state: Random seed
            
        Returns:
            Training results dictionary
        """
        logger.info("Starting LSTM model training")
        start_time = time.time()
        
        # Engineer comprehensive features (ALL order flow concepts)
        logger.info("🌊 Engineering comprehensive order flow features...")
        features_df = self.comprehensive_engineer.engineer_all_order_flow_features(mbo_df)
        
        # Add any legacy features for backward compatibility
        legacy_features = self.feature_engineer.process_mbo_dataframe(mbo_df)
        for col in legacy_features.columns:
            if col not in features_df.columns:
                features_df[col] = legacy_features[col]
        
        # Analyze feature importance (but keep ALL features)
        logger.info("🔍 Analyzing feature importance while preserving all features...")
        self._analyze_feature_importance(features_df)
        
        logger.info(f"✅ Comprehensive feature engineering completed. Total features: {len(features_df.columns)}")
        logger.info(f"💡 Keeping ALL {len(features_df.columns)} features for model-driven alpha generation")
        
        # Create targets for each horizon
        targets = self._create_targets(mbo_df)
        
        # Scale features
        features_scaled = self.feature_scaler.fit_transform(features_df)
        
        # Training results
        training_results = {}
        
        for horizon in self.config.prediction_horizons:
            logger.info(f"Training LSTM for {horizon}-minute horizon")
            
            # Prepare sequences
            X, y = self._prepare_sequences(
                features_scaled, 
                targets[horizon].values, 
                self.config.sequence_length
            )
            
            # Split data
            split_idx = int(len(X) * (1 - validation_split - test_split))
            val_split_idx = int(len(X) * (1 - test_split))
            
            X_train, y_train = X[:split_idx], y[:split_idx]
            X_val, y_val = X[split_idx:val_split_idx], y[split_idx:val_split_idx]
            X_test, y_test = X[val_split_idx:], y[val_split_idx:]
            
            # Create data loaders
            train_loader, val_loader = self._create_data_loaders(
                X_train, y_train, X_val, y_val, self.config.batch_size
            )
            
            # Train model
            horizon_results = self._train_single_horizon(
                horizon, train_loader, val_loader
            )
            
            # Evaluate on test set
            test_metrics = self._evaluate_horizon(horizon, X_test, y_test)
            
            training_results[horizon] = {
                **horizon_results,
                'test_metrics': test_metrics,
                'train_samples': len(X_train),
                'val_samples': len(X_val),
                'test_samples': len(X_test)
            }
        
        # Calculate training duration
        training_duration = (time.time() - start_time) / 60
        
        # Store training history
        self.training_history = {
            'training_duration_minutes': training_duration,
            'horizons_trained': list(self.config.prediction_horizons),
            'total_samples': len(features_df),
            'feature_count': len(features_df.columns),
            'results': training_results
        }
        
        self.is_trained = True
        
        logger.info(f"LSTM training completed in {training_duration:.2f} minutes")
        return self.training_history
    
    def _create_targets(self, mbo_df: pd.DataFrame) -> Dict[int, pd.Series]:
        """
        Create targets for each prediction horizon.
        
        Args:
            mbo_df: MBO dataframe
            
        Returns:
            Dictionary of target series for each horizon
        """
        targets = {}
        
        for horizon in self.config.prediction_horizons:
            # Convert horizon from minutes to approximate tick count
            tick_horizon = horizon * 1000  # Assuming 1000 ticks per minute
            
            # Calculate future price change
            future_price = mbo_df['price'].shift(-tick_horizon)
            current_price = mbo_df['price']
            
            # Target: log returns (more stable for financial data)
            log_returns = np.log(future_price / current_price) * 100
            
            targets[horizon] = log_returns.dropna()
        
        return targets
    
    def _evaluate_horizon(self, horizon: int, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model performance for a specific horizon.
        
        Args:
            horizon: Prediction horizon
            X_test: Test features
            y_test: Test targets
            
        Returns:
            Dictionary of evaluation metrics
        """
        # Load best model
        input_size = X_test.shape[-1]
        model = LSTMModel(
            input_size=input_size,
            hidden_size=128,
            num_layers=3,
            num_horizons=1,
            dropout=0.2,
            bidirectional=True
        ).to(self.device)
        
        model.load_state_dict(self.best_models[horizon])
        model.eval()
        
        # Make predictions
        with torch.no_grad():
            X_test_tensor = torch.FloatTensor(X_test).to(self.device)
            predictions = model(X_test_tensor).cpu().numpy().squeeze()
        
        # Calculate metrics
        rmse = np.sqrt(mean_squared_error(y_test, predictions))
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions)
        
        # Calculate financial metrics
        financial_metrics = self._calculate_financial_metrics(
            predictions, y_test, np.arange(len(y_test))  # Placeholder for prices
        )
        
        return {
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            **financial_metrics
        }
    
    def predict(self, 
                mbo_df: pd.DataFrame,
                horizon: int = 1) -> np.ndarray:
        """
        Make predictions for given horizon.
        
        Args:
            mbo_df: MBO dataframe
            horizon: Prediction horizon in minutes
            
        Returns:
            Predictions array
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        if horizon not in self.config.prediction_horizons:
            raise ValueError(f"Horizon {horizon} not trained. Available: {self.config.prediction_horizons}")
        
        # Engineer features
        features_df = self.feature_engineer.process_mbo_dataframe(mbo_df)
        features_scaled = self.feature_scaler.transform(features_df)
        
        # Prepare sequences
        X, _ = self._prepare_sequences(
            features_scaled, 
            np.zeros(len(features_scaled)),  # Dummy targets
            self.config.sequence_length
        )
        
        # Load model and make predictions
        input_size = X.shape[-1]
        model = LSTMModel(
            input_size=input_size,
            hidden_size=128,
            num_layers=3,
            num_horizons=1,
            dropout=0.2,
            bidirectional=True
        ).to(self.device)
        
        model.load_state_dict(self.best_models[horizon])
        model.eval()
        
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            predictions = model(X_tensor).cpu().numpy().squeeze()
        
        return predictions
    
    def evaluate(self, 
                 mbo_df: pd.DataFrame,
                 horizon: int = 1) -> TrainingMetrics:
        """
        Evaluate model performance.
        
        Args:
            mbo_df: MBO dataframe
            horizon: Prediction horizon in minutes
            
        Returns:
            Training metrics
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before evaluation")
        
        # Create targets
        targets = self._create_targets(mbo_df)
        
        # Engineer features
        features_df = self.feature_engineer.process_mbo_dataframe(mbo_df)
        features_scaled = self.feature_scaler.transform(features_df)
        
        # Prepare sequences
        X, y = self._prepare_sequences(
            features_scaled, 
            targets[horizon].values, 
            self.config.sequence_length
        )
        
        # Make predictions
        predictions = self.predict(mbo_df, horizon)
        
        # Calculate metrics
        metrics = self._evaluate_horizon(horizon, X, y)
        
        # Create TrainingMetrics object
        return TrainingMetrics(
            train_rmse=metrics['rmse'],
            val_rmse=metrics['rmse'],
            test_rmse=metrics['rmse'],
            train_mae=metrics['mae'],
            val_mae=metrics['mae'],
            test_mae=metrics['mae'],
            train_r2=metrics['r2'],
            val_r2=metrics['r2'],
            test_r2=metrics['r2'],
            sharpe_ratio=metrics['sharpe_ratio'],
            max_drawdown=metrics['max_drawdown'],
            win_rate=metrics['win_rate'],
            profit_factor=metrics['profit_factor'],
            avg_win=metrics['avg_win'],
            avg_loss=metrics['avg_loss'],
            total_return=metrics['total_return'],
            volatility=metrics['volatility'],
            var_95=metrics['var_95'],
            cvar_95=metrics['cvar_95'],
            calmar_ratio=metrics['calmar_ratio'],
            sortino_ratio=metrics['sortino_ratio'],
            total_trades=metrics['total_trades'],
            profitable_trades=metrics['profitable_trades'],
            avg_trade_duration=0.0,  # Placeholder
            avg_trade_return=metrics['avg_win']
        )
    
    def save_model(self, filepath: str):
        """Save the complete model."""
        import joblib
        
        model_data = {
            'best_models': self.best_models,
            'feature_scaler': self.feature_scaler,
            'target_scaler': self.target_scaler,
            'training_history': self.training_history,
            'config': self.config,
            'feature_engineer': self.feature_engineer,
            'training_losses': self.training_losses,
            'validation_losses': self.validation_losses
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"LSTM model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a saved model."""
        import joblib
        
        model_data = joblib.load(filepath)
        
        self.best_models = model_data['best_models']
        self.feature_scaler = model_data['feature_scaler']
        self.target_scaler = model_data['target_scaler']
        self.training_history = model_data['training_history']
        self.feature_engineer = model_data['feature_engineer']
        self.training_losses = model_data['training_losses']
        self.validation_losses = model_data['validation_losses']
        
        self.is_trained = True
        logger.info(f"LSTM model loaded from {filepath}")
    
    def train(self, mbo_df: pd.DataFrame, validation_split: float = 0.2, 
              test_split: float = 0.1, random_state: int = 42, 
              progress_callback: Optional[Any] = None) -> Dict[str, Any]:
        """
        Train the LSTM model on MBO data.
        
        Args:
            mbo_df: MBO dataframe
            validation_split: Validation split ratio
            test_split: Test split ratio
            random_state: Random state for reproducibility
            
        Returns:
            Training results dictionary
        """
        try:
            logger.info("Starting LSTM model training...")
            start_time = datetime.now()
            
            # Update progress
            if progress_callback:
                progress_callback.on_phase_start("feature_engineering", "Engineering comprehensive order flow features...")
            
            # Engineer comprehensive features
            logger.info("Engineering comprehensive order flow features...")
            features_df = self.comprehensive_engineer.engineer_all_order_flow_features(mbo_df)
            
            # Add legacy features for backward compatibility
            logger.info("Adding legacy features for backward compatibility...")
            features_df = self._add_legacy_features(features_df, mbo_df)
            
            # Analyze feature importance while preserving ALL features
            self._analyze_feature_importance(features_df)
            
            logger.info(f"Comprehensive feature engineering complete. Total features: {len(features_df.columns)}")
            logger.info(f"Keeping ALL {len(features_df.columns)} features for model-driven alpha generation")
            
            # Create targets for different horizons
            targets = self._create_targets(features_df, mbo_df)
            
            # Scale features
            feature_columns = [col for col in features_df.columns 
                             if col not in ['timestamp', 'price'] and not any(f'target_{h}m' in col 
                                                                             for h in self.config.prediction_horizons)]
            
            self.feature_scaler = StandardScaler()
            features_scaled = self.feature_scaler.fit_transform(features_df[feature_columns])
            features_scaled_df = pd.DataFrame(features_scaled, columns=feature_columns, index=features_df.index)
            
            # Update progress
            if progress_callback:
                progress_callback.on_phase_start("model_training", f"Training {len(self.config.prediction_horizons)} LSTM models...")
            
            # Train models for each horizon
            results = {}
            for i, horizon in enumerate(self.config.prediction_horizons):
                logger.info(f"Training model for {horizon}m horizon...")
                
                # Update progress for each horizon
                if progress_callback:
                    progress_callback.on_phase_start("model_training", f"Training LSTM model {i+1}/{len(self.config.prediction_horizons)}: {horizon}m horizon")
                
                # Get target for this horizon
                target_col = f'price_change_{horizon}m'
                if target_col not in targets:
                    logger.warning(f"Target {target_col} not found, skipping horizon {horizon}")
                    continue
                
                target = targets[target_col]
                
                # Prepare sequences
                X, y = self._prepare_sequences(
                    features_scaled, 
                    target.values, 
                    self.config.sequence_length
                )
                
                # Split data
                split_idx = int(len(X) * (1 - validation_split - test_split))
                val_idx = int(len(X) * (1 - test_split))
                
                X_train, y_train = X[:split_idx], y[:split_idx]
                X_val, y_val = X[split_idx:val_idx], y[split_idx:val_idx]
                X_test, y_test = X[val_idx:], y[val_idx:]
                
                # Create data loaders
                train_loader, val_loader = self._create_data_loaders(
                    X_train, y_train, X_val, y_val, self.config.batch_size
                )
                
                # Initialize GPU trainer for this training session
                if self.gpu_trainer is None:
                    # Create a temporary model to get input size
                    temp_model = LSTMModel(
                        input_size=X_train.shape[-1],
                        hidden_size=getattr(self, 'lstm_params', {}).get('hidden_size', 256),
                        num_layers=getattr(self, 'lstm_params', {}).get('num_layers', 4),
                        num_horizons=1,
                        dropout=getattr(self, 'lstm_params', {}).get('dropout', 0.2)
                    )
                    
                    # Create temporary datasets
                    train_dataset = TensorDataset(
                        torch.FloatTensor(X_train), 
                        torch.FloatTensor(y_train)
                    )
                    val_dataset = TensorDataset(
                        torch.FloatTensor(X_val), 
                        torch.FloatTensor(y_val)
                    )
                    
                    self.gpu_trainer = GPUOptimizedTrainer(
                        model=temp_model,
                        train_dataset=train_dataset,
                        val_dataset=val_dataset,
                        learning_rate=getattr(self, 'lstm_params', {}).get('learning_rate', 0.001),
                        **self.gpu_config
                    )
                
                # Train the model with progress tracking
                train_results = self._train_single_horizon(
                    horizon, train_loader, val_loader, progress_callback
                )
                
                results[f'horizon_{horizon}m'] = train_results
            
            # Calculate overall metrics
            overall_metrics = self._calculate_overall_metrics(results)
            
            # Update training state
            self.is_trained = True
            self.training_metrics = results
            
            training_duration = (datetime.now() - start_time).total_seconds() / 60
            
            logger.info(f"LSTM training completed in {training_duration:.2f} minutes")
            
            return {
                'success': True,
                'results': results,
                'overall_metrics': overall_metrics,
                'training_duration_minutes': training_duration,
                'total_samples': len(features_df),
                'feature_count': len(feature_columns)
            }
            
        except Exception as e:
            logger.error(f"LSTM training failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_targets(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Create target variables for different horizons."""
        targets = {}
        
        # Get price data (prioritize features_df, then mbo_df, then generate dummy)
        if 'price' in features_df.columns:
            price_data = features_df['price']
        elif 'price' in mbo_df.columns:
            price_data = mbo_df['price']
        else:
            logger.warning("No price data found, generating dummy price data")
            price_data = pd.Series(np.random.randn(len(features_df)), index=features_df.index)
        
        # Create price change targets for different horizons
        for horizon in self.config.prediction_horizons:
            price_target = price_data.shift(-horizon * 60) / price_data - 1
            price_target = price_target.fillna(0)
            targets[f'price_change_{horizon}m'] = price_target
        
        return targets
    
    def _add_legacy_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add legacy features for backward compatibility."""
        try:
            # Add basic features that might be missing
            if 'price_direction' not in features_df.columns:
                features_df['price_direction'] = 0
            if 'price_direction_ma' not in features_df.columns:
                features_df['price_direction_ma'] = 0
            if 'momentum_1m' not in features_df.columns:
                features_df['momentum_1m'] = 0
            if 'momentum_5m' not in features_df.columns:
                features_df['momentum_5m'] = 0
            if 'momentum_15m' not in features_df.columns:
                features_df['momentum_15m'] = 0
            if 'volatility_1m' not in features_df.columns:
                features_df['volatility_1m'] = 0
            if 'volatility_5m' not in features_df.columns:
                features_df['volatility_5m'] = 0
            if 'trend_strength' not in features_df.columns:
                features_df['trend_strength'] = 0
            if 'trend_consistency' not in features_df.columns:
                features_df['trend_consistency'] = 0
                
        except Exception as e:
            logger.warning(f"Error adding legacy features: {e}")
        
        return features_df
    
    def _analyze_feature_importance(self, features_df: pd.DataFrame) -> None:
        """Analyze feature importance while preserving ALL features for model-driven alpha generation."""
        
        try:
            logger.info("🔍 Starting comprehensive feature importance analysis...")
            
            # Create target variables for analysis
            if 'price' in features_df.columns:
                # Create direction targets for different horizons
                for horizon in self.config.prediction_horizons:
                    target_col = f'direction_{horizon}m'
                    if target_col in features_df.columns:
                        # Prepare feature matrix (exclude target columns)
                        feature_cols = [col for col in features_df.columns 
                                       if not any(f'target_{h}m' in col or f'direction_{h}m' in col 
                                                for h in self.config.prediction_horizons)]
                        
                        X = features_df[feature_cols].fillna(0)
                        y = features_df[target_col].fillna(0)
                        
                        # Analyze feature importance
                        importance_results = self.feature_selector.analyze_feature_importance(
                            X, y, target_type='classification'
                        )
                        
                        logger.info(f"✅ Feature importance analysis completed for {horizon}m horizon")
                        logger.info(f"📊 Analyzed {len(feature_cols)} features")
                        
                        # Log top features but emphasize we keep ALL
                        top_features = importance_results['rankings'].get('lightgbm', [])[:10]
                        logger.info(f"🏆 Top 10 features for {horizon}m horizon: {top_features}")
                        logger.info(f"💡 Keeping ALL {len(feature_cols)} features for model-driven alpha generation")
            
            # Specialized order flow analysis
            self._analyze_order_flow_features(features_df)
            
        except Exception as e:
            logger.error(f"Error in feature importance analysis: {e}")
            logger.info("Continuing with all features as per QuantTime philosophy")
    
    def _analyze_order_flow_features(self, features_df: pd.DataFrame) -> None:
        """Specialized analysis of order flow features for comprehensive understanding."""
        
        try:
            logger.info("🌊 Analyzing comprehensive order flow features...")
            
            # Identify all order flow related features
            order_flow_keywords = [
                'volume', 'imbalance', 'absorption', 'iceberg', 'order_block',
                'bid', 'ask', 'spread', 'flow', 'pressure', 'momentum',
                'delta', 'gamma', 'theta', 'vega', 'greeks',
                'liquidity', 'depth', 'resistance', 'support',
                'breakout', 'breakdown', 'consolidation', 'accumulation',
                'distribution', 'divergence', 'convergence', 'momentum',
                'volatility', 'skew', 'kurtosis', 'correlation',
                'regime', 'regime_change', 'market_microstructure',
                'order_flow', 'trade_flow', 'institutional_flow',
                'retail_flow', 'smart_money', 'dumb_money',
                'alpha', 'beta', 'sharpe', 'sortino', 'calmar',
                'max_drawdown', 'var', 'cvar', 'expected_shortfall'
            ]
            
            order_flow_features = [
                col for col in features_df.columns 
                if any(keyword in col.lower() for keyword in order_flow_keywords)
            ]
            
            logger.info(f"Identified {len(order_flow_features)} order flow features")
            
            # Analyze order flow feature categories
            order_flow_categories = {
                'volume_analysis': [col for col in order_flow_features if 'volume' in col.lower()],
                'imbalance_analysis': [col for col in order_flow_features if 'imbalance' in col.lower()],
                'pattern_detection': [col for col in order_flow_features if any(x in col.lower() for x in ['pattern', 'detection', 'iceberg', 'absorption'])],
                'price_action': [col for col in order_flow_features if any(x in col.lower() for x in ['price', 'spread', 'bid', 'ask'])],
                'temporal_features': [col for col in order_flow_features if any(x in col.lower() for x in ['time', 'momentum', 'trend'])],
                'statistical_features': [col for col in order_flow_features if any(x in col.lower() for x in ['std', 'mean', 'skew', 'kurtosis', 'correlation'])],
                'market_microstructure': [col for col in order_flow_features if any(x in col.lower() for x in ['microstructure', 'liquidity', 'depth', 'flow'])],
                'regime_features': [col for col in order_flow_features if any(x in col.lower() for x in ['regime', 'state', 'condition'])],
                'risk_features': [col for col in order_flow_features if any(x in col.lower() for x in ['risk', 'var', 'drawdown', 'volatility'])]
            }
            
            # Log category breakdown
            for category, features in order_flow_categories.items():
                if features:
                    logger.info(f"{category}: {len(features)} features")
            
            # Store comprehensive order flow analysis
            self.order_flow_analysis = {
                'total_order_flow_features': len(order_flow_features),
                'feature_categories': order_flow_categories,
                'all_order_flow_features': order_flow_features,
                'analysis_timestamp': pd.Timestamp.now()
            }
            
            logger.info("Comprehensive order flow analysis completed")
            
        except Exception as e:
            logger.error(f"Error in order flow analysis: {e}")
            logger.info("Continuing with all order flow features")
    
    def _calculate_overall_metrics(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall training metrics."""
        if not results:
            return {}
        
        val_losses = [r.get('best_val_loss', float('inf')) for r in results.values()]
        train_losses = [r.get('final_train_loss', float('inf')) for r in results.values()]
        epochs = [r.get('epochs_trained', 0) for r in results.values()]
        
        return {
            'avg_val_loss': np.mean(val_losses),
            'avg_train_loss': np.mean(train_losses),
            'total_epochs': sum(epochs),
            'num_horizons': len(results)
        }


def create_lstm_model(**kwargs) -> MBOLSTMModel:
    """Factory function to create LSTM model."""
    # Filter out LSTM-specific parameters that aren't in ModelConfig
    model_config_params = {
        'model_type', 'prediction_horizons', 'orderbook_depth', 'sequence_length', 
        'feature_window', 'use_gpu', 'use_mixed_precision', 'max_gpu_memory_gb', 
        'max_ram_gb', 'batch_size', 'min_trade_duration_seconds', 'risk_management'
    }
    
    # Separate ModelConfig parameters from LSTM-specific parameters
    config_params = {k: v for k, v in kwargs.items() if k in model_config_params}
    lstm_params = {k: v for k, v in kwargs.items() if k not in model_config_params}
    
    # Ensure required parameters are provided
    if 'model_type' not in config_params:
        config_params['model_type'] = 'lstm'
    if 'prediction_horizons' not in config_params:
        config_params['prediction_horizons'] = [1, 2, 3]
    
    # Create ModelConfig with only valid parameters
    config = ModelConfig(**config_params)
    
    # Create model instance
    model = MBOLSTMModel(config)
    
    # Store LSTM-specific parameters for use during training
    model.lstm_params = lstm_params
    
    return model
