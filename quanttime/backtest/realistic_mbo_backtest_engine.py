"""
Realistic Tick-by-Tick MBO Backtest Engine
Simulates actual futures trading with order book dynamics, slippage, and contract-based P&L
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderBookLevel:
    """Represents a single level in the order book"""
    price: float
    size: int
    side: OrderSide
    timestamp: datetime


@dataclass
class OrderBook:
    """Realistic order book with bid/ask levels"""
    timestamp: datetime
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    
    def get_best_bid(self) -> Optional[OrderBookLevel]:
        """Get best bid (highest price)"""
        return max(self.bids, key=lambda x: x.price) if self.bids else None
    
    def get_best_ask(self) -> Optional[OrderBookLevel]:
        """Get best ask (lowest price)"""
        return min(self.asks, key=lambda x: x.price) if self.asks else None
    
    def get_mid_price(self) -> float:
        """Calculate mid price"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2
        elif best_bid:
            return best_bid.price
        elif best_ask:
            return best_ask.price
        else:
            return 0.0
    
    def get_spread(self) -> float:
        """Calculate bid-ask spread"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return 0.0
    
    def get_depth(self, side: OrderSide, levels: int = 5) -> List[OrderBookLevel]:
        """Get order book depth for specified side"""
        if side == OrderSide.BUY:
            return sorted(self.bids, key=lambda x: x.price, reverse=True)[:levels]
        else:
            return sorted(self.asks, key=lambda x: x.price)[:levels]


@dataclass
class Trade:
    """Represents a filled trade"""
    timestamp: datetime
    side: OrderSide
    price: float
    size: int
    order_id: str
    fill_id: str
    slippage: float = 0.0
    commission: float = 0.0


@dataclass
class Order:
    """Represents a trading order"""
    order_id: str
    timestamp: datetime
    side: OrderSide
    order_type: OrderType
    size: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_size: int = 0
    avg_fill_price: float = 0.0
    trades: List[Trade] = field(default_factory=list)


@dataclass
class Position:
    """Represents current position"""
    size: int = 0  # Positive = long, Negative = short
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    
    def update_unrealized_pnl(self, current_price: float, tick_value: float):
        """Update unrealized P&L based on current price"""
        if self.size != 0:
            price_diff = (current_price - self.avg_price) * np.sign(self.size)
            self.unrealized_pnl = price_diff * abs(self.size) * tick_value
            self.total_pnl = self.realized_pnl + self.unrealized_pnl


@dataclass
class BacktestConfig:
    """Configuration for realistic backtest"""
    initial_capital: float = 100000.0
    commission_per_contract: float = 2.50  # Per side
    tick_size: float = 0.25  # ES tick size
    tick_value: float = 12.50  # ES tick value
    max_position_size: int = 10  # Max contracts
    slippage_model: str = "realistic"  # "realistic", "fixed", "none"
    fixed_slippage_ticks: float = 0.5
    use_order_book: bool = True
    min_trade_velocity: float = 2.0  # Minimum prediction velocity for trade
    rl_model_path: Optional[str] = None
    prediction_threshold: float = 1.0  # Minimum prediction magnitude for trade


class RealisticMBOBacktestEngine:
    """Realistic tick-by-tick MBO backtest engine"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.reset()
    
    def reset(self):
        """Reset backtest state"""
        self.capital = self.config.initial_capital
        self.position = Position()
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.order_book_history: List[OrderBook] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.current_timestamp: Optional[datetime] = None
        self.order_id_counter = 0
        self.trade_id_counter = 0
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0.0
        self.peak_capital = self.config.initial_capital
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self.order_id_counter += 1
        return f"ORDER_{self.order_id_counter:06d}"
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        self.trade_id_counter += 1
        return f"TRADE_{self.trade_id_counter:06d}"
    
    def _calculate_slippage(self, order: Order, order_book: OrderBook) -> float:
        """Calculate realistic slippage based on order book"""
        if self.config.slippage_model == "none":
            return 0.0
        elif self.config.slippage_model == "fixed":
            return self.config.fixed_slippage_ticks * self.config.tick_size
        
        # Realistic slippage based on order book depth
        if order.side == OrderSide.BUY:
            # For buy orders, slippage increases with ask depth
            depth = order_book.get_depth(OrderSide.SELL, 10)
            if not depth:
                return self.config.tick_size
            
            # Calculate how much volume we need to consume
            remaining_size = order.size - order.filled_size
            consumed_volume = 0
            slippage_ticks = 0
            
            for level in depth:
                if consumed_volume >= remaining_size:
                    break
                volume_at_level = min(level.size, remaining_size - consumed_volume)
                consumed_volume += volume_at_level
                slippage_ticks += (level.price - order_book.get_best_ask().price) / self.config.tick_size
            
            return slippage_ticks * self.config.tick_size
        
        else:  # SELL
            # For sell orders, slippage increases with bid depth
            depth = order_book.get_depth(OrderSide.BUY, 10)
            if not depth:
                return self.config.tick_size
            
            remaining_size = order.size - order.filled_size
            consumed_volume = 0
            slippage_ticks = 0
            
            for level in depth:
                if consumed_volume >= remaining_size:
                    break
                volume_at_level = min(level.size, remaining_size - consumed_volume)
                consumed_volume += volume_at_level
                slippage_ticks += (order_book.get_best_bid().price - level.price) / self.config.tick_size
            
            return slippage_ticks * self.config.tick_size
    
    def _fill_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Fill an order based on current order book"""
        trades = []
        remaining_size = order.size - order.filled_size
        
        if order.order_type == OrderType.MARKET:
            # Market orders get filled immediately
            if order.side == OrderSide.BUY:
                best_ask = order_book.get_best_ask()
                if best_ask:
                    fill_price = best_ask.price
                    slippage = self._calculate_slippage(order, order_book)
                    fill_price += slippage
                    
                    trade = Trade(
                        timestamp=self.current_timestamp,
                        side=order.side,
                        price=fill_price,
                        size=remaining_size,
                        order_id=order.order_id,
                        fill_id=self._generate_trade_id(),
                        slippage=slippage,
                        commission=self.config.commission_per_contract * remaining_size
                    )
                    trades.append(trade)
                    
                    order.filled_size = order.size
                    order.status = OrderStatus.FILLED
                    order.avg_fill_price = fill_price
                    order.trades.append(trade)
            
            elif order.side == OrderSide.SELL:
                best_bid = order_book.get_best_bid()
                if best_bid:
                    fill_price = best_bid.price
                    slippage = self._calculate_slippage(order, order_book)
                    fill_price -= slippage
                    
                    trade = Trade(
                        timestamp=self.current_timestamp,
                        side=order.side,
                        price=fill_price,
                        size=remaining_size,
                        order_id=order.order_id,
                        fill_id=self._generate_trade_id(),
                        slippage=slippage,
                        commission=self.config.commission_per_contract * remaining_size
                    )
                    trades.append(trade)
                    
                    order.filled_size = order.size
                    order.status = OrderStatus.FILLED
                    order.avg_fill_price = fill_price
                    order.trades.append(trade)
        
        elif order.order_type == OrderType.LIMIT:
            # Limit orders only fill if price is favorable
            if order.side == OrderSide.BUY and order.price:
                best_ask = order_book.get_best_ask()
                if best_ask and best_ask.price <= order.price:
                    # Can fill at limit price or better
                    fill_price = min(order.price, best_ask.price)
                    
                    trade = Trade(
                        timestamp=self.current_timestamp,
                        side=order.side,
                        price=fill_price,
                        size=remaining_size,
                        order_id=order.order_id,
                        fill_id=self._generate_trade_id(),
                        slippage=0.0,
                        commission=self.config.commission_per_contract * remaining_size
                    )
                    trades.append(trade)
                    
                    order.filled_size = order.size
                    order.status = OrderStatus.FILLED
                    order.avg_fill_price = fill_price
                    order.trades.append(trade)
            
            elif order.side == OrderSide.SELL and order.price:
                best_bid = order_book.get_best_bid()
                if best_bid and best_bid.price >= order.price:
                    # Can fill at limit price or better
                    fill_price = max(order.price, best_bid.price)
                    
                    trade = Trade(
                        timestamp=self.current_timestamp,
                        side=order.side,
                        price=fill_price,
                        size=remaining_size,
                        order_id=order.order_id,
                        fill_id=self._generate_trade_id(),
                        slippage=0.0,
                        commission=self.config.commission_per_contract * remaining_size
                    )
                    trades.append(trade)
                    
                    order.filled_size = order.size
                    order.status = OrderStatus.FILLED
                    order.avg_fill_price = fill_price
                    order.trades.append(trade)
        
        return trades
    
    def _update_position(self, trade: Trade):
        """Update position based on trade"""
        old_size = self.position.size
        old_avg_price = self.position.avg_price
        
        # Calculate realized P&L if closing position
        if (old_size > 0 and trade.side == OrderSide.SELL) or (old_size < 0 and trade.side == OrderSide.BUY):
            # Closing position
            if old_size > 0:  # Closing long position
                pnl = (trade.price - old_avg_price) * min(abs(old_size), trade.size) * self.config.tick_value
            else:  # Closing short position
                pnl = (old_avg_price - trade.price) * min(abs(old_size), trade.size) * self.config.tick_value
            
            self.position.realized_pnl += pnl
            self.capital += pnl - trade.commission
        
        # Update position
        if trade.side == OrderSide.BUY:
            new_size = old_size + trade.size
        else:
            new_size = old_size - trade.size
        
        # Update average price
        if new_size != 0:
            if old_size == 0:
                new_avg_price = trade.price
            else:
                # Weighted average
                total_value = old_size * old_avg_price + trade.size * trade.price
                new_avg_price = total_value / new_size
        else:
            new_avg_price = 0.0
        
        self.position.size = new_size
        self.position.avg_price = new_avg_price
        
        # Update trade statistics
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
    
    def place_order(self, side: OrderSide, order_type: OrderType, size: int, 
                   price: Optional[float] = None, stop_price: Optional[float] = None) -> str:
        """Place a trading order"""
        order_id = self._generate_order_id()
        
        order = Order(
            order_id=order_id,
            timestamp=self.current_timestamp,
            side=side,
            order_type=order_type,
            size=size,
            price=price,
            stop_price=stop_price
        )
        
        self.orders[order_id] = order
        return order_id
    
    def process_tick(self, timestamp: datetime, order_book: OrderBook, 
                    predictions: Optional[Dict[str, float]] = None,
                    rl_action: Optional[np.ndarray] = None) -> List[Trade]:
        """Process a single tick with order book update"""
        self.current_timestamp = timestamp
        self.order_book_history.append(order_book)
        
        # Update position unrealized P&L
        mid_price = order_book.get_mid_price()
        self.position.update_unrealized_pnl(mid_price, self.config.tick_value)
        
        # Process pending orders
        all_trades = []
        for order in list(self.orders.values()):
            if order.status == OrderStatus.PENDING:
                trades = self._fill_order(order, order_book)
                all_trades.extend(trades)
                
                for trade in trades:
                    self._update_position(trade)
                    self.trades.append(trade)
        
        # Update equity curve
        total_value = self.capital + self.position.total_pnl
        self.peak_capital = max(self.peak_capital, total_value)
        current_drawdown = (self.peak_capital - total_value) / self.peak_capital
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'capital': self.capital,
            'position_size': self.position.size,
            'position_value': self.position.total_pnl,
            'total_value': total_value,
            'drawdown': current_drawdown,
            'mid_price': mid_price
        })
        
        return all_trades
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        if not self.equity_curve:
            return {}
        
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['returns'] = equity_df['total_value'].pct_change()
        
        # Basic metrics
        total_return = (equity_df['total_value'].iloc[-1] - self.config.initial_capital) / self.config.initial_capital
        annualized_return = total_return * (252 / len(equity_df)) if len(equity_df) > 1 else 0
        
        # Risk metrics
        volatility = equity_df['returns'].std() * np.sqrt(252) if len(equity_df) > 1 else 0
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # Trade metrics
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        
        # Calculate average trade P&L
        if self.trades:
            trade_pnls = []
            for i in range(0, len(self.trades), 2):  # Round trips
                if i + 1 < len(self.trades):
                    entry_trade = self.trades[i]
                    exit_trade = self.trades[i + 1]
                    
                    if entry_trade.side != exit_trade.side:
                        if entry_trade.side == OrderSide.BUY:
                            pnl = (exit_trade.price - entry_trade.price) * entry_trade.size * self.config.tick_value
                        else:
                            pnl = (entry_trade.price - exit_trade.price) * entry_trade.size * self.config.tick_value
                        
                        pnl -= (entry_trade.commission + exit_trade.commission)
                        trade_pnls.append(pnl)
            
            avg_trade_pnl = np.mean(trade_pnls) if trade_pnls else 0
            max_trade_pnl = np.max(trade_pnls) if trade_pnls else 0
            min_trade_pnl = np.min(trade_pnls) if trade_pnls else 0
        else:
            avg_trade_pnl = max_trade_pnl = min_trade_pnl = 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_trade_pnl': avg_trade_pnl,
            'max_trade_pnl': max_trade_pnl,
            'min_trade_pnl': min_trade_pnl,
            'final_capital': equity_df['total_value'].iloc[-1],
            'peak_capital': self.peak_capital,
            'total_commission': sum(trade.commission for trade in self.trades)
        }
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame"""
        return pd.DataFrame(self.equity_curve)
    
    def get_trade_history(self) -> pd.DataFrame:
        """Get trade history as DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        
        trade_data = []
        for trade in self.trades:
            trade_data.append({
                'timestamp': trade.timestamp,
                'side': trade.side.value,
                'price': trade.price,
                'size': trade.size,
                'slippage': trade.slippage,
                'commission': trade.commission,
                'order_id': trade.order_id,
                'fill_id': trade.fill_id
            })
        
        return pd.DataFrame(trade_data)


class PredictionBasedTrader:
    """Trading logic based on model predictions"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.last_predictions = {}
        self.prediction_velocity = {}
    
    def calculate_prediction_velocity(self, current_predictions: Dict[str, float]) -> Dict[str, float]:
        """Calculate prediction velocity (change in predictions)"""
        velocity = {}
        
        for model_name, prediction in current_predictions.items():
            if model_name in self.last_predictions:
                velocity[model_name] = prediction - self.last_predictions[model_name]
            else:
                velocity[model_name] = 0.0
            
            self.last_predictions[model_name] = prediction
        
        return velocity
    
    def should_trade(self, predictions: Dict[str, float], velocity: Dict[str, float], 
                    order_book: OrderBook) -> Tuple[bool, OrderSide, int]:
        """Determine if we should trade based on predictions and velocity"""
        if not predictions:
            return False, OrderSide.BUY, 0
        
        # Calculate aggregate prediction
        avg_prediction = np.mean(list(predictions.values()))
        avg_velocity = np.mean(list(velocity.values()))
        
        # Check minimum prediction threshold
        if abs(avg_prediction) < self.config.prediction_threshold:
            return False, OrderSide.BUY, 0
        
        # Check minimum velocity threshold
        if abs(avg_velocity) < self.config.min_trade_velocity:
            return False, OrderSide.BUY, 0
        
        # Determine trade direction
        if avg_prediction > 0 and avg_velocity > 0:
            return True, OrderSide.BUY, 1
        elif avg_prediction < 0 and avg_velocity < 0:
            return True, OrderSide.SELL, 1
        
        return False, OrderSide.BUY, 0


