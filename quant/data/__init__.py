"""数据层：行情拉取、本地缓存（范围感知 + 增量更新）、交易日历、代码名称查询。"""

from .fetcher import get_daily
from .symbols import get_name

__all__ = ["get_daily", "get_name"]
