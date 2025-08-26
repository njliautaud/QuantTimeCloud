"""
Application configuration management.

Loads configuration from settings.txt file and environment variables.
Focused on Databento MBO data and multi-second to multi-minute trading strategies.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration with Databento focus."""
    
    # Databento Configuration
    databento_key: str = ""
    databento_dataset: str = "GLBX.MDP3"
    databento_symbol: str = "ES.FUT"
    databento_schema: str = "mbo"
    
    # Data Configuration
    data_dir: str = "./data/es_futures/mbo"
    live_stream_dir: str = "./data/live_streams"  # Added missing attribute
    backtest_dir: str = "./backtests"
    model_dir: str = "./models"
    log_dir: str = "./logs"
    
    # Database Configuration
    database_url: str = "sqlite:///quanttime.db"
    
    # Logging
    log_level: str = "INFO"
    
    # ZMQ Configuration
    zmq_pub_port: int = 5555
    zmq_sub_port: int = 5556
    zmq_rep_port: int = 5557
    
    # Live Trading Configuration
    live_trading_enabled: bool = False
    live_trading_account: str = "paper"
    live_trading_risk_limit: float = 1000.0
    
    # Model Configuration
    model_type: str = "lightgbm"
    model_prediction_horizons: List[int] = field(default_factory=lambda: [1, 3, 5])
    model_train_split_ratio: List[float] = field(default_factory=lambda: [0.6, 0.2, 0.2])
    model_session_split_seed: int = 42
    
    # Trading Strategy Configuration
    min_hold_time_seconds: int = 30
    max_hold_time_minutes: int = 30
    position_sizing_method: str = "fixed"
    risk_per_trade: float = 0.02
    commission_per_contract: float = 2.4
    slippage_ticks: float = 0.5
    
    # Chart Configuration
    chart_symbol: str = "ES.FUT"
    chart_source: str = "databento"
    chart_lookback_minutes: int = 60
    
    def __post_init__(self):
        """Load configuration from settings file and environment variables."""
        self._load_settings_file()
        self._load_env_vars()
    
    def _load_settings_file(self):
        """Load configuration from settings.txt file."""
        settings_file = Path("settings.txt")
        if not settings_file.exists():
            logger.warning("settings.txt not found, using defaults")
            return
        
        try:
            with open(settings_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Map settings to config fields
                        self._set_config_value(key, value)
                        
        except Exception as e:
            logger.error(f"Error loading settings.txt: {e}")
    
    def _load_env_vars(self):
        """Load configuration from environment variables."""
        env_mappings = {
            'DATABENTO_KEY': 'databento_key',
            'DATABENTO_DATASET': 'databento_dataset',
            'DATABENTO_SYMBOL': 'databento_symbol',
            'DATABENTO_SCHEMA': 'databento_schema',
            'DATA_DIR': 'data_dir',
            'LIVE_STREAM_DIR': 'live_stream_dir',  # Added missing mapping
            'BACKTEST_DIR': 'backtest_dir',
            'MODEL_DIR': 'model_dir',
            'LOG_DIR': 'log_dir',
            'LOG_LEVEL': 'log_level',
            'ZMQ_PUB_PORT': 'zmq_pub_port',
            'ZMQ_SUB_PORT': 'zmq_sub_port',
            'ZMQ_REP_PORT': 'zmq_rep_port',
            'LIVE_TRADING_ENABLED': 'live_trading_enabled',
            'LIVE_TRADING_ACCOUNT': 'live_trading_account',
            'LIVE_TRADING_RISK_LIMIT': 'live_trading_risk_limit',
            'MODEL_TYPE': 'model_type',
            'MODEL_PREDICTION_HORIZONS': 'model_prediction_horizons',
            'MODEL_TRAIN_SPLIT_RATIO': 'model_train_split_ratio',
            'MODEL_SESSION_SPLIT_SEED': 'model_session_split_seed',
            'MIN_HOLD_TIME_SECONDS': 'min_hold_time_seconds',
            'MAX_HOLD_TIME_MINUTES': 'max_hold_time_minutes',
            'POSITION_SIZING_METHOD': 'position_sizing_method',
            'RISK_PER_TRADE': 'risk_per_trade',
            'COMMISSION_PER_CONTRACT': 'commission_per_contract',
            'SLIPPAGE_TICKS': 'slippage_ticks',
            'CHART_SYMBOL': 'chart_symbol',
            'CHART_SOURCE': 'chart_source',
            'CHART_LOOKBACK_MINUTES': 'chart_lookback_minutes'
        }
        
        for env_key, config_key in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                self._set_config_value(env_key, env_value)
    
    def _set_config_value(self, key: str, value: str):
        """Set a configuration value from settings file."""
        if hasattr(self, key):
            # Convert value to appropriate type
            attr_type = type(getattr(self, key))
            if attr_type == bool:
                setattr(self, key, value.lower() in ('true', '1', 'yes', 'on'))
            elif attr_type == int:
                setattr(self, key, int(value))
            elif attr_type == float:
                setattr(self, key, float(value))
            elif attr_type == list:
                # Handle list values (comma-separated)
                if key == 'model_prediction_horizons':
                    setattr(self, key, [int(x.strip()) for x in value.split(',')])
                elif key == 'model_train_split_ratio':
                    setattr(self, key, [float(x.strip()) for x in value.split(',')])
                else:
                    setattr(self, key, [x.strip() for x in value.split(',')])
            else:
                setattr(self, key, value)


def ensure_data_dirs(cfg: AppConfig) -> None:
    """Ensure all required data directories exist."""
    dirs = [cfg.data_dir, cfg.live_stream_dir, cfg.backtest_dir, cfg.model_dir, cfg.log_dir]
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def get_databento_config(self) -> dict:
        """Get Databento configuration as dictionary."""
        return {
            'key': self.databento_key,
            'dataset': self.databento_dataset,
            'symbol': self.databento_symbol,
            'schema': self.databento_schema
        }
    
    def get_trading_config(self) -> dict:
        """Get trading configuration as dictionary."""
        return {
            'min_hold_time_seconds': self.min_hold_time_seconds,
            'max_hold_time_minutes': self.max_hold_time_minutes,
            'position_sizing_method': self.position_sizing_method,
            'risk_per_trade': self.risk_per_trade,
            'commission_per_contract': self.commission_per_contract,
            'slippage_ticks': self.slippage_ticks
        }
    
    def get_model_config(self) -> dict:
        """Get model configuration as dictionary."""
        return {
            'type': self.model_type,
            'prediction_horizons': self.model_prediction_horizons,
            'train_split_ratio': self.model_train_split_ratio,
            'session_split_seed': self.model_session_split_seed
        }
    
    def validate(self) -> bool:
        """Validate configuration."""
        errors = []
        
        if not self.databento_key:
            errors.append("DATABENTO_KEY is required")
        
        if not Path(self.data_dir).exists():
            errors.append(f"DATA_DIR does not exist: {self.data_dir}")
        
        if len(self.model_prediction_horizons) == 0:
            errors.append("MODEL_PREDICTION_HORIZONS must have at least one value")
        
        if len(self.model_train_split_ratio) != 3:
            errors.append("MODEL_TRAIN_SPLIT_RATIO must have exactly 3 values")
        
        if sum(self.model_train_split_ratio) != 1.0:
            errors.append("MODEL_TRAIN_SPLIT_RATIO values must sum to 1.0")
        
        if self.min_hold_time_seconds < 1:
            errors.append("MIN_HOLD_TIME_SECONDS must be at least 1")
        
        if self.max_hold_time_minutes < 1:
            errors.append("MAX_HOLD_TIME_MINUTES must be at least 1")
        
        if self.risk_per_trade <= 0 or self.risk_per_trade > 1:
            errors.append("RISK_PER_TRADE must be between 0 and 1")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False
        
        return True