class RLTrader:
    """Reinforcement Learning based trader"""
    
    def __init__(self, config: BacktestConfig, rl_model=None):
        self.config = config
        self.rl_model = rl_model
        self.observation_history = []
        self.action_history = []
    
    def create_observation(self, order_book: OrderBook, predictions: Dict[str, float], 
                          velocity: Dict[str, float], position: Position) -> np.ndarray:
        """Create observation vector for RL model"""
        # Price features
        mid_price = order_book.get_mid_price()
        spread = order_book.get_spread()
        
        # Order book features (top 5 levels)
        bid_prices = [level.price for level in order_book.get_depth(OrderSide.BUY, 5)]
        ask_prices = [level.price for level in order_book.get_depth(OrderSide.SELL, 5)]
        bid_sizes = [level.size for level in order_book.get_depth(OrderSide.BUY, 5)]
        ask_sizes = [level.size for level in order_book.get_depth(OrderSide.SELL, 5)]
        
        # Pad with zeros if not enough levels
        while len(bid_prices) < 5:
            bid_prices.append(0.0)
            ask_prices.append(0.0)
            bid_sizes.append(0)
            ask_sizes.append(0)
        
        # Prediction features
        pred_values = list(predictions.values()) if predictions else [0.0] * 3
        vel_values = list(velocity.values()) if velocity else [0.0] * 3
        
        # Pad predictions and velocity
        while len(pred_values) < 3:
            pred_values.append(0.0)
        while len(vel_values) < 3:
            vel_values.append(0.0)
        
        # Position features
        position_size = position.size
        position_pnl = position.total_pnl
        
        # Combine all features
        observation = np.array([
            mid_price, spread,
            *bid_prices, *ask_prices, *bid_sizes, *ask_sizes,
            *pred_values, *vel_values,
            position_size, position_pnl
        ], dtype=np.float32)
        
        return observation
    
    def get_action(self, observation: np.ndarray) -> Tuple[OrderSide, int]:
        """Get trading action from RL model"""
        if self.rl_model is None:
            return OrderSide.BUY, 0
        
        try:
            action = self.rl_model.predict(observation)[0]
            
            # Interpret action: [position_size, action_type]
            position_size = action[0]  # -1 to 1
            action_type = int(action[1])  # 0=hold, 1=buy, 2=sell
            
            if action_type == 1:  # Buy
                return OrderSide.BUY, 1
            elif action_type == 2:  # Sell
                return OrderSide.SELL, 1
            else:  # Hold
                return OrderSide.BUY, 0
                
        except Exception as e:
            logger.error(f"RL model prediction failed: {e}")
            return OrderSide.BUY, 0


