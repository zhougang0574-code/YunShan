"""模拟交易（纸上交易）接口。

撮合记账在 ``quant.paper`` 里，本路由负责取实时价、补标的名称，并把持仓按最新价
折算市值/浮动盈亏，组装账户总览。所有接口都要求登录，按用户隔离。每次看账户时顺手
记一笔当日净值（同日覆盖），用于净值曲线。
"""

from fastapi import APIRouter, HTTPException

from quant import paper
from quant.data import quotes
from quant.data.symbols import get_name

from ..deps import CurrentUser
from ..schemas import OrderRequest, ResetRequest

router = APIRouter(prefix="/paper", tags=["paper"])


def _price(symbol: str) -> float:
    """取最新价；取不到则报 400（不能按未知价撮合/估值）。"""
    quote = quotes.get_quote(symbol)
    price = quote.get("price")
    if price is None or price <= 0:
        raise HTTPException(status_code=400, detail=f"取不到 {symbol} 的最新价，暂时无法交易")
    return float(price)


def _account_view(user_id: int, record: bool = True) -> dict:
    """组装账户总览：现金 + 持仓（按最新价折市值/浮盈）+ 总资产/收益。"""
    acct = paper.get_or_create_account(user_id)
    cash, initial = acct["cash"], acct["initial"]

    positions = []
    market_value = 0.0
    for pos in paper.list_positions(user_id):
        symbol = pos["symbol"]
        quote = quotes.get_quote(symbol)
        price = quote.get("price")
        shares = pos["shares"]
        avg_cost = pos["avg_cost"]
        if price is not None and price > 0:
            value = price * shares
            unrealized = value - pos["cost"]
        else:
            price = None
            value = pos["cost"]  # 取不到价时按成本占位，避免总资产跳变
            unrealized = 0.0
        market_value += value
        positions.append(
            {
                "symbol": symbol,
                "name": _safe_name(symbol),
                "shares": shares,
                "avg_cost": avg_cost,
                "price": price,
                "market_value": value,
                "cost": pos["cost"],
                "unrealized": unrealized,
                "unrealized_pct": (unrealized / pos["cost"] * 100) if pos["cost"] else 0.0,
            }
        )

    total = cash + market_value
    if record:
        paper.record_equity(user_id, total)
    return {
        "cash": cash,
        "initial": initial,
        "market_value": market_value,
        "total": total,
        "profit": total - initial,
        "profit_pct": (total - initial) / initial * 100 if initial else 0.0,
        "positions": positions,
    }


def _safe_name(symbol: str) -> str:
    try:
        return get_name(symbol)
    except Exception:
        return ""


@router.get("/account")
def get_account(user: dict = CurrentUser) -> dict:
    return _account_view(user["id"])


@router.post("/order")
def place_order(req: OrderRequest, user: dict = CurrentUser) -> dict:
    symbol = req.symbol.strip()
    price = _price(symbol)
    name = _safe_name(symbol)
    try:
        if req.side == "buy":
            fill = paper.buy(user["id"], symbol, name, price, req.shares)
        else:
            fill = paper.sell(user["id"], symbol, name, price, req.shares)
    except paper.TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"fill": fill, "account": _account_view(user["id"])}


@router.get("/trades")
def get_trades(user: dict = CurrentUser) -> list[dict]:
    return paper.list_trades(user["id"])


@router.get("/equity")
def get_equity(user: dict = CurrentUser) -> list[dict]:
    return paper.list_equity(user["id"])


@router.post("/reset")
def reset(req: ResetRequest, user: dict = CurrentUser) -> dict:
    initial = req.initial or paper.DEFAULT_INITIAL
    paper.reset_account(user["id"], initial)
    return _account_view(user["id"])
