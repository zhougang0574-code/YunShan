"""按策略名运行回测的便捷入口，供后端 API / 页面共用，避免重复拼装逻辑。"""

import pandas as pd

from . import metrics
from .costs import CostModel
from .engine import run_backtest
from .strategies import get_strategy


def run_strategy_backtest(
    price: pd.DataFrame,
    strategy_name: str,
    params: dict | None = None,
    cost_model: CostModel | None = None,
) -> tuple[pd.DataFrame, dict]:
    """根据策略名+参数跑回测，返回 (逐日结果 DataFrame, 指标 dict)。"""
    strategy = get_strategy(strategy_name)(**(params or {}))
    signal = strategy.generate_signal(price)
    result = run_backtest(price, signal, cost_model=cost_model)
    return result, metrics.summarize(result)
