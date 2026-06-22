"""标的库接口：分页、搜索、股票/基金切换（用假表，离线）。"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from quant.data import symbols


@pytest.fixture(autouse=True)
def fake_tables(monkeypatch):
    stocks = {"000001": "平安银行", "600519": "贵州茅台", "000002": "万科A"}
    funds = {"512480": "半导体ETF", "159915": "创业板ETF"}
    monkeypatch.setattr(symbols, "_load", lambda: stocks)
    monkeypatch.setattr(symbols, "_load_funds", lambda: funds)


@pytest.fixture
def client():
    return TestClient(app)


def test_catalog_stock_paged(client):
    r = client.get("/api/catalog", params={"kind": "stock", "page": 1, "page_size": 2}).json()
    assert r["total"] == 3
    assert len(r["items"]) == 2
    assert r["items"][0]["symbol"] == "000001"  # 按代码升序


def test_catalog_fund(client):
    r = client.get("/api/catalog", params={"kind": "fund"}).json()
    assert r["total"] == 2
    assert {i["symbol"] for i in r["items"]} == {"512480", "159915"}


def test_catalog_search_by_name_and_code(client):
    by_name = client.get("/api/catalog", params={"kind": "stock", "query": "茅台"}).json()
    assert by_name["total"] == 1 and by_name["items"][0]["symbol"] == "600519"

    by_code = client.get("/api/catalog", params={"kind": "stock", "query": "000"}).json()
    assert by_code["total"] == 2
