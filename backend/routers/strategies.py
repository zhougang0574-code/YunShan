"""策略发现：列出已注册策略及其可寻优参数空间。"""

from fastapi import APIRouter

from quant.strategies import list_strategies

from ..schemas import StrategyInfo

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyInfo])
def get_strategies() -> list[StrategyInfo]:
    return [
        StrategyInfo(name=name, param_space=space)
        for name, space in list_strategies().items()
    ]
