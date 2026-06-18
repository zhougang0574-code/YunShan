"""全局配置：数据目录、交易成本默认值、数据源参数。

集中放置可调参数，避免散落在各模块里硬编码。
"""

import os
import pathlib

# 项目根目录与本地数据缓存目录
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---- 数据源直连（彻底无视本地代理）----
# 行情源 eastmoney/sina 都是国内站点，应直连；本项目也只访问国内行情源 + 本机服务，
# 不需要任何 HTTP 代理。而本机代理（如 Clash 127.0.0.1:7890）一旦未运行或配置异常，
# 会导致 ProxyError / RemoteDisconnected。因此默认在**本进程内**清除代理环境变量，
# 让所有请求直连——这不影响系统全局代理，只作用于运行本程序的进程。
# 若你确实要让本程序走代理，把 IGNORE_PROXY 改成 False。
IGNORE_PROXY = True

_PROXY_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
)


def _disable_proxy_in_process() -> None:
    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    # 兜底：个别库即便无代理变量仍会查询，显式声明"全部不走代理"
    os.environ["no_proxy"] = "*"
    os.environ["NO_PROXY"] = "*"


if IGNORE_PROXY:
    _disable_proxy_in_process()

# ---- 数据源 ----
# akshare 拉取的复权方式默认值："qfq"(前复权)/"hfq"(后复权)/""(不复权)
DEFAULT_ADJUST = "qfq"
# akshare 请求失败时的重试次数与退避秒数（东财偶发断连，多试几次成功率更高）
FETCH_MAX_RETRIES = 5
FETCH_RETRY_BACKOFF = 1.5

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
