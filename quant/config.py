"""全局配置：数据目录、交易成本默认值、数据源参数。

集中放置可调参数，避免散落在各模块里硬编码。
"""

import os
import pathlib

# 项目根目录与本地数据缓存目录
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---- 数据源直连（绕过本地代理）----
# eastmoney / sina 等行情源都是国内站点，应直连。自动把它们加入 no_proxy，
# 避免本机代理（如未启动的 Clash 127.0.0.1:7890）拦截请求导致 ProxyError。
# 只影响这些数据主机，不改变其它主机的代理行为。
_DOMESTIC_DATA_HOSTS = [
    "eastmoney.com",
    "push2his.eastmoney.com",
    "push2.eastmoney.com",
    "sina.com.cn",
    "sinajs.cn",
    "hq.sinajs.cn",
]


def _bypass_proxy_for_data_hosts() -> None:
    for key in ("no_proxy", "NO_PROXY"):
        hosts = [h for h in os.environ.get(key, "").split(",") if h]
        for host in _DOMESTIC_DATA_HOSTS:
            if host not in hosts:
                hosts.append(host)
        os.environ[key] = ",".join(hosts)


_bypass_proxy_for_data_hosts()

# ---- 数据源 ----
# akshare 拉取的复权方式默认值："qfq"(前复权)/"hfq"(后复权)/""(不复权)
DEFAULT_ADJUST = "qfq"
# akshare 请求失败时的重试次数与退避秒数
FETCH_MAX_RETRIES = 3
FETCH_RETRY_BACKOFF = 1.0

# ---- 交易成本默认值（A股）----
# 佣金费率（双边），万分之几，含最低 5 元由 costs 模块处理
COMMISSION_RATE = 0.00025
COMMISSION_MIN = 5.0
# 印花税（仅卖出收取）
STAMP_TAX_RATE = 0.0005
# 过户费（双边，沪深统一近似）
TRANSFER_FEE_RATE = 0.00001
# 滑点（按成交价的比例，双边）
SLIPPAGE_RATE = 0.0

# ---- 回测默认值 ----
INITIAL_CAPITAL = 100_000.0
TRADING_DAYS_PER_YEAR = 252
