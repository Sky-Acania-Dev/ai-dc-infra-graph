from __future__ import annotations

from enum import StrEnum

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field


class UserRole(StrEnum):
    MANAGER = "manager"
    EDITOR = "editor"
    VIEWER = "viewer"


class AuthUser(BaseModel):
    uid: str
    display_name: str
    role: UserRole
    is_dev_default: bool = False


class UserAuthRecord(BaseModel):
    uid: str
    display_name: str
    role: UserRole


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class PendingChange(BaseModel):
    uid: str
    requested_by: str
    target: str
    action: str
    status: str = "pending"
    payload: dict[str, object] = Field(default_factory=dict)


router = APIRouter(prefix="/auth", tags=["auth"])

_USERS: dict[str, UserAuthRecord] = {
    "dev": UserAuthRecord(uid="dev", display_name="Developer", role=UserRole.MANAGER),
}
_PENDING_CHANGES: list[PendingChange] = []


@router.get("/me", response_model=AuthUser)
def current_user(
    x_user_uid: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
) -> AuthUser:
    if x_user_uid and x_user_uid in _USERS:
        user = _USERS[x_user_uid]
        return AuthUser(uid=user.uid, display_name=user.display_name, role=user.role)

    if x_user_role:
        return AuthUser(
            uid=x_user_uid or "header-user",
            display_name=x_user_uid or "Header User",
            role=UserRole(x_user_role),
        )

    return AuthUser(uid="dev", display_name="Developer", role=UserRole.MANAGER, is_dev_default=True)


@router.get("/users", response_model=list[UserAuthRecord])
def list_users(user: AuthUser = Depends(current_user)) -> list[UserAuthRecord]:
    require_manager(user)
    return sorted(_USERS.values(), key=lambda item: item.uid)


@router.patch("/users/{user_uid}", response_model=UserAuthRecord)
def update_user_role(
    user_uid: str,
    request: UpdateUserRoleRequest,
    user: AuthUser = Depends(current_user),
) -> UserAuthRecord:
    require_manager(user)
    existing = _USERS.get(user_uid)
    if existing is None:
        existing = UserAuthRecord(uid=user_uid, display_name=user_uid, role=request.role)
    else:
        existing.role = request.role
    _USERS[user_uid] = existing
    return existing


@router.get("/pending-changes", response_model=list[PendingChange])
def list_pending_changes(user: AuthUser = Depends(current_user)) -> list[PendingChange]:
    require_manager(user)
    return _PENDING_CHANGES


def require_editor(user: AuthUser) -> None:
    if user.role not in {UserRole.MANAGER, UserRole.EDITOR}:
        raise HTTPException(status_code=403, detail="Editor or manager role is required.")


def require_manager(user: AuthUser) -> None:
    if user.role != UserRole.MANAGER:
        raise HTTPException(status_code=403, detail="Manager role is required.")
