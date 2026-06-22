"""收藏：按登录用户隔离的自选股。

所有接口都要求登录（带 token），只操作/返回当前用户自己的收藏。
"""

from fastapi import APIRouter

from quant import users
from quant.data.symbols import get_name

from ..deps import CurrentUser
from ..schemas import AddFavoriteRequest, FavoriteItem

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteItem])
def get_favorites(user: dict = CurrentUser) -> list[FavoriteItem]:
    return [FavoriteItem(**f) for f in users.list_favorites(user["id"])]


@router.post("", response_model=list[FavoriteItem])
def add_favorite(req: AddFavoriteRequest, user: dict = CurrentUser) -> list[FavoriteItem]:
    symbol = req.symbol.strip()
    name = ""
    try:
        name = get_name(symbol)  # 无网时安全降级为空串
    except Exception:
        pass
    users.add_favorite(user["id"], symbol, name)
    return [FavoriteItem(**f) for f in users.list_favorites(user["id"])]


@router.delete("/{symbol}", response_model=list[FavoriteItem])
def remove_favorite(symbol: str, user: dict = CurrentUser) -> list[FavoriteItem]:
    users.remove_favorite(user["id"], symbol)
    return [FavoriteItem(**f) for f in users.list_favorites(user["id"])]
