"""向量化回测引擎。

按 signal 仓位（1=满仓，0=空仓；未来可扩展为 0~1 权重）模拟每日权益，
并扣除交易成本、输出买入持有基准以便对比。

防未来函数：signal 在 T 日收盘后产生，仓位延迟到 T+1 日生效（``signal.shift(1)``）。
"""

import pandas as pd

from .. import config
from ..costs import CostModel


def run_backtest(
    price: pd.DataFrame,
    signal: pd.Series,
    initial_capital: float = config.INITIAL_CAPITAL,
    cost_model: CostModel | None = None,
) -> pd.DataFrame:
    """向量化回测，返回逐日明细 DataFrame。

    列：close / position / turnover / gross_return / cost / daily_return(净)
        / equity(策略净值) / benchmark_equity(买入持有基准)
    """
    cost_model = cost_model or CostModel()

    daily_return = price["close"].pct_change().fillna(0.0)
    position = signal.shift(1).fillna(0.0)

    # 换手：仓位变化绝对值，首日建仓也计成本
    turnover = position.diff().abs().fillna(position.abs())
    cost = cost_model.turnover_cost_rate(turnover)

    gross_return = daily_return * position
    net_return = gross_return - cost
    equity = (1 + net_return).cumprod() * initial_capital
    benchmark_equity = (1 + daily_return).cumprod() * initial_capital

    return pd.DataFrame(
        {
            "close": price["close"],
            "position": position,
            "turnover": turnover,
            "gross_return": gross_return,
            "cost": cost,
            "daily_return": net_return,
            "equity": equity,
            "benchmark_equity": benchmark_equity,
        }
    )
