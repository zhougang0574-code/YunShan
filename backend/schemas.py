"""API 请求/响应模型（Pydantic）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from quant import config


class StrategyInfo(BaseModel):
    name: str
    param_space: dict[str, list[Any]]


class DataInfo(BaseModel):
    symbol: str
    name: str = ""
    adjust: str
    rows: int
    start: str | None = None
    end: str | None = None


class BacktestRequest(BaseModel):
    symbol: str = Field(..., examples=["000001"])
    start: str = Field(..., examples=["2022-01-01"])
    end: str = Field(..., examples=["2023-12-31"])
    strategy: str = Field(..., examples=["ma_cross"])
    params: dict[str, Any] = Field(default_factory=dict)
    adjust: str = config.DEFAULT_ADJUST
    engine: Literal["vectorized", "event"] = "vectorized"
    stop_loss: float | None = None
    take_profit: float | None = None


class BacktestSeries(BaseModel):
    """逐日序列，按列存放便于前端直接画图。"""

    dates: list[str]
    close: list[float]
    equity: list[float]
    benchmark_equity: list[float]
    position: list[float]


class BacktestResponse(BaseModel):
    symbol: str
    name: str = ""
    strategy: str
    params: dict[str, Any]
    stats: dict[str, float]
    series: BacktestSeries


class OptimizeRequest(BaseModel):
    symbol: str
    start: str
    end: str
    strategy: str
    adjust: str = config.DEFAULT_ADJUST
    metric: str = "sharpe_ratio"
    mode: Literal["grid", "walk_forward"] = "grid"
    n_splits: int = 4
    param_grid: dict[str, list[Any]] | None = None


class OptimizeResponse(BaseModel):
    symbol: str
    strategy: str
    metric: str
    mode: str
    results: list[dict[str, Any]]
    robustness: dict[str, Any] | None = None


# ---- 股票池 / 截面选股 ----


class FactorSpec(BaseModel):
    key: str
    weight: float = 1.0


class ScreeningRequest(BaseModel):
    universe_key: str = Field("index:000300", examples=["index:000300"])
    factors: list[FactorSpec] = Field(..., min_length=1)
    top_n: int = 50
    max_symbols: int = 300
    lookback_days: int = 180


class TaskSubmitResponse(BaseModel):
    task_id: str


# ---- 登录 / 用户 ----


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, examples=["alice"])
    password: str = Field(..., min_length=4, max_length=128)


class AuthResponse(BaseModel):
    token: str
    username: str


class MeResponse(BaseModel):
    username: str


# ---- 收藏 ----


class AddFavoriteRequest(BaseModel):
    symbol: str = Field(..., examples=["000001"])


class FavoriteItem(BaseModel):
    symbol: str
    name: str = ""
    created_at: str


class ScreeningStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    error: str | None = None
    results: list[dict[str, Any]] | None = None
