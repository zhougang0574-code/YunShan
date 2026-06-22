"""标的库：分页浏览全部个股 / 基金(ETF)，支持按代码或名称搜索。"""

from typing import Literal

from fastapi import APIRouter, Query

from quant.data.symbols import list_symbols

from ..schemas import CatalogPage

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogPage)
def get_catalog(
    kind: Literal["stock", "fund"] = "stock",
    query: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> CatalogPage:
    return CatalogPage(**list_symbols(kind=kind, query=query, page=page, page_size=page_size))
