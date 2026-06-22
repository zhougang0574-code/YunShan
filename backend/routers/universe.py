"""股票池接口：列出可选池、取某池成分股。"""

from fastapi import APIRouter, HTTPException

from quant.data import universe

router = APIRouter(prefix="/universe", tags=["universe"])


@router.get("")
def list_universes() -> dict:
    """列出可选股票池：全市场 / 宽基指数 / 行业板块。"""
    return universe.list_universes()


@router.get("/constituents")
def get_constituents(key: str) -> list[dict]:
    """取某个池子的成分股（含 code / name）。key：all / index:<代码> / industry:<板块名>。"""
    try:
        df = universe.get_constituents(key)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return df.to_dict(orient="records")
