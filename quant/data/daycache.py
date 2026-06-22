"""通用「按天失效」DataFrame 缓存。

universe / fundamentals / altdata 这类数据更新频率低（日级或更慢），但又不像
日线行情那样有专门的范围感知逻辑。这里提供一个轻量缓存：按 ``key`` 存一个
parquet + ``.meta.json``（记录拉取日期），只信任「当天拉取的」缓存，隔天自动失效
重拉。与 ``storage.py`` 的行情缓存共用同一套"按天失效"理念，但不涉及日期区间。

``key`` 会被规范化为安全文件名（替换路径分隔符等），调用方可用 ``"universe_all"``、
``"fundamentals_000001"`` 这类带前缀的键避免不同数据互相覆盖。
"""

import datetime
import json
import re

import pandas as pd

from .. import config

_SAFE = re.compile(r"[^0-9A-Za-z_.-]+")


def _paths(key: str):
    config.DATA_DIR.mkdir(exist_ok=True)
    stem = _SAFE.sub("_", key)
    return (
        config.DATA_DIR / f"{stem}.parquet",
        config.DATA_DIR / f"{stem}.meta.json",
    )


def load(key: str, max_age_days: int = 0) -> pd.DataFrame | None:
    """读取缓存；不存在或已过期（拉取日期早于今天 - max_age_days）返回 None。

    ``max_age_days=0`` 表示只信任当天拉取的缓存（与行情缓存一致）；传更大的值可
    容忍更久（如基本面季度更新，可用 max_age_days=30）。
    """
    data_path, meta_path = _paths(key)
    if not data_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        fetched = datetime.date.fromisoformat(meta["fetched"])
    except (ValueError, OSError, KeyError):
        return None
    if fetched < datetime.date.today() - datetime.timedelta(days=max_age_days):
        return None
    return pd.read_parquet(data_path)


def save(key: str, df: pd.DataFrame, fetched: datetime.date | None = None) -> None:
    data_path, meta_path = _paths(key)
    df.to_parquet(data_path)
    meta_path.write_text(
        json.dumps({"fetched": (fetched or datetime.date.today()).isoformat()})
    )
