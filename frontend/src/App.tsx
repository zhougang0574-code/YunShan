import { useEffect, useMemo, useState } from "react";
import {
  BacktestResponse,
  getStrategies,
  OptimizeResponse,
  Params,
  runBacktest,
  runOptimize,
  StrategyInfo,
} from "./api/client";
import EquityChart from "./components/EquityChart";
import MetricCard from "./components/MetricCard";
import OptimizePanel from "./components/OptimizePanel";
import PriceSignalChart from "./components/PriceSignalChart";
import { METRIC_CARDS } from "./metrics";

const OPT_METRICS = [
  "sharpe_ratio",
  "annualized_return",
  "calmar_ratio",
  "sortino_ratio",
];

export default function App() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [symbol, setSymbol] = useState("000001");
  const [start, setStart] = useState("2022-01-01");
  const [end, setEnd] = useState("2023-12-31");
  const [strategyName, setStrategyName] = useState("");
  const [params, setParams] = useState<Params>({});
  const [optMetric, setOptMetric] = useState("sharpe_ratio");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [optResult, setOptResult] = useState<OptimizeResponse | null>(null);

  const current = useMemo(
    () => strategies.find((s) => s.name === strategyName),
    [strategies, strategyName]
  );

  // 加载策略列表
  useEffect(() => {
    getStrategies()
      .then((list) => {
        setStrategies(list);
        if (list.length) selectStrategy(list[0]);
      })
      .catch((e) => setError(`无法加载策略列表：${e.message}（后端启动了吗？）`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectStrategy(s: StrategyInfo) {
    setStrategyName(s.name);
    // 默认参数取每个参数候选的首值
    const init: Params = {};
    for (const [k, candidates] of Object.entries(s.param_space)) {
      init[k] = candidates[0];
    }
    setParams(init);
  }

  async function handleRun() {
    setLoading(true);
    setError("");
    setOptResult(null);
    try {
      const res = await runBacktest({ symbol, start, end, strategy: strategyName, params });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleOptimize(mode: "grid" | "walk_forward") {
    setLoading(true);
    setError("");
    try {
      const res = await runOptimize({
        symbol,
        start,
        end,
        strategy: strategyName,
        metric: optMetric,
        mode,
        n_splits: 4,
      });
      setOptResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>YunShan 量化回测</h1>

        <label>股票代码</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />

        <label>开始日期</label>
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />

        <label>结束日期</label>
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />

        <label>策略</label>
        <select
          value={strategyName}
          onChange={(e) => {
            const s = strategies.find((x) => x.name === e.target.value);
            if (s) selectStrategy(s);
          }}
        >
          {strategies.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>

        {current &&
          Object.keys(current.param_space).map((p) => (
            <div key={p}>
              <label>{p}</label>
              <input
                type="number"
                value={params[p] ?? ""}
                step="any"
                onChange={(e) =>
                  setParams({ ...params, [p]: Number(e.target.value) })
                }
              />
            </div>
          ))}

        <button onClick={handleRun} disabled={loading || !strategyName}>
          {loading ? "运行中…" : "运行回测"}
        </button>

        <label>寻优目标指标</label>
        <select value={optMetric} onChange={(e) => setOptMetric(e.target.value)}>
          {OPT_METRICS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button
          className="secondary"
          onClick={() => handleOptimize("grid")}
          disabled={loading || !strategyName}
        >
          网格寻优
        </button>
        <button
          className="secondary"
          onClick={() => handleOptimize("walk_forward")}
          disabled={loading || !strategyName}
        >
          走动检验
        </button>
      </aside>

      <main className="main">
        {error && <div className="error">{error}</div>}

        {!result && !error && (
          <p className="muted">在左侧设置参数后点击「运行回测」。</p>
        )}

        {result && (
          <>
            <div className="cards">
              {METRIC_CARDS.map((m) => (
                <MetricCard key={m.key} meta={m} value={result.stats[m.key]} />
              ))}
            </div>
            <div className="panel">
              <PriceSignalChart series={result.series} />
            </div>
            <div className="panel">
              <EquityChart series={result.series} />
            </div>
          </>
        )}

        {optResult && (
          <div className="panel">
            <h3>
              参数{optResult.mode === "grid" ? "网格寻优" : "走动检验"}（目标：
              {optResult.metric}）
            </h3>
            <OptimizePanel
              data={optResult}
              paramKeys={current ? Object.keys(current.param_space) : []}
            />
          </div>
        )}
      </main>
    </div>
  );
}
