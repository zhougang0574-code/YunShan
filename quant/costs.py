"""交易成本模型（A 股）。

涵盖佣金（双边、有最低收费）、印花税（仅卖出）、过户费（双边）、滑点（双边）。
既支持单笔成交计算（事件驱动引擎用），也支持按换手率向量化计算（向量化引擎用）。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config


@dataclass
class CostModel:
    commission_rate: float = config.COMMISSION_RATE
    commission_min: float = config.COMMISSION_MIN
    stamp_tax_rate: float = config.STAMP_TAX_RATE
    transfer_fee_rate: float = config.TRANSFER_FEE_RATE
    slippage_rate: float = config.SLIPPAGE_RATE

    def trade_cost(self, notional: float, side: str) -> float:
        """单笔成交成本。notional 为成交额（>0），side 为 "buy"/"sell"。"""
        notional = abs(notional)
        if notional == 0:
            return 0.0
        commission = max(notional * self.commission_rate, self.commission_min)
        transfer = notional * self.transfer_fee_rate
        slippage = notional * self.slippage_rate
        stamp = notional * self.stamp_tax_rate if side == "sell" else 0.0
        return commission + transfer + slippage + stamp

    def turnover_cost_rate(self, turnover: pd.Series) -> pd.Series:
        """按每日换手（仓位变化绝对值，0~1）估算当日成本占比。

        用于向量化引擎：turnover[t] = |position[t] - position[t-1]|，
        返回的成本率直接从当日策略收益中扣除。买卖各承担一半费率，
        卖出额外计印花税（近似按一半换手为卖出）。
        最低佣金在向量化口径下忽略（组合层面占比极小）。
        """
        buy_sell_rate = self.commission_rate + self.transfer_fee_rate + self.slippage_rate
        # turnover 同时含买入和卖出方向，印花税只对卖出方向收取
        rate = turnover * buy_sell_rate + turnover * self.stamp_tax_rate * 0.5
        return rate.fillna(0.0).astype(np.float64)
