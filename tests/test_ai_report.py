"""AI 个股分析（离线：monkeypatch LLM 客户端与数据源，不发真实网络请求）。"""

import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from quant import ai
from quant.ai import report
from quant.data import altdata, fundamentals, quotes
import quant.data as qdata


def _price_df(n=120):
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    closes = np.linspace(100, 60, n)  # 持续下行 → 空头排列
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"close": c, "high": c * 1.01, "low": c * 0.99})


@pytest.fixture
def patch_sources(monkeypatch):
    monkeypatch.setattr(qdata, "get_daily", lambda s, a, b, **k: _price_df())
    monkeypatch.setattr(
        quotes, "get_quote",
        lambda s: {"symbol": s, "price": 60.0, "prev_close": 61.0, "pct_chg": -1.6,
                   "open": 61.0, "high": 61.5, "low": 59.5, "volume": 1.0e7, "amount": 6.0e8},
    )
    monkeypatch.setattr(qdata, "get_name", lambda s: "测试股票")
    monkeypatch.setattr(
        fundamentals, "get_fundamentals",
        lambda s, use_cache=True: {"pe_ttm": 15.0, "roe": 18.0, "profit_yoy": float("nan")},
    )
    monkeypatch.setattr(altdata, "fund_flow", lambda s, use_cache=True: {"main_net": -1.0e7, "main_net_pct": -6.0})


# ---- 数据包：可用性标注 ----

def test_data_pack_availability_full(patch_sources):
    pack = report.build_data_pack("600578")
    assert pack["symbol"] == "600578" and pack["name"] == "测试股票"
    assert pack["availability"]["quote"] == "available"
    assert pack["availability"]["technical"] == "available"
    # profit_yoy 为 NaN → 基本面部分缺失
    assert pack["availability"]["fundamentals"] == "partial"
    assert pack["technical"]["ma_alignment"] == "空头排列"
    assert pack["fundamentals"]["profit_yoy"] is None  # NaN 清洗为 None


def test_data_pack_sources_fail_safe(monkeypatch):
    # 所有数据源抛错 → 各维度降级为 missing，不崩
    def boom(*a, **k):
        raise RuntimeError("source down")

    monkeypatch.setattr(qdata, "get_daily", boom)
    monkeypatch.setattr(quotes, "get_quote", boom)
    monkeypatch.setattr(qdata, "get_name", boom)
    monkeypatch.setattr(fundamentals, "get_fundamentals", boom)
    monkeypatch.setattr(altdata, "fund_flow", boom)

    pack = report.build_data_pack("000001")
    assert pack["availability"] == {
        "quote": "missing",
        "technical": "missing",
        "fundamentals": "missing",
        "fund_flow": "missing",
    }


# ---- 报告解析 / 归一化 ----

def test_generate_report_parses_and_normalizes(patch_sources, monkeypatch):
    fake = {
        "conclusion": "卖出",
        "score": 150,  # 越界 → 收敛到 100
        "trend": "看空",
        "confidence": "中",
        "summary": "空头排列，规避",
        "risks": ["主力净流出"],
        # 故意漏掉 key_points / operation / checklist → 兜底补齐
    }
    monkeypatch.setattr(ai.client, "chat", lambda *a, **k: json.dumps(fake))

    out = report.generate_stock_report("600578")
    r = out["report"]
    assert r["conclusion"] == "卖出"
    assert r["score"] == 100  # clamp
    assert r["operation"] == {"holder": "", "empty": ""}  # 补齐
    assert r["key_points"] == [] and isinstance(r["checklist"], list)
    assert out["availability"]["technical"] == "available"
    assert out["model"]  # 带模型名


def test_generate_report_bad_json_raises(patch_sources, monkeypatch):
    monkeypatch.setattr(ai.client, "chat", lambda *a, **k: "这不是JSON")
    with pytest.raises(ai.LLMError):
        report.generate_stock_report("600578")


# ---- 路由 ----

@pytest.fixture
def client():
    return TestClient(app)


def test_status_disabled(client, monkeypatch):
    monkeypatch.setattr(ai.config, "is_configured", lambda: False)
    body = client.get("/api/ai/status").json()
    assert body["enabled"] is False and "model" in body


def test_report_requires_config(client, monkeypatch):
    monkeypatch.setattr(ai.config, "is_configured", lambda: False)
    resp = client.post("/api/ai/report", json={"symbol": "600578"})
    assert resp.status_code == 400


def test_report_ok(client, monkeypatch):
    monkeypatch.setattr(ai.config, "is_configured", lambda: True)
    monkeypatch.setattr(
        report, "generate_stock_report",
        lambda s: {"symbol": s, "name": "测试股票", "report": {"conclusion": "观望"}},
    )
    body = client.post("/api/ai/report", json={"symbol": "600578"}).json()
    assert body["report"]["conclusion"] == "观望"


def test_report_llm_error_502(client, monkeypatch):
    monkeypatch.setattr(ai.config, "is_configured", lambda: True)

    def boom(s):
        raise ai.LLMError("额度耗尽")

    monkeypatch.setattr(report, "generate_stock_report", boom)
    resp = client.post("/api/ai/report", json={"symbol": "600578"})
    assert resp.status_code == 502 and "额度" in resp.json()["detail"]
