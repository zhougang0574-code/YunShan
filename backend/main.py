"""FastAPI 应用入口。

启动：``uvicorn backend.main:app --reload``
交互式文档：http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import backtest, data, optimize, strategies

app = FastAPI(
    title="YunShan 量化回测 API",
    version="0.1.0",
    description="数据 / 策略 / 回测 / 参数寻优 的 REST 接口，供 React 前端调用。",
)

# 允许本地 React 开发服务器跨域访问
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

app.include_router(strategies.router)
app.include_router(data.router)
app.include_router(backtest.router)
app.include_router(optimize.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
