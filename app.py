import datetime

import plotly.graph_objects as go
import streamlit as st

from quant import get_daily, metrics, optimize, run_backtest
from quant.strategies import get_strategy, list_strategies

st.set_page_config(page_title="YunShan 量化回测", layout="wide")
st.title("YunShan 股票量化回测")

strategy_spaces = list_strategies()

with st.sidebar:
    symbol = st.text_input("股票代码", value="000001")
    date_range = st.date_input(
        "日期范围",
        value=(datetime.date(2022, 1, 1), datetime.date.today()),
    )

    strategy_name = st.selectbox("策略", list(strategy_spaces))
    space = strategy_spaces[strategy_name]

    # 按所选策略的参数空间动态生成输入控件（默认取候选首值，类型自动推断）
    params: dict = {}
    for pname, candidates in space.items():
        first = candidates[0]
        if isinstance(first, int):
            params[pname] = int(
                st.number_input(pname, value=int(first), step=1)
            )
        else:
            params[pname] = float(
                st.number_input(pname, value=float(first))
            )

    run_clicked = st.button("运行回测")
    do_optimize = st.checkbox("同时做参数网格寻优")
    opt_metric = st.selectbox(
        "寻优目标指标",
        ["sharpe_ratio", "annualized_return", "calmar_ratio", "sortino_ratio"],
    )

if run_clicked:
    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.warning("请选择完整的日期范围")
        st.stop()

    start_date, end_date = date_range
    price = get_daily(symbol, str(start_date), str(end_date))

    if price.empty:
        st.warning("未获取到数据，请检查股票代码或日期范围")
        st.stop()

    strategy_cls = get_strategy(strategy_name)
    try:
        strategy = strategy_cls(**params)
    except (ValueError, TypeError) as err:
        st.warning(f"参数不合法：{err}")
        st.stop()

    signal = strategy.generate_signal(price)
    result = run_backtest(price, signal)
    stats = metrics.summarize(result)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("年化收益率", f"{stats['annualized_return']:.2%}")
    col2.metric("最大回撤", f"{stats['max_drawdown']:.2%}")
    col3.metric("夏普比率", f"{stats['sharpe_ratio']:.2f}")
    col4.metric("超额收益(vs买入持有)", f"{stats['excess_return']:.2%}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("交易胜率", f"{stats['trade_win_rate']:.2%}")
    col6.metric("Sortino", f"{stats['sortino_ratio']:.2f}")
    col7.metric("Calmar", f"{stats['calmar_ratio']:.2f}")
    col8.metric("交易笔数", f"{stats['total_trades']}")

    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(x=result.index, y=result["close"], name="收盘价"))
    price_fig.add_trace(
        go.Scatter(
            x=result.index,
            y=result["close"].where(result["position"] > 0),
            name="持仓区间",
            mode="markers",
            marker=dict(size=4, color="red"),
        )
    )
    price_fig.update_layout(title="价格与持仓信号", height=350)
    st.plotly_chart(price_fig, use_container_width=True)

    equity_fig = go.Figure()
    equity_fig.add_trace(go.Scatter(x=result.index, y=result["equity"], name="策略净值"))
    equity_fig.add_trace(
        go.Scatter(
            x=result.index,
            y=result["benchmark_equity"],
            name="买入持有基准",
            line=dict(dash="dash", color="gray"),
        )
    )
    equity_fig.update_layout(title="权益曲线", height=350)
    st.plotly_chart(equity_fig, use_container_width=True)

    st.dataframe(result.tail(20))

    if do_optimize:
        st.subheader(f"参数网格寻优（目标：{opt_metric}）")
        ranked = optimize.grid_search(
            price, strategy_cls, metric=opt_metric
        )
        if ranked.empty:
            st.info("无有效参数组合")
        else:
            st.dataframe(ranked)
            # 恰好两个参数时画热力图
            param_cols = list(space)
            if len(param_cols) == 2:
                pivot = ranked.pivot_table(
                    index=param_cols[0], columns=param_cols[1], values=opt_metric
                )
                heat = go.Figure(
                    go.Heatmap(
                        z=pivot.values,
                        x=pivot.columns.astype(str),
                        y=pivot.index.astype(str),
                        colorscale="RdYlGn",
                    )
                )
                heat.update_layout(
                    title=f"{param_cols[0]} × {param_cols[1]} 的 {opt_metric}",
                    height=350,
                )
                st.plotly_chart(heat, use_container_width=True)
else:
    st.info("在左侧设置参数后点击「运行回测」")
