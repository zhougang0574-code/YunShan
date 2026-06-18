"""A 股「代码 → 名称」查询。

首次调用拉取全市场代码-名称对照表（akshare），缓存到本地 parquet 并在进程内
常驻；之后直接查表。名称极少变动，无需按天刷新。网络不可用时安全降级为空串，
不影响回测流程。
"""

import pandas as pd

from .. import config

_CACHE = config.DATA_DIR / "symbol_names.parquet"
_TABLE: dict[str, str] | None = None


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


def get_name(symbol: str) -> str:
    """返回股票名称，查不到（或无网）则返回空串。"""
    return _load().get(symbol, "")
