// 后端 API 封装。开发环境经 vite 代理 /api -> http://127.0.0.1:8000。
const BASE = "/api";

export type ParamValue = number;
export type Params = Record<string, ParamValue>;

export interface StrategyInfo {
  name: string;
  param_space: Record<string, ParamValue[]>;
}

export interface BacktestSeries {
  dates: string[];
  close: number[];
  equity: number[];
  benchmark_equity: number[];
  position: number[];
}

export interface BacktestResponse {
  symbol: string;
  name: string;
  strategy: string;
  params: Params;
  stats: Record<string, number>;
  series: BacktestSeries;
}

export interface OptimizeResponse {
  symbol: string;
  strategy: string;
  metric: string;
  mode: string;
  results: Record<string, number | null>[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* 忽略解析失败，沿用状态码文案 */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export function getStrategies(): Promise<StrategyInfo[]> {
  return request<StrategyInfo[]>("/strategies");
}

export interface BacktestRequest {
  symbol: string;
  start: string;
  end: string;
  strategy: string;
  params: Params;
}

export function runBacktest(req: BacktestRequest): Promise<BacktestResponse> {
  return request<BacktestResponse>("/backtest", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export interface OptimizeRequest {
  symbol: string;
  start: string;
  end: string;
  strategy: string;
  metric: string;
  mode: "grid" | "walk_forward";
  n_splits?: number;
}

export function runOptimize(req: OptimizeRequest): Promise<OptimizeResponse> {
  return request<OptimizeResponse>("/optimize", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
