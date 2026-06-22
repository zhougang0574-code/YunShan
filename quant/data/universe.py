"""股票池：截面选股的候选池来源。

提供三类候选池（均走 akshare 免费接口）：
- ``"all"``：全市场 A 股列表（``stock_zh_a_spot_em``）；
- ``"index:<代码>"``：指数成分股（``index_stock_cons``），如 ``index:000300`` 沪深300；
- ``"industry:<板块名>"``：行业板块成分股（``stock_board_industry_cons_em``）。

结果按天缓存（``daycache``），避免每次截面打分都重新拉全市场列表。akshare 各接口
返回列名不完全统一，这里用模糊匹配统一规整为 ``code / name`` 两列。
"""

import pandas as pd

from . import daycache

# 常用宽基指数（key -> 展示名）。指数成分股相对稳定，按天缓存足够。
KNOWN_INDICES = {
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000016": "上证50",
    "000688": "科创50",
    "399006": "创业板指",
}


def _normalize_code_name(df: pd.DataFrame) -> pd.DataFrame:
    """从 akshare 各接口的不统一列名里提取 code / name 两列。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=["code", "name"])
    code_col = next(
        (c for c in df.columns if "代码" in str(c) or str(c).lower() == "code"), None
    )
    name_col = next(
        (c for c in df.columns if "名称" in str(c) or str(c).lower() == "name"), None
    )
    if code_col is None:
        return pd.DataFrame(columns=["code", "name"])
    out = pd.DataFrame(
        {
            "code": df[code_col].astype(str).str.zfill(6),
            "name": df[name_col].astype(str) if name_col else "",
        }
    )
    return out.drop_duplicates("code").reset_index(drop=True)


def list_industries() -> list[str]:
    """返回东方财富行业板块名称列表（带缓存）。"""
    cached = daycache.load("universe_industries")
    if cached is not None:
        return cached["name"].tolist()
    try:
        import akshare as ak

        df = ak.stock_board_industry_name_em()
        names = df["板块名称"].astype(str).tolist()
        daycache.save("universe_industries", pd.DataFrame({"name": names}))
        return names
    except Exception:
        return []


def list_universes() -> dict:
    """列出可选股票池：全市场 + 宽基指数 + 行业板块。供前端下拉/后端 /universe。"""
    return {
        "all": {"key": "all", "label": "全市场 A 股"},
        "indices": [
            {"key": f"index:{code}", "label": f"{name}（{code}）"}
            for code, name in KNOWN_INDICES.items()
        ],
        "industries": [
            {"key": f"industry:{name}", "label": name} for name in list_industries()
        ],
    }


def _fetch_constituents(key: str) -> pd.DataFrame:
    import akshare as ak

    if key == "all":
        return _normalize_code_name(ak.stock_zh_a_spot_em())
    if key.startswith("index:"):
        return _normalize_code_name(ak.index_stock_cons(symbol=key.split(":", 1)[1]))
    if key.startswith("industry:"):
        return _normalize_code_name(
            ak.stock_board_industry_cons_em(symbol=key.split(":", 1)[1])
        )
    raise ValueError(f"未知股票池 key：{key}（应为 all / index:<代码> / industry:<板块名>）")


def get_constituents(key: str, use_cache: bool = True) -> pd.DataFrame:
    """取某个池子的成分股，返回含 ``code / name`` 两列的 DataFrame（按天缓存）。"""
    cache_key = f"universe_{key}"
    if use_cache:
        cached = daycache.load(cache_key)
        if cached is not None:
            return cached
    df = _fetch_constituents(key)
    if not df.empty:
        daycache.save(cache_key, df)
    return df