def run_realistic_backtest(mbo_data: pd.DataFrame, predictions: Dict[str, np.ndarray],
                          config: BacktestConfig, trader_type: str = "prediction",
                          rl_model=None) -> Dict[str, Any]:
    """Run realistic tick-by-tick backtest"""
    
    # Initialize backtest engine
    engine = RealisticMBOBacktestEngine(config)
    
    # Initialize traders
    prediction_trader = PredictionBasedTrader(config)
    rl_trader = RLTrader(config, rl_model)
    
    # Process each tick
    for i, (timestamp, row) in enumerate(mbo_data.iterrows()):
        # Create order book from MBO data
        order_book = create_order_book_from_mbo(row, timestamp)
        
        # Get current predictions
        current_predictions = {}
        current_velocity = {}
        
        if predictions:
            for model_name, pred_series in predictions.items():
                if i < len(pred_series):
                    current_predictions[model_name] = pred_series[i]
            
            current_velocity = prediction_trader.calculate_prediction_velocity(current_predictions)
        
        # Get trading decision
        should_trade = False
        trade_side = OrderSide.BUY
        trade_size = 0
        
        if trader_type == "prediction":
            should_trade, trade_side, trade_size = prediction_trader.should_trade(
                current_predictions, current_velocity, order_book
            )
        elif trader_type == "rl":
            observation = rl_trader.create_observation(
                order_book, current_predictions, current_velocity, engine.position
            )
            trade_side, trade_size = rl_trader.get_action(observation)
            should_trade = trade_size > 0
        
        # Place order if needed
        if should_trade and trade_size > 0:
            engine.place_order(trade_side, OrderType.MARKET, trade_size)
        
        # Process tick
        engine.process_tick(timestamp, order_book, current_predictions)
    
    # Calculate performance metrics
    metrics = engine.get_performance_metrics()
    metrics['trader_type'] = trader_type
    metrics['config'] = config.__dict__
    
    return {
        'metrics': metrics,
        'equity_curve': engine.get_equity_curve(),
        'trade_history': engine.get_trade_history(),
        'engine': engine
    }


