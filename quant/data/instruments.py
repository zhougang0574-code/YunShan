"""标的类型与交易所判别（按代码前缀）。

集中处理「这是个股还是基金/ETF」「属于哪个交易所」，供数据层 / 报价 / 名称等共用，
避免各处各写一份前缀规则。仅覆盖 A 股常见场内品种，足够本项目使用。
"""


def market(symbol: str) -> str:
    """交易所前缀：sh（沪）/ sz（深）/ bj（北）。

    沪市：6xxxxx 股票、688xxx 科创板、9xxxxx B股、5xxxxx 基金/ETF；
    北市：4xxxxx / 8xxxxx；
    其余（0/2/3 股票、15xxxx/16xxxx 基金/ETF）归深市。
    """
    s = symbol.strip()
    if s.startswith(("6", "9", "5")):
        return "sh"
    if s.startswith(("4", "8")):
        return "bj"
    return "sz"


def is_fund(symbol: str) -> bool:
    """是否为场内基金/ETF/LOF：沪市 5xxxxx，深市 15xxxx / 16xxxx。"""
    s = symbol.strip()
    return s.startswith("5") or s.startswith(("15", "16"))
