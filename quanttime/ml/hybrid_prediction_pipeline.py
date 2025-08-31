"""
Hybrid Prediction Pipeline for QuantTime
Combines feature engineering, multiple prediction models, and RL trade engine
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoModel, AutoTokenizer
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime, timedelta

# RL imports
import gym
from stable_baselines3 import PPO, SAC, TD3
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback
import optuna

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for individual models"""
    model_type: str  # 'transformer', 'lstm', 'lightgbm'
    model_name: str
    hyperparameters: Dict[str, Any]
    feature_columns: List[str]
    target_columns: List[str]
    sequence_length: int = 100
    prediction_horizon: int = 1
    use_engineered_features: bool = True
    use_raw_features: bool = True
    extract_intermediate_features: bool = False


@dataclass
class PipelineConfig:
    """Configuration for the entire pipeline"""
    pipeline_name: str
    models: List[ModelConfig]
    rl_config: Dict[str, Any]
    feature_engineering_config: Dict[str, Any]
    data_config: Dict[str, Any]
    training_config: Dict[str, Any]


class FeatureEngineer:
    """Advanced feature engineering from raw MBO data"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.scaler = StandardScaler()
        self.feature_names = []
        
    def engineer_features(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Engineer comprehensive features from raw MBO data"""
        logger.info("Engineering features from raw MBO data...")
        
        features = pd.DataFrame()
        
        # Basic price features
        features['mid_price'] = (raw_data['bid_price'] + raw_data['ask_price']) / 2
        features['spread'] = raw_data['ask_price'] - raw_data['bid_price']
        features['spread_bps'] = features['spread'] / features['mid_price'] * 10000
        
        # Volume features
        features['total_volume'] = raw_data['bid_size'] + raw_data['ask_size']
        features['volume_imbalance'] = raw_data['bid_size'] - raw_data['ask_size']
        features['volume_ratio'] = raw_data['bid_size'] / (raw_data['ask_size'] + 1e-8)
        
        # Price momentum features
        features['price_change'] = features['mid_price'].diff()
        features['price_change_pct'] = features['mid_price'].pct_change()
        features['price_acceleration'] = features['price_change'].diff()
        
        # Volume momentum features
        features['volume_change'] = features['total_volume'].diff()
        features['volume_change_pct'] = features['total_volume'].pct_change()
        
        # Order book depth features (if available)
        if 'depth_1_bid' in raw_data.columns:
            for i in range(1, 6):  # Top 5 levels
                features[f'depth_{i}_bid'] = raw_data[f'depth_{i}_bid']
                features[f'depth_{i}_ask'] = raw_data[f'depth_{i}_ask']
                features[f'depth_{i}_bid_size'] = raw_data[f'depth_{i}_bid_size']
                features[f'depth_{i}_ask_size'] = raw_data[f'depth_{i}_ask_size']
        
        # Technical indicators
        features['sma_5'] = features['mid_price'].rolling(5).mean()
        features['sma_20'] = features['mid_price'].rolling(20).mean()
        features['ema_12'] = features['mid_price'].ewm(span=12).mean()
        features['ema_26'] = features['mid_price'].ewm(span=26).mean()
        features['macd'] = features['ema_12'] - features['ema_26']
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # Volatility features
        features['volatility_5'] = features['price_change'].rolling(5).std()
        features['volatility_20'] = features['price_change'].rolling(20).std()
        features['realized_volatility'] = features['price_change'].rolling(20).apply(
            lambda x: np.sqrt(np.sum(x**2))
        )
        
        # Microstructure features
        features['tick_size'] = features['mid_price'] * 0.0001  # Approximate tick size
        features['price_levels'] = (features['mid_price'] / features['tick_size']).round()
        features['spread_ticks'] = (features['spread'] / features['tick_size']).round()
        
        # Time-based features
        features['hour'] = pd.to_datetime(raw_data.index).hour
        features['minute'] = pd.to_datetime(raw_data.index).minute
        features['day_of_week'] = pd.to_datetime(raw_data.index).dayofweek
        features['is_market_open'] = ((features['hour'] >= 9) & (features['hour'] < 16)).astype(int)
        
        # Lagged features
        for lag in [1, 2, 3, 5, 10]:
            features[f'price_lag_{lag}'] = features['mid_price'].shift(lag)
            features[f'volume_lag_{lag}'] = features['total_volume'].shift(lag)
            features[f'spread_lag_{lag}'] = features['spread'].shift(lag)
        
        # Rolling statistics
        for window in [5, 10, 20]:
            features[f'price_mean_{window}'] = features['mid_price'].rolling(window).mean()
            features[f'price_std_{window}'] = features['mid_price'].rolling(window).std()
            features[f'volume_mean_{window}'] = features['total_volume'].rolling(window).mean()
            features[f'spread_mean_{window}'] = features['spread'].rolling(window).mean()
        
        # Remove NaN values
        features = features.dropna()
        
        # Store feature names
        self.feature_names = features.columns.tolist()
        
        logger.info(f"Engineered {len(self.feature_names)} features")
        return features
    
    def normalize_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Normalize features using StandardScaler"""
        normalized = self.scaler.fit_transform(features)
        return pd.DataFrame(normalized, columns=features.columns, index=features.index)
    
    def save_scaler(self, path: str):
        """Save the fitted scaler"""
        joblib.dump(self.scaler, path)
    
    def load_scaler(self, path: str):
        """Load a fitted scaler"""
        self.scaler = joblib.load(path)


class TransformerPredictor(nn.Module):
    """Transformer model for time series prediction"""
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Model architecture
        self.input_dim = len(config.feature_columns)
        self.hidden_dim = config.hyperparameters.get('hidden_dim', 256)
        self.num_layers = config.hyperparameters.get('num_layers', 6)
        self.num_heads = config.hyperparameters.get('num_heads', 8)
        self.dropout = config.hyperparameters.get('dropout', 0.1)
        self.output_dim = len(config.target_columns)
        
        # Embedding layer
        self.input_embedding = nn.Linear(self.input_dim, self.hidden_dim)
        
        # Positional encoding
        self.pos_encoding = nn.Parameter(torch.randn(1000, self.hidden_dim))
        
        # Transformer layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.hidden_dim,
            nhead=self.num_heads,
            dim_feedforward=self.hidden_dim * 4,
            dropout=self.dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=self.num_layers)
        
        # Output layers
        self.output_projection = nn.Linear(self.hidden_dim, self.output_dim)
        
        # Attention weights storage for feature extraction
        self.attention_weights = None
        self.intermediate_features = None
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        
        # Input embedding
        x = self.input_embedding(x)
        
        # Add positional encoding
        pos_enc = self.pos_encoding[:seq_len].unsqueeze(0).expand(batch_size, -1, -1)
        x = x + pos_enc
        
        # Store intermediate features for extraction
        self.intermediate_features = []
        
        # Pass through transformer layers
        for i, layer in enumerate(self.transformer.layers):
            x = layer(x)
            if self.config.extract_intermediate_features:
                self.intermediate_features.append(x.detach())
        
        # Global average pooling
        x = x.mean(dim=1)
        
        # Output projection
        output = self.output_projection(x)
        
        return output
    
    def get_intermediate_features(self) -> List[torch.Tensor]:
        """Get intermediate features from transformer layers"""
        return self.intermediate_features if self.intermediate_features else []


class LSTMPredictor(nn.Module):
    """LSTM model for time series prediction"""
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Model architecture
        self.input_dim = len(config.feature_columns)
        self.hidden_dim = config.hyperparameters.get('hidden_dim', 128)
        self.num_layers = config.hyperparameters.get('num_layers', 2)
        self.dropout = config.hyperparameters.get('dropout', 0.2)
        self.output_dim = len(config.target_columns)
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=self.input_dim,
            hidden_size=self.hidden_dim,
            num_layers=self.num_layers,
            dropout=self.dropout if self.num_layers > 1 else 0,
            batch_first=True,
            bidirectional=True
        )
        
        # Output layers
        self.output_projection = nn.Linear(self.hidden_dim * 2, self.output_dim)
        
        # Hidden states storage for feature extraction
        self.hidden_states = None
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # LSTM forward pass
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Store hidden states for feature extraction
        if self.config.extract_intermediate_features:
            self.hidden_states = lstm_out.detach()
        
        # Take the last output
        last_output = lstm_out[:, -1, :]
        
        # Output projection
        output = self.output_projection(last_output)
        
        return output
    
    def get_intermediate_features(self) -> torch.Tensor:
        """Get intermediate features from LSTM hidden states"""
        return self.hidden_states if self.hidden_states is not None else torch.tensor([])


class LightGBMPredictor:
    """LightGBM model for prediction"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None
        self.feature_importance = None
    
    def train(self, X: pd.DataFrame, y: pd.DataFrame, 
              X_val: pd.DataFrame = None, y_val: pd.DataFrame = None):
        """Train LightGBM model"""
        logger.info(f"Training LightGBM model: {self.config.model_name}")
        
        # Prepare training data
        train_data = lgb.Dataset(X, label=y.iloc[:, 0])  # Use first target column
        
        # Validation data if provided
        valid_data = None
        if X_val is not None and y_val is not None:
            valid_data = lgb.Dataset(X_val, label=y_val.iloc[:, 0])
        
        # Training parameters
        params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': self.config.hyperparameters.get('num_leaves', 31),
            'learning_rate': self.config.hyperparameters.get('learning_rate', 0.05),
            'feature_fraction': self.config.hyperparameters.get('feature_fraction', 0.9),
            'bagging_fraction': self.config.hyperparameters.get('bagging_fraction', 0.8),
            'bagging_freq': self.config.hyperparameters.get('bagging_freq', 5),
            'verbose': -1
        }
        
        # Train model
        self.model = lgb.train(
            params,
            train_data,
            valid_sets=[valid_data] if valid_data else None,
            num_boost_round=self.config.hyperparameters.get('num_boost_round', 1000),
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
        )
        
        # Store feature importance
        self.feature_importance = self.model.feature_importance()
        
        logger.info(f"LightGBM training completed")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.predict(X)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance"""
        if self.feature_importance is None:
            return {}
        return dict(zip(self.config.feature_columns, self.feature_importance))


class TradingEnvironment(gym.Env):
    """Reinforcement Learning trading environment"""
    
    def __init__(self, data: pd.DataFrame, predictions: Dict[str, np.ndarray], config: Dict[str, Any]):
        super().__init__()
        
        self.data = data
        self.predictions = predictions
        self.config = config
        
        # Environment parameters
        self.initial_balance = config.get('initial_balance', 100000)
        self.commission_rate = config.get('commission_rate', 0.001)
        self.max_position_size = config.get('max_position_size', 0.1)
        
        # Action space: [position_size, action_type]
        # position_size: -1 to 1 (short to long)
        # action_type: 0 (hold), 1 (buy), 2 (sell)
        self.action_space = gym.spaces.Box(
            low=np.array([-1, 0]),
            high=np.array([1, 2]),
            dtype=np.float32
        )
        
        # Observation space: [price_features, prediction_features, portfolio_state]
        obs_dim = len(data.columns) + len(predictions) + 3  # +3 for balance, position, pnl
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32
        )
        
        # State variables
        self.reset()
    
    def reset(self):
        """Reset environment"""
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0
        self.total_pnl = 0
        self.trades = []
        
        return self._get_observation()
    
    def step(self, action):
        """Take action and return next state"""
        # Extract action components
        position_size = action[0]
        action_type = int(action[1])
        
        # Get current price
        current_price = self.data.iloc[self.current_step]['mid_price']
        
        # Execute trade
        reward = self._execute_trade(position_size, action_type, current_price)
        
        # Move to next step
        self.current_step += 1
        
        # Check if episode is done
        done = self.current_step >= len(self.data) - 1
        
        # Calculate new PnL
        if self.position != 0:
            price_change = current_price - self.trades[-1]['price']
            self.total_pnl = self.position * price_change
        
        return self._get_observation(), reward, done, {}
    
    def _execute_trade(self, position_size: float, action_type: int, current_price: float) -> float:
        """Execute trade and return reward"""
        old_position = self.position
        old_balance = self.balance
        
        # Calculate new position
        if action_type == 1:  # Buy
            new_position = position_size * self.max_position_size
        elif action_type == 2:  # Sell
            new_position = -position_size * self.max_position_size
        else:  # Hold
            new_position = self.position
        
        # Calculate trade size
        trade_size = new_position - old_position
        
        # Apply commission
        commission = abs(trade_size) * current_price * self.commission_rate
        
        # Update position and balance
        self.position = new_position
        self.balance -= trade_size * current_price + commission
        
        # Record trade
        if trade_size != 0:
            self.trades.append({
                'step': self.current_step,
                'price': current_price,
                'size': trade_size,
                'commission': commission
            })
        
        # Calculate reward (change in portfolio value)
        reward = (self.balance - old_balance) / self.initial_balance
        
        return reward
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation"""
        # Price features
        price_features = self.data.iloc[self.current_step].values
        
        # Prediction features
        pred_features = []
        for model_name, predictions in self.predictions.items():
            pred_features.append(predictions[self.current_step])
        pred_features = np.array(pred_features)
        
        # Portfolio state
        portfolio_state = np.array([
            self.balance / self.initial_balance,
            self.position,
            self.total_pnl / self.initial_balance
        ])
        
        # Combine all features
        observation = np.concatenate([price_features, pred_features, portfolio_state])
        
        return observation.astype(np.float32)


