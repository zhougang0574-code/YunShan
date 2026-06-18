"""参数寻优接口：网格寻优 或 走动检验。"""

import numpy as np
from fastapi import APIRouter, HTTPException

from quant import get_daily, optimize as opt
from quant.strategies import get_strategy

from ..schemas import OptimizeRequest, OptimizeResponse

router = APIRouter(prefix="/optimize", tags=["optimize"])


def _clean(records: list[dict]) -> list[dict]:
    """把 numpy 标量与 NaN 转成 JSON 可序列化的原生类型。"""
    cleaned = []
    for row in records:
        item = {}
        for k, v in row.items():
            if isinstance(v, (np.integer,)):
                item[k] = int(v)
            elif isinstance(v, (np.floating, float)):
                item[k] = None if np.isnan(v) else float(v)
            else:
                item[k] = v
        cleaned.append(item)
    return cleaned


@router.post("", response_model=OptimizeResponse)
def run(req: OptimizeRequest) -> OptimizeResponse:
    try:
        price = get_daily(req.symbol, req.start, req.end, adjust=req.adjust)
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    if price.empty:
        raise HTTPException(status_code=404, detail="未获取到数据")

    try:
        strategy_cls = get_strategy(req.strategy)
    except KeyError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    if req.mode == "grid":
        df = opt.grid_search(price, strategy_cls, req.param_grid, req.metric)
    else:
        df = opt.walk_forward(
            price, strategy_cls, req.param_grid, req.n_splits, req.metric
        )

    return OptimizeResponse(
        symbol=req.symbol,
        strategy=req.strategy,
        metric=req.metric,
        mode=req.mode,
        results=_clean(df.to_dict(orient="records")),
    )
