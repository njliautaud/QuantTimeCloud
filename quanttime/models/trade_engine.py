"""
Trade Engine for QuantTime ML Trading Suite.

This module implements a comprehensive trade engine that:
- Combines predictions from multiple models with weights
- Implements risk management and position sizing
- Handles order flow pattern recognition
- Provides backtesting and live trading capabilities
- Uses 1 contract position sizing with 6 trading strategies
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import warnings

from .base import ModelBase, TrainingMetrics
from ..features.mbo_feature_engineering import MBOFeatureEngineer

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types supported by the trade engine."""
    MARKET = "market"
    BID = "bid"  # Market order at bid price
    LIMIT = "limit"


class PositionSide(Enum):
    """Position sides."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class TradingStrategy(Enum):
    """Trading strategies available."""
    BUY_MARKET = "buy_market"
    BUY_BID = "buy_bid"
    BUY_LIMIT = "buy_limit"
    SELL_MARKET = "sell_market"
    SELL_BID = "sell_bid"
    SELL_LIMIT = "sell_limit"


@dataclass
class TradeSignal:
    """Trade signal from model prediction."""
    timestamp: datetime
    model_name: str
    prediction_horizon: int
    predicted_direction: float  # -1 to 1 (negative = down, positive = up)
    predicted_price_change: float
    confidence: float  # 0 to 1
    order_flow_patterns: Dict[str, float]  # Pattern confidence scores
    price_target: float
    stop_loss: float
    take_profit: float
    recommended_strategy: TradingStrategy
    limit_price: Optional[float] = None  # For limit orders


@dataclass
class Position:
    """Current trading position."""
    side: PositionSide
    size: int = 1  # Always 1 contract
    entry_price: float = 0.0
    entry_time: datetime = None
    current_price: float = 0.0
    unrealized_pnl_ticks: float = 0.0
    unrealized_pnl_dollars: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    strategy_used: TradingStrategy = None


@dataclass
class TradeEngineConfig:
    """Configuration for the trade engine."""
    # Model weights (must sum to 100)
    model_weights: Dict[str, float]
    
    # Risk management
    max_drawdown: float = 0.05  # 5% max drawdown
    stop_loss_ticks: int = 10  # Stop loss in ticks
    take_profit_ticks: int = 20  # Take profit in ticks
    
    # Signal thresholds
    min_confidence: float = 0.6  # Minimum confidence to trade
    min_direction_strength: float = 0.3  # Minimum direction strength
    
    # Order flow patterns
    iceberg_threshold: float = 0.7  # Confidence threshold for iceberg detection
    order_block_threshold: float = 0.6  # Confidence threshold for order blocks
    absorption_threshold: float = 0.5  # Confidence threshold for absorption
    
    # Trading constraints
    min_trade_duration_seconds: int = 10  # Minimum time between trades
    max_trades_per_hour: int = 10  # Maximum trades per hour
    
    # ES Futures specific
    tick_size: float = 0.25  # ES tick size
    tick_value: float = 12.50  # ES tick value ($12.50 per tick)
    contract_size: int = 1  # Always 1 contract


class OrderFlowPatternDetector:
    """
    Detects order flow patterns from MBO data.
    
    Patterns detected:
    - Iceberg orders (large hidden orders)
    - Order blocks (significant support/resistance)
    - Absorption (price rejection at levels)
    - Large order levels
    - Reversal patterns
    """
    
    def __init__(self, config: TradeEngineConfig):
        """Initialize pattern detector."""
        self.config = config
        self.feature_engineer = MBOFeatureEngineer()
        
    def detect_iceberg_orders(self, mbo_df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect iceberg orders (large hidden orders).
        
        Returns:
            Dictionary with iceberg confidence scores
        """
        # Calculate volume imbalances
        buy_volume = mbo_df[mbo_df['side'] == 'buy']['size'].sum()
        sell_volume = mbo_df[mbo_df['side'] == 'sell']['size'].sum()
        
        # Look for sustained volume in one direction
        volume_imbalance = (buy_volume - sell_volume) / (buy_volume + sell_volume)
        
        # Detect large orders that don't move price significantly
        price_impact = mbo_df['price'].pct_change().abs().mean()
        volume_impact = mbo_df['size'].sum() / len(mbo_df)
        
        # Iceberg confidence based on volume imbalance and low price impact
        iceberg_confidence = min(abs(volume_imbalance) * (1 - price_impact), 1.0)
        
        return {
            'iceberg_buy': iceberg_confidence if volume_imbalance > 0 else 0.0,
            'iceberg_sell': iceberg_confidence if volume_imbalance < 0 else 0.0,
            'iceberg_confidence': iceberg_confidence
        }
    
    def detect_order_blocks(self, mbo_df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect order blocks (significant support/resistance levels).
        
        Returns:
            Dictionary with order block confidence scores
        """
        # Find price levels with high volume
        price_levels = mbo_df.groupby('price')['size'].sum().sort_values(ascending=False)
        
        # Identify significant levels (top 10% by volume)
        threshold = price_levels.quantile(0.9)
        significant_levels = price_levels[price_levels > threshold]
        
        current_price = mbo_df['price'].iloc[-1]
        
        # Find nearest support and resistance
        support_levels = significant_levels[significant_levels.index < current_price]
        resistance_levels = significant_levels[significant_levels.index > current_price]
        
        nearest_support = support_levels.index[-1] if len(support_levels) > 0 else None
        nearest_resistance = resistance_levels.index[0] if len(resistance_levels) > 0 else None
        
        # Calculate confidence based on volume at levels
        support_confidence = 0.0
        resistance_confidence = 0.0
        
        if nearest_support is not None:
            support_volume = significant_levels[nearest_support]
            support_confidence = min(support_volume / significant_levels.max(), 1.0)
        
        if nearest_resistance is not None:
            resistance_volume = significant_levels[nearest_resistance]
            resistance_confidence = min(resistance_volume / significant_levels.max(), 1.0)
        
        return {
            'support_level': nearest_support,
            'resistance_level': nearest_resistance,
            'support_confidence': support_confidence,
            'resistance_confidence': resistance_confidence,
            'order_block_confidence': max(support_confidence, resistance_confidence)
        }
    
    def detect_absorption(self, mbo_df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect absorption (price rejection at levels).
        
        Returns:
            Dictionary with absorption confidence scores
        """
        # Calculate price movements and volume
        price_changes = mbo_df['price'].pct_change()
        volumes = mbo_df['size']
        
        # Look for price rejection with high volume
        rejection_threshold = 0.001  # 0.1% price movement
        
        # Find periods where price moved significantly but then reversed
        significant_moves = abs(price_changes) > rejection_threshold
        
        absorption_signals = []
        for i in range(1, len(mbo_df)):
            if significant_moves.iloc[i]:
                # Check if price reversed in next few ticks
                future_prices = mbo_df['price'].iloc[i:i+5]
                if len(future_prices) > 1:
                    reversal = (price_changes.iloc[i] > 0 and future_prices.iloc[-1] < mbo_df['price'].iloc[i]) or \
                              (price_changes.iloc[i] < 0 and future_prices.iloc[-1] > mbo_df['price'].iloc[i])
                    
                    if reversal:
                        volume_at_level = volumes.iloc[i]
                        absorption_signals.append({
                            'timestamp': mbo_df.index[i],
                            'price': mbo_df['price'].iloc[i],
                            'volume': volume_at_level,
                            'direction': 'buy' if price_changes.iloc[i] < 0 else 'sell'
                        })
        
        # Calculate absorption confidence
        absorption_confidence = 0.0
        if absorption_signals:
            total_volume = sum(signal['volume'] for signal in absorption_signals)
            avg_volume = total_volume / len(absorption_signals)
            absorption_confidence = min(avg_volume / volumes.mean(), 1.0)
        
        return {
            'absorption_confidence': absorption_confidence,
            'absorption_signals': len(absorption_signals),
            'absorption_volume': sum(signal['volume'] for signal in absorption_signals) if absorption_signals else 0
        }
    
    def detect_patterns(self, mbo_df: pd.DataFrame) -> Dict[str, float]:
        """
        Detect all order flow patterns.
        
        Returns:
            Dictionary with all pattern confidence scores
        """
        patterns = {}
        
        # Detect individual patterns
        iceberg_patterns = self.detect_iceberg_orders(mbo_df)
        order_block_patterns = self.detect_order_blocks(mbo_df)
        absorption_patterns = self.detect_absorption(mbo_df)
        
        # Combine patterns
        patterns.update(iceberg_patterns)
        patterns.update(order_block_patterns)
        patterns.update(absorption_patterns)
        
        # Calculate overall pattern confidence
        pattern_confidences = [
            iceberg_patterns.get('iceberg_confidence', 0.0),
            order_block_patterns.get('order_block_confidence', 0.0),
            absorption_patterns.get('absorption_confidence', 0.0)
        ]
        
        patterns['overall_pattern_confidence'] = np.mean(pattern_confidences)
        
        return patterns


class TradeEngine:
    """
    Main trade engine that combines model predictions and executes trades.
    Uses 1 contract position sizing with 6 trading strategies.
    """
    
    def __init__(self, config: TradeEngineConfig):
        """Initialize trade engine."""
        self.config = config
        self.pattern_detector = OrderFlowPatternDetector(config)
        
        # Validate model weights
        total_weight = sum(config.model_weights.values())
        if abs(total_weight - 100.0) > 0.01:
            raise ValueError(f"Model weights must sum to 100, got {total_weight}")
        
        # Trading state
        self.current_position = Position(
            side=PositionSide.FLAT,
            size=1,  # Always 1 contract
            entry_price=0.0,
            entry_time=datetime.now(),
            current_price=0.0,
            unrealized_pnl_ticks=0.0,
            unrealized_pnl_dollars=0.0,
            stop_loss=0.0,
            take_profit=0.0
        )
        
        self.trade_history = []
        self.portfolio_value = 100000.0  # Starting portfolio value
        self.max_portfolio_value = 100000.0
        
        # Performance tracking
        self.direction_accuracy = {}
        self.price_accuracy = {}
        self.pattern_accuracy = {}
        
        # Strategy performance tracking
        self.strategy_performance = {strategy: {'wins': 0, 'losses': 0, 'pnl': 0.0} for strategy in TradingStrategy}
        
        logger.info(f"Trade engine initialized with {len(config.model_weights)} models")
    
    def _select_trading_strategy(self, signal: TradeSignal, current_price: float, 
                               bid_price: float, ask_price: float) -> Tuple[TradingStrategy, float]:
        """
        Select the best trading strategy based on signal and market conditions.
        
        Returns:
            Tuple of (strategy, execution_price)
        """
        direction = signal.predicted_direction
        patterns = signal.order_flow_patterns
        
        # Check for absorption patterns (good for limit orders)
        absorption_confidence = patterns.get('absorption_confidence', 0.0)
        order_block_confidence = patterns.get('order_block_confidence', 0.0)
        
        if direction > 0:  # Bullish signal
            if absorption_confidence > 0.6 or order_block_confidence > 0.6:
                # Use limit order near support level
                support_level = patterns.get('support_level', current_price - self.config.tick_size * 5)
                return TradingStrategy.BUY_LIMIT, support_level
            elif signal.confidence > 0.8:
                # High confidence - use market order
                return TradingStrategy.BUY_MARKET, ask_price
            else:
                # Medium confidence - use bid order
                return TradingStrategy.BUY_BID, bid_price
        else:  # Bearish signal
            if absorption_confidence > 0.6 or order_block_confidence > 0.6:
                # Use limit order near resistance level
                resistance_level = patterns.get('resistance_level', current_price + self.config.tick_size * 5)
                return TradingStrategy.SELL_LIMIT, resistance_level
            elif signal.confidence > 0.8:
                # High confidence - use market order
                return TradingStrategy.SELL_MARKET, bid_price
            else:
                # Medium confidence - use bid order
                return TradingStrategy.SELL_BID, ask_price
    
    def combine_model_predictions(self, 
                                model_predictions: Dict[str, Dict[str, Any]],
                                mbo_df: pd.DataFrame) -> TradeSignal:
        """
        Combine predictions from multiple models with weights.
        
        Args:
            model_predictions: Dictionary of model predictions
            mbo_df: Current MBO data
            
        Returns:
            Combined trade signal
        """
        if not model_predictions:
            raise ValueError("No model predictions provided")
        
        # Detect order flow patterns
        patterns = self.pattern_detector.detect_patterns(mbo_df)
        
        # Combine weighted predictions
        weighted_direction = 0.0
        weighted_price_change = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0
        
        current_price = mbo_df['price'].iloc[-1]
        timestamp = mbo_df.index[-1] if hasattr(mbo_df.index[-1], 'to_pydatetime') else datetime.now()
        
        # Estimate bid/ask prices (simplified)
        bid_price = current_price - self.config.tick_size
        ask_price = current_price + self.config.tick_size
        
        for model_name, prediction in model_predictions.items():
            if model_name not in self.config.model_weights:
                continue
            
            weight = self.config.model_weights[model_name] / 100.0
            
            # Extract prediction components
            direction = prediction.get('direction', 0.0)
            price_change = prediction.get('price_change', 0.0)
            confidence = prediction.get('confidence', 0.5)
            horizon = prediction.get('horizon', 1)
            
            # Apply weights
            weighted_direction += direction * weight
            weighted_price_change += price_change * weight
            weighted_confidence += confidence * weight
            total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            weighted_direction /= total_weight
            weighted_price_change /= total_weight
            weighted_confidence /= total_weight
        
        # Calculate price target
        price_target = current_price * (1 + weighted_price_change)
        
        # Calculate stop loss and take profit in ticks
        stop_loss_ticks = self.config.stop_loss_ticks
        take_profit_ticks = self.config.take_profit_ticks
        
        if weighted_direction > 0:  # Long position
            stop_loss = current_price - (stop_loss_ticks * self.config.tick_size)
            take_profit = current_price + (take_profit_ticks * self.config.tick_size)
        else:  # Short position
            stop_loss = current_price + (stop_loss_ticks * self.config.tick_size)
            take_profit = current_price - (take_profit_ticks * self.config.tick_size)
        
        # Select trading strategy
        strategy, execution_price = self._select_trading_strategy(
            TradeSignal(
                timestamp=timestamp,
                model_name="ensemble",
                prediction_horizon=1,
                predicted_direction=weighted_direction,
                predicted_price_change=weighted_price_change,
                confidence=weighted_confidence,
                order_flow_patterns=patterns,
                price_target=price_target,
                stop_loss=stop_loss,
                take_profit=take_profit,
                recommended_strategy=TradingStrategy.BUY_MARKET
            ),
            current_price, bid_price, ask_price
        )
        
        # Create trade signal
        signal = TradeSignal(
            timestamp=timestamp,
            model_name="ensemble",
            prediction_horizon=1,  # Default to 1 minute
            predicted_direction=weighted_direction,
            predicted_price_change=weighted_price_change,
            confidence=weighted_confidence,
            order_flow_patterns=patterns,
            price_target=price_target,
            stop_loss=stop_loss,
            take_profit=take_profit,
            recommended_strategy=strategy,
            limit_price=execution_price if strategy in [TradingStrategy.BUY_LIMIT, TradingStrategy.SELL_LIMIT] else None
        )
        
        return signal
    
    def should_trade(self, signal: TradeSignal) -> Tuple[bool, str]:
        """
        Determine if we should trade based on the signal.
        
        Returns:
            Tuple of (should_trade, reason)
        """
        # Check confidence threshold
        if signal.confidence < self.config.min_confidence:
            return False, f"Confidence {signal.confidence:.3f} below threshold {self.config.min_confidence}"
        
        # Check direction strength
        if abs(signal.predicted_direction) < self.config.min_direction_strength:
            return False, f"Direction strength {abs(signal.predicted_direction):.3f} below threshold {self.config.min_direction_strength}"
        
        # Check drawdown limit
        current_drawdown = (self.max_portfolio_value - self.portfolio_value) / self.max_portfolio_value
        if current_drawdown > self.config.max_drawdown:
            return False, f"Drawdown {current_drawdown:.3f} above limit {self.config.max_drawdown}"
        
        # Check if we already have a position
        if self.current_position.side != PositionSide.FLAT:
            return False, "Already have an open position"
        
        # Check order flow patterns
        pattern_confidence = signal.order_flow_patterns.get('overall_pattern_confidence', 0.0)
        if pattern_confidence < 0.3:  # Minimum pattern confidence
            return False, f"Pattern confidence {pattern_confidence:.3f} too low"
        
        return True, "Signal meets all criteria"
    
    def execute_trade(self, signal: TradeSignal, current_price: float) -> Optional[Dict[str, Any]]:
        """
        Execute a trade based on the signal.
        
        Returns:
            Trade execution details or None if no trade
        """
        should_trade, reason = self.should_trade(signal)
        
        if not should_trade:
            logger.info(f"No trade executed: {reason}")
            return None
        
        # Determine position side
        if signal.predicted_direction > 0:
            position_side = PositionSide.LONG
        else:
            position_side = PositionSide.SHORT
        
        # Determine execution price based on strategy
        execution_price = current_price
        if signal.recommended_strategy in [TradingStrategy.BUY_LIMIT, TradingStrategy.SELL_LIMIT]:
            execution_price = signal.limit_price
        elif signal.recommended_strategy in [TradingStrategy.BUY_BID, TradingStrategy.SELL_BID]:
            # Use bid/ask prices (simplified)
            if position_side == PositionSide.LONG:
                execution_price = current_price + self.config.tick_size  # Ask price
            else:
                execution_price = current_price - self.config.tick_size  # Bid price
        
        # Update current position
        self.current_position = Position(
            side=position_side,
            size=1,  # Always 1 contract
            entry_price=execution_price,
            entry_time=signal.timestamp,
            current_price=execution_price,
            unrealized_pnl_ticks=0.0,
            unrealized_pnl_dollars=0.0,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy_used=signal.recommended_strategy
        )
        
        # Record trade
        trade = {
            'timestamp': signal.timestamp,
            'side': position_side.value,
            'size': 1,  # Always 1 contract
            'entry_price': execution_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'confidence': signal.confidence,
            'predicted_direction': signal.predicted_direction,
            'predicted_price_change': signal.predicted_price_change,
            'patterns': signal.order_flow_patterns,
            'strategy': signal.recommended_strategy.value,
            'execution_price': execution_price
        }
        
        self.trade_history.append(trade)
        
        logger.info(f"Trade executed: {position_side.value} 1 contract at {execution_price:.2f} using {signal.recommended_strategy.value}")
        
        return trade
    
    def update_position(self, current_price: float) -> Optional[Dict[str, Any]]:
        """
        Update current position and check for exit conditions.
        
        Returns:
            Exit trade details or None if position remains open
        """
        if self.current_position.side == PositionSide.FLAT:
            return None
        
        # Update position
        self.current_position.current_price = current_price
        
        # Calculate unrealized P&L in ticks and dollars
        if self.current_position.side == PositionSide.LONG:
            price_diff = current_price - self.current_position.entry_price
        else:
            price_diff = self.current_position.entry_price - current_price
        
        self.current_position.unrealized_pnl_ticks = price_diff / self.config.tick_size
        self.current_position.unrealized_pnl_dollars = self.current_position.unrealized_pnl_ticks * self.config.tick_value
        
        # Check exit conditions
        exit_reason = None
        
        # Stop loss
        if self.current_position.side == PositionSide.LONG and current_price <= self.current_position.stop_loss:
            exit_reason = "stop_loss"
        elif self.current_position.side == PositionSide.SHORT and current_price >= self.current_position.stop_loss:
            exit_reason = "stop_loss"
        
        # Take profit
        elif self.current_position.side == PositionSide.LONG and current_price >= self.current_position.take_profit:
            exit_reason = "take_profit"
        elif self.current_position.side == PositionSide.SHORT and current_price <= self.current_position.take_profit:
            exit_reason = "take_profit"
        
        if exit_reason:
            # Close position
            exit_trade = {
                'timestamp': datetime.now(),
                'side': 'close',
                'size': 1,  # Always 1 contract
                'exit_price': current_price,
                'exit_reason': exit_reason,
                'realized_pnl_ticks': self.current_position.unrealized_pnl_ticks,
                'realized_pnl_dollars': self.current_position.unrealized_pnl_dollars,
                'strategy': self.current_position.strategy_used.value if self.current_position.strategy_used else 'unknown'
            }
            
            # Update portfolio value
            self.portfolio_value += self.current_position.unrealized_pnl_dollars
            self.max_portfolio_value = max(self.max_portfolio_value, self.portfolio_value)
            
            # Update strategy performance
            if self.current_position.strategy_used:
                strategy = self.current_position.strategy_used.value
                if self.current_position.unrealized_pnl_dollars > 0:
                    self.strategy_performance[strategy]['wins'] += 1
                else:
                    self.strategy_performance[strategy]['losses'] += 1
                self.strategy_performance[strategy]['pnl'] += self.current_position.unrealized_pnl_dollars
            
            # Reset position
            self.current_position = Position(
                side=PositionSide.FLAT,
                size=1,
                entry_price=0.0,
                entry_time=datetime.now(),
                current_price=0.0,
                unrealized_pnl_ticks=0.0,
                unrealized_pnl_dollars=0.0,
                stop_loss=0.0,
                take_profit=0.0
            )
            
            logger.info(f"Position closed: {exit_reason} at {current_price:.2f}, P&L: {exit_trade['realized_pnl_ticks']:.1f} ticks (${exit_trade['realized_pnl_dollars']:.2f})")
            
            return exit_trade
        
        return None
    
    def evaluate_prediction_accuracy(self, 
                                   prediction: Dict[str, Any], 
                                   actual_price: float,
                                   actual_direction: float) -> Dict[str, float]:
        """
        Evaluate prediction accuracy for a model.
        
        Returns:
            Dictionary with accuracy metrics
        """
        predicted_price = prediction.get('price_target', 0.0)
        predicted_direction = prediction.get('direction', 0.0)
        
        # Direction accuracy
        direction_correct = (predicted_direction > 0 and actual_direction > 0) or \
                           (predicted_direction < 0 and actual_direction < 0)
        direction_accuracy = 1.0 if direction_correct else 0.0
        
        # Price accuracy (how close to target)
        if predicted_price > 0:
            price_error = abs(actual_price - predicted_price) / predicted_price
            price_accuracy = max(0.0, 1.0 - price_error)
        else:
            price_accuracy = 0.0
        
        # Pattern accuracy (if patterns were predicted)
        pattern_accuracy = 0.0
        if 'patterns' in prediction:
            predicted_patterns = prediction['patterns']
            # This would need to be compared with actual pattern detection
            # For now, use a placeholder
            pattern_accuracy = 0.5
        
        return {
            'direction_accuracy': direction_accuracy,
            'price_accuracy': price_accuracy,
            'pattern_accuracy': pattern_accuracy,
            'overall_accuracy': (direction_accuracy + price_accuracy + pattern_accuracy) / 3.0
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary with financial metrics."""
        if not self.trade_history:
            return {"message": "No trades executed"}
        
        # Calculate basic metrics
        total_trades = len(self.trade_history)
        winning_trades = len([t for t in self.trade_history if t.get('realized_pnl_dollars', 0) > 0])
        losing_trades = len([t for t in self.trade_history if t.get('realized_pnl_dollars', 0) < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        
        # Calculate P&L metrics
        total_pnl_dollars = sum(t.get('realized_pnl_dollars', 0) for t in self.trade_history)
        total_pnl_ticks = sum(t.get('realized_pnl_ticks', 0) for t in self.trade_history)
        
        avg_win_dollars = np.mean([t.get('realized_pnl_dollars', 0) for t in self.trade_history if t.get('realized_pnl_dollars', 0) > 0]) if winning_trades > 0 else 0.0
        avg_loss_dollars = np.mean([t.get('realized_pnl_dollars', 0) for t in self.trade_history if t.get('realized_pnl_dollars', 0) < 0]) if losing_trades > 0 else 0.0
        
        avg_win_ticks = np.mean([t.get('realized_pnl_ticks', 0) for t in self.trade_history if t.get('realized_pnl_ticks', 0) > 0]) if winning_trades > 0 else 0.0
        avg_loss_ticks = np.mean([t.get('realized_pnl_ticks', 0) for t in self.trade_history if t.get('realized_pnl_ticks', 0) < 0]) if losing_trades > 0 else 0.0
        
        profit_factor = abs(avg_win_dollars * winning_trades / (avg_loss_dollars * losing_trades)) if avg_loss_dollars != 0 else float('inf')
        
        # Calculate drawdown
        portfolio_values = [100000.0]  # Starting value
        for trade in self.trade_history:
            if 'realized_pnl_dollars' in trade:
                portfolio_values.append(portfolio_values[-1] + trade['realized_pnl_dollars'])
        
        max_value = max(portfolio_values)
        current_value = portfolio_values[-1]
        max_drawdown = (max_value - current_value) / max_value if max_value > 0 else 0.0
        
        # Calculate Sharpe ratio (simplified)
        returns = []
        for i in range(1, len(portfolio_values)):
            returns.append((portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1])
        
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0.0
        
        # Calculate Sortino ratio
        negative_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(negative_returns) if negative_returns else 0.0
        sortino_ratio = np.mean(returns) / downside_deviation * np.sqrt(252) if downside_deviation > 0 else 0.0
        
        # Calculate Calmar ratio
        calmar_ratio = (np.mean(returns) * 252) / max_drawdown if max_drawdown > 0 else 0.0
        
        # Calculate VaR and CVaR (95% confidence)
        if returns:
            var_95 = np.percentile(returns, 5)  # 5th percentile
            cvar_95 = np.mean([r for r in returns if r <= var_95]) if var_95 is not None else 0.0
        else:
            var_95 = 0.0
            cvar_95 = 0.0
        
        # Strategy performance
        strategy_metrics = {}
        for strategy, perf in self.strategy_performance.items():
            total_strategy_trades = perf['wins'] + perf['losses']
            if total_strategy_trades > 0:
                strategy_win_rate = perf['wins'] / total_strategy_trades
                strategy_metrics[strategy] = {
                    'total_trades': total_strategy_trades,
                    'wins': perf['wins'],
                    'losses': perf['losses'],
                    'win_rate': strategy_win_rate,
                    'total_pnl': perf['pnl'],
                    'avg_pnl_per_trade': perf['pnl'] / total_strategy_trades
                }
        
        return {
            # Basic metrics
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            
            # P&L metrics
            'total_pnl_dollars': total_pnl_dollars,
            'total_pnl_ticks': total_pnl_ticks,
            'avg_win_dollars': avg_win_dollars,
            'avg_loss_dollars': avg_loss_dollars,
            'avg_win_ticks': avg_win_ticks,
            'avg_loss_ticks': avg_loss_ticks,
            'profit_factor': profit_factor,
            
            # Risk metrics
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'var_95': var_95,
            'cvar_95': cvar_95,
            
            # Portfolio metrics
            'current_portfolio_value': self.portfolio_value,
            'return_pct': (self.portfolio_value - 100000.0) / 100000.0 * 100,
            
            # Strategy metrics
            'strategy_performance': strategy_metrics,
            
            # ES Futures specific
            'tick_size': self.config.tick_size,
            'tick_value': self.config.tick_value,
            'contract_size': self.config.contract_size
        }


def create_trade_engine(model_weights: Dict[str, float], **kwargs) -> TradeEngine:
    """Factory function to create trade engine."""
    config = TradeEngineConfig(
        model_weights=model_weights,
        **kwargs
    )
    return TradeEngine(config)
