import ReactECharts from "echarts-for-react";
import { BacktestSeries } from "../api/client";

export default function PriceSignalChart({ series }: { series: BacktestSeries }) {
  // 持仓区间：仓位>0 的日子标在收盘价上，直观展示策略何时在场内。
  const holding = series.close.map((c, i) => (series.position[i] > 0 ? c : null));
  const option = {
    title: { text: "价格与持仓信号", left: "center", textStyle: { fontSize: 14 } },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0 },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: series.dates },
    yAxis: { type: "value", scale: true },
    series: [
      {
        name: "收盘价",
        type: "line",
        showSymbol: false,
        data: series.close,
        lineStyle: { color: "#334e68" },
      },
      {
        name: "持仓区间",
        type: "scatter",
        symbolSize: 4,
        data: holding,
        itemStyle: { color: "#c0392b" },
      },
    ],
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}
