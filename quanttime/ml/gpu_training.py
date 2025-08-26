"""
GPU-Accelerated Training Module using Databento Data

This module provides GPU-accelerated training functionality for MBO data
using the official Databento Python library for data processing.
"""

import os
import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta

# Import PyTorch for GPU training
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    logging.warning("PyTorch not available. Install with: pip install torch")

# Import official Databento library
try:
    from databento import DBNStore, Historical, SType
    DATABENTO_AVAILABLE = True
except ImportError:
    DATABENTO_AVAILABLE = False
    logging.warning("Databento library not available. Install with: pip install databento")

# Import MBO processor
try:
    from quanttime.adapter.mbo_processor import process_mbo_for_training
    MBO_PROCESSOR_AVAILABLE = True
except ImportError:
    MBO_PROCESSOR_AVAILABLE = False
    logging.warning("MBO processor not available")

# Import scikit-learn for feature engineering
try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("Scikit-learn not available. Install with: pip install scikit-learn")

logger = logging.getLogger(__name__)


class MBOPricePredictor(nn.Module):
    """
    LSTM-based price prediction model using Databento MBO data with order book context.
    
    Features:
    - LSTM layers for sequence modeling
    - Attention mechanism for cumulative delta and order book analysis
    - Order book context integration (±100 points)
    - Cumulative delta divergence analysis
    - Dropout for regularization
    - GPU acceleration support
    """
    
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, 
                 dropout: float = 0.2, num_classes: int = 3, order_book_levels: int = 10):
        """
        Initialize the MBO Price Predictor.
        
        Args:
            input_size: Number of input features (including order book features)
            hidden_size: LSTM hidden layer size
            num_layers: Number of LSTM layers
            dropout: Dropout rate for regularization
            num_classes: Number of output classes (up, down, neutral)
            order_book_levels: Number of order book levels to consider
        """
        super(MBOPricePredictor, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.order_book_levels = order_book_levels
        
        # LSTM layers for sequence modeling
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True
        )
        
        # Attention mechanism for cumulative delta and order book analysis
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size * 2,  # Bidirectional
            num_heads=8,
            dropout=dropout,
            batch_first=True
        )
        
        # Order book attention (separate attention for order book features)
        self.order_book_attention = nn.MultiheadAttention(
            embed_dim=hidden_size * 2,
            num_heads=4,
            dropout=dropout,
            batch_first=True
        )
        
        # Cumulative delta analysis layer
        self.delta_analysis = nn.Linear(hidden_size * 2, hidden_size)
        
        # Output layers
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size * 3, hidden_size)  # Increased for order book context
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, num_classes)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights for better training."""
        for name, param in self.named_parameters():
            if 'weight' in name:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                nn.init.constant_(param, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the model with order book context.
        
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
               Includes price, volume, cumulative delta, and order book features
            
        Returns:
            Output tensor of shape (batch_size, num_classes)
        """
        # LSTM forward pass for sequence modeling
        lstm_out, _ = self.lstm(x)
        
        # Apply attention for general sequence analysis
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Apply order book specific attention
        ob_attn_out, _ = self.order_book_attention(attn_out, attn_out, attn_out)
        
        # Global average pooling
        pooled = torch.mean(attn_out, dim=1)
        ob_pooled = torch.mean(ob_attn_out, dim=1)
        
        # Cumulative delta analysis
        delta_features = self.delta_analysis(ob_pooled)
        
        # Combine features: general sequence + order book context + delta analysis
        combined = torch.cat([pooled, ob_pooled, delta_features], dim=1)
        
        # Fully connected layers
        out = self.dropout(combined)
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        
        return out


