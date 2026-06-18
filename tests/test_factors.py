"""因子库测试：取值范围、对齐、无未来值。"""

import numpy as np
import pandas as pd

from quant.factors import technical


def _price(n=120, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {
            "close": close,
            "high": close + np.abs(rng.normal(0, 0.5, n)),
            "low": close - np.abs(rng.normal(0, 0.5, n)),
        },
        index=idx,
    )


def test_rsi_bounded():
    rsi = technical.rsi(_price(), 14)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_macd_columns_aligned():
    out = technical.macd(_price())
    assert list(out.columns) == ["dif", "dea", "hist"]
    assert len(out) == 120


def test_bollinger_order():
    bands = technical.bollinger(_price(), 20, 2.0).dropna()
    assert (bands["upper"] >= bands["mid"]).all()
    assert (bands["mid"] >= bands["lower"]).all()


def test_sma_no_lookahead():
    """改动末尾价格不应影响更早的 SMA 值。"""
    p = _price()
    base = technical.sma(p, 20)
    p2 = p.copy()
    p2.iloc[-1, p2.columns.get_loc("close")] += 50
    altered = technical.sma(p2, 20)
    pd.testing.assert_series_equal(base.iloc[:-1], altered.iloc[:-1])
