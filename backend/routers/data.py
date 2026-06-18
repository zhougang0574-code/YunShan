"""数据接口：拉取/更新某标的行情，并返回缓存概况。"""

from fastapi import APIRouter, HTTPException, Query

from quant import config, get_daily

from ..schemas import DataInfo

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/{symbol}", response_model=DataInfo)
def fetch_data(
    symbol: str,
    start: str = Query(..., examples=["2022-01-01"]),
    end: str = Query(..., examples=["2023-12-31"]),
    adjust: str = config.DEFAULT_ADJUST,
) -> DataInfo:
    """拉取（或命中缓存读取）日线数据，返回行数与覆盖区间。"""
    try:
        df = get_daily(symbol, start, end, adjust=adjust)
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    if df.empty:
        raise HTTPException(status_code=404, detail="未获取到数据，请检查代码或日期范围")

    return DataInfo(
        symbol=symbol,
        adjust=adjust,
        rows=len(df),
        start=str(df.index.min().date()),
        end=str(df.index.max().date()),
    )
