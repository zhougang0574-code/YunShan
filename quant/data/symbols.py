"""A 股「代码 → 名称」查询。

首次调用拉取全市场代码-名称对照表（akshare），缓存到本地 parquet 并在进程内
常驻；之后直接查表。名称极少变动，无需按天刷新。网络不可用时安全降级为空串，
不影响回测流程。
"""

import pandas as pd

from .. import config
from .instruments import is_fund

_CACHE = config.DATA_DIR / "symbol_names.parquet"
_TABLE: dict[str, str] | None = None

_FUND_CACHE = config.DATA_DIR / "fund_names.parquet"
_FUND_TABLE: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _TABLE
    if _TABLE is not None:
        return _TABLE

    config.DATA_DIR.mkdir(exist_ok=True)
    if _CACHE.exists():
        df = pd.read_parquet(_CACHE)
    else:
        try:
            import akshare as ak

            df = ak.stock_info_a_code_name()  # 列：code / name
            df.to_parquet(_CACHE)
        except Exception:
            return {}  # 失败不缓存，下次有网时再试

    _TABLE = dict(zip(df["code"].astype(str), df["name"]))
    return _TABLE


def _load_funds() -> dict[str, str]:
    """场内基金/ETF 代码→名称表（新浪，去掉 sh/sz 前缀后按 6 位代码键）。"""
    global _FUND_TABLE
    if _FUND_TABLE is not None:
        return _FUND_TABLE

    config.DATA_DIR.mkdir(exist_ok=True)
    if _FUND_CACHE.exists():
        df = pd.read_parquet(_FUND_CACHE)
    else:
        try:
            import akshare as ak

            raw = ak.fund_etf_category_sina(symbol="ETF基金")  # 列含 代码/名称
            df = pd.DataFrame(
                {
                    "code": raw["代码"].astype(str).str[-6:],
                    "name": raw["名称"].astype(str),
                }
            )
            df.to_parquet(_FUND_CACHE)
        except Exception:
            return {}

    _FUND_TABLE = dict(zip(df["code"].astype(str), df["name"]))
    return _FUND_TABLE


def get_name(symbol: str) -> str:
    """返回标的名称（个股或基金/ETF），查不到（或无网）则返回空串。"""
    if is_fund(symbol):
        return _load_funds().get(symbol, "")
    return _load().get(symbol, "")


def list_symbols(
    kind: str = "stock", query: str = "", page: int = 1, page_size: int = 20
) -> dict:
    """分页列出全部个股或基金/ETF（code + name），支持按代码/名称模糊搜索。

    返回 {total, page, page_size, items:[{symbol, name}]}。数据来自本地缓存表
    （首次会拉取并缓存），不可用时返回空列表，不报错。
    """
    table = _load_funds() if kind == "fund" else _load()
    items = [{"symbol": c, "name": n} for c, n in table.items()]
    items.sort(key=lambda it: it["symbol"])

    q = query.strip().lower()
    if q:
        items = [
            it for it in items
            if q in it["symbol"].lower() or q in str(it["name"]).lower()
        ]

    total = len(items)
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start : start + page_size],
    }
