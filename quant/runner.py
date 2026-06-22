"""按策略名运行回测的便捷入口，供后端 API / 页面共用，避免重复拼装逻辑。"""

import pandas as pd

from . import metrics
from .costs import CostModel
from .engine import run_backtest, run_event_backtest
from .strategies import get_strategy


def run_strategy_backtest(
    price: pd.DataFrame,
    strategy_name: str,
    params: dict | None = None,
    cost_model: CostModel | None = None,
    engine: str = "vectorized",
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    """根据策略名+参数跑回测，返回 (逐日结果 DataFrame, 指标 dict)。

    engine: ``"vectorized"`` 向量化（默认，快）；``"event"`` 事件驱动（支持止损止盈）。
    stop_loss / take_profit 仅在事件驱动引擎下生效（相对建仓价比例，如 0.1=10%）。
    """
    strategy = get_strategy(strategy_name)(**(params or {}))
    signal = strategy.generate_signal(price)
    if engine == "event":
        result = run_event_backtest(
            price, signal, cost_model=cost_model,
            stop_loss=stop_loss, take_profit=take_profit,
        )
    else:
        result = run_backtest(price, signal, cost_model=cost_model)
    return result, metrics.summarize(result)