class GPUTrainingManager:
    """
    GPU training manager for MBO data using Databento library.
    
    Features:
    - Automatic GPU detection and utilization
    - Memory-efficient training with batching
    - Early stopping and model checkpointing
    - Comprehensive metrics tracking
    """
    
    def __init__(self, model: MBOPricePredictor, device: Optional[str] = None):
        """
        Initialize GPU Training Manager.
        
        Args:
            model: MBOPricePredictor model instance
            device: Device to use ('cuda', 'cpu', or None for auto-detection)
        """
        self.model = model
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        logger.info(f"Using device: {self.device}")
        
        # Move model to device
        self.model.to(self.device)
        
        # Training state
        self.train_losses = []
        self.val_losses = []
        self.train_accuracies = []
        self.val_accuracies = []
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        
        # Initialize optimizer and loss function
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001, weight_decay=1e-5)
        self.criterion = nn.CrossEntropyLoss()
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5, verbose=True
        )
    
    def train_epoch(self, train_loader: DataLoader) -> Tuple[float, float]:
        """
        Train for one epoch.
        
        Args:
            train_loader: Training data loader
            
        Returns:
            Tuple of (average_loss, accuracy)
        """
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for batch_idx, (data, targets) in enumerate(train_loader):
            # Move data to device
            data = data.to(self.device)
            targets = targets.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            outputs = self.model(data)
            loss = self.criterion(outputs, targets)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            # Calculate accuracy
            _, predicted = torch.max(outputs.data, 1)
            total += targets.size(0)
            correct += (predicted == targets).sum().item()
            total_loss += loss.item()
            
            # Log progress
            if batch_idx % 100 == 0:
                logger.info(f"Batch {batch_idx}/{len(train_loader)}, Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / len(train_loader)
        accuracy = 100 * correct / total
        
        return avg_loss, accuracy
    
    def validate(self, val_loader: DataLoader) -> Tuple[float, float]:
        """
        Validate the model.
        
        Args:
            val_loader: Validation data loader
            
        Returns:
            Tuple of (average_loss, accuracy)
        """
        self.model.eval()
        total_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for data, targets in val_loader:
                # Move data to device
                data = data.to(self.device)
                targets = targets.to(self.device)
                
                # Forward pass
                outputs = self.model(data)
                loss = self.criterion(outputs, targets)
                
                # Calculate accuracy
                _, predicted = torch.max(outputs.data, 1)
                total += targets.size(0)
                correct += (predicted == targets).sum().item()
                total_loss += loss.item()
        
        avg_loss = total_loss / len(val_loader)
        accuracy = 100 * correct / total
        
        return avg_loss, accuracy
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader, 
              epochs: int = 50, patience: int = 10) -> Dict[str, List[float]]:
        """
        Train the model with early stopping.
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            epochs: Maximum number of epochs
            patience: Early stopping patience
            
        Returns:
            Dictionary with training history
        """
        logger.info(f"Starting training for {epochs} epochs with patience {patience}")
        
        for epoch in range(epochs):
            # Train
            train_loss, train_acc = self.train_epoch(train_loader)
            
            # Validate
            val_loss, val_acc = self.validate(val_loader)
            
            # Update learning rate
            self.scheduler.step(val_loss)
            
            # Store metrics
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.train_accuracies.append(train_acc)
            self.val_accuracies.append(val_acc)
            
            # Log progress
            logger.info(f"Epoch {epoch+1}/{epochs}:")
            logger.info(f"  Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
            logger.info(f"  Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
            
            # Early stopping
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                # Save best model
                torch.save(self.model.state_dict(), 'best_mbo_model.pth')
                logger.info("New best model saved!")
            else:
                self.patience_counter += 1
                if self.patience_counter >= patience:
                    logger.info(f"Early stopping triggered after {epoch+1} epochs")
                    break
        
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'train_accuracies': self.train_accuracies,
            'val_accuracies': self.val_accuracies
        }


def prepare_mbo_features(df: pd.DataFrame, sequence_length: int = 60, max_price_distance: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare features from MBO data with order book context and cumulative delta.
    
    Args:
        df: DataFrame with MBO data from Databento
        sequence_length: Length of input sequences
        max_price_distance: Maximum price points to track in order book
        
    Returns:
        Tuple of (features, labels) as numpy arrays
    """
    if not MBO_PROCESSOR_AVAILABLE:
        logger.error("MBO processor not available for feature preparation")
        return np.array([]), np.array([])
    
    try:
        logger.info(f"Processing MBO data with {len(df)} records")
        
        # Process MBO data through the processor
        features_df = process_mbo_for_training(df, max_price_distance=max_price_distance)
        
        if len(features_df) == 0:
            logger.error("No features generated from MBO processor")
            return np.array([]), np.array([])
        
        logger.info(f"Generated {len(features_df)} training samples with {len(features_df.columns)} features")
        
        # Select feature columns (exclude timestamp and side)
        exclude_cols = ['timestamp', 'side']
        feature_columns = [col for col in features_df.columns if col not in exclude_cols]
        
        # Prepare features and labels
        features = features_df[feature_columns].values
        labels = []
        
        # Create labels (next price direction)
        for i in range(len(features_df) - 1):
            current_price = features_df['price'].iloc[i]
            next_price = features_df['price'].iloc[i + 1]
            price_change = (next_price - current_price) / current_price
            
            if price_change > 0.0001:  # Up (0.01% threshold)
                labels.append(0)
            elif price_change < -0.0001:  # Down
                labels.append(1)
            else:  # Neutral
                labels.append(2)
        
        # Remove the last row since we don't have a label for it
        features = features[:-1]
        labels = np.array(labels)
        
        # Create sequences
        X, y = [], []
        for i in range(len(features) - sequence_length):
            X.append(features[i:i + sequence_length])
            y.append(labels[i + sequence_length])
        
        X = np.array(X)
        y = np.array(y)
        
        # Normalize features
        scaler = StandardScaler()
        X_reshaped = X.reshape(-1, X.shape[-1])
        X_scaled = scaler.fit_transform(X_reshaped)
        X = X_scaled.reshape(X.shape)
        
        logger.info(f"Prepared {len(X)} sequences with {len(feature_columns)} features")
        logger.info(f"Label distribution: {np.bincount(y)}")
        logger.info(f"Feature columns: {feature_columns}")
        
        return X, y
        
    except Exception as e:
        logger.error(f"Error preparing MBO features: {e}")
        return np.array([]), np.array([])


def prepare_features(df: pd.DataFrame, sequence_length: int = 60) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepare features from OHLCV data using Databento timestamp fields.
    
    Args:
        df: DataFrame with OHLCV data from Databento
        sequence_length: Length of input sequences
        
    Returns:
        Tuple of (features, labels) as numpy arrays
    """
    if not SKLEARN_AVAILABLE:
        logger.error("Scikit-learn not available for feature preparation")
        return np.array([]), np.array([])
    
    try:
        # Ensure we have the required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns. Available: {list(df.columns)}")
            return np.array([]), np.array([])
        
        # Calculate technical indicators
        features_df = df.copy()
        
        # Price-based indicators
        features_df['price_change'] = features_df['close'].pct_change()
        features_df['high_low_ratio'] = features_df['high'] / features_df['low']
        features_df['close_open_ratio'] = features_df['close'] / features_df['open']
        
        # Moving averages
        features_df['sma_5'] = features_df['close'].rolling(5).mean()
        features_df['sma_10'] = features_df['close'].rolling(10).mean()
        features_df['sma_20'] = features_df['close'].rolling(20).mean()
        features_df['ema_12'] = features_df['close'].ewm(span=12).mean()
        features_df['ema_26'] = features_df['close'].ewm(span=26).mean()
        
        # Price relative to moving averages
        features_df['price_vs_sma_5'] = features_df['close'] / features_df['sma_5'] - 1
        features_df['price_vs_sma_10'] = features_df['close'] / features_df['sma_10'] - 1
        features_df['price_vs_sma_20'] = features_df['close'] / features_df['sma_20'] - 1
        
        # RSI
        delta = features_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        features_df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        features_df['macd'] = features_df['ema_12'] - features_df['ema_26']
        features_df['macd_signal'] = features_df['macd'].ewm(span=9).mean()
        features_df['macd_histogram'] = features_df['macd'] - features_df['macd_signal']
        
        # Bollinger Bands
        features_df['bb_middle'] = features_df['close'].rolling(20).mean()
        bb_std = features_df['close'].rolling(20).std()
        features_df['bb_upper'] = features_df['bb_middle'] + (bb_std * 2)
        features_df['bb_lower'] = features_df['bb_middle'] - (bb_std * 2)
        features_df['bb_position'] = (features_df['close'] - features_df['bb_lower']) / (features_df['bb_upper'] - features_df['bb_lower'])
        
        # Volume indicators
        features_df['volume_sma'] = features_df['volume'].rolling(20).mean()
        features_df['volume_ratio'] = features_df['volume'] / features_df['volume_sma']
        
        # Volatility
        features_df['volatility'] = features_df['close'].rolling(20).std()
        
        # Remove NaN values
        features_df = features_df.dropna()
        
        if len(features_df) < sequence_length + 1:
            logger.warning(f"Insufficient data: {len(features_df)} rows, need {sequence_length + 1}")
            return np.array([]), np.array([])
        
        # Select feature columns
        feature_columns = [
            'price_change', 'high_low_ratio', 'close_open_ratio',
            'price_vs_sma_5', 'price_vs_sma_10', 'price_vs_sma_20',
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'bb_position', 'volume_ratio', 'volatility'
        ]
        
        # Ensure all feature columns exist
        available_features = [col for col in feature_columns if col in features_df.columns]
        if len(available_features) < 10:
            logger.warning(f"Too few features available: {available_features}")
            return np.array([]), np.array([])
        
        # Prepare features and labels
        features = features_df[available_features].values
        labels = []
        
        # Create labels (next price direction)
        for i in range(len(features_df) - 1):
            next_return = features_df['price_change'].iloc[i + 1]
            if next_return > 0.001:  # Up
                labels.append(0)
            elif next_return < -0.001:  # Down
                labels.append(1)
            else:  # Neutral
                labels.append(2)
        
        # Remove the last row since we don't have a label for it
        features = features[:-1]
        labels = np.array(labels)
        
        # Create sequences
        X, y = [], []
        for i in range(len(features) - sequence_length):
            X.append(features[i:i + sequence_length])
            y.append(labels[i + sequence_length])
        
        X = np.array(X)
        y = np.array(y)
        
        # Normalize features
        scaler = StandardScaler()
        X_reshaped = X.reshape(-1, X.shape[-1])
        X_scaled = scaler.fit_transform(X_reshaped)
        X = X_scaled.reshape(X.shape)
        
        logger.info(f"Prepared {len(X)} sequences with {len(available_features)} features")
        logger.info(f"Label distribution: {np.bincount(y)}")
        
        return X, y
        
    except Exception as e:
        logger.error(f"Error preparing features: {e}")
        return np.array([]), np.array([])


def create_training_data_loader(X: np.ndarray, y: np.ndarray, 
                               batch_size: int = 32, train_ratio: float = 0.8) -> Tuple[DataLoader, DataLoader]:
    """
    Create training and validation data loaders.
    
    Args:
        X: Feature array
        y: Label array
        batch_size: Batch size for training
        train_ratio: Ratio of data to use for training
        
    Returns:
        Tuple of (train_loader, val_loader)
    """
    if not PYTORCH_AVAILABLE:
        logger.error("PyTorch not available for data loader creation")
        return None, None
    
    try:
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=1-train_ratio, random_state=42, stratify=y
        )
        
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train)
        y_train_tensor = torch.LongTensor(y_train)
        X_val_tensor = torch.FloatTensor(X_val)
        y_val_tensor = torch.LongTensor(y_val)
        
        # Create datasets
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
        
        # Create data loaders
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        logger.info(f"Created data loaders: {len(train_loader)} train batches, {len(val_loader)} val batches")
        
        return train_loader, val_loader
        
    except Exception as e:
        logger.error(f"Error creating data loaders: {e}")
        return None, None


