"""回测引擎：向量化（Phase 1）+ 事件驱动（Phase 4）。"""

from .event_driven import run_event_backtest
from .vectorized import run_backtest

__all__ = ["run_backtest", "run_event_backtest"]
