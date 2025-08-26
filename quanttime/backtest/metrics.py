import numpy as np


def sharpe_ratio(returns: np.ndarray, eps: float = 1e-9) -> float:
    if returns.size == 0:
        return 0.0
    mu = returns.mean()
    sigma = returns.std() + eps
    return float(mu / sigma * np.sqrt(252))


def sortino_ratio(returns: np.ndarray, eps: float = 1e-9) -> float:
    downside = returns[returns < 0]
    if returns.size == 0:
        return 0.0
    mu = returns.mean()
    dd = downside.std() + eps
    return float(mu / dd * np.sqrt(252))


def max_drawdown(equity: np.ndarray) -> float:
    if equity.size == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / (peak + 1e-9)
    return float(drawdown.min())


