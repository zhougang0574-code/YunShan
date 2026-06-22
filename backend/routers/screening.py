"""截面选股接口：提交筛选任务（后台跑）+ 轮询进度/结果。

截面打分可能遍历整个股票池并逐股拉价格，耗时较长，所以走后台任务：
- ``GET  /screening/factors``：列出可选因子（基本面快照因子 + 技术因子）。
- ``POST /screening``：提交筛选条件，立即返回 ``task_id``。
- ``GET  /screening/{task_id}``：轮询任务状态/进度，完成后取 Top N 结果。
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from quant import screening
from quant.experiments import record as record_experiment

from .. import serialize, tasks
from ..schemas import ScreeningRequest, ScreeningStatusResponse, TaskSubmitResponse

router = APIRouter(prefix="/screening", tags=["screening"])


@router.get("/factors")
def list_factors() -> dict:
    """可选因子目录：{key: {label, direction, kind}}。"""
    return screening.available_factors()


def _run(task_id: str, req: ScreeningRequest) -> None:
    try:
        df = screening.screen(
            factors=[f.model_dump() for f in req.factors],
            universe_key=req.universe_key,
            top_n=req.top_n,
            max_symbols=req.max_symbols,
            lookback_days=req.lookback_days,
            progress=lambda p: tasks.set_progress(task_id, p),
        )
        results = serialize.clean_records(df.to_dict(orient="records"))
        tasks.finish(task_id, results)
        record_experiment(
            kind="screening",
            params={
                "universe_key": req.universe_key,
                "factors": [f.model_dump() for f in req.factors],
                "top_n": req.top_n,
            },
            summary={"candidates": len(results)},
        )
    except Exception as err:  # 后台任务里任何失败都记录到任务状态，避免静默
        tasks.fail(task_id, f"{type(err).__name__}: {err}")


@router.post("", response_model=TaskSubmitResponse)
def submit(req: ScreeningRequest, background: BackgroundTasks) -> TaskSubmitResponse:
    bad = [f.key for f in req.factors if f.key not in screening.available_factors()]
    if bad:
        raise HTTPException(status_code=400, detail=f"未知因子：{bad}")
    task_id = tasks.create()
    background.add_task(_run, task_id, req)
    return TaskSubmitResponse(task_id=task_id)


@router.get("/{task_id}", response_model=ScreeningStatusResponse)
def status(task_id: str) -> ScreeningStatusResponse:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在（可能已重启清空）")
    return ScreeningStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        error=task["error"],
        results=task["result"],
    )
