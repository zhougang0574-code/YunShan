"""本地缓存读写。

缓存按 ``symbol + adjust`` 维度分文件，避免不同复权方式互相覆盖。
每个标的额外维护一个 ``.meta.json``，记录：
- 已请求覆盖的日期区间 ``[start, end]``（fetcher 据此判断缺口、按需增量补拉）；
- ``fetched``：本次缓存的**拉取日期**。日线数据当天不变，但隔天后前复权价可能因
  分红送股被重算，且会有新交易日——所以只有"当天拉取的"缓存才被信任，隔天自动失效。
"""

import datetime
import json
import pathlib

import pandas as pd

from .. import config

COLUMNS = ["open", "close", "high", "low", "volume", "amount"]


def _normalize_adjust(adjust: str) -> str:
    return adjust if adjust else "none"


def _paths(symbol: str, adjust: str) -> tuple[pathlib.Path, pathlib.Path]:
    config.DATA_DIR.mkdir(exist_ok=True)
    stem = f"{symbol}_{_normalize_adjust(adjust)}"
    return (
        config.DATA_DIR / f"{stem}.parquet",
        config.DATA_DIR / f"{stem}.meta.json",
    )


def load_cached(
    symbol: str, adjust: str
) -> tuple[pd.DataFrame | None, tuple[pd.Timestamp, pd.Timestamp] | None, datetime.date | None]:
    """返回 (缓存DataFrame, 已覆盖区间, 拉取日期)；无缓存时三者均为 None。"""
    data_path, meta_path = _paths(symbol, adjust)
    if not data_path.exists() or not meta_path.exists():
        return None, None, None
    df = pd.read_parquet(data_path)
    meta = json.loads(meta_path.read_text())
    coverage = (pd.Timestamp(meta["start"]), pd.Timestamp(meta["end"]))
    fetched = (
        datetime.date.fromisoformat(meta["fetched"]) if meta.get("fetched") else None
    )
    return df, coverage, fetched


def purge_old_cache(days: int = 30) -> list[str]:
    """手动清理：删除拉取日期早于 ``days`` 天的行情缓存（含 .parquet 与 .meta.json）。

    仅清理带 meta 的行情缓存，不动交易日历/名称表等基础数据。**不会自动运行**，
    需要时手动调用以回收磁盘（日线缓存通常很小，一般无需清理）。返回被删的标的列表。
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    removed = []
    for meta_path in config.DATA_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_text())
            fetched = datetime.date.fromisoformat(meta.get("fetched", ""))
        except (ValueError, OSError):
            continue
        if fetched < cutoff:
            data_path = meta_path.with_suffix("").with_suffix(".parquet")
            data_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            removed.append(meta_path.stem.removesuffix(".meta"))
    return removed


def save_cache(
    symbol: str,
    adjust: str,
    df: pd.DataFrame,
    coverage: tuple[pd.Timestamp, pd.Timestamp],
    fetched: datetime.date | None = None,
) -> None:
    fetched = fetched or datetime.date.today()
    data_path, meta_path = _paths(symbol, adjust)
    df.to_parquet(data_path)
    meta_path.write_text(
        json.dumps(
            {
                "start": str(coverage[0].date()),
                "end": str(coverage[1].date()),
                "fetched": fetched.isoformat(),
            }
        )
    )
