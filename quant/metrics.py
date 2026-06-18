"""业绩指标。

修正旧实现的两处口径问题：
1. 新增**交易级胜率**（按每笔完整持仓的盈亏统计），旧的"每日上涨占比"保留为
   ``daily_win_rate``，不再混称"胜率"。
2. 夏普提供 ``active_only`` 选项，仅用持仓日收益计算，避免空仓日 0 收益稀释。
另补充基准对比、Sortino、Calmar。
"""

import numpy as np
import pandas as pd

from . import config

TRADING_DAYS_PER_YEAR = config.TRADING_DAYS_PER_YEAR


def annualized_return(equity: pd.Series) -> float:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    n_days = len(equity)
    if n_days <= 1:
        return 0.0
    return (1 + total_return) ** (TRADING_DAYS_PER_YEAR / n_days) - 1


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return float(drawdown.min())


def sharpe_ratio(
    daily_return: pd.Series, risk_free_rate: float = 0.0, active_only: bool = False
) -> float:
    series = daily_return[daily_return != 0] if active_only else daily_return
    if len(series) == 0:
        return 0.0
    excess = series - risk_free_rate / TRADING_DAYS_PER_YEAR
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(daily_return: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = daily_return - risk_free_rate / TRADING_DAYS_PER_YEAR
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR))


def calmar_ratio(equity: pd.Series) -> float:
    mdd = max_drawdown(equity)
    if mdd == 0:
        return 0.0
    return float(annualized_return(equity) / abs(mdd))


def daily_win_rate(daily_return: pd.Series) -> float:
    """每日盈利占比（仅统计有持仓/非零收益的交易日）。"""
    traded = daily_return[daily_return != 0]
    if len(traded) == 0:
        return 0.0
    return float((traded > 0).sum() / len(traded))


def _trade_returns(result: pd.DataFrame) -> list[float]:
    """把每段连续持仓视作一笔交易，返回每笔的净收益率。"""
    pos = result["position"] > 0
    ret = result["daily_return"]
    entry = pos & ~pos.shift(1, fill_value=False)
    seg = entry.cumsum().where(pos)
    trade_rets: list[float] = []
    for _, grp in ret[pos].groupby(seg[pos]):
        trade_rets.append(float((1 + grp).prod() - 1))
    return trade_rets


def trade_win_rate(result: pd.DataFrame) -> float:
    """交易级胜率：盈利的完整持仓笔数占比。"""
    trades = _trade_returns(result)
    if not trades:
        return 0.0
    wins = sum(1 for r in trades if r > 0)
    return wins / len(trades)


def summarize(result: pd.DataFrame) -> dict:
    """汇总策略与基准指标。result 来自 engine.run_backtest。"""
    equity = result["equity"]
    daily_return = result["daily_return"]
    stats = {
        "annualized_return": annualized_return(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe_ratio": sharpe_ratio(daily_return),
        "sortino_ratio": sortino_ratio(daily_return),
        "calmar_ratio": calmar_ratio(equity),
        "trade_win_rate": trade_win_rate(result),
        "daily_win_rate": daily_win_rate(daily_return),
        "total_trades": len(_trade_returns(result)),
    }
    if "benchmark_equity" in result:
        bench = result["benchmark_equity"]
        stats["benchmark_return"] = annualized_return(bench)
        stats["excess_return"] = stats["annualized_return"] - stats["benchmark_return"]
    return stats
