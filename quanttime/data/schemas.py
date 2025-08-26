from pydantic import BaseModel
from typing import List


class Tick(BaseModel):
    ts: float
    price: float
    size: float
    side: str  # "buy" or "sell"


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBookSnapshot(BaseModel):
    ts: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]


class Trade(BaseModel):
    ts: float
    price: float
    size: float
    aggressive: bool


