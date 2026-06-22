"""quotes / symbols 个股详情路由（离线，monkeypatch 数据源）。"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import quotes as quotes_router
from backend.routers import symbols as symbols_router
from quant import signals
from quant.data import altdata, fundamentals, quotes


@pytest.fixture(autouse=True)
def patch_sources(monkeypatch):
    monkeypatch.setattr(
        quotes, "get_quote", lambda s: {"symbol": s, "price": 12.3, "pct_chg": 1.5}
    )
    monkeypatch.setattr(
        quotes,
        "get_intraday",
        lambda s: pd.DataFrame({"time": ["09:30"], "price": [12.3], "volume": [100]}),
    )
    monkeypatch.setattr(
        fundamentals,
        "get_fundamentals",
        lambda s, use_cache=True: {"pe_ttm": 15.0, "roe": 18.0, "profit_yoy": float("nan")},
    )
    monkeypatch.setattr(altdata, "fund_flow", lambda s, use_cache=True: {"main_net_pct": 6.0})
    monkeypatch.setattr(altdata, "north_hold", lambda s, use_cache=True: {"hold_market_value": float("nan")})
    monkeypatch.setattr(signals, "for_symbol", lambda s, lookback_days=250: {"symbol": s, "tags": []})
    for mod in (quotes_router, symbols_router):
        monkeypatch.setattr(mod, "get_name", lambda s: "测试股票")


@pytest.fixture
def client():
    return TestClient(app)


def test_quote(client):
    body = client.get("/api/quotes/000001").json()
    assert body["price"] == 12.3 and body["name"] == "测试股票"


def test_intraday(client):
    rows = client.get("/api/quotes/000001/intraday").json()
    assert rows[0]["time"] == "09:30"


def test_signals(client):
    body = client.get("/api/symbols/000001/signals").json()
    assert body["symbol"] == "000001" and "tags" in body


def test_fundamentals_nan_to_null(client):
    body = client.get("/api/symbols/000001/fundamentals").json()
    assert body["roe"] == 18.0
    assert body["profit_yoy"] is None  # NaN -> null


def test_altdata(client):
    body = client.get("/api/symbols/000001/altdata").json()
    assert body["fund_flow"]["main_net_pct"] == 6.0
    assert body["north_hold"]["hold_market_value"] is None
