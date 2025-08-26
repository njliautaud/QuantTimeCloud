import time
from dataclasses import dataclass
from typing import Optional

from quanttime.utils.logging import get_logger


@dataclass
class RiskLimits:
    max_position: int
    max_daily_loss: float


class LiveExecutor:
    def __init__(self, risk: RiskLimits):
        self.risk = risk
        self.position = 0
        self.realized_pnl = 0.0
        self.logger = get_logger(self.__class__.__name__)

    def can_open(self, qty: int) -> bool:
        return abs(self.position + qty) <= self.risk.max_position and self.realized_pnl > -self.risk.max_daily_loss

    def market_order(self, side: str, qty: int, price: Optional[float] = None) -> bool:
        delta = qty if side == "buy" else -qty
        if not self.can_open(delta):
            self.logger.warning("Risk limits prevent opening position")
            return False
        self.position += delta
        self.logger.info(f"Executed market order side={side} qty={qty} at price={price}")
        return True


@dataclass
class AdaptiveExecutionPolicy:
    """Adaptive aggressiveness based on liquidity and predicted edge.

    - Increase size when predicted probability and depth imbalance favor the side
    - Reduce or skip in chop/low-liquidity or spoofing suspected
    """
    base_qty: int = 1
    max_qty: int = 4
    prob_threshold: float = 0.55
    high_prob_threshold: float = 0.65
    low_liquidity_threshold: float = 0.1

    def decide_qty(self, prob: float, liquidity_score: float, spoofing_flag: bool) -> int:
        if spoofing_flag:
            return 0
        if prob < self.prob_threshold:
            return 0
        if liquidity_score < self.low_liquidity_threshold:
            return self.base_qty  # avoid sizing up in thin conditions
        if prob > self.high_prob_threshold:
            return min(self.max_qty, max(self.base_qty + 1, 2))
        return self.base_qty


