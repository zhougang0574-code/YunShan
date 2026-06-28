// 后端 API 封装。开发环境经 vite 代理 /api -> http://127.0.0.1:8000。
const BASE = "/api";

// ---- 登录 token（存 localStorage，随请求带 Authorization 头）----
const TOKEN_KEY = "yunshan_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---- 记住的登录凭据（“记住我”：登录页自动填充，退出后也能一键再登）----
// 注意：密码以明文存在 localStorage，仅适合个人/可信浏览器。不勾选则不存。
const CREDS_KEY = "yunshan_creds";

export interface SavedCreds {
  username: string;
  password: string;
}

export function getSavedCreds(): SavedCreds | null {
  const raw = localStorage.getItem(CREDS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SavedCreds;
  } catch {
    return null;
  }
}
export function saveCreds(username: string, password: string): void {
  localStorage.setItem(CREDS_KEY, JSON.stringify({ username, password }));
}
export function clearCreds(): void {
  localStorage.removeItem(CREDS_KEY);
}

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

export interface MonteCarlo {
  observed_sharpe: number;
  null_mean_sharpe: number;
  p_value: number;
  n_iter: number;
}

export interface Robustness {
  sr_observed: number;
  expected_max_sharpe: number;
  n_trials: number;
  deflated_sharpe_ratio: number | null;
  monte_carlo: MonteCarlo;
  best_params: Params;
}

export interface OptimizeResponse {
  symbol: string;
  strategy: string;
  metric: string;
  mode: string;
  results: Record<string, number | null>[];
  robustness: Robustness | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) || {}),
  };
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    // token 失效：清掉并广播，App 据此回到登录页
    if (resp.status === 401 && token) {
      clearToken();
      window.dispatchEvent(new Event("auth:logout"));
    }
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
  engine?: "vectorized" | "event";
  stop_loss?: number | null;
  take_profit?: number | null;
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

// ---- 股票池 / 截面选股 ----

export interface UniverseOption {
  key: string;
  label: string;
}
export interface UniverseList {
  all: UniverseOption;
  indices: UniverseOption[];
  industries: UniverseOption[];
}

export function getUniverses(): Promise<UniverseList> {
  return request<UniverseList>("/universe");
}

export interface FactorInfo {
  label: string;
  direction: "low" | "high";
  kind: "fundamental" | "technical";
}

export function getFactors(): Promise<Record<string, FactorInfo>> {
  return request<Record<string, FactorInfo>>("/screening/factors");
}

export interface FactorSpec {
  key: string;
  weight: number;
}
export interface ScreeningRequest {
  universe_key: string;
  factors: FactorSpec[];
  top_n: number;
  max_symbols: number;
  lookback_days: number;
}
export interface ScreeningStatus {
  task_id: string;
  status: "pending" | "running" | "done" | "error";
  progress: number;
  error: string | null;
  results: Record<string, number | string | null>[] | null;
}

