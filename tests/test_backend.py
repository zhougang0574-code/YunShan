"""后端 API 测试：TestClient + 合成行情（离线，不触网）。"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import backtest as backtest_router
from backend.routers import data as data_router
from backend.routers import optimize as optimize_router


def _synthetic_price(symbol, start, end, adjust="qfq"):
    n = 250
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    close = 100 + np.cumsum(rng.normal(0.05, 1, n))
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.DataFrame(
        {"close": close, "high": close + 0.5, "low": close - 0.5}, index=idx
    )


@pytest.fixture(autouse=True)
def patch_get_daily(monkeypatch):
    for mod in (backtest_router, data_router, optimize_router):
        monkeypatch.setattr(mod, "get_daily", _synthetic_price)
    # 名称查询固定返回，避免触网
    for mod in (backtest_router, data_router):
        monkeypatch.setattr(mod, "get_name", lambda s: "测试股票")


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_strategies(client):
    resp = client.get("/api/strategies")
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert {"ma_cross", "rsi_reversal", "macd_trend", "bollinger_revert"} <= names
    # 每个策略都带参数空间
    assert all(s["param_space"] for s in resp.json())


def test_data_endpoint(client):
    resp = client.get("/api/data/000001", params={"start": "2022-01-03", "end": "2023-01-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "000001" and body["rows"] == 250
    assert body["name"] == "测试股票"


def test_backtest_endpoint(client):
    resp = client.post(
        "/api/backtest",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "ma_cross",
            "params": {"short_window": 5, "long_window": 20},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "sharpe_ratio" in body["stats"]
    s = body["series"]
    assert len(s["dates"]) == len(s["equity"]) == len(s["benchmark_equity"]) == 250


def test_backtest_event_engine_with_stops(client):
    resp = client.post(
        "/api/backtest",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "ma_cross",
            "params": {"short_window": 5, "long_window": 20},
            "engine": "event",
            "stop_loss": 0.08,
            "take_profit": 0.2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "sharpe_ratio" in body["stats"]
    assert len(body["series"]["equity"]) == 250


def test_backtest_invalid_params(client):
    resp = client.post(
        "/api/backtest",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "ma_cross",
            "params": {"short_window": 30, "long_window": 10},  # short>=long 非法
        },
    )
    assert resp.status_code == 422


def test_backtest_unknown_strategy(client):
    resp = client.post(
        "/api/backtest",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "does_not_exist",
        },
    )
    assert resp.status_code == 400


def test_optimize_grid(client):
    resp = client.post(
        "/api/optimize",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "ma_cross",
            "metric": "sharpe_ratio",
            "mode": "grid",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    results = body["results"]
    assert results and "sharpe_ratio" in results[0]
    # 网格寻优附带稳健性检验
    rob = body["robustness"]
    assert rob is not None
    assert "deflated_sharpe_ratio" in rob and "monte_carlo" in rob


def test_optimize_walk_forward(client):
    resp = client.post(
        "/api/optimize",
        json={
            "symbol": "000001",
            "start": "2022-01-03",
            "end": "2023-01-01",
            "strategy": "ma_cross",
            "metric": "sharpe_ratio",
            "mode": "walk_forward",
            "n_splits": 3,
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 3
    assert "oos_sharpe_ratio" in results[0]
