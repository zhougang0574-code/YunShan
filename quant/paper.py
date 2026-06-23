"""模拟交易（纸上交易）：虚拟账户 + 持仓 + 成交记录 + 每日净值。

按用户隔离，存本地 SQLite（``data/paper.db``）。成交按传入的最新价撮合，复用
``costs.CostModel`` 计真实 A 股费用（佣金/印花税/过户费）；买入要求 100 股整数倍。
本模块只管存储与撮合记账，**不取行情**——实时价由上层（路由）取好后传入。
"""

import datetime
import sqlite3

from . import config
from .costs import CostModel
from .data.instruments import is_fund

_DB_PATH = config.DATA_DIR / "paper.db"

DEFAULT_INITIAL = 1_000_000.0  # 默认初始资金（元）
_LOT = 100                     # A 股一手 = 100 股

# 个股按标准费率；场内基金/ETF 不收印花税
_STOCK_COST = CostModel()
_FUND_COST = CostModel(stamp_tax_rate=0.0)


class TradeError(Exception):
    """下单校验失败（现金不足 / 持仓不足 / 数量非法等）。"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.date.today().isoformat()


def _fee(symbol: str, notional: float, side: str) -> float:
    model = _FUND_COST if is_fund(symbol) else _STOCK_COST
    return model.trade_cost(notional, side)


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            user_id INTEGER PRIMARY KEY,
            cash REAL NOT NULL,
            initial REAL NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            shares INTEGER NOT NULL,
            cost REAL NOT NULL,
            UNIQUE(user_id, symbol)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            shares INTEGER NOT NULL,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            realized REAL NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS equity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            total REAL NOT NULL,
            UNIQUE(user_id, date)
        )"""
    )
    return conn


# ---- 账户 ----


def get_or_create_account(user_id: int, initial: float = DEFAULT_INITIAL) -> dict:
    conn = _connect()
    with conn:
        row = conn.execute(
            "SELECT cash, initial FROM accounts WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO accounts (user_id, cash, initial, created_at) VALUES (?, ?, ?, ?)",
                (user_id, initial, initial, _now()),
            )
            row = (initial, initial)
    conn.close()
    return {"cash": row[0], "initial": row[1]}


def reset_account(user_id: int, initial: float = DEFAULT_INITIAL) -> dict:
    conn = _connect()
    with conn:
        for t in ("positions", "trades", "equity"):
            conn.execute(f"DELETE FROM {t} WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO accounts (user_id, cash, initial, created_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id) DO UPDATE SET cash = excluded.cash, initial = excluded.initial,"
            " created_at = excluded.created_at",
            (user_id, initial, initial, _now()),
        )
    conn.close()
    return {"cash": initial, "initial": initial}


# ---- 撮合 ----


def buy(user_id: int, symbol: str, name: str, price: float, shares: int) -> dict:
    """按 price 买入 shares 股（需 100 整数倍）。返回本笔成交摘要。"""
    if shares <= 0 or shares % _LOT != 0:
        raise TradeError(f"买入数量需为 {_LOT} 股的整数倍")
    if price <= 0:
        raise TradeError("价格无效")
    get_or_create_account(user_id)

    notional = price * shares
    fee = _fee(symbol, notional, "buy")
    total = notional + fee

    conn = _connect()
    try:
        with conn:
            cash = conn.execute(
                "SELECT cash FROM accounts WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if total > cash + 1e-6:
                raise TradeError(f"现金不足：需 {total:.2f}，可用 {cash:.2f}")
            conn.execute(
                "UPDATE accounts SET cash = ? WHERE user_id = ?", (cash - total, user_id)
            )
            pos = conn.execute(
                "SELECT shares, cost FROM positions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
            ).fetchone()
            if pos:
                conn.execute(
                    "UPDATE positions SET shares = ?, cost = ? WHERE user_id = ? AND symbol = ?",
                    (pos[0] + shares, pos[1] + total, user_id, symbol),
                )
            else:
                conn.execute(
                    "INSERT INTO positions (user_id, symbol, shares, cost) VALUES (?, ?, ?, ?)",
                    (user_id, symbol, shares, total),
                )
            conn.execute(
                "INSERT INTO trades (user_id, ts, symbol, name, side, price, shares, amount, fee, realized)"
                " VALUES (?, ?, ?, ?, 'buy', ?, ?, ?, ?, 0)",
                (user_id, _now(), symbol, name, price, shares, notional, fee),
            )
    finally:
        conn.close()
    return {"side": "buy", "symbol": symbol, "price": price, "shares": shares, "fee": fee}


def sell(user_id: int, symbol: str, name: str, price: float, shares: int) -> dict:
    """按 price 卖出 shares 股（不超过持仓）。返回本笔成交摘要（含已实现盈亏）。"""
    if shares <= 0:
        raise TradeError("卖出数量无效")
    if price <= 0:
        raise TradeError("价格无效")
    get_or_create_account(user_id)

    conn = _connect()
    try:
        with conn:
            pos = conn.execute(
                "SELECT shares, cost FROM positions WHERE user_id = ? AND symbol = ?",
                (user_id, symbol),
            ).fetchone()
            if not pos or pos[0] < shares:
                raise TradeError("持仓不足")
            held, cost = pos
            avg = cost / held
            notional = price * shares
            fee = _fee(symbol, notional, "sell")
            proceeds = notional - fee
            cost_of_sold = avg * shares
            realized = proceeds - cost_of_sold

            cash = conn.execute(
                "SELECT cash FROM accounts WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE accounts SET cash = ? WHERE user_id = ?", (cash + proceeds, user_id)
            )
            remaining = held - shares
            if remaining == 0:
                conn.execute(
                    "DELETE FROM positions WHERE user_id = ? AND symbol = ?", (user_id, symbol)
                )
            else:
                conn.execute(
                    "UPDATE positions SET shares = ?, cost = ? WHERE user_id = ? AND symbol = ?",
                    (remaining, cost - cost_of_sold, user_id, symbol),
                )
            conn.execute(
                "INSERT INTO trades (user_id, ts, symbol, name, side, price, shares, amount, fee, realized)"
                " VALUES (?, ?, ?, ?, 'sell', ?, ?, ?, ?, ?)",
                (user_id, _now(), symbol, name, price, shares, notional, fee, realized),
            )
    finally:
        conn.close()
    return {"side": "sell", "symbol": symbol, "price": price, "shares": shares,
            "fee": fee, "realized": realized}


# ---- 查询 ----


def list_positions(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT symbol, shares, cost FROM positions WHERE user_id = ? ORDER BY symbol",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for symbol, shares, cost in rows:
        out.append(
            {
                "symbol": symbol,
                "shares": shares,
                "cost": cost,
                "avg_cost": cost / shares if shares else 0.0,
            }
        )
    return out


def list_trades(user_id: int, limit: int = 200) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT ts, symbol, name, side, price, shares, amount, fee, realized"
            " FROM trades WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    keys = ["ts", "symbol", "name", "side", "price", "shares", "amount", "fee", "realized"]
    return [dict(zip(keys, r)) for r in rows]


def record_equity(user_id: int, total: float, date: str | None = None) -> None:
    """记录某日账户总资产（同日覆盖），用于净值曲线。"""
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO equity (user_id, date, total) VALUES (?, ?, ?)"
            " ON CONFLICT(user_id, date) DO UPDATE SET total = excluded.total",
            (user_id, date or _today(), total),
        )
    conn.close()


def list_equity(user_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT date, total FROM equity WHERE user_id = ? ORDER BY date", (user_id,)
        ).fetchall()
    finally:
        conn.close()
    return [{"date": d, "total": t} for d, t in rows]
