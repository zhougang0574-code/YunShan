"""回测引擎测试：无未来函数 + 成本扣减 + 基准对比。"""

import numpy as np
import pandas as pd

from quant import metrics, run_backtest
from quant.costs import CostModel


def _price(returns):
    close = 100 * (1 + pd.Series(returns)).cumprod()
    idx = pd.date_range("2022-01-03", periods=len(close), freq="B")
    return pd.DataFrame({"close": close.values}, index=idx)


def test_no_lookahead():
    """信号 T 日生成、T+1 生效：仅最后一天置仓不应影响历史权益。"""
    price = _price([0.0, 0.01, -0.02, 0.03, 0.01, -0.01])
    base_signal = pd.Series(0.0, index=price.index)
    base_signal.iloc[2:5] = 1.0

    r1 = run_backtest(price, base_signal, cost_model=CostModel(slippage_rate=0))
    # 改动最后一天的信号，历史权益曲线（除最后一天）应完全不变
    altered = base_signal.copy()
    altered.iloc[-1] = 1.0
    r2 = run_backtest(price, altered, cost_model=CostModel(slippage_rate=0))
    pd.testing.assert_series_equal(r1["equity"].iloc[:-1], r2["equity"].iloc[:-1])


def test_costs_reduce_return():
    price = _price([0.0, 0.01, 0.01, 0.01, 0.01])
    signal = pd.Series([0, 1, 0, 1, 0], index=price.index, dtype=float)
    free = run_backtest(price, signal, cost_model=CostModel(commission_rate=0, stamp_tax_rate=0, transfer_fee_rate=0, slippage_rate=0))
    costly = run_backtest(price, signal, cost_model=CostModel(commission_rate=0.001))
    assert costly["equity"].iloc[-1] < free["equity"].iloc[-1]


def test_benchmark_present_and_buyhold_matches():
    price = _price([0.0, 0.02, -0.01, 0.03])
    # 全程满仓且零成本，策略净值应与买入持有基准一致
    signal = pd.Series(1.0, index=price.index)
    r = run_backtest(price, signal, cost_model=CostModel(commission_rate=0, stamp_tax_rate=0, transfer_fee_rate=0, slippage_rate=0))
    assert "benchmark_equity" in r
    np.testing.assert_allclose(r["equity"].values, r["benchmark_equity"].values, rtol=1e-9)


def test_trade_win_rate_counts_round_trips():
    price = _price([0.0, 0.05, 0.05, -0.10, -0.10, 0.0])
    # 两段持仓：第一段盈利，第二段亏损 -> 交易胜率应为 0.5
    signal = pd.Series([0, 1, 0, 0, 1, 0], index=price.index, dtype=float)
    r = run_backtest(price, signal, cost_model=CostModel(commission_rate=0, stamp_tax_rate=0, transfer_fee_rate=0, slippage_rate=0))
    assert metrics.summarize(r)["total_trades"] == 2
    assert metrics.trade_win_rate(r) == 0.5
