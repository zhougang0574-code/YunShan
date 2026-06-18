"""组合与资金管理。

为事件驱动引擎（Phase 4）和多标的组合提供账户抽象：现金、持仓、成交记录、
按市价估值的总权益。向量化引擎不直接依赖它，但二者共用同一套成本模型与口径。
"""

from dataclasses import dataclass, field

from .costs import CostModel


@dataclass
class Trade:
    date: object
    symbol: str
    side: str  # "buy" / "sell"
    shares: float
    price: float
    cost: float


@dataclass
class Portfolio:
    cash: float
    cost_model: CostModel = field(default_factory=CostModel)
    holdings: dict[str, float] = field(default_factory=dict)  # symbol -> shares
    trades: list[Trade] = field(default_factory=list)

    def buy(self, date, symbol: str, shares: float, price: float) -> None:
        notional = shares * price
        fee = self.cost_model.trade_cost(notional, "buy")
        self.cash -= notional + fee
        self.holdings[symbol] = self.holdings.get(symbol, 0.0) + shares
        self.trades.append(Trade(date, symbol, "buy", shares, price, fee))

    def sell(self, date, symbol: str, shares: float, price: float) -> None:
        notional = shares * price
        fee = self.cost_model.trade_cost(notional, "sell")
        self.cash += notional - fee
        self.holdings[symbol] = self.holdings.get(symbol, 0.0) - shares
        if abs(self.holdings[symbol]) < 1e-9:
            self.holdings.pop(symbol, None)
        self.trades.append(Trade(date, symbol, "sell", shares, price, fee))

    def equity(self, prices: dict[str, float]) -> float:
        """按当前市价估算总权益（现金 + 持仓市值）。"""
        market_value = sum(
            shares * prices.get(symbol, 0.0)
            for symbol, shares in self.holdings.items()
        )
        return self.cash + market_value
