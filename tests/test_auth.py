"""登录 + 收藏接口测试：注册/登录/鉴权、收藏 CRUD、按用户隔离（离线，不触网）。"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import favorites as favorites_router
from quant import users


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    # 每个测试用独立的临时 users.db，互不污染
    monkeypatch.setattr(users, "_DB_PATH", tmp_path / "users.db")
    # 收藏加名称会查 get_name（会触网），测试里固定返回
    monkeypatch.setattr(favorites_router, "get_name", lambda s: "测试股票")


@pytest.fixture
def client():
    return TestClient(app)


def _register(client, username="alice", password="secret"):
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me(client):
    token = _register(client)
    assert client.get("/api/auth/me", headers=_auth(token)).json() == {"username": "alice"}

    # 重复注册 -> 409
    dup = client.post("/api/auth/register", json={"username": "alice", "password": "x123"})
    assert dup.status_code == 409

    # 正确登录拿到新 token
    login = client.post("/api/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200

    # 密码错误 -> 401
    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401


def test_favorites_require_auth(client):
    assert client.get("/api/favorites").status_code == 401
    assert client.post("/api/favorites", json={"symbol": "000001"}).status_code == 401


def test_favorites_crud(client):
    token = _register(client)
    h = _auth(token)

    assert client.get("/api/favorites", headers=h).json() == []

    rows = client.post("/api/favorites", json={"symbol": "000001"}, headers=h).json()
    assert [r["symbol"] for r in rows] == ["000001"]
    assert rows[0]["name"] == "测试股票"

    # 再加一个，最近的在前
    rows = client.post("/api/favorites", json={"symbol": "600519"}, headers=h).json()
    assert [r["symbol"] for r in rows] == ["600519", "000001"]

    # 幂等：重复加不产生重复
    rows = client.post("/api/favorites", json={"symbol": "600519"}, headers=h).json()
    assert [r["symbol"] for r in rows] == ["600519", "000001"]

    # 删除
    rows = client.delete("/api/favorites/600519", headers=h).json()
    assert [r["symbol"] for r in rows] == ["000001"]


def test_favorites_isolated_per_user(client):
    ta = _register(client, "alice", "secret")
    tb = _register(client, "bob", "secret")

    client.post("/api/favorites", json={"symbol": "000001"}, headers=_auth(ta))
    client.post("/api/favorites", json={"symbol": "600519"}, headers=_auth(tb))

    alice = [r["symbol"] for r in client.get("/api/favorites", headers=_auth(ta)).json()]
    bob = [r["symbol"] for r in client.get("/api/favorites", headers=_auth(tb)).json()]
    assert alice == ["000001"]
    assert bob == ["600519"]


def test_logout_invalidates_token(client):
    token = _register(client)
    h = _auth(token)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=h).status_code == 401
