"""事件驱动引擎：与向量化引擎一致性 + 止损止盈路径依赖。"""

import numpy as np
import pandas as pd

from quant.costs import CostModel
from quant.engine import run_backtest, run_event_backtest
from quant.strategies import get_strategy

ZERO_COST = CostModel(
    commission_rate=0.0,
    commission_min=0.0,
    stamp_tax_rate=0.0,
    transfer_fee_rate=0.0,
    slippage_rate=0.0,
)


def _price(seed=0, n=200):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {"close": close, "high": close + 0.5, "low": close - 0.5}, index=idx
    )


def test_matches_vectorized_without_costs_or_stops():
    price = _price(seed=1)
    signal = get_strategy("ma_cross")(short_window=5, long_window=20).generate_signal(price)
    vec = run_backtest(price, signal, cost_model=ZERO_COST)
    evt = run_event_backtest(price, signal, cost_model=ZERO_COST)
    # 无成本无止损时，逐日净值应与向量化引擎几乎完全一致
    np.testing.assert_allclose(evt["equity"].to_numpy(), vec["equity"].to_numpy(), rtol=1e-9)
    pd.testing.assert_series_equal(
        evt["position"], vec["position"], check_names=False
    )


def test_stop_loss_caps_loss_vs_no_stop():
    # 单调下跌中持有：止损应比不止损少亏
    n = 60
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 60, n), index=idx)
    price = pd.DataFrame({"close": close, "high": close + 0.2, "low": close - 0.2})
    signal = pd.Series(1.0, index=idx)  # 全程想持有

    no_stop = run_event_backtest(price, signal, cost_model=ZERO_COST)
    with_stop = run_event_backtest(price, signal, cost_model=ZERO_COST, stop_loss=0.05)

    assert with_stop["equity"].iloc[-1] > no_stop["equity"].iloc[-1]
    # 止损后应转为空仓
    assert with_stop["position"].iloc[-1] == 0.0


def test_take_profit_exits_in_uptrend():
    n = 60
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 140, n), index=idx)
    price = pd.DataFrame({"close": close, "high": close + 0.2, "low": close - 0.2})
    signal = pd.Series(1.0, index=idx)

    tp = run_event_backtest(price, signal, cost_model=ZERO_COST, take_profit=0.1)
    # 止盈触发后离场，期末应空仓
    assert tp["position"].iloc[-1] == 0.0
    # 锁定的收益约为 +10%（建仓价 100 附近，止盈价 110 附近）
    assert tp["equity"].iloc[-1] > 100_000 * 1.05


def test_costs_drag_equity_below_zero_cost():
    price = _price(seed=2)
    signal = get_strategy("ma_cross")(short_window=5, long_window=20).generate_signal(price)
    free = run_event_backtest(price, signal, cost_model=ZERO_COST)
    costed = run_event_backtest(price, signal)  # 默认含成本
    assert costed["equity"].iloc[-1] <= free["equity"].iloc[-1]
