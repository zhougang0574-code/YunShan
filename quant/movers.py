"""板块当月涨幅榜：选定行业板块，按成分股「当月至今涨幅」排名取龙头。

「当月至今涨幅」(month-to-date) 口径：以**上月最后一个交易日收盘价**为基准，到最新
收盘价的涨跌幅；若个股本月才上市（无上月收盘），退化为本月首个交易日收盘价为基准。
采用前复权价（``get_daily`` 默认），避免月内除权造成的虚假跳变。

逐股拉日线较慢（一个板块约 50~100 只），所以和 ``screening`` 一样走后台任务 + 进度回调，
并复用行情缓存。结果按涨幅降序输出 Top N，附带所属板块名，既能看「涨幅最高的几只」，
也能按 ``industry`` 列分辨各板块龙头。
"""

import datetime

import pandas as pd

from .data import get_daily, universe


def _month_start(today: datetime.date) -> datetime.date:
    return today.replace(day=1)


def _mtd_return(price: pd.DataFrame, month_first: pd.Timestamp) -> tuple[float, float, float]:
    """从日线算 (当月涨幅%, 基准价, 最新价)；数据不足时返回 NaN。"""
    if price is None or price.empty:
        return float("nan"), float("nan"), float("nan")
    close = price["close"].dropna()
    if close.empty:
        return float("nan"), float("nan"), float("nan")
    latest = float(close.iloc[-1])
    prior = close[close.index < month_first]
    # 优先用上月最后收盘价做基准；本月才上市则用本月首个收盘价。
    if not prior.empty:
        base = float(prior.iloc[-1])
    else:
        in_month = close[close.index >= month_first]
        base = float(in_month.iloc[0]) if not in_month.empty else float("nan")
    if not base:
        return float("nan"), base, latest
    return (latest / base - 1.0) * 100.0, base, latest


def month_leaders(
    industries: list[str],
    top_n: int = 30,
    max_symbols: int = 300,
    today: datetime.date | None = None,
    price_loader=None,
    progress=None,
) -> pd.DataFrame:
    """选定行业板块，按成分股当月至今涨幅降序排名取 Top N。

    industries: 行业板块名列表（取自 ``universe.list_industries()``）。
    max_symbols: 跨所有选定板块合计最多扫描的股票数（安全上限，防止全选时过慢）。
    返回列：rank/code/name/industry/month_pct/base_price/price，按 month_pct 降序。
    """
    if not industries:
        raise ValueError("至少需要选择一个板块")

    today = today or datetime.date.today()
    month_first = pd.Timestamp(_month_start(today))
    # 多拉两周，确保覆盖到上月最后一个交易日（含长假）。
    start = _month_start(today) - datetime.timedelta(days=20)
    loader = price_loader or get_daily

    # 汇总各板块成分股，按 code 去重（保留首个出现的板块归属）。
    rows: list[dict] = []
    seen: set[str] = set()
    for name in industries:
        members = universe.get_constituents(f"industry:{name}")
        for _, m in members.iterrows():
            code = str(m["code"])
            if code in seen:
                continue
            seen.add(code)
            rows.append({"code": code, "name": m.get("name", ""), "industry": name})
            if len(rows) >= max_symbols:
                break
        if len(rows) >= max_symbols:
            break

    total = len(rows)
    if total == 0:
        return pd.DataFrame(
            columns=["rank", "code", "name", "industry", "month_pct", "base_price", "price"]
        )

    records: list[dict] = []
    for i, r in enumerate(rows):
        try:
            price = loader(r["code"], str(start), str(today))
            pct, base, last = _mtd_return(price, month_first)
        except Exception:
            pct, base, last = float("nan"), float("nan"), float("nan")
        records.append({**r, "month_pct": pct, "base_price": base, "price": last})
        if progress:
            progress((i + 1) / total)

    df = pd.DataFrame(records)
    df = df[df["month_pct"].notna()]
    df = df.sort_values("month_pct", ascending=False).head(top_n).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df
