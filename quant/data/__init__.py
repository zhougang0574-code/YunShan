"""数据层：行情拉取、本地缓存（范围感知 + 增量更新）、交易日历、代码名称查询，
以及股票池 / 基本面 / 近实时报价 / 另类数据等截面与个股详情所需的数据适配。"""

from . import altdata, fundamentals, quotes, universe
from .fetcher import get_daily
from .symbols import get_name

__all__ = [
    "get_daily",
    "get_name",
    "universe",
    "fundamentals",
    "quotes",
    "altdata",
]
