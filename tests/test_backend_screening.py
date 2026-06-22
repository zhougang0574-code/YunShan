"""screening / universe 路由（离线，TestClient + monkeypatch 数据源）。

注：Starlette TestClient 会在返回响应前同步跑完 BackgroundTasks，所以提交后
立即轮询即可拿到完成结果。"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import screening as screening_router
from quant import screening
from quant.data import fundamentals, universe


@pytest.fixture(autouse=True)
def patch_sources(monkeypatch):
    members = pd.DataFrame({"code": ["000001", "000002", "000003"], "name": list("甲乙丙")})
    snap = pd.DataFrame(
        {"pe": [10.0, 20.0, 30.0], "pb": [1.0, 2.0, 3.0]},
        index=pd.Index(["000001", "000002", "000003"], name="code"),
    )
    monkeypatch.setattr(universe, "get_constituents", lambda key, use_cache=True: members)
    monkeypatch.setattr(fundamentals, "market_snapshot", lambda use_cache=True: snap)
    monkeypatch.setattr(
        universe, "list_universes", lambda: {"all": {"key": "all", "label": "全市场"}, "indices": [], "industries": []}
    )
    # 不真正落地实验记录
    monkeypatch.setattr(screening_router, "record_experiment", lambda **k: None)


@pytest.fixture
def client():
    return TestClient(app)


def test_universe_list(client):
    body = client.get("/api/universe").json()
    assert "all" in body


def test_universe_constituents(client):
    rows = client.get("/api/universe/constituents", params={"key": "all"}).json()
    assert {r["code"] for r in rows} == {"000001", "000002", "000003"}


def test_screening_factors(client):
    cat = client.get("/api/screening/factors").json()
    assert "pe" in cat and cat["pe"]["kind"] == "fundamental"


def test_screening_submit_and_poll(client):
    resp = client.post(
        "/api/screening",
        json={
            "universe_key": "all",
            "factors": [{"key": "pe", "weight": 1.0}],
            "top_n": 10,
        },
    )
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    status = client.get(f"/api/screening/{task_id}").json()
    assert status["status"] == "done"
    assert status["progress"] == 1.0
    # 低 PE 的 000001 排第一
    assert status["results"][0]["code"] == "000001"


def test_screening_unknown_factor_rejected(client):
    resp = client.post(
        "/api/screening",
        json={"universe_key": "all", "factors": [{"key": "bogus"}]},
    )
    assert resp.status_code == 400


def test_screening_missing_task(client):
    assert client.get("/api/screening/deadbeef").status_code == 404
