"""实验记录落地与查询 + /experiments 路由（用临时 DB，不污染 data/）。"""

import importlib

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def exp(tmp_path, monkeypatch):
    """把实验 DB 指到临时路径，重载模块使其生效。"""
    from quant import experiments

    monkeypatch.setattr(experiments, "_DB_PATH", tmp_path / "experiments.db")
    return experiments


def test_record_and_list(exp):
    rid = exp.record(
        kind="backtest",
        symbol="000001",
        strategy="ma_cross",
        params={"short": 5},
        summary={"sharpe_ratio": 1.2},
    )
    assert isinstance(rid, int)
    rows = exp.list_experiments()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "000001"
    assert rows[0]["summary"]["sharpe_ratio"] == 1.2


def test_filter_and_order(exp):
    exp.record(kind="backtest", symbol="000001", strategy="ma_cross", params={}, summary={})
    exp.record(kind="optimize_grid", symbol="600000", strategy="rsi_reversal", params={}, summary={})
    exp.record(kind="backtest", symbol="600000", strategy="macd_trend", params={}, summary={})

    only_bt = exp.list_experiments(kind="backtest")
    assert {r["kind"] for r in only_bt} == {"backtest"}
    # 倒序：最后插入的在最前
    assert only_bt[0]["strategy"] == "macd_trend"

    by_symbol = exp.list_experiments(symbol="600000")
    assert len(by_symbol) == 2


def test_record_never_raises(exp, monkeypatch):
    # 即便底层写库异常，record 也只返回 None，不抛错
    monkeypatch.setattr(exp, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert exp.record(kind="x", params={}, summary={}) is None


def test_experiments_endpoint(tmp_path, monkeypatch):
    from quant import experiments

    monkeypatch.setattr(experiments, "_DB_PATH", tmp_path / "exp.db")
    experiments.record(kind="backtest", symbol="000001", strategy="ma_cross", params={}, summary={})
    client = TestClient(app)
    rows = client.get("/api/experiments", params={"kind": "backtest"}).json()
    assert any(r["symbol"] == "000001" for r in rows)