def train_model_on_mbo_data(mbo_df: pd.DataFrame, sequence_length: int = 60, 
                           batch_size: int = 32, epochs: int = 50, max_price_distance: int = 100,
                           timeframe_filter: Optional[Any] = None, test_mode: bool = False) -> Optional[Dict[str, List[float]]]:
    """
    Train a model on MBO data with order book context and cumulative delta.
    
    Args:
        mbo_df: DataFrame with MBO data from Databento
        sequence_length: Length of input sequences
        batch_size: Batch size for training
        epochs: Number of training epochs
        max_price_distance: Maximum price points to track in order book
        
    Returns:
        Training results dictionary or None if failed
    """
    if not PYTORCH_AVAILABLE:
        logger.error("PyTorch not available for training")
        return None
    
    if not DATABENTO_AVAILABLE:
        logger.error("Databento library not available for data processing")
        return None
    
    try:
        logger.info("Starting GPU training on MBO data with order book context")
        
        # Apply timeframe filtering if provided
        if timeframe_filter is not None:
            logger.info(f"Applying timeframe filter: {timeframe_filter.tag}")
            from quanttime.utils.timeframe_filter import filter_mbo_data_by_timeframe
            mbo_df = filter_mbo_data_by_timeframe(mbo_df, timeframe_filter)
            logger.info(f"Filtered data: {len(mbo_df)} rows remaining")
        
        # Adjust parameters for test mode
        if test_mode:
            logger.info("Running in test mode with reduced parameters")
            epochs = min(epochs, 5)  # Max 5 epochs for testing
            batch_size = min(batch_size, 16)  # Smaller batch size for testing
            sequence_length = min(sequence_length, 30)  # Shorter sequences for testing
        
        # Prepare MBO features with order book context
        X, y = prepare_mbo_features(mbo_df, sequence_length, max_price_distance)
        
        if len(X) == 0:
            logger.error("No MBO features prepared")
            return None
        
        # Create data loaders
        train_loader, val_loader = create_training_data_loader(X, y, batch_size)
        
        if train_loader is None:
            logger.error("Failed to create data loaders")
            return None
        
        # Initialize model with order book context
        input_size = X.shape[2]
        model = MBOPricePredictor(input_size=input_size, order_book_levels=10)
        
        # Initialize training manager
        trainer = GPUTrainingManager(model)
        
        # Train model
        results = trainer.train(train_loader, val_loader, epochs=epochs)
        
        logger.info("MBO training completed successfully")
        return results
        
    except Exception as e:
        logger.error(f"Error during training: {e}")
        return None
