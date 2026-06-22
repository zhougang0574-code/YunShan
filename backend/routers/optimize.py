"""参数寻优接口：网格寻优 或 走动检验，网格模式附带稳健性检验。"""

from fastapi import APIRouter, HTTPException

from quant import get_daily, optimize as opt, robustness
from quant.engine import run_backtest
from quant.experiments import record as record_experiment
from quant.strategies import get_strategy

from .. import serialize
from ..schemas import OptimizeRequest, OptimizeResponse

router = APIRouter(prefix="/optimize", tags=["optimize"])


def _clean(records: list[dict]) -> list[dict]:
    return serialize.clean_records(records)


def _best_params(best_row, param_grid: dict) -> dict:
    """从结果行恢复最优参数的原始类型（pandas 会把 int 参数上转成 float）。"""
    return {
        k: next((c for c in param_grid[k] if c == best_row[k]), best_row[k])
        for k in param_grid
    }


def _robustness(price, strategy_cls, df, param_grid: dict) -> dict | None:
    """对网格寻优的最优参数做 Deflated Sharpe + 蒙特卡洛择时置换检验。"""
    if df.empty or "sharpe_ratio" not in df.columns:
        return None
    try:
        best_params = _best_params(df.iloc[0], param_grid)
        signal = strategy_cls(**best_params).generate_signal(price)
        result = run_backtest(price, signal)
        dsr = robustness.deflated_sharpe_ratio(
            result["daily_return"], df["sharpe_ratio"].tolist()
        )
        mkt = price["close"].pct_change().fillna(0.0)
        mc = robustness.monte_carlo_signal_pvalue(mkt, result["position"], n_iter=500)
        cleaned = {k: serialize.clean_value(v) for k, v in dsr.items()}
        cleaned["monte_carlo"] = {k: serialize.clean_value(v) for k, v in mc.items()}
        cleaned["best_params"] = best_params
        return cleaned
    except Exception:
        return None


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

    param_grid = req.param_grid or strategy_cls.param_space()
    robustness_info = None
    if req.mode == "grid":
        df = opt.grid_search(price, strategy_cls, param_grid, req.metric)
        robustness_info = _robustness(price, strategy_cls, df, param_grid)
    else:
        df = opt.walk_forward(
            price, strategy_cls, param_grid, req.n_splits, req.metric
        )

    record_experiment(
        kind=f"optimize_{req.mode}",
        symbol=req.symbol,
        strategy=req.strategy,
        params={"metric": req.metric, "param_grid": param_grid, "n_splits": req.n_splits},
        summary={
            "trials": len(df),
            "deflated_sharpe_ratio": (robustness_info or {}).get("deflated_sharpe_ratio"),
        },
    )

    return OptimizeResponse(
        symbol=req.symbol,
        strategy=req.strategy,
        metric=req.metric,
        mode=req.mode,
        results=_clean(df.to_dict(orient="records")),
        robustness=robustness_info,
    )
