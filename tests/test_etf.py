"""ETF/基金支持：标的分类、市场前缀、数据源路由（离线，不触网）。"""

import pandas as pd

from quant.data import fetcher
from quant.data.instruments import is_fund, market


def test_is_fund():
    assert is_fund("512480")  # 沪 ETF
    assert is_fund("159915")  # 深 ETF
    assert is_fund("588000")  # 科创 50 ETF（沪 5）
    assert is_fund("161725")  # 深 LOF（16）
    assert not is_fund("600519")
    assert not is_fund("000001")
    assert not is_fund("688981")  # 科创板个股


def test_market():
    assert market("512480") == "sh"
    assert market("600519") == "sh"
    assert market("159915") == "sz"
    assert market("000001") == "sz"
    assert market("830799") == "bj"


def test_fetch_routes_fund_vs_stock(monkeypatch):
    """is_fund 的代码走基金源，其余走个股源。"""
    called: list[str] = []

    def make(tag):
        def fn(symbol, start, end, adjust):
            called.append(tag)
            idx = pd.to_datetime(["2024-01-02"])
            cols = ["open", "close", "high", "low", "volume", "amount"]
            return pd.DataFrame({c: [1.0] for c in cols}, index=idx)

        return fn

    monkeypatch.setattr(fetcher, "_STOCK_SOURCES", (("stock", make("stock")),))
    monkeypatch.setattr(fetcher, "_FUND_SOURCES", (("fund", make("fund")),))
    monkeypatch.setattr(fetcher, "_preferred_source", {})
    monkeypatch.setattr(fetcher.storage, "save_cache", lambda *a, **k: None)

    fetcher.get_daily("512480", "2024-01-01", "2024-01-31", use_cache=False)
    fetcher.get_daily("600519", "2024-01-01", "2024-01-31", use_cache=False)
    assert called == ["fund", "stock"]