export function submitScreening(req: ScreeningRequest): Promise<{ task_id: string }> {
  return request<{ task_id: string }>("/screening", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getScreeningStatus(taskId: string): Promise<ScreeningStatus> {
  return request<ScreeningStatus>(`/screening/${taskId}`);
}

// ---- 板块当月涨幅榜（龙头股）----

export interface LeadersRequest {
  industries: string[];
  top_n: number;
  max_symbols: number;
}

// 任务状态结构与截面选股一致（results 列：rank/code/name/industry/month_pct/...）。
export function submitLeaders(req: LeadersRequest): Promise<{ task_id: string }> {
  return request<{ task_id: string }>("/leaders", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export function getLeadersStatus(taskId: string): Promise<ScreeningStatus> {
  return request<ScreeningStatus>(`/leaders/${taskId}`);
}

// ---- 个股详情 / 报价 / 信号 / 另类数据 ----

export interface Quote {
  symbol: string;
  name?: string;
  price: number | null;
  pct_chg: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  prev_close: number | null;
  volume: number | null;
  amount: number | null;
}

export function getQuote(symbol: string): Promise<Quote> {
  return request<Quote>(`/quotes/${symbol}`);
}

export interface IntradayPoint {
  date?: string;
  time: string;
  price: number | null;
  volume: number | null;
}

export function getIntraday(symbol: string): Promise<IntradayPoint[]> {
  return request<IntradayPoint[]>(`/quotes/${symbol}/intraday`);
}

export interface SignalTag {
  category: "technical" | "fundamental" | "altdata";
  level: "good" | "warn" | "bad" | "info";
  text: string;
}

export function getSignals(symbol: string): Promise<{ symbol: string; tags: SignalTag[] }> {
  return request<{ symbol: string; tags: SignalTag[] }>(`/symbols/${symbol}/signals`);
}

export function getFundamentals(symbol: string): Promise<Record<string, number | null>> {
  return request<Record<string, number | null>>(`/symbols/${symbol}/fundamentals`);
}

export interface AltData {
  name: string;
  fund_flow: Record<string, number | string | null>;
  north_hold: Record<string, number | string | null>;
}

export function getAltData(symbol: string): Promise<AltData> {
  return request<AltData>(`/symbols/${symbol}/altdata`);
}

// ---- 实验记录 ----

export interface Experiment {
  id: number;
  ts: string;
  kind: string;
  symbol: string | null;
  strategy: string | null;
  params: Record<string, unknown>;
  summary: Record<string, unknown>;
}

export function getExperiments(params?: {
  kind?: string;
  symbol?: string;
  strategy?: string;
}): Promise<Experiment[]> {
  const q = new URLSearchParams();
  if (params?.kind) q.set("kind", params.kind);
  if (params?.symbol) q.set("symbol", params.symbol);
  if (params?.strategy) q.set("strategy", params.strategy);
  const qs = q.toString();
  return request<Experiment[]>(`/experiments${qs ? `?${qs}` : ""}`);
}

// ---- 登录 / 注册 / 用户 ----

export interface AuthResult {
  token: string;
  username: string;
}

export function register(username: string, password: string): Promise<AuthResult> {
  return request<AuthResult>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function login(username: string, password: string): Promise<AuthResult> {
  return request<AuthResult>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getMe(): Promise<{ username: string }> {
  return request<{ username: string }>("/auth/me");
}

export function logout(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/auth/logout", { method: "POST" });
}

// ---- 收藏 ----

export interface Favorite {
  symbol: string;
  name: string;
  created_at: string;
}

export function getFavorites(): Promise<Favorite[]> {
  return request<Favorite[]>("/favorites");
}

export function addFavorite(symbol: string): Promise<Favorite[]> {
  return request<Favorite[]>("/favorites", {
    method: "POST",
    body: JSON.stringify({ symbol }),
  });
}

export function removeFavorite(symbol: string): Promise<Favorite[]> {
  return request<Favorite[]>(`/favorites/${symbol}`, { method: "DELETE" });
}

// ---- 标的库（全量浏览：股票 / 基金）----

export interface CatalogItem {
  symbol: string;
  name: string;
}
export interface CatalogPage {
  total: number;
  page: number;
  page_size: number;
  items: CatalogItem[];
}

export function getCatalog(
  kind: "stock" | "fund",
  query: string,
  page: number,
  pageSize: number
): Promise<CatalogPage> {
  const q = new URLSearchParams({
    kind,
    query,
    page: String(page),
    page_size: String(pageSize),
  });
  return request<CatalogPage>(`/catalog?${q.toString()}`);
}

// ---- 模拟交易 ----

export interface PaperPosition {
  symbol: string;
  name: string;
  shares: number;
  avg_cost: number;
  price: number | null;
  market_value: number;
  cost: number;
  unrealized: number;
  unrealized_pct: number;
}

export interface PaperAccount {
  cash: number;
  initial: number;
  market_value: number;
  total: number;
  profit: number;
  profit_pct: number;
  positions: PaperPosition[];
}

export interface PaperTrade {
  ts: string;
  symbol: string;
  name: string | null;
  side: "buy" | "sell";
  price: number;
  shares: number;
  amount: number;
  fee: number;
  realized: number;
}

export interface EquityPoint {
  date: string;
  total: number;
}

export function getPaperAccount(): Promise<PaperAccount> {
  return request<PaperAccount>("/paper/account");
}

export function placePaperOrder(
  symbol: string,
  side: "buy" | "sell",
  shares: number
): Promise<{ fill: Record<string, number | string>; account: PaperAccount }> {
  return request("/paper/order", {
    method: "POST",
    body: JSON.stringify({ symbol, side, shares }),
  });
}

export function getPaperTrades(): Promise<PaperTrade[]> {
  return request<PaperTrade[]>("/paper/trades");
}

export function getPaperEquity(): Promise<EquityPoint[]> {
  return request<EquityPoint[]>("/paper/equity");
}

export function resetPaperAccount(initial?: number): Promise<PaperAccount> {
  return request<PaperAccount>("/paper/reset", {
    method: "POST",
    body: JSON.stringify({ initial: initial ?? null }),
  });
}
