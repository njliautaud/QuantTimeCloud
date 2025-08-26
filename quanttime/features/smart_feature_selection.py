"""
Smart Feature Selection for QuantTime

This module implements intelligent feature selection that:
1. Keeps ALL features that could be predictive
2. Lets models learn feature importance during training
3. Provides feature importance tracking and analysis
4. Enables model-driven feature selection
5. Maintains full order flow understanding

Philosophy: Don't remove features that could predict price movements.
Let the model discover what's actually predictive through training.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
import lightgbm as lgb
import joblib
import os

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportanceConfig:
    """Configuration for feature importance analysis."""
    
    # Feature importance methods
    use_mutual_info: bool = True
    use_random_forest: bool = True
    use_lightgbm: bool = True
    use_correlation: bool = True
    
    # Thresholds for feature selection
    min_importance_threshold: float = 0.001  # Keep features above this threshold
    max_features_to_remove: int = 0  # 0 = don't remove any features automatically
    
    # Analysis parameters
    correlation_threshold: float = 0.95  # Remove highly correlated features
    stability_threshold: float = 0.8  # Feature importance stability threshold
    
    # Order flow preservation
    preserve_order_flow_features: bool = True
    preserve_absorption_features: bool = True
    preserve_imbalance_features: bool = True
    preserve_pattern_features: bool = True
    
    # Feature categories to always preserve
    critical_features: List[str] = field(default_factory=lambda: [
        'volume_imbalance', 'price_impact', 'bid_ask_spread',
        'order_book_imbalance', 'iceberg_detection', 'absorption_detection',
        'order_block_detection', 'mid_price', 'spread', 'imbalance_ratio'
    ])


class SmartFeatureSelector:
    """
    Smart feature selector that preserves all potentially predictive features
    and lets models learn what's actually important.
    """
    
    def __init__(self, config: FeatureImportanceConfig = None):
        self.config = config or FeatureImportanceConfig()
        self.feature_importance_history = []
        self.feature_stability_scores = {}
        self.critical_features_preserved = set()
        
    def analyze_feature_importance(self, X: pd.DataFrame, y: pd.Series, 
                                 target_type: str = 'regression') -> Dict[str, Any]:
        """
        Analyze feature importance using multiple methods.
        
        Args:
            X: Feature matrix
            y: Target variable
            target_type: 'regression' or 'classification'
            
        Returns:
            Dictionary with feature importance analysis
        """
        
        logger.info(f"Analyzing feature importance for {len(X.columns)} features")
        
        importance_results = {
            'feature_names': list(X.columns),
            'total_features': len(X.columns),
            'importance_scores': {},
            'rankings': {},
            'stability_scores': {},
            'recommendations': {}
        }
        
        # 1. Mutual Information Analysis
        if self.config.use_mutual_info:
            logger.info("Computing mutual information scores...")
            if target_type == 'regression':
                mi_scores = mutual_info_regression(X, y, random_state=42)
            else:
                mi_scores = mutual_info_classif(X, y, random_state=42)
            
            importance_results['importance_scores']['mutual_info'] = dict(zip(X.columns, mi_scores))
            importance_results['rankings']['mutual_info'] = self._rank_features(mi_scores, X.columns)
        
        # 2. Random Forest Importance
        if self.config.use_random_forest:
            logger.info("Computing Random Forest importance...")
            if target_type == 'regression':
                rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
            else:
                rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            
            rf.fit(X, y)
            rf_importance = rf.feature_importances_
            importance_results['importance_scores']['random_forest'] = dict(zip(X.columns, rf_importance))
            importance_results['rankings']['random_forest'] = self._rank_features(rf_importance, X.columns)
        
        # 3. LightGBM Importance
        if self.config.use_lightgbm:
            logger.info("Computing LightGBM importance...")
            if target_type == 'regression':
                lgb_model = lgb.LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
            else:
                lgb_model = lgb.LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
            
            lgb_model.fit(X, y)
            lgb_importance = lgb_model.feature_importances_
            importance_results['importance_scores']['lightgbm'] = dict(zip(X.columns, lgb_importance))
            importance_results['rankings']['lightgbm'] = self._rank_features(lgb_importance, X.columns)
        
        # 4. Correlation Analysis
        if self.config.use_correlation:
            logger.info("Computing correlation analysis...")
            correlation_matrix = X.corr().abs()
            importance_results['correlation_matrix'] = correlation_matrix
        
        # 5. Feature Stability Analysis
        importance_results['stability_scores'] = self._compute_stability_scores(importance_results)
        
        # 6. Generate Recommendations
        importance_results['recommendations'] = self._generate_recommendations(importance_results, X)
        
        # Store for historical analysis
        self.feature_importance_history.append(importance_results)
        
        return importance_results
    
    def _rank_features(self, scores: np.ndarray, feature_names: List[str]) -> List[str]:
        """Rank features by importance scores."""
        feature_scores = list(zip(feature_names, scores))
        feature_scores.sort(key=lambda x: x[1], reverse=True)
        return [feature for feature, score in feature_scores]
    
    def _compute_stability_scores(self, importance_results: Dict[str, Any]) -> Dict[str, float]:
        """Compute feature importance stability across methods."""
        
        stability_scores = {}
        methods = list(importance_results['importance_scores'].keys())
        
        if len(methods) < 2:
            return {feature: 1.0 for feature in importance_results['feature_names']}
        
        for feature in importance_results['feature_names']:
            scores = []
            for method in methods:
                if feature in importance_results['importance_scores'][method]:
                    scores.append(importance_results['importance_scores'][method][feature])
            
            if len(scores) >= 2:
                # Compute coefficient of variation (lower = more stable)
                mean_score = np.mean(scores)
                std_score = np.std(scores)
                if mean_score > 0:
                    cv = std_score / mean_score
                    stability_scores[feature] = 1.0 / (1.0 + cv)  # Convert to stability score
                else:
                    stability_scores[feature] = 0.0
            else:
                stability_scores[feature] = 0.0
        
        return stability_scores
    
    def _generate_recommendations(self, importance_results: Dict[str, Any], 
                                X: pd.DataFrame) -> Dict[str, Any]:
        """Generate feature selection recommendations."""
        
        recommendations = {
            'keep_all_features': True,  # Our philosophy: keep everything
            'high_importance_features': [],
            'low_importance_features': [],
            'correlated_feature_groups': [],
            'critical_features_preserved': [],
            'warnings': [],
            'insights': []
        }
        
        # Identify high and low importance features
        avg_importance = {}
        for feature in importance_results['feature_names']:
            scores = []
            for method, scores_dict in importance_results['importance_scores'].items():
                if feature in scores_dict:
                    scores.append(scores_dict[feature])
            
            if scores:
                avg_importance[feature] = np.mean(scores)
        
        # Sort features by average importance
        sorted_features = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)
        
        # Top 20% are high importance
        high_threshold = sorted_features[int(len(sorted_features) * 0.2)][1]
        recommendations['high_importance_features'] = [
            feature for feature, score in sorted_features if score >= high_threshold
        ]
        
        # Bottom 20% are low importance (but we still keep them)
        low_threshold = sorted_features[int(len(sorted_features) * 0.8)][1]
        recommendations['low_importance_features'] = [
            feature for feature, score in sorted_features if score <= low_threshold
        ]
        
        # Identify critical features that should always be preserved
        for feature in self.config.critical_features:
            if feature in importance_results['feature_names']:
                recommendations['critical_features_preserved'].append(feature)
                self.critical_features_preserved.add(feature)
        
        # Find highly correlated feature groups
        if 'correlation_matrix' in importance_results:
            correlation_matrix = importance_results['correlation_matrix']
            correlated_groups = self._find_correlated_groups(correlation_matrix)
            recommendations['correlated_feature_groups'] = correlated_groups
        
        # Generate insights
        recommendations['insights'] = self._generate_insights(importance_results, recommendations)
        
        return recommendations
    
    def _find_correlated_groups(self, correlation_matrix: pd.DataFrame, 
                               threshold: float = 0.95) -> List[List[str]]:
        """Find groups of highly correlated features."""
        
        correlated_groups = []
        processed_features = set()
        
        for feature in correlation_matrix.columns:
            if feature in processed_features:
                continue
            
            # Find features highly correlated with this feature
            correlations = correlation_matrix[feature]
            correlated_features = [feature] + [
                col for col in correlations.index 
                if col != feature and correlations[col] >= threshold
            ]
            
            if len(correlated_features) > 1:
                correlated_groups.append(correlated_features)
                processed_features.update(correlated_features)
        
        return correlated_groups
    
    def _generate_insights(self, importance_results: Dict[str, Any], 
                          recommendations: Dict[str, Any]) -> List[str]:
        """Generate insights about feature importance."""
        
        insights = []
        
        # Feature count insights
        total_features = importance_results['total_features']
        high_importance_count = len(recommendations['high_importance_features'])
        low_importance_count = len(recommendations['low_importance_features'])
        
        insights.append(f"Total features analyzed: {total_features}")
        insights.append(f"High importance features: {high_importance_count} ({high_importance_count/total_features*100:.1f}%)")
        insights.append(f"Low importance features: {low_importance_count} ({low_importance_count/total_features*100:.1f}%)")
        
        # Stability insights
        stability_scores = importance_results['stability_scores']
        avg_stability = np.mean(list(stability_scores.values()))
        insights.append(f"Average feature importance stability: {avg_stability:.3f}")
        
        # Critical features insights
        critical_count = len(recommendations['critical_features_preserved'])
        insights.append(f"Critical order flow features preserved: {critical_count}")
        
        # Correlation insights
        if recommendations['correlated_feature_groups']:
            correlated_count = sum(len(group) for group in recommendations['correlated_feature_groups'])
            insights.append(f"Features in correlated groups: {correlated_count}")
        
        return insights
    
    def get_feature_subset(self, X: pd.DataFrame, 
                          importance_results: Dict[str, Any],
                          subset_type: str = 'all') -> pd.DataFrame:
        """
        Get feature subset based on importance analysis.
        
        Args:
            X: Original feature matrix
            importance_results: Results from analyze_feature_importance
            subset_type: 'all', 'high_importance', 'stable', 'critical'
            
        Returns:
            Feature matrix with selected features
        """
        
        if subset_type == 'all':
            # Our philosophy: keep ALL features
            logger.info("Keeping ALL features as per QuantTime philosophy")
            return X
        
        elif subset_type == 'high_importance':
            high_importance_features = importance_results['recommendations']['high_importance_features']
            logger.info(f"Selecting {len(high_importance_features)} high importance features")
            return X[high_importance_features]
        
        elif subset_type == 'stable':
            # Features with high stability scores
            stability_scores = importance_results['stability_scores']
            stable_features = [
                feature for feature, score in stability_scores.items()
                if score >= self.config.stability_threshold
            ]
            logger.info(f"Selecting {len(stable_features)} stable features")
            return X[stable_features]
        
        elif subset_type == 'critical':
            # Critical order flow features
            critical_features = importance_results['recommendations']['critical_features_preserved']
            logger.info(f"Selecting {len(critical_features)} critical features")
            return X[critical_features]
        
        else:
            logger.warning(f"Unknown subset type: {subset_type}. Returning all features.")
            return X
    
    def track_feature_importance_over_time(self, model_results: Dict[str, Any]) -> None:
        """Track feature importance over multiple training runs."""
        
        if 'feature_importance' in model_results:
            self.feature_importance_history.append(model_results['feature_importance'])
            
            # Update stability scores
            self._update_stability_scores()
    
    def _update_stability_scores(self) -> None:
        """Update feature stability scores based on historical data."""
        
        if len(self.feature_importance_history) < 2:
            return
        
        # Compute stability across training runs
        all_features = set()
        for result in self.feature_importance_history:
            all_features.update(result['feature_names'])
        
        for feature in all_features:
            scores = []
            for result in self.feature_importance_history:
                if feature in result['feature_names']:
                    # Get average importance across methods
                    feature_scores = []
                    for method, scores_dict in result['importance_scores'].items():
                        if feature in scores_dict:
                            feature_scores.append(scores_dict[feature])
                    
                    if feature_scores:
                        scores.append(np.mean(feature_scores))
            
            if len(scores) >= 2:
                mean_score = np.mean(scores)
                std_score = np.std(scores)
                if mean_score > 0:
                    cv = std_score / mean_score
                    self.feature_stability_scores[feature] = 1.0 / (1.0 + cv)
                else:
                    self.feature_stability_scores[feature] = 0.0
    
    def save_importance_analysis(self, importance_results: Dict[str, Any], 
                               filepath: str) -> None:
        """Save feature importance analysis to file."""
        
        # Save detailed results
        joblib.dump(importance_results, filepath)
        
        # Save summary report
        summary_filepath = filepath.replace('.pkl', '_summary.txt')
        with open(summary_filepath, 'w') as f:
            f.write("QuantTime Feature Importance Analysis Summary\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Total Features Analyzed: {importance_results['total_features']}\n")
            f.write(f"Analysis Methods: {list(importance_results['importance_scores'].keys())}\n\n")
            
            f.write("Top 10 Most Important Features:\n")
            f.write("-" * 30 + "\n")
            for i, feature in enumerate(importance_results['rankings'].get('lightgbm', [])[:10]):
                f.write(f"{i+1:2d}. {feature}\n")
            
            f.write("\nCritical Features Preserved:\n")
            f.write("-" * 30 + "\n")
            for feature in importance_results['recommendations']['critical_features_preserved']:
                f.write(f"- {feature}\n")
            
            f.write("\nInsights:\n")
            f.write("-" * 10 + "\n")
            for insight in importance_results['recommendations']['insights']:
                f.write(f"- {insight}\n")
        
        logger.info(f"Feature importance analysis saved to {filepath}")
        logger.info(f"Summary report saved to {summary_filepath}")


def create_smart_feature_selector(config: FeatureImportanceConfig = None) -> SmartFeatureSelector:
    """Create a smart feature selector with the QuantTime philosophy."""
    
    if config is None:
        config = FeatureImportanceConfig()
    
    return SmartFeatureSelector(config)


def analyze_order_flow_features(features_df: pd.DataFrame, 
                              target_col: str = 'price_direction_5m') -> Dict[str, Any]:
    """
    Specialized analysis for order flow features.
    
    Args:
        features_df: DataFrame with order flow features
        target_col: Target column for analysis
        
    Returns:
        Order flow feature analysis results
    """
    
    # Identify order flow features
    order_flow_features = [
        col for col in features_df.columns 
        if any(keyword in col.lower() for keyword in [
            'volume', 'imbalance', 'absorption', 'iceberg', 'order_block',
            'bid', 'ask', 'spread', 'flow', 'pressure', 'momentum'
        ])
    ]
    
    if not order_flow_features:
        return {'order_flow_features': [], 'analysis': 'No order flow features found'}
    
    # Analyze order flow features
    X_flow = features_df[order_flow_features]
    y = features_df[target_col]
    
    # Create feature selector
    selector = SmartFeatureSelector()
    
    # Analyze importance
    importance_results = selector.analyze_feature_importance(X_flow, y, 'classification')
    
    return {
        'order_flow_features': order_flow_features,
        'importance_analysis': importance_results,
        'recommendations': importance_results['recommendations']
    }
