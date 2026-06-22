"""FastAPI 依赖：从 Authorization: Bearer <token> 解析当前登录用户。"""

from fastapi import Depends, Header, HTTPException

from quant import users


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """要求请求带有效 token，返回当前用户 {id, username}；否则 401。"""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = users.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


CurrentUser = Depends(get_current_user)
