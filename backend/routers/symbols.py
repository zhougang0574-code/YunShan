"""个股详情：基本面快照、另类数据标签、当前"注意点"信号。"""

from fastapi import APIRouter

from quant import signals
from quant.data import altdata, fundamentals, get_name

from .. import serialize

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("/{symbol}/signals")
def get_signals(symbol: str) -> dict:
    """当前注意点标签（技术 + 基本面 + 另类数据），供个股详情页标签卡。"""
    return signals.for_symbol(symbol)


@router.get("/{symbol}/fundamentals")
def get_fundamentals(symbol: str) -> dict:
    """单只股票基本面指标（估值/ROE/增速），NaN 统一转 null。"""
    fund = fundamentals.get_fundamentals(symbol)
    return {k: serialize.clean_value(v) for k, v in fund.items()}


@router.get("/{symbol}/altdata")
def get_altdata(symbol: str) -> dict:
    """另类数据：主力资金流向、北向资金持股（展示用）。"""
    return {
        "name": get_name(symbol),
        "fund_flow": {k: serialize.clean_value(v) for k, v in altdata.fund_flow(symbol).items()},
        "north_hold": {k: serialize.clean_value(v) for k, v in altdata.north_hold(symbol).items()},
    }
