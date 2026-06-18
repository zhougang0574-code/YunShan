"""策略注册表 + 参数寻优 + 走动检验测试。"""

import numpy as np
import pandas as pd
import pytest

from quant import optimize
from quant.strategies import REGISTRY, get_strategy, list_strategies


def _price(n=300, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1, n))
    idx = pd.date_range("2021-01-04", periods=n, freq="B")
    return pd.DataFrame(
        {
            "close": close,
            "high": close + np.abs(rng.normal(0, 0.5, n)),
            "low": close - np.abs(rng.normal(0, 0.5, n)),
        },
        index=idx,
    )


def test_registry_populated():
    assert {"ma_cross", "rsi_reversal", "macd_trend", "bollinger_revert"} <= set(REGISTRY)
    spaces = list_strategies()
    assert all(isinstance(v, dict) and v for v in spaces.values())


@pytest.mark.parametrize("name", list(REGISTRY))
def test_each_strategy_produces_valid_signal(name):
    price = _price()
    cls = get_strategy(name)
    signal = cls().generate_signal(price)
    assert signal.index.equals(price.index)
    assert set(signal.dropna().unique()) <= {0.0, 1.0}


def test_grid_search_sorted_and_covers_grid():
    price = _price()
    cls = get_strategy("ma_cross")
    res = optimize.grid_search(price, cls, metric="sharpe_ratio")
    assert not res.empty
    # 降序排列
    assert res["sharpe_ratio"].is_monotonic_decreasing
    # short<long 的非法组合被跳过：合法组合数应少于 3*3 笛卡尔积
    assert len(res) < 9


def test_walk_forward_shape():
    price = _price()
    cls = get_strategy("ma_cross")
    wf = optimize.walk_forward(price, cls, n_splits=3, metric="sharpe_ratio")
    assert len(wf) == 3
    assert {"split", "is_sharpe_ratio", "oos_sharpe_ratio"} <= set(wf.columns)