class RLTradeEngine:
    """
    Reinforcement Learning Trade Engine with Real-Time Latency Awareness
    
    This is where latency analysis, alpha decay, and competitive timing belongs!
    The RL engine makes real-time trading decisions based on:
    - Model predictions (from prediction models)
    - Current latency situation
    - Alpha decay calculations  
    - Competitive analysis
    - Real-time PnL tracking
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.env = None
        
        # Real-time latency tracking
        self.our_latency_ms = config.get('our_latency_ms', 2.0)
        self.databento_latency_ms = config.get('databento_latency_ms', 0.5) 
        self.alpha_half_life_ms = config.get('alpha_half_life_ms', 100.0)
        
        # Real-time state tracking
        self.current_position = {'side': 'flat', 'size': 0, 'entry_price': 0.0, 'entry_time': None}
        self.pnl_ticks = 0.0
        self.pnl_dollars = 0.0
        self.trade_history = []
        
        # Tick-based configuration (ES futures)
        self.tick_size = config.get('tick_size', 0.25)
        self.tick_value = config.get('tick_value', 12.50)  # $12.50 per tick for ES
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl_ticks = 0.0
        
        logger.info(f"RL Trade Engine initialized with {self.our_latency_ms}ms latency awareness")
        
    def create_environment(self, data: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> TradingEnvironment:
        """Create trading environment"""
        return TradingEnvironment(data, predictions, self.config)
    
    def train(self, env: TradingEnvironment, model_type: str = 'PPO'):
        """Train RL model"""
        logger.info(f"Training RL model: {model_type}")
        
        # Wrap environment
        env = DummyVecEnv([lambda: env])
        
        # Create model
        if model_type == 'PPO':
            self.model = PPO(
                "MlpPolicy",
                env,
                learning_rate=self.config.get('learning_rate', 0.0003),
                n_steps=self.config.get('n_steps', 2048),
                batch_size=self.config.get('batch_size', 64),
                n_epochs=self.config.get('n_epochs', 10),
                gamma=self.config.get('gamma', 0.99),
                verbose=1
            )
        elif model_type == 'SAC':
            self.model = SAC(
                "MlpPolicy",
                env,
                learning_rate=self.config.get('learning_rate', 0.0003),
                buffer_size=self.config.get('buffer_size', 1000000),
                learning_starts=self.config.get('learning_starts', 100),
                batch_size=self.config.get('batch_size', 256),
                verbose=1
            )
        
        # Train model
        self.model.learn(total_timesteps=self.config.get('total_timesteps', 100000))
        
        logger.info("RL training completed")
    
    def predict_action(self, observation: np.ndarray) -> np.ndarray:
        """Predict action for given observation"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        return self.model.predict(observation)[0]
    
    def save_model(self, path: str):
        """Save trained model"""
        if self.model is not None:
            self.model.save(path)
    
    def load_model(self, path: str):
        """Load trained model"""
        self.model = PPO.load(path)
    
    def calculate_alpha_remaining(self, prediction_time: float, current_time: float) -> float:
        """
        Calculate remaining alpha based on time elapsed and our latency
        
        Args:
            prediction_time: When the prediction was made (timestamp)
            current_time: Current time (timestamp)
            
        Returns:
            Alpha remaining as percentage (0-100)
        """
        # Calculate total elapsed time since prediction
        elapsed_ms = (current_time - prediction_time) * 1000  # Convert to ms
        
        # Add our processing latency
        total_latency_ms = elapsed_ms + self.our_latency_ms + self.databento_latency_ms
        
        # Calculate alpha decay (exponential)
        alpha_remaining = np.exp(-total_latency_ms / self.alpha_half_life_ms)
        
        return alpha_remaining * 100  # Return as percentage
    
    def should_trade_decision(self, 
                             predictions: Dict[str, float], 
                             current_price: float,
                             prediction_time: float,
                             current_time: float) -> Dict[str, Any]:
        """
        Real-time trading decision with latency awareness
        
        Args:
            predictions: Model predictions {'direction': float, 'confidence': float, ...}
            current_price: Current market price
            prediction_time: When prediction was made
            current_time: Current time
            
        Returns:
            Trading decision with reasoning
        """
        # Calculate alpha remaining
        alpha_remaining = self.calculate_alpha_remaining(prediction_time, current_time)
        
        # Calculate competitive window (time left before alpha decays significantly)
        elapsed_ms = (current_time - prediction_time) * 1000
        total_latency_ms = elapsed_ms + self.our_latency_ms + self.databento_latency_ms
        competitive_window_ms = max(0, self.alpha_half_life_ms - total_latency_ms)
        
        decision = {
            'should_trade': False,
            'action': 'hold',
            'size': 0,
            'confidence': 0.0,
            'alpha_remaining': alpha_remaining,
            'competitive_window_ms': competitive_window_ms,
            'reasoning': []
        }
        
        # Check if we have a position
        if self.current_position['side'] != 'flat':
            decision['reasoning'].append("Already have position")
            return decision
        
        # Alpha decay check - don't trade if too little alpha remains
        if alpha_remaining < 30:  # Less than 30% alpha remaining
            decision['reasoning'].append(f"Alpha decayed to {alpha_remaining:.1f}%")
            return decision
        
        # Competitive window check
        if competitive_window_ms < 10:  # Less than 10ms left
            decision['reasoning'].append(f"Competitive window too small: {competitive_window_ms:.1f}ms")
            return decision
        
        # Check prediction confidence
        prediction_confidence = predictions.get('confidence', 0.0)
        if prediction_confidence < 0.6:
            decision['reasoning'].append(f"Prediction confidence too low: {prediction_confidence:.2f}")
            return decision
        
        # Check direction strength
        direction = predictions.get('direction', 0.0)
        if abs(direction) < 0.3:
            decision['reasoning'].append(f"Direction signal too weak: {direction:.2f}")
            return decision
        
        # Decision to trade
        decision['should_trade'] = True
        decision['action'] = 'buy' if direction > 0 else 'sell'
        decision['size'] = 1  # Always 1 contract
        decision['confidence'] = prediction_confidence * (alpha_remaining / 100)  # Adjust for alpha decay
        decision['reasoning'].append(f"Trade approved: {alpha_remaining:.1f}% alpha remaining")
        
        return decision
    
    def execute_trade(self, 
                     decision: Dict[str, Any], 
                     current_price: float, 
                     timestamp: float) -> Dict[str, Any]:
        """
        Execute trade and update position with tick-based PnL tracking
        
        Args:
            decision: Trading decision from should_trade_decision()
            current_price: Current market price
            timestamp: Current timestamp
            
        Returns:
            Trade execution details
        """
        if not decision['should_trade']:
            return {'executed': False, 'reason': 'No trade decision'}
        
        # Execute the trade
        self.current_position = {
            'side': decision['action'],
            'size': decision['size'],
            'entry_price': current_price,
            'entry_time': timestamp
        }
        
        # Reset PnL for new position
        self.pnl_ticks = 0.0
        self.pnl_dollars = 0.0
        
        # Record trade
        trade_record = {
            'timestamp': timestamp,
            'action': decision['action'],
            'size': decision['size'],
            'price': current_price,
            'confidence': decision['confidence'],
            'alpha_remaining': decision['alpha_remaining'],
            'competitive_window_ms': decision['competitive_window_ms']
        }
        
        self.trade_history.append(trade_record)
        self.total_trades += 1
        
        logger.info(f"RL Trade executed: {decision['action']} {decision['size']} at {current_price:.2f}, "
                   f"Alpha: {decision['alpha_remaining']:.1f}%")
        
        return {
            'executed': True,
            'trade': trade_record,
            'position': self.current_position.copy()
        }
    
    def update_position_pnl(self, current_price: float) -> Dict[str, Any]:
        """
        Update position PnL with tick-based calculations
        
        Args:
            current_price: Current market price
            
        Returns:
            Updated position info with PnL
        """
        if self.current_position['side'] == 'flat':
            return {'has_position': False}
        
        entry_price = self.current_position['entry_price']
        side = self.current_position['side']
        
        # Calculate price difference
        if side == 'buy':
            price_diff = current_price - entry_price
        else:  # sell
            price_diff = entry_price - current_price
        
        # Convert to ticks and dollars
        self.pnl_ticks = price_diff / self.tick_size
        self.pnl_dollars = self.pnl_ticks * self.tick_value
        
        return {
            'has_position': True,
            'side': side,
            'size': self.current_position['size'],
            'entry_price': entry_price,
            'current_price': current_price,
            'unrealized_pnl_ticks': self.pnl_ticks,
            'unrealized_pnl_dollars': self.pnl_dollars,
            'price_diff': price_diff
        }
    
    def should_exit_position(self, 
                           current_price: float, 
                           timestamp: float,
                           stop_loss_ticks: float = 10.0,
                           take_profit_ticks: float = 20.0) -> Dict[str, Any]:
        """
        Determine if position should be exited
        
        Args:
            current_price: Current market price
            timestamp: Current timestamp
            stop_loss_ticks: Stop loss in ticks
            take_profit_ticks: Take profit in ticks
            
        Returns:
            Exit decision
        """
        if self.current_position['side'] == 'flat':
            return {'should_exit': False, 'reason': 'No position'}
        
        # Update PnL
        position_info = self.update_position_pnl(current_price)
        unrealized_pnl_ticks = position_info['unrealized_pnl_ticks']
        
        # Check stop loss
        if unrealized_pnl_ticks <= -stop_loss_ticks:
            return {
                'should_exit': True,
                'reason': 'stop_loss',
                'pnl_ticks': unrealized_pnl_ticks,
                'pnl_dollars': position_info['unrealized_pnl_dollars']
            }
        
        # Check take profit
        if unrealized_pnl_ticks >= take_profit_ticks:
            return {
                'should_exit': True,
                'reason': 'take_profit',
                'pnl_ticks': unrealized_pnl_ticks,
                'pnl_dollars': position_info['unrealized_pnl_dollars']
            }
        
        # Check time-based exit (if position held too long)
        time_held_ms = (timestamp - self.current_position['entry_time']) * 1000
        max_hold_time_ms = self.config.get('max_hold_time_ms', 60000)  # 1 minute default
        
        if time_held_ms > max_hold_time_ms:
            return {
                'should_exit': True,
                'reason': 'time_limit',
                'pnl_ticks': unrealized_pnl_ticks,
                'pnl_dollars': position_info['unrealized_pnl_dollars'],
                'time_held_ms': time_held_ms
            }
        
        return {'should_exit': False, 'reason': 'hold_position'}
    
    def close_position(self, current_price: float, timestamp: float, reason: str) -> Dict[str, Any]:
        """
        Close current position and update performance metrics
        
        Args:
            current_price: Exit price
            timestamp: Exit timestamp
            reason: Reason for exit
            
        Returns:
            Closed position details
        """
        if self.current_position['side'] == 'flat':
            return {'closed': False, 'reason': 'No position to close'}
        
        # Final PnL calculation
        position_info = self.update_position_pnl(current_price)
        realized_pnl_ticks = position_info['unrealized_pnl_ticks']
        realized_pnl_dollars = position_info['unrealized_pnl_dollars']
        
        # Record closed position
        closed_position = {
            'timestamp': timestamp,
            'action': 'close',
            'side': self.current_position['side'],
            'size': self.current_position['size'],
            'entry_price': self.current_position['entry_price'],
            'exit_price': current_price,
            'realized_pnl_ticks': realized_pnl_ticks,
            'realized_pnl_dollars': realized_pnl_dollars,
            'exit_reason': reason,
            'time_held_ms': (timestamp - self.current_position['entry_time']) * 1000
        }
        
        # Update performance metrics
        self.total_pnl_ticks += realized_pnl_ticks
        if realized_pnl_ticks > 0:
            self.winning_trades += 1
        
        # Reset position
        self.current_position = {'side': 'flat', 'size': 0, 'entry_price': 0.0, 'entry_time': None}
        self.pnl_ticks = 0.0
        self.pnl_dollars = 0.0
        
        logger.info(f"Position closed: {reason}, PnL: {realized_pnl_ticks:.1f} ticks (${realized_pnl_dollars:.2f})")
        
        return {
            'closed': True,
            'position': closed_position,
            'total_pnl_ticks': self.total_pnl_ticks,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
        }
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time performance metrics"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0,
            'total_pnl_ticks': self.total_pnl_ticks,
            'total_pnl_dollars': self.total_pnl_ticks * self.tick_value,
            'current_position': self.current_position.copy(),
            'unrealized_pnl_ticks': self.pnl_ticks,
            'unrealized_pnl_dollars': self.pnl_dollars,
            'our_latency_ms': self.our_latency_ms,
            'alpha_half_life_ms': self.alpha_half_life_ms
        }


