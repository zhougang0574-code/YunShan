"""FastAPI 应用入口。

一个进程同时提供两样东西：

* ``/api/*``  —— 数据 / 策略 / 回测 / 参数寻优 等 REST 接口。
* ``/*``      —— 打包后的 React 前端（``frontend/dist``），含 SPA 路由回退。

本地一键启动：``py -3 run.py``（会自动构建前端再起服务）。
仅起后端：``uvicorn backend.main:app --reload``，交互式文档在 /docs。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .routers import (
    ai,
    auth,
    backtest,
    catalog,
    data,
    experiments,
    favorites,
    leaders,
    optimize,
    paper,
    quotes,
    screening,
    strategies,
    symbols,
    universe,
)

# 前端构建产物目录（npm run build 输出）。
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(
    title="YunShan 量化回测 API",
    version="0.1.0",
    description="数据 / 策略 / 回测 / 参数寻优 的 REST 接口，供 React 前端调用。",
)

# 允许本地 React 开发服务器（npm run dev，端口 5173）跨域访问。
# 生产/一键模式下前后端同源，CORS 不会被触发，留着只为兼容纯 dev 调试。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有业务接口统一挂到 /api 前缀下，给前端静态文件腾出根路径。
for _router in (
    strategies.router,
    data.router,
    backtest.router,
    optimize.router,
    universe.router,
    screening.router,
    leaders.router,
    quotes.router,
    symbols.router,
    experiments.router,
    auth.router,
    favorites.router,
    catalog.router,
    paper.router,
    ai.router,
):
    app.include_router(_router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


# ---- 前端静态托管 ----
# 只有在前端已构建（存在 dist）时才挂载，否则纯后端模式照常用 /docs 调试。
if _FRONTEND_DIST.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """非 /api 的 GET：命中真实文件就返回，否则回退到 index.html。

        这样 react-router 的前端路由（/screening、/stock、/experiments 等）
        在直接刷新或带路径访问时也能正常加载。
        """
        # 未匹配到任何 API 路由的 /api 请求应当是 404，而不是回退成 HTML 页面。
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
