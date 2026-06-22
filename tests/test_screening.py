"""截面选股 + 股票池 + 基本面因子（离线，monkeypatch akshare/数据源）。"""

import numpy as np
import pandas as pd
import pytest

from quant import screening
from quant.data import fundamentals, universe


@pytest.fixture
def fake_universe(monkeypatch):
    members = pd.DataFrame(
        {"code": ["000001", "000002", "000003", "000004"], "name": list("甲乙丙丁")}
    )
    monkeypatch.setattr(universe, "get_constituents", lambda key, use_cache=True: members)
    return members


@pytest.fixture
def fake_snapshot(monkeypatch):
    snap = pd.DataFrame(
        {
            "pe": [10.0, 20.0, 30.0, 40.0],
            "pb": [1.0, 2.0, 3.0, 4.0],
            "total_mv": [1e9, 2e9, 3e9, 4e9],
            "turnover": [1.0, 2.0, 3.0, 4.0],
            "ret_60d": [5.0, 10.0, -5.0, 0.0],
            "ret_ytd": [1.0, 2.0, 3.0, 4.0],
        },
        index=pd.Index(["000001", "000002", "000003", "000004"], name="code"),
    )
    monkeypatch.setattr(fundamentals, "market_snapshot", lambda use_cache=True: snap)
    return snap


def test_available_factors_has_both_kinds():
    cat = screening.available_factors()
    assert cat["pe"]["kind"] == "fundamental"
    assert cat["tech_mom_20"]["kind"] == "technical"
    assert cat["pe"]["direction"] == "low"


def test_screen_fundamental_only_ranks_low_pe_first(fake_universe, fake_snapshot):
    # 仅用 pe（低估值优）：最低 PE 的 000001 应排第一
    df = screening.screen(
        factors=[{"key": "pe", "weight": 1.0}],
        universe_key="index:000300",
        top_n=10,
    )
    assert list(df["code"]) == ["000001", "000002", "000003", "000004"]
    assert df.iloc[0]["rank"] == 1
    # direction=low 时，最低 PE 的标准化分应为正且最大
    assert df.iloc[0]["pe_z"] > 0 > df.iloc[-1]["pe_z"]


def test_screen_weights_and_detail_columns(fake_universe, fake_snapshot):
    df = screening.screen(
        factors=[
            {"key": "pe", "weight": 1.0},
            {"key": "mom_60d", "weight": 2.0},
        ],
        universe_key="all",
    )
    assert {"pe", "pe_z", "mom_60d", "mom_60d_z", "score"} <= set(df.columns)
    # 综合分应等于按权重的 z 加权和
    row = df.iloc[0]
    expected = 1.0 * row["pe_z"] + 2.0 * row["mom_60d_z"]
    assert row["score"] == pytest.approx(expected)


def test_screen_unknown_factor_raises(fake_universe, fake_snapshot):
    with pytest.raises(ValueError):
        screening.screen(factors=[{"key": "not_a_factor"}])


def test_screen_technical_uses_price_loader(fake_universe, fake_snapshot):
    calls = []

    def loader(symbol, start, end):
        calls.append(symbol)
        n = 80
        idx = pd.date_range(start, periods=n, freq="B")
        # 让 000004 动量最高
        drift = 0.01 if symbol == "000004" else 0.0
        close = 100 + np.cumsum(np.full(n, drift) + 0.001)
        return pd.DataFrame({"close": close, "high": close, "low": close}, index=idx)

    progress = []
    df = screening.screen(
        factors=[{"key": "tech_mom_20", "weight": 1.0}],
        universe_key="all",
        price_loader=loader,
        progress=progress.append,
    )
    assert len(calls) == 4  # 每只股票都拉了价格
    assert progress and progress[-1] == pytest.approx(1.0)
    assert df.iloc[0]["code"] == "000004"


def test_normalize_code_name_fuzzy():
    raw = pd.DataFrame({"品种代码": ["1", "600000"], "品种名称": ["x", "y"]})
    out = universe._normalize_code_name(raw)
    assert list(out.columns) == ["code", "name"]
    assert out.iloc[0]["code"] == "000001"  # zfill 到 6 位