class HybridPredictionPipeline:
    """Main pipeline combining all components"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.feature_engineer = FeatureEngineer(config.feature_engineering_config)
        self.models = {}
        self.rl_engine = RLTradeEngine(config.rl_config)
        self.predictions = {}
        
    def prepare_data(self, raw_data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare data for training"""
        logger.info("Preparing data for training...")
        
        # Engineer features
        engineered_features = self.feature_engineer.engineer_features(raw_data)
        normalized_features = self.feature_engineer.normalize_features(engineered_features)
        
        # Create targets (future price changes)
        targets = pd.DataFrame()
        for horizon in [1, 2, 3, 5, 10]:
            targets[f'price_change_{horizon}'] = normalized_features['mid_price'].shift(-horizon) - normalized_features['mid_price']
        
        # Remove NaN values
        valid_idx = normalized_features.dropna().index.intersection(targets.dropna().index)
        features = normalized_features.loc[valid_idx]
        targets = targets.loc[valid_idx]
        
        logger.info(f"Prepared {len(features)} samples with {len(features.columns)} features")
        
        return features, targets
    
    def train_models(self, features: pd.DataFrame, targets: pd.DataFrame):
        """Train all prediction models"""
        logger.info("Training prediction models...")
        
        # Split data
        train_idx, test_idx = train_test_split(
            features.index, test_size=0.2, shuffle=False
        )
        
        X_train = features.loc[train_idx]
        y_train = targets.loc[train_idx]
        X_test = features.loc[test_idx]
        y_test = targets.loc[test_idx]
        
        # Train each model
        for model_config in self.config.models:
            logger.info(f"Training {model_config.model_type}: {model_config.model_name}")
            
            if model_config.model_type == 'transformer':
                model = self._train_transformer(model_config, X_train, y_train, X_test, y_test)
            elif model_config.model_type == 'lstm':
                model = self._train_lstm(model_config, X_train, y_train, X_test, y_test)
            elif model_config.model_type == 'lightgbm':
                model = self._train_lightgbm(model_config, X_train, y_train, X_test, y_test)
            else:
                raise ValueError(f"Unknown model type: {model_config.model_type}")
            
            self.models[model_config.model_name] = model
    
    def _train_transformer(self, config: ModelConfig, X_train: pd.DataFrame, y_train: pd.DataFrame,
                          X_test: pd.DataFrame, y_test: pd.DataFrame) -> TransformerPredictor:
        """Train transformer model"""
        # Prepare data
        X_train_tensor = torch.FloatTensor(X_train.values)
        y_train_tensor = torch.FloatTensor(y_train.values)
        X_test_tensor = torch.FloatTensor(X_test.values)
        y_test_tensor = torch.FloatTensor(y_test.values)
        
        # Create sequences
        train_dataset = self._create_sequences(X_train_tensor, y_train_tensor, config.sequence_length)
        test_dataset = self._create_sequences(X_test_tensor, y_test_tensor, config.sequence_length)
        
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
        
        # Create model
        model = TransformerPredictor(config)
        optimizer = optim.Adam(model.parameters(), lr=config.hyperparameters.get('learning_rate', 0.001))
        criterion = nn.MSELoss()
        
        # Training loop
        num_epochs = config.hyperparameters.get('num_epochs', 50)
        for epoch in range(num_epochs):
            model.train()
            train_loss = 0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            # Validation
            model.eval()
            val_loss = 0
            with torch.no_grad():
                for batch_X, batch_y in test_loader:
                    outputs = model(batch_X)
                    val_loss += criterion(outputs, batch_y).item()
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: Train Loss: {train_loss/len(train_loader):.4f}, Val Loss: {val_loss/len(test_loader):.4f}")
        
        return model
    
    def _train_lstm(self, config: ModelConfig, X_train: pd.DataFrame, y_train: pd.DataFrame,
                    X_test: pd.DataFrame, y_test: pd.DataFrame) -> LSTMPredictor:
        """Train LSTM model"""
        # Similar to transformer training
        X_train_tensor = torch.FloatTensor(X_train.values)
        y_train_tensor = torch.FloatTensor(y_train.values)
        X_test_tensor = torch.FloatTensor(X_test.values)
        y_test_tensor = torch.FloatTensor(y_test.values)
        
        train_dataset = self._create_sequences(X_train_tensor, y_train_tensor, config.sequence_length)
        test_dataset = self._create_sequences(X_test_tensor, y_test_tensor, config.sequence_length)
        
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
        
        model = LSTMPredictor(config)
        optimizer = optim.Adam(model.parameters(), lr=config.hyperparameters.get('learning_rate', 0.001))
        criterion = nn.MSELoss()
        
        num_epochs = config.hyperparameters.get('num_epochs', 50)
        for epoch in range(num_epochs):
            model.train()
            train_loss = 0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            model.eval()
            val_loss = 0
            with torch.no_grad():
                for batch_X, batch_y in test_loader:
                    outputs = model(batch_X)
                    val_loss += criterion(outputs, batch_y).item()
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: Train Loss: {train_loss/len(train_loader):.4f}, Val Loss: {val_loss/len(test_loader):.4f}")
        
        return model
    
    def _train_lightgbm(self, config: ModelConfig, X_train: pd.DataFrame, y_train: pd.DataFrame,
                        X_test: pd.DataFrame, y_test: pd.DataFrame) -> LightGBMPredictor:
        """Train LightGBM model"""
        model = LightGBMPredictor(config)
        model.train(X_train, y_train, X_test, y_test)
        return model
    
    def _create_sequences(self, X: torch.Tensor, y: torch.Tensor, sequence_length: int) -> TensorDataset:
        """Create sequences for time series models"""
        sequences_X = []
        sequences_y = []
        
        for i in range(sequence_length, len(X)):
            sequences_X.append(X[i-sequence_length:i])
            sequences_y.append(y[i])
        
        return TensorDataset(torch.stack(sequences_X), torch.stack(sequences_y))
    
    def generate_predictions(self, features: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Generate predictions from all models"""
        logger.info("Generating predictions from all models...")
        
        predictions = {}
        
        for model_name, model in self.models.items():
            if isinstance(model, (TransformerPredictor, LSTMPredictor)):
                # Neural network models
                model.eval()
                with torch.no_grad():
                    X_tensor = torch.FloatTensor(features.values)
                    sequences = []
                    for i in range(model.config.sequence_length, len(X_tensor)):
                        sequences.append(X_tensor[i-model.config.sequence_length:i])
                    
                    if sequences:
                        batch_X = torch.stack(sequences)
                        outputs = model(batch_X)
                        pred = outputs.numpy()
                        
                        # Pad with zeros for initial sequence_length steps
                        full_pred = np.zeros((len(features), pred.shape[1]))
                        full_pred[model.config.sequence_length:] = pred
                        predictions[model_name] = full_pred
                    else:
                        predictions[model_name] = np.zeros((len(features), 1))
            
            elif isinstance(model, LightGBMPredictor):
                # LightGBM model
                pred = model.predict(features)
                predictions[model_name] = pred.reshape(-1, 1)
        
        self.predictions = predictions
        return predictions
    
    def train_rl_engine(self, features: pd.DataFrame, predictions: Dict[str, np.ndarray]):
        """Train the RL trade engine"""
        logger.info("Training RL trade engine...")
        
        # Create environment
        env = self.rl_engine.create_environment(features, predictions)
        
        # Train RL model
        self.rl_engine.train(env, model_type=self.config.rl_config.get('model_type', 'PPO'))
        
        logger.info("RL trade engine training completed")
    
    def run_backtest(self, features: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Run backtest using trained RL engine"""
        logger.info("Running backtest...")
        
        # Create environment
        env = self.rl_engine.create_environment(features, predictions)
        
        # Run episode
        obs = env.reset()
        done = False
        total_reward = 0
        actions = []
        
        while not done:
            action = self.rl_engine.predict_action(obs)
            obs, reward, done, _ = env.step(action)
            total_reward += reward
            actions.append(action)
        
        # Calculate performance metrics
        final_balance = env.balance
        total_return = (final_balance - env.initial_balance) / env.initial_balance
        sharpe_ratio = total_reward / (np.std(actions) + 1e-8)
        
        results = {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': final_balance,
            'total_trades': len(env.trades),
            'total_reward': total_reward,
            'trades': env.trades
        }
        
        logger.info(f"Backtest completed: Return: {total_return:.2%}, Sharpe: {sharpe_ratio:.2f}")
        
        return results
    
    def save_pipeline(self, path: str):
        """Save the entire pipeline"""
        pipeline_data = {
            'config': self.config,
            'feature_engineer': self.feature_engineer,
            'models': self.models,
            'rl_engine': self.rl_engine
        }
        
        # Save to directory
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save config
        with open(save_path / 'config.json', 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)
        
        # Save feature engineer
        self.feature_engineer.save_scaler(save_path / 'feature_scaler.pkl')
        
        # Save models
        for model_name, model in self.models.items():
            if isinstance(model, (TransformerPredictor, LSTMPredictor)):
                torch.save(model.state_dict(), save_path / f'{model_name}.pth')
            elif isinstance(model, LightGBMPredictor):
                joblib.dump(model, save_path / f'{model_name}.pkl')
        
        # Save RL engine
        if self.rl_engine.model is not None:
            self.rl_engine.save_model(save_path / 'rl_model')
        
        logger.info(f"Pipeline saved to {path}")
    
    def load_pipeline(self, path: str):
        """Load the entire pipeline"""
        load_path = Path(path)
        
        # Load config
        with open(load_path / 'config.json', 'r') as f:
            config_dict = json.load(f)
            self.config = PipelineConfig(**config_dict)
        
        # Load feature engineer
        self.feature_engineer.load_scaler(load_path / 'feature_scaler.pkl')
        
        # Load models
        for model_config in self.config.models:
            model_name = model_config.model_name
            if model_config.model_type == 'transformer':
                model = TransformerPredictor(model_config)
                model.load_state_dict(torch.load(load_path / f'{model_name}.pth'))
            elif model_config.model_type == 'lstm':
                model = LSTMPredictor(model_config)
                model.load_state_dict(torch.load(load_path / f'{model_name}.pth'))
            elif model_config.model_type == 'lightgbm':
                model = joblib.load(load_path / f'{model_name}.pkl')
            
            self.models[model_name] = model
        
        # Load RL engine
        if (load_path / 'rl_model').exists():
            self.rl_engine.load_model(load_path / 'rl_model')
        
        logger.info(f"Pipeline loaded from {path}")


def create_sample_pipeline_config() -> PipelineConfig:
    """Create a sample pipeline configuration"""
    
    # Model configurations
    transformer_config = ModelConfig(
        model_type='transformer',
        model_name='price_transformer',
        hyperparameters={
            'hidden_dim': 256,
            'num_layers': 6,
            'num_heads': 8,
            'dropout': 0.1,
            'learning_rate': 0.001,
            'num_epochs': 50
        },
        feature_columns=['mid_price', 'spread', 'total_volume', 'volume_imbalance'],
        target_columns=['price_change_1', 'price_change_2', 'price_change_3'],
        sequence_length=100,
        prediction_horizon=1,
        use_engineered_features=True,
        use_raw_features=True,
        extract_intermediate_features=True
    )
    
    lstm_config = ModelConfig(
        model_type='lstm',
        model_name='volume_lstm',
        hyperparameters={
            'hidden_dim': 128,
            'num_layers': 2,
            'dropout': 0.2,
            'learning_rate': 0.001,
            'num_epochs': 50
        },
        feature_columns=['total_volume', 'volume_imbalance', 'volume_change'],
        target_columns=['price_change_1', 'price_change_2'],
        sequence_length=50,
        prediction_horizon=1,
        use_engineered_features=True,
        use_raw_features=False,
        extract_intermediate_features=True
    )
    
    lightgbm_config = ModelConfig(
        model_type='lightgbm',
        model_name='ensemble_lightgbm',
        hyperparameters={
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'num_boost_round': 1000
        },
        feature_columns=['mid_price', 'spread', 'total_volume', 'sma_5', 'sma_20'],
        target_columns=['price_change_1'],
        sequence_length=1,
        prediction_horizon=1,
        use_engineered_features=True,
        use_raw_features=False,
        extract_intermediate_features=False
    )
    
    # RL configuration
    rl_config = {
        'model_type': 'PPO',
        'initial_balance': 100000,
        'commission_rate': 0.001,
        'max_position_size': 0.1,
        'learning_rate': 0.0003,
        'n_steps': 2048,
        'batch_size': 64,
        'n_epochs': 10,
        'gamma': 0.99,
        'total_timesteps': 100000
    }
    
    # Feature engineering configuration
    feature_engineering_config = {
        'include_technical_indicators': True,
        'include_microstructure_features': True,
        'include_time_features': True,
        'normalize_features': True
    }
    
    # Data configuration
    data_config = {
        'symbols': ['ES'],
        'timeframe': '1m',
        'date_range': '2024-01-01 to 2024-12-31',
        'features_to_include': ['price', 'volume', 'orderbook']
    }
    
    # Training configuration
    training_config = {
        'train_test_split': 0.8,
        'validation_split': 0.2,
        'random_seed': 42,
        'use_gpu': True
    }
    
    return PipelineConfig(
        pipeline_name='hybrid_prediction_pipeline',
        models=[transformer_config, lstm_config, lightgbm_config],
        rl_config=rl_config,
        feature_engineering_config=feature_engineering_config,
        data_config=data_config,
        training_config=training_config
    )


if __name__ == "__main__":
    # Example usage
    config = create_sample_pipeline_config()
    pipeline = HybridPredictionPipeline(config)
    
    # Load sample data (replace with actual data loading)
    # raw_data = load_mbo_data()
    # features, targets = pipeline.prepare_data(raw_data)
    # pipeline.train_models(features, targets)
    # predictions = pipeline.generate_predictions(features)
    # pipeline.train_rl_engine(features, predictions)
    # results = pipeline.run_backtest(features, predictions)
    # pipeline.save_pipeline('models/hybrid_pipeline')
