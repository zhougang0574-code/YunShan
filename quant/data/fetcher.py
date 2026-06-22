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
from .instruments import is_fund, market

# 东财中文列名 → 统一英文列名
COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}


def _normalize(raw: pd.DataFrame, column_map: dict) -> pd.DataFrame:
    """把数据源返回的原始表规范化为以 date 为索引、列为 storage.COLUMNS 的表。"""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=storage.COLUMNS)
    df = raw.rename(columns=column_map)[["date", *storage.COLUMNS]].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def _fetch_eastmoney(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    raw = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start.replace("-", ""),
        end_date=end.replace("-", ""),
        adjust=adjust,
    )
    return _normalize(raw, COLUMN_MAP)


def _fetch_sina(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    # 新浪返回的列已是英文（date/open/high/low/close/volume/amount），无需改名。
    # 注意：成交量(volume)单位与东财口径可能略有差异，但回测信号只用价格，影响可忽略。
    raw = ak.stock_zh_a_daily(
        symbol=f"{market(symbol)}{symbol}",
        start_date=start.replace("-", ""),
        end_date=end.replace("-", ""),
        adjust=adjust,
    )
    return _normalize(raw, {})


def _fetch_fund_eastmoney(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    raw = ak.fund_etf_hist_em(
        symbol=symbol,
        period="daily",
        start_date=start.replace("-", ""),
        end_date=end.replace("-", ""),
        adjust=adjust,
    )
    return _normalize(raw, COLUMN_MAP)


def _fetch_fund_sina(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    # 新浪 ETF 接口返回全历史、英文列、不带复权，这里按区间裁剪。
    raw = ak.fund_etf_hist_sina(symbol=f"{market(symbol)}{symbol}")
    df = _normalize(raw, {})
    return df.loc[start:end] if not df.empty else df


# 数据源主备：东财为主、新浪为备（个股与基金各一组对应接口）。
# 部分网络（Clash TUN / 运营商对东财的干扰）会稳定掐断东财连接，而新浪可用，
# 多源回退让回测在这些环境下也能正常拉到数据。
_STOCK_SOURCES = (
    ("eastmoney", _fetch_eastmoney),
    ("sina", _fetch_sina),
)
_FUND_SOURCES = (
    ("fund_eastmoney", _fetch_fund_eastmoney),
    ("fund_sina", _fetch_fund_sina),
)


# 上次成功的数据源下标（按 "stock"/"fund" 分别记）。某些网络下主源（东财）会稳定
# 不可用，记住可用源后下次优先尝试它，避免每次都先在不可用的源上重试、空等数秒。
_preferred_source: dict[str, int] = {}


def _fetch_raw(symbol: str, start: str, end: str, adjust: str) -> pd.DataFrame:
    """从数据源拉取并规范化为以 date 为索引的 DataFrame（多源 + 重试）。

    自动按代码识别个股 / 基金(ETF)，分别走对应的数据源。
    """
    if is_fund(symbol):
        kind, sources = "fund", _FUND_SOURCES
    else:
        kind, sources = "stock", _STOCK_SOURCES

    pref = _preferred_source.get(kind, 0)
    order = [pref] + [i for i in range(len(sources)) if i != pref]
    last_err: Exception | None = None
    for i in order:
        _, fetch = sources[i]
        for attempt in range(config.FETCH_MAX_RETRIES):
            try:
                df = fetch(symbol, start, end, adjust)
                _preferred_source[kind] = i  # 记住可用源，下次优先用
                return df
            except Exception as err:  # 偶发网络/限流错误，重试或切换数据源
                last_err = err
                time.sleep(config.FETCH_RETRY_BACKOFF * (attempt + 1))
    names = "/".join(name for name, _ in sources)
    raise RuntimeError(
        f"行情拉取 {symbol} 失败（已尝试 {names}；"
        f"最后错误 {type(last_err).__name__}: {last_err}）"
    ) from last_err


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