def create_order_book_from_mbo(mbo_row: pd.Series, timestamp: datetime) -> OrderBook:
    """Create order book from MBO data row"""
    order_book = OrderBook(timestamp=timestamp)
    
    # Extract bid/ask levels from MBO data
    # This assumes MBO data has columns like bid_price_1, bid_size_1, ask_price_1, ask_size_1, etc.
    
    for i in range(1, 6):  # Top 5 levels
        bid_price_col = f'bid_price_{i}'
        bid_size_col = f'bid_size_{i}'
        ask_price_col = f'ask_price_{i}'
        ask_size_col = f'ask_size_{i}'
        
        if bid_price_col in mbo_row and not pd.isna(mbo_row[bid_price_col]):
            order_book.bids.append(OrderBookLevel(
                price=mbo_row[bid_price_col],
                size=int(mbo_row[bid_size_col]) if bid_size_col in mbo_row else 1,
                side=OrderSide.BUY,
                timestamp=timestamp
            ))
        
        if ask_price_col in mbo_row and not pd.isna(mbo_row[ask_price_col]):
            order_book.asks.append(OrderBookLevel(
                price=mbo_row[ask_price_col],
                size=int(mbo_row[ask_size_col]) if ask_size_col in mbo_row else 1,
                side=OrderSide.SELL,
                timestamp=timestamp
            ))
    
    return order_book


