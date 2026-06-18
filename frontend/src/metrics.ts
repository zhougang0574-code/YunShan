// 指标的展示名、格式化、评级规则与「人话点评」。
// 每张卡片自带：彩色评级徽章(好/中/差) + 一句大白话，无需悬停即可看懂；
// 详细解释仍保留在问号 tooltip 里供深究。

export type MetricFormat = "pct" | "ratio" | "int";
export type Rating = "good" | "ok" | "bad" | "neutral";

export interface MetricMeta {
  key: string;
  label: string;
  format: MetricFormat;
  help: string; // 问号悬停的详细解释
  rate: (v: number) => Rating; // 按阈值自动评级
  note: (v: number) => string; // 结合数值的人话点评
}

export const RATING_BADGE: Record<Rating, { emoji: string; text: string }> = {
  good: { emoji: "🟢", text: "不错" },
  ok: { emoji: "🟡", text: "一般" },
  bad: { emoji: "🔴", text: "偏差" },
  neutral: { emoji: "⚪", text: "参考" },
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

// 主面板展示的指标（顺序即展示顺序）
export const METRIC_CARDS: MetricMeta[] = [
  {
    key: "annualized_return",
    label: "年化收益率",
    format: "pct",
    help: "把整段收益折算成平均每年涨多少。越高越好，但必须结合风险一起看。",
    rate: (v) => (v < 0 ? "bad" : v < 0.1 ? "ok" : "good"),
    note: (v) => (v >= 0 ? `平均每年赚 ${pct(v)}` : `平均每年亏 ${pct(-v)}`),
  },
  {
    key: "excess_return",
    label: "超额收益(vs买入持有)",
    format: "pct",
    help: "策略年化 − 一直满仓不动的年化。>0 才说明策略真有用，否则不如买了就拿着。",
    rate: (v) => (v < 0 ? "bad" : v < 0.03 ? "ok" : "good"),
    note: (v) =>
      v >= 0 ? `比一直拿着不动多赚 ${pct(v)}` : `还不如一直拿着，少赚 ${pct(-v)}`,
  },
  {
    key: "max_drawdown",
    label: "最大回撤",
    format: "pct",
    help: "从最高点跌到之后最低点的最大跌幅（负数）。越接近 0 越好，代表最惨时账户缩水多少。",
    rate: (v) => (v >= -0.1 ? "good" : v >= -0.3 ? "ok" : "bad"),
    note: (v) => `最惨时账户从高点缩水 ${pct(-v)}`,
  },
  {
    key: "sharpe_ratio",
    label: "夏普比率",
    format: "ratio",
    help: "每承担一单位总波动换来的超额收益。粗略：<0.5 偏差，0.5~1.5 一般，>1.5 不错，<0 亏钱。",
    rate: (v) => (v < 0.5 ? "bad" : v < 1.5 ? "ok" : "good"),
    note: (v) =>
      v < 0 ? "承担了波动却没赚到钱" : "每冒一份波动换来的回报，越高越划算",
  },
  {
    key: "sortino_ratio",
    label: "Sortino",
    format: "ratio",
    help: "类似夏普，但只把下跌波动算作风险，更贴近真实感受。越高越好。",
    rate: (v) => (v < 0.5 ? "bad" : v < 1.5 ? "ok" : "good"),
    note: () => "只看下跌风险时的划算程度，越高越好",
  },
  {
    key: "calmar_ratio",
    label: "Calmar",
    format: "ratio",
    help: "年化收益 ÷ 最大回撤。衡量冒着最惨回撤的风险能换多少年化，>1 算不错。",
    rate: (v) => (v < 0.5 ? "bad" : v < 1 ? "ok" : "good"),
    note: () => "用最惨回撤衡量的性价比，>1 较好",
  },
  {
    key: "trade_win_rate",
    label: "交易胜率",
    format: "pct",
    help: "每一笔完整买卖中盈利的占比。高不一定好：趋势策略常靠少数大赚覆盖多数小亏。",
    rate: () => "neutral",
    note: (v) => `每 10 笔约 ${Math.round(v * 10)} 笔赚钱（高低都可能赚钱）`,
  },
  {
    key: "total_trades",
    label: "交易笔数",
    format: "int",
    help: "回测期间完整买卖的次数。太少（2~3 笔）则胜率/夏普等没有统计意义。",
    rate: (v) => (v < 5 ? "ok" : "neutral"),
    note: (v) =>
      v < 5 ? `只有 ${Math.round(v)} 笔，样本太少、结论别太当真` : `共 ${Math.round(v)} 笔交易`,
  },
];

export function formatMetric(value: number | undefined, format: MetricFormat): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  switch (format) {
    case "pct":
      return `${(value * 100).toFixed(2)}%`;
    case "ratio":
      return value.toFixed(2);
    case "int":
      return String(Math.round(value));
  }
}
