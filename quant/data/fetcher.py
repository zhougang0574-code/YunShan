"""行情拉取：封装 akshare，叠加范围感知缓存与增量更新。

缓存正确性要点（修复旧实现的两个 bug）：
1. 缓存按 ``symbol + adjust`` 维度，前/后复权不再互相覆盖；
2. 缓存记录已请求区间，命中时若请求区间超出已覆盖范围，只补拉缺失的
   头部 / 尾部段落再合并，而不是直接返回缓存子集导致缺口永不补齐。
"""

import datetime
import time

import akshare as ak
import pandas as pd

from .. import config
from . import storage

COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}


def _fetch_raw(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    """直接从 akshare 拉取并规范化为以 date 为索引的 DataFrame（带重试）。"""
    last_err: Exception | None = None
    for attempt in range(config.FETCH_MAX_RETRIES):
        try:
            raw = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust=adjust,
            )
            break
        except Exception as err:  # akshare 偶发网络/限流错误
            last_err = err
            time.sleep(config.FETCH_RETRY_BACKOFF * (attempt + 1))
    else:
        raise RuntimeError(
            f"akshare 拉取 {symbol} 失败（{type(last_err).__name__}: {last_err}）"
        ) from last_err

    if raw is None or raw.empty:
        return pd.DataFrame(columns=storage.COLUMNS)

    df = raw.rename(columns=COLUMN_MAP)[["date", *storage.COLUMNS]].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _merge(*frames: pd.DataFrame) -> pd.DataFrame:
    """合并多段行情，按日期去重保序。"""
    combined = pd.concat([f for f in frames if not f.empty])
    if combined.empty:
        return combined
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined


def get_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = config.DEFAULT_ADJUST,
    use_cache: bool = True,
) -> pd.DataFrame:
    """获取 A 股日线（开/高/低/收/量/额），优先用缓存并按需增量补拉。

    symbol: 股票代码，如 "000001"
    start_date/end_date: "YYYY-MM-DD"
    adjust: "qfq"(前复权)/"hfq"(后复权)/""(不复权)
    """
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if not use_cache:
        df = _fetch_raw(symbol, start_date, end_date, adjust)
        if not df.empty:
            storage.save_cache(symbol, adjust, df, (start, end))
        return df.loc[start:end]

    cached, coverage, fetched = storage.load_cached(symbol, adjust)

    # 缓存只信任「当天拉取的」：无缓存、或缓存是隔天/更早拉的，都重新拉最新数据。
    # 这样当天首次查询拿到最新行情与前复权价，当天后续查询才走缓存。
    stale = fetched is None or fetched < datetime.date.today()
    if cached is None or coverage is None or stale:
        df = _fetch_raw(symbol, start_date, end_date, adjust)
        if not df.empty:
            storage.save_cache(symbol, adjust, df, (start, end))
        return df.loc[start:end]

    cov_start, cov_end = coverage
    segments = [cached]
    one_day = pd.Timedelta(days=1)

    if start < cov_start:  # 缺头部
        head = _fetch_raw(
            symbol, start_date, str((cov_start - one_day).date()), adjust
        )
        segments.append(head)
    if end > cov_end:  # 缺尾部
        tail = _fetch_raw(
            symbol, str((cov_end + one_day).date()), end_date, adjust
        )
        segments.append(tail)

    if len(segments) > 1:  # 有补拉，合并并更新覆盖区间
        merged = _merge(*segments)
        new_coverage = (min(start, cov_start), max(end, cov_end))
        storage.save_cache(symbol, adjust, merged, new_coverage)
        return merged.loc[start:end]

    return cached.loc[start:end]