def create_sample_mbo_data(n_ticks: int = 10000) -> pd.DataFrame:
    """Create sample MBO data for testing"""
    np.random.seed(42)
    
    # Generate base price movement
    base_price = 4850.0
    price_changes = np.cumsum(np.random.randn(n_ticks) * 0.1)
    mid_prices = base_price + price_changes
    
    # Generate order book data
    data = []
    for i in range(n_ticks):
        mid_price = mid_prices[i]
        spread = np.random.uniform(0.25, 1.0)
        
        # Generate bid/ask levels
        row = {'timestamp': pd.Timestamp.now() + pd.Timedelta(seconds=i)}
        
        for level in range(1, 6):
            # Bids (below mid price)
            bid_offset = level * 0.25 + np.random.uniform(0, 0.25)
            row[f'bid_price_{level}'] = mid_price - bid_offset
            row[f'bid_size_{level}'] = np.random.randint(1, 100)
            
            # Asks (above mid price)
            ask_offset = level * 0.25 + np.random.uniform(0, 0.25)
            row[f'ask_price_{level}'] = mid_price + ask_offset
            row[f'ask_size_{level}'] = np.random.randint(1, 100)
        
        data.append(row)
    
    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    config = BacktestConfig(
        initial_capital=100000.0,
        commission_per_contract=2.50,
        tick_size=0.25,
        tick_value=12.50,
        max_position_size=10,
        slippage_model="realistic",
        use_order_book=True,
        min_trade_velocity=2.0,
        prediction_threshold=1.0
    )
    
    # Create sample data
    mbo_data = create_sample_mbo_data(1000)
    
    # Create sample predictions
    predictions = {
        'model_1': np.random.randn(1000) * 5,
        'model_2': np.random.randn(1000) * 3,
        'model_3': np.random.randn(1000) * 4
    }
    
    # Run backtest
    results = run_realistic_backtest(mbo_data, predictions, config, trader_type="prediction")
    
    print("Backtest Results:")
    print(json.dumps(results['metrics'], indent=2))
