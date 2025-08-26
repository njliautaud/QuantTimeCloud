"""
Models package for QuantTime ML Trading Suite.

This package provides various model implementations for financial prediction.
"""

from .base import ModelBase, ModelConfig, TrainingMetrics
from .enhanced_mbo_lightgbm import create_enhanced_mbo_lightgbm_model, EnhancedMBOLightGBMModel
from .lstm_model import create_lstm_model, MBOLSTMModel
from .transformer_model import create_transformer_model, MBOTransformerModel
from .trade_engine import TradeEngine, TradeEngineConfig, create_trade_engine

# Legacy imports for backward compatibility
try:
    from .lgbm_tabular import LightGBMTabularModel
    LGBMModel = LightGBMTabularModel
except ImportError:
    LGBMModel = None

try:
    from .mbo_lightgbm_model import MBOLightGBMModel
except ImportError:
    MBOLightGBMModel = None

# Model factories for dynamic creation
MODEL_FACTORIES = {
    'lightgbm': create_enhanced_mbo_lightgbm_model,
    'lstm': create_lstm_model,
    'transformer': create_transformer_model
}

def create_model(model_type: str, **kwargs) -> ModelBase:
    """
    Factory function to create models by type.
    
    Args:
        model_type: Type of model to create ('lightgbm', 'lstm', 'transformer')
        **kwargs: Model configuration parameters
        
    Returns:
        Model instance
    """
    if model_type not in MODEL_FACTORIES:
        raise ValueError(f"Unknown model type: {model_type}. Available: {list(MODEL_FACTORIES.keys())}")
    
    return MODEL_FACTORIES[model_type](**kwargs)

__all__ = [
    'ModelBase',
    'ModelConfig', 
    'TrainingMetrics',
    'EnhancedMBOLightGBMModel',
    'create_enhanced_mbo_lightgbm_model',
    'MBOLSTMModel',
    'create_lstm_model',
    'MBOTransformerModel',
    'create_transformer_model',
    'TradeEngine',
    'TradeEngineConfig',
    'create_trade_engine',
    'create_model',
    'MODEL_FACTORIES'
]



