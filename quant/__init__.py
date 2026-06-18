"""YunShan 量化核心库。

纯 Python，不依赖任何 Web 框架，可被 FastAPI 后端、脚本或 Notebook 直接调用。
"""

from . import config, costs, factors, metrics, optimize, portfolio, strategies
from .data import get_daily
from .engine import run_backtest
from .runner import run_strategy_backtest

__all__ = [
    "config",
    "costs",
    "factors",
    "metrics",
    "optimize",
    "portfolio",
    "strategies",
    "get_daily",
    "run_backtest",
    "run_strategy_backtest",
]
