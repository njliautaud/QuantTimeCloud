"""
Model Analysis and Recommendation System for QuantTime.

This module provides intelligent analysis of model performance and generates
recommendations for architecture tuning based on training metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import dataclass
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ModelAnalysisResult:
    """Result of model performance analysis."""
    
    # Performance metrics
    train_accuracy: float
    val_accuracy: float
    test_accuracy: float
    overfitting_score: float
    underfitting_score: float
    
    # Training characteristics
    training_duration: float
    convergence_rate: float
    stability_score: float
    
    # Model capacity analysis
    capacity_utilization: float
    complexity_score: float
    
    # Recommendations
    recommendations: List[str]
    priority_changes: List[str]
    architecture_suggestions: Dict[str, Any]
    
    # Visualization data
    training_curves: Dict[str, List[float]]
    performance_metrics: Dict[str, float]
    
    # Trade metrics (if available)
    trade_metrics: Optional[Dict[str, Any]] = None


class ModelAnalyzer:
    """
    Analyzes model performance and provides intelligent recommendations.
    """
    
    def __init__(self):
        self.analysis_history = []
        
    def analyze_model_performance(self, 
                                training_results: Dict[str, Any],
                                model_config: Dict[str, Any],
                                model_type: str) -> ModelAnalysisResult:
        """
        Analyze model performance and generate recommendations.
        
        Args:
            training_results: Results from model training
            model_config: Model configuration used
            model_type: Type of model (lightgbm, lstm, transformer)
            
        Returns:
            ModelAnalysisResult with analysis and recommendations
        """
        
        logger.info(f"Analyzing {model_type} model performance...")
        
        # Extract performance metrics
        performance_metrics = self._extract_performance_metrics(training_results)
        
        # Analyze training characteristics
        training_analysis = self._analyze_training_characteristics(training_results)
        
        # Analyze model capacity
        capacity_analysis = self._analyze_model_capacity(model_config, model_type, performance_metrics)
        
        # Analyze trade metrics if available
        trade_analysis = self._analyze_trade_metrics(training_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            performance_metrics, training_analysis, capacity_analysis, model_type, trade_analysis
        )
        
        # Create analysis result
        result = ModelAnalysisResult(
            train_accuracy=performance_metrics.get('train_accuracy', 0.0),
            val_accuracy=performance_metrics.get('val_accuracy', 0.0),
            test_accuracy=performance_metrics.get('test_accuracy', 0.0),
            overfitting_score=training_analysis['overfitting_score'],
            underfitting_score=training_analysis['underfitting_score'],
            training_duration=training_analysis['training_duration'],
            convergence_rate=training_analysis['convergence_rate'],
            stability_score=training_analysis['stability_score'],
            capacity_utilization=capacity_analysis['capacity_utilization'],
            complexity_score=capacity_analysis['complexity_score'],
            recommendations=recommendations['general'],
            priority_changes=recommendations['priority'],
            architecture_suggestions=recommendations['architecture'],
            training_curves=training_analysis['training_curves'],
            performance_metrics=performance_metrics,
            trade_metrics=trade_analysis.get('trade_metrics')
        )
        
        # Store analysis
        self.analysis_history.append({
            'timestamp': datetime.now(),
            'model_type': model_type,
            'result': result
        })
        
        return result
    
    def _extract_performance_metrics(self, training_results: Dict[str, Any]) -> Dict[str, float]:
        """Extract performance metrics from training results."""
        
        metrics = {}
        
        # Handle different result structures
        if 'results' in training_results:
            # Standard model results
            results = training_results['results']
            for horizon, horizon_results in results.items():
                if isinstance(horizon_results, dict):
                    metrics[f'train_rmse_{horizon}'] = horizon_results.get('final_train_loss', 0.0)
                    metrics[f'val_rmse_{horizon}'] = horizon_results.get('final_val_loss', 0.0)
                    metrics[f'test_rmse_{horizon}'] = horizon_results.get('test_metrics', {}).get('rmse', 0.0)
                    metrics[f'test_r2_{horizon}'] = horizon_results.get('test_metrics', {}).get('r2', 0.0)
        elif 'success' in training_results:
            # Enhanced model results
            metrics['train_accuracy'] = training_results.get('train_accuracy', 0.0)
            metrics['val_accuracy'] = training_results.get('val_accuracy', 0.0)
            metrics['test_accuracy'] = training_results.get('test_accuracy', 0.0)
            metrics['sharpe_ratio'] = training_results.get('sharpe_ratio', 0.0)
            metrics['max_drawdown'] = training_results.get('max_drawdown', 0.0)
        
        # Calculate overall metrics
        if 'test_r2_1' in metrics:
            metrics['overall_r2'] = np.mean([v for k, v in metrics.items() if k.startswith('test_r2_')])
        if 'test_rmse_1' in metrics:
            metrics['overall_rmse'] = np.mean([v for k, v in metrics.items() if k.startswith('test_rmse_')])
        
        return metrics
    
    def _analyze_training_characteristics(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze training characteristics and patterns."""
        
        analysis = {
            'training_duration': training_results.get('training_duration_minutes', 0.0),
            'convergence_rate': 0.0,
            'stability_score': 0.0,
            'overfitting_score': 0.0,
            'underfitting_score': 0.0,
            'training_curves': {}
        }
        
        # Analyze training curves if available
        if 'training_losses' in training_results:
            training_losses = training_results['training_losses']
            val_losses = training_results.get('validation_losses', {})
            
            # Calculate convergence rate
            if training_losses:
                first_loss = list(training_losses.values())[0][0] if training_losses else 1.0
                final_loss = list(training_losses.values())[0][-1] if training_losses else 1.0
                analysis['convergence_rate'] = (first_loss - final_loss) / first_loss if first_loss > 0 else 0.0
            
            # Calculate stability score
            if training_losses:
                losses = list(training_losses.values())[0]
                if len(losses) > 1:
                    variance = np.var(losses[-10:]) if len(losses) >= 10 else np.var(losses)
                    analysis['stability_score'] = 1.0 / (1.0 + variance)
            
            # Store training curves
            analysis['training_curves'] = {
                'training_losses': training_losses,
                'validation_losses': val_losses
            }
        
        # Calculate overfitting/underfitting scores
        train_acc = training_results.get('train_accuracy', 0.0)
        val_acc = training_results.get('val_accuracy', 0.0)
        
        if train_acc > 0 and val_acc > 0:
            gap = train_acc - val_acc
            analysis['overfitting_score'] = max(0, gap / train_acc) if train_acc > 0 else 0.0
            analysis['underfitting_score'] = max(0, (0.8 - val_acc) / 0.8) if val_acc < 0.8 else 0.0
        
        return analysis
    
    def _analyze_model_capacity(self, 
                              model_config: Dict[str, Any], 
                              model_type: str,
                              performance_metrics: Dict[str, float]) -> Dict[str, float]:
        """Analyze model capacity utilization."""
        
        analysis = {
            'capacity_utilization': 0.0,
            'complexity_score': 0.0
        }
        
        # Calculate complexity score based on model type
        if model_type == "lightgbm":
            complexity = (
                model_config.get('num_leaves', 31) * 
                model_config.get('max_depth', 6) * 
                model_config.get('num_iterations', 100)
            ) / 10000  # Normalize
            analysis['complexity_score'] = min(1.0, complexity)
            
        elif model_type == "lstm":
            complexity = (
                model_config.get('hidden_size', 256) * 
                model_config.get('num_layers', 4) * 
                model_config.get('sequence_length', 200)
            ) / 1000000  # Normalize
            analysis['complexity_score'] = min(1.0, complexity)
            
        elif model_type == "transformer":
            complexity = (
                model_config.get('d_model', 512) * 
                model_config.get('num_layers', 8) * 
                model_config.get('nhead', 16) * 
                model_config.get('sequence_length', 200)
            ) / 10000000  # Normalize
            analysis['complexity_score'] = min(1.0, complexity)
        
        # Calculate capacity utilization based on performance
        overall_performance = performance_metrics.get('overall_r2', 0.0) or performance_metrics.get('test_accuracy', 0.0)
        analysis['capacity_utilization'] = overall_performance / analysis['complexity_score'] if analysis['complexity_score'] > 0 else 0.0
        
        return analysis
    
    def _analyze_trade_metrics(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trade metrics if available in training results."""
        
        analysis = {
            'trade_metrics': None,
            'trade_quality_score': 0.0,
            'trade_recommendations': []
        }
        
        # Check if trade metrics are available
        if 'trade_metrics' in training_results:
            trade_metrics = training_results['trade_metrics']
            analysis['trade_metrics'] = trade_metrics
            
            # Calculate trade quality score
            win_rate = trade_metrics.get('daily_win_rate', 0.0)
            profit_factor = trade_metrics.get('profit_factor', 0.0)
            sharpe_ratio = trade_metrics.get('sharpe_ratio', 0.0)
            
            # Simple quality score based on key metrics
            quality_score = (
                (win_rate * 0.4) + 
                (min(profit_factor / 3.0, 1.0) * 0.3) + 
                (min(sharpe_ratio / 2.0, 1.0) * 0.3)
            )
            analysis['trade_quality_score'] = quality_score
            
            # Generate trade-specific recommendations
            if win_rate < 0.5:
                analysis['trade_recommendations'].append("🟡 Consider improving entry/exit timing - low win rate")
            if profit_factor < 1.5:
                analysis['trade_recommendations'].append("🟡 Focus on risk management - low profit factor")
            if sharpe_ratio < 1.0:
                analysis['trade_recommendations'].append("🟡 Optimize position sizing - low Sharpe ratio")
            if trade_metrics.get('avg_position_hold_time_minutes', 0) > 60:
                analysis['trade_recommendations'].append("🟡 Consider shorter holding periods for better capital efficiency")
            
            # Positive feedback
            if win_rate > 0.6 and profit_factor > 2.0:
                analysis['trade_recommendations'].append("✅ Excellent trade performance - consider scaling up")
        
        return analysis
    
    def _generate_recommendations(self,
                                performance_metrics: Dict[str, float],
                                training_analysis: Dict[str, Any],
                                capacity_analysis: Dict[str, float],
                                model_type: str,
                                trade_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate intelligent recommendations for model improvement."""
        
        recommendations = {
            'general': [],
            'priority': [],
            'architecture': {}
        }
        
        # Analyze performance gaps
        train_acc = performance_metrics.get('train_accuracy', 0.0)
        val_acc = performance_metrics.get('val_accuracy', 0.0)
        test_acc = performance_metrics.get('test_accuracy', 0.0)
        
        # Overfitting recommendations
        if training_analysis['overfitting_score'] > 0.2:
            recommendations['priority'].append("🔴 HIGH PRIORITY: Model is overfitting")
            recommendations['general'].append("Reduce model complexity to prevent overfitting")
            
            if model_type == "lightgbm":
                recommendations['architecture']['reduce_max_depth'] = "Decrease max_depth by 1-2 levels"
                recommendations['architecture']['reduce_num_leaves'] = "Decrease num_leaves by 10-20"
                recommendations['architecture']['increase_regularization'] = "Add L1/L2 regularization"
            elif model_type in ["lstm", "transformer"]:
                recommendations['architecture']['increase_dropout'] = "Increase dropout rate by 0.1"
                recommendations['architecture']['reduce_layers'] = "Decrease number of layers by 1"
                recommendations['architecture']['reduce_hidden_size'] = "Decrease hidden size by 25%"
        
        # Underfitting recommendations
        elif training_analysis['underfitting_score'] > 0.3:
            recommendations['priority'].append("🟡 MEDIUM PRIORITY: Model is underfitting")
            recommendations['general'].append("Increase model capacity to capture more patterns")
            
            if model_type == "lightgbm":
                recommendations['architecture']['increase_max_depth'] = "Increase max_depth by 1-2 levels"
                recommendations['architecture']['increase_num_leaves'] = "Increase num_leaves by 20-30"
                recommendations['architecture']['increase_iterations'] = "Increase num_iterations by 50"
            elif model_type in ["lstm", "transformer"]:
                recommendations['architecture']['increase_layers'] = "Add 1-2 more layers"
                recommendations['architecture']['increase_hidden_size'] = "Increase hidden size by 25%"
                recommendations['architecture']['decrease_dropout'] = "Decrease dropout rate by 0.1"
        
        # Good performance recommendations
        else:
            recommendations['general'].append("✅ Model performance is well-balanced")
            recommendations['general'].append("Consider fine-tuning for marginal improvements")
            
            # Suggest optimizations
            if capacity_analysis['capacity_utilization'] < 0.5:
                recommendations['architecture']['optimize_learning_rate'] = "Try reducing learning rate by 20%"
                recommendations['architecture']['increase_training_time'] = "Train for more epochs"
        
        # Training stability recommendations
        if training_analysis['stability_score'] < 0.5:
            recommendations['general'].append("Training is unstable - consider reducing learning rate")
            recommendations['architecture']['reduce_learning_rate'] = "Decrease learning rate by 50%"
        
        # Convergence recommendations
        if training_analysis['convergence_rate'] < 0.3:
            recommendations['general'].append("Model may not have converged - train longer")
            recommendations['architecture']['increase_epochs'] = "Increase training epochs by 50%"
        
        # Trade-specific recommendations
        if trade_analysis.get('trade_recommendations'):
            recommendations['general'].extend(trade_analysis['trade_recommendations'])
        
        return recommendations
    
    def generate_visualization_data(self, analysis_result: ModelAnalysisResult) -> Dict[str, Any]:
        """Generate data for visualizations."""
        
        viz_data = {
            'performance_metrics': {
                'Train Accuracy': analysis_result.train_accuracy,
                'Validation Accuracy': analysis_result.val_accuracy,
                'Test Accuracy': analysis_result.test_accuracy
            },
            'training_analysis': {
                'Overfitting Score': analysis_result.overfitting_score,
                'Underfitting Score': analysis_result.underfitting_score,
                'Stability Score': analysis_result.stability_score,
                'Convergence Rate': analysis_result.convergence_rate
            },
            'capacity_analysis': {
                'Capacity Utilization': analysis_result.capacity_utilization,
                'Complexity Score': analysis_result.complexity_score
            },
            'training_curves': analysis_result.training_curves
        }
        
        return viz_data


def create_model_analyzer() -> ModelAnalyzer:
    """Factory function to create model analyzer."""
    return ModelAnalyzer()
