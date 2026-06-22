"""回测 / 寻优 / 选股 的实验记录（轻量本地落地）。

每次运行把入参（策略、参数、标的、日期范围等）与关键结果指标存到本地 SQLite
（``data/experiments.db``），便于事后对比"这次参数和上次比是变好还是变差"。不引入
MLflow 等重型工具。``record`` 做成**绝不抛错**——记录失败不应影响主回测/选股流程。
"""

import datetime
import json
import sqlite3

from . import config

_DB_PATH = config.DATA_DIR / "experiments.db"


def _connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            symbol TEXT,
            strategy TEXT,
            params TEXT,
            summary TEXT
        )
        """
    )
    return conn


def record(
    kind: str,
    params: dict,
    summary: dict,
    symbol: str | None = None,
    strategy: str | None = None,
) -> int | None:
    """落地一条实验记录，返回自增 id；任何异常都吞掉并返回 None（不影响主流程）。"""
    try:
        conn = _connect()
        with conn:
            cur = conn.execute(
                "INSERT INTO experiments (ts, kind, symbol, strategy, params, summary)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.datetime.now().isoformat(timespec="seconds"),
                    kind,
                    symbol,
                    strategy,
                    json.dumps(params, ensure_ascii=False, default=str),
                    json.dumps(summary, ensure_ascii=False, default=str),
                ),
            )
        conn.close()
        return cur.lastrowid
    except Exception:
        return None


def list_experiments(
    kind: str | None = None,
    symbol: str | None = None,
    strategy: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """按时间倒序返回实验记录，可按 kind/symbol/strategy 过滤。"""
    try:
        conn = _connect()
    except Exception:
        return []
    clauses, args = [], []
    for col, val in (("kind", kind), ("symbol", symbol), ("strategy", strategy)):
        if val:
            clauses.append(f"{col} = ?")
            args.append(val)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT id, ts, kind, symbol, strategy, params, summary FROM experiments"
        f" {where} ORDER BY id DESC LIMIT ?",
        (*args, limit),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "ts": r[1],
                "kind": r[2],
                "symbol": r[3],
                "strategy": r[4],
                "params": json.loads(r[5]) if r[5] else {},
                "summary": json.loads(r[6]) if r[6] else {},
            }
        )
    return out
