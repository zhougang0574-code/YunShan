"""实验记录接口：回测/寻优/选股的历史运行，按时间倒序，可按 kind/标的/策略筛选。"""

from fastapi import APIRouter, Query

from quant.experiments import list_experiments

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
def get_experiments(
    kind: str | None = Query(None, examples=["backtest"]),
    symbol: str | None = None,
    strategy: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return list_experiments(kind=kind, symbol=symbol, strategy=strategy, limit=limit)
