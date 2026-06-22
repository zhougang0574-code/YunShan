import { Robustness } from "../api/client";

// 把稳健性数字翻译成"这结果可信吗"的大白话。
function dsrVerdict(dsr: number | null): { text: string; cls: string } {
  if (dsr === null) return { text: "样本太短，无法判定", cls: "badge-neutral" };
  if (dsr >= 0.95) return { text: "很可能是真实 alpha", cls: "badge-bad" }; // bad=绿(沿用配色)
  if (dsr >= 0.8) return { text: "较可信", cls: "badge-ok" };
  return { text: "可能只是寻优运气", cls: "badge-good" }; // good=红
}

function mcVerdict(p: number): { text: string; cls: string } {
  if (p < 0.05) return { text: "显著优于随机择时", cls: "badge-bad" };
  if (p < 0.2) return { text: "略优于随机", cls: "badge-ok" };
  return { text: "与随机择时无异", cls: "badge-good" };
}

export default function RobustnessPanel({ data }: { data: Robustness }) {
  const dsr = data.deflated_sharpe_ratio;
  const dv = dsrVerdict(dsr);
  const mv = mcVerdict(data.monte_carlo.p_value);

  return (
    <div>
      <h3>
        稳健性检验
        <span className="help" title="寻优试了很多组参数，最高的 Sharpe 天然被选择偏差抬高。下面两个指标帮你判断该结果是真本事还是运气/过拟合。">
          ?
        </span>
      </h3>
      <table>
        <tbody>
          <tr>
            <td>尝试参数组合数</td>
            <td>{data.n_trials}</td>
            <td className="muted">试得越多，越要警惕过拟合</td>
          </tr>
          <tr>
            <td>观测 Sharpe（最优组）</td>
            <td>{data.sr_observed.toFixed(2)}</td>
            <td className="muted">寻优挑出的最好那组的年化夏普</td>
          </tr>
          <tr>
            <td>随机期望最高 Sharpe</td>
            <td>{data.expected_max_sharpe.toFixed(2)}</td>
            <td className="muted">纯靠运气、试这么多次也能达到的夏普</td>
          </tr>
          <tr>
            <td>
              Deflated Sharpe
              <span className="help" title="扣除多重尝试水分后，真实 Sharpe>0 的概率。越接近 1 越可信。">
                ?
              </span>
            </td>
            <td>{dsr === null ? "—" : `${(dsr * 100).toFixed(1)}%`}</td>
            <td>
              <span className={`badge ${dv.cls}`}>{dv.text}</span>
            </td>
          </tr>
          <tr>
            <td>
              蒙特卡洛 p 值
              <span className="help" title="随机打乱仓位与收益的对应关系重算夏普，原策略胜过随机的程度。p 越小越可信。">
                ?
              </span>
            </td>
            <td>{data.monte_carlo.p_value.toFixed(3)}</td>
            <td>
              <span className={`badge ${mv.cls}`}>{mv.text}</span>
            </td>
          </tr>
        </tbody>
      </table>
      {data.best_params && (
        <p className="muted">
          最优参数：{Object.entries(data.best_params).map(([k, v]) => `${k}=${v}`).join("，")}
        </p>
      )}
    </div>
  );
}
