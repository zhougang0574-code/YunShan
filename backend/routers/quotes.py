"""近实时报价接口（前端分钟级轮询）。"""

from fastapi import APIRouter

from quant.data import get_name, quotes

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/{symbol}")
def get_quote(symbol: str) -> dict:
    """最新报价（最新价/涨跌幅/开高低/昨收/量额）。源失败时各字段为 null。"""
    quote = quotes.get_quote(symbol)
    quote["name"] = get_name(symbol)
    return quote


@router.get("/{symbol}/intraday")
def get_intraday(symbol: str) -> list[dict]:
    """当日分时（时间/价格/成交量）。"""
    return quotes.get_intraday(symbol).to_dict(orient="records")
