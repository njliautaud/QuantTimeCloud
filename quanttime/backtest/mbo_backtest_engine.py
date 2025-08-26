"""
MBO (Market By Order) Level 3 Backtesting Engine

A comprehensive backtesting engine designed specifically for MBO data,
featuring realistic fill simulation, slippage modeling, and market impact analysis.
Now with live-like walk-forward analysis and session-based data splits.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from enum import Enum
import random

from quanttime.features.mbo_features import FeatureConfig, MBOFeatureEngineer
from quanttime.adapter.databento_mbo import DatabentoMBOReader

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class TradingSession(Enum):
    ASIA = "asia"      # 00:00-08:00 UTC
    LONDON = "london"  # 08:00-16:00 UTC
    NEW_YORK = "ny"    # 13:00-21:00 UTC
    OVERNIGHT = "overnight"  # 21:00-00:00 UTC


@dataclass
class Order:
    """Represents a trading order."""
    id: str
    timestamp: datetime
    side: OrderSide
    order_type: OrderType
    size: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    filled_size: int = 0
    filled_price: float = 0.0
    status: str = "pending"  # pending, filled, cancelled, rejected
    fills: List[Dict] = field(default_factory=list)
    
    @property
    def is_filled(self) -> bool:
        return self.filled_size >= self.size
    
    @property
    def remaining_size(self) -> int:
        return self.size - self.filled_size


@dataclass
class Trade:
    """Represents a completed trade."""
    id: str
    timestamp: datetime
    side: OrderSide
    size: int
    price: float
    order_id: str
    slippage: float = 0.0
    market_impact: float = 0.0


@dataclass
class Position:
    """Represents a trading position."""
    size: int = 0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    
    def update(self, trade: Trade):
        """Update position with a new trade."""
        if self.size == 0:
            # Opening position
            self.size = trade.size if trade.side == OrderSide.BUY else -trade.size
            self.avg_price = trade.price
        else:
            # Adding to existing position
            if (self.size > 0 and trade.side == OrderSide.BUY) or (self.size < 0 and trade.side == OrderSide.SELL):
                # Same direction - update average price
                total_cost = self.size * self.avg_price + trade.size * trade.price
                self.size += trade.size if trade.side == OrderSide.BUY else -trade.size
                self.avg_price = total_cost / abs(self.size)
            else:
                # Opposite direction - calculate realized P&L
                if self.size > 0:  # Long position
                    if trade.side == OrderSide.SELL:
                        realized_pnl = (trade.price - self.avg_price) * min(trade.size, self.size)
                        self.realized_pnl += realized_pnl
                        self.size -= trade.size
                        if self.size <= 0:
                            self.size = 0
                            self.avg_price = 0.0
                else:  # Short position
                    if trade.side == OrderSide.BUY:
                        realized_pnl = (self.avg_price - trade.price) * min(trade.size, abs(self.size))
                        self.realized_pnl += realized_pnl
                        self.size += trade.size
                        if self.size >= 0:
                            self.size = 0
                            self.avg_price = 0.0
        
        self.total_pnl = self.realized_pnl + self.unrealized_pnl


@dataclass
class BacktestConfig:
    """Configuration for MBO backtesting."""
    # Trading parameters
    initial_capital: float = 100000.0
    commission_per_contract: float = 2.4
    slippage_ticks: float = 0.5
    tick_size: float = 0.25
    
    # Risk management
    max_position_size: int = 100
    max_daily_loss: float = 5000.0
    stop_loss_ticks: Optional[int] = None
    take_profit_ticks: Optional[int] = None
    
    # Market impact modeling
    market_impact_model: str = "linear"  # linear, square_root, none
    impact_coefficient: float = 0.0001
    
    # Fill modeling
    fill_probability: float = 1.0  # Probability of getting filled at limit price
    partial_fills: bool = True
    min_fill_size: int = 1
    
    # Data processing
    batch_size: int = 50000
    feature_config: FeatureConfig = field(default_factory=FeatureConfig)
    
    # Walk-forward parameters
    walk_forward_window_days: int = 30
    walk_forward_step_days: int = 7
    live_mode: bool = True  # Process tick-by-tick like live trading
    
    # Session-based splits
    session_split_seed: int = 42
    train_session_ratio: float = 0.6
    val_session_ratio: float = 0.2
    test_session_ratio: float = 0.2
    
    # Trading strategy parameters (multi-second to multi-minute focus)
    min_hold_time_seconds: int = 30      # Minimum time to hold a position
    max_hold_time_minutes: int = 30      # Maximum time to hold a position
    position_sizing_method: str = "fixed"  # fixed, kelly, volatility
    risk_per_trade: float = 0.02         # 2% risk per trade
    
    # Model prediction horizons (1-5 minutes)
    prediction_horizons: List[int] = field(default_factory=lambda: [1, 3, 5])


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    # Performance metrics
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    
    # Trading statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    
    # Risk metrics
    volatility: float
    var_95: float
    cvar_95: float
    
    # Detailed data
    trades: List[Trade]
    positions: List[Position]
    equity_curve: pd.DataFrame
    daily_returns: pd.Series
    
    # MBO-specific metrics
    total_volume_traded: int
    avg_slippage: float
    avg_market_impact: float
    fill_rate: float
    
    # Walk-forward metrics
    walk_forward_periods: int
    avg_period_return: float
    period_consistency: float  # Standard deviation of period returns


class SessionSplitter:
    """Handles session-based data splitting for robust model training."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
    
    def get_trading_session(self, timestamp: datetime) -> TradingSession:
        """Determine trading session based on timestamp."""
        hour = timestamp.hour
        
        if 0 <= hour < 8:
            return TradingSession.ASIA
        elif 8 <= hour < 16:
            return TradingSession.LONDON
        elif 13 <= hour < 21:
            return TradingSession.NEW_YORK
        else:
            return TradingSession.OVERNIGHT
    
    def split_data_by_sessions(self, mbo_df: pd.DataFrame, 
                              train_ratio: float = 0.6,
                              val_ratio: float = 0.2,
                              test_ratio: float = 0.2) -> Dict[str, pd.DataFrame]:
        """Split data by trading sessions with randomization."""
        
        # Add datetime and session columns
        mbo_df = mbo_df.copy()
        mbo_df['datetime'] = pd.to_datetime(mbo_df['ts_event'], unit='ns')
        mbo_df['session'] = mbo_df['datetime'].apply(self.get_trading_session)
        mbo_df['date'] = mbo_df['datetime'].dt.date
        
        # Get unique sessions and dates
        sessions = mbo_df['session'].unique()
        dates = mbo_df['date'].unique()
        
        # Randomize sessions and dates
        random.shuffle(sessions)
        random.shuffle(dates)
        
        # Split sessions
        n_sessions = len(sessions)
        n_train = int(n_sessions * train_ratio)
        n_val = int(n_sessions * val_ratio)
        
        train_sessions = sessions[:n_train]
        val_sessions = sessions[n_train:n_train + n_val]
        test_sessions = sessions[n_train + n_val:]
        
        # Split dates
        n_dates = len(dates)
        n_train_dates = int(n_dates * train_ratio)
        n_val_dates = int(n_dates * val_ratio)
        
        train_dates = dates[:n_train_dates]
        val_dates = dates[n_train_dates:n_train_dates + n_val_dates]
        test_dates = dates[n_train_dates + n_val_dates:]
        
        # Create splits
        train_mask = (mbo_df['session'].isin(train_sessions)) & (mbo_df['date'].isin(train_dates))
        val_mask = (mbo_df['session'].isin(val_sessions)) & (mbo_df['date'].isin(val_dates))
        test_mask = (mbo_df['session'].isin(test_sessions)) & (mbo_df['date'].isin(test_dates))
        
        return {
            'train': mbo_df[train_mask].sort_values('ts_event'),
            'val': mbo_df[val_mask].sort_values('ts_event'),
            'test': mbo_df[test_mask].sort_values('ts_event')
        }
    
    def create_walk_forward_splits(self, mbo_df: pd.DataFrame,
                                  window_days: int = 30,
                                  step_days: int = 7) -> List[Dict[str, pd.DataFrame]]:
        """Create walk-forward splits for time series validation."""
        
        mbo_df = mbo_df.copy()
        mbo_df['datetime'] = pd.to_datetime(mbo_df['ts_event'], unit='ns')
        mbo_df['date'] = mbo_df['datetime'].dt.date
        
        dates = sorted(mbo_df['date'].unique())
        splits = []
        
        for i in range(0, len(dates) - window_days, step_days):
            if i + window_days >= len(dates):
                break
                
            # Training window
            train_start = dates[i]
            train_end = dates[i + window_days - step_days]
            
            # Validation window
            val_start = dates[i + window_days - step_days + 1]
            val_end = dates[i + window_days]
            
            # Test window (future)
            test_start = dates[i + window_days + 1]
            test_end = dates[min(i + window_days + step_days, len(dates) - 1)]
            
            train_mask = (mbo_df['date'] >= train_start) & (mbo_df['date'] <= train_end)
            val_mask = (mbo_df['date'] >= val_start) & (mbo_df['date'] <= val_end)
            test_mask = (mbo_df['date'] >= test_start) & (mbo_df['date'] <= test_end)
            
            splits.append({
                'train': mbo_df[train_mask].sort_values('ts_event'),
                'val': mbo_df[val_mask].sort_values('ts_event'),
                'test': mbo_df[test_mask].sort_values('ts_event'),
                'period': i // step_days,
                'train_dates': (train_start, train_end),
                'val_dates': (val_start, val_end),
                'test_dates': (test_start, test_end)
            })
        
        return splits


