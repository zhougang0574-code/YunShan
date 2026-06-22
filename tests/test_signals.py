"""个股注意点信号 evaluate（纯函数，构造数据触发各类标签）。"""

import numpy as np
import pandas as pd

from quant import signals


def _price(closes):
    idx = pd.date_range("2023-01-01", periods=len(closes), freq="B")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"close": c, "high": c, "low": c})


def test_no_tags_when_too_short():
    assert signals.evaluate(_price([1, 2, 3])) == []


def test_rsi_oversold_tag():
    # 持续下跌 → RSI 极低 → 超卖标签
    closes = list(np.linspace(100, 50, 80))
    tags = signals.evaluate(_price(closes))
    assert any("超卖" in t["text"] and t["level"] == "good" for t in tags)


def test_rsi_overbought_tag():
    closes = list(np.linspace(50, 150, 80))
    tags = signals.evaluate(_price(closes))
    assert any("超买" in t["text"] and t["level"] == "warn" for t in tags)


def test_fundamental_tags():
    tags = signals.evaluate(
        fundamentals={"pe_ttm": 120.0, "roe": -3.0, "profit_yoy": -20.0}
    )
    texts = " ".join(t["text"] for t in tags)
    assert "估值偏高" in texts and "盈利恶化" in texts and "下滑" in texts
    assert {t["category"] for t in tags} == {"fundamental"}


def test_altdata_tags():
    out = signals.evaluate(alt={"main_net_pct": -8.0})
    assert out and out[0]["category"] == "altdata" and out[0]["level"] == "warn"
    out2 = signals.evaluate(alt={"main_net_pct": 9.0})
    assert out2[0]["level"] == "good"


def test_nan_fundamentals_ignored():
    assert signals.evaluate(fundamentals={"pe_ttm": float("nan"), "roe": float("nan")}) == []
