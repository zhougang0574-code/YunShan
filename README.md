# YunShan 股票量化回测系统

研究型 A 股量化回测系统：数据 → 因子/策略 → 回测 → 业绩分析 → 可视化。
前后端分离架构，纯研究回测（不接实盘）。设计文档见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 架构

- `quant/` — 核心计算库（纯 Python）：数据/因子/策略/回测引擎/指标/参数寻优
- `backend/` — FastAPI 后端：把核心能力封装为 REST 接口
- `frontend/` — React + TypeScript + ECharts 前端
- `app.py` — Streamlit 快速验证入口（可选，单文件即可跑）
- `tests/` — pytest 测试

## 环境准备

```bash
# Python 依赖（项目根目录）
.venv/bin/pip install -r requirements.txt

# 前端依赖
cd frontend && npm install && cd ..
```

> 行情源（eastmoney/sina）是国内站点，代码已自动让它们直连、绕开本地代理
> （如 Clash 127.0.0.1:7890），无需手动 unset 代理。

## 启动（前后端联调）

需要开**两个终端**，都在项目根目录：

```bash
# 终端 1：启动后端 API（文档在 http://127.0.0.1:8000/docs）
.venv/bin/uvicorn backend.main:app --reload

# 终端 2：启动前端（浏览器打开 http://localhost:5173）
cd frontend && npm run dev
```

前端通过 `/api` 代理到后端，打开 `http://localhost:5173` 即可使用：
选股票/日期/策略 → 运行回测看指标卡（含问号说明）与图表 → 网格寻优/走动检验。

## 仅用 Streamlit 快速看（可选）

```bash
.venv/bin/streamlit run app.py
```

## 跑测试

```bash
.venv/bin/python -m pytest tests/ -v
```
