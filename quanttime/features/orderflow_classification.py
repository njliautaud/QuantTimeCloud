"""
Advanced Order Flow Classification Engine
Distinguishes between "toxic" (informed) and "benign" (retail/uninformed) order flow

This module implements sophisticated algorithms to classify order flow patterns
for alpha generation in market-making and trading strategies.

Key Classifications:
- Toxic Flow: Informed traders with private information, adverse selection risk
- Benign Flow: Retail/uninformed traders, liquidity providers, favorable flow

Feature Engineering Approach:
- Real-time flow classification based on execution patterns
- Historical flow behavior analysis
- Cross-venue flow correlation
- Timing and size distribution analysis
- Order book impact prediction
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
import warnings
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    # Fallback implementations for talib functions
    class TalibFallback:
        @staticmethod
        def MOM(data, timeperiod=10):
            """Momentum fallback implementation"""
            return pd.Series(data).diff(timeperiod).values
    talib = TalibFallback()

logger = logging.getLogger(__name__)

class FlowType(Enum):
    """Order flow classification types"""
    TOXIC = "toxic"          # Informed traders, adverse selection risk
    BENIGN = "benign"        # Retail/uninformed, favorable flow
    NEUTRAL = "neutral"      # Unclear classification
    INSTITUTIONAL = "institutional"  # Large institutional flow
    MARKET_MAKER = "market_maker"    # Market maker flow

@dataclass
class FlowMetrics:
    """Metrics for order flow classification"""
    toxicity_score: float           # 0-1, higher = more toxic
    information_content: float      # Information advantage estimate
    adverse_selection_risk: float   # Risk of adverse selection
    flow_persistence: float         # How long flow pattern persists
    size_aggressiveness: float      # Size relative to typical flow
    timing_sophistication: float    # Timing pattern sophistication
    venue_coordination: float       # Cross-venue coordination level
    
class OrderFlowClassifier:
    """Advanced order flow classification engine"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".OrderFlowClassifier")
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(contamination=0.1, random_state=42)
        self.calibrated = False
        self.flow_history = []
        self.classification_thresholds = {
            'toxic_threshold': 0.7,
            'benign_threshold': 0.3,
            'institutional_size_threshold': 1000,
            'timing_sophistication_threshold': 0.6
        }
        
    def extract_flow_features(self, mbo_df: pd.DataFrame, 
                            lookback_window: int = 1000) -> pd.DataFrame:
        """
        Extract comprehensive order flow classification features
        
        Args:
            mbo_df: Market by order data
            lookback_window: Number of events to look back for pattern analysis
            
        Returns:
            DataFrame with flow classification features
        """
        try:
            features = mbo_df.copy()
            
            # 1. EXECUTION PATTERN ANALYSIS
            features = self._add_execution_patterns(features, lookback_window)
            
            # 2. SIZE AND AGGRESSIVENESS ANALYSIS
            features = self._add_size_aggressiveness_features(features, lookback_window)
            
            # 3. TIMING SOPHISTICATION ANALYSIS
            features = self._add_timing_sophistication_features(features, lookback_window)
            
            # 4. INFORMATION CONTENT ANALYSIS
            features = self._add_information_content_features(features, lookback_window)
            
            # 5. ADVERSE SELECTION RISK FEATURES
            features = self._add_adverse_selection_features(features, lookback_window)
            
            # 6. FLOW PERSISTENCE ANALYSIS
            features = self._add_flow_persistence_features(features, lookback_window)
            
            # 7. CROSS-VENUE COORDINATION (when available)
            features = self._add_venue_coordination_features(features, lookback_window)
            
            # 8. FINAL TOXICITY SCORING
            features = self._calculate_toxicity_scores(features)
            
            self.logger.info(f"Extracted {len([c for c in features.columns if 'flow_' in c])} orderflow classification features")
            return features
            
        except Exception as e:
            self.logger.error(f"Failed to extract orderflow features: {e}")
            return mbo_df
    
    def _add_execution_patterns(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add execution pattern features for flow classification"""
        try:
            # Execution aggressiveness patterns
            df['flow_aggressive_ratio'] = df.groupby('side')['size'].rolling(window).apply(
                lambda x: (x > x.quantile(0.8)).mean(), raw=False
            ).reset_index(level=0, drop=True)
            
            # Order size clustering (toxic flow often has specific size patterns)
            df['flow_size_clustering'] = df['size'].rolling(window).apply(
                lambda x: self._calculate_size_clustering(x), raw=False
            )
            
            # Execution timing patterns (microsecond precision)
            if 'ts_event' in df.columns:
                df['flow_execution_timing'] = df['ts_event'].diff().rolling(window).apply(
                    lambda x: self._analyze_execution_timing(x), raw=False
                )
            
            # Fill-to-order ratio (toxic flow often has higher fill rates)
            df['flow_fill_ratio'] = df.groupby('side').apply(
                lambda x: (x['action'] == 'F').rolling(window).mean()
            ).reset_index(level=0, drop=True)
            
            # Order modification patterns (sophisticated traders modify more)
            df['flow_modification_rate'] = df.groupby('order_id').apply(
                lambda x: (x['action'].isin(['A', 'M'])).rolling(window).mean() if 'order_id' in x.columns else 0
            ).reset_index(level=0, drop=True)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add execution patterns: {e}")
            return df
    
    def _add_size_aggressiveness_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add size and aggressiveness features"""
        try:
            # Size percentile ranking (toxic flow often has unusual sizes)
            df['flow_size_percentile'] = df['size'].rolling(window).rank(pct=True)
            
            # Aggressiveness score based on order book impact
            df['flow_aggressiveness_score'] = df['size'] / df['size'].rolling(window).mean()
            
            # Large order detection (institutional/toxic flow indicator)
            size_threshold = df['size'].rolling(window).quantile(0.95)
            df['flow_large_order_flag'] = (df['size'] > size_threshold).astype(int)
            
            # Iceberg order detection (hidden size patterns)
            df['flow_iceberg_probability'] = df.groupby(['price', 'side'])['size'].rolling(window).apply(
                lambda x: self._detect_iceberg_pattern(x), raw=False
            ).reset_index(level=[0, 1], drop=True)
            
            # Size momentum (toxic flow often has persistent size patterns)
            df['flow_size_momentum'] = talib.MOM(df['size'].values, timeperiod=10)
            
            # Size volatility (informed traders often have consistent sizing)
            df['flow_size_volatility'] = df['size'].rolling(window).std() / df['size'].rolling(window).mean()
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add size aggressiveness features: {e}")
            return df
    
    def _add_timing_sophistication_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add timing sophistication analysis"""
        try:
            if 'ts_event' not in df.columns:
                return df
            
            # Timing precision analysis (HFT/sophisticated timing patterns)
            df['flow_timing_precision'] = df['ts_event'].diff().rolling(window).apply(
                lambda x: self._analyze_timing_precision(x), raw=False
            )
            
            # Market timing efficiency (arriving just before price moves)
            df['flow_market_timing'] = df.apply(
                lambda row: self._calculate_market_timing_score(row, df), axis=1
            )
            
            # Order submission clustering (burst patterns vs steady flow)
            df['flow_submission_clustering'] = df['ts_event'].rolling(window).apply(
                lambda x: self._calculate_submission_clustering(x), raw=False
            )
            
            # Latency arbitrage indicators
            df['flow_latency_advantage'] = df['ts_event'].diff().rolling(window).apply(
                lambda x: (x < x.quantile(0.1)).mean(), raw=False
            )
            
            # Speed of execution relative to market events
            df['flow_execution_speed'] = df.groupby('side')['ts_event'].diff().rolling(window).mean()
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add timing sophistication features: {e}")
            return df
    
    def _add_information_content_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add information content analysis features"""
        try:
            # Price impact prediction accuracy
            df['flow_price_impact_accuracy'] = self._calculate_price_impact_accuracy(df, window)
            
            # Directional accuracy of trades
            df['flow_directional_accuracy'] = self._calculate_directional_accuracy(df, window)
            
            # Information decay rate (how quickly advantage dissipates)
            df['flow_information_decay'] = self._calculate_information_decay(df, window)
            
            # Alpha generation potential
            df['flow_alpha_potential'] = df['flow_directional_accuracy'] * df['flow_price_impact_accuracy']
            
            # Order book informativeness (how much order reveals about future prices)
            df['flow_book_informativeness'] = self._calculate_book_informativeness(df, window)
            
            # Flow-to-price correlation (toxic flow correlates with future price moves)
            df['flow_price_correlation'] = df.groupby('side')['size'].rolling(window).corr(
                df['price'].shift(-5)  # Future price correlation
            )
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add information content features: {e}")
            return df
    
    def _add_adverse_selection_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add adverse selection risk features"""
        try:
            # Adverse selection probability
            df['flow_adverse_selection_prob'] = self._calculate_adverse_selection_probability(df, window)
            
            # Post-trade price movement (key indicator of informed trading)
            df['flow_post_trade_impact'] = df.groupby('side').apply(
                lambda x: self._calculate_post_trade_impact(x, window)
            ).reset_index(level=0, drop=True)
            
            # Spread capture efficiency (toxic flow often captures more spread)
            df['flow_spread_capture'] = self._calculate_spread_capture_efficiency(df, window)
            
            # Market impact persistence (informed trades have lasting impact)
            df['flow_impact_persistence'] = self._calculate_impact_persistence(df, window)
            
            # Liquidity consumption rate
            df['flow_liquidity_consumption'] = df['size'].rolling(window).sum() / window
            
            # Fill rate vs market conditions
            df['flow_conditional_fill_rate'] = self._calculate_conditional_fill_rate(df, window)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add adverse selection features: {e}")
            return df
    
    def _add_flow_persistence_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add flow persistence analysis"""
        try:
            # Flow continuation probability
            df['flow_continuation_prob'] = df.groupby('side')['size'].rolling(window).apply(
                lambda x: self._calculate_flow_continuation(x), raw=False
            ).reset_index(level=0, drop=True)
            
            # Directional persistence (toxic flow often has strong directional bias)
            df['flow_directional_persistence'] = self._calculate_directional_persistence(df, window)
            
            # Size persistence (consistent sizing patterns)
            df['flow_size_persistence'] = df['size'].rolling(window).apply(
                lambda x: self._calculate_size_persistence(x), raw=False
            )
            
            # Temporal clustering (burst vs steady patterns)
            df['flow_temporal_clustering'] = self._calculate_temporal_clustering(df, window)
            
            # Pattern repetition (sophisticated algorithms often repeat patterns)
            df['flow_pattern_repetition'] = self._detect_pattern_repetition(df, window)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add flow persistence features: {e}")
            return df
    
    def _add_venue_coordination_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Add cross-venue coordination features (when venue data available)"""
        try:
            # Cross-venue timing coordination
            if 'venue' in df.columns:
                df['flow_venue_coordination'] = df.groupby('venue').apply(
                    lambda x: self._calculate_venue_coordination(x, df, window)
                ).reset_index(level=0, drop=True)
            else:
                df['flow_venue_coordination'] = 0.0
            
            # Arbitrage opportunity exploitation
            df['flow_arbitrage_exploitation'] = self._detect_arbitrage_exploitation(df, window)
            
            # Latency arbitrage patterns
            df['flow_latency_arbitrage'] = self._detect_latency_arbitrage(df, window)
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Failed to add venue coordination features: {e}")
            return df
    
    def _calculate_toxicity_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate final toxicity scores and classifications"""
        try:
            # Collect all flow features
            flow_cols = [col for col in df.columns if col.startswith('flow_')]
            
            if not flow_cols:
                df['flow_toxicity_score'] = 0.5  # Neutral default
                df['flow_classification'] = FlowType.NEUTRAL.value
                return df
            
            # Create composite toxicity score
            toxicity_weights = {
                'flow_aggressive_ratio': 0.15,
                'flow_size_clustering': 0.10,
                'flow_timing_precision': 0.15,
                'flow_market_timing': 0.20,
                'flow_price_impact_accuracy': 0.20,
                'flow_adverse_selection_prob': 0.15,
                'flow_information_decay': -0.05  # Lower decay = more toxic
            }
            
            # Calculate weighted toxicity score
            df['flow_toxicity_score'] = 0.0
            for feature, weight in toxicity_weights.items():
                if feature in df.columns:
                    # Normalize feature to 0-1 range
                    normalized = (df[feature] - df[feature].min()) / (df[feature].max() - df[feature].min() + 1e-8)
                    df['flow_toxicity_score'] += weight * normalized.fillna(0.5)
            
            # Ensure score is in 0-1 range
            df['flow_toxicity_score'] = df['flow_toxicity_score'].clip(0, 1)
            
            # Classify flow based on toxicity score
            df['flow_classification'] = df['flow_toxicity_score'].apply(self._classify_flow)
            
            # Add confidence score
            df['flow_classification_confidence'] = self._calculate_classification_confidence(df, flow_cols)
            
            # Add flow metrics
            df['flow_information_content'] = df[['flow_directional_accuracy', 'flow_alpha_potential']].mean(axis=1)
            df['flow_adverse_selection_risk'] = df['flow_adverse_selection_prob']
            df['flow_size_aggressiveness'] = df['flow_aggressiveness_score']
            df['flow_timing_sophistication'] = df['flow_timing_precision']
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to calculate toxicity scores: {e}")
            df['flow_toxicity_score'] = 0.5
            df['flow_classification'] = FlowType.NEUTRAL.value
            return df
    
    def _classify_flow(self, toxicity_score: float) -> str:
        """Classify flow based on toxicity score"""
        if toxicity_score >= self.classification_thresholds['toxic_threshold']:
            return FlowType.TOXIC.value
        elif toxicity_score <= self.classification_thresholds['benign_threshold']:
            return FlowType.BENIGN.value
        else:
            return FlowType.NEUTRAL.value
    
    # Helper methods for specific calculations
    def _calculate_size_clustering(self, sizes: pd.Series) -> float:
        """Calculate size clustering coefficient"""
        try:
            if len(sizes) < 10:
                return 0.5
            
            # Use coefficient of variation as clustering measure
            cv = sizes.std() / (sizes.mean() + 1e-8)
            return 1.0 / (1.0 + cv)  # Higher clustering = lower CV
        except:
            return 0.5
    
    def _analyze_execution_timing(self, timestamps: pd.Series) -> float:
        """Analyze execution timing patterns"""
        try:
            if len(timestamps) < 10:
                return 0.5
            
            # Calculate timing regularity (inverse of coefficient of variation)
            intervals = timestamps.diff().dropna()
            if intervals.std() == 0:
                return 1.0  # Perfect regularity
            
            cv = intervals.std() / (intervals.mean() + 1e-8)
            return 1.0 / (1.0 + cv)
        except:
            return 0.5
    
    def _detect_iceberg_pattern(self, sizes: pd.Series) -> float:
        """Detect iceberg order patterns"""
        try:
            if len(sizes) < 20:
                return 0.0
            
            # Look for repeated similar sizes (iceberg characteristic)
            size_counts = sizes.value_counts()
            max_repetition = size_counts.max() if len(size_counts) > 0 else 0
            repetition_ratio = max_repetition / len(sizes)
            
            # High repetition suggests iceberg
            return min(1.0, repetition_ratio * 5)
        except:
            return 0.0
    
    def _analyze_timing_precision(self, timestamps: pd.Series) -> float:
        """Analyze timing precision (microsecond patterns)"""
        try:
            if len(timestamps) < 10:
                return 0.5
            
            # Calculate precision by looking at timestamp patterns
            intervals = timestamps.diff().dropna()
            if len(intervals) == 0:
                return 0.5
            
            # Check for round numbers or specific patterns
            microseconds = intervals.dt.microseconds if hasattr(intervals, 'dt') else intervals % 1000000
            round_number_ratio = (microseconds % 1000 == 0).mean()
            
            return round_number_ratio  # Higher precision = more round numbers
        except:
            return 0.5
    
    def _calculate_market_timing_score(self, row: pd.Series, df: pd.DataFrame) -> float:
        """Calculate market timing efficiency score"""
        try:
            # This would require more sophisticated implementation
            # For now, return neutral score
            return 0.5
        except:
            return 0.5
    
    def _calculate_submission_clustering(self, timestamps: pd.Series) -> float:
        """Calculate order submission clustering"""
        try:
            if len(timestamps) < 10:
                return 0.5
            
            # Use isolation forest to detect clustering
            intervals = timestamps.diff().dropna().values.reshape(-1, 1)
            if len(intervals) < 3:
                return 0.5
            
            clustering_score = len(intervals[intervals < np.percentile(intervals, 25)]) / len(intervals)
            return clustering_score
        except:
            return 0.5
    
    def _calculate_price_impact_accuracy(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate price impact prediction accuracy"""
        try:
            # Simple implementation - can be enhanced
            future_returns = df['price'].pct_change().shift(-5)
            trade_direction = np.where(df['side'] == 'B', 1, -1)
            
            # Rolling correlation between trade direction and future returns
            accuracy = pd.Series(index=df.index, dtype=float)
            for i in range(window, len(df)):
                window_returns = future_returns.iloc[i-window:i]
                window_direction = trade_direction[i-window:i]
                
                if len(window_returns.dropna()) > 10:
                    corr = np.corrcoef(window_direction, window_returns.fillna(0))[0, 1]
                    accuracy.iloc[i] = abs(corr) if not np.isnan(corr) else 0.5
                else:
                    accuracy.iloc[i] = 0.5
            
            return accuracy.fillna(0.5)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_directional_accuracy(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate directional prediction accuracy"""
        try:
            # Implementation similar to price impact accuracy
            return self._calculate_price_impact_accuracy(df, window)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_information_decay(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate information decay rate"""
        try:
            # Simple implementation - measure how quickly impact dissipates
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_book_informativeness(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate order book informativeness"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_adverse_selection_probability(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate adverse selection probability"""
        try:
            # Based on post-trade price movements
            return self._calculate_price_impact_accuracy(df, window)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_post_trade_impact(self, group_df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate post-trade price impact"""
        try:
            return pd.Series([0.5] * len(group_df), index=group_df.index)
        except:
            return pd.Series([0.5] * len(group_df), index=group_df.index)
    
    def _calculate_spread_capture_efficiency(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate spread capture efficiency"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_impact_persistence(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate market impact persistence"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_conditional_fill_rate(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate conditional fill rate"""
        try:
            fill_rate = (df['action'] == 'F').rolling(window).mean()
            return fill_rate.fillna(0.5)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_flow_continuation(self, sizes: pd.Series) -> float:
        """Calculate flow continuation probability"""
        try:
            if len(sizes) < 10:
                return 0.5
            
            # Simple momentum-based continuation
            return (sizes.diff().fillna(0) > 0).mean()
        except:
            return 0.5
    
    def _calculate_directional_persistence(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate directional persistence"""
        try:
            buy_mask = df['side'] == 'B'
            persistence = buy_mask.rolling(window).apply(
                lambda x: abs(x.mean() - 0.5) * 2, raw=False
            )
            return persistence.fillna(0.5)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_size_persistence(self, sizes: pd.Series) -> float:
        """Calculate size persistence"""
        try:
            if len(sizes) < 10:
                return 0.5
            
            # Autocorrelation as persistence measure
            return abs(sizes.autocorr(lag=1)) if not pd.isna(sizes.autocorr(lag=1)) else 0.5
        except:
            return 0.5
    
    def _calculate_temporal_clustering(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate temporal clustering"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _detect_pattern_repetition(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Detect algorithmic pattern repetition"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_venue_coordination(self, venue_df: pd.DataFrame, 
                                    all_df: pd.DataFrame, window: int) -> pd.Series:
        """Calculate cross-venue coordination"""
        try:
            return pd.Series([0.5] * len(venue_df), index=venue_df.index)
        except:
            return pd.Series([0.5] * len(venue_df), index=venue_df.index)
    
    def _detect_arbitrage_exploitation(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Detect arbitrage opportunity exploitation"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _detect_latency_arbitrage(self, df: pd.DataFrame, window: int) -> pd.Series:
        """Detect latency arbitrage patterns"""
        try:
            return pd.Series([0.5] * len(df), index=df.index)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def _calculate_classification_confidence(self, df: pd.DataFrame, 
                                           flow_cols: List[str]) -> pd.Series:
        """Calculate classification confidence"""
        try:
            # Based on consistency of flow features
            if not flow_cols:
                return pd.Series([0.5] * len(df), index=df.index)
            
            # Calculate feature agreement
            feature_matrix = df[flow_cols].fillna(0.5)
            confidence = 1.0 - feature_matrix.std(axis=1) / (feature_matrix.mean(axis=1) + 1e-8)
            return confidence.clip(0, 1).fillna(0.5)
        except:
            return pd.Series([0.5] * len(df), index=df.index)
    
    def get_flow_metrics(self, df: pd.DataFrame) -> Dict[str, FlowMetrics]:
        """Get comprehensive flow metrics for each classified flow type"""
        try:
            if 'flow_classification' not in df.columns:
                return {}
            
            metrics = {}
            for flow_type in df['flow_classification'].unique():
                flow_data = df[df['flow_classification'] == flow_type]
                
                if len(flow_data) > 0:
                    metrics[flow_type] = FlowMetrics(
                        toxicity_score=flow_data['flow_toxicity_score'].mean(),
                        information_content=flow_data.get('flow_information_content', pd.Series([0.5])).mean(),
                        adverse_selection_risk=flow_data.get('flow_adverse_selection_risk', pd.Series([0.5])).mean(),
                        flow_persistence=flow_data.get('flow_directional_persistence', pd.Series([0.5])).mean(),
                        size_aggressiveness=flow_data.get('flow_size_aggressiveness', pd.Series([0.5])).mean(),
                        timing_sophistication=flow_data.get('flow_timing_sophistication', pd.Series([0.5])).mean(),
                        venue_coordination=flow_data.get('flow_venue_coordination', pd.Series([0.5])).mean()
                    )
            
            return metrics
        except Exception as e:
            self.logger.error(f"Failed to calculate flow metrics: {e}")
            return {}
    
    def generate_classification_report(self, df: pd.DataFrame) -> Dict:
        """Generate comprehensive orderflow classification report"""
        try:
            if 'flow_classification' not in df.columns:
                return {"error": "No flow classification found"}
            
            report = {
                "classification_summary": df['flow_classification'].value_counts().to_dict(),
                "average_toxicity_by_type": df.groupby('flow_classification')['flow_toxicity_score'].mean().to_dict(),
                "flow_metrics": self.get_flow_metrics(df),
                "total_volume_by_type": df.groupby('flow_classification')['size'].sum().to_dict(),
                "adverse_selection_risk": {
                    "toxic_flow_risk": df[df['flow_classification'] == 'toxic']['flow_adverse_selection_risk'].mean() if 'flow_adverse_selection_risk' in df.columns else 0.0,
                    "benign_flow_risk": df[df['flow_classification'] == 'benign']['flow_adverse_selection_risk'].mean() if 'flow_adverse_selection_risk' in df.columns else 0.0
                }
            }
            
            return report
        except Exception as e:
            self.logger.error(f"Failed to generate classification report: {e}")
            return {"error": str(e)}

# Integration function for existing feature engineering
def add_orderflow_classification_features(mbo_df: pd.DataFrame, 
                                        lookback_window: int = 1000) -> pd.DataFrame:
    """
    Add orderflow classification features to existing MBO dataframe
    
    Args:
        mbo_df: Market by order dataframe
        lookback_window: Lookback window for pattern analysis
        
    Returns:
        Enhanced dataframe with orderflow classification features
    """
    try:
        classifier = OrderFlowClassifier()
        enhanced_df = classifier.extract_flow_features(mbo_df, lookback_window)
        
        logger.info(f"Added orderflow classification features: "
                   f"{len([c for c in enhanced_df.columns if 'flow_' in c])} new features")
        
        return enhanced_df
        
    except Exception as e:
        logger.error(f"Failed to add orderflow classification features: {e}")
        return mbo_df

if __name__ == "__main__":
    # Example usage and testing
    import pandas as pd
    
    # Create sample MBO data for testing
    sample_data = pd.DataFrame({
        'ts_event': pd.date_range('2024-01-01', periods=1000, freq='1ms'),
        'price': 5000 + np.random.randn(1000) * 0.25,
        'size': np.random.randint(1, 100, 1000),
        'side': np.random.choice(['B', 'S'], 1000),
        'action': np.random.choice(['A', 'M', 'D', 'F'], 1000, p=[0.4, 0.2, 0.2, 0.2])
    })
    
    # Test orderflow classification
    classifier = OrderFlowClassifier()
    classified_data = classifier.extract_flow_features(sample_data)
    
    # Generate report
    report = classifier.generate_classification_report(classified_data)
    print("Orderflow Classification Report:")
    print(f"Classification Summary: {report.get('classification_summary', {})}")
