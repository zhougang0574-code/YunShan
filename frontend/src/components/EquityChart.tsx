import ReactECharts from "echarts-for-react";
import { BacktestSeries } from "../api/client";

export default function EquityChart({ series }: { series: BacktestSeries }) {
  const option = {
    title: { text: "权益曲线", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: series.dates },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: "策略净值",
        type: "line",
        showSymbol: false,
        data: series.equity,
        lineStyle: { color: "#2563eb" },
      },
      {
        name: "买入持有基准",
        type: "line",
        showSymbol: false,
        data: series.benchmark_equity,
        lineStyle: { color: "#9aa5b1", type: "dashed" },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}
