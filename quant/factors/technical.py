"""常用技术指标因子。

约定：输入含 close（部分含 high/low）的价格 DataFrame，返回与之对齐的 Series；
多输出指标（MACD/布林带）返回多列 DataFrame。所有计算只用历史数据，不引入未来值。
"""

import pandas as pd


def sma(price: pd.DataFrame, window: int = 20) -> pd.Series:
    """简单移动平均。"""
    return price["close"].rolling(window).mean()


def ema(price: pd.DataFrame, span: int = 20) -> pd.Series:
    """指数移动平均。"""
    return price["close"].ewm(span=span, adjust=False).mean()


def macd(
    price: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD：返回 dif / dea / hist 三列。"""
    close = price["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": hist})


def rsi(price: pd.DataFrame, window: int = 14) -> pd.Series:
    """相对强弱指标 RSI（Wilder 平滑），取值 0~100。"""
    delta = price["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def bollinger(
    price: pd.DataFrame, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """布林带：返回 mid / upper / lower 三列。"""
    mid = price["close"].rolling(window).mean()
    std = price["close"].rolling(window).std()
    return pd.DataFrame(
        {"mid": mid, "upper": mid + num_std * std, "lower": mid - num_std * std}
    )


def momentum(price: pd.DataFrame, window: int = 20) -> pd.Series:
    """动量：close 相对 window 日前的涨跌幅。"""
    return price["close"].pct_change(window)


def atr(price: pd.DataFrame, window: int = 14) -> pd.Series:
    """平均真实波幅 ATR（需要 high/low/close）。"""
    high, low, close = price["high"], price["low"], price["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / window, adjust=False).mean()
