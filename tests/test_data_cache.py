"""数据缓存正确性测试：范围感知增量补拉 + adjust 隔离。"""

import pandas as pd
import pytest

from quant import config
from quant.data import fetcher, storage


@pytest.fixture
def synthetic_market(tmp_path, monkeypatch):
    """把缓存目录指向临时目录，并用确定性假行情替换 akshare 拉取。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    full = pd.DataFrame(
        {c: range(1, 11) for c in storage.COLUMNS},
        index=pd.date_range("2022-01-03", periods=10, freq="B"),
    )
    full.index.name = "date"

    calls = []

    def fake_fetch(symbol, start, end, adjust):
        calls.append((start, end, adjust))
        return full.loc[pd.Timestamp(start) : pd.Timestamp(end)]

    monkeypatch.setattr(fetcher, "_fetch_raw", fake_fetch)
    return full, calls


def test_incremental_fills_gaps(synthetic_market):
    full, _ = synthetic_market
    # 先缓存中间一小段
    first = fetcher.get_daily("TEST", "2022-01-10", "2022-01-12", adjust="qfq")
    assert len(first) == 3
    # 再请求更大区间：应补齐头尾而非返回缓存子集
    second = fetcher.get_daily("TEST", "2022-01-03", "2022-01-14", adjust="qfq")
    assert len(second) == 10
    assert second.index.min() == full.index.min()
    assert second.index.max() == full.index.max()


def test_subset_request_hits_cache(synthetic_market):
    full, calls = synthetic_market
    fetcher.get_daily("TEST", "2022-01-03", "2022-01-14", adjust="qfq")
    n_calls = len(calls)
    # 请求已覆盖区间的子集，不应再触发拉取
    fetcher.get_daily("TEST", "2022-01-05", "2022-01-07", adjust="qfq")
    assert len(calls) == n_calls


def test_adjust_isolation(synthetic_market):
    fetcher.get_daily("TEST", "2022-01-03", "2022-01-14", adjust="qfq")
    qfq_df, _ = storage.load_cached("TEST", "qfq")
    hfq_df, _ = storage.load_cached("TEST", "hfq")
    assert qfq_df is not None
    assert hfq_df is None  # 不同复权方式互不污染
