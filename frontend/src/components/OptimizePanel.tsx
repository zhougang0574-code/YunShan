import ReactECharts from "echarts-for-react";
import { OptimizeResponse } from "../api/client";

interface Props {
  data: OptimizeResponse;
  paramKeys: string[];
}

function formatCell(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(3);
}

export default function OptimizePanel({ data, paramKeys }: Props) {
  if (!data.results.length) return <p className="muted">无有效参数组合。</p>;

  const columns = Object.keys(data.results[0]);
  const showHeatmap = data.mode === "grid" && paramKeys.length === 2;

  return (
    <div>
      {showHeatmap && <Heatmap data={data} paramKeys={paramKeys} />}
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.results.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{formatCell(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Heatmap({ data, paramKeys }: Props) {
  const [pY, pX] = paramKeys;
  const xVals = [...new Set(data.results.map((r) => r[pX]))].sort(
    (a, b) => Number(a) - Number(b)
  );
  const yVals = [...new Set(data.results.map((r) => r[pY]))].sort(
    (a, b) => Number(a) - Number(b)
  );
  const points = data.results
    .map((r) => {
      const xi = xVals.indexOf(r[pX]);
      const yi = yVals.indexOf(r[pY]);
      const v = r[data.metric];
      return v === null ? null : [xi, yi, v];
    })
    .filter((p): p is number[] => p !== null);

  const values = points.map((p) => p[2]);
  const option = {
    title: {
      text: `${pY} × ${pX} 的 ${data.metric}`,
      left: "center",
      textStyle: { fontSize: 13 },
    },
    tooltip: {
      formatter: (p: { data: number[] }) =>
        `${pY}=${yVals[p.data[1]]}, ${pX}=${xVals[p.data[0]]}<br/>${data.metric}=${p.data[2].toFixed(3)}`,
    },
    grid: { left: 70, right: 20, top: 40, bottom: 50 },
    xAxis: { type: "category", data: xVals.map(String), name: pX },
    yAxis: { type: "category", data: yVals.map(String), name: pY },
    visualMap: {
      min: Math.min(...values),
      max: Math.max(...values),
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#14794a", "#f7e463", "#c0392b"] },
    },
    series: [
      {
        type: "heatmap",
        data: points,
        label: { show: true, formatter: (p: { data: number[] }) => p.data[2].toFixed(2) },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}
