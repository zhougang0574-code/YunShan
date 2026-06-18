"""策略包：导入各策略以触发注册，并暴露注册表辅助函数。"""

from .base import REGISTRY, get_strategy, list_strategies, register
from .bollinger_revert import BollingerRevertStrategy
from .ma_cross import MovingAverageCrossStrategy
from .macd_trend import MacdTrendStrategy
from .rsi_reversal import RsiReversalStrategy

__all__ = [
    "REGISTRY",
    "get_strategy",
    "list_strategies",
    "register",
    "MovingAverageCrossStrategy",
    "RsiReversalStrategy",
    "MacdTrendStrategy",
    "BollingerRevertStrategy",
]
