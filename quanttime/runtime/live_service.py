"""
Simplified live service for QuantTime.
"""

from dataclasses import dataclass
from typing import Optional
from quanttime.utils.config import AppConfig


@dataclass
class LiveState:
    is_running: bool = False
    last_price: Optional[float] = None
    last_prediction: Optional[float] = None
    position: int = 0
    realized_pnl: float = 0.0


class LiveService:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.state = LiveState()

    def start(self, run_id: int = 0, threshold: float = 0.0) -> None:
        """Start live trading service."""
        self.state.is_running = True
        self.state.last_price = 5000.0  # Default price
        self.state.last_prediction = 0.5  # Default prediction

    def stop(self) -> None:
        """Stop live trading service."""
        self.state.is_running = False

    def reset_position(self) -> None:
        """Reset position."""
        self.state.position = 0
        self.state.realized_pnl = 0.0

    def snapshot(self) -> LiveState:
        """Get current state snapshot."""
        return self.state


def get_live_service(cfg: AppConfig) -> LiveService:
    """Get live service instance."""
    return LiveService(cfg)


