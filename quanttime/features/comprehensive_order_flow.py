"""
Comprehensive Order Flow Feature Engineering for QuantTime

This module implements ALL possible order flow concepts and features that could be predictive
of price movements. The philosophy is to give models ALL available information and let them
determine what's actually predictive through training.

Core Principle: Model-Driven Alpha Generation
- Models determine their own alpha using all available data
- No manual feature selection or removal
- Comprehensive order flow understanding
- Full market microstructure analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass
from scipy import stats
from scipy.signal import savgol_filter
# Note: This module uses pandas methods for technical indicators instead of talib
# All calculations are done using pandas rolling(), ewm(), and other built-in methods

logger = logging.getLogger(__name__)


@dataclass
class OrderFlowConfig:
    """Configuration for comprehensive order flow feature engineering."""
    
    # Time windows for analysis
    short_windows: List[int] = None  # 1, 5, 15 minutes
    medium_windows: List[int] = None  # 30, 60, 120 minutes
    long_windows: List[int] = None   # 240, 480, 1440 minutes (daily)
    
    # Order book depth
    orderbook_depth: int = 10
    
    # Feature categories to include
    include_volume_analysis: bool = True
    include_imbalance_analysis: bool = True
    include_pattern_detection: bool = True
    include_microstructure: bool = True
    include_regime_analysis: bool = True
    include_risk_metrics: bool = True
    include_statistical_features: bool = True
    include_temporal_features: bool = True
    include_cross_features: bool = True
    
    # Advanced features
    include_greeks: bool = True
    include_liquidity_metrics: bool = True
    include_momentum_features: bool = True
    include_divergence_features: bool = True
    
    def __post_init__(self):
        if self.short_windows is None:
            self.short_windows = [1, 5, 15]
        if self.medium_windows is None:
            self.medium_windows = [30, 60, 120]
        if self.long_windows is None:
            self.long_windows = [240, 480, 1440]


class ComprehensiveOrderFlowEngineer:
    """
    Comprehensive order flow feature engineer that captures ALL possible concepts.
    
    Philosophy: Give models ALL available information and let them determine what's predictive.
    """
    
    def __init__(self, config: OrderFlowConfig = None):
        self.config = config or OrderFlowConfig()
        self.feature_categories = {}
        
    def engineer_all_order_flow_features(self, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer ALL possible order flow features for comprehensive analysis.
        
        Args:
            mbo_df: MBO dataframe with order book events
            
        Returns:
            DataFrame with comprehensive order flow features
        """
        
        logger.info("Starting comprehensive order flow feature engineering...")
        
        features_df = pd.DataFrame(index=mbo_df.index)
        
        try:
            # 1. Basic Order Flow Features
            if self.config.include_volume_analysis:
                features_df = self._add_volume_analysis_features(features_df, mbo_df)
            
            if self.config.include_imbalance_analysis:
                features_df = self._add_imbalance_analysis_features(features_df, mbo_df)
            
            if self.config.include_pattern_detection:
                features_df = self._add_pattern_detection_features(features_df, mbo_df)
            
            # 2. Market Microstructure Features
            if self.config.include_microstructure:
                features_df = self._add_microstructure_features(features_df, mbo_df)
            
            # 3. Regime Analysis Features
            if self.config.include_regime_analysis:
                features_df = self._add_regime_analysis_features(features_df, mbo_df)
            
            # 4. Risk Metrics
            if self.config.include_risk_metrics:
                features_df = self._add_risk_metrics_features(features_df, mbo_df)
            
            # 5. Statistical Features
            if self.config.include_statistical_features:
                features_df = self._add_statistical_features(features_df, mbo_df)
            
            # 6. Temporal Features
            if self.config.include_temporal_features:
                features_df = self._add_temporal_features(features_df, mbo_df)
            
            # 7. Advanced Features
            if self.config.include_greeks:
                features_df = self._add_greeks_features(features_df, mbo_df)
            
            if self.config.include_liquidity_metrics:
                features_df = self._add_liquidity_features(features_df, mbo_df)
            
            if self.config.include_momentum_features:
                features_df = self._add_momentum_features(features_df, mbo_df)
            
            if self.config.include_divergence_features:
                features_df = self._add_divergence_features(features_df, mbo_df)
            
            # 8. Cross Features (interactions between different feature types)
            if self.config.include_cross_features:
                features_df = self._add_cross_features(features_df)
            
            # 9. Multi-timeframe Analysis
            features_df = self._add_multi_timeframe_features(features_df, mbo_df)
            
            # 10. Order Flow Intelligence Features
            features_df = self._add_order_flow_intelligence_features(features_df, mbo_df)
            
            logger.info(f"Comprehensive order flow engineering completed. Total features: {len(features_df.columns)}")
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error in comprehensive order flow engineering: {e}")
            return features_df
    
    def _add_volume_analysis_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive volume analysis features."""
        
        logger.info("Adding volume analysis features...")
        
        # Basic volume features
        if 'size' in mbo_df.columns:
            features_df['volume'] = mbo_df['size']
            features_df['volume_ma'] = features_df['volume'].rolling(window=20).mean()
            features_df['volume_std'] = features_df['volume'].rolling(window=20).std()
            features_df['volume_ratio'] = features_df['volume'] / features_df['volume_ma']
            
            # Volume by side
            if 'side' in mbo_df.columns:
                buy_volume = mbo_df[mbo_df['side'] == 'B']['size'].fillna(0)
                sell_volume = mbo_df[mbo_df['side'] == 'A']['size'].fillna(0)
                
                features_df['buy_volume'] = buy_volume
                features_df['sell_volume'] = sell_volume
                features_df['buy_volume_ma'] = features_df['buy_volume'].rolling(window=20).mean()
                features_df['sell_volume_ma'] = features_df['sell_volume'].rolling(window=20).mean()
                features_df['buy_sell_ratio'] = features_df['buy_volume'] / (features_df['sell_volume'] + 1e-8)
        
        # Volume profile features
        features_df['volume_profile_skew'] = features_df['volume'].rolling(window=100).apply(
            lambda x: stats.skew(x) if len(x) > 2 and x.var() > 1e-10 else 0
        )
        features_df['volume_profile_kurtosis'] = features_df['volume'].rolling(window=100).apply(
            lambda x: stats.kurtosis(x) if len(x) > 2 and x.var() > 1e-10 else 0
        )
        
        # Volume momentum
        for window in self.config.short_windows:
            features_df[f'volume_momentum_{window}m'] = features_df['volume'].pct_change(window, fill_method=None)
            features_df[f'volume_acceleration_{window}m'] = features_df[f'volume_momentum_{window}m'].pct_change(fill_method=None)
        
        # Volume volatility
        for window in self.config.medium_windows:
            features_df[f'volume_volatility_{window}m'] = features_df['volume'].rolling(window).std()
        
        return features_df
    
    def _add_imbalance_analysis_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive imbalance analysis features."""
        
        logger.info("Adding imbalance analysis features...")
        
        # Volume imbalance
        if 'buy_volume' in features_df.columns and 'sell_volume' in features_df.columns:
            features_df['volume_imbalance'] = (features_df['buy_volume'] - features_df['sell_volume']) / (features_df['buy_volume'] + features_df['sell_volume'] + 1e-8)
            features_df['volume_imbalance_ma'] = features_df['volume_imbalance'].rolling(window=20).mean()
            features_df['volume_imbalance_std'] = features_df['volume_imbalance'].rolling(window=20).std()
            
            # Imbalance momentum
            for window in self.config.short_windows:
                features_df[f'volume_imbalance_momentum_{window}m'] = features_df['volume_imbalance'].pct_change(window, fill_method=None)
        
        # Price imbalance (if price data available)
        if 'price' in mbo_df.columns:
            features_df['price_imbalance'] = mbo_df['price'].pct_change(fill_method=None)
            features_df['price_imbalance_ma'] = features_df['price_imbalance'].rolling(window=20).mean()
            
            # Price-volume imbalance
            features_df['price_volume_imbalance'] = features_df['price_imbalance'] * features_df['volume_imbalance']
        
        # Order flow imbalance
        if 'side' in mbo_df.columns:
            buy_orders = (mbo_df['side'] == 'B').astype(int)
            sell_orders = (mbo_df['side'] == 'A').astype(int)
            
            features_df['order_flow_imbalance'] = buy_orders - sell_orders
            features_df['order_flow_imbalance_ma'] = features_df['order_flow_imbalance'].rolling(window=20).mean()
        
        return features_df
    
    def _add_pattern_detection_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive pattern detection features."""
        
        logger.info("Adding pattern detection features...")
        
        # Iceberg order detection
        if 'size' in mbo_df.columns:
            large_order_threshold = mbo_df['size'].rolling(window=100).quantile(0.95)
            features_df['iceberg_detection'] = (mbo_df['size'] > large_order_threshold).astype(int)
            
            # Iceberg persistence and confidence
            features_df['iceberg_persistence'] = features_df['iceberg_detection'].rolling(window=10).sum()
            features_df['iceberg_confidence'] = features_df['iceberg_detection'] * (mbo_df['size'] / large_order_threshold)
        
        # Absorption pattern detection
        if 'price' in mbo_df.columns and 'size' in mbo_df.columns:
            # Large volume with small price change indicates absorption
            price_change = mbo_df['price'].pct_change(fill_method=None).abs()
            volume_ratio = features_df['volume'] / features_df['volume_ma']
            
            features_df['absorption_detection'] = ((volume_ratio > 2) & (price_change < 0.001)).astype(int)
            features_df['absorption_intensity'] = volume_ratio * (1 - price_change)
            features_df['absorption_confidence'] = features_df['absorption_detection'] * features_df['absorption_intensity']
        
        # Order block detection
        if 'price' in mbo_df.columns:
            # Identify areas of high order concentration
            price_levels = mbo_df['price'].round(2)
            level_volume = mbo_df.groupby(price_levels)['size'].sum()
            features_df['order_block_volume'] = price_levels.map(level_volume)
            features_df['order_block_detection'] = (features_df['order_block_volume'] > features_df['order_block_volume'].rolling(window=50).quantile(0.9)).astype(int)
            features_df['order_block_confidence'] = features_df['order_block_detection'] * (features_df['order_block_volume'] / features_df['order_block_volume'].rolling(window=50).max())
        
        # Support/Resistance detection
        if 'price' in mbo_df.columns:
            try:
                # Identify price levels with high volume
                price_bins = pd.cut(mbo_df['price'], bins=50)
                bin_volume = mbo_df.groupby(price_bins, observed=True)['size'].sum()
                features_df['support_resistance_volume'] = price_bins.map(bin_volume)
                features_df['support_resistance_detection'] = (features_df['support_resistance_volume'] > features_df['support_resistance_volume'].rolling(window=100).quantile(0.95)).astype(int)
            except Exception as e:
                logger.warning(f"Could not process support/resistance detection: {e}")
                features_df['support_resistance_volume'] = 0.0
                features_df['support_resistance_detection'] = 0
        
        return features_df
    
    def _add_microstructure_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features."""
        
        logger.info("Adding microstructure features...")
        
        # Bid-ask spread (if available)
        if 'price' in mbo_df.columns:
            # Estimate spread from price movements
            price_changes = mbo_df['price'].pct_change(fill_method=None).abs()
            features_df['estimated_spread'] = price_changes.rolling(window=20).mean()
            features_df['spread_volatility'] = price_changes.rolling(window=20).std()
        
        # Order book depth
        if 'size' in mbo_df.columns:
            features_df['order_book_depth'] = features_df['volume'].rolling(window=10).sum()
            features_df['depth_imbalance'] = features_df['order_book_depth'].pct_change(fill_method=None)
        
        # Market impact
        if 'price' in mbo_df.columns and 'size' in mbo_df.columns:
            price_impact = mbo_df['price'].pct_change(fill_method=None).abs()
            volume_impact = features_df['volume'] / features_df['volume'].rolling(window=100).max()
            features_df['market_impact'] = price_impact / (volume_impact + 1e-8)
        
        # Liquidity measures
        features_df['liquidity_ratio'] = features_df['volume'] / (features_df['estimated_spread'] + 1e-8)
        features_df['liquidity_ma'] = features_df['liquidity_ratio'].rolling(window=20).mean()
        
        # Order flow toxicity
        if 'side' in mbo_df.columns:
            # Measure of adverse selection
            side_changes = mbo_df['side'].ne(mbo_df['side'].shift()).astype(int)
            features_df['order_flow_toxicity'] = side_changes.rolling(window=50).mean()
        
        return features_df
    
    def _add_regime_analysis_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add regime analysis features."""
        
        logger.info("Adding regime analysis features...")
        
        # Volatility regime
        if 'price' in mbo_df.columns:
            price_volatility = mbo_df['price'].pct_change(fill_method=None).rolling(window=20).std()
            features_df['volatility_regime'] = pd.qcut(price_volatility, q=5, labels=False, duplicates='drop')
            
            # Regime change detection
            features_df['regime_change'] = features_df['volatility_regime'].diff().abs()
        
        # Volume regime
        volume_regime = pd.qcut(features_df['volume'], q=5, labels=False, duplicates='drop')
        features_df['volume_regime'] = volume_regime
        features_df['volume_regime_change'] = features_df['volume_regime'].diff().abs()
        
        # Market state features
        features_df['market_state'] = features_df['volatility_regime'] + features_df['volume_regime']
        features_df['state_persistence'] = features_df['market_state'].rolling(window=50).apply(
            lambda x: len(x) - len(x.unique()) if len(x) > 0 else 0
        )
        
        # Regime momentum
        for window in self.config.medium_windows:
            features_df[f'regime_momentum_{window}m'] = features_df['market_state'].rolling(window).mean()
        
        return features_df
    
    def _add_risk_metrics_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive risk metrics features."""
        
        logger.info("Adding risk metrics features...")
        
        # Value at Risk (VaR)
        if 'price' in mbo_df.columns:
            returns = mbo_df['price'].pct_change(fill_method=None)
            for confidence in [0.95, 0.99]:
                features_df[f'var_{int(confidence*100)}'] = returns.rolling(window=100).quantile(1-confidence)
        
        # Expected Shortfall (CVaR)
        for confidence in [0.95, 0.99]:
            features_df[f'cvar_{int(confidence*100)}'] = returns.rolling(window=100).apply(
                lambda x: x[x <= x.quantile(1-confidence)].mean() if len(x) > 0 else 0
            )
        
        # Maximum Drawdown
        if 'price' in mbo_df.columns:
            rolling_max = mbo_df['price'].rolling(window=100).max()
            features_df['drawdown'] = (mbo_df['price'] - rolling_max) / rolling_max
            features_df['max_drawdown'] = features_df['drawdown'].rolling(window=100).min()
        
        # Volatility measures
        for window in [20, 50, 100]:
            features_df[f'volatility_{window}'] = returns.rolling(window).std()
            features_df[f'volatility_of_volatility_{window}'] = features_df[f'volatility_{window}'].rolling(window).std()
        
        # Skewness and Kurtosis
        features_df['returns_skew'] = returns.rolling(window=100).apply(
            lambda x: stats.skew(x) if len(x) > 2 and x.var() > 1e-10 else 0
        )
        features_df['returns_kurtosis'] = returns.rolling(window=100).apply(
            lambda x: stats.kurtosis(x) if len(x) > 2 and x.var() > 1e-10 else 0
        )
        
        return features_df
    
    def _add_statistical_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive statistical features."""
        
        logger.info("Adding statistical features...")
        
        # Moving averages and standard deviations
        for window in self.config.short_windows + self.config.medium_windows:
            if 'price' in mbo_df.columns:
                features_df[f'price_ma_{window}m'] = mbo_df['price'].rolling(window).mean()
                features_df[f'price_std_{window}m'] = mbo_df['price'].rolling(window).std()
                features_df[f'price_zscore_{window}m'] = (mbo_df['price'] - features_df[f'price_ma_{window}m']) / features_df[f'price_std_{window}m']
            
            if 'volume' in features_df.columns:
                features_df[f'volume_ma_{window}m'] = features_df['volume'].rolling(window).mean()
                features_df[f'volume_std_{window}m'] = features_df['volume'].rolling(window).std()
                features_df[f'volume_zscore_{window}m'] = (features_df['volume'] - features_df[f'volume_ma_{window}m']) / features_df[f'volume_std_{window}m']
        
        # Correlation features
        if 'price' in mbo_df.columns and 'volume' in features_df.columns:
            for window in [20, 50, 100]:
                features_df[f'price_volume_corr_{window}'] = mbo_df['price'].rolling(window).corr(features_df['volume'])
        
        # Autocorrelation features
        if 'price' in mbo_df.columns:
            for lag in [1, 5, 10]:
                features_df[f'price_autocorr_lag_{lag}'] = mbo_df['price'].rolling(window=50).apply(
                    lambda x: x.autocorr(lag=lag) if len(x) > lag else 0
                )
        
        # Entropy measures
        if 'price' in mbo_df.columns:
            features_df['price_entropy'] = mbo_df['price'].rolling(window=20).apply(
                lambda x: stats.entropy(np.histogram(x, bins=10)[0]) if len(x) > 0 else 0
            )
        
        return features_df
    
    def _add_temporal_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add temporal and time-based features."""
        
        logger.info("Adding temporal features...")
        
        # Time-based features
        if 'ts_event' in mbo_df.columns:
            try:
                # Convert timestamps to datetime
                timestamps = pd.to_datetime(mbo_df['ts_event'], unit='ns')
                
                # Time of day features
                features_df['hour_of_day'] = timestamps.dt.hour
                features_df['minute_of_hour'] = timestamps.dt.minute
                features_df['day_of_week'] = timestamps.dt.dayofweek
                
                # Cyclical encoding
                features_df['hour_sin'] = np.sin(2 * np.pi * features_df['hour_of_day'] / 24)
                features_df['hour_cos'] = np.cos(2 * np.pi * features_df['hour_of_day'] / 24)
                features_df['minute_sin'] = np.sin(2 * np.pi * features_df['minute_of_hour'] / 60)
                features_df['minute_cos'] = np.cos(2 * np.pi * features_df['minute_of_hour'] / 60)
                features_df['day_sin'] = np.sin(2 * np.pi * features_df['day_of_week'] / 7)
                features_df['day_cos'] = np.cos(2 * np.pi * features_df['day_of_week'] / 7)
            except Exception as e:
                logger.warning(f"Could not process temporal features: {e}")
                # Create dummy temporal features
                features_df['hour_of_day'] = 12  # Default to noon
                features_df['minute_of_hour'] = 0
                features_df['day_of_week'] = 0
                features_df['hour_sin'] = 0
                features_df['hour_cos'] = 1
                features_df['minute_sin'] = 0
                features_df['minute_cos'] = 1
                features_df['day_sin'] = 0
                features_df['day_cos'] = 1
        
        # Time since last event
        if 'ts_event' in mbo_df.columns:
            try:
                time_diffs = mbo_df['ts_event'].diff()
                features_df['time_since_last_event'] = time_diffs
                features_df['time_since_last_event_ma'] = time_diffs.rolling(window=20).mean()
                
                # Event frequency
                features_df['event_frequency'] = 1 / (features_df['time_since_last_event'] + 1e-8)
                features_df['event_frequency_ma'] = features_df['event_frequency'].rolling(window=20).mean()
            except Exception as e:
                logger.warning(f"Could not process time-based features: {e}")
                # Create dummy time features
                features_df['time_since_last_event'] = 1.0
                features_df['time_since_last_event_ma'] = 1.0
                features_df['event_frequency'] = 1.0
                features_df['event_frequency_ma'] = 1.0
        else:
            # Create dummy time features if no timestamp data
            features_df['time_since_last_event'] = 1.0
            features_df['time_since_last_event_ma'] = 1.0
            features_df['event_frequency'] = 1.0
            features_df['event_frequency_ma'] = 1.0
        
        return features_df
    
    def _add_greeks_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add options-style Greeks features for order flow analysis."""
        
        logger.info("Adding Greeks features...")
        
        # Delta (price sensitivity)
        if 'price' in mbo_df.columns:
            try:
                features_df['delta'] = mbo_df['price'].pct_change(fill_method=None)
                features_df['delta_ma'] = features_df['delta'].rolling(window=20).mean()
                features_df['delta_gamma'] = features_df['delta'].pct_change(fill_method=None)  # Second derivative
                
                # Gamma (convexity)
                features_df['gamma'] = features_df['delta'].pct_change(fill_method=None)
                features_df['gamma_ma'] = features_df['gamma'].rolling(window=20).mean()
            except Exception as e:
                logger.warning(f"Could not process Greeks features: {e}")
                features_df['delta'] = 0.0
                features_df['delta_ma'] = 0.0
                features_df['delta_gamma'] = 0.0
                features_df['gamma'] = 0.0
                features_df['gamma_ma'] = 0.0
        else:
            # Create dummy Greeks features
            features_df['delta'] = 0.0
            features_df['delta_ma'] = 0.0
            features_df['delta_gamma'] = 0.0
            features_df['gamma'] = 0.0
            features_df['gamma_ma'] = 0.0
        
        # Theta (time decay)
        if 'ts_event' in mbo_df.columns:
            try:
                time_decay = mbo_df['ts_event'].diff()
                features_df['theta'] = time_decay / (time_decay.rolling(window=100).mean() + 1e-8)
            except Exception as e:
                logger.warning(f"Could not process Theta: {e}")
                features_df['theta'] = 0.0
        else:
            features_df['theta'] = 0.0
        
        # Vega (volatility sensitivity)
        if 'price' in mbo_df.columns:
            try:
                volatility = mbo_df['price'].pct_change(fill_method=None).rolling(window=20).std()
                features_df['vega'] = volatility.pct_change(fill_method=None)
            except Exception as e:
                logger.warning(f"Could not process Vega: {e}")
                features_df['vega'] = 0.0
        else:
            features_df['vega'] = 0.0
        
        return features_df
    
    def _add_liquidity_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add comprehensive liquidity metrics."""
        
        logger.info("Adding liquidity features...")
        
        # Amihud illiquidity
        if 'price' in mbo_df.columns and 'volume' in features_df.columns:
            returns = mbo_df['price'].pct_change(fill_method=None).abs()
            features_df['amihud_illiquidity'] = returns / (features_df['volume'] + 1e-8)
            features_df['amihud_ma'] = features_df['amihud_illiquidity'].rolling(window=20).mean()
        
        # Kyle's lambda
        if 'price' in mbo_df.columns and 'volume' in features_df.columns:
            signed_volume = features_df['volume'] * features_df['volume_imbalance']
            features_df['kyle_lambda'] = mbo_df['price'].pct_change(fill_method=None) / (signed_volume + 1e-8)
        
        # Roll's implicit spread
        if 'price' in mbo_df.columns:
            price_changes = mbo_df['price'].pct_change(fill_method=None)
            features_df['roll_spread'] = 2 * np.sqrt(-price_changes.rolling(window=20).cov(price_changes.shift(1)))
        
        # Bid-ask bounce
        if 'price' in mbo_df.columns:
            price_reversals = (mbo_df['price'].pct_change(fill_method=None) * mbo_df['price'].pct_change(fill_method=None).shift(1) < 0).astype(int)
            features_df['bid_ask_bounce'] = price_reversals.rolling(window=20).mean()
        
        return features_df
    
    def _add_momentum_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum and trend features."""
        
        logger.info("Adding momentum features...")
        
        # Price momentum
        if 'price' in mbo_df.columns:
            for window in self.config.short_windows + self.config.medium_windows:
                features_df[f'price_momentum_{window}m'] = mbo_df['price'].pct_change(window, fill_method=None)
                features_df[f'price_momentum_ma_{window}m'] = features_df[f'price_momentum_{window}m'].rolling(window).mean()
        
        # Volume momentum
        for window in self.config.short_windows:
            features_df[f'volume_momentum_{window}m'] = features_df['volume'].pct_change(window, fill_method=None)
            features_df[f'volume_momentum_ma_{window}m'] = features_df[f'volume_momentum_{window}m'].rolling(window).mean()
        
        # RSI-style momentum
        if 'price' in mbo_df.columns:
            for window in [14, 20, 50]:
                delta = mbo_df['price'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
                rs = gain / (loss + 1e-8)
                features_df[f'rsi_{window}'] = 100 - (100 / (1 + rs))
        
        # MACD-style momentum
        if 'price' in mbo_df.columns:
            ema_12 = mbo_df['price'].ewm(span=12).mean()
            ema_26 = mbo_df['price'].ewm(span=26).mean()
            features_df['macd'] = ema_12 - ema_26
            features_df['macd_signal'] = features_df['macd'].ewm(span=9).mean()
            features_df['macd_histogram'] = features_df['macd'] - features_df['macd_signal']
        
        return features_df
    
    def _add_divergence_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add divergence detection features."""
        
        logger.info("Adding divergence features...")
        
        # Price-volume divergence
        if 'price' in mbo_df.columns and 'volume' in features_df.columns:
            price_momentum = mbo_df['price'].pct_change(5, fill_method=None)
            volume_momentum = features_df['volume'].pct_change(5, fill_method=None)
            
            features_df['price_volume_divergence'] = np.sign(price_momentum) * np.sign(volume_momentum)
            features_df['divergence_strength'] = abs(price_momentum) * abs(volume_momentum)
        
        # Momentum divergence
        if 'price' in mbo_df.columns:
            short_momentum = mbo_df['price'].pct_change(5, fill_method=None)
            long_momentum = mbo_df['price'].pct_change(20, fill_method=None)
            
            features_df['momentum_divergence'] = np.sign(short_momentum) * np.sign(long_momentum)
            features_df['momentum_divergence_strength'] = abs(short_momentum - long_momentum)
        
        return features_df
    
    def _add_cross_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Add interaction features between different feature types."""
        
        logger.info("Adding cross features...")
        
        # Volume-imbalance interactions
        if 'volume' in features_df.columns and 'volume_imbalance' in features_df.columns:
            features_df['volume_imbalance_interaction'] = features_df['volume'] * features_df['volume_imbalance']
            features_df['volume_imbalance_ratio'] = features_df['volume'] / (features_df['volume_imbalance'].abs() + 1e-8)
        
        # Price-volume interactions
        if 'price' in features_df.columns and 'volume' in features_df.columns:
            features_df['price_volume_interaction'] = features_df['price'].pct_change(fill_method=None) * features_df['volume']
        
        # Regime-interaction features
        if 'volatility_regime' in features_df.columns and 'volume_regime' in features_df.columns:
            features_df['regime_interaction'] = features_df['volatility_regime'] * features_df['volume_regime']
        
        return features_df
    
    def _add_multi_timeframe_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add multi-timeframe analysis features."""
        
        logger.info("Adding multi-timeframe features...")
        
        all_windows = self.config.short_windows + self.config.medium_windows + self.config.long_windows
        
        # Multi-timeframe momentum
        if 'price' in mbo_df.columns:
            for window in all_windows:
                features_df[f'mtf_momentum_{window}m'] = mbo_df['price'].pct_change(window, fill_method=None)
            
            # Momentum alignment
            short_momentum = features_df[f'mtf_momentum_{self.config.short_windows[0]}m']
            medium_momentum = features_df[f'mtf_momentum_{self.config.medium_windows[0]}m']
            long_momentum = features_df[f'mtf_momentum_{self.config.long_windows[0]}m']
            
            features_df['momentum_alignment'] = (np.sign(short_momentum) + np.sign(medium_momentum) + np.sign(long_momentum)) / 3
        
        # Multi-timeframe volatility
        if 'price' in mbo_df.columns:
            for window in all_windows:
                features_df[f'mtf_volatility_{window}m'] = mbo_df['price'].pct_change(fill_method=None).rolling(window).std()
        
        return features_df
    
    def _add_order_flow_intelligence_features(self, features_df: pd.DataFrame, mbo_df: pd.DataFrame) -> pd.DataFrame:
        """Add advanced order flow intelligence features."""
        
        logger.info("Adding order flow intelligence features...")
        
        # Smart money detection
        if 'volume' in features_df.columns and 'price' in mbo_df.columns:
            # Large orders with low price impact might indicate smart money
            large_volume = features_df['volume'] > features_df['volume'].rolling(window=100).quantile(0.9)
            low_impact = mbo_df['price'].pct_change(fill_method=None).abs() < mbo_df['price'].pct_change(fill_method=None).rolling(window=100).quantile(0.1)
            features_df['smart_money_detection'] = (large_volume & low_impact).astype(int)
        
        # Order flow clustering
        if 'volume' in features_df.columns:
            # Detect clustering of orders
            volume_clusters = features_df['volume'].rolling(window=10).apply(
                lambda x: len(x[x > x.mean() + x.std()]) if len(x) > 0 else 0
            )
            features_df['order_clustering'] = volume_clusters
        
        # Market microstructure efficiency
        if 'price' in mbo_df.columns:
            # Measure how efficiently price reflects information
            price_efficiency = mbo_df['price'].pct_change(fill_method=None).rolling(window=20).apply(
                lambda x: 1 - abs(x.autocorr()) if len(x) > 1 else 0
            )
            features_df['market_efficiency'] = price_efficiency
        
        return features_df
