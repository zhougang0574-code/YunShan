"""A 股交易日历：用于日期校验与缺口检测。

数据来自 akshare ``tool_trade_date_hist_sina``，首次拉取后缓存到本地
parquet。若网络不可用，退化为"工作日(周一至周五)"的近似日历，保证上层
逻辑不会因日历缺失而中断。
"""

import functools

import pandas as pd

from .. import config

_CACHE_PATH = config.DATA_DIR / "trade_calendar.parquet"


@functools.lru_cache(maxsize=1)
def _trade_dates() -> pd.DatetimeIndex:
    config.DATA_DIR.mkdir(exist_ok=True)
    if _CACHE_PATH.exists():
        return pd.DatetimeIndex(pd.read_parquet(_CACHE_PATH)["date"])
    try:
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        dates = pd.to_datetime(df["trade_date"])
        pd.DataFrame({"date": dates}).to_parquet(_CACHE_PATH)
        return pd.DatetimeIndex(dates)
    except Exception:
        # 退化：1990 至今的工作日近似
        return pd.bdate_range("1990-12-19", pd.Timestamp.today())


def is_trading_day(date) -> bool:
    return pd.Timestamp(date).normalize() in _trade_dates()


def trading_days(start, end) -> pd.DatetimeIndex:
    """返回 [start, end] 内的交易日。"""
    days = _trade_dates()
    mask = (days >= pd.Timestamp(start)) & (days <= pd.Timestamp(end))
    return days[mask]


def previous_trading_day(date) -> pd.Timestamp:
    days = _trade_dates()
    prior = days[days <= pd.Timestamp(date).normalize()]
    return prior[-1] if len(prior) else pd.Timestamp(date).normalize()


def missing_trading_days(index: pd.DatetimeIndex, start, end) -> pd.DatetimeIndex:
    """检测已有数据 index 在 [start, end] 内缺失了哪些交易日。"""
    expected = trading_days(start, end)
    return expected.difference(index.normalize())
