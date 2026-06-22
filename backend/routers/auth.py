"""登录 / 注册 / 登出 / 当前用户。

简单的用户名+密码注册登录，登录后返回 token，前端带在 Authorization 头里。
"""

from fastapi import APIRouter, Header, HTTPException

from quant import users

from ..deps import CurrentUser
from ..schemas import AuthRequest, AuthResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(req: AuthRequest) -> AuthResponse:
    try:
        user = users.create_user(req.username, req.password)
    except users.UserExistsError:
        raise HTTPException(status_code=409, detail="用户名已被占用")
    token = users.create_token(user["id"])
    return AuthResponse(token=token, username=user["username"])


@router.post("/login", response_model=AuthResponse)
def login(req: AuthRequest) -> AuthResponse:
    user = users.verify_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = users.create_token(user["id"])
    return AuthResponse(token=token, username=user["username"])


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    """删除当前 token。无论 token 有效与否都返回 ok（幂等）。"""
    if authorization and authorization.lower().startswith("bearer "):
        users.delete_token(authorization[7:].strip())
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: dict = CurrentUser) -> MeResponse:
    return MeResponse(username=user["username"])
