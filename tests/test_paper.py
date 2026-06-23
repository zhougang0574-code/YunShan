"""模拟交易接口测试：下单撮合、费用、持仓盈亏、净值记录、按用户隔离（离线，不触网）。"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import paper as paper_router
from quant import paper, users


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(users, "_DB_PATH", tmp_path / "users.db")
    monkeypatch.setattr(paper, "_DB_PATH", tmp_path / "paper.db")
    # 行情与名称都会触网，测试里固定返回
    monkeypatch.setattr(paper_router, "get_name", lambda s: "测试标的")
    monkeypatch.setattr(paper_router.quotes, "get_quote", lambda s: {"symbol": s, "price": 10.0})


@pytest.fixture
def client():
    return TestClient(app)


def _register(client, username="alice", password="secret"):
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_requires_auth(client):
    assert client.get("/api/paper/account").status_code == 401
    assert client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 100}).status_code == 401


def test_initial_account(client):
    h = _register(client)
    acct = client.get("/api/paper/account", headers=h).json()
    assert acct["cash"] == paper.DEFAULT_INITIAL
    assert acct["total"] == paper.DEFAULT_INITIAL
    assert acct["positions"] == []


def test_buy_then_sell(client):
    h = _register(client)

    # 买入 1000 股 @ 10 -> 现金减少 名义额 + 费用
    res = client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 1000}, headers=h)
    assert res.status_code == 200, res.text
    acct = res.json()["account"]
    assert acct["cash"] < paper.DEFAULT_INITIAL - 10000  # 含费用
    pos = acct["positions"][0]
    assert pos["symbol"] == "000001"
    assert pos["shares"] == 1000
    assert pos["price"] == 10.0

    # 卖出一半
    res = client.post("/api/paper/order", json={"symbol": "000001", "side": "sell", "shares": 500}, headers=h)
    assert res.status_code == 200, res.text
    acct = res.json()["account"]
    assert acct["positions"][0]["shares"] == 500

    trades = client.get("/api/paper/trades", headers=h).json()
    assert len(trades) == 2
    assert trades[0]["side"] == "sell"  # 最近在前


def test_buy_lot_validation(client):
    h = _register(client)
    res = client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 150}, headers=h)
    assert res.status_code == 400
    assert "100" in res.json()["detail"]


def test_insufficient_cash(client):
    h = _register(client)
    # 100万本金，10元价 -> 最多约10万股，下单20万股必失败
    res = client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 200000}, headers=h)
    assert res.status_code == 400
    assert "现金不足" in res.json()["detail"]


def test_sell_without_holding(client):
    h = _register(client)
    res = client.post("/api/paper/order", json={"symbol": "000001", "side": "sell", "shares": 100}, headers=h)
    assert res.status_code == 400
    assert "持仓不足" in res.json()["detail"]


def test_equity_recorded(client):
    h = _register(client)
    client.get("/api/paper/account", headers=h)
    equity = client.get("/api/paper/equity", headers=h).json()
    assert len(equity) == 1
    assert equity[0]["total"] == paper.DEFAULT_INITIAL


def test_reset(client):
    h = _register(client)
    client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 100}, headers=h)
    acct = client.post("/api/paper/reset", json={}, headers=h).json()
    assert acct["cash"] == paper.DEFAULT_INITIAL
    assert acct["positions"] == []
    assert client.get("/api/paper/trades", headers=h).json() == []


def test_isolated_per_user(client):
    ta = _register(client, "alice", "secret")
    tb = _register(client, "bob", "secret")
    client.post("/api/paper/order", json={"symbol": "000001", "side": "buy", "shares": 100}, headers=ta)

    alice = client.get("/api/paper/account", headers=ta).json()
    bob = client.get("/api/paper/account", headers=tb).json()
    assert len(alice["positions"]) == 1
    assert bob["positions"] == []
    assert bob["cash"] == paper.DEFAULT_INITIAL