class LiveBacktestEngine:
    """Live-like backtesting engine with tick-by-tick processing."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        # Initialize MBO reader with default data directory (not used in backtesting)
        self.mbo_reader = DatabentoMBOReader("data/")
        self.feature_engineer = MBOFeatureEngineer(config.feature_config)
        self.session_splitter = SessionSplitter(config.session_split_seed)
        
        # State variables
        self.current_time: Optional[datetime] = None
        self.current_price: Optional[float] = None
        self.order_book: Dict = {'bids': {}, 'asks': {}}
        self.position = Position()
        self.capital = config.initial_capital
        self.orders: List[Order] = []
        self.trades: List[Trade] = []
        self.equity_history: List[Dict] = []
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.max_equity = config.initial_capital
        self.min_equity = config.initial_capital
        
        # Live mode tracking
        self.tick_count = 0
        self.last_tick_time = None
        self.tick_latency_stats = []
        
    def reset(self):
        """Reset the backtest engine state."""
        self.current_time = None
        self.current_price = None
        self.order_book = {'bids': {}, 'asks': {}}
        self.position = Position()
        self.capital = self.config.initial_capital
        self.orders.clear()
        self.trades.clear()
        self.equity_history.clear()
        self.daily_pnl = 0.0
        self.max_equity = self.config.initial_capital
        self.min_equity = self.config.initial_capital
        self.feature_engineer.reset_order_book()
        self.tick_count = 0
        self.last_tick_time = None
        self.tick_latency_stats.clear()
    
    def process_tick(self, mbo_event: pd.Series) -> Dict:
        """Process a single MBO event as if it were live."""
        start_time = datetime.now()
        
        # Update current time
        self.current_time = pd.to_datetime(mbo_event['ts_event'], unit='ns')
        
        # Track tick latency
        if self.last_tick_time:
            latency = (self.current_time - self.last_tick_time).total_seconds()
            self.tick_latency_stats.append(latency)
        
        self.last_tick_time = self.current_time
        self.tick_count += 1
        
        # Update order book
        self.update_order_book(mbo_event)
        
        # Check for order fills
        fills_processed = []
        for order in self.orders:
            if order.status == "pending":
                fill_info = self.simulate_fill(order, mbo_event)
                if fill_info:
                    self.process_fill(order, fill_info)
                    fills_processed.append(fill_info)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'tick_count': self.tick_count,
            'timestamp': self.current_time,
            'price': self.current_price,
            'position_size': self.position.size,
            'unrealized_pnl': self.position.unrealized_pnl,
            'total_pnl': self.position.total_pnl,
            'fills_processed': len(fills_processed),
            'processing_time_ms': processing_time * 1000,
            'order_book_depth': len(self.order_book['bids']) + len(self.order_book['asks'])
        }
    
    def update_order_book(self, mbo_event: pd.Series):
        """Update order book with MBO event."""
        self.feature_engineer.update_order_book(mbo_event)
        self.order_book = self.feature_engineer.order_book.copy()
        
        # Update current price (mid price)
        if self.order_book['bids'] and self.order_book['asks']:
            best_bid = max(self.order_book['bids'].keys())
            best_ask = min(self.order_book['asks'].keys())
            self.current_price = (best_bid + best_ask) / 2
    
    def calculate_slippage(self, order: Order, fill_price: float) -> float:
        """Calculate slippage for a trade."""
        if order.order_type == OrderType.MARKET:
            # Market order slippage
            if order.side == OrderSide.BUY:
                expected_price = min(self.order_book['asks'].keys()) if self.order_book['asks'] else self.current_price
            else:
                expected_price = max(self.order_book['bids'].keys()) if self.order_book['bids'] else self.current_price
            
            slippage = abs(fill_price - expected_price) if expected_price else 0
        else:
            # Limit order slippage (usually minimal)
            slippage = 0
        
        return slippage
    
    def calculate_market_impact(self, order: Order, fill_size: int) -> float:
        """Calculate market impact of a trade."""
        if self.config.market_impact_model == "none":
            return 0.0
        
        # Simple linear impact model
        impact = self.config.impact_coefficient * fill_size
        
        if self.config.market_impact_model == "square_root":
            impact = self.config.impact_coefficient * np.sqrt(fill_size)
        
        return impact
    
    def simulate_fill(self, order: Order, mbo_event: pd.Series) -> Optional[Dict]:
        """Simulate order fill based on MBO event."""
        if order.is_filled:
            return None
        
        # Check if this event could fill our order
        if mbo_event['action'] != 'execute':
            return None
        
        # Market orders always get filled
        if order.order_type == OrderType.MARKET:
            fill_size = min(order.remaining_size, mbo_event['size'])
            fill_price = mbo_event['price']
            
            # Apply slippage
            slippage = self.calculate_slippage(order, fill_price)
            fill_price += slippage if order.side == OrderSide.BUY else -slippage
            
            return {
                'size': fill_size,
                'price': fill_price,
                'slippage': slippage,
                'market_impact': self.calculate_market_impact(order, fill_size)
            }
        
        # Limit orders
        elif order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and mbo_event['side'] == 'sell':
                # Buy limit order can be filled by sell executions
                if mbo_event['price'] <= order.price:
                    if np.random.random() <= self.config.fill_probability:
                        fill_size = min(order.remaining_size, mbo_event['size'])
                        fill_price = min(order.price, mbo_event['price'])
                        
                        return {
                            'size': fill_size,
                            'price': fill_price,
                            'slippage': 0.0,
                            'market_impact': self.calculate_market_impact(order, fill_size)
                        }
            
            elif order.side == OrderSide.SELL and mbo_event['side'] == 'buy':
                # Sell limit order can be filled by buy executions
                if mbo_event['price'] >= order.price:
                    if np.random.random() <= self.config.fill_probability:
                        fill_size = min(order.remaining_size, mbo_event['size'])
                        fill_price = max(order.price, mbo_event['price'])
                        
                        return {
                            'size': fill_size,
                            'price': fill_price,
                            'slippage': 0.0,
                            'market_impact': self.calculate_market_impact(order, fill_size)
                        }
        
        return None
    
    def process_fill(self, order: Order, fill_info: Dict):
        """Process an order fill."""
        fill_size = fill_info['size']
        fill_price = fill_info['price']
        slippage = fill_info['slippage']
        market_impact = fill_info['market_impact']
        
        # Update order
        order.filled_size += fill_size
        order.filled_price = (order.filled_price * (order.filled_size - fill_size) + fill_price * fill_size) / order.filled_size
        
        # Record fill
        order.fills.append({
            'timestamp': self.current_time,
            'size': fill_size,
            'price': fill_price,
            'slippage': slippage,
            'market_impact': market_impact
        })
        
        # Create trade
        trade = Trade(
            id=f"trade_{len(self.trades)}",
            timestamp=self.current_time,
            side=order.side,
            size=fill_size,
            price=fill_price,
            order_id=order.id,
            slippage=slippage,
            market_impact=market_impact
        )
        
        self.trades.append(trade)
        
        # Update position
        self.position.update(trade)
        
        # Calculate costs
        commission = self.config.commission_per_contract * fill_size
        total_cost = fill_price * fill_size + commission
        
        if order.side == OrderSide.BUY:
            self.capital -= total_cost
        else:
            self.capital += total_cost - commission
        
        # Update order status
        if order.is_filled:
            order.status = "filled"
        
        # Update unrealized P&L
        if self.current_price and self.position.size != 0:
            if self.position.size > 0:
                self.position.unrealized_pnl = (self.current_price - self.position.avg_price) * self.position.size
            else:
                self.position.unrealized_pnl = (self.position.avg_price - self.current_price) * abs(self.position.size)
        
        self.position.total_pnl = self.position.realized_pnl + self.position.unrealized_pnl
    
    def place_order(self, side: OrderSide, order_type: OrderType, size: int, 
                   price: Optional[float] = None, stop_price: Optional[float] = None) -> str:
        """Place a new order."""
        order_id = f"order_{len(self.orders)}"
        
        order = Order(
            id=order_id,
            timestamp=self.current_time,
            side=side,
            order_type=order_type,
            size=size,
            price=price,
            stop_price=stop_price
        )
        
        self.orders.append(order)
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""
        for order in self.orders:
            if order.id == order_id and order.status == "pending":
                order.status = "cancelled"
                return True
        return False
    
    def update_equity(self):
        """Update equity curve."""
        total_equity = self.capital + self.position.total_pnl
        self.max_equity = max(self.max_equity, total_equity)
        self.min_equity = min(self.min_equity, total_equity)
        
        self.equity_history.append({
            'timestamp': self.current_time,
            'equity': total_equity,
            'capital': self.capital,
            'position_size': self.position.size,
            'position_value': self.position.size * self.current_price if self.current_price else 0,
            'unrealized_pnl': self.position.unrealized_pnl,
            'realized_pnl': self.position.realized_pnl,
            'total_pnl': self.position.total_pnl,
            'tick_count': self.tick_count
        })
    
    def check_risk_limits(self) -> bool:
        """Check if risk limits are exceeded."""
        # Position size limit
        if abs(self.position.size) > self.config.max_position_size:
            logger.warning(f"Position size limit exceeded: {self.position.size}")
            return False
        
        # Daily loss limit
        if self.daily_pnl < -self.config.max_daily_loss:
            logger.warning(f"Daily loss limit exceeded: {self.daily_pnl}")
            return False
        
        return True
    
    def run_live_backtest(self, mbo_data: pd.DataFrame, strategy_func: Callable, 
                         timeframe_filter: Optional[Any] = None) -> BacktestResult:
        """Run a live-like backtest with tick-by-tick processing."""
        self.reset()
        
        # Apply timeframe filtering if provided
        if timeframe_filter is not None:
            logger.info(f"Applying timeframe filter for backtest: {timeframe_filter.tag}")
            from quanttime.utils.timeframe_filter import filter_mbo_data_by_timeframe
            mbo_data = filter_mbo_data_by_timeframe(mbo_data, timeframe_filter, timestamp_col='ts_event')
            logger.info(f"Filtered backtest data: {len(mbo_data)} events remaining")
        
        # Sort data by timestamp
        mbo_data = mbo_data.sort_values('ts_event').copy()
        mbo_data['datetime'] = pd.to_datetime(mbo_data['ts_event'], unit='ns')
        
        logger.info(f"Starting live backtest with {len(mbo_data)} MBO events")
        
        tick_results = []
        
        for _, mbo_event in mbo_data.iterrows():
            # Process tick
            tick_result = self.process_tick(mbo_event)
            tick_results.append(tick_result)
            
            # Call strategy function
            try:
                strategy_func(self, mbo_event)
            except Exception as e:
                logger.error(f"Strategy error at {self.current_time}: {e}")
                continue
            
            # Check risk limits
            if not self.check_risk_limits():
                logger.warning("Risk limits exceeded, stopping backtest")
                break
            
            # Update equity curve
            self.update_equity()
        
        # Calculate results
        return self.calculate_results(tick_results)
    
    def run_walk_forward_backtest(self, mbo_data: pd.DataFrame, strategy_func: Callable) -> List[BacktestResult]:
        """Run walk-forward backtest with multiple periods."""
        splits = self.session_splitter.create_walk_forward_splits(
            mbo_data, 
            self.config.walk_forward_window_days,
            self.config.walk_forward_step_days
        )
        
        results = []
        
        for split in splits:
            logger.info(f"Running walk-forward period {split['period']}")
            logger.info(f"Train: {split['train_dates']}, Val: {split['val_dates']}, Test: {split['test_dates']}")
            
            # Run backtest on test data
            result = self.run_live_backtest(split['test'], strategy_func)
            result.walk_forward_period = split['period']
            results.append(result)
        
        return results
    
    def calculate_results(self, tick_results: List[Dict] = None) -> BacktestResult:
        """Calculate comprehensive backtest results."""
        if not self.equity_history:
            return BacktestResult(
                total_return=0.0, sharpe_ratio=0.0, max_drawdown=0.0,
                win_rate=0.0, profit_factor=0.0, total_trades=0,
                winning_trades=0, losing_trades=0, avg_trade_pnl=0.0,
                avg_win=0.0, avg_loss=0.0, volatility=0.0, var_95=0.0,
                cvar_95=0.0, trades=[], positions=[], equity_curve=pd.DataFrame(),
                daily_returns=pd.Series(), total_volume_traded=0,
                avg_slippage=0.0, avg_market_impact=0.0, fill_rate=0.0,
                walk_forward_periods=0, avg_period_return=0.0, period_consistency=0.0
            )
        
        # Create equity curve DataFrame
        equity_df = pd.DataFrame(self.equity_history)
        equity_df.set_index('timestamp', inplace=True)
        
        # Calculate returns
        equity_df['returns'] = equity_df['equity'].pct_change().fillna(0)
        daily_returns = equity_df['returns'].resample('D').sum()
        
        # Performance metrics
        initial_equity = self.config.initial_capital
        final_equity = equity_df['equity'].iloc[-1]
        total_return = (final_equity - initial_equity) / initial_equity
        
        # Sharpe ratio
        if daily_returns.std() > 0:
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Maximum drawdown
        rolling_max = equity_df['equity'].expanding().max()
        drawdown = (equity_df['equity'] - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min())
        
        # Trade statistics
        if self.trades:
            trade_pnls = []
            for i in range(0, len(self.trades), 2):
                if i + 1 < len(self.trades):
                    entry = self.trades[i]
                    exit = self.trades[i + 1]
                    if entry.side != exit.side:
                        if entry.side == OrderSide.BUY:
                            pnl = (exit.price - entry.price) * entry.size
                        else:
                            pnl = (entry.price - exit.price) * entry.size
                        trade_pnls.append(pnl)
            
            if trade_pnls:
                winning_trades = sum(1 for pnl in trade_pnls if pnl > 0)
                losing_trades = sum(1 for pnl in trade_pnls if pnl < 0)
                win_rate = winning_trades / len(trade_pnls) if trade_pnls else 0
                
                avg_trade_pnl = np.mean(trade_pnls)
                avg_win = np.mean([pnl for pnl in trade_pnls if pnl > 0]) if winning_trades > 0 else 0
                avg_loss = np.mean([pnl for pnl in trade_pnls if pnl < 0]) if losing_trades > 0 else 0
                
                profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 else float('inf')
            else:
                winning_trades = losing_trades = win_rate = avg_trade_pnl = avg_win = avg_loss = profit_factor = 0
        else:
            winning_trades = losing_trades = win_rate = avg_trade_pnl = avg_win = avg_loss = profit_factor = 0
        
        # Risk metrics
        volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0
        var_95 = np.percentile(daily_returns, 5) if len(daily_returns) > 0 else 0
        cvar_95 = daily_returns[daily_returns <= var_95].mean() if len(daily_returns) > 0 else 0
        
        # MBO-specific metrics
        total_volume_traded = sum(trade.size for trade in self.trades)
        avg_slippage = np.mean([trade.slippage for trade in self.trades]) if self.trades else 0
        avg_market_impact = np.mean([trade.market_impact for trade in self.trades]) if self.trades else 0
        
        filled_orders = sum(1 for order in self.orders if order.status == "filled")
        total_orders = len(self.orders)
        fill_rate = filled_orders / total_orders if total_orders > 0 else 0
        
        # Live performance metrics
        avg_tick_latency = np.mean(self.tick_latency_stats) if self.tick_latency_stats else 0
        max_tick_latency = np.max(self.tick_latency_stats) if self.tick_latency_stats else 0
        
        return BacktestResult(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(self.trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_trade_pnl=avg_trade_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            volatility=volatility,
            var_95=var_95,
            cvar_95=cvar_95,
            trades=self.trades.copy(),
            positions=[self.position],
            equity_curve=equity_df,
            daily_returns=daily_returns,
            total_volume_traded=total_volume_traded,
            avg_slippage=avg_slippage,
            avg_market_impact=avg_market_impact,
            fill_rate=fill_rate,
            walk_forward_periods=1,
            avg_period_return=total_return,
            period_consistency=0.0
        )


def run_mbo_backtest(mbo_data: pd.DataFrame, strategy_func: Callable, 
                    config: BacktestConfig = None, timeframe_filter: Optional[Any] = None) -> BacktestResult:
    """Convenience function to run MBO backtest."""
    config = config or BacktestConfig()
    engine = LiveBacktestEngine(config)
    return engine.run_live_backtest(mbo_data, strategy_func, timeframe_filter)


def run_walk_forward_backtest(mbo_data: pd.DataFrame, strategy_func: Callable,
                            config: BacktestConfig = None) -> List[BacktestResult]:
    """Convenience function to run walk-forward backtest."""
    config = config or BacktestConfig()
    engine = LiveBacktestEngine(config)
    return engine.run_walk_forward_backtest(mbo_data, strategy_func)


def create_session_splits(mbo_data: pd.DataFrame, seed: int = 42) -> Dict[str, pd.DataFrame]:
    """Create session-based data splits."""
    splitter = SessionSplitter(seed)
    return splitter.split_data_by_sessions(mbo_data)
