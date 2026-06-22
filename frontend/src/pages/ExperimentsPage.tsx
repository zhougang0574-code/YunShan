import { Fragment, useEffect, useState } from "react";
import { Experiment, getExperiments } from "../api/client";

const KINDS = ["", "backtest", "optimize_grid", "optimize_walk_forward", "screening"];

export default function ExperimentsPage() {
  const [rows, setRows] = useState<Experiment[]>([]);
  const [kind, setKind] = useState("");
  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  function load() {
    setError("");
    getExperiments({ kind: kind || undefined, symbol: symbol || undefined })
      .then(setRows)
      .catch((e) => setError(e.message));
  }

  useEffect(load, [kind]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="app">
      <aside className="sidebar">
        <label>类型</label>
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k || "全部"}
            </option>
          ))}
        </select>
        <label>标的（可选）</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        <button onClick={load}>查询</button>
      </aside>

      <main className="main">
        <h1>历史记录</h1>
        {error && <div className="error">{error}</div>}
        {!rows.length && !error && <p className="muted">暂无记录。跑一次回测/寻优/选股后会出现在这里。</p>}

        {rows.length > 0 && (
          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>类型</th>
                  <th>标的</th>
                  <th>策略</th>
                  <th>关键结果</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <Fragment key={r.id}>
                    <tr className="clickable" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
                      <td>{r.ts.replace("T", " ")}</td>
                      <td>{r.kind}</td>
                      <td>{r.symbol || "—"}</td>
                      <td>{r.strategy || "—"}</td>
                      <td>{summaryBrief(r.summary)}</td>
                    </tr>
                    {expanded === r.id && (
                      <tr>
                        <td colSpan={5}>
                          <div className="detail-grid">
                            <div>
                              <strong>入参</strong>
                              <pre>{JSON.stringify(r.params, null, 2)}</pre>
                            </div>
                            <div>
                              <strong>结果</strong>
                              <pre>{JSON.stringify(r.summary, null, 2)}</pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

function summaryBrief(summary: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(summary)) {
    if (v == null) continue;
    parts.push(`${k}=${typeof v === "number" ? (v as number).toFixed(3) : v}`);
  }
  return parts.slice(0, 3).join("，") || "—";
}
